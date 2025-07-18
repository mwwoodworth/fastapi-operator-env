"""
User and team management routes for BrainOps backend.

Handles user profiles, team creation, membership, and administration.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from pydantic import BaseModel, EmailStr

from ..core.database import get_db
from ..core.auth import get_current_user, require_admin
from ..core.permissions import require_permission
from ..db.business_models import User, Team, UserRole, team_members
from ..core.pagination import paginate, PaginationParams

router = APIRouter()


# Pydantic models
class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]


class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class UserAdminUpdate(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class TeamCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    max_members: Optional[int] = None


class TeamResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    website: Optional[str]
    owner_id: str
    member_count: int
    created_at: datetime


class TeamMember(BaseModel):
    user_id: str
    email: str
    username: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    role: str
    joined_at: datetime


class MemberRoleUpdate(BaseModel):
    role: str  # admin, member, viewer


class UserActivity(BaseModel):
    timestamp: datetime
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: dict


# Helper functions
def is_team_admin(user_id: UUID, team_id: UUID, db: Session) -> bool:
    """Check if user is team owner or admin member."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if team and team.owner_id == user_id:
        return True
    
    member = db.query(team_members).filter(
        and_(
            team_members.c.team_id == team_id,
            team_members.c.user_id == user_id,
            team_members.c.role == 'admin'
        )
    ).first()
    
    return member is not None


# User Management Endpoints - List users first (no path params)
@router.get("/", response_model=List[UserResponse])
async def list_users(
    search: Optional[str] = None,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users (admin only).
    
    Supports filtering by search term, role, and active status.
    """
    query = db.query(User)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                User.email.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
        )
    
    if role:
        query = query.filter(User.role == role)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # Order by creation date
    query = query.order_by(User.created_at.desc())
    
    # Paginate
    users = paginate(query, pagination)
    
    return [
        UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            bio=user.bio,
            role=user.role.value,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login
        )
        for user in users
    ]


# Team Management Endpoints - All team routes BEFORE user-specific routes
@router.post("/teams", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new team."""
    # Check if slug is unique
    existing = db.query(Team).filter(Team.slug == team_data.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team slug already exists"
        )
    
    # Create team
    team = Team(
        name=team_data.name,
        slug=team_data.slug,
        description=team_data.description,
        logo_url=team_data.logo_url,
        website=team_data.website,
        owner_id=current_user.id
    )
    
    db.add(team)
    db.commit()
    
    # Add owner as admin member
    db.execute(
        team_members.insert().values(
            team_id=team.id,
            user_id=current_user.id,
            role='admin',
            joined_at=datetime.utcnow()
        )
    )
    db.commit()
    db.refresh(team)
    
    return TeamResponse(
        id=str(team.id),
        name=team.name,
        slug=team.slug,
        description=team.description,
        logo_url=team.logo_url,
        website=team.website,
        owner_id=str(team.owner_id),
        member_count=1,
        created_at=team.created_at
    )


@router.get("/teams", response_model=List[TeamResponse])
async def list_teams(
    search: Optional[str] = None,
    my_teams: bool = False,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List teams."""
    query = db.query(Team).options(joinedload(Team.members))
    
    # Filter by membership if requested
    if my_teams:
        query = query.join(team_members).filter(
            team_members.c.user_id == current_user.id
        )
    
    # Search filter
    if search:
        query = query.filter(
            or_(
                Team.name.ilike(f"%{search}%"),
                Team.description.ilike(f"%{search}%")
            )
        )
    
    # Only show active teams
    query = query.filter(Team.is_active == True)
    
    # Order by creation date
    query = query.order_by(Team.created_at.desc())
    
    # Paginate
    teams = paginate(query, pagination)
    
    return [
        TeamResponse(
            id=str(team.id),
            name=team.name,
            slug=team.slug,
            description=team.description,
            logo_url=team.logo_url,
            website=team.website,
            owner_id=str(team.owner_id),
            member_count=len(team.members),
            created_at=team.created_at
        )
        for team in teams
    ]


@router.get("/teams/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get team details."""
    team = db.query(Team).options(joinedload(Team.members)).filter(
        Team.id == team_id
    ).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    return TeamResponse(
        id=str(team.id),
        name=team.name,
        slug=team.slug,
        description=team.description,
        logo_url=team.logo_url,
        website=team.website,
        owner_id=str(team.owner_id),
        member_count=len(team.members),
        created_at=team.created_at
    )


@router.put("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: UUID,
    update_data: TeamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update team details."""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check permission (owner or admin member)
    if not is_team_admin(current_user.id, team_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this team"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(team, field, value)
    
    db.commit()
    db.refresh(team)
    
    return TeamResponse(
        id=str(team.id),
        name=team.name,
        slug=team.slug,
        description=team.description,
        logo_url=team.logo_url,
        website=team.website,
        owner_id=str(team.owner_id),
        member_count=len(team.members),
        created_at=team.created_at
    )


@router.delete("/teams/{team_id}")
async def delete_team(
    team_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a team (owner only)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    if team.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team owner can delete the team"
        )
    
    # Soft delete
    team.is_active = False
    team.deleted_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Team deleted successfully"}


@router.get("/teams/{team_id}/members", response_model=List[TeamMember])
async def list_team_members(
    team_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List team members."""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Get members with their roles
    members = db.query(User, team_members.c.role, team_members.c.joined_at).join(
        team_members, User.id == team_members.c.user_id
    ).filter(team_members.c.team_id == team_id).all()
    
    return [
        TeamMember(
            user_id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            role=role,
            joined_at=joined_at
        )
        for user, role, joined_at in members
    ]


class AddTeamMemberRequest(BaseModel):
    user_email: EmailStr
    role: str = "member"


@router.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: UUID,
    request: AddTeamMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a member to the team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check permission
    if not is_team_admin(current_user.id, team_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add members to this team"
        )
    
    # Find user by email
    new_member = db.query(User).filter(User.email == request.user_email).first()
    if not new_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if already a member
    existing = db.query(team_members).filter(
        and_(
            team_members.c.team_id == team_id,
            team_members.c.user_id == new_member.id
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a team member"
        )
    
    # Check team member limit
    member_count = db.query(team_members).filter(
        team_members.c.team_id == team_id
    ).count()
    
    if member_count >= team.max_members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team member limit ({team.max_members}) reached"
        )
    
    # Add member
    db.execute(
        team_members.insert().values(
            team_id=team_id,
            user_id=new_member.id,
            role=request.role,
            joined_at=datetime.utcnow()
        )
    )
    db.commit()
    
    return {"message": "Member added successfully"}


@router.delete("/teams/{team_id}/members/{user_id}")
async def remove_team_member(
    team_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a member from the team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check permission
    if not is_team_admin(current_user.id, team_id, db) and str(user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to remove members from this team"
        )
    
    # Cannot remove team owner
    if str(user_id) == str(team.owner_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove team owner"
        )
    
    # Remove member
    result = db.execute(
        team_members.delete().where(
            and_(
                team_members.c.team_id == team_id,
                team_members.c.user_id == user_id
            )
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in team"
        )
    
    db.commit()
    
    return {"message": "Member removed successfully"}


@router.put("/teams/{team_id}/members/{user_id}/role")
async def update_member_role(
    team_id: UUID,
    user_id: UUID,
    role_update: MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a team member's role."""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check permission
    if not is_team_admin(current_user.id, team_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update member roles"
        )
    
    # Cannot change owner's role
    if str(user_id) == str(team.owner_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change team owner's role"
        )
    
    # Update role
    result = db.execute(
        team_members.update().where(
            and_(
                team_members.c.team_id == team_id,
                team_members.c.user_id == user_id
            )
        ).values(role=role_update.role)
    )
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in team"
        )
    
    db.commit()
    
    return {"message": "Member role updated successfully"}


# User-specific endpoints - AFTER all team routes
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user details."""
    # Users can view their own profile, admins can view anyone
    if str(user_id) != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        role=user.role.value,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile."""
    # Users can update their own profile
    if str(user_id) != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        role=user.role.value,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login
    )


@router.put("/{user_id}/admin", response_model=UserResponse)
async def admin_update_user(
    user_id: UUID,
    update_data: UserAdminUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user administrative settings (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-demotion
    if str(user_id) == str(current_user.id) and update_data.role and update_data.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own admin role"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        role=user.role.value,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)."""
    if str(user_id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Soft delete by deactivating
    user.is_active = False
    user.deleted_at = datetime.utcnow()
    db.commit()
    
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Suspend a user account (admin only)."""
    if str(user_id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend your own account"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    user.suspended_at = datetime.utcnow()
    db.commit()
    
    return {"message": "User suspended successfully"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate a suspended user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = True
    user.suspended_at = None
    db.commit()
    
    return {"message": "User activated successfully"}


@router.get("/{user_id}/activity", response_model=List[UserActivity])
async def get_user_activity(
    user_id: UUID,
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user activity history."""
    # Users can view their own activity, admins can view anyone's
    if str(user_id) != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's activity"
        )
    
    # In a real implementation, this would query an activity log table
    # For now, return mock data
    return [
        UserActivity(
            timestamp=datetime.utcnow(),
            action="login",
            resource_type="session",
            resource_id=None,
            details={"ip": "127.0.0.1"}
        )
    ]