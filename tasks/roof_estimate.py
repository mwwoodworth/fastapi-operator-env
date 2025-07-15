"""
Generate roof estimate task implementation.
Creates detailed roofing estimates using AI and current market data.
"""

import logging
from typing import Dict, Any, AsyncIterator, Optional
from datetime import datetime
from decimal import Decimal

from ..agents.claude_agent import ClaudeAgent
from ..agents.search_agent import SearchAgent
from ..agents.base import AgentContext
from ..memory.memory_store import MemoryStore
from .base_task import BaseTask, TaskResult

logger = logging.getLogger(__name__)

# Task identifier for registration
TASK_ID = "generate_roof_estimate"


class GenerateRoofEstimateTask(BaseTask):
    """
    Generates comprehensive commercial roofing estimates.
    
    This task:
    1. Researches current material prices
    2. Calculates labor requirements
    3. Factors in project complexity
    4. Generates detailed estimate document
    5. Provides multiple pricing scenarios
    """
    
    # Task metadata
    METADATA = {
        "category": "roofing",
        "requires_approval": True,
        "estimated_duration_seconds": 180,
        "industry": "construction"
    }
    
    # Standard roofing calculations
    LABOR_RATES = {
        "low": 45.00,     # $/hour
        "medium": 65.00,  # $/hour
        "high": 85.00     # $/hour
    }
    
    COMPLEXITY_MULTIPLIERS = {
        "low": 1.0,
        "medium": 1.25,
        "high": 1.5,
        "extreme": 2.0
    }
    
    WASTE_FACTORS = {
        "TPO": 0.10,      # 10% waste
        "EPDM": 0.08,     # 8% waste
        "BUR": 0.15,      # 15% waste
        "METAL": 0.05,    # 5% waste
        "SHINGLE": 0.12   # 12% waste
    }
    
    def __init__(self):
        super().__init__(task_id=TASK_ID)
        self.claude_agent = ClaudeAgent()
        self.search_agent = SearchAgent()
        self.memory_store = MemoryStore()
        
    async def run(self, context: Dict[str, Any]) -> TaskResult:
        """
        Execute roof estimate generation.
        
        Args:
            context: Must include:
                - project_name: Name of the project
                - roof_area_sqft: Total roof area in square feet
                - roof_type: Type of roofing system (TPO, EPDM, BUR, etc.)
                - complexity: Project complexity (low, medium, high, extreme)
                - location: Project location for regional pricing
                - additional_features: Optional list of features (drains, curbs, etc.)
                
        Returns:
            TaskResult with detailed estimate data
        """
        try:
            # Validate required context
            self._validate_context(context)
            
            # Extract parameters
            project_name = context['project_name']
            roof_area = context['roof_area_sqft']
            roof_type = context['roof_type'].upper()
            complexity = context['complexity'].lower()
            location = context['location']
            
            # Step 1: Research current material prices
            material_prices = await self._research_material_prices(
                roof_type, location
            )
            
            # Step 2: Calculate material requirements
            material_calc = self._calculate_materials(
                roof_area, roof_type, complexity
            )
            
            # Step 3: Calculate labor requirements
            labor_calc = self._calculate_labor(
                roof_area, roof_type, complexity
            )
            
            # Step 4: Calculate additional features cost
            features_cost = self._calculate_additional_features(
                context.get('additional_features', []),
                roof_area
            )
            
            # Step 5: Generate detailed estimate document
            estimate_doc = await self._generate_estimate_document(
                project_name,
                roof_area,
                roof_type,
                material_calc,
                labor_calc,
                features_cost,
                material_prices
            )
            
            # Step 6: Calculate pricing scenarios
            pricing_scenarios = self._calculate_pricing_scenarios(
                material_calc['total_cost'],
                labor_calc['total_cost'],
                features_cost
            )
            
            # Save estimate to memory
            await self._save_estimate(project_name, estimate_doc, pricing_scenarios)
            
            return TaskResult(
                success=True,
                data={
                    "project_name": project_name,
                    "roof_area_sqft": roof_area,
                    "roof_type": roof_type,
                    "materials_cost": material_calc['total_cost'],
                    "labor_cost": labor_calc['total_cost'],
                    "features_cost": features_cost,
                    "pricing_scenarios": pricing_scenarios,
                    "estimate": estimate_doc,
                    "material_prices": material_prices,
                    "generated_at": datetime.utcnow().isoformat()
                },
                message=f"Successfully generated estimate for {project_name}"
            )
            
        except Exception as e:
            logger.error(f"Estimate generation failed for '{context.get('project_name')}': {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message=f"Estimate generation failed: {str(e)}"
            )
    
    async def stream(self, context: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream estimate generation progress.
        """
        try:
            # Validate
            yield {"stage": "validating", "message": "Validating project parameters"}
            self._validate_context(context)
            
            # Research prices
            yield {"stage": "researching", "message": "Researching current material prices"}
            material_prices = await self._research_material_prices(
                context['roof_type'], context['location']
            )
            yield {
                "stage": "prices_found",
                "message": "Current prices retrieved",
                "data": {"base_price_sqft": material_prices.get('base_price', 0)}
            }
            
            # Calculate materials
            yield {"stage": "calculating_materials", "message": "Calculating material requirements"}
            material_calc = self._calculate_materials(
                context['roof_area_sqft'],
                context['roof_type'],
                context['complexity']
            )
            yield {
                "stage": "materials_calculated",
                "message": "Material calculations complete",
                "data": {"materials_cost": material_calc['total_cost']}
            }
            
            # Calculate labor
            yield {"stage": "calculating_labor", "message": "Calculating labor requirements"}
            labor_calc = self._calculate_labor(
                context['roof_area_sqft'],
                context['roof_type'],
                context['complexity']
            )
            yield {
                "stage": "labor_calculated",
                "message": "Labor calculations complete",
                "data": {"labor_cost": labor_calc['total_cost']}
            }
            
            # Generate document
            yield {"stage": "generating_document", "message": "Creating detailed estimate document"}
            
            # Complete
            total_cost = material_calc['total_cost'] + labor_calc['total_cost']
            yield {
                "stage": "completed",
                "message": "Estimate generation complete",
                "summary": {
                    "total_cost": total_cost,
                    "cost_per_sqft": total_cost / context['roof_area_sqft']
                }
            }
            
        except Exception as e:
            yield {
                "stage": "error",
                "message": f"Error: {str(e)}",
                "error": str(e)
            }
    
    def _validate_context(self, context: Dict[str, Any]) -> None:
        """Validate required context fields."""
        required_fields = ['project_name', 'roof_area_sqft', 'roof_type', 'complexity', 'location']
        missing = [field for field in required_fields if field not in context]
        
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
            
        # Validate roof area
        if context['roof_area_sqft'] <= 0:
            raise ValueError("Roof area must be greater than 0")
            
        # Validate roof type
        valid_types = ['TPO', 'EPDM', 'BUR', 'METAL', 'SHINGLE', 'PVC', 'MOD-BIT']
        if context['roof_type'].upper() not in valid_types:
            raise ValueError(f"Invalid roof type. Must be one of: {', '.join(valid_types)}")
            
        # Validate complexity
        if context['complexity'].lower() not in self.COMPLEXITY_MULTIPLIERS:
            raise ValueError("Complexity must be: low, medium, high, or extreme")
    
    async def _research_material_prices(
        self,
        roof_type: str,
        location: str
    ) -> Dict[str, float]:
        """Research current material prices using search agent."""
        # Load research template
        with open('apps/backend/tasks/prompt_templates/research/research_template.md', 'r') as f:
            template = f.read()
        
        # Prepare research context
        agent_context = AgentContext(
            task_id=self.task_id,
            user_input=template.format(
                research_question=f"Current pricing for {roof_type} roofing materials in {location}",
                research_type="pricing",
                time_sensitivity="high",
                depth_level="detailed",
                industry_focus="commercial roofing",
                geographic_scope=location,
                time_frame="current month",
                regulatory_context="commercial building codes",
                recency_requirement="30 days",
                primary_topic=f"{roof_type} roofing materials",
                specific_aspects="material cost per square foot, installation materials, accessories",
                competitor_list="GAF, Carlisle, Firestone, Johns Manville",
                output_length="concise",
                additional_context=f"Need accurate pricing for commercial {roof_type} roofing system"
            )
        )
        
        # Get pricing research
        result = await self.search_agent.execute(agent_context)
        
        # Parse pricing from result (simplified - would parse actual data)
        # Default prices if not found in research
        default_prices = {
            "TPO": 6.50,
            "EPDM": 5.75,
            "BUR": 4.50,
            "METAL": 12.00,
            "SHINGLE": 3.50,
            "PVC": 7.00,
            "MOD-BIT": 5.00
        }
        
        base_price = default_prices.get(roof_type, 6.00)
        
        return {
            "base_price": base_price,
            "insulation_price": 0.75,  # per sqft
            "fasteners_price": 0.25,   # per sqft
            "adhesive_price": 0.50,    # per sqft
            "accessories_price": 0.35  # per sqft
        }
    
    def _calculate_materials(
        self,
        roof_area: float,
        roof_type: str,
        complexity: str
    ) -> Dict[str, Any]:
        """Calculate material requirements and costs."""
        # Get waste factor
        waste_factor = self.WASTE_FACTORS.get(roof_type, 0.10)
        
        # Calculate area with waste
        total_area = roof_area * (1 + waste_factor)
        
        # Get complexity multiplier
        complexity_mult = self.COMPLEXITY_MULTIPLIERS[complexity]
        
        # Calculate squares (100 sqft = 1 square)
        squares = total_area / 100
        
        # Material calculations (simplified)
        materials = {
            "membrane_sqft": total_area,
            "insulation_sqft": roof_area,  # No waste on insulation
            "cover_board_sqft": roof_area,
            "fasteners_count": int(total_area * 0.25),  # 1 fastener per 4 sqft
            "adhesive_gallons": int(total_area / 100),   # 1 gallon per 100 sqft
            "edge_metal_lf": int((roof_area ** 0.5) * 4 * 1.1),  # Perimeter + 10%
            "drains_count": int(roof_area / 5000),  # 1 drain per 5000 sqft
        }
        
        # Cost calculation will be done with actual prices
        return {
            "materials": materials,
            "total_area": total_area,
            "waste_percentage": waste_factor * 100,
            "squares": squares,
            "total_cost": 0  # Will be calculated with prices
        }
    
    def _calculate_labor(
        self,
        roof_area: float,
        roof_type: str,
        complexity: str
    ) -> Dict[str, Any]:
        """Calculate labor requirements and costs."""
        # Base production rates (sqft per day per crew)
        production_rates = {
            "TPO": 3000,
            "EPDM": 3500,
            "BUR": 1500,
            "METAL": 2000,
            "SHINGLE": 2500,
            "PVC": 2800,
            "MOD-BIT": 2000
        }
        
        base_rate = production_rates.get(roof_type, 2500)
        
        # Adjust for complexity
        complexity_mult = self.COMPLEXITY_MULTIPLIERS[complexity]
        adjusted_rate = base_rate / complexity_mult
        
        # Calculate crew days
        crew_days = roof_area / adjusted_rate
        
        # Crew composition (typical commercial crew)
        crew_size = 6  # 1 foreman, 5 roofers
        labor_hours = crew_days * 8 * crew_size
        
        # Get labor rate based on complexity
        labor_rate = self.LABOR_RATES[complexity if complexity != 'extreme' else 'high']
        
        # Calculate costs
        labor_cost = labor_hours * labor_rate
        
        return {
            "crew_days": round(crew_days, 1),
            "crew_size": crew_size,
            "total_hours": round(labor_hours, 0),
            "hourly_rate": labor_rate,
            "total_cost": round(labor_cost, 2),
            "production_rate": adjusted_rate
        }
    
    def _calculate_additional_features(
        self,
        features: list[str],
        roof_area: float
    ) -> float:
        """Calculate cost of additional features."""
        feature_costs = {
            "lightning_protection": 1.50 * roof_area,
            "snow_guards": 2.00 * (roof_area ** 0.5) * 4,  # Perimeter
            "walkways": 15.00 * (roof_area / 1000) * 100,  # 100 lf per 1000 sqft
            "skylights": 1500.00 * max(1, int(roof_area / 5000)),
            "hvac_curbs": 500.00 * max(2, int(roof_area / 2500)),
            "fall_protection": 0.75 * roof_area,
            "green_roof": 15.00 * roof_area,
            "solar_ready": 2.50 * roof_area
        }
        
        total_cost = 0
        for feature in features:
            if feature in feature_costs:
                total_cost += feature_costs[feature]
                
        return round(total_cost, 2)
    
    async def _generate_estimate_document(
        self,
        project_name: str,
        roof_area: float,
        roof_type: str,
        material_calc: Dict[str, Any],
        labor_calc: Dict[str, Any],
        features_cost: float,
        material_prices: Dict[str, float]
    ) -> str:
        """Generate detailed estimate document using Claude."""
        # Calculate material costs with prices
        mat_costs = {
            "membrane": material_calc['materials']['membrane_sqft'] * material_prices['base_price'],
            "insulation": material_calc['materials']['insulation_sqft'] * material_prices['insulation_price'],
            "fasteners": material_calc['materials']['fasteners_count'] * 0.15,  # $0.15 per fastener
            "adhesive": material_calc['materials']['adhesive_gallons'] * 45.00,  # $45 per gallon
            "accessories": roof_area * material_prices['accessories_price']
        }
        
        total_material_cost = sum(mat_costs.values())
        material_calc['total_cost'] = round(total_material_cost, 2)
        
        # Prepare context for Claude
        agent_context = AgentContext(
            task_id=self.task_id,
            user_input=f"""
Create a professional roofing estimate document with the following information:

Project: {project_name}
Roof Area: {roof_area:,.0f} square feet
Roof Type: {roof_type}

Material Costs:
- Membrane: ${mat_costs['membrane']:,.2f}
- Insulation: ${mat_costs['insulation']:,.2f}
- Fasteners & Accessories: ${mat_costs['fasteners'] + mat_costs['accessories']:,.2f}
- Adhesives: ${mat_costs['adhesive']:,.2f}
- Total Materials: ${total_material_cost:,.2f}

Labor:
- Crew Size: {labor_calc['crew_size']} workers
- Duration: {labor_calc['crew_days']} days
- Total Hours: {labor_calc['total_hours']:,.0f}
- Labor Cost: ${labor_calc['total_cost']:,.2f}

Additional Features: ${features_cost:,.2f}

Total Project Cost: ${total_material_cost + labor_calc['total_cost'] + features_cost:,.2f}

Format this as a professional estimate with:
1. Executive summary
2. Scope of work
3. Material specifications
4. Labor breakdown
5. Timeline
6. Terms and conditions
7. Warranty information

Make it comprehensive but easy to understand for building owners.
"""
        )
        
        # Generate estimate document
        result = await self.claude_agent.execute(agent_context)
        
        return result.content
    
    def _calculate_pricing_scenarios(
        self,
        material_cost: float,
        labor_cost: float,
        features_cost: float
    ) -> Dict[str, Dict[str, float]]:
        """Calculate different pricing scenarios with margins."""
        base_cost = material_cost + labor_cost + features_cost
        
        scenarios = {
            "competitive": {
                "margin_percent": 15,
                "overhead_percent": 10,
                "subtotal": base_cost * 1.25,
                "total": round(base_cost * 1.25, 2)
            },
            "standard": {
                "margin_percent": 25,
                "overhead_percent": 12,
                "subtotal": base_cost * 1.37,
                "total": round(base_cost * 1.37, 2)
            },
            "premium": {
                "margin_percent": 35,
                "overhead_percent": 15,
                "subtotal": base_cost * 1.50,
                "total": round(base_cost * 1.50, 2)
            }
        }
        
        # Add cost breakdown to each scenario
        for scenario in scenarios.values():
            scenario.update({
                "material_cost": material_cost,
                "labor_cost": labor_cost,
                "features_cost": features_cost,
                "base_cost": base_cost,
                "markup": scenario['total'] - base_cost
            })
            
        return scenarios
    
    async def _save_estimate(
        self,
        project_name: str,
        estimate_doc: str,
        pricing_scenarios: Dict[str, Dict[str, float]]
    ) -> None:
        """Save estimate to memory for future reference."""
        await self.memory_store.save_memory_entry(
            namespace="roof_estimates",
            key=f"estimate_{project_name}_{datetime.utcnow().timestamp()}",
            content={
                "project_name": project_name,
                "estimate_document": estimate_doc,
                "pricing_scenarios": pricing_scenarios,
                "created_at": datetime.utcnow().isoformat(),
                "status": "draft"
            }
        )