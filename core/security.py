"""Enhanced security module for BrainOps FastAPI backend."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.settings import Settings
from db.models import User
from db.session import get_db
from utils.metrics import SECURITY_EVENTS

settings = Settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# JWT settings
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class Token(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token data extracted from JWT."""
    username: Optional[str] = None
    user_id: Optional[int] = None
    roles: list[str] = []
    scopes: list[str] = []


class UserInDB(BaseModel):
    """User model with hashed password."""
    id: int
    username: str
    email: str
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    roles: list[str] = []
    created_at: datetime
    updated_at: datetime


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": secrets.token_urlsafe(32)  # Unique token ID
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "access":
            raise credentials_exception
            
        token_data = TokenData(
            username=username,
            user_id=user_id,
            roles=payload.get("roles", []),
            scopes=payload.get("scopes", [])
        )
    except JWTError as e:
        SECURITY_EVENTS.labels(event="jwt_error").inc()
        raise credentials_exception from e
    
    # Get user from database
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        SECURITY_EVENTS.labels(event="user_not_found").inc()
        raise credentials_exception
        
    if not user.is_active:
        SECURITY_EVENTS.labels(event="inactive_user").inc()
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Store user in request state for logging
    request.state.user = user
    
    return user


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get the current active superuser."""
    if not current_user.is_superuser:
        SECURITY_EVENTS.labels(event="unauthorized_admin_access").inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def check_api_key(request: Request, x_api_key: str = Depends(lambda: None)) -> Optional[str]:
    """Check API key for webhook endpoints."""
    # Extract API key from header
    api_key = request.headers.get("X-API-Key") or x_api_key
    
    # Define endpoint-specific API keys
    webhook_keys = {
        "/webhook/stripe": settings.STRIPE_WEBHOOK_SECRET,
        "/webhook/clickup": settings.CLICKUP_API_TOKEN,
        "/webhook/notion": settings.NOTION_API_KEY,
        "/webhook/make": settings.MAKE_WEBHOOK_SECRET,
    }
    
    # Check if endpoint requires API key
    path = request.url.path
    for endpoint, expected_key in webhook_keys.items():
        if path.startswith(endpoint):
            if not api_key or api_key != expected_key:
                SECURITY_EVENTS.labels(event="invalid_api_key").inc()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )
            return api_key
    
    return None


class RateLimiter:
    """Custom rate limiter with user-specific limits."""
    
    def __init__(self):
        self.requests = {}
        
    async def check_rate_limit(
        self,
        request: Request,
        user: Optional[User] = None,
        limit: int = 100,
        window: int = 60
    ) -> bool:
        """Check if request exceeds rate limit."""
        # Use user ID if authenticated, otherwise IP
        if user:
            key = f"user:{user.id}"
            # Higher limits for authenticated users
            limit = limit * 2
        else:
            key = f"ip:{request.client.host}"
        
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(seconds=window)
        
        # Clean old entries
        if key in self.requests:
            self.requests[key] = [
                timestamp for timestamp in self.requests[key]
                if timestamp > minute_ago
            ]
        else:
            self.requests[key] = []
        
        # Check limit
        if len(self.requests[key]) >= limit:
            SECURITY_EVENTS.labels(event="rate_limit_exceeded").inc()
            return False
        
        # Add current request
        self.requests[key].append(now)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter()


async def validate_request_size(request: Request, max_size: int = 10 * 1024 * 1024):
    """Validate request body size (default 10MB)."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        SECURITY_EVENTS.labels(event="request_too_large").inc()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request body too large"
        )


def create_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


class SecurityHeaders:
    """Security headers middleware."""
    
    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # CORS headers for MyRoofGenius frontend
        if settings.ENVIRONMENT == "production":
            response.headers["Access-Control-Allow-Origin"] = "https://myroofgenius.com"
        else:
            response.headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
        
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key"
        
        return response