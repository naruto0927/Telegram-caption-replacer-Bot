"""
Message editing engine.

Pipeline
────────
  New channel post
      ↓
  editor_enabled?
      ↓
  from ECHANNEL?
      ↓
  extract text / caption + entities
      ↓
  replace_in_text_with_entities()
      ↓
  content changed?  →  edit Telegram message
      ↓
  update statistics
"""
import asyncio
import logging

from pyrogram import enums
from pyrogram.errors import (
    ChatAdminRequired,
    FloodWait,
    MessageIdInvalid,
    MessageNotModified,
    RPCError,
)

from utils.formatting import replace_in_text_with_entities

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


class MessageEditor:
    def __init__(self, cache, stats) -> None:
        self._cache = cache
        self._stats = stats

    # ── Public entry-point ────────────────────────────────────────────────────

    async def process_message(self, client, message) -> None:
        """
        Check a channel post for configured keywords and edit it if found.
        All errors are caught so one bad message never stops the handler loop.
        """
        try:
            await self._process(client, message)
        except Exception as exc:
            logger.error(
                "Unhandled error processing message %s: %s",
                getattr(message, "id", "?"),
                exc,
                exc_info=True,
            )

    # ── Internal pipeline ─────────────────────────────────────────────────────

    async def _process(self, client, message) -> None:
        cache = self._cache

        # Guard: editor disabled
        if not cache.editor_enabled:
            return

        # Guard: wrong channel
        if message.chat.id != cache.echannel_id:
            return

        keywords    = cache.keywords
        replacement = cache.replacement

        # Guard: nothing to do
        if not keywords or not replacement:
            return

        # Determine whether this is a text message or a media caption
        is_caption = False
        raw_text   = message.text
        raw_ents   = message.entities

        if raw_text is None:
            raw_text   = message.caption
            raw_ents   = message.caption_entities
            is_caption = True

        if not raw_text:
            return

        text = str(raw_text)

        await self._stats.increment("messages_processed")

        # Apply replacement
        new_text, new_entities = replace_in_text_with_entities(
            text,
            list(raw_ents or []),
            keywords,
            replacement,
            cache.case_sensitive,
        )

        if new_text == text:
            logger.debug("Message %d — no keywords found, skipping.", message.id)
            return

        await self._stats.increment("keywords_detected")

        # Edit the message on Telegram
        success = await self._edit_with_retry(
            client, message, new_text, new_entities, is_caption
        )

        if success:
            await self._stats.increment("messages_edited")
            logger.info(
                "Edited message %d in channel %d.", message.id, message.chat.id
            )
        else:
            await self._stats.increment("failed_edits")

    # ── Telegram API edit with FloodWait retry ────────────────────────────────

    async def _edit_with_retry(
        self, client, message, new_text, new_entities, is_caption
    ) -> bool:
        for attempt in range(_MAX_RETRIES):
            try:
                await self._do_edit(client, message, new_text, new_entities, is_caption)
                return True

            except FloodWait as exc:
                wait = exc.value + 1
                logger.warning("FloodWait %ds — sleeping.", wait)
                await asyncio.sleep(wait)
                # retry

            except MessageNotModified:
                # Text didn't actually change (e.g. same content after normalization)
                logger.debug("Message %d not modified.", message.id)
                return True  # not an error

            except MessageIdInvalid:
                logger.warning("Message %d no longer exists.", message.id)
                return True  # not an error — message was deleted

            except ChatAdminRequired:
                logger.error(
                    "Bot lacks 'Edit Messages' permission in channel %d.",
                    message.chat.id,
                )
                return False

            except RPCError as exc:
                logger.error(
                    "RPC error on attempt %d editing message %d: %s",
                    attempt + 1,
                    message.id,
                    exc,
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)

        return False

    async def _do_edit(self, client, message, new_text, new_entities, is_caption) -> None:
        """Single Telegram API call — no retry logic here."""
        # Pass entities= / caption_entities= only when there's something to set.
        # Passing an empty list would strip all entities; passing None lets
        # Telegram keep whatever is currently on the message (safe default when
        # our adjusted list happens to be empty).
        entity_arg = new_entities if new_entities else None

        if is_caption:
            await client.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.id,
                caption=new_text,
                parse_mode=enums.ParseMode.DISABLED,
                caption_entities=entity_arg,
            )
        else:
            await client.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.id,
                text=new_text,
                parse_mode=enums.ParseMode.DISABLED,
                entities=entity_arg,
            )
