import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession
from pyrogram.errors import *
from telethon.errors import *
from config import API_ID, API_HASH, BOT_TOKEN

# लॉगिंग सेटअप
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# सेशन डेटा स्टोरेज
session_data = {}

# Pyrogram क्लाइंट
app = Client("sessionstring", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 🔹 सेशन हैंडलर सेटअप
def setup_string_handler(app: Client):
    @app.on_message(filters.command(["pyro", "tele"]) & filters.private)
    async def session_setup(client, message: Message):
        platform = "Pyrogram" if message.command[0] == "pyro" else "Telethon"
        await start_session(client, message, platform)

    @app.on_callback_query(filters.regex(r"^session_go_"))
    async def handle_callback(client, callback_query):
        await process_callback(client, callback_query)

    @app.on_message(filters.text & filters.create(lambda _, __, msg: msg.chat.id in session_data))
    async def handle_text(client, message: Message):
        await process_text(client, message)

async def start_session(client, message, platform):
    chat_id = message.chat.id
    session_data[chat_id] = {"type": platform, "stage": "api_id"}
    
    await message.reply(
        f"**Welcome to the {platform} Session Generator!**\n\n"
        "🔹 **Steps:**\n"
        "1️⃣ Send **API ID**\n"
        "2️⃣ Send **API Hash**\n"
        "3️⃣ Send **Phone Number**\n"
        "4️⃣ Enter **OTP** sent to your Telegram\n"
        "5️⃣ If 2FA enabled, enter **Password**\n\n"
        "⚠️ **Do not share your session string with anyone!**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Go", callback_data=f"session_go_{platform.lower()}")],
            [InlineKeyboardButton("Close", callback_data="session_close")]
        ])
    )

async def process_callback(client, callback_query):
    chat_id = callback_query.message.chat.id
    data = callback_query.data

    if data == "session_close":
        await callback_query.message.edit_text("Session generation canceled.")
        session_data.pop(chat_id, None)
        return

    if data.startswith("session_go_"):
        session_data[chat_id]["stage"] = "api_id"
        await callback_query.message.edit_text("<b>Send Your API ID</b>", parse_mode=ParseMode.HTML)

async def process_text(client, message: Message):
    chat_id = message.chat.id
    session = session_data.get(chat_id, {})
    stage = session.get("stage")

    if stage == "api_id":
        try:
            session["api_id"] = int(message.text)
            session["stage"] = "api_hash"
            await message.reply("<b>Send Your API Hash</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await message.reply("❌ Invalid API ID. Please enter a valid integer.")

    elif stage == "api_hash":
        session["api_hash"] = message.text
        session["stage"] = "phone_number"
        await message.reply("<b>Send Your Phone Number (Example: +91XXXXXXXXXX)</b>", parse_mode=ParseMode.HTML)

    elif stage == "phone_number":
        session["phone_number"] = message.text
        await message.reply("🔄 Sending OTP...")
        await send_otp(client, message)

    elif stage == "otp":
        session["otp"] = ''.join(filter(str.isdigit, message.text))
        await message.reply("🔄 Validating OTP...")
        await validate_otp(client, message)

    elif stage == "2fa":
        session["password"] = message.text
        await validate_2fa(client, message)

async def send_otp(client, message):
    chat_id = message.chat.id
    session = session_data[chat_id]
    api_id, api_hash, phone = session["api_id"], session["api_hash"], session["phone_number"]
    telethon = session["type"] == "Telethon"

    client_obj = TelegramClient(StringSession(), api_id, api_hash) if telethon else Client(":memory:", api_id, api_hash)
    
    try:
        await client_obj.connect()
        session["client_obj"] = client_obj
        if telethon:
            await client_obj.send_code_request(phone)
        else:
            await client_obj.send_code(phone)
        session["stage"] = "otp"
        await message.reply("<b>Enter the OTP sent to your Telegram</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error sending OTP: {e}")
        await message.reply("❌ Error sending OTP. Please try again.")

async def validate_otp(client, message):
    session = session_data[message.chat.id]
    client_obj, phone, otp = session["client_obj"], session["phone_number"], session["otp"]
    telethon = session["type"] == "Telethon"

    try:
        if telethon:
            await client_obj.sign_in(phone, otp)
        else:
            await client_obj.sign_in(phone, session["code"], otp)
        await generate_session(client, message)
    except Exception as e:
        logger.error(f"OTP validation error: {e}")
        await message.reply("❌ Invalid OTP. Please try again.")

async def validate_2fa(client, message):
    session = session_data[message.chat.id]
    client_obj, password = session["client_obj"], session["password"]

    try:
        await client_obj.sign_in(password=password)
        await generate_session(client, message)
    except Exception as e:
        logger.error(f"2FA validation error: {e}")
        await message.reply("❌ Invalid Password. Please try again.")

async def generate_session(client, message):
    session = session_data[message.chat.id]
    client_obj, telethon = session["client_obj"], session["type"] == "Telethon"

    session_string = client_obj.session.save() if telethon else await client_obj.export_session_string()
    await client_obj.send_message("me", f"**Your {session['type']} session:**\n\n`{session_string}`\n\n⚠️ **Keep it safe!**")
    
    await client_obj.disconnect()
    await message.reply("✅ Session saved in your **Saved Messages**!", parse_mode=ParseMode.HTML)
    session_data.pop(message.chat.id, None)

# बॉट स्टार्ट करें
setup_string_handler(app)
app.run()
