"""
Project and task management routes for BrainOps backend.

Handles project creation, task assignment, and progress tracking.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func
from pydantic import BaseModel

from ..core.database import get_db
from ..core.auth import get_current_user
from ..db.business_models import (
    User, Project, ProjectTask, TaskComment, Team, 
    project_members, Document
)
from ..core.pagination import paginate, PaginationParams

router = APIRouter()


# Pydantic models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str]
    project_type: str = "general"
    team_id: Optional[str]
    start_date: Optional[datetime]
    due_date: Optional[datetime]
    metadata: dict = {}
    tags: List[str] = []


class ProjectUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    start_date: Optional[datetime]
    due_date: Optional[datetime]
    metadata: Optional[dict]
    tags: Optional[List[str]]


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    project_type: str
    status: str
    priority: str
    owner_id: str
    team_id: Optional[str]
    start_date: Optional[datetime]
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    metadata: dict
    tags: List[str]
    member_count: int
    task_count: int
    completed_task_count: int
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: Optional[str]
    status: str = "todo"
    priority: str = "medium"
    assignee_id: Optional[str]
    due_date: Optional[datetime]
    estimated_hours: Optional[float]
    tags: List[str] = []
    checklist: List[dict] = []


class TaskUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    assignee_id: Optional[str]
    due_date: Optional[datetime]
    estimated_hours: Optional[float]
    actual_hours: Optional[float]
    tags: Optional[List[str]]
    checklist: Optional[List[dict]]


class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    assignee_id: Optional[str]
    assignee_name: Optional[str]
    created_by: str
    creator_name: str
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_hours: Optional[float]
    actual_hours: Optional[float]
    tags: List[str]
    checklist: List[dict]
    attachments: List[dict]
    comment_count: int
    created_at: datetime
    updated_at: datetime


class CommentCreate(BaseModel):
    content: str
    attachments: List[dict] = []


class CommentResponse(BaseModel):
    id: str
    task_id: str
    user_id: str
    user_name: str
    user_avatar: Optional[str]
    content: str
    attachments: List[dict]
    created_at: datetime
    updated_at: datetime


class TaskAssign(BaseModel):
    assignee_id: str


class ProjectMemberAdd(BaseModel):
    user_id: str
    role: str = "member"


class ProjectStats(BaseModel):
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    overdue_tasks: int
    total_estimated_hours: float
    total_actual_hours: float
    completion_rate: float
    members: int
    documents: int


# Project Management Endpoints
@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project."""
    # Verify team ownership if team_id provided
    if project_data.team_id:
        team = db.query(Team).filter(Team.id == project_data.team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )
        
        # Check if user is a team member
        is_member = db.query(project_members).filter(
            and_(
                project_members.c.user_id == current_user.id,
                project_members.c.project_id == project_data.team_id
            )
        ).first()
        
        if not is_member and team.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be a team member to create projects"
            )
    
    # Create project
    project = Project(
        name=project_data.name,
        description=project_data.description,
        project_type=project_data.project_type,
        owner_id=current_user.id,
        team_id=project_data.team_id,
        start_date=project_data.start_date,
        due_date=project_data.due_date,
        metadata=project_data.metadata,
        tags=project_data.tags
    )
    
    db.add(project)
    db.commit()
    
    # Add owner as project member
    db.execute(
        project_members.insert().values(
            project_id=project.id,
            user_id=current_user.id,
            role='admin',
            joined_at=datetime.utcnow()
        )
    )
    db.commit()
    db.refresh(project)
    
    return format_project_response(project, db)


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    search: Optional[str] = None,
    status: Optional[str] = None,
    project_type: Optional[str] = None,
    team_id: Optional[UUID] = None,
    my_projects: bool = True,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List projects."""
    query = db.query(Project).options(
        joinedload(Project.members),
        joinedload(Project.tasks)
    )
    
    # Filter by membership
    if my_projects:
        query = query.join(project_members).filter(
            project_members.c.user_id == current_user.id
        )
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Project.name.ilike(f"%{search}%"),
                Project.description.ilike(f"%{search}%")
            )
        )
    
    if status:
        query = query.filter(Project.status == status)
    
    if project_type:
        query = query.filter(Project.project_type == project_type)
    
    if team_id:
        query = query.filter(Project.team_id == team_id)
    
    # Order by updated date
    query = query.order_by(Project.updated_at.desc())
    
    # Paginate
    projects = paginate(query, pagination)
    
    return [format_project_response(project, db) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get project details."""
    project = db.query(Project).options(
        joinedload(Project.members),
        joinedload(Project.tasks)
    ).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if user has access
    if not is_project_member(current_user.id, project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this project"
        )
    
    return format_project_response(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    update_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update project details."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check permission
    if not is_project_admin(current_user.id, project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this project"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(project, field, value)
    
    # Update completed_at if status changed to completed
    if update_data.status == "completed" and project.completed_at is None:
        project.completed_at = datetime.utcnow()
    elif update_data.status != "completed":
        project.completed_at = None
    
    db.commit()
    db.refresh(project)
    
    return format_project_response(project, db)


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Only owner can delete
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can delete the project"
        )
    
    # Soft delete by archiving
    project.status = "archived"
    project.archived_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Project archived successfully"}


@router.post("/{project_id}/archive")
async def archive_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Archive a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check permission
    if not is_project_admin(current_user.id, project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to archive this project"
        )
    
    project.status = "archived"
    project.archived_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Project archived successfully"}


@router.post("/{project_id}/restore")
async def restore_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Restore an archived project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check permission
    if not is_project_admin(current_user.id, project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to restore this project"
        )
    
    project.status = "active"
    project.archived_at = None
    db.commit()
    
    return {"message": "Project restored successfully"}


@router.get("/{project_id}/stats", response_model=ProjectStats)
async def get_project_stats(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get project statistics."""
    # Check access
    if not is_project_member(current_user.id, project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this project"
        )
    
    # Get task stats
    task_stats = db.query(
        func.count(ProjectTask.id).label('total'),
        func.sum(func.cast(ProjectTask.status == 'done', db.Integer)).label('completed'),
        func.sum(func.cast(ProjectTask.status == 'in_progress', db.Integer)).label('in_progress'),
        func.sum(func.cast(
            and_(ProjectTask.due_date < datetime.utcnow(), ProjectTask.status != 'done'),
            db.Integer
        )).label('overdue'),
        func.sum(ProjectTask.estimated_hours).label('estimated'),
        func.sum(ProjectTask.actual_hours).label('actual')
    ).filter(ProjectTask.project_id == project_id).first()
    
    # Get member count
    member_count = db.query(project_members).filter(
        project_members.c.project_id == project_id
    ).count()
    
    # Get document count
    doc_count = db.query(Document).filter(
        Document.project_id == project_id
    ).count()
    
    completion_rate = 0
    if task_stats.total > 0:
        completion_rate = (task_stats.completed or 0) / task_stats.total * 100
    
    return ProjectStats(
        total_tasks=task_stats.total or 0,
        completed_tasks=task_stats.completed or 0,
        in_progress_tasks=task_stats.in_progress or 0,
        overdue_tasks=task_stats.overdue or 0,
        total_estimated_hours=task_stats.estimated or 0,
        total_actual_hours=task_stats.actual or 0,
        completion_rate=completion_rate,
        members=member_count,
        documents=doc_count
    )


# Task Management Endpoints
@router.post("/{project_id}/tasks", response_model=TaskResponse)
async def create_task(
    project_id: UUID,
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new task in project."""
    # Check project access
    if not is_project_member(current_user.id, project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create tasks in this project"
        )
    
    # Verify assignee is a project member
    if task_data.assignee_id:
        if not is_project_member(task_data.assignee_id, project_id, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignee must be a project member"
            )
    
    # Create task
    task = ProjectTask(
        project_id=project_id,
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        assignee_id=task_data.assignee_id,
        created_by=current_user.id,
        due_date=task_data.due_date,
        estimated_hours=task_data.estimated_hours,
        tags=task_data.tags,
        checklist=task_data.checklist
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return format_task_response(task, db)


@router.get("/{project_id}/tasks", response_model=List[TaskResponse])
async def list_project_tasks(
    project_id: UUID,
    status: Optional[str] = None,
    assignee_id: Optional[UUID] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List tasks in a project."""
    # Check project access
    if not is_project_member(current_user.id, project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view tasks in this project"
        )
    
    query = db.query(ProjectTask).options(
        joinedload(ProjectTask.assignee),
        joinedload(ProjectTask.creator),
        joinedload(ProjectTask.comments)
    ).filter(ProjectTask.project_id == project_id)
    
    # Apply filters
    if status:
        query = query.filter(ProjectTask.status == status)
    
    if assignee_id:
        query = query.filter(ProjectTask.assignee_id == assignee_id)
    
    if priority:
        query = query.filter(ProjectTask.priority == priority)
    
    if search:
        query = query.filter(
            or_(
                ProjectTask.title.ilike(f"%{search}%"),
                ProjectTask.description.ilike(f"%{search}%")
            )
        )
    
    # Order by priority and due date
    query = query.order_by(
        ProjectTask.priority.desc(),
        ProjectTask.due_date.asc().nullslast(),
        ProjectTask.created_at.desc()
    )
    
    # Paginate
    tasks = paginate(query, pagination)
    
    return [format_task_response(task, db) for task in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get task details."""
    task = db.query(ProjectTask).options(
        joinedload(ProjectTask.assignee),
        joinedload(ProjectTask.creator),
        joinedload(ProjectTask.comments)
    ).filter(ProjectTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check project access
    if not is_project_member(current_user.id, task.project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this task"
        )
    
    return format_task_response(task, db)


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    update_data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update task details."""
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check project access
    if not is_project_member(current_user.id, task.project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this task"
        )
    
    # Verify new assignee if changed
    if update_data.assignee_id and update_data.assignee_id != task.assignee_id:
        if not is_project_member(update_data.assignee_id, task.project_id, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignee must be a project member"
            )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(task, field, value)
    
    # Update completed_at if status changed to done
    if update_data.status == "done" and task.completed_at is None:
        task.completed_at = datetime.utcnow()
    elif update_data.status != "done":
        task.completed_at = None
    
    db.commit()
    db.refresh(task)
    
    return format_task_response(task, db)


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a task."""
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check permission (creator or project admin)
    if task.created_by != current_user.id and not is_project_admin(current_user.id, task.project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this task"
        )
    
    db.delete(task)
    db.commit()
    
    return {"message": "Task deleted successfully"}


@router.post("/tasks/{task_id}/assign")
async def assign_task(
    task_id: UUID,
    assignment: TaskAssign,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Assign task to a user."""
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check project access
    if not is_project_member(current_user.id, task.project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to assign this task"
        )
    
    # Verify assignee is a project member
    if not is_project_member(assignment.assignee_id, task.project_id, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must be a project member"
        )
    
    task.assignee_id = assignment.assignee_id
    db.commit()
    
    return {"message": "Task assigned successfully"}


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: UUID,
    actual_hours: Optional[float] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark task as completed."""
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check if user is assignee or project member
    if task.assignee_id != current_user.id and not is_project_member(current_user.id, task.project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to complete this task"
        )
    
    task.status = "done"
    task.completed_at = datetime.utcnow()
    if actual_hours is not None:
        task.actual_hours = actual_hours
    
    db.commit()
    
    return {"message": "Task completed successfully"}


# Task Comments
@router.post("/tasks/{task_id}/comments", response_model=CommentResponse)
async def add_comment(
    task_id: UUID,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add comment to task."""
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check project access
    if not is_project_member(current_user.id, task.project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to comment on this task"
        )
    
    # Create comment
    comment = TaskComment(
        task_id=task_id,
        user_id=current_user.id,
        content=comment_data.content,
        attachments=comment_data.attachments
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return CommentResponse(
        id=str(comment.id),
        task_id=str(comment.task_id),
        user_id=str(comment.user_id),
        user_name=current_user.full_name or current_user.username or current_user.email,
        user_avatar=current_user.avatar_url,
        content=comment.content,
        attachments=comment.attachments,
        created_at=comment.created_at,
        updated_at=comment.updated_at
    )


@router.get("/tasks/{task_id}/comments", response_model=List[CommentResponse])
async def get_comments(
    task_id: UUID,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get task comments."""
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check project access
    if not is_project_member(current_user.id, task.project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view comments"
        )
    
    query = db.query(TaskComment).join(User).filter(
        TaskComment.task_id == task_id
    ).order_by(TaskComment.created_at.desc())
    
    comments = paginate(query, pagination)
    
    return [
        CommentResponse(
            id=str(comment.id),
            task_id=str(comment.task_id),
            user_id=str(comment.user_id),
            user_name=comment.user.full_name or comment.user.username or comment.user.email,
            user_avatar=comment.user.avatar_url,
            content=comment.content,
            attachments=comment.attachments,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        )
        for comment in comments
    ]


# Project Members
@router.post("/{project_id}/members")
async def add_project_member(
    project_id: UUID,
    member_data: ProjectMemberAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add member to project."""
    # Check permission
    if not is_project_admin(current_user.id, project_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add members"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == member_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if already a member
    existing = db.query(project_members).filter(
        and_(
            project_members.c.project_id == project_id,
            project_members.c.user_id == member_data.user_id
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a project member"
        )
    
    # Add member
    db.execute(
        project_members.insert().values(
            project_id=project_id,
            user_id=member_data.user_id,
            role=member_data.role,
            joined_at=datetime.utcnow()
        )
    )
    db.commit()
    
    return {"message": "Member added successfully"}


# Helper functions
def is_project_member(user_id: UUID, project_id: UUID, db: Session) -> bool:
    """Check if user is a project member."""
    member = db.query(project_members).filter(
        and_(
            project_members.c.project_id == project_id,
            project_members.c.user_id == user_id
        )
    ).first()
    
    return member is not None


def is_project_admin(user_id: UUID, project_id: UUID, db: Session) -> bool:
    """Check if user is project owner or admin member."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.owner_id == user_id:
        return True
    
    member = db.query(project_members).filter(
        and_(
            project_members.c.project_id == project_id,
            project_members.c.user_id == user_id,
            project_members.c.role == 'admin'
        )
    ).first()
    
    return member is not None


def format_project_response(project: Project, db: Session) -> ProjectResponse:
    """Format project response with computed fields."""
    completed_tasks = sum(1 for task in project.tasks if task.status == 'done')
    
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        project_type=project.project_type,
        status=project.status,
        priority=project.priority,
        owner_id=str(project.owner_id),
        team_id=str(project.team_id) if project.team_id else None,
        start_date=project.start_date,
        due_date=project.due_date,
        completed_at=project.completed_at,
        metadata=project.metadata,
        tags=project.tags,
        member_count=len(project.members),
        task_count=len(project.tasks),
        completed_task_count=completed_tasks,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


def format_task_response(task: ProjectTask, db: Session) -> TaskResponse:
    """Format task response with computed fields."""
    return TaskResponse(
        id=str(task.id),
        project_id=str(task.project_id),
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        assignee_id=str(task.assignee_id) if task.assignee_id else None,
        assignee_name=(task.assignee.full_name or task.assignee.username or task.assignee.email) if task.assignee else None,
        created_by=str(task.created_by),
        creator_name=task.creator.full_name or task.creator.username or task.creator.email,
        due_date=task.due_date,
        completed_at=task.completed_at,
        estimated_hours=task.estimated_hours,
        actual_hours=task.actual_hours,
        tags=task.tags,
        checklist=task.checklist,
        attachments=task.attachments,
        comment_count=len(task.comments) if hasattr(task, 'comments') else 0,
        created_at=task.created_at,
        updated_at=task.updated_at
    )