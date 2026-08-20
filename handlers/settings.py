"""
Settings commands.

/on      — Enable keyword editor      (admin)
/off     — Disable keyword editor     (admin)
/status  — Show full bot status       (admin)
/reload  — Force cache reload         (admin)
/cancel  — Cancel active conversation (any admin)
/channel — Set ECHANNEL               (owner only)
"""
import logging

from pyrogram import filters

from config import Config
from utils.helpers import format_number
from utils.permissions import is_admin
from utils.states import state_manager

logger = logging.getLogger(__name__)


def register(app, db, cache, stats) -> None:

    # ── /cancel ───────────────────────────────────────────────────────────────

    @app.on_message(filters.command("cancel") & filters.private)
    async def cancel_handler(client, message):
        user_id  = message.from_user.id
        state, _ = await state_manager.get_state(user_id)

        if state and state != "expired":
            await state_manager.clear_state(user_id)
            await message.reply("❌ **Operation cancelled.**")
        else:
            await message.reply("Nothing to cancel.")

    # ── /on ───────────────────────────────────────────────────────────────────

    @app.on_message(filters.command("on") & filters.private)
    async def on_handler(client, message):
        user_id = message.from_user.id
        if not await is_admin(user_id, db):
            await message.reply("❌ You don't have permission to use this command.")
            return

        await db.update_settings(editor_enabled=True)
        await cache.set_editor_enabled(True)
        logger.info("Editor enabled by %d", user_id)
        await message.reply("▶️ **Keyword editor enabled.**")

    # ── /off ──────────────────────────────────────────────────────────────────

    @app.on_message(filters.command("off") & filters.private)
    async def off_handler(client, message):
        user_id = message.from_user.id
        if not await is_admin(user_id, db):
            await message.reply("❌ You don't have permission to use this command.")
            return

        await db.update_settings(editor_enabled=False)
        await cache.set_editor_enabled(False)
        logger.info("Editor disabled by %d", user_id)
        await message.reply("⏸ **Keyword editor disabled.**")

    # ── /channel ──────────────────────────────────────────────────────────────

    @app.on_message(filters.command("channel") & filters.private)
    async def channel_handler(client, message):
        user_id = message.from_user.id

        if user_id != Config.OWNER_ID:
            await message.reply("❌ You don't have permission to use this command.")
            return

        args = message.command

        if len(args) < 2:
            current = cache.echannel_id
            if current:
                await message.reply(
                    f"📢 **Current ECHANNEL:** `{current}`\n\n"
                    "**Usage:** `/channel -1001234567890`"
                )
            else:
                await message.reply(
                    "📢 **No ECHANNEL configured.**\n\n"
                    "**Usage:** `/channel -1001234567890`\n\n"
                    "_Make sure the bot is added as an admin with **Edit Messages** "
                    "permission in the channel._"
                )
            return

        raw = args[1].strip()
        try:
            channel_id = int(raw)
        except ValueError:
            await message.reply(
                "❌ Invalid channel ID — must be a negative integer.\n"
                "**Example:** `-1001234567890`"
            )
            return

        # Optional live verification
        try:
            chat = await client.get_chat(channel_id)
            chat_title = getattr(chat, "title", str(channel_id))
        except Exception:
            await message.reply(
                f"⚠️ Could not access channel `{channel_id}`.\n\n"
                "_Proceeding anyway — make sure the bot is an admin with "
                "**Edit Messages** permission._"
            )
            chat_title = str(channel_id)

        await db.update_settings(echannel_id=channel_id)
        await cache.set_echannel_id(channel_id)
        logger.info("ECHANNEL set to %d by owner", channel_id)
        await message.reply(
            f"✅ **ECHANNEL updated.**\n\n"
            f"Channel: **{chat_title}**\n"
            f"ID: `{channel_id}`"
        )

    # ── /reload ───────────────────────────────────────────────────────────────

    @app.on_message(filters.command("reload") & filters.private)
    async def reload_handler(client, message):
        user_id = message.from_user.id
        if not await is_admin(user_id, db):
            await message.reply("❌ You don't have permission to use this command.")
            return

        await cache.refresh()
        kw_count = len(cache.keywords)
        logger.info("Cache reloaded by %d — %d keywords", user_id, kw_count)
        await message.reply(
            f"🔄 **Cache reloaded.**\n\n"
            f"Keywords loaded: **{kw_count}**\n"
            f"Replacement: {'set ✅' if cache.replacement else 'not set ❌'}"
        )

    # ── /status ───────────────────────────────────────────────────────────────

    @app.on_message(filters.command("status") & filters.private)
    async def status_handler(client, message):
        user_id = message.from_user.id
        if not await is_admin(user_id, db):
            await message.reply("❌ You don't have permission to use this command.")
            return

        settings      = await db.get_settings()
        kw_count      = await db.count_keywords()
        admins        = await db.get_admins()
        stat_data     = await stats.get_all()
        db_ok         = await db.is_connected()

        editor_on     = settings.get("editor_enabled", True)
        echannel_id   = settings.get("echannel_id")
        replacement   = settings.get("replacement_phrase")
        case_s        = settings.get("case_sensitive", False)

        editor_icon   = "🟢" if editor_on else "🔴"
        db_icon       = "🟢 Connected" if db_ok else "🔴 Disconnected"
        repl_display  = f"`{replacement}`" if replacement else "❌ Not configured"
        channel_disp  = f"`{echannel_id}`" if echannel_id else "❌ Not set"

        lines = [
            "🤖 **Bot Status**",
            "",
            f"Editor: {editor_icon} {'Enabled' if editor_on else 'Disabled'}",
            f"Case sensitive: {'Yes' if case_s else 'No'}",
            "",
            f"ECHANNEL:\n{channel_disp}",
            "",
            f"Keywords: **{kw_count}**",
            "",
            f"Replacement:\n{repl_display}",
            "",
            f"Admins: **{len(admins) + 1}** (including owner)",
            "",
            "**📊 Statistics:**",
            f"Messages Processed: `{format_number(stat_data.get('messages_processed', 0))}`",
            f"Messages Edited:    `{format_number(stat_data.get('messages_edited', 0))}`",
            f"Keywords Detected:  `{format_number(stat_data.get('keywords_detected', 0))}`",
            f"Failed Edits:       `{format_number(stat_data.get('failed_edits', 0))}`",
            f"Uptime:             `{stat_data.get('uptime_str', '—')}`",
            "",
            f"Database: {db_icon}",
        ]

        await message.reply("\n".join(lines))
