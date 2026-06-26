import os
import time
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

class ObservabilityManager:
    """
    Centralized structured logging for tracing agent executions,
    MCP requests, tool invocations, validation failures, and elapsed latency.
    """
    def __init__(self, log_dir: str = "data/logs", log_file: str = "system.log"):
        self.log_dir = log_dir
        self.log_path = os.path.join(self.log_dir, log_file)
        self._ensure_log_dir()
        
        # Configure logging
        self.logger = logging.getLogger("ElectronicsRefurbResale")
        self.logger.setLevel(logging.INFO)
        
        # Prevent adding handlers multiple times in singletons
        if not self.logger.handlers:
            # File handler
            file_handler = logging.FileHandler(self.log_path, encoding="utf-8")
            file_formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

    def _ensure_log_dir(self):
        os.makedirs(self.log_dir, exist_ok=True)

    def log_agent_execution(self, agent_name: str, status: str, details: str, elapsed_time: Optional[float] = None):
        """Log agent lifecycle events and execution times."""
        timing_str = f" in {elapsed_time:.3f}s" if elapsed_time is not None else ""
        self.logger.info(f"[{agent_name}] Status: {status} | {details}{timing_str}")

    def log_mcp_request(self, server_name: str, tool_name: str, payload: Dict[str, Any], status: str, elapsed_time: float):
        """Log MCP requests and their response times."""
        self.logger.info(
            f"[MCP Client] Called {server_name}.{tool_name} | Status: {status} | "
            f"Latency: {elapsed_time:.3f}s | Payload: {payload}"
        )

    def log_validation_failure(self, validator_name: str, target: str, reason: str):
        """Log verification and evaluator check failures."""
        self.logger.warning(f"[{validator_name}] Validation Failed for [{target}] | Reason: {reason}")

    def log_error(self, component: str, error_msg: str, exception: Optional[Exception] = None):
        """Log errors and details of failures."""
        exc_info = True if exception else False
        self.logger.error(f"[{component}] Error: {error_msg}", exc_info=exc_info)

    def get_logs(self, limit: int = 100) -> str:
        """Fetch the last N lines of the log file for display in the dashboard."""
        if not os.path.exists(self.log_path):
            return "No logs found."
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return "".join(lines[-limit:])
        except Exception as e:
            return f"Failed to retrieve logs: {str(e)}"

# Global observer instance
observer = ObservabilityManager()

def trace_execution_time(component_name: str, action_name: str):
    """Decorator to measure and log execution times of agent/tool calls."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            observer.log_agent_execution(component_name, "STARTED", f"Action: {action_name}")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                observer.log_agent_execution(component_name, "COMPLETED", f"Action: {action_name} | Success", elapsed)
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                observer.log_error(component_name, f"Action: {action_name} failed: {str(e)}")
                observer.log_agent_execution(component_name, "FAILED", f"Action: {action_name} | Error: {str(e)}", elapsed)
                raise e
        return wrapper
    return decorator
