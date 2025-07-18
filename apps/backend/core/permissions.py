"""
Permission management utilities for BrainOps backend.
"""

from typing import List, Optional
from functools import wraps
from fastapi import Depends, HTTPException, status

from .auth import get_current_user
from ..db.business_models import User, UserRole


def require_permission(permission: str):
    """
    Decorator to require specific permission for endpoint access.
    
    Usage:
        @router.get("/admin/users")
        @require_permission("users.read")
        async def list_users(...):
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check permission
            if not has_permission(current_user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user


def require_role(role: UserRole):
    """Dependency factory to require specific role."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role.value}' required"
            )
        
        return current_user
    
    return role_checker


def has_permission(user: User, permission: str) -> bool:
    """
    Check if user has specific permission.
    
    Permission format: resource.action
    Examples: users.read, projects.write, admin.all
    """
    # Admin has all permissions
    if user.role == UserRole.ADMIN:
        return True
    
    # Define role-based permissions
    role_permissions = {
        UserRole.USER: [
            "projects.read",
            "projects.write",
            "tasks.read",
            "tasks.write",
            "teams.read",
            "ai.use",
            "memory.read",
            "memory.write",
            "workflows.read",
            "workflows.write",
            "integrations.read",
            "integrations.write"
        ],
        UserRole.VIEWER: [
            "projects.read",
            "tasks.read",
            "teams.read",
            "memory.read",
            "workflows.read",
            "integrations.read"
        ]
    }
    
    # Get user's permissions based on role
    user_permissions = role_permissions.get(user.role, [])
    
    # Check exact permission
    if permission in user_permissions:
        return True
    
    # Check wildcard permissions (e.g., projects.* matches projects.read)
    resource = permission.split('.')[0]
    if f"{resource}.*" in user_permissions:
        return True
    
    return False


def get_user_permissions(user: User) -> List[str]:
    """Get list of all permissions for a user."""
    if user.role == UserRole.ADMIN:
        # Admin has all permissions
        return ["*"]
    
    # Return role-based permissions
    role_permissions = {
        UserRole.USER: [
            "projects.*",
            "tasks.*",
            "teams.read",
            "ai.use",
            "memory.*",
            "workflows.*",
            "integrations.*"
        ],
        UserRole.VIEWER: [
            "*.read"
        ]
    }
    
    return role_permissions.get(user.role, [])


def check_resource_ownership(user: User, resource_type: str, resource_id: str, db) -> bool:
    """
    Check if user owns or has access to a specific resource.
    
    This is a placeholder for more complex ownership checks.
    """
    # Admin can access everything
    if user.role == UserRole.ADMIN:
        return True
    
    # Implement resource-specific ownership checks
    # This would query the database to check ownership
    
    return True  # Placeholder


class PermissionChecker:
    """
    Class-based permission checker for more complex scenarios.
    """
    
    def __init__(self, user: User):
        self.user = user
        self.permissions = get_user_permissions(user)
    
    def can(self, permission: str) -> bool:
        """Check if user can perform action."""
        return has_permission(self.user, permission)
    
    def cannot(self, permission: str) -> bool:
        """Check if user cannot perform action."""
        return not self.can(permission)
    
    def require(self, permission: str):
        """Require permission or raise exception."""
        if not self.can(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
    
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.user.role == UserRole.ADMIN
    
    def owns_resource(self, resource_type: str, resource_id: str, db) -> bool:
        """Check resource ownership."""
        return check_resource_ownership(self.user, resource_type, resource_id, db)