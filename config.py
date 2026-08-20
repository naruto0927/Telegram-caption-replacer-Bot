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
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "7575709072:AAGBvZRoXkfH7YYe_55drSrwHI0mY4PHsFY")
    API_ID: int = int(os.getenv("API_ID", "20167916") or "0")
    API_HASH: str = os.getenv("API_HASH", "325de70c258003ff1c30fb02077dde25")

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://prit092714_db_user:lOAH50s0alBM3nPu@ac-nnrf9nt-shard-00-00.jgbeo2s.mongodb.net:27017,ac-nnrf9nt-shard-00-01.jgbeo2s.mongodb.net:27017,ac-nnrf9nt-shard-00-02.jgbeo2s.mongodb.net:27017/?ssl=true&replicaSet=atlas-ff6qlt-shard-0&authSource=admin&appName=Cluster0")

    # ── Access control ────────────────────────────────────────────────────────
    OWNER_ID: int = int(os.getenv("OWNER_ID", "6672752177") or "0")

    # ── Optional channels (can be overridden at runtime via /channel command) ─
    _raw_echannel = os.getenv("ECHANNEL_ID", "-1002203431634")
    DEFAULT_ECHANNEL_ID: int = int(_raw_echannel) if _raw_echannel.lstrip("-").isdigit() else 0

    _raw_log = os.getenv("LOG_CHANNEL_ID", "-1003917903989")
    LOG_CHANNEL_ID: int = int(_raw_log) if _raw_log.lstrip("-").isdigit() else 0

    # ── Userbot session (required for /scan — bots cannot read channel history) ─
    # Generate with:  python generate_session.py
    SESSION_STRING: str = os.getenv("SESSION_STRING", "BQEzvOwAFduDEdLILwcD8BcXbjVZuXUyNBDBcJ9dTcjs8icPaIOSMYsbuDI3v-dx03pqkQV-WwzV3-usCKdSXrh0gbwe_0Ml3x2EHskvrHge1J_oPfuQUnMlfz5St-3sQW6U21RBSRA5SUhHvuMhk1q2gkyxbTfADZLDt_8htidwZbD2ULkhEAcVW8dudZ6iPmnmxCcf63Q_f9sTNRe1UC9tXNKub27bvjbGwJZdPJ9WNgGb8IV7_A_dDQPNjjI7tpwscLdMPVqob-kjhgPWhPz0XdbdwJTIP-W2BrYNBsmejRMYIoxbaGqPecFM4jHqD3hr-i34p--oHKTTvwvb17sDBMc_twAAAAGNuh4xAA")

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
