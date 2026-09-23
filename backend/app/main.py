from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import init_db
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
app.mount("/media", StaticFiles(directory="media"), name="media")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

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
app.include_router(auth.router)
app.include_router(readings.router)
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
async def health():
    return {
        "status": "healthy",
        "database": "connected",
        "api": "running",
    }