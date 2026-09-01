import asyncio
import logging
import hashlib
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import temp
from plugins.forwarder import _make_client
from plugins.channels import _resolve_chat_universal

logger = logging.getLogger(__name__)

_RUNNING_CLEANERS = set()
_PENDING_CLEANERS = {}

_CANCEL_BTN = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel ✖️", callback_data="unequify_cancel_task")]])
_HOME_BTN = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="main_menu")]])

DUPLICATE_TEXT = """
🧹 <b>𝙳𝚞𝚙𝚕𝚒𝚌𝚊𝚝𝚎 𝙲𝚕𝚎𝚊𝚗𝚎𝚛 (𝚄𝚗𝚎𝚚𝚞𝚒𝚏𝚢)</b>

• <b>𝚂𝚌𝚊𝚗𝚗𝚎𝚍 𝚖e𝚜𝚜𝚊𝚐𝚎𝚜:</b> <code>{}</code>
• <b>𝙳𝚞𝚙𝚕𝚒𝚌𝚊𝚝𝚎𝚜 𝚍𝚎𝚕𝚎𝚝𝚎𝚍:</b> <code>{}</code>
• <b>𝚂𝚝𝚊𝚝𝚞𝚜:</b> <code>{}</code>
"""

# Helper to get media file ID
def _get_media_file_unique_id(message: Message) -> str | None:
    if message.media:
        media_obj = getattr(message, message.media.value, None)
        if media_obj:
            return getattr(media_obj, "file_unique_id", None)
    return None

@Client.on_message(filters.command("unequify") & filters.private)
async def cmd_unequify(bot: Client, message: Message):
    user_id = message.from_user.id
    is_premium = await db.is_premium(user_id)
    if not is_premium:
        return await message.reply_text("🌟 𝚃𝚑𝚒𝚜 𝚠𝚒𝚕𝚕 𝚘𝚗𝚕𝚢 𝚠𝚘𝚛𝚔 𝚏𝚘𝚛 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚞𝚜𝚎𝚛𝚜.")

    if user_id in _RUNNING_CLEANERS:
        return await message.reply_text("⚠️ You already have a duplicate cleaning process running.")

    # Start wizard
    await _start_unequify_wizard(bot, user_id, message.chat.id)


async def cb_unequify_start(bot: Client, query):
    user_id = query.from_user.id
    if user_id in _RUNNING_CLEANERS:
        return await query.answer("⚠️ You already have a duplicate cleaning process running.", show_alert=True)
    await query.answer()
    await _start_unequify_wizard(bot, user_id, query.message.chat.id, query.message)


async def _start_unequify_wizard(bot: Client, user_id: int, chat_id: int, edit_msg=None):
    _PENDING_CLEANERS[user_id] = {}

    prompt_text = (
        "🧹 <b>𝙳𝚞𝚙𝚕𝚒𝚌𝚊𝚝𝚎 𝙲𝚕𝚎𝚊𝚗𝚎𝚛 (𝚄𝚗𝚎𝚚𝚞𝚒𝚏𝚢)</b>\n\n"
        "𝙿𝚕𝚎𝚊𝚜𝚎 𝚜𝚎𝚗𝚍 <b>𝚊𝚗𝚢 𝚘𝚗𝚎</b> 𝚘𝚏 𝚝𝚑𝚎𝚜𝚎 𝚏𝚘𝚛 𝚝𝚑𝚎 𝚌𝚑𝚊𝚝 𝚢𝚘𝚞 𝚠𝚊𝚗𝚝 𝚝𝚘 𝚌𝚕𝚎𝚊𝚗:\n"
        "• Forward a message from that chat\n"
        "• Send <code>@username</code>\n"
        "• Send numeric chat ID (e.g. <code>-1001234567890</code>)\n"
        "• Send a message link from the chat (e.g. <code>https://t.me/c/1234567890/10</code>)\n\n"
        "<i>Send /cancel to abort. Timeout: 3 min.</i>"
    )

    if edit_msg:
        prompt = await edit_msg.edit_text(prompt_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="menu_settings")]]))
    else:
        prompt = await bot.send_message(chat_id, prompt_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="menu_settings")]]))

    try:
        msg = await bot.listen(chat_id=chat_id, user_id=user_id, timeout=180)
    except asyncio.TimeoutError:
        _PENDING_CLEANERS.pop(user_id, None)
        return await prompt.edit("⏰ Timed out.", reply_markup=_HOME_BTN)

    if msg.text and msg.text.strip().lower() == "/cancel":
        _PENDING_CLEANERS.pop(user_id, None)
        await msg.delete()
        return await prompt.edit("❌ Cancelled.", reply_markup=_HOME_BTN)

    # Resolve chat using universal resolver
    # Try using user's userbot first if running
    userbot = temp.USERBOT_CLIENTS.get(user_id)
    target_chat_id, title = await _resolve_chat_universal(userbot or bot, msg)
    await msg.delete()

    if target_chat_id is None:
        _PENDING_CLEANERS.pop(user_id, None)
        return await prompt.edit(
            f"❌ Could not resolve chat: {title}\n\nTry sending a link or username instead.",
            reply_markup=_HOME_BTN
        )

    _PENDING_CLEANERS[user_id] = {
        "chat_id": target_chat_id,
        "title": title
    }

    buttons = [
        [
            InlineKeyboardButton("✅ ᴄᴏɴꜰɪʀᴍ", callback_data="unequify_confirm"),
            InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="menu_settings")
        ]
    ]

    await prompt.edit(
        f"🧹 <b>𝚁𝚎𝚊𝚍𝚢 𝚝𝚘 𝙲𝚕𝚎𝚊𝚗!</b>\n\n"
        f"• <b>𝙲𝚑𝚊𝚝:</b> {title} (<code>{target_chat_id}</code>)\n\n"
        "𝚃𝚑𝚒𝚜 𝚠𝚒𝚕𝚕 𝚜𝚌𝚊𝚗 the latest message history and delete duplicates. "
        "𝙼𝚊𝚔𝚎 𝚜𝚞𝚛𝚎 𝚢𝚘𝚞package 𝚞𝚜𝚎package𝚋𝚘package 𝚑𝚊𝚜 <b>𝚍𝚎𝚕𝚎𝚝𝚎 package𝚎package𝚖package𝚜𝚜package𝚜𝚜𝚘package𝚗</b> in this chat!\n\n"
        " do you want to start?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex(r"^unequify_confirm$"))
async def cb_unequify_confirm(bot: Client, query):
    user_id = query.from_user.id
    data = _PENDING_CLEANERS.pop(user_id, None)
    if not data:
        return await query.answer("No pending unequify session.", show_alert=True)

    await query.answer()
    prompt = await query.message.edit_text("⏳ Starting cleaner task in background...")

    asyncio.get_event_loop().create_task(_run_unequify_task(bot, user_id, data["chat_id"], data["title"], prompt))


@Client.on_callback_query(filters.regex(r"^unequify_cancel_task$"))
async def cb_unequify_cancel_task(bot: Client, query):
    user_id = query.from_user.id
    if user_id in _RUNNING_CLEANERS:
        _RUNNING_CLEANERS.discard(user_id)
        await query.answer("Cancelling task...")
    else:
        await query.answer("No running cleaner task to cancel.")


async def _run_unequify_task(bot: Client, user_id: int, target_chat_id: int, chat_title: str, prompt: Message):
    _RUNNING_CLEANERS.add(user_id)

    # Use running userbot if available
    user_client = temp.USERBOT_CLIENTS.get(user_id)
    should_stop_client = False

    if not user_client:
        session_string = await db.get_session(user_id)
        if not session_string:
            _RUNNING_CLEANERS.discard(user_id)
            return await prompt.edit("❌ Clean failed: No Pyrogram session found. Set session string first.", reply_markup=_HOME_BTN)

        user_client = _make_client(user_id, session_string=session_string)
        try:
            await user_client.start()
            should_stop_client = True
        except Exception as e:
            _RUNNING_CLEANERS.discard(user_id)
            return await prompt.edit(f"❌ Userbot failed to start: {e}", reply_markup=_HOME_BTN)

    scanned = 0
    deleted_count = 0
    seen_media = set()
    seen_text = set()
    batch_delete = []

    try:
        await prompt.edit(DUPLICATE_TEXT.format(scanned, deleted_count, "Scanning history..."), reply_markup=_CANCEL_BTN)
        
        # Scan last 2000 messages (most users duplicate within this range; change limit if needed)
        async for msg in user_client.get_chat_history(chat_id=target_chat_id, limit=2000):
            if user_id not in _RUNNING_CLEANERS:
                await prompt.edit(DUPLICATE_TEXT.format(scanned, deleted_count, "Cancelled ❌"), reply_markup=_HOME_BTN)
                break

            scanned += 1
            if scanned % 100 == 0:
                try:
                    await prompt.edit(DUPLICATE_TEXT.format(scanned, deleted_count, "Scanning history..."), reply_markup=_CANCEL_BTN)
                except Exception:
                    pass

            if msg.empty or msg.service:
                continue

            is_duplicate = False

            # Check media
            fid = _get_media_file_unique_id(msg)
            if fid:
                if fid in seen_media:
                    is_duplicate = True
                else:
                    seen_media.add(fid)
            # Check text
            elif msg.text:
                thash = hashlib.sha256(msg.text.strip().encode("utf-8")).hexdigest()
                if thash in seen_text:
                    is_duplicate = True
                else:
                    seen_text.add(thash)

            if is_duplicate:
                batch_delete.append(msg.id)
                if len(batch_delete) >= 50:
                    try:
                        await user_client.delete_messages(chat_id=target_chat_id, message_ids=batch_delete)
                        deleted_count += len(batch_delete)
                        batch_delete = []
                        await prompt.edit(DUPLICATE_TEXT.format(scanned, deleted_count, f"Cleaning duplicates ({deleted_count} deleted)..."), reply_markup=_CANCEL_BTN)
                    except Exception as e:
                        logger.error(f"Error bulk deleting: {e}")
                    await asyncio.sleep(1.0) # avoid rate limit

        # Delete any remaining duplicates
        if batch_delete and user_id in _RUNNING_CLEANERS:
            try:
                await user_client.delete_messages(chat_id=target_chat_id, message_ids=batch_delete)
                deleted_count += len(batch_delete)
            except Exception as e:
                logger.error(f"Error bulk deleting: {e}")

        if user_id in _RUNNING_CLEANERS:
            await prompt.edit(
                f"🎉 <b>𝙳𝚞𝚙𝚕𝚒𝚌𝚊𝚝𝚎𝚜 𝙲𝚕𝚎𝚊𝚗𝚎𝚍 𝚂𝚞𝚌𝚌𝚎𝚜𝚜𝚏𝚞𝚕𝚕𝚢!</b>\n\n"
                f"• <b>𝙲𝚑𝚊𝚝:</b> {chat_title}\n"
                f"• <b>𝚂𝚌𝚊package package𝚎𝚍:</b> <code>{scanned}</code> messages\n"
                f"• <b>𝙳𝚎𝚕𝚎package𝚎𝚍:</b> <code>{deleted_count}</code> duplicates",
                reply_markup=_HOME_BTN
            )
    except Exception as e:
        logger.error(f"Error during unequify task: {e}")
        await prompt.edit(f"⚠️ Clean task interrupted by error:\n<code>{e}</code>", reply_markup=_HOME_BTN)
    finally:
        _RUNNING_CLEANERS.discard(user_id)
        if should_stop_client:
            try:
                await user_client.stop()
            except Exception:
                pass
