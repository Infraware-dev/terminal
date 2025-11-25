"""Pydantic models for API request/response validation."""

from pydantic import BaseModel, ConfigDict, Field


class AuthRequest(BaseModel):
    """Request model for /auth endpoint."""

    model_config = ConfigDict(strict=True)

    api_key: str = Field(..., description="Anthropic API key", min_length=1)


class AuthResponse(BaseModel):
    """Response model for /auth endpoint."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether authentication was successful")
    message: str = Field(..., description="Status message")


class AuthStatusResponse(BaseModel):
    """Response model for /get-auth endpoint."""

    model_config = ConfigDict(strict=True)

    authenticated: bool = Field(..., description="Whether user is authenticated")
    has_api_key: bool = Field(..., description="Whether API key is configured")
