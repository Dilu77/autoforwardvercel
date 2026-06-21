import os


class Config:
    # ── Telegram API credentials ──────────────────────────────────────────────
    API_ID   = os.environ.get("API_ID", "")
    API_HASH = os.environ.get("API_HASH", "")

    # ── Bot token ─────────────────────────────────────────────────────────────
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    # ── MongoDB ───────────────────────────────────────────────────────────────
    DATABASE_URI  = os.environ.get("DATABASE_URI", "")
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "LiveForwardBot")

    # ── Owner / admins ────────────────────────────────────────────────────────
    OWNER_ID = [
        int(x)
        for x in os.environ.get("OWNER_ID", "").split()
        if x.strip().lstrip("-").isdigit()
    ]

    # ── Bot pyrogram session name ─────────────────────────────────────────────
    BOT_SESSION = "live-forward-bot"

    # ── Free plan: watermark caption suffix ───────────────────────────────────
    FREE_CAPTION_TAG = os.environ.get("FREE_CAPTION_TAG", "\n\n📡 Forwarded by @fdforwardbot")

    # ── Free plan: initial delay in seconds before forwarding starts ──────────
    # During this window, no messages are fetched/forwarded.
    # Only messages arriving AFTER the wait is over are forwarded.
    FREE_PLAN_DELAY = int(os.environ.get("FREE_PLAN_DELAY", "60"))  # default 60s

    # ── Log channel: where invite links of to-channels are sent ──────────────
    # Set to a chat_id (negative for groups/channels) or leave empty to send
    # to all OWNER_IDs as a DM.
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0")) or None

    # ── Affiliate module ──────────────────────────────────────────────────────
    # Default affiliate tag used as fallback if no per-user tag is set.
    AFFILIATE_TAG = os.environ.get("AFFILIATE_TAG", "")

    # ── Multi-task (Premium Ultra) ────────────────────────────────────────────
    # Max number of tasks (source→dest pairs) an ultra user can create.
    MAX_ULTRA_TASKS = int(os.environ.get("MAX_ULTRA_TASKS", "10"))


class temp:
    """Runtime in-memory state – reset on each restart."""
    LISTENER_TASKS:  dict = {}
    USERBOT_CLIENTS: dict = {}
    ACTIVE_USERS:    set  = set()
    # user_id -> asyncio.Event  (set when free-plan delay expires)
    FREE_PLAN_READY: dict = {}
    # task_key (str: "task_{user_id}_{task_id}") -> asyncio.Task
    TASK_LISTENERS: dict = {}
