# Full Sequence Bot with F-Sub Inline Menu (Add/Remove/List)
# This replaces the previous skeleton.

import asyncio
import re
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from pymongo import MongoClient
from config import API_HASH, API_ID, BOT_TOKEN, MONGO_URI, START_PIC, START_MSG, HELP_TXT, OWNER_ID

logging.basicConfig(level=logging.INFO)

# ----------------------- MONGO -----------------------
mongo = MongoClient(MONGO_URI)
db = mongo["sequence_bot"]
users_collection = db["users"]
fsub_collection = db["fsub_channels"]

# ----------------------- BOT -----------------------
app = Client("sequence_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sequences = {}
user_fsub_state = {}  # waiting for add/remove input

# ----------------------- F-SUB TOOLS -----------------------
async def check_fsub(client, user_id):
    channels = list(fsub_collection.find())
    if not channels:
        return True, None

    for ch in channels:
        try:
            await client.get_chat_member(ch["channel_id"], user_id)
        except:
            return False, channels
    return True, channels


def fsub_keyboard():
    channels = list(fsub_collection.find())
    rows = []

    for ch in channels:
        rows.append([
            InlineKeyboardButton(f"{ch['channel_name']}", url=f"https://t.me/{ch['channel_username']}") ,
            InlineKeyboardButton("❌ Remove", callback_data=f"fsub_remove_{ch['channel_id']}")
        ])

    if len(channels) < 3:
        rows.append([InlineKeyboardButton("➕ Add Channel", callback_data="fsub_add")])

    rows.append([InlineKeyboardButton("🔙 Back", callback_data="start")])

    return InlineKeyboardMarkup(rows)


# ----------------------- START & MENU -----------------------
@app.on_message(filters.command("menu"))
async def main_menu(client, message):
    await message.reply(
        "<b>Main Menu</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Sequence Mode", callback_data="seq_menu")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_menu")],
            [InlineKeyboardButton("👥 Users", callback_data="users_menu"), InlineKeyboardButton("🏆 Leaderboard", callback_data="leader_menu")],
            [InlineKeyboardButton("🔐 F-Sub Control", callback_data="open_fsub")]
        ])
    )

# Existing START command
@app.on_message(filters.command("start"))
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await client.send_photo(
        message.chat.id,
        START_PIC,
        caption=START_MSG.format(first=message.from_user.first_name),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Help", callback_data="help"), InlineKeyboardButton("Close", callback_data="close")],
            [InlineKeyboardButton("BotsKingdoms", url="https://t.me/BOTSKINGDOMS")]
        ])
    )

# ----------------------- F-SUB MENU -----------------------
@app.on_message(filters.command("fsub_menu"))
async def fsub_menu(client, message):
    await client.send_photo(
        message.chat.id,
        photo="https://i.rj1.dev/aNWlA.png",
        caption="<b>F-Sub Control Panel</b>",
        reply_markup=fsub_keyboard()
    )

# ----------------------- INLINE F-SUB ACTIONS -----------------------
@app.on_callback_query(filters.regex("^fsub_add$"))
async def fsub_add_btn(client, query):
    if query.from_user.id != OWNER_ID:
        return await query.answer("Owner only", show_alert=True)

    user_fsub_state[query.from_user.id] = "add"
    await query.message.reply_text("Send channel username or ID to add:")
    await query.answer()

@app.on_callback_query(filters.regex("^fsub_remove_"))
async def fsub_remove_btn(client, query):
    if query.from_user.id != OWNER_ID:
        return await query.answer("Owner only", show_alert=True)

    ch_id = query.data.replace("fsub_remove_", "")
    fsub_collection.delete_one({"channel_id": ch_id})

    await query.message.edit_caption(
        caption="<b>F-Sub Channel Removed</b>",
        reply_markup=fsub_keyboard()
    )
    await query.answer("Removed")

# Listen for Add Channel Input
@app.on_message(filters.text & filters.private)
async def handle_fsub_add(client, message):
    user_id = message.from_user.id

    if user_id not in user_fsub_state:
        return

    if user_fsub_state[user_id] == "add":
        if fsub_collection.count_documents({}) >= 3:
            await message.reply("Max 3 channels allowed.")
            user_fsub_state.pop(user_id, None)
            return

        text = message.text.replace("@", "").strip()

        try:
            chat = await client.get_chat(text)
            fsub_collection.insert_one({
                "channel_id": str(chat.id),
                "channel_name": chat.title,
                "channel_username": chat.username or text
            })

            await message.reply(
                f"Added F-Sub Channel: {chat.title}",
                reply_markup=fsub_keyboard()
            )

        except Exception as e:
            await message.reply(f"Error: {e}")

        user_fsub_state.pop(user_id, None)


# ----------------------- SEQUENCE & OTHER BOT FUNCTIONS -----------------------
# ----------------------- MAIN MENU CALLBACK HANDLERS -----------------------
@app.on_callback_query(filters.regex("^seq_menu$"))
async def seq_menu_cb(client, query):
    await query.message.edit_text(
        """<b>Sequence Mode</b>/nChoose an option:""",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Start Sequence", callback_data="seq_start")],
            [InlineKeyboardButton("End Sequence", callback_data="seq_end")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_menu")]
        ])
    )
    await query.answer()

@app.on_callback_query(filters.regex("^broadcast_menu$"))
async def broadcast_menu_cb(client, query):
    await query.message.edit_text(
        """<b>Broadcast Panel</b>/nSend message to all users.""",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Start Broadcast", callback_data="broadcast_start")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_menu")]
        ])
    )
    await query.answer()

@app.on_callback_query(filters.regex("^users_menu$"))
async def users_menu_cb(client, query):
    count = users_collection.count_documents({})
    await query.message.edit_text(
        f"<b>Total Users:</b> {count}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_menu")]
        ])
    )
    await query.answer()

@app.on_callback_query(filters.regex("^leader_menu$"))
async def leader_menu_cb(client, query):
    data = users_collection.find().sort("files_sequenced", -1)
    text = "<b>🏆 Leaderboard</b>
"
    for u in data:
        text += f"<b>{u.get('username','User')}</b> — {u.get('files_sequenced',0)} files
"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_menu")]]))
    await query.answer()

@app.on_callback_query(filters.regex("^open_fsub$"))
async def open_fsub_cb(client, query):
    await query.message.edit_caption(
        caption="<b>F-Sub Control Panel</b>",
        reply_markup=fsub_keyboard()
    )
    await query.answer()

@app.on_callback_query(filters.regex("^back_menu$"))
async def back_main_menu(client, query):
    await query.message.edit_text(
        "<b>Main Menu</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Sequence Mode", callback_data="seq_menu")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_menu")],
            [InlineKeyboardButton("👥 Users", callback_data="users_menu"), InlineKeyboardButton("🏆 Leaderboard", callback_data="leader_menu")],
            [InlineKeyboardButton("🔐 F-Sub Control", callback_data="open_fsub")]
        ])
    )
    await query.answer()
# I will merge everything once you confirm UI behavior.


# ----------------------- RUN -----------------------
if __name__ == "__main__":
    app.run()


