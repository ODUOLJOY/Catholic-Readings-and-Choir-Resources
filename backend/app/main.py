from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.core.config import settings
from app.services.public_files import PublicFiles
from app.routes import (
    admin,
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
    user,
    favorites,
    parish_requests,
    community,
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

# API Routes
app.include_router(auth.router)
app.include_router(readings.router)
app.include_router(liturgy.router)
app.include_router(locations.router)
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