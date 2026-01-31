"""Pydantic models for request/response schemas."""

from pydantic import BaseModel


class ProcessingResult(BaseModel):
    """Response model for processing results."""

    success: bool
    message: str
    products_count: int | None = None


class HealthCheck(BaseModel):
    """Health check response model."""

    status: str
    version: str
