"""
Source & Destination channel management.

Adding a source / setting destination → user can send ANY of:
  1. A forwarded message from the channel/group
  2. @username  (public)
  3. -1001234567890  (numeric chat ID)
  4. https://t.me/c/1234567890/N  (private channel link)
  5. https://t.me/username/N  (public link)

Groups, supergroups, and channels are all accepted.
"""

import asyncio
import logging
import re

from database import db
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logger = logging.getLogger(__name__)

_BACK_BTN = [[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")]]

# Matches:  t.me/c/CHATID/MSGID   or   t.me/username/MSGID
_LINK_RE = re.compile(
    r"https?://(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([a-zA-Z0-9_]+)/(?:[0-9]+/)?(\d+)"
)


# ─────────────────────────────────────────────────────────────────────────────
#  Universal chat resolver
# ─────────────────────────────────────────────────────────────────────────────

async def _resolve_chat_universal(bot: Client, msg: Message) -> tuple:
    """
    Return (chat_id, title) or (None, error_message).

    Resolution priority:
      1. Forwarded message  → use forward_from_chat
      2. t.me/c/ private link  → parse numeric ID
      3. t.me/username/N public link → parse username
      4. @username / plain username
      5. Numeric chat ID (with or without -100 prefix)
    """

    # ── 1. Forwarded message ────────────────────────────────────────────────
    if msg.forward_from_chat:
        chat = msg.forward_from_chat
        return chat.id, chat.title or chat.username or str(chat.id)

    raw = (msg.text or "").strip()
    if not raw:
        return None, "No input provided."

    # ── 2. t.me/c/ private channel link ────────────────────────────────────
    if "t.me/c/" in raw:
        parts = raw.rstrip("/").split("/")
        try:
            c_idx = parts.index("c")
            raw_id = parts[c_idx + 1]
            chat_id = int("-100" + raw_id) if raw_id.isdigit() else int(raw_id)
            try:
                chat = await bot.get_chat(chat_id)
                return chat.id, chat.title or str(chat.id)
            except Exception:
                return chat_id, f"Private Chat ({chat_id})"
        except (ValueError, IndexError) as e:
            return None, f"Could not parse private link: {e}"

    # ── 3. General t.me link (public) ───────────────────────────────────────
    m = _LINK_RE.search(raw)
    if m:
        seg = m.group(1)
        if seg.isdigit():
            identifier = int("-100" + seg)
        else:
            identifier = f"@{seg}"
        try:
            chat = await bot.get_chat(identifier)
            return chat.id, chat.title or str(identifier)
        except Exception as e:
            return None, f"Could not resolve from link: {e}"

    # ── 4. @username ─────────────────────────────────────────────────────────
    if raw.startswith("@") or (not raw.lstrip("-").isdigit()):
        identifier = raw if raw.startswith("@") else f"@{raw}"
        try:
            chat = await bot.get_chat(identifier)
            return chat.id, chat.title or str(identifier)
        except Exception as e:
            return None, f"Could not find '{identifier}': {e}"

    # ── 5. Numeric ID ────────────────────────────────────────────────────────
    if raw.lstrip("-").isdigit():
        chat_id = int(raw)
        try:
            chat = await bot.get_chat(chat_id)
            return chat.id, chat.title or str(chat_id)
        except Exception:
            # Bot not in chat — trust the ID if it looks plausible
            if abs(chat_id) > 1000:
                return chat_id, f"Chat {chat_id}"
            return None, f"Could not resolve chat ID {chat_id}."

    return None, f"Unrecognised input: {raw[:80]}"


# ─────────────────────────────────────────────────────────────────────────────
#  Sources menu
# ─────────────────────────────────────────────────────────────────────────────


async def _sources_keyboard(user_id: int) -> InlineKeyboardMarkup:
    sources = await db.get_sources(user_id)
    rows = []
    for s in sources:
        label = f"❌ {s['title'][:25]}"
        rows.append([
            InlineKeyboardButton(label, callback_data=f"src_remove_{s['chat_id']}")
        ])
    rows.append([InlineKeyboardButton("➕ ᴀᴅᴅ ꜱᴏᴜʀᴄᴇ", callback_data="src_add")])
    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")])
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^menu_sources$"))
async def cb_menu_sources(bot: Client, query):
    user_id = query.from_user.id
    await query.message.edit_text(
        "📥 <b>𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚕𝚜 / 𝙶𝚛𝚘𝚞𝚙𝚜</b>\n\n"
        "𝚃𝚑𝚎𝚜𝚎 𝚊𝚛𝚎 𝚝𝚑𝚎 𝚌𝚑𝚊𝚝𝚜 𝙸 𝚖𝚘𝚗𝚒𝚝𝚘𝚛 𝚏𝚘𝚛 𝚗𝚎𝚠 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜.\n"
        "𝚃𝚊𝚙 𝚊 𝚗𝚊𝚖𝚎 𝚝𝚘 <b>𝚛𝚎𝚖𝚘𝚟𝚎</b> 𝚒𝚝.\n\n"
        "<i>𝙰𝚌𝚌𝚎𝚙𝚝𝚜: 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚍 𝚖𝚜𝚐, @𝚞𝚜𝚎𝚛𝚗𝚊𝚖𝚎, 𝚌𝚑𝚊𝚝 𝙸𝙳, 𝚘𝚛 𝚝.𝚖𝚎 𝚕𝚒𝚗𝚔.</i>",
        reply_markup=await _sources_keyboard(user_id),
    )


@Client.on_callback_query(filters.regex(r"^src_add$"))
async def cb_src_add(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    prompt = await query.message.edit_text(
        "📥 <b>𝙰𝚍𝚍 𝚂𝚘𝚞𝚛𝚌𝚎</b>\n\n"
        "𝚂𝚎𝚗𝚍 <b>𝚊𝚗𝚢 𝚘𝚗𝚎</b> 𝚘𝚏 𝚝𝚑𝚎𝚜𝚎:\n"
        "• 𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚌𝚑𝚊𝚝\n"
        "• <code>@username</code>\n"
        "• <code>-1001234567890</code> (𝚗𝚞𝚖𝚎𝚛𝚒𝚌 𝙸𝙳)\n"
        "• <code>https://t.me/c/1234567890/1</code> (𝚙𝚛𝚒𝚟𝚊𝚝𝚎 𝚕𝚒𝚗𝚔)\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚖𝚒𝚗.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="menu_sources")]]
        ),
    )

    try:
        fwd_msg: Message = await bot.listen(
            chat_id=query.message.chat.id, user_id=user_id, timeout=300
        )
    except asyncio.TimeoutError:
        return await prompt.edit(
            "⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.",
            reply_markup=InlineKeyboardMarkup(_BACK_BTN),
        )

    if fwd_msg.text and fwd_msg.text.strip().lower() in ("/cancel", "cancel"):
        await fwd_msg.delete()
        return await prompt.edit(
            "❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.",
            reply_markup=InlineKeyboardMarkup(_BACK_BTN),
        )

    chat_id, title = await _resolve_chat_universal(bot, fwd_msg)
    await fwd_msg.delete()

    if chat_id is None:
        return await prompt.edit(
            f"⚠️ 𝙲𝚘𝚞𝚕𝚍 𝚗𝚘𝚝 𝚛𝚎𝚜𝚘𝚕𝚟𝚎 𝚌𝚑𝚊𝚝.\n<code>{title}</code>\n\n"
            "𝚃𝚛𝚢 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚌𝚑𝚊𝚝 𝚒𝚗𝚜𝚝𝚎𝚊𝚍.",
            reply_markup=await _sources_keyboard(user_id),
        )

    added = await db.add_source(user_id, chat_id, title)
    if added:
        text = f"✅ 𝚂𝚘𝚞𝚛𝚌𝚎 𝚊𝚍𝚍𝚎𝚍: <b>{title}</b> (<code>{chat_id}</code>)"
    else:
        text = f"⚠️ <b>{title}</b> 𝚒𝚜 𝚊𝚕𝚛𝚎𝚊𝚍𝚢 𝚒𝚗 𝚢𝚘𝚞𝚛 𝚜𝚘𝚞𝚛𝚌𝚎𝚜."

    await prompt.edit(text, reply_markup=await _sources_keyboard(user_id))


@Client.on_callback_query(filters.regex(r"^src_remove_(-?\d+)$"))
async def cb_src_remove(bot: Client, query):
    user_id = query.from_user.id
    chat_id = int(query.data.split("_")[-1])
    await db.remove_source(user_id, chat_id)
    await query.answer("𝚂𝚘𝚞𝚛𝚌𝚎 𝚛𝚎𝚖𝚘𝚟𝚎𝚍.", show_alert=False)
    await query.message.edit_reply_markup(await _sources_keyboard(user_id))


# ─────────────────────────────────────────────────────────────────────────────
#  Destination menu
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^menu_dest$"))
async def cb_menu_dest(bot: Client, query):
    user_id = query.from_user.id
    dest    = await db.get_destination(user_id)

    current = (
        f"<b>𝙲𝚞𝚛𝚛𝚎𝚗𝚝:</b> {dest['title']} (<code>{dest['chat_id']}</code>)"
        if dest else "<b>𝙲𝚞𝚛𝚛𝚎𝚗𝚝:</b> ❌ 𝙽𝚘𝚝 𝚜𝚎𝚝"
    )
    await query.message.edit_text(
        f"📤 <b>𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗</b>\n\n{current}\n\n"
        "𝚃𝚊𝚙 𝚋𝚎𝚕𝚘𝚠 𝚝𝚘 𝚌𝚑𝚊𝚗𝚐𝚎 𝚢𝚘𝚞𝚛 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ ꜱᴇᴛ ᴅᴇꜱᴛɪɴᴀᴛɪᴏɴ", callback_data="dest_set")],
            [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")],
        ]),
    )


@Client.on_callback_query(filters.regex(r"^dest_set$"))
async def cb_dest_set(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    prompt = await query.message.edit_text(
        "📤 <b>𝚂𝚎𝚝 𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗</b>\n\n"
        "𝚂𝚎𝚗𝚍 <b>𝚊𝚗𝚢 𝚘𝚗𝚎</b> 𝚘𝚏 𝚝𝚑𝚎𝚜𝚎:\n"
        "• 𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚝\n"
        "• <code>@username</code>\n"
        "• <code>-1001234567890</code> (𝚗𝚞𝚖𝚎𝚛𝚒𝚌 𝙸𝙳)\n"
        "• <code>https://t.me/c/1234567890/1</code> (𝚙𝚛𝚒𝚟𝚊𝚝𝚎 𝚕𝚒𝚗𝚔)\n\n"
        "<b>⚠️ 𝚈𝚘𝚞𝚛 𝚞𝚜𝚎𝚛𝚋𝚘𝚝/𝚋𝚘𝚝 𝚖𝚞𝚜𝚝 𝚋𝚎 𝚊𝚗 𝚊𝚍𝚖𝚒𝚗 𝚒𝚗 𝚝𝚑𝚎 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗!</b>\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚖𝚒𝚗.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="menu_dest")]]
        ),
    )

    try:
        fwd_msg: Message = await bot.listen(
            chat_id=query.message.chat.id, user_id=user_id, timeout=300
        )
    except asyncio.TimeoutError:
        return await prompt.edit(
            "⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.",
            reply_markup=InlineKeyboardMarkup(_BACK_BTN),
        )

    if fwd_msg.text and fwd_msg.text.strip().lower() in ("/cancel", "cancel"):
        await fwd_msg.delete()
        return await prompt.edit(
            "❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.",
            reply_markup=InlineKeyboardMarkup(_BACK_BTN),
        )

    chat_id, title = await _resolve_chat_universal(bot, fwd_msg)
    await fwd_msg.delete()

    if chat_id is None:
        return await prompt.edit(
            f"⚠️ 𝙲𝚘𝚞𝚕𝚍 𝚗𝚘𝚝 𝚛𝚎𝚜𝚘𝚕𝚟𝚎 𝚌𝚑𝚊𝚝.\n<code>{title}</code>\n\n"
            "𝚃𝚛𝚢 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚒𝚗𝚜𝚝𝚎𝚊𝚍.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 ᴛʀʏ ᴀɢᴀɪɴ", callback_data="dest_set")],
                [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")],
            ]),
        )

    await db.set_destination(user_id, chat_id, title)
    await prompt.edit(
        f"✅ 𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚜𝚎𝚝: <b>{title}</b> (<code>{chat_id}</code>)\n\n"
        "𝙼𝚊𝚔𝚎 𝚜𝚞𝚛𝚎 𝚢𝚘𝚞𝚛 𝚞𝚜𝚎𝚛𝚋𝚘𝚝 𝚒𝚜 𝚊𝚗 <b>𝚊𝚍𝚖𝚒𝚗</b> 𝚒𝚗 𝚝𝚑𝚒𝚜 𝚌𝚑𝚊𝚝!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")]
        ]),
    )