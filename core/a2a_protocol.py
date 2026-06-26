import json
from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, Field, field_validator

class AgentMessage(BaseModel):
    """
    Standardized A2A (Agent-to-Agent) message schema.
    Ensure structured communication between all agents in the workspace.
    """
    sender: str = Field(..., description="The name/identifier of the sending agent")
    receiver: str = Field(..., description="The name/identifier of the receiving agent")
    task: str = Field(..., description="The action or purpose of the message")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Custom payload contents")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z", 
        description="ISO 8601 UTC timestamp of message generation"
    )

    @field_validator("sender", "receiver", "task")
    @classmethod
    def cannot_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return value.strip()

    def to_json(self) -> str:
        """Serialize the message to a formatted JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "AgentMessage":
        """Deserialize a JSON string into an AgentMessage instance."""
        return cls.model_validate_json(json_str)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to a dictionary."""
        return self.model_dump()

def create_message(sender: str, receiver: str, task: str, payload: Dict[str, Any]) -> AgentMessage:
    """Helper function to create a new AgentMessage with an auto-populated timestamp."""
    return AgentMessage(
        sender=sender,
        receiver=receiver,
        task=task,
        payload=payload
    )
