"""
MongoDB database layer.

Collections
───────────
  settings   — single document {key:"main"} with all bot settings
  admins     — one document per admin user
  keywords   — one document per detection keyword
  statistics — single document {key:"main"} with counters
"""
import logging
import re as _re
import time
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

logger = logging.getLogger(__name__)


class Database:
    """Async MongoDB manager using Motor."""

    def __init__(self, mongo_uri: str) -> None:
        self.mongo_uri = mongo_uri
        self.client: AsyncIOMotorClient = None  # type: ignore[assignment]
        self.db = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open connection and verify it's alive."""
        self.client = AsyncIOMotorClient(
            self.mongo_uri,
            serverSelectionTimeoutMS=8_000,
            connectTimeoutMS=8_000,
        )
        self.db = self.client.keyword_editor_bot
        await self.client.admin.command("ping")
        logger.info("MongoDB connected.")
        await self._ensure_indexes()

    async def _ensure_indexes(self) -> None:
        try:
            await self.db.keywords.create_index(
                [("keyword", ASCENDING)], unique=True, background=True
            )
            await self.db.admins.create_index(
                [("user_id", ASCENDING)], unique=True, background=True
            )
        except Exception as exc:
            logger.warning("Index creation: %s", exc)

    async def is_connected(self) -> bool:
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False

    # ── Settings ──────────────────────────────────────────────────────────────

    async def get_settings(self) -> dict:
        doc = await self.db.settings.find_one({"key": "main"})
        if not doc:
            return {
                "echannel_id": None,
                "replacement_phrase": None,
                "editor_enabled": True,
                "case_sensitive": False,
            }
        return doc

    async def update_settings(self, **kwargs) -> None:
        await self.db.settings.update_one(
            {"key": "main"}, {"$set": kwargs}, upsert=True
        )

    # ── Admins ────────────────────────────────────────────────────────────────

    async def add_admin(self, user_id: int, added_by: int) -> bool:
        """Return False if user is already an admin."""
        try:
            await self.db.admins.insert_one(
                {"user_id": user_id, "added_by": added_by, "added_at": time.time()}
            )
            logger.info("Admin added: %d (by %d)", user_id, added_by)
            return True
        except Exception:
            return False

    async def remove_admin(self, user_id: int) -> bool:
        result = await self.db.admins.delete_one({"user_id": user_id})
        if result.deleted_count:
            logger.info("Admin removed: %d", user_id)
            return True
        return False

    async def is_admin(self, user_id: int) -> bool:
        doc = await self.db.admins.find_one({"user_id": user_id})
        return doc is not None

    async def get_admins(self) -> list:
        cursor = self.db.admins.find({}, sort=[("added_at", ASCENDING)])
        return [doc async for doc in cursor]

    # ── Keywords ──────────────────────────────────────────────────────────────

    async def add_keyword(self, keyword: str, created_by: int) -> bool:
        """Return False if duplicate."""
        try:
            ts = time.time()
            await self.db.keywords.insert_one(
                {
                    "keyword": keyword,
                    "created_by": created_by,
                    "created_at": ts,
                    "updated_at": ts,
                }
            )
            logger.info("Keyword added: '%s'", keyword)
            return True
        except Exception:
            return False

    async def remove_keyword(self, keyword: str) -> bool:
        result = await self.db.keywords.delete_one({"keyword": keyword})
        if result.deleted_count:
            logger.info("Keyword removed: '%s'", keyword)
            return True
        return False

    async def update_keyword(self, old_kw: str, new_kw: str) -> bool:
        try:
            result = await self.db.keywords.update_one(
                {"keyword": old_kw},
                {"$set": {"keyword": new_kw, "updated_at": time.time()}},
            )
            if result.modified_count:
                logger.info("Keyword updated: '%s' → '%s'", old_kw, new_kw)
                return True
            return False
        except Exception:
            return False  # new_kw already exists (unique index violation)

    async def get_keywords(self) -> list:
        cursor = self.db.keywords.find({}, sort=[("created_at", ASCENDING)])
        return [doc["keyword"] async for doc in cursor]

    async def keyword_exists(self, keyword: str, case_sensitive: bool = False) -> bool:
        if case_sensitive:
            doc = await self.db.keywords.find_one({"keyword": keyword})
        else:
            doc = await self.db.keywords.find_one(
                {
                    "keyword": {
                        "$regex": f"^{_re.escape(keyword)}$",
                        "$options": "i",
                    }
                }
            )
        return doc is not None

    async def count_keywords(self) -> int:
        return await self.db.keywords.count_documents({})

    # ── Statistics ────────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        doc = await self.db.statistics.find_one({"key": "main"})
        if not doc:
            return {
                "messages_processed": 0,
                "messages_edited": 0,
                "keywords_detected": 0,
                "failed_edits": 0,
            }
        return doc

    async def increment_stat(self, field: str, amount: int = 1) -> None:
        await self.db.statistics.update_one(
            {"key": "main"}, {"$inc": {field: amount}}, upsert=True
        )
