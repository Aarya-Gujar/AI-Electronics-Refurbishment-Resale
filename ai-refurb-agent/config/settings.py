"""
config/settings.py
──────────────────
Centralised configuration via Pydantic BaseSettings.
All values are loaded from environment variables or a .env file.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Enumerations ─────────────────────────────────────────────────────────────

class MCPMode(str, Enum):
    STDIO = "stdio"          # Spawn MCP servers as subprocesses (local dev)
    IN_PROCESS = "in_process"  # Run MCP tools as direct async calls (HF deploy)


class MemoryBackend(str, Enum):
    CHROMADB = "chromadb"
    PINECONE = "pinecone"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ── Settings ─────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model for text tasks (flash = faster/cheaper)",
    )
    gemini_vision_model: str = Field(
        default="gemini-1.5-pro",
        description="Gemini model for vision/multimodal tasks",
    )

    # ── MCP ──────────────────────────────────────────────────────────────────
    mcp_mode: MCPMode = Field(
        default=MCPMode.IN_PROCESS,
        description="How MCP servers are executed",
    )

    # ── Memory ───────────────────────────────────────────────────────────────
    memory_backend: MemoryBackend = Field(
        default=MemoryBackend.CHROMADB,
        description="Vector store backend for long-term memory",
    )
    chromadb_persist_path: str = Field(
        default="./chroma_db",
        description="Local path for ChromaDB persistence",
    )
    pinecone_api_key: Optional[str] = Field(
        default=None,
        description="Pinecone API key (required if memory_backend=pinecone)",
    )
    pinecone_index_name: str = Field(
        default="refurb-agent-memory",
        description="Pinecone index name",
    )
    session_ttl_seconds: int = Field(
        default=3600,
        description="Session memory TTL in seconds",
    )

    # ── Observability ─────────────────────────────────────────────────────────
    log_level: LogLevel = Field(default=LogLevel.INFO)
    log_file: str = Field(
        default="logs/refurb_agent.log",
        description="Path for structured log file",
    )
    enable_tracing: bool = Field(default=True)
    trace_output_dir: str = Field(default="traces/")

    # ── Data Paths ────────────────────────────────────────────────────────────
    data_dir: Path = Field(default=Path("data"))

    # ── Agent Config ──────────────────────────────────────────────────────────
    agent_timeout_seconds: int = Field(
        default=120,
        description="Max seconds an agent step may take before timing out",
    )
    max_retries: int = Field(
        default=3,
        description="Max retries for LLM calls and MCP tool calls",
    )
    evaluator_min_score: float = Field(
        default=6.0,
        description="Minimum evaluation score (0-10) to accept a report",
    )

    # ── UI ────────────────────────────────────────────────────────────────────
    gradio_server_port: int = Field(default=7860)
    gradio_server_name: str = Field(default="0.0.0.0")
    gradio_share: bool = Field(default=False)

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("pinecone_api_key")
    @classmethod
    def check_pinecone_key(cls, v: Optional[str], info) -> Optional[str]:
        # Defer check to runtime; warn rather than raise at import time
        return v


# ── Singleton ─────────────────────────────────────────────────────────────────
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
