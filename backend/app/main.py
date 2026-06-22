from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine

from app.routes import auth
from app.routes import readings
from app.routes import saints
from app.routes import choir
from app.routes import downloads
from app.routes import uploads
from app.routes import admin

app = FastAPI(
    title="Catholic Readings API"
)
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(readings.router)
app.include_router(saints.router)
app.include_router(choir.router)
app.include_router(downloads.router)
app.include_router(uploads.router)
app.include_router(admin.router)

@app.get("/")
def root():
    return {
        "message": "Catholic API Running"
    }
    
