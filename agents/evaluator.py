from typing import Dict, Any, List
from core.a2a_protocol import AgentMessage, create_message
from core.context_engineering import ContextEngineer
from core.observability import observer, trace_execution_time
from agents.investment_agent import InvestmentRecommendationAgent

class EvaluatorAgent:
    """
    Evaluator Agent inspects all worker outputs for quality, consistency, and financial sanity.
    Detects negative margins, model mismatches, or missing specifications.
    """
    def __init__(self):
        self.name = "evaluator_agent"
        self.investment_agent = InvestmentRecommendationAgent()

    @trace_execution_time("EvaluatorAgent", "validate_outputs")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        payload = message.payload
        all_agent_outputs = payload.get("all_agent_outputs", {})
        
        # Apply Context Engineering
        context = ContextEngineer.get_evaluator_context(all_agent_outputs)
        eval_payload = context["evaluation_payload"]

        errors = []
        warnings = []
        score = 1.0

        # Extract agent data
        vision_data = eval_payload.get("vision_agent", {})
        product_data = eval_payload.get("product_agent", {})
        refurb_data = eval_payload.get("refurbishment_agent", {})
        resale_data = eval_payload.get("resale_agent", {})

        # 1. Check Completeness
        if not vision_data or not vision_data.get("verified_model"):
            errors.append("Vision Agent output is missing or has no verified model.")
            score -= 0.25

        if not product_data or not product_data.get("specs_dict"):
            errors.append("Product specifications are missing.")
            score -= 0.25

        if not refurb_data or "total_repair_cost" not in refurb_data:
            errors.append("Refurbishment repair estimates are missing.")
            score -= 0.25

        if not resale_data or not resale_data.get("pricing_dict"):
            errors.append("Resale financial calculations are missing.")
            score -= 0.25

        # Proceed to consistency checks if base records exist
        if not errors:
            # 2. Check Consistency
            vis_model = vision_data.get("verified_model", "").lower()
            prod_model = product_data.get("specs_dict", {}).get("model", "").lower()
            
            # Check if vision identification aligns with catalog specs
            if vis_model != prod_model and vis_model not in prod_model and prod_model not in vis_model:
                warnings.append(f"Model mismatch warning: Vision detected '{vis_model}', but Product Catalog loaded specs for '{prod_model}'.")
                score -= 0.1

            # 3. Check Financial Feasibility & Safety
            pricing_dict = resale_data.get("pricing_dict", {})
            net_profit = pricing_dict.get("net_profit", 0.0)
            margin = pricing_dict.get("profit_margin_percentage", 0.0)
            total_investment = pricing_dict.get("total_investment", 0.0)
            resale_value = pricing_dict.get("market_resale_value", 0.0)

            if net_profit <= 0:
                msg = f"Negative Profitability: Total investment (${total_investment:.2f}) exceeds resale value (${resale_value:.2f}), yielding a net loss of ${net_profit:.2f}."
                errors.append(msg)
                score -= 0.4
                observer.log_validation_failure(self.name, "Financial Sanity", msg)
            elif margin < 15.0:
                msg = f"Low profit margin warning: Projected margin of {margin}% is below the standard recommended threshold (15.0%)."
                warnings.append(msg)
                score -= 0.05
                observer.log_validation_failure(self.name, "Margin Threshold", msg)

        # Determine approval status
        # Validation passes if no errors are present and validation score is high enough
        approved = len(errors) == 0
        notes = "All validation checks passed successfully. Financial model and specifications validated."
        if errors or warnings:
            notes = "Validation issues discovered. Errors: " + "; ".join(errors) + " | Warnings: " + "; ".join(warnings)

        # Call Investment Recommendation Agent
        pricing_dict = resale_data.get("pricing_dict", {}) if resale_data else {}
        repair_cost = pricing_dict.get("repair_cost", 0.0)
        resale_value = pricing_dict.get("market_resale_value", 0.0)
        profit_margin = pricing_dict.get("profit_margin_percentage", 0.0)
        total_investment = pricing_dict.get("total_investment", 0.0)
        net_profit = pricing_dict.get("net_profit", 0.0)
        device_model = product_data.get("specs_dict", {}).get("model", "generic") if product_data else "generic"

        inv_msg = create_message(
            sender=self.name,
            receiver="investment_agent",
            task="evaluate_investment",
            payload={
                "repair_cost": repair_cost,
                "resale_value": resale_value,
                "profit_margin": profit_margin,
                "total_investment": total_investment,
                "net_profit": net_profit,
                "device_model": device_model
            }
        )
        inv_res = self.investment_agent.process_message(inv_msg)
        investment_rec = inv_res.payload

        observer.log_agent_execution(
            self.name, 
            "EVALUATION_COMPLETED", 
            f"Approved: {approved} | Score: {score:.2f} | Errors: {len(errors)}, Warnings: {len(warnings)}"
        )

        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="evaluator_response",
            payload={
                "approved": approved,
                "score": round(score, 2),
                "errors": errors,
                "warnings": warnings,
                "notes": notes,
                "investment_recommendation": {
                    "recommendation": investment_rec.get("recommendation", "REJECT"),
                    "risk_score": investment_rec.get("risk_score", 1.0),
                    "reasoning": investment_rec.get("reasoning", "No investment evaluation context available.")
                }
            }
        )
