from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.core.config import settings
from app.services.public_files import PublicFiles
from app.routes import (
    admin,
    admin_v2,
    auth,
    choir,
    content,
    downloads,
    readings,
    payments,
    saints,
    uploads,
    liturgy,
    locations,
    hierarchy,
    user,
    favorites,
    parish_requests,
    community,
    report,
)

app = FastAPI(
    title="Catholic Readings & Choir Resource API",
    description="Backend API for the Catholic Readings & Choir Resource App",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

Path("media").mkdir(parents=True, exist_ok=True)
Path("uploads").mkdir(parents=True, exist_ok=True)
app.mount(
    "/media",
    PublicFiles(directory="media", url_prefix="/media"),
    name="media",
)
app.mount(
    "/uploads",
    PublicFiles(directory="uploads", url_prefix="/uploads"),
    name="uploads",
)

# Legacy table creation is restricted to explicit development opt-in. Production
# schema changes are deployed with reviewed Alembic migrations.
if settings.AUTO_CREATE_TABLES:
    init_db()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Stable application error codes for authentication-flow errors (§10).
#
# Every error the backend returns during registration, login, token refresh,
# password reset, email verification and Google sign-in carries a stable
# application error code alongside the human-readable ``detail``. A global
# HTTPException handler attaches the code; for any exception whose
# (status_code, detail) is not mapped here the response is byte-for-byte
# identical to FastAPI's default ``{"detail": ...}`` shape, so behaviour
# outside the authentication flow is unchanged.
# ---------------------------------------------------------------------------

_AUTH_ERROR_CODES = {
    # --- Registration / account identity (ONE EMAIL = ONE ACCOUNT) ---
    (400, "Email already registered."): "AUTH_EMAIL_ALREADY_EXISTS",
    (400, "Email already exists."): "AUTH_EMAIL_ALREADY_EXISTS",
    # Concurrent same-email registration slips past the pre-check and is
    # rejected by the users.email UNIQUE constraint (see create_user).
    (409, "Email already registered."): "AUTH_EMAIL_ALREADY_EXISTS",
    (400, "Google did not provide a verified email address."): "AUTH_GOOGLE_NO_VERIFIED_EMAIL",
    (400, "Incorrect current password."): "AUTH_CURRENT_PASSWORD_INCORRECT",
    (400, "Invalid reset token."): "AUTH_INVALID_RESET_TOKEN",
    (400, "Invalid or already used reset token."): "AUTH_INVALID_RESET_TOKEN",
    (400, "Invalid verification token."): "AUTH_INVALID_VERIFICATION_TOKEN",
    (400, "Invalid or already used verification token."): "AUTH_INVALID_VERIFICATION_TOKEN",
    (400, "Provide at least one profile field to update."): "AUTH_PROFILE_UPDATE_INVALID",
    (400, "Full name cannot be empty."): "AUTH_PROFILE_UPDATE_INVALID",
    (400, "Invalid role."): "AUTH_INVALID_ROLE",
    (400, "The requested redirect URI is not allowed."): "AUTH_INVALID_REDIRECT_URI",
    (400, "Unable to verify the Google account."): "AUTH_GOOGLE_VERIFICATION_FAILED",
    (400, "Invalid Google identity token."): "AUTH_INVALID_GOOGLE_TOKEN",
    (400, "Invalid or expired Google sign-in state."): "AUTH_INVALID_GOOGLE_STATE",
    # --- Login ---
    (401, "Invalid email or password."): "AUTH_INVALID_CREDENTIALS",
    (401, "Authentication required."): "AUTH_UNAUTHENTICATED",
    # FastAPI's OAuth2PasswordBearer raises this literal when no token is sent.
    (401, "Not authenticated"): "AUTH_UNAUTHENTICATED",
    # --- Token verification / current user ---
    (401, "Invalid or expired token."): "AUTH_UNAUTHENTICATED",
    (401, "Invalid authentication token."): "AUTH_UNAUTHENTICATED",
    (401, "User not found."): "AUTH_UNAUTHENTICATED",
    (401, "Linked account no longer exists."): "AUTH_UNAUTHENTICATED",
    # --- Refresh / session expiration ---
    (401, "Invalid or expired refresh token."): "AUTH_INVALID_REFRESH_TOKEN",
    (401, "Invalid refresh token."): "AUTH_INVALID_REFRESH_TOKEN",
    (401, "Refresh session is no longer valid."): "AUTH_INVALID_REFRESH_TOKEN",
    (401, "Refresh session has expired."): "AUTH_INVALID_REFRESH_TOKEN",
    # --- Disabled accounts ---
    (403, "Account disabled."): "AUTH_ACCOUNT_DISABLED",
    (403, "Account is disabled."): "AUTH_ACCOUNT_DISABLED",
    (403, "Your account has been disabled."): "AUTH_ACCOUNT_DISABLED",
    # --- Authorization: server-side admin/moderator enforcement (#16) ---
    (403, "Moderator privileges required."): "AUTH_INSUFFICIENT_ROLE",
    (403, "Moderator access required."): "AUTH_INSUFFICIENT_ROLE",
    (403, "Administrator privileges required."): "AUTH_INSUFFICIENT_ROLE",
    (403, "Administrator access required."): "AUTH_INSUFFICIENT_ROLE",
    (403, "Super Admin privileges required."): "AUTH_INSUFFICIENT_ROLE",
    (403, "You do not have permission to manage this user."): "AUTH_INSUFFICIENT_ROLE",
    (403, "You do not have permission to assign this role to this user."): "AUTH_INSUFFICIENT_ROLE",
    (403, "Cannot suspend yourself if you are the last super admin."): "AUTH_LAST_SUPER_ADMIN",
    # --- Google identity conflicts (single canonical identity) ---
    (409, "An account with this email already exists. Sign in with your password to link Google sign-in."): "AUTH_EMAIL_ALREADY_EXISTS",
    (409, "This Google account is already linked."): "AUTH_GOOGLE_ACCOUNT_LINKED",
    # --- Google / email delivery configuration ---
    (503, "Google sign-in is not configured."): "AUTH_GOOGLE_NOT_CONFIGURED",
    (503, "Password reset email delivery is not configured."): "AUTH_EMAIL_NOT_CONFIGURED",
    (503, "Email delivery is not configured."): "AUTH_EMAIL_NOT_CONFIGURED",
    (503, "Database unavailable"): "AUTH_DATABASE_UNAVAILABLE",
}


@app.exception_handler(HTTPException)
async def _auth_error_code_handler(request, exc: HTTPException):
    body: dict = {"detail": exc.detail}
    # Only string details are hashable enough for the lookup key; list-style
    # details (e.g. 422 validation bodies) fall through to the default shape.
    if isinstance(exc.detail, str):
        code = _AUTH_ERROR_CODES.get((exc.status_code, exc.detail))
        if code:
            body["code"] = code

    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers=exc.headers,
    )


# API Routes
app.include_router(auth.router)
app.include_router(readings.router)
app.include_router(liturgy.router)
app.include_router(locations.router)
app.include_router(hierarchy.router)
app.include_router(user.router)
app.include_router(favorites.router, prefix="/api")
app.include_router(parish_requests.router)
app.include_router(community.router)
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(saints.router)
app.include_router(choir.router)
app.include_router(uploads.router)
app.include_router(downloads.router)
app.include_router(content.router)
app.include_router(admin.router)
app.include_router(admin_v2.router)
# Registered so the in-app "Report Content" button resolves. This router was
# previously written but never mounted, which made reporting silently fail.
app.include_router(report.router)


@app.get("/", tags=["System"])
async def root():
    return {
        "application": "Catholic Readings & Choir Resource API",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return {
        "status": "healthy",
        "database": "connected",
        "api": "running",
    }