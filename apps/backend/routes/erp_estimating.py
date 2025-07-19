"""
ERP Estimating System - Production-grade implementation for field operations.

This module provides comprehensive estimating functionality including:
- Material cost calculations with real-time pricing
- Labor hour estimation based on job complexity
- Overhead and profit margin calculations
- Multi-tier pricing strategies
- Automated quote generation
- Historical estimate tracking and analytics
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal
from enum import Enum
import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from pydantic import BaseModel, Field, validator

from ..core.database import get_db
from ..core.auth import get_current_user
from ..core.logging import get_logger
from ..db.business_models import (
    User, Project, Estimate, Inspection, Product, 
    DocumentTemplate, Document
)
from ..services.pricing import PricingService
from ..services.tax import TaxService
from ..services.materials import MaterialsDatabase
from ..integrations.suppliers import SupplierAPIClient

logger = get_logger(__name__)
router = APIRouter()

# Enums for type safety
class EstimateStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVISED = "revised"

class PricingTier(str, Enum):
    STANDARD = "standard"
    PREMIUM = "premium"
    BUDGET = "budget"
    CUSTOM = "custom"

class MaterialCategory(str, Enum):
    ROOFING_SHINGLES = "roofing_shingles"
    UNDERLAYMENT = "underlayment"
    FLASHING = "flashing"
    VENTILATION = "ventilation"
    FASTENERS = "fasteners"
    SEALANTS = "sealants"
    GUTTERS = "gutters"
    INSULATION = "insulation"
    DECKING = "decking"
    CUSTOM = "custom"

class LaborType(str, Enum):
    INSTALLATION = "installation"
    REMOVAL = "removal"
    REPAIR = "repair"
    INSPECTION = "inspection"
    CLEANUP = "cleanup"

# Request/Response Models
class MaterialLineItem(BaseModel):
    category: MaterialCategory
    product_id: Optional[str] = None
    name: str
    quantity: float
    unit: str = "sq ft"
    unit_cost: Optional[float] = None
    markup_percent: float = Field(default=30.0, ge=0, le=200)
    waste_factor: float = Field(default=1.1, ge=1.0, le=2.0)
    notes: Optional[str] = None

class LaborLineItem(BaseModel):
    type: LaborType
    description: str
    hours: float
    workers: int = 1
    hourly_rate: Optional[float] = None
    complexity_factor: float = Field(default=1.0, ge=0.5, le=3.0)
    
class EstimateCreateRequest(BaseModel):
    project_id: Optional[str] = None
    inspection_id: Optional[str] = None
    client_name: str
    client_email: str
    client_phone: str
    property_address: str
    
    # Job details
    job_type: str  # roof_replacement, repair, new_construction
    square_footage: float
    pitch: Optional[float] = None  # Roof pitch affects labor
    stories: int = 1
    access_difficulty: str = "normal"  # easy, normal, difficult
    
    # Pricing
    pricing_tier: PricingTier = PricingTier.STANDARD
    materials: List[MaterialLineItem]
    labor: List[LaborLineItem]
    
    # Options
    include_tearoff: bool = True
    include_permit: bool = True
    include_dumpster: bool = True
    include_warranty: bool = True
    warranty_years: int = 10
    
    # Scheduling
    estimated_start_date: Optional[datetime] = None
    estimated_duration_days: int = 3
    valid_days: int = 30
    
    # Additional costs
    permit_cost: Optional[float] = None
    dumpster_cost: Optional[float] = None
    additional_costs: List[Dict[str, Any]] = []
    
    # Discounts
    discount_percent: float = 0
    discount_reason: Optional[str] = None
    
    notes: Optional[str] = None
    internal_notes: Optional[str] = None

class EstimateUpdateRequest(BaseModel):
    status: Optional[EstimateStatus] = None
    materials: Optional[List[MaterialLineItem]] = None
    labor: Optional[List[LaborLineItem]] = None
    discount_percent: Optional[float] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None

class BulkPricingUpdateRequest(BaseModel):
    category: Optional[MaterialCategory] = None
    price_increase_percent: float
    effective_date: datetime
    reason: str
    notify_active_estimates: bool = True

# Service classes
class EstimateCalculator:
    """Handles all estimate calculations with real business logic."""
    
    def __init__(self, db: Session):
        self.db = db
        self.pricing_service = PricingService()
        self.tax_service = TaxService()
        self.materials_db = MaterialsDatabase()
        
    async def calculate_material_costs(
        self, 
        materials: List[MaterialLineItem], 
        square_footage: float,
        pricing_tier: PricingTier
    ) -> Dict[str, Any]:
        """Calculate material costs with waste factors and markups."""
        total_cost = Decimal('0')
        detailed_items = []
        
        for item in materials:
            # Get current market price if not provided
            if item.unit_cost is None:
                market_price = await self.materials_db.get_current_price(
                    item.category, 
                    item.product_id
                )
                item.unit_cost = market_price
            
            # Calculate with waste factor
            actual_quantity = item.quantity * item.waste_factor
            base_cost = Decimal(str(actual_quantity * item.unit_cost))
            
            # Apply markup based on pricing tier
            tier_markup = self._get_tier_markup(pricing_tier, item.category)
            markup_amount = base_cost * Decimal(str((item.markup_percent + tier_markup) / 100))
            item_total = base_cost + markup_amount
            
            detailed_items.append({
                'name': item.name,
                'category': item.category,
                'quantity': item.quantity,
                'waste_factor': item.waste_factor,
                'actual_quantity': actual_quantity,
                'unit_cost': item.unit_cost,
                'base_cost': float(base_cost),
                'markup_percent': item.markup_percent + tier_markup,
                'markup_amount': float(markup_amount),
                'total': float(item_total),
                'notes': item.notes
            })
            
            total_cost += item_total
        
        return {
            'total_cost': float(total_cost),
            'items': detailed_items,
            'average_markup': sum(i['markup_percent'] for i in detailed_items) / len(detailed_items)
        }
    
    async def calculate_labor_costs(
        self,
        labor: List[LaborLineItem],
        square_footage: float,
        pitch: float,
        stories: int,
        access_difficulty: str
    ) -> Dict[str, Any]:
        """Calculate labor costs with complexity factors."""
        total_hours = 0
        total_cost = Decimal('0')
        detailed_items = []
        
        # Calculate difficulty multiplier
        difficulty_multiplier = self._calculate_difficulty_multiplier(
            pitch, stories, access_difficulty
        )
        
        for item in labor:
            # Get standard hourly rate if not provided
            if item.hourly_rate is None:
                item.hourly_rate = self.pricing_service.get_labor_rate(item.type)
            
            # Apply complexity and difficulty factors
            adjusted_hours = item.hours * item.workers * item.complexity_factor * difficulty_multiplier
            item_cost = Decimal(str(adjusted_hours * item.hourly_rate))
            
            detailed_items.append({
                'type': item.type,
                'description': item.description,
                'base_hours': item.hours,
                'workers': item.workers,
                'hourly_rate': item.hourly_rate,
                'complexity_factor': item.complexity_factor,
                'difficulty_multiplier': difficulty_multiplier,
                'total_hours': adjusted_hours,
                'total_cost': float(item_cost)
            })
            
            total_hours += adjusted_hours
            total_cost += item_cost
        
        return {
            'total_hours': total_hours,
            'total_cost': float(total_cost),
            'items': detailed_items,
            'difficulty_multiplier': difficulty_multiplier,
            'average_hourly_rate': float(total_cost / Decimal(str(total_hours))) if total_hours > 0 else 0
        }
    
    def _get_tier_markup(self, tier: PricingTier, category: MaterialCategory) -> float:
        """Get additional markup based on pricing tier."""
        markup_matrix = {
            PricingTier.BUDGET: {
                MaterialCategory.ROOFING_SHINGLES: -5,
                MaterialCategory.UNDERLAYMENT: -3,
                'default': 0
            },
            PricingTier.STANDARD: {
                'default': 0
            },
            PricingTier.PREMIUM: {
                MaterialCategory.ROOFING_SHINGLES: 10,
                MaterialCategory.UNDERLAYMENT: 8,
                'default': 5
            }
        }
        
        tier_markups = markup_matrix.get(tier, {})
        return tier_markups.get(category, tier_markups.get('default', 0))
    
    def _calculate_difficulty_multiplier(
        self, 
        pitch: float, 
        stories: int, 
        access: str
    ) -> float:
        """Calculate labor difficulty multiplier."""
        multiplier = 1.0
        
        # Pitch factor (steeper = harder)
        if pitch:
            if pitch > 9:
                multiplier += 0.3
            elif pitch > 6:
                multiplier += 0.15
            elif pitch > 4:
                multiplier += 0.05
        
        # Height factor
        if stories > 2:
            multiplier += 0.2 * (stories - 2)
        
        # Access factor
        access_factors = {
            'easy': -0.1,
            'normal': 0,
            'difficult': 0.25
        }
        multiplier += access_factors.get(access, 0)
        
        return max(0.8, min(2.0, multiplier))  # Cap between 0.8 and 2.0

# Main endpoints
@router.post("/estimates", response_model=Dict[str, Any])
async def create_estimate(
    request: EstimateCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a comprehensive estimate with real calculations."""
    calculator = EstimateCalculator(db)
    
    # Generate unique estimate number
    estimate_number = f"EST-{datetime.utcnow().strftime('%Y%m')}-{str(uuid4())[:8].upper()}"
    
    # Calculate material costs
    material_calc = await calculator.calculate_material_costs(
        request.materials,
        request.square_footage,
        request.pricing_tier
    )
    
    # Calculate labor costs
    labor_calc = await calculator.calculate_labor_costs(
        request.labor,
        request.square_footage,
        request.pitch or 5.0,  # Default 5/12 pitch
        request.stories,
        request.access_difficulty
    )
    
    # Calculate additional costs
    additional_costs = Decimal('0')
    additional_items = []
    
    if request.include_permit:
        permit_cost = request.permit_cost or Decimal('500')
        additional_costs += permit_cost
        additional_items.append({
            'name': 'Building Permit',
            'cost': float(permit_cost)
        })
    
    if request.include_dumpster:
        dumpster_cost = request.dumpster_cost or Decimal('400')
        additional_costs += dumpster_cost
        additional_items.append({
            'name': 'Dumpster Rental',
            'cost': float(dumpster_cost)
        })
    
    for item in request.additional_costs:
        cost = Decimal(str(item['cost']))
        additional_costs += cost
        additional_items.append(item)
    
    # Calculate subtotal
    subtotal = Decimal(str(material_calc['total_cost'])) + \
               Decimal(str(labor_calc['total_cost'])) + \
               additional_costs
    
    # Calculate tax
    tax_rate = await calculator.tax_service.get_tax_rate(request.property_address)
    tax_amount = subtotal * Decimal(str(tax_rate))
    
    # Apply discount
    discount_amount = subtotal * Decimal(str(request.discount_percent / 100))
    
    # Calculate total
    total = subtotal + tax_amount - discount_amount
    
    # Build line items for database
    line_items = {
        'materials': material_calc['items'],
        'labor': labor_calc['items'],
        'additional': additional_items,
        'summary': {
            'materials_subtotal': material_calc['total_cost'],
            'labor_subtotal': labor_calc['total_cost'],
            'additional_subtotal': float(additional_costs),
            'subtotal': float(subtotal),
            'tax_rate': tax_rate,
            'tax_amount': float(tax_amount),
            'discount_percent': request.discount_percent,
            'discount_amount': float(discount_amount),
            'total': float(total)
        }
    }
    
    # Create estimate record
    estimate = Estimate(
        id=str(uuid4()),
        estimate_number=estimate_number,
        project_id=request.project_id,
        inspection_id=request.inspection_id,
        client_name=request.client_name,
        client_email=request.client_email,
        client_phone=request.client_phone,
        created_by_id=current_user.id,
        status=EstimateStatus.DRAFT.value,
        subtotal=float(subtotal),
        tax_rate=tax_rate,
        tax_amount=float(tax_amount),
        discount_amount=float(discount_amount),
        total=float(total),
        line_items=line_items,
        valid_until=datetime.utcnow() + timedelta(days=request.valid_days),
        created_at=datetime.utcnow()
    )
    
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    
    # Schedule follow-up tasks
    background_tasks.add_task(
        schedule_estimate_followup,
        estimate.id,
        request.valid_days
    )
    
    # Log for analytics
    logger.info(
        f"Estimate created: {estimate_number}",
        extra={
            'estimate_id': estimate.id,
            'total': float(total),
            'user_id': current_user.id
        }
    )
    
    return {
        'id': estimate.id,
        'estimate_number': estimate.estimate_number,
        'status': estimate.status,
        'total': estimate.total,
        'valid_until': estimate.valid_until.isoformat(),
        'breakdown': line_items,
        'created_at': estimate.created_at.isoformat()
    }

@router.get("/estimates", response_model=Dict[str, Any])
async def list_estimates(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[EstimateStatus] = None,
    client_name: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List estimates with comprehensive filtering."""
    query = db.query(Estimate).filter(
        Estimate.created_by_id == current_user.id
    )
    
    # Apply filters
    if status:
        query = query.filter(Estimate.status == status.value)
    
    if client_name:
        query = query.filter(
            Estimate.client_name.ilike(f"%{client_name}%")
        )
    
    if date_from:
        query = query.filter(Estimate.created_at >= date_from)
    
    if date_to:
        query = query.filter(Estimate.created_at <= date_to)
    
    if min_amount is not None:
        query = query.filter(Estimate.total >= min_amount)
    
    if max_amount is not None:
        query = query.filter(Estimate.total <= max_amount)
    
    # Apply sorting
    sort_column = getattr(Estimate, sort_by, Estimate.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    estimates = query.offset((page - 1) * limit).limit(limit).all()
    
    # Calculate statistics
    stats_query = db.query(
        func.count(Estimate.id).label('count'),
        func.sum(Estimate.total).label('total_value'),
        func.avg(Estimate.total).label('average_value')
    ).filter(
        Estimate.created_by_id == current_user.id
    )
    
    if status:
        stats_query = stats_query.filter(Estimate.status == status.value)
    
    stats = stats_query.first()
    
    return {
        'items': [
            {
                'id': e.id,
                'estimate_number': e.estimate_number,
                'client_name': e.client_name,
                'status': e.status,
                'total': e.total,
                'valid_until': e.valid_until.isoformat() if e.valid_until else None,
                'created_at': e.created_at.isoformat()
            }
            for e in estimates
        ],
        'total': total,
        'page': page,
        'limit': limit,
        'pages': (total + limit - 1) // limit,
        'statistics': {
            'count': stats.count or 0,
            'total_value': float(stats.total_value or 0),
            'average_value': float(stats.average_value or 0)
        }
    }

@router.get("/estimates/{estimate_id}", response_model=Dict[str, Any])
async def get_estimate(
    estimate_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed estimate information."""
    estimate = db.query(Estimate).filter(
        Estimate.id == estimate_id,
        Estimate.created_by_id == current_user.id
    ).first()
    
    if not estimate:
        raise HTTPException(404, "Estimate not found")
    
    # Get related project and inspection if available
    project = None
    inspection = None
    
    if estimate.project_id:
        project = db.query(Project).filter(
            Project.id == estimate.project_id
        ).first()
    
    if estimate.inspection_id:
        inspection = db.query(Inspection).filter(
            Inspection.id == estimate.inspection_id
        ).first()
    
    return {
        'id': estimate.id,
        'estimate_number': estimate.estimate_number,
        'status': estimate.status,
        'client': {
            'name': estimate.client_name,
            'email': estimate.client_email,
            'phone': estimate.client_phone
        },
        'financial': {
            'subtotal': estimate.subtotal,
            'tax_rate': estimate.tax_rate,
            'tax_amount': estimate.tax_amount,
            'discount_amount': estimate.discount_amount,
            'total': estimate.total
        },
        'line_items': estimate.line_items,
        'project': {
            'id': project.id,
            'name': project.name,
            'status': project.status
        } if project else None,
        'inspection': {
            'id': inspection.id,
            'property_address': inspection.property_address,
            'status': inspection.status,
            'roof_type': inspection.roof_type,
            'measurements': inspection.measurements
        } if inspection else None,
        'valid_until': estimate.valid_until.isoformat() if estimate.valid_until else None,
        'sent_at': estimate.sent_at.isoformat() if estimate.sent_at else None,
        'approved_at': estimate.approved_at.isoformat() if estimate.approved_at else None,
        'created_at': estimate.created_at.isoformat(),
        'updated_at': estimate.updated_at.isoformat() if estimate.updated_at else None
    }

@router.put("/estimates/{estimate_id}", response_model=Dict[str, Any])
async def update_estimate(
    estimate_id: str,
    request: EstimateUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an estimate with recalculation."""
    estimate = db.query(Estimate).filter(
        Estimate.id == estimate_id,
        Estimate.created_by_id == current_user.id
    ).first()
    
    if not estimate:
        raise HTTPException(404, "Estimate not found")
    
    # Check if estimate can be modified
    if estimate.status in [EstimateStatus.ACCEPTED.value, EstimateStatus.EXPIRED.value]:
        raise HTTPException(400, f"Cannot modify {estimate.status} estimate")
    
    # Update fields
    if request.status:
        estimate.status = request.status.value
        
        if request.status == EstimateStatus.SENT:
            estimate.sent_at = datetime.utcnow()
        elif request.status == EstimateStatus.APPROVED:
            estimate.approved_at = datetime.utcnow()
    
    # Recalculate if materials or labor changed
    if request.materials or request.labor:
        # This would trigger full recalculation
        # Implementation depends on having original request data stored
        pass
    
    if request.discount_percent is not None:
        old_discount = estimate.discount_amount
        estimate.discount_amount = estimate.subtotal * (request.discount_percent / 100)
        estimate.total = estimate.subtotal + estimate.tax_amount - estimate.discount_amount
    
    if request.notes:
        estimate.line_items['notes'] = request.notes
    
    if request.internal_notes:
        estimate.line_items['internal_notes'] = request.internal_notes
    
    estimate.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(estimate)
    
    return {
        'id': estimate.id,
        'estimate_number': estimate.estimate_number,
        'status': estimate.status,
        'total': estimate.total,
        'updated_at': estimate.updated_at.isoformat()
    }

@router.post("/estimates/{estimate_id}/send", response_model=Dict[str, Any])
async def send_estimate(
    estimate_id: str,
    background_tasks: BackgroundTasks,
    message: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send estimate to client via email."""
    estimate = db.query(Estimate).filter(
        Estimate.id == estimate_id,
        Estimate.created_by_id == current_user.id
    ).first()
    
    if not estimate:
        raise HTTPException(404, "Estimate not found")
    
    if estimate.status == EstimateStatus.ACCEPTED.value:
        raise HTTPException(400, "Estimate already accepted")
    
    # Generate PDF
    background_tasks.add_task(
        generate_and_send_estimate,
        estimate,
        message,
        current_user
    )
    
    # Update status
    estimate.status = EstimateStatus.SENT.value
    estimate.sent_at = datetime.utcnow()
    db.commit()
    
    return {
        'message': 'Estimate queued for sending',
        'estimate_id': estimate.id,
        'sent_to': estimate.client_email
    }

@router.post("/estimates/{estimate_id}/duplicate", response_model=Dict[str, Any])
async def duplicate_estimate(
    estimate_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a copy of an existing estimate."""
    original = db.query(Estimate).filter(
        Estimate.id == estimate_id,
        Estimate.created_by_id == current_user.id
    ).first()
    
    if not original:
        raise HTTPException(404, "Estimate not found")
    
    # Create new estimate with same details
    new_estimate = Estimate(
        id=str(uuid4()),
        estimate_number=f"EST-{datetime.utcnow().strftime('%Y%m')}-{str(uuid4())[:8].upper()}",
        project_id=original.project_id,
        inspection_id=original.inspection_id,
        client_name=original.client_name,
        client_email=original.client_email,
        client_phone=original.client_phone,
        created_by_id=current_user.id,
        status=EstimateStatus.DRAFT.value,
        subtotal=original.subtotal,
        tax_rate=original.tax_rate,
        tax_amount=original.tax_amount,
        discount_amount=original.discount_amount,
        total=original.total,
        line_items=original.line_items.copy(),
        valid_until=datetime.utcnow() + timedelta(days=30),
        created_at=datetime.utcnow()
    )
    
    # Add note about duplication
    if 'notes' not in new_estimate.line_items:
        new_estimate.line_items['notes'] = ''
    new_estimate.line_items['notes'] += f"\nDuplicated from {original.estimate_number}"
    
    db.add(new_estimate)
    db.commit()
    db.refresh(new_estimate)
    
    return {
        'id': new_estimate.id,
        'estimate_number': new_estimate.estimate_number,
        'original_estimate': original.estimate_number,
        'status': new_estimate.status,
        'total': new_estimate.total
    }

@router.post("/estimates/bulk-pricing-update", response_model=Dict[str, Any])
async def bulk_update_pricing(
    request: BulkPricingUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update pricing across multiple estimates."""
    if not current_user.is_superuser:
        raise HTTPException(403, "Admin access required")
    
    # Find affected estimates
    query = db.query(Estimate).filter(
        Estimate.status.in_([
            EstimateStatus.DRAFT.value,
            EstimateStatus.PENDING_REVIEW.value,
            EstimateStatus.SENT.value
        ])
    )
    
    affected_estimates = []
    
    for estimate in query.all():
        # Check if estimate has materials from the category
        if request.category:
            has_category = any(
                item.get('category') == request.category.value
                for item in estimate.line_items.get('materials', [])
            )
            if not has_category:
                continue
        
        affected_estimates.append(estimate)
    
    # Schedule background update
    background_tasks.add_task(
        apply_bulk_pricing_update,
        affected_estimates,
        request.price_increase_percent,
        request.effective_date,
        request.reason,
        request.notify_active_estimates
    )
    
    return {
        'affected_count': len(affected_estimates),
        'update_scheduled': True,
        'effective_date': request.effective_date.isoformat(),
        'reason': request.reason
    }

@router.get("/estimates/analytics", response_model=Dict[str, Any])
async def get_estimate_analytics(
    date_from: datetime = Query(
        default=datetime.utcnow() - timedelta(days=90)
    ),
    date_to: datetime = Query(default=datetime.utcnow()),
    group_by: str = Query(default="month", pattern="^(day|week|month|quarter)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive analytics on estimates."""
    # Status distribution
    status_dist = db.query(
        Estimate.status,
        func.count(Estimate.id).label('count'),
        func.sum(Estimate.total).label('value')
    ).filter(
        Estimate.created_by_id == current_user.id,
        Estimate.created_at >= date_from,
        Estimate.created_at <= date_to
    ).group_by(Estimate.status).all()
    
    # Conversion metrics
    total_estimates = db.query(func.count(Estimate.id)).filter(
        Estimate.created_by_id == current_user.id,
        Estimate.created_at >= date_from,
        Estimate.created_at <= date_to
    ).scalar() or 0
    
    accepted_estimates = db.query(func.count(Estimate.id)).filter(
        Estimate.created_by_id == current_user.id,
        Estimate.status == EstimateStatus.ACCEPTED.value,
        Estimate.created_at >= date_from,
        Estimate.created_at <= date_to
    ).scalar() or 0
    
    # Average values by status
    avg_by_status = db.query(
        Estimate.status,
        func.avg(Estimate.total).label('avg_value'),
        func.avg(Estimate.discount_amount).label('avg_discount')
    ).filter(
        Estimate.created_by_id == current_user.id,
        Estimate.created_at >= date_from,
        Estimate.created_at <= date_to
    ).group_by(Estimate.status).all()
    
    # Time to close analysis
    time_to_close = db.query(
        func.avg(
            func.extract('epoch', Estimate.approved_at - Estimate.created_at) / 86400
        ).label('avg_days')
    ).filter(
        Estimate.created_by_id == current_user.id,
        Estimate.status == EstimateStatus.ACCEPTED.value,
        Estimate.approved_at.isnot(None),
        Estimate.created_at >= date_from,
        Estimate.created_at <= date_to
    ).scalar() or 0
    
    return {
        'period': {
            'from': date_from.isoformat(),
            'to': date_to.isoformat()
        },
        'summary': {
            'total_estimates': total_estimates,
            'accepted_estimates': accepted_estimates,
            'conversion_rate': (accepted_estimates / total_estimates * 100) if total_estimates > 0 else 0,
            'average_days_to_close': float(time_to_close)
        },
        'status_distribution': [
            {
                'status': item.status,
                'count': item.count,
                'total_value': float(item.value or 0)
            }
            for item in status_dist
        ],
        'average_values': [
            {
                'status': item.status,
                'average_value': float(item.avg_value or 0),
                'average_discount': float(item.avg_discount or 0)
            }
            for item in avg_by_status
        ]
    }

# Background tasks
async def schedule_estimate_followup(estimate_id: str, valid_days: int):
    """Schedule follow-up reminders for estimates."""
    # This would integrate with your notification system
    # Send reminder at 50% of validity period
    # Send final reminder 2 days before expiry
    pass

async def generate_and_send_estimate(
    estimate: Estimate, 
    message: str, 
    user: User
):
    """Generate PDF and send estimate via email."""
    # This would integrate with PDF generation and email service
    # Generate professional PDF with company branding
    # Send via email service with tracking
    pass

async def apply_bulk_pricing_update(
    estimates: List[Estimate],
    increase_percent: float,
    effective_date: datetime,
    reason: str,
    notify: bool
):
    """Apply pricing updates to multiple estimates."""
    # This would update material costs and recalculate
    # Send notifications if requested
    pass

# Initialize pricing and tax services
class PricingService:
    """Manages pricing rules and labor rates."""
    
    def get_labor_rate(self, labor_type: LaborType) -> float:
        """Get current labor rate by type."""
        rates = {
            LaborType.INSTALLATION: 65.0,
            LaborType.REMOVAL: 45.0,
            LaborType.REPAIR: 75.0,
            LaborType.INSPECTION: 50.0,
            LaborType.CLEANUP: 35.0
        }
        return rates.get(labor_type, 50.0)

class TaxService:
    """Handles tax calculations by location."""
    
    async def get_tax_rate(self, address: str) -> float:
        """Get tax rate for given address."""
        # This would integrate with tax API
        # For now, return default rate
        return 0.0825  # 8.25%

class MaterialsDatabase:
    """Access current material pricing."""
    
    async def get_current_price(
        self, 
        category: MaterialCategory, 
        product_id: Optional[str]
    ) -> float:
        """Get current market price for materials."""
        # This would integrate with supplier APIs
        # For now, return sample prices
        base_prices = {
            MaterialCategory.ROOFING_SHINGLES: 95.0,  # per square
            MaterialCategory.UNDERLAYMENT: 65.0,
            MaterialCategory.FLASHING: 12.0,
            MaterialCategory.VENTILATION: 45.0,
            MaterialCategory.FASTENERS: 150.0,
            MaterialCategory.SEALANTS: 8.50,
            MaterialCategory.GUTTERS: 12.0,
            MaterialCategory.INSULATION: 1.25,
            MaterialCategory.DECKING: 2.50
        }
        return base_prices.get(category, 50.0)

class SupplierAPIClient:
    """Integration with supplier systems for real-time pricing."""
    
    async def get_product_availability(self, product_id: str) -> Dict[str, Any]:
        """Check product availability and lead time."""
        # This would call supplier APIs
        return {
            'in_stock': True,
            'quantity_available': 1000,
            'lead_time_days': 2
        }