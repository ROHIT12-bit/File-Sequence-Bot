import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import re
from pymongo import MongoClient
from config import API_HASH, API_ID, BOT_TOKEN, MONGO_URI, START_PIC, START_MSG, HELP_TXT, OWNER_ID

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["sequence_bot"]
users_collection = db["users_sequence"]

app = Client("sequence_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sequences = {}

# Regex patterns
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

# ----------------------- START COMMAND -----------------------
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

# ----------------------- START SEQUENCE -----------------------
@app.on_message(filters.command("ssequence"))
async def start_sequence(client, message):
    user_id = message.from_user.id
    if user_id not in user_sequences:
        user_sequences[user_id] = []
        await message.reply_text("<blockquote>ғɪʟᴇ sᴇǫᴜᴇɴᴄᴇ ᴍᴏᴅᴇ sᴛᴀʀᴛᴇᴅ! sᴇɴᴅ ʏᴏᴜʀ ғɪʟᴇs ɴᴏᴡ</blockquote>")

# ----------------------- END SEQUENCE -----------------------
@app.on_message(filters.command("esequence"))
async def end_sequence(client, message):
    user_id = message.from_user.id
    if user_id not in user_sequences or not user_sequences[user_id]:
        await message.reply_text("<blockquote>Nᴏ ғɪʟᴇs ɪɴ sᴇǫᴜᴇɴᴄᴇ!</blockquote>")
        return

    sorted_files = sorted(user_sequences[user_id], key=lambda x: extract_episode_number(x["filename"]))

    for file in sorted_files:
        await client.copy_message(
            message.chat.id,
            from_chat_id=file["chat_id"],
            message_id=file["msg_id"]
        )
        await asyncio.sleep(0.1)

    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"files_sequenced": len(user_sequences[user_id])},
         "$set": {"username": message.from_user.first_name}},
        upsert=True
    )

    del user_sequences[user_id]
    await message.reply_text("<blockquote>ᴀʟʟ ғɪʟᴇs sᴇǫᴜᴇɴᴄᴇᴅ!</blockquote>")

# ----------------------- STORE FILES -----------------------
@app.on_message(filters.document | filters.video | filters.audio)
async def store_file(client, message):
    user_id = message.from_user.id
    if user_id in user_sequences:
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

        await message.reply_text("<blockquote>ғɪʟᴇ ᴀᴅᴅᴇᴅ! ᴜsᴇ /ᴇsᴇǫᴜᴇɴᴄᴇ ᴛᴏ enᴅ.<blockquote>")
    else:
        await message.reply_text("<blockquote>sᴛᴀʀᴛ sᴇǫᴜᴇɴᴄᴇ ᴡɪᴛʜ /ssequence ғɪʀsᴛ.<blockquote>")

# ----------------------- LEADERBOARD -----------------------
@app.on_message(filters.command("leaderboard"))
async def leaderboard(client, message):
    top_users = users_collection.find().sort("files_sequenced", -1).limit(5)
    leaderboard_text = "<blockquote>🏆 ᴛᴏᴘ ᴜsᴇʀs\n\n</blockquote>"

    found = False
    for index, user in enumerate(top_users, start=1):
        found = True
        leaderboard_text += f"**{index}. {user['username']}** - {user['files_sequenced']} files\n"

    if not found:
        leaderboard_text = "No data available!"

    await message.reply_text(leaderboard_text)

# ----------------------- BROADCAST -----------------------
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast(client, message):
    if len(message.command) < 2:
        await message.reply_text("<blockquote>ᴜsᴀɢᴇ: `/broadcast your message`</blockquote>")
        return

    text = message.text.split(" ", 1)[1]
    users = users_collection.find({}, {"user_id": 1})

    count = 0
    for user in users:
        try:
            await client.send_message(user["user_id"], text)
            count += 1
        except:
            pass

    await message.reply_text(f"✅ Broadcast sent to {count} users.")

# ----------------------- USERS -----------------------
@app.on_message(filters.command("users") & filters.user(OWNER_ID))
async def get_users(client, message):
    count = users_collection.count_documents({})
    await message.reply_text(f"<blockquote>📊 ᴛᴏᴛᴀʟ ᴜsᴇʀs: {count}</blockquote>")

# ----------------------- CALLBACK -----------------------
@app.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data

    if data == "help":
        await query.message.edit_text(
            text=HELP_TXT.format(first=query.from_user.first_name),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Back", callback_data='start'),
                    InlineKeyboardButton("Close", callback_data='close')
                ]
            ])
        )

    elif data == "start":
        await query.message.edit_text(
            text=START_MSG.format(first=query.from_user.first_name),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Help", callback_data='help'),
                    InlineKeyboardButton("Close", callback_data='close')
                ],
                [InlineKeyboardButton("𝗕𝗼𝘁𝘀𝗞𝗶𝗻𝗴𝗱𝗼𝗺𝘀", url='https://t.me/BOTSKINGDOMS')]
            ])
        )

    elif data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass

app.run()


