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
channels_collection = db["fsub_channels"]  # stores documents: {"_id": <identifier>, "name": <title_or_username>} 

# ----------------------- BOT -----------------------
app = Client("sequence_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sequences = {}

# ----------------------- EPISODE REGEX -----------------------
patterns = [
    re.compile(r'\b(?:EP|E)\s*-\s*(\d{1,3})\b', re.IGNORECASE),
    re.compile(r'\b(?:EP|E)\s*(\d{1,3})\b', re.IGNORECASE),
    re.compile(r'S(\d+)(?:E|EP)(\d+)', re.IGNORECASE),
    re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)\s*(\d+)', re.IGNORECASE),
    re.compile(r'(?:[[<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)', re.IGNORECASE),
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

# ----------------------- HELPERS -----------------------
async def is_owner(user_id: int) -> bool:
    return int(user_id) == int(OWNER_ID)

async def get_fsub_channels():
    # returns list of channel identifiers (documents)
    docs = list(channels_collection.find({}))
    return docs

async def is_user_subscribed_to_all(user_id: int) -> (bool, list):
    """Return (True, []) if subscribed to all; else (False, [missing_channel_docs])"""
    channels = await get_fsub_channels()
    missing = []
    for ch in channels:
        identifier = ch.get("_id")
        try:
            member = await app.get_chat_member(identifier, user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:
            # any exception treat as not a member (bot might not have access)
            missing.append(ch)
    return (len(missing) == 0, missing)

def make_join_button_for_channel(ch):
    identifier = str(ch.get("_id"))
    label = ch.get("name") or identifier
    # create t.me link if possible
    username = identifier.lstrip("@")
    url = f"https://t.me/{username}"
    return InlineKeyboardButton(label, url=url)

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
        caption=START_MSG.format(first=message.from_user.first_name),
        reply_markup=buttons,
    )

@app.on_message(filters.command("ssequence"))
async def start_sequence(client, message):
    user_id = message.from_user.id

    ok, missing = await is_user_subscribed_to_all(user_id)
    if not ok:
        # build inline join buttons for missing channels
        kb = []
        for ch in missing[:3]:
            kb.append([make_join_button_for_channel(ch)])
        kb.append([InlineKeyboardButton("I've Joined ✅", callback_data="fsub_check")])
        await message.reply_photo(
            photo="https://i.rj1.dev/aNWlA.png",
            caption="<b>⛔ You must join the required channels to use this feature.</b>",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    user_sequences[user_id] = []
    await message.reply_text("<blockquote>ғɪʟᴇ sᴇǫᴜᴇɴᴄᴇ ᴍᴏᴅᴇ ᴏɴ! sᴇɴᴅ ғɪʟᴇs ɴᴏᴡ.</blockquote>")

@app.on_message(filters.command("esequence"))
async def end_sequence(client, message):
    user_id = message.from_user.id

    ok, missing = await is_user_subscribed_to_all(user_id)
    if not ok:
        kb = []
        for ch in missing[:3]:
            kb.append([make_join_button_for_channel(ch)])
        kb.append([InlineKeyboardButton("I've Joined ✅", callback_data="fsub_check")])
        await message.reply_photo(
            photo="https://i.rj1.dev/aNWlA.png",
            caption="<b>⛔ You must join the required channels to use this feature.</b>",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

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

# ----------------------- F-SUB MENU & Management -----------------------
@app.on_message(filters.command("fsub_menu"))
async def fsub_menu_cmd(client, message):
    # only owner can manage channels from menu
    if not await is_owner(message.from_user.id):
        return await message.reply_text("Only the bot owner can manage the forced-subscription list.")

    channels = await get_fsub_channels()
    kb = [
        [InlineKeyboardButton("Add Channel", callback_data="fsub_add")],
        [InlineKeyboardButton("Remove Channel", callback_data="fsub_remove")],
        [InlineKeyboardButton("List Channels", callback_data="fsub_list")],
        [InlineKeyboardButton("Close", callback_data="close")]
    ]

    await client.send_photo(
        chat_id=message.chat.id,
        photo="https://i.rj1.dev/aNWlA.png",
        caption="🔐 <b>Forced Subscription Menu</b>\nManage required channels (max 3).\n\nUse buttons below — add/remove via commands or the inline list.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

@app.on_message(filters.command("fsub_add"))
async def fsub_add_cmd(client, message):
    if not await is_owner(message.from_user.id):
        return await message.reply_text("Only the owner can add channels.")

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text("Usage: /fsub_add <@channelusername_or_channelid>\nExample: /fsub_add @mychannel")

    identifier = args[1].strip()
    # enforce max 3
    current = await get_fsub_channels()
    if len(current) >= 3:
        return await message.reply_text("Maximum of 3 forced channels already set. Remove one first.")

    try:
        # try to fetch chat info to get title
        chat = await app.get_chat(identifier)
        title = chat.title or chat.username or identifier
    except Exception:
        title = identifier

    channels_collection.update_one({"_id": identifier}, {"$set": {"name": title}}, upsert=True)
    await message.reply_text(f"Added forced channel: {title} ({identifier})")

@app.on_message(filters.command("fsub_remove"))
async def fsub_remove_cmd(client, message):
    if not await is_owner(message.from_user.id):
        return await message.reply_text("Only the owner can remove channels.")

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text("Usage: /fsub_remove <@channelusername_or_channelid>\nExample: /fsub_remove @mychannel")

    identifier = args[1].strip()
    res = channels_collection.delete_one({"_id": identifier})
    if res.deleted_count:
        await message.reply_text(f"Removed channel: {identifier}")
    else:
        await message.reply_text(f"Channel not found: {identifier}")

@app.on_message(filters.command("fsub_list"))
async def fsub_list_cmd(client, message):
    if not await is_owner(message.from_user.id):
        return await message.reply_text("Only the owner can view the list.")

    channels = await get_fsub_channels()
    if not channels:
        return await message.reply_text("No forced channels set.")

    text = "<b>Forced channels (max 3):</b>\n"
    kb_rows = []
    for ch in channels:
        text += f"\n• {ch.get('name')} ({ch.get('_id')})"
        kb_rows.append([InlineKeyboardButton(f"Remove {ch.get('name')}", callback_data=f"fsub_rm::{ch.get('_id')}")])

    kb_rows.append([InlineKeyboardButton("Close", callback_data="close")])
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb_rows))

# ----------------------- BROADCAST / USERS / LEADERBOARD -----------------------
@app.on_message(filters.command("broadcast"))
async def broadcast_cmd(client, message):
    if not await is_owner(message.from_user.id):
        return await message.reply_text("Only owner can run broadcast.")

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text("Usage: /broadcast <message>")

    text = args[1]
    users = list(users_collection.find({}, {"user_id": 1}))
    sent = 0
    for u in users:
        uid = u.get("user_id")
        try:
            await client.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.03)
        except Exception:
            continue

    await message.reply_text(f"Broadcast sent to {sent} users.")

@app.on_message(filters.command("users"))
async def users_cmd(client, message):
    if not await is_owner(message.from_user.id):
        return await message.reply_text("Only owner can view users.")

    total = users_collection.count_documents({})
    total_files = 0
    top = list(users_collection.find({}).sort("files_sequenced", -1).limit(5))
    for u in users_collection.find({}):
        total_files += u.get("files_sequenced", 0)

    text = f"<b>Total users:</b> {total}\n<b>Total files sequenced:</b> {total_files}\n\n<b>Top users:</b>\n"
    for i, u in enumerate(top, start=1):
        text += f"{i}. {u.get('username','Unknown')} — {u.get('files_sequenced',0)} files\n"

    await message.reply_text(text)

@app.on_message(filters.command("leaderboard"))
async def leaderboard_cmd(client, message):
    top = list(users_collection.find({}).sort("files_sequenced", -1).limit(10))
    if not top:
        return await message.reply_text("No data yet.")

    text = "<b>🏆 Leaderboard</b>\n"
    for i, u in enumerate(top, start=1):
        text += f"{i}. {u.get('username','Unknown')} — {u.get('files_sequenced',0)} files\n"

    await message.reply_text(text)

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
        try:
            await query.message.delete()
        except Exception:
            pass

    elif data == "fsub_add":
        # instruct owner to use command to add
        await query.message.edit_caption("To add a channel use the command:\n/fsub_add @channelusername\n(Max 3 channels)")

    elif data == "fsub_remove":
        await query.message.edit_caption("To remove a channel use the command:\n/fsub_remove @channelusername")

    elif data == "fsub_list":
        channels = await get_fsub_channels()
        if not channels:
            await query.message.edit_caption("No forced channels set.")
            return
        text = "<b>Forced channels (max 3):</b>\n"
        kb = []
        for ch in channels:
            text += f"\n• {ch.get('name')} ({ch.get('_id')})"
            kb.append([InlineKeyboardButton(f"Remove {ch.get('name')}", callback_data=f"fsub_rm::{ch.get('_id')}")])
        kb.append([InlineKeyboardButton("Close", callback_data="close")])
        await query.message.edit_caption(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("fsub_rm::"):
        # owner clicked remove on inline list
        identifier = data.split("::", 1)[1]
        channels_collection.delete_one({"_id": identifier})
        await query.message.edit_caption(f"Removed forced channel: {identifier}")

    elif data == "fsub_check":
        ok, missing = await is_user_subscribed_to_all(query.from_user.id)
        if ok:
            await query.message.edit_caption("Thanks — you are subscribed to all required channels. You can now use the bot.")
        else:
            kb = []
            for ch in missing[:3]:
                kb.append([make_join_button_for_channel(ch)])
            kb.append([InlineKeyboardButton("I've Joined ✅", callback_data="fsub_check")])
            await query.message.edit_caption("You are still missing some channels.", reply_markup=InlineKeyboardMarkup(kb))

# ----------------------- START BOT -----------------------
if __name__ == "__main__":
    print("Starting Sequence Bot with F-Sub system...")
    app.run()
