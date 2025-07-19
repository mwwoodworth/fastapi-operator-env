"""
Materials service for roofing project materials management.
"""

from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel
from enum import Enum

class MaterialType(str, Enum):
    SHINGLES = "shingles"
    UNDERLAYMENT = "underlayment"
    FLASHING = "flashing"
    RIDGE_CAP = "ridge_cap"
    STARTER_STRIP = "starter_strip"
    NAILS = "nails"
    CEMENT = "cement"
    SEALANT = "sealant"
    VENTILATION = "ventilation"
    ICE_WATER_SHIELD = "ice_water_shield"
    DRIP_EDGE = "drip_edge"
    OTHER = "other"

class MaterialUnit(str, Enum):
    SQUARE = "square"  # 100 sq ft
    BUNDLE = "bundle"
    ROLL = "roll"
    BOX = "box"
    GALLON = "gallon"
    TUBE = "tube"
    PIECE = "piece"
    LINEAR_FOOT = "linear_foot"

class Material(BaseModel):
    id: str
    name: str
    type: MaterialType
    manufacturer: str
    sku: Optional[str] = None
    unit: MaterialUnit
    coverage: Optional[float] = None  # Coverage per unit
    price_per_unit: Decimal
    weight_per_unit: Optional[float] = None  # In pounds
    color: Optional[str] = None
    warranty_years: Optional[int] = None
    in_stock: bool = True
    min_order_quantity: int = 1

class MaterialOrder(BaseModel):
    material_id: str
    quantity: float
    unit_price: Decimal
    total_price: Decimal
    notes: Optional[str] = None

class MaterialsService:
    """Service for managing roofing materials."""
    
    def __init__(self):
        # Initialize with common roofing materials
        self.materials_catalog = {
            "shingles_arch_30": Material(
                id="shingles_arch_30",
                name="Architectural Shingles 30-Year",
                type=MaterialType.SHINGLES,
                manufacturer="CertainTeed",
                sku="CT-ARCH-30",
                unit=MaterialUnit.SQUARE,
                coverage=100.0,
                price_per_unit=Decimal("95.00"),
                weight_per_unit=240.0,
                warranty_years=30,
                in_stock=True
            ),
            "shingles_arch_50": Material(
                id="shingles_arch_50",
                name="Architectural Shingles 50-Year",
                type=MaterialType.SHINGLES,
                manufacturer="GAF",
                sku="GAF-TIMB-50",
                unit=MaterialUnit.SQUARE,
                coverage=100.0,
                price_per_unit=Decimal("125.00"),
                weight_per_unit=280.0,
                warranty_years=50,
                in_stock=True
            ),
            "underlayment_synthetic": Material(
                id="underlayment_synthetic",
                name="Synthetic Underlayment",
                type=MaterialType.UNDERLAYMENT,
                manufacturer="Owens Corning",
                sku="OC-SYNTH-10",
                unit=MaterialUnit.ROLL,
                coverage=1000.0,  # 10 squares per roll
                price_per_unit=Decimal("65.00"),
                weight_per_unit=25.0,
                in_stock=True
            ),
            "ice_water_shield": Material(
                id="ice_water_shield",
                name="Ice & Water Shield",
                type=MaterialType.ICE_WATER_SHIELD,
                manufacturer="Grace",
                sku="GR-IWS-225",
                unit=MaterialUnit.ROLL,
                coverage=225.0,  # 2.25 squares per roll
                price_per_unit=Decimal("95.00"),
                weight_per_unit=60.0,
                in_stock=True
            ),
            "ridge_cap": Material(
                id="ridge_cap",
                name="Ridge Cap Shingles",
                type=MaterialType.RIDGE_CAP,
                manufacturer="CertainTeed",
                sku="CT-RIDGE-20",
                unit=MaterialUnit.BUNDLE,
                coverage=20.0,  # 20 linear feet per bundle
                price_per_unit=Decimal("45.00"),
                weight_per_unit=35.0,
                in_stock=True
            ),
            "drip_edge": Material(
                id="drip_edge",
                name="Aluminum Drip Edge",
                type=MaterialType.DRIP_EDGE,
                manufacturer="Amerimax",
                sku="AM-DRIP-10",
                unit=MaterialUnit.PIECE,
                coverage=10.0,  # 10 linear feet per piece
                price_per_unit=Decimal("12.50"),
                weight_per_unit=5.0,
                color="White",
                in_stock=True
            ),
            "roofing_nails": Material(
                id="roofing_nails",
                name="Roofing Nails 1.25\"",
                type=MaterialType.NAILS,
                manufacturer="Grip-Rite",
                sku="GR-NAIL-50",
                unit=MaterialUnit.BOX,
                coverage=None,  # About 7200 nails per 50lb box
                price_per_unit=Decimal("35.00"),
                weight_per_unit=50.0,
                in_stock=True
            ),
            "roof_cement": Material(
                id="roof_cement",
                name="Roofing Cement",
                type=MaterialType.CEMENT,
                manufacturer="Henry",
                sku="HE-208-5G",
                unit=MaterialUnit.GALLON,
                coverage=None,
                price_per_unit=Decimal("25.00"),
                weight_per_unit=40.0,
                in_stock=True
            )
        }
    
    def get_material(self, material_id: str) -> Optional[Material]:
        """Get material details by ID."""
        return self.materials_catalog.get(material_id)
    
    def search_materials(self, 
                        material_type: Optional[MaterialType] = None,
                        manufacturer: Optional[str] = None,
                        max_price: Optional[Decimal] = None) -> List[Material]:
        """Search materials by criteria."""
        results = []
        
        for material in self.materials_catalog.values():
            if material_type and material.type != material_type:
                continue
            if manufacturer and material.manufacturer.lower() != manufacturer.lower():
                continue
            if max_price and material.price_per_unit > max_price:
                continue
            results.append(material)
        
        return results
    
    def calculate_material_needs(self, 
                               roof_area: float,
                               roof_type: str = "gable",
                               complexity: str = "standard") -> List[MaterialOrder]:
        """Calculate materials needed for a roofing project."""
        orders = []
        
        # Calculate shingles needed (add 10% waste)
        shingle_squares = (roof_area / 100) * 1.10
        
        # Default to 30-year architectural shingles
        shingle_material = self.materials_catalog["shingles_arch_30"]
        orders.append(MaterialOrder(
            material_id=shingle_material.id,
            quantity=shingle_squares,
            unit_price=shingle_material.price_per_unit,
            total_price=shingle_material.price_per_unit * Decimal(str(shingle_squares))
        ))
        
        # Underlayment (full coverage)
        underlayment = self.materials_catalog["underlayment_synthetic"]
        underlayment_rolls = roof_area / underlayment.coverage
        orders.append(MaterialOrder(
            material_id=underlayment.id,
            quantity=underlayment_rolls,
            unit_price=underlayment.price_per_unit,
            total_price=underlayment.price_per_unit * Decimal(str(underlayment_rolls))
        ))
        
        # Ice & Water Shield (for valleys and edges - estimate 10% of area)
        ice_shield = self.materials_catalog["ice_water_shield"]
        ice_shield_area = roof_area * 0.10
        ice_shield_rolls = ice_shield_area / ice_shield.coverage
        orders.append(MaterialOrder(
            material_id=ice_shield.id,
            quantity=ice_shield_rolls,
            unit_price=ice_shield.price_per_unit,
            total_price=ice_shield.price_per_unit * Decimal(str(ice_shield_rolls))
        ))
        
        # Ridge cap (estimate based on roof type)
        ridge_multipliers = {
            "gable": 1.0,
            "hip": 1.5,
            "complex": 2.0
        }
        ridge_multiplier = ridge_multipliers.get(roof_type, 1.0)
        ridge_length = (roof_area ** 0.5) * ridge_multiplier
        
        ridge_cap = self.materials_catalog["ridge_cap"]
        ridge_bundles = ridge_length / ridge_cap.coverage
        orders.append(MaterialOrder(
            material_id=ridge_cap.id,
            quantity=ridge_bundles,
            unit_price=ridge_cap.price_per_unit,
            total_price=ridge_cap.price_per_unit * Decimal(str(ridge_bundles))
        ))
        
        # Drip edge (perimeter estimate)
        perimeter = (roof_area ** 0.5) * 4  # Rough estimate
        drip_edge = self.materials_catalog["drip_edge"]
        drip_edge_pieces = perimeter / drip_edge.coverage
        orders.append(MaterialOrder(
            material_id=drip_edge.id,
            quantity=drip_edge_pieces,
            unit_price=drip_edge.price_per_unit,
            total_price=drip_edge.price_per_unit * Decimal(str(drip_edge_pieces))
        ))
        
        # Nails (1 box per 3 squares)
        nails = self.materials_catalog["roofing_nails"]
        nail_boxes = shingle_squares / 3
        orders.append(MaterialOrder(
            material_id=nails.id,
            quantity=nail_boxes,
            unit_price=nails.price_per_unit,
            total_price=nails.price_per_unit * Decimal(str(nail_boxes))
        ))
        
        # Roof cement (1 gallon per 10 squares)
        cement = self.materials_catalog["roof_cement"]
        cement_gallons = shingle_squares / 10
        orders.append(MaterialOrder(
            material_id=cement.id,
            quantity=cement_gallons,
            unit_price=cement.price_per_unit,
            total_price=cement.price_per_unit * Decimal(str(cement_gallons))
        ))
        
        return orders
    
    def get_material_weight(self, orders: List[MaterialOrder]) -> float:
        """Calculate total weight of materials."""
        total_weight = 0.0
        
        for order in orders:
            material = self.get_material(order.material_id)
            if material and material.weight_per_unit:
                total_weight += material.weight_per_unit * order.quantity
        
        return total_weight
    
    def check_availability(self, orders: List[MaterialOrder]) -> Dict[str, bool]:
        """Check if all materials are available."""
        availability = {}
        
        for order in orders:
            material = self.get_material(order.material_id)
            if material:
                availability[material.name] = material.in_stock
            else:
                availability[order.material_id] = False
        
        return availability
    
    def get_delivery_estimate(self, total_weight: float, 
                            distance_miles: float) -> Dict[str, any]:
        """Estimate delivery cost and time."""
        # Base delivery fee
        base_fee = Decimal("75.00")
        
        # Weight-based fee (per 1000 lbs)
        weight_fee = Decimal(str(total_weight / 1000)) * Decimal("25.00")
        
        # Distance fee ($2 per mile over 25 miles)
        distance_fee = Decimal("0")
        if distance_miles > 25:
            distance_fee = Decimal(str(distance_miles - 25)) * Decimal("2.00")
        
        total_delivery_cost = base_fee + weight_fee + distance_fee
        
        # Estimate delivery time (1-3 days based on distance)
        if distance_miles <= 50:
            delivery_days = 1
        elif distance_miles <= 150:
            delivery_days = 2
        else:
            delivery_days = 3
        
        return {
            "base_fee": base_fee,
            "weight_fee": weight_fee,
            "distance_fee": distance_fee,
            "total_cost": total_delivery_cost,
            "estimated_days": delivery_days,
            "total_weight_lbs": total_weight
        }

# Alias for backward compatibility
MaterialsDatabase = MaterialsService