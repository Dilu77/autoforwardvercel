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
            workers=4,
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

        # ── Re-launch userbot listeners for owners & premium users
        # For multi-tasks, only Owner users (in Config.OWNER_ID) are auto-resumed on restart.
        main_active = await db.get_active_users()
        task_active = await db.get_users_with_active_tasks()
        
        # Non-owners only auto-resume main forwarding if premium; owner auto-resumes both main & multi-tasks.
        resumable_user_ids = sorted(list(set(main_active + [u for u in task_active if u in Config.OWNER_ID])))

        if resumable_user_ids:
            logging.info(
                f"Processing restart auto-resume for {len(resumable_user_ids)} user(s)..."
            )
            for user_id in resumable_user_ids:
                is_owner = user_id in Config.OWNER_ID
                is_prem = await db.is_premium(user_id)
                if not is_prem and not is_owner:
                    # Free plan: stop active state on restart
                    await db.set_active(user_id, False)
                    tasks = await db.get_active_tasks(user_id)
                    for t in tasks:
                        await db.set_task_active(user_id, t["task_id"], False)
                    try:
                        await self.send_message(
                            user_id,
                            "⚠️ <b>Bot restarted.</b> Free plan live forwarding is paused after a server restart.\n"
                            "Please tap <b>▶️ Start Forwarding</b> in /start to resume manually.",
                        )
                    except Exception:
                        pass
                else:
                    # Premium / Owner: auto-resume forwarding session & multi-tasks (for owner)
                    try:
                        from plugins.forwarder import launch_userbot
                        res = await launch_userbot(self, user_id)
                        if res is None:
                            await self.send_message(
                                user_id,
                                "♻️ <b>Bot restarted.</b> Your live forwarding session has been automatically resumed!",
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
