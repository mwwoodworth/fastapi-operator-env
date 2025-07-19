"""
Task Management and Operations Tracking System

This module provides comprehensive task management functionality for field operations,
including task creation, assignment, dependencies, workflow management, and real-time
status tracking. It integrates with job management, crew scheduling, and compliance
to provide a unified operations view.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, relationship
from sqlalchemy import and_, or_, func, case, Column, String, Integer, Float, Boolean, Text, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timedelta, date
from pydantic import BaseModel, Field, validator
import uuid
import json
import asyncio
from enum import Enum

from ..core.database import get_db
from ..core.auth import get_current_user
from ..core.permissions import require_permission
from ..core.cache import cache_result, invalidate_cache
from ..services.notifications import send_notification, NotificationType
from ..core.audit import audit_log
from ..db.business_models import User, UserRole, Project, ProjectTask, Base
from ..services.weather import WeatherService
from ..services.crew_scheduler import CrewScheduler
from ..integrations.calendar import CalendarIntegration


router = APIRouter(prefix="/api/v1/task-management", tags=["Task Management"])


# Enums for task management
class TaskStatus(str, Enum):
    """Task status enumeration with workflow states."""
    TODO = "todo"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    BLOCKED = "blocked"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskType(str, Enum):
    """Types of tasks in the system."""
    FIELD_WORK = "field_work"
    INSPECTION = "inspection"
    MAINTENANCE = "maintenance"
    ADMINISTRATIVE = "administrative"
    SAFETY_CHECK = "safety_check"
    CUSTOMER_SERVICE = "customer_service"
    TRAINING = "training"
    EMERGENCY = "emergency"


class DependencyType(str, Enum):
    """Types of task dependencies."""
    FINISH_TO_START = "finish_to_start"  # Task B starts after Task A finishes
    START_TO_START = "start_to_start"    # Task B starts when Task A starts
    FINISH_TO_FINISH = "finish_to_finish" # Task B finishes when Task A finishes
    START_TO_FINISH = "start_to_finish"   # Task B finishes when Task A starts


# Request/Response Models
class TaskDependency(BaseModel):
    """Model for task dependencies."""
    predecessor_id: uuid.UUID
    dependency_type: DependencyType = DependencyType.FINISH_TO_START
    lag_hours: float = 0  # Hours to wait after dependency is satisfied


class TaskChecklistItem(BaseModel):
    """Checklist item within a task."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    is_completed: bool = False
    completed_by: Optional[uuid.UUID] = None
    completed_at: Optional[datetime] = None


class TaskCreate(BaseModel):
    """Request model for creating a task."""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    task_type: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    project_id: Optional[uuid.UUID] = None
    job_id: Optional[uuid.UUID] = None
    
    # Assignment
    assignee_id: Optional[uuid.UUID] = None
    crew_ids: List[uuid.UUID] = []
    
    # Scheduling
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    estimated_hours: float = Field(default=1.0, ge=0.1, le=100)
    
    # Location
    location_address: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    
    # Dependencies
    dependencies: List[TaskDependency] = []
    
    # Task details
    tags: List[str] = []
    checklist_items: List[str] = []
    required_tools: List[str] = []
    safety_requirements: List[str] = []
    
    # Automation
    auto_assign: bool = False
    weather_dependent: bool = True
    notify_on_creation: bool = True


class TaskUpdate(BaseModel):
    """Request model for updating a task."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    
    # Assignment changes
    assignee_id: Optional[uuid.UUID] = None
    add_crew_ids: List[uuid.UUID] = []
    remove_crew_ids: List[uuid.UUID] = []
    
    # Rescheduling
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    estimated_hours: Optional[float] = Field(None, ge=0.1, le=100)
    
    # Progress
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    actual_hours: Optional[float] = Field(None, ge=0)
    
    # Updates
    add_tags: List[str] = []
    remove_tags: List[str] = []
    notes: Optional[str] = None


class TaskBulkUpdate(BaseModel):
    """Request model for bulk task updates."""
    task_ids: List[uuid.UUID]
    update_data: TaskUpdate
    reason: str


class TaskFilter(BaseModel):
    """Filter criteria for task queries."""
    status: Optional[List[TaskStatus]] = None
    priority: Optional[List[TaskPriority]] = None
    task_type: Optional[List[TaskType]] = None
    assignee_ids: Optional[List[uuid.UUID]] = None
    project_ids: Optional[List[uuid.UUID]] = None
    job_ids: Optional[List[uuid.UUID]] = None
    tags: Optional[List[str]] = None
    
    # Date filters
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    due_after: Optional[datetime] = None
    due_before: Optional[datetime] = None
    
    # Special filters
    overdue_only: bool = False
    blocked_only: bool = False
    my_tasks_only: bool = False
    unassigned_only: bool = False


# Extended Task Model
class TaskExtended(ProjectTask):
    """Extended task model with additional computed fields."""
    __tablename__ = "task_extensions"
    __table_args__ = {'extend_existing': True}
    
    # Additional fields for comprehensive task management
    task_type = Column(String(50), default="field_work")
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    
    # Location
    location_address = Column(Text, nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    
    # Scheduling
    planned_start = Column(DateTime, nullable=True)
    planned_end = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    
    # Progress tracking
    progress_percentage = Column(Integer, default=0)
    is_blocked = Column(Boolean, default=False)
    blocked_reason = Column(Text, nullable=True)
    
    # Crew assignment (JSON array of user IDs)
    crew_ids = Column(JSON, default=[])
    
    # Requirements
    required_tools = Column(JSON, default=[])
    safety_requirements = Column(JSON, default=[])
    
    # Weather dependency
    weather_dependent = Column(Boolean, default=True)
    weather_hold = Column(Boolean, default=False)
    
    # Parent-child relationships
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("project_tasks.id"), nullable=True)
    
    # Approval workflow
    requires_approval = Column(Boolean, default=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)


class TaskDependencyModel(Base):
    """Model for task dependencies."""
    __tablename__ = "task_dependencies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    predecessor_id = Column(UUID(as_uuid=True), ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    dependency_type = Column(String(20), default="finish_to_start")
    lag_hours = Column(Float, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    task = relationship("ProjectTask", foreign_keys=[task_id])
    predecessor = relationship("ProjectTask", foreign_keys=[predecessor_id])


# API Endpoints

@router.post("/tasks", response_model=Dict[str, Any])
async def create_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new task with automatic scheduling and assignment.
    
    Features:
    - Auto-assignment based on skills and availability
    - Weather-aware scheduling
    - Dependency validation
    - Notification to assignees
    """
    try:
        # Create base task
        task = TaskExtended(
            id=uuid.uuid4(),
            title=task_data.title,
            description=task_data.description,
            task_type=task_data.task_type.value,
            priority=task_data.priority.value,
            status=TaskStatus.TODO.value,
            project_id=task_data.project_id,
            job_id=task_data.job_id,
            created_by=current_user.id,
            
            # Assignment
            assignee_id=task_data.assignee_id,
            crew_ids=task_data.crew_ids,
            
            # Scheduling
            planned_start=task_data.planned_start,
            planned_end=task_data.planned_end,
            estimated_hours=task_data.estimated_hours,
            
            # Location
            location_address=task_data.location_address,
            location_lat=task_data.location_lat,
            location_lng=task_data.location_lng,
            
            # Requirements
            tags=task_data.tags,
            required_tools=task_data.required_tools,
            safety_requirements=task_data.safety_requirements,
            weather_dependent=task_data.weather_dependent,
            
            # Checklist
            checklist=[{"title": item, "is_completed": False} for item in task_data.checklist_items]
        )
        
        # Auto-assign if requested
        if task_data.auto_assign and not task_data.assignee_id:
            scheduler = CrewScheduler()
            best_assignee = await scheduler.find_best_assignee(
                task_type=task_data.task_type,
                required_skills=task_data.tags,
                preferred_time=task_data.planned_start,
                location=(task_data.location_lat, task_data.location_lng)
            )
            if best_assignee:
                task.assignee_id = best_assignee["user_id"]
                task.crew_ids = best_assignee.get("crew_ids", [])
        
        # Validate and create dependencies
        for dep in task_data.dependencies:
            # Check predecessor exists
            predecessor = db.query(ProjectTask).filter_by(id=dep.predecessor_id).first()
            if not predecessor:
                raise HTTPException(400, f"Predecessor task {dep.predecessor_id} not found")
            
            # Check for circular dependencies
            if await _would_create_circular_dependency(db, task.id, dep.predecessor_id):
                raise HTTPException(400, f"Circular dependency detected with task {dep.predecessor_id}")
            
            # Create dependency
            dependency = TaskDependencyModel(
                task_id=task.id,
                predecessor_id=dep.predecessor_id,
                dependency_type=dep.dependency_type.value,
                lag_hours=dep.lag_hours
            )
            db.add(dependency)
        
        # Check weather if location provided and weather-dependent
        if task_data.weather_dependent and task_data.location_lat and task_data.location_lng:
            weather_service = WeatherService()
            weather = await weather_service.check_conditions(
                lat=task_data.location_lat,
                lng=task_data.location_lng,
                date=task_data.planned_start or datetime.utcnow()
            )
            
            if weather.get("unsafe_conditions"):
                task.weather_hold = True
                task.blocked_reason = f"Weather hold: {weather['conditions']}"
                task.is_blocked = True
        
        # Save task
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Send notifications
        if task_data.notify_on_creation:
            background_tasks.add_task(
                _send_task_notifications,
                task_id=task.id,
                notification_type="created",
                actor_id=current_user.id
            )
        
        # Schedule calendar events
        if task.planned_start and task.assignee_id:
            background_tasks.add_task(
                _create_calendar_event,
                task_id=task.id,
                user_id=task.assignee_id
            )
        
        # Audit log
        await audit_log(
            user_id=current_user.id,
            action="task_created",
            resource_type="task",
            resource_id=task.id,
            details={"title": task.title, "type": task.task_type}
        )
        
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "assignee_id": task.assignee_id,
            "planned_start": task.planned_start,
            "message": "Task created successfully",
            "warnings": ["Weather hold applied"] if task.weather_hold else []
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create task: {str(e)}")


@router.get("/tasks", response_model=Dict[str, Any])
async def list_tasks(
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    
    # Filters
    status: Optional[List[TaskStatus]] = Query(None),
    priority: Optional[List[TaskPriority]] = Query(None),
    task_type: Optional[List[TaskType]] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    job_id: Optional[uuid.UUID] = Query(None),
    
    # Date filters
    due_after: Optional[datetime] = Query(None),
    due_before: Optional[datetime] = Query(None),
    
    # Special filters
    overdue_only: bool = Query(False),
    blocked_only: bool = Query(False),
    my_tasks_only: bool = Query(False),
    
    # Sorting
    sort_by: str = Query("created_at", pattern="^(created_at|due_date|priority|status)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    List tasks with comprehensive filtering and sorting.
    
    Features:
    - Multiple filter criteria
    - Smart sorting
    - Pagination
    - Computed fields (overdue, blocked status)
    """
    try:
        # Build base query
        query = db.query(TaskExtended)
        
        # Apply filters
        if my_tasks_only:
            query = query.filter(or_(
                TaskExtended.assignee_id == current_user.id,
                TaskExtended.crew_ids.contains([str(current_user.id)])
            ))
        elif assignee_id:
            query = query.filter(or_(
                TaskExtended.assignee_id == assignee_id,
                TaskExtended.crew_ids.contains([str(assignee_id)])
            ))
        
        if status:
            query = query.filter(TaskExtended.status.in_([s.value for s in status]))
        
        if priority:
            query = query.filter(TaskExtended.priority.in_([p.value for p in priority]))
        
        if task_type:
            query = query.filter(TaskExtended.task_type.in_([t.value for t in task_type]))
        
        if project_id:
            query = query.filter(TaskExtended.project_id == project_id)
        
        if job_id:
            query = query.filter(TaskExtended.job_id == job_id)
        
        if due_after:
            query = query.filter(TaskExtended.due_date >= due_after)
        
        if due_before:
            query = query.filter(TaskExtended.due_date <= due_before)
        
        if overdue_only:
            query = query.filter(
                TaskExtended.due_date < datetime.utcnow(),
                TaskExtended.status != TaskStatus.COMPLETED.value
            )
        
        if blocked_only:
            query = query.filter(TaskExtended.is_blocked == True)
        
        # Get total count
        total_count = query.count()
        
        # Apply sorting
        sort_column = getattr(TaskExtended, sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        tasks = query.offset(offset).limit(page_size).all()
        
        # Format response
        task_list = []
        for task in tasks:
            # Load assignee info
            assignee = None
            if task.assignee_id:
                assignee = db.query(User).filter_by(id=task.assignee_id).first()
            
            # Check dependencies
            dependencies = db.query(TaskDependencyModel).filter_by(task_id=task.id).all()
            blocked_by = []
            for dep in dependencies:
                predecessor = db.query(TaskExtended).filter_by(id=dep.predecessor_id).first()
                if predecessor and predecessor.status != TaskStatus.COMPLETED.value:
                    blocked_by.append({
                        "task_id": predecessor.id,
                        "title": predecessor.title,
                        "status": predecessor.status
                    })
            
            task_list.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "task_type": task.task_type,
                "assignee": {
                    "id": assignee.id,
                    "name": assignee.full_name,
                    "email": assignee.email
                } if assignee else None,
                "planned_start": task.planned_start,
                "planned_end": task.planned_end,
                "due_date": task.due_date,
                "progress_percentage": task.progress_percentage,
                "is_blocked": task.is_blocked or len(blocked_by) > 0,
                "blocked_by": blocked_by,
                "blocked_reason": task.blocked_reason,
                "weather_hold": task.weather_hold,
                "is_overdue": task.due_date < datetime.utcnow() if task.due_date else False,
                "tags": task.tags,
                "created_at": task.created_at,
                "updated_at": task.updated_at
            })
        
        return {
            "tasks": task_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size
            },
            "filters_applied": {
                "status": [s.value for s in status] if status else None,
                "priority": [p.value for p in priority] if priority else None,
                "task_type": [t.value for t in task_type] if task_type else None,
                "overdue_only": overdue_only,
                "blocked_only": blocked_only
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve tasks: {str(e)}")


@router.get("/tasks/{task_id}", response_model=Dict[str, Any])
async def get_task_details(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive task details including dependencies and history.
    """
    try:
        # Get task with relationships
        task = db.query(TaskExtended).options(
            joinedload(TaskExtended.assignee),
            joinedload(TaskExtended.creator),
            joinedload(TaskExtended.project),
            joinedload(TaskExtended.comments)
        ).filter_by(id=task_id).first()
        
        if not task:
            raise HTTPException(404, "Task not found")
        
        # Get dependencies
        dependencies = db.query(TaskDependencyModel).filter_by(task_id=task_id).all()
        dependency_list = []
        for dep in dependencies:
            predecessor = db.query(TaskExtended).filter_by(id=dep.predecessor_id).first()
            dependency_list.append({
                "predecessor_id": dep.predecessor_id,
                "predecessor_title": predecessor.title if predecessor else "Unknown",
                "predecessor_status": predecessor.status if predecessor else "unknown",
                "dependency_type": dep.dependency_type,
                "lag_hours": dep.lag_hours,
                "is_satisfied": predecessor.status == TaskStatus.COMPLETED.value if predecessor else False
            })
        
        # Get dependent tasks
        dependent_tasks = db.query(TaskDependencyModel).filter_by(predecessor_id=task_id).all()
        dependents_list = []
        for dep in dependent_tasks:
            dependent = db.query(TaskExtended).filter_by(id=dep.task_id).first()
            dependents_list.append({
                "task_id": dep.task_id,
                "title": dependent.title if dependent else "Unknown",
                "status": dependent.status if dependent else "unknown",
                "dependency_type": dep.dependency_type
            })
        
        # Get crew members
        crew_members = []
        if task.crew_ids:
            crew = db.query(User).filter(User.id.in_(task.crew_ids)).all()
            crew_members = [{"id": u.id, "name": u.full_name, "email": u.email} for u in crew]
        
        # Get activity history
        history = await _get_task_history(db, task_id)
        
        # Calculate metrics
        metrics = {
            "estimated_hours": task.estimated_hours,
            "actual_hours": task.actual_hours,
            "efficiency": (task.estimated_hours / task.actual_hours * 100) if task.actual_hours else None,
            "days_overdue": (datetime.utcnow() - task.due_date).days if task.due_date and task.due_date < datetime.utcnow() else 0,
            "blockers_count": len(dependency_list),
            "blocking_count": len(dependents_list)
        }
        
        return {
            "task": {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "task_type": task.task_type,
                "progress_percentage": task.progress_percentage,
                
                # People
                "assignee": {
                    "id": task.assignee.id,
                    "name": task.assignee.full_name,
                    "email": task.assignee.email
                } if task.assignee else None,
                "creator": {
                    "id": task.creator.id,
                    "name": task.creator.full_name
                },
                "crew_members": crew_members,
                
                # Scheduling
                "planned_start": task.planned_start,
                "planned_end": task.planned_end,
                "actual_start": task.actual_start,
                "actual_end": task.actual_end,
                "due_date": task.due_date,
                
                # Location
                "location": {
                    "address": task.location_address,
                    "latitude": task.location_lat,
                    "longitude": task.location_lng
                } if task.location_address else None,
                
                # Status flags
                "is_blocked": task.is_blocked,
                "blocked_reason": task.blocked_reason,
                "weather_hold": task.weather_hold,
                "requires_approval": task.requires_approval,
                "approved_by": task.approved_by,
                "approved_at": task.approved_at,
                
                # Details
                "tags": task.tags,
                "checklist": task.checklist,
                "required_tools": task.required_tools,
                "safety_requirements": task.safety_requirements,
                "attachments": task.attachments,
                
                # Timestamps
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "completed_at": task.completed_at
            },
            "dependencies": dependency_list,
            "dependent_tasks": dependents_list,
            "metrics": metrics,
            "history": history,
            "comments_count": len(task.comments) if task.comments else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve task details: {str(e)}")


@router.put("/tasks/{task_id}", response_model=Dict[str, Any])
async def update_task(
    task_id: uuid.UUID,
    update_data: TaskUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update task with validation and workflow triggers.
    """
    try:
        # Get task
        task = db.query(TaskExtended).filter_by(id=task_id).first()
        if not task:
            raise HTTPException(404, "Task not found")
        
        # Check permissions
        if not _can_update_task(task, current_user):
            raise HTTPException(403, "Insufficient permissions to update this task")
        
        # Track changes for notifications
        changes = []
        old_status = task.status
        old_assignee = task.assignee_id
        
        # Update basic fields
        if update_data.title is not None:
            task.title = update_data.title
            changes.append("title")
        
        if update_data.description is not None:
            task.description = update_data.description
            changes.append("description")
        
        if update_data.priority is not None:
            task.priority = update_data.priority.value
            changes.append("priority")
        
        # Status change with validation
        if update_data.status is not None:
            new_status = update_data.status.value
            
            # Validate status transition
            if not _is_valid_status_transition(old_status, new_status):
                raise HTTPException(400, f"Invalid status transition from {old_status} to {new_status}")
            
            # Check dependencies before marking as in progress
            if new_status == TaskStatus.IN_PROGRESS.value:
                unmet_deps = await _get_unmet_dependencies(db, task_id)
                if unmet_deps:
                    raise HTTPException(400, f"Cannot start task: {len(unmet_deps)} dependencies not met")
                
                task.actual_start = datetime.utcnow()
            
            # Handle completion
            if new_status == TaskStatus.COMPLETED.value:
                task.actual_end = datetime.utcnow()
                task.completed_at = datetime.utcnow()
                task.progress_percentage = 100
                
                # Trigger dependent tasks
                background_tasks.add_task(_trigger_dependent_tasks, task_id)
            
            task.status = new_status
            changes.append("status")
        
        # Assignment changes
        if update_data.assignee_id is not None:
            task.assignee_id = update_data.assignee_id
            changes.append("assignee")
            
            # Update calendar
            if task.planned_start:
                background_tasks.add_task(
                    _update_calendar_event,
                    task_id=task.id,
                    old_assignee=old_assignee,
                    new_assignee=update_data.assignee_id
                )
        
        # Crew updates
        if update_data.add_crew_ids:
            current_crew = set(task.crew_ids or [])
            current_crew.update(str(uid) for uid in update_data.add_crew_ids)
            task.crew_ids = list(current_crew)
            changes.append("crew")
        
        if update_data.remove_crew_ids:
            current_crew = set(task.crew_ids or [])
            for uid in update_data.remove_crew_ids:
                current_crew.discard(str(uid))
            task.crew_ids = list(current_crew)
            changes.append("crew")
        
        # Schedule updates
        if update_data.planned_start is not None:
            task.planned_start = update_data.planned_start
            changes.append("schedule")
            
            # Check weather for new date
            if task.weather_dependent and task.location_lat:
                weather_service = WeatherService()
                weather = await weather_service.check_conditions(
                    lat=task.location_lat,
                    lng=task.location_lng,
                    date=update_data.planned_start
                )
                
                task.weather_hold = weather.get("unsafe_conditions", False)
                if task.weather_hold:
                    task.blocked_reason = f"Weather hold: {weather['conditions']}"
        
        if update_data.planned_end is not None:
            task.planned_end = update_data.planned_end
            changes.append("schedule")
        
        if update_data.estimated_hours is not None:
            task.estimated_hours = update_data.estimated_hours
        
        # Progress updates
        if update_data.progress_percentage is not None:
            task.progress_percentage = update_data.progress_percentage
            changes.append("progress")
        
        if update_data.actual_hours is not None:
            task.actual_hours = update_data.actual_hours
        
        # Tag updates
        if update_data.add_tags:
            current_tags = set(task.tags or [])
            current_tags.update(update_data.add_tags)
            task.tags = list(current_tags)
        
        if update_data.remove_tags:
            current_tags = set(task.tags or [])
            for tag in update_data.remove_tags:
                current_tags.discard(tag)
            task.tags = list(current_tags)
        
        # Add notes as comment if provided
        if update_data.notes:
            from ..db.business_models import TaskComment
            comment = TaskComment(
                task_id=task.id,
                user_id=current_user.id,
                content=update_data.notes,
                is_system=False
            )
            db.add(comment)
        
        # Update timestamps
        task.updated_at = datetime.utcnow()
        
        # Save changes
        db.commit()
        db.refresh(task)
        
        # Send notifications
        if changes:
            background_tasks.add_task(
                _send_task_notifications,
                task_id=task.id,
                notification_type="updated",
                actor_id=current_user.id,
                changes=changes
            )
        
        # Audit log
        await audit_log(
            user_id=current_user.id,
            action="task_updated",
            resource_type="task",
            resource_id=task.id,
            details={
                "changes": changes,
                "old_status": old_status,
                "new_status": task.status
            }
        )
        
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "message": "Task updated successfully",
            "changes": changes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to update task: {str(e)}")


@router.post("/tasks/{task_id}/checklist/{item_id}/complete", response_model=Dict[str, Any])
async def complete_checklist_item(
    task_id: uuid.UUID,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Mark a checklist item as complete.
    """
    try:
        # Get task
        task = db.query(TaskExtended).filter_by(id=task_id).first()
        if not task:
            raise HTTPException(404, "Task not found")
        
        # Find checklist item
        checklist = task.checklist or []
        item_found = False
        
        for item in checklist:
            if item.get("id") == item_id:
                item["is_completed"] = True
                item["completed_by"] = str(current_user.id)
                item["completed_at"] = datetime.utcnow().isoformat()
                item_found = True
                break
        
        if not item_found:
            raise HTTPException(404, "Checklist item not found")
        
        # Update checklist
        task.checklist = checklist
        
        # Calculate progress based on checklist
        completed_items = sum(1 for item in checklist if item.get("is_completed"))
        total_items = len(checklist)
        if total_items > 0:
            checklist_progress = int(completed_items / total_items * 100)
            # Update progress if checklist represents overall progress
            if task.progress_percentage < checklist_progress:
                task.progress_percentage = checklist_progress
        
        db.commit()
        
        return {
            "task_id": task.id,
            "item_id": item_id,
            "completed_items": completed_items,
            "total_items": total_items,
            "task_progress": task.progress_percentage,
            "message": "Checklist item completed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to update checklist: {str(e)}")


@router.post("/tasks/bulk-update", response_model=Dict[str, Any])
@require_permission("task:bulk_update")
async def bulk_update_tasks(
    bulk_data: TaskBulkUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update multiple tasks at once (requires supervisor permissions).
    """
    try:
        updated_count = 0
        failed_updates = []
        
        for task_id in bulk_data.task_ids:
            try:
                # Get task
                task = db.query(TaskExtended).filter_by(id=task_id).first()
                if not task:
                    failed_updates.append({"task_id": task_id, "error": "Not found"})
                    continue
                
                # Apply updates (simplified version of single update)
                if bulk_data.update_data.status:
                    task.status = bulk_data.update_data.status.value
                
                if bulk_data.update_data.priority:
                    task.priority = bulk_data.update_data.priority.value
                
                if bulk_data.update_data.assignee_id:
                    task.assignee_id = bulk_data.update_data.assignee_id
                
                task.updated_at = datetime.utcnow()
                updated_count += 1
                
            except Exception as e:
                failed_updates.append({"task_id": task_id, "error": str(e)})
        
        # Commit all changes
        db.commit()
        
        # Audit log
        await audit_log(
            user_id=current_user.id,
            action="tasks_bulk_updated",
            resource_type="task",
            resource_id=None,
            details={
                "count": updated_count,
                "reason": bulk_data.reason,
                "updates": bulk_data.update_data.dict(exclude_unset=True)
            }
        )
        
        return {
            "updated_count": updated_count,
            "failed_count": len(failed_updates),
            "failed_updates": failed_updates,
            "message": f"Successfully updated {updated_count} tasks"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Bulk update failed: {str(e)}")


@router.get("/dashboard/operations", response_model=Dict[str, Any])
@cache_result(ttl=300)  # Cache for 5 minutes
async def get_operations_dashboard(
    date_range: str = Query("today", pattern="^(today|week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive operations dashboard with task metrics.
    """
    try:
        # Calculate date range
        now = datetime.utcnow()
        if date_range == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif date_range == "week":
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
        else:  # month
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end_date = start_date.replace(year=now.year + 1, month=1)
            else:
                end_date = start_date.replace(month=now.month + 1)
        
        # Get task statistics
        base_query = db.query(TaskExtended).filter(
            TaskExtended.created_at >= start_date,
            TaskExtended.created_at < end_date
        )
        
        # Overall metrics
        total_tasks = base_query.count()
        completed_tasks = base_query.filter(TaskExtended.status == TaskStatus.COMPLETED.value).count()
        in_progress_tasks = base_query.filter(TaskExtended.status == TaskStatus.IN_PROGRESS.value).count()
        blocked_tasks = base_query.filter(TaskExtended.is_blocked == True).count()
        overdue_tasks = base_query.filter(
            TaskExtended.due_date < now,
            TaskExtended.status != TaskStatus.COMPLETED.value
        ).count()
        
        # Completion rate
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Average completion time
        completed_with_times = base_query.filter(
            TaskExtended.status == TaskStatus.COMPLETED.value,
            TaskExtended.actual_start.isnot(None),
            TaskExtended.actual_end.isnot(None)
        ).all()
        
        if completed_with_times:
            total_hours = sum(
                (task.actual_end - task.actual_start).total_seconds() / 3600
                for task in completed_with_times
            )
            avg_completion_hours = total_hours / len(completed_with_times)
        else:
            avg_completion_hours = 0
        
        # Tasks by priority
        priority_breakdown = {}
        for priority in TaskPriority:
            count = base_query.filter(TaskExtended.priority == priority.value).count()
            priority_breakdown[priority.value] = count
        
        # Tasks by type
        type_breakdown = {}
        for task_type in TaskType:
            count = base_query.filter(TaskExtended.task_type == task_type.value).count()
            type_breakdown[task_type.value] = count
        
        # Top performers (most tasks completed)
        top_performers = db.query(
            User.id,
            User.full_name,
            func.count(TaskExtended.id).label('completed_count')
        ).join(
            TaskExtended,
            TaskExtended.assignee_id == User.id
        ).filter(
            TaskExtended.status == TaskStatus.COMPLETED.value,
            TaskExtended.completed_at >= start_date,
            TaskExtended.completed_at < end_date
        ).group_by(
            User.id,
            User.full_name
        ).order_by(
            func.count(TaskExtended.id).desc()
        ).limit(5).all()
        
        # Upcoming tasks (next 7 days)
        upcoming_tasks = db.query(TaskExtended).filter(
            TaskExtended.planned_start >= now,
            TaskExtended.planned_start < now + timedelta(days=7),
            TaskExtended.status.in_([TaskStatus.TODO.value, TaskStatus.PLANNED.value])
        ).order_by(TaskExtended.planned_start).limit(10).all()
        
        # Weather-affected tasks
        weather_affected = base_query.filter(TaskExtended.weather_hold == True).count()
        
        return {
            "period": {
                "range": date_range,
                "start_date": start_date,
                "end_date": end_date
            },
            "metrics": {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "in_progress_tasks": in_progress_tasks,
                "blocked_tasks": blocked_tasks,
                "overdue_tasks": overdue_tasks,
                "weather_affected_tasks": weather_affected,
                "completion_rate": round(completion_rate, 1),
                "avg_completion_hours": round(avg_completion_hours, 1)
            },
            "breakdowns": {
                "by_priority": priority_breakdown,
                "by_type": type_breakdown
            },
            "top_performers": [
                {
                    "user_id": p.id,
                    "name": p.full_name,
                    "completed_count": p.completed_count
                }
                for p in top_performers
            ],
            "upcoming_tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "priority": t.priority,
                    "planned_start": t.planned_start,
                    "assignee_id": t.assignee_id
                }
                for t in upcoming_tasks
            ],
            "alerts": {
                "high_priority_overdue": base_query.filter(
                    TaskExtended.priority == TaskPriority.CRITICAL.value,
                    TaskExtended.due_date < now,
                    TaskExtended.status != TaskStatus.COMPLETED.value
                ).count(),
                "unassigned_urgent": base_query.filter(
                    TaskExtended.priority.in_([TaskPriority.CRITICAL.value, TaskPriority.HIGH.value]),
                    TaskExtended.assignee_id.is_(None)
                ).count()
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to generate dashboard: {str(e)}")


# Helper functions

def _can_update_task(task: TaskExtended, user: User) -> bool:
    """Check if user has permission to update task."""
    # Task creator can update
    if task.created_by == user.id:
        return True
    
    # Assignee can update
    if task.assignee_id == user.id:
        return True
    
    # Crew members can update
    if task.crew_ids and str(user.id) in task.crew_ids:
        return True
    
    # Supervisors and admins can update
    if user.role in [UserRole.ADMIN, UserRole.SUPERVISOR]:
        return True
    
    return False


def _is_valid_status_transition(old_status: str, new_status: str) -> bool:
    """Validate status transitions follow workflow rules."""
    valid_transitions = {
        TaskStatus.TODO.value: [TaskStatus.PLANNED.value, TaskStatus.IN_PROGRESS.value, TaskStatus.CANCELLED.value],
        TaskStatus.PLANNED.value: [TaskStatus.IN_PROGRESS.value, TaskStatus.ON_HOLD.value, TaskStatus.CANCELLED.value],
        TaskStatus.IN_PROGRESS.value: [TaskStatus.ON_HOLD.value, TaskStatus.BLOCKED.value, TaskStatus.REVIEW.value, TaskStatus.COMPLETED.value],
        TaskStatus.ON_HOLD.value: [TaskStatus.IN_PROGRESS.value, TaskStatus.CANCELLED.value],
        TaskStatus.BLOCKED.value: [TaskStatus.IN_PROGRESS.value, TaskStatus.CANCELLED.value],
        TaskStatus.REVIEW.value: [TaskStatus.IN_PROGRESS.value, TaskStatus.COMPLETED.value],
        TaskStatus.COMPLETED.value: [],  # No transitions from completed
        TaskStatus.CANCELLED.value: []   # No transitions from cancelled
    }
    
    return new_status in valid_transitions.get(old_status, [])


async def _would_create_circular_dependency(db: Session, task_id: uuid.UUID, predecessor_id: uuid.UUID) -> bool:
    """Check if adding dependency would create a circular reference."""
    # Simple check: if predecessor depends on this task (directly or indirectly)
    visited = set()
    to_check = [predecessor_id]
    
    while to_check:
        current = to_check.pop()
        if current in visited:
            continue
        
        visited.add(current)
        
        if current == task_id:
            return True  # Circular dependency found
        
        # Get dependencies of current task
        deps = db.query(TaskDependencyModel).filter_by(task_id=current).all()
        to_check.extend(dep.predecessor_id for dep in deps)
    
    return False


async def _get_unmet_dependencies(db: Session, task_id: uuid.UUID) -> List[Dict[str, Any]]:
    """Get list of unmet dependencies for a task."""
    deps = db.query(TaskDependencyModel).filter_by(task_id=task_id).all()
    unmet = []
    
    for dep in deps:
        predecessor = db.query(TaskExtended).filter_by(id=dep.predecessor_id).first()
        if predecessor and predecessor.status != TaskStatus.COMPLETED.value:
            unmet.append({
                "task_id": predecessor.id,
                "title": predecessor.title,
                "status": predecessor.status,
                "dependency_type": dep.dependency_type
            })
    
    return unmet


async def _get_task_history(db: Session, task_id: uuid.UUID) -> List[Dict[str, Any]]:
    """Get activity history for a task."""
    # This would typically query an audit log table
    # For now, return a simplified version
    return []


async def _send_task_notifications(
    task_id: uuid.UUID,
    notification_type: str,
    actor_id: uuid.UUID,
    changes: List[str] = None
):
    """Send notifications for task events."""
    # Implementation would send actual notifications
    pass


async def _create_calendar_event(task_id: uuid.UUID, user_id: uuid.UUID):
    """Create calendar event for task."""
    # Implementation would integrate with calendar service
    pass


async def _update_calendar_event(
    task_id: uuid.UUID,
    old_assignee: uuid.UUID,
    new_assignee: uuid.UUID
):
    """Update calendar event when task is reassigned."""
    # Implementation would update calendar service
    pass


async def _trigger_dependent_tasks(task_id: uuid.UUID):
    """Trigger dependent tasks when a task is completed."""
    # Implementation would check and update dependent tasks
    pass