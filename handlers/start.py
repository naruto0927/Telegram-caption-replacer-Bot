"""
/start command handler.
Shows a welcome message and lists available commands based on the caller's role.
"""
import logging

from pyrogram import filters

from config import Config
from utils.permissions import is_admin

logger = logging.getLogger(__name__)


def register(app, db, cache, stats) -> None:

    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client, message):
        user_id  = message.from_user.id
        name     = message.from_user.first_name or "there"
        owner    = user_id == Config.OWNER_ID
        admin    = await is_admin(user_id, db)

        lines = [
            f"👋 Hello, **{name}**!",
            "",
            "🤖 **Telegram Channel Keyword Editor Bot**",
            "",
            "I automatically detect and replace configured keywords in your "
            "channel posts in real-time — no manual intervention needed.",
            "",
        ]

        if admin:
            lines += [
                "**📋 Available Commands:**",
                "",
                "• /nkey — Manage detection keywords",
                "• /rkey — Set the global replacement phrase",
                "• /status — View bot status & statistics",
                "• /on — Enable the keyword editor",
                "• /off — Disable the keyword editor",
                "• /reload — Reload keyword cache from database",
                "",
                "**🔍 Bulk Edit:**",
                "",
                "• /scan `[limit]` — Scan ECHANNEL history and replace keywords",
                "  _e.g. `/scan 500` scans the last 500 posts_",
                "• /stopscan — Cancel a running scan",
            ]
            if owner:
                lines += [
                    "",
                    "**👑 Owner-Only Commands:**",
                    "",
                    "• /addadmin `USER_ID` — Grant admin access",
                    "• /deladmin `USER_ID` — Revoke admin access",
                    "• /listadmin — List all admins",
                    "• /channel `CHANNEL_ID` — Set the monitored channel",
                ]
        else:
            lines.append("ℹ️ You don't have access to bot controls.")

        await message.reply("\n".join(lines))
