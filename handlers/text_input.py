"""
Text-input handler — routes admin free-text messages to the active conversation state.

Registered in group=1 so it runs *after* all command handlers (group=0).
For every private text message that is not a command, we:
  1. Check whether the sender has an active conversation state.
  2. Route to the appropriate sub-handler.
  3. Clear the state after a successful action.

States and their flows
──────────────────────
  ADD_KEYWORD
      admin sends the new keyword text
      → validate duplicate → save to DB → update cache → confirm

  REMOVE_KEYWORD
      admin sends the number from the displayed list
      → validate index → delete from DB → update cache → confirm

  EDIT_KEYWORD_SELECT
      admin sends the number of the keyword to edit
      → store old keyword in state.data → advance to EDIT_KEYWORD_NEW

  EDIT_KEYWORD_NEW
      admin sends the replacement text for the keyword
      → validate duplicate → update in DB → update cache → confirm

  SET_REPLACEMENT
      admin sends the new global replacement phrase
      → save to DB → update cache → confirm
"""
import logging

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.permissions import is_admin
from utils.states import EXPIRED, State, state_manager

logger = logging.getLogger(__name__)


def register(app, db, cache, stats) -> None:

    @app.on_message(filters.private & filters.text, group=1)
    async def text_input_router(client, message):
        # Skip slash-commands — they are handled by group=0 handlers
        text = message.text or ""
        if text.startswith("/"):
            return

        user_id = message.from_user.id

        # Non-admins are silently ignored
        if not await is_admin(user_id, db):
            return

        state, data = await state_manager.get_state(user_id)

        if state is None:
            return  # No active conversation

        if state == EXPIRED:
            await state_manager.clear_state(user_id)
            await message.reply(
                "⌛ **Operation expired.**\n\nPlease start again."
            )
            return

        value = text.strip()
        if not value:
            await message.reply("❌ Input cannot be empty. Please try again.")
            return

        # ── Route to sub-handler ──────────────────────────────────────────────
        if   state == State.ADD_KEYWORD:
            await _handle_add_keyword(message, value, user_id, db, cache)

        elif state == State.REMOVE_KEYWORD:
            await _handle_remove_keyword(message, value, user_id, db, cache)

        elif state == State.EDIT_KEYWORD_SELECT:
            await _handle_edit_select(message, value, user_id, db)

        elif state == State.EDIT_KEYWORD_NEW:
            await _handle_edit_new(message, value, user_id, data, db, cache)

        elif state == State.SET_REPLACEMENT:
            await _handle_set_replacement(message, value, user_id, db, cache)


# ── Sub-handlers ──────────────────────────────────────────────────────────────

_BACK_BUTTON = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🔑 Keyword Manager", callback_data="nkey_back")]]
)


async def _handle_add_keyword(message, keyword, user_id, db, cache):
    settings       = await db.get_settings()
    case_sensitive = settings.get("case_sensitive", False)

    # Duplicate check
    if await db.keyword_exists(keyword, case_sensitive):
        await message.reply(
            "⚠️ **Keyword already exists.**\n\n"
            "Use ✏️ Edit if you want to change it.\n\n"
            "Send another keyword or /cancel to cancel."
        )
        return  # keep state active

    success = await db.add_keyword(keyword, user_id)
    if not success:
        await message.reply("❌ Failed to save keyword. Please try again.")
        return

    await cache.add_keyword(keyword)
    await state_manager.clear_state(user_id)
    logger.info("Keyword added by %d: '%s'", user_id, keyword)
    await message.reply(
        f"✅ **Keyword Added**\n\n`{keyword}`",
        reply_markup=_BACK_BUTTON,
    )


async def _handle_remove_keyword(message, text, user_id, db, cache):
    keywords = await db.get_keywords()

    try:
        idx = int(text) - 1  # convert 1-based to 0-based
    except ValueError:
        await message.reply(
            "❌ Please send a **number**, not text.\n\n"
            "Send /cancel to cancel."
        )
        return

    if idx < 0 or idx >= len(keywords):
        await message.reply(
            f"❌ Invalid number. Please send a number between **1** and **{len(keywords)}**."
        )
        return

    target_kw = keywords[idx]
    success   = await db.remove_keyword(target_kw)

    if not success:
        await message.reply("❌ Failed to remove keyword. Please try again.")
        return

    await cache.remove_keyword(target_kw)
    await state_manager.clear_state(user_id)
    logger.info("Keyword removed by %d: '%s'", user_id, target_kw)
    await message.reply(
        f"✅ **Keyword Removed**\n\n`{target_kw}`",
        reply_markup=_BACK_BUTTON,
    )


async def _handle_edit_select(message, text, user_id, db):
    keywords = await db.get_keywords()

    try:
        idx = int(text) - 1
    except ValueError:
        await message.reply(
            "❌ Please send a **number**, not text.\n\n"
            "Send /cancel to cancel."
        )
        return

    if idx < 0 or idx >= len(keywords):
        await message.reply(
            f"❌ Invalid number. Please send a number between **1** and **{len(keywords)}**."
        )
        return

    old_kw = keywords[idx]
    # Advance state to EDIT_KEYWORD_NEW, storing which keyword we're editing
    await state_manager.set_state(
        user_id, State.EDIT_KEYWORD_NEW, {"old_keyword": old_kw}
    )
    await message.reply(
        f"✏️ **Edit Keyword**\n\n"
        f"Current keyword:\n`{old_kw}`\n\n"
        f"Send the **new keyword**.\n\n"
        f"Send /cancel to cancel."
    )


async def _handle_edit_new(message, new_kw, user_id, data, db, cache):
    old_kw = data.get("old_keyword")

    if not old_kw:
        await state_manager.clear_state(user_id)
        await message.reply(
            "❌ Session error — please start again with /nkey."
        )
        return

    settings       = await db.get_settings()
    case_sensitive = settings.get("case_sensitive", False)

    # Duplicate check (skip if new_kw == old_kw under same case rules)
    same_as_old = (
        new_kw == old_kw
        if case_sensitive
        else new_kw.lower() == old_kw.lower()
    )
    if not same_as_old and await db.keyword_exists(new_kw, case_sensitive):
        await message.reply(
            "⚠️ **Keyword already exists.**\n\n"
            "Send a different keyword or /cancel to cancel."
        )
        return

    success = await db.update_keyword(old_kw, new_kw)
    if not success:
        await message.reply("❌ Failed to update keyword. Please try again.")
        return

    await cache.update_keyword(old_kw, new_kw)
    await state_manager.clear_state(user_id)
    logger.info("Keyword updated by %d: '%s' → '%s'", user_id, old_kw, new_kw)
    await message.reply(
        f"✅ **Keyword Updated**\n\n"
        f"Old:\n`{old_kw}`\n\n"
        f"New:\n`{new_kw}`",
        reply_markup=_BACK_BUTTON,
    )


async def _handle_set_replacement(message, phrase, user_id, db, cache):
    await db.update_settings(replacement_phrase=phrase)
    await cache.set_replacement(phrase)
    await state_manager.clear_state(user_id)
    logger.info("Replacement phrase set by %d", user_id)
    await message.reply(
        f"✅ **Replacement Phrase Updated**\n\n"
        f"New replacement:\n`{phrase}`\n\n"
        f"All configured keywords will now be replaced with this phrase."
    )
