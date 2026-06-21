"""
Source & Destination channel management.

Adding a source  → user forwards any message from the source chat
Setting dest     → user forwards any message from the destination chat
"""

import asyncio
import logging

from database import db
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logger = logging.getLogger(__name__)

_BACK_BTN = [[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")]]


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
    rows.append([InlineKeyboardButton("➕ ᴀᴅᴅ ꜱᴏᴜʀᴄᴇ ᴄʜᴀɴɴᴇʟ", callback_data="src_add")])
    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")])
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^menu_sources$"))
async def cb_menu_sources(bot: Client, query):
    user_id = query.from_user.id
    await query.message.edit_text(
        "📥 <b>𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚕𝚜</b>\n\n"
        "𝚃𝚑𝚎𝚜𝚎 𝚊𝚛𝚎 𝚝𝚑𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜 𝙸 𝚖𝚘𝚗𝚒𝚝𝚘𝚛 𝚏𝚘𝚛 𝚗𝚎𝚠 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜.\n"
        "𝚃𝚊𝚙 𝚊 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚗𝚊𝚖𝚎 𝚝𝚘 <b>𝚛𝚎𝚖𝚘𝚟𝚎</b> 𝚒𝚝, 𝚘𝚛 𝚊𝚍𝚍 𝚊 𝚗𝚎𝚠 𝚘𝚗𝚎 𝚋𝚎𝚕𝚘𝚠.\n\n"
        "<i>𝚃𝚘 𝚊𝚍𝚍: 𝚝𝚊𝚙 ➕ 𝚝𝚑𝚎𝚗 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚊𝚗𝚢 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚏𝚛𝚘𝚖 𝚝𝚑𝚊𝚝 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚝𝚘 𝚖𝚎.</i>",
        reply_markup=await _sources_keyboard(user_id),
    )


@Client.on_callback_query(filters.regex(r"^src_add$"))
async def cb_src_add(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    prompt = await query.message.edit_text(
        "📥 <b>𝙰𝚍𝚍 𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚕</b>\n\n"
        "𝙵𝚘𝚛𝚠𝚊𝚛𝚍 <b>𝚊𝚗𝚢 𝚖𝚎𝚜𝚜𝚊𝚐𝚎</b> 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚢𝚘𝚞 𝚠𝚊𝚗𝚝 𝚝𝚘 𝚖𝚘𝚗𝚒𝚝𝚘𝚛.\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚖𝚒𝚗𝚞𝚝𝚎𝚜.</i>",
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

    if fwd_msg.text and fwd_msg.text.strip() == "/cancel":
        await fwd_msg.delete()
        return await prompt.edit(
            "❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.",
            reply_markup=InlineKeyboardMarkup(_BACK_BTN),
        )

    # Must be a forwarded message from a channel
    if not fwd_msg.forward_from_chat:
        await fwd_msg.delete()
        return await prompt.edit(
            "⚠️ 𝚃𝚑𝚊𝚝 𝚍𝚘𝚎𝚜𝚗'𝚝 𝚕𝚘𝚘𝚔 𝚕𝚒𝚔𝚎 𝚊 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚍 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚖𝚎𝚜𝚜𝚊𝚐𝚎.\n"
            "𝙿𝚕𝚎𝚊𝚜𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 <b>𝚏𝚛𝚘𝚖 𝚊 𝚌𝚑𝚊𝚗𝚗𝚎𝚕</b>.",
            reply_markup=await _sources_keyboard(user_id),
        )

    chat_id = fwd_msg.forward_from_chat.id
    title   = fwd_msg.forward_from_chat.title or str(chat_id)
    await fwd_msg.delete()

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
        f"📤 <b>𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝙲𝚑𝚊𝚗𝚗𝚎𝚕</b>\n\n{current}\n\n"
        "𝚃𝚊𝚙 𝚋𝚎𝚕𝚘𝚠 𝚝𝚘 𝚌𝚑𝚊𝚗𝚐𝚎 𝚢𝚘𝚞𝚛 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚗𝚗𝚎𝚕.",
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
        "📤 <b>𝚂𝚎𝚝 𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝙲𝚑𝚊𝚗𝚗𝚎𝚕</b>\n\n"
        "𝙵𝚘𝚛𝚠𝚊𝚛𝚍 <b>𝚊𝚗𝚢 𝚖𝚎𝚜𝚜𝚊𝚐𝚎</b> 𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚗𝚗𝚎𝚕.\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚖𝚒𝚗𝚞𝚝𝚎𝚜.</i>",
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

    if fwd_msg.text and fwd_msg.text.strip() == "/cancel":
        await fwd_msg.delete()
        return await prompt.edit(
            "❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.",
            reply_markup=InlineKeyboardMarkup(_BACK_BTN),
        )

    if not fwd_msg.forward_from_chat:
        await fwd_msg.delete()
        return await prompt.edit(
            "⚠️ 𝚃𝚑𝚊𝚝 𝚍𝚘𝚎𝚜𝚗'𝚝 𝚕𝚘𝚘𝚔 𝚕𝚒𝚔𝚎 𝚊 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚍 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚖𝚎𝚜𝚜𝚊𝚐𝚎.\n"
            "𝙿𝚕𝚎𝚊𝚜𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍 𝚊 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 <b>𝚏𝚛𝚘𝚖 𝚝𝚑𝚎 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚗𝚗𝚎𝚕</b>.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 ᴛʀʏ ᴀɢᴀɪɴ", callback_data="dest_set")],
                [InlineKeyboardButton("↩ ʙᴀᴄᴋ",      callback_data="menu_settings_hub")],
            ]),
        )

    chat_id = fwd_msg.forward_from_chat.id
    title   = fwd_msg.forward_from_chat.title or str(chat_id)
    await fwd_msg.delete()

    await db.set_destination(user_id, chat_id, title)
    await prompt.edit(
        f"✅ 𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚜𝚎𝚝 𝚝𝚘: <b>{title}</b> (<code>{chat_id}</code>)\n\n"
        "𝙼𝚊𝚔𝚎 𝚜𝚞𝚛𝚎 𝚢𝚘𝚞𝚛 𝚞𝚜𝚎𝚛𝚋𝚘𝚝 𝚒𝚜 𝚊𝚗 <b>𝚊𝚍𝚖𝚒𝚗</b> 𝚒𝚗 𝚝𝚑𝚒𝚜 𝚌𝚑𝚊𝚗𝚗𝚎𝚕!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")]
        ]),
    )