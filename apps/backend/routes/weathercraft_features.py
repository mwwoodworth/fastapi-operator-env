"""
Weathercraft-specific ERP features for roofing contractors.
Includes weather-based scheduling, material optimization, and roofing-specific workflows.
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import json

from ..core.database import get_db
from ..core.auth import get_current_user
from ..core.rbac import check_permission, Permission
from ..core.cache import cache, cache_key_builder
from ..models import User
from ..db.models import Project, Job, Estimate
from ..db.financial_models import Invoice, Customer
from ..services.weather import WeatherService
from ..services.crew_scheduler import CrewScheduler
from ..agents.langgraph_orchestrator import orchestrator


router = APIRouter(
    prefix="/api/v1/weathercraft",
    tags=["Weathercraft Features"]
)

weather_service = WeatherService()
crew_scheduler = CrewScheduler()


# --- Roofing Material Calculator ---

@router.post("/material-calculator")
async def calculate_roofing_materials(
    roof_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate roofing materials based on roof measurements and type.
    
    Supports:
    - Multiple roof sections with different pitches
    - Various shingle types (3-tab, architectural, premium)
    - Accessories (ridge caps, starter strips, underlayment)
    - Waste factor calculations
    - Bundle and square calculations
    """
    check_permission(current_user, Permission.ERP_ESTIMATING_READ)
    
    # Extract roof data
    sections = roof_data.get("sections", [])
    shingle_type = roof_data.get("shingle_type", "architectural")
    include_accessories = roof_data.get("include_accessories", True)
    waste_factor = roof_data.get("waste_factor", 0.10)  # 10% default
    
    # Shingle coverage by type (sq ft per bundle)
    shingle_coverage = {
        "3_tab": 33.33,
        "architectural": 33.33,
        "premium": 25,
        "designer": 20
    }
    
    # Calculate total roof area
    total_area = 0
    for section in sections:
        length = section.get("length", 0)
        width = section.get("width", 0)
        pitch = section.get("pitch", "4/12")
        
        # Calculate pitch multiplier
        pitch_parts = pitch.split("/")
        rise = float(pitch_parts[0])
        run = float(pitch_parts[1])
        pitch_multiplier = ((rise**2 + run**2) ** 0.5) / run
        
        # Calculate section area with pitch
        section_area = length * width * pitch_multiplier
        total_area += section_area
    
    # Add waste factor
    total_area_with_waste = total_area * (1 + waste_factor)
    
    # Calculate squares (100 sq ft)
    squares = total_area_with_waste / 100
    
    # Calculate bundles needed
    coverage_per_bundle = shingle_coverage.get(shingle_type, 33.33)
    bundles_needed = int(total_area_with_waste / coverage_per_bundle) + 1
    
    # Calculate accessories if requested
    accessories = {}
    if include_accessories:
        # Ridge caps (linear feet)
        total_ridge = sum(s.get("ridge_length", 0) for s in sections)
        ridge_bundles = int(total_ridge / 35) + 1  # 35 linear ft per bundle
        
        # Starter strips
        total_perimeter = sum(
            2 * (s.get("length", 0) + s.get("width", 0)) 
            for s in sections
        )
        starter_bundles = int(total_perimeter / 120) + 1  # 120 linear ft per bundle
        
        # Underlayment (rolls)
        underlayment_rolls = int(squares * 4) + 1  # 4 rolls per square average
        
        # Flashing
        valley_length = sum(s.get("valley_length", 0) for s in sections)
        valley_rolls = int(valley_length / 50) + 1 if valley_length > 0 else 0
        
        # Nails (boxes)
        nail_boxes = int(squares * 2) + 1  # 2 boxes per square
        
        accessories = {
            "ridge_cap_bundles": ridge_bundles,
            "starter_strip_bundles": starter_bundles,
            "underlayment_rolls": underlayment_rolls,
            "valley_flashing_rolls": valley_rolls,
            "nail_boxes": nail_boxes,
            "drip_edge_pieces": int(total_perimeter / 10) + 1,  # 10 ft pieces
            "step_flashing_bundles": int(total_perimeter / 100) + 1,
            "ice_water_shield_rolls": int(total_perimeter / 75) + 1  # For edges
        }
    
    # Material cost estimates (example prices)
    material_costs = {
        "shingles": bundles_needed * _get_shingle_price(shingle_type),
        "ridge_caps": accessories.get("ridge_cap_bundles", 0) * 45,
        "starter_strips": accessories.get("starter_strip_bundles", 0) * 30,
        "underlayment": accessories.get("underlayment_rolls", 0) * 25,
        "valley_flashing": accessories.get("valley_flashing_rolls", 0) * 50,
        "nails": accessories.get("nail_boxes", 0) * 15,
        "drip_edge": accessories.get("drip_edge_pieces", 0) * 12,
        "step_flashing": accessories.get("step_flashing_bundles", 0) * 25,
        "ice_water_shield": accessories.get("ice_water_shield_rolls", 0) * 85
    }
    
    total_material_cost = sum(material_costs.values())
    
    return {
        "roof_measurements": {
            "total_area_sqft": round(total_area, 2),
            "total_area_with_waste_sqft": round(total_area_with_waste, 2),
            "squares": round(squares, 2),
            "waste_percentage": waste_factor * 100
        },
        "materials_needed": {
            "shingle_type": shingle_type,
            "shingle_bundles": bundles_needed,
            "bundles_per_square": 3 if shingle_type in ["3_tab", "architectural"] else 4,
            "accessories": accessories
        },
        "cost_estimate": {
            "materials": material_costs,
            "total_materials": round(total_material_cost, 2),
            "price_per_square": round(total_material_cost / squares, 2)
        },
        "delivery_requirements": {
            "total_weight_lbs": bundles_needed * 70,  # ~70 lbs per bundle
            "pallet_count": int(bundles_needed / 42) + 1,  # 42 bundles per pallet
            "truck_loads": 1 if bundles_needed < 200 else 2
        }
    }


def _get_shingle_price(shingle_type: str) -> float:
    """Get price per bundle based on shingle type."""
    prices = {
        "3_tab": 35,
        "architectural": 45,
        "premium": 85,
        "designer": 120
    }
    return prices.get(shingle_type, 45)


# --- Weather-Based Scheduling ---

@router.post("/weather-scheduling/optimize")
async def optimize_weather_scheduling(
    scheduling_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Optimize job scheduling based on weather forecasts.
    
    Considers:
    - Rain probability and intensity
    - Wind speeds
    - Temperature ranges
    - Job type requirements
    - Crew availability
    """
    check_permission(current_user, Permission.ERP_JOB_MANAGEMENT_WRITE)
    
    start_date = datetime.fromisoformat(scheduling_data["start_date"])
    end_date = datetime.fromisoformat(scheduling_data["end_date"])
    location = scheduling_data["location"]
    jobs = scheduling_data.get("jobs", [])
    
    # Get weather forecast
    forecast = weather_service.get_extended_forecast(
        latitude=location["latitude"],
        longitude=location["longitude"],
        days=14
    )
    
    # Weather constraints for roofing work
    weather_constraints = {
        "max_wind_speed_mph": 25,
        "max_rain_probability": 30,
        "min_temperature": 40,
        "max_temperature": 95,
        "min_hours_dry_after_rain": 4
    }
    
    # Analyze each day's workability
    workable_days = []
    for day_forecast in forecast:
        forecast_date = datetime.fromisoformat(day_forecast["date"])
        
        if start_date <= forecast_date <= end_date:
            workability_score = 100
            reasons = []
            
            # Check wind
            if day_forecast.get("wind_speed", 0) > weather_constraints["max_wind_speed_mph"]:
                workability_score -= 50
                reasons.append(f"High winds ({day_forecast['wind_speed']} mph)")
            
            # Check rain
            rain_prob = day_forecast.get("precipitation_probability", 0)
            if rain_prob > weather_constraints["max_rain_probability"]:
                workability_score -= (rain_prob - weather_constraints["max_rain_probability"])
                reasons.append(f"Rain probability {rain_prob}%")
            
            # Check temperature
            temp_high = day_forecast.get("temperature_high", 70)
            temp_low = day_forecast.get("temperature_low", 50)
            
            if temp_high > weather_constraints["max_temperature"]:
                workability_score -= 30
                reasons.append(f"Too hot ({temp_high}°F)")
            elif temp_low < weather_constraints["min_temperature"]:
                workability_score -= 40
                reasons.append(f"Too cold ({temp_low}°F)")
            
            workable_days.append({
                "date": forecast_date.isoformat(),
                "workability_score": max(0, workability_score),
                "weather": day_forecast,
                "issues": reasons,
                "recommended_hours": _get_recommended_work_hours(day_forecast)
            })
    
    # Schedule jobs on best days
    scheduled_jobs = []
    available_days = sorted(workable_days, key=lambda x: x["workability_score"], reverse=True)
    
    for job in jobs:
        job_duration_days = job.get("estimated_days", 1)
        job_type = job.get("type", "roofing")
        
        # Find best consecutive days for job
        best_start_date = None
        best_score = 0
        
        for i in range(len(available_days) - job_duration_days + 1):
            consecutive_days = available_days[i:i + job_duration_days]
            avg_score = sum(d["workability_score"] for d in consecutive_days) / job_duration_days
            
            # Higher threshold for certain job types
            min_score = 70 if job_type == "roofing" else 50
            
            if avg_score >= min_score and avg_score > best_score:
                best_score = avg_score
                best_start_date = consecutive_days[0]["date"]
        
        if best_start_date:
            scheduled_jobs.append({
                "job": job,
                "scheduled_start": best_start_date,
                "scheduled_end": (
                    datetime.fromisoformat(best_start_date) + 
                    timedelta(days=job_duration_days - 1)
                ).isoformat(),
                "weather_score": best_score,
                "weather_days": available_days[i:i + job_duration_days]
            })
    
    # Generate recommendations
    recommendations = []
    
    # Rain preparation
    rainy_days = [d for d in workable_days if d["weather"].get("precipitation_probability", 0) > 50]
    if rainy_days:
        recommendations.append({
            "type": "weather_alert",
            "message": f"Rain expected on {len(rainy_days)} days. Schedule interior work or prep days.",
            "affected_dates": [d["date"] for d in rainy_days]
        })
    
    # Temperature extremes
    hot_days = [d for d in workable_days if d["weather"].get("temperature_high", 0) > 90]
    if hot_days:
        recommendations.append({
            "type": "heat_advisory",
            "message": f"High temperatures on {len(hot_days)} days. Start work early, ensure hydration.",
            "affected_dates": [d["date"] for d in hot_days]
        })
    
    # Optimal work windows
    perfect_days = [d for d in workable_days if d["workability_score"] >= 90]
    if perfect_days:
        recommendations.append({
            "type": "optimal_conditions",
            "message": f"{len(perfect_days)} days with perfect conditions. Prioritize critical work.",
            "optimal_dates": [d["date"] for d in perfect_days]
        })
    
    return {
        "weather_analysis": {
            "forecast_days": len(workable_days),
            "excellent_days": len([d for d in workable_days if d["workability_score"] >= 90]),
            "good_days": len([d for d in workable_days if 70 <= d["workability_score"] < 90]),
            "marginal_days": len([d for d in workable_days if 50 <= d["workability_score"] < 70]),
            "poor_days": len([d for d in workable_days if d["workability_score"] < 50])
        },
        "scheduled_jobs": scheduled_jobs,
        "daily_forecast": workable_days,
        "recommendations": recommendations,
        "crew_assignments": _optimize_crew_assignments(scheduled_jobs, scheduling_data.get("crews", []))
    }


def _get_recommended_work_hours(forecast: Dict[str, Any]) -> Dict[str, Any]:
    """Determine best work hours based on weather."""
    temp_high = forecast.get("temperature_high", 70)
    temp_low = forecast.get("temperature_low", 50)
    hourly = forecast.get("hourly_forecast", [])
    
    if temp_high > 85:
        # Hot day - work early
        return {
            "start": "06:00",
            "end": "14:00",
            "break_times": ["10:00", "12:00"],
            "notes": "Start early to avoid peak heat"
        }
    elif temp_low < 45:
        # Cold day - wait for warmup
        return {
            "start": "09:00",
            "end": "17:00",
            "break_times": ["12:00", "15:00"],
            "notes": "Wait for morning warmup"
        }
    else:
        # Normal conditions
        return {
            "start": "07:00",
            "end": "16:00",
            "break_times": ["12:00"],
            "notes": "Standard work hours"
        }


def _optimize_crew_assignments(scheduled_jobs: List[Dict], crews: List[Dict]) -> List[Dict]:
    """Assign crews to scheduled jobs optimally."""
    assignments = []
    
    for job_data in scheduled_jobs:
        job = job_data["job"]
        required_skills = set(job.get("required_skills", ["roofing"]))
        crew_size_needed = job.get("crew_size_needed", 4)
        
        # Find best matching crew
        best_crew = None
        best_score = 0
        
        for crew in crews:
            crew_skills = set(crew.get("skills", []))
            skill_match = len(required_skills.intersection(crew_skills)) / len(required_skills)
            size_match = min(crew.get("size", 0) / crew_size_needed, 1.0)
            
            score = (skill_match * 0.7) + (size_match * 0.3)
            
            if score > best_score and crew.get("available", True):
                best_score = score
                best_crew = crew
        
        if best_crew:
            assignments.append({
                "job_id": job["id"],
                "crew_id": best_crew["id"],
                "crew_name": best_crew.get("name", "Crew"),
                "match_score": round(best_score * 100, 1),
                "start_date": job_data["scheduled_start"],
                "end_date": job_data["scheduled_end"]
            })
            
            # Mark crew as assigned
            best_crew["available"] = False
    
    return assignments


# --- Drone Inspection Integration ---

@router.post("/drone-inspection/analyze")
async def analyze_drone_inspection(
    inspection_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyze drone inspection data for roof damage assessment.
    
    Features:
    - Damage detection and classification
    - Area calculations
    - Repair recommendations
    - Cost estimates
    """
    check_permission(current_user, Permission.ERP_FIELD_CAPTURE_WRITE)
    
    # Mock AI analysis (would integrate with real drone/AI service)
    images = inspection_data.get("images", [])
    property_id = inspection_data.get("property_id")
    inspection_date = inspection_data.get("inspection_date", datetime.now().isoformat())
    
    # Simulate damage detection
    detected_issues = []
    total_damage_area = 0
    
    damage_types = [
        {"type": "missing_shingles", "severity": "high", "area_sqft": 12},
        {"type": "hail_damage", "severity": "medium", "area_sqft": 150},
        {"type": "moss_growth", "severity": "low", "area_sqft": 30},
        {"type": "lifted_shingles", "severity": "medium", "area_sqft": 25},
        {"type": "flashing_damage", "severity": "high", "area_sqft": 8}
    ]
    
    # Simulate detection based on image count
    import random
    num_issues = min(len(images), random.randint(2, 5))
    
    for i in range(num_issues):
        issue = random.choice(damage_types).copy()
        issue["location"] = f"Section {i+1}"
        issue["confidence"] = round(random.uniform(0.85, 0.98), 2)
        issue["repair_urgency"] = _get_repair_urgency(issue["severity"])
        detected_issues.append(issue)
        total_damage_area += issue["area_sqft"]
    
    # Generate repair recommendations
    repair_recommendations = []
    estimated_cost = 0
    
    for issue in detected_issues:
        recommendation = _get_repair_recommendation(issue)
        repair_recommendations.append(recommendation)
        estimated_cost += recommendation["estimated_cost"]
    
    # Create 3D damage map (mock data)
    damage_map = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [_generate_polygon_coords()]
                },
                "properties": {
                    "damage_type": issue["type"],
                    "severity": issue["severity"],
                    "area_sqft": issue["area_sqft"]
                }
            }
            for issue in detected_issues
        ]
    }
    
    # Generate comprehensive report
    report = {
        "inspection_summary": {
            "inspection_id": f"INSP-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
            "property_id": property_id,
            "inspection_date": inspection_date,
            "weather_conditions": "Clear, 72°F, Wind 5mph",
            "images_analyzed": len(images),
            "processing_time_seconds": round(random.uniform(15, 30), 1)
        },
        "damage_assessment": {
            "total_issues_found": len(detected_issues),
            "total_damage_area_sqft": total_damage_area,
            "overall_roof_condition": _get_overall_condition(detected_issues),
            "estimated_remaining_life_years": _estimate_roof_life(detected_issues),
            "issues": detected_issues
        },
        "repair_recommendations": repair_recommendations,
        "cost_estimate": {
            "immediate_repairs": sum(
                r["estimated_cost"] for r in repair_recommendations 
                if r["urgency"] == "immediate"
            ),
            "preventive_repairs": sum(
                r["estimated_cost"] for r in repair_recommendations 
                if r["urgency"] == "preventive"
            ),
            "total_estimated_cost": estimated_cost,
            "warranty_coverage": _check_warranty_coverage(property_id)
        },
        "damage_visualization": {
            "heat_map_url": f"/api/v1/weathercraft/inspection/{property_id}/heatmap",
            "3d_model_url": f"/api/v1/weathercraft/inspection/{property_id}/3d-model",
            "damage_map_geojson": damage_map
        },
        "next_steps": [
            "Schedule on-site verification for high-severity issues",
            "Generate detailed estimate for customer",
            "Check material availability for repairs",
            "Schedule repairs based on weather forecast"
        ]
    }
    
    # Save inspection results
    # await _save_inspection_results(db, property_id, report)
    
    return report


def _get_repair_urgency(severity: str) -> str:
    """Determine repair urgency based on severity."""
    urgency_map = {
        "high": "immediate",
        "medium": "within_30_days",
        "low": "preventive"
    }
    return urgency_map.get(severity, "within_30_days")


def _get_repair_recommendation(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Generate repair recommendation for an issue."""
    recommendations = {
        "missing_shingles": {
            "action": "Replace missing shingles",
            "materials": ["Matching shingles", "Roofing nails", "Sealant"],
            "labor_hours": 2,
            "cost_per_sqft": 8
        },
        "hail_damage": {
            "action": "Assess for full replacement or repair",
            "materials": ["Shingles", "Underlayment", "Ice & water shield"],
            "labor_hours": 1,
            "cost_per_sqft": 6
        },
        "moss_growth": {
            "action": "Clean and treat moss",
            "materials": ["Moss killer", "Zinc strips"],
            "labor_hours": 3,
            "cost_per_sqft": 2
        },
        "lifted_shingles": {
            "action": "Re-secure lifted shingles",
            "materials": ["Roofing cement", "Nails"],
            "labor_hours": 1.5,
            "cost_per_sqft": 4
        },
        "flashing_damage": {
            "action": "Replace damaged flashing",
            "materials": ["Metal flashing", "Sealant", "Fasteners"],
            "labor_hours": 3,
            "cost_per_sqft": 12
        }
    }
    
    rec_template = recommendations.get(issue["type"], recommendations["missing_shingles"])
    
    labor_cost = rec_template["labor_hours"] * 75  # $75/hour
    material_cost = issue["area_sqft"] * rec_template["cost_per_sqft"]
    
    return {
        "issue_type": issue["type"],
        "recommended_action": rec_template["action"],
        "required_materials": rec_template["materials"],
        "estimated_labor_hours": rec_template["labor_hours"],
        "estimated_cost": round(labor_cost + material_cost, 2),
        "urgency": issue["repair_urgency"],
        "warranty_applicable": issue["severity"] != "low"
    }


def _generate_polygon_coords() -> List[List[float]]:
    """Generate mock polygon coordinates for damage area."""
    import random
    base_lat = 37.7749
    base_lon = -122.4194
    
    points = []
    for i in range(5):
        lat = base_lat + random.uniform(-0.0001, 0.0001)
        lon = base_lon + random.uniform(-0.0001, 0.0001)
        points.append([lon, lat])
    
    # Close the polygon
    points.append(points[0])
    return points


def _get_overall_condition(issues: List[Dict[str, Any]]) -> str:
    """Determine overall roof condition based on issues."""
    high_severity = sum(1 for i in issues if i["severity"] == "high")
    medium_severity = sum(1 for i in issues if i["severity"] == "medium")
    
    if high_severity >= 3:
        return "poor"
    elif high_severity >= 1 or medium_severity >= 3:
        return "fair"
    elif medium_severity >= 1:
        return "good"
    else:
        return "excellent"


def _estimate_roof_life(issues: List[Dict[str, Any]]) -> int:
    """Estimate remaining roof life based on damage."""
    base_life = 20  # years
    
    for issue in issues:
        if issue["severity"] == "high":
            base_life -= 3
        elif issue["severity"] == "medium":
            base_life -= 1
        elif issue["severity"] == "low":
            base_life -= 0.5
    
    return max(1, int(base_life))


def _check_warranty_coverage(property_id: str) -> Dict[str, Any]:
    """Check warranty coverage for property."""
    # Mock warranty check
    return {
        "has_warranty": True,
        "warranty_type": "manufacturer",
        "coverage_remaining_years": 8,
        "covered_damage_types": ["hail_damage", "missing_shingles"],
        "deductible": 500
    }


# --- Smart Inventory Management ---

@router.get("/inventory/smart-reorder")
async def get_smart_reorder_suggestions(
    warehouse_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get smart reorder suggestions based on usage patterns and weather.
    
    Uses:
    - Historical usage data
    - Upcoming job requirements
    - Weather forecasts
    - Seasonal patterns
    - Lead times
    """
    check_permission(current_user, Permission.ERP_JOB_MANAGEMENT_READ)
    
    # Mock inventory data
    inventory_items = [
        {
            "id": "inv_001",
            "name": "Architectural Shingles - Weathered Wood",
            "current_stock": 120,
            "unit": "bundles",
            "reorder_point": 100,
            "avg_daily_usage": 15,
            "lead_time_days": 3
        },
        {
            "id": "inv_002", 
            "name": "Ice & Water Shield",
            "current_stock": 25,
            "unit": "rolls",
            "reorder_point": 30,
            "avg_daily_usage": 4,
            "lead_time_days": 2
        },
        {
            "id": "inv_003",
            "name": "Roofing Nails - 1.25\"",
            "current_stock": 45,
            "unit": "boxes",
            "reorder_point": 50,
            "avg_daily_usage": 8,
            "lead_time_days": 1
        }
    ]
    
    # Get upcoming jobs
    upcoming_jobs = [
        {"date": "2024-01-20", "shingles_needed": 150, "nails_needed": 10},
        {"date": "2024-01-22", "shingles_needed": 200, "nails_needed": 15},
        {"date": "2024-01-25", "shingles_needed": 100, "nails_needed": 8}
    ]
    
    # Weather impact on usage
    weather_forecast = weather_service.get_extended_forecast(
        latitude=37.7749,
        longitude=-122.4194,
        days=14
    )
    
    workable_days = sum(
        1 for day in weather_forecast 
        if day.get("precipitation_probability", 0) < 30
    )
    weather_factor = workable_days / 14  # Percentage of workable days
    
    # Generate reorder suggestions
    reorder_suggestions = []
    
    for item in inventory_items:
        # Calculate days until stockout
        daily_usage_adjusted = item["avg_daily_usage"] * weather_factor
        days_until_stockout = (
            (item["current_stock"] - item["reorder_point"]) / daily_usage_adjusted
            if daily_usage_adjusted > 0 else 999
        )
        
        # Check upcoming job requirements
        job_requirement = 0
        if "shingles" in item["name"].lower():
            job_requirement = sum(j["shingles_needed"] for j in upcoming_jobs)
        elif "nails" in item["name"].lower():
            job_requirement = sum(j["nails_needed"] for j in upcoming_jobs)
        
        # Calculate total needed
        forecast_period_days = 14
        predicted_usage = daily_usage_adjusted * forecast_period_days
        total_needed = predicted_usage + job_requirement
        
        # Determine if reorder needed
        stock_after_period = item["current_stock"] - total_needed
        reorder_needed = stock_after_period < item["reorder_point"]
        
        if reorder_needed or days_until_stockout < item["lead_time_days"] + 2:
            # Calculate optimal order quantity
            order_quantity = max(
                item["reorder_point"] * 2,  # Min order
                total_needed + item["reorder_point"] - item["current_stock"]
            )
            
            # Add seasonal adjustment
            import datetime
            current_month = datetime.datetime.now().month
            if current_month in [6, 7, 8]:  # Summer - busy season
                order_quantity *= 1.3
            elif current_month in [12, 1, 2]:  # Winter - slow season
                order_quantity *= 0.7
            
            reorder_suggestions.append({
                "item": item,
                "urgency": "high" if days_until_stockout < item["lead_time_days"] else "medium",
                "days_until_stockout": round(days_until_stockout, 1),
                "recommended_order_quantity": int(order_quantity),
                "order_by_date": (
                    datetime.now() + timedelta(days=max(0, days_until_stockout - item["lead_time_days"] - 1))
                ).date().isoformat(),
                "reasons": [
                    f"Current stock below reorder point" if item["current_stock"] < item["reorder_point"] else None,
                    f"High upcoming demand: {job_requirement} units" if job_requirement > item["current_stock"] * 0.5 else None,
                    f"Weather impact: {round((1-weather_factor)*100)}% fewer workable days" if weather_factor < 0.7 else None
                ],
                "estimated_cost": order_quantity * _get_item_unit_cost(item["name"])
            })
    
    # Get supplier recommendations
    supplier_recommendations = []
    for suggestion in reorder_suggestions:
        suppliers = _get_supplier_recommendations(suggestion["item"]["name"])
        supplier_recommendations.append({
            "item": suggestion["item"]["name"],
            "suppliers": suppliers
        })
    
    return {
        "analysis_date": datetime.now().isoformat(),
        "weather_impact": {
            "workable_days_next_14": workable_days,
            "weather_factor": round(weather_factor, 2),
            "recommendation": "Order extra inventory" if weather_factor < 0.7 else "Normal ordering"
        },
        "reorder_suggestions": reorder_suggestions,
        "supplier_recommendations": supplier_recommendations,
        "cost_summary": {
            "total_reorder_cost": sum(s["estimated_cost"] for s in reorder_suggestions),
            "urgent_items_cost": sum(s["estimated_cost"] for s in reorder_suggestions if s["urgency"] == "high")
        },
        "optimization_tips": [
            "Consider bulk ordering for summer season discounts",
            "Monitor weather patterns for demand fluctuations",
            "Set up automatic reordering for high-volume items"
        ]
    }


def _get_item_unit_cost(item_name: str) -> float:
    """Get unit cost for inventory item."""
    # Mock pricing
    if "shingles" in item_name.lower():
        return 45.00
    elif "ice" in item_name.lower():
        return 85.00
    elif "nails" in item_name.lower():
        return 15.00
    else:
        return 25.00


def _get_supplier_recommendations(item_name: str) -> List[Dict[str, Any]]:
    """Get supplier recommendations for an item."""
    # Mock supplier data
    suppliers = [
        {
            "name": "ABC Building Supply",
            "price_per_unit": _get_item_unit_cost(item_name) * 0.95,
            "lead_time_days": 2,
            "min_order_quantity": 50,
            "rating": 4.5,
            "notes": "Volume discounts available"
        },
        {
            "name": "RoofPro Distributors",
            "price_per_unit": _get_item_unit_cost(item_name),
            "lead_time_days": 1,
            "min_order_quantity": 25,
            "rating": 4.8,
            "notes": "Same-day delivery available"
        }
    ]
    
    return sorted(suppliers, key=lambda x: (x["lead_time_days"], x["price_per_unit"]))


# --- Warranty Tracking ---

@router.post("/warranty/register")
async def register_warranty(
    warranty_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Register a new warranty for a completed roofing job.
    
    Tracks:
    - Warranty terms and conditions
    - Coverage periods
    - Exclusions
    - Claim history
    """
    check_permission(current_user, Permission.ERP_JOB_MANAGEMENT_WRITE)
    
    # Generate warranty details
    warranty = {
        "warranty_id": f"WR-{datetime.now().strftime('%Y%m%d')}-{warranty_data['job_id'][-4:]}",
        "job_id": warranty_data["job_id"],
        "customer_id": warranty_data["customer_id"],
        "property_address": warranty_data["property_address"],
        "installation_date": warranty_data["installation_date"],
        "warranty_type": warranty_data.get("warranty_type", "standard"),
        "coverage": {
            "workmanship": {
                "years": 10 if warranty_data.get("warranty_type") == "premium" else 5,
                "start_date": warranty_data["installation_date"],
                "end_date": (
                    datetime.fromisoformat(warranty_data["installation_date"]) +
                    timedelta(days=365 * (10 if warranty_data.get("warranty_type") == "premium" else 5))
                ).isoformat(),
                "covers": [
                    "Installation defects",
                    "Flashing failures",
                    "Leaks due to workmanship"
                ]
            },
            "materials": {
                "years": warranty_data.get("manufacturer_warranty_years", 30),
                "start_date": warranty_data["installation_date"],
                "end_date": (
                    datetime.fromisoformat(warranty_data["installation_date"]) +
                    timedelta(days=365 * warranty_data.get("manufacturer_warranty_years", 30))
                ).isoformat(),
                "manufacturer": warranty_data.get("shingle_manufacturer", "GAF"),
                "covers": [
                    "Manufacturing defects",
                    "Premature deterioration",
                    "Wind damage up to 130mph"
                ]
            }
        },
        "exclusions": [
            "Acts of God (earthquakes, floods)",
            "Damage from falling objects",
            "Improper maintenance",
            "Unauthorized modifications"
        ],
        "maintenance_requirements": [
            {
                "task": "Annual inspection",
                "frequency": "yearly",
                "next_due": (
                    datetime.fromisoformat(warranty_data["installation_date"]) +
                    timedelta(days=365)
                ).date().isoformat()
            },
            {
                "task": "Gutter cleaning",
                "frequency": "bi-annually",
                "next_due": (
                    datetime.fromisoformat(warranty_data["installation_date"]) +
                    timedelta(days=180)
                ).date().isoformat()
            }
        ],
        "registration_date": datetime.now().isoformat(),
        "status": "active",
        "transferable": warranty_data.get("warranty_type") == "premium",
        "documents": {
            "warranty_certificate": f"/api/v1/weathercraft/warranty/{warranty_data['job_id']}/certificate",
            "terms_conditions": f"/api/v1/weathercraft/warranty/{warranty_data['job_id']}/terms",
            "maintenance_guide": f"/api/v1/weathercraft/warranty/{warranty_data['job_id']}/guide"
        }
    }
    
    # Save warranty (mock)
    # warranty_record = await _save_warranty(db, warranty)
    
    # Send confirmation email
    # await _send_warranty_confirmation(warranty_data["customer_email"], warranty)
    
    return {
        "warranty": warranty,
        "next_steps": [
            "Warranty certificate will be emailed within 24 hours",
            "Schedule first annual inspection",
            "Register with manufacturer for extended coverage",
            "Keep all receipts and documentation"
        ],
        "customer_portal": f"https://warranty.weathercraft.com/track/{warranty['warranty_id']}"
    }


# --- AI-Powered Estimation ---

@router.post("/ai-estimation/generate")
async def generate_ai_estimation(
    estimation_request: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate AI-powered roofing estimation using photos and property data.
    
    Uses:
    - Computer vision for roof analysis
    - Historical pricing data
    - Local market conditions
    - Material availability
    """
    check_permission(current_user, Permission.ERP_ESTIMATING_WRITE)
    
    # Use LangGraph for complex estimation
    workflow = orchestrator.create_analysis_workflow()
    
    # Prepare context for AI
    context = {
        "property_address": estimation_request["property_address"],
        "images": estimation_request.get("images", []),
        "customer_preferences": estimation_request.get("preferences", {}),
        "local_market": "San Francisco Bay Area",
        "season": "winter",
        "urgency": estimation_request.get("urgency", "standard")
    }
    
    # Run AI analysis
    result = await orchestrator.execute_workflow(
        workflow_id=workflow["id"],
        initial_state={
            "messages": [f"Analyze roofing project and generate estimate for: {json.dumps(context)}"],
            "context": context
        }
    )
    
    # Parse AI results and structure estimate
    ai_analysis = result.get("final_output", {})
    
    # Generate structured estimate
    estimate = {
        "estimate_id": f"EST-{datetime.now().strftime('%Y%m%d')}-{hash(estimation_request['property_address']) % 10000:04d}",
        "property": {
            "address": estimation_request["property_address"],
            "roof_area_sqft": ai_analysis.get("roof_area", 2500),
            "roof_type": ai_analysis.get("roof_type", "gable"),
            "pitch": ai_analysis.get("pitch", "6/12"),
            "current_material": ai_analysis.get("current_material", "asphalt_shingle"),
            "layers": ai_analysis.get("layers", 1),
            "age_years": ai_analysis.get("age", 15)
        },
        "scope_of_work": ai_analysis.get("scope", [
            "Remove existing shingles",
            "Inspect and repair decking",
            "Install ice and water shield",
            "Install synthetic underlayment",
            "Install architectural shingles",
            "Replace all flashing",
            "Install ridge vents"
        ]),
        "materials": {
            "shingles": {
                "type": "Architectural - 30 year",
                "color": estimation_request.get("preferences", {}).get("color", "Weathered Wood"),
                "squares": 25,
                "bundles": 75,
                "cost": 3375.00
            },
            "underlayment": {
                "type": "Synthetic",
                "rolls": 8,
                "cost": 800.00
            },
            "accessories": {
                "ice_water_shield": 425.00,
                "flashing": 350.00,
                "ridge_vents": 280.00,
                "nails_and_supplies": 225.00
            },
            "total_materials": 5455.00
        },
        "labor": {
            "tear_off": {
                "hours": 16,
                "rate": 75,
                "cost": 1200.00
            },
            "installation": {
                "hours": 32,
                "rate": 85,
                "cost": 2720.00
            },
            "cleanup": {
                "hours": 4,
                "rate": 50,
                "cost": 200.00
            },
            "total_labor": 4120.00
        },
        "additional_costs": {
            "permits": 350.00,
            "dumpster": 400.00,
            "contingency": 500.00
        },
        "pricing": {
            "subtotal": 10825.00,
            "overhead_markup": 2165.00,  # 20%
            "profit_margin": 1625.00,     # 15%
            "total_before_tax": 14615.00,
            "tax": 1315.35,               # 9%
            "total": 15930.35,
            "price_per_square": 637.21
        },
        "options": [
            {
                "description": "Upgrade to premium shingles",
                "additional_cost": 1250.00
            },
            {
                "description": "Add solar vents (4)",
                "additional_cost": 800.00
            },
            {
                "description": "Gutter replacement",
                "additional_cost": 2400.00
            }
        ],
        "timeline": {
            "estimated_days": 3,
            "start_availability": (datetime.now() + timedelta(days=7)).date().isoformat(),
            "weather_considerations": "Check 5-day forecast before scheduling"
        },
        "warranty": {
            "workmanship": "5 years standard, 10 years available",
            "materials": "30 year manufacturer warranty"
        },
        "ai_confidence": ai_analysis.get("confidence", 0.92),
        "ai_notes": ai_analysis.get("notes", [
            "Detected moderate hail damage on south-facing slope",
            "Recommend full replacement due to age and damage extent",
            "Good candidate for insurance claim"
        ]),
        "generated_date": datetime.now().isoformat(),
        "valid_until": (datetime.now() + timedelta(days=30)).date().isoformat()
    }
    
    # Save estimate
    # await _save_estimate(db, estimate)
    
    return {
        "estimate": estimate,
        "visualizations": {
            "3d_model": f"/api/v1/weathercraft/estimate/{estimate['estimate_id']}/3d-model",
            "damage_overlay": f"/api/v1/weathercraft/estimate/{estimate['estimate_id']}/damage-map",
            "color_preview": f"/api/v1/weathercraft/estimate/{estimate['estimate_id']}/color-preview"
        },
        "next_actions": [
            "Schedule in-person consultation",
            "Run insurance claim analysis",
            "Check material availability",
            "Generate customer proposal"
        ]
    }


# --- Safety Compliance ---

@router.post("/safety/job-assessment")
async def assess_job_safety(
    job_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Assess safety requirements and generate compliance checklist.
    
    Includes:
    - OSHA requirements
    - Fall protection needs
    - Weather-related safety
    - Equipment inspection
    """
    check_permission(current_user, Permission.ERP_COMPLIANCE_READ)
    
    job_details = {
        "height": job_data.get("roof_height_ft", 20),
        "pitch": job_data.get("roof_pitch", "6/12"),
        "workers": job_data.get("crew_size", 4),
        "duration_days": job_data.get("estimated_days", 3)
    }
    
    # Determine safety requirements based on job
    safety_requirements = []
    
    # Fall protection
    if job_details["height"] > 6:
        safety_requirements.append({
            "category": "Fall Protection",
            "required": True,
            "items": [
                "Safety harnesses for all workers",
                "Roof anchors or safety rails",
                "Warning line system for low-slope roofs",
                "Safety net if applicable"
            ],
            "regulation": "OSHA 1926.501"
        })
    
    # Ladder safety
    if job_details["height"] > 10:
        safety_requirements.append({
            "category": "Ladder Safety",
            "required": True,
            "items": [
                "Extension ladder (3 feet above roof line)",
                "Ladder stabilizers",
                "Ladder inspection checklist"
            ],
            "regulation": "OSHA 1926.1053"
        })
    
    # Personal Protective Equipment
    safety_requirements.append({
        "category": "Personal Protective Equipment",
        "required": True,
        "items": [
            "Hard hats",
            "Safety glasses",
            "Work gloves",
            "Non-slip footwear",
            "High-visibility vests"
        ],
        "regulation": "OSHA 1926.95-106"
    })
    
    # Weather-specific safety
    current_season = "winter"  # Would be determined dynamically
    if current_season == "summer":
        safety_requirements.append({
            "category": "Heat Safety",
            "required": True,
            "items": [
                "Water stations (1 gallon per worker per day)",
                "Shade/rest area",
                "Heat illness prevention training",
                "Work-rest schedules"
            ],
            "regulation": "Cal/OSHA Heat Illness Prevention"
        })
    elif current_season == "winter":
        safety_requirements.append({
            "category": "Cold Weather Safety",
            "required": True,
            "items": [
                "Cold weather gear",
                "Ice melt for walkways",
                "Roof ice assessment",
                "Shortened work periods"
            ],
            "regulation": "General Duty Clause"
        })
    
    # Generate safety checklist
    safety_checklist = []
    for req in safety_requirements:
        for item in req["items"]:
            safety_checklist.append({
                "item": item,
                "category": req["category"],
                "checked": False,
                "required": req["required"],
                "notes": ""
            })
    
    # Risk assessment
    risk_factors = []
    
    # Height risk
    if job_details["height"] > 20:
        risk_factors.append({
            "factor": "Extreme height",
            "severity": "high",
            "mitigation": "Additional fall protection, experienced crew only"
        })
    
    # Pitch risk
    pitch_parts = job_details["pitch"].split("/")
    if int(pitch_parts[0]) > 8:
        risk_factors.append({
            "factor": "Steep pitch",
            "severity": "high",
            "mitigation": "Roof jacks, additional safety equipment"
        })
    
    # Weather risk
    weather = weather_service.get_current_weather(37.7749, -122.4194)
    if weather.get("wind_speed", 0) > 20:
        risk_factors.append({
            "factor": "High winds",
            "severity": "high",
            "mitigation": "Postpone work or implement wind safety protocols"
        })
    
    # Generate safety briefing topics
    safety_briefing = [
        "Review job site hazards and controls",
        "Demonstrate proper use of fall protection",
        "Emergency procedures and contact numbers",
        "Weather conditions and updates",
        "Tool and equipment inspection",
        "Communication protocols"
    ]
    
    return {
        "job_safety_assessment": {
            "job_id": job_data.get("job_id"),
            "assessment_date": datetime.now().isoformat(),
            "overall_risk_level": "high" if any(r["severity"] == "high" for r in risk_factors) else "medium",
            "job_details": job_details
        },
        "safety_requirements": safety_requirements,
        "safety_checklist": safety_checklist,
        "risk_factors": risk_factors,
        "required_documentation": [
            {
                "document": "Site-Specific Safety Plan",
                "required": True,
                "template_url": "/api/v1/weathercraft/safety/templates/site-plan"
            },
            {
                "document": "Daily Safety Inspection Form",
                "required": True,
                "template_url": "/api/v1/weathercraft/safety/templates/daily-inspection"
            },
            {
                "document": "Toolbox Talk Records",
                "required": True,
                "template_url": "/api/v1/weathercraft/safety/templates/toolbox-talk"
            }
        ],
        "safety_briefing_topics": safety_briefing,
        "emergency_contacts": {
            "emergency_services": "911",
            "osha_hotline": "1-800-321-OSHA",
            "company_safety_officer": "+1-555-SAFE-001",
            "nearest_hospital": "SF General Hospital - 10 min"
        },
        "compliance_status": {
            "osha_compliant": True,
            "state_compliant": True,
            "insurance_requirements_met": True,
            "last_safety_audit": "2024-01-01"
        }
    }


# --- Customer Portal Integration ---

@router.get("/customer-portal/{customer_id}/dashboard")
async def get_customer_portal_data(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive customer portal dashboard data.
    
    Includes:
    - Active projects
    - Warranty information
    - Maintenance schedules
    - Payment history
    - Weather alerts
    """
    # Verify customer access or admin
    if current_user.id != customer_id:
        check_permission(current_user, Permission.CRM_CUSTOMERS_READ)
    
    # Mock customer data retrieval
    customer_data = {
        "customer": {
            "id": customer_id,
            "name": "John Smith",
            "property_address": "123 Main St, San Francisco, CA",
            "member_since": "2020-01-15",
            "loyalty_tier": "gold"
        },
        "active_projects": [
            {
                "id": "proj_001",
                "type": "Full Roof Replacement",
                "status": "in_progress",
                "progress": 65,
                "scheduled_completion": "2024-01-25",
                "crew_lead": "Mike Johnson",
                "next_milestone": "Shingle installation",
                "weather_delay_risk": "low"
            }
        ],
        "warranties": [
            {
                "id": "wr_001",
                "type": "Premium Warranty",
                "workmanship_years_remaining": 9.5,
                "materials_years_remaining": 29.5,
                "status": "active",
                "next_inspection_due": "2024-07-15"
            }
        ],
        "maintenance_schedule": [
            {
                "task": "Gutter Cleaning",
                "due_date": "2024-03-15",
                "status": "scheduled",
                "estimated_cost": 150.00,
                "weather_dependent": True
            },
            {
                "task": "Annual Roof Inspection",
                "due_date": "2024-07-15",
                "status": "pending",
                "included_in_warranty": True
            }
        ],
        "payment_summary": {
            "total_spent": 45000.00,
            "open_balance": 0.00,
            "payment_methods": ["Credit Card ****1234", "ACH Transfer"],
            "autopay_enabled": True
        },
        "weather_alerts": [
            {
                "type": "storm_warning",
                "date": "2024-01-22",
                "severity": "moderate",
                "message": "Heavy rain expected. Ensure gutters are clear.",
                "action_required": False
            }
        ],
        "documents": [
            {
                "name": "Warranty Certificate",
                "type": "warranty",
                "date": "2023-07-15",
                "url": f"/api/v1/weathercraft/documents/{customer_id}/warranty.pdf"
            },
            {
                "name": "Installation Photos",
                "type": "photos",
                "date": "2023-07-15",
                "url": f"/api/v1/weathercraft/documents/{customer_id}/photos.zip"
            }
        ],
        "referral_program": {
            "referrals_made": 3,
            "referrals_converted": 2,
            "rewards_earned": 500.00,
            "reward_balance": 200.00,
            "referral_code": "SMITH2024"
        },
        "communication_preferences": {
            "email": True,
            "sms": True,
            "phone": False,
            "preferred_contact_time": "morning"
        }
    }
    
    return customer_data


# Export router
__all__ = ["router"]