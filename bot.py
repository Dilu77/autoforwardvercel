import asyncio
import logging
import logging.config
from database import db
from config import Config, temp
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait

logging.config.fileConfig("logging.conf")
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)


class Bot(Client):
    def __init__(self):
        super().__init__(
            Config.BOT_SESSION,
            api_hash=Config.API_HASH,
            api_id=Config.API_ID,
            plugins={"root": "plugins"},
            workers=50,
            bot_token=Config.BOT_TOKEN,
        )
        self.log = logging

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.id         = me.id
        self.username   = me.username
        self.first_name = me.first_name
        self.set_parse_mode(ParseMode.DEFAULT)

        logging.info(
            f"{me.first_name} started | pyrogram v{__version__} (Layer {layer}) | @{me.username}"
        )

        # ── Re-launch userbot listeners for users who were active before restart
        active_user_ids = await db.get_active_users()
        if active_user_ids:
            logging.info(
                f"Auto-resuming listeners for {len(active_user_ids)} user(s)..."
            )
            for user_id in active_user_ids:
                try:
                    from plugins.forwarder import launch_userbot
                    await launch_userbot(self, user_id)
                    await self.send_message(
                        user_id,
                        "♻️ <b>Bot restarted.</b> Your live forwarding has been automatically resumed!",
                    )
                except Exception as e:
                    logging.warning(f"Could not resume listener for {user_id}: {e}")
                    await db.set_active(user_id, False)
                    try:
                        await self.send_message(
                            user_id,
                            "⚠️ <b>Bot restarted</b> but your forwarding session could not be resumed.\n"
                            "Please use /start → <b>▶️ Start Forwarding</b> again.",
                        )
                    except Exception:
                        pass

    async def stop(self, *args):
        logging.info(f"@{self.username} stopped.")
        await super().stop()
