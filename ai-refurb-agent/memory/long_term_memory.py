"""
memory/long_term_memory.py
───────────────────────────
Vector-store backed long-term memory for historical device analyses.
Supports ChromaDB (local) and Pinecone (managed) via a unified interface.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from loguru import logger


# ── Abstract Base ─────────────────────────────────────────────────────────────

class LongTermMemoryBase(ABC):
    """Unified interface for all long-term memory backends."""

    @abstractmethod
    def store(self, record: Dict[str, Any]) -> str:
        """Persist a device analysis record. Returns the record ID."""
        ...

    @abstractmethod
    def query_similar(
        self,
        device_model: str,
        condition_grade: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find historically similar device analyses."""
        ...

    @abstractmethod
    def get_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific record by ID."""
        ...

    @abstractmethod
    def get_price_comps(
        self, device_model: str, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Return historical resale prices for a device model."""
        ...


# ── ChromaDB Backend ──────────────────────────────────────────────────────────

class ChromaDBMemory(LongTermMemoryBase):
    """
    ChromaDB-backed long-term memory.
    Uses sentence embeddings via ChromaDB's default embedding function.
    """

    COLLECTION_NAME = "device_evaluations"

    def __init__(self, persist_path: str = "./chroma_db") -> None:
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            self._client = chromadb.PersistentClient(path=persist_path)
            ef = embedding_functions.DefaultEmbeddingFunction()
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"[LTM:ChromaDB] Connected. Collection '{self.COLLECTION_NAME}' "
                f"has {self._collection.count()} records."
            )
        except ImportError:
            raise ImportError(
                "chromadb is not installed. Run: pip install chromadb"
            )

    def _build_document(self, record: Dict[str, Any]) -> str:
        """Build a searchable text document from a record."""
        return (
            f"Device: {record.get('brand', '')} {record.get('model_name', '')}. "
            f"Condition: {record.get('condition_grade', '')}. "
            f"Repair cost: ${record.get('total_repair_cost_mid', 0):.0f}. "
            f"Resale price: ${record.get('resale_price_mid', 0):.0f}. "
            f"Damage: {', '.join(record.get('damage_types', []))}."
        )

    def store(self, record: Dict[str, Any]) -> str:
        record_id = record.get("record_id") or str(uuid.uuid4())
        record["record_id"] = record_id
        document = self._build_document(record)
        self._collection.add(
            ids=[record_id],
            documents=[document],
            metadatas=[{k: str(v) for k, v in record.items()}],
        )
        logger.debug(f"[LTM:ChromaDB] Stored record {record_id}")
        return record_id

    def query_similar(
        self,
        device_model: str,
        condition_grade: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        query_text = f"Device: {device_model}. Condition: {condition_grade}."
        results = self._collection.query(
            query_texts=[query_text],
            n_results=min(top_k, self._collection.count() or 1),
        )
        metadatas = results.get("metadatas", [[]])[0]
        return list(metadatas)

    def get_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        result = self._collection.get(ids=[record_id])
        metas = result.get("metadatas", [])
        return metas[0] if metas else None

    def get_price_comps(
        self, device_model: str, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        query_text = f"Device: {device_model}."
        results = self._collection.query(
            query_texts=[query_text],
            n_results=min(top_k, self._collection.count() or 1),
        )
        return results.get("metadatas", [[]])[0]


# ── Pinecone Backend ──────────────────────────────────────────────────────────

class PineconeMemory(LongTermMemoryBase):
    """
    Pinecone-backed long-term memory (managed vector store).
    Uses Google Generative AI embeddings for vectorisation.
    """

    def __init__(self, api_key: str, index_name: str) -> None:
        try:
            from pinecone import Pinecone, ServerlessSpec
            import google.generativeai as genai

            self._pc = Pinecone(api_key=api_key)
            existing = [i.name for i in self._pc.list_indexes()]
            if index_name not in existing:
                self._pc.create_index(
                    name=index_name,
                    dimension=768,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
            self._index = self._pc.Index(index_name)
            self._genai = genai
            logger.info(f"[LTM:Pinecone] Connected to index '{index_name}'")
        except ImportError:
            raise ImportError(
                "pinecone-client is not installed. Run: pip install pinecone-client"
            )

    def _embed(self, text: str) -> List[float]:
        result = self._genai.embed_content(
            model="models/text-embedding-004", content=text
        )
        return result["embedding"]

    def store(self, record: Dict[str, Any]) -> str:
        record_id = record.get("record_id") or str(uuid.uuid4())
        record["record_id"] = record_id
        document = (
            f"Device: {record.get('brand', '')} {record.get('model_name', '')}. "
            f"Condition: {record.get('condition_grade', '')}."
        )
        vector = self._embed(document)
        self._index.upsert(
            vectors=[{"id": record_id, "values": vector, "metadata": {k: str(v) for k, v in record.items()}}]
        )
        logger.debug(f"[LTM:Pinecone] Stored record {record_id}")
        return record_id

    def query_similar(
        self, device_model: str, condition_grade: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        query_text = f"Device: {device_model}. Condition: {condition_grade}."
        vector = self._embed(query_text)
        results = self._index.query(vector=vector, top_k=top_k, include_metadata=True)
        return [match["metadata"] for match in results.get("matches", [])]

    def get_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        result = self._index.fetch(ids=[record_id])
        vectors = result.get("vectors", {})
        if record_id in vectors:
            return vectors[record_id].get("metadata")
        return None

    def get_price_comps(self, device_model: str, top_k: int = 10) -> List[Dict[str, Any]]:
        query_text = f"Device: {device_model}."
        vector = self._embed(query_text)
        results = self._index.query(vector=vector, top_k=top_k, include_metadata=True)
        return [match["metadata"] for match in results.get("matches", [])]


# ── Factory ───────────────────────────────────────────────────────────────────

def create_long_term_memory(
    backend: str = "chromadb",
    chromadb_path: str = "./chroma_db",
    pinecone_api_key: Optional[str] = None,
    pinecone_index_name: str = "refurb-agent-memory",
) -> LongTermMemoryBase:
    """Factory function — creates the appropriate backend from config."""
    if backend == "chromadb":
        return ChromaDBMemory(persist_path=chromadb_path)
    elif backend == "pinecone":
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY is required when memory_backend=pinecone")
        return PineconeMemory(api_key=pinecone_api_key, index_name=pinecone_index_name)
    else:
        raise ValueError(f"Unknown memory backend: {backend}")
