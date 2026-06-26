import importlib.util
import os
import sys
from typing import Any, Dict

# Programmatically load local mcp/client.py to bypass shadowing from the global 'mcp' package
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
client_path = os.path.join(project_dir, "mcp", "client.py")

spec = importlib.util.spec_from_file_location("local_mcp_client", client_path)
mcp_client_module = importlib.util.module_from_spec(spec)
sys.modules["local_mcp_client"] = mcp_client_module
spec.loader.exec_module(mcp_client_module)

LocalMCPClient = mcp_client_module.LocalMCPClient

# Instantiate a single global MCP client for the application.
# Set mode="direct" for high speed. Can also be set to "subprocess" for standard CLI subprocess communication.
mcp_client = LocalMCPClient(mode="direct")

def ocr_tool(image_path: str) -> str:
    """Wrapper that calls the OCR MCP Server via the MCP Client."""
    result = mcp_client.call_tool(
        server_name="ocr_server",
        tool_name="extract_text_from_image",
        arguments={"image_path": image_path}
    )
    if result.get("success"):
        return result["result"]
    else:
        return f"Error executing OCR: {result.get('error')}"

def product_specs_tool(model_query: str) -> str:
    """Wrapper that calls the Product Information MCP Server via the MCP Client."""
    result = mcp_client.call_tool(
        server_name="product_server",
        tool_name="get_product_specs",
        arguments={"model_query": model_query}
    )
    if result.get("success"):
        return result["result"]
    else:
        return f"Error executing Product Specs lookup: {result.get('error')}"

def estimate_repair_tool(model_name: str, issues_list: str) -> str:
    """Wrapper that calls the Repair Knowledge MCP Server via the MCP Client."""
    result = mcp_client.call_tool(
        server_name="repair_server",
        tool_name="estimate_repair_costs",
        arguments={"model_name": model_name, "issues_list": issues_list}
    )
    if result.get("success"):
        return result["result"]
    else:
        return f"Error estimating repair costs: {result.get('error')}"

def pricing_tool(model_name: str, target_condition: str, total_repair_cost: float) -> str:
    """Wrapper that calls the Pricing & Resale MCP Server via the MCP Client."""
    result = mcp_client.call_tool(
        server_name="pricing_server",
        tool_name="calculate_market_resale",
        arguments={
            "model_name": model_name,
            "target_condition": target_condition,
            "total_repair_cost": total_repair_cost
        }
    )
    if result.get("success"):
        return result["result"]
    else:
        return f"Error calculating pricing: {result.get('error')}"

def listing_tool(
    model_name: str,
    condition: str,
    specs_json: str,
    repair_json: str,
    pricing_json: str,
    session_id: str
) -> str:
    """Wrapper that calls the Listing Generator MCP Server via the MCP Client."""
    result = mcp_client.call_tool(
        server_name="listing_server",
        tool_name="generate_marketplace_listing",
        arguments={
            "model_name": model_name,
            "condition": condition,
            "specs_json": specs_json,
            "repair_json": repair_json,
            "pricing_json": pricing_json,
            "session_id": session_id
        }
    )
    if result.get("success"):
        return result["result"]
    else:
        return f"Error generating marketplace listing: {result.get('error')}"
