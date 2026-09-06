"""
Multi-Task Forwarding (Premium Ultra + Owner only)
───────────────────────────────────────────────────
Allows premium ultra users to configure multiple independent forwarding tasks,
each with their own set of source channels → destination channel mapping.

A "task" is a named pair: one destination + N source channels.
Task 1, Task 2, … each run as independent listeners on the same userbot session.

Commands / UI:
  Accessed via 📋 ᴛᴀꜱᴋꜱ button in main menu (only shown to ultra/owner).
  From there: list tasks, add/edit/delete tasks, set sources & destination per task.
"""

import asyncio
import logging

from config import Config, temp
from database import db
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChannelPrivate, ChatAdminRequired, PeerIdInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

MAX_TASKS = int(getattr(Config, "MAX_ULTRA_TASKS", 10))

_HOME = [[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]
_BACK_TASKS = [[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="tasks_menu")]]


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _task_key(user_id: int, task_id: int) -> str:
    return f"task_{user_id}_{task_id}"


async def _ultra_guard(query) -> bool:
    """Return True (and answer the query) if user is NOT ultra — block access."""
    user_id = query.from_user.id
    if user_id in Config.OWNER_ID:
        return False
    if not await db.is_premium_ultra(user_id):
        await query.answer(
            "🌟 Multi-task is a Premium Ultra feature. Contact admin to upgrade.",
            show_alert=True,
        )
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
#  Tasks menu
# ─────────────────────────────────────────────────────────────────────────────

async def tasks_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    tasks = await db.get_tasks(user_id)
    rows = []

    for t in tasks:
        tid = t["task_id"]
        dest = t.get("destination")
        dest_name = dest["title"] if dest else "no dest"
        src_count = len(t.get("sources", []))
        # show running state
        running = _task_key(user_id, tid) in temp.TASK_LISTENERS
        icon = "▶️" if running else "⏹"
        rows.append([
            InlineKeyboardButton(
                f"{icon} ᴛᴀꜱᴋ {tid}: {src_count} ꜱʀᴄ → {dest_name}",
                callback_data=f"task_view_{tid}",
            )
        ])

    if len(tasks) < MAX_TASKS:
        rows.append([InlineKeyboardButton("➕ ɴᴇᴡ ᴛᴀꜱᴋ", callback_data="task_new")])
    rows.append([InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^tasks_menu$"))
async def cb_tasks_menu(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    tasks = await db.get_tasks(user_id)
    await query.message.edit_text(
        f"📋 <b>Your Tasks</b> ({len(tasks)}/{MAX_TASKS})\n\n"
        "Each task has its own sources → destination mapping.\n"
        "All tasks share your single userbot session.",
        reply_markup=await tasks_menu_keyboard(user_id),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Create new task
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^task_new$"))
async def cb_task_new(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    tasks = await db.get_tasks(user_id)
    if len(tasks) >= MAX_TASKS:
        return await query.answer(f"Max {MAX_TASKS} tasks allowed.", show_alert=True)

    task_id = await db.add_task(user_id)
    await query.answer(f"Task {task_id} created!")
    # Show the task edit panel immediately
    await _show_task_panel(bot, query, user_id, task_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Task panel
# ─────────────────────────────────────────────────────────────────────────────

async def _show_task_panel(bot, query, user_id: int, task_id: int):
    task = await db.get_task(user_id, task_id)
    if not task:
        return await query.message.edit_text(
            "Task not found.", reply_markup=InlineKeyboardMarkup(_BACK_TASKS)
        )

    dest = task.get("destination")
    sources = task.get("sources", [])
    running = _task_key(user_id, task_id) in temp.TASK_LISTENERS

    dest_text = f"{dest['title']} (<code>{dest['chat_id']}</code>)" if dest else "❌ Not set"
    src_lines = "\n".join(
        f"  • {s['title']} (<code>{s['chat_id']}</code>)" for s in sources
    ) or "  _(none)_"

    toggle_label = "⏹ ꜱᴛᴏᴘ ᴛᴀꜱᴋ" if running else "▶️ ꜱᴛᴀʀᴛ ᴛᴀꜱᴋ"
    toggle_data  = f"task_stop_{task_id}"  if running else f"task_start_{task_id}"

    rows = [
        [InlineKeyboardButton("📥 ᴀᴅᴅ ꜱᴏᴜʀᴄᴇ",    callback_data=f"task_addsrc_{task_id}")],
        [InlineKeyboardButton("🗑 ʀᴇᴍᴏᴠᴇ ꜱᴏᴜʀᴄᴇ", callback_data=f"task_rmsrc_{task_id}")],
        [InlineKeyboardButton("📤 ꜱᴇᴛ ᴅᴇꜱᴛ",      callback_data=f"task_setdest_{task_id}")],
        [InlineKeyboardButton(toggle_label,         callback_data=toggle_data)],
        [InlineKeyboardButton("🗑 ᴅᴇʟᴇᴛᴇ ᴛᴀꜱᴋ",    callback_data=f"task_delete_{task_id}")],
        [InlineKeyboardButton("↩ ʙᴀᴄᴋ",            callback_data="tasks_menu")],
    ]

    await query.message.edit_text(
        f"📋 <b>Task {task_id}</b>  {'▶️ Running' if running else '⏹ Stopped'}\n\n"
        f"<b>Sources ({len(sources)}):</b>\n{src_lines}\n\n"
        f"<b>Destination:</b> {dest_text}",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@Client.on_callback_query(filters.regex(r"^task_view_(\d+)$"))
async def cb_task_view(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    task_id = int(query.data.split("_")[-1])
    await _show_task_panel(bot, query, user_id, task_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Add / remove source per task
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^task_addsrc_(\d+)$"))
async def cb_task_addsrc(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    task_id = int(query.data.split("_")[-1])
    await query.answer()

    prompt = await query.message.edit_text(
        f"📥 <b>Add Source — Task {task_id}</b>\n\n"
        "Forward a message from the source channel, or send its username / ID.\n\n"
        "<i>Send /cancel to abort. Timeout: 3 min.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"task_view_{task_id}")]]
        ),
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=180)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ Timed out.", reply_markup=InlineKeyboardMarkup(_HOME))

    if msg.text and msg.text.strip() == "/cancel":
        await msg.delete()
        return await _show_task_panel(bot, query, user_id, task_id)

    # Resolve channel — try userbot first (for private groups), then bot
    userbot = temp.USERBOT_CLIENTS.get(user_id)
    chat_id, title = await _resolve_chat(userbot or bot, msg)
    await msg.delete()

    if chat_id is None:
        return await prompt.edit(
            f"❌ Could not resolve chat: {title}\n\nTry sending a forwarded message, @username, or numeric ID.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data=f"task_view_{task_id}")]]),
        )

    added = await db.add_task_source(user_id, task_id, chat_id, title)
    if not added:
        await prompt.edit(
            f"⚠️ <code>{title}</code> is already a source for Task {task_id}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data=f"task_view_{task_id}")]]),
        )
    else:
        await query.answer(f"✅ Added {title}", show_alert=False)
        await _show_task_panel(bot, query, user_id, task_id)


@Client.on_callback_query(filters.regex(r"^task_rmsrc_(\d+)$"))
async def cb_task_rmsrc(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    task_id = int(query.data.split("_")[-1])

    task = await db.get_task(user_id, task_id)
    sources = task.get("sources", []) if task else []

    if not sources:
        return await query.answer("No sources to remove.", show_alert=True)

    rows = [
        [InlineKeyboardButton(f"🗑 {s['title']}", callback_data=f"task_rmsrc_confirm_{task_id}_{s['chat_id']}")]
        for s in sources
    ]
    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data=f"task_view_{task_id}")])
    await query.message.edit_text(
        f"🗑 <b>Remove Source — Task {task_id}</b>\n\nTap a source to remove it:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@Client.on_callback_query(filters.regex(r"^task_rmsrc_confirm_(\d+)_(-?\d+)$"))
async def cb_task_rmsrc_confirm(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    parts = query.data.split("_")
    task_id = int(parts[3])
    chat_id = int(parts[4])

    await db.remove_task_source(user_id, task_id, chat_id)
    await query.answer("✅ Removed", show_alert=False)
    await _show_task_panel(bot, query, user_id, task_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Set destination per task
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^task_setdest_(\d+)$"))
async def cb_task_setdest(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    task_id = int(query.data.split("_")[-1])
    await query.answer()

    prompt = await query.message.edit_text(
        f"📤 <b>Set Destination — Task {task_id}</b>\n\n"
        "Forward a message from the destination channel, or send its username / ID.\n\n"
        "<i>Send /cancel to abort. Timeout: 3 min.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"task_view_{task_id}")]]
        ),
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=180)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ Timed out.", reply_markup=InlineKeyboardMarkup(_HOME))

    if msg.text and msg.text.strip() == "/cancel":
        await msg.delete()
        return await _show_task_panel(bot, query, user_id, task_id)

    # Try userbot first (for private channels/groups), then bot
    userbot = temp.USERBOT_CLIENTS.get(user_id)
    chat_id, title = await _resolve_chat(userbot or bot, msg)
    await msg.delete()

    if chat_id is None:
        return await prompt.edit(
            f"❌ Could not resolve chat: {title}\n\nTry sending a forwarded message, @username, or numeric ID.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data=f"task_view_{task_id}")]]),
        )

    await db.set_task_destination(user_id, task_id, chat_id, title)
    await query.answer(f"✅ Destination set to {title}", show_alert=False)
    await _show_task_panel(bot, query, user_id, task_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Delete task
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^task_delete_(\d+)$"))
async def cb_task_delete(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    task_id = int(query.data.split("_")[-1])

    # Stop task if running
    key = _task_key(user_id, task_id)
    if key in temp.TASK_LISTENERS:
        task_obj = temp.TASK_LISTENERS.pop(key)
        if not task_obj.done():
            task_obj.cancel()

    await db.set_task_active(user_id, task_id, False)
    await db.delete_task(user_id, task_id)
    await query.answer(f"Task {task_id} deleted.", show_alert=False)
    await cb_tasks_menu(bot, query)


# ─────────────────────────────────────────────────────────────────────────────
#  Start / stop individual task
# ─────────────────────────────────────────────────────────────────────────────

async def start_single_task_listener(bot: Client, user_id: int, task_id: int) -> bool:
    """Helper to start task listener if userbot client is available."""
    key = _task_key(user_id, task_id)
    if key in temp.TASK_LISTENERS:
        return True
    userbot = temp.USERBOT_CLIENTS.get(user_id)
    if not userbot:
        return False
    is_premium = True
    loop_task = asyncio.get_event_loop().create_task(
        _task_listener(bot, user_id, task_id, userbot, is_premium)
    )
    temp.TASK_LISTENERS[key] = loop_task
    return True


@Client.on_callback_query(filters.regex(r"^task_start_(\d+)$"))
async def cb_task_start(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    task_id = int(query.data.split("_")[-1])

    task = await db.get_task(user_id, task_id)
    if not task:
        return await query.answer("Task not found.", show_alert=True)
    if not task.get("destination"):
        return await query.answer("Set a destination first.", show_alert=True)
    if not task.get("sources"):
        return await query.answer("Add at least one source first.", show_alert=True)

    key = _task_key(user_id, task_id)
    if key in temp.TASK_LISTENERS:
        return await query.answer("Already running.", show_alert=True)

    userbot = temp.USERBOT_CLIENTS.get(user_id)
    if not userbot:
        from plugins.forwarder import launch_userbot
        await launch_userbot(bot, user_id)
        userbot = temp.USERBOT_CLIENTS.get(user_id)
        if not userbot:
            return await query.answer(
                "Could not start session client. Please add a session string or bot token first.",
                show_alert=True,
            )

    started = await start_single_task_listener(bot, user_id, task_id)
    if started:
        await db.set_task_active(user_id, task_id, True)
        await query.answer(f"Task {task_id} started ✅", show_alert=False)
    else:
        await query.answer("Could not start task listener.", show_alert=True)

    await _show_task_panel(bot, query, user_id, task_id)


@Client.on_callback_query(filters.regex(r"^task_stop_(\d+)$"))
async def cb_task_stop(bot: Client, query):
    if await _ultra_guard(query):
        return
    user_id = query.from_user.id
    task_id = int(query.data.split("_")[-1])

    key = _task_key(user_id, task_id)
    task_obj = temp.TASK_LISTENERS.pop(key, None)
    if task_obj and not task_obj.done():
        task_obj.cancel()

    await db.set_task_active(user_id, task_id, False)
    await query.answer(f"Task {task_id} stopped.", show_alert=False)
    await _show_task_panel(bot, query, user_id, task_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Listener coroutine per task
# ─────────────────────────────────────────────────────────────────────────────

async def _task_listener(bot_client, user_id: int, task_id: int, userbot, is_premium: bool):
    from plugins.forwarder import _handle_message_for_dest
    from pyrogram import filters as pyro_filters
    from pyrogram.handlers import MessageHandler

    task = await db.get_task(user_id, task_id)
    if not task:
        return

    source_ids = [s["chat_id"] for s in task.get("sources", [])]
    dest_chat_id = task["destination"]["chat_id"]

    logger.info(f"[user {user_id}] Task {task_id} listener starting | sources: {source_ids} → {dest_chat_id}")

    async def on_task_message(client, message):
        await _handle_message_for_dest(client, message, bot_client, user_id, is_premium, dest_chat_id)

    handler = MessageHandler(on_task_message, pyro_filters.chat(source_ids))
    userbot.add_handler(handler)

    try:
        while True:
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        logger.info(f"[user {user_id}] Task {task_id} listener cancelled.")
    finally:
        try:
            userbot.remove_handler(handler)
        except Exception as e:
            logger.error(f"Error removing task handler: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: resolve a chat from a message or text
# ─────────────────────────────────────────────────────────────────────────────

async def _resolve_chat(bot: Client, msg: Message) -> tuple:
    """
    Universal resolver — delegates to channels._resolve_chat_universal.
    Tries userbot first (for private groups/channels), then falls back to bot.
    """
    from plugins.channels import _resolve_chat_universal
    # Try with bot client first
    result = await _resolve_chat_universal(bot, msg)
    if result[0] is not None:
        return result
    # Also attempt with the userbot for the sender if it's running
    user_id = msg.from_user.id if msg.from_user else None
    if user_id:
        userbot = temp.USERBOT_CLIENTS.get(user_id)
        if userbot:
            try:
                result2 = await _resolve_chat_universal(userbot, msg)
                if result2[0] is not None:
                    return result2
            except Exception:
                pass
    return result  # return the (None, error) from the bot attempt
