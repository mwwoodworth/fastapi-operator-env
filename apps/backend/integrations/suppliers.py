"""
Supplier integrations for real-time pricing and availability.
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import httpx
from pydantic import BaseModel

class SupplierProduct(BaseModel):
    """Product information from supplier."""
    product_id: str
    name: str
    description: str
    manufacturer: str
    sku: str
    unit_price: Decimal
    available_quantity: int
    lead_time_days: int
    min_order_quantity: int = 1
    bulk_pricing: Optional[Dict[int, Decimal]] = None

class SupplierQuote(BaseModel):
    """Quote from supplier."""
    quote_id: str
    supplier_name: str
    products: List[Dict[str, Any]]
    subtotal: Decimal
    shipping: Decimal
    tax: Decimal
    total: Decimal
    valid_until: datetime
    delivery_date: datetime

class SupplierAPIClient:
    """Integration with supplier systems for real-time pricing."""
    
    def __init__(self):
        self.suppliers = {
            "abc_supply": {
                "name": "ABC Supply",
                "api_base": "https://api.abcsupply.com/v1",
                "api_key": None  # Would be loaded from env
            },
            "beacon": {
                "name": "Beacon Building Products", 
                "api_base": "https://api.beacon.com/v2",
                "api_key": None
            },
            "srs": {
                "name": "SRS Distribution",
                "api_base": "https://api.srsdistribution.com/v1", 
                "api_key": None
            }
        }
        
        # Mock data for demo
        self.mock_inventory = {
            "SHINGLE-ARCH-30": {
                "abc_supply": {"quantity": 500, "price": 92.50},
                "beacon": {"quantity": 350, "price": 94.00},
                "srs": {"quantity": 425, "price": 93.25}
            },
            "UNDERLAYMENT-SYNTH": {
                "abc_supply": {"quantity": 200, "price": 62.00},
                "beacon": {"quantity": 150, "price": 63.50},
                "srs": {"quantity": 175, "price": 62.75}
            }
        }
    
    async def get_product_availability(self, product_id: str) -> Dict[str, Any]:
        """Get real-time availability from all suppliers."""
        # In production, this would make API calls to suppliers
        # For now, return mock data
        
        availability = {}
        
        if product_id in self.mock_inventory:
            for supplier, data in self.mock_inventory[product_id].items():
                availability[supplier] = {
                    "available": data["quantity"] > 0,
                    "quantity": data["quantity"],
                    "price": data["price"],
                    "lead_time_days": 1 if data["quantity"] > 100 else 3
                }
        else:
            # Default availability
            for supplier in self.suppliers:
                availability[supplier] = {
                    "available": True,
                    "quantity": 100,
                    "price": 50.00,
                    "lead_time_days": 2
                }
        
        return {
            "product_id": product_id,
            "timestamp": datetime.utcnow().isoformat(),
            "suppliers": availability
        }
    
    async def get_best_price(self, product_id: str, quantity: int) -> Dict[str, Any]:
        """Find best price across suppliers for given quantity."""
        availability = await self.get_product_availability(product_id)
        
        best_supplier = None
        best_price = None
        best_total = None
        
        for supplier, data in availability["suppliers"].items():
            if data["available"] and data["quantity"] >= quantity:
                # Apply bulk pricing if applicable
                unit_price = Decimal(str(data["price"]))
                
                # Mock bulk discount tiers
                if quantity >= 100:
                    unit_price *= Decimal("0.95")  # 5% discount
                elif quantity >= 50:
                    unit_price *= Decimal("0.97")  # 3% discount
                
                total = unit_price * quantity
                
                if best_price is None or unit_price < best_price:
                    best_supplier = supplier
                    best_price = unit_price
                    best_total = total
        
        if best_supplier:
            return {
                "supplier": best_supplier,
                "unit_price": float(best_price),
                "total_price": float(best_total),
                "quantity": quantity,
                "savings": float((Decimal(str(data["price"])) - best_price) * quantity)
            }
        
        return {
            "error": "No suppliers have sufficient quantity",
            "requested_quantity": quantity
        }
    
    async def create_purchase_order(self, 
                                   supplier: str,
                                   products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create purchase order with supplier."""
        # In production, this would create actual PO via API
        # Mock implementation
        
        po_number = f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        subtotal = Decimal("0")
        items = []
        
        for product in products:
            unit_price = Decimal(str(product["unit_price"]))
            quantity = product["quantity"]
            line_total = unit_price * quantity
            subtotal += line_total
            
            items.append({
                "product_id": product["product_id"],
                "description": product.get("description", ""),
                "quantity": quantity,
                "unit_price": float(unit_price),
                "line_total": float(line_total)
            })
        
        # Calculate shipping (mock)
        shipping = subtotal * Decimal("0.05")  # 5% of subtotal
        tax = subtotal * Decimal("0.08")  # 8% tax
        total = subtotal + shipping + tax
        
        return {
            "po_number": po_number,
            "supplier": supplier,
            "status": "submitted",
            "items": items,
            "subtotal": float(subtotal),
            "shipping": float(shipping),
            "tax": float(tax),
            "total": float(total),
            "created_at": datetime.utcnow().isoformat(),
            "expected_delivery": (datetime.utcnow() + timedelta(days=3)).isoformat()
        }
    
    async def track_order(self, po_number: str) -> Dict[str, Any]:
        """Track purchase order status."""
        # Mock tracking data
        return {
            "po_number": po_number,
            "status": "in_transit",
            "tracking_number": "1Z999AA10123456784",
            "carrier": "UPS",
            "shipped_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
            "expected_delivery": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "current_location": "Distribution Center - Dallas, TX",
            "updates": [
                {
                    "timestamp": (datetime.utcnow() - timedelta(hours=20)).isoformat(),
                    "status": "Order placed",
                    "location": "Supplier Warehouse"
                },
                {
                    "timestamp": (datetime.utcnow() - timedelta(hours=16)).isoformat(),
                    "status": "Order picked and packed",
                    "location": "Supplier Warehouse"
                },
                {
                    "timestamp": (datetime.utcnow() - timedelta(hours=12)).isoformat(),
                    "status": "Shipped",
                    "location": "Supplier Warehouse"
                },
                {
                    "timestamp": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
                    "status": "In transit",
                    "location": "Distribution Center - Dallas, TX"
                }
            ]
        }
    
    async def get_supplier_catalog(self, supplier: str, 
                                  category: Optional[str] = None) -> List[SupplierProduct]:
        """Get product catalog from supplier."""
        # Mock catalog
        catalog = [
            SupplierProduct(
                product_id="SHINGLE-ARCH-30",
                name="Architectural Shingles 30-Year",
                description="Premium architectural shingles with 30-year warranty",
                manufacturer="CertainTeed",
                sku="CT-ARCH-30",
                unit_price=Decimal("92.50"),
                available_quantity=500,
                lead_time_days=1,
                min_order_quantity=1,
                bulk_pricing={
                    10: Decimal("90.00"),
                    50: Decimal("87.50"),
                    100: Decimal("85.00")
                }
            ),
            SupplierProduct(
                product_id="UNDERLAYMENT-SYNTH",
                name="Synthetic Underlayment",
                description="High-performance synthetic roofing underlayment",
                manufacturer="Owens Corning",
                sku="OC-SYNTH-10",
                unit_price=Decimal("62.00"),
                available_quantity=200,
                lead_time_days=1,
                min_order_quantity=1
            ),
            SupplierProduct(
                product_id="ICE-WATER-SHIELD",
                name="Ice & Water Shield",
                description="Self-adhering roofing underlayment",
                manufacturer="Grace",
                sku="GR-IWS-225",
                unit_price=Decimal("95.00"),
                available_quantity=150,
                lead_time_days=2,
                min_order_quantity=1
            )
        ]
        
        if category:
            # Filter by category if provided
            return [p for p in catalog if category.lower() in p.name.lower()]
        
        return catalog
    
    async def get_quote(self, supplier: str, 
                       products: List[Dict[str, Any]],
                       delivery_address: Dict[str, str]) -> SupplierQuote:
        """Get formal quote from supplier."""
        subtotal = Decimal("0")
        quote_items = []
        
        for product in products:
            quantity = product["quantity"]
            # Get current pricing
            catalog = await self.get_supplier_catalog(supplier)
            product_info = next((p for p in catalog if p.product_id == product["product_id"]), None)
            
            if product_info:
                # Apply bulk pricing if available
                unit_price = product_info.unit_price
                if product_info.bulk_pricing:
                    for min_qty, price in sorted(product_info.bulk_pricing.items()):
                        if quantity >= min_qty:
                            unit_price = price
                
                line_total = unit_price * quantity
                subtotal += line_total
                
                quote_items.append({
                    "product_id": product_info.product_id,
                    "name": product_info.name,
                    "quantity": quantity,
                    "unit_price": float(unit_price),
                    "line_total": float(line_total)
                })
        
        # Calculate shipping based on distance (mock)
        base_shipping = Decimal("75.00")
        distance_fee = Decimal("2.00") * 25  # Assume 25 miles
        shipping = base_shipping + distance_fee
        
        # Calculate tax
        tax = subtotal * Decimal("0.0825")
        
        total = subtotal + shipping + tax
        
        return SupplierQuote(
            quote_id=f"Q-{supplier.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            supplier_name=self.suppliers[supplier]["name"],
            products=quote_items,
            subtotal=subtotal,
            shipping=shipping,
            tax=tax,
            total=total,
            valid_until=datetime.utcnow() + timedelta(days=30),
            delivery_date=datetime.utcnow() + timedelta(days=3)
        )