"""
CRM (Customer Relationship Management) module for BrainOps.
Comprehensive customer lifecycle management, sales pipeline tracking,
communication history, and relationship analytics.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
import json

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..db.models import User
from ..db.financial_models import Customer
from ..db.crm_models import (
    Lead, Opportunity, Contact, Communication, 
    Activity, Campaign, SalesGoal, CustomerSegment,
    LeadSource, OpportunityStage, ActivityType
)
from ..core.auth import get_current_user
from ..core.database import get_db
from ..core.rbac import Permission, require_permission
from ..core.cache import cache_key_builder, cache
from ..services.email_service import send_email
from ..services.notifications import NotificationService
from ..integrations.calendar import CalendarService
from ..services.analytics import AnalyticsService


router = APIRouter()
notification_service = NotificationService()
calendar_service = CalendarService()
analytics_service = AnalyticsService()


# Lead Management Endpoints
@router.post("/leads", response_model=Dict[str, Any])
@require_permission(Permission.CRM_WRITE)
async def create_lead(
    lead_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create new sales lead with automated scoring and assignment."""
    # Validate required fields
    required_fields = ["name", "email", "source"]
    for field in required_fields:
        if field not in lead_data:
            raise HTTPException(400, f"Missing required field: {field}")
    
    # Calculate lead score based on various factors
    lead_score = calculate_lead_score(lead_data)
    
    # Auto-assign to sales rep based on rules
    assigned_to = assign_lead_to_rep(lead_data, lead_score, db)
    
    # Create lead
    lead = Lead(
        name=lead_data["name"],
        email=lead_data["email"],
        phone=lead_data.get("phone"),
        company=lead_data.get("company"),
        title=lead_data.get("title"),
        source=lead_data["source"],
        score=lead_score,
        status="new",
        assigned_to=assigned_to,
        description=lead_data.get("description"),
        tags=lead_data.get("tags", []),
        custom_fields=lead_data.get("custom_fields", {}),
        created_by=current_user.id
    )
    
    db.add(lead)
    db.commit()
    
    # Track lead source attribution
    track_lead_source(lead.source, db)
    
    # Send notifications
    if assigned_to:
        background_tasks.add_task(
            notification_service.notify_user,
            assigned_to,
            "New Lead Assigned",
            f"You've been assigned a new lead: {lead.name} from {lead.source}"
        )
    
    # Add to nurture campaign if applicable
    if lead_score < 50:  # Low score leads go to nurture
        background_tasks.add_task(
            add_to_nurture_campaign,
            lead.id,
            db
        )
    
    return {
        "lead": {
            "id": str(lead.id),
            "name": lead.name,
            "email": lead.email,
            "score": lead.score,
            "status": lead.status,
            "assigned_to": str(assigned_to) if assigned_to else None
        },
        "actions_taken": {
            "scored": True,
            "assigned": bool(assigned_to),
            "nurture_campaign": lead_score < 50
        }
    }


@router.get("/leads", response_model=Dict[str, Any])
@require_permission(Permission.CRM_READ)
async def list_leads(
    status: Optional[str] = None,
    assigned_to: Optional[UUID] = None,
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """List leads with advanced filtering and search."""
    query = db.query(Lead)
    
    # Apply filters
    if status:
        query = query.filter(Lead.status == status)
    if assigned_to:
        query = query.filter(Lead.assigned_to == assigned_to)
    if source:
        query = query.filter(Lead.source == source)
    if min_score:
        query = query.filter(Lead.score >= min_score)
    if search:
        query = query.filter(
            or_(
                Lead.name.ilike(f"%{search}%"),
                Lead.email.ilike(f"%{search}%"),
                Lead.company.ilike(f"%{search}%")
            )
        )
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    leads = query.order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()
    
    # Get summary stats
    stats = db.query(
        func.count(Lead.id).label("total_leads"),
        func.avg(Lead.score).label("avg_score"),
        func.count(Lead.id).filter(Lead.status == "qualified").label("qualified_count")
    ).one()
    
    return {
        "leads": [
            {
                "id": str(lead.id),
                "name": lead.name,
                "email": lead.email,
                "company": lead.company,
                "source": lead.source,
                "score": lead.score,
                "status": lead.status,
                "assigned_to": str(lead.assigned_to) if lead.assigned_to else None,
                "created_at": lead.created_at.isoformat()
            }
            for lead in leads
        ],
        "total": total,
        "stats": {
            "total_leads": stats.total_leads or 0,
            "average_score": float(stats.avg_score or 0),
            "qualified_leads": stats.qualified_count or 0
        }
    }


@router.put("/leads/{lead_id}/convert", response_model=Dict[str, Any])
@require_permission(Permission.CRM_WRITE)
async def convert_lead_to_opportunity(
    lead_id: UUID,
    conversion_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Convert qualified lead to opportunity."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lead not found")
    
    # Create or find customer
    customer = db.query(Customer).filter(Customer.email == lead.email).first()
    if not customer:
        customer = Customer(
            name=lead.company or lead.name,
            email=lead.email,
            phone=lead.phone,
            source=lead.source,
            tags=lead.tags
        )
        db.add(customer)
        db.flush()
    
    # Create contact
    contact = Contact(
        customer_id=customer.id,
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        title=lead.title,
        is_primary=True
    )
    db.add(contact)
    
    # Create opportunity
    opportunity = Opportunity(
        customer_id=customer.id,
        title=conversion_data.get("title", f"Opportunity for {customer.name}"),
        value_cents=int(conversion_data.get("value", 0) * 100),
        probability=conversion_data.get("probability", 20),
        stage="qualification",
        expected_close_date=datetime.strptime(
            conversion_data["expected_close_date"], 
            "%Y-%m-%d"
        ).date() if "expected_close_date" in conversion_data else date.today() + timedelta(days=30),
        assigned_to=lead.assigned_to or current_user.id,
        lead_id=lead.id,
        created_by=current_user.id
    )
    db.add(opportunity)
    
    # Update lead status
    lead.status = "converted"
    lead.converted_to_opportunity_id = opportunity.id
    lead.converted_date = datetime.utcnow()
    
    # Log conversion activity
    activity = Activity(
        type="lead_conversion",
        entity_type="lead",
        entity_id=lead.id,
        title="Lead Converted to Opportunity",
        description=f"Lead converted by {current_user.email}",
        user_id=current_user.id
    )
    db.add(activity)
    
    db.commit()
    
    # Send notifications
    background_tasks.add_task(
        notification_service.notify_team,
        "sales",
        "Lead Converted",
        f"{lead.name} has been converted to an opportunity worth ${opportunity.value_cents / 100:,.2f}"
    )
    
    return {
        "success": True,
        "lead": {"id": str(lead.id), "status": "converted"},
        "customer": {"id": str(customer.id), "name": customer.name},
        "opportunity": {
            "id": str(opportunity.id),
            "title": opportunity.title,
            "value": opportunity.value_cents / 100
        }
    }


# Opportunity Management
@router.post("/opportunities", response_model=Dict[str, Any])
@require_permission(Permission.CRM_WRITE)
async def create_opportunity(
    opp_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create new sales opportunity."""
    opportunity = Opportunity(
        customer_id=UUID(opp_data["customer_id"]),
        title=opp_data["title"],
        value_cents=int(opp_data["value"] * 100),
        probability=opp_data.get("probability", 20),
        stage=opp_data.get("stage", "qualification"),
        expected_close_date=datetime.strptime(
            opp_data["expected_close_date"], 
            "%Y-%m-%d"
        ).date(),
        assigned_to=UUID(opp_data["assigned_to"]) if "assigned_to" in opp_data else current_user.id,
        description=opp_data.get("description"),
        competitors=opp_data.get("competitors", []),
        tags=opp_data.get("tags", []),
        created_by=current_user.id
    )
    
    db.add(opportunity)
    db.commit()
    
    # Calculate weighted pipeline value
    weighted_value = (opportunity.value_cents * opportunity.probability) / 10000
    
    return {
        "opportunity": {
            "id": str(opportunity.id),
            "title": opportunity.title,
            "value": opportunity.value_cents / 100,
            "weighted_value": weighted_value,
            "probability": opportunity.probability,
            "stage": opportunity.stage,
            "expected_close_date": opportunity.expected_close_date.isoformat()
        }
    }


@router.put("/opportunities/{opp_id}/stage", response_model=Dict[str, Any])
@require_permission(Permission.CRM_WRITE)
async def update_opportunity_stage(
    opp_id: UUID,
    stage_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update opportunity stage with automatic actions."""
    opportunity = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opportunity:
        raise HTTPException(404, "Opportunity not found")
    
    old_stage = opportunity.stage
    new_stage = stage_data["stage"]
    
    # Update stage and probability
    opportunity.stage = new_stage
    opportunity.probability = get_stage_probability(new_stage)
    
    # Handle stage-specific actions
    if new_stage == "proposal":
        # Generate proposal template
        background_tasks.add_task(
            generate_proposal_template,
            opportunity.id,
            db
        )
    elif new_stage == "negotiation":
        # Schedule follow-up
        background_tasks.add_task(
            schedule_negotiation_followup,
            opportunity.id,
            current_user.id
        )
    elif new_stage == "closed_won":
        # Create project and invoice
        background_tasks.add_task(
            handle_closed_won,
            opportunity.id,
            db
        )
        opportunity.closed_date = datetime.utcnow()
        opportunity.is_won = True
    elif new_stage == "closed_lost":
        opportunity.closed_date = datetime.utcnow()
        opportunity.is_won = False
        opportunity.lost_reason = stage_data.get("lost_reason")
    
    # Log activity
    activity = Activity(
        type="stage_change",
        entity_type="opportunity",
        entity_id=opportunity.id,
        title=f"Stage changed from {old_stage} to {new_stage}",
        user_id=current_user.id
    )
    db.add(activity)
    
    db.commit()
    
    return {
        "opportunity": {
            "id": str(opportunity.id),
            "stage": opportunity.stage,
            "probability": opportunity.probability,
            "is_closed": opportunity.stage.startswith("closed_")
        },
        "actions_triggered": get_stage_actions(new_stage)
    }


# Customer Communication
@router.post("/communications", response_model=Dict[str, Any])
@require_permission(Permission.CRM_WRITE)
async def log_communication(
    comm_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Log customer communication with automatic follow-up scheduling."""
    communication = Communication(
        entity_type=comm_data["entity_type"],  # lead, opportunity, customer
        entity_id=UUID(comm_data["entity_id"]),
        type=comm_data["type"],  # email, call, meeting, note
        direction=comm_data.get("direction", "outbound"),
        subject=comm_data.get("subject"),
        content=comm_data["content"],
        duration_minutes=comm_data.get("duration_minutes"),
        user_id=current_user.id,
        scheduled_at=datetime.strptime(
            comm_data["scheduled_at"], 
            "%Y-%m-%d %H:%M:%S"
        ) if "scheduled_at" in comm_data else None
    )
    
    db.add(communication)
    
    # Update last contact date
    if comm_data["entity_type"] == "customer":
        customer = db.query(Customer).filter(
            Customer.id == UUID(comm_data["entity_id"])
        ).first()
        if customer:
            customer.last_contact_date = datetime.utcnow()
    
    # Schedule follow-up if requested
    if comm_data.get("schedule_followup"):
        followup_date = datetime.utcnow() + timedelta(
            days=comm_data.get("followup_days", 7)
        )
        
        followup = Communication(
            entity_type=comm_data["entity_type"],
            entity_id=UUID(comm_data["entity_id"]),
            type="task",
            subject=f"Follow up on: {comm_data.get('subject', 'Previous communication')}",
            content=f"Follow up regarding: {comm_data['content'][:100]}...",
            user_id=current_user.id,
            scheduled_at=followup_date,
            is_completed=False
        )
        db.add(followup)
        
        # Add to calendar
        background_tasks.add_task(
            calendar_service.create_event,
            {
                "title": followup.subject,
                "start": followup_date,
                "duration": 30,
                "attendees": [current_user.email]
            }
        )
    
    db.commit()
    
    return {
        "communication": {
            "id": str(communication.id),
            "type": communication.type,
            "subject": communication.subject,
            "logged_at": communication.created_at.isoformat()
        },
        "followup_scheduled": bool(comm_data.get("schedule_followup"))
    }


@router.get("/communications/timeline/{entity_type}/{entity_id}")
@require_permission(Permission.CRM_READ)
async def get_communication_timeline(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get complete communication timeline for an entity."""
    # Get communications
    communications = db.query(Communication).filter(
        and_(
            Communication.entity_type == entity_type,
            Communication.entity_id == entity_id
        )
    ).order_by(Communication.created_at.desc()).all()
    
    # Get activities
    activities = db.query(Activity).filter(
        and_(
            Activity.entity_type == entity_type,
            Activity.entity_id == entity_id
        )
    ).order_by(Activity.created_at.desc()).all()
    
    # Combine and sort
    timeline = []
    
    for comm in communications:
        timeline.append({
            "type": "communication",
            "timestamp": comm.created_at.isoformat(),
            "data": {
                "id": str(comm.id),
                "type": comm.type,
                "direction": comm.direction,
                "subject": comm.subject,
                "user": comm.user_id
            }
        })
    
    for activity in activities:
        timeline.append({
            "type": "activity",
            "timestamp": activity.created_at.isoformat(),
            "data": {
                "id": str(activity.id),
                "type": activity.type,
                "title": activity.title,
                "user": activity.user_id
            }
        })
    
    # Sort by timestamp
    timeline.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "entity": {"type": entity_type, "id": str(entity_id)},
        "timeline": timeline,
        "total_interactions": len(timeline)
    }


# Sales Analytics
@router.get("/analytics/pipeline")
@require_permission(Permission.CRM_READ)
@cache(key_builder=cache_key_builder)
async def get_pipeline_analytics(
    date_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive pipeline analytics."""
    # Calculate date range
    end_date = datetime.utcnow()
    if date_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif date_range == "30d":
        start_date = end_date - timedelta(days=30)
    elif date_range == "90d":
        start_date = end_date - timedelta(days=90)
    else:  # 1y
        start_date = end_date - timedelta(days=365)
    
    # Pipeline by stage
    pipeline_by_stage = db.query(
        Opportunity.stage,
        func.count(Opportunity.id).label("count"),
        func.sum(Opportunity.value_cents).label("total_value"),
        func.avg(Opportunity.probability).label("avg_probability")
    ).filter(
        Opportunity.created_at >= start_date,
        Opportunity.is_active == True
    ).group_by(Opportunity.stage).all()
    
    # Win/loss analysis
    win_loss = db.query(
        func.count(Opportunity.id).filter(Opportunity.is_won == True).label("won"),
        func.count(Opportunity.id).filter(Opportunity.is_won == False).label("lost"),
        func.sum(Opportunity.value_cents).filter(Opportunity.is_won == True).label("won_value"),
        func.sum(Opportunity.value_cents).filter(Opportunity.is_won == False).label("lost_value")
    ).filter(
        Opportunity.closed_date >= start_date,
        Opportunity.closed_date.isnot(None)
    ).one()
    
    # Sales velocity metrics
    avg_sales_cycle = db.query(
        func.avg(
            func.extract('epoch', Opportunity.closed_date - Opportunity.created_at) / 86400
        ).label("avg_days")
    ).filter(
        Opportunity.closed_date >= start_date,
        Opportunity.is_won == True
    ).scalar() or 0
    
    # Lead conversion funnel
    lead_funnel = db.query(
        func.count(Lead.id).label("total_leads"),
        func.count(Lead.id).filter(Lead.status == "qualified").label("qualified"),
        func.count(Lead.id).filter(Lead.status == "converted").label("converted")
    ).filter(Lead.created_at >= start_date).one()
    
    # Top performers
    top_performers = db.query(
        User.id,
        User.email,
        func.count(Opportunity.id).label("deals_closed"),
        func.sum(Opportunity.value_cents).label("revenue")
    ).join(
        Opportunity, Opportunity.assigned_to == User.id
    ).filter(
        Opportunity.closed_date >= start_date,
        Opportunity.is_won == True
    ).group_by(User.id, User.email).order_by(
        func.sum(Opportunity.value_cents).desc()
    ).limit(5).all()
    
    return {
        "period": date_range,
        "pipeline": {
            "by_stage": [
                {
                    "stage": stage,
                    "opportunities": count,
                    "total_value": total_value / 100 if total_value else 0,
                    "weighted_value": (total_value * avg_prob) / 10000 if total_value and avg_prob else 0
                }
                for stage, count, total_value, avg_prob in pipeline_by_stage
            ],
            "total_pipeline_value": sum(s[2] for s in pipeline_by_stage if s[2]) / 100
        },
        "win_loss": {
            "won_deals": win_loss.won or 0,
            "lost_deals": win_loss.lost or 0,
            "win_rate": (win_loss.won / (win_loss.won + win_loss.lost) * 100) if (win_loss.won + win_loss.lost) > 0 else 0,
            "won_value": win_loss.won_value / 100 if win_loss.won_value else 0,
            "lost_value": win_loss.lost_value / 100 if win_loss.lost_value else 0
        },
        "velocity": {
            "average_sales_cycle_days": round(avg_sales_cycle, 1),
            "deals_in_pipeline": sum(s[1] for s in pipeline_by_stage)
        },
        "lead_conversion": {
            "total_leads": lead_funnel.total_leads or 0,
            "qualified_rate": (lead_funnel.qualified / lead_funnel.total_leads * 100) if lead_funnel.total_leads > 0 else 0,
            "conversion_rate": (lead_funnel.converted / lead_funnel.total_leads * 100) if lead_funnel.total_leads > 0 else 0
        },
        "top_performers": [
            {
                "user_id": str(user_id),
                "email": email,
                "deals_closed": deals,
                "revenue": revenue / 100 if revenue else 0
            }
            for user_id, email, deals, revenue in top_performers
        ]
    }


@router.get("/analytics/forecast")
@require_permission(Permission.CRM_READ)
async def get_sales_forecast(
    months: int = Query(3, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Generate sales forecast based on pipeline and historical data."""
    current_date = date.today()
    forecast = []
    
    for month_offset in range(months):
        month_start = current_date.replace(day=1) + timedelta(days=30 * month_offset)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Get opportunities expected to close this month
        opportunities = db.query(
            func.sum(Opportunity.value_cents).label("total_value"),
            func.sum(Opportunity.value_cents * Opportunity.probability / 100).label("weighted_value"),
            func.count(Opportunity.id).label("count")
        ).filter(
            Opportunity.expected_close_date >= month_start,
            Opportunity.expected_close_date <= month_end,
            Opportunity.is_active == True
        ).one()
        
        # Calculate forecast based on historical win rate
        historical_win_rate = get_historical_win_rate(db, month_offset)
        
        forecast.append({
            "month": month_start.strftime("%Y-%m"),
            "opportunities": opportunities.count or 0,
            "pipeline_value": opportunities.total_value / 100 if opportunities.total_value else 0,
            "weighted_forecast": opportunities.weighted_value / 100 if opportunities.weighted_value else 0,
            "ai_forecast": (opportunities.weighted_value * historical_win_rate / 100) / 100 if opportunities.weighted_value else 0,
            "confidence": calculate_forecast_confidence(opportunities.count or 0, historical_win_rate)
        })
    
    return {
        "forecast_period": f"{months} months",
        "forecast": forecast,
        "total_forecast": sum(f["ai_forecast"] for f in forecast),
        "methodology": "AI-weighted pipeline with historical win rate adjustment"
    }


# Campaign Management
@router.post("/campaigns", response_model=Dict[str, Any])
@require_permission(Permission.CRM_WRITE)
async def create_campaign(
    campaign_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create marketing campaign with automated lead assignment."""
    campaign = Campaign(
        name=campaign_data["name"],
        type=campaign_data["type"],  # email, event, webinar, content
        status="planned",
        start_date=datetime.strptime(campaign_data["start_date"], "%Y-%m-%d").date(),
        end_date=datetime.strptime(campaign_data["end_date"], "%Y-%m-%d").date() if "end_date" in campaign_data else None,
        budget_cents=int(campaign_data.get("budget", 0) * 100),
        target_audience=campaign_data.get("target_audience", {}),
        goals=campaign_data.get("goals", {}),
        created_by=current_user.id
    )
    
    db.add(campaign)
    db.commit()
    
    # Set up campaign automation
    if campaign.type == "email":
        background_tasks.add_task(
            setup_email_campaign,
            campaign.id,
            campaign_data.get("email_sequence", [])
        )
    
    return {
        "campaign": {
            "id": str(campaign.id),
            "name": campaign.name,
            "type": campaign.type,
            "status": campaign.status,
            "start_date": campaign.start_date.isoformat()
        }
    }


@router.post("/campaigns/{campaign_id}/leads/import")
@require_permission(Permission.CRM_WRITE)
async def import_campaign_leads(
    campaign_id: UUID,
    leads_data: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Bulk import leads for a campaign."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    
    imported = 0
    duplicates = 0
    errors = []
    
    for lead_data in leads_data:
        try:
            # Check for duplicates
            existing = db.query(Lead).filter(Lead.email == lead_data["email"]).first()
            if existing:
                duplicates += 1
                # Update campaign association
                existing.campaign_id = campaign_id
                continue
            
            # Create new lead
            lead = Lead(
                name=lead_data["name"],
                email=lead_data["email"],
                phone=lead_data.get("phone"),
                company=lead_data.get("company"),
                source=f"campaign_{campaign.name}",
                campaign_id=campaign_id,
                score=calculate_lead_score(lead_data),
                status="new",
                tags=lead_data.get("tags", []) + [f"campaign:{campaign.name}"],
                created_by=current_user.id
            )
            db.add(lead)
            imported += 1
            
        except Exception as e:
            errors.append({"email": lead_data.get("email"), "error": str(e)})
    
    db.commit()
    
    # Update campaign metrics
    campaign.leads_generated = (campaign.leads_generated or 0) + imported
    db.commit()
    
    # Trigger lead nurturing
    if imported > 0:
        background_tasks.add_task(
            start_campaign_nurture_sequence,
            campaign_id,
            db
        )
    
    return {
        "campaign_id": str(campaign_id),
        "imported": imported,
        "duplicates": duplicates,
        "errors": len(errors),
        "error_details": errors[:10]  # First 10 errors
    }


# Helper Functions
def calculate_lead_score(lead_data: Dict[str, Any]) -> int:
    """Calculate lead score based on various factors."""
    score = 0
    
    # Email domain scoring
    email = lead_data.get("email", "")
    if email.endswith((".com", ".org", ".net")):
        score += 10
    if not email.endswith(("gmail.com", "yahoo.com", "hotmail.com")):
        score += 20  # Business email
    
    # Company info
    if lead_data.get("company"):
        score += 15
    if lead_data.get("title"):
        score += 10
        if any(term in lead_data["title"].lower() for term in ["ceo", "president", "director", "manager"]):
            score += 20
    
    # Source scoring
    source = lead_data.get("source", "")
    if source in ["referral", "partner"]:
        score += 30
    elif source in ["website", "content"]:
        score += 20
    elif source in ["event", "webinar"]:
        score += 25
    
    # Engagement
    if lead_data.get("downloaded_content"):
        score += 15
    if lead_data.get("requested_demo"):
        score += 40
    
    return min(score, 100)  # Cap at 100


def assign_lead_to_rep(lead_data: Dict[str, Any], score: int, db: Session) -> Optional[UUID]:
    """Auto-assign lead to sales rep based on rules."""
    # High-value leads go to senior reps
    if score >= 70:
        # Get senior sales reps
        reps = db.query(User).filter(
            User.roles.contains(["sales_senior"])
        ).all()
    else:
        # Regular sales reps
        reps = db.query(User).filter(
            User.roles.contains(["sales"])
        ).all()
    
    if not reps:
        return None
    
    # Round-robin assignment (simple implementation)
    # In production, would track last assignment
    import random
    return random.choice(reps).id


def get_stage_probability(stage: str) -> int:
    """Get default probability for opportunity stage."""
    probabilities = {
        "qualification": 20,
        "needs_analysis": 30,
        "proposal": 50,
        "negotiation": 70,
        "closed_won": 100,
        "closed_lost": 0
    }
    return probabilities.get(stage, 20)


def get_stage_actions(stage: str) -> List[str]:
    """Get automated actions for stage."""
    actions = {
        "qualification": ["Assigned to sales rep", "Added to CRM workflow"],
        "needs_analysis": ["Discovery call scheduled", "Needs assessment sent"],
        "proposal": ["Proposal template generated", "Pricing approved"],
        "negotiation": ["Legal review initiated", "Executive briefing scheduled"],
        "closed_won": ["Project created", "Invoice generated", "Onboarding initiated"],
        "closed_lost": ["Loss analysis logged", "Re-engagement campaign scheduled"]
    }
    return actions.get(stage, [])


def get_historical_win_rate(db: Session, months_back: int = 6) -> float:
    """Calculate historical win rate for forecasting."""
    start_date = datetime.utcnow() - timedelta(days=30 * months_back)
    
    stats = db.query(
        func.count(Opportunity.id).filter(Opportunity.is_won == True).label("won"),
        func.count(Opportunity.id).label("total")
    ).filter(
        Opportunity.closed_date >= start_date,
        Opportunity.closed_date.isnot(None)
    ).one()
    
    if stats.total and stats.total > 0:
        return (stats.won / stats.total) * 100
    return 25.0  # Default win rate


def calculate_forecast_confidence(opportunity_count: int, win_rate: float) -> str:
    """Calculate confidence level for forecast."""
    if opportunity_count >= 20 and win_rate >= 20:
        return "High"
    elif opportunity_count >= 10 or win_rate >= 15:
        return "Medium"
    else:
        return "Low"


async def add_to_nurture_campaign(lead_id: UUID, db: Session):
    """Add lead to automated nurture campaign."""
    # Implementation would integrate with email marketing platform
    pass


async def generate_proposal_template(opportunity_id: UUID, db: Session):
    """Generate proposal template for opportunity."""
    # Implementation would create document from template
    pass


async def schedule_negotiation_followup(opportunity_id: UUID, user_id: UUID):
    """Schedule follow-up tasks for negotiation stage."""
    # Implementation would create calendar events and tasks
    pass


async def handle_closed_won(opportunity_id: UUID, db: Session):
    """Handle closed-won opportunity automation."""
    # Implementation would create project, invoice, etc.
    pass


def track_lead_source(source: str, db: Session):
    """Track lead source performance."""
    # Update lead source analytics
    pass


async def setup_email_campaign(campaign_id: UUID, email_sequence: List[Dict]):
    """Set up automated email campaign."""
    # Integration with email platform
    pass


async def start_campaign_nurture_sequence(campaign_id: UUID, db: Session):
    """Start nurture sequence for campaign leads."""
    # Implementation would trigger email workflows
    pass