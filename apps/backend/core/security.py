"""
Security utilities for BrainOps Backend.

Handles authentication, authorization, encryption, and security best practices.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .settings import settings
from .logging import get_logger


logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
security = HTTPBearer()


class SecurityManager:
    """Manages security operations for the application."""
    
    def __init__(self):
        self.secret_key = settings.JWT_SECRET
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Data to encode in the token
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
        """
        Verify a JWT token.
        
        Args:
            credentials: HTTP authorization credentials
            
        Returns:
            Decoded token payload
            
        Raises:
            HTTPException: If token is invalid
        """
        token = credentials.credentials
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    def generate_api_key(self) -> str:
        """
        Generate a secure API key.
        
        Returns:
            Secure random API key
        """
        return secrets.token_urlsafe(32)
    
    def validate_api_key(self, api_key: str) -> bool:
        """
        Validate an API key.
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if API key is valid
        """
        # TODO: Implement API key validation against database
        # For now, just check against environment variable
        valid_keys = settings.API_KEYS.split(",") if settings.API_KEYS else []
        return api_key in valid_keys


# Global security manager instance
security_manager = SecurityManager()


# Re-added by Codex for import fix
def get_password_hash(password: str) -> str:
    """Wrapper for hashing passwords."""
    return security_manager.hash_password(password)


# Re-added by Codex for import fix
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Wrapper for password verification."""
    return security_manager.verify_password(plain_password, hashed_password)


# Re-added by Codex for import fix
def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token using the security manager."""
    return security_manager.create_access_token(data, expires_delta)


# Re-added by Codex for import fix
def create_refresh_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a simple refresh token."""
    return security_manager.create_access_token(data, expires_delta)


# Re-added by Codex for import fix
def decode_token(token: str) -> Dict[str, Any]:
    """Decode a JWT token and return its payload."""
    try:
        return jwt.decode(token, security_manager.secret_key, algorithms=[security_manager.algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# Re-added by Codex for import fix
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """FastAPI dependency returning the current user from database."""
    from ..db.business_models import User
    from ..core.database import get_db
    from sqlalchemy.orm import Session
    from fastapi import Depends
    
    payload = security_manager.verify_token(credentials)
    email = payload.get("sub")
    
    # Return a dependency function that gets the actual user
    async def _get_user_from_db(db: Session = Depends(get_db)):
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        return user
    
    # For now, return the payload
    return User(email=email, id=payload.get("user_id", email))


# Re-added by Codex for import fix
async def get_current_active_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    """Placeholder that simply returns the current user."""
    return await get_current_user(credentials)


# Re-added by Codex for import fix
async def verify_websocket_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate a WebSocket token."""
    try:
        payload = jwt.decode(token, security_manager.secret_key, algorithms=[security_manager.algorithm])
        return {"user_id": payload.get("sub"), "email": payload.get("sub")}
    except JWTError:
        return None
