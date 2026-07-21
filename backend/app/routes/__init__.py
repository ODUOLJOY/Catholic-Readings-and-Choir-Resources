from .auth import router as auth_router
from .readings import router as readings_router
from .choir import router as choir_router
from .saints import router as saints_router
from .calendar import router as calendar_router
from .favorites import router as favorites_router
from .downloads import router as downloads_router
from .notifications import router as notifications_router
from .reports import router as reports_router
from .search import router as search_router
from .profile import router as profile_router
from .admin import router as admin_router

__all__ = [
    "auth_router",
    "readings_router",
    "choir_router",
    "saints_router",
    "calendar_router",
    "favorites_router",
    "downloads_router",
    "notifications_router",
    "reports_router",
    "search_router",
    "profile_router",
    "admin_router",
]