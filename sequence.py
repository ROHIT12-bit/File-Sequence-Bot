import os
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient
import re
from config import API_HASH, API_ID, BOT_TOKEN, MONGO_URI, START_PIC, START_MSG, HELP_TXT, OWNER_ID
from flask import Flask

# ------------------ Logging ------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ------------------ MongoDB ------------------
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["sequence_bot"]
users_collection = db["users_sequence"]

# ------------------ Bot ------------------
bot = Client("sequence_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sequences = {}

# ------------------ Flask ------------------
web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is running!"

# ------------------ Regex Patterns ------------------
patterns = [
    re.compile(r'\b(?:EP|E)\s*-\s*(\d{1,3})\b', re.IGNORECASE),
    re.compile(r'\b(?:EP|E)\s*(\d{1,3})\b', re.IGNORECASE),
    re.compile(r'S(\d+)(?:E|EP)(\d+)', re.IGNORECASE),
    re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)\s*(\d+)', re.IGNORECASE),
    re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)', re.IGNORECASE),
    re.compile(r'(?:EP|E)?\s*[-]?\s*(\d{1,3})', re.IGNORECASE),
    re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE),
    re.compile(r'(\d+)')
]

def extract_episode_number(filename):
    for pattern in patterns:
        match = pattern.search(filename)
        if match:
            return int(match.groups()[-1])
    return float('inf')

# ------------------ Handlers ------------------
@bot.on_message(filters.command("start"))
async def start_command(client, message):
    logging.info(f"/start from {message.from_user.id}")
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("ʜᴇʟᴘ", callback_data="help"),
         InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")],
        [InlineKeyboardButton("ʙᴏᴛsᴋɪɴɢᴅᴏᴍs", url="https://t.me/BOTSKINGDOMS")]
    ])
    await client.send_photo(
        chat_id=message.chat.id,
        photo=START_PIC,
        caption=START_MSG,
        reply_markup=buttons
    )

@bot.on_message(filters.command("ssequence"))
async def start_sequence(client, message):
    user_id = message.from_user.id
    if user_id not in user_sequences:
        user_sequences[user_id] = []
        logging.info(f"User {user_id} started sequence mode")
        await message.reply_text("<blockquote>ғɪʟᴇ sᴇǫᴜᴇɴᴄᴇ ᴍᴏᴅᴇ sᴛᴀʀᴛᴇᴅ!</blockquote>")

@bot.on_message(filters.command("esequence"))
async def end_sequence(client, message):
    user_id = message.from_user.id
    if user_id not in user_sequences or not user_sequences[user_id]:
        await message.reply_text("<blockquote>Nᴏ ғɪʟᴇs ɪɴ sᴇǫᴜᴇɴᴄᴇ!</blockquote>")
        return

    sorted_files = sorted(user_sequences[user_id], key=lambda x: extract_episode_number(x["filename"]))
    for file in sorted_files:
        await client.copy_message(message.chat.id, file["chat_id"], file["msg_id"])
        await asyncio.sleep(0.1)

    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"files_sequenced": len(user_sequences[user_id])},
         "$set": {"username": message.from_user.first_name}},
        upsert=True
    )
    logging.info(f"User {user_id} finished sequence mode with {len(user_sequences[user_id])} files")
    del user_sequences[user_id]
    await message.reply_text("<blockquote>ᴀʟʟ ғɪʟᴇs sᴇǫᴜᴇɴᴄᴇᴅ!</blockquote>")

@bot.on_message(filters.document | filters.video | filters.audio)
async def store_file(client, message):
    user_id = message.from_user.id
    if user_id in user_sequences:
        file_name = getattr(message.document or message.video or message.audio, "file_name", "Unknown")
        user_sequences[user_id].append({
            "filename": file_name,
            "msg_id": message.id,
            "chat_id": message.chat.id
        })
        logging.info(f"User {user_id} added file: {file_name}")
        await message.reply_text("<blockquote>ғɪʟᴇ ᴀᴅᴅᴇᴅ! Use /esequence to end.</blockquote>")
    else:
        await message.reply_text("<blockquote>Start sequence with /ssequence first.</blockquote>")

# ------------------ Callbacks ------------------
@bot.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    old_text = query.message.text or ""

    async def safe_edit(new_text, kb):
        if old_text.strip() != new_text.strip():
            try:
                await query.message.edit_text(new_text, reply_markup=kb)
            except Exception as e:
                logging.warning(f"Edit error: {e}")
        else:
            await query.answer("Already open!", show_alert=False)

    if data == "help":
        new_text = HELP_TXT.replace("{first}", query.from_user.first_name)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="start_menu"),
                                    InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]])
        await safe_edit(new_text, kb)
    elif data == "start_menu":
        new_text = START_MSG.replace("{first}", query.from_user.first_name)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("ʜᴇʟᴘ", callback_data="help"),
             InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")],
            [InlineKeyboardButton("ʙᴏᴛsᴋɪɴɢᴅᴏᴍs", url="https://t.me/BOTSKINGDOMS")]
        ])
        await safe_edit(new_text, kb)
    elif data == "close":
        try:
            await query.message.delete()
        except:
            pass
        try:
            if query.message.reply_to_message:
                await query.message.reply_to_message.delete()
        except:
            pass
    await query.answer()

# ------------------ Run Bot ------------------
async def main():
    await bot.start()
    logging.info("Bot started successfully!")
    # notify owner on restart
    try:
        await bot.send_message(OWNER_ID, "<b>⚡ Bot has restarted!</b>")
    except Exception as e:
        logging.warning(f"Failed to notify owner: {e}")
    await idle()

if __name__ == "__main__":
    import threading
    import os
    # Run bot in background
    loop = asyncio.get_event_loop()
    loop.create_task(main())

    # Run Flask web server in main thread
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
