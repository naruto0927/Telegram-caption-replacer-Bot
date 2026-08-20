"""Statistics tracker."""
import logging
import time

from utils.helpers import format_uptime

logger = logging.getLogger(__name__)


class Statistics:
    def __init__(self, db) -> None:
        self._db = db
        self._start_time = time.monotonic()

    async def increment(self, field: str, amount: int = 1) -> None:
        """Atomically increment a named counter in MongoDB."""
        try:
            await self._db.increment_stat(field, amount)
        except Exception as exc:
            logger.warning("Failed to increment stat '%s': %s", field, exc)

    async def get_all(self) -> dict:
        """Return all counters plus live uptime."""
        try:
            data = await self._db.get_stats()
        except Exception:
            data = {}
        data["uptime_seconds"] = time.monotonic() - self._start_time
        data["uptime_str"]     = format_uptime(data["uptime_seconds"])
        return data
