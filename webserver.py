# 1. Imports
import os
import asyncio
import logging
from pyrogram import Client, filters, idle
from flask import Flask

# 2. Config & Bot setup
from config import API_HASH, API_ID, BOT_TOKEN
app_bot = Client("sequence_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = Flask(__name__)

# 3. Handlers (start, sequence, store files, leaderboard, callbacks...)
# ... your full sequence bot code goes here ...

# 4. Flask route
@web.route("/")
def home():
    return "Bot is running!"

# 5. Async main to start bot
async def main():
    await app_bot.start()
    logging.info("Bot started")
    await idle()  # keeps Pyrogram alive

# 6. Run Flask and bot
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
