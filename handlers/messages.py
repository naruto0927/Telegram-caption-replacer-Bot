"""
Channel message handler.

Registers a single Pyrogram handler that fires on every new channel post.
The actual editing logic lives in MessageEditor.
"""
import logging

from pyrogram import filters

from services.message_editor import MessageEditor

logger = logging.getLogger(__name__)


def register(app, db, cache, stats) -> None:
    editor = MessageEditor(cache, stats)

    @app.on_message(filters.channel)
    async def on_channel_post(client, message):
        """Entry-point for every new channel message."""
        await editor.process_message(client, message)
