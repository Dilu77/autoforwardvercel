"""
Admin commands (owner only):
  /stats          – total users, active userbots, premium count
  /broadcast      – send a message to all users
  /addpremium     – grant premium to a user
  /removepremium  – revoke premium from a user
  /listpremium    – list all premium users
"""

import asyncio
import logging

from config import Config, temp
from database import db
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

logger = logging.getLogger(__name__)

OWNER_FILTER = filters.user(Config.OWNER_ID) & filters.private


# ─────────────────────────────────────────────────────────────────────────────
#  /stats
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_message(OWNER_FILTER & filters.command("stats"))
async def cmd_stats(bot: Client, message: Message):
    total   = await db.total_users_count()
    active  = len(temp.ACTIVE_USERS)
    premium = await db.total_premium_count()
    await message.reply(
        f"📊 <b>Bot Stats</b>\n\n"
        f"<b>Total users:</b> {total}\n"
        f"<b>Premium users:</b> {premium}\n"
        f"<b>Active forwarders:</b> {active}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /addpremium <user_id>
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_message(OWNER_FILTER & filters.command("addpremium"))
async def cmd_add_premium(bot: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return await message.reply(
            "Usage: <code>/addpremium &lt;user_id&gt;</code>"
        )

    target_id = int(parts[1])
    await db.add_premium(target_id, message.from_user.id)

    # Notify the user if possible
    try:
        await bot.send_message(
            target_id,
            "🌟 <b>You've been upgraded to Premium!</b>\n\n"
            "All features are now unlocked:\n"
            "• No watermark on forwarded messages\n"
            "• No start delay\n"
            "• Replace text rules\n"
            "• Custom captions & all settings\n\n"
            "Enjoy! 🎉"
        )
    except Exception:
        pass

    await message.reply(
        f"✅ User <code>{target_id}</code> has been granted <b>Premium</b>."
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /removepremium <user_id>
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_message(OWNER_FILTER & filters.command("removepremium"))
async def cmd_remove_premium(bot: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return await message.reply(
            "Usage: <code>/removepremium &lt;user_id&gt;</code>"
        )

    target_id = int(parts[1])
    await db.remove_premium(target_id)

    try:
        await bot.send_message(
            target_id,
            "ℹ️ Your <b>Premium</b> access has been revoked.\n"
            "Free plan limits now apply."
        )
    except Exception:
        pass

    await message.reply(
        f"✅ Premium removed from <code>{target_id}</code>."
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /listpremium
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_message(OWNER_FILTER & filters.command("listpremium"))
async def cmd_list_premium(bot: Client, message: Message):
    users = await db.get_all_premium()
    if not users:
        return await message.reply("No premium users yet.")

    lines = []
    for u in users:
        lines.append(f"• <code>{u['user_id']}</code> (added by <code>{u.get('added_by','?')}</code>)")

    await message.reply(
        f"🌟 <b>Premium Users ({len(users)})</b>\n\n" + "\n".join(lines)
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /broadcast
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_message(OWNER_FILTER & filters.command("broadcast"))
async def cmd_broadcast(bot: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply(
            "⚠️ Reply to the message you want to broadcast with /broadcast."
        )

    bcast_msg = message.reply_to_message
    sts       = await message.reply("📡 Broadcasting...")
    users     = await db.get_all_users()
    success = failed = 0

    async for user in users:
        try:
            await bcast_msg.copy(user["user_id"])
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            try:
                await bcast_msg.copy(user["user_id"])
                success += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await sts.edit(
        f"✅ <b>Broadcast complete.</b>\n\n"
        f"<b>Success:</b> {success}\n"
        f"<b>Failed:</b> {failed}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /addultra <user_id>  /removeultra <user_id>
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_message(OWNER_FILTER & filters.command("addultra"))
async def cmd_add_ultra(bot: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return await message.reply("Usage: <code>/addultra &lt;user_id&gt;</code>")

    target_id = int(parts[1])
    await db.add_premium_ultra(target_id, message.from_user.id)

    try:
        await bot.send_message(
            target_id,
            "💎 <b>You've been upgraded to Premium Ultra!</b>\n\n"
            "All features are now unlocked including:\n"
            "• Multi-task forwarding (multiple source→dest pairs)\n"
            "• No watermark, no delay, custom captions, text replacement\n\n"
            "Use the <b>📋 Tasks</b> button in the main menu to set up tasks. 🎉"
        )
    except Exception:
        pass

    await message.reply(f"✅ User <code>{target_id}</code> has been granted <b>Premium Ultra</b>.")


@Client.on_message(OWNER_FILTER & filters.command("removeultra"))
async def cmd_remove_ultra(bot: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return await message.reply("Usage: <code>/removeultra &lt;user_id&gt;</code>")

    target_id = int(parts[1])
    await db.remove_premium_ultra(target_id)

    try:
        await bot.send_message(
            target_id,
            "ℹ️ Your <b>Premium Ultra</b> has been downgraded to regular Premium.\n"
            "Multi-task forwarding is no longer available."
        )
    except Exception:
        pass

    await message.reply(f"✅ Ultra removed from <code>{target_id}</code> (kept regular Premium).")


# ─────────────────────────────────────────────────────────────────────────────
#  Admin Menus
# ─────────────────────────────────────────────────────────────────────────────

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_callback_query(filters.regex(r"^admin_main_menu$"))
async def cb_admin_main_menu(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 ᴍᴀɴᴀɢᴇ ᴜꜱᴇʀꜱ", callback_data="admin_manage_users")],
        [InlineKeyboardButton("🛒 ᴀꜰꜰɪʟɪᴀᴛᴇ ꜱᴇᴛᴛɪɴɢꜱ", callback_data="admin_affiliate_menu")],
        [
            InlineKeyboardButton("📡 ʙʀᴏᴀᴅᴄᴀsᴛ", callback_data="admin_broadcast_prompt"),
            InlineKeyboardButton("📊 ꜱᴛᴀᴛꜱ", callback_data="admin_stats")
        ],
        [InlineKeyboardButton("🏠 ᴍᴇɴᴜ", callback_data="main_menu")]
    ])
    await query.message.edit_text(
        "🛠 <b>𝙰𝚍𝚖𝚒𝚗 𝙲𝚘𝚗𝚝𝚛𝚘𝚕 𝙿𝚊𝚗𝚎𝚕</b>\n\n"
        "𝙼𝚊𝚗𝚊𝚐𝚎 𝚜𝚞𝚋𝚜𝚌𝚛𝚒𝚙𝚝𝚒𝚘𝚗𝚜, 𝚋𝚛𝚘𝚊𝚍𝚌𝚊𝚜𝚝 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜, 𝚘𝚛 𝚌𝚘𝚗𝚏𝚒𝚐𝚞𝚛𝚎 𝚊𝚏𝚏𝚒𝚕𝚒𝚊𝚝𝚎 𝚕𝚒𝚗𝚔𝚜.",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex(r"^admin_manage_users$"))
async def cb_admin_manage_users(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ᴘʀᴇᴍɪᴜᴍ", callback_data="admin_usr_addprem"),
            InlineKeyboardButton("➖ ᴘʀᴇᴍɪᴜᴍ", callback_data="admin_usr_rmprem")
        ],
        [
            InlineKeyboardButton("➕ ᴜʟᴛʀᴀ", callback_data="admin_usr_addultra"),
            InlineKeyboardButton("➖ ᴜʟᴛʀᴀ", callback_data="admin_usr_rmultra")
        ],
        [InlineKeyboardButton("📋 ʟɪꜱᴛ ᴘʀᴇᴍɪᴜᴍ", callback_data="admin_usr_list")],
        [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_main_menu")]
    ])
    await query.message.edit_text(
        "👥 <b>𝚄𝚜𝚎𝚛 𝙼𝚊𝚗𝚊𝚐𝚎𝚖𝚎𝚗𝚝</b>\n\n"
        "𝙶𝚛𝚊𝚗𝚝 𝚘𝚛 𝚛𝚎𝚟𝚘𝚔𝚎 Premium/Ultra 𝚝𝚒𝚎𝚛𝚜.",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex(r"^admin_stats$"))
async def cb_admin_stats(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    total   = await db.total_users_count()
    active  = len(temp.ACTIVE_USERS)
    premium = await db.total_premium_count()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_main_menu")]])
    await query.message.edit_text(
        f"📊 <b>𝙱𝚘𝚝 𝚂tats</b>\n\n"
        f"• <b>𝚃𝚘𝚝𝚊𝚕 𝚞𝚜𝚎𝚛𝚜:</b> {total}\n"
        f"• <b>𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚞𝚜𝚎𝚛𝚜:</b> {premium}\n"
        f"• <b>𝙰𝚌𝚝𝚒𝚟𝚎 𝚏𝚘𝚛𝚠𝚊𝚛𝚍𝚎𝚛𝚜:</b> {active}",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex(r"^admin_usr_(addprem|rmprem|addultra|rmultra)$"))
async def cb_admin_user_action(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    action = query.matches[0].group(1)
    
    action_labels = {
        "addprem": "Grant Premium",
        "rmprem": "Revoke Premium",
        "addultra": "Grant Ultra",
        "rmultra": "Revoke Ultra"
    }

    await query.answer()
    prompt = await query.message.edit_text(
        f"👤 <b>{action_labels[action]}</b>\n\n"
        f"𝙿𝚕𝚎𝚊𝚜𝚎 𝚜𝚎𝚗𝚍 𝚝𝚑𝚎 𝚝𝚊𝚛𝚐𝚎𝚝 <b>𝚄𝚜𝚎𝚛 𝙸𝙳</b>.\n\n"
        f"<i>𝚂𝚎𝚗𝚍 /𝚌𝚊𝚗𝚌𝚎𝚕 𝚝𝚘 𝚊𝚋𝚘𝚛𝚝.</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="admin_manage_users")]])
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_manage_users")]]))

    if msg.text and msg.text.strip().lower() == "/cancel":
        await msg.delete()
        return await cb_admin_manage_users(bot, query)

    target_id_str = msg.text.strip()
    await msg.delete()

    if not target_id_str.isdigit():
        return await prompt.edit("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 User ID. Must be numeric.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_manage_users")]]))

    target_id = int(target_id_str)

    try:
        if action == "addprem":
            await db.add_premium(target_id, user_id)
            await bot.send_message(target_id, "🌟 <b>𝚈𝚘𝚞'𝚟𝚎 𝚋𝚎𝚎𝚗 𝚞𝚙𝚐𝚛𝚊𝚍𝚎𝚍 𝚝𝚘 𝙿𝚛𝚎𝚖𝚒𝚞𝚖!</b>")
            res_text = f"✅ User <code>{target_id}</code> is now <b>Premium</b>."
        elif action == "rmprem":
            await db.remove_premium(target_id)
            await bot.send_message(target_id, "ℹ️ 𝚈𝚘𝚞𝚛 <b>𝙿𝚛𝚎𝚖𝚒𝚞𝚖</b> 𝚑𝚊𝚜 𝚋𝚎𝚎𝚗 𝚛𝚎𝚟𝚘𝚔𝚎𝚍.")
            res_text = f"✅ Premium removed from user <code>{target_id}</code>."
        elif action == "addultra":
            await db.add_premium_ultra(target_id, user_id)
            await bot.send_message(target_id, "💎 <b>𝚈𝚘𝚞'𝚟𝚎 𝚋𝚎𝚎𝚗 𝚞𝚙𝚐𝚛𝚊𝚍𝚎𝚍 𝚝𝚘 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚄𝚕𝚝𝚛α!</b>")
            res_text = f"✅ User <code>{target_id}</code> is now <b>Premium Ultra</b>."
        elif action == "rmultra":
            await db.remove_premium_ultra(target_id)
            await bot.send_message(target_id, "ℹ️ 𝚈𝚘𝚞𝚛 <b>𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚄𝚕𝚝𝚛𝚊</b> 𝚑𝚊𝚜 𝚋𝚎𝚎𝚗 𝚛𝚎𝚟𝚘𝚔𝚎𝚍.")
            res_text = f"✅ Ultra removed from user <code>{target_id}</code>."
    except Exception as e:
        logger.warning(f"Could not notify target user {target_id}: {e}")
        res_text = f"✅ Action performed, but target user could not be notified."

    await prompt.edit(res_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_manage_users")]]))

@Client.on_callback_query(filters.regex(r"^admin_usr_list$"))
async def cb_admin_user_list(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    users = await db.get_all_premium()
    if not users:
        list_text = "No premium users yet."
    else:
        lines = []
        for u in users:
            lines.append(f"• <code>{u['user_id']}</code> (added by <code>{u.get('added_by','?')}</code>)")
        list_text = "🌟 <b>𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚄𝚜𝚎𝚛𝚜:</b>\n\n" + "\n".join(lines)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_manage_users")]])
    await query.message.edit_text(list_text, reply_markup=kb)

@Client.on_callback_query(filters.regex(r"^admin_broadcast_prompt$"))
async def cb_admin_broadcast_prompt(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    await query.answer()
    prompt = await query.message.edit_text(
        "📡 <b>𝙱𝚛𝚘𝚊𝚍𝚌𝚊𝚜𝚝 𝙼𝚎𝚜𝚜𝚊𝚐𝚎</b>\n\n"
        "𝚂𝚎𝚗𝚍 the message you want to broadcast (supports text, links, photos, etc.).\n\n"
        "<i>𝚂𝚎𝚗𝚍 /cancel to cancel.</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="admin_main_menu")]])
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=300)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ 𝚃𝚒𝚖𝚎𝚍 𝚘𝚞𝚝.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_main_menu")]]))

    if msg.text and msg.text.strip().lower() == "/cancel":
        await msg.delete()
        return await cb_admin_main_menu(bot, query)

    sts = await prompt.edit("📡 Broadcasting...")
    users = await db.get_all_users()
    success = failed = 0

    async for u in users:
        try:
            await msg.copy(u["user_id"])
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            try:
                await msg.copy(u["user_id"])
                success += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await msg.delete()
    await sts.edit(
        f"✅ <b>𝙱𝚛𝚘𝚊𝚍𝚌𝚊𝚜𝚝 𝙲𝚘𝚖𝚙𝚕𝚎𝚝𝚎</b>\n\n"
        f"• <b>𝚂𝚞𝚌𝚌𝚎𝚜𝚜:</b> {success}\n"
        f"• <b>𝙵𝚊𝚒𝚕𝚎𝚍:</b> {failed}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_main_menu")]])
    )

@Client.on_callback_query(filters.regex(r"^admin_affiliate_menu$"))
async def cb_admin_affiliate_menu(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    from plugins.affiliate import _get_affiliate_settings
    aff = await _get_affiliate_settings(user_id)
    enabled_status = "🟢 Enabled" if aff.get("enabled") else "⏹ Disabled"
    tag = aff.get("tag") or "❌ Not set"
    blacklist_count = len(aff.get("blacklist", []))

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ᴛᴏɢɢʟᴇ ᴍᴏᴅᴇ", callback_data="admin_aff_toggle")],
        [InlineKeyboardButton("📝 ᴇᴅɪᴛ ᴛᴀɢ", callback_data="admin_aff_settag")],
        [InlineKeyboardButton("🚫 ʙʟᴀᴄᴋʟɪꜱᴛ ᴏᴘᴛɪᴏɴꜱ", callback_data="admin_aff_blacklist_menu")],
        [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_main_menu")]
    ])
    
    await query.message.edit_text(
        f"🛒 <b>𝙰𝚏𝚏𝚒𝚕𝚒𝚊𝚝𝚎 𝚂𝚎𝚝𝚝𝚒𝚗settings</b>\n\n"
        f"• <b>𝙰𝚞𝚝𝚘-𝚁𝚎𝚠𝚛𝚒𝚝𝚎:</b> {enabled_status}\n"
        f"• <b>𝙰𝚖𝚊𝚣𝚘𝚗 𝚃𝚊𝚐:</b> <code>{tag}</code>\n"
        f"• <b>𝙱𝚕𝚊𝚌𝚔𝚕𝚒𝚜𝚝 𝙸𝚝𝚎𝚖𝚜:</b> {blacklist_count}",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex(r"^admin_aff_toggle$"))
async def cb_admin_aff_toggle(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    from plugins.affiliate import _get_affiliate_settings, _save_affiliate_settings
    aff = await _get_affiliate_settings(user_id)
    aff["enabled"] = not aff.get("enabled", False)
    await _save_affiliate_settings(user_id, aff)
    await query.answer(f"Affiliate mode toggled to: {aff['enabled']}")
    await cb_admin_affiliate_menu(bot, query)

@Client.on_callback_query(filters.regex(r"^admin_aff_settag$"))
async def cb_admin_aff_settag(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    await query.answer()
    prompt = await query.message.edit_text(
        "📝 <b>Set Affiliate Tag</b>\n\n"
        "Please send your new Amazon Affiliate Tag (e.g. `myid-21`).\n\n"
        "<i>Send /cancel to abort.</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="admin_affiliate_menu")]])
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ Timed out.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_affiliate_menu")]]))

    if msg.text and msg.text.strip().lower() == "/cancel":
        await msg.delete()
        return await cb_admin_affiliate_menu(bot, query)

    tag = msg.text.strip()
    await msg.delete()

    from plugins.affiliate import _get_affiliate_settings, _save_affiliate_settings
    aff = await _get_affiliate_settings(user_id)
    aff["tag"] = tag
    await _save_affiliate_settings(user_id, aff)

    await prompt.edit(f"✅ Affiliate tag set to: <code>{tag}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_affiliate_menu")]]))

@Client.on_callback_query(filters.regex(r"^admin_aff_blacklist_menu$"))
async def cb_admin_aff_blacklist_menu(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    from plugins.affiliate import _get_affiliate_settings
    aff = await _get_affiliate_settings(user_id)
    blacklist = aff.get("blacklist", [])

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ᴀᴅᴅ", callback_data="admin_aff_bl_add"),
            InlineKeyboardButton("➖ ʀᴇᴍᴏᴠᴇ", callback_data="admin_aff_bl_rm")
        ],
        [InlineKeyboardButton("🗑 ᴄʟᴇᴀʀ ᴀʟʟ", callback_data="admin_aff_bl_clear")],
        [InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_affiliate_menu")]
    ])

    bl_list = "\n".join(f"• <code>{x}</code>" for x in blacklist) or "_(none)_"
    await query.message.edit_text(
        f"🚫 <b>Blacklist Items</b>\n\n"
        f"Messages containing these words will be silently dropped:\n\n"
        f"{bl_list}",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex(r"^admin_aff_bl_add$"))
async def cb_admin_aff_bl_add(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    await query.answer()
    prompt = await query.message.edit_text(
        "➕ <b>Add Blacklist Term</b>\n\n"
        "Send the word or term you want to blacklist.\n\n"
        "<i>Send /cancel to abort.</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="admin_aff_blacklist_menu")]])
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ Timed out.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_aff_blacklist_menu")]]))

    if msg.text and msg.text.strip().lower() == "/cancel":
        await msg.delete()
        return await cb_admin_aff_blacklist_menu(bot, query)

    term = msg.text.strip()
    await msg.delete()

    from plugins.affiliate import _get_affiliate_settings, _save_affiliate_settings
    aff = await _get_affiliate_settings(user_id)
    blacklist = aff.setdefault("blacklist", [])
    if term not in blacklist:
        blacklist.append(term)
        await _save_affiliate_settings(user_id, aff)
        res = f"✅ Term <code>{term}</code> added to blacklist."
    else:
        res = f"⚠️ Term <code>{term}</code> is already in blacklist."

    await prompt.edit(res, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_aff_blacklist_menu")]]))

@Client.on_callback_query(filters.regex(r"^admin_aff_bl_rm$"))
async def cb_admin_aff_bl_rm(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    await query.answer()
    prompt = await query.message.edit_text(
        "➖ <b>Remove Blacklist Term</b>\n\n"
        "Send the word or term you want to remove.\n\n"
        "<i>Send /cancel to abort.</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="admin_aff_blacklist_menu")]])
    )

    try:
        msg = await bot.listen(chat_id=query.message.chat.id, user_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        return await prompt.edit("⏰ Timed out.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_aff_blacklist_menu")]]))

    if msg.text and msg.text.strip().lower() == "/cancel":
        await msg.delete()
        return await cb_admin_aff_blacklist_menu(bot, query)

    term = msg.text.strip()
    await msg.delete()

    from plugins.affiliate import _get_affiliate_settings, _save_affiliate_settings
    aff = await _get_affiliate_settings(user_id)
    blacklist = aff.get("blacklist", [])
    if term in blacklist:
        blacklist.remove(term)
        await _save_affiliate_settings(user_id, aff)
        res = f"✅ Term <code>{term}</code> removed from blacklist."
    else:
        res = f"⚠️ Term <code>{term}</code> was not in blacklist."

    await prompt.edit(res, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="admin_aff_blacklist_menu")]]))

@Client.on_callback_query(filters.regex(r"^admin_aff_bl_clear$"))
async def cb_admin_aff_bl_clear(bot: Client, query):
    user_id = query.from_user.id
    if user_id not in Config.OWNER_ID:
        return await query.answer("Not authorized", show_alert=True)

    from plugins.affiliate import _get_affiliate_settings, _save_affiliate_settings
    aff = await _get_affiliate_settings(user_id)
    aff["blacklist"] = []
    await _save_affiliate_settings(user_id, aff)
    await query.answer("Blacklist cleared.")
    await cb_admin_aff_blacklist_menu(bot, query)
