import requests
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession
from pyrogram.errors import SessionPasswordNeeded
from telethon.errors import SessionPasswordNeededError

# 🔹 API Details
API_ID = 28049056
API_HASH = "1a301acbe312e760b4d0716fd3b8eab2"
BOT_TOKEN = "7589052839:AAGPMVeZpb63GEG_xXzQEua1q9ewfNzTg50"

# ✅ Pyrogram Client Initialization
app = Client("session_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 📌 Session Data Storage
session_data = {}

# 📌 Start Command
@app.on_message(filters.command(["start"]) & filters.private)
async def start(client, message):
    await message.reply(
        "**🤖 Welcome to Telegram Session Generator!**\n\n"
        "✨ **Pyrogram** और ⚡ **Telethon** सेशन बनाने के लिए बटन दबाएं।",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Pyrogram", callback_data="start_pyro"),
             InlineKeyboardButton("⚡ Telethon", callback_data="start_tele")]
        ])
    )

# 📌 Callback Query Handler
@app.on_callback_query(filters.regex(r"^start_"))
async def start_session(client, callback_query):
    session_type = "Pyrogram" if callback_query.data == "start_pyro" else "Telethon"
    chat_id = callback_query.message.chat.id
    session_data[chat_id] = {"type": session_type, "stage": "api_id"}

    await callback_query.message.edit_text(
        f"🔹 **{session_type} Session Setup शुरू हो रहा है...**\n\n"
        "📌 **API ID भेजें** (my.telegram.org से लें)।",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
    )

# 📌 Handle User Input
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
            await message.reply("❌ **गलत API ID! कृपया सही नंबर भेजें।**")

    elif stage == "api_hash":
        session["api_hash"] = message.text
        session["stage"] = "phone_number"
        await message.reply("📲 अब अपना **फ़ोन नंबर** भेजें (Example: +919876543210)")

    elif stage == "phone_number":
        session["phone_number"] = message.text
        await send_otp(client, message)

    elif stage == "otp":
        session["otp"] = message.text
        await validate_otp(client, message)

    elif stage == "2fa":
        session["password"] = message.text
        await validate_2fa(client, message)

# 📌 OTP भेजना (Send OTP)
async def send_otp(client, message):
    chat_id = message.chat.id
    session = session_data[chat_id]
    api_id, api_hash, phone = session["api_id"], session["api_hash"], session["phone_number"]

    if session["type"] == "Telethon":
        client_obj = TelegramClient(StringSession(), api_id, api_hash)
    else:
        client_obj = Client(":memory:", api_id, api_hash)

    await client_obj.connect()
    try:
        if session["type"] == "Telethon":
            session["code"] = await client_obj.send_code_request(phone)
        else:
            session["code"] = await client_obj.send_code(phone)

        session["client_obj"] = client_obj
        session["stage"] = "otp"

        await message.reply("🔢 **OTP भेजें** (Example: `12345`)।")
    except Exception as e:
        await message.reply(f"❌ **Error:** `{str(e)}`")
        del session_data[chat_id]

# 📌 OTP वेरिफाई करना
async def validate_otp(client, message):
    chat_id = message.chat.id
    session = session_data[chat_id]
    client_obj, phone, otp = session["client_obj"], session["phone_number"], session["otp"]

    try:
        if session["type"] == "Telethon":
            await client_obj.sign_in(phone, otp)
        else:
            await client_obj.sign_in(phone, session["code"].phone_code_hash, otp)

        await generate_session(client, message)

    except (SessionPasswordNeededError, SessionPasswordNeeded):
        session["stage"] = "2fa"
        await message.reply("🔐 **2FA पासवर्ड भेजें।**\n\nआपके अकाउंट में **Two-Step Verification (2FA)** ऑन है। कृपया अपना **पासवर्ड** भेजें।")

    except Exception as e:
        await message.reply(f"❌ **OTP Invalid:** `{str(e)}`")
        del session_data[chat_id]

# 📌 2FA पासवर्ड वेरिफाई करना
async def validate_2fa(client, message):
    chat_id = message.chat.id
    session = session_data[chat_id]
    client_obj, password = session["client_obj"], session["password"]

    try:
        if session["type"] == "Telethon":
            await client_obj.sign_in(password=password)
        else:
            await client_obj.check_password(password=password)

        await generate_session(client, message)

    except Exception as e:
        await message.reply(f"❌ **गलत 2FA पासवर्ड!** `{str(e)}`")
        del session_data[chat_id]

# 📌 Session String बनाना
async def generate_session(client, message):
    chat_id = message.chat.id
    session = session_data[chat_id]
    client_obj = session["client_obj"]

    if session["type"] == "Telethon":
        session_string = client_obj.session.save()
    else:
        session_string = await client_obj.export_session_string()

    await client_obj.send_message("me", f"✅ **Session String Generated!**\n\n`{session_string}`\n\n⚠ **इसे सुरक्षित रखें और किसी को न दें!**")
    await client_obj.disconnect()
    await message.reply("✅ **Session String आपकी Saved Messages में भेज दी गई है!**")
    del session_data[chat_id]

# 📌 Cancel Process
@app.on_callback_query(filters.regex("cancel"))
async def cancel_process(client, callback_query):
    chat_id = callback_query.message.chat.id
    if chat_id in session_data:
        del session_data[chat_id]
    await callback_query.message.edit_text("🚫 **Session Generation Canceled!**")

# ✅ Run the bot
app.run()
