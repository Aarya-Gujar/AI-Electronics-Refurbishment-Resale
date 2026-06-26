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
from typing import List

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("RepairServer")

mcp = FastMCP("Repair Knowledge Server")

REPAIR_COSTS_PATH = "data/repair_costs.json"

def _load_repair_costs():
    if os.path.exists(REPAIR_COSTS_PATH):
        with open(REPAIR_COSTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@mcp.tool()
def estimate_repair_costs(model_name: str, issues_list: str) -> str:
    """
    Estimate refurbishment recommendations and costs for specific issues on a given model.
    issues_list should be a comma-separated list of issues (e.g., 'screen_replacement, battery_replacement').
    """
    logger.info(f"Estimating repair costs for {model_name} with issues: {issues_list}")
    costs_db = _load_repair_costs()
    
    # Match the model in our database
    model_key = "default"
    cleaned_model = model_name.lower().strip()
    for key in costs_db.keys():
        if key in cleaned_model or cleaned_model in key:
            model_key = key
            break
            
    model_costs = costs_db.get(model_key, costs_db.get("default", {}))
    
    # Parse the issues
    issues = [iss.strip().lower() for iss in issues_list.split(",") if iss.strip()]
    
    breakdown = []
    total_cost = 0.0
    
    for issue in issues:
        # Standardize issue keys
        issue_key = issue.replace(" ", "_")
        
        # Try exact lookup, or substring search in keys
        matched_key = None
        for key in model_costs.keys():
            if key in issue_key or issue_key in key:
                matched_key = key
                break
                
        if matched_key:
            cost = model_costs[matched_key]
            breakdown.append({
                "issue": issue,
                "action": f"Perform {matched_key.replace('_', ' ')}",
                "cost": cost
            })
            total_cost += cost
        else:
            # Fallback for unknown issue
            fallback_cost = model_costs.get("battery_replacement", 50.00) # use battery as average benchmark
            breakdown.append({
                "issue": issue,
                "action": f"Repair/Inspect {issue}",
                "cost": fallback_cost
            })
            total_cost += fallback_cost
            
    response = {
        "device": model_name,
        "matched_model_key": model_key,
        "repairs": breakdown,
        "total_repair_cost": total_cost,
        "currency": "USD"
    }
    
    return json.dumps(response, indent=2)

if __name__ == "__main__":
    mcp.run()
