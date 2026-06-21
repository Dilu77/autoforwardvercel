"""
Text Replacement Rules — Premium feature.

Allows users to set keyword → replacement mappings.
When a forwarded message contains a keyword, it is replaced before sending.
Works on both message text and captions.
"""

import asyncio
import logging

from database import db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

_HOME = [[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")]]
_BACK = [[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_replace")]]

MAX_RULES = 20  # reasonable cap


# ─────────────────────────────────────────────────────────────────────────────
#  Keyboard
# ─────────────────────────────────────────────────────────────────────────────


async def _replace_keyboard(user_id: int) -> InlineKeyboardMarkup:
    rules = await db.get_replace_rules(user_id)
    rows  = []

    for rule in rules:
        kw    = rule["keyword"][:20]
        repl  = rule["replace_with"][:15] or "(𝚎𝚖𝚙𝚝𝚢)"
        label = f"❌ {kw!r} → {repl!r}"
        rows.append([
            InlineKeyboardButton(label, callback_data=f"rep_del_{rule['keyword'][:30]}")
        ])

    if len(rules) < MAX_RULES:
        rows.append([InlineKeyboardButton("➕ ᴀᴅᴅ ʀᴜʟᴇ", callback_data="rep_add")])

    if rules:
        rows.append([InlineKeyboardButton("🗑 ᴄʟᴇᴀʀ ᴀʟʟ ʀᴜʟᴇꜱ", callback_data="rep_clear")])

    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")])
    return InlineKeyboardMarkup(rows)


# ─────────────────────────────────────────────────────────────────────────────
#  Main replace menu
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^menu_replace$"))
async def cb_menu_replace(bot: Client, query):
    user_id = query.from_user.id

    if not await db.is_premium(user_id):
        return await query.answer(
            "🌟 𝚁𝚎𝚙𝚕𝚊𝚌𝚎 𝚃𝚎𝚡𝚝 𝚒𝚜 𝚊 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚏𝚎𝚊𝚝𝚞𝚛𝚎. 𝙲𝚘𝚗𝚝𝚊𝚌𝚝 𝚊𝚍𝚖𝚒𝚗 𝚝𝚘 𝚞𝚙𝚐𝚛𝚊𝚍𝚎.",
            show_alert=True,
        )

    rules = await db.get_replace_rules(user_id)
    count = len(rules)

    await query.message.edit_text(
        f"🔄 <b>𝚁𝚎𝚙𝚕𝚊𝚌𝚎 𝚃𝚎𝚡𝚝 𝚁𝚞𝚕𝚎𝚜</b>  ({count}/{MAX_RULES})\n\n"
        "𝚆𝚑𝚎𝚗 𝚊 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚍 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚌𝚘𝚗𝚝𝚊𝚒𝚗𝚜 𝚊 <b>𝚔𝚎𝚢𝚠𝚘𝚛𝚍</b>, 𝚒𝚝 𝚠𝚒𝚕𝚕 𝚋𝚎 "
        "𝚊𝚞𝚝𝚘𝚖𝚊𝚝𝚒𝚌𝚊𝚕𝚕𝚢 𝚛𝚎𝚙𝚕𝚊𝚌𝚎𝚍 𝚠𝚒𝚝𝚑 𝚢𝚘𝚞𝚛 𝚌𝚑𝚘𝚜𝚎𝚗 𝚝𝚎𝚡𝚝.\n\n"
        "𝚃𝚊𝚙 𝚊 𝚛𝚞𝚕𝚎 𝚝𝚘 <b>𝚍𝚎𝚕𝚎𝚝𝚎</b> 𝚒𝚝, 𝚘𝚛 𝚊𝚍𝚍 𝚊 𝚗𝚎𝚠 𝚘𝚗𝚎 𝚋𝚎𝚕𝚘𝚠.",
        reply_markup=await _replace_keyboard(user_id),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Add rule
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^rep_add$"))
async def cb_rep_add(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    prompt = await query.message.edit_text(
        "➕ <b>𝙰𝚍𝚍 𝚁𝚎𝚙𝚕𝚊𝚌𝚎 𝚁𝚞𝚕𝚎 — 𝚂𝚝𝚎𝚙 𝟷/𝟸</b>\n\n"
        "𝚂𝚎𝚗𝚍 𝚝𝚑𝚎 <b>𝚔𝚎𝚢𝚠𝚘𝚛𝚍</b> 𝚝𝚘 𝚖𝚊𝚝𝚌𝚑 (𝚎𝚡𝚊𝚌𝚝, 𝚌𝚊𝚜𝚎-𝚜𝚎𝚗𝚜𝚒𝚝𝚒𝚟𝚎).\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟹 𝚖𝚒𝚗𝚞𝚝𝚎𝚜.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="menu_replace")]]
        ),
    )

    try:
        kw_msg = await bot.listen(
            chat_id=query.message.chat.id, user_id=user_id, timeout=180
        )
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.", reply_markup=InlineKeyboardMarkup(_HOME))

    if kw_msg.text.strip() == "/cancel":
        await kw_msg.delete()
        return await prompt.edit("❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.", reply_markup=InlineKeyboardMarkup(_HOME))

    keyword = kw_msg.text.strip()
    await kw_msg.delete()

    if not keyword:
        return await prompt.edit(
            "⚠️ 𝙺𝚎𝚢𝚠𝚘𝚛𝚍 𝚌𝚊𝚗𝚗𝚘𝚝 𝚋𝚎 𝚎𝚖𝚙𝚝𝚢.",
            reply_markup=InlineKeyboardMarkup(_BACK),
        )

    await prompt.edit(
        f"➕ <b>𝙰𝚍𝚍 𝚁𝚎𝚙𝚕𝚊𝚌𝚎 𝚁𝚞𝚕𝚎 — 𝚂𝚝𝚎𝚙 𝟸/𝟸</b>\n\n"
        f"𝙺𝚎𝚢𝚠𝚘𝚛𝚍: <code>{keyword}</code>\n\n"
        "𝙽𝚘𝚠 𝚜𝚎𝚗𝚍 𝚝𝚑𝚎 <b>𝚛𝚎𝚙𝚕𝚊𝚌𝚎𝚖𝚎𝚗𝚝 𝚝𝚎𝚡𝚝</b>.\n"
        "𝚂𝚎𝚗𝚍 𝚊 𝚜𝚒𝚗𝚐𝚕𝚎 𝚜𝚙𝚊𝚌𝚎 𝚘𝚛 <code>-</code> 𝚝𝚘 𝚍𝚎𝚕𝚎𝚝𝚎 (𝚛𝚎𝚙𝚕𝚊𝚌𝚎 𝚠𝚒𝚝𝚑 𝚗𝚘𝚝𝚑𝚒𝚗𝚐).\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟹 𝚖𝚒𝚗𝚞𝚝𝚎𝚜.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="menu_replace")]]
        ),
    )

    try:
        repl_msg = await bot.listen(
            chat_id=query.message.chat.id, user_id=user_id, timeout=180
        )
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.", reply_markup=InlineKeyboardMarkup(_HOME))

    if repl_msg.text.strip() == "/cancel":
        await repl_msg.delete()
        return await prompt.edit("❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.", reply_markup=InlineKeyboardMarkup(_HOME))

    replace_with = repl_msg.text
    # Treat "-" or single space as "delete the keyword"
    if replace_with.strip() in ("-", ""):
        replace_with = ""
    await repl_msg.delete()

    added = await db.add_replace_rule(user_id, keyword, replace_with)
    if added:
        repl_display = f"<code>{replace_with}</code>" if replace_with else "<i>(𝚍𝚎𝚕𝚎𝚝𝚎𝚍)</i>"
        await prompt.edit(
            f"✅ 𝚁𝚞𝚕𝚎 𝚊𝚍𝚍𝚎𝚍!\n\n"
            f"<code>{keyword}</code> → {repl_display}",
            reply_markup=await _replace_keyboard(user_id),
        )
    else:
        await prompt.edit(
            f"⚠️ 𝙰 𝚛𝚞𝚕𝚎 𝚏𝚘𝚛 <code>{keyword}</code> 𝚊𝚕𝚛𝚎𝚊𝚍𝚢 𝚎𝚡𝚒𝚜𝚝𝚜. 𝙳𝚎𝚕𝚎𝚝𝚎 𝚒𝚝 𝚏𝚒𝚛𝚜𝚝.",
            reply_markup=await _replace_keyboard(user_id),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Delete individual rule
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^rep_del_(.+)$"))
async def cb_rep_del(bot: Client, query):
    user_id = query.from_user.id
    keyword = query.data[len("rep_del_"):]
    removed = await db.remove_replace_rule(user_id, keyword)
    msg = f"𝚁𝚎𝚖𝚘𝚟𝚎𝚍 𝚛𝚞𝚕𝚎 𝚏𝚘𝚛 «{keyword}»." if removed else "𝚁𝚞𝚕𝚎 𝚗𝚘𝚝 𝚏𝚘𝚞𝚗𝚍."
    await query.answer(msg, show_alert=False)
    await query.message.edit_reply_markup(await _replace_keyboard(user_id))


# ─────────────────────────────────────────────────────────────────────────────
#  Clear all rules
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^rep_clear$"))
async def cb_rep_clear(bot: Client, query):
    user_id = query.from_user.id
    await db.clear_replace_rules(user_id)
    await query.answer("𝙰𝚕𝚕 𝚛𝚞𝚕𝚎𝚜 𝚌𝚕𝚎𝚊𝚛𝚎𝚍.", show_alert=False)
    await query.message.edit_reply_markup(await _replace_keyboard(user_id))