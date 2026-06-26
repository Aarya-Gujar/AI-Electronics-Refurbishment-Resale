from typing import Dict, Any
from core.a2a_protocol import AgentMessage, create_message
from core.context_engineering import ContextEngineer
from core.observability import observer, trace_execution_time


class InvestmentRecommendationAgent:
    """
    Investment Recommendation Agent analyzes the financial viability of a device
    refurbishment project and produces an actionable investment decision.

    Outputs one of:
        - BUY: High profit potential, low risk
        - REFURBISH: Moderate profit, worth refurbishing for resale
        - SELL AS-IS: Low margin, sell without refurbishment
        - REJECT: Negative ROI, not worth pursuing
    """
    def __init__(self):
        self.name = "investment_agent"

    @trace_execution_time("InvestmentAgent", "evaluate_investment")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        """
        Evaluate investment viability based on repair cost, resale value,
        profit margin, and computed risk score.
        """
        payload = message.payload

        # Apply Context Engineering
        context = ContextEngineer.get_investment_context(
            repair_cost=payload.get("repair_cost", 0.0),
            resale_value=payload.get("resale_value", 0.0),
            profit_margin=payload.get("profit_margin", 0.0),
            total_investment=payload.get("total_investment", 0.0),
            net_profit=payload.get("net_profit", 0.0),
            device_model=payload.get("device_model", "generic"),
        )

        repair_cost = context["repair_cost"]
        resale_value = context["resale_value"]
        profit_margin = context["profit_margin"]
        total_investment = context["total_investment"]
        net_profit = context["net_profit"]

        # --- Compute Risk Score (0.0 = no risk, 1.0 = maximum risk) ---
        risk_score = 0.0

        # Factor 1: Repair-to-value ratio (high repair cost relative to resale = higher risk)
        if resale_value > 0:
            repair_ratio = repair_cost / resale_value
            if repair_ratio > 0.6:
                risk_score += 0.35
            elif repair_ratio > 0.4:
                risk_score += 0.20
            elif repair_ratio > 0.2:
                risk_score += 0.10
        else:
            risk_score += 0.40  # No resale value = very risky

        # Factor 2: Profit margin assessment
        if profit_margin < 0:
            risk_score += 0.35
        elif profit_margin < 10:
            risk_score += 0.20
        elif profit_margin < 20:
            risk_score += 0.10

        # Factor 3: Absolute net profit threshold
        if net_profit < 0:
            risk_score += 0.20
        elif net_profit < 30:
            risk_score += 0.10

        # Factor 4: Investment size relative to return
        if total_investment > 0 and resale_value > 0:
            investment_ratio = total_investment / resale_value
            if investment_ratio > 0.85:
                risk_score += 0.10

        # Clamp risk score to [0.0, 1.0]
        risk_score = min(1.0, max(0.0, round(risk_score, 2)))

        # --- Determine Recommendation ---
        if net_profit <= 0 or risk_score >= 0.70:
            recommendation = "REJECT"
            reasoning = (
                f"Negative ROI projected. Net loss of ${abs(net_profit):.2f} with risk score "
                f"{risk_score:.2f}. Not financially viable for refurbishment investment."
            )
        elif risk_score >= 0.45 or profit_margin < 10:
            recommendation = "SELL AS-IS"
            reasoning = (
                f"Marginal profitability with risk score {risk_score:.2f} and margin {profit_margin:.1f}%. "
                f"Recommend selling as-is without refurbishment to minimize capital risk."
            )
        elif profit_margin >= 25 and risk_score < 0.25:
            recommendation = "BUY"
            reasoning = (
                f"Excellent investment opportunity. Projected profit margin of {profit_margin:.1f}% "
                f"with low risk score of {risk_score:.2f}. Strong ROI with net profit of ${net_profit:.2f}."
            )
        else:
            recommendation = "REFURBISH"
            reasoning = (
                f"Viable refurbishment project. Profit margin of {profit_margin:.1f}% "
                f"with moderate risk score of {risk_score:.2f}. Expected net profit: ${net_profit:.2f}."
            )

        observer.log_agent_execution(
            self.name,
            "RECOMMENDATION_ISSUED",
            f"Decision: {recommendation} | Risk: {risk_score:.2f} | Margin: {profit_margin:.1f}%"
        )

        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="investment_response",
            payload={
                "recommendation": recommendation,
                "risk_score": risk_score,
                "reasoning": reasoning,
                "financials": {
                    "repair_cost": repair_cost,
                    "resale_value": resale_value,
                    "profit_margin": profit_margin,
                    "total_investment": total_investment,
                    "net_profit": net_profit
                }
            }
        )
