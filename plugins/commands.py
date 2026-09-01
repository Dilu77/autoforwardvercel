import asyncio
import logging

from database import db
from config import Config, temp
from plugins.forwarder import launch_userbot, stop_userbot, is_running
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Keyboard helpers
# ─────────────────────────────────────────────────────────────────────────────


async def main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    is_ultra     = await db.is_premium_ultra(user_id) or user_id in Config.OWNER_ID
    is_owner     = user_id in Config.OWNER_ID

    rows = [
        [
            InlineKeyboardButton("📡 ʟɪᴠᴇ ғᴏʀᴡᴀʀᴅ", callback_data="menu_live_forward"),
            InlineKeyboardButton("📂 ғᴏʀᴡᴀʀᴅ ᴏʟᴅ", callback_data="clone_start")
        ],
        [InlineKeyboardButton("⚙️ sᴇᴛᴛɪɴɢs ʜᴜʙ", callback_data="menu_settings_hub")],
    ]

    adv_row = []
    if is_ultra:
         adv_row.append(InlineKeyboardButton("📋 ᴍᴜʟᴛɪ-ᴛᴀꜱᴋꜱ 💎", callback_data="tasks_menu"))
    if is_owner:
         adv_row.append(InlineKeyboardButton("🛠 ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", callback_data="admin_main_menu"))
         
    if adv_row:
         rows.append(adv_row)
         
    rows.append([InlineKeyboardButton("💎 ᴘʟᴀɴꜱ & ʜᴇʟᴘ", callback_data="menu_plans_help")])

    return InlineKeyboardMarkup(rows)

async def settings_hub_keyboard(user_id: int) -> InlineKeyboardMarkup:
    is_premium = await db.is_premium(user_id)
    premium_tag = " 🌟" if is_premium else ""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 ᴀᴜᴛʜ ꜱᴇᴛᴜᴘ", callback_data="menu_auth_setup")],
        [
            InlineKeyboardButton("📥 ꜱᴏᴜʀᴄᴇꜱ", callback_data="menu_sources"),
            InlineKeyboardButton("📤 ᴅᴇꜱᴛɪɴᴀᴛɪᴏɴ", callback_data="menu_dest")
        ],
        [InlineKeyboardButton(f"⚙️ ꜰᴏʀᴡᴀʀᴅɪɴɢ ʀᴜʟᴇꜱ{premium_tag}", callback_data="menu_settings")],
        [InlineKeyboardButton("🔄 ʀᴇᴘʟᴀᴄᴇ ᴛᴇxᴛ 🌟", callback_data="menu_replace")],
        [InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]
    ])

async def auth_setup_keyboard(user_id: int) -> InlineKeyboardMarkup:
    is_premium  = await db.is_premium(user_id)
    has_session = await db.has_session(user_id)
    has_bot     = await db.has_bot_token(user_id)
    
    settings    = await db.get_settings(user_id)
    client_type = settings.get("client_type", "session")

    auth_row = []
    if not is_premium:
        if has_session:
            auth_row = [InlineKeyboardButton("🔑 ʀᴇ-ɢᴇɴᴇʀᴀᴛᴇ ꜱᴇꜱꜱɪᴏɴ", callback_data="gen_start")]
        elif has_bot:
            auth_row = [InlineKeyboardButton("🤖 ʀᴇ-ᴀᴅᴅ ʙᴏᴛ ᴛᴏᴋᴇɴ", callback_data="gen_bot_start")]
        else:
            auth_row = [
                InlineKeyboardButton("🔑 ᴀᴅᴅ ꜱᴇꜱꜱɪᴏɴ", callback_data="gen_start"),
                InlineKeyboardButton("🤖 ᴀᴅᴅ ʙᴏᴛ ᴛᴏᴋᴇɴ", callback_data="gen_bot_start")
            ]
        rows = [auth_row]
    else:
        btn_sess = "🟢 ꜱᴇꜱꜱɪᴏɴ" if client_type == "session" and has_session else ("🔑 ᴀᴅᴅ ꜱᴇꜱꜱɪᴏɴ" if not has_session else "⚪ ꜱᴇꜱꜱɪᴏɴ")
        btn_bot  = "🟢 ʙᴏᴛ ᴛᴏᴋᴇɴ" if client_type == "bot" and has_bot else ("🤖 ᴀᴅᴅ ʙᴏᴛ" if not has_bot else "⚪ ʙᴏᴛ ᴛᴏᴋᴇɴ")
        rows = [
            [
                InlineKeyboardButton(btn_sess, callback_data="set_client_session"),
                InlineKeyboardButton(btn_bot, callback_data="set_client_bot")
            ]
        ]

    rows.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_settings_hub")])
    return InlineKeyboardMarkup(rows)


START_TEXT = (
    "👋 𝙷𝚎𝚕𝚕𝚘, <b>{name}</b>!{badge}\n\n"
    "𝙸 𝚊𝚖 𝚊 𝚙𝚘𝚠𝚎𝚛𝚏𝚞𝚕 <b>𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝙱𝚘𝚝</b>.\n\n"
    "⚙️ 𝚄𝚜𝚎 𝚝𝚑𝚎 𝚑𝚞𝚋 𝚋𝚞𝚝𝚝𝚘𝚗𝚜 𝚋𝚎𝚕𝚘𝚠 𝚝𝚘 𝚌𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎 𝚊𝚗𝚍 𝚌𝚘𝚗𝚝𝚛𝚘𝚕 𝚢𝚘𝚞𝚛 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐."
)


# ─────────────────────────────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_message(filters.private & filters.command("start"))
async def cmd_start(bot: Client, message: Message):
    user = message.from_user
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)

    is_premium = await db.is_premium(user.id)
    is_ultra   = await db.is_premium_ultra(user.id)
    if is_ultra:
        badge = " 💎 <b>𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚄𝚕𝚝𝚛𝚊</b>"
    elif is_premium:
        badge = " 🌟 <b>𝙿𝚛𝚎𝚖𝚒𝚞𝚖</b>"
    else:
        badge = ""

    await message.reply(
        START_TEXT.format(name=user.first_name, badge=badge),
        reply_markup=await main_menu_keyboard(user.id),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Main-menu callback – "Back to menu"
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^main_menu$"))
async def cb_main_menu(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)
    is_ultra   = await db.is_premium_ultra(user_id)
    if is_ultra:
        badge = " 💎 <b>𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚄𝚕𝚝𝚛𝚊</b>"
    elif is_premium:
        badge = " 🌟 <b>𝙿𝚛𝚎𝚖𝚒𝚞𝚖</b>"
    else:
        badge = ""

    await query.message.edit_text(
        START_TEXT.format(name=query.from_user.first_name, badge=badge),
        reply_markup=await main_menu_keyboard(user_id),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  💎 Plans panel
# ─────────────────────────────────────────────────────────────────────────────

PLANS_TEXT = (
    "💎 <b>𝙿𝚕𝚊𝚗𝚜 &amp; 𝙿𝚛𝚒𝚌𝚒𝚗𝚐 (𝚄𝚂𝙳)</b>\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "🆓 <b>Free Plan — $0.00 / month</b>\n"
    "  • Live forwarding (1 source → 1 dest)\n"
    f"  • {Config.FREE_PLAN_DELAY}s start delay\n"
    "  • Watermark on all messages\n"
    "  • Basic media type filters\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "🌟 <b>Premium Plan — $2.99 / month</b>\n"
    "  • Instant forwarding (No delay)\n"
    "  • No watermark (Clean forwarding)\n"
    "  • Custom captions ({caption}, {filename}, {size})\n"
    "  • Custom inline buttons & URLs\n"
    "  • File size limits & Extension blacklist\n"
    "  • Keyword whitelist & Text replace rules\n"
    "  • Protect content & Duplicate skipping\n"
    "  • Unequify duplicate message cleaner\n"
    "  • Auto-resume on server restart\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "💎 <b>Premium Ultra Plan — $5.99 / month</b>\n"
    "  • Everything included in Premium\n"
    "  • Multi-Task forwarding\n"
    f"  • Up to {Config.MAX_ULTRA_TASKS} independent tasks\n"
    "  • Separate sources & destination per task\n"
    "  • Priority VIP support\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "📩 <b>To upgrade, contact the bot admin!</b>"
)

HELP_TEXT = (
    "❔ <b>𝙷𝚎𝚕𝚙 &amp; 𝙵𝚎𝚊𝚝𝚞𝚛𝚎𝚜 𝙶𝚞𝚒𝚍𝚎</b>\n\n"
    "💡 <b>𝙷𝚘𝚠 𝚝𝚘 𝚞𝚜𝚎 𝚝𝚑𝚒𝚜 𝚋𝚘𝚝:</b>\n"
    "𝟷. <b>𝙰𝚞𝚝𝚑:</b> Tap 🔑 <b>𝙰𝚍𝚍 𝚂𝚎𝚜𝚜𝚒𝚘𝚗</b> or 🤖 <b>𝙰𝚍𝚍 𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗</b> to link your Telegram account or Bot.\n"
    "𝟸. <b>𝚂𝚘𝚞𝚛𝚌𝚎𝚜:</b> Tap 📥 <b>𝚂𝚘𝚞𝚛𝚌𝚎𝚜</b> → ➕ <b>𝙰𝚍𝚍 𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚕</b>, then forward any message from the target channel to register it.\n"
    "𝟹. <b>𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗:</b> Tap 📤 <b>𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗</b> → ✏️ <b>𝚂𝚎𝚝 𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗</b>, then forward a message from your channel (your bot/session must be an Admin there).\n"
    "𝟺. <b>𝙻𝚊𝚞𝚗𝚌𝚑:</b> Tap ▶️ <b>𝚂𝚝𝚊𝚛𝚝 𝙵𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐</b> to begin live tracking!\n\n"
    "🗄️ <b>𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝙾𝚕𝚍 𝙼𝚎𝚜𝚜𝚊𝚐𝚎𝚜:</b>\n"
    "• Tap 📂 <b>𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝙾𝚕𝚍</b> to copy old messages.\n"
    "• Provide the starting message link (e.g. <code>t.me/c/12345/10</code>).\n"
    "• Provide the ending message link to forward the range in the background.\n\n"
    "⚙️ <b>𝚄𝚜𝚎𝚛 𝙲𝚘𝚖𝚖𝚊𝚗𝚍𝚜:</b>\n"
    "• /start - Open the main control panel"
)


@Client.on_callback_query(filters.regex(r"^menu_plans$"))
async def cb_menu_plans(bot: Client, query):
    await query.message.edit_text(
        PLANS_TEXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 ʙᴀᴄᴋ", callback_data="main_menu")]
        ]),
    )


@Client.on_callback_query(filters.regex(r"^menu_help$"))
async def cb_menu_help(bot: Client, query):
    await query.message.edit_text(
        HELP_TEXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 ʙᴀᴄᴋ", callback_data="main_menu")]
        ]),
    )


@Client.on_callback_query(filters.regex(r"^menu_live_forward$"))
async def cb_menu_live_forward(bot: Client, query):
    user_id = query.from_user.id
    running = is_running(user_id)
    settings = await db.get_settings(user_id)
    client_type = settings.get("client_type", "session").upper()
    status_text = "🟢 Running" if running else "⏹ Stopped"

    toggle_label = "⏹ ꜱᴛᴏᴘ ꜰᴏʀᴡᴀʀᴅɪɴɢ" if running else "▶️ ꜱᴛᴀʀᴛ ꜰᴏʀᴡᴀʀᴅɪɴɢ"
    toggle_data  = "fw_stop"            if running else "fw_start"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data=toggle_data)],
        [InlineKeyboardButton("📊 ꜱᴛᴀᴛᴜꜱ", callback_data="menu_status")],
        [InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]
    ])

    await query.message.edit_text(
        f"📡 <b>𝙻𝚒𝚟𝚎 𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝙲𝚘𝚗𝚝𝚛𝚘𝚕</b>\n\n"
        f"<b>𝚂𝚝𝚊𝚝𝚞𝚜:</b> {status_text}\n"
        f"<b>𝙰𝚌𝚝𝚒𝚟𝚎 𝙴𝚗𝚐𝚒𝚗𝚎:</b> {client_type}\n\n"
        "𝙻𝚒𝚟𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚠𝚒𝚕𝚕 𝚖𝚘𝚗𝚒𝚝𝚘𝚛 𝚢𝚘𝚞𝚛 𝚜𝚘𝚞𝚛𝚌𝚎𝚜 𝚊𝚗𝚍 𝚌𝚘𝚙𝚢 𝚗𝚎𝚠 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜 𝚒𝚗𝚜𝚝𝚊𝚗𝚝𝚕𝚢.",
        reply_markup=kb
    )


@Client.on_callback_query(filters.regex(r"^menu_settings_hub$"))
async def cb_menu_settings_hub(bot: Client, query):
    user_id = query.from_user.id
    await query.message.edit_text(
        "⚙️ <b>𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝙷𝚞𝚋</b>\n\n"
        "𝙲𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎 𝚢𝚘𝚞𝚛 𝚊𝚞𝚝𝚑𝚎𝚗𝚝𝚒𝚌𝚊ᴛ𝚒𝚘𝚗, 𝚜𝚘𝚞𝚛𝚌𝚎/𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜, 𝚊𝚗𝚍 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚛𝚞𝚕𝚎𝚜.",
        reply_markup=await settings_hub_keyboard(user_id)
    )


@Client.on_callback_query(filters.regex(r"^menu_auth_setup$"))
async def cb_menu_auth_setup(bot: Client, query):
    user_id = query.from_user.id
    await query.message.edit_text(
        "🔑 <b>𝙰𝚞𝚝𝚑𝚎𝚗𝚝𝚒𝚌𝚊𝚝𝚒𝚘𝚗 𝚂𝚎𝚝𝚞𝚙</b>\n\n"
        "𝙼𝚊𝚗𝚊𝚐𝚎 𝚢𝚘𝚞𝚛 𝚞𝚜𝚎𝚛𝚋𝚘𝚝 𝚜𝚎𝚜𝚜𝚒𝚘𝚗 or 𝚋𝚘𝚝 𝚝𝚘𝚔𝚎𝚗.\n"
        "𝙵𝚛𝚎𝚎 𝚞𝚜𝚎𝚛𝚜 𝚌𝚊𝚗 𝚘𝚗𝚕𝚢 𝚑𝚊𝚟𝚎 𝚘𝚗𝚎 𝚊𝚌𝚝𝚒𝚟ᴇ 𝚎𝚗𝚐𝚒𝚗𝚎.",
        reply_markup=await auth_setup_keyboard(user_id)
    )


@Client.on_callback_query(filters.regex(r"^menu_plans_help$"))
async def cb_menu_plans_help(bot: Client, query):
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 ᴘʟᴀɴꜱ", callback_data="menu_plans"),
            InlineKeyboardButton("❔ ʜᴇʟᴘ", callback_data="menu_help")
        ],
        [InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]
    ])
    await query.message.edit_text(
        "💎 <b>𝙿𝚕𝚊𝚗𝚜 &amp; 𝙷𝚎𝚕𝚙 𝙲𝚎𝚗𝚝𝚎𝚛</b>\n\n"
        "𝙻𝚎𝚊𝚛𝚗 𝚖𝚘𝚛𝚎 𝚊𝚋𝚘𝚞𝚝 𝚘𝚞𝚛 𝚙𝚕𝚊𝚗𝚜 or 𝚛𝚎𝚊𝚍 𝚝𝚑𝚎 𝚞𝚜𝚎𝚛 𝚐𝚞𝚒𝚍𝚎.",
        reply_markup=kb
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ▶️ Start / ⏹ Stop forwarding
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^fw_start$"))
async def cb_fw_start(bot: Client, query):
    user_id    = query.from_user.id
    is_premium = await db.is_premium(user_id)
    await query.answer()

    if is_running(user_id):
        return await query.answer("𝙰𝚕𝚛𝚎𝚊𝚍𝚢 𝚛𝚞𝚗𝚗𝚒𝚗𝚐!", show_alert=True)

    await query.message.edit_text("🔄 𝚂𝚝𝚊𝚛𝚝𝚒𝚗𝚐 𝚕𝚒𝚟𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐, 𝚙𝚕𝚎𝚊𝚜𝚎 𝚠𝚊𝚒𝚝...")

    error = await launch_userbot(bot, user_id)

    if error == "no_session":
        return await query.message.edit_text(
            "❌ <b>𝙽𝚘 𝚜𝚎𝚜𝚜𝚒𝚘𝚗 𝚏𝚘𝚞𝚗𝚍.</b>\n\n𝙿𝚕𝚎𝚊𝚜𝚎 𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚎 𝚊 𝚜𝚎𝚜𝚜𝚒𝚘𝚗 𝚏𝚒𝚛𝚜𝚝.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 ɢᴇɴᴇʀᴀᴛᴇ ꜱᴇꜱꜱɪᴏɴ", callback_data="gen_start")],
                [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_live_forward")],
            ]),
        )
    if error == "no_sources":
        return await query.message.edit_text(
            "❌ <b>𝙽𝚘 𝚜𝚘𝚞𝚛𝚌𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜 𝚌𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎𝚍.</b>\n\n"
            "𝙿𝚕𝚎𝚊𝚜𝚎 𝚊𝚍𝚍 𝚊𝚝 𝚕𝚎𝚊𝚜𝚝 𝚘𝚗𝚎 𝚜𝚘𝚞𝚛𝚌𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 ᴀᴅᴅ ꜱᴏᴜʀᴄᴇ", callback_data="menu_sources")],
                [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_live_forward")],
            ]),
        )
    if error == "no_destination":
        return await query.message.edit_text(
            "❌ <b>𝙽𝚘 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚜𝚎𝚝.</b>\n\n𝙿𝚕𝚎𝚊𝚜𝚎 𝚜𝚎𝚝 𝚢𝚘𝚞𝚛 𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚗𝚗𝚎𝚕.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 ꜱᴇᴛ ᴅᴇꜱᴛɪɴᴀᴛɪᴏɴ", callback_data="menu_dest")],
                [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_live_forward")],
            ]),
        )
    if error and error.startswith("start_error"):
        return await query.message.edit_text(
            f"❌ <b>𝙵𝚊𝚒𝚕𝚎𝚍 𝚝𝚘 𝚜𝚝𝚊𝚛𝚝 𝚞𝚜𝚎𝚛𝚋𝚘𝚝:</b>\n<code>{error}</code>\n\n"
            "𝚈𝚘𝚞𝚛 𝚜𝚎𝚜𝚜𝚒𝚘𝚗 𝚖𝚊𝚢 𝚋𝚎 𝚎𝚡𝚙𝚒𝚛𝚎𝚍. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚛𝚎𝚐𝚎𝚗𝚎𝚛𝚊𝚝𝚎.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 ʀᴇ-ɢᴇɴᴇʀᴀᴛᴇ", callback_data="gen_start")],
                [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_live_forward")],
            ]),
        )

    sources  = await db.get_sources(user_id)
    dest     = await db.get_destination(user_id)
    src_list = "\n".join(
        f"  • {s['title']} (<code>{s['chat_id']}</code>)" for s in sources
    )

    plan_note = ""
    if not is_premium:
        plan_note = (
            f"\n\n⏳ <b>𝙵𝚛𝚎𝚎 𝚙𝚕𝚊𝚗:</b> {Config.FREE_PLAN_DELAY}𝚜 𝚠𝚊𝚛𝚖-𝚞𝚙 𝚍𝚎𝚕𝚊𝚢 𝚋𝚎𝚏𝚘𝚛𝚎 "
            f"𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚜𝚝𝚊𝚛𝚝𝚜.\n𝙼𝚎𝚜𝚜𝚊𝚐𝚎𝚜 𝚠𝚒𝚕𝚕 𝚌𝚊𝚛𝚛𝚢 𝚝𝚑𝚎 <code>@fdforwardbot</code> 𝚝𝚊𝚐."
        )

    await query.message.edit_text(
        "✅ <b>𝙻𝚒𝚟𝚎 𝙵𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚂𝚝𝚊𝚛𝚝𝚎𝚍!</b>\n\n"
        f"<b>𝚂𝚘𝚞𝚛𝚌𝚎𝚜:</b>\n{src_list}\n\n"
        f"<b>𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗:</b> {dest['title']} (<code>{dest['chat_id']}</code>)"
        f"{plan_note}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹ ꜱᴛᴏᴘ ꜰᴏʀᴡᴀʀᴅɪɴɢ", callback_data="fw_stop")],
            [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_live_forward")],
        ]),
    )


@Client.on_callback_query(filters.regex(r"^fw_stop$"))
async def cb_fw_stop(bot: Client, query):
    user_id = query.from_user.id
    await query.answer()

    if not is_running(user_id):
        return await query.answer("𝙽𝚘𝚝 𝚛𝚞𝚗𝚗𝚒𝚗𝚐.", show_alert=True)

    await query.message.edit_text("⏸ 𝚂𝚝𝚘𝚙𝚙𝚒𝚗𝚐 𝚕𝚒𝚟𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐...")
    await stop_userbot(user_id)

    await query.message.edit_text(
        "⏹ <b>𝙻𝚒𝚟𝚎 𝙵𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚂𝚝𝚘𝚙𝚙𝚎𝚍.</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ ꜱᴛᴀʀᴛ ᴀɢᴀɪɴ", callback_data="fw_start")],
            [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_live_forward")],
        ]),
    )


@Client.on_callback_query(filters.regex(r"^set_client_(session|bot)$"))
async def cb_set_client_type(bot: Client, query):
    user_id = query.from_user.id
    target_type = query.matches[0].group(1)
    
    if target_type == "session":
        if not await db.has_session(user_id):
            return await cb_generate_session(bot, query)
    else:
        if not await db.has_bot_token(user_id):
            return await cb_gen_bot_start(bot, query)
            
    await db.update_setting(user_id, "client_type", target_type)
    await query.answer(f"Switched active client to: {target_type}", show_alert=True)
    await cb_menu_auth_setup(bot, query)


# ─────────────────────────────────────────────────────────────────────────────
#  📊 Status
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_callback_query(filters.regex(r"^menu_status$"))
async def cb_status(bot: Client, query):
    user_id     = query.from_user.id
    running     = is_running(user_id)
    sources     = await db.get_sources(user_id)
    dest        = await db.get_destination(user_id)
    has_sess    = await db.has_session(user_id)
    settings    = await db.get_settings(user_id)
    is_premium  = await db.is_premium(user_id)
    is_ultra    = await db.is_premium_ultra(user_id)
    rep_rules   = await db.get_replace_rules(user_id)

    state_emoji = "✅ 𝚁𝚞𝚗𝚗𝚒𝚗𝚐" if running else "⏹ 𝚂𝚝𝚘𝚙𝚙𝚎𝚍"
    src_count   = len(sources)
    dest_title  = dest["title"] if dest else "𝙽𝚘𝚝 𝚜𝚎𝚝"
    fwd_tag     = "✅" if settings.get("forward_tag") else "❌"
    rem_cap     = "✅" if settings.get("remove_caption") else "❌"
    if is_ultra:
        plan_label = "💎 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚄𝚕𝚝𝚛𝚊"
        tasks = await db.get_tasks(user_id)
        active_tasks = sum(
            1 for t in tasks
            if f"task_{user_id}_{t['task_id']}" in temp.TASK_LISTENERS
        )
        task_line = f"\n<b>𝚃𝚊𝚜𝚔𝚜:</b> {len(tasks)} configured, {active_tasks} running"
    elif is_premium:
        plan_label = "🌟 𝙿𝚛𝚎𝚖𝚒𝚞𝚖"
        task_line = ""
    else:
        plan_label = "🆓 𝙵𝚛𝚎𝚎"
        task_line = ""

    text = (
        f"📊 <b>𝚈𝚘𝚞𝚛 𝚂𝚝𝚊𝚝𝚞𝚜</b>\n\n"
        f"<b>𝙿𝚕𝚊𝚗:</b> {plan_label}\n"
        f"<b>𝙵𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐:</b> {state_emoji}\n"
        f"<b>𝙰𝚌𝚝𝚒𝚟𝚎 𝙲𝚕𝚒𝚎𝚗𝚝:</b> {settings.get('client_type', 'session').capitalize()}\n"
        f"<b>𝚂𝚎𝚜𝚜𝚒𝚘𝚗:</b> {'✅ 𝚂𝚎𝚝' if has_sess else '❌ 𝙽𝚘𝚝 𝚜𝚎𝚝'}\n"
        f"<b>𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗:</b> {'✅ 𝚂𝚎𝚝' if await db.has_bot_token(user_id) else '❌ 𝙽𝚘𝚝 𝚜𝚎𝚝'}\n"
        f"<b>𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚕𝚜:</b> {src_count}\n"
        f"<b>𝙳𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗:</b> {dest_title}\n"
        f"<b>𝙵𝚘𝚛𝚠𝚊𝚛𝚍 𝚃𝚊𝚐:</b> {fwd_tag}\n"
        f"<b>𝚁𝚎𝚖𝚘𝚟𝚎 𝙲𝚊𝚙𝚝𝚒𝚘𝚗:</b> {rem_cap}\n"
        f"<b>𝚁𝚎𝚙𝚕𝚊𝚌𝚎 𝚁𝚞𝚕𝚎𝚜:</b> {len(rep_rules)}"
        f"{task_line}\n"
        f"\n<b>𝚃𝚘𝚝𝚊𝚕 𝙰𝚌𝚝𝚒𝚟𝚎 𝚄𝚜𝚎𝚛𝚜:</b> {len(temp.ACTIVE_USERS)}"
    )
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="menu_live_forward")]]
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Text Commands (/settings, /help, /reset)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("settings"))
async def cmd_settings(bot: Client, message: Message):
    user_id = message.from_user.id
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)
    await message.reply_text(
        "⚙️ <b>𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝙷𝚞𝚋</b>\n\n"
        "𝙲𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎 𝚢𝚘𝚞𝚛 𝚊𝚞𝚝𝚑𝚎𝚗𝚝𝚒𝚌𝚊ᴛ𝚒𝚘𝚗, 𝚜𝚘𝚞𝚛𝚌𝚎/𝚍𝚎𝚜𝚝𝚒𝚗𝚊𝚝𝚒𝚘𝚗 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜, 𝚊𝚗𝚍 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚒𝚗𝚐 𝚛𝚞𝚕𝚎𝚜.",
        reply_markup=await settings_hub_keyboard(user_id)
    )


@Client.on_message(filters.private & filters.command("help"))
async def cmd_help(bot: Client, message: Message):
    user_id = message.from_user.id
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)
    await message.reply_text(
        HELP_TEXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]
        ]),
    )


@Client.on_message(filters.private & filters.command("reset"))
async def cmd_reset(bot: Client, message: Message):
    user_id = message.from_user.id
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)
    
    # Reset user config in database
    await db.settings.update_one(
        {"user_id": int(user_id)},
        {"$set": {"config": db._DEFAULT_SETTINGS}},
        upsert=True
    )
    await message.reply_text("✅ 𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝚜𝚞𝚌𝚌𝚎𝚜𝚜𝚏𝚞𝚕𝚕𝚢 𝚛𝚎𝚜𝚎𝚝 𝚝𝚘 𝚍𝚎𝚏𝚊𝚞𝚕𝚝𝚜!")
