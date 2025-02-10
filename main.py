
import requests
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)
from telethon.errors import (
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError
)
from asyncio.exceptions import TimeoutError

# यूजर से API ID, API HASH और BOT TOKEN लेने के लिए
API_ID = 28049056  # अपना API ID यहाँ डालें (Integer होना चाहिए)
API_HASH = "1a301acbe312e760b4d0716fd3b8eab2"  # अपना API HASH यहाँ डालें
BOT_TOKEN = "7589052839:AAGPMVeZpb63GEG_xXzQEua1q9ewfNzTg50"  # अपना BOT TOKEN यहाँ डालें

# टाइमआउट वैल्यूज़
TIMEOUT_OTP = 600  # 10 मिनट
TIMEOUT_2FA = 300  # 5 मिनट

session_data = {}

def setup_string_handler(app: Client):
    @app.on_message(filters.command(["pyro", "tele"], prefixes=["/", "."]) & (filters.private | filters.group))
    async def session_setup(client, message: Message):
        if message.chat.type in (ChatType.SUPERGROUP, ChatType.GROUP):
            await message.reply("**❌ यह टूल केवल प्राइवेट चैट में काम करता है।**", parse_mode=ParseMode.MARKDOWN)
            return
        
        platform = "PyroGram" if message.command[0] == "pyro" else "Telethon"
        await handle_start(client, message, platform)

    @app.on_callback_query(filters.regex(r"^session_go_"))
    async def callback_query_go_handler(client, callback_query):
        await handle_callback_query(client, callback_query)

    @app.on_callback_query(filters.regex(r"^session_resume_"))
    async def callback_query_resume_handler(client, callback_query):
        await handle_callback_query(client, callback_query)

    @app.on_callback_query(filters.regex(r"^session_close$"))
    async def callback_query_close_handler(client, callback_query):
        await handle_callback_query(client, callback_query)

    @app.on_message(filters.text & filters.create(lambda _, __, message: message.chat.id in session_data))
    async def text_handler(client, message: Message):
        await handle_text(client, message)

async def handle_start(client, message, platform):
    session_type = "Telethon" if platform == "Telethon" else "Pyrogram"
    session_data[message.chat.id] = {"type": session_type}
    await message.reply(
        f"**{session_type} सेशन स्टार्ट करने के लिए निर्देश:**\n"
        "1. **API ID** डालें (my.telegram.org से ले सकते हैं)।\n"
        "2. **API HASH** डालें।\n"
        "3. **फोन नंबर** डालें जिससे टेलीग्राम अकाउंट बना है।\n"
        "4. **OTP डालें** (Telegram से मिले कोड को कॉपी करके भेजें)।\n"
        "5. **अगर 2FA ऑन है**, तो पासवर्ड डालें।\n\n"
        "**⚠️ सावधानियां:**\n"
        "- किसी को अपना **Session String** शेयर न करें!\n"
        "- गलत जानकारी देने से सेशन जनरेट नहीं होगा।\n",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 अपडेट चैनल", url="https://t.me/ModVipRM"),
                InlineKeyboardButton("My Dev 👨‍💻", user_id=7303810912)
            ], [
                InlineKeyboardButton("Go", callback_data=f"session_go_{session_type.lower()}"),
                InlineKeyboardButton("Close", callback_data="session_close")
            ]
        ])
    )

async def handle_callback_query(client, callback_query):
    data = callback_query.data
    chat_id = callback_query.message.chat.id

    if data == "session_close":
        await callback_query.message.edit_text("❌ सेशन जेनरेशन कैंसिल किया गया।")
        if chat_id in session_data:
            del session_data[chat_id]
        return

    if data.startswith("session_go_"):
        session_type = data.split('_')[2]
        await callback_query.message.edit_text(
            "📌 **अपना API ID भेजें**",
            parse_mode=ParseMode.HTML
        )
        session_data[chat_id]["stage"] = "api_id"

async def handle_text(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in session_data:
        return

    session = session_data[chat_id]
    stage = session.get("stage")

    if stage == "api_id":
        try:
            api_id = int(message.text)
            session["api_id"] = api_id
            await message.reply("📌 **अपना API HASH भेजें**")
            session["stage"] = "api_hash"
        except ValueError:
            await message.reply("❌ **API ID गलत है। कृपया सही API ID भेजें।**")

    elif stage == "api_hash":
        session["api_hash"] = message.text
        await message.reply("📌 **अपना फ़ोन नंबर भेजें (उदाहरण: +91xxxxxxxxxx)**")
        session["stage"] = "phone_number"

    elif stage == "phone_number":
        session["phone_number"] = message.text
        await message.reply("📌 **OTP भेजा जा रहा है...**")
        await send_otp(client, message)

async def send_otp(client, message):
    session = session_data[message.chat.id]
    api_id = session["api_id"]
    api_hash = session["api_hash"]
    phone_number = session["phone_number"]
    telethon = session["type"] == "Telethon"

    client_obj = TelegramClient(StringSession(), api_id, api_hash) if telethon else Client(":memory:", api_id, api_hash)

    await client_obj.connect()

    try:
        code = await client_obj.send_code_request(phone_number) if telethon else await client_obj.send_code(phone_number)
        session["client_obj"] = client_obj
        session["code"] = code
        session["stage"] = "otp"
        await message.reply("📌 **OTP भेज दिया गया। कृपया भेजे गए कोड को टाइप करके भेजें।**")
    except ApiIdInvalid:
        await message.reply("❌ **API_ID या API_HASH गलत है। कृपया सही जानकारी डालें।**")

async def generate_session(client, message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]
    telethon = session["type"] == "Telethon"

    string_session = client_obj.session.save() if telethon else await client_obj.export_session_string()
    text = f"**{session['type'].upper()} SESSION:**\n\n`{string_session}`\n\nGenerated by @ItsSmartToolBot"

    await client_obj.send_message("me", text)
    await client_obj.disconnect()
    await message.reply("✅ **सेशन सेव कर दिया गया है। अपने Saved Messages में चेक करें।**")
    del session_data[message.chat.id]

# Pyrogram Client रन करें
app = Client("sessionstring", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

setup_string_handler(app)

app.run()
