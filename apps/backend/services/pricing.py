"""
Pricing service for roofing estimates.
"""

from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime

class MaterialCost(BaseModel):
    name: str
    quantity: float
    unit_price: Decimal
    total_price: Decimal

class LaborCost(BaseModel):
    description: str
    hours: float
    rate: Decimal
    total_price: Decimal

class PricingEstimate(BaseModel):
    materials: List[MaterialCost]
    labor: List[LaborCost]
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    overhead_rate: Decimal
    overhead_amount: Decimal
    profit_margin: Decimal
    profit_amount: Decimal
    total: Decimal
    created_at: datetime

class PricingService:
    """Service for calculating roofing project pricing."""
    
    def __init__(self):
        self.default_tax_rate = Decimal("0.08")
        self.default_overhead_rate = Decimal("0.10")
        self.default_profit_margin = Decimal("0.20")
        self.material_prices = {
            "shingles_sq": Decimal("90.00"),
            "underlayment_roll": Decimal("45.00"),
            "ridge_cap_bundle": Decimal("55.00"),
            "nails_box": Decimal("35.00"),
            "flashing_roll": Decimal("65.00"),
            "drip_edge_10ft": Decimal("12.00"),
            "ice_water_shield_roll": Decimal("85.00")
        }
        self.labor_rates = {
            "installer": Decimal("45.00"),
            "lead_installer": Decimal("65.00"),
            "supervisor": Decimal("85.00")
        }
    
    def calculate_material_needs(self, roof_area: float, 
                               pitch: float = 4.0) -> Dict[str, float]:
        """Calculate material quantities needed."""
        # Add waste factor based on pitch
        waste_factor = 1.10 if pitch <= 6 else 1.15
        
        # Calculate squares (100 sq ft units)
        squares = (roof_area / 100) * waste_factor
        
        materials = {
            "shingles_sq": squares,
            "underlayment_roll": squares / 4,  # 400 sq ft per roll
            "ridge_cap_bundle": squares / 20,  # Estimate
            "nails_box": squares / 16,  # 4 boxes per square
            "flashing_roll": 1,  # Standard amount
            "drip_edge_10ft": (roof_area ** 0.5) * 4 / 10,  # Perimeter estimate
            "ice_water_shield_roll": squares / 10  # For valleys/edges
        }
        
        return materials
    
    def calculate_labor_hours(self, roof_area: float, 
                            complexity: str = "standard") -> Dict[str, float]:
        """Calculate labor hours needed."""
        # Base rate: 1 hour per square
        base_hours = roof_area / 100
        
        # Complexity multiplier
        complexity_multipliers = {
            "simple": 0.8,
            "standard": 1.0,
            "complex": 1.3,
            "very_complex": 1.6
        }
        
        multiplier = complexity_multipliers.get(complexity, 1.0)
        total_hours = base_hours * multiplier
        
        # Crew composition
        return {
            "installer": total_hours * 2,  # 2 installers
            "lead_installer": total_hours,
            "supervisor": total_hours * 0.2  # Part time supervision
        }
    
    def generate_estimate(self, 
                         roof_area: float,
                         pitch: float = 4.0,
                         complexity: str = "standard",
                         tax_rate: Optional[Decimal] = None,
                         overhead_rate: Optional[Decimal] = None,
                         profit_margin: Optional[Decimal] = None) -> PricingEstimate:
        """Generate a complete pricing estimate."""
        
        # Use provided rates or defaults
        tax_rate = tax_rate or self.default_tax_rate
        overhead_rate = overhead_rate or self.default_overhead_rate
        profit_margin = profit_margin or self.default_profit_margin
        
        # Calculate materials
        material_needs = self.calculate_material_needs(roof_area, pitch)
        materials = []
        material_total = Decimal("0")
        
        for item, quantity in material_needs.items():
            if quantity > 0:
                unit_price = self.material_prices.get(item, Decimal("0"))
                total_price = unit_price * Decimal(str(quantity))
                materials.append(MaterialCost(
                    name=item.replace("_", " ").title(),
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price
                ))
                material_total += total_price
        
        # Calculate labor
        labor_hours = self.calculate_labor_hours(roof_area, complexity)
        labor_items = []
        labor_total = Decimal("0")
        
        for role, hours in labor_hours.items():
            if hours > 0:
                rate = self.labor_rates.get(role, Decimal("0"))
                total_price = rate * Decimal(str(hours))
                labor_items.append(LaborCost(
                    description=role.replace("_", " ").title(),
                    hours=hours,
                    rate=rate,
                    total_price=total_price
                ))
                labor_total += total_price
        
        # Calculate totals
        subtotal = material_total + labor_total
        tax_amount = subtotal * tax_rate
        overhead_amount = subtotal * overhead_rate
        profit_amount = subtotal * profit_margin
        total = subtotal + tax_amount + overhead_amount + profit_amount
        
        return PricingEstimate(
            materials=materials,
            labor=labor_items,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            overhead_rate=overhead_rate,
            overhead_amount=overhead_amount,
            profit_margin=profit_margin,
            profit_amount=profit_amount,
            total=total,
            created_at=datetime.utcnow()
        )
    
    def adjust_for_location(self, estimate: PricingEstimate, 
                          location_factor: Decimal) -> PricingEstimate:
        """Adjust pricing for geographic location."""
        # Adjust all prices by location factor
        for material in estimate.materials:
            material.unit_price *= location_factor
            material.total_price *= location_factor
        
        for labor in estimate.labor:
            labor.rate *= location_factor
            labor.total_price *= location_factor
        
        # Recalculate totals
        material_total = sum(m.total_price for m in estimate.materials)
        labor_total = sum(l.total_price for l in estimate.labor)
        
        estimate.subtotal = material_total + labor_total
        estimate.tax_amount = estimate.subtotal * estimate.tax_rate
        estimate.overhead_amount = estimate.subtotal * estimate.overhead_rate
        estimate.profit_amount = estimate.subtotal * estimate.profit_margin
        estimate.total = (estimate.subtotal + estimate.tax_amount + 
                         estimate.overhead_amount + estimate.profit_amount)
        
        return estimate