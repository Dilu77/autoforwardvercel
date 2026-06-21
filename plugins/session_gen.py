"""
Session-string generator that runs entirely inside the bot chat.

Flow
────
1. User sends /generate_session  (or taps button)
2. Bot asks for phone number
3. Bot asks for OTP
4. Bot asks for 2FA password if needed
5. Session string is saved to MongoDB via db.set_session()

Uses Telethon StringSession so the string is ~350 chars and compatible
with the Pyrogram StringSession format used when monitoring.
We generate a Pyrogram-compatible session using pyrogram itself (in-memory)
so no Telethon dependency is needed.
"""

import asyncio
import logging
import re

from config import Config, temp
from database import db
from pyrogram import Client, filters
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
    FloodWait,
)
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logger = logging.getLogger(__name__)

# Tracks users currently in the generation wizard
_PENDING: dict[int, dict] = {}

CANCEL_TEXT = "/cancel"


def _back_btn():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="gen_cancel")]]
    )


# ── Entry points ──────────────────────────────────────────────────────────────


@Client.on_message(filters.private & filters.command("generate_session"))
async def cmd_generate_session(bot: Client, message: Message):
    await _start_generation(bot, message.from_user.id, message.chat.id)


@Client.on_callback_query(filters.regex(r"^gen_start$"))
async def cb_generate_session(bot: Client, query):
    await query.answer()
    await _start_generation(bot, query.from_user.id, query.message.chat.id)


@Client.on_callback_query(filters.regex(r"^gen_bot_start$"))
async def cb_gen_bot_start(bot: Client, query):
    await query.answer()
    await _start_bot_generation(bot, query.from_user.id, query.message.chat.id)


@Client.on_callback_query(filters.regex(r"^gen_cancel$"))
async def cb_gen_cancel(bot: Client, query):
    user_id = query.from_user.id
    _PENDING.pop(user_id, None)
    await query.answer("𝚂𝚎𝚜𝚜𝚒𝚘𝚗 𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚒𝚘𝚗 𝚌𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.", show_alert=True)
    await query.message.delete()


# ── Internal wizard ───────────────────────────────────────────────────────────


async def _start_generation(bot: Client, user_id: int, chat_id: int):
    if user_id in _PENDING:
        await bot.send_message(
            chat_id,
            "⚠️ 𝚈𝚘𝚞 𝚊𝚕𝚛𝚎𝚊𝚍𝚢 𝚑𝚊𝚟𝚎 𝚊𝚗 𝚊𝚌𝚝𝚒𝚟𝚎 𝚜𝚎𝚜𝚜𝚒𝚘𝚗 𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚒𝚘𝚗. "
            "𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝 𝚒𝚝 𝚏𝚒𝚛𝚜𝚝.",
        )
        return

    _PENDING[user_id] = {}

    prompt = await bot.send_message(
        chat_id,
        "📱 <b>𝚂𝚎𝚜𝚜𝚒𝚘𝚗 𝙶𝚎𝚗𝚎𝚛𝚊𝚝𝚘𝚛</b>\n\n"
        "𝚂𝚎𝚗𝚍 𝚢𝚘𝚞𝚛 <b>𝚙𝚑𝚘𝚗𝚎 𝚗𝚞𝚖𝚋𝚎𝚛</b> 𝚒𝚗 𝚒𝚗𝚝𝚎𝚛𝚗𝚊𝚝𝚒𝚘𝚗𝚊𝚕 𝚏𝚘𝚛𝚖𝚊𝚝.\n"
        "𝙴𝚡𝚊𝚖𝚙𝚕𝚎: <code>+919876543210</code>\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝.</i>",
        reply_markup=_back_btn(),
    )

    try:
        phone_msg = await bot.listen(chat_id=chat_id, user_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        _PENDING.pop(user_id, None)
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗.")

    if phone_msg.text.strip().lower() == CANCEL_TEXT:
        _PENDING.pop(user_id, None)
        await phone_msg.delete()
        return await prompt.edit("❌ 𝚂𝚎𝚜𝚜𝚒𝚘𝚗 𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚒𝚘𝚗 𝚌𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.")

    phone = phone_msg.text.strip()
    await phone_msg.delete()

    # ── Create an in-memory pyrogram client for the user ─────────────────────
    user_client = Client(
        name=f"session_gen_{user_id}",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        in_memory=True,
    )

    await prompt.edit("🔄 𝙲𝚘𝚗𝚗𝚎𝚌𝚝𝚒𝚗𝚐 𝚝𝚘 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖...")

    try:
        await user_client.connect()
    except Exception as e:
        _PENDING.pop(user_id, None)
        return await prompt.edit(f"❌ 𝙲𝚘𝚗𝚗𝚎𝚌𝚝𝚒𝚘𝚗 𝚏𝚊𝚒𝚕𝚎𝚍:\n<code>{e}</code>")

    # ── Send OTP ──────────────────────────────────────────────────────────────
    try:
        sent_code = await user_client.send_code(phone)
    except PhoneNumberInvalid:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        return await prompt.edit("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚙𝚑𝚘𝚗𝚎 𝚗𝚞𝚖𝚋𝚎𝚛. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗.")
    except FloodWait as e:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        return await prompt.edit(
            f"⏳ 𝙵𝚕𝚘𝚘𝚍 𝚠𝚊𝚒𝚝! 𝙿𝚕𝚎𝚊𝚜𝚎 𝚠𝚊𝚒𝚝 <b>{e.value}</b> 𝚜𝚎𝚌𝚘𝚗𝚍𝚜 𝚊𝚗𝚍 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗."
        )
    except Exception as e:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        return await prompt.edit(f"❌ 𝙴𝚛𝚛𝚘𝚛: <code>{e}</code>")

    await prompt.edit(
        "✅ 𝙾𝚃𝙿 𝚜𝚎𝚗𝚝 𝚝𝚘 𝚢𝚘𝚞𝚛 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚊𝚌𝚌𝚘𝚞𝚗𝚝.\n\n"
        "📨 𝙴𝚗𝚝𝚎𝚛 𝚝𝚑𝚎 𝙾𝚃𝙿 𝚒𝚗 𝚝𝚑𝚎 𝚏𝚘𝚛𝚖𝚊𝚝: <code>1 2 3 4 5</code> (𝚠𝚒𝚝𝚑 𝚜𝚙𝚊𝚌𝚎𝚜)\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝.</i>",
        reply_markup=_back_btn(),
    )

    try:
        otp_msg = await bot.listen(chat_id=chat_id, user_id=user_id, timeout=180)
    except asyncio.TimeoutError:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝 𝚠𝚊𝚒𝚝𝚒𝚗𝚐 𝚏𝚘𝚛 𝙾𝚃𝙿.")

    if otp_msg.text.strip().lower() == CANCEL_TEXT:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        await otp_msg.delete()
        return await prompt.edit("❌ 𝚂𝚎𝚜𝚜𝚒𝚘𝚗 𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚒𝚘𝚗 𝚌𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.")

    otp = otp_msg.text.strip().replace(" ", "")
    await otp_msg.delete()

    # ── Sign in ───────────────────────────────────────────────────────────────
    try:
        await user_client.sign_in(phone, sent_code.phone_code_hash, otp)

    except PhoneCodeInvalid:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        return await prompt.edit("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝙾𝚃𝙿. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗.")

    except PhoneCodeExpired:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        return await prompt.edit("❌ 𝙾𝚃𝙿 𝚎𝚡𝚙𝚒𝚛𝚎𝚍. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚜𝚝𝚊𝚛𝚝 𝚊𝚐𝚊𝚒𝚗 𝚠𝚒𝚝𝚑 /𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚎_𝚜𝚎𝚜𝚜𝚒𝚘𝚗.")

    except SessionPasswordNeeded:
        # ── 2-FA ─────────────────────────────────────────────────────────────
        await prompt.edit(
            "🔐 𝚃𝚠𝚘-𝚜𝚝𝚎𝚙 𝚟𝚎𝚛𝚒𝚏𝚒𝚌𝚊𝚝𝚒𝚘𝚗 𝚒𝚜 𝚎𝚗𝚊𝚋𝚕𝚎𝚍.\n\n"
            "𝚂𝚎𝚗𝚍 𝚢𝚘𝚞𝚛 <b>𝚌𝚕𝚘𝚞𝚍 𝚙𝚊𝚜𝚜𝚠𝚘𝚛𝚍</b>:\n\n"
            "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝.</i>",
            reply_markup=_back_btn(),
        )
        try:
            pw_msg = await bot.listen(chat_id=chat_id, user_id=user_id, timeout=120)
        except asyncio.TimeoutError:
            _PENDING.pop(user_id, None)
            await user_client.disconnect()
            return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝 𝚠𝚊𝚒𝚝𝚒𝚗𝚐 𝚏𝚘𝚛 𝚙𝚊𝚜𝚜𝚠𝚘𝚛𝚍.")

        if pw_msg.text.strip().lower() == CANCEL_TEXT:
            _PENDING.pop(user_id, None)
            await user_client.disconnect()
            await pw_msg.delete()
            return await prompt.edit("❌ 𝚂𝚎𝚜𝚜𝚒𝚘𝚗 𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚒𝚘𝚗 𝚌𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.")

        password = pw_msg.text.strip()
        await pw_msg.delete()

        try:
            await user_client.check_password(password)
        except Exception as e:
            _PENDING.pop(user_id, None)
            await user_client.disconnect()
            return await prompt.edit(f"❌ 𝙿𝚊𝚜𝚜𝚠𝚘𝚛𝚍 𝚎𝚛𝚛𝚘𝚛: <code>{e}</code>")

    except Exception as e:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        return await prompt.edit(f"❌ 𝚂𝚒𝚐𝚗-𝚒𝚗 𝚎𝚛𝚛𝚘𝚛: <code>{e}</code>")

    # ── Export session string ─────────────────────────────────────────────────
    try:
        session_string = await user_client.export_session_string()
        me = await user_client.get_me()
        await user_client.disconnect()
    except Exception as e:
        _PENDING.pop(user_id, None)
        await user_client.disconnect()
        return await prompt.edit(f"❌ 𝙲𝚘𝚞𝚕𝚍 𝚗𝚘𝚝 𝚎𝚡𝚙𝚘𝚛𝚝 𝚜𝚎𝚜𝚜𝚒𝚘𝚗: <code>{e}</code>")

    # Save to MongoDB
    await db.set_session(user_id, session_string)
    _PENDING.pop(user_id, None)

    await prompt.edit(
        f"✅ <b>𝚂𝚎𝚜𝚜𝚒𝚘𝚗 𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚎𝚍 𝚜𝚞𝚌𝚌𝚎𝚜𝚜𝚏𝚞𝚕𝚕𝚢!</b>\n\n"
        f"👤 𝙻𝚘𝚐𝚐𝚎𝚍 𝚒𝚗 𝚊𝚜: <b>{me.first_name}</b> (@{me.username or '𝙽/𝙰'})\n\n"
        "𝚈𝚘𝚞𝚛 𝚜𝚎𝚜𝚜𝚒𝚘𝚗 𝚑𝚊𝚜 𝚋𝚎𝚎𝚗 𝚜𝚊𝚟𝚎𝚍 𝚜𝚎𝚌𝚞𝚛𝚎𝚕𝚢. "
        "𝚈𝚘𝚞 𝚌𝚊𝚗 𝚗𝚘𝚠 𝚜𝚎𝚝 𝚜𝚘𝚞𝚛𝚌𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜 𝚊𝚗𝚍 𝚜𝚝𝚊𝚛𝚝 𝚕𝚒𝚟𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐!",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="main_menu")]]
        ),
    )
    logger.info(f"Session generated for user {user_id} ({me.first_name})")


# ── Bot Token Wizard ──────────────────────────────────────────────────────────

async def _start_bot_generation(bot: Client, user_id: int, chat_id: int):
    if user_id in _PENDING:
        await bot.send_message(
            chat_id,
            "⚠️ 𝚈𝚘𝚞 𝚊𝚕𝚛𝚎𝚊𝚍𝚢 𝚑𝚊𝚟𝚎 𝚊𝚗 𝚊𝚌𝚝𝚒𝚟𝚎 𝚜𝚎𝚜𝚜𝚒𝚘𝚗/𝚋𝚘𝚝 𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚒𝚘𝚗. "
            "𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝 𝚒𝚝 𝚏𝚒𝚛𝚜𝚝.",
        )
        return

    _PENDING[user_id] = {}

    prompt = await bot.send_message(
        chat_id,
        "🤖 <b>𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗 𝚂𝚎𝚝𝚞𝚙</b>\n\n"
        "𝙿𝚕𝚎𝚊𝚜𝚎 𝚜𝚎𝚗𝚍 𝚢𝚘𝚞𝚛 <b>𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗</b> 𝚘𝚋𝚝𝚊𝚒𝚗𝚎𝚍 𝚏𝚛𝚘𝚖 @BotFather.\n"
        "𝙴𝚡𝚊𝚖𝚙𝚕𝚎: <code>123456789:ABCdefGHIjklmNOPqrstUVWxyz</code>\n\n"
        "<i>Note: The bot MUST be an admin in your source and destination channels.</i>\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝.</i>",
        reply_markup=_back_btn(),
    )

    try:
        token_msg = await bot.listen(chat_id=chat_id, user_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        _PENDING.pop(user_id, None)
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗.")

    if token_msg.text.strip().lower() == CANCEL_TEXT:
        _PENDING.pop(user_id, None)
        await token_msg.delete()
        return await prompt.edit("❌ 𝙱𝚘𝚝 𝚝𝚘𝚔𝚎ɴ 𝚜𝚎𝚝𝚞𝚙 𝚌𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.")

    bot_token = token_msg.text.strip()
    await token_msg.delete()

    if not re.match(r"^\d+:[A-Za-z0-9_-]+$", bot_token):
        _PENDING.pop(user_id, None)
        return await prompt.edit("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚋𝚘𝚝 𝚝𝚘𝚔𝚎𝚗 𝚏𝚘𝚛𝚖𝚊𝚝. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗.")

    await prompt.edit("🔄 𝚅𝚎𝚛𝚒𝚏𝚢𝚒𝚗𝚐 𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗...")

    # Validate token
    test_client = Client(
        name=f"test_bot_{user_id}",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=bot_token,
        in_memory=True
    )
    
    try:
        await test_client.start()
        me = await test_client.get_me()
        await test_client.stop()
    except Exception as e:
        _PENDING.pop(user_id, None)
        return await prompt.edit(f"❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗 𝚘𝚛 𝚌𝚘𝚗𝚗𝚎𝚌𝚝𝚒𝚘𝚗 𝚎𝚛𝚛𝚘𝚛:\n<code>{e}</code>")

    # Save to MongoDB
    await db.set_bot_token(user_id, bot_token)
    await db.update_setting(user_id, "client_type", "bot") # Automatically set active to bot
    
    _PENDING.pop(user_id, None)

    await prompt.edit(
        f"✅ <b>𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗 𝚜𝚊𝚟𝚎𝚍 𝚜𝚞𝚌𝚌𝚎𝚜𝚜𝚏𝚞𝚕𝚕𝚢!</b>\n\n"
        f"🤖 𝙱𝚘𝚝: <b>{me.first_name}</b> (@{me.username})\n\n"
        "𝚈𝚘𝚞𝚛 𝚋𝚘𝚝 𝚝𝚘𝚔𝚎𝚗 𝚒𝚜 𝚗𝚘𝚠 𝚊𝚌𝚝𝚒𝚟𝚎 𝚏𝚘𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐. "
        "𝙿𝚕𝚎𝚊𝚜𝚎 𝚎𝚗𝚜𝚞𝚛𝚎 𝚝𝚑𝚒𝚜 𝚋𝚘𝚝 𝚒𝚜 𝚊𝚍𝚍𝚎𝚍 𝚊𝚜 𝚊𝚗 <b>𝙰𝚍𝚖𝚒𝚗</b> 𝚝𝚘 𝚊𝚕𝚕 𝚢𝚘𝚞𝚛 𝚜𝚘𝚞𝚛𝚌𝚎 𝚊𝚗𝚍 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="main_menu")]]
        ),
    )
    logger.info(f"Bot token added for user {user_id} (@{me.username})")