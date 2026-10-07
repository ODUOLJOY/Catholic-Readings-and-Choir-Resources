import re
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# `NoDecode` stops pydantic-settings from JSON-decoding these fields before the
# validator below sees them. Without it a comma-separated value raises a
# SettingsError at import time, so only a JSON array would have worked.
OriginList = Annotated[list[str], NoDecode]

# The Expo dev server takes the next free port whenever the previous one is
# still held, so the loopback origin is not a fixed value: it moves between
# 8081, 8082, 8083 and so on depending on what is already running. Pinning a
# single port in the allow-list below made the API reject a legitimate request
# from the developer's own machine, and the browser reported that rejection as
# a CORS fault with no `Access-Control-Allow-Origin` header.
#
# Accepting loopback on any port closes that moving target without widening the
# trust boundary: a page served from the public internet cannot claim a loopback
# origin, so no remote host can use this to read credentialed responses. The
# pattern matches a loopback host only, and never a wildcard.
LOOPBACK_ORIGIN_RE = re.compile(
    r"^https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?$",
    re.IGNORECASE,
)


def is_allowed_origin(origin: str | None, allowed_origins: list[str]) -> bool:
    """Report whether ``origin`` may be sent credentialed CORS headers.

    An origin qualifies either by appearing in the configured allow-list or by
    being a loopback address on any port. A wildcard never qualifies: echoing
    ``*`` alongside credentials is invalid, and treating it as a match would
    downgrade the credential restriction it exists to enforce.
    """
    if not origin:
        return False
    candidate = origin.strip().rstrip("/")
    if candidate == "*":
        return False
    return candidate in allowed_origins or LOOPBACK_ORIGIN_RE.match(candidate) is not None


class Settings(BaseSettings):
    # ==========================================
    # Application
    # ==========================================
    APP_NAME: str = "Catholic Readings & Choir Resources API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    AUTO_CREATE_TABLES: bool = False
    BOOTSTRAP_SUPER_ADMIN_EMAIL: str = ""
    BOOTSTRAP_SUPER_ADMIN_PASSWORD: str = ""
    SCHEDULED_JOB_TOKEN: str = ""

    # When True, the liturgical sync additionally fetches public-domain
    # Douay-Rheims reading *text* (English, per date) from bible-api.com and
    # stores it in the `readings` table so `GET /api/readings/{date}?language=English`
    # returns 200. Default off = references-only behaviour is unchanged. Kiswahili
    # text is never synthesised (no PD Swahili biblical-text source).
    FETCH_READING_TEXT: bool = False

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

    # M-Pesa payments
    MPESA_ENVIRONMENT: str = "sandbox"
    MPESA_CONSUMER_KEY: str = ""
    MPESA_CONSUMER_SECRET: str = ""
    MPESA_PASSKEY: str = ""
    MPESA_SHORTCODE: str = ""
    MPESA_CALLBACK_URL: str = ""
    MPESA_ACCOUNT_REFERENCE: str = "CatholicReadings"
    MPESA_TRANSACTION_DESCRIPTION: str = "Catholic Readings Subscription"
    MPESA_TRANSACTION_TYPE: str = "CustomerPayBillOnline"
    MPESA_MONTHLY_AMOUNT: int = 10
    # Entitlement names granted while a subscription is active. Kept in
    # configuration so the plan can change without a code change, and left empty
    # by default so no content is gated by a feature nobody configured.
    SUBSCRIPTION_FEATURES: list[str] = []
    MPESA_RECIPIENT_NUMBER: str = ""

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ==========================================
    # Google Sign-In (OpenID Connect / OAuth 2.0)
    # ==========================================
    # All values must be supplied through environment variables. When
    # GOOGLE_CLIENT_ID is empty the sign-in endpoints fail closed.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    # Optional comma-separated extra redirect URIs accepted for the
    # authorization-code flow.
    GOOGLE_ALLOWED_REDIRECT_URIS: str = ""
    GOOGLE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"

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
    STORAGE_BACKEND: Literal["local", "firebase"] = "local"
    FIREBASE_STORAGE_BUCKET: str = ""

    # ==========================================
    # Render / Production
    # ==========================================
    BASE_URL: str = "https://catholic-readings-and-choir-resource-app.onrender.com"

    # Hosts this service will answer to.
    #
    # `TrustedHostMiddleware` rejects requests whose `Host` header is not on this
    # list. Without it, `request.base_url` reflects whatever the caller sent, and
    # `app/routes/uploads.py` persists that value into `ChoirResource.file_url`.
    # An attacker could therefore upload a resource with a `Host` header of their
    # own domain and have an attacker-controlled URL stored permanently in the
    # database -- a stored, persistent redirect of every member who opens the
    # resource.
    #
    # Empty means "derive from BASE_URL". Hosts are names only, without scheme,
    # port or path. Adding a host requires no application restart of any other
    # component, and does not require changing deployment settings to add the
    # common cases already listed here.
    ALLOWED_HOSTS: OriginList = []

    # ==========================================
    # CORS
    # ==========================================
    # `CORS_ORIGINS` is the name several deployment environments already set.
    # It used to be ignored entirely, so an operator could configure it and still
    # get the default list below -- which is how the local Expo web origin ended
    # up being rejected by the deployed API. Both names are merged by
    # `_merge_cors_origins`. It must be declared *before* ALLOWED_ORIGINS so its
    # value is available to that validator.
    CORS_ORIGINS: OriginList = []
    # The deployed frontend origins are listed here so a production deployment
    # that does not override ALLOWED_ORIGINS still accepts its own frontend.
    ALLOWED_ORIGINS: OriginList = [
        "http://localhost:8081",
        "http://localhost:19006",
        "http://127.0.0.1:8081",
        "http://127.0.0.1:19006",
        "http://localhost:3000",
        "https://catholic-readings-and-choir-resource-app.onrender.com",
        "https://catholic-readings-and-choir-resource-app.vercel.app",
        "https://catholic-readings-and-choir-resourc.vercel.app",
        "https://stellular-clafoutis-ad641c.netlify.app",
    ]

    @field_validator("CORS_ORIGINS", "ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        """Accept a JSON array, or a comma/whitespace separated string.

        Render and most hosts can only supply strings, so ``["a","b"]`` and
        ``a,b`` must both work; without this the value silently became a
        single-element list containing the whole string.
        """
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                import json

                try:
                    return json.loads(text)
                except ValueError:
                    pass
            return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
        return value

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def _merge_cors_origins(cls, value: list[str], info) -> list[str]:
        """Merge ``CORS_ORIGINS`` into ``ALLOWED_ORIGINS``, preserving order."""
        extra = info.data.get("CORS_ORIGINS") or []
        merged: list[str] = []
        for origin in [*value, *extra]:
            cleaned = origin.strip().rstrip("/")
            if cleaned and cleaned not in merged:
                merged.append(cleaned)
        return merged

    @field_validator("ALLOWED_HOSTS")
    @classmethod
    def _derive_allowed_hosts(cls, value: list[str], info) -> list[str]:
        """Normalise hosts and always include the one serving this API.

        ``ALLOWED_HOSTS`` is intentionally allowed to stay empty so a deployment
        does not have to configure it to be safe, but an empty list must never mean
        "accept any host". The configured ``BASE_URL`` host is the minimum, and it
        is added even when the operator supplied a list without it -- otherwise
        the service would reject its own public hostname.

        The loopback names are added unconditionally rather than only when the
        list comes out empty. ``BASE_URL`` always contributes a host, so the
        "empty" branch below can never fire, which meant a local server was
        rejected with ``400 Invalid host header`` for every single request until
        an operator edited deployment settings -- the opposite of what the field
        comment promises. ``TrustedHostMiddleware`` compares only the hostname,
        so the port a dev server listens on is irrelevant here.
        """
        hosts: list[str] = []
        for host in value:
            # Accept a full URL as well as a bare host, since operators naturally
            # paste the value they already have.
            cleaned = host.strip().lower().rstrip("/")
            if "://" in cleaned:
                cleaned = cleaned.split("://", 1)[1]
            cleaned = cleaned.split("/", 1)[0]
            # Drop any port, then normalise IPv6 literals which contain colons.
            if cleaned.startswith("["):
                cleaned = cleaned.split("]", 1)[0] + "]"
            elif ":" in cleaned:
                cleaned = cleaned.split(":", 1)[0]
            if cleaned and cleaned not in hosts:
                hosts.append(cleaned)

        base_url = info.data.get("BASE_URL") or ""
        if "://" in base_url:
            base_host = base_url.split("://", 1)[1].split("/", 1)[0]
            if ":" in base_host and not base_host.startswith("["):
                base_host = base_host.split(":", 1)[0]
            if base_host and base_host not in hosts:
                hosts.append(base_host)

        # Loopback is never a way to reach the deployed service from outside, and
        # it cannot be supplied by a remote caller in place of the real Host, so
        # admitting it costs no security while keeping local development working.
        for loopback in ("localhost", "127.0.0.1", "[::1]"):
            if loopback not in hosts:
                hosts.append(loopback)

        return hosts

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()