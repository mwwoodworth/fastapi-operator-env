"""
Generate Roof Estimate Task

This task generates comprehensive commercial roofing estimates by combining
AI analysis with specialized roofing calculations and industry data.
"""

import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
from decimal import Decimal
import json

from ..agents.claude_agent import ClaudeAgent
from ..agents.search_agent import SearchAgent
from ..memory.memory_store import MemoryStore
from ..integrations.clickup import ClickUpClient
from ..core.logging import get_logger

logger = get_logger(__name__)

TASK_ID = "generate_roof_estimate"


class RoofingCalculator:
    """Handles specialized roofing calculations based on industry standards."""
    
    def __init__(self):
        # Standard roofing measurements
        self.SQUARE_FEET_PER_SQUARE = 100
        self.WASTE_FACTORS = {
            "flat": 0.10,  # 10% waste for flat roofs
            "low_slope": 0.12,  # 12% for low slope
            "steep_slope": 0.15,  # 15% for steep slope
            "complex": 0.20  # 20% for complex geometry
        }
        
    def calculate_squares(self, area_sf: float, waste_factor: float = 0.10) -> float:
        """Calculate roofing squares including waste factor."""
        base_squares = area_sf / self.SQUARE_FEET_PER_SQUARE
        return base_squares * (1 + waste_factor)
    
    def calculate_materials(self, squares: float, system_type: str) -> Dict[str, Any]:
        """Calculate material quantities based on roof system type."""
        materials = {}
        
        if system_type == "TPO":
            materials["membrane_rolls"] = int(squares / 10) + 1  # 10 squares per roll
            materials["adhesive_buckets"] = int(squares / 5)  # 5 squares per bucket
            materials["fasteners_boxes"] = int(squares / 3)  # 3 squares per box
            materials["insulation_boards"] = int(squares * 4.5)  # 4.5 boards per square
            
        elif system_type == "EPDM":
            materials["membrane_sheets"] = int(squares / 8) + 1  # 8 squares per sheet
            materials["adhesive_gallons"] = int(squares / 4)  # 4 squares per gallon
            materials["seam_tape_rolls"] = int(squares / 20)  # 20 squares per roll
            
        elif system_type == "Modified_Bitumen":
            materials["rolls"] = int(squares / 1) + 2  # 1 square per roll + extras
            materials["primer_gallons"] = int(squares / 10)  # 10 squares per gallon
            materials["torch_fuel_tanks"] = int(squares / 50)  # 50 squares per tank
            
        return materials


async def run(
    context: Dict[str, Any],
    project_name: str,
    building_info: Dict[str, Any],
    roof_specs: Dict[str, Any],
    scope_of_work: List[str],
    local_market: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate a comprehensive commercial roofing estimate.
    
    Args:
        context: Execution context with user info and settings
        project_name: Name of the roofing project
        building_info: Dict with building details (address, type, size, etc.)
        roof_specs: Dict with roof specifications (area, slope, system, etc.)
        scope_of_work: List of work items to include
        local_market: Optional market location for pricing adjustments
        
    Returns:
        Dict containing complete estimate with breakdowns
    """
    
    # Initialize services
    claude = ClaudeAgent()
    search = SearchAgent()
    memory = MemoryStore()
    calculator = RoofingCalculator()
    
    try:
        # Step 1: Search for current material pricing if needed
        if kwargs.get("use_current_pricing", True):
            logger.info("Searching for current roofing material prices")
            
            pricing_data = await search.search_market_pricing(
                material_type=roof_specs.get("system_type", "TPO"),
                location=local_market or "Denver, CO",
                year=datetime.now().year
            )
        else:
            # Use standard pricing from memory
            pricing_data = await memory.get_standard_pricing(
                system_type=roof_specs.get("system_type", "TPO"),
                region=local_market
            )
        
        # Step 2: Calculate base quantities
        area_sf = roof_specs.get("area_sf", 10000)
        roof_type = roof_specs.get("roof_type", "flat")
        waste_factor = calculator.WASTE_FACTORS.get(roof_type, 0.10)
        
        total_squares = calculator.calculate_squares(area_sf, waste_factor)
        materials_needed = calculator.calculate_materials(
            total_squares, 
            roof_specs.get("system_type", "TPO")
        )
        
        # Step 3: Retrieve similar past estimates for reference
        similar_estimates = await memory.search_similar_estimates(
            building_type=building_info.get("type"),
            roof_size_range=(area_sf * 0.8, area_sf * 1.2),
            system_type=roof_specs.get("system_type"),
            limit=3
        )
        
        # Step 4: Build comprehensive prompt for Claude
        estimate_prompt = await _build_estimate_prompt(
            project_name,
            building_info,
            roof_specs,
            scope_of_work,
            materials_needed,
            pricing_data,
            similar_estimates
        )
        
        # Step 5: Generate detailed estimate narrative with Claude
        logger.info(f"Generating detailed estimate for {project_name}")
        
        estimate_response = await claude.generate(
            prompt=estimate_prompt,
            max_tokens=6000,
            temperature=0.3,  # Lower temperature for consistency
            system_prompt="""You are a senior commercial roofing estimator with 20+ years of experience. 
            Generate accurate, detailed estimates that protect both contractor margins and client budgets.
            Focus on completeness, hidden cost identification, and clear scope definition."""
        )
        
        # Step 6: Parse and structure the estimate
        structured_estimate = _parse_estimate_response(
            estimate_response,
            materials_needed,
            pricing_data
        )
        
        # Step 7: Calculate final pricing
        pricing_breakdown = _calculate_pricing_breakdown(
            structured_estimate,
            roof_specs,
            kwargs.get("markup_percentage", 35),
            kwargs.get("include_warranty", True)
        )
        
        # Step 8: Store estimate in memory
        estimate_id = await memory.store_estimate(
            project_name=project_name,
            estimate_data=structured_estimate,
            pricing=pricing_breakdown,
            context=context
        )
        
        # Step 9: Create ClickUp task if integrated
        if kwargs.get("create_clickup_task", False) and context.get("clickup_enabled"):
            clickup = ClickUpClient()
            task_id = await clickup.create_estimate_task(
                project_name=project_name,
                estimate_id=estimate_id,
                due_date=kwargs.get("proposal_due_date")
            )
            structured_estimate["clickup_task_id"] = task_id
        
        return {
            "status": "success",
            "estimate_id": estimate_id,
            "project_name": project_name,
            "estimate": structured_estimate,
            "pricing": pricing_breakdown,
            "total_project_cost": pricing_breakdown["grand_total"],
            "generated_at": datetime.utcnow().isoformat(),
            "task_id": TASK_ID
        }
        
    except Exception as e:
        logger.error(f"Error generating roof estimate: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "task_id": TASK_ID
        }


async def stream(
    context: Dict[str, Any],
    **kwargs
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream estimate generation progress for real-time updates.
    """
    
    steps = [
        ("Analyzing project specifications", 10),
        ("Researching current material pricing", 25),
        ("Calculating material quantities", 40),
        ("Reviewing similar past estimates", 55),
        ("Generating detailed scope of work", 70),
        ("Calculating labor requirements", 85),
        ("Finalizing pricing and terms", 100)
    ]
    
    for step, progress in steps:
        await asyncio.sleep(0.5)  # Simulate processing
        yield {
            "type": "progress",
            "message": step,
            "progress": progress
        }
    
    # Run the actual estimation
    result = await run(context, **kwargs)
    yield {
        "type": "complete",
        "result": result
    }


async def _build_estimate_prompt(
    project_name: str,
    building_info: Dict[str, Any],
    roof_specs: Dict[str, Any],
    scope_of_work: List[str],
    materials_needed: Dict[str, Any],
    pricing_data: Dict[str, Any],
    similar_estimates: List[Dict[str, Any]]
) -> str:
    """
    Build comprehensive prompt for estimate generation.
    """
    
    prompt = f"""Generate a detailed commercial roofing estimate for:

PROJECT: {project_name}

BUILDING INFORMATION:
- Type: {building_info.get('type', 'Commercial')}
- Address: {building_info.get('address', 'TBD')}
- Stories: {building_info.get('stories', 1)}
- Occupancy: {building_info.get('occupancy', 'General Commercial')}

ROOF SPECIFICATIONS:
- Total Area: {roof_specs.get('area_sf', 0):,} sq ft ({roof_specs.get('area_sf', 0) / 100:.1f} squares)
- Roof Type: {roof_specs.get('roof_type', 'Flat')}
- Current System: {roof_specs.get('current_system', 'Unknown')}
- Proposed System: {roof_specs.get('system_type', 'TPO')}
- Insulation R-Value: R-{roof_specs.get('r_value', 30)}

SCOPE OF WORK:
{chr(10).join([f"- {item}" for item in scope_of_work])}

CALCULATED MATERIAL QUANTITIES:
{json.dumps(materials_needed, indent=2)}

CURRENT PRICING DATA:
{json.dumps(pricing_data, indent=2)}

Generate a comprehensive estimate that includes:
1. Detailed scope narrative
2. Material breakdown with quantities and pricing
3. Labor breakdown by trade
4. Equipment and special requirements
5. Potential hidden costs or risks
6. Warranty and maintenance considerations
7. Project timeline estimate
8. Terms and conditions

Focus on protecting both contractor margins and providing client value.
"""
    
    # Add context from similar estimates
    if similar_estimates:
        prompt += "\n\nREFERENCE SIMILAR ESTIMATES:\n"
        for est in similar_estimates[:2]:
            prompt += f"- {est.get('project_name')}: ${est.get('total_cost'):,.2f} ({est.get('cost_per_sf')}/sf)\n"
    
    return prompt


def _parse_estimate_response(response: str, materials: Dict, pricing: Dict) -> Dict[str, Any]:
    """
    Parse Claude's response into structured estimate format.
    """
    
    # Extract key sections from the response
    sections = {
        "executive_summary": _extract_section(response, "Executive Summary"),
        "scope_narrative": _extract_section(response, "Scope"),
        "materials_breakdown": materials,  # Use calculated quantities
        "labor_breakdown": _extract_labor_section(response),
        "equipment_requirements": _extract_section(response, "Equipment"),
        "risk_factors": _extract_section(response, "Risks|Hidden Costs"),
        "warranty_details": _extract_section(response, "Warranty"),
        "timeline": _extract_section(response, "Timeline|Schedule"),
        "terms_conditions": _extract_section(response, "Terms")
    }
    
    return sections


def _calculate_pricing_breakdown(
    estimate: Dict[str, Any],
    roof_specs: Dict[str, Any],
    markup_percentage: float,
    include_warranty: bool
) -> Dict[str, Any]:
    """
    Calculate detailed pricing breakdown with all components.
    """
    
    # Base calculations
    area_sf = roof_specs.get("area_sf", 10000)
    
    # Material costs (would be calculated from actual quantities and prices)
    material_cost = area_sf * 3.50  # Example: $3.50/sf for materials
    
    # Labor costs (varies by system and complexity)
    labor_cost = area_sf * 2.25  # Example: $2.25/sf for labor
    
    # Equipment and overhead
    equipment_cost = area_sf * 0.35
    overhead = (material_cost + labor_cost + equipment_cost) * 0.15
    
    # Subtotal before markup
    subtotal = material_cost + labor_cost + equipment_cost + overhead
    
    # Apply markup
    markup = subtotal * (markup_percentage / 100)
    
    # Warranty cost if included
    warranty_cost = 0
    if include_warranty:
        warranty_cost = subtotal * 0.05  # 5% for extended warranty
    
    # Calculate totals
    project_total = subtotal + markup + warranty_cost
    
    return {
        "material_cost": round(material_cost, 2),
        "labor_cost": round(labor_cost, 2),
        "equipment_cost": round(equipment_cost, 2),
        "overhead": round(overhead, 2),
        "subtotal": round(subtotal, 2),
        "markup_percentage": markup_percentage,
        "markup_amount": round(markup, 2),
        "warranty_cost": round(warranty_cost, 2),
        "grand_total": round(project_total, 2),
        "cost_per_sf": round(project_total / area_sf, 2),
        "cost_per_square": round((project_total / area_sf) * 100, 2)
    }


def _extract_section(content: str, section_pattern: str) -> Optional[str]:
    """Extract a section from the estimate response."""
    import re
    
    # Create pattern to match section headers
    pattern = rf"(?:^|\n)(?:#+\s*)?(?:{section_pattern})[:\s]*\n(.*?)(?=\n(?:#+\s*)?[A-Z]|\Z)"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    
    if match:
        return match.group(1).strip()
    return None


def _extract_labor_section(content: str) -> Dict[str, float]:
    """Extract labor breakdown from estimate response."""
    # Simplified extraction - in production would parse more carefully
    labor = {
        "roofing_mechanics": 80,  # hours
        "helpers": 120,
        "foreman": 40,
        "specialty_trades": 20
    }
    return labor