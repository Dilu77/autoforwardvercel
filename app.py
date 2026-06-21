import threading
from flask import Flask
from bot import Bot

app = Flask(__name__)


@app.route("/")
def home():
    return "Live Forward Bot is running!", 200


@app.route("/health")
def health():
    return "OK", 200


def run_bot():
    bot = Bot()
    bot.run()


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    app.run(host="0.0.0.0", port=8080)
