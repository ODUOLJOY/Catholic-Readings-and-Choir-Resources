from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ==========================================
    # Application
    # ==========================================
    APP_NAME: str = "Catholic Readings & Choir Resources API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ==========================================
    # API
    # ==========================================
    API_V1_PREFIX: str = "/api"

    # ==========================================
    # Database
    # ==========================================
    DATABASE_URL: str

    # ==========================================
    # JWT Authentication
    # ==========================================
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ==========================================
    # Email
    # ==========================================
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""

    # ==========================================
    # Frontend
    # ==========================================
    FRONTEND_URL: str = "http://localhost:8081"

    # ==========================================
    # Uploads
    # ==========================================
    MAX_IMAGE_SIZE: int = 5 * 1024 * 1024          # 5MB
    MAX_AUDIO_SIZE: int = 50 * 1024 * 1024         # 50MB
    MAX_VIDEO_SIZE: int = 300 * 1024 * 1024        # 300MB
    MAX_DOCUMENT_SIZE: int = 20 * 1024 * 1024      # 20MB

    ALLOWED_IMAGE_TYPES: str = "jpg,jpeg,png,webp"
    ALLOWED_DOCUMENT_TYPES: str = "pdf"
    ALLOWED_AUDIO_TYPES: str = "mp3,wav,m4a,aac"
    ALLOWED_VIDEO_TYPES: str = "mp4,mov,mkv"

    # ==========================================
    # Firebase Notifications
    # ==========================================
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""

    # ==========================================
    # Storage
    # ==========================================
    STORAGE_PATH: str = "storage"

    # ==========================================
    # Render / Production
    # ==========================================
    BASE_URL: str = "https://catholic-readings-and-choir-resource-app.onrender.com"

    # ==========================================
    # CORS
    # ==========================================
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:8081",
        "http://localhost:19006",
        "http://localhost:3000",
        "https://catholic-readings-and-choir-resource-app.onrender.com",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()