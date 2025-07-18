"""
Role-Based Access Control (RBAC) System

Comprehensive permissions system with:
- Multiple roles (Admin, Supervisor, Office, Field, User, Viewer)
- Resource-based permissions
- Hierarchical permission inheritance
- Field-level access control
- Dynamic permission evaluation
- Audit trail integration
"""

from typing import List, Dict, Any, Optional, Set, Union, Callable
from functools import wraps
from datetime import datetime
from enum import Enum
import json

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .audit import audit_log
from ..db.business_models import User, UserRole


class Permission(str, Enum):
    """Granular permissions for all system operations."""
    
    # User Management
    USERS_READ = "users.read"
    USERS_WRITE = "users.write"
    USERS_DELETE = "users.delete"
    USERS_ADMIN = "users.admin"
    
    # Project Management
    PROJECTS_READ = "projects.read"
    PROJECTS_WRITE = "projects.write"
    PROJECTS_DELETE = "projects.delete"
    PROJECTS_ASSIGN = "projects.assign"
    
    # Task Management
    TASKS_READ = "tasks.read"
    TASKS_WRITE = "tasks.write"
    TASKS_DELETE = "tasks.delete"
    TASKS_ASSIGN = "tasks.assign"
    TASKS_BULK_UPDATE = "tasks.bulk_update"
    
    # ERP - Estimating
    ESTIMATES_READ = "estimates.read"
    ESTIMATES_WRITE = "estimates.write"
    ESTIMATES_DELETE = "estimates.delete"
    ESTIMATES_APPROVE = "estimates.approve"
    ESTIMATES_SEND = "estimates.send"
    
    # ERP - Jobs
    JOBS_READ = "jobs.read"
    JOBS_WRITE = "jobs.write"
    JOBS_DELETE = "jobs.delete"
    JOBS_SCHEDULE = "jobs.schedule"
    JOBS_COMPLETE = "jobs.complete"
    
    # ERP - Field Operations
    FIELD_READ = "field.read"
    FIELD_WRITE = "field.write"
    FIELD_CAPTURE = "field.capture"
    FIELD_APPROVE = "field.approve"
    
    # ERP - Compliance
    COMPLIANCE_READ = "compliance.read"
    COMPLIANCE_WRITE = "compliance.write"
    COMPLIANCE_AUDIT = "compliance.audit"
    COMPLIANCE_APPROVE = "compliance.approve"
    
    # Financial
    FINANCE_READ = "finance.read"
    FINANCE_WRITE = "finance.write"
    FINANCE_APPROVE = "finance.approve"
    FINANCE_REPORTS = "finance.reports"
    
    # CRM
    CRM_READ = "crm.read"
    CRM_WRITE = "crm.write"
    CRM_DELETE = "crm.delete"
    CRM_EXPORT = "crm.export"
    
    # Automation
    AUTOMATION_READ = "automation.read"
    AUTOMATION_WRITE = "automation.write"
    AUTOMATION_EXECUTE = "automation.execute"
    AUTOMATION_ADMIN = "automation.admin"
    
    # AI Services
    AI_USE = "ai.use"
    AI_ADMIN = "ai.admin"
    
    # System
    SYSTEM_ADMIN = "system.admin"
    SYSTEM_LOGS = "system.logs"
    SYSTEM_CONFIG = "system.config"
    
    # Reports
    REPORTS_READ = "reports.read"
    REPORTS_CREATE = "reports.create"
    REPORTS_EXPORT = "reports.export"


# Role permission mappings
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: set(Permission),  # All permissions
    
    UserRole.SUPERVISOR: {
        # Full access to most operations
        Permission.USERS_READ, Permission.USERS_WRITE,
        Permission.PROJECTS_READ, Permission.PROJECTS_WRITE, Permission.PROJECTS_ASSIGN,
        Permission.TASKS_READ, Permission.TASKS_WRITE, Permission.TASKS_ASSIGN, Permission.TASKS_BULK_UPDATE,
        Permission.ESTIMATES_READ, Permission.ESTIMATES_WRITE, Permission.ESTIMATES_APPROVE, Permission.ESTIMATES_SEND,
        Permission.JOBS_READ, Permission.JOBS_WRITE, Permission.JOBS_SCHEDULE, Permission.JOBS_COMPLETE,
        Permission.FIELD_READ, Permission.FIELD_WRITE, Permission.FIELD_APPROVE,
        Permission.COMPLIANCE_READ, Permission.COMPLIANCE_WRITE, Permission.COMPLIANCE_APPROVE,
        Permission.FINANCE_READ, Permission.FINANCE_WRITE, Permission.FINANCE_APPROVE,
        Permission.CRM_READ, Permission.CRM_WRITE,
        Permission.AUTOMATION_READ, Permission.AUTOMATION_WRITE, Permission.AUTOMATION_EXECUTE,
        Permission.AI_USE,
        Permission.REPORTS_READ, Permission.REPORTS_CREATE, Permission.REPORTS_EXPORT,
    },
    
    UserRole.USER: {
        # Standard user - can manage their own work
        Permission.PROJECTS_READ,
        Permission.TASKS_READ, Permission.TASKS_WRITE,
        Permission.ESTIMATES_READ,
        Permission.JOBS_READ,
        Permission.FIELD_READ, Permission.FIELD_WRITE, Permission.FIELD_CAPTURE,
        Permission.COMPLIANCE_READ,
        Permission.CRM_READ, Permission.CRM_WRITE,
        Permission.AUTOMATION_READ, Permission.AUTOMATION_EXECUTE,
        Permission.AI_USE,
        Permission.REPORTS_READ,
    },
    
    UserRole.VIEWER: {
        # Read-only access
        Permission.PROJECTS_READ,
        Permission.TASKS_READ,
        Permission.ESTIMATES_READ,
        Permission.JOBS_READ,
        Permission.FIELD_READ,
        Permission.COMPLIANCE_READ,
        Permission.CRM_READ,
        Permission.AUTOMATION_READ,
        Permission.REPORTS_READ,
    }
}


# Add custom roles for field operations
class CustomRole(str, Enum):
    """Custom roles for specialized access."""
    FIELD_WORKER = "field_worker"
    OFFICE_STAFF = "office_staff"
    ACCOUNTANT = "accountant"
    SAFETY_OFFICER = "safety_officer"


# Custom role permissions
CUSTOM_ROLE_PERMISSIONS: Dict[CustomRole, Set[Permission]] = {
    CustomRole.FIELD_WORKER: {
        Permission.TASKS_READ, Permission.TASKS_WRITE,
        Permission.JOBS_READ,
        Permission.FIELD_READ, Permission.FIELD_WRITE, Permission.FIELD_CAPTURE,
        Permission.COMPLIANCE_READ,
    },
    
    CustomRole.OFFICE_STAFF: {
        Permission.PROJECTS_READ, Permission.PROJECTS_WRITE,
        Permission.TASKS_READ, Permission.TASKS_WRITE, Permission.TASKS_ASSIGN,
        Permission.ESTIMATES_READ, Permission.ESTIMATES_WRITE, Permission.ESTIMATES_SEND,
        Permission.JOBS_READ, Permission.JOBS_WRITE, Permission.JOBS_SCHEDULE,
        Permission.CRM_READ, Permission.CRM_WRITE,
        Permission.REPORTS_READ, Permission.REPORTS_CREATE,
    },
    
    CustomRole.ACCOUNTANT: {
        Permission.ESTIMATES_READ,
        Permission.JOBS_READ,
        Permission.FINANCE_READ, Permission.FINANCE_WRITE, Permission.FINANCE_REPORTS,
        Permission.REPORTS_READ, Permission.REPORTS_CREATE, Permission.REPORTS_EXPORT,
    },
    
    CustomRole.SAFETY_OFFICER: {
        Permission.JOBS_READ,
        Permission.FIELD_READ,
        Permission.COMPLIANCE_READ, Permission.COMPLIANCE_WRITE, Permission.COMPLIANCE_AUDIT,
        Permission.REPORTS_READ, Permission.REPORTS_CREATE,
    }
}


class PermissionContext:
    """Context for permission evaluation with resource details."""
    
    def __init__(
        self,
        user: User,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        field_filters: Optional[Dict[str, Any]] = None
    ):
        self.user = user
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
        self.field_filters = field_filters or {}
        self.timestamp = datetime.utcnow()


class RBACService:
    """Role-Based Access Control service."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_permissions(self, user: User) -> Set[Permission]:
        """Get all permissions for a user including custom roles."""
        permissions = set()
        
        # Base role permissions
        if user.role in ROLE_PERMISSIONS:
            permissions.update(ROLE_PERMISSIONS[user.role])
        
        # Custom role permissions (from user metadata)
        if hasattr(user, 'custom_roles'):
            for custom_role in user.custom_roles:
                if custom_role in CUSTOM_ROLE_PERMISSIONS:
                    permissions.update(CUSTOM_ROLE_PERMISSIONS[custom_role])
        
        # Additional permissions from groups/teams
        # This would query team memberships and aggregate permissions
        
        return permissions
    
    def has_permission(
        self,
        user: User,
        permission: Union[Permission, str],
        context: Optional[PermissionContext] = None
    ) -> bool:
        """Check if user has specific permission."""
        # Convert string to Permission enum if needed
        if isinstance(permission, str):
            try:
                permission = Permission(permission)
            except ValueError:
                return False
        
        # Get user's permissions
        user_permissions = self.get_user_permissions(user)
        
        # Check direct permission
        if permission in user_permissions:
            # Additional context-based checks
            if context:
                return self._evaluate_context(user, permission, context)
            return True
        
        # Check wildcard permissions
        resource = permission.value.split('.')[0]
        if Permission(f"{resource}.*") in user_permissions:
            return True
        
        return False
    
    def _evaluate_context(
        self,
        user: User,
        permission: Permission,
        context: PermissionContext
    ) -> bool:
        """Evaluate permission in context (ownership, field-level, etc)."""
        # Resource ownership check
        if context.resource_type and context.resource_id:
            if not self._check_resource_access(user, context):
                return False
        
        # Field-level access control
        if context.field_filters:
            if not self._check_field_access(user, permission, context.field_filters):
                return False
        
        # Time-based restrictions
        if hasattr(user, 'access_schedule'):
            if not self._check_time_access(user):
                return False
        
        return True
    
    def _check_resource_access(self, user: User, context: PermissionContext) -> bool:
        """Check if user can access specific resource."""
        # Admin can access everything
        if user.role == UserRole.ADMIN:
            return True
        
        # Check ownership based on resource type
        if context.resource_type == "project":
            from ..db.business_models import Project
            project = self.db.query(Project).filter_by(id=context.resource_id).first()
            if project:
                # Check if user is owner or member
                if project.owner_id == user.id:
                    return True
                if any(member.id == user.id for member in project.members):
                    return True
        
        elif context.resource_type == "task":
            from ..db.business_models import ProjectTask
            task = self.db.query(ProjectTask).filter_by(id=context.resource_id).first()
            if task:
                # Check if user created, is assigned, or is in crew
                if task.created_by == user.id or task.assignee_id == user.id:
                    return True
                if hasattr(task, 'crew_ids') and str(user.id) in task.crew_ids:
                    return True
        
        # Similar checks for other resource types...
        
        return False
    
    def _check_field_access(
        self,
        user: User,
        permission: Permission,
        field_filters: Dict[str, Any]
    ) -> bool:
        """Check field-level access restrictions."""
        # Define sensitive fields by resource
        sensitive_fields = {
            "users": ["hashed_password", "two_factor_secret"],
            "finance": ["bank_account", "tax_id"],
            "estimates": ["cost_breakdown", "profit_margin"],
        }
        
        # Check if user is trying to access sensitive fields
        for resource, fields in sensitive_fields.items():
            if permission.value.startswith(resource):
                requested_fields = field_filters.get("fields", [])
                if any(field in fields for field in requested_fields):
                    # Only admin can access sensitive fields
                    return user.role == UserRole.ADMIN
        
        return True
    
    def _check_time_access(self, user: User) -> bool:
        """Check time-based access restrictions."""
        # Implement business hours checks, temporary access, etc.
        return True
    
    def filter_response_fields(
        self,
        user: User,
        resource_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter response data based on user's field-level permissions."""
        # Define fields to remove for non-admin users
        restricted_fields = {
            "users": ["hashed_password", "two_factor_secret", "reset_token"],
            "estimates": ["cost_breakdown", "profit_margin"] if user.role not in [UserRole.ADMIN, UserRole.SUPERVISOR] else [],
            "finance": ["bank_details", "tax_info"] if user.role != UserRole.ADMIN else [],
        }
        
        # Remove restricted fields
        fields_to_remove = restricted_fields.get(resource_type, [])
        for field in fields_to_remove:
            data.pop(field, None)
        
        return data
    
    def get_resource_query_filters(self, user: User, resource_type: str) -> Dict[str, Any]:
        """Get query filters to limit resource access based on permissions."""
        filters = {}
        
        if user.role == UserRole.ADMIN:
            # Admin sees everything
            return filters
        
        # Resource-specific filters
        if resource_type == "projects":
            # Users see only their projects
            filters["or"] = [
                {"owner_id": user.id},
                {"members": {"contains": user.id}}
            ]
        
        elif resource_type == "tasks":
            # Users see tasks they created, are assigned to, or are in crew
            filters["or"] = [
                {"created_by": user.id},
                {"assignee_id": user.id},
                {"crew_ids": {"contains": str(user.id)}}
            ]
        
        elif resource_type == "estimates":
            # Based on role
            if user.role == UserRole.SUPERVISOR:
                # Supervisors see all estimates
                pass
            else:
                # Others see only their estimates
                filters["created_by"] = user.id
        
        return filters


# Dependency injection helpers
def get_rbac_service(db: Session = Depends(get_db)) -> RBACService:
    """Get RBAC service instance."""
    return RBACService(db)


def require_permission(permission: Union[Permission, str]):
    """Decorator to require specific permission."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies from kwargs
            current_user = kwargs.get('current_user')
            db = kwargs.get('db')
            request = kwargs.get('request')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Create RBAC service
            rbac = RBACService(db) if db else None
            
            # Build context
            context = PermissionContext(
                user=current_user,
                action=permission.value if isinstance(permission, Permission) else permission
            )
            
            # Extract resource info from request if available
            if request and hasattr(request, 'path_params'):
                context.resource_id = request.path_params.get('id')
                context.resource_type = request.url.path.split('/')[3]  # Extract from path
            
            # Check permission
            if not rbac or not rbac.has_permission(current_user, permission, context):
                # Audit failed access attempt
                await audit_log(
                    user_id=current_user.id,
                    action="access_denied",
                    resource_type="permission",
                    details={
                        "permission": permission.value if isinstance(permission, Permission) else permission,
                        "context": context.__dict__ if context else None
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission.value if isinstance(permission, Permission) else permission}"
                )
            
            # Audit successful access
            await audit_log(
                user_id=current_user.id,
                action="access_granted",
                resource_type="permission",
                details={"permission": permission.value if isinstance(permission, Permission) else permission}
            )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_permission(*permissions: Union[Permission, str]):
    """Decorator to require any of the specified permissions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            db = kwargs.get('db')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            rbac = RBACService(db) if db else None
            
            # Check if user has any of the required permissions
            for permission in permissions:
                if rbac and rbac.has_permission(current_user, permission):
                    return await func(*args, **kwargs)
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required one of: {[p.value if isinstance(p, Permission) else p for p in permissions]}"
            )
        
        return wrapper
    return decorator


def require_all_permissions(*permissions: Union[Permission, str]):
    """Decorator to require all specified permissions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            db = kwargs.get('db')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            rbac = RBACService(db) if db else None
            
            # Check if user has all required permissions
            missing_permissions = []
            for permission in permissions:
                if not rbac or not rbac.has_permission(current_user, permission):
                    missing_permissions.append(permission.value if isinstance(permission, Permission) else permission)
            
            if missing_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Missing: {missing_permissions}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# FastAPI dependency for permission checking
class PermissionChecker:
    """Dependency class for permission checking in route handlers."""
    
    def __init__(self, permission: Union[Permission, str]):
        self.permission = permission
    
    def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        """Check permission and return user if authorized."""
        rbac = RBACService(db)
        
        if not rbac.has_permission(current_user, self.permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {self.permission.value if isinstance(self.permission, Permission) else self.permission}"
            )
        
        return current_user


# Utility functions for common permission checks
def can_read_resource(
    user: User,
    resource_type: str,
    resource_id: Optional[str] = None,
    db: Optional[Session] = None
) -> bool:
    """Check if user can read a resource."""
    permission = Permission(f"{resource_type}.read")
    rbac = RBACService(db) if db else None
    
    context = PermissionContext(
        user=user,
        resource_type=resource_type,
        resource_id=resource_id,
        action="read"
    ) if resource_id else None
    
    return rbac.has_permission(user, permission, context) if rbac else False


def can_write_resource(
    user: User,
    resource_type: str,
    resource_id: Optional[str] = None,
    db: Optional[Session] = None
) -> bool:
    """Check if user can write/update a resource."""
    permission = Permission(f"{resource_type}.write")
    rbac = RBACService(db) if db else None
    
    context = PermissionContext(
        user=user,
        resource_type=resource_type,
        resource_id=resource_id,
        action="write"
    ) if resource_id else None
    
    return rbac.has_permission(user, permission, context) if rbac else False


def can_delete_resource(
    user: User,
    resource_type: str,
    resource_id: Optional[str] = None,
    db: Optional[Session] = None
) -> bool:
    """Check if user can delete a resource."""
    permission = Permission(f"{resource_type}.delete")
    rbac = RBACService(db) if db else None
    
    context = PermissionContext(
        user=user,
        resource_type=resource_type,
        resource_id=resource_id,
        action="delete"
    ) if resource_id else None
    
    return rbac.has_permission(user, permission, context) if rbac else False