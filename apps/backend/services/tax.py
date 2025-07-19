"""
Tax calculation service.
"""

from decimal import Decimal
from typing import Dict, Optional

class TaxService:
    """Service for tax calculations."""
    
    def __init__(self):
        # Default tax rates by state
        self.state_tax_rates = {
            "AL": Decimal("0.04"),
            "AK": Decimal("0.00"),
            "AZ": Decimal("0.056"),
            "AR": Decimal("0.065"),
            "CA": Decimal("0.0725"),
            "CO": Decimal("0.029"),
            "CT": Decimal("0.0635"),
            "DE": Decimal("0.00"),
            "FL": Decimal("0.06"),
            "GA": Decimal("0.04"),
            "HI": Decimal("0.04"),
            "ID": Decimal("0.06"),
            "IL": Decimal("0.0625"),
            "IN": Decimal("0.07"),
            "IA": Decimal("0.06"),
            "KS": Decimal("0.065"),
            "KY": Decimal("0.06"),
            "LA": Decimal("0.0445"),
            "ME": Decimal("0.055"),
            "MD": Decimal("0.06"),
            "MA": Decimal("0.0625"),
            "MI": Decimal("0.06"),
            "MN": Decimal("0.06875"),
            "MS": Decimal("0.07"),
            "MO": Decimal("0.04225"),
            "MT": Decimal("0.00"),
            "NE": Decimal("0.055"),
            "NV": Decimal("0.0685"),
            "NH": Decimal("0.00"),
            "NJ": Decimal("0.06625"),
            "NM": Decimal("0.05125"),
            "NY": Decimal("0.04"),
            "NC": Decimal("0.0475"),
            "ND": Decimal("0.05"),
            "OH": Decimal("0.0575"),
            "OK": Decimal("0.045"),
            "OR": Decimal("0.00"),
            "PA": Decimal("0.06"),
            "RI": Decimal("0.07"),
            "SC": Decimal("0.06"),
            "SD": Decimal("0.045"),
            "TN": Decimal("0.07"),
            "TX": Decimal("0.0625"),
            "UT": Decimal("0.0485"),
            "VT": Decimal("0.06"),
            "VA": Decimal("0.043"),
            "WA": Decimal("0.065"),
            "WV": Decimal("0.06"),
            "WI": Decimal("0.05"),
            "WY": Decimal("0.04"),
            "DC": Decimal("0.06")
        }
    
    def get_tax_rate(self, state: str, county: Optional[str] = None, 
                     city: Optional[str] = None) -> Decimal:
        """Get combined tax rate for a location."""
        # Base state rate
        state_rate = self.state_tax_rates.get(state.upper(), Decimal("0.06"))
        
        # Add estimated local rates (simplified)
        local_rate = Decimal("0")
        if county:
            local_rate += Decimal("0.01")  # County tax estimate
        if city:
            local_rate += Decimal("0.005")  # City tax estimate
        
        return state_rate + local_rate
    
    def calculate_tax(self, amount: Decimal, state: str, 
                     county: Optional[str] = None, 
                     city: Optional[str] = None) -> Dict[str, Decimal]:
        """Calculate tax for an amount."""
        tax_rate = self.get_tax_rate(state, county, city)
        tax_amount = amount * tax_rate
        
        return {
            "subtotal": amount,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total": amount + tax_amount
        }
    
    def is_tax_exempt(self, item_type: str) -> bool:
        """Check if an item type is tax exempt."""
        exempt_types = [
            "labor",
            "service",
            "consultation",
            "design"
        ]
        return item_type.lower() in exempt_types
    
    def calculate_itemized_tax(self, items: list, state: str,
                              county: Optional[str] = None,
                              city: Optional[str] = None) -> Dict[str, Decimal]:
        """Calculate tax for itemized list."""
        taxable_total = Decimal("0")
        exempt_total = Decimal("0")
        
        for item in items:
            if self.is_tax_exempt(item.get("type", "")):
                exempt_total += Decimal(str(item.get("amount", 0)))
            else:
                taxable_total += Decimal(str(item.get("amount", 0)))
        
        tax_rate = self.get_tax_rate(state, county, city)
        tax_amount = taxable_total * tax_rate
        
        return {
            "taxable_amount": taxable_total,
            "exempt_amount": exempt_total,
            "subtotal": taxable_total + exempt_total,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total": taxable_total + exempt_total + tax_amount
        }