from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import (
    admin,
    auth,
    choir,
    content,
    downloads,
    readings,
    saints,
    uploads,
)

app = FastAPI(
    title="Catholic Readings & Choir Resource API",
    description="Backend API for the Catholic Readings & Choir Resource App",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Create database tables
init_db()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://localhost:19006",
        "http://127.0.0.1:8081",
        "http://127.0.0.1:19006",
        "https://catholic-readings-and-choir-resource-app.vercel.app",
        "https://catholic-readings-and-choir-resource-app.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(readings.router, prefix="/api/readings", tags=["Readings"])
app.include_router(saints.router, prefix="/api/saints", tags=["Saints"])
app.include_router(choir.router, prefix="/api/choir", tags=["Choir"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(downloads.router, prefix="/api/downloads", tags=["Downloads"])
app.include_router(content.router, prefix="/api/content", tags=["Content"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


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
async def health():
    return {
        "status": "healthy",
        "database": "connected",
        "api": "running",
    }