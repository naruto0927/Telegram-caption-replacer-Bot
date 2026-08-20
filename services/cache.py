"""
In-memory keyword cache.

Reads from MongoDB on startup and after any add / edit / remove operation.
All channel messages are processed against this in-memory cache — MongoDB is
not touched per-message.

Architecture
────────────
  MongoDB  ──on change──▶  refresh()  ──▶  KeywordCache  ──▶  MessageEditor
"""
import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class KeywordCache:
    """Thread-safe, async-safe in-memory cache of keywords and settings."""

    def __init__(self, db) -> None:
        self._db = db
        self._lock = asyncio.Lock()

        # Cached values
        self._keywords:        List[str]   = []
        self._replacement:     Optional[str] = None
        self._editor_enabled:  bool          = True
        self._case_sensitive:  bool          = False
        self._echannel_id:     Optional[int] = None

    # ── Full refresh ──────────────────────────────────────────────────────────

    async def refresh(self) -> None:
        """Reload everything from MongoDB."""
        async with self._lock:
            try:
                settings = await self._db.get_settings()
                self._editor_enabled = settings.get("editor_enabled", True)
                self._case_sensitive = settings.get("case_sensitive",  False)
                self._echannel_id    = settings.get("echannel_id",     None)
                self._replacement    = settings.get("replacement_phrase", None)
                self._keywords       = await self._db.get_keywords()
                logger.info(
                    "Cache refreshed — %d keywords, replacement=%s, channel=%s",
                    len(self._keywords),
                    "set" if self._replacement else "unset",
                    self._echannel_id,
                )
            except Exception as exc:
                logger.error("Cache refresh failed: %s", exc)

    # ── Read-only properties ──────────────────────────────────────────────────

    @property
    def keywords(self) -> List[str]:
        return list(self._keywords)

    @property
    def replacement(self) -> Optional[str]:
        return self._replacement

    @property
    def editor_enabled(self) -> bool:
        return self._editor_enabled

    @property
    def case_sensitive(self) -> bool:
        return self._case_sensitive

    @property
    def echannel_id(self) -> Optional[int]:
        return self._echannel_id

    # ── Targeted mutations (no DB round-trip needed after an add/remove) ──────

    async def set_editor_enabled(self, enabled: bool) -> None:
        async with self._lock:
            self._editor_enabled = enabled

    async def set_echannel_id(self, channel_id: Optional[int]) -> None:
        async with self._lock:
            self._echannel_id = channel_id

    async def set_replacement(self, phrase: Optional[str]) -> None:
        async with self._lock:
            self._replacement = phrase

    async def set_case_sensitive(self, value: bool) -> None:
        async with self._lock:
            self._case_sensitive = value

    async def add_keyword(self, keyword: str) -> None:
        async with self._lock:
            if keyword not in self._keywords:
                self._keywords.append(keyword)

    async def remove_keyword(self, keyword: str) -> None:
        async with self._lock:
            try:
                self._keywords.remove(keyword)
            except ValueError:
                pass

    async def update_keyword(self, old: str, new: str) -> None:
        async with self._lock:
            try:
                idx = self._keywords.index(old)
                self._keywords[idx] = new
            except ValueError:
                pass
