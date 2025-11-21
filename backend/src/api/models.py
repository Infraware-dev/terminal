"""Pydantic models for API request/response validation."""

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    """Request model for /auth endpoint."""

    api_key: str = Field(..., description="Anthropic API key", min_length=1)


class AuthResponse(BaseModel):
    """Response model for /auth endpoint."""

    success: bool = Field(..., description="Whether authentication was successful")
    message: str = Field(..., description="Status message")


class AuthStatusResponse(BaseModel):
    """Response model for /get-auth endpoint."""

    authenticated: bool = Field(..., description="Whether user is authenticated")
    has_api_key: bool = Field(..., description="Whether API key is configured")
