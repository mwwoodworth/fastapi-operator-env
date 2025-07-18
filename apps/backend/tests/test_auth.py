"""
Comprehensive tests for authentication endpoints.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import pyotp
from unittest.mock import patch, AsyncMock

from ..main import app
from ..core.database import get_db
from ..core.auth import get_password_hash, create_access_token
from ..db.business_models import User, UserRole, APIKey, UserSession


# Using fixtures from conftest.py instead of redefining


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_register_user(self, client: TestClient, test_db: Session):
        """Test user registration."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "username": "newuser"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "id" in data
        
        # TODO: Add database verification once memory_store is connected to real DB
        # For now, just verify the API response
    
    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        """Test registration with duplicate email."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "anotherpassword",
                "username": "anotheruser"
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["message"]
    
    def test_login_success(self, client: TestClient, test_user: User):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_password(self, client: TestClient, test_user: User):
        """Test login with invalid password."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["message"]
    
    def test_get_current_user(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test getting current user info."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
    
    def test_update_profile(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test updating user profile."""
        response = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={
                "full_name": "Updated Name",
                "bio": "Test bio"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["bio"] == "Test bio"
    
    def test_change_password(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test changing password."""
        response = client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "testpassword",
                "new_password": "newpassword123"
            }
        )
        
        assert response.status_code == 200
        
        # Try logging in with new password
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "newpassword123"
            }
        )
        
        assert login_response.status_code == 200
    
    def test_refresh_token(self, client: TestClient, test_user: User):
        """Test refreshing access token."""
        # First login to get refresh token
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword"
            }
        )
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Use refresh token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestExtendedAuthEndpoints:
    """Test extended authentication features."""
    
    @patch('apps.backend.core.email.EmailService.send_email', new_callable=AsyncMock)
    def test_forgot_password(self, mock_send_email, client: TestClient, test_user: User):
        """Test password reset request."""
        mock_send_email.return_value = True
        
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": test_user.email}
        )
        
        assert response.status_code == 200
        assert "reset link has been sent" in response.json()["message"]
    
    def test_reset_password_invalid_token(self, client: TestClient):
        """Test password reset with invalid token."""
        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "invalid-token",
                "new_password": "newpassword123"
            }
        )
        
        assert response.status_code == 400
        assert "Invalid or expired reset token" in response.json()["message"]
    
    def test_enable_2fa(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test enabling two-factor authentication."""
        response = client.post(
            "/api/v1/auth/two-factor/enable",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert "qr_code" in data
        assert "backup_codes" in data
        assert len(data["backup_codes"]) == 10
    
    def test_confirm_2fa(self, client: TestClient, test_user: User, auth_headers: dict, test_db: Session):
        """Test confirming 2FA setup."""
        # First enable 2FA
        enable_response = client.post(
            "/api/v1/auth/two-factor/enable",
            headers=auth_headers
        )
        
        secret = enable_response.json()["secret"]
        
        # Generate valid TOTP code
        totp = pyotp.TOTP(secret)
        code = totp.now()
        
        # Confirm with code
        response = client.post(
            "/api/v1/auth/two-factor/confirm",
            headers=auth_headers,
            json={"code": code}
        )
        
        assert response.status_code == 200
        
        # Verify 2FA is enabled in database
        test_db.refresh(test_user)
        assert test_user.two_factor_enabled is True
    
    def test_create_api_key(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test creating an API key."""
        response = client.post(
            "/api/v1/auth/api-keys",
            headers=auth_headers,
            json={
                "name": "Test API Key",
                "scopes": ["read", "write"],
                "expires_in_days": 30
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "key" in data
        assert data["key"].startswith("brainops_")
        assert data["name"] == "Test API Key"
        assert data["scopes"] == ["read", "write"]
    
    def test_list_api_keys(self, client: TestClient, test_user: User, auth_headers: dict, test_db: Session):
        """Test listing API keys."""
        # Create an API key first
        api_key = APIKey(
            user_id=test_user.id,
            name="Existing Key",
            key_hash="hashed_key",
            prefix="brainops_test",
            scopes=["read"]
        )
        test_db.add(api_key)
        test_db.commit()
        
        response = client.get("/api/v1/auth/api-keys", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Existing Key"
        assert data[0]["key"] == ""  # Key should not be returned
    
    def test_revoke_api_key(self, client: TestClient, test_user: User, auth_headers: dict, test_db: Session):
        """Test revoking an API key."""
        # Create an API key
        api_key = APIKey(
            user_id=test_user.id,
            name="Key to Revoke",
            key_hash="hashed_key",
            prefix="brainops_test",
            is_active=True
        )
        test_db.add(api_key)
        test_db.commit()
        test_db.refresh(api_key)
        
        response = client.delete(
            f"/api/v1/auth/api-keys/{api_key.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify key is deactivated
        test_db.refresh(api_key)
        assert api_key.is_active is False
    
    def test_list_sessions(self, client: TestClient, test_user: User, auth_headers: dict, test_db: Session):
        """Test listing active sessions."""
        # Create a session
        session = UserSession(
            user_id=test_user.id,
            refresh_token_hash="hashed_token",
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        test_db.add(session)
        test_db.commit()
        
        response = client.get("/api/v1/auth/sessions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["ip_address"] == "127.0.0.1"
    
    def test_revoke_session(self, client: TestClient, test_user: User, auth_headers: dict, test_db: Session):
        """Test revoking a session."""
        # Create a session
        session = UserSession(
            user_id=test_user.id,
            refresh_token_hash="hashed_token",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        test_db.add(session)
        test_db.commit()
        test_db.refresh(session)
        
        response = client.delete(
            f"/api/v1/auth/sessions/{session.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify session is deactivated
        test_db.refresh(session)
        assert session.is_active is False


class TestAuthSecurity:
    """Test authentication security features."""
    
    def test_invalid_token(self, client: TestClient):
        """Test accessing protected endpoint with invalid token."""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["message"]
    
    def test_expired_token(self, client: TestClient, test_user: User):
        """Test accessing protected endpoint with expired token."""
        # Create expired token
        token = create_access_token(
            data={"sub": test_user.email},
            expires_delta=timedelta(seconds=-1)
        )
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert "expired" in response.json()["message"].lower()
    
    def test_account_lockout(self, client: TestClient, test_user: User, test_db: Session):
        """Test account lockout after failed attempts."""
        # Make 5 failed login attempts
        for _ in range(5):
            client.post(
                "/api/v1/auth/login",
                data={
                    "username": test_user.email,
                    "password": "wrongpassword"
                }
            )
        
        # Verify account is locked
        test_db.refresh(test_user)
        assert test_user.failed_login_attempts >= 5
        assert test_user.locked_until is not None
        
        # Try to login with correct password
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword"
            }
        )
        
        assert response.status_code == 401
    
    def test_inactive_user_access(self, client: TestClient, test_user: User, test_db: Session):
        """Test that inactive users cannot access protected endpoints."""
        # Deactivate user
        test_user.is_active = False
        test_db.commit()
        
        # Try to login
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword"
            }
        )
        
        assert response.status_code == 403
    
    def test_unverified_email_restrictions(self, client: TestClient, test_user: User, test_db: Session, auth_headers: dict):
        """Test restrictions for unverified email."""
        # Mark user as unverified
        test_user.is_verified = False
        test_db.commit()
        
        # Should still be able to access basic profile
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        
        # But certain features might be restricted
        # (This would depend on specific endpoint requirements)