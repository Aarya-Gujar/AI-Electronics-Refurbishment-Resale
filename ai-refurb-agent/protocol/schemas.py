"""
protocol/schemas.py
────────────────────
Pydantic v2 schemas for all typed agent payloads.
Every agent input/output payload is defined here for strict validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────────

class DeviceCategory(str, Enum):
    SMARTPHONE = "smartphone"
    LAPTOP = "laptop"
    TABLET = "tablet"
    SMARTWATCH = "smartwatch"
    DESKTOP = "desktop"
    GAMING_CONSOLE = "gaming_console"
    CAMERA = "camera"
    OTHER = "other"


class ConditionGrade(str, Enum):
    LIKE_NEW = "like_new"       # 90-100
    EXCELLENT = "excellent"    # 75-89
    GOOD = "good"              # 55-74
    FAIR = "fair"              # 35-54
    POOR = "poor"              # 10-34
    FOR_PARTS = "for_parts"    # 0-9


class DamageType(str, Enum):
    CRACKED_SCREEN = "cracked_screen"
    BATTERY_DEGRADED = "battery_degraded"
    WATER_DAMAGE = "water_damage"
    CHARGING_PORT = "charging_port"
    BACK_GLASS = "back_glass"
    CAMERA_LENS = "camera_lens"
    SPEAKER = "speaker"
    KEYBOARD = "keyboard"
    HINGE = "hinge"
    MOTHERBOARD = "motherboard"
    COSMETIC_SCRATCHES = "cosmetic_scratches"
    SOFTWARE_ISSUE = "software_issue"


class Marketplace(str, Enum):
    EBAY = "ebay"
    SWAPPA = "swappa"
    BACK_MARKET = "back_market"
    AMAZON = "amazon"
    CRAIGSLIST = "craigslist"
    FACEBOOK_MARKETPLACE = "facebook_marketplace"


# ── Phase 1: Vision Agent Schemas ────────────────────────────────────────────

class DamageRegion(BaseModel):
    damage_type: DamageType
    location: str = Field(description="e.g. 'top-left corner', 'center screen'")
    severity: float = Field(ge=0.0, le=1.0, description="0=minor, 1=severe")
    confidence: float = Field(ge=0.0, le=1.0)


class DeviceImagePayload(BaseModel):
    """Input to Vision Agent."""
    image_bytes: Optional[bytes] = None
    image_base64: Optional[str] = None
    image_path: Optional[str] = None
    user_notes: Optional[str] = None
    session_id: str


class DeviceIdentificationResult(BaseModel):
    """Output of Vision Agent."""
    session_id: str
    device_category: DeviceCategory
    brand: str
    model_name: str
    model_number: Optional[str] = None
    condition_score: float = Field(ge=0.0, le=100.0, description="Overall condition 0–100")
    condition_grade: ConditionGrade
    identified_text: Optional[str] = Field(None, description="Text extracted from image (OCR)")
    damage_regions: List[DamageRegion] = Field(default_factory=list)
    identification_confidence: float = Field(ge=0.0, le=1.0)
    vision_notes: Optional[str] = None


# ── Phase 2: Product Intelligence Schemas ────────────────────────────────────

class DeviceSpec(BaseModel):
    """Full device specification sheet."""
    model_name: str
    brand: str
    release_year: Optional[int] = None
    msrp_usd: Optional[float] = None
    display_size_inches: Optional[float] = None
    storage_options_gb: List[int] = Field(default_factory=list)
    ram_options_gb: List[int] = Field(default_factory=list)
    processor: Optional[str] = None
    operating_system: Optional[str] = None
    battery_mah: Optional[int] = None
    camera_mp: Optional[int] = None
    connectivity: List[str] = Field(default_factory=list)
    weight_grams: Optional[float] = None
    dimensions_mm: Optional[str] = None
    colors: List[str] = Field(default_factory=list)
    eol_date: Optional[str] = None
    software_support_until: Optional[str] = None
    repairability_score: Optional[float] = Field(None, ge=0.0, le=10.0)


class ProductSpecPayload(BaseModel):
    """Output of Product Intelligence Agent."""
    session_id: str
    device_identification: DeviceIdentificationResult
    specs: DeviceSpec
    is_eol: bool = False
    lifecycle_notes: Optional[str] = None


# ── Phase 3: Refurbishment Schemas ───────────────────────────────────────────

class RepairItem(BaseModel):
    damage_type: DamageType
    repair_description: str
    parts_required: List[str] = Field(default_factory=list)
    labor_hours: float
    parts_cost_usd_min: float
    parts_cost_usd_max: float
    labor_cost_usd: float
    difficulty_score: int = Field(ge=1, le=5, description="1=easy, 5=expert only")
    total_cost_min: float
    total_cost_max: float


class RepairEstimatePayload(BaseModel):
    """Output of Refurbishment Agent."""
    session_id: str
    device_identification: DeviceIdentificationResult
    repair_items: List[RepairItem] = Field(default_factory=list)
    total_repair_cost_min: float
    total_repair_cost_max: float
    total_labor_hours: float
    overall_difficulty: int = Field(ge=1, le=5)
    is_worth_repairing: bool
    refurbishment_narrative: str
    recommended_actions: List[str] = Field(default_factory=list)


# ── Phase 4: Resale Schemas ───────────────────────────────────────────────────

class MarketComp(BaseModel):
    platform: Marketplace
    listing_url: Optional[str] = None
    listed_price_usd: float
    condition: ConditionGrade
    days_listed: Optional[int] = None


class ResaleValuationPayload(BaseModel):
    """Output of Resale Agent."""
    session_id: str
    device_identification: DeviceIdentificationResult
    repair_estimate: RepairEstimatePayload
    purchase_price_usd: Optional[float] = None  # What refurbisher paid
    market_price_low: float
    market_price_mid: float
    market_price_high: float
    recommended_listing_price: float
    best_platform: Marketplace
    platform_fee_pct: float = Field(ge=0.0, le=1.0)
    estimated_profit_min: float
    estimated_profit_max: float
    profit_margin_pct: float
    price_trend: str = Field(description="'rising', 'stable', or 'falling'")
    market_comps: List[MarketComp] = Field(default_factory=list)
    resale_narrative: str
    listing_tips: List[str] = Field(default_factory=list)


# ── Phase 5: Listing Schemas ──────────────────────────────────────────────────

class MarketplaceListing(BaseModel):
    platform: Marketplace
    title: str
    description: str
    price_usd: float
    condition_label: str
    key_specs: List[str] = Field(default_factory=list)
    photos_needed: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


# ── Phase 6: Evaluator Schemas ────────────────────────────────────────────────

class EvaluationIssue(BaseModel):
    severity: str = Field(description="'warning' or 'error'")
    agent: str
    description: str
    suggestion: Optional[str] = None


class EvaluationResult(BaseModel):
    """Output of Evaluator Agent."""
    session_id: str
    passed: bool
    score: float = Field(ge=0.0, le=10.0, description="Overall quality score 0–10")
    issues: List[EvaluationIssue] = Field(default_factory=list)
    re_run_agents: List[str] = Field(
        default_factory=list,
        description="Agent names that should re-run due to quality issues",
    )
    evaluator_notes: Optional[str] = None


# ── Final Report Schema ───────────────────────────────────────────────────────

class RefurbReport(BaseModel):
    """The complete end-to-end analysis report."""
    report_id: str
    session_id: str
    generated_at: datetime
    device: DeviceIdentificationResult
    specs: ProductSpecPayload
    repair_estimate: RepairEstimatePayload
    resale_valuation: ResaleValuationPayload
    listings: List[MarketplaceListing] = Field(default_factory=list)
    evaluation: EvaluationResult
    pipeline_duration_seconds: float
    agent_timings: Dict[str, float] = Field(default_factory=dict)
