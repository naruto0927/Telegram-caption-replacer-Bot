"""
/nkey — Keyword Manager

Provides the full inline-keyboard UI for managing detection keywords:
  ➕ Add     → prompts user for new keyword (conversation state)
  ➖ Remove  → shows numbered list, prompts for a number (conversation state)
  ✏️ Edit    → shows numbered list, prompts for a number then new value (conversation state)
  🔄 Refresh → re-renders the menu with fresh data
  ❌ Close   → deletes the menu message

All callbacks verify the caller's admin status before executing.
Conversation states are handled in handlers/text_input.py.
"""
import logging

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.helpers import keyword_list_text
from utils.permissions import is_admin
from utils.states import State, state_manager

logger = logging.getLogger(__name__)


# ── Shared UI builder ─────────────────────────────────────────────────────────

async def _keyword_menu(db) -> tuple:
    """Return (text, InlineKeyboardMarkup) for the keyword manager."""
    keywords = await db.get_keywords()

    if keywords:
        kw_display = keyword_list_text(keywords)
        text = (
            "🔑 **Keyword Manager**\n\n"
            "**Configured Keywords:**\n\n"
            f"{kw_display}\n\n"
            "Select an action:"
        )
        buttons = [
            [
                InlineKeyboardButton("➕ Add",    callback_data="nkey_add"),
                InlineKeyboardButton("➖ Remove", callback_data="nkey_remove"),
            ],
            [InlineKeyboardButton("✏️ Edit", callback_data="nkey_edit")],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="nkey_refresh"),
                InlineKeyboardButton("❌ Close",   callback_data="nkey_close"),
            ],
        ]
    else:
        text = "🔑 **Keyword Manager**\n\n_No keywords configured._"
        buttons = [
            [InlineKeyboardButton("➕ Add", callback_data="nkey_add")],
            [InlineKeyboardButton("❌ Close", callback_data="nkey_close")],
        ]

    return text, InlineKeyboardMarkup(buttons)


async def show_keyword_menu(target, db, *, edit: bool = False) -> None:
    """
    Send or edit a message to show the keyword manager.

    target  — a Message (for /nkey command) or a CallbackQuery (for callbacks)
    edit    — True  → edit the existing message
              False → send a new reply
    """
    text, keyboard = await _keyword_menu(db)

    if edit:
        # target is a CallbackQuery
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        # target is a Message
        await target.reply(text, reply_markup=keyboard)


# ── Handler registration ──────────────────────────────────────────────────────

def register(app, db, cache, stats) -> None:

    # ── /nkey command ─────────────────────────────────────────────────────────

    @app.on_message(filters.command("nkey") & filters.private)
    async def nkey_command(client, message):
        user_id = message.from_user.id
        if not await is_admin(user_id, db):
            await message.reply("❌ You don't have permission to use this command.")
            return
        await show_keyword_menu(message, db, edit=False)

    # ── Inline keyboard callbacks ─────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^nkey_"))
    async def nkey_callback(client, cq):
        user_id = cq.from_user.id

        # Security: every callback verifies the caller's permission
        if not await is_admin(user_id, db):
            await cq.answer("❌ You don't have permission.", show_alert=True)
            return

        data = cq.data

        # ── Refresh ───────────────────────────────────────────────────────────
        if data == "nkey_refresh":
            await cq.answer("🔄 Refreshed")
            await show_keyword_menu(cq, db, edit=True)

        # ── Close ─────────────────────────────────────────────────────────────
        elif data == "nkey_close":
            await cq.answer()
            try:
                await cq.message.delete()
            except Exception:
                pass

        # ── Back (return to menu after a sub-action) ──────────────────────────
        elif data == "nkey_back":
            await cq.answer()
            await show_keyword_menu(cq, db, edit=True)

        # ── Add ───────────────────────────────────────────────────────────────
        elif data == "nkey_add":
            await state_manager.set_state(user_id, State.ADD_KEYWORD)
            await cq.answer()
            await cq.message.edit_text(
                "➕ **Add Keyword**\n\n"
                "Send the keyword or phrase you want the bot to detect.\n\n"
                "**Example:**\n`@user`\n\n"
                "Send /cancel to cancel."
            )

        # ── Remove ────────────────────────────────────────────────────────────
        elif data == "nkey_remove":
            keywords = await db.get_keywords()
            if not keywords:
                await cq.answer("No keywords to remove.", show_alert=True)
                return

            await state_manager.set_state(user_id, State.REMOVE_KEYWORD)
            await cq.answer()
            kw_display = keyword_list_text(keywords)
            await cq.message.edit_text(
                f"➖ **Remove Keyword**\n\n{kw_display}\n\n"
                "Send the **number** of the keyword you want to delete.\n\n"
                "Send /cancel to cancel."
            )

        # ── Edit ──────────────────────────────────────────────────────────────
        elif data == "nkey_edit":
            keywords = await db.get_keywords()
            if not keywords:
                await cq.answer("No keywords to edit.", show_alert=True)
                return

            await state_manager.set_state(user_id, State.EDIT_KEYWORD_SELECT)
            await cq.answer()
            kw_display = keyword_list_text(keywords)
            await cq.message.edit_text(
                f"✏️ **Edit Keyword**\n\n{kw_display}\n\n"
                "Send the **number** of the keyword you want to edit.\n\n"
                "Send /cancel to cancel."
            )
