"""
Settings panel for per-user forwarding configuration.

Free plan:  media filters only (other settings locked)
Premium:    all settings unlocked
"""

import asyncio
import logging

from database import db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

_BACK = [[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings")]]
_HOME = [[InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]]


# ─────────────────────────────────────────────────────────────────────────────
#  Settings main panel
# ─────────────────────────────────────────────────────────────────────────────


async def _settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    s          = await db.get_settings(user_id)
    is_premium = await db.is_premium(user_id)
    tf  = "✅" if s.get("forward_tag")    else "❌"
    rc  = "✅" if s.get("remove_caption") else "❌"
    cc  = "✏️ ᴇᴅɪᴛ" if s.get("custom_caption") else "➕ ᴀᴅᴅ"

    lock = "" if is_premium else " 🔒"

    rows = [
        [InlineKeyboardButton(f"🏷 ꜰᴏʀᴡᴀʀᴅ ᴛᴀɢ: {tf}{lock}",    callback_data="stg_toggle_forward_tag")],
        [InlineKeyboardButton(f"✂️ ʀᴇᴍᴏᴠᴇ ᴄᴀᴘᴛɪᴏɴ: {rc}{lock}", callback_data="stg_toggle_remove_caption")],
        [InlineKeyboardButton(f"📝 ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ: {cc}{lock}", callback_data="stg_custom_caption")],
        [InlineKeyboardButton("🎛 ᴍᴇᴅɪᴀ ꜰɪʟᴛᴇʀꜱ",               callback_data="stg_filters")],
        [InlineKeyboardButton("↩ ʙᴀᴄᴋ",                        callback_data="menu_settings_hub")],
    ]
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^menu_settings$"))
async def cb_menu_settings(bot: Client, query):
    is_premium = await db.is_premium(query.from_user.id)

    if not is_premium:
        # Non-premium: show locked message with upgrade prompt — full settings panel blocked
        return await query.message.edit_text(
            "⚙️ <b>𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜</b>\n\n"
            "🔒 <i>𝙰𝚕𝚕 𝚜𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝚊𝚛𝚎 𝙿𝚛𝚎𝚖𝚒𝚞𝚖-𝚘𝚗𝚕𝚢.</i>\n\n"
            "𝙵𝚛𝚎𝚎 𝚙𝚕𝚊𝚗 𝚒𝚗𝚌𝚕𝚞𝚍𝚎𝚜 𝚖𝚎𝚍𝚒𝚊 𝚏𝚒𝚕𝚝𝚎𝚛𝚜 𝚘𝚗𝚕𝚢.\n\n"
            "𝚄𝚙𝚐𝚛𝚊𝚍𝚎 𝚝𝚘 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚝𝚘 𝚞𝚗𝚕𝚘𝚌𝚔:\n"
            "• 𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝚝𝚊𝚐 𝚝𝚘𝚐𝚐𝚕𝚎\n"
            "• 𝚁𝚎𝚖𝚘𝚟𝚎 𝚌𝚊𝚙𝚝𝚒𝚘𝚗\n"
            "• 𝙲𝚞𝚜𝚝𝚘𝚖 𝚌𝚊𝚙𝚝𝚒𝚘𝚗\n"
            "• 𝚃𝚎𝚡𝚝 𝚛𝚎𝚙𝚕𝚊𝚌𝚎 𝚛𝚞𝚕𝚎𝚜",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎛 ᴍᴇᴅɪᴀ ꜰɪʟᴛᴇʀꜱ", callback_data="stg_filters")],
                [InlineKeyboardButton("💎 ᴠɪᴇᴡ ᴘʟᴀɴꜱ", callback_data="menu_plans")],
                [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")],
            ]),
        )

    await query.message.edit_text(
        "⚙️ <b>𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜</b>\n\n𝙲𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎 𝚢𝚘𝚞𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚋𝚎𝚑𝚊𝚟𝚒𝚘𝚞𝚛:",
        reply_markup=await _settings_keyboard(query.from_user.id),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Simple toggle handlers — premium-gated
# ─────────────────────────────────────────────────────────────────────────────


_PREMIUM_KEYS = {"forward_tag", "remove_caption"}


@Client.on_callback_query(filters.regex(r"^stg_toggle_(.+)$"))
async def cb_stg_toggle(bot: Client, query):
    user_id    = query.from_user.id
    key        = query.data.replace("stg_toggle_", "")
    is_premium = await db.is_premium(user_id)

    if key in _PREMIUM_KEYS and not is_premium:
        return await query.answer(
            "🌟 𝚃𝚑𝚒𝚜 𝚜𝚎𝚝𝚝𝚒𝚗𝚐 𝚒𝚜 𝙿𝚛𝚎𝚖𝚒𝚞𝚖-𝚘𝚗𝚕𝚢. 𝙲𝚘𝚗𝚝𝚊𝚌𝚝 𝚊𝚍𝚖𝚒𝚗 𝚝𝚘 𝚞𝚙𝚐𝚛𝚊𝚍𝚎.",
            show_alert=True,
        )

    s       = await db.get_settings(user_id)
    current = s.get(key, False)
    await db.update_setting(user_id, key, not current)
    await query.answer(f"{'𝙴𝚗𝚊𝚋𝚕𝚎𝚍' if not current else '𝙳𝚒𝚜𝚊𝚋𝚕𝚎𝚍'} ✅", show_alert=False)
    await query.message.edit_reply_markup(await _settings_keyboard(user_id))


# ─────────────────────────────────────────────────────────────────────────────
#  Custom caption — premium-gated
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^stg_custom_caption$"))
async def cb_custom_caption(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)

    if not is_premium:
        return await query.answer(
            "🌟 𝙲𝚞𝚜𝚝𝚘𝚖 𝙲𝚊𝚙𝚝𝚒𝚘𝚗 𝚒𝚜 𝚊 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚏𝚎𝚊𝚝𝚞𝚛𝚎. 𝙲𝚘𝚗𝚝𝚊𝚌𝚝 𝚊𝚍𝚖𝚒𝚗 𝚝𝚘 𝚞𝚙𝚐𝚛𝚊𝚍𝚎.",
            show_alert=True,
        )

    s       = await db.get_settings(user_id)
    current = s.get("custom_caption")

    rows = []
    if current:
        rows.append([InlineKeyboardButton("👁 ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ", callback_data="stg_view_caption")])
        rows.append([InlineKeyboardButton("🗑 ᴅᴇʟᴇᴛᴇ ᴄᴀᴘᴛɪᴏɴ", callback_data="stg_del_caption")])
    rows.append([InlineKeyboardButton("✏️ ꜱᴇᴛ ɴᴇᴡ ᴄᴀᴘᴛɪᴏɴ", callback_data="stg_set_caption")])
    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings")])

    await query.message.edit_text(
        "📝 <b>𝙲𝚞𝚜𝚝𝚘𝚖 𝙲𝚊𝚙𝚝𝚒𝚘𝚗</b>\n\n"
        "𝚈𝚘𝚞 𝚌𝚊𝚗 𝚘𝚟𝚎𝚛𝚛𝚒𝚍𝚎 𝚝𝚑𝚎 𝚌𝚊𝚙𝚝𝚒𝚘𝚗 𝚘𝚗 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚍 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜.\n\n"
        "<b>𝙰𝚟𝚊𝚒𝚕𝚊𝚋𝚕𝚎 𝚙𝚕𝚊𝚌𝚎𝚑𝚘𝚕𝚍𝚎𝚛:</b>\n"
        "• <code>{caption}</code> — 𝚘𝚛𝚒𝚐𝚒𝚗𝚊𝚕 𝚌𝚊𝚙𝚝𝚒𝚘𝚗\n\n"
        f"<b>𝚂𝚝𝚊𝚝𝚞𝚜:</b> {'✅ 𝚂𝚎𝚝' if current else '❌ 𝙽𝚘𝚝 𝚜𝚎𝚝'}",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@Client.on_callback_query(filters.regex(r"^stg_view_caption$"))
async def cb_view_caption(bot: Client, query):
    s   = await db.get_settings(query.from_user.id)
    cap = s.get("custom_caption") or "None"
    await query.answer(f"𝙲𝚊𝚙𝚝𝚒𝚘𝚗:\n{cap[:200]}", show_alert=True)


@Client.on_callback_query(filters.regex(r"^stg_del_caption$"))
async def cb_del_caption(bot: Client, query):
    await db.update_setting(query.from_user.id, "custom_caption", None)
    await query.answer("𝙲𝚊𝚙𝚝𝚒𝚘𝚗 𝚍𝚎𝚕𝚎𝚝𝚎𝚍.", show_alert=False)
    await cb_custom_caption(bot, query)


@Client.on_callback_query(filters.regex(r"^stg_set_caption$"))
async def cb_set_caption(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    prompt = await query.message.edit_text(
        "✏️ <b>𝚂𝚎𝚝 𝙲𝚞𝚜𝚝𝚘𝚖 𝙲𝚊𝚙𝚝𝚒𝚘𝚗</b>\n\n"
        "𝚂𝚎𝚗𝚍 𝚢𝚘𝚞𝚛 𝚌𝚊𝚙𝚝𝚒𝚘𝚗 𝚝𝚎𝚡𝚝 𝚗𝚘𝚠.\n"
        "𝚈𝚘𝚞 𝚌𝚊𝚗 𝚞𝚜𝚎 <code>{caption}</code> 𝚊𝚜 𝚊 𝚙𝚕𝚊𝚌𝚎𝚑𝚘𝚕𝚍𝚎𝚛 𝚏𝚘𝚛 𝚝𝚑𝚎 𝚘𝚛𝚒𝚐𝚒𝚗𝚊𝚕 𝚌𝚊𝚙𝚝𝚒𝚘𝚗.\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚖𝚒𝚗𝚞𝚝𝚎𝚜.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="stg_custom_caption")]]
        ),
    )

    try:
        msg = await bot.listen(
            chat_id=query.message.chat.id, user_id=user_id, timeout=300
        )
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.", reply_markup=InlineKeyboardMarkup(_HOME))

    if msg.text.strip() == "/cancel":
        await msg.delete()
        return await prompt.edit("❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.", reply_markup=InlineKeyboardMarkup(_HOME))

    try:
        msg.text.format(caption="test")
    except KeyError as e:
        await msg.delete()
        return await prompt.edit(
            f"⚠️ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚙𝚕𝚊𝚌𝚎𝚑𝚘𝚕𝚍𝚎𝚛 <code>{e}</code>. 𝙾𝚗𝚕𝚢 <code>{{caption}}</code> 𝚒𝚜 𝚜𝚞𝚙𝚙𝚘𝚛𝚝𝚎𝚍.",
            reply_markup=InlineKeyboardMarkup(_BACK),
        )

    await db.update_setting(user_id, "custom_caption", msg.text)
    await msg.delete()
    await prompt.edit(
        "✅ 𝙲𝚞𝚜𝚝𝚘𝚖 𝚌𝚊𝚙𝚝𝚒𝚘𝚗 𝚜𝚊𝚟𝚎𝚍!",
        reply_markup=InlineKeyboardMarkup(_BACK),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Media filter toggles — available to all plans
# ─────────────────────────────────────────────────────────────────────────────

_FILTER_LABELS = {
    "text":      "🖍 ᴛᴇxᴛ",
    "photo":     "📷 ᴘʜᴏᴛᴏ",
    "video":     "🎞 ᴠɪᴅᴇᴏ",
    "audio":     "🎵 ᴀᴜᴅɪᴏ",
    "document":  "📁 ᴅᴏᴄᴜᴍᴇɴᴛ",
    "voice":     "🎤 ᴠᴏɪᴄᴇ",
    "animation": "🎭 ᴀɴɪᴍᴀᴛɪᴏɴ",
    "sticker":   "🃏 ꜱᴛɪᴄᴋᴇʀ",
}


async def _filter_keyboard(user_id: int) -> InlineKeyboardMarkup:
    s     = await db.get_settings(user_id)
    fltrs = s.get("filters", {})
    rows  = []

    for key, label in _FILTER_LABELS.items():
        val  = fltrs.get(key, True)
        icon = "✅" if val else "❌"
        rows.append([
            InlineKeyboardButton(f"{label}: {icon}", callback_data=f"stg_flt_{key}_{val}")
        ])

    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings")])
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^stg_filters$"))
async def cb_stg_filters(bot: Client, query):
    await query.message.edit_text(
        "🎛 <b>𝙼𝚎𝚍𝚒𝚊 𝙵𝚒𝚕𝚝𝚎𝚛𝚜</b>\n\n𝚃𝚘𝚐𝚐𝚕𝚎 𝚠𝚑𝚒𝚌𝚑 𝚖𝚎𝚍𝚒𝚊 𝚝𝚢𝚙𝚎𝚜 𝚝𝚘 𝚏𝚘𝚛𝚠𝚊𝚛𝚍:",
        reply_markup=await _filter_keyboard(query.from_user.id),
    )


@Client.on_callback_query(filters.regex(r"^stg_flt_(.+)_(True|False)$"))
async def cb_filter_toggle(bot: Client, query):
    user_id = query.from_user.id
    parts   = query.data.split("_")
    val_str = parts[-1]
    key     = "_".join(parts[2:-1])
    new_val = val_str != "True"
    await db.update_filter(user_id, key, new_val)
    await query.answer(f"{'𝙴𝚗𝚊𝚋𝚕𝚎𝚍' if new_val else '𝙳𝚒𝚜𝚊𝚋𝚕𝚎𝚍'} {_FILTER_LABELS.get(key, key)}")
    await query.message.edit_reply_markup(await _filter_keyboard(user_id))