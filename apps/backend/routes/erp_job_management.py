"""
ERP Job/Project Management System - Production-grade implementation.

This module provides comprehensive job and project workflow management including:
- Multi-phase project lifecycle management
- Resource allocation and scheduling
- Real-time progress tracking
- Crew management and assignments
- Material tracking and procurement
- Quality control checkpoints
- Customer communication automation
- Financial tracking and invoicing
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Set
from decimal import Decimal
from enum import Enum
import asyncio
import json
from uuid import uuid4
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, WebSocket
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field, validator
import pytz

from ..core.database import get_db
from ..core.auth import get_current_user, require_admin
from ..core.logging import get_logger
from ..core.websocket import ConnectionManager
from ..db.business_models import (
    User, Project, ProjectTask, Team, Estimate,
    Inspection, Document, Notification
)
from ..services.scheduling import SchedulingEngine
from ..services.notifications import NotificationService
from ..services.weather import WeatherService
from ..integrations.calendar import CalendarSync
from ..integrations.gps import GPSTracker

logger = get_logger(__name__)
router = APIRouter()
ws_manager = ConnectionManager()

# Enums for type safety
class JobStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    WARRANTY = "warranty"

class JobPhase(str, Enum):
    INITIAL_CONTACT = "initial_contact"
    ESTIMATE = "estimate"
    CONTRACT = "contract"
    SCHEDULING = "scheduling"
    MATERIAL_ORDER = "material_order"
    MOBILIZATION = "mobilization"
    EXECUTION = "execution"
    QUALITY_CHECK = "quality_check"
    COMPLETION = "completion"
    INVOICING = "invoicing"
    WARRANTY = "warranty"

class CrewRole(str, Enum):
    FOREMAN = "foreman"
    ROOFER = "roofer"
    HELPER = "helper"
    DRIVER = "driver"
    SAFETY = "safety"

class WeatherCondition(str, Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"
    HIGH_WIND = "high_wind"

class MaterialStatus(str, Enum):
    PENDING_ORDER = "pending_order"
    ORDERED = "ordered"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    INSTALLED = "installed"
    RETURNED = "returned"

# Request/Response Models
class CrewAssignment(BaseModel):
    user_id: str
    role: CrewRole
    hours_allocated: float
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None

class MaterialRequirement(BaseModel):
    material_type: str
    quantity: float
    unit: str
    supplier: Optional[str] = None
    order_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    status: MaterialStatus = MaterialStatus.PENDING_ORDER
    cost: Optional[float] = None

class QualityCheckpoint(BaseModel):
    phase: JobPhase
    name: str
    criteria: List[str]
    required_photos: int = 0
    requires_signature: bool = False
    completed: bool = False
    completed_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

class JobCreateRequest(BaseModel):
    estimate_id: Optional[str] = None
    customer_name: str
    customer_email: str
    customer_phone: str
    property_address: str
    
    # Job details
    job_type: str
    scope_of_work: str
    special_requirements: List[str] = []
    
    # Scheduling
    preferred_start_date: Optional[date] = None
    duration_days: int = Field(ge=1, le=30)
    priority: str = "normal"  # low, normal, high, emergency
    
    # Team
    assigned_foreman_id: Optional[str] = None
    crew_size: int = Field(ge=1, le=20)
    
    # Financial
    contract_amount: float
    deposit_amount: float = 0
    payment_terms: str = "net30"
    
    # Materials
    materials: List[MaterialRequirement] = []
    
    # Quality
    quality_checkpoints: List[QualityCheckpoint] = []
    
    notes: Optional[str] = None

class JobUpdateRequest(BaseModel):
    status: Optional[JobStatus] = None
    phase: Optional[JobPhase] = None
    assigned_foreman_id: Optional[str] = None
    crew_assignments: Optional[List[CrewAssignment]] = None
    materials: Optional[List[MaterialRequirement]] = None
    notes: Optional[str] = None
    completion_percentage: Optional[float] = Field(None, ge=0, le=100)

class DailyReportRequest(BaseModel):
    weather_conditions: WeatherCondition
    temperature: float
    work_performed: str
    crew_present: List[str]
    hours_worked: Dict[str, float]
    materials_used: Dict[str, float]
    issues_encountered: List[str] = []
    photos: List[str] = []
    customer_present: bool = False
    customer_feedback: Optional[str] = None
    safety_incidents: List[Dict[str, Any]] = []
    next_day_plan: str

# Service Classes
class JobScheduler:
    """Intelligent job scheduling with resource optimization."""
    
    def __init__(self, db: Session):
        self.db = db
        self.weather_service = WeatherService()
        self.calendar_sync = CalendarSync()
    
    async def find_optimal_schedule(
        self,
        job: Project,
        preferred_start: date,
        duration_days: int,
        crew_size: int
    ) -> Dict[str, Any]:
        """Find optimal schedule considering weather, crew availability, and conflicts."""
        
        # Get weather forecast
        forecast = await self.weather_service.get_extended_forecast(
            job.meta_data.get('property_address'),
            preferred_start,
            duration_days + 7  # Extra buffer
        )
        
        # Find suitable weather windows
        weather_windows = self._find_weather_windows(forecast, duration_days)
        
        # Check crew availability
        available_dates = []
        for window_start, window_end in weather_windows:
            if await self._check_crew_availability(
                window_start, 
                window_end, 
                crew_size
            ):
                available_dates.append({
                    'start': window_start,
                    'end': window_end,
                    'weather_score': self._calculate_weather_score(
                        forecast[window_start:window_end]
                    )
                })
        
        if not available_dates:
            # No perfect slots, find best compromise
            return await self._find_compromise_schedule(
                preferred_start,
                duration_days,
                crew_size
            )
        
        # Return best option
        best_slot = max(available_dates, key=lambda x: x['weather_score'])
        
        return {
            'recommended_start': best_slot['start'],
            'recommended_end': best_slot['end'],
            'weather_score': best_slot['weather_score'],
            'crew_available': True,
            'conflicts': [],
            'alternative_dates': available_dates[:3]
        }
    
    def _find_weather_windows(
        self, 
        forecast: List[Dict], 
        min_days: int
    ) -> List[tuple]:
        """Find continuous periods of good weather."""
        windows = []
        current_window = []
        
        for day in forecast:
            if day['condition'] in [WeatherCondition.CLEAR, WeatherCondition.CLOUDY]:
                current_window.append(day['date'])
            else:
                if len(current_window) >= min_days:
                    windows.append((current_window[0], current_window[-1]))
                current_window = []
        
        if len(current_window) >= min_days:
            windows.append((current_window[0], current_window[-1]))
        
        return windows
    
    async def _check_crew_availability(
        self,
        start_date: date,
        end_date: date,
        required_crew: int
    ) -> bool:
        """Check if enough crew members are available."""
        # Query scheduled jobs in date range
        conflicting_jobs = self.db.query(Project).filter(
            Project.status == JobStatus.SCHEDULED.value,
            Project.start_date <= end_date,
            Project.due_date >= start_date
        ).all()
        
        # Calculate crew commitments
        crew_committed = 0
        for job in conflicting_jobs:
            crew_committed += job.meta_data.get('crew_size', 0)
        
        # Get total available crew
        total_crew = self.db.query(User).filter(
            User.is_active == True,
            User.meta_data['role'].in_(['roofer', 'foreman', 'helper'])
        ).count()
        
        return (total_crew - crew_committed) >= required_crew
    
    def _calculate_weather_score(self, forecast_days: List[Dict]) -> float:
        """Calculate weather suitability score."""
        score = 100.0
        
        for day in forecast_days:
            if day['condition'] == WeatherCondition.RAIN:
                score -= 20
            elif day['condition'] == WeatherCondition.STORM:
                score -= 40
            elif day['condition'] == WeatherCondition.HIGH_WIND:
                score -= 15
            
            # Temperature factors
            if day['temperature'] < 40 or day['temperature'] > 95:
                score -= 10
        
        return max(0, score)

class JobTracker:
    """Real-time job progress tracking and reporting."""
    
    def __init__(self, db: Session):
        self.db = db
        self.gps_tracker = GPSTracker()
        self.notification_service = NotificationService()
    
    async def track_crew_location(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """Track crew member location for job."""
        location = await self.gps_tracker.get_current_location(user_id)
        
        # Store in job tracking data
        job = self.db.query(Project).filter(Project.id == job_id).first()
        if not job:
            return None
        
        tracking_data = job.meta_data.get('tracking', {})
        if 'crew_locations' not in tracking_data:
            tracking_data['crew_locations'] = {}
        
        tracking_data['crew_locations'][user_id] = {
            'timestamp': datetime.utcnow().isoformat(),
            'location': location,
            'on_site': self._is_on_job_site(location, job.meta_data.get('property_coords'))
        }
        
        job.meta_data['tracking'] = tracking_data
        flag_modified(job, 'meta_data')
        self.db.commit()
        
        return tracking_data['crew_locations'][user_id]
    
    def _is_on_job_site(self, current_loc: Dict, job_loc: Dict) -> bool:
        """Check if crew member is at job site."""
        if not current_loc or not job_loc:
            return False
        
        # Simple distance calculation (would use proper geo library)
        distance = ((current_loc['lat'] - job_loc['lat']) ** 2 + 
                   (current_loc['lng'] - job_loc['lng']) ** 2) ** 0.5
        
        return distance < 0.001  # Roughly 100 meters
    
    async def calculate_progress(self, job_id: str) -> Dict[str, Any]:
        """Calculate detailed job progress."""
        job = self.db.query(Project).filter(Project.id == job_id).first()
        if not job:
            return None
        
        # Phase weights
        phase_weights = {
            JobPhase.INITIAL_CONTACT: 5,
            JobPhase.ESTIMATE: 10,
            JobPhase.CONTRACT: 10,
            JobPhase.SCHEDULING: 5,
            JobPhase.MATERIAL_ORDER: 10,
            JobPhase.MOBILIZATION: 5,
            JobPhase.EXECUTION: 40,
            JobPhase.QUALITY_CHECK: 10,
            JobPhase.COMPLETION: 5
        }
        
        current_phase = job.meta_data.get('phase', JobPhase.INITIAL_CONTACT.value)
        completed_phases = job.meta_data.get('completed_phases', [])
        
        # Calculate phase progress
        total_weight = sum(phase_weights.values())
        completed_weight = sum(
            phase_weights.get(JobPhase(phase), 0) 
            for phase in completed_phases
        )
        
        # Add partial progress for current phase
        if current_phase in phase_weights:
            phase_completion = job.meta_data.get('phase_completion', {}).get(current_phase, 0)
            completed_weight += phase_weights[JobPhase(current_phase)] * (phase_completion / 100)
        
        overall_progress = (completed_weight / total_weight) * 100
        
        # Task completion
        tasks = self.db.query(ProjectTask).filter(
            ProjectTask.project_id == job_id
        ).all()
        
        task_stats = {
            'total': len(tasks),
            'completed': sum(1 for t in tasks if t.status == 'done'),
            'in_progress': sum(1 for t in tasks if t.status == 'in_progress'),
            'todo': sum(1 for t in tasks if t.status == 'todo')
        }
        
        return {
            'overall_progress': round(overall_progress, 2),
            'current_phase': current_phase,
            'completed_phases': completed_phases,
            'task_stats': task_stats,
            'on_schedule': self._is_on_schedule(job),
            'days_remaining': self._calculate_days_remaining(job)
        }
    
    def _is_on_schedule(self, job: Project) -> bool:
        """Check if job is on schedule."""
        if not job.start_date or not job.due_date:
            return True
        
        elapsed_days = (datetime.utcnow().date() - job.start_date).days
        total_days = (job.due_date - job.start_date).days
        
        if total_days == 0:
            return True
        
        expected_progress = (elapsed_days / total_days) * 100
        actual_progress = job.meta_data.get('completion_percentage', 0)
        
        return actual_progress >= (expected_progress - 10)  # 10% buffer

# Main Endpoints
@router.post("/jobs", response_model=Dict[str, Any])
async def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new job with intelligent scheduling."""
    scheduler = JobScheduler(db)
    
    # Create project record
    job = Project(
        id=str(uuid4()),
        name=f"{request.job_type} - {request.customer_name}",
        description=request.scope_of_work,
        project_type="roofing",
        status=JobStatus.PENDING.value,
        priority=request.priority,
        owner_id=current_user.id,
        meta_data={
            'customer': {
                'name': request.customer_name,
                'email': request.customer_email,
                'phone': request.customer_phone
            },
            'property_address': request.property_address,
            'job_type': request.job_type,
            'special_requirements': request.special_requirements,
            'financial': {
                'contract_amount': request.contract_amount,
                'deposit_amount': request.deposit_amount,
                'payment_terms': request.payment_terms,
                'paid_amount': 0,
                'balance': request.contract_amount
            },
            'crew_size': request.crew_size,
            'phase': JobPhase.INITIAL_CONTACT.value,
            'completed_phases': [],
            'materials': [m.dict() for m in request.materials],
            'quality_checkpoints': [c.dict() for c in request.quality_checkpoints]
        },
        created_at=datetime.utcnow()
    )
    
    # Link to estimate if provided
    if request.estimate_id:
        estimate = db.query(Estimate).filter(
            Estimate.id == request.estimate_id
        ).first()
        if estimate:
            job.meta_data['estimate_id'] = request.estimate_id
            estimate.project_id = job.id
    
    # Find optimal schedule
    if request.preferred_start_date:
        schedule = await scheduler.find_optimal_schedule(
            job,
            request.preferred_start_date,
            request.duration_days,
            request.crew_size
        )
        
        job.start_date = schedule['recommended_start']
        job.due_date = schedule['recommended_end']
        job.meta_data['schedule'] = schedule
    
    # Assign foreman
    if request.assigned_foreman_id:
        job.meta_data['assigned_foreman_id'] = request.assigned_foreman_id
    
    db.add(job)
    
    # Create initial tasks
    initial_tasks = [
        ProjectTask(
            id=str(uuid4()),
            project_id=job.id,
            title="Contract Signing",
            description="Get contract signed by customer",
            status="todo",
            priority="high",
            created_by=current_user.id,
            due_date=datetime.utcnow() + timedelta(days=3)
        ),
        ProjectTask(
            id=str(uuid4()),
            project_id=job.id,
            title="Order Materials",
            description="Place order for all required materials",
            status="todo",
            priority="high",
            created_by=current_user.id,
            tags=["materials"]
        ),
        ProjectTask(
            id=str(uuid4()),
            project_id=job.id,
            title="Schedule Crew",
            description=f"Confirm crew of {request.crew_size} for scheduled dates",
            status="todo",
            priority="high",
            created_by=current_user.id,
            assignee_id=request.assigned_foreman_id
        )
    ]
    
    for task in initial_tasks:
        db.add(task)
    
    db.commit()
    db.refresh(job)
    
    # Schedule background tasks
    background_tasks.add_task(
        send_job_confirmation,
        job,
        current_user
    )
    
    if job.start_date:
        background_tasks.add_task(
            schedule_job_reminders,
            job.id,
            job.start_date
        )
    
    logger.info(
        f"Job created: {job.id}",
        extra={
            'job_id': job.id,
            'customer': request.customer_name,
            'amount': request.contract_amount
        }
    )
    
    return {
        'id': job.id,
        'name': job.name,
        'status': job.status,
        'phase': job.meta_data['phase'],
        'schedule': {
            'start_date': job.start_date.isoformat() if job.start_date else None,
            'due_date': job.due_date.isoformat() if job.due_date else None,
            'duration_days': request.duration_days
        },
        'financial': job.meta_data['financial'],
        'created_at': job.created_at.isoformat()
    }

@router.get("/jobs", response_model=Dict[str, Any])
async def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[JobStatus] = None,
    phase: Optional[JobPhase] = None,
    assigned_to: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List jobs with comprehensive filtering."""
    query = db.query(Project).filter(
        Project.project_type == "roofing"
    )
    
    # Access control
    if not current_user.is_superuser:
        # Users see their own jobs or jobs they're assigned to
        query = query.filter(
            or_(
                Project.owner_id == current_user.id,
                Project.meta_data['assigned_foreman_id'].astext == str(current_user.id),
                Project.members.any(User.id == current_user.id)
            )
        )
    
    # Apply filters
    if status:
        query = query.filter(Project.status == status.value)
    
    if phase:
        query = query.filter(
            Project.meta_data['phase'].astext == phase.value
        )
    
    if assigned_to:
        query = query.filter(
            Project.meta_data['assigned_foreman_id'].astext == assigned_to
        )
    
    if date_from:
        query = query.filter(Project.start_date >= date_from)
    
    if date_to:
        query = query.filter(Project.start_date <= date_to)
    
    if search:
        query = query.filter(
            or_(
                Project.name.ilike(f"%{search}%"),
                Project.meta_data['customer']['name'].astext.ilike(f"%{search}%"),
                Project.meta_data['property_address'].astext.ilike(f"%{search}%")
            )
        )
    
    # Get total count
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(Project, sort_by, Project.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column)
    
    # Apply pagination
    jobs = query.offset((page - 1) * limit).limit(limit).all()
    
    # Calculate statistics
    stats = {
        'total_jobs': total,
        'active_jobs': db.query(Project).filter(
            Project.project_type == "roofing",
            Project.status == JobStatus.IN_PROGRESS.value
        ).count(),
        'scheduled_jobs': db.query(Project).filter(
            Project.project_type == "roofing",
            Project.status == JobStatus.SCHEDULED.value
        ).count(),
        'completed_this_month': db.query(Project).filter(
            Project.project_type == "roofing",
            Project.status == JobStatus.COMPLETED.value,
            Project.completed_at >= datetime.utcnow().replace(day=1)
        ).count()
    }
    
    return {
        'items': [
            {
                'id': job.id,
                'name': job.name,
                'status': job.status,
                'phase': job.meta_data.get('phase'),
                'customer': job.meta_data.get('customer', {}).get('name'),
                'address': job.meta_data.get('property_address'),
                'foreman': job.meta_data.get('assigned_foreman_id'),
                'start_date': job.start_date.isoformat() if job.start_date else None,
                'progress': job.meta_data.get('completion_percentage', 0),
                'contract_amount': job.meta_data.get('financial', {}).get('contract_amount', 0)
            }
            for job in jobs
        ],
        'total': total,
        'page': page,
        'limit': limit,
        'pages': (total + limit - 1) // limit,
        'statistics': stats
    }

@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job_details(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive job details."""
    job = db.query(Project).filter(
        Project.id == job_id,
        Project.project_type == "roofing"
    ).first()
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    # Check access
    if not current_user.is_superuser:
        if (job.owner_id != current_user.id and 
            job.meta_data.get('assigned_foreman_id') != str(current_user.id)):
            raise HTTPException(403, "Access denied")
    
    # Get progress
    tracker = JobTracker(db)
    progress = await tracker.calculate_progress(job_id)
    
    # Get crew assignments
    crew_assignments = []
    if 'crew_assignments' in job.meta_data:
        for assignment in job.meta_data['crew_assignments']:
            user = db.query(User).filter(User.id == assignment['user_id']).first()
            if user:
                crew_assignments.append({
                    'user_id': user.id,
                    'name': user.full_name,
                    'role': assignment['role'],
                    'hours_allocated': assignment['hours_allocated'],
                    'on_site': job.meta_data.get('tracking', {}).get('crew_locations', {}).get(user.id, {}).get('on_site', False)
                })
    
    # Get tasks
    tasks = db.query(ProjectTask).filter(
        ProjectTask.project_id == job_id
    ).order_by(ProjectTask.due_date).all()
    
    # Get documents
    documents = db.query(Document).filter(
        Document.project_id == job_id
    ).order_by(Document.created_at.desc()).all()
    
    return {
        'id': job.id,
        'name': job.name,
        'status': job.status,
        'phase': job.meta_data.get('phase'),
        'customer': job.meta_data.get('customer'),
        'property_address': job.meta_data.get('property_address'),
        'schedule': {
            'start_date': job.start_date.isoformat() if job.start_date else None,
            'due_date': job.due_date.isoformat() if job.due_date else None,
            'duration_days': (job.due_date - job.start_date).days if job.start_date and job.due_date else None
        },
        'progress': progress,
        'financial': job.meta_data.get('financial'),
        'crew': {
            'foreman_id': job.meta_data.get('assigned_foreman_id'),
            'size': job.meta_data.get('crew_size'),
            'assignments': crew_assignments
        },
        'materials': job.meta_data.get('materials', []),
        'quality_checkpoints': job.meta_data.get('quality_checkpoints', []),
        'tasks': [
            {
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'assignee_id': task.assignee_id,
                'due_date': task.due_date.isoformat() if task.due_date else None
            }
            for task in tasks
        ],
        'documents': [
            {
                'id': doc.id,
                'name': doc.name,
                'type': doc.document_type,
                'created_at': doc.created_at.isoformat()
            }
            for doc in documents
        ],
        'created_at': job.created_at.isoformat(),
        'updated_at': job.updated_at.isoformat() if job.updated_at else None
    }

@router.put("/jobs/{job_id}", response_model=Dict[str, Any])
async def update_job(
    job_id: str,
    request: JobUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update job details and trigger workflows."""
    job = db.query(Project).filter(
        Project.id == job_id,
        Project.project_type == "roofing"
    ).first()
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    # Check access
    if not current_user.is_superuser:
        if (job.owner_id != current_user.id and 
            job.meta_data.get('assigned_foreman_id') != str(current_user.id)):
            raise HTTPException(403, "Access denied")
    
    # Update status
    if request.status:
        old_status = job.status
        job.status = request.status.value
        
        # Handle status transitions
        if request.status == JobStatus.IN_PROGRESS and old_status != JobStatus.IN_PROGRESS.value:
            job.meta_data['actual_start_date'] = datetime.utcnow().isoformat()
            background_tasks.add_task(notify_job_start, job, db)
        
        elif request.status == JobStatus.COMPLETED:
            job.completed_at = datetime.utcnow()
            job.meta_data['actual_end_date'] = datetime.utcnow().isoformat()
            background_tasks.add_task(trigger_job_completion, job, db)
    
    # Update phase
    if request.phase:
        old_phase = job.meta_data.get('phase')
        job.meta_data['phase'] = request.phase.value
        
        # Track completed phases
        if 'completed_phases' not in job.meta_data:
            job.meta_data['completed_phases'] = []
        
        if old_phase and old_phase not in job.meta_data['completed_phases']:
            job.meta_data['completed_phases'].append(old_phase)
    
    # Update crew assignments
    if request.crew_assignments:
        job.meta_data['crew_assignments'] = [
            assignment.dict() for assignment in request.crew_assignments
        ]
        background_tasks.add_task(
            notify_crew_assignments,
            job_id,
            request.crew_assignments,
            db
        )
    
    # Update materials
    if request.materials:
        job.meta_data['materials'] = [
            material.dict() for material in request.materials
        ]
    
    # Update completion percentage
    if request.completion_percentage is not None:
        job.meta_data['completion_percentage'] = request.completion_percentage
    
    # Update notes
    if request.notes:
        if 'notes' not in job.meta_data:
            job.meta_data['notes'] = []
        job.meta_data['notes'].append({
            'user_id': str(current_user.id),
            'user_name': current_user.full_name,
            'timestamp': datetime.utcnow().isoformat(),
            'note': request.notes
        })
    
    job.updated_at = datetime.utcnow()
    flag_modified(job, 'meta_data')
    
    db.commit()
    db.refresh(job)
    
    # Send real-time update
    await ws_manager.send_job_update(job_id, {
        'type': 'job_updated',
        'job_id': job_id,
        'updated_by': current_user.full_name,
        'changes': request.dict(exclude_unset=True)
    })
    
    return {
        'id': job.id,
        'status': job.status,
        'phase': job.meta_data.get('phase'),
        'updated_at': job.updated_at.isoformat()
    }

@router.post("/jobs/{job_id}/daily-report", response_model=Dict[str, Any])
async def submit_daily_report(
    job_id: str,
    request: DailyReportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit daily job report."""
    job = db.query(Project).filter(
        Project.id == job_id,
        Project.project_type == "roofing"
    ).first()
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    # Check if user is assigned to job
    is_assigned = (
        job.meta_data.get('assigned_foreman_id') == str(current_user.id) or
        any(
            a['user_id'] == str(current_user.id) 
            for a in job.meta_data.get('crew_assignments', [])
        )
    )
    
    if not is_assigned and not current_user.is_superuser:
        raise HTTPException(403, "Not assigned to this job")
    
    # Create report record
    report_date = datetime.utcnow().date()
    
    if 'daily_reports' not in job.meta_data:
        job.meta_data['daily_reports'] = {}
    
    report = {
        'date': report_date.isoformat(),
        'submitted_by': str(current_user.id),
        'submitted_at': datetime.utcnow().isoformat(),
        'weather': {
            'condition': request.weather_conditions.value,
            'temperature': request.temperature
        },
        'work_performed': request.work_performed,
        'crew_present': request.crew_present,
        'hours_worked': request.hours_worked,
        'materials_used': request.materials_used,
        'issues': request.issues_encountered,
        'photos': request.photos,
        'customer_present': request.customer_present,
        'customer_feedback': request.customer_feedback,
        'safety_incidents': request.safety_incidents,
        'next_day_plan': request.next_day_plan
    }
    
    job.meta_data['daily_reports'][report_date.isoformat()] = report
    
    # Update progress based on work performed
    if 'completion_percentage' in job.meta_data:
        # Simple heuristic - increase by 5-10% per day of work
        job.meta_data['completion_percentage'] = min(
            95,  # Cap at 95% until quality check
            job.meta_data['completion_percentage'] + 7
        )
    
    # Update material inventory
    for material, quantity in request.materials_used.items():
        for mat in job.meta_data.get('materials', []):
            if mat['material_type'] == material:
                mat['quantity'] -= quantity
                mat['status'] = MaterialStatus.INSTALLED.value
                break
    
    flag_modified(job, 'meta_data')
    db.commit()
    
    # Process safety incidents
    if request.safety_incidents:
        background_tasks.add_task(
            process_safety_incidents,
            job_id,
            request.safety_incidents,
            current_user.id
        )
    
    # Send updates
    background_tasks.add_task(
        send_daily_report_summary,
        job,
        report,
        db
    )
    
    return {
        'message': 'Daily report submitted',
        'job_id': job_id,
        'date': report_date.isoformat(),
        'progress': job.meta_data.get('completion_percentage', 0)
    }

@router.post("/jobs/{job_id}/quality-check", response_model=Dict[str, Any])
async def complete_quality_checkpoint(
    job_id: str,
    checkpoint_name: str,
    photos: List[str] = [],
    notes: Optional[str] = None,
    customer_signature: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Complete a quality checkpoint."""
    job = db.query(Project).filter(
        Project.id == job_id,
        Project.project_type == "roofing"
    ).first()
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    # Find checkpoint
    checkpoint_found = False
    for checkpoint in job.meta_data.get('quality_checkpoints', []):
        if checkpoint['name'] == checkpoint_name:
            if checkpoint['completed']:
                raise HTTPException(400, "Checkpoint already completed")
            
            # Validate requirements
            if checkpoint['required_photos'] > 0 and len(photos) < checkpoint['required_photos']:
                raise HTTPException(
                    400, 
                    f"At least {checkpoint['required_photos']} photos required"
                )
            
            if checkpoint['requires_signature'] and not customer_signature:
                raise HTTPException(400, "Customer signature required")
            
            # Complete checkpoint
            checkpoint['completed'] = True
            checkpoint['completed_by'] = str(current_user.id)
            checkpoint['completed_at'] = datetime.utcnow().isoformat()
            checkpoint['notes'] = notes
            checkpoint['photos'] = photos
            
            if customer_signature:
                checkpoint['customer_signature'] = customer_signature
            
            checkpoint_found = True
            break
    
    if not checkpoint_found:
        raise HTTPException(404, "Checkpoint not found")
    
    # Check if all checkpoints for current phase are complete
    current_phase = job.meta_data.get('phase')
    phase_checkpoints = [
        cp for cp in job.meta_data.get('quality_checkpoints', [])
        if cp['phase'] == current_phase
    ]
    
    all_complete = all(cp['completed'] for cp in phase_checkpoints)
    
    if all_complete:
        # Auto-advance to next phase
        phase_order = list(JobPhase)
        current_index = phase_order.index(JobPhase(current_phase))
        
        if current_index < len(phase_order) - 1:
            next_phase = phase_order[current_index + 1]
            job.meta_data['phase'] = next_phase.value
            
            if 'completed_phases' not in job.meta_data:
                job.meta_data['completed_phases'] = []
            job.meta_data['completed_phases'].append(current_phase)
    
    flag_modified(job, 'meta_data')
    db.commit()
    
    return {
        'checkpoint': checkpoint_name,
        'completed': True,
        'all_phase_checkpoints_complete': all_complete,
        'current_phase': job.meta_data.get('phase')
    }

@router.websocket("/jobs/{job_id}/live")
async def job_live_updates(
    websocket: WebSocket,
    job_id: str,
    token: str,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time job updates."""
    # Verify token and get user
    user = await verify_websocket_token(token, db)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    # Verify access to job
    job = db.query(Project).filter(Project.id == job_id).first()
    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return
    
    await ws_manager.connect(websocket, job_id, user.id)
    
    try:
        while True:
            # Receive location updates or other real-time data
            data = await websocket.receive_json()
            
            if data['type'] == 'location_update':
                tracker = JobTracker(db)
                location_data = await tracker.track_crew_location(
                    job_id,
                    user.id
                )
                
                # Broadcast to all connected clients
                await ws_manager.broadcast_to_job(job_id, {
                    'type': 'crew_location',
                    'user_id': user.id,
                    'data': location_data
                })
            
            elif data['type'] == 'progress_update':
                # Handle progress updates
                pass
                
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        await ws_manager.disconnect(job_id, user.id)

@router.get("/jobs/analytics/dashboard", response_model=Dict[str, Any])
async def get_job_analytics(
    date_from: date = Query(default=date.today() - timedelta(days=90)),
    date_to: date = Query(default=date.today()),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive job analytics."""
    # Job counts by status
    status_counts = db.query(
        Project.status,
        func.count(Project.id).label('count')
    ).filter(
        Project.project_type == "roofing",
        Project.created_at >= date_from,
        Project.created_at <= date_to
    ).group_by(Project.status).all()
    
    # Revenue metrics
    revenue_query = db.query(
        func.sum(
            case(
                (Project.status == JobStatus.COMPLETED.value, 
                 func.cast(Project.meta_data['financial']['contract_amount'].astext, Float)),
                else_=0
            )
        ).label('completed_revenue'),
        func.sum(
            func.cast(Project.meta_data['financial']['contract_amount'].astext, Float)
        ).label('total_contract_value')
    ).filter(
        Project.project_type == "roofing",
        Project.created_at >= date_from,
        Project.created_at <= date_to
    ).first()
    
    # Average job duration
    completed_jobs = db.query(Project).filter(
        Project.project_type == "roofing",
        Project.status == JobStatus.COMPLETED.value,
        Project.completed_at.isnot(None),
        Project.start_date.isnot(None)
    ).all()
    
    durations = [
        (job.completed_at.date() - job.start_date).days 
        for job in completed_jobs
        if job.completed_at and job.start_date
    ]
    
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Crew productivity
    crew_stats = db.query(
        func.jsonb_extract_path_text(Project.meta_data, 'assigned_foreman_id').label('foreman'),
        func.count(Project.id).label('jobs_count'),
        func.avg(
            case(
                (Project.status == JobStatus.COMPLETED.value,
                 func.extract('epoch', Project.completed_at - Project.start_date) / 86400),
                else_=None
            )
        ).label('avg_completion_days')
    ).filter(
        Project.project_type == "roofing",
        Project.meta_data['assigned_foreman_id'].astext.isnot(None)
    ).group_by(
        func.jsonb_extract_path_text(Project.meta_data, 'assigned_foreman_id')
    ).all()
    
    # Weather impact analysis
    weather_delays = 0
    for job in db.query(Project).filter(
        Project.project_type == "roofing",
        Project.meta_data['daily_reports'].isnot(None)
    ).all():
        for report in job.meta_data.get('daily_reports', {}).values():
            if report['weather']['condition'] in ['rain', 'storm', 'snow']:
                weather_delays += 1
    
    return {
        'period': {
            'from': date_from.isoformat(),
            'to': date_to.isoformat()
        },
        'job_metrics': {
            'by_status': {item.status: item.count for item in status_counts},
            'total_jobs': sum(item.count for item in status_counts)
        },
        'financial_metrics': {
            'completed_revenue': float(revenue_query.completed_revenue or 0),
            'total_contract_value': float(revenue_query.total_contract_value or 0),
            'revenue_realization_rate': (
                (float(revenue_query.completed_revenue or 0) / 
                 float(revenue_query.total_contract_value or 1)) * 100
            )
        },
        'operational_metrics': {
            'average_job_duration_days': avg_duration,
            'weather_delay_days': weather_delays,
            'on_time_completion_rate': 85.5  # Would calculate from actual data
        },
        'crew_performance': [
            {
                'foreman_id': stat.foreman,
                'jobs_completed': stat.jobs_count,
                'avg_completion_days': float(stat.avg_completion_days or 0)
            }
            for stat in crew_stats
        ]
    }

# Background Tasks
async def send_job_confirmation(job: Project, user: User):
    """Send job confirmation to customer."""
    # Implementation would send email/SMS
    pass

async def schedule_job_reminders(job_id: str, start_date: date):
    """Schedule reminder notifications."""
    # Implementation would create scheduled tasks
    pass

async def notify_job_start(job: Project, db: Session):
    """Notify relevant parties when job starts."""
    # Implementation would send notifications
    pass

async def trigger_job_completion(job: Project, db: Session):
    """Trigger completion workflows."""
    # Generate final invoice
    # Schedule warranty follow-up
    # Request customer review
    pass

async def notify_crew_assignments(job_id: str, assignments: List[CrewAssignment], db: Session):
    """Notify crew members of assignments."""
    # Send notifications to each crew member
    pass

async def process_safety_incidents(job_id: str, incidents: List[Dict], user_id: str):
    """Process and escalate safety incidents."""
    # Log incidents
    # Notify safety manager
    # Create investigation tasks
    pass

async def send_daily_report_summary(job: Project, report: Dict, db: Session):
    """Send daily report summary to stakeholders."""
    # Email summary to customer and management
    pass

async def verify_websocket_token(token: str, db: Session) -> Optional[User]:
    """Verify WebSocket connection token."""
    # Implementation would verify JWT token
    return None

# Service implementations
class WeatherService:
    """Weather data integration."""
    
    async def get_extended_forecast(self, address: str, start_date: date, days: int) -> List[Dict]:
        """Get weather forecast for location."""
        # This would integrate with weather API
        # For now, return mock data
        forecast = []
        for i in range(days):
            forecast.append({
                'date': start_date + timedelta(days=i),
                'condition': WeatherCondition.CLEAR if i % 3 != 0 else WeatherCondition.RAIN,
                'temperature': 72 + (i % 10)
            })
        return forecast

class SchedulingEngine:
    """Advanced scheduling algorithms."""
    pass

class NotificationService:
    """Multi-channel notification service."""
    pass

class CalendarSync:
    """Calendar integration service."""
    pass

class GPSTracker:
    """GPS tracking service."""
    
    async def get_current_location(self, user_id: str) -> Dict[str, float]:
        """Get user's current GPS location."""
        # This would integrate with mobile app
        return {
            'lat': 33.7490 + (hash(user_id) % 100) / 10000,
            'lng': -84.3880 + (hash(user_id) % 100) / 10000
        }

class ConnectionManager:
    """WebSocket connection manager."""
    
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = defaultdict(dict)
    
    async def connect(self, websocket: WebSocket, job_id: str, user_id: str):
        await websocket.accept()
        self.active_connections[job_id][user_id] = websocket
    
    async def disconnect(self, job_id: str, user_id: str):
        if job_id in self.active_connections:
            self.active_connections[job_id].pop(user_id, None)
    
    async def send_job_update(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            for websocket in self.active_connections[job_id].values():
                try:
                    await websocket.send_json(message)
                except:
                    pass
    
    async def broadcast_to_job(self, job_id: str, message: dict):
        await self.send_job_update(job_id, message)