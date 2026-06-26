import os
import json
from datetime import datetime
from typing import Any, Dict, List

class LongTermMemory:
    """
    Long-Term Memory persists completed evaluation sessions, repair histories,
    and resale pricing data. This memory helps agents look up historical precedents.
    """
    def __init__(self, storage_path: str = "data/historical_evaluations.json"):
        self.storage_path = storage_path
        self.records: List[Dict[str, Any]] = []
        self._ensure_storage_exists()
        self.load()

    def _ensure_storage_exists(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def save(self):
        """Save historical records to JSON."""
        self._ensure_storage_exists()
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2, ensure_ascii=False)

    def load(self):
        """Load historical records from local storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        self.records = json.loads(content)
            except Exception:
                self.records = []

    def add_evaluation(self, session_id: str, device_info: Dict[str, Any], analysis: Dict[str, Any], final_listing: Dict[str, Any]):
        """Save a completed device evaluation run into historical records."""
        record = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "device": device_info,
            "analysis": analysis,
            "listing": final_listing
        }
        self.records.append(record)
        self.save()

    def search_by_device(self, brand: str = None, model: str = None) -> List[Dict[str, Any]]:
        """Search historical records for a specific brand or model."""
        results = []
        for r in self.records:
            dev = r.get("device", {})
            brand_match = not brand or brand.lower() in dev.get("brand", "").lower()
            model_match = not model or model.lower() in dev.get("model", "").lower()
            if brand_match and model_match:
                results.append(r)
        return results

    def get_average_repair_cost(self, brand: str, model: str) -> float:
        """Calculate average repair cost for a given device from history."""
        records = self.search_by_device(brand, model)
        costs = []
        for r in records:
            # Look inside refurbishment agent's analysis for total estimated cost
            refurb_data = r.get("analysis", {}).get("refurbishment_agent", {})
            cost = refurb_data.get("estimated_repair_cost", 0.0)
            if cost > 0:
                costs.append(cost)
        return sum(costs) / len(costs) if costs else 0.0

    def get_all_records(self) -> List[Dict[str, Any]]:
        """Return all historical evaluation records."""
        return self.records
