"""
memory/memory_manager.py
─────────────────────────
Unified MemoryManager that combines session memory and long-term vector memory.
Injected into every agent as the single memory interface.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from loguru import logger

from config.settings import get_settings
from memory.long_term_memory import LongTermMemoryBase, create_long_term_memory
from memory.session_memory import SessionMemory


class MemoryManager:
    """
    Single entry-point for all agent memory operations.

    Session memory  → fast, ephemeral, scoped to one analysis run.
    Long-term memory → persistent vector store for historical lookups.
    """

    def __init__(
        self,
        session_memory: Optional[SessionMemory] = None,
        long_term_memory: Optional[LongTermMemoryBase] = None,
    ) -> None:
        cfg = get_settings()
        self._session = session_memory or SessionMemory(ttl_seconds=cfg.session_ttl_seconds)
        self._ltm = long_term_memory or create_long_term_memory(
            backend=cfg.memory_backend.value,
            chromadb_path=cfg.chromadb_persist_path,
            pinecone_api_key=cfg.pinecone_api_key,
            pinecone_index_name=cfg.pinecone_index_name,
        )
        logger.info(
            f"[MemoryManager] Initialised | "
            f"backend={cfg.memory_backend.value}"
        )

    # ── Session Memory ────────────────────────────────────────────────────────

    def new_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        self._session.create_session(session_id)
        logger.info(f"[MemoryManager] New session: {session_id}")
        return session_id

    def save_to_session(self, session_id: str, key: str, value: Any) -> None:
        self._session.set(session_id, key, value)

    def load_from_session(self, session_id: str, key: str, default: Any = None) -> Any:
        return self._session.get(session_id, key, default)

    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Return the complete session context dict."""
        return self._session.get_all(session_id)

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        self._session.update(session_id, updates)

    def destroy_session(self, session_id: str) -> None:
        self._session.destroy_session(session_id)

    # ── Long-Term Memory ──────────────────────────────────────────────────────

    def save_analysis(self, record: Dict[str, Any]) -> str:
        """
        Persist a completed device analysis to long-term memory.

        Expected record keys (subset):
            brand, model_name, condition_grade, damage_types,
            total_repair_cost_mid, resale_price_mid, profit_margin_pct,
            session_id, report_id
        """
        try:
            record_id = self._ltm.store(record)
            logger.info(f"[MemoryManager] Analysis saved to LTM: {record_id}")
            return record_id
        except Exception as exc:
            logger.error(f"[MemoryManager] Failed to save to LTM: {exc}")
            return ""

    def find_similar_cases(
        self,
        device_model: str,
        condition_grade: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Query long-term memory for historically similar device analyses."""
        try:
            results = self._ltm.query_similar(device_model, condition_grade, top_k)
            logger.debug(
                f"[MemoryManager] Found {len(results)} similar cases for "
                f"'{device_model}' / '{condition_grade}'"
            )
            return results
        except Exception as exc:
            logger.warning(f"[MemoryManager] LTM query failed: {exc}")
            return []

    def get_historical_prices(
        self, device_model: str, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Fetch historical resale price data for a specific device model."""
        try:
            return self._ltm.get_price_comps(device_model, top_k)
        except Exception as exc:
            logger.warning(f"[MemoryManager] Price history query failed: {exc}")
            return []

    def get_analysis_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific past analysis by its record ID."""
        try:
            return self._ltm.get_by_id(record_id)
        except Exception as exc:
            logger.warning(f"[MemoryManager] LTM get-by-id failed: {exc}")
            return None

    # ── Combined Helpers ──────────────────────────────────────────────────────

    def get_pricing_context(
        self, session_id: str, device_model: str, condition_grade: str
    ) -> Dict[str, Any]:
        """
        Build a combined pricing context from session + LTM.
        Used by the Resale Agent to enrich its valuation.
        """
        session_ctx = self.get_session_context(session_id)
        historical = self.get_historical_prices(device_model, top_k=10)
        similar = self.find_similar_cases(device_model, condition_grade, top_k=5)

        return {
            "session": session_ctx,
            "historical_prices": historical,
            "similar_cases": similar,
        }
