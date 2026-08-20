"""
bot.py — Main entry point for the Telegram Keyword Editor Bot.

Startup sequence
────────────────
  1. Validate config (all required env vars present)
  2. Connect to MongoDB
  3. Seed ECHANNEL from env if DB has no channel set yet
  4. Build in-memory keyword cache from DB
  5. Create Pyrogram client
  6. Register all handlers
  7. Start client and idle
"""
# ── Python 3.10+ / 3.12+ / 3.14 compatibility fix ────────────────────────────
# Pyrogram's sync.py calls asyncio.get_event_loop() at *import time*.
# Python 3.10+ raises RuntimeError("There is no current event loop") when no
# loop has been created yet in the main thread.  We create and set one before
# any Pyrogram module is imported.
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# ─────────────────────────────────────────────────────────────────────────────

import logging
import sys

from pyrogram import Client, idle

from config import Config
from database import Database
from services.cache import KeywordCache
from services.statistics import Statistics

# Configure logging — never log BOT_TOKEN, API_HASH, MONGO_URI
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Silence Pyrogram's very chatty DEBUG output
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logger = logging.getLogger("bot")


async def main() -> None:
    # ── 1. Validate configuration ─────────────────────────────────────────────
    if not Config.validate():
        logger.critical("Bot cannot start — fix the environment variables above.")
        sys.exit(1)

    logger.info("Starting Telegram Keyword Editor Bot …")

    # ── 2. Connect to MongoDB ─────────────────────────────────────────────────
    db = Database(Config.MONGO_URI)
    try:
        await db.connect()
    except Exception as exc:
        logger.critical("Cannot connect to MongoDB: %s", exc)
        sys.exit(1)

    # ── 3. Seed ECHANNEL from env var if not already stored in DB ─────────────
    settings = await db.get_settings()
    if settings.get("echannel_id") is None and Config.DEFAULT_ECHANNEL_ID:
        await db.update_settings(echannel_id=Config.DEFAULT_ECHANNEL_ID)
        logger.info("ECHANNEL initialised from env: %d", Config.DEFAULT_ECHANNEL_ID)

    # ── 4. Build in-memory cache ──────────────────────────────────────────────
    cache = KeywordCache(db)
    await cache.refresh()

    # ── 5. Statistics tracker ─────────────────────────────────────────────────
    stats = Statistics(db)

    # ── 6. Create Pyrogram bot client ────────────────────────────────────────
    app = Client(
        name="keyword_editor_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        in_memory=True,          # no session file — safe for ephemeral containers
    )

    # ── 6b. Create userbot client if SESSION_STRING is provided ──────────────
    # Bots cannot call messages.GetHistory, so /scan needs a user account to
    # read channel history.  The bot still performs all edits.
    user_client = None
    if Config.SESSION_STRING:
        user_client = Client(
            name="keyword_editor_userbot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            session_string=Config.SESSION_STRING,
            in_memory=True,
        )
        logger.info("Userbot client created (SESSION_STRING is set).")
    else:
        logger.warning(
            "SESSION_STRING not set — /scan will be unavailable. "
            "Run 'python generate_session.py' to generate one."
        )

    # ── 7. Register handlers ──────────────────────────────────────────────────
    from handlers.start       import register as reg_start
    from handlers.admin       import register as reg_admin
    from handlers.keywords    import register as reg_keywords
    from handlers.replacement import register as reg_replacement
    from handlers.settings    import register as reg_settings
    from handlers.messages    import register as reg_messages
    from handlers.scan        import register as reg_scan
    from handlers.text_input  import register as reg_text_input

    reg_start(app, db, cache, stats)
    reg_admin(app, db, cache, stats)
    reg_keywords(app, db, cache, stats)
    reg_replacement(app, db, cache, stats)
    reg_settings(app, db, cache, stats)
    reg_messages(app, db, cache, stats)
    reg_scan(app, db, cache, stats, user_client=user_client)   # dual-client
    reg_text_input(app, db, cache, stats)                       # group=1 — last

    logger.info("All handlers registered.")

    # ── 8. Start bot (+ userbot) and idle ────────────────────────────────────
    if user_client:
        async with app, user_client:
            me_bot  = await app.get_me()
            me_user = await user_client.get_me()
            logger.info(
                "Bot @%s (ID %d) + Userbot @%s (ID %d) running.",
                me_bot.username,  me_bot.id,
                me_user.username, me_user.id,
            )
            await idle()
    else:
        async with app:
            me = await app.get_me()
            logger.info(
                "Bot running as @%s (ID %d). Press Ctrl+C to stop.",
                me.username, me.id,
            )
            await idle()

    logger.info("Bot stopped gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
