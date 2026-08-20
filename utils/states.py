"""
Per-user conversation state manager.

States expire after STATE_TTL seconds (default 5 minutes).
Each admin has an independent state — they never interfere.
"""
import asyncio
import time
from enum import Enum, auto
from typing import Any, Dict, Optional, Tuple

STATE_TTL: int = 300  # seconds


class State(Enum):
    ADD_KEYWORD         = auto()
    REMOVE_KEYWORD      = auto()
    EDIT_KEYWORD_SELECT = auto()
    EDIT_KEYWORD_NEW    = auto()
    SET_REPLACEMENT     = auto()


_EXPIRED = "expired"   # sentinel returned when a state has timed out


class StateManager:
    """Thread-safe, in-memory state store with TTL."""

    def __init__(self) -> None:
        self._states: Dict[int, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def set_state(
        self,
        user_id: int,
        state: State,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        async with self._lock:
            self._states[user_id] = {
                "state": state,
                "data": data or {},
                "expires_at": time.monotonic() + STATE_TTL,
            }

    async def get_state(
        self, user_id: int
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        """
        Returns (state, data).
        state is None  → no active state
        state is _EXPIRED → was set but has timed out
        state is State.XXX → active state
        """
        async with self._lock:
            entry = self._states.get(user_id)
            if entry is None:
                return None, {}
            if time.monotonic() > entry["expires_at"]:
                del self._states[user_id]
                return _EXPIRED, {}
            return entry["state"], entry["data"]

    async def clear_state(self, user_id: int) -> None:
        async with self._lock:
            self._states.pop(user_id, None)

    async def has_active_state(self, user_id: int) -> bool:
        state, _ = await self.get_state(user_id)
        return state is not None and state is not _EXPIRED


# Global singleton — import this everywhere
state_manager = StateManager()
EXPIRED = _EXPIRED
