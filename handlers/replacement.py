"""
/rkey — Global Replacement Phrase Manager

ONE phrase that replaces EVERY configured keyword.
There is no per-keyword replacement.

UI:
  If phrase is set  → [✏️ Change] [🗑 Clear] [❌ Close]
  If phrase is not set → [➕ Set Replacement] [❌ Close]
"""
import logging

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.permissions import is_admin
from utils.states import State, state_manager

logger = logging.getLogger(__name__)


# ── Shared UI builder ─────────────────────────────────────────────────────────

async def _rkey_menu(db) -> tuple:
    settings    = await db.get_settings()
    replacement = settings.get("replacement_phrase")

    if replacement:
        text = (
            "🔄 **Replacement Phrase**\n\n"
            "Current replacement:\n\n"
            f"`{replacement}`"
        )
        buttons = [
            [
                InlineKeyboardButton("✏️ Change", callback_data="rkey_change"),
                InlineKeyboardButton("🗑 Clear",  callback_data="rkey_clear"),
            ],
            [InlineKeyboardButton("❌ Close", callback_data="rkey_close")],
        ]
    else:
        text = (
            "🔄 **Replacement Phrase**\n\n"
            "Current replacement:\n\n"
            "❌ Not configured\n\n"
            "_Without a replacement phrase, automatic editing is disabled._"
        )
        buttons = [
            [InlineKeyboardButton("➕ Set Replacement", callback_data="rkey_change")],
            [InlineKeyboardButton("❌ Close", callback_data="rkey_close")],
        ]

    return text, InlineKeyboardMarkup(buttons)


async def show_rkey_menu(target, db, *, edit: bool = False) -> None:
    text, keyboard = await _rkey_menu(db)
    if edit:
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.reply(text, reply_markup=keyboard)


# ── Handler registration ──────────────────────────────────────────────────────

def register(app, db, cache, stats) -> None:

    # ── /rkey command ─────────────────────────────────────────────────────────

    @app.on_message(filters.command("rkey") & filters.private)
    async def rkey_command(client, message):
        user_id = message.from_user.id
        if not await is_admin(user_id, db):
            await message.reply("❌ You don't have permission to use this command.")
            return
        await show_rkey_menu(message, db, edit=False)

    # ── Inline callbacks ──────────────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^rkey_"))
    async def rkey_callback(client, cq):
        user_id = cq.from_user.id

        if not await is_admin(user_id, db):
            await cq.answer("❌ You don't have permission.", show_alert=True)
            return

        data = cq.data

        # ── Close ─────────────────────────────────────────────────────────────
        if data == "rkey_close":
            await cq.answer()
            try:
                await cq.message.delete()
            except Exception:
                pass

        # ── Change / Set ──────────────────────────────────────────────────────
        elif data == "rkey_change":
            await state_manager.set_state(user_id, State.SET_REPLACEMENT)
            await cq.answer()
            await cq.message.edit_text(
                "🔄 **Set Replacement Phrase**\n\n"
                "Send the phrase that should replace **every** configured keyword.\n\n"
                "**Example:**\n`@hii`\n\n"
                "The phrase can contain spaces and multiple words:\n"
                "`🔥 Join @MyChannel for updates`\n\n"
                "Send /cancel to cancel."
            )

        # ── Clear (ask confirmation) ───────────────────────────────────────────
        elif data == "rkey_clear":
            await cq.answer()
            await cq.message.edit_text(
                "⚠️ **Clear replacement phrase?**\n\n"
                "Without a replacement phrase, automatic editing will be disabled.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Confirm", callback_data="rkey_clear_confirm"),
                        InlineKeyboardButton("❌ Cancel",  callback_data="rkey_clear_cancel"),
                    ]
                ]),
            )

        # ── Clear confirmed ───────────────────────────────────────────────────
        elif data == "rkey_clear_confirm":
            await db.update_settings(replacement_phrase=None)
            await cache.set_replacement(None)
            logger.info("Replacement phrase cleared by %d", user_id)
            await cq.answer("✅ Cleared")
            await cq.message.edit_text(
                "✅ **Replacement phrase cleared.**\n\n"
                "Automatic editing is now paused until a replacement is configured.\n\n"
                "Use /rkey to set a new replacement."
            )

        # ── Clear cancelled ───────────────────────────────────────────────────
        elif data == "rkey_clear_cancel":
            await cq.answer("Cancelled")
            await show_rkey_menu(cq, db, edit=True)
