"""
protocol/message.py
────────────────────
Core A2A message types and the AgentMessage dataclass.
Every inter-agent communication uses this contract.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


# ── Message Type Enum ─────────────────────────────────────────────────────────

class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    BROADCAST = "broadcast"


# ── Priority Enum ─────────────────────────────────────────────────────────────

class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ── AgentMessage ──────────────────────────────────────────────────────────────

@dataclass
class AgentMessage:
    """
    The universal envelope for all agent-to-agent communication.

    Attributes
    ----------
    id              : Unique message identifier (UUID4).
    sender          : Name of the sending agent.
    recipient       : Name of the target agent, or "broadcast" for all.
    message_type    : REQUEST | RESPONSE | ERROR | BROADCAST.
    payload         : Arbitrary typed payload (use schemas.py for structure).
    timestamp       : UTC datetime of creation.
    correlation_id  : Links a response back to its originating request.
    session_id      : Identifies the user analysis session.
    priority        : Message processing priority.
    metadata        : Extra trace/context data (trace_id, step_index, etc.).
    error           : Populated only when message_type == ERROR.
    """

    sender: str
    recipient: str
    message_type: MessageType
    payload: Dict[str, Any]

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = field(default=None)
    session_id: Optional[str] = field(default=None)
    priority: Priority = field(default=Priority.NORMAL)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = field(default=None)

    # ── Factory helpers ───────────────────────────────────────────────────────

    @classmethod
    def request(
        cls,
        sender: str,
        recipient: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        **metadata,
    ) -> "AgentMessage":
        return cls(
            sender=sender,
            recipient=recipient,
            message_type=MessageType.REQUEST,
            payload=payload,
            session_id=session_id,
            metadata=metadata,
        )

    @classmethod
    def respond(
        cls,
        original: "AgentMessage",
        sender: str,
        payload: Dict[str, Any],
    ) -> "AgentMessage":
        return cls(
            sender=sender,
            recipient=original.sender,
            message_type=MessageType.RESPONSE,
            payload=payload,
            correlation_id=original.id,
            session_id=original.session_id,
            metadata={"in_reply_to": original.id},
        )

    @classmethod
    def error_response(
        cls,
        original: "AgentMessage",
        sender: str,
        error: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> "AgentMessage":
        return cls(
            sender=sender,
            recipient=original.sender,
            message_type=MessageType.ERROR,
            payload=payload or {},
            correlation_id=original.id,
            session_id=original.session_id,
            error=error,
            metadata={"in_reply_to": original.id},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "priority": self.priority.value,
            "metadata": self.metadata,
            "error": self.error,
        }
