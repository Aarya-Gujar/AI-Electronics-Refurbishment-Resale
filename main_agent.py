import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Tuple

from core.a2a_protocol import create_message, AgentMessage
from core.observability import observer, trace_execution_time
from memory.session_memory import SessionMemory
from memory.long_term_memory import LongTermMemory
from agents.security_agent import SecurityAgent
from agents.planner import PlannerAgent
from agents.worker import VisionAgent, ProductIntelligenceAgent, RefurbishmentAgent, ResaleAgent
from agents.evaluator import EvaluatorAgent
from tools.tools import listing_tool

class MainAgentOrchestrator:
    """
    MainAgentOrchestrator manages the execution flow of the AI Electronics Refurbishment & Resale system.
    Sequentially drives the Planner -> Worker -> Evaluator agent pipeline,
    recording structured A2A communication, managing memory systems, and compiling the final listing report.
    """
    def __init__(self):
        self.session_mem = SessionMemory()
        self.long_term_mem = LongTermMemory()
        
        # Initialize agents
        self.security_agent = SecurityAgent()
        self.planner_agent = PlannerAgent()
        self.vision_agent = VisionAgent()
        self.product_agent = ProductIntelligenceAgent()
        self.refurb_agent = RefurbishmentAgent()
        self.resale_agent = ResaleAgent()
        self.evaluator_agent = EvaluatorAgent()

    @trace_execution_time("Orchestrator", "run_pipeline")
    def run_workflow(self, user_request: str, image_path: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute the multi-agent pipeline from security audit to final listing generation.
        """
        # 1. Reset/Initialize Session Memory
        self.session_mem.clear()
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        self.session_mem.set_session_id(session_id)
        self.session_mem.set_workflow_state("running")
        
        observer.log_agent_execution("Orchestrator", "STARTED", f"Initializing new session: {session_id}")
        
        # Capture file metadata if image exists
        filesize = os.path.getsize(image_path) if image_path and os.path.exists(image_path) else 0
        filename = os.path.basename(image_path) if image_path else ""
        file_metadata = {
            "filename": filename,
            "filesize": filesize,
            "extension": "." + filename.split(".")[-1].lower() if "." in filename else ""
        }
        
        # --- STAGE 1: SECURITY AUDIT ---
        self.session_mem.set_workflow_state("security_audit")
        sec_msg = create_message(
            sender="orchestrator",
            receiver="security_agent",
            task="validate_request",
            payload={"user_input": user_request, "file_metadata": file_metadata}
        )
        self.session_mem.add_message(sec_msg)
        
        sec_response = self.security_agent.process_message(sec_msg)
        self.session_mem.add_message(sec_response)
        
        if not sec_response.payload.get("is_safe"):
            reason = sec_response.payload.get("reason", "Unknown security breach.")
            self.session_mem.set_workflow_state("failed_security")
            observer.log_agent_execution("Orchestrator", "FAILED", f"Security rejection: {reason}")
            return False, {
                "session_id": session_id,
                "status": "security_failed",
                "error": reason,
                "logs": observer.get_logs(20)
            }
            
        # --- STAGE 2: WORKFLOW PLANNING ---
        self.session_mem.set_workflow_state("planning")
        plan_msg = create_message(
            sender="orchestrator",
            receiver="planner_agent",
            task="create_plan",
            payload={"user_request": user_request, "image_path": image_path or ""}
        )
        self.session_mem.add_message(plan_msg)
        
        plan_response = self.planner_agent.process_message(plan_msg)
        self.session_mem.add_message(plan_response)
        
        plan_data = plan_response.payload
        self.session_mem.set_plan(plan_data.get("plan_steps", []))
        
        # --- STAGE 3: WORKER EXECUTIONS ---
        device_profile = {
            "requested_model": plan_data.get("parsed_model", "generic"),
            "condition": plan_data.get("parsed_condition", "Good"),
            "issues": plan_data.get("parsed_issues", [])
        }
        self.session_mem.set_device_info("profile", device_profile)
        
        worker_outputs = {}
        
        # 3.1 Vision Worker
        self.session_mem.set_workflow_state("vision_analysis")
        vis_msg = create_message(
            sender="orchestrator",
            receiver="vision_agent",
            task="identify_device",
            payload={"image_path": image_path, "estimated_model": device_profile["requested_model"]}
        )
        self.session_mem.add_message(vis_msg)
        vis_response = self.vision_agent.process_message(vis_msg)
        self.session_mem.add_message(vis_response)
        
        verified_model = vis_response.payload.get("verified_model", device_profile["requested_model"])
        brand = vis_response.payload.get("brand", "Generic")
        ocr_text = vis_response.payload.get("ocr_text", "")
        self.session_mem.set_device_info("verified_model", verified_model)
        self.session_mem.set_device_info("brand", brand)
        self.session_mem.set_device_info("ocr_text", ocr_text)
        
        worker_outputs["vision_agent"] = vis_response.payload

        # 3.2 Product Intel Worker
        self.session_mem.set_workflow_state("specs_retrieval")
        prod_msg = create_message(
            sender="orchestrator",
            receiver="product_agent",
            task="retrieve_specs",
            payload={"model": verified_model, "brand": brand}
        )
        self.session_mem.add_message(prod_msg)
        prod_response = self.product_agent.process_message(prod_msg)
        self.session_mem.add_message(prod_response)
        
        specs_dict = prod_response.payload.get("specs_dict", {})
        worker_outputs["product_agent"] = prod_response.payload

        # 3.3 Refurbishment Worker
        self.session_mem.set_workflow_state("refurbishment_estimation")
        issues_str = ",".join(device_profile["issues"]) if device_profile["issues"] else "none"
        refurb_msg = create_message(
            sender="orchestrator",
            receiver="refurbishment_agent",
            task="estimate_repairs",
            payload={"model": verified_model, "brand": brand, "specs": specs_dict, "issues": issues_str}
        )
        self.session_mem.add_message(refurb_msg)
        refurb_response = self.refurb_agent.process_message(refurb_msg)
        self.session_mem.add_message(refurb_response)
        
        total_repair_cost = refurb_response.payload.get("total_repair_cost", 0.0)
        worker_outputs["refurbishment_agent"] = refurb_response.payload

        # 3.4 Resale Worker
        self.session_mem.set_workflow_state("resale_valuation")
        resale_msg = create_message(
            sender="orchestrator",
            receiver="resale_agent",
            task="calculate_economics",
            payload={
                "model": verified_model, 
                "brand": brand, 
                "target_condition": device_profile["condition"], 
                "total_repair_cost": total_repair_cost
            }
        )
        self.session_mem.add_message(resale_msg)
        resale_response = self.resale_agent.process_message(resale_msg)
        self.session_mem.add_message(resale_response)
        
        pricing_dict = resale_response.payload.get("pricing_dict", {})
        worker_outputs["resale_agent"] = resale_response.payload

        # Save worker outputs to active session memory
        for agent_name, out_payload in worker_outputs.items():
            self.session_mem.update_analysis(agent_name, out_payload)

        # --- STAGE 4: QUALITY VALIDATION & EVALUATION ---
        self.session_mem.set_workflow_state("quality_evaluation")
        eval_msg = create_message(
            sender="orchestrator",
            receiver="evaluator_agent",
            task="validate_outputs",
            payload={"all_agent_outputs": worker_outputs}
        )
        self.session_mem.add_message(eval_msg)
        eval_response = self.evaluator_agent.process_message(eval_msg)
        self.session_mem.add_message(eval_response)
        
        eval_payload = eval_response.payload
        validation_approved = eval_payload.get("approved", False)
        
        # Save evaluation result to session memory
        self.session_mem.update_analysis("evaluator_agent", eval_payload)

        if not validation_approved:
            self.session_mem.set_workflow_state("failed_evaluation")
            observer.log_agent_execution("Orchestrator", "FAILED", f"Evaluator rejected the workflow: {eval_payload.get('notes')}")
            return False, {
                "session_id": session_id,
                "status": "validation_failed",
                "validation_score": eval_payload.get("score", 0.0),
                "errors": eval_payload.get("errors", []),
                "warnings": eval_payload.get("warnings", []),
                "device_profile": {
                    "brand": brand,
                    "model": verified_model,
                    "specs": specs_dict,
                    "total_repair_cost": total_repair_cost
                },
                "pricing": pricing_dict,
                "investment_recommendation": eval_payload.get("investment_recommendation", {})
            }

        # --- STAGE 5: REPORT & LISTING GENERATION ---
        self.session_mem.set_workflow_state("generating_report")
        
        # Run Listing Generator Server tool via MCP client wrapper
        listing_json = listing_tool(
            model_name=verified_model,
            condition=device_profile["condition"],
            specs_json=prod_response.payload.get("specs_raw", "{}"),
            repair_json=refurb_response.payload.get("repair_raw", "{}"),
            pricing_json=resale_response.payload.get("pricing_raw", "{}"),
            session_id=session_id
        )
        
        try:
            listing_data = json.loads(listing_json)
        except Exception:
            listing_data = {
                "report_file": f"reports/{session_id}_report.md",
                "ebay_listing": "Failed to serialize listing template.",
                "report_markdown": "Failed to serialize report."
            }

        # Record generation to session memory
        self.session_mem.update_analysis("listing_generator", listing_data)

        # --- STAGE 6: FINALIZE & PERSIST TO LONG-TERM MEMORY ---
        device_info = {
            "brand": brand,
            "model": verified_model,
            "target_condition": device_profile["condition"],
            "image_path": image_path or ""
        }
        
        analysis_summary = {
            "specs": specs_dict,
            "refurbishment": refurb_response.payload.get("repair_dict", {}),
            "pricing": pricing_dict,
            "validation_score": eval_payload.get("score", 1.0),
            "investment_recommendation": eval_payload.get("investment_recommendation", {})
        }
        
        # Save to historical long-term database
        self.long_term_mem.add_evaluation(
            session_id=session_id,
            device_info=device_info,
            analysis=analysis_summary,
            final_listing=listing_data
        )

        self.session_mem.set_workflow_state("completed")
        observer.log_agent_execution("Orchestrator", "COMPLETED", f"Session {session_id} finalized successfully.")
        
        return True, {
            "session_id": session_id,
            "status": "completed",
            "device_profile": device_info,
            "specs": specs_dict,
            "repairs": refurb_response.payload.get("repair_dict", {}),
            "pricing": pricing_dict,
            "listing": listing_data,
            "validation_score": eval_payload.get("score", 1.0),
            "warnings": eval_payload.get("warnings", []),
            "investment_recommendation": eval_payload.get("investment_recommendation", {})
        }
