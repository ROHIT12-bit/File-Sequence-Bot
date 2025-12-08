import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import re
from pymongo import MongoClient
from config import API_HASH, API_ID, BOT_TOKEN, MONGO_URI, START_PIC, START_MSG, HELP_TXT, OWNER_ID

# ----------------------- MONGO -----------------------
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["sequence_bot"]
users_collection = db["users_sequence"]

# ----------------------- BOT -----------------------
app = Client("sequence_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sequences = {}

# ----------------------- EPISODE REGEX -----------------------
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

# ----------------------- COMMANDS -----------------------
@app.on_message(filters.command("start"))
async def start_command(client, message):
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Help", callback_data='help'),
            InlineKeyboardButton("Close", callback_data='close')
        ],
        [InlineKeyboardButton("ʙᴏᴛsᴋɪɴɢᴅᴏᴍs", url='https://t.me/BOTSKINGDOMS')]
    ])

    await client.send_photo(
        chat_id=message.chat.id,
        photo=START_PIC,
        caption=START_MSG,
        reply_markup=buttons,
    )

@app.on_message(filters.command("ssequence"))
async def start_sequence(client, message):
    user_id = message.from_user.id
    user_sequences[user_id] = []
    await message.reply_text("<blockquote>ғɪʟᴇ sᴇǫᴜᴇɴᴄᴇ ᴍᴏᴅᴇ ᴏɴ! sᴇɴᴅ ғɪʟᴇs ɴᴏᴡ.</blockquote>")

@app.on_message(filters.command("esequence"))
async def end_sequence(client, message):
    user_id = message.from_user.id
    if user_id not in user_sequences or not user_sequences[user_id]:
        return await message.reply_text("<blockquote>Nᴏ ғɪʟᴇs ғᴏᴜɴᴅ!</blockquote>")

    sorted_files = sorted(user_sequences[user_id], key=lambda x: extract_episode_number(x["filename"]))

    for file in sorted_files:
        await client.copy_message(
            message.chat.id,
            from_chat_id=file["chat_id"],
            message_id=file["msg_id"]
        )
        await asyncio.sleep(0.08)

    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"files_sequenced": len(user_sequences[user_id])},
         "$set": {"username": message.from_user.first_name}},
        upsert=True
    )

    del user_sequences[user_id]
    await message.reply_text("<blockquote>ᴅᴏɴᴇ! ᴀʟʟ ғɪʟᴇs sᴇǫᴜᴇɴᴄᴇᴅ ✔️</blockquote>")

@app.on_message(filters.document | filters.video | filters.audio)
async def store_file(client, message):
    user_id = message.from_user.id

    if user_id not in user_sequences:
        return await message.reply_text("<blockquote>ᴜsᴇ /ssequence ғɪʀsᴛ!</blockquote>")

    file_name = (
        message.document.file_name if message.document else
        message.video.file_name if message.video else
        message.audio.file_name if message.audio else "Unknown"
    )

    user_sequences[user_id].append({
        "filename": file_name,
        "msg_id": message.id,
        "chat_id": message.chat.id
    })

    await message.reply_text("<blockquote>ғɪʟᴇ ᴀᴅᴅᴇᴅ ✔️</blockquote>")

# ----------------------- CALLBACKS -----------------------
@app.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    await query.answer()
    data = query.data

    if data == "help":
        await query.message.edit_text(
            HELP_TXT.format(first=query.from_user.first_name),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="start"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "start":
        await query.message.edit_text(
            START_MSG.format(first=query.from_user.first_name),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Help", callback_data='help'),
                 InlineKeyboardButton("Close", callback_data='close')],
                [InlineKeyboardButton("ʙᴏᴛsᴋɪɴɢᴅᴏᴍs", url='https://t.me/BOTSKINGDOMS')]
            ])
        )

    elif data == "close":
        await query.message.delete()

# ----------------------- START BOT -----------------------
if __name__ == "__main__":
    app.run()
