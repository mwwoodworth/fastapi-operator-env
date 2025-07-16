"""
Authentication and Authorization Routes

This module handles user authentication, token management, and session control
for the BrainOps platform. Implements JWT-based authentication with refresh
tokens and secure password handling.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets

from .core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_current_active_user
)
from .core.settings import settings
from .memory.models import User, UserCreate, UserLogin, TokenResponse
from .memory.memory_store import (
    get_user_by_email,
    create_user,
    update_user_last_login,
    invalidate_refresh_token,
    validate_refresh_token
)


router = APIRouter()


@router.post("/register", response_model=User)
async def register(user_data: UserCreate) -> User:
    """
    Register a new user account.
    
    Creates a new user with hashed password and sends verification email
    if email service is configured.
    """
    # Check if user already exists
    existing_user = await get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash the password before storage
    hashed_password = get_password_hash(user_data.password)
    
    # Create user record with additional metadata
    user = await create_user(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        company=user_data.company,
        role=user_data.role or "user"
    )
    
    # TODO: Send verification email if email service is configured
    # await send_verification_email(user.email, user.verification_token)
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """
    Authenticate user and return access/refresh tokens.
    
    Validates credentials and returns JWT tokens for API access.
    """
    # Authenticate user credentials
    user = await get_user_by_email(form_data.username)  # username is email
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support."
        )
    
    # Generate access and refresh tokens
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.email, "user_id": user.id}
    )
    
    # Update last login timestamp
    await update_user_last_login(user.id)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str) -> TokenResponse:
    """
    Refresh access token using valid refresh token.
    
    Validates refresh token and issues new access token without
    requiring password re-authentication.
    """
    # Decode and validate refresh token
    try:
        payload = decode_token(refresh_token)
        email = payload.get("sub")
        user_id = payload.get("user_id")
        
        if not email or not user_id:
            raise ValueError("Invalid token payload")
            
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Validate token hasn't been revoked
    is_valid = await validate_refresh_token(refresh_token, user_id)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked"
        )
    
    # Get user and verify still active
    user = await get_user_by_email(email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive"
        )
    
    # Issue new access token (keep same refresh token)
    new_access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}
    )
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token,  # Return same refresh token
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(
    refresh_token: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Logout user and invalidate refresh token.
    
    Revokes the provided refresh token to prevent further use.
    Access tokens remain valid until expiration.
    """
    # Invalidate the refresh token
    await invalidate_refresh_token(refresh_token, current_user.id)
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current authenticated user profile.
    
    Returns full user profile information for the authenticated user.
    """
    return current_user


@router.put("/me", response_model=User)
async def update_profile(
    profile_update: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Update current user profile.
    
    Allows users to update their profile information except
    for email and password (use dedicated endpoints).
    """
    # Prevent updating sensitive fields through this endpoint
    protected_fields = {"email", "hashed_password", "id", "created_at", "is_active"}
    update_data = {k: v for k, v in profile_update.items() if k not in protected_fields}
    
    # Update user profile
    updated_user = await update_user_profile(current_user.id, update_data)
    
    return updated_user


@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """
    Change user password.
    
    Requires current password verification before updating to new password.
    """
    # Verify current password
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Hash and update password
    new_hashed_password = get_password_hash(new_password)
    await update_user_password(current_user.id, new_hashed_password)
    
    # Invalidate all existing refresh tokens for security
    await invalidate_all_user_tokens(current_user.id)
    
    return {"message": "Password successfully changed. Please login again."}


@router.post("/verify-email/{token}")
async def verify_email(token: str) -> Dict[str, str]:
    """
    Verify user email address using verification token.
    
    Completes email verification process for new user accounts.
    """
    # Validate and process email verification token
    user = await verify_email_token(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    return {"message": "Email successfully verified. You can now login."}
