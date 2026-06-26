import os
import sys

# Unshadow global mcp package from the local mcp directory namespace
local_mcp_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(local_mcp_path)
removed_paths = []
for p in list(sys.path):
    if p in (project_root, local_mcp_path, "") or os.path.abspath(p) in (project_root, local_mcp_path):
        sys.path.remove(p)
        removed_paths.append(p)

from mcp.server.fastmcp import FastMCP

# Restore path for other imports
for p in reversed(removed_paths):
    sys.path.insert(0, p)

import json
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("PricingServer")

mcp = FastMCP("Pricing & Resale Server")

PRICES_PATH = "data/resale_prices.json"

def _load_resale_prices():
    if os.path.exists(PRICES_PATH):
        with open(PRICES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@mcp.tool()
def calculate_market_resale(model_name: str, target_condition: str, total_repair_cost: float) -> str:
    """
    Retrieve baseline market value for a model in a specific target condition,
    and calculate estimated resale price, net margins, and ROI based on repair costs.
    target_condition should be one of: 'Excellent', 'Good', 'Fair'.
    """
    logger.info(f"Calculating resale economics for {model_name} in {target_condition} condition (repairs: ${total_repair_cost})")
    prices_db = _load_resale_prices()
    
    # Match the model
    model_key = "default"
    cleaned_model = model_name.lower().strip()
    for key in prices_db.keys():
        if key in cleaned_model or cleaned_model in key:
            model_key = key
            break
            
    condition_prices = prices_db.get(model_key, prices_db.get("default", {}))
    
    # Standardize condition capitalization
    cond = target_condition.strip().capitalize()
    if cond not in ["Excellent", "Good", "Fair"]:
        cond = "Good" # default fallback
        
    market_value = condition_prices.get(cond, condition_prices.get("Good", 150.00))
    
    # Let's say our acquisition cost is standard, or we estimate acquisition cost as 30% of market resale value
    estimated_acquisition_cost = round(market_value * 0.35, 2)
    
    # Economics calculation
    total_investment = estimated_acquisition_cost + total_repair_cost
    net_profit = market_value - total_investment
    profit_margin_pct = (net_profit / market_value) * 100 if market_value > 0 else 0.0
    roi_pct = (net_profit / total_investment) * 100 if total_investment > 0 else 0.0
    
    analysis = {
        "model_name": model_name,
        "matched_model_key": model_key,
        "target_condition": cond,
        "market_resale_value": market_value,
        "estimated_acquisition_cost": estimated_acquisition_cost,
        "repair_cost": total_repair_cost,
        "total_investment": total_investment,
        "net_profit": round(net_profit, 2),
        "profit_margin_percentage": round(profit_margin_pct, 2),
        "roi_percentage": round(roi_pct, 2),
        "currency": "USD"
    }
    
    return json.dumps(analysis, indent=2)

if __name__ == "__main__":
    mcp.run()
