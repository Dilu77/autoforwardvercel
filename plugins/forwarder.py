"""
Live Forwarding Engine
──────────────────────
• Starts a Pyrogram userbot (from stored session string) per user.
• Registers a new_message handler on all configured source chat_ids.
• On each new message → immediately copies/forwards to destination.
• Handles FloodWait, filter rules, caption customisation, text replacement.
• Free plan: adds watermark caption + initial wait before forwarding.
• On userbot start: creates invite link for destination and logs to admins.
"""

import asyncio
import logging
import hashlib

from config import Config, temp
from database import db
from pyrogram import Client, filters
from pyrogram.errors import (
    ChannelPrivate,
    ChatAdminRequired,
    FloodWait,
    PeerIdInvalid,
    UserNotParticipant,
    ChatNotModified,
)
from pyrogram.types import Message
from plugins.affiliate import process_affiliate

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Userbot factory
# ─────────────────────────────────────────────────────────────────────────────


def _make_client(user_id: int, session_string: str = None, bot_token: str = None) -> Client:
    return Client(
        name=f"client_{user_id}",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        session_string=session_string,
        bot_token=bot_token,
        in_memory=True,
        workers=2,
        no_updates=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Text replacement helper
# ─────────────────────────────────────────────────────────────────────────────


def _apply_replacements(text: str, rules: list[dict]) -> str:
    """Apply all keyword→replacement rules to a string (case-sensitive)."""
    if not text or not rules:
        return text
    for rule in rules:
        text = text.replace(rule["keyword"], rule["replace_with"])
    return text


# ─────────────────────────────────────────────────────────────────────────────
#  Per-message forwarding logic
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
#  Filtering & Duplicate Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_media_file_unique_id(message: Message) -> str | None:
    if message.media:
        media_obj = getattr(message, message.media.value, None)
        if media_obj:
            return getattr(media_obj, "file_unique_id", None)
    return None

def _get_message_identifier(message: Message) -> str | None:
    fid = _get_media_file_unique_id(message)
    if fid:
        return f"media_{fid}"
    if message.text:
        h = hashlib.sha256(message.text.strip().encode("utf-8")).hexdigest()
        return f"text_{h}"
    return None

def _check_file_size(message: Message, file_size_mb_limit: int, size_limit_type: bool | None) -> bool:
    if file_size_mb_limit == 0 or size_limit_type is None:
        return True
    if message.media:
        media_obj = getattr(message, message.media.value, None)
        if media_obj:
            size_bytes = getattr(media_obj, "file_size", 0)
            if size_bytes:
                size_mb = size_bytes / (1024 * 1024)
                if size_limit_type == True:  # Greater than
                    return size_mb > file_size_mb_limit
                elif size_limit_type == False:  # Less than
                    return size_mb < file_size_mb_limit
    return True

def _check_extensions(message: Message, blacklisted_extensions: list[str]) -> bool:
    if not blacklisted_extensions:
        return True
    if message.media:
        media_obj = getattr(message, message.media.value, None)
        if media_obj:
            file_name = getattr(media_obj, "file_name", "")
            if file_name:
                ext = file_name.split(".")[-1].lower()
                if ext in blacklisted_extensions:
                    return False
    return True

def _check_keywords(message: Message, whitelisted_keywords: list[str]) -> bool:
    if not whitelisted_keywords:
        return True
    content = ""
    if message.text:
        content += " " + message.text.lower()
    if message.caption:
        content += " " + message.caption.lower()
    if message.media:
        media_obj = getattr(message, message.media.value, None)
        if media_obj:
            file_name = getattr(media_obj, "file_name", "")
            if file_name:
                content += " " + file_name.lower()
    for kw in whitelisted_keywords:
        if kw in content:
            return True
    return False

def _get_readable_file_size(size_bytes: int) -> str:
    units = ["Bytes", "KB", "MB", "GB"]
    size = float(size_bytes)
    i = 0
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.2f} {units[i]}"


async def _handle_message(
    userbot: Client,
    message: Message,
    bot_client: Client,
    user_id: int,
    is_premium: bool,
):
    try:
        is_premium    = await db.is_premium(user_id)
        settings      = await db.get_settings(user_id)
        dest_info     = await db.get_destination(user_id)

        if not dest_info:
            return

        dest_chat_id  = dest_info["chat_id"]
        forward_tag   = settings.get("forward_tag", False)
        remove_cap    = settings.get("remove_caption", False)
        custom_cap    = settings.get("custom_caption")
        msg_filters   = settings.get("filters", {})
        replace_rules = settings.get("replace_rules", [])

        # ── Affiliate mode: rewrite Amazon links & apply blacklist ──────────
        if await process_affiliate(userbot, message, user_id, dest_chat_id):
            return  # affiliate module handled (or dropped) this message

        # ── Filter by media type ────────────────────────────────────────────
        if message.text      and not msg_filters.get("text",      True): return
        if message.photo     and not msg_filters.get("photo",     True): return
        if message.video     and not msg_filters.get("video",     True): return
        if message.audio     and not msg_filters.get("audio",     True): return
        if message.document  and not msg_filters.get("document",  True): return
        if message.voice     and not msg_filters.get("voice",     True): return
        if message.animation and not msg_filters.get("animation", True): return
        if message.sticker   and not msg_filters.get("sticker",   True): return

        # ── Additional filters from settings (premium only) ──────────────────
        if is_premium:
            # 1. File size check
            limit_val = settings.get("file_size", 0)
            limit_type = settings.get("size_limit")
            if not _check_file_size(message, limit_val, limit_type):
                logger.info(f"[user {user_id}] Message skipped due to file size limits.")
                return

            # 2. Extensions blacklist
            blacklisted_exts = settings.get("extensions", [])
            if not _check_extensions(message, blacklisted_exts):
                logger.info(f"[user {user_id}] Message skipped due to extension blacklist.")
                return

            # 3. Keywords whitelist
            whitelisted_kws = settings.get("keywords", [])
            if not _check_keywords(message, whitelisted_kws):
                logger.info(f"[user {user_id}] Message skipped due to keywords whitelist.")
                return

            # 4. Duplicate prevention
            if settings.get("duplicate_skip", True):
                identifier = _get_message_identifier(message)
                if identifier:
                    if await db.is_duplicate(user_id, dest_chat_id, identifier):
                        logger.info(f"[user {user_id}] Message skipped (duplicate detected).")
                        return
                    await db.add_duplicate(user_id, dest_chat_id, identifier)

        # ── Parse custom button (premium only) ──────────────────────────────
        reply_markup = None
        if is_premium and settings.get("button"):
            from plugins.settings import parse_custom_buttons
            reply_markup = parse_custom_buttons(settings.get("button"))

        protect_content = settings.get("protect_content", False) if is_premium else False

        # ── Decide how to forward ───────────────────────────────────────────
        if forward_tag and is_premium:
            # Native forward keeps "Forwarded from" tag; replacement doesn't apply
            await _safe_forward(userbot, dest_chat_id, message, protect_content=protect_content)
        else:
            caption = _resolve_caption(
                message, remove_cap, custom_cap, replace_rules, is_premium
            )
            # Apply replacements to plain text messages too
            text_override = None
            if message.text and not message.media:
                text_override = _apply_replacements(message.text, replace_rules)
                if not is_premium:
                    text_override = (text_override or "") + Config.FREE_CAPTION_TAG

            await _safe_copy(
                userbot, dest_chat_id, message, caption,
                text_override=text_override,
                reply_markup=reply_markup,
                protect_content=protect_content,
            )

    except Exception as e:
        logger.error(f"[user {user_id}] Error handling message: {e}")


def _resolve_caption(
    message: Message,
    remove_cap: bool,
    custom_cap: str | None,
    replace_rules: list[dict],
    is_premium: bool,
) -> str | None:
    """
    Returns the caption to pass to copy_message.
    None = keep original (Pyrogram default).
    """
    if remove_cap and is_premium:
        return ""

    original = message.caption or ""
    # Apply text replacement rules to caption
    original_replaced = _apply_replacements(str(original), replace_rules)

    if custom_cap and is_premium:
        media_obj = getattr(message, message.media.value, None) if message.media else None
        filename = getattr(media_obj, "file_name", "") if media_obj else ""
        file_size_bytes = getattr(media_obj, "file_size", 0) if media_obj else 0
        size_str = _get_readable_file_size(file_size_bytes) if file_size_bytes else ""
        try:
            result = custom_cap.format(
                caption=original_replaced,
                filename=filename,
                size=size_str
            )
        except Exception:
            result = custom_cap
        return result

    if not is_premium:
        # Watermark appended to existing caption
        base = original_replaced if original_replaced else (str(original) if original else "")
        return base + Config.FREE_CAPTION_TAG

    # Premium, no custom caption: apply replacements to original caption
    if replace_rules and original:
        return original_replaced

    return None  # keep original as-is


async def _safe_forward(userbot: Client, dest: int, message: Message, protect_content: bool = False):
    while True:
        try:
            await userbot.forward_messages(
                chat_id=dest,
                from_chat_id=message.chat.id,
                message_ids=message.id,
                protect_content=protect_content,
            )
            return
        except FloodWait as e:
            logger.warning(f"FloodWait {e.value}s on forward, sleeping...")
            await asyncio.sleep(e.value + 1)
        except (ChatAdminRequired, ChannelPrivate, PeerIdInvalid) as e:
            logger.error(f"Cannot forward to destination: {e}")
            return
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return


async def _safe_copy(
    userbot: Client,
    dest: int,
    message: Message,
    caption,
    text_override: str | None = None,
    reply_markup=None,
    protect_content: bool = False,
):
    while True:
        try:
            if text_override is not None and message.text and not message.media:
                # Send as a new text message with replacement applied
                await userbot.send_message(
                    chat_id=dest, 
                    text=text_override,
                    reply_markup=reply_markup,
                    protect_content=protect_content
                )
            else:
                await userbot.copy_message(
                    chat_id=dest,
                    from_chat_id=message.chat.id,
                    message_id=message.id,
                    caption=caption,
                    reply_markup=reply_markup,
                    protect_content=protect_content
                )
            return
        except FloodWait as e:
            logger.warning(f"FloodWait {e.value}s on copy, sleeping...")
            await asyncio.sleep(e.value + 1)
        except (ChatAdminRequired, ChannelPrivate, PeerIdInvalid) as e:
            logger.error(f"Cannot copy to destination: {e}")
            return
        except Exception as e:
            logger.error(f"Copy error: {e}")
            return


# ─────────────────────────────────────────────────────────────────────────────
#  Invite link + log helper
# ─────────────────────────────────────────────────────────────────────────────


async def _log_invite_link(
    bot_client: Client,
    userbot: Client,
    user_id: int,
    dest_chat_id: int,
    dest_title: str,
):
    """
    Ask the userbot to create an invite link for dest_chat_id,
    then send it to LOG_CHANNEL or all owners.
    """
    try:
        link_obj = await userbot.create_chat_invite_link(dest_chat_id)
        invite   = link_obj.invite_link
    except Exception as e:
        logger.warning(f"[user {user_id}] Could not create invite link: {e}")
        invite = "_(could not create invite link — bot may not be admin)_"

    me = await userbot.get_me()
    log_text = (
        f"🔗 <b>New Forwarder Started</b>\n\n"
        f"👤 User: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
        f"🤖 Userbot: {me.first_name} (@{me.username or 'N/A'})\n"
        f"📤 Destination: <b>{dest_title}</b> (<code>{dest_chat_id}</code>)\n"
        f"🔗 Invite Link: {invite}"
    )

    if Config.LOG_CHANNEL:
        try:
            await bot_client.send_message(Config.LOG_CHANNEL, log_text)
        except Exception as e:
            logger.error(f"Could not send to LOG_CHANNEL: {e}")
    else:
        for owner_id in Config.OWNER_ID:
            try:
                await bot_client.send_message(owner_id, log_text)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
#  Listener task
# ─────────────────────────────────────────────────────────────────────────────


async def _listener_task(bot_client: Client, user_id: int, userbot: Client, is_premium: bool):
    try:
        sources    = await db.get_sources(user_id)
        source_ids = [s["chat_id"] for s in sources]

        if not source_ids:
            logger.warning(f"[user {user_id}] No source channels configured.")
            return

        logger.info(
            f"[user {user_id}] Starting live listener | "
            f"premium={is_premium} | sources: {source_ids}"
        )

        # ── Free-plan delay: wait before forwarding ─────────────────────────
        if not is_premium and Config.FREE_PLAN_DELAY > 0:
            delay = Config.FREE_PLAN_DELAY
            logger.info(f"[user {user_id}] Free plan: waiting {delay}s before forwarding.")

            ready_event = asyncio.Event()
            temp.FREE_PLAN_READY[user_id] = ready_event

            # Register handler now but gate on the event
            @userbot.on_message(filters.chat(source_ids))
            async def on_new_message_free(client: Client, message: Message):
                if not ready_event.is_set():
                    return  # still in delay window, ignore
                await _handle_message(client, message, bot_client, user_id, is_premium)

            await asyncio.sleep(delay)
            ready_event.set()
            temp.FREE_PLAN_READY.pop(user_id, None)
            logger.info(f"[user {user_id}] Free plan delay over, forwarding active.")

        else:
            # Premium: start immediately
            @userbot.on_message(filters.chat(source_ids))
            async def on_new_message(client: Client, message: Message):
                await _handle_message(client, message, bot_client, user_id, is_premium)

        # Keep alive
        while True:
            await asyncio.sleep(10)

    except asyncio.CancelledError:
        logger.info(f"[user {user_id}] Listener task cancelled.")
    except Exception as e:
        logger.error(f"[user {user_id}] Listener task crashed: {e}")
    finally:
        try:
            await userbot.stop()
        except Exception:
            pass
        temp.USERBOT_CLIENTS.pop(user_id, None)
        temp.LISTENER_TASKS.pop(user_id, None)
        temp.FREE_PLAN_READY.pop(user_id, None)
        temp.ACTIVE_USERS.discard(user_id)
        logger.info(f"[user {user_id}] Userbot stopped and cleaned up.")


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────


async def launch_userbot(bot_client: Client, user_id: int) -> str | None:
    if user_id in temp.ACTIVE_USERS:
        return "already_running"

    settings = await db.get_settings(user_id)
    client_type = settings.get("client_type", "session")

    if client_type == "session":
        session_string = await db.get_session(user_id)
        if not session_string:
            return "no_session"
        userbot = _make_client(user_id, session_string=session_string)
    else:
        bot_token = await db.get_bot_token(user_id)
        if not bot_token:
            return "no_bot_token"
        userbot = _make_client(user_id, bot_token=bot_token)

    sources = await db.get_sources(user_id)
    dest = await db.get_destination(user_id)
    is_premium = await db.is_premium(user_id)

    try:
        await userbot.start()
    except Exception as e:
        logger.error(f"[user {user_id}] Userbot start failed: {e}")
        return f"start_error: {e}"

    temp.USERBOT_CLIENTS[user_id] = userbot
    temp.ACTIVE_USERS.add(user_id)

    main_started = False
    if sources and dest:
        asyncio.get_event_loop().create_task(
            _log_invite_link(bot_client, userbot, user_id, dest["chat_id"], dest["title"])
        )
        task = asyncio.get_event_loop().create_task(
            _listener_task(bot_client, user_id, userbot, is_premium)
        )
        temp.LISTENER_TASKS[user_id] = task
        await db.set_active(user_id, True)
        main_started = True

    # Re-launch active multi-tasks for Ultra / Owner users
    tasks_started = 0
    if await db.is_premium_ultra(user_id) or user_id in Config.OWNER_ID:
        active_tasks = await db.get_active_tasks(user_id)
        if active_tasks:
            from plugins.tasks import start_single_task_listener
            for t in active_tasks:
                try:
                    if await start_single_task_listener(bot_client, user_id, t["task_id"]):
                        tasks_started += 1
                except Exception as e:
                    logger.warning(f"Could not auto-resume task {t.get('task_id')} for {user_id}: {e}")

    if not main_started and tasks_started == 0:
        try:
            await userbot.stop()
        except Exception:
            pass
        temp.USERBOT_CLIENTS.pop(user_id, None)
        temp.ACTIVE_USERS.discard(user_id)
        if not sources:
            return "no_sources"
        if not dest:
            return "no_destination"

    logger.info(f"[user {user_id}] Live forwarding started (main={main_started}, multi_tasks={tasks_started}, premium={is_premium}).")
    return None  # success


async def stop_userbot(user_id: int):
    task = temp.LISTENER_TASKS.get(user_id)
    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=5)
        except Exception:
            pass

    # Also cancel any running multi-tasks for this user
    tasks_to_cancel = [k for k in temp.TASK_LISTENERS if k.startswith(f"task_{user_id}_")]
    for k in tasks_to_cancel:
        t_obj = temp.TASK_LISTENERS.pop(k, None)
        if t_obj and not t_obj.done():
            t_obj.cancel()

    userbot = temp.USERBOT_CLIENTS.get(user_id)
    if userbot:
        try:
            await userbot.stop()
        except Exception:
            pass

    temp.LISTENER_TASKS.pop(user_id, None)
    temp.USERBOT_CLIENTS.pop(user_id, None)
    temp.FREE_PLAN_READY.pop(user_id, None)
    temp.ACTIVE_USERS.discard(user_id)

    await db.set_active(user_id, False)
    logger.info(f"[user {user_id}] Live forwarding stopped.")


def is_running(user_id: int) -> bool:
    return user_id in temp.ACTIVE_USERS


# ─────────────────────────────────────────────────────────────────────────────
#  Task-aware variant: handle a message for a specific destination
#  (used by multi-task system so each task can route to its own dest)
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_message_for_dest(
    userbot: Client,
    message: Message,
    bot_client: Client,
    user_id: int,
    is_premium: bool,
    dest_chat_id: int,
):
    """Same as _handle_message but uses a given dest_chat_id instead of DB lookup."""
    try:
        is_premium    = await db.is_premium(user_id)
        settings      = await db.get_settings(user_id)
        forward_tag   = settings.get("forward_tag", False)
        remove_cap    = settings.get("remove_caption", False)
        custom_cap    = settings.get("custom_caption")
        msg_filters   = settings.get("filters", {})
        replace_rules = settings.get("replace_rules", [])

        # ── Affiliate mode ──────────────────────────────────────────────────
        if await process_affiliate(userbot, message, user_id, dest_chat_id):
            return

        # ── Filter by media type ────────────────────────────────────────────
        if message.text      and not msg_filters.get("text",      True): return
        if message.photo     and not msg_filters.get("photo",     True): return
        if message.video     and not msg_filters.get("video",     True): return
        if message.audio     and not msg_filters.get("audio",     True): return
        if message.document  and not msg_filters.get("document",  True): return
        if message.voice     and not msg_filters.get("voice",     True): return
        if message.animation and not msg_filters.get("animation", True): return
        if message.sticker   and not msg_filters.get("sticker",   True): return

        # ── Additional filters from settings (premium only) ──────────────────
        if is_premium:
            # 1. File size check
            limit_val = settings.get("file_size", 0)
            limit_type = settings.get("size_limit")
            if not _check_file_size(message, limit_val, limit_type):
                logger.info(f"[user {user_id}][task dest {dest_chat_id}] Message skipped due to file size limits.")
                return

            # 2. Extensions blacklist
            blacklisted_exts = settings.get("extensions", [])
            if not _check_extensions(message, blacklisted_exts):
                logger.info(f"[user {user_id}][task dest {dest_chat_id}] Message skipped due to extension blacklist.")
                return

            # 3. Keywords whitelist
            whitelisted_kws = settings.get("keywords", [])
            if not _check_keywords(message, whitelisted_kws):
                logger.info(f"[user {user_id}][task dest {dest_chat_id}] Message skipped due to keywords whitelist.")
                return

            # 4. Duplicate prevention
            if settings.get("duplicate_skip", True):
                identifier = _get_message_identifier(message)
                if identifier:
                    if await db.is_duplicate(user_id, dest_chat_id, identifier):
                        logger.info(f"[user {user_id}][task dest {dest_chat_id}] Message skipped (duplicate detected).")
                        return
                    await db.add_duplicate(user_id, dest_chat_id, identifier)

        # ── Parse custom button (premium only) ──────────────────────────────
        reply_markup = None
        if is_premium and settings.get("button"):
            from plugins.settings import parse_custom_buttons
            reply_markup = parse_custom_buttons(settings.get("button"))

        protect_content = settings.get("protect_content", False) if is_premium else False

        if forward_tag and is_premium:
            await _safe_forward(userbot, dest_chat_id, message, protect_content=protect_content)
        else:
            caption = _resolve_caption(message, remove_cap, custom_cap, replace_rules, is_premium)
            text_override = None
            if message.text and not message.media:
                text_override = _apply_replacements(message.text, replace_rules)
                if not is_premium:
                    text_override = (text_override or "") + Config.FREE_CAPTION_TAG
            await _safe_copy(
                userbot, dest_chat_id, message, caption, 
                text_override=text_override,
                reply_markup=reply_markup,
                protect_content=protect_content
            )

    except Exception as e:
        logger.error(f"[user {user_id}][task dest {dest_chat_id}] Error handling message: {e}")
