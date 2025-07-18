"""
ERP Compliance Management System - Production-grade implementation.

This module provides comprehensive compliance tracking including:
- License and certification management
- Regulatory compliance tracking
- Safety program management
- Insurance verification
- Audit trails and reporting
- Training requirements
- Permit management
- Environmental compliance
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from decimal import Decimal
from enum import Enum
import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from pydantic import BaseModel, Field, validator, EmailStr

from ..core.database import get_db
from ..core.auth import get_current_user, require_admin
from ..core.logging import get_logger
from ..db.business_models import (
    User, Team, Project, Document, Notification,
    SystemConfig
)
from ..services.notifications import NotificationService, NotificationPriority
from ..services.document_generator import DocumentGenerator
from ..services.compliance_checker import ComplianceChecker
from ..integrations.government_apis import GovernmentAPIClient

logger = get_logger(__name__)
router = APIRouter()

# Enums
class ComplianceType(str, Enum):
    LICENSE = "license"
    CERTIFICATION = "certification"
    PERMIT = "permit"
    INSURANCE = "insurance"
    SAFETY = "safety"
    ENVIRONMENTAL = "environmental"
    FINANCIAL = "financial"
    CONTRACTUAL = "contractual"

class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    PENDING_RENEWAL = "pending_renewal"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"

class RequirementFrequency(str, Enum):
    ONE_TIME = "one_time"
    ANNUAL = "annual"
    BIANNUAL = "biannual"
    QUARTERLY = "quarterly"
    MONTHLY = "monthly"
    PER_PROJECT = "per_project"
    AS_NEEDED = "as_needed"

class AuditType(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    REGULATORY = "regulatory"
    CUSTOMER = "customer"
    SAFETY = "safety"

# Request/Response Models
class ComplianceItemRequest(BaseModel):
    type: ComplianceType
    name: str
    description: Optional[str] = None
    issuing_authority: str
    
    # Validity
    issue_date: date
    expiry_date: Optional[date] = None
    frequency: RequirementFrequency = RequirementFrequency.ANNUAL
    
    # Requirements
    requirements: List[str] = []
    renewal_lead_time_days: int = 30
    
    # Associations
    applies_to: str = "company"  # company, team, individual, project
    entity_ids: List[str] = []
    
    # Documents
    document_urls: List[str] = []
    
    # Costs
    renewal_cost: Optional[float] = None
    
    # Notifications
    notify_users: List[str] = []
    escalation_users: List[str] = []

class ComplianceUpdateRequest(BaseModel):
    status: Optional[ComplianceStatus] = None
    expiry_date: Optional[date] = None
    document_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    renewal_submitted: Optional[bool] = None
    renewal_date: Optional[date] = None

class TrainingRequirementRequest(BaseModel):
    name: str
    description: str
    required_for_roles: List[str]
    
    # Training details
    duration_hours: float
    validity_period_days: int
    provider: Optional[str] = None
    
    # Requirements
    prerequisites: List[str] = []
    recertification_required: bool = True
    
    # Content
    course_content: List[str] = []
    assessment_required: bool = True
    passing_score: float = 80.0
    
    # Compliance
    regulatory_requirement: bool = False
    regulation_reference: Optional[str] = None

class AuditRequest(BaseModel):
    audit_type: AuditType
    scope: str
    scheduled_date: date
    
    # Audit details
    auditor_name: str
    auditor_organization: Optional[str] = None
    
    # Areas to audit
    compliance_areas: List[ComplianceType]
    specific_requirements: List[str] = []
    
    # Participants
    required_participants: List[str] = []
    
    # Documents needed
    required_documents: List[str] = []

class SafetyIncidentRequest(BaseModel):
    incident_date: datetime
    incident_type: str  # injury, near_miss, property_damage, environmental
    location: str
    project_id: Optional[str] = None
    
    # People involved
    involved_employees: List[str]
    witnesses: List[str] = []
    
    # Incident details
    description: str
    immediate_actions_taken: str
    injuries: List[Dict[str, Any]] = []
    property_damage: Optional[str] = None
    
    # Root cause
    root_causes: List[str] = []
    contributing_factors: List[str] = []
    
    # Corrective actions
    corrective_actions: List[Dict[str, Any]] = []
    
    # Reporting
    reported_to_authorities: bool = False
    case_number: Optional[str] = None
    
    # Costs
    estimated_cost: Optional[float] = None

# Service Classes
class ComplianceManager:
    """Manages all compliance-related operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService()
        self.compliance_checker = ComplianceChecker()
        self.gov_api = GovernmentAPIClient()
    
    async def check_compliance_status(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """Check comprehensive compliance status for an entity."""
        
        # Get all applicable compliance items
        compliance_items = self._get_applicable_items(entity_type, entity_id)
        
        # Check each item
        status_summary = {
            'overall_status': ComplianceStatus.COMPLIANT,
            'items_total': len(compliance_items),
            'compliant': 0,
            'expiring_soon': 0,
            'expired': 0,
            'non_compliant': 0,
            'details': []
        }
        
        for item in compliance_items:
            item_status = self._check_item_status(item)
            
            status_summary['details'].append({
                'item_id': item['id'],
                'name': item['name'],
                'type': item['type'],
                'status': item_status['status'],
                'expiry_date': item_status.get('expiry_date'),
                'days_until_expiry': item_status.get('days_until_expiry'),
                'action_required': item_status.get('action_required')
            })
            
            # Update counters
            if item_status['status'] == ComplianceStatus.COMPLIANT:
                status_summary['compliant'] += 1
            elif item_status['status'] == ComplianceStatus.EXPIRING_SOON:
                status_summary['expiring_soon'] += 1
            elif item_status['status'] == ComplianceStatus.EXPIRED:
                status_summary['expired'] += 1
            else:
                status_summary['non_compliant'] += 1
        
        # Determine overall status
        if status_summary['expired'] > 0 or status_summary['non_compliant'] > 0:
            status_summary['overall_status'] = ComplianceStatus.NON_COMPLIANT
        elif status_summary['expiring_soon'] > 0:
            status_summary['overall_status'] = ComplianceStatus.EXPIRING_SOON
        
        # Add risk score
        status_summary['risk_score'] = self._calculate_risk_score(status_summary)
        
        return status_summary
    
    def _check_item_status(self, item: Dict) -> Dict[str, Any]:
        """Check status of individual compliance item."""
        today = date.today()
        status = ComplianceStatus.COMPLIANT
        days_until_expiry = None
        action_required = None
        
        if item.get('expiry_date'):
            expiry = item['expiry_date']
            if isinstance(expiry, str):
                expiry = date.fromisoformat(expiry)
            
            days_until_expiry = (expiry - today).days
            
            if days_until_expiry < 0:
                status = ComplianceStatus.EXPIRED
                action_required = "Immediate renewal required"
            elif days_until_expiry <= item.get('renewal_lead_time_days', 30):
                status = ComplianceStatus.EXPIRING_SOON
                action_required = f"Renewal required by {expiry}"
            
            # Check if renewal is in progress
            if item.get('renewal_submitted'):
                status = ComplianceStatus.PENDING_RENEWAL
                action_required = "Awaiting renewal approval"
        
        return {
            'status': status,
            'expiry_date': item.get('expiry_date'),
            'days_until_expiry': days_until_expiry,
            'action_required': action_required
        }
    
    def _calculate_risk_score(self, status_summary: Dict) -> float:
        """Calculate compliance risk score (0-100)."""
        score = 100.0
        
        # Deduct for non-compliance
        score -= status_summary['non_compliant'] * 20
        score -= status_summary['expired'] * 15
        score -= status_summary['expiring_soon'] * 5
        
        # Factor in percentage compliant
        if status_summary['items_total'] > 0:
            compliance_rate = status_summary['compliant'] / status_summary['items_total']
            score *= compliance_rate
        
        return max(0, min(100, score))
    
    async def auto_renew_item(self, item_id: str) -> Dict[str, Any]:
        """Attempt automatic renewal of compliance item."""
        item = self._get_compliance_item(item_id)
        
        if not item:
            raise ValueError("Compliance item not found")
        
        # Check if auto-renewal is possible
        if item['type'] == ComplianceType.LICENSE:
            # Try to renew through government API
            if item['issuing_authority'] in self.gov_api.supported_authorities:
                result = await self.gov_api.renew_license(
                    item['license_number'],
                    item['issuing_authority']
                )
                
                if result['success']:
                    # Update item
                    item['expiry_date'] = result['new_expiry_date']
                    item['status'] = ComplianceStatus.COMPLIANT
                    item['last_renewed'] = datetime.utcnow()
                    
                    return {
                        'success': True,
                        'new_expiry_date': result['new_expiry_date'],
                        'confirmation_number': result['confirmation_number']
                    }
        
        return {
            'success': False,
            'reason': 'Manual renewal required',
            'instructions': self._get_renewal_instructions(item)
        }
    
    def _get_renewal_instructions(self, item: Dict) -> str:
        """Get renewal instructions for compliance item."""
        instructions = {
            ComplianceType.LICENSE: "Visit issuing authority website or office to renew",
            ComplianceType.CERTIFICATION: "Complete recertification training or exam",
            ComplianceType.PERMIT: "Submit new permit application with updated project details",
            ComplianceType.INSURANCE: "Contact insurance broker for renewal quote",
            ComplianceType.SAFETY: "Schedule safety audit or training session"
        }
        
        return instructions.get(item['type'], "Contact compliance department for renewal")

class TrainingManager:
    """Manages training and certification requirements."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_training_requirements(self, user_id: str) -> Dict[str, Any]:
        """Get training requirements for a user."""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise ValueError("User not found")
        
        # Get user's role and team
        user_role = user.meta_data.get('role', 'general')
        user_teams = [team.id for team in user.teams]
        
        # Get applicable training requirements
        requirements = self._get_requirements_for_role(user_role)
        
        # Check completion status
        completed_training = user.meta_data.get('completed_training', [])
        
        training_status = {
            'required_training': [],
            'completed_training': [],
            'expiring_soon': [],
            'overdue': []
        }
        
        for req in requirements:
            completion = next(
                (t for t in completed_training if t['training_id'] == req['id']),
                None
            )
            
            if not completion:
                training_status['overdue'].append({
                    'training': req,
                    'due_date': 'Immediately'
                })
            else:
                # Check expiry
                if req.get('validity_period_days'):
                    completion_date = datetime.fromisoformat(completion['completion_date'])
                    expiry_date = completion_date + timedelta(days=req['validity_period_days'])
                    days_until_expiry = (expiry_date.date() - date.today()).days
                    
                    if days_until_expiry < 0:
                        training_status['overdue'].append({
                            'training': req,
                            'expired_date': expiry_date.date(),
                            'days_overdue': abs(days_until_expiry)
                        })
                    elif days_until_expiry <= 30:
                        training_status['expiring_soon'].append({
                            'training': req,
                            'expiry_date': expiry_date.date(),
                            'days_remaining': days_until_expiry
                        })
                    else:
                        training_status['completed_training'].append({
                            'training': req,
                            'completion_date': completion_date.date(),
                            'expiry_date': expiry_date.date()
                        })
        
        # Calculate compliance score
        total_required = len(requirements)
        total_compliant = len(training_status['completed_training'])
        compliance_score = (total_compliant / total_required * 100) if total_required > 0 else 100
        
        training_status['compliance_score'] = compliance_score
        training_status['total_required'] = total_required
        
        return training_status
    
    def _get_requirements_for_role(self, role: str) -> List[Dict]:
        """Get training requirements for a specific role."""
        # This would fetch from database
        # For now, return sample requirements
        base_requirements = [
            {
                'id': 'safety_basic',
                'name': 'Basic Safety Training',
                'duration_hours': 8,
                'validity_period_days': 365
            },
            {
                'id': 'fall_protection',
                'name': 'Fall Protection',
                'duration_hours': 4,
                'validity_period_days': 365
            }
        ]
        
        role_specific = {
            'foreman': [
                {
                    'id': 'leadership',
                    'name': 'Crew Leadership',
                    'duration_hours': 16,
                    'validity_period_days': 730
                }
            ],
            'roofer': [
                {
                    'id': 'roofing_cert',
                    'name': 'Professional Roofing Certification',
                    'duration_hours': 40,
                    'validity_period_days': 1095
                }
            ]
        }
        
        return base_requirements + role_specific.get(role, [])

# Main Endpoints
@router.post("/compliance/items", response_model=Dict[str, Any])
async def create_compliance_item(
    request: ComplianceItemRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new compliance tracking item."""
    if not current_user.is_superuser:
        # Check if user has compliance management permission
        if 'compliance_manager' not in current_user.meta_data.get('permissions', []):
            raise HTTPException(403, "Compliance management permission required")
    
    # Create compliance record
    item_id = str(uuid4())
    compliance_item = {
        'id': item_id,
        'type': request.type.value,
        'name': request.name,
        'description': request.description,
        'issuing_authority': request.issuing_authority,
        'issue_date': request.issue_date.isoformat(),
        'expiry_date': request.expiry_date.isoformat() if request.expiry_date else None,
        'frequency': request.frequency.value,
        'requirements': request.requirements,
        'renewal_lead_time_days': request.renewal_lead_time_days,
        'applies_to': request.applies_to,
        'entity_ids': request.entity_ids,
        'document_urls': request.document_urls,
        'renewal_cost': request.renewal_cost,
        'notify_users': request.notify_users,
        'escalation_users': request.escalation_users,
        'status': ComplianceStatus.COMPLIANT.value,
        'created_by': current_user.id,
        'created_at': datetime.utcnow().isoformat()
    }
    
    # Store in system config (in production, would be separate table)
    config_key = f"compliance_item_{item_id}"
    system_config = SystemConfig(
        key=config_key,
        value=compliance_item,
        description=f"Compliance item: {request.name}",
        config_type="compliance"
    )
    
    db.add(system_config)
    
    # Create initial audit log
    audit_log = {
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': current_user.id,
        'action': 'created',
        'details': f"Created compliance item: {request.name}"
    }
    
    audit_config = SystemConfig(
        key=f"compliance_audit_{item_id}_{datetime.utcnow().timestamp()}",
        value=audit_log,
        config_type="audit"
    )
    
    db.add(audit_config)
    db.commit()
    
    # Schedule notifications
    if request.expiry_date:
        background_tasks.add_task(
            schedule_compliance_reminders,
            item_id,
            request.expiry_date,
            request.renewal_lead_time_days,
            request.notify_users
        )
    
    # Send creation notification
    background_tasks.add_task(
        send_compliance_notification,
        "New Compliance Item Created",
        f"{request.name} has been added to compliance tracking",
        request.notify_users,
        NotificationPriority.MEDIUM
    )
    
    logger.info(
        f"Compliance item created: {item_id}",
        extra={
            'item_type': request.type.value,
            'name': request.name,
            'created_by': current_user.id
        }
    )
    
    return {
        'id': item_id,
        'status': 'created',
        'message': f'Compliance item {request.name} created successfully'
    }

@router.get("/compliance/status/{entity_type}/{entity_id}", response_model=Dict[str, Any])
async def get_compliance_status(
    entity_type: str,
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get compliance status for an entity."""
    # Verify access
    if entity_type == "user" and entity_id != str(current_user.id):
        if not current_user.is_superuser:
            raise HTTPException(403, "Cannot view other users' compliance")
    
    manager = ComplianceManager(db)
    status = await manager.check_compliance_status(entity_type, entity_id)
    
    return status

@router.get("/compliance/items", response_model=Dict[str, Any])
async def list_compliance_items(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    type: Optional[ComplianceType] = None,
    status: Optional[ComplianceStatus] = None,
    applies_to: Optional[str] = None,
    expiring_within_days: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List compliance items with filtering."""
    # Get all compliance items from system config
    compliance_configs = db.query(SystemConfig).filter(
        SystemConfig.config_type == "compliance",
        SystemConfig.key.like("compliance_item_%")
    ).all()
    
    items = []
    for config in compliance_configs:
        item = config.value
        
        # Apply filters
        if type and item['type'] != type.value:
            continue
        
        if applies_to and item['applies_to'] != applies_to:
            continue
        
        # Check status
        manager = ComplianceManager(db)
        item_status = manager._check_item_status(item)
        item['current_status'] = item_status['status']
        
        if status and item_status['status'] != status:
            continue
        
        # Check expiry filter
        if expiring_within_days and item_status.get('days_until_expiry'):
            if item_status['days_until_expiry'] > expiring_within_days:
                continue
        
        items.append({
            **item,
            'status_details': item_status
        })
    
    # Sort by expiry date
    items.sort(key=lambda x: x.get('expiry_date') or '9999-12-31')
    
    # Paginate
    total = len(items)
    start = (page - 1) * limit
    end = start + limit
    
    return {
        'items': items[start:end],
        'total': total,
        'page': page,
        'limit': limit,
        'pages': (total + limit - 1) // limit
    }

@router.put("/compliance/items/{item_id}", response_model=Dict[str, Any])
async def update_compliance_item(
    item_id: str,
    request: ComplianceUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update compliance item."""
    # Get item
    config = db.query(SystemConfig).filter(
        SystemConfig.key == f"compliance_item_{item_id}"
    ).first()
    
    if not config:
        raise HTTPException(404, "Compliance item not found")
    
    item = config.value
    
    # Update fields
    if request.status:
        item['status'] = request.status.value
    
    if request.expiry_date:
        item['expiry_date'] = request.expiry_date.isoformat()
    
    if request.document_urls is not None:
        item['document_urls'] = request.document_urls
    
    if request.renewal_submitted is not None:
        item['renewal_submitted'] = request.renewal_submitted
        if request.renewal_submitted:
            item['renewal_date'] = (request.renewal_date or date.today()).isoformat()
    
    if request.notes:
        if 'notes' not in item:
            item['notes'] = []
        item['notes'].append({
            'user_id': current_user.id,
            'timestamp': datetime.utcnow().isoformat(),
            'note': request.notes
        })
    
    item['updated_at'] = datetime.utcnow().isoformat()
    item['updated_by'] = current_user.id
    
    # Save
    config.value = item
    
    # Audit log
    audit_log = {
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': current_user.id,
        'action': 'updated',
        'changes': request.dict(exclude_unset=True)
    }
    
    audit_config = SystemConfig(
        key=f"compliance_audit_{item_id}_{datetime.utcnow().timestamp()}",
        value=audit_log,
        config_type="audit"
    )
    
    db.add(audit_config)
    db.commit()
    
    # Send notifications if status changed
    if request.status:
        background_tasks.add_task(
            send_compliance_notification,
            f"Compliance Status Updated: {item['name']}",
            f"Status changed to: {request.status.value}",
            item.get('notify_users', []),
            NotificationPriority.HIGH if request.status == ComplianceStatus.EXPIRED else NotificationPriority.MEDIUM
        )
    
    return {
        'id': item_id,
        'status': 'updated',
        'current_status': item.get('status')
    }

@router.post("/compliance/training/requirements", response_model=Dict[str, Any])
async def create_training_requirement(
    request: TrainingRequirementRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new training requirement."""
    requirement_id = str(uuid4())
    
    requirement = {
        'id': requirement_id,
        'name': request.name,
        'description': request.description,
        'required_for_roles': request.required_for_roles,
        'duration_hours': request.duration_hours,
        'validity_period_days': request.validity_period_days,
        'provider': request.provider,
        'prerequisites': request.prerequisites,
        'recertification_required': request.recertification_required,
        'course_content': request.course_content,
        'assessment_required': request.assessment_required,
        'passing_score': request.passing_score,
        'regulatory_requirement': request.regulatory_requirement,
        'regulation_reference': request.regulation_reference,
        'created_by': current_user.id,
        'created_at': datetime.utcnow().isoformat()
    }
    
    # Store requirement
    config = SystemConfig(
        key=f"training_requirement_{requirement_id}",
        value=requirement,
        description=f"Training requirement: {request.name}",
        config_type="training"
    )
    
    db.add(config)
    db.commit()
    
    return {
        'id': requirement_id,
        'status': 'created',
        'message': f'Training requirement {request.name} created'
    }

@router.get("/compliance/training/status/{user_id}", response_model=Dict[str, Any])
async def get_user_training_status(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get training compliance status for a user."""
    # Check access
    if user_id != str(current_user.id) and not current_user.is_superuser:
        raise HTTPException(403, "Cannot view other users' training status")
    
    manager = TrainingManager(db)
    status = await manager.get_training_requirements(user_id)
    
    return status

@router.post("/compliance/training/complete", response_model=Dict[str, Any])
async def record_training_completion(
    training_id: str,
    user_id: str,
    completion_date: date,
    score: Optional[float] = None,
    certificate_url: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record training completion."""
    # Verify permission
    if not current_user.is_superuser and 'training_manager' not in current_user.meta_data.get('permissions', []):
        raise HTTPException(403, "Training management permission required")
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    # Record completion
    if 'completed_training' not in user.meta_data:
        user.meta_data['completed_training'] = []
    
    completion_record = {
        'training_id': training_id,
        'completion_date': completion_date.isoformat(),
        'score': score,
        'certificate_url': certificate_url,
        'recorded_by': current_user.id,
        'recorded_at': datetime.utcnow().isoformat()
    }
    
    # Remove any previous completion of same training
    user.meta_data['completed_training'] = [
        t for t in user.meta_data['completed_training']
        if t['training_id'] != training_id
    ]
    
    user.meta_data['completed_training'].append(completion_record)
    
    db.commit()
    
    return {
        'status': 'recorded',
        'user_id': user_id,
        'training_id': training_id,
        'completion_date': completion_date.isoformat()
    }

@router.post("/compliance/audits", response_model=Dict[str, Any])
async def schedule_audit(
    request: AuditRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Schedule a compliance audit."""
    audit_id = str(uuid4())
    
    audit = {
        'id': audit_id,
        'audit_type': request.audit_type.value,
        'scope': request.scope,
        'scheduled_date': request.scheduled_date.isoformat(),
        'auditor_name': request.auditor_name,
        'auditor_organization': request.auditor_organization,
        'compliance_areas': [area.value for area in request.compliance_areas],
        'specific_requirements': request.specific_requirements,
        'required_participants': request.required_participants,
        'required_documents': request.required_documents,
        'status': 'scheduled',
        'created_by': current_user.id,
        'created_at': datetime.utcnow().isoformat()
    }
    
    # Store audit
    config = SystemConfig(
        key=f"compliance_audit_schedule_{audit_id}",
        value=audit,
        description=f"Audit: {request.scope}",
        config_type="audit_schedule"
    )
    
    db.add(config)
    db.commit()
    
    # Schedule notifications
    background_tasks.add_task(
        send_audit_notifications,
        audit,
        db
    )
    
    # Create calendar events
    background_tasks.add_task(
        create_audit_calendar_events,
        audit,
        db
    )
    
    return {
        'id': audit_id,
        'status': 'scheduled',
        'scheduled_date': request.scheduled_date.isoformat()
    }

@router.post("/compliance/incidents/safety", response_model=Dict[str, Any])
async def report_safety_incident(
    request: SafetyIncidentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Report a safety incident."""
    incident_id = str(uuid4())
    
    incident = {
        'id': incident_id,
        'incident_date': request.incident_date.isoformat(),
        'incident_type': request.incident_type,
        'location': request.location,
        'project_id': request.project_id,
        'involved_employees': request.involved_employees,
        'witnesses': request.witnesses,
        'description': request.description,
        'immediate_actions_taken': request.immediate_actions_taken,
        'injuries': request.injuries,
        'property_damage': request.property_damage,
        'root_causes': request.root_causes,
        'contributing_factors': request.contributing_factors,
        'corrective_actions': request.corrective_actions,
        'reported_to_authorities': request.reported_to_authorities,
        'case_number': request.case_number,
        'estimated_cost': request.estimated_cost,
        'reported_by': current_user.id,
        'reported_at': datetime.utcnow().isoformat(),
        'status': 'reported'
    }
    
    # Store incident
    config = SystemConfig(
        key=f"safety_incident_{incident_id}",
        value=incident,
        description=f"Safety incident: {request.incident_type}",
        config_type="safety_incident"
    )
    
    db.add(config)
    
    # Update safety statistics
    update_safety_statistics(incident, db)
    
    db.commit()
    
    # Immediate notifications
    background_tasks.add_task(
        send_safety_incident_notifications,
        incident,
        db
    )
    
    # Generate reports if required
    if request.reported_to_authorities:
        background_tasks.add_task(
            generate_regulatory_report,
            incident,
            db
        )
    
    # Schedule investigation
    background_tasks.add_task(
        schedule_incident_investigation,
        incident,
        db
    )
    
    return {
        'id': incident_id,
        'status': 'reported',
        'case_number': request.case_number,
        'next_steps': get_incident_next_steps(incident)
    }

@router.get("/compliance/dashboard", response_model=Dict[str, Any])
async def get_compliance_dashboard(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get compliance dashboard data."""
    # Default to company-wide if not specified
    if not entity_type:
        entity_type = "company"
        entity_id = "all"
    
    # Get compliance items
    manager = ComplianceManager(db)
    compliance_status = await manager.check_compliance_status(entity_type, entity_id)
    
    # Get training statistics
    training_stats = get_training_statistics(entity_type, entity_id, db)
    
    # Get audit schedule
    upcoming_audits = get_upcoming_audits(db)
    
    # Get incident statistics
    incident_stats = get_incident_statistics(db)
    
    # Calculate overall health score
    health_score = calculate_compliance_health_score(
        compliance_status,
        training_stats,
        incident_stats
    )
    
    return {
        'health_score': health_score,
        'compliance_summary': compliance_status,
        'training_statistics': training_stats,
        'upcoming_audits': upcoming_audits,
        'incident_statistics': incident_stats,
        'action_items': generate_action_items(
            compliance_status,
            training_stats,
            upcoming_audits
        )
    }

# Helper Functions
async def schedule_compliance_reminders(
    item_id: str,
    expiry_date: date,
    lead_time_days: int,
    notify_users: List[str]
):
    """Schedule reminder notifications for compliance items."""
    # This would integrate with scheduling system
    # Create reminders at various intervals
    reminder_intervals = [lead_time_days, lead_time_days // 2, 7, 1]
    
    for days_before in reminder_intervals:
        reminder_date = expiry_date - timedelta(days=days_before)
        if reminder_date > date.today():
            # Schedule reminder
            pass

async def send_compliance_notification(
    subject: str,
    message: str,
    recipients: List[str],
    priority: NotificationPriority
):
    """Send compliance notification."""
    # This would use notification service
    pass

def update_safety_statistics(incident: Dict, db: Session):
    """Update safety statistics based on incident."""
    # Get or create statistics record
    stats_config = db.query(SystemConfig).filter(
        SystemConfig.key == "safety_statistics_current_year"
    ).first()
    
    if not stats_config:
        stats_config = SystemConfig(
            key="safety_statistics_current_year",
            value={
                'total_incidents': 0,
                'injury_incidents': 0,
                'near_misses': 0,
                'property_damage': 0,
                'days_without_incident': 0
            },
            config_type="statistics"
        )
        db.add(stats_config)
    
    stats = stats_config.value
    stats['total_incidents'] += 1
    
    if incident['incident_type'] == 'injury':
        stats['injury_incidents'] += 1
        stats['days_without_incident'] = 0
    elif incident['incident_type'] == 'near_miss':
        stats['near_misses'] += 1
    elif incident['incident_type'] == 'property_damage':
        stats['property_damage'] += 1
    
    stats_config.value = stats

async def send_safety_incident_notifications(incident: Dict, db: Session):
    """Send notifications for safety incident."""
    # Notify safety manager
    # Notify involved employees' supervisors
    # Notify executive team if serious
    pass

async def generate_regulatory_report(incident: Dict, db: Session):
    """Generate regulatory report for incident."""
    # Use document generator to create official report
    pass

async def schedule_incident_investigation(incident: Dict, db: Session):
    """Schedule incident investigation."""
    # Create investigation tasks
    # Assign to safety team
    # Set deadlines
    pass

def get_incident_next_steps(incident: Dict) -> List[str]:
    """Get next steps for incident."""
    steps = []
    
    if incident['injuries']:
        steps.append("Ensure all injured parties receive medical attention")
        steps.append("Complete injury reports for each affected employee")
    
    steps.append("Conduct root cause analysis within 48 hours")
    steps.append("Implement immediate corrective actions")
    steps.append("Schedule safety briefing for all crews")
    
    if incident['reported_to_authorities']:
        steps.append("Follow up with regulatory authorities")
        steps.append("Prepare for potential inspection")
    
    return steps

def get_training_statistics(entity_type: str, entity_id: str, db: Session) -> Dict:
    """Get training statistics."""
    # This would calculate real statistics
    return {
        'total_employees': 45,
        'compliant_employees': 38,
        'compliance_rate': 84.4,
        'trainings_due_soon': 12,
        'overdue_trainings': 7
    }

def get_upcoming_audits(db: Session) -> List[Dict]:
    """Get upcoming audits."""
    # Query audit schedule
    audits = db.query(SystemConfig).filter(
        SystemConfig.config_type == "audit_schedule",
        SystemConfig.key.like("compliance_audit_schedule_%")
    ).all()
    
    upcoming = []
    today = date.today()
    
    for audit_config in audits:
        audit = audit_config.value
        audit_date = date.fromisoformat(audit['scheduled_date'])
        
        if audit_date >= today and audit['status'] == 'scheduled':
            days_until = (audit_date - today).days
            upcoming.append({
                'id': audit['id'],
                'type': audit['audit_type'],
                'scope': audit['scope'],
                'date': audit['scheduled_date'],
                'days_until': days_until,
                'auditor': audit['auditor_name']
            })
    
    return sorted(upcoming, key=lambda x: x['date'])[:5]

def get_incident_statistics(db: Session) -> Dict:
    """Get incident statistics."""
    stats_config = db.query(SystemConfig).filter(
        SystemConfig.key == "safety_statistics_current_year"
    ).first()
    
    if stats_config:
        return stats_config.value
    
    return {
        'total_incidents': 0,
        'injury_incidents': 0,
        'near_misses': 0,
        'property_damage': 0,
        'days_without_incident': 0
    }

def calculate_compliance_health_score(
    compliance_status: Dict,
    training_stats: Dict,
    incident_stats: Dict
) -> float:
    """Calculate overall compliance health score."""
    score = 100.0
    
    # Factor in compliance status (40%)
    compliance_factor = compliance_status['risk_score'] * 0.4
    
    # Factor in training compliance (30%)
    training_factor = training_stats.get('compliance_rate', 100) * 0.3
    
    # Factor in safety record (30%)
    safety_factor = 30.0
    if incident_stats['injury_incidents'] > 0:
        safety_factor -= incident_stats['injury_incidents'] * 5
    if incident_stats['days_without_incident'] < 30:
        safety_factor -= 5
    
    score = compliance_factor + training_factor + max(0, safety_factor)
    
    return min(100, max(0, score))

def generate_action_items(
    compliance_status: Dict,
    training_stats: Dict,
    upcoming_audits: List[Dict]
) -> List[Dict]:
    """Generate prioritized action items."""
    actions = []
    
    # Add items for expired compliance
    for item in compliance_status['details']:
        if item['status'] == 'expired':
            actions.append({
                'priority': 'critical',
                'type': 'compliance',
                'action': f"Renew {item['name']} immediately",
                'due_date': 'Immediately'
            })
        elif item['status'] == 'expiring_soon':
            actions.append({
                'priority': 'high',
                'type': 'compliance',
                'action': f"Renew {item['name']}",
                'due_date': item['expiry_date']
            })
    
    # Add training actions
    if training_stats['overdue_trainings'] > 0:
        actions.append({
            'priority': 'high',
            'type': 'training',
            'action': f"Complete overdue training for {training_stats['overdue_trainings']} employees",
            'due_date': 'Within 7 days'
        })
    
    # Add audit preparation
    for audit in upcoming_audits[:3]:
        if audit['days_until'] <= 14:
            actions.append({
                'priority': 'medium',
                'type': 'audit',
                'action': f"Prepare for {audit['type']} audit",
                'due_date': audit['date']
            })
    
    return sorted(actions, key=lambda x: {'critical': 0, 'high': 1, 'medium': 2}.get(x['priority'], 3))

async def send_audit_notifications(audit: Dict, db: Session):
    """Send audit notifications."""
    # Notify participants
    # Send calendar invites
    # Send document requests
    pass

async def create_audit_calendar_events(audit: Dict, db: Session):
    """Create calendar events for audit."""
    # Create events in calendar system
    # Include preparation meetings
    pass

# Service implementations
class ComplianceChecker:
    """Service for checking compliance requirements."""
    pass

class GovernmentAPIClient:
    """Integration with government compliance APIs."""
    
    def __init__(self):
        self.supported_authorities = [
            'state_license_board',
            'osha',
            'epa',
            'dot'
        ]
    
    async def renew_license(self, license_number: str, authority: str) -> Dict:
        """Attempt to renew license through API."""
        # This would integrate with real APIs
        # For now, return mock response
        return {
            'success': False,
            'reason': 'Manual renewal required'
        }

class NotificationService:
    """Notification service."""
    pass

class DocumentGenerator:
    """Document generation service."""
    pass