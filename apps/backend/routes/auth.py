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

from ..core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from ..core.auth import authenticate_user
from ..core.settings import settings
from ..db.business_models import User
from ..core.database import get_db
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..core.auth_utils import (
    get_user_by_email,
    create_user,
    update_user_last_login,
    invalidate_refresh_token,
    validate_refresh_token,
    update_user_profile,
    update_user_password,
    invalidate_all_user_tokens,
    verify_email_token
)
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

security = HTTPBearer()

# Pydantic models for auth
class UserCreate(BaseModel):
    email: str
    username: Optional[str] = None
    password: str
    full_name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = "USER"

class UserLogin(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from token."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials - no email in token"
            )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials - JWT error: {str(e)}"
        )
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Creates a new user with hashed password and sends verification email
    if email service is configured.
    """
    # Check if user already exists
    existing_user = await get_user_by_email(user_data.email, db)
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
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        company=user_data.company,
        role=user_data.role or "USER",
        db=db
    )
    
    # TODO: Send verification email if email service is configured
    # await send_verification_email(user.email, user.verification_token)
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    """
    Authenticate user and return access/refresh tokens.
    
    Validates credentials and returns JWT tokens for API access.
    """
    # Authenticate user credentials
    user = await authenticate_user(form_data.username, form_data.password, db)
    
    if not user:
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
        data={"sub": user.email, "user_id": str(user.id)}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.email, "user_id": str(user.id)}
    )
    
    # Update last login timestamp
    await update_user_last_login(str(user.id), db)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Refresh access token using valid refresh token.
    
    Validates refresh token and issues new access token without
    requiring password re-authentication.
    """
    # Decode and validate refresh token
    try:
        payload = decode_token(request.refresh_token)
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
    is_valid = await validate_refresh_token(request.refresh_token, user_id, db)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked"
        )
    
    # Get user and verify still active
    user = await get_user_by_email(email, db)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive"
        )
    
    # Issue new access token (keep same refresh token)
    new_access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id)}
    )
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=request.refresh_token,  # Return same refresh token
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Logout user and invalidate refresh token.
    
    Revokes the provided refresh token to prevent further use.
    Access tokens remain valid until expiration.
    """
    # Invalidate the refresh token
    await invalidate_refresh_token(request.refresh_token, str(current_user.id), db)
    
    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current authenticated user profile.
    
    Returns full user profile information for the authenticated user.
    """
    return current_user


@router.put("/me")
async def update_profile(
    profile_update: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update current user profile.
    
    Allows users to update their profile information except
    for email and password (use dedicated endpoints).
    """
    # Prevent updating sensitive fields through this endpoint
    protected_fields = {"email", "hashed_password", "id", "created_at", "is_active"}
    update_data = {k: v for k, v in profile_update.items() if k not in protected_fields}
    
    # Update user profile
    updated_user = await update_user_profile(str(current_user.id), update_data, db)
    
    return updated_user


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Change user password.
    
    Requires current password verification before updating to new password.
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Hash and update password
    new_hashed_password = get_password_hash(request.new_password)
    await update_user_password(str(current_user.id), new_hashed_password, db)
    
    # Invalidate all existing refresh tokens for security
    await invalidate_all_user_tokens(str(current_user.id), db)
    
    return {"message": "Password successfully changed. Please login again."}


@router.post("/verify-email/{token}")
async def verify_email(token: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    Verify user email address using verification token.
    
    Completes email verification process for new user accounts.
    """
    # Validate and process email verification token
    user = await verify_email_token(token, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    return {"message": "Email successfully verified. You can now login."}
