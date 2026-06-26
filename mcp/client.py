import os
import sys
import json
import time
import subprocess
import logging
from typing import Any, Dict
from core.observability import observer

# Programmatically import local server modules to avoid name collision with standard 'mcp' library namespace
import importlib.util

def load_local_server(name: str):
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "servers", f"{name}.py")
    
    # Temporarily remove local paths from sys.path to allow importing global 'mcp' package
    old_path = sys.path.copy()
    project_dir = os.path.dirname(current_dir)
    sys.path = [p for p in sys.path if p not in (project_dir, current_dir, "")]
    
    try:
        spec = importlib.util.spec_from_file_location(f"local_{name}", file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"local_{name}"] = module
        spec.loader.exec_module(module)
    finally:
        sys.path = old_path
        
    return module

try:
    ocr_server = load_local_server("ocr_server")
    product_server = load_local_server("product_server")
    repair_server = load_local_server("repair_server")
    pricing_server = load_local_server("pricing_server")
    listing_server = load_local_server("listing_server")
    SERVERS_IMPORTED = True
except Exception as e:
    observer.log_error("MCP Client", f"Failed to dynamically import local server scripts: {str(e)}")
    SERVERS_IMPORTED = False

class LocalMCPClient:
    """
    LocalMCPClient communicates with MCP servers.
    Supports two modes:
    1. Direct Mode (Default & Fast): Calls the tool functions in-memory.
    2. Stdio Subprocess Mode: Spawns server scripts as Python subprocesses, 
       exchanging JSON-RPC messages over stdin/stdout.
    """
    def __init__(self, mode: str = "direct"):
        self.mode = mode.lower()
        self.running_processes: Dict[str, subprocess.Popen] = {}
        observer.log_agent_execution("MCP Client", "INITIALIZED", f"Client mode: {self.mode}")

    def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the tool call request to the correct MCP server.
        """
        start_time = time.time()
        observer.log_agent_execution("MCP Client", "CALLING_TOOL", f"{server_name}.{tool_name} with args: {arguments}")

        if self.mode == "direct" and SERVERS_IMPORTED:
            try:
                res_text = self._call_direct(server_name, tool_name, arguments)
                elapsed = time.time() - start_time
                observer.log_mcp_request(server_name, tool_name, arguments, "SUCCESS", elapsed)
                return {"success": True, "result": res_text}
            except Exception as e:
                elapsed = time.time() - start_time
                observer.log_error("MCP Client", f"Direct call to {server_name}.{tool_name} failed: {str(e)}")
                observer.log_mcp_request(server_name, tool_name, arguments, "FAILED", elapsed)
                return {"success": False, "error": str(e)}
        else:
            # Subprocess Stdio JSON-RPC Communication
            try:
                res_text = self._call_subprocess(server_name, tool_name, arguments)
                elapsed = time.time() - start_time
                observer.log_mcp_request(server_name, tool_name, arguments, "SUCCESS", elapsed)
                return {"success": True, "result": res_text}
            except Exception as e:
                elapsed = time.time() - start_time
                observer.log_error("MCP Client", f"Subprocess stdio call to {server_name}.{tool_name} failed: {str(e)}")
                observer.log_mcp_request(server_name, tool_name, arguments, "FAILED", elapsed)
                # Failover to direct if import is available
                if SERVERS_IMPORTED:
                    observer.log_agent_execution("MCP Client", "FAILOVER", f"Attempting direct failover call to {server_name}.{tool_name}")
                    try:
                        res_text = self._call_direct(server_name, tool_name, arguments)
                        return {"success": True, "result": res_text, "failover": True}
                    except Exception as fail_err:
                        return {"success": False, "error": f"Subprocess failed ({str(e)}), and direct failover failed ({str(fail_err)})"}
                return {"success": False, "error": str(e)}

    def _call_direct(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call the target tool in-memory."""
        if server_name == "ocr_server":
            if tool_name == "extract_text_from_image":
                return ocr_server.extract_text_from_image(**arguments)
        elif server_name == "product_server":
            if tool_name == "get_product_specs":
                return product_server.get_product_specs(**arguments)
        elif server_name == "repair_server":
            if tool_name == "estimate_repair_costs":
                return repair_server.estimate_repair_costs(**arguments)
        elif server_name == "pricing_server":
            if tool_name == "calculate_market_resale":
                return pricing_server.calculate_market_resale(**arguments)
        elif server_name == "listing_server":
            if tool_name == "generate_marketplace_listing":
                return listing_server.generate_marketplace_listing(**arguments)
                
        raise ValueError(f"Tool '{tool_name}' not found on server '{server_name}' in direct mode.")

    def _call_subprocess(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Interacts with the server via command line stdio JSON-RPC interface.
        Note: FastMCP servers support running direct tool executions using command line arguments
        when run with python: `python mcp/servers/ocr_server.py extract_text_from_image --image_path '...'`.
        We can leverage FastMCP's built-in CLI argument parsing to call tools synchronously and reliably!
        """
        server_script = f"mcp/servers/{server_name}.py"
        if not os.path.exists(server_script):
            raise FileNotFoundError(f"Server script '{server_script}' does not exist.")

        # Build command: python mcp/servers/xxx.py <tool_name> --arg1 val1 --arg2 val2
        cmd = [sys.executable, server_script, tool_name]
        for arg_name, arg_val in arguments.items():
            cmd.append(f"--{arg_name}")
            cmd.append(str(arg_val))

        # Run process
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True
        )
        
        # FastMCP outputs tool result to stdout
        output = process.stdout.strip()
        if not output and process.stderr:
            # Check if there is an error logged to stderr
            raise RuntimeError(f"Server stderr: {process.stderr}")
            
        return output
