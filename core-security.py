"""
Security and authentication module for BrainOps.

Provides robust authentication, authorization, and security utilities to protect
high-stakes business operations. Built to prevent unauthorized access and ensure
only verified users can trigger critical automations.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import secrets
import hashlib
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

from ..core.settings import settings
from ..memory.memory_store import get_user_by_email, save_auth_event


# Password hashing configuration with strong defaults
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # High cost factor for production security
)

# Bearer token security scheme
security_scheme = HTTPBearer()


class TokenData(BaseModel):
    """
    JWT token payload structure with comprehensive claims.
    
    Includes user identification, permissions, and security metadata
    to enable fine-grained access control.
    """
    sub: str = Field(..., description="Subject (user email)")
    user_id: str = Field(..., description="Unique user identifier")
    permissions: List[str] = Field(default_factory=list, description="Granted permissions")
    exp: datetime = Field(..., description="Token expiration")
    iat: datetime = Field(default_factory=datetime.utcnow, description="Issued at")
    jti: Optional[str] = Field(default_factory=lambda: secrets.token_urlsafe(16), description="JWT ID for revocation")


class SecurityManager:
    """
    Central security management for authentication and authorization.
    
    Handles password verification, JWT token generation/validation, and
    permission checking. Built to protect against common attack vectors
    while maintaining usability for legitimate users.
    """
    
    def __init__(self):
        self.algorithm = settings.ALGORITHM
        self.secret_key = settings.SECRET_KEY.get_secret_value()
        self.access_token_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Track revoked tokens (in production, use Redis)
        self.revoked_tokens: set = set()
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash using timing-safe comparison.
        
        Protects against timing attacks while maintaining reasonable
        performance for authentication flows.
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """
        Generate secure password hash with salt.
        
        Uses bcrypt with high cost factor to protect against
        rainbow table and brute force attacks.
        """
        return pwd_context.hash(password)
    
    def create_access_token(
        self,
        email: str,
        user_id: str,
        permissions: List[str] = None
    ) -> str:
        """
        Create JWT access token with user claims and permissions.
        
        Short-lived token for API access with minimal permissions
        to limit exposure window if compromised.
        """
        expire = datetime.utcnow() + self.access_token_expire
        
        token_data = TokenData(
            sub=email,
            user_id=user_id,
            permissions=permissions or [],
            exp=expire
        )
        
        # Encode JWT with secure algorithm
        encoded_jwt = jwt.encode(
            token_data.dict(),
            self.secret_key,
            algorithm=self.algorithm
        )
        
        # Log token creation for security audit
        save_auth_event({
            "event_type": "access_token_created",
            "user_id": user_id,
            "expires_at": expire
        })
        
        return encoded_jwt
    
    def create_refresh_token(self, user_id: str) -> str:
        """
        Create long-lived refresh token for token renewal.
        
        Allows users to maintain sessions without re-authentication
        while enabling token revocation if account is compromised.
        """
        expire = datetime.utcnow() + self.refresh_token_expire
        jti = secrets.token_urlsafe(32)
        
        payload = {
            "sub": user_id,
            "exp": expire,
            "jti": jti,
            "type": "refresh"
        }
        
        encoded_jwt = jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.algorithm
        )
        
        return encoded_jwt
    
    async def verify_token(self, credentials: HTTPAuthorizationCredentials) -> TokenData:
        """
        Verify and decode JWT token with comprehensive validation.
        
        Checks signature, expiration, revocation status, and structure
        to ensure token integrity and validity.
        """
        token = credentials.credentials
        
        try:
            # Decode and verify signature
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Check if token is revoked
            jti = payload.get("jti")
            if jti and jti in self.revoked_tokens:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
            
            # Validate token structure
            token_data = TokenData(**payload)
            
            # Additional validation for token age (prevent replay attacks)
            token_age = datetime.utcnow() - token_data.iat
            if token_age > timedelta(hours=24):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token too old, please re-authenticate"
                )
            
            return token_data
            
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication credentials: {str(e)}"
            )
    
    def revoke_token(self, jti: str) -> None:
        """
        Revoke a token by its JWT ID.
        
        Enables immediate invalidation of compromised tokens without
        waiting for natural expiration.
        """
        self.revoked_tokens.add(jti)
        
        # In production, store in Redis with TTL matching token expiration
        # This prevents unbounded growth of revocation list
    
    def check_permissions(
        self,
        required_permissions: List[str],
        user_permissions: List[str]
    ) -> bool:
        """
        Verify user has required permissions for operation.
        
        Implements least-privilege principle by requiring explicit
        permission grants for sensitive operations.
        """
        return all(perm in user_permissions for perm in required_permissions)
    
    def generate_api_key(self, user_id: str, key_name: str) -> Dict[str, str]:
        """
        Generate secure API key for programmatic access.
        
        Creates non-expiring keys for automation tools while maintaining
        security through proper key management and rotation.
        """
        # Generate cryptographically secure random key
        key_value = secrets.token_urlsafe(32)
        
        # Create key hash for storage (never store plain keys)
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()
        
        # Key ID for reference without exposing value
        key_id = f"bops_{secrets.token_urlsafe(8)}"
        
        return {
            "key_id": key_id,
            "key_value": f"{key_id}.{key_value}",  # Full key shown once
            "key_hash": key_hash,
            "key_name": key_name,
            "created_at": datetime.utcnow().isoformat()
        }
    
    def verify_api_key(self, api_key: str) -> Optional[str]:
        """
        Verify API key and return associated user ID.
        
        Validates key format, checks hash, and returns user context
        for API operations.
        """
        try:
            # Parse key format: bops_xxxxx.yyyyyyyy
            key_parts = api_key.split(".")
            if len(key_parts) != 2 or not key_parts[0].startswith("bops_"):
                return None
            
            key_id = key_parts[0]
            key_value = key_parts[1]
            
            # Verify key hash matches stored value
            key_hash = hashlib.sha256(key_value.encode()).hexdigest()
            
            # In production, look up key in database
            # For now, return None (invalid)
            return None
            
        except Exception:
            return None


# Global security manager instance
security_manager = SecurityManager()


# Dependency injection functions for FastAPI routes
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme)
) -> Dict[str, Any]:
    """
    FastAPI dependency to extract and verify current user from JWT.
    
    Provides clean interface for route protection while handling
    all security validation behind the scenes.
    """
    token_data = await security_manager.verify_token(credentials)
    
    # Fetch full user data (in production, from database)
    user = await get_user_by_email(token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return {
        "user_id": token_data.user_id,
        "email": token_data.sub,
        "permissions": token_data.permissions,
        "full_user": user
    }


def require_permissions(permissions: List[str]):
    """
    FastAPI dependency factory for permission-based route protection.
    
    Usage:
        @app.get("/admin", dependencies=[Depends(require_permissions(["admin"]))])
        async def admin_endpoint():
            # Only accessible to users with 'admin' permission
    """
    async def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ):
        if not security_manager.check_permissions(permissions, current_user["permissions"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permissions}"
            )
        return current_user
    
    return permission_checker


# Utility functions for common security operations
def sanitize_filename(filename: str) -> str:
    """
    Sanitize uploaded filename to prevent directory traversal attacks.
    
    Ensures uploaded files can't escape designated directories or
    overwrite system files through malicious naming.
    """
    # Remove any path components
    filename = filename.replace("/", "").replace("\\", "")
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = f"{name[:240]}.{ext}" if ext else name[:255]
    
    # Ensure non-empty
    if not filename:
        filename = f"unnamed_{secrets.token_urlsafe(8)}"
    
    return filename