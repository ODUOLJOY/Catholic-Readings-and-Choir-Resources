"""Explicit permission system for role-based access control."""
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Permission(Base):
    """Explicit permission definitions."""
    __tablename__ = "permissions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # users, content, hierarchy, system
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RolePermission(Base):
    """Mapping of roles to permissions."""
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role", "permission_id", name="uq_role_permission"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id"), nullable=False)
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    permission = relationship("Permission")


# Permission definitions
PERMISSIONS = {
    # User management
    "users.read": "View user information",
    "users.create": "Create new users",
    "users.update": "Update user information",
    "users.suspend": "Suspend user accounts",
    "users.reactivate": "Reactivate suspended accounts",
    "users.lock": "Lock user accounts",
    "users.unlock": "Unlock user accounts",
    "users.delete": "Delete user accounts",
    "users.reset_password": "Reset user passwords",
    
    # Role management
    "roles.read": "View role assignments",
    "roles.assign": "Assign roles to users",
    "roles.revoke": "Revoke roles from users",
    "roles.create": "Create new role definitions",
    "roles.update": "Update role definitions",
    
    # Hierarchy management
    "parishes.read": "View parish information",
    "parishes.create": "Create new parishes",
    "parishes.update": "Update parish information",
    "parishes.deactivate": "Deactivate parishes",
    "parishes.manage_users": "Manage parish users",
    
    "dioceses.read": "View diocese information",
    "dioceses.create": "Create new dioceses",
    "dioceses.update": "Update diocese information",
    "dioceses.deactivate": "Deactivate dioceses",
    "dioceses.manage_parishes": "Manage parishes within diocese",
    "dioceses.manage_admins": "Manage diocesan administrators",
    
    "deaneries.read": "View deanery information",
    "deaneries.create": "Create new deaneries",
    "deaneries.update": "Update deanery information",
    
    # Content management
    "readings.read": "View reading references",
    "readings.create": "Create reading references",
    "readings.update": "Update reading references",
    "readings.approve": "Approve reading references",
    "readings.reject": "Reject reading references",
    "readings.verify": "Verify reading references",
    
    "saints.read": "View saint information",
    "saints.create": "Create saint records",
    "saints.update": "Update saint records",
    "saints.delete": "Delete saint records",
    "saints.approve": "Approve saint records",
    
    "calendar.read": "View liturgical calendar",
    "calendar.create": "Create calendar entries",
    "calendar.update": "Update calendar entries",
    "calendar.import": "Import calendar data",
    "calendar.verify": "Verify calendar data",
    
    "choir_resources.read": "View choir resources",
    "choir_resources.create": "Upload choir resources",
    "choir_resources.update": "Update choir resources",
    "choir_resources.delete": "Delete choir resources",
    "choir_resources.approve": "Approve choir resources",
    "choir_resources.reject": "Reject choir resources",
    "choir_resources.moderate": "Moderate choir resources",
    
    "uploads.create": "Upload files",
    "uploads.read": "View uploads",
    "uploads.delete": "Delete uploads",
    "uploads.moderate": "Moderate uploads",
    
    # Moderation
    "moderation.queue.read": "View moderation queue",
    "moderation.review": "Review moderation items",
    "moderation.approve": "Approve content",
    "moderation.reject": "Reject content",
    "moderation.request_changes": "Request changes to content",
    "moderation.suspend": "Suspend content",
    
    # Reports
    "reports.create": "Create reports",
    "reports.read": "View reports",
    "reports.review": "Review reports",
    "reports.resolve": "Resolve reports",
    
    # Audit
    "audit_logs.read": "View audit logs",
    "audit_logs.export": "Export audit logs",
    
    # System
    "settings.read": "View system settings",
    "settings.update": "Update system settings",
    "notifications.create": "Create notifications",
    "notifications.manage": "Manage notifications",
}


# Default role permissions
DEFAULT_ROLE_PERMISSIONS = {
    "user": [
        "users.read",  # Only own profile
        "parishes.read",
        "dioceses.read",
        "deaneries.read",
        "readings.read",
        "saints.read",
        "calendar.read",
        "choir_resources.read",
        "reports.create",
    ],
    "choir_contributor": [
        "users.read",  # Only own profile
        "parishes.read",
        "dioceses.read",
        "deaneries.read",
        "readings.read",
        "saints.read",
        "calendar.read",
        "choir_resources.create",
        "choir_resources.read",
        "choir_resources.update",  # Only own pending submissions
        "reports.create",
    ],
    "parish_administrator": [
        "users.read",
        "users.update",  # Within parish
        "users.suspend",  # Within parish
        "users.reactivate",  # Within parish
        "parishes.read",
        "parishes.update",  # Only own parish
        "parishes.manage_users",
        "dioceses.read",
        "deaneries.read",
        "readings.read",
        "saints.read",
        "calendar.read",
        "choir_resources.read",
        "choir_resources.moderate",  # Within parish
        "choir_resources.approve",  # Within parish
        "choir_resources.reject",  # Within parish
        "moderation.queue.read",  # Within parish
        "moderation.review",  # Within parish
        "reports.read",  # Within parish
        "reports.review",  # Within parish
        "reports.resolve",  # Within parish
        "audit_logs.read",  # Within parish
    ],
    "diocesan_administrator": [
        "users.read",
        "users.update",  # Within diocese
        "users.suspend",  # Within diocese
        "users.reactivate",  # Within diocese
        "parishes.read",
        "parishes.update",  # Within diocese
        "parishes.manage_users",
        "parishes.deactivate",  # Within diocese
        "dioceses.read",
        "dioceses.update",  # Only own diocese
        "dioceses.manage_parishes",
        "dioceses.manage_admins",
        "deaneries.read",
        "deaneries.update",  # Within diocese
        "readings.read",
        "saints.read",
        "calendar.read",
        "choir_resources.read",
        "choir_resources.moderate",  # Within diocese
        "choir_resources.approve",  # Within diocese
        "choir_resources.reject",  # Within diocese
        "moderation.queue.read",  # Within diocese
        "moderation.review",  # Within diocese
        "reports.read",  # Within diocese
        "reports.review",  # Within diocese
        "reports.resolve",  # Within diocese
        "audit_logs.read",  # Within diocese
    ],
    "moderator": [
        "users.read",
        "parishes.read",
        "dioceses.read",
        "deaneries.read",
        "readings.read",
        "saints.read",
        "calendar.read",
        "choir_resources.read",
        "choir_resources.moderate",
        "choir_resources.approve",
        "choir_resources.reject",
        "uploads.moderate",
        "moderation.queue.read",
        "moderation.review",
        "moderation.approve",
        "moderation.reject",
        "moderation.request_changes",
        "moderation.suspend",
        "reports.read",
        "reports.review",
        "reports.resolve",
        "audit_logs.read",  # Only moderation-related
    ],
    "admin": [
        "users.read",
        "users.create",
        "users.update",
        "users.suspend",
        "users.reactivate",
        "users.lock",
        "users.unlock",
        "users.delete",
        "users.reset_password",
        "roles.read",
        "parishes.read",
        "parishes.create",
        "parishes.update",
        "parishes.deactivate",
        "parishes.manage_users",
        "dioceses.read",
        "dioceses.create",
        "dioceses.update",
        "dioceses.deactivate",
        "dioceses.manage_parishes",
        "deaneries.read",
        "deaneries.create",
        "deaneries.update",
        "readings.read",
        "readings.create",
        "readings.update",
        "readings.approve",
        "readings.reject",
        "readings.verify",
        "saints.read",
        "saints.create",
        "saints.update",
        "saints.delete",
        "saints.approve",
        "calendar.read",
        "calendar.create",
        "calendar.update",
        "calendar.import",
        "calendar.verify",
        "choir_resources.read",
        "choir_resources.create",
        "choir_resources.update",
        "choir_resources.delete",
        "choir_resources.approve",
        "choir_resources.reject",
        "choir_resources.moderate",
        "uploads.create",
        "uploads.read",
        "uploads.delete",
        "uploads.moderate",
        "moderation.queue.read",
        "moderation.review",
        "moderation.approve",
        "moderation.reject",
        "moderation.request_changes",
        "moderation.suspend",
        "reports.create",
        "reports.read",
        "reports.review",
        "reports.resolve",
        "audit_logs.read",
        "audit_logs.export",
        "settings.read",
        "settings.update",
        "notifications.create",
        "notifications.manage",
    ],
    "super_admin": [
        # All permissions
    ],
}
