"""memory/session_memory.py — In-session ephemeral context store."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from loguru import logger


class SessionMemory:
    """
    Lightweight in-process session store keyed by session_id.

    Each session holds an arbitrary key→value context dict.
    Sessions expire after `ttl_seconds` of inactivity (last-access-time based).
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        # { session_id: {"data": {...}, "last_access": float} }
        self._store: Dict[str, Dict[str, Any]] = {}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _touch(self, session_id: str) -> None:
        """Update last-access time for a session."""
        if session_id in self._store:
            self._store[session_id]["last_access"] = time.monotonic()

    def _is_expired(self, session_id: str) -> bool:
        if session_id not in self._store:
            return True
        elapsed = time.monotonic() - self._store[session_id]["last_access"]
        return elapsed > self._ttl

    # ── Public API ────────────────────────────────────────────────────────────

    def create_session(self, session_id: str) -> None:
        """Initialise a new empty session. No-op if it already exists."""
        if session_id not in self._store:
            self._store[session_id] = {
                "data": {},
                "last_access": time.monotonic(),
            }
            logger.debug(f"[SessionMemory] Created session: {session_id}")

    def set(self, session_id: str, key: str, value: Any) -> None:
        """Store a key-value pair in a session (creates session if missing)."""
        self.create_session(session_id)
        self._store[session_id]["data"][key] = value
        self._touch(session_id)
        logger.debug(f"[SessionMemory] Set {key} in session {session_id}")

    def get(self, session_id: str, key: str, default: Any = None) -> Any:
        """Retrieve a value from a session."""
        if self._is_expired(session_id):
            self._evict(session_id)
            return default
        self._touch(session_id)
        return self._store.get(session_id, {}).get("data", {}).get(key, default)

    def get_all(self, session_id: str) -> Dict[str, Any]:
        """Return the full data dict for a session."""
        if self._is_expired(session_id):
            self._evict(session_id)
            return {}
        self._touch(session_id)
        return dict(self._store.get(session_id, {}).get("data", {}))

    def update(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Batch update multiple keys in a session."""
        self.create_session(session_id)
        self._store[session_id]["data"].update(updates)
        self._touch(session_id)

    def delete_key(self, session_id: str, key: str) -> None:
        """Delete a single key from a session."""
        if session_id in self._store:
            self._store[session_id]["data"].pop(key, None)
            self._touch(session_id)

    def destroy_session(self, session_id: str) -> None:
        """Permanently remove a session and all its data."""
        self._store.pop(session_id, None)
        logger.debug(f"[SessionMemory] Destroyed session: {session_id}")

    def _evict(self, session_id: str) -> None:
        if session_id in self._store:
            self._store.pop(session_id)
            logger.debug(f"[SessionMemory] Evicted expired session: {session_id}")

    def evict_expired(self) -> int:
        """Evict all expired sessions. Returns count of evicted sessions."""
        expired = [sid for sid in list(self._store) if self._is_expired(sid)]
        for sid in expired:
            self._evict(sid)
        return len(expired)

    def active_sessions(self) -> int:
        return len(self._store)
