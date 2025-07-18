"""
Authentication utility functions for user management.
"""

from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ..db.business_models import User
import uuid

async def get_user_by_email(email: str, db: Session) -> Optional[User]:
    """Get user by email from database."""
    return db.query(User).filter(User.email == email).first()


async def create_user(
    email: str,
    username: Optional[str],
    hashed_password: str,
    full_name: Optional[str],
    company: Optional[str],
    role: str,
    db: Session
) -> User:
    """Create a new user in the database."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
        role=role,
        is_active=True,
        is_verified=False,
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def update_user_last_login(user_id: str, db: Session):
    """Update user's last login timestamp."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.last_login = datetime.utcnow()
        db.commit()


async def invalidate_refresh_token(refresh_token: str, user_id: str, db: Session):
    """Invalidate a refresh token (stub for now)."""
    # TODO: Implement token blacklist table
    pass


async def validate_refresh_token(refresh_token: str, user_id: str, db: Session) -> bool:
    """Validate if a refresh token is still valid."""
    # TODO: Check against token blacklist
    return True


async def update_user_profile(user_id: str, update_data: dict, db: Session) -> User:
    """Update user profile data."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
    return user


async def update_user_password(user_id: str, new_hashed_password: str, db: Session):
    """Update user's password."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.hashed_password = new_hashed_password
        user.updated_at = datetime.utcnow()
        db.commit()


async def invalidate_all_user_tokens(user_id: str, db: Session):
    """Invalidate all tokens for a user (stub for now)."""
    # TODO: Implement token blacklist
    pass


async def verify_email_token(token: str, db: Session) -> Optional[User]:
    """Verify email verification token (stub for now)."""
    # TODO: Implement email verification logic
    return None