import os
import asyncio
from flask import Flask
from sequence import start_bot  # import your bot starter function

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())  # start bot in background

    # Run Flask server on Render port
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)
