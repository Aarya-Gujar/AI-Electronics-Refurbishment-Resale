import os
import time
import json
import random
import shutil
import pandas as pd
from datetime import datetime, timedelta
import gradio as gr

from main_agent import MainAgentOrchestrator
from core.observability import observer
from memory.long_term_memory import LongTermMemory
from agents.market_intelligence_agent import MarketIntelligenceAgent

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

# Initialize Orchestrator, Long-Term Memory and Market Agent
orchestrator = MainAgentOrchestrator()
lt_memory = LongTermMemory()
market_agent = MarketIntelligenceAgent()

# Helper to resolve fallback recommendations for pre-existing or seeded records
def get_investment_recommendation_fallback(record_analysis):
    inv_rec = record_analysis.get("investment_recommendation", {})
    if inv_rec and inv_rec.get("recommendation"):
        return (
            inv_rec.get("recommendation"),
            inv_rec.get("risk_score", 0.0),
            inv_rec.get("reasoning", "")
        )
    
    # Calculate fallback using standard scoring rules if field is missing
    pricing = record_analysis.get("pricing", {})
    net_profit = pricing.get("net_profit", 0.0)
    profit_margin = pricing.get("profit_margin_percentage", 0.0)
    repair_cost = pricing.get("repair_cost", 0.0)
    resale_value = pricing.get("market_resale_value", 0.0)
    total_investment = pricing.get("total_investment", 0.0)
    
    risk_score = 0.0
    if resale_value > 0:
        repair_ratio = repair_cost / resale_value
        if repair_ratio > 0.6: risk_score += 0.35
        elif repair_ratio > 0.4: risk_score += 0.20
        elif repair_ratio > 0.2: risk_score += 0.10
    else:
        risk_score += 0.40
        
    if profit_margin < 0: risk_score += 0.35
    elif profit_margin < 10: risk_score += 0.20
    elif profit_margin < 20: risk_score += 0.10
    
    if net_profit < 0: risk_score += 0.20
    elif net_profit < 30: risk_score += 0.10
    
    if total_investment > 0 and resale_value > 0:
        if total_investment / resale_value > 0.85: risk_score += 0.10
        
    risk_score = min(1.0, max(0.0, round(risk_score, 2)))
    
    if net_profit <= 0 or risk_score >= 0.70:
        recommendation = "REJECT"
        reasoning = f"Negative ROI projected. Net loss of ${abs(net_profit):.2f} with risk score {risk_score:.2f}."
    elif risk_score >= 0.45 or profit_margin < 10:
        recommendation = "SELL AS-IS"
        reasoning = f"Marginal profitability with risk score {risk_score:.2f} and margin {profit_margin:.1f}%."
    elif profit_margin >= 25 and risk_score < 0.25:
        recommendation = "BUY"
        reasoning = f"Excellent investment opportunity with {profit_margin:.1f}% profit margin."
    else:
        recommendation = "REFURBISH"
        reasoning = f"Viable refurbishment project with {profit_margin:.1f}% profit margin."
        
    return recommendation, risk_score, reasoning

# Seeder function to populate memory with professional demonstration data if database is empty
def seed_historical_database(memory_instance):
    storage_path = "data/historical_evaluations.json"
    records = []
    if os.path.exists(storage_path):
        try:
            with open(storage_path, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
            
    if len(records) < 5:
        device_pool = [
            {
                "brand": "Apple", "model": "iphone 13", "target_condition": "Excellent",
                "specs": {"brand": "Apple", "model": "iPhone 13", "release_year": 2021, "specs": {"screen_size": "6.1 inches", "display": "Super Retina XDR OLED", "processor": "Apple A15 Bionic", "storage_options": ["128GB", "256GB"], "battery": "3240 mAh"}},
                "repairs": [{"issue": "screen_replacement", "action": "Perform screen replacement", "cost": 150.0}],
                "pricing": {"market_resale_value": 450.0, "estimated_acquisition_cost": 157.5, "repair_cost": 150.0, "total_investment": 307.5, "net_profit": 142.5, "profit_margin_percentage": 31.7, "roi_percentage": 46.3},
                "category": "Smartphone", "recommendation": "BUY", "risk_score": 0.15, "reasoning": "Excellent investment opportunity with high profit margin and low risk."
            },
            {
                "brand": "Apple", "model": "iphone 13", "target_condition": "Good",
                "specs": {"brand": "Apple", "model": "iPhone 13", "release_year": 2021, "specs": {"screen_size": "6.1 inches", "display": "Super Retina XDR OLED", "processor": "Apple A15 Bionic", "storage_options": ["128GB", "256GB"], "battery": "3240 mAh"}},
                "repairs": [{"issue": "battery_replacement", "action": "Replace lithium battery", "cost": 60.0}],
                "pricing": {"market_resale_value": 380.0, "estimated_acquisition_cost": 133.0, "repair_cost": 60.0, "total_investment": 193.0, "net_profit": 187.0, "profit_margin_percentage": 49.2, "roi_percentage": 96.9},
                "category": "Smartphone", "recommendation": "BUY", "risk_score": 0.05, "reasoning": "High profit margin with minimal repair cost."
            },
            {
                "brand": "Apple", "model": "iphone 14", "target_condition": "Excellent",
                "specs": {"brand": "Apple", "model": "iPhone 14", "release_year": 2022, "specs": {"screen_size": "6.1 inches", "display": "Super Retina XDR OLED", "processor": "Apple A15 Bionic", "storage_options": ["128GB", "256GB", "512GB"], "battery": "3279 mAh"}},
                "repairs": [{"issue": "screen_replacement", "action": "Perform screen replacement", "cost": 180.0}, {"issue": "back_glass_replacement", "action": "Replace back glass panel", "cost": 130.0}],
                "pricing": {"market_resale_value": 550.0, "estimated_acquisition_cost": 192.5, "repair_cost": 310.0, "total_investment": 502.5, "net_profit": 47.5, "profit_margin_percentage": 8.6, "roi_percentage": 9.5},
                "category": "Smartphone", "recommendation": "SELL AS-IS", "risk_score": 0.55, "reasoning": "Marginal profitability with high repair costs relative to value. Sell without refurbishment."
            },
            {
                "brand": "Samsung", "model": "galaxy s22", "target_condition": "Fair",
                "specs": {"brand": "Samsung", "model": "Galaxy S22", "release_year": 2022, "specs": {"screen_size": "6.1 inches", "display": "Dynamic AMOLED 2X", "processor": "Snapdragon 8 Gen 1", "storage_options": ["128GB", "256GB"], "battery": "3700 mAh"}},
                "repairs": [{"issue": "logic_board_repair", "action": "Repair micro-solder connections", "cost": 180.0}],
                "pricing": {"market_resale_value": 220.0, "estimated_acquisition_cost": 77.0, "repair_cost": 180.0, "total_investment": 257.0, "net_profit": -37.0, "profit_margin_percentage": -16.8, "roi_percentage": -14.4},
                "category": "Smartphone", "recommendation": "REJECT", "risk_score": 0.85, "reasoning": "Negative ROI projected. Not financially viable for refurbishment investment."
            },
            {
                "brand": "Apple", "model": "macbook pro m1 2020", "target_condition": "Excellent",
                "specs": {"brand": "Apple", "model": "MacBook Pro M1 2020", "release_year": 2020, "specs": {"screen_size": "13.3 inches", "display": "Retina Display", "processor": "Apple M1", "storage_options": ["256GB", "512GB", "1TB"], "battery": "58.2 Wh"}},
                "repairs": [{"issue": "keyboard_replacement", "action": "Replace scissor-switch keyboard assembly", "cost": 150.0}],
                "pricing": {"market_resale_value": 750.0, "estimated_acquisition_cost": 262.5, "repair_cost": 150.0, "total_investment": 412.5, "net_profit": 337.5, "profit_margin_percentage": 45.0, "roi_percentage": 81.8},
                "category": "Laptop", "recommendation": "BUY", "risk_score": 0.10, "reasoning": "Strong resale market with a healthy profit margin."
            },
            {
                "brand": "Apple", "model": "macbook pro m1 2020", "target_condition": "Good",
                "specs": {"brand": "Apple", "model": "MacBook Pro M1 2020", "release_year": 2020, "specs": {"screen_size": "13.3 inches", "display": "Retina Display", "processor": "Apple M1", "storage_options": ["256GB", "512GB", "1TB"], "battery": "58.2 Wh"}},
                "repairs": [{"issue": "screen_replacement", "action": "Replace Retina display panel", "cost": 350.0}],
                "pricing": {"market_resale_value": 630.0, "estimated_acquisition_cost": 220.5, "repair_cost": 350.0, "total_investment": 570.5, "net_profit": 59.5, "profit_margin_percentage": 9.4, "roi_percentage": 10.4},
                "category": "Laptop", "recommendation": "SELL AS-IS", "risk_score": 0.50, "reasoning": "High screen repair cost eats into profit margin. Better to sell in current state."
            },
            {
                "brand": "Apple", "model": "ipad pro 11 2021", "target_condition": "Excellent",
                "specs": {"brand": "Apple", "model": "iPad Pro 11 2021", "release_year": 2021, "specs": {"screen_size": "11 inches", "display": "Liquid Retina", "processor": "Apple M1", "storage_options": ["128GB", "256GB", "512GB"], "battery": "7538 mAh"}},
                "repairs": [{"issue": "charging_port_repair", "action": "Repair USB-C charging port", "cost": 70.0}],
                "pricing": {"market_resale_value": 500.0, "estimated_acquisition_cost": 175.0, "repair_cost": 70.0, "total_investment": 245.0, "net_profit": 255.0, "profit_margin_percentage": 51.0, "roi_percentage": 104.1},
                "category": "Tablet", "recommendation": "BUY", "risk_score": 0.05, "reasoning": "Outstanding profitability with minimal investment."
            },
            {
                "brand": "Apple", "model": "ipad pro 11 2021", "target_condition": "Good",
                "specs": {"brand": "Apple", "model": "iPad Pro 11 2021", "release_year": 2021, "specs": {"screen_size": "11 inches", "display": "Liquid Retina", "processor": "Apple M1", "storage_options": ["128GB", "256GB", "512GB"], "battery": "7538 mAh"}},
                "repairs": [{"issue": "screen_replacement", "action": "Replace Liquid Retina screen assembly", "cost": 220.0}],
                "pricing": {"market_resale_value": 420.0, "estimated_acquisition_cost": 147.0, "repair_cost": 220.0, "total_investment": 367.0, "net_profit": 53.0, "profit_margin_percentage": 12.6, "roi_percentage": 14.4},
                "category": "Tablet", "recommendation": "REFURBISH", "risk_score": 0.35, "reasoning": "Moderate return, screen replacement is standard refurbishment process."
            },
            {
                "brand": "Samsung", "model": "galaxy s22", "target_condition": "Excellent",
                "specs": {"brand": "Samsung", "model": "Galaxy S22", "release_year": 2022, "specs": {"screen_size": "6.1 inches", "display": "Dynamic AMOLED 2X", "processor": "Snapdragon 8 Gen 1", "storage_options": ["128GB", "256GB"], "battery": "3700 mAh"}},
                "repairs": [{"issue": "battery_replacement", "action": "Replace rechargeable battery pack", "cost": 55.0}],
                "pricing": {"market_resale_value": 350.0, "estimated_acquisition_cost": 122.5, "repair_cost": 55.0, "total_investment": 177.5, "net_profit": 172.5, "profit_margin_percentage": 49.3, "roi_percentage": 97.2},
                "category": "Smartphone", "recommendation": "BUY", "risk_score": 0.05, "reasoning": "Sleek device with minimal repair required. Strong resell margin."
            },
            {
                "brand": "Samsung", "model": "galaxy s22", "target_condition": "Good",
                "specs": {"brand": "Samsung", "model": "Galaxy S22", "release_year": 2022, "specs": {"screen_size": "6.1 inches", "display": "Dynamic AMOLED 2X", "processor": "Snapdragon 8 Gen 1", "storage_options": ["128GB", "256GB"], "battery": "3700 mAh"}},
                "repairs": [{"issue": "camera_repair", "action": "Replace primary camera module", "cost": 85.0}],
                "pricing": {"market_resale_value": 290.0, "estimated_acquisition_cost": 101.5, "repair_cost": 85.0, "total_investment": 186.5, "net_profit": 103.5, "profit_margin_percentage": 35.7, "roi_percentage": 55.5},
                "category": "Smartphone", "recommendation": "BUY", "risk_score": 0.15, "reasoning": "Healthy profit margin and moderate demand for Galaxy S series."
            }
        ]
        
        base_time = datetime.utcnow()
        for idx, item in enumerate(device_pool):
            timestamp = (base_time - timedelta(days=idx, hours=random.randint(1, 23))).isoformat() + "Z"
            session_id = f"session_seed{idx:02d}"
            
            ebay_copy = f"# Professional Refurbished {item['brand']} {item['model']}\n- Resale Condition: {item['target_condition']}\n- Tested: Fully Functional.\n- Repairs completed: {item['repairs'][0]['action']}."
            
            record = {
                "session_id": session_id,
                "timestamp": timestamp,
                "device": {
                    "brand": item["brand"],
                    "model": item["model"],
                    "target_condition": item["target_condition"],
                    "image_path": ""
                },
                "analysis": {
                    "specs": item["specs"],
                    "refurbishment": {
                        "device": item["model"],
                        "matched_model_key": item["model"],
                        "repairs": item["repairs"],
                        "total_repair_cost": item["pricing"]["repair_cost"],
                        "currency": "USD"
                    },
                    "pricing": {
                        "model_name": item["model"],
                        "matched_model_key": item["model"],
                        "target_condition": item["target_condition"],
                        "market_resale_value": item["pricing"]["market_resale_value"],
                        "estimated_acquisition_cost": item["pricing"]["estimated_acquisition_cost"],
                        "repair_cost": item["pricing"]["repair_cost"],
                        "total_investment": item["pricing"]["total_investment"],
                        "net_profit": item["pricing"]["net_profit"],
                        "profit_margin_percentage": item["pricing"]["profit_margin_percentage"],
                        "roi_percentage": item["pricing"]["roi_percentage"],
                        "currency": "USD"
                    },
                    "validation_score": 0.95 if item["recommendation"] == "REFURBISH" else (1.0 if item["recommendation"] == "BUY" else 0.8),
                    "investment_recommendation": {
                        "recommendation": item["recommendation"],
                        "risk_score": item["risk_score"],
                        "reasoning": item["reasoning"]
                    }
                },
                "listing": {
                    "report_file": f"reports/{session_id}_report.md",
                    "ebay_listing": ebay_copy,
                    "report_markdown": f"# Refurbishment Report for {item['model']}"
                }
            }
            records.append(record)
            
        with open(storage_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
            
        memory_instance.load()

# Run seeding on startup
seed_historical_database(lt_memory)

# Custom CSS for dark theme and metrics
custom_css = """
body {
    background-color: #0b0f19;
    color: #f8fafc;
    font-family: 'Outfit', 'Inter', sans-serif;
}
.gradio-container {
    background-color: #2f4f4f !important;
    border: none !important;
}
.sidebar-panel {
    background: rgba(17, 24, 39, 0.95) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 16px !important;
    padding: 20px !important;
}
.main-panel {
    background: rgba(17, 24, 39, 0.5) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-radius: 16px !important;
    padding: 24px !important;
    min-height: 80vh;
}
.log-box textarea {
    font-family: 'Fira Code', 'Courier New', Courier, monospace !important;
    background-color: #030712 !important;
    color: #10b981 !important;
    border: 1px solid #1f2937 !important;
    border-radius: 8px !important;
}
.card {
    border-radius: 12px;
    background: rgba(31, 41, 55, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.06);
    padding: 18px;
    margin-bottom: 12px;
    transition: all 0.2s ease;
}
.card:hover {
    transform: translateY(-2px);
    border-color: rgba(20, 184, 166, 0.3);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}
.glow-button {
    background: linear-gradient(135deg, #0d9488 0%, #0284c7 100%) !important;
    color: white !important;
    border: none !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(13, 148, 136, 0.4);
}
.glow-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(13, 148, 136, 0.6);
}
.kpi-card {
    background: linear-gradient(145deg, rgba(20, 26, 42, 0.9), rgba(10, 13, 22, 0.9));
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
}
.badge-buy {
    background-color: rgba(16, 185, 129, 0.2) !important;
    color: #10b981 !important;
    border: 1px solid rgba(16, 185, 129, 0.4) !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
    font-weight: bold !important;
    font-size: 12px !important;
    display: inline-block;
}
.badge-refurbish {
    background-color: rgba(59, 130, 246, 0.2) !important;
    color: #3b82f6 !important;
    border: 1px solid rgba(59, 130, 246, 0.4) !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
    font-weight: bold !important;
    font-size: 12px !important;
    display: inline-block;
}
.badge-sell-as-is {
    background-color: rgba(245, 158, 11, 0.2) !important;
    color: #f59e0b !important;
    border: 1px solid rgba(245, 158, 11, 0.4) !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
    font-weight: bold !important;
    font-size: 12px !important;
    display: inline-block;
}
.badge-reject {
    background-color: rgba(239, 68, 68, 0.2) !important;
    color: #ef4444 !important;
    border: 1px solid rgba(239, 68, 68, 0.4) !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
    font-weight: bold !important;
    font-size: 12px !important;
    display: inline-block;
}
"""

def get_recent_logs():
    return observer.get_logs(35)

# Calculate statistics for the Dashboard metrics
def get_dashboard_stats_html():
    records = lt_memory.get_all_records()
    total_runs = len(records)
    
    total_profit = 0.0
    margins = []
    approved_count = 0
    
    for r in records:
        pricing = r.get("analysis", {}).get("pricing", {})
        net_profit = pricing.get("net_profit", 0.0)
        margin = pricing.get("profit_margin_percentage", 0.0)
        val_score = r.get("analysis", {}).get("validation_score", 1.0)
        
        total_profit += net_profit
        margins.append(margin)
        if val_score >= 0.85:
            approved_count += 1
            
    avg_margin = sum(margins) / len(margins) if margins else 0.0
    pass_rate = (approved_count / total_runs * 100) if total_runs else 0.0
    
    return f"""
    <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;'>
        <div class='kpi-card'>
            <div style='font-size: 13px; color: #94a3b8; font-weight: 600; text-transform: uppercase;'>Total Evaluations</div>
            <div style='font-size: 32px; font-weight: 800; color: #38bdf8; margin-top: 8px;'>{total_runs}</div>
            <div style='font-size: 12px; color: #64748b; margin-top: 4px;'>Completed session runs</div>
        </div>
        <div class='kpi-card'>
            <div style='font-size: 13px; color: #94a3b8; font-weight: 600; text-transform: uppercase;'>Proj. Net Profit</div>
            <div style='font-size: 32px; font-weight: 800; color: #10b981; margin-top: 8px;'>${total_profit:,.2f}</div>
            <div style='font-size: 12px; color: #64748b; margin-top: 4px;'>Accumulated estimate</div>
        </div>
        <div class='kpi-card'>
            <div style='font-size: 13px; color: #94a3b8; font-weight: 600; text-transform: uppercase;'>Avg. Profit Margin</div>
            <div style='font-size: 32px; font-weight: 800; color: #f59e0b; margin-top: 8px;'>{avg_margin:.1f}%</div>
            <div style='font-size: 12px; color: #64748b; margin-top: 4px;'>Across all cataloged models</div>
        </div>
        <div class='kpi-card'>
            <div style='font-size: 13px; color: #94a3b8; font-weight: 600; text-transform: uppercase;'>Validation Pass Rate</div>
            <div style='font-size: 32px; font-weight: 800; color: #2dd4bf; margin-top: 8px;'>{pass_rate:.1f}%</div>
            <div style='font-size: 12px; color: #64748b; margin-top: 4px;'>Score &ge; 0.85 passing rate</div>
        </div>
    </div>
    """

def get_system_status_html():
    return """
    <div class='card' style='background: rgba(17, 24, 39, 0.6); padding: 20px;'>
        <h3 style='color: #f8fafc; margin-top: 0; margin-bottom: 15px;'>📡 Live Multi-Agent & Service Status</h3>
        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;'>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='height: 10px; width: 10px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;'></span>
                <div>
                    <div style='font-weight: bold; font-size: 14px;'>Planner Agent</div>
                    <div style='font-size: 12px; color: #94a3b8;'>Active (In-Memory)</div>
                </div>
            </div>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='height: 10px; width: 10px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;'></span>
                <div>
                    <div style='font-weight: bold; font-size: 14px;'>Worker Agents</div>
                    <div style='font-size: 12px; color: #94a3b8;'>Active (Vision, Specs, Refurb, Resale)</div>
                </div>
            </div>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='height: 10px; width: 10px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;'></span>
                <div>
                    <div style='font-weight: bold; font-size: 14px;'>Evaluator Agent</div>
                    <div style='font-size: 12px; color: #94a3b8;'>Active (Quality Audit & Investment)</div>
                </div>
            </div>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='height: 10px; width: 10px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;'></span>
                <div>
                    <div style='font-weight: bold; font-size: 14px;'>Security Agent</div>
                    <div style='font-size: 12px; color: #94a3b8;'>Active (Safety & Content Check)</div>
                </div>
            </div>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='height: 10px; width: 10px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;'></span>
                <div>
                    <div style='font-weight: bold; font-size: 14px;'>Investment Agent</div>
                    <div style='font-size: 12px; color: #94a3b8;'>Active (Risk & ROI Recommendation)</div>
                </div>
            </div>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='height: 10px; width: 10px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;'></span>
                <div>
                    <div style='font-weight: bold; font-size: 14px;'>MCP Servers</div>
                    <div style='font-size: 12px; color: #94a3b8;'>Direct In-Memory (Direct mode)</div>
                </div>
            </div>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='height: 10px; width: 10px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;'></span>
                <div>
                    <div style='font-weight: bold; font-size: 14px;'>Long-Term Memory</div>
                    <div style='font-size: 12px; color: #94a3b8;'>JSON Storage (Active)</div>
                </div>
            </div>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='height: 10px; width: 10px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;'></span>
                <div>
                    <div style='font-weight: bold; font-size: 14px;'>Observability Logs</div>
                    <div style='font-size: 12px; color: #94a3b8;'>observer Hooked</div>
                </div>
            </div>
        </div>
    </div>
    """

def run_agent_pipeline_core(user_request, image):
    """Executes the multi-agent pipeline from scratch."""
    temp_img_path = None
    if image is not None:
        if isinstance(image, str):
            if os.path.exists(image):
                ext = image.split(".")[-1]
                temp_img_path = f"uploads/temp_upload.{ext}"
                shutil.copy(image, temp_img_path)
        else:
            ext = getattr(image, "name", "jpg").split(".")[-1]
            temp_img_path = f"uploads/temp_upload.{ext}"
            with open(temp_img_path, "wb") as f:
                f.write(image.read() if hasattr(image, 'read') else open(image, 'rb').read())

    # Trigger orchestrator
    success, result = orchestrator.run_workflow(user_request, temp_img_path)
    
    logs_output = get_recent_logs()
    
    if not success:
        if result.get("status") == "security_failed":
            error_html = f"""
            <div style='background-color: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; border-radius: 8px; padding: 15px; margin-bottom: 20px;'>
                <h3 style='color: #ef4444; margin-top: 0;'>🛡️ Security Rejection</h3>
                <p style='color: #fca5a5; margin-bottom: 0;'>{result.get('error')}</p>
            </div>
            """
            return (
                "Failed at Security Check", 
                error_html, 
                "No specifications loaded.", 
                "No repair estimates loaded.", 
                "No pricing details loaded.", 
                "Listing generation failed.",
                logs_output,
                "No investment analysis loaded."
            )
        elif result.get("status") == "validation_failed":
            errors_li = "".join([f"<li style='color: #fca5a5;'>{err}</li>" for err in result.get("errors", [])])
            warnings_li = "".join([f"<li style='color: #fde047;'>{warn}</li>" for warn in result.get("warnings", [])])
            
            error_html = f"""
            <div style='background-color: rgba(220, 38, 38, 0.15); border: 1px solid #dc2626; border-radius: 8px; padding: 15px; margin-bottom: 20px;'>
                <h3 style='color: #ef4444; margin-top: 0;'>❌ Evaluator Validation Failed (Score: {result.get('validation_score')})</h3>
                <ul style='margin-bottom: 10px; padding-left: 20px;'>{errors_li}</ul>
                {f"<h4 style='color: #eab308; margin-top: 10px; margin-bottom: 5px;'>Warnings:</h4><ul style='padding-left: 20px; margin-bottom: 0;'>{warnings_li}</ul>" if warnings_li else ""}
            </div>
            """
            
            specs_dict = result.get("device_profile", {}).get("specs", {})
            specs_md = f"### Specs for {result.get('device_profile', {}).get('model', 'Unknown')}\n" + \
                       "\n".join([f"- **{k.title()}**: {v}" for k, v in specs_dict.items()])
            
            repair_cost = result.get("device_profile", {}).get("total_repair_cost", 0.0)
            repairs_md = f"### Total Refurbishment Cost: **${repair_cost:.2f}**\n\nValidation rejected due to negative profit projections."

            pricing = result.get("pricing", {})
            pricing_md = f"""### Projected Deficit Analysis
- **Market Valuation**: ${pricing.get('market_resale_value', 0.0):.2f}
- **Required Investment**: ${pricing.get('total_investment', 0.0):.2f}
- **Net Loss**: <span style='color:#ef4444; font-weight:bold;'>${pricing.get('net_profit', 0.0):.2f}</span>
- **ROI**: {pricing.get('roi_percentage', 0.0)}%
"""
            inv_rec = result.get("investment_recommendation", {})
            badge_class = f"badge-{inv_rec.get('recommendation', 'REJECT').lower().replace(' ', '-')}"
            inv_md = f"""### 💵 Investment Decision: <span class='{badge_class}'>{inv_rec.get('recommendation', 'REJECT')}</span>
- **Risk Score**: `{inv_rec.get('risk_score', 1.0):.2f} / 1.00`
- **Analysis Details**:
  - Net Profit: <span style='color:#ef4444; font-weight:bold;'>${pricing.get('net_profit', 0.0):.2f}</span>
  - Profit Margin: `{pricing.get('profit_margin_percentage', 0.0):.1f}%`
- **Reasoning**: {inv_rec.get('reasoning', 'Quality validation check failed.')}
"""

            return (
                "Failed at Quality Evaluation", 
                error_html, 
                specs_md, 
                repairs_md, 
                pricing_md, 
                "No listing generated.",
                logs_output,
                inv_md
            )

    # Success Flow
    dp = result["device_profile"]
    specs = result["specs"]
    repairs = result["repairs"]
    pricing = result["pricing"]
    listing = result["listing"]
    warnings_list = result["warnings"]
    inv_rec = result.get("investment_recommendation", {})

    warnings_html = ""
    if warnings_list:
        warn_li = "".join([f"<li style='color: #fde047;'>{w}</li>" for w in warnings_list])
        warnings_html = f"""
        <div style='background-color: rgba(234, 179, 8, 0.15); border: 1px solid #eab308; border-radius: 8px; padding: 12px; margin-top: 15px;'>
            <h4 style='color: #eab308; margin-top: 0; margin-bottom: 5px;'>⚠️ Evaluator Warnings Passed</h4>
            <ul style='margin-bottom: 0; padding-left: 20px;'>{warn_li}</ul>
        </div>
        """

    status_html = f"""
    <div style='background-color: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; border-radius: 8px; padding: 15px;'>
        <h3 style='color: #22c55e; margin-top: 0; margin-bottom: 5px;'>✅ Pipeline Completed Successfully</h3>
        <p style='margin-bottom: 0;'>Identified <b>{dp['brand']} {dp['model']}</b>. Target Resale Condition is <b>{dp['target_condition']}</b>.</p>
        <p style='margin-top: 5px; margin-bottom: 0;'><b>Validation Score</b>: {result['validation_score']}/1.0</p>
        {warnings_html}
    </div>
    """

    specs_md = f"### 📱 Specifications\n" + \
               f"- **Brand**: {dp['brand']}\n" + \
               f"- **Model**: {dp['model']}\n" + \
               "\n".join([f"- **{k.replace('_', ' ').title()}**: {v}" for k, v in specs.items()])

    repairs_list = repairs.get("repairs", [])
    repairs_md = f"### 🔧 Estimated Refurbishment Costs\n"
    if repairs_list:
        repairs_md += "\n".join([f"- **{r['issue'].replace('_', ' ').title()}**: {r['action']} - `${r['cost']:.2f}`" for r in repairs_list])
    else:
        repairs_md += "- No repairs detected."
    repairs_md += f"\n\n---\n**Total Repair Cost**: `${repairs.get('total_repair_cost', 0.0):.2f}`"

    pricing_md = f"""### 📊 Resale Economics Analysis
- **Market Price ({dp['target_condition']})**: `${pricing['market_resale_value']:.2f}`
- **Est. Acquisition Cost**: `${pricing['estimated_acquisition_cost']:.2f}`
- **Refurbishment Cost**: `${pricing['repair_cost']:.2f}`
- **Total Capital Investment**: `${pricing['total_investment']:.2f}`
- **Projected Net Profit**: `<span style='color:#22c55e; font-weight:bold;'>${pricing['net_profit']:.2f}</span>`
- **Expected Profit Margin**: `{pricing['profit_margin_percentage']}%`
- **Return on Investment (ROI)**: `{pricing['roi_percentage']}%`
"""

    badge_class = f"badge-{inv_rec.get('recommendation', 'BUY').lower().replace(' ', '-')}"
    inv_md = f"""### 💵 Investment Recommendation: <span class='{badge_class}'>{inv_rec.get('recommendation', 'BUY')}</span>
- **Risk Score**: `{inv_rec.get('risk_score', 0.0):.2f} / 1.00`
- **Analysis Details**:
  - Projected ROI: `{pricing.get('roi_percentage', 0.0):.1f}%`
  - Projected Net Profit: <span style='color:#22c55e; font-weight:bold;'>${pricing.get('net_profit', 0.0):.2f}</span>
  - Margin: `{pricing.get('profit_margin_percentage', 0.0):.1f}%`
- **Reasoning**: {inv_rec.get('reasoning', 'Healthy resale margins.')}
"""

    listing_md = f"""### 📝 Marketplace Listing Copy
Below is the optimized marketplace description ready for eBay or Facebook Marketplace. A full PDF/Markdown report has been exported to: `{listing['report_file']}`.

```markdown
{listing['ebay_listing']}
```
"""

    return (
        "Completed", 
        status_html, 
        specs_md, 
        repairs_md, 
        pricing_md, 
        listing_md,
        logs_output,
        inv_md
    )

def run_pipeline_wrapper(user_request, image):
    """Wrapper that updates all pages/plots upon evaluation completion."""
    status, display, specs, repairs, pricing, listing, logs, investment = run_agent_pipeline_core(user_request, image)
    
    # Reload local memory
    lt_memory.load()
    
    # Refresh dashboard and history
    kpi_html = get_dashboard_stats_html()
    history_html_val, dropdown_val = update_history_view("", "All")
    
    # Refresh analytics
    df_counts, df_repair, df_margin, df_category = get_analytics_data()
    
    return (
        status, 
        display, 
        specs, 
        repairs, 
        pricing, 
        listing, 
        investment, 
        logs,
        kpi_html,
        history_html_val,
        dropdown_val,
        gr.update(value=df_counts, x_lim=[0, df_counts["Count"].max() + 1 if not df_counts.empty else 5]),
        gr.update(value=df_repair),
        gr.update(value=df_margin),
        gr.update(value=df_category)
    )

# Market Intelligence analysis function
def run_market_analysis(device_model):
    from core.a2a_protocol import create_message
    msg = create_message(
        sender="ui",
        receiver="market_intelligence_agent",
        task="analyze_market",
        payload={"device_model": device_model}
    )
    res = market_agent.process_message(msg)
    reports = res.payload.get("device_reports", [])
    if not reports:
        return f"<p style='color: #ef4444;'>No market insights found for '{device_model}'.</p>"
        
    rep = reports[0]
    pricing = rep.get("pricing", {})
    
    demand = rep.get("demand_level", "Unknown")
    if demand == "High":
        demand_badge = f"<span class='badge-buy'>{demand} Demand</span>"
    elif demand == "Medium":
        demand_badge = f"<span class='badge-refurbish'>{demand} Demand</span>"
    else:
        demand_badge = f"<span class='badge-reject'>{demand} Demand</span>"
        
    trend = rep.get("market_trend", "Unknown")
    if trend == "Rising":
        trend_badge = f"<span class='badge-buy'>📈 {trend} Trend</span>"
    elif trend == "Stable":
        trend_badge = f"<span class='badge-refurbish'>➡️ {trend} Trend</span>"
    else:
        trend_badge = f"<span class='badge-reject'>📉 {trend} Trend</span>"
        
    html = f"""
    <div class='card' style='padding: 20px;'>
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>
            <h2 style='margin: 0; color: #2dd4bf;'>📊 {rep.get('device', '').upper()} Market Pricing Report</h2>
            <div style='display: flex; gap: 8px;'>
                {demand_badge}
                {trend_badge}
            </div>
        </div>
        <p style='color: #e2e8f0; font-size: 15px;'><b>Resale Recommendation:</b> {rep.get('resale_recommendation', '')}</p>
        
        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin: 20px 0;'>
            <div style='background: rgba(255,255,255,0.02); padding: 12px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.05);'>
                <div style='font-size: 12px; color: #94a3b8;'>Avg Resale Price</div>
                <div style='font-size: 22px; font-weight: bold; color: #10b981; margin-top: 5px;'>${pricing.get('average_resale', 0.0):.2f}</div>
            </div>
            <div style='background: rgba(255,255,255,0.02); padding: 12px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.05);'>
                <div style='font-size: 12px; color: #94a3b8;'>Avg Days to Sell</div>
                <div style='font-size: 22px; font-weight: bold; color: #38bdf8; margin-top: 5px;'>{rep.get('avg_days_to_sell', 0)} days</div>
            </div>
            <div style='background: rgba(255,255,255,0.02); padding: 12px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.05);'>
                <div style='font-size: 12px; color: #94a3b8;'>Est. Profit Margin</div>
                <div style='font-size: 22px; font-weight: bold; color: #f59e0b; margin-top: 5px;'>{rep.get('estimated_profit_margin', 0.0):.1f}%</div>
            </div>
            <div style='background: rgba(255,255,255,0.02); padding: 12px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.05);'>
                <div style='font-size: 12px; color: #94a3b8;'>Supply Level</div>
                <div style='font-size: 22px; font-weight: bold; color: #c084fc; margin-top: 5px;'>{rep.get('supply_availability', 'Unknown')}</div>
            </div>
        </div>
        
        <h3 style='color: #94a3b8; margin-top: 15px; margin-bottom: 8px;'>📋 Valuation by Resale Condition</h3>
        <table style='width: 100%; border-collapse: collapse; text-align: left;'>
            <thead>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.1); color: #94a3b8; font-size: 13px;'>
                    <th style='padding: 6px;'>Condition</th>
                    <th style='padding: 6px;'>Estimated Resale Price</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style='padding: 8px;'>Excellent Grade</td>
                    <td style='padding: 8px; font-weight: bold; color: #10b981;'>${pricing.get('excellent', 0.0):.2f}</td>
                </tr>
                <tr style='background: rgba(255,255,255,0.01);'>
                    <td style='padding: 8px;'>Good Grade (Baseline)</td>
                    <td style='padding: 8px; font-weight: bold; color: #38bdf8;'>${pricing.get('good', 0.0):.2f}</td>
                </tr>
                <tr>
                    <td style='padding: 8px;'>Fair Grade</td>
                    <td style='padding: 8px; font-weight: bold; color: #f59e0b;'>${pricing.get('fair', 0.0):.2f}</td>
                </tr>
            </tbody>
        </table>
        
        <div style='margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.05); font-size: 13px; color: #94a3b8;'>
            <b>Buyer Interest Score:</b> {rep.get('buyer_interest_score', 0.0)}/10 | <b>Seasonal Adjustment Factor:</b> {rep.get('seasonal_factor', 1.0)}x | <b>Recommended Platforms:</b> {", ".join(rep.get('recommended_platforms', []))}
        </div>
    </div>
    """
    return html

# History searching, filtering and dynamic details loading
def update_history_view(search_query="", filter_rec="All"):
    records = lt_memory.get_all_records()
    
    filtered_records = []
    choices = []
    
    for r in reversed(records):
        dev = r.get("device", {})
        analysis = r.get("analysis", {})
        
        model_name = f"{dev.get('brand', '')} {dev.get('model', '')}".lower()
        search_match = not search_query or search_query.lower() in model_name
        
        rec, risk, reasoning = get_investment_recommendation_fallback(analysis)
        filter_match = (filter_rec == "All" or rec == filter_rec)
        
        if search_match and filter_match:
            filtered_records.append((r, rec))
            choices.append(r.get("session_id"))
            
    table_rows = []
    if not filtered_records:
        table_html = "<p style='color: #64748b; padding: 10px; text-align: center;'>No evaluations matched the criteria.</p>"
    else:
        for r, rec in filtered_records:
            dev = r.get("device", {})
            analysis = r.get("analysis", {})
            pricing = analysis.get("pricing", {})
            
            model_lower = dev.get("model", "").lower()
            icon = "📱"
            if "macbook" in model_lower or "laptop" in model_lower:
                icon = "💻"
            elif "ipad" in model_lower or "tablet" in model_lower:
                icon = "📁"
                
            badge_class = f"badge-{rec.lower().replace(' ', '-')}"
            
            table_rows.append(f"""
            <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'>
                <td style='padding: 10px; font-weight: bold;'>{icon} {dev.get('brand','')} {dev.get('model','')}</td>
                <td style='padding: 10px; font-size: 13px; color: #94a3b8;'>{r.get('timestamp', '')[:16].replace('T', ' ')}</td>
                <td style='padding: 10px;'>${pricing.get('repair_cost', 0.0):.2f}</td>
                <td style='padding: 10px;'>${pricing.get('market_resale_value', 0.0):.2f}</td>
                <td style='padding: 10px; color: #10b981;'>${pricing.get('net_profit', 0.0):.2f}</td>
                <td style='padding: 10px;'>{pricing.get('profit_margin_percentage', 0.0):.1f}%</td>
                <td style='padding: 10px;'><span class='{badge_class}'>{rec}</span></td>
            </tr>
            """)
        table_html = f"""
        <table style='width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;'>
            <thead>
                <tr style='border-bottom: 2px solid rgba(255,255,255,0.1); color: #94a3b8;'>
                    <th style='padding: 10px;'>Device</th>
                    <th style='padding: 10px;'>Date</th>
                    <th style='padding: 10px;'>Repair</th>
                    <th style='padding: 10px;'>Resale</th>
                    <th style='padding: 10px;'>Net Profit</th>
                    <th style='padding: 10px;'>Margin</th>
                    <th style='padding: 10px;'>Recommendation</th>
                </tr>
            </thead>
            <tbody>
                {"".join(table_rows)}
            </tbody>
        </table>
        """
        
    dropdown_choices = choices if choices else ["None"]
    return table_html, gr.update(choices=dropdown_choices, value=dropdown_choices[0])

def get_history_detail(session_id):
    if not session_id or session_id == "None":
        return "<p style='color: #64748b; font-size: 14px;'>Select a session from the dropdown above to load its detailed evaluation report.</p>"
    records = lt_memory.get_all_records()
    for r in records:
        if r.get("session_id") == session_id:
            dev = r.get("device", {})
            analysis = r.get("analysis", {})
            pricing = analysis.get("pricing", {})
            listing = r.get("listing", {})
            
            rec, risk, reasoning = get_investment_recommendation_fallback(analysis)
            badge_class = f"badge-{rec.lower().replace(' ', '-')}"
            
            html = f"""
            <div style='border: 1px solid rgba(255,255,255,0.08); padding: 20px; border-radius: 12px; background: rgba(30,41,59,0.3);'>
                <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 10px; margin-bottom: 15px;'>
                    <h3 style='margin: 0; color: #2dd4bf;'>📜 Evaluation Detail: {dev.get('brand', '')} {dev.get('model', '')}</h3>
                    <span class='{badge_class}'>{rec} Recommendation</span>
                </div>
                <p style='font-size: 13px;'><b>Date Analyzed:</b> {r.get('timestamp', '')[:19].replace('T', ' ')} | <b>Session ID:</b> <code>{session_id}</code> | <b>Target Condition:</b> {dev.get('target_condition','')}</p>
                
                <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 15px; margin-bottom: 15px;'>
                    <div style='background: rgba(255,255,255,0.01); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);'>
                        <h4 style='margin-top:0; color:#38bdf8;'>📈 Profitability Metrics</h4>
                        <ul style='margin: 5px 0; padding-left: 20px; font-size: 13px; color:#cbd5e1;'>
                            <li>Market Resale Price: ${pricing.get('market_resale_value', 0.0):.2f}</li>
                            <li>Est. Acquisition Cost: ${pricing.get('estimated_acquisition_cost', 0.0):.2f}</li>
                            <li>Estimated Repair Budget: ${pricing.get('repair_cost', 0.0):.2f}</li>
                            <li>Projected Net Profit: <span style='color:#10b981; font-weight:bold;'>${pricing.get('net_profit', 0.0):.2f}</span></li>
                            <li>Margin: {pricing.get('profit_margin_percentage', 0.0):.1f}%</li>
                        </ul>
                    </div>
                    <div style='background: rgba(255,255,255,0.01); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);'>
                        <h4 style='margin-top:0; color:#eab308;'>🛡️ Risk & Recommendations</h4>
                        <p style='font-size: 13px; color: #cbd5e1; margin: 5px 0;'><b>Investment Decision:</b> {rec}</p>
                        <p style='font-size: 13px; color: #cbd5e1; margin: 5px 0;'><b>Calculated Risk Score:</b> <code>{risk:.2f} / 1.00</code></p>
                        <p style='font-size: 13px; color: #cbd5e1; margin: 5px 0;'><b>Details:</b> {reasoning}</p>
                    </div>
                </div>
                
                <h4 style='color: #94a3b8; margin-top: 15px; margin-bottom: 5px;'>📝 Ebay Listing Template Output:</h4>
                <pre style='background: #020617; padding: 12px; border-radius: 8px; font-size: 12px; color: #cbd5e1; white-space: pre-wrap; font-family: monospace; border: 1px solid #1e293b;'>{listing.get('ebay_listing', '')}</pre>
            </div>
            """
            return html
    return "<p style='color: #ef4444;'>Session detail failed to load.</p>"

# Retrieve pandas DataFrames from history for Gradio plots
def get_analytics_data():
    records = lt_memory.get_all_records()
    if not records:
        return (
            pd.DataFrame(columns=["Device Model", "Count"]),
            pd.DataFrame(columns=["Device Model", "Avg Repair Cost ($)"]),
            pd.DataFrame(columns=["Device Model", "Avg Margin (%)"]),
            pd.DataFrame(columns=["Category", "Count"])
        )
        
    data_list = []
    for r in records:
        dev = r.get("device", {})
        analysis = r.get("analysis", {})
        pricing = analysis.get("pricing", {})
        
        model_name = f"{dev.get('brand', '')} {dev.get('model', '')}".strip()
        model_lower = dev.get("model", "").lower()
        category = "Smartphone"
        if "macbook" in model_lower or "laptop" in model_lower:
            category = "Laptop"
        elif "ipad" in model_lower or "tablet" in model_lower:
            category = "Tablet"
            
        data_list.append({
            "model": model_name.title(),
            "repair_cost": pricing.get("repair_cost", 0.0),
            "net_profit": pricing.get("net_profit", 0.0),
            "margin": pricing.get("profit_margin_percentage", 0.0),
            "category": category
        })
        
    df = pd.DataFrame(data_list)
    
    # 1. Counts per model
    df_counts = df["model"].value_counts().reset_index()
    df_counts.columns = ["Device Model", "Count"]
    
    # 2. Avg Repair Cost
    df_repair = df.groupby("model")["repair_cost"].mean().reset_index()
    df_repair.columns = ["Device Model", "Avg Repair Cost ($)"]
    
    # 3. Avg Margin
    df_margin = df.groupby("model")["margin"].mean().reset_index()
    df_margin.columns = ["Device Model", "Avg Margin (%)"]
    
    # 4. Category distribution
    df_category = df["category"].value_counts().reset_index()
    df_category.columns = ["Category", "Count"]
    
    return df_counts, df_repair, df_margin, df_category

def refresh_analytics_plots():
    df_counts, df_repair, df_margin, df_category = get_analytics_data()
    return (
        gr.update(value=df_counts, x_lim=[0, df_counts["Count"].max() + 1 if not df_counts.empty else 5]),
        gr.update(value=df_repair),
        gr.update(value=df_margin),
        gr.update(value=df_category)
    )

# Reset local database from settings page
def clear_and_reset_database():
    storage_path = "data/historical_evaluations.json"
    if os.path.exists(storage_path):
        try:
            os.remove(storage_path)
        except Exception:
            pass
            
    # Re-seed with fresh data
    seed_historical_database(lt_memory)
    
    kpi_html = get_dashboard_stats_html()
    history_html_val, dropdown_val = update_history_view("", "All")
    df_counts, df_repair, df_margin, df_category = get_analytics_data()
    
    return (
        kpi_html,
        history_html_val,
        dropdown_val,
        gr.update(value=df_counts, x_lim=[0, df_counts["Count"].max() + 1 if not df_counts.empty else 5]),
        gr.update(value=df_repair),
        gr.update(value=df_margin),
        gr.update(value=df_category),
        "<div class='card' style='background:rgba(16,185,129,0.15); border:1px solid #10b981; padding:10px; color:#10b981;'>Memory database has been reset and seeded successfully.</div>"
    )

# Layout toggles
def select_page(page_name):
    pages = ["dashboard", "analyzer", "market", "history", "analytics", "settings"]
    updates = []
    # 6 page updates
    for p in pages:
        updates.append(gr.update(visible=(p == page_name)))
    # 6 navigation button updates (set active vs inactive styling)
    for p in pages:
        updates.append(gr.update(variant="primary" if p == page_name else "secondary"))
    return updates

# Build Gradio Blocks Dashboard
with gr.Blocks(theme=gr.themes.Soft(primary_hue="teal", secondary_hue="slate"), css=custom_css) as demo:
    
    with gr.Row():
        # LEFT COLUMN - Navigation Sidebar
        with gr.Column(scale=1, min_width=240, elem_classes=["sidebar-panel"]):
            gr.HTML("""
            <div style='text-align: center; padding: 15px 0 25px 0; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 20px;'>
                <h1 style='font-size: 22px; font-weight: 800; background: linear-gradient(135deg, #0d9488 0%, #38bdf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px;'>
                    🔄 AI Refurb Agent
                </h1>
                <p style='color: #64748b; font-size: 11px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase; margin: 0;'>
                    CAPSTONE PLATFORM
                </p>
            </div>
            """)
            
            nav_dashboard = gr.Button("📊 Dashboard Overview", variant="primary")
            nav_analyzer = gr.Button("🔍 Device Analyzer", variant="secondary")
            nav_market = gr.Button("📈 Market Intelligence", variant="secondary")
            nav_history = gr.Button("📜 History Log", variant="secondary")
            nav_analytics = gr.Button("📊 Analytics Charts", variant="secondary")
            nav_settings = gr.Button("⚙️ System Settings", variant="secondary")
            
            gr.HTML("""
            <div style='margin-top: 50px; padding: 12px; border-radius: 8px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04); font-size: 11px; text-align: center; color: #64748b;'>
                <b>Version:</b> 2.0.0-Beta<br>
                Multi-Agent Orchestrator active
            </div>
            """)

        # RIGHT COLUMN - Main Content Area
        with gr.Column(scale=4, elem_classes=["main-panel"]):
            
            # --- 1. DASHBOARD PAGE ---
            with gr.Column(visible=True) as page_dashboard:
                gr.HTML("""
                <div style='margin-bottom: 20px;'>
                    <h2 style='margin: 0; font-size: 24px; font-weight: 700; color: #f8fafc;'>📊 Business Intelligence Dashboard</h2>
                    <p style='margin: 5px 0 0 0; color: #94a3b8; font-size: 14px;'>Real-time metrics summary and running status of your resale agent network.</p>
                </div>
                """)
                
                dashboard_kpi_display = gr.HTML(value=get_dashboard_stats_html())
                
                gr.HTML("""
                <div class='card' style='margin-bottom: 20px;'>
                    <h3 style='color: #2dd4bf; margin-top: 0;'>🚀 Quick Start Guide</h3>
                    <p style='color: #cbd5e1; font-size: 14px; margin-bottom: 0;'>
                        Welcome to the AI Electronics Refurbishment & Resale Platform. Navigate to the <b>Device Analyzer</b> to analyze a device, verify its specs, estimate repairs, and generate marketing descriptions. Use <b>Market Intelligence</b> to fetch direct pricing recommendations, and explore <b>Analytics</b> for historical business insights.
                    </p>
                </div>
                """)
                
                dashboard_status_display = gr.HTML(value=get_system_status_html())

            # --- 2. DEVICE ANALYZER PAGE ---
            with gr.Column(visible=False) as page_analyzer:
                gr.HTML("""
                <div style='margin-bottom: 20px;'>
                    <h2 style='margin: 0; font-size: 24px; font-weight: 700; color: #f8fafc;'>🔍 Multi-Agent Device Analyzer</h2>
                    <p style='margin: 5px 0 0 0; color: #94a3b8; font-size: 14px;'>Execute the complete pipeline from device capture to marketplace listing copy.</p>
                </div>
                """)
                
                with gr.Row():
                    # Input
                    with gr.Column(scale=2, elem_classes=["sidebar-panel"]):
                        gr.Markdown("### 📥 Step 1: Device Input Data")
                        image_input = gr.Image(sources=["upload", "webcam"], type="filepath", label="Device Photo (Upload or Webcam)")
                        request_input = gr.Textbox(
                            label="Repair & Evaluation Instruction",
                            placeholder="e.g. Evaluate this iPhone 13. Screen needs replacement. Target condition is Excellent.",
                            lines=4,
                            value="Evaluate this iPhone 13. Screen needs replacement. Target condition is Excellent."
                        )
                        
                        run_btn = gr.Button("🚀 Start Agent Evaluation", elem_classes=["glow-button"])
                        
                        gr.Markdown("---")
                        gr.Markdown("### 📡 Live Agent Observability Stream")
                        logs_box = gr.Textbox(
                            label="Structured Agent logs (Auto-refresh)", 
                            value=get_recent_logs(), 
                            lines=12,
                            max_lines=15,
                            elem_classes=["log-box"],
                            interactive=False
                        )
                        refresh_logs_btn = gr.Button("🔄 Refresh Stream Logs", size="sm")

                    # Results
                    with gr.Column(scale=3, elem_classes=["sidebar-panel"]):
                        gr.Markdown("### ⚙️ Step 2: Agent Diagnostics & Resale Valuation")
                        
                        with gr.Row():
                            workflow_status = gr.Label(label="Workflow Progress State", value="Idle")
                            
                        status_display = gr.HTML(
                            value="<div style='background-color: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 15px; text-align: center; color: #64748b;'>Submit a request to execute agents...</div>"
                        )
                        
                        with gr.Tabs():
                            with gr.Tab("📱 Device Profile"):
                                specs_output = gr.Markdown("No specifications loaded.")
                            with gr.Tab("🔧 Refurbishment Plan"):
                                repairs_output = gr.Markdown("No repair estimates loaded.")
                            with gr.Tab("📊 Resale Economics"):
                                pricing_output = gr.Markdown("No pricing details loaded.")
                            with gr.Tab("💵 Investment Decision"):
                                investment_output = gr.Markdown("No investment analysis loaded.")
                            with gr.Tab("📝 Marketplace Copy"):
                                listing_output = gr.Markdown("No listing generated.")

            # --- 3. MARKET INTELLIGENCE PAGE ---
            with gr.Column(visible=False) as page_market:
                gr.HTML("""
                <div style='margin-bottom: 20px;'>
                    <h2 style='margin: 0; font-size: 24px; font-weight: 700; color: #f8fafc;'>📈 Market Intelligence Module</h2>
                    <p style='margin: 5px 0 0 0; color: #94a3b8; font-size: 14px;'>Analyze demand, pricing thresholds, and resale recommendations across categories.</p>
                </div>
                """)
                
                with gr.Row():
                    with gr.Column(scale=1):
                        market_device_dropdown = gr.Dropdown(
                            label="Select Cataloged Device Model",
                            choices=["iphone 13", "iphone 14", "macbook pro m1 2020", "ipad pro 11 2021", "galaxy s22"],
                            value="iphone 13"
                        )
                        market_btn = gr.Button("📈 Analyze Market Conditions", elem_classes=["glow-button"])
                    
                    with gr.Column(scale=2):
                        market_results_display = gr.HTML(
                            value="<div style='background-color: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 15px; text-align: center; color: #64748b;'>Select a model and run market analysis...</div>"
                        )

            # --- 4. HISTORY PAGE ---
            with gr.Column(visible=False) as page_history:
                gr.HTML("""
                <div style='margin-bottom: 20px;'>
                    <h2 style='margin: 0; font-size: 24px; font-weight: 700; color: #f8fafc;'>📜 Evaluation History Database</h2>
                    <p style='margin: 5px 0 0 0; color: #94a3b8; font-size: 14px;'>Browse, search, and audit past evaluation sessions saved in long-term memory.</p>
                </div>
                """)
                
                with gr.Row(elem_classes=["sidebar-panel"]):
                    with gr.Column(scale=2):
                        history_search = gr.Textbox(label="🔍 Search by Model or Brand", placeholder="e.g. iphone")
                    with gr.Column(scale=2):
                        history_filter = gr.Dropdown(
                            label="💵 Filter by Recommendation",
                            choices=["All", "BUY", "REFURBISH", "SELL AS-IS", "REJECT"],
                            value="All"
                        )
                    with gr.Column(scale=1, min_width=100):
                        history_refresh_btn = gr.Button("🔄 Refresh Database", size="sm")

                with gr.Row():
                    # Table List
                    with gr.Column(scale=3):
                        history_table_display = gr.HTML(value="")
                        
                    # Detail view panel
                    with gr.Column(scale=2, elem_classes=["sidebar-panel"]):
                        gr.Markdown("### 📜 Selected Session Inspector")
                        # Dropdown options are loaded dynamically
                        history_detail_select = gr.Dropdown(
                            label="Select Session ID",
                            choices=["None"],
                            value="None"
                        )
                        history_detail_display = gr.HTML(
                            value="<p style='color: #64748b; font-size:14px;'>Select a session from the dropdown above to load its detailed evaluation report.</p>"
                        )

            # --- 5. ANALYTICS PAGE ---
            with gr.Column(visible=False) as page_analytics:
                gr.HTML("""
                <div style='margin-bottom: 20px;'>
                    <h2 style='margin: 0; font-size: 24px; font-weight: 700; color: #f8fafc;'>📊 Visual Analytics Suite</h2>
                    <p style='margin: 5px 0 0 0; color: #94a3b8; font-size: 14px;'>Interactive visualizations representing average repair costs, margins, and distributions.</p>
                </div>
                """)
                
                df_counts, df_repair, df_margin, df_category = get_analytics_data()
                
                with gr.Row():
                    with gr.Column(scale=1):
                        plot_counts = gr.BarPlot(
                            value=df_counts,
                            x="Count",
                            y="Device Model",
                            title="Most Analyzed Device Models (Runs)",
                            color="Device Model",
                            x_lim=[0, df_counts["Count"].max() + 1 if not df_counts.empty else 5]
                        )
                    with gr.Column(scale=1):
                        plot_category = gr.BarPlot(
                            value=df_category,
                            x="Count",
                            y="Category",
                            title="Device Category Distribution",
                            color="Category"
                        )
                
                with gr.Row():
                    with gr.Column(scale=1):
                        plot_repair = gr.BarPlot(
                            value=df_repair,
                            x="Device Model",
                            y="Avg Repair Cost ($)",
                            title="Average Refurbishment Cost ($)",
                            color="Device Model"
                        )
                    with gr.Column(scale=1):
                        plot_margin = gr.BarPlot(
                            value=df_margin,
                            x="Device Model",
                            y="Avg Margin (%)",
                            title="Average Expected Profit Margin (%)",
                            color="Device Model"
                        )

            # --- 6. SETTINGS PAGE ---
            with gr.Column(visible=False) as page_settings:
                gr.HTML("""
                <div style='margin-bottom: 20px;'>
                    <h2 style='margin: 0; font-size: 24px; font-weight: 700; color: #f8fafc;'>⚙️ System Settings & Controls</h2>
                    <p style='margin: 5px 0 0 0; color: #94a3b8; font-size: 14px;'>Configure multi-agent integrations and manage long-term database memory.</p>
                </div>
                """)
                
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 🗃️ Memory Management Controls")
                        gr.Markdown("Seeding automatically injects 10 mock evaluations across iPhone, iPad, and MacBook models to feed the Analytics and History dashboard displays.")
                        
                        reset_mem_btn = gr.Button("🚨 Reset & Re-Seed Memory Database", variant="stop")
                        reset_status = gr.HTML(value="")
                        
                    with gr.Column(elem_classes=["sidebar-panel"]):
                        gr.Markdown("### ⚙️ Engine Specifications")
                        gr.Markdown(f"""
                        - **Client mode**: `direct` (high performance)
                        - **GenAI Interface**: Google GenAI Python API
                        - **LTM Database Path**: `data/historical_evaluations.json`
                        - **Session Cache Path**: `data/session_memory.json`
                        """)
                        
    # Initialize history list on page build
    demo.load(
        fn=update_history_view,
        inputs=[],
        outputs=[history_table_display, history_detail_select]
    )

    # --- SIDEBAR NAV WIRING ---
    pages_list = [page_dashboard, page_analyzer, page_market, page_history, page_analytics, page_settings]
    btns_list = [nav_dashboard, nav_analyzer, nav_market, nav_history, nav_analytics, nav_settings]
    
    # Wire Sidebar Buttons to switch pages
    nav_dashboard.click(fn=lambda: select_page("dashboard"), inputs=[], outputs=pages_list + btns_list)
    nav_analyzer.click(fn=lambda: select_page("analyzer"), inputs=[], outputs=pages_list + btns_list)
    nav_market.click(fn=lambda: select_page("market"), inputs=[], outputs=pages_list + btns_list)
    nav_history.click(fn=lambda: select_page("history"), inputs=[], outputs=pages_list + btns_list)
    
    # Reload plots when opening Analytics page
    nav_analytics.click(
        fn=select_page,
        inputs=[gr.State("analytics")],
        outputs=pages_list + btns_list
    ).then(
        fn=refresh_analytics_plots,
        inputs=[],
        outputs=[plot_counts, plot_repair, plot_margin, plot_category]
    )
    
    nav_settings.click(fn=lambda: select_page("settings"), inputs=[], outputs=pages_list + btns_list)

    # --- ACTION WIRING ---
    
    # Running the Analyzer Pipeline
    run_btn.click(
        fn=run_pipeline_wrapper,
        inputs=[request_input, image_input],
        outputs=[
            workflow_status, 
            status_display, 
            specs_output, 
            repairs_output, 
            pricing_output, 
            listing_output,
            investment_output,
            logs_box,
            # Dashboard KPIs
            dashboard_kpi_display,
            # History
            history_table_display,
            history_detail_select,
            # Analytics Plots
            plot_counts,
            plot_repair,
            plot_margin,
            plot_category
        ]
    )
    
    # Refresh Log Stream
    refresh_logs_btn.click(
        fn=get_recent_logs,
        inputs=[],
        outputs=[logs_box]
    )
    
    # Run Market analysis
    market_btn.click(
        fn=run_market_analysis,
        inputs=[market_device_dropdown],
        outputs=[market_results_display]
    )
    
    # Filter/Search history log
    history_search.change(
        fn=update_history_view,
        inputs=[history_search, history_filter],
        outputs=[history_table_display, history_detail_select]
    )
    history_filter.change(
        fn=update_history_view,
        inputs=[history_search, history_filter],
        outputs=[history_table_display, history_detail_select]
    )
    history_refresh_btn.click(
        fn=update_history_view,
        inputs=[history_search, history_filter],
        outputs=[history_table_display, history_detail_select]
    )
    
    # History Detail Selection Dropdown click
    history_detail_select.change(
        fn=get_history_detail,
        inputs=[history_detail_select],
        outputs=[history_detail_display]
    )
    
    # Reset/Seed button
    reset_mem_btn.click(
        fn=clear_and_reset_database,
        inputs=[],
        outputs=[
            dashboard_kpi_display,
            history_table_display,
            history_detail_select,
            plot_counts,
            plot_repair,
            plot_margin,
            plot_category,
            reset_status
        ]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
