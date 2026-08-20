"""
Configuration module — reads all settings from environment variables.
Never hard-code credentials here.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class Config:
    # ── Core Telegram credentials ─────────────────────────────────────────────
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    API_ID: int = int(os.getenv("API_ID", "") or "0")
    API_HASH: str = os.getenv("API_HASH", "")

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI: str = os.getenv("MONGO_URI", "")

    # ── Access control ────────────────────────────────────────────────────────
    OWNER_ID: int = int(os.getenv("OWNER_ID", "") or "0")

    # ── Optional channels (can be overridden at runtime via /channel command) ─
    _raw_echannel = os.getenv("ECHANNEL_ID", "")
    DEFAULT_ECHANNEL_ID: int = int(_raw_echannel) if _raw_echannel.lstrip("-").isdigit() else 0

    _raw_log = os.getenv("LOG_CHANNEL_ID", "")
    LOG_CHANNEL_ID: int = int(_raw_log) if _raw_log.lstrip("-").isdigit() else 0

    # ── Userbot session (required for /scan — bots cannot read channel history) ─
    # Generate with:  python generate_session.py
    SESSION_STRING: str = os.getenv("SESSION_STRING", "")

    @classmethod
    def validate(cls) -> bool:
        """Return True only when all required variables are present."""
        missing = []
        if not cls.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not cls.API_ID:
            missing.append("API_ID")
        if not cls.API_HASH:
            missing.append("API_HASH")
        if not cls.MONGO_URI:
            missing.append("MONGO_URI")
        if not cls.OWNER_ID:
            missing.append("OWNER_ID")

        if missing:
            logger.error(
                "Missing required environment variables: %s", ", ".join(missing)
            )
            return False
        return True
