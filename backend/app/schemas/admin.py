"""Response schemas for the v2 administrator endpoints.

These exist because the v2 admin routes previously returned raw ORM rows. With
no ``response_model`` declared, FastAPI serialised every column of the model --
including ``hashed_password``, ``password_reset_token`` and
``email_verification_token``. Declaring an explicit schema makes the exposed
surface reviewable and keeps credentials on the server.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import AdminUserListResponse


class PaginatedAdminUsersResponse(BaseModel):
    """User-management table payload.

    ``users`` is explicitly typed so the secret-bearing columns cannot reach the
    wire even if the query later returns a different model.
    """

    users: list[AdminUserListResponse] = Field(default_factory=list)
    total: int
    page: int
    per_page: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class AdminAuditLogResponse(BaseModel):
    """One administrative audit entry.

    ``actor_id`` is intentionally nullable because system actions are recorded
    without an actor.
    """

    id: int
    actor_id: Optional[int] = None
    actor_type: str = "user"
    action: str
    target_type: str
    target_id: Optional[int] = None
    role: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAuditLogResponse(BaseModel):
    logs: list[AdminAuditLogResponse] = Field(default_factory=list)
    total: int
    page: int
    per_page: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)