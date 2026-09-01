from config import Config
import motor.motor_asyncio
from pymongo import MongoClient


def mongodb_version():
    x = MongoClient(Config.DATABASE_URI)
    ver = x.server_info()["version"]
    x.close()
    return ver


class Database:
    def __init__(self, uri: str, db_name: str):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(
            uri,
            maxPoolSize=10,
            minPoolSize=1,
            maxIdleTimeMS=30000,
        )
        self.db      = self._client[db_name]

        # collections
        self.users    = self.db.users        # one doc per telegram user_id
        self.sessions = self.db.sessions     # userbot session strings
        self.bots     = self.db.bots         # bot tokens
        self.sources  = self.db.sources      # source chat_ids per user
        self.settings = self.db.settings     # per-user forwarding settings
        self.premium  = self.db.premium      # premium user records
        self.duplicates = self.db.duplicates  # duplicate message detection

    # ── helpers ───────────────────────────────────────────────────────────────

    def _user_filter(self, user_id: int) -> dict:
        return {"user_id": int(user_id)}

    # ── users ─────────────────────────────────────────────────────────────────

    async def is_user_exist(self, user_id: int) -> bool:
        return bool(await self.users.find_one(self._user_filter(user_id)))

    async def add_user(self, user_id: int, name: str):
        if not await self.is_user_exist(user_id):
            await self.users.insert_one({"user_id": int(user_id), "name": name})

    async def get_all_users(self):
        return self.users.find({})

    async def total_users_count(self) -> int:
        return await self.users.count_documents({})

    # ── premium ───────────────────────────────────────────────────────────────

    async def add_premium(self, user_id: int, added_by: int):
        """Grant premium to a user. Idempotent."""
        await self.premium.update_one(
            self._user_filter(user_id),
            {"$set": {"user_id": int(user_id), "added_by": int(added_by)}},
            upsert=True,
        )

    async def remove_premium(self, user_id: int):
        await self.premium.delete_many(self._user_filter(user_id))

    async def is_premium(self, user_id: int) -> bool:
        if int(user_id) in Config.OWNER_ID:
            return True
        return bool(await self.premium.find_one(self._user_filter(user_id)))

    async def get_all_premium(self) -> list[dict]:
        cursor = self.premium.find({})
        return [doc async for doc in cursor]

    async def total_premium_count(self) -> int:
        return await self.premium.count_documents({})

    # ── session string ────────────────────────────────────────────────────────

    async def set_session(self, user_id: int, session_string: str):
        await self.sessions.update_one(
            self._user_filter(user_id),
            {"$set": {"session": session_string}},
            upsert=True,
        )

    async def get_session(self, user_id: int) -> str | None:
        doc = await self.sessions.find_one(self._user_filter(user_id))
        return doc["session"] if doc else None

    async def remove_session(self, user_id: int):
        await self.sessions.delete_many(self._user_filter(user_id))

    async def has_session(self, user_id: int) -> bool:
        return bool(await self.sessions.find_one(self._user_filter(user_id)))

    # ── bot token ─────────────────────────────────────────────────────────────

    async def set_bot_token(self, user_id: int, bot_token: str):
        await self.bots.update_one(
            self._user_filter(user_id),
            {"$set": {"bot_token": bot_token}},
            upsert=True,
        )

    async def get_bot_token(self, user_id: int) -> str | None:
        doc = await self.bots.find_one(self._user_filter(user_id))
        return doc["bot_token"] if doc else None

    async def remove_bot_token(self, user_id: int):
        await self.bots.delete_many(self._user_filter(user_id))

    async def has_bot_token(self, user_id: int) -> bool:
        return bool(await self.bots.find_one(self._user_filter(user_id)))

    # ── source channels ───────────────────────────────────────────────────────

    async def add_source(self, user_id: int, chat_id: int, title: str) -> bool:
        exists = await self.sources.find_one(
            {"user_id": int(user_id), "chat_id": int(chat_id)}
        )
        if exists:
            return False
        await self.sources.insert_one(
            {"user_id": int(user_id), "chat_id": int(chat_id), "title": title}
        )
        return True

    async def remove_source(self, user_id: int, chat_id: int) -> bool:
        res = await self.sources.delete_many(
            {"user_id": int(user_id), "chat_id": int(chat_id)}
        )
        return res.deleted_count > 0

    async def get_sources(self, user_id: int) -> list[dict]:
        cursor = self.sources.find({"user_id": int(user_id)})
        return [doc async for doc in cursor]

    async def remove_all_sources(self, user_id: int):
        await self.sources.delete_many(self._user_filter(user_id))

    # ── destination channel ───────────────────────────────────────────────────

    async def set_destination(self, user_id: int, chat_id: int, title: str):
        await self.settings.update_one(
            self._user_filter(user_id),
            {"$set": {"destination": {"chat_id": int(chat_id), "title": title}}},
            upsert=True,
        )

    async def get_destination(self, user_id: int) -> dict | None:
        doc = await self.settings.find_one(self._user_filter(user_id))
        return doc.get("destination") if doc else None

    # ── forwarding settings ───────────────────────────────────────────────────

    _DEFAULT_SETTINGS = {
        "client_type":    "session", # 'session' or 'bot'
        "forward_tag":    False,
        "remove_caption": False,
        "custom_caption": None,
        "filters": {
            "text":      True,
            "photo":     True,
            "video":     True,
            "audio":     True,
            "document":  True,
            "voice":     True,
            "animation": True,
            "sticker":   True,
        },
        "is_active":   False,
        # list of {"keyword": str, "replace_with": str}
        "replace_rules": [],
        "button": None,
        "file_size": 0,
        "size_limit": None,
        "extensions": [],
        "keywords": [],
        "protect_content": False,
        "duplicate_skip": True,
        "db_uri": None,
    }

    async def get_settings(self, user_id: int) -> dict:
        doc = await self.settings.find_one(self._user_filter(user_id))
        if doc:
            merged = dict(self._DEFAULT_SETTINGS)
            saved  = doc.get("config", {})
            merged.update(saved)
            merged["filters"] = {**self._DEFAULT_SETTINGS["filters"],
                                  **merged.get("filters", {})}
            if "replace_rules" not in merged:
                merged["replace_rules"] = []
            if "extensions" not in merged:
                merged["extensions"] = []
            if "keywords" not in merged:
                merged["keywords"] = []
            return merged
        return dict(self._DEFAULT_SETTINGS)

    async def update_setting(self, user_id: int, key: str, value):
        await self.settings.update_one(
            self._user_filter(user_id),
            {"$set": {f"config.{key}": value}},
            upsert=True,
        )

    async def update_filter(self, user_id: int, filter_key: str, value: bool):
        await self.settings.update_one(
            self._user_filter(user_id),
            {"$set": {f"config.filters.{filter_key}": value}},
            upsert=True,
        )

    async def set_active(self, user_id: int, active: bool):
        await self.update_setting(user_id, "is_active", active)

    async def is_active(self, user_id: int) -> bool:
        s = await self.get_settings(user_id)
        return s.get("is_active", False)

    async def get_active_users(self) -> list[int]:
        cursor = self.settings.find({"config.is_active": True})
        return [doc["user_id"] async for doc in cursor]

    # ── replace rules ─────────────────────────────────────────────────────────

    async def get_replace_rules(self, user_id: int) -> list[dict]:
        s = await self.get_settings(user_id)
        return s.get("replace_rules", [])

    async def add_replace_rule(self, user_id: int, keyword: str, replace_with: str) -> bool:
        """Returns False if keyword already exists."""
        rules = await self.get_replace_rules(user_id)
        for r in rules:
            if r["keyword"].lower() == keyword.lower():
                return False
        rules.append({"keyword": keyword, "replace_with": replace_with})
        await self.update_setting(user_id, "replace_rules", rules)
        return True

    async def remove_replace_rule(self, user_id: int, keyword: str) -> bool:
        rules = await self.get_replace_rules(user_id)
        new_rules = [r for r in rules if r["keyword"].lower() != keyword.lower()]
        if len(new_rules) == len(rules):
            return False
        await self.update_setting(user_id, "replace_rules", new_rules)
        return True

    async def clear_replace_rules(self, user_id: int):
        await self.update_setting(user_id, "replace_rules", [])


    # ── premium ultra (multi-task) ─────────────────────────────────────────────

    async def add_premium_ultra(self, user_id: int, added_by: int):
        """Grant premium ultra to a user. Idempotent. Ultra implies premium."""
        await self.add_premium(user_id, added_by)
        await self.premium.update_one(
            self._user_filter(user_id),
            {"$set": {"ultra": True}},
            upsert=True,
        )

    async def remove_premium_ultra(self, user_id: int):
        """Downgrade user to regular premium (keep premium, remove ultra flag)."""
        await self.premium.update_one(
            self._user_filter(user_id),
            {"$unset": {"ultra": ""}},
        )

    async def is_premium_ultra(self, user_id: int) -> bool:
        if int(user_id) in Config.OWNER_ID:
            return True
        doc = await self.premium.find_one(self._user_filter(user_id))
        return bool(doc and doc.get("ultra"))

    # ── multi-task: per-task source→destination pairs ─────────────────────────

    async def get_tasks(self, user_id: int) -> list[dict]:
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        cursor = self.tasks.find({"user_id": int(user_id)})
        return sorted([doc async for doc in cursor], key=lambda d: d.get("task_id", 0))

    async def add_task(self, user_id: int) -> int:
        """Create a new empty task and return its task_id."""
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        existing = await self.get_tasks(user_id)
        task_id = (max((t["task_id"] for t in existing), default=0)) + 1
        await self.tasks.insert_one({
            "user_id": int(user_id),
            "task_id": task_id,
            "sources": [],
            "destination": None,
        })
        return task_id

    async def get_task(self, user_id: int, task_id: int) -> dict | None:
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        return await self.tasks.find_one({"user_id": int(user_id), "task_id": task_id})

    async def delete_task(self, user_id: int, task_id: int):
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        await self.tasks.delete_many({"user_id": int(user_id), "task_id": task_id})

    async def set_task_destination(self, user_id: int, task_id: int, chat_id: int, title: str):
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        await self.tasks.update_one(
            {"user_id": int(user_id), "task_id": task_id},
            {"$set": {"destination": {"chat_id": int(chat_id), "title": title}}},
        )

    async def add_task_source(self, user_id: int, task_id: int, chat_id: int, title: str) -> bool:
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        task = await self.get_task(user_id, task_id)
        if not task:
            return False
        sources = task.get("sources", [])
        if any(s["chat_id"] == int(chat_id) for s in sources):
            return False
        sources.append({"chat_id": int(chat_id), "title": title})
        await self.tasks.update_one(
            {"user_id": int(user_id), "task_id": task_id},
            {"$set": {"sources": sources}},
        )
        return True

    async def remove_task_source(self, user_id: int, task_id: int, chat_id: int) -> bool:
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        task = await self.get_task(user_id, task_id)
        if not task:
            return False
        old = task.get("sources", [])
        new = [s for s in old if s["chat_id"] != int(chat_id)]
        if len(new) == len(old):
            return False
        await self.tasks.update_one(
            {"user_id": int(user_id), "task_id": task_id},
            {"$set": {"sources": new}},
        )
        return True

    async def set_task_active(self, user_id: int, task_id: int, active: bool):
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        await self.tasks.update_one(
            {"user_id": int(user_id), "task_id": task_id},
            {"$set": {"is_active": active}},
        )

    async def get_active_tasks(self, user_id: int) -> list[dict]:
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        cursor = self.tasks.find({"user_id": int(user_id), "is_active": True})
        return [doc async for doc in cursor]

    async def get_users_with_active_tasks(self) -> list[int]:
        if not hasattr(self, "tasks"):
            self.tasks = self.db.tasks
        cursor = self.tasks.find({"is_active": True})
        user_ids = set()
        async for doc in cursor:
            if "user_id" in doc:
                user_ids.add(int(doc["user_id"]))
        return list(user_ids)


    # ── duplicate check helpers ────────────────────────────────────────────────
    async def is_duplicate(self, user_id: int, dest_chat_id: int, identifier: str) -> bool:
        doc = await self.duplicates.find_one({
            "user_id": int(user_id),
            "dest_chat_id": int(dest_chat_id),
            "identifier": identifier
        })
        return doc is not None

    async def add_duplicate(self, user_id: int, dest_chat_id: int, identifier: str):
        await self.duplicates.insert_one({
            "user_id": int(user_id),
            "dest_chat_id": int(dest_chat_id),
            "identifier": identifier
        })

    async def clear_duplicates(self, user_id: int, dest_chat_id: int):
        await self.duplicates.delete_many({
            "user_id": int(user_id),
            "dest_chat_id": int(dest_chat_id)
        })


db = Database(Config.DATABASE_URI, Config.DATABASE_NAME)
