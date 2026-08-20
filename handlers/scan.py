"""
/scan [limit]  — Walk ECHANNEL history and edit every post that contains a
                 configured keyword, using the same replacement pipeline as
                 the live message handler.

/stopscan      — Cancel a running scan (any admin can stop it).

Dual-client architecture
────────────────────────
  Bots cannot call messages.GetHistory (Telegram restriction).
  Solution: a userbot (session string) reads the channel history, while the
  existing bot client (which is already a channel admin with Edit Messages
  permission) performs all the edits — exactly as it does for live posts.

  user_client  → get_chat_history()          (read-only, needs channel access)
  bot_client   → edit_message_text/caption() (write, needs Edit Messages perm)

If SESSION_STRING is not configured, /scan replies with setup instructions.
"""
import asyncio
import logging

from pyrogram import enums, filters
from pyrogram.errors import (
    ChatAdminRequired,
    FloodWait,
    MessageIdInvalid,
    MessageNotModified,
    RPCError,
)

from utils.formatting import replace_in_text_with_entities
from utils.permissions import is_admin

logger = logging.getLogger(__name__)

# ── Global scan state (one scan at a time across all users) ──────────────────
_scan_lock   = asyncio.Lock()
_stop_event: asyncio.Event = None   # type: ignore[assignment]

_DEFAULT_LIMIT  = 100
_MAX_LIMIT      = 5_000
_EDIT_DELAY     = 0.5    # seconds between successful edits
_PROGRESS_EVERY = 25     # redraw progress every N messages scanned


# ── Handler registration ──────────────────────────────────────────────────────

def register(app, db, cache, stats, user_client=None) -> None:

    # ── /scan ─────────────────────────────────────────────────────────────────
    @app.on_message(filters.command("scan") & filters.private)
    async def scan_command(client, message):
        user_id = message.from_user.id
        if not await is_admin(user_id, db):
            await message.reply("❌ You don't have permission to use this command.")
            return

        # Guard: SESSION_STRING not configured
        if user_client is None:
            await message.reply(
                "❌ **Scan unavailable — no user session configured.**\n\n"
                "Telegram blocks bots from reading channel history.\n"
                "A Telegram user account is needed to fetch past messages.\n\n"
                "**Setup (one-time):**\n"
                "1. Run `python generate_session.py` on your machine\n"
                "2. Copy the printed `SESSION_STRING=…` into your `.env`\n"
                "3. Restart the bot\n\n"
                "_The userbot only reads history. The bot still performs all edits._"
            )
            return

        # Guard: another scan is already running
        if _scan_lock.locked():
            await message.reply(
                "⚠️ A scan is already running.\n\nSend /stopscan to cancel it."
            )
            return

        # ── Parse optional limit ──────────────────────────────────────────────
        args  = message.command
        limit = _DEFAULT_LIMIT
        if len(args) > 1:
            try:
                limit = int(args[1])
                if limit < 1:
                    raise ValueError
                limit = min(limit, _MAX_LIMIT)
            except ValueError:
                await message.reply(
                    "❌ Invalid limit.\n\n"
                    "**Usage:** `/scan [limit]`\n"
                    "**Examples:**\n"
                    "`/scan` — last 100 messages (default)\n"
                    "`/scan 500` — last 500 messages\n"
                    f"Maximum: `{_MAX_LIMIT:,}`"
                )
                return

        # ── Pre-flight checks ─────────────────────────────────────────────────
        echannel_id = cache.echannel_id
        if not echannel_id:
            await message.reply("❌ ECHANNEL not configured. Use /channel first.")
            return

        keywords    = cache.keywords
        replacement = cache.replacement

        if not keywords:
            await message.reply("❌ No keywords configured. Add some with /nkey first.")
            return
        if not replacement:
            await message.reply("❌ No replacement phrase set. Configure it with /rkey first.")
            return

        # ── Build initial status message ──────────────────────────────────────
        kw_preview = ", ".join(f"`{k}`" for k in keywords[:4])
        if len(keywords) > 4:
            kw_preview += f" … +{len(keywords) - 4} more"

        status_msg = await message.reply(
            f"🔍 **ECHANNEL Bulk Scan**\n\n"
            f"Scanning up to **{limit:,}** messages\n"
            f"Keywords : {kw_preview}\n"
            f"Replace  : `{replacement}`\n\n"
            f"⏳ Starting…\n\n"
            f"_Send /stopscan to cancel._"
        )

        # ── Launch scan as background task ────────────────────────────────────
        global _stop_event
        _stop_event = asyncio.Event()

        asyncio.create_task(
            _run_scan(
                bot_client=client,          # bot edits messages
                user_client=user_client,    # userbot reads history
                status_msg=status_msg,
                echannel_id=echannel_id,
                keywords=keywords,
                replacement=replacement,
                case_sensitive=cache.case_sensitive,
                limit=limit,
                stats=stats,
            )
        )

    # ── /stopscan ─────────────────────────────────────────────────────────────
    @app.on_message(filters.command("stopscan") & filters.private)
    async def stopscan_command(client, message):
        user_id = message.from_user.id
        if not await is_admin(user_id, db):
            await message.reply("❌ You don't have permission to use this command.")
            return

        if _scan_lock.locked() and _stop_event is not None:
            _stop_event.set()
            await message.reply(
                "🛑 **Stop signal sent.**\n\n"
                "The scan will halt after the current message."
            )
        else:
            await message.reply("ℹ️ No active scan to stop.")


# ── Core scan loop ────────────────────────────────────────────────────────────

async def _run_scan(
    bot_client,
    user_client,
    status_msg,
    echannel_id: int,
    keywords:    list,
    replacement: str,
    case_sensitive: bool,
    limit:       int,
    stats,
) -> None:
    """
    Walk channel history via userbot, replace keywords via bot client.
    Holds _scan_lock for its entire duration so only one scan runs at a time.
    """
    async with _scan_lock:
        scanned = edited = failed = skipped = 0

        async def _refresh_status(note: str = "⏳ Scanning…") -> None:
            try:
                pct    = min(int(scanned / limit * 100), 100) if limit else 0
                filled = pct // 5
                bar    = "█" * filled + "░" * (20 - filled)
                await status_msg.edit_text(
                    f"🔍 **Scanning ECHANNEL…**\n\n"
                    f"`{bar}` {pct}%\n\n"
                    f"Scanned : **{scanned:,}** / {limit:,}\n"
                    f"Edited  : ✅ **{edited:,}**\n"
                    f"Skipped : ⏭ **{skipped:,}**\n"
                    f"Failed  : ❌ **{failed:,}**\n\n"
                    f"{note}\n"
                    f"_Send /stopscan to cancel._"
                )
            except Exception:
                pass

        try:
            await _refresh_status()

            # user_client reads history; bot cannot use messages.GetHistory
            async for msg in user_client.get_chat_history(echannel_id, limit=limit):
                if _stop_event and _stop_event.is_set():
                    break

                scanned += 1
                if scanned % _PROGRESS_EVERY == 0:
                    await _refresh_status()

                # ── Extract text / caption ────────────────────────────────────
                is_caption = False
                raw_text   = msg.text
                raw_ents   = msg.entities

                if raw_text is None:
                    raw_text   = msg.caption
                    raw_ents   = msg.caption_entities
                    is_caption = True

                if not raw_text:
                    skipped += 1
                    continue

                text = str(raw_text)

                # ── Apply replacement ─────────────────────────────────────────
                new_text, new_entities = replace_in_text_with_entities(
                    text,
                    list(raw_ents or []),
                    keywords,
                    replacement,
                    case_sensitive,
                )

                if new_text == text:
                    skipped += 1
                    continue

                # ── Edit via bot client (has Edit Messages permission) ─────────
                ok = await _safe_edit(
                    bot_client, msg, new_text, new_entities, is_caption,
                    status_msg, scanned, limit, edited, skipped, failed,
                )

                if ok:
                    edited += 1
                    await stats.increment("messages_edited")
                    await stats.increment("keywords_detected")
                    await asyncio.sleep(_EDIT_DELAY)
                else:
                    failed += 1

            # ── Final report ──────────────────────────────────────────────────
            stopped = _stop_event and _stop_event.is_set()
            icon    = "🛑 Stopped" if stopped else "✅ Scan complete"

            await status_msg.edit_text(
                f"{icon} **— ECHANNEL Scan**\n\n"
                f"📊 **Results**\n\n"
                f"Messages scanned  : **{scanned:,}**\n"
                f"Messages edited   : ✅ **{edited:,}**\n"
                f"No keywords found : ⏭ **{skipped:,}**\n"
                f"Failed edits      : ❌ **{failed:,}**"
            )

        except ChatAdminRequired:
            logger.error("Scan: bot lacks Edit Messages permission in %d", echannel_id)
            try:
                await status_msg.edit_text(
                    "❌ **Scan failed.**\n\n"
                    "The bot is missing **Edit Messages** permission in ECHANNEL.\n\n"
                    "Grant the permission and try again."
                )
            except Exception:
                pass

        except Exception as exc:
            logger.error("Scan error: %s", exc, exc_info=True)
            try:
                await status_msg.edit_text(
                    f"❌ **Scan error:** `{type(exc).__name__}`\n\n"
                    f"`{exc}`\n\n"
                    f"Scanned: {scanned:,} | Edited: {edited:,} | Failed: {failed:,}"
                )
            except Exception:
                pass


# ── Single-message edit with FloodWait retry ─────────────────────────────────

async def _safe_edit(
    bot_client,
    msg,
    new_text:     str,
    new_entities: list,
    is_caption:   bool,
    status_msg,
    scanned: int,
    limit:   int,
    edited:  int,
    skipped: int,
    failed:  int,
) -> bool:
    """
    Edit one message using the bot client.
    Returns True on success (or MessageNotModified / MessageIdInvalid).
    Sleeps through FloodWait and retries up to 3 times.
    """
    entity_arg = new_entities if new_entities else None

    for attempt in range(3):
        try:
            if is_caption:
                await bot_client.edit_message_caption(
                    chat_id=msg.chat.id,
                    message_id=msg.id,
                    caption=new_text,
                    parse_mode=enums.ParseMode.DISABLED,
                    caption_entities=entity_arg,
                )
            else:
                await bot_client.edit_message_text(
                    chat_id=msg.chat.id,
                    message_id=msg.id,
                    text=new_text,
                    parse_mode=enums.ParseMode.DISABLED,
                    entities=entity_arg,
                )
            logger.debug("Scan edited msg %d", msg.id)
            return True

        except FloodWait as exc:
            wait = exc.value + 2
            logger.warning("Scan FloodWait %ds on msg %d", wait, msg.id)
            try:
                await status_msg.edit_text(
                    f"⏳ **FloodWait — sleeping {wait}s**\n\n"
                    f"Scanned: {scanned:,}/{limit:,} | "
                    f"Edited: {edited:,} | Failed: {failed:,}\n\n"
                    f"_Scan resumes automatically._"
                )
            except Exception:
                pass
            await asyncio.sleep(wait)
            # loop → retry

        except MessageNotModified:
            return True   # already correct — not an error

        except MessageIdInvalid:
            logger.debug("Scan: msg %d deleted, skipping.", msg.id)
            return True

        except ChatAdminRequired:
            raise         # propagate so the outer loop reports it cleanly

        except RPCError as exc:
            logger.warning("Scan RPC error msg %d attempt %d: %s", msg.id, attempt + 1, exc)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

        except Exception as exc:
            logger.warning("Scan unexpected error msg %d: %s", msg.id, exc)
            return False

    logger.error("Scan: gave up on msg %d after 3 attempts.", msg.id)
    return False
