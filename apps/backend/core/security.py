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
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
    
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