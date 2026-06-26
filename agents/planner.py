import time
from typing import Dict, Any, List
from core.a2a_protocol import AgentMessage, create_message
from core.context_engineering import ContextEngineer
from core.observability import observer, trace_execution_time

class PlannerAgent:
    """
    Planner Agent parses the user request, extracts device properties,
    and constructs a structured task sequence (execution plan) for worker agents.
    """
    def __init__(self):
        self.name = "planner_agent"

    @trace_execution_time("PlannerAgent", "create_plan")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        """
        Processes a user request to generate an execution plan.
        Expects payload containing "user_request" and optional "image_path".
        """
        payload = message.payload
        user_request = payload.get("user_request", "")
        image_path = payload.get("image_path", "")
        
        # Apply Context Engineering
        context = ContextEngineer.get_planner_context(user_request)
        req = context["user_request"]

        # Parse request details using simple but robust parsing
        req_lower = req.lower()
        
        # 1. Determine Device Model
        model = "generic"
        for potential_model in ["iphone 13", "iphone 14", "macbook pro m1 2020", "ipad pro 11 2021", "galaxy s22"]:
            if potential_model in req_lower:
                model = potential_model
                break
        
        # 2. Determine Condition
        condition = "Good"
        if "excellent" in req_lower:
            condition = "Excellent"
        elif "fair" in req_lower:
            condition = "Fair"

        # 3. Determine Issues
        issues = []
        possible_issues = [
            "screen_replacement", "battery_replacement", "charging_port_repair", 
            "camera_repair", "back_glass_replacement", "logic_board_repair",
            "keyboard_replacement", "trackpad_replacement"
        ]
        for issue in possible_issues:
            # Check for issue keywords in request (replacing underscore with space for search)
            if issue.replace("_", " ") in req_lower or issue in req_lower:
                issues.append(issue)
        
        # If no issues parsed, default to battery_replacement or screen_replacement based on text hints,
        # or leave empty if the device is pristine.
        if not issues:
            if "screen" in req_lower:
                issues.append("screen_replacement")
            if "battery" in req_lower:
                issues.append("battery_replacement")
            if "port" in req_lower:
                issues.append("charging_port_repair")
            if "board" in req_lower:
                issues.append("logic_board_repair")
            if "keyboard" in req_lower:
                issues.append("keyboard_replacement")
            if not issues and "repair" in req_lower:
                issues.append("battery_replacement") # standard safe default

        issues_str = ",".join(issues) if issues else "none"

        # Construct task plan
        plan_steps = [
            {
                "step": 1,
                "agent": "vision_agent",
                "task": "identify_device",
                "description": "Analyze image and run OCR to verify device identity.",
                "payload": {"image_path": image_path, "estimated_model": model}
            },
            {
                "step": 2,
                "agent": "product_agent",
                "task": "retrieve_specs",
                "description": "Fetch official product specifications and metadata from catalog.",
                "payload": {"model": model} # Will be refined by vision agent outputs
            },
            {
                "step": 3,
                "agent": "refurbishment_agent",
                "task": "estimate_repairs",
                "description": "Evaluate required repairs and calculate estimated costs.",
                "payload": {"model": model, "issues": issues_str}
            },
            {
                "step": 4,
                "agent": "resale_agent",
                "task": "calculate_economics",
                "description": "Compute resale valuation, target pricing, net profit, and ROI.",
                "payload": {"model": model, "target_condition": condition, "total_repair_cost": 0.0} # Cost populated dynamically
            },
            {
                "step": 5,
                "agent": "evaluator_agent",
                "task": "validate_outputs",
                "description": "Audit all worker outputs for consistency, completeness, and positive margins.",
                "payload": {}
            }
        ]

        observer.log_agent_execution(self.name, "PLAN_CREATED", f"Generated {len(plan_steps)} plan steps for {model}")

        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="planner_response",
            payload={
                "parsed_model": model,
                "parsed_condition": condition,
                "parsed_issues": issues,
                "plan_steps": plan_steps
            }
        )
