import time
from typing import Dict, Any
from core.a2a_protocol import AgentMessage, create_message
from core.context_engineering import ContextEngineer
from core.observability import observer, trace_execution_time

class SecurityAgent:
    """
    Security Agent validates incoming user request text and uploaded file metadata.
    Enforces maximum file sizes, permitted file types, and blocks prompt injection attempts.
    """
    def __init__(self, max_file_size_mb: float = 5.0):
        self.name = "security_agent"
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.allowed_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        self.injection_triggers = [
            "ignore previous instructions",
            "system prompt overrides",
            "you are now an administrator",
            "ignore safety guidelines",
            "override current plan",
            "bypass system limitations",
            "disregard safety instructions"
        ]

    @trace_execution_time("SecurityAgent", "validate_request")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        """
        Process security checks on incoming messages.
        Expects payload containing "user_input" and "file_metadata".
        """
        payload = message.payload
        user_input = payload.get("user_input", "")
        file_metadata = payload.get("file_metadata", {})
        
        # Apply Context Engineering
        context = ContextEngineer.get_security_context(user_input, file_metadata)
        
        sanitized_input = context["user_input"]
        filename = context["file_metadata"]["filename"]
        filesize = context["file_metadata"]["filesize"]
        
        # 1. Validate File Size
        if filesize > self.max_file_size:
            reason = f"File size ({filesize / 1024 / 1024:.2f} MB) exceeds maximum permitted limit of {self.max_file_size / 1024 / 1024} MB."
            observer.log_validation_failure(self.name, "File Upload", reason)
            return create_message(
                sender=self.name,
                receiver=message.sender,
                task="security_response",
                payload={"is_safe": False, "reason": reason}
            )
            
        # 2. Validate File Extension
        if filename:
            ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
            if ext not in self.allowed_extensions:
                reason = f"File extension '{ext}' is not allowed. Supported formats: {', '.join(self.allowed_extensions)}"
                observer.log_validation_failure(self.name, "File Upload", reason)
                return create_message(
                    sender=self.name,
                    receiver=message.sender,
                    task="security_response",
                    payload={"is_safe": False, "reason": reason}
                )

        # 3. Detect Prompt Injection Attempts
        input_lower = sanitized_input.lower()
        for trigger in self.injection_triggers:
            if trigger in input_lower:
                reason = f"Potential prompt injection detected. Blocked input matching: '{trigger}'"
                observer.log_validation_failure(self.name, "User Query Safety", reason)
                return create_message(
                    sender=self.name,
                    receiver=message.sender,
                    task="security_response",
                    payload={"is_safe": False, "reason": reason}
                )

        # All checks passed
        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="security_response",
            payload={
                "is_safe": True,
                "reason": "Request successfully passed all security, size, and prompt safety audits."
            }
        )
