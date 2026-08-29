"""
Authentication Schemas
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login credentials."""

    email: str = Field(min_length=5, max_length=255, description="User email")
    password: str = Field(min_length=6, max_length=128, description="User password")


class RegisterRequest(BaseModel):
    """New user registration."""

    email: str = Field(min_length=5, max_length=255, description="User email")
    password: str = Field(min_length=8, max_length=128, description="Password (min 8 chars)")
    full_name: str = Field(min_length=1, max_length=150, description="Full display name")
    role: str = Field(default="viewer", description="Role: admin, operator, viewer")


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: str | None = None
    created_at: str

    model_config = {"from_attributes": True}
