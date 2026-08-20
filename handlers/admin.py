"""
Admin management commands — owner-only.

/addadmin USER_ID
/deladmin USER_ID
/listadmin
"""
import logging

from pyrogram import filters

from config import Config

logger = logging.getLogger(__name__)


def register(app, db, cache, stats) -> None:

    # ── /addadmin ─────────────────────────────────────────────────────────────

    @app.on_message(filters.command("addadmin") & filters.private)
    async def add_admin(client, message):
        if message.from_user.id != Config.OWNER_ID:
            await message.reply("❌ You don't have permission to use this command.")
            return

        args = message.command
        if len(args) < 2:
            await message.reply("**Usage:** `/addadmin USER_ID`")
            return

        try:
            target_id = int(args[1])
        except ValueError:
            await message.reply("❌ Invalid user ID — must be a numeric Telegram ID.")
            return

        if target_id == Config.OWNER_ID:
            await message.reply("⚠️ The owner already has the highest level of access.")
            return

        success = await db.add_admin(target_id, message.from_user.id)
        if success:
            logger.info("Admin added: %d (by owner)", target_id)
            await message.reply(
                f"✅ **Admin added.**\n\nUser ID:\n`{target_id}`"
            )
        else:
            await message.reply(
                f"⚠️ User `{target_id}` is already an admin."
            )

    # ── /deladmin ─────────────────────────────────────────────────────────────

    @app.on_message(filters.command("deladmin") & filters.private)
    async def del_admin(client, message):
        if message.from_user.id != Config.OWNER_ID:
            await message.reply("❌ You don't have permission to use this command.")
            return

        args = message.command
        if len(args) < 2:
            await message.reply("**Usage:** `/deladmin USER_ID`")
            return

        try:
            target_id = int(args[1])
        except ValueError:
            await message.reply("❌ Invalid user ID.")
            return

        if target_id == Config.OWNER_ID:
            await message.reply("⚠️ Cannot remove the owner.")
            return

        success = await db.remove_admin(target_id)
        if success:
            logger.info("Admin removed: %d (by owner)", target_id)
            await message.reply(
                f"✅ **Admin removed.**\n\nUser ID:\n`{target_id}`"
            )
        else:
            await message.reply(
                f"⚠️ User `{target_id}` is not an admin."
            )

    # ── /listadmin ────────────────────────────────────────────────────────────

    @app.on_message(filters.command("listadmin") & filters.private)
    async def list_admins(client, message):
        if message.from_user.id != Config.OWNER_ID:
            await message.reply("❌ You don't have permission to use this command.")
            return

        admins = await db.get_admins()

        lines = ["👥 **Admin List**", "", f"👑 **Owner:** `{Config.OWNER_ID}`"]

        if admins:
            lines.append("\n**Admins:**")
            for adm in admins:
                lines.append(f"• `{adm['user_id']}`")
        else:
            lines.append("\n_No additional admins configured._")

        await message.reply("\n".join(lines))
