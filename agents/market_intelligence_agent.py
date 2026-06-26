import os
import json
from typing import Dict, Any, List
from core.a2a_protocol import AgentMessage, create_message
from core.context_engineering import ContextEngineer
from core.observability import observer, trace_execution_time


class MarketIntelligenceAgent:
    """
    Market Intelligence Agent provides market pricing insights and resale trend
    analysis for electronic devices. Uses local mock/sample market data — no
    external APIs required.

    Responsibilities:
        - Show average resale prices across conditions
        - Show device demand level (High / Medium / Low)
        - Show estimated profit margin by condition
        - Show resale recommendations (best platform, best time)
    """
    def __init__(self, market_data_path: str = "data/market_data.json",
                 resale_prices_path: str = "data/resale_prices.json",
                 repair_costs_path: str = "data/repair_costs.json"):
        self.name = "market_intelligence_agent"
        self.market_data_path = market_data_path
        self.resale_prices_path = resale_prices_path
        self.repair_costs_path = repair_costs_path

    def _load_json(self, path: str) -> dict:
        """Safely load a JSON file."""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    @trace_execution_time("MarketIntelligenceAgent", "analyze_market")
    def process_message(self, message: AgentMessage) -> AgentMessage:
        """
        Analyze market conditions for a specific device or for all cataloged devices.
        Expects payload with optional 'device_model' key.
        If 'device_model' is 'all' or empty, returns data for all cataloged devices.
        """
        payload = message.payload
        device_model = payload.get("device_model", "all")

        # Apply Context Engineering
        context = ContextEngineer.get_market_intelligence_context(device_model)
        query_model = context["device_model"]

        # Load data sources
        market_data = self._load_json(self.market_data_path)
        resale_prices = self._load_json(self.resale_prices_path)
        repair_costs = self._load_json(self.repair_costs_path)

        # Determine which devices to analyze
        if query_model.lower() in ("all", "", "generic"):
            devices_to_analyze = [k for k in market_data.keys()]
        else:
            # Find matching device key
            matched_key = None
            query_lower = query_model.lower().strip()
            for key in market_data.keys():
                if key in query_lower or query_lower in key:
                    matched_key = key
                    break
            devices_to_analyze = [matched_key] if matched_key else [query_lower]

        # Build market intelligence report
        device_reports: List[Dict[str, Any]] = []

        for device_key in devices_to_analyze:
            mkt = market_data.get(device_key, {})
            prices = resale_prices.get(device_key, resale_prices.get("default", {}))
            repairs = repair_costs.get(device_key, repair_costs.get("default", {}))

            # Calculate average resale price across conditions
            price_values = [v for v in prices.values() if isinstance(v, (int, float))]
            avg_resale = round(sum(price_values) / len(price_values), 2) if price_values else 0.0

            # Calculate average repair cost
            repair_values = [v for v in repairs.values() if isinstance(v, (int, float))]
            avg_repair = round(sum(repair_values) / len(repair_values), 2) if repair_values else 0.0

            # Estimate profit margin (using 'Good' condition as baseline)
            good_price = prices.get("Good", avg_resale)
            acquisition_cost = round(good_price * 0.35, 2)
            est_investment = acquisition_cost + avg_repair
            est_profit = round(good_price - est_investment, 2)
            est_margin = round((est_profit / good_price) * 100, 2) if good_price > 0 else 0.0

            # Generate resale recommendation
            demand = mkt.get("demand_level", "Unknown")
            trend = mkt.get("market_trend", "Unknown")

            if demand == "High" and trend in ("Rising", "Stable"):
                resale_recommendation = "Strong Buy — high demand with favorable pricing trends."
            elif demand == "Medium" and trend == "Stable":
                resale_recommendation = "Moderate — stable market, decent returns expected."
            elif demand == "Medium" and trend == "Declining":
                resale_recommendation = "Caution — declining prices may reduce margins."
            elif demand == "Low":
                resale_recommendation = "Avoid — low demand, high risk of slow sales."
            else:
                resale_recommendation = "Evaluate case-by-case based on specific unit condition."

            device_reports.append({
                "device": device_key,
                "category": mkt.get("category", "Electronics"),
                "demand_level": demand,
                "market_trend": trend,
                "avg_days_to_sell": mkt.get("avg_days_to_sell", 0),
                "supply_availability": mkt.get("supply_availability", "Unknown"),
                "buyer_interest_score": mkt.get("buyer_interest_score", 0.0),
                "seasonal_factor": mkt.get("seasonal_factor", 1.0),
                "recommended_platforms": mkt.get("recommended_platforms", []),
                "pricing": {
                    "excellent": prices.get("Excellent", 0.0),
                    "good": prices.get("Good", 0.0),
                    "fair": prices.get("Fair", 0.0),
                    "average_resale": avg_resale
                },
                "avg_repair_cost": avg_repair,
                "estimated_profit_margin": est_margin,
                "estimated_net_profit": est_profit,
                "resale_recommendation": resale_recommendation
            })

        observer.log_agent_execution(
            self.name,
            "MARKET_ANALYSIS_COMPLETE",
            f"Analyzed {len(device_reports)} device(s)"
        )

        return create_message(
            sender=self.name,
            receiver=message.sender,
            task="market_intelligence_response",
            payload={
                "device_reports": device_reports,
                "total_devices_analyzed": len(device_reports)
            }
        )
