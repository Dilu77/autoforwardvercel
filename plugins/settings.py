"""
Settings panel for per-user forwarding configuration.

Free plan:  media filters only (other settings locked)
Premium:    all settings unlocked
"""

import asyncio
import logging
import re

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
    btn_lbl = "✏️ ᴇᴅɪᴛ" if s.get("button") else "➕ ᴀᴅᴅ"
    
    # size limit display
    size = s.get("file_size", 0)
    limit = s.get("size_limit")
    if size == 0 or limit is None:
        size_lbl = "❌"
    else:
        sign = ">" if limit else "<"
        size_lbl = f"{sign} {size}MB"
        
    ext_lbl = "✏️ ᴇᴅɪᴛ" if s.get("extensions") else "➕ ᴀᴅᴅ"
    kw_lbl = "✏️ ᴇᴅɪᴛ" if s.get("keywords") else "➕ ᴀᴅᴅ"
    pc  = "✅" if s.get("protect_content") else "❌"
    ds  = "✅" if s.get("duplicate_skip") else "❌"

    lock = "" if is_premium else " 🔒"

    rows = [
        [
            InlineKeyboardButton(f"🏷 ᴛᴀɢ: {tf}{lock}", callback_data="stg_toggle_forward_tag"),
            InlineKeyboardButton(f"✂️ ᴄᴀᴘ: {rc}{lock}", callback_data="stg_toggle_remove_caption"),
        ],
        [
            InlineKeyboardButton(f"📝 ᴄᴜsᴛ ᴄᴀᴘ: {cc}{lock}", callback_data="stg_custom_caption"),
            InlineKeyboardButton(f"⏹ ʙᴜᴛᴛᴏɴ: {btn_lbl}{lock}", callback_data="stg_custom_button"),
        ],
        [
            InlineKeyboardButton(f"📁 ꜱɪᴢᴇ: {size_lbl}{lock}", callback_data="stg_size_limits"),
            InlineKeyboardButton(f"🚫 ᴇxᴛ: {ext_lbl}{lock}", callback_data="stg_extensions"),
        ],
        [
            InlineKeyboardButton(f"🔍 ᴋᴡᴏʀᴅ: {kw_lbl}{lock}", callback_data="stg_keywords"),
            InlineKeyboardButton("🎛 ᴍᴇᴅɪᴀ ꜰɪʟᴛᴇʀꜱ", callback_data="stg_filters"),
        ],
        [
            InlineKeyboardButton(f"🔒 ᴘʀᴏᴛᴇᴄᴛ: {pc}{lock}", callback_data="stg_toggle_protect_content"),
            InlineKeyboardButton(f"🔄 ᴅᴜᴘ sᴋɪᴘ: {ds}{lock}", callback_data="stg_toggle_duplicate_skip"),
        ],
        [InlineKeyboardButton("🧹 🛡️ ᴄʟᴇᴀɴ ᴅᴜᴘʟɪᴄᴀᴛᴇꜱ", callback_data="stg_clean_duplicates")],
        [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")],
    ]
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^menu_settings$"))
async def cb_menu_settings(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)

    if is_premium:
        await query.message.edit_text(
            "⚙️ <b>𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜</b>\n\n𝙲𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎 𝚢𝚘𝚞𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚋𝚎𝚑𝚊𝚟𝚒𝚘𝚞𝚛:",
            reply_markup=await _settings_keyboard(user_id),
        )
    else:
        # Free users: always show full panel — premium items show 🔒 but user can tap filters
        await query.message.edit_text(
            "⚙️ <b>𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜</b>\n\n"
            "🔒 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚒𝚝𝚎𝚖𝚜 𝚊𝚛𝚎 𝚕𝚘𝚌𝚔𝚎𝚍 — 𝙼𝚎𝚍𝚒𝚊 𝙵𝚒𝚕𝚝𝚎𝚛𝚜 𝚊𝚛𝚎 𝚏𝚛𝚎𝚎.\n\n"
            "𝚄𝚙𝚐𝚛𝚊𝚍𝚎 𝚝𝚘 𝚞𝚗𝚕𝚘𝚌𝚔 𝚊𝚕𝚕 𝚜𝚎𝚝𝚝𝚒𝚗𝚐𝚜:",
            reply_markup=await _settings_keyboard(user_id),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Simple toggle handlers — premium-gated
# ─────────────────────────────────────────────────────────────────────────────


_PREMIUM_KEYS = {
    "forward_tag", "remove_caption", "protect_content", 
    "duplicate_skip", "custom_caption", "custom_button", 
    "size_limits", "extensions", "keywords", "clean_duplicates"
}


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


# ─────────────────────────────────────────────────────────────────────────────
#  Custom button — premium-gated
# ─────────────────────────────────────────────────────────────────────────────

def parse_custom_buttons(text: str):
    """
    Parse brackets [button_name][buttonurl:url] (with optional :same)
    and return InlineKeyboardMarkup or None.
    """
    if not text:
        return None
    matches = re.finditer(r"\[([^\[]+?)\]\[buttonurl:/{0,2}([^\s\]:]+)(:same)?\]", text)
    buttons = []
    for match in matches:
        name = match.group(1)
        url = match.group(2)
        same = match.group(3)
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if same and buttons:
            buttons[-1].append(InlineKeyboardButton(name, url=url))
        else:
            buttons.append([InlineKeyboardButton(name, url=url)])
    return InlineKeyboardMarkup(buttons) if buttons else None


@Client.on_callback_query(filters.regex(r"^stg_custom_button$"))
async def cb_custom_button(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)

    if not is_premium:
        return await query.answer(
            "🌟 𝙲𝚞𝚜𝚝𝚘𝚖 𝙱𝚞𝚝𝚝𝚘𝚗 𝚒𝚜 𝚊 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚏𝚎𝚊𝚝𝚞𝚛𝚎. 𝙲𝚘𝚗𝚝𝚊𝚌𝚝 𝚊𝚍𝚖𝚒𝚗 𝚝𝚘 𝚞𝚙𝚐𝚛𝚊𝚍𝚎.",
            show_alert=True,
        )

    s       = await db.get_settings(user_id)
    current = s.get("button")

    rows = []
    if current:
        rows.append([InlineKeyboardButton("👁 ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ", callback_data="stg_view_button")])
        rows.append([InlineKeyboardButton("🗑 ᴅᴇʟᴇᴛᴇ ʙᴜᴛᴛᴏɴ", callback_data="stg_del_button")])
    rows.append([InlineKeyboardButton("✏️ ꜱᴇᴛ ɴᴇᴡ ʙᴜᴛᴛᴏɴ", callback_data="stg_set_button")])
    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings")])

    await query.message.edit_text(
        "⏹ <b>𝙲𝚞𝚜𝚝𝚘𝚖 𝙸𝚗𝚕𝚒𝚗𝚎 𝙱𝚞𝚝𝚝𝚘𝚗𝚜</b>\n\n"
        "𝚈𝚘𝚞 𝚌𝚊𝚗 𝚊𝚙𝚙𝚎𝚗𝚍 𝚌𝚞𝚜𝚝𝚘𝚖 𝚞𝚛𝚕 𝚋𝚞𝚝𝚝𝚘𝚗𝚜 𝚊𝚝 𝚝𝚑𝚎 𝚋𝚘𝚝𝚝𝚘𝚖 𝚘𝚏 𝚢𝚘𝚞𝚛 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜.\n\n"
        "<b>𝙵𝚘𝚛𝚖𝚊𝚝:</b>\n"
        "<code>[Button Text][buttonurl:https://t.me/yoururl]</code>\n"
        "𝙰𝚙𝚙𝚎𝚗𝚍 <code>:same</code> 𝚏𝚘𝚛 𝚜𝚊𝚖𝚎-𝚛𝚘𝚚 𝚋𝚞𝚝𝚝𝚘𝚗𝚜:\n"
        "<code>[Btn 1][buttonurl:url1] [Btn 2][buttonurl:url2:same]</code>\n\n"
        f"<b>𝚂𝚝𝚊𝚝𝚞𝚜:</b> {'✅ 𝚂𝚎𝚝' if current else '❌ 𝙽𝚘𝚝 𝚜𝚎𝚝'}",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@Client.on_callback_query(filters.regex(r"^stg_view_button$"))
async def cb_view_button(bot: Client, query):
    s = await db.get_settings(query.from_user.id)
    btn_str = s.get("button") or "None"
    await query.answer(f"𝙱𝚞𝚝𝚝𝚘𝚗 𝚏𝚘𝚛𝚖𝚊𝚝:\n{btn_str}", show_alert=True)


@Client.on_callback_query(filters.regex(r"^stg_del_button$"))
async def cb_del_button(bot: Client, query):
    await db.update_setting(query.from_user.id, "button", None)
    await query.answer("𝙲𝚞𝚜𝚝𝚘𝚖 𝚋𝚞𝚝𝚝𝚘𝚗 𝚍𝚎𝚕𝚎𝚝𝚎𝚍.", show_alert=False)
    await cb_custom_button(bot, query)


@Client.on_callback_query(filters.regex(r"^stg_set_button$"))
async def cb_set_button(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    prompt = await query.message.edit_text(
        "✏️ <b>𝚂𝚎𝚝 𝙲𝚞𝚜𝚝𝚘𝚖 𝙱𝚞𝚝𝚝𝚘𝚗</b>\n\n"
        "𝚂𝚎𝚗𝚍 𝚢𝚘𝚞𝚛 𝚋𝚞𝚝𝚝𝚘𝚗𝚜 𝚜𝚝𝚛𝚒𝚗𝚐 𝚗𝚘𝚠.\n\n"
        "<b>𝙵𝚘𝚛𝚖𝚊𝚝:</b>\n"
        "<code>[My Channel][buttonurl:t.me/mychannel]</code>\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚖𝚒𝚗.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="stg_custom_button")]]
        ),
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=300)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.", reply_markup=InlineKeyboardMarkup(_HOME))

    if msg.text and msg.text.strip() == "/cancel":
        await msg.delete()
        return await prompt.edit("❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.", reply_markup=InlineKeyboardMarkup(_HOME))

    markup = parse_custom_buttons(msg.text.strip() if msg.text else "")
    if not markup:
        if msg.text:
            await msg.delete()
        return await prompt.edit(
            "⚠️ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚋𝚞𝚝𝚝𝚘𝚗 𝚏𝚘𝚛𝚖𝚊𝚝. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗.",
            reply_markup=InlineKeyboardMarkup(_BACK),
        )

    await db.update_setting(user_id, "button", msg.text.strip())
    await msg.delete()
    await prompt.edit("✅ 𝙲𝚞𝚜𝚝𝚘𝚖 𝚋𝚞𝚝𝚝𝚘𝚗𝚜 𝚜𝚊𝚟𝚎𝚍!", reply_markup=InlineKeyboardMarkup(_BACK))


# ─────────────────────────────────────────────────────────────────────────────
#  File Size Limits — premium-gated
# ─────────────────────────────────────────────────────────────────────────────

async def _size_keyboard(user_id: int) -> InlineKeyboardMarkup:
    s     = await db.get_settings(user_id)
    size  = s.get("file_size", 0)
    limit = s.get("size_limit")

    btn_none = "✅ Disable" if (size == 0 or limit is None) else "❌ Disable"
    btn_gt   = "✅ Greater (>)" if limit == True else "Greater (>)"
    btn_lt   = "✅ Less (<)" if limit == False else "Less (<)"

    rows = [
        [
            InlineKeyboardButton(btn_none, callback_data="stg_size_type_none"),
            InlineKeyboardButton(btn_gt,   callback_data="stg_size_type_greater"),
            InlineKeyboardButton(btn_lt,   callback_data="stg_size_type_less"),
        ],
        [
            InlineKeyboardButton("-50MB", callback_data="stg_size_adj_-50"),
            InlineKeyboardButton("-10MB", callback_data="stg_size_adj_-10"),
            InlineKeyboardButton("-1MB",  callback_data="stg_size_adj_-1"),
        ],
        [
            InlineKeyboardButton("+1MB",  callback_data="stg_size_adj_1"),
            InlineKeyboardButton("+10MB", callback_data="stg_size_adj_10"),
            InlineKeyboardButton("+50MB", callback_data="stg_size_adj_50"),
        ],
        [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings")],
    ]
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^stg_size_limits$"))
async def cb_size_limits(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)

    if not is_premium:
        return await query.answer(
            "🌟 𝚂𝚒𝚣𝚎 𝙻𝚒𝚖𝚒𝚝𝚜 𝚊𝚛𝚎 𝚊 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚏𝚎𝚊𝚝𝚞𝚛𝚎. 𝙲𝚘𝚗𝚝𝚊𝚌𝚝 𝚊𝚍𝚖𝚒𝚗 𝚝𝚘 𝚞𝚙𝚐𝚛𝚊𝚍𝚎.",
            show_alert=True,
        )

    s     = await db.get_settings(user_id)
    size  = s.get("file_size", 0)
    limit = s.get("size_limit")

    if size == 0 or limit is None:
        status_text = "❌ 𝙳𝚒𝚜𝚊𝚋𝚕𝚎𝚍 (𝚊𝚕𝚕 sizes will forward)"
    else:
        sign = "𝚐𝚛𝚎𝚊𝚝𝚎𝚛 𝚝𝚑𝚊𝚗 (>)" if limit else "𝚕𝚎𝚜𝚜 𝚝𝚑𝚊𝚗 (<)"
        status_text = f"✅ Forward files {sign} <b>{size} 𝙼𝙱</b>"

    await query.message.edit_text(
        f"📁 <b>𝙵ɪʟᴇ 𝚂ɪᴢᴇ 𝙻ɪᴍɪᴛs</b>\n\n"
        f"𝙲𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎 𝚊 size limit filter for forwarded files.\n\n"
        f"<b>𝚂𝚝𝚊𝚝𝚞𝚜:</b> {status_text}",
        reply_markup=await _size_keyboard(user_id),
    )


@Client.on_callback_query(filters.regex(r"^stg_size_type_(none|greater|less)$"))
async def cb_size_type(bot: Client, query):
    user_id = query.from_user.id
    t = query.data.split("_")[-1]

    s = await db.get_settings(user_id)
    curr_size = s.get("file_size", 0)

    if t == "none":
        await db.update_setting(user_id, "size_limit", None)
        await db.update_setting(user_id, "file_size", 0)
    elif t == "greater":
        await db.update_setting(user_id, "size_limit", True)
        if curr_size == 0:
            await db.update_setting(user_id, "file_size", 10)
    elif t == "less":
        await db.update_setting(user_id, "size_limit", False)
        if curr_size == 0:
            await db.update_setting(user_id, "file_size", 10)

    await cb_size_limits(bot, query)


@Client.on_callback_query(filters.regex(r"^stg_size_adj_(-?\d+)$"))
async def cb_size_adj(bot: Client, query):
    user_id = query.from_user.id
    adj = int(query.data.split("_")[-1])

    s = await db.get_settings(user_id)
    size = s.get("file_size", 0)
    limit = s.get("size_limit")

    if limit is None:
        return await query.answer("⚠️ 𝙴𝚗𝚊𝚋𝚕𝚎 𝚕𝚒𝚖𝚒𝚝 type (Greater / Less) first!", show_alert=True)

    new_size = max(1, size + adj)
    await db.update_setting(user_id, "file_size", new_size)
    await cb_size_limits(bot, query)


# ─────────────────────────────────────────────────────────────────────────────
#  Blacklist Extensions — premium-gated
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^stg_extensions$"))
async def cb_extensions(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)

    if not is_premium:
        return await query.answer(
            "🌟 𝙴𝚡𝚝𝚎𝚗𝚜𝚒𝚘𝚗 𝚏𝚒𝚕𝚝𝚎𝚛𝚜 𝚊𝚛𝚎 𝚊 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚏𝚎𝚊𝚝𝚞𝚛𝚎. 𝙲𝚘𝚗𝚝𝚊𝚌𝚝 𝚊𝚍𝚖𝚒𝚗 𝚝𝚘 𝚞𝚙𝚐𝚛𝚊𝚍𝚎.",
            show_alert=True,
        )

    s    = await db.get_settings(user_id)
    exts = s.get("extensions", [])

    rows = []
    if exts:
        rows.append([InlineKeyboardButton("🗑 ᴄʟᴇᴀʀ ᴀʟʟ", callback_data="stg_del_extensions")])
    rows.append([InlineKeyboardButton("✏️ ꜱᴇᴛ ʙʟᴀᴄᴋʟɪꜱᴛ", callback_data="stg_set_extensions")])
    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings")])

    ext_str = ", ".join(f"<code>.{e}</code>" for e in exts) if exts else "None"

    await query.message.edit_text(
        "🚫 <b>𝙱ʟᴀᴄᴋʟɪsᴛ 𝙴xᴛᴇɴsɪᴏɴs</b>\n\n"
        "𝙵𝚒𝚕𝚎𝚜 𝚠𝚒𝚝𝚑 𝚝𝚑𝚎𝚜𝚎 extensions 𝚠𝚒𝚕𝚕 <b>𝚗𝚘𝚝</b> 𝚋𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚍.\n\n"
        f"<b>𝙲𝚞𝚛𝚛𝚎𝚗𝚝:</b> {ext_str}",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@Client.on_callback_query(filters.regex(r"^stg_del_extensions$"))
async def cb_del_extensions(bot: Client, query):
    await db.update_setting(query.from_user.id, "extensions", [])
    await query.answer("𝙴𝚡𝚝𝚎𝚗𝚜𝚒𝚘𝚗 blacklist cleared.", show_alert=False)
    await cb_extensions(bot, query)


@Client.on_callback_query(filters.regex(r"^stg_set_extensions$"))
async def cb_set_extensions(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    prompt = await query.message.edit_text(
        "✏️ <b>𝚂𝚎𝚝 Blacklist Extensions</b>\n\n"
        "𝚂𝚎𝚗𝚍 a list of extensions separated by spaces (e.g. <code>zip rar exe apk</code>).\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚖𝚒𝚗.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="stg_extensions")]]
        ),
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=300)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.", reply_markup=InlineKeyboardMarkup(_HOME))

    if msg.text and msg.text.strip() == "/cancel":
        await msg.delete()
        return await prompt.edit("❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.", reply_markup=InlineKeyboardMarkup(_HOME))

    raw_text = msg.text or ""
    exts = [e.strip().lower().replace(".", "") for e in raw_text.split() if e.strip()]
    await db.update_setting(user_id, "extensions", exts)
    await msg.delete()
    await prompt.edit("✅ Extensions blacklist updated!", reply_markup=InlineKeyboardMarkup(_BACK))


# ─────────────────────────────────────────────────────────────────────────────
#  Whitelist Keywords — premium-gated
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^stg_keywords$"))
async def cb_keywords(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)

    if not is_premium:
        return await query.answer(
            "🌟 𝙺𝚎𝚢𝚠𝚘𝚛𝚍 𝚏𝚒𝚕𝚝𝚎𝚛𝚜 𝚊𝚛𝚎 𝚊 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚏𝚎𝚊𝚝𝚞𝚛𝚎. 𝙲𝚘𝚗𝚝𝚊𝚌𝚝 𝚊𝚍𝚖𝚒𝚗 𝚝𝚘 𝚞𝚙𝚐𝚛𝚊𝚍𝚎.",
            show_alert=True,
        )

    s    = await db.get_settings(user_id)
    kws  = s.get("keywords", [])

    rows = []
    if kws:
        rows.append([InlineKeyboardButton("🗑 ᴄʟᴇᴀʀ ᴀʟʟ", callback_data="stg_del_keywords")])
    rows.append([InlineKeyboardButton("✏️ ꜱᴇᴛ ᴋᴇʏᴡᴏʀᴅꜱ", callback_data="stg_set_keywords")])
    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings")])

    kw_str = ", ".join(f"<code>{k}</code>" for k in kws) if kws else "None (all messages forward)"

    await query.message.edit_text(
        "🔍 <b>𝙺𝚎𝚢𝚠𝚘𝚛𝚍 𝙵ɪʟᴛᴇʀs</b>\n\n"
        "𝙸𝚏 configured, messages/files will <b>𝚘𝚗𝚕𝚢</b> 𝚋𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚍 if they contain "
        "𝚊𝚝 𝚕𝚎𝚊𝚜𝚝 𝚘𝚗𝚎 of these keywords (case-insensitive).\n\n"
        f"<b>𝙲𝚞𝚛𝚛𝚎𝚗𝚝:</b> {kw_str}",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@Client.on_callback_query(filters.regex(r"^stg_del_keywords$"))
async def cb_del_keywords(bot: Client, query):
    await db.update_setting(query.from_user.id, "keywords", [])
    await query.answer("𝙺𝚎𝚢𝚠𝚘𝚛𝚍 whitelist cleared.", show_alert=False)
    await cb_keywords(bot, query)


@Client.on_callback_query(filters.regex(r"^stg_set_keywords$"))
async def cb_set_keywords(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    prompt = await query.message.edit_text(
        "✏️ <b>𝚂𝚎𝚝 Whitelist Keywords</b>\n\n"
        "𝚂𝚎𝚗𝚍 keywords separated by spaces (e.g. <code>premium leak paid python</code>).\n\n"
        "<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝. 𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚖𝚒𝚗.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="stg_keywords")]]
        ),
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=300)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.", reply_markup=InlineKeyboardMarkup(_HOME))

    if msg.text and msg.text.strip() == "/cancel":
        await msg.delete()
        return await prompt.edit("❌ 𝙲𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍.", reply_markup=InlineKeyboardMarkup(_HOME))

    raw_text = msg.text or ""
    kws = [k.strip().lower() for k in raw_text.split() if k.strip()]
    await db.update_setting(user_id, "keywords", kws)
    await msg.delete()
    await prompt.edit("✅ Whitelist keywords updated!", reply_markup=InlineKeyboardMarkup(_BACK))


# ─────────────────────────────────────────────────────────────────────────────
#  Clean Duplicates (Unequify) trigger
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^stg_clean_duplicates$"))
async def cb_clean_duplicates(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)

    if not is_premium:
        return await query.answer(
            "🌟 𝙳𝚞𝚙𝚕𝚒𝚌𝚊𝚝𝚎 Cleaner is a Premium feature. Contact admin to upgrade.",
            show_alert=True,
        )

    # Trigger unequify starting wizard
    from plugins.unequify import cb_unequify_start
    await cb_unequify_start(bot, query)