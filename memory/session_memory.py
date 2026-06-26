import os
import json
from typing import Any, Dict, List
from core.a2a_protocol import AgentMessage

class SessionMemory:
    """
    Session Memory persists the state of the active workflow evaluation.
    This includes the current device metadata, historical agent messages for this session,
    the active plan steps, and intermediate evaluation outputs.
    """
    def __init__(self, storage_path: str = "data/session_memory.json"):
        self.storage_path = storage_path
        self.data: Dict[str, Any] = {
            "session_id": "",
            "current_device": {},
            "current_analysis": {},
            "current_workflow_state": "idle",
            "plan": [],
            "messages": []
        }
        self._ensure_storage_exists()
        self.load()

    def _ensure_storage_exists(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def save(self):
        """Save the current session memory state to JSON."""
        self._ensure_storage_exists()
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def load(self):
        """Load session memory from the local JSON file if it exists."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        self.data = json.loads(content)
            except Exception:
                # Fall back to default empty state if file is corrupted
                self.clear()

    def clear(self):
        """Reset the session memory to an empty state."""
        self.data = {
            "session_id": "",
            "current_device": {},
            "current_analysis": {},
            "current_workflow_state": "idle",
            "plan": [],
            "messages": []
        }
        self.save()

    def set_session_id(self, session_id: str):
        self.data["session_id"] = session_id
        self.save()

    def set_workflow_state(self, state: str):
        self.data["current_workflow_state"] = state
        self.save()

    def set_device_info(self, key: str, value: Any):
        self.data["current_device"][key] = value
        self.save()

    def update_analysis(self, agent_name: str, analysis_data: Dict[str, Any]):
        self.data["current_analysis"][agent_name] = analysis_data
        self.save()

    def set_plan(self, plan_steps: List[Dict[str, Any]]):
        self.data["plan"] = plan_steps
        self.save()

    def add_message(self, message: AgentMessage):
        """Record an A2A message in the session log."""
        self.data["messages"].append(message.to_dict())
        self.save()

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.data["messages"]

    def get_data(self) -> Dict[str, Any]:
        return self.data
