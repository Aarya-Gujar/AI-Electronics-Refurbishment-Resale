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
from datetime import datetime

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("ListingServer")

mcp = FastMCP("Listing Generator Server")

@mcp.tool()
def generate_marketplace_listing(
    model_name: str,
    condition: str,
    specs_json: str,
    repair_json: str,
    pricing_json: str,
    session_id: str = "default_session"
) -> str:
    """
    Generate professional marketplace listing copies (formatted in Markdown/HTML) 
    and save a detailed refurbishment report under the reports/ directory.
    """
    logger.info(f"Generating listing for {model_name} (session: {session_id})")
    
    # Safely parse JSON inputs
    try:
        specs = json.loads(specs_json)
    except Exception:
        specs = {"specs": {}, "brand": "Unknown", "model": model_name}
        
    try:
        repairs = json.loads(repair_json)
    except Exception:
        repairs = {"repairs": [], "total_repair_cost": 0.0}
        
    try:
        pricing = json.loads(pricing_json)
    except Exception:
        pricing = {"market_resale_value": 0.0, "net_profit": 0.0, "profit_margin_percentage": 0.0}

    # Format specs
    specs_details = specs.get("specs", {})
    specs_md = "\n".join([f"- **{k.replace('_', ' ').title()}**: {v}" for k, v in specs_details.items()])
    if not specs_md:
        specs_md = "- Specs: Details not available"
        
    # Format repairs
    repairs_list = repairs.get("repairs", [])
    if repairs_list:
        repairs_md = "\n".join([f"- {r.get('action', '')} (Estimated Cost: ${r.get('cost', 0.0):.2f})" for r in repairs_list])
    else:
        repairs_md = "- None (Fully Functional)"

    # Format marketplace text
    ebay_template = f"""# Professional Refurbished {specs.get('brand', 'Generic')} {specs.get('model', model_name)}

## Device Specifications
{specs_md}

## Condition & Refurbishment Details
- **Resale Grade Condition**: {condition}
- **Refurbishment Process Completed**:
{repairs_md}
- **Testing Status**: Passed rigorous quality validation. Fully functional.

## Pricing & Shipping
- **Price**: ${pricing.get('market_resale_value', 0.0):.2f} (Firm)
- **Fast Shipping**: Shipped secure within 24 hours.

*Perfect working order. Buy with confidence!*
"""

    report_template = f"""# AI Refurbishment & Resale Report
**Session ID**: {session_id}
**Report Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

---

## 1. Device Profile
- **Brand**: {specs.get('brand', 'Unknown')}
- **Model**: {specs.get('model', model_name)}
- **Release Year**: {specs.get('release_year', 'Unknown')}
- **Hardware Specs**:
{specs_md}

## 2. Refurbishment Diagnostics
- **Target Condition**: {condition}
- **Required Repairs & Estimated Costs**:
{repairs_md}
- **Total Refurbishment Budget**: ${repairs.get('total_repair_cost', 0.0):.2f}

## 3. Financial Analysis
- **Estimated Acquisition Cost**: ${pricing.get('estimated_acquisition_cost', 0.0):.2f}
- **Refurbishment Cost**: ${pricing.get('repair_cost', 0.0):.2f}
- **Total Investment**: ${pricing.get('total_investment', 0.0):.2f}
- **Estimated Resale Price**: ${pricing.get('market_resale_value', 0.0):.2f}
- **Projected Net Profit**: ${pricing.get('net_profit', 0.0):.2f}
- **Profit Margin**: {pricing.get('profit_margin_percentage', 0.0)}%
- **ROI**: {pricing.get('roi_percentage', 0.0)}%

---

## 4. Generated Marketplace Listing (Markdown)
```markdown
{ebay_template.strip()}
```
"""

    # Ensure reports directory exists
    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/{session_id}_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_template)
        
    return json.dumps({
        "report_file": report_path,
        "ebay_listing": ebay_template.strip(),
        "report_markdown": report_template
    }, indent=2)

if __name__ == "__main__":
    mcp.run()
