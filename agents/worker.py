import json
from typing import Any, Dict
from core.a2a_protocol import AgentMessage, create_message
from core.context_engineering import ContextEngineer
from core.observability import trace_execution_time, observer
from tools.tools import ocr_tool, product_specs_tool, estimate_repair_tool, pricing_tool

class VisionAgent:
    """
    Vision Agent identifies the device type, brand, and model from physical visual context.
    Strictly uses the OCR MCP Server tool via the MCP Client.
    """
    def __init__(self):
        self.name = "vision_agent"

    @trace_execution_time("VisionAgent", "identify_device")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        payload = message.payload
        image_path = payload.get("image_path", "")
        estimated_model = payload.get("estimated_model", "generic")

        # Apply Context Engineering
        context = ContextEngineer.get_vision_context(image_path)
        img_path = context["image_path"]

        if not img_path:
            # If no image uploaded, default to planner's estimated model
            observer.log_agent_execution(self.name, "NO_IMAGE", "No image provided. Using estimated model.")
            return create_message(
                sender=self.name,
                receiver=message.sender,
                task="vision_response",
                payload={"verified_model": estimated_model, "ocr_text": "No image uploaded.", "brand": "Generic"}
            )

        # Call OCR server via MCP tool
        ocr_result = ocr_tool(img_path)

        # Match device brand/model from OCR text
        ocr_lower = ocr_result.lower()
        verified_model = estimated_model
        brand = "Generic"

        if "iphone" in ocr_lower or "apple" in ocr_lower:
            brand = "Apple"
            if "13" in ocr_lower:
                verified_model = "iphone 13"
            elif "14" in ocr_lower:
                verified_model = "iphone 14"
            elif "macbook" in ocr_lower:
                verified_model = "macbook pro m1 2020"
            elif "ipad" in ocr_lower:
                verified_model = "ipad pro 11 2021"
        elif "samsung" in ocr_lower or "galaxy" in ocr_lower:
            brand = "Samsung"
            if "s22" in ocr_lower:
                verified_model = "galaxy s22"

        observer.log_agent_execution(self.name, "IDENTIFICATION_SUCCESS", f"Identified as: {brand} {verified_model}")

        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="vision_response",
            payload={
                "verified_model": verified_model,
                "brand": brand,
                "ocr_text": ocr_result
            }
        )

class ProductIntelligenceAgent:
    """
    ProductIntelligenceAgent retrieves tech specifications and product metadata.
    Uses the Product Information MCP Server tool via the MCP Client.
    """
    def __init__(self):
        self.name = "product_agent"

    @trace_execution_time("ProductIntelligenceAgent", "retrieve_specs")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        payload = message.payload
        model = payload.get("model", "generic")
        brand = payload.get("brand", "Generic")

        # Apply Context Engineering
        context = ContextEngineer.get_product_context(brand, model)
        query_model = context["model"]

        # Call Product specs tool
        specs_json = product_specs_tool(query_model)
        
        try:
            specs_dict = json.loads(specs_json)
        except Exception:
            specs_dict = {"model": query_model, "specs": {}}

        observer.log_agent_execution(self.name, "SPECS_RETRIEVED", f"Metadata loaded for {query_model}")

        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="product_response",
            payload={
                "specs_raw": specs_json,
                "specs_dict": specs_dict
            }
        )

class RefurbishmentAgent:
    """
    RefurbishmentAgent identifies repair requirements and estimates repair costs.
    Uses the Repair Knowledge MCP Server tool via the MCP Client.
    """
    def __init__(self):
        self.name = "refurbishment_agent"

    @trace_execution_time("RefurbishmentAgent", "estimate_repairs")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        payload = message.payload
        model = payload.get("model", "generic")
        brand = payload.get("brand", "Generic")
        specs = payload.get("specs", {})
        issues = payload.get("issues", "none")

        # Apply Context Engineering
        context = ContextEngineer.get_refurbishment_context(brand, model, specs, issues)
        query_model = context["model"]
        query_issues = context["reported_issues"]

        # Call Repair costs estimator tool
        repair_json = estimate_repair_tool(query_model, query_issues)
        
        try:
            repair_dict = json.loads(repair_json)
        except Exception:
            repair_dict = {"repairs": [], "total_repair_cost": 0.0}

        observer.log_agent_execution(self.name, "REPAIRS_ESTIMATED", f"Cost: ${repair_dict.get('total_repair_cost', 0.0):.2f}")

        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="refurbishment_response",
            payload={
                "repair_raw": repair_json,
                "repair_dict": repair_dict,
                "total_repair_cost": repair_dict.get("total_repair_cost", 0.0)
            }
        )

class ResaleAgent:
    """
    ResaleAgent calculates target resale condition price guidelines,
    expected acquisition costs, net margins, and return on investment (ROI).
    Uses the Pricing & Resale MCP Server tool via the MCP Client.
    """
    def __init__(self):
        self.name = "resale_agent"

    @trace_execution_time("ResaleAgent", "calculate_economics")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        payload = message.payload
        model = payload.get("model", "generic")
        brand = payload.get("brand", "Generic")
        target_condition = payload.get("target_condition", "Good")
        total_repair_cost = payload.get("total_repair_cost", 0.0)

        # Apply Context Engineering
        context = ContextEngineer.get_resale_context(brand, model, target_condition, total_repair_cost)
        query_model = context["model"]
        query_cond = context["target_condition"]
        query_cost = context["total_repair_cost"]

        # Call Pricing tool
        pricing_json = pricing_tool(query_model, query_cond, query_cost)
        
        try:
            pricing_dict = json.loads(pricing_json)
        except Exception:
            pricing_dict = {"market_resale_value": 0.0, "net_profit": 0.0, "profit_margin_percentage": 0.0}

        observer.log_agent_execution(
            self.name, 
            "ECONOMICS_CALCULATED", 
            f"Resale Value: ${pricing_dict.get('market_resale_value', 0.0):.2f} | Margin: {pricing_dict.get('profit_margin_percentage', 0.0)}%"
        )

        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="resale_response",
            payload={
                "pricing_raw": pricing_json,
                "pricing_dict": pricing_dict
            }
        )
