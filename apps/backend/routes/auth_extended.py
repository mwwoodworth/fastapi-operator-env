"""
Extended authentication routes for BrainOps backend.

Implements additional auth features like 2FA, password reset, API keys, and session management.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import secrets
import pyotp
import qrcode
import io
import base64

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from ..core.database import get_db
from ..core.auth import get_current_user, create_access_token, verify_password, get_password_hash
from ..core.email import send_email
from ..core.settings import settings
from ..db.business_models import User, APIKey, UserSession
from ..memory.models import User as UserModel

router = APIRouter()
security = HTTPBearer()


# Pydantic models for requests/responses
class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class TwoFactorEnableResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: List[str]


class TwoFactorVerify(BaseModel):
    code: str


class APIKeyCreate(BaseModel):
    name: str
    scopes: List[str] = []
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key: str  # Only returned on creation
    prefix: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime]


class SessionResponse(BaseModel):
    id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    last_activity: datetime
    is_current: bool


# Helper functions
def generate_reset_token() -> str:
    """Generate a secure password reset token."""
    return secrets.token_urlsafe(32)


def generate_api_key() -> tuple[str, str, str]:
    """Generate API key, hash, and prefix."""
    key = f"brainops_{secrets.token_urlsafe(32)}"
    prefix = key[:12]
    # In production, use proper hashing
    key_hash = get_password_hash(key)
    return key, key_hash, prefix


def generate_backup_codes() -> List[str]:
    """Generate 2FA backup codes."""
    return [secrets.token_hex(4) for _ in range(10)]


def generate_qr_code(secret: str, email: str) -> str:
    """Generate QR code for 2FA setup."""
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name='BrainOps'
    )
    
    # For testing, return the provisioning URI as the QR code
    # In production, you would use a library like PIL to generate an actual image
    return provisioning_uri


# Password Reset Endpoints
@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Request password reset email.
    
    Always returns success to prevent email enumeration.
    """
    user = db.query(User).filter(User.email == request.email).first()
    
    if user and user.is_active:
        # Generate reset token
        reset_token = generate_reset_token()
        
        # Store token in database (in production, use Redis with expiry)
        user.reset_token = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        
        # Send reset email
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        background_tasks.add_task(
            send_email,
            to_email=user.email,
            subject="Reset Your Password",
            body=f"Click here to reset your password: {reset_url}\n\nThis link expires in 1 hour."
        )
    
    return {"message": "If an account exists with this email, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """Reset password using token from email."""
    user = db.query(User).filter(
        User.reset_token == request.token,
        User.reset_token_expires > datetime.utcnow()
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update password
    user.hashed_password = get_password_hash(request.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    
    return {"message": "Password successfully reset"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resend email verification link."""
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Generate verification token
    verification_token = generate_reset_token()
    current_user.verification_token = verification_token
    current_user.verification_token_expires = datetime.utcnow() + timedelta(hours=24)
    db.commit()
    
    # Send verification email
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    background_tasks.add_task(
        send_email,
        to_email=current_user.email,
        subject="Verify Your Email",
        body=f"Click here to verify your email: {verify_url}\n\nThis link expires in 24 hours."
    )
    
    return {"message": "Verification email sent"}


# Two-Factor Authentication Endpoints
@router.post("/two-factor/enable", response_model=TwoFactorEnableResponse)
async def enable_two_factor(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enable two-factor authentication."""
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication already enabled"
        )
    
    # Generate secret
    secret = pyotp.random_base32()
    
    # Generate backup codes
    backup_codes = generate_backup_codes()
    
    # Store temporarily (confirm with code before fully enabling)
    current_user.two_factor_secret_temp = secret
    current_user.two_factor_backup_codes = backup_codes
    db.commit()
    
    # Generate QR code
    qr_code = generate_qr_code(secret, current_user.email)
    
    return TwoFactorEnableResponse(
        secret=secret,
        qr_code=qr_code,
        backup_codes=backup_codes
    )


@router.post("/two-factor/confirm", status_code=status.HTTP_200_OK)
async def confirm_two_factor(
    request: TwoFactorVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm 2FA setup with initial code."""
    if not current_user.two_factor_secret_temp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending 2FA setup"
        )
    
    # Verify code
    totp = pyotp.TOTP(current_user.two_factor_secret_temp)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Enable 2FA
    current_user.two_factor_enabled = True
    current_user.two_factor_secret = current_user.two_factor_secret_temp
    current_user.two_factor_secret_temp = None
    db.commit()
    
    return {"message": "Two-factor authentication enabled successfully"}


@router.post("/two-factor/disable", status_code=status.HTTP_200_OK)
async def disable_two_factor(
    request: TwoFactorVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable two-factor authentication."""
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication not enabled"
        )
    
    # Verify code or backup code
    totp = pyotp.TOTP(current_user.two_factor_secret)
    valid = totp.verify(request.code, valid_window=1)
    
    if not valid and current_user.two_factor_backup_codes:
        # Check backup codes
        if request.code in current_user.two_factor_backup_codes:
            valid = True
            current_user.two_factor_backup_codes.remove(request.code)
    
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Disable 2FA
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.two_factor_backup_codes = []
    db.commit()
    
    return {"message": "Two-factor authentication disabled"}


@router.post("/two-factor/verify", status_code=status.HTTP_200_OK)
async def verify_two_factor(
    request: TwoFactorVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify 2FA code during login."""
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication not enabled"
        )
    
    # Verify code
    totp = pyotp.TOTP(current_user.two_factor_secret)
    if not totp.verify(request.code, valid_window=1):
        # Check backup codes
        if request.code in current_user.two_factor_backup_codes:
            current_user.two_factor_backup_codes.remove(request.code)
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )
    
    # Generate new tokens with 2FA verified flag
    access_token = create_access_token(
        data={"sub": current_user.email, "2fa_verified": True}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# Session Management Endpoints
@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all active sessions for current user."""
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.utcnow()
    ).all()
    
    # Get current session from token
    current_session_id = None  # Extract from JWT if stored
    
    return [
        SessionResponse(
            id=str(session.id),
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            created_at=session.created_at,
            last_activity=session.last_activity,
            is_current=str(session.id) == current_session_id
        )
        for session in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke a specific session."""
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session.is_active = False
    db.commit()
    
    return {"message": "Session revoked successfully"}


@router.delete("/sessions", status_code=status.HTTP_200_OK)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke all sessions except current."""
    # Get current session ID from token
    current_session_id = None  # Extract from JWT if stored
    
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.id != current_session_id
    ).update({"is_active": False})
    
    db.commit()
    
    return {"message": "All other sessions revoked"}


# API Key Management Endpoints
@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new API key."""
    # Check user's API key limit
    key_count = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.is_active == True
    ).count()
    
    if key_count >= settings.MAX_API_KEYS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {settings.MAX_API_KEYS_PER_USER} API keys allowed"
        )
    
    # Generate key
    key, key_hash, prefix = generate_api_key()
    
    # Calculate expiry
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    # Create API key record
    api_key = APIKey(
        user_id=current_user.id,
        name=request.name,
        key_hash=key_hash,
        prefix=prefix,
        scopes=request.scopes,
        expires_at=expires_at
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return APIKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=key,  # Only returned on creation
        prefix=api_key.prefix,
        scopes=api_key.scopes,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at
    )


@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all API keys for current user."""
    keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.is_active == True
    ).all()
    
    return [
        APIKeyResponse(
            id=str(key.id),
            name=key.name,
            key="",  # Never return actual key after creation
            prefix=key.prefix,
            scopes=key.scopes,
            created_at=key.created_at,
            expires_at=key.expires_at
        )
        for key in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_200_OK)
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke an API key."""
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = False
    db.commit()
    
    return {"message": "API key revoked successfully"}