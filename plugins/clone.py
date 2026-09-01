import asyncio
import logging
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import Config
from plugins.forwarder import _make_client, _handle_message_for_dest

logger = logging.getLogger(__name__)

_PENDING_CLONE = {}
_RUNNING_CLONES = set()

# Regex for telegram message link: t.me/c/chat_id/message_id or t.me/username/message_id
LINK_RE = re.compile(r"https?://(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([a-zA-Z0-9_]+)/(?:[0-9]+/)?(\d+)")

def _back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="clone_cancel")]])

@Client.on_callback_query(filters.regex(r"^clone_start$"))
async def cb_clone_start(bot: Client, query):
    user_id = query.from_user.id
    if user_id in _RUNNING_CLONES:
        return await query.answer("⚠️ You already have a history forwarding task running in the background. Please wait for it to complete.", show_alert=True)
    
    await query.answer()
    await _start_clone_wizard(bot, user_id, query)

@Client.on_callback_query(filters.regex(r"^clone_cancel$"))
async def cb_clone_cancel(bot: Client, query):
    user_id = query.from_user.id
    _PENDING_CLONE.pop(user_id, None)
    await query.message.edit_text("❌ Forwarding process cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]))

async def _start_clone_wizard(bot: Client, user_id: int, query):
    chat_id = query.message.chat.id
    if user_id in _PENDING_CLONE:
        return await query.message.edit_text(
            "⚠️ You are already setting up a forwarding task. Use /cancel to reset.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]])
        )

    _PENDING_CLONE[user_id] = {}

    dest_info = await db.get_destination(user_id)
    if not dest_info:
        _PENDING_CLONE.pop(user_id, None)
        return await query.message.edit_text(
            "❌ Please set a destination channel first in the settings menu.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]])
        )
    
    dest_chat_id = dest_info["chat_id"]

    prompt = await query.message.edit_text(
        "🗄️ **Forward Old Messages Wizard**\n\n"
        f"**Destination:** {dest_info['title']}\n\n"
        "Please send the **link to the FIRST message** you want to start forwarding from.\n"
        "Example: `https://t.me/c/1234567/10` or `https://t.me/channelusername/10`\n\n"
        "*(Send /cancel to abort)*",
        reply_markup=_back_btn()
    )

    try:
        msg1 = await bot.listen(chat_id=chat_id, user_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        _PENDING_CLONE.pop(user_id, None)
        return await prompt.edit("⏰ Timed out.")

    if not msg1.text:
        _PENDING_CLONE.pop(user_id, None)
        return await prompt.edit("❌ Please send a valid text link containing the message URL.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]))

    if msg1.text.strip().lower() == "/cancel":
        _PENDING_CLONE.pop(user_id, None)
        await msg1.delete()
        return await prompt.edit("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]))

    match1 = LINK_RE.search(msg1.text.strip())
    if not match1:
        _PENDING_CLONE.pop(user_id, None)
        return await prompt.edit("❌ Invalid link format. Please try again.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]))
    
    source_chat_id_str = match1.group(1)
    if source_chat_id_str.isdigit():
        source_chat_id = int("-100" + source_chat_id_str)
    else:
        source_chat_id = source_chat_id_str
    start_msg_id = int(match1.group(2))
    await msg1.delete()

    await prompt.edit(
        "✅ Start message registered.\n\n"
        "Now, send the **link to the LAST message** you want to forward (must be from the same channel).\n"
        "*(Send /cancel to abort)*",
        reply_markup=_back_btn()
    )

    try:
        msg2 = await bot.listen(chat_id=chat_id, user_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        _PENDING_CLONE.pop(user_id, None)
        return await prompt.edit("⏰ Timed out.")

    if not msg2.text:
        _PENDING_CLONE.pop(user_id, None)
        return await prompt.edit("❌ Please send a valid text link containing the message URL.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]))

    if msg2.text.strip().lower() == "/cancel":
        _PENDING_CLONE.pop(user_id, None)
        await msg2.delete()
        return await prompt.edit("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]))

    match2 = LINK_RE.search(msg2.text.strip())
    if not match2:
        _PENDING_CLONE.pop(user_id, None)
        return await prompt.edit("❌ Invalid link format.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]))
    
    end_msg_id = int(match2.group(2))
    await msg2.delete()

    if start_msg_id > end_msg_id:
        start_msg_id, end_msg_id = end_msg_id, start_msg_id

    total_msgs = end_msg_id - start_msg_id + 1
    _PENDING_CLONE[user_id] = {
        "source": source_chat_id,
        "dest": dest_chat_id,
        "start": start_msg_id,
        "end": end_msg_id
    }

    buttons = [[
        InlineKeyboardButton("✅ ᴄᴏɴꜰɪʀᴍ & ꜱᴛᴀʀᴛ", callback_data="clone_confirm"),
        InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="clone_cancel")
    ]]
    await prompt.edit(
        f"🗄️ **Ready to Forward!**\n\n"
        f"**Source:** `{source_chat_id}`\n"
        f"**Destination:** `{dest_chat_id}`\n"
        f"**Messages:** {start_msg_id} to {end_msg_id} (Up to {total_msgs} messages)\n\n"
        "Do you want to start the forwarding process? This will run in the background.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^clone_confirm$"))
async def cb_clone_confirm(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in _PENDING_CLONE:
        return await query.answer("No pending forwarding task found.", show_alert=True)
    
    data = _PENDING_CLONE.pop(user_id)
    await query.message.edit_text("⏳ **Forwarding process started in background!** You will be notified when it's complete.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]))
    
    # Launch background task
    asyncio.get_event_loop().create_task(_run_clone_task(bot, user_id, data))

async def _run_clone_task(bot: Client, user_id: int, data: dict):
    _RUNNING_CLONES.add(user_id)
    try:
        source = data["source"]
        dest = data["dest"]
        start_id = data["start"]
        end_id = data["end"]

        settings = await db.get_settings(user_id)
        client_type = settings.get("client_type", "session")

        if client_type == "session":
            session_string = await db.get_session(user_id)
            if not session_string:
                return await bot.send_message(user_id, "❌ Forwarding failed: No session found.")
            user_client = _make_client(user_id, session_string=session_string)
        else:
            bot_token = await db.get_bot_token(user_id)
            if not bot_token:
                return await bot.send_message(user_id, "❌ Forwarding failed: No bot token found.")
            user_client = _make_client(user_id, bot_token=bot_token)

        try:
            await user_client.start()
        except Exception as e:
            return await bot.send_message(user_id, f"❌ Forwarding failed to start client: {e}")

        success = 0
        failed = 0
        is_premium = await db.is_premium(user_id) # dynamic premium check for watermark

        try:
            msg_ids = list(range(start_id, end_id + 1))
            
            # get_messages max 200 per call, we batch it.
            chunk_size = 200
            for i in range(0, len(msg_ids), chunk_size):
                chunk = msg_ids[i:i + chunk_size]
                messages = await user_client.get_messages(source, chunk)
                
                for msg in messages:
                    if msg.empty:
                        continue
                    try:
                        await _handle_message_for_dest(user_client, msg, bot, user_id, is_premium, dest)
                        success += 1
                    except Exception:
                        failed += 1
                    await asyncio.sleep(1.5) # generous sleep to avoid FloodWait
                    
        except Exception as e:
            logger.error(f"Forwarding old messages error for user {user_id}: {e}")
            await bot.send_message(user_id, f"⚠️ Forwarding process interrupted by an error: {e}")
        finally:
            try:
                await user_client.stop()
            except Exception:
                pass
            await bot.send_message(
                user_id, 
                f"✅ **Forwarding Process Completed!**\n\n"
                f"**Successfully forwarded:** {success} messages.\n"
                f"**Failed:** {failed} messages."
            )
    finally:
        _RUNNING_CLONES.discard(user_id)
