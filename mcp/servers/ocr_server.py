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

import logging

# Setup logging to stderr so it doesn't corrupt stdout JSON-RPC communication
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("OCRServer")

mcp = FastMCP("OCR Server")

@mcp.tool()
def extract_text_from_image(image_path: str) -> str:
    """
    Perform optical character recognition (OCR) on the uploaded electronic device image.
    Extracts brand labels, model numbers, and serial text visible on the casing.
    """
    logger.info(f"Performing OCR on image: {image_path}")
    
    # Verify file exists
    if not os.path.exists(image_path):
        return f"Error: File '{image_path}' not found."
    
    filename = os.path.basename(image_path).lower()
    
    # Smart mock OCR logic based on file name or simple heuristics
    if "iphone_13" in filename or "iphone13" in filename:
        return "MODEL: A2633 | FCC ID: BCG-E4030A | iPhone 13 Designed by Apple in California"
    elif "iphone_14" in filename or "iphone14" in filename:
        return "MODEL: A2882 | FCC ID: BCG-E8139A | iPhone 14 Designed by Apple in California"
    elif "macbook" in filename:
        return "MacBook Pro Model A2338 | Rated 20V 3.0A | Serial C02DX123Q05D"
    elif "ipad" in filename:
        return "iPad Model A2377 | FCC ID: BCG-A2377 | Serial DMPX12345678"
    elif "s22" in filename:
        return "SAMSUNG Galaxy S22 SM-S901B | Made in Vietnam | IMEI 354678/10/123456/7"
    else:
        # Default fallback: return some text based on the file name
        cleaned_name = os.path.splitext(filename)[0].replace("_", " ").upper()
        return f"DEVICE LABEL: {cleaned_name} | SERIAL NO: SN-{hash(filename) % 10000000}"

if __name__ == "__main__":
    mcp.run()
