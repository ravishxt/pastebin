from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models import PasteStatus


class PasteCreateRequest(BaseModel):
    content: str = Field(..., description="Paste content")
    max_views: int = Field(..., ge=1, description="Maximum allowed views (>= 1)")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional expiration datetime (timezone-aware)",
    )
    password_hash: Optional[str] = Field(
        default=None,
        description="Optional pre-hashed password protecting the paste",
    )


class PasteResponse(BaseModel):
    id: UUID
    content: str
    max_views: int
    current_views: int
    expires_at: Optional[datetime]
    status: PasteStatus
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"

