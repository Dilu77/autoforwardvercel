"""
Affiliate Module (Admin-only)
──────────────────────────────
Intercepts forwarded messages, follows any Amazon short/affiliate link found in
the text or caption, extracts the ASIN from the final redirect URL, rebuilds the
URL with the bot-owner's affiliate tag, and sends the message with the swapped link.

Key fix: if a link cannot be rewritten (no ASIN found — e.g. search/filter URLs),
the message is DROPPED silently instead of forwarded with the original link.

Features:
  • Admin-only setup via /affiliate commands
  • Per-user affiliate tag stored in DB (config.affiliate_tag)
  • Optional: global AFFILIATE_TAG env-var as fallback
  • Blacklist: messages containing any blacklisted term are silently dropped
  • Works for text messages AND media with captions
  • Multiple Amazon domains supported (amazon.in / amazon.com / etc.)
  • Messages with unresolvable Amazon links are dropped (not forwarded as-is)

Commands (OWNER only):
  /affiliate                    – show current affiliate settings
  /setaffiliatetag <tag>        – set your Amazon affiliate tag (e.g. marigo04-21)
  /toggleaffiliate              – enable / disable affiliate mode
  /addblacklist <term>          – add a blacklist term
  /removeblacklist <term>       – remove a blacklist term
  /listblacklist                – list all blacklist terms
  /clearblacklist               – wipe all blacklist terms
"""

import asyncio
import logging
import re
import urllib.parse

import aiohttp

from config import Config, temp
from database import db
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

OWNER_FILTER = filters.user(Config.OWNER_ID) & filters.private

# ─── Amazon URL patterns ─────────────────────────────────────────────────────

# Matches amzn.to/xxx  amzn.in/xxx  a.co/xxx and full amazon URLs
_AMZN_SHORT_RE = re.compile(
    r"https?://(?:amzn\.to|amzn\.in|a\.co)/\S+", re.IGNORECASE
)
_AMZN_FULL_RE = re.compile(
    r"https?://(?:www\.)?amazon\.[a-z.]{2,}/(?:[^/\s]+/)?dp/([A-Z0-9]{10})[^\s]*",
    re.IGNORECASE,
)
# Matches ANY amazon.XX URL (to detect links that couldn't be rewritten)
_AMZN_ANY_RE = re.compile(
    r"https?://(?:www\.)?amazon\.[a-z.]{2,}/\S+", re.IGNORECASE
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ─── DB helpers (stored under config.affiliate_*) ────────────────────────────


async def _get_affiliate_settings(user_id: int) -> dict:
    """Return affiliate sub-document with safe defaults."""
    s = await db.get_settings(user_id)
    return s.get(
        "affiliate",
        {
            "enabled": False,
            "tag": Config.AFFILIATE_TAG or "",
            "blacklist": [],
        },
    )


async def _save_affiliate_settings(user_id: int, aff: dict):
    await db.update_setting(user_id, "affiliate", aff)


# ─── Link resolution ─────────────────────────────────────────────────────────


async def _resolve_url(short_url: str, timeout: int = 10) -> str | None:
    """Follow redirects and return the final URL (no body needed)."""
    try:
        async with aiohttp.ClientSession(headers=_HEADERS) as session:
            async with session.get(
                short_url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                return str(resp.url)
    except Exception as e:
        logger.warning(f"[affiliate] Could not resolve {short_url}: {e}")
        return None


def _extract_asin(url: str) -> str | None:
    """Extract ASIN from a full Amazon product URL."""
    m = _AMZN_FULL_RE.search(url)
    if m:
        return m.group(1)
    # Fallback: /dp/ASIN anywhere in path
    m2 = re.search(r"/dp/([A-Z0-9]{10})", url, re.IGNORECASE)
    return m2.group(1) if m2 else None


def _extract_domain(url: str) -> str:
    """Extract amazon domain, e.g. 'amazon.in'."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().lstrip("www.")
    # Keep only amazon.XX part
    if "amazon." in host:
        return host
    return "amazon.in"  # sensible default


def _build_affiliate_url(asin: str, domain: str, tag: str) -> str:
    return f"https://www.{domain}/dp/{asin}?tag={tag}"


async def _rewrite_amazon_links(text: str, affiliate_tag: str) -> tuple[str, bool]:
    """
    Find all Amazon-ish links in text, resolve short links,
    extract ASIN, rebuild with affiliate_tag. Returns (updated_text, all_rewritten).

    all_rewritten is False if ANY Amazon link was found but could NOT be rewritten
    (e.g. search/filter URLs with no ASIN). In that case the caller should drop
    the message entirely instead of forwarding the original link.
    """
    if not affiliate_tag:
        return text, True

    replacements: list[tuple[str, str]] = []  # (original_url, new_url)
    failed_rewrites: list[str] = []  # URLs that had no ASIN

    # Step 1: resolve & rewrite short links
    for m in _AMZN_SHORT_RE.finditer(text):
        original = m.group(0)
        final_url = await _resolve_url(original)
        if not final_url:
            # Could not resolve — treat as unresolvable Amazon link
            failed_rewrites.append(original)
            continue
        asin = _extract_asin(final_url)
        if not asin:
            logger.debug(f"[affiliate] No ASIN found in resolved {final_url} (from {original})")
            failed_rewrites.append(original)
            continue
        domain = _extract_domain(final_url)
        new_url = _build_affiliate_url(asin, domain, affiliate_tag)
        replacements.append((original, new_url))
        logger.info(f"[affiliate] {original} → {new_url}")

    # Step 2: handle full Amazon links not already processed as short links
    short_originals = {r[0] for r in replacements} | set(failed_rewrites)
    for m in _AMZN_FULL_RE.finditer(text):
        original = m.group(0)
        if original in short_originals:
            continue
        asin = _extract_asin(original)
        if not asin:
            failed_rewrites.append(original)
            continue
        domain = _extract_domain(original)
        new_url = _build_affiliate_url(asin, domain, affiliate_tag)
        replacements.append((original, new_url))
        logger.info(f"[affiliate] (full) {original} → {new_url}")

    # Step 3: check if there are ANY remaining Amazon URLs that we didn't rewrite
    # (e.g. amazon.in/s?k=... search URLs, filter URLs, etc.)
    already_replaced_originals = {r[0] for r in replacements} | set(failed_rewrites)
    for m in _AMZN_ANY_RE.finditer(text):
        original = m.group(0)
        if original not in already_replaced_originals:
            # Amazon link we didn't catch — no ASIN possible (search/filter page)
            logger.debug(f"[affiliate] Unrewritable Amazon URL detected: {original}")
            failed_rewrites.append(original)

    # Apply successful replacements to text
    for orig, new in replacements:
        text = text.replace(orig, new)

    all_rewritten = len(failed_rewrites) == 0
    return text, all_rewritten


# ─── Blacklist check ──────────────────────────────────────────────────────────


def _is_blacklisted(text: str, blacklist: list[str]) -> bool:
    if not blacklist or not text:
        return False
    text_lower = text.lower()
    for term in blacklist:
        if term.lower() in text_lower:
            return True
    return False


def _has_amazon_link(text: str) -> bool:
    """Return True if text contains any Amazon or short Amazon link."""
    return bool(_AMZN_SHORT_RE.search(text) or _AMZN_ANY_RE.search(text))


# ─── Public hook: called from forwarder._handle_message ──────────────────────


async def process_affiliate(
    userbot: Client,
    message: Message,
    user_id: int,
    dest_chat_id: int,
) -> bool:
    """
    If affiliate mode is active for user_id, intercept the message,
    apply link rewriting & blacklist, send the result, and return True
    (meaning forwarder should skip its own send).
    Returns False if affiliate mode is off or not applicable.

    IMPORTANT: If a message contains an Amazon link that cannot be rewritten
    (no ASIN — e.g. search/filter URLs), the message is dropped (True returned,
    nothing sent) instead of forwarding the original unmodified link.
    """
    aff = await _get_affiliate_settings(user_id)
    if not aff.get("enabled"):
        return False

    tag = aff.get("tag", "")
    blacklist = aff.get("blacklist", [])

    # Gather full text for blacklist check
    raw_text = message.text or message.caption or ""

    if _is_blacklisted(raw_text, blacklist):
        logger.info(f"[affiliate][user {user_id}] Message blacklisted — dropping.")
        return True  # consumed, don't forward

    # If there are no Amazon links at all, let forwarder handle normally
    if not _has_amazon_link(raw_text):
        return False

    # Rewrite links in the text/caption
    new_text, all_rewritten = await _rewrite_amazon_links(raw_text, tag)

    if not all_rewritten:
        # Some Amazon links couldn't be rewritten (search/filter URLs, etc.)
        # Drop the message entirely — do NOT send original with old affiliate tag
        logger.info(
            f"[affiliate][user {user_id}] Message contains unrewritable Amazon URL — dropping to prevent old affiliate leak."
        )
        return True  # consumed, nothing sent

    try:
        if message.photo or message.video or message.document or message.animation:
            # Media with caption
            await _safe_send_media(userbot, message, dest_chat_id, new_text)
        elif message.text:
            await _safe_send_text(userbot, dest_chat_id, new_text)
        else:
            # Non-text, non-media (sticker, voice, etc.) — pass through unchanged
            await userbot.copy_message(
                chat_id=dest_chat_id,
                from_chat_id=message.chat.id,
                message_id=message.id,
            )
    except Exception as e:
        logger.error(f"[affiliate][user {user_id}] Send error: {e}")

    return True  # always consumed when affiliate mode is on


async def _safe_send_text(userbot: Client, dest: int, text: str):
    from pyrogram.errors import FloodWait

    while True:
        try:
            await userbot.send_message(chat_id=dest, text=text, disable_web_page_preview=True)
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception as e:
            logger.error(f"[affiliate] send_message error: {e}")
            return


async def _safe_send_media(userbot: Client, message: Message, dest: int, caption: str):
    from pyrogram.errors import FloodWait

    while True:
        try:
            await userbot.copy_message(
                chat_id=dest,
                from_chat_id=message.chat.id,
                message_id=message.id,
                caption=caption,
            )
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception as e:
            logger.error(f"[affiliate] copy_message error: {e}")
            return


# ─────────────────────────────────────────────────────────────────────────────
#  Admin commands
# ─────────────────────────────────────────────────────────────────────────────


@Client.on_message(OWNER_FILTER & filters.command("affiliate"))
async def cmd_affiliate_status(bot: Client, message: Message):
    user_id = message.from_user.id
    aff = await _get_affiliate_settings(user_id)
    enabled = aff.get("enabled", False)
    tag = aff.get("tag") or "_(not set)_"
    blacklist = aff.get("blacklist", [])
    bl_text = ", ".join(f"<code>{t}</code>" for t in blacklist) if blacklist else "_(none)_"

    await message.reply(
        f"🛒 <b>Affiliate Module</b>\n\n"
        f"<b>Status:</b> {'✅ Enabled' if enabled else '❌ Disabled'}\n"
        f"<b>Your tag:</b> <code>{tag}</code>\n"
        f"<b>Blacklist ({len(blacklist)}):</b> {bl_text}\n\n"
        f"<b>Note:</b> Messages with search/filter Amazon URLs (no ASIN) are "
        f"dropped silently instead of forwarding the original link.\n\n"
        f"<b>Commands:</b>\n"
        f"• /setaffiliatetag &lt;tag&gt;\n"
        f"• /toggleaffiliate\n"
        f"• /addblacklist &lt;term&gt;\n"
        f"• /removeblacklist &lt;term&gt;\n"
        f"• /listblacklist\n"
        f"• /clearblacklist"
    )


@Client.on_message(OWNER_FILTER & filters.command("setaffiliatetag"))
async def cmd_set_tag(bot: Client, message: Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply(
            "Usage: <code>/setaffiliatetag marigo04-21</code>"
        )
    tag = parts[1].strip()
    aff = await _get_affiliate_settings(user_id)
    aff["tag"] = tag
    await _save_affiliate_settings(user_id, aff)
    await message.reply(f"✅ Affiliate tag set to <code>{tag}</code>")


@Client.on_message(OWNER_FILTER & filters.command("toggleaffiliate"))
async def cmd_toggle_affiliate(bot: Client, message: Message):
    user_id = message.from_user.id
    aff = await _get_affiliate_settings(user_id)
    aff["enabled"] = not aff.get("enabled", False)
    await _save_affiliate_settings(user_id, aff)
    state = "✅ Enabled" if aff["enabled"] else "❌ Disabled"
    await message.reply(f"Affiliate mode: <b>{state}</b>")


@Client.on_message(OWNER_FILTER & filters.command("addblacklist"))
async def cmd_add_blacklist(bot: Client, message: Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Usage: <code>/addblacklist &lt;term&gt;</code>")
    term = parts[1].strip()
    aff = await _get_affiliate_settings(user_id)
    bl: list = aff.get("blacklist", [])
    if term.lower() in [t.lower() for t in bl]:
        return await message.reply(f"<code>{term}</code> is already blacklisted.")
    bl.append(term)
    aff["blacklist"] = bl
    await _save_affiliate_settings(user_id, aff)
    await message.reply(f"✅ <code>{term}</code> added to blacklist.")


@Client.on_message(OWNER_FILTER & filters.command("removeblacklist"))
async def cmd_remove_blacklist(bot: Client, message: Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Usage: <code>/removeblacklist &lt;term&gt;</code>")
    term = parts[1].strip()
    aff = await _get_affiliate_settings(user_id)
    bl: list = aff.get("blacklist", [])
    new_bl = [t for t in bl if t.lower() != term.lower()]
    if len(new_bl) == len(bl):
        return await message.reply(f"<code>{term}</code> not found in blacklist.")
    aff["blacklist"] = new_bl
    await _save_affiliate_settings(user_id, aff)
    await message.reply(f"✅ <code>{term}</code> removed from blacklist.")


@Client.on_message(OWNER_FILTER & filters.command("listblacklist"))
async def cmd_list_blacklist(bot: Client, message: Message):
    user_id = message.from_user.id
    aff = await _get_affiliate_settings(user_id)
    bl = aff.get("blacklist", [])
    if not bl:
        return await message.reply("Blacklist is empty.")
    lines = "\n".join(f"{i+1}. <code>{t}</code>" for i, t in enumerate(bl))
    await message.reply(f"🚫 <b>Blacklist ({len(bl)} terms)</b>\n\n{lines}")


@Client.on_message(OWNER_FILTER & filters.command("clearblacklist"))
async def cmd_clear_blacklist(bot: Client, message: Message):
    user_id = message.from_user.id
    aff = await _get_affiliate_settings(user_id)
    aff["blacklist"] = []
    await _save_affiliate_settings(user_id, aff)
    await message.reply("✅ Blacklist cleared.")
