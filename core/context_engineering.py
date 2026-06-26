from typing import Any, Dict

class ContextEngineer:
    """
    ContextEngineer guarantees that agents receive only the subset of system context
    necessary to fulfill their specific role. This enforces a strict 'need-to-know' policy,
    preventing prompt leakage, noise, and data corruption.
    """
    @staticmethod
    def get_security_context(user_input: str, file_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Provides only user input text and basic upload metadata (size, name, extension)."""
        return {
            "user_input": user_input,
            "file_metadata": {
                "filename": file_metadata.get("filename", ""),
                "filesize": file_metadata.get("filesize", 0),
                "extension": file_metadata.get("extension", "")
            }
        }

    @staticmethod
    def get_planner_context(user_request: str) -> Dict[str, Any]:
        """Planner needs the sanitized user request to coordinate execution."""
        return {
            "user_request": user_request
        }

    @staticmethod
    def get_vision_context(image_path: str) -> Dict[str, Any]:
        """Vision worker receives only the physical image reference."""
        return {
            "image_path": image_path
        }

    @staticmethod
    def get_product_context(brand: str, model: str) -> Dict[str, Any]:
        """Product Agent needs the identified model metadata from Vision Agent."""
        return {
            "brand": brand,
            "model": model
        }

    @staticmethod
    def get_refurbishment_context(brand: str, model: str, specs: Dict[str, Any], issues: str) -> Dict[str, Any]:
        """Refurbishment Agent needs brand, model, specifications, and the user reported issues list."""
        return {
            "brand": brand,
            "model": model,
            "specs": specs,
            "reported_issues": issues
        }

    @staticmethod
    def get_resale_context(brand: str, model: str, target_condition: str, total_repair_cost: float) -> Dict[str, Any]:
        """Resale Agent calculates pricing based on device identification and repair cost totals."""
        return {
            "brand": brand,
            "model": model,
            "target_condition": target_condition,
            "total_repair_cost": total_repair_cost
        }

    @staticmethod
    def get_evaluator_context(all_agent_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluator reviews the complete collection of outputs to perform validation."""
        return {
            "evaluation_payload": all_agent_outputs
        }

    @staticmethod
    def get_market_intelligence_context(device_model: str) -> Dict[str, Any]:
        """Market Intelligence Agent receives the target model reference."""
        return {
            "device_model": device_model
        }

    @staticmethod
    def get_investment_context(repair_cost: float, resale_value: float, profit_margin: float, total_investment: float, net_profit: float, device_model: str) -> Dict[str, Any]:
        """Investment Agent receives refurbishment margins, values, and costs to make a recommendation."""
        return {
            "repair_cost": repair_cost,
            "resale_value": resale_value,
            "profit_margin": profit_margin,
            "total_investment": total_investment,
            "net_profit": net_profit,
            "device_model": device_model
        }
