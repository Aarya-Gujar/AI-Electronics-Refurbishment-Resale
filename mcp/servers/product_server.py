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
logger = logging.getLogger("ProductServer")

mcp = FastMCP("Product Information Server")

CATALOG_PATH = "data/product_catalog.json"

def _load_catalog():
    if os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@mcp.tool()
def get_product_specs(model_query: str) -> str:
    """
    Retrieve specifications, release year, processor, RAM/storage options, 
    and display details for a given device model query.
    """
    logger.info(f"Querying product specifications for: '{model_query}'")
    catalog = _load_catalog()
    
    query = model_query.lower().strip()
    
    # Try direct or substring matching
    for key, data in catalog.items():
        if key in query or query in key:
            return json.dumps(data, indent=2)
            
    # Default fallback if not found in catalog
    fallback_data = {
        "brand": "Generic/Unknown",
        "model": model_query,
        "release_year": 2020,
        "specs": {
            "screen_size": "Unknown",
            "display": "Standard LCD",
            "processor": "Generic Processor",
            "storage_options": ["128GB"],
            "battery": "Standard Battery"
        },
        "note": "Specifications estimated based on generic device defaults"
    }
    return json.dumps(fallback_data, indent=2)

if __name__ == "__main__":
    mcp.run()
