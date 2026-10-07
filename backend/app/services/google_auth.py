"""Google Sign-In helpers.

Verification is delegated to Google's own ``google-auth`` library so that the
signature, issuer, audience and expiry of an ID token are all validated. The
provider subject (``sub``) is the only value used to identify an external
account; a caller-supplied email is never trusted on its own.
"""
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional
import uuid
from urllib.parse import urlencode

import requests
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt

from app.auth.security import ALGORITHM
from app.core.config import settings

logger = logging.getLogger(__name__)

PROVIDER_GOOGLE = "google"

# Both issuer spellings are emitted by Google depending on the token source.
GOOGLE_ISSUERS = frozenset(
    {
        "accounts.google.com",
        "https://accounts.google.com",
    }
)

GOOGLE_STATE_TYPE = "google_oauth_state"
GOOGLE_STATE_TTL_SECONDS = 600
GOOGLE_SCOPES = "openid email profile"

# Loopback redirect URIs on any port are accepted for local development,
# mirroring the CORS loopback policy in config.LOOPBACK_ORIGIN_RE.  A remote
# host cannot claim a loopback origin, so this carries no additional security
# risk and avoids the fragility of hardcoding the dynamic Expo dev-server port
# (which changes between 8081, 8082, 8083, etc. on each restart).
_LOOPBACK_REDIRECT_RE = re.compile(
    r"^https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?/auth/google$",
    re.IGNORECASE,
)


class GoogleAuthError(RuntimeError):
    """Raised when a Google identity cannot be trusted or is not configured."""


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: Optional[str]
    email_verified: bool
    name: Optional[str]
    picture: Optional[str]


def google_oauth_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID)


def _verify_with_google(id_token_value: str, audience: str) -> Mapping[str, Any]:
    return google_id_token.verify_oauth2_token(
        id_token_value,
        google_requests.Request(),
        audience,
    )


def verify_google_id_token(
    id_token_value: str,
    *,
    audience: Optional[str] = None,
) -> GoogleIdentity:
    """Verify a Google ID token and return the trusted identity."""

    if not google_oauth_configured():
        raise GoogleAuthError("Google sign-in is not configured.")

    expected_audience = audience or settings.GOOGLE_CLIENT_ID

    try:
        claims = _verify_with_google(id_token_value, expected_audience)
    except (ValueError, google_exceptions.GoogleAuthError) as error:
        logger.info("Rejected Google ID token: %s", type(error).__name__)
        raise GoogleAuthError("Invalid Google identity token.") from error

    issuer = claims.get("iss")
    if issuer not in GOOGLE_ISSUERS:
        raise GoogleAuthError("Unexpected Google token issuer.")

    subject = claims.get("sub")
    if not subject:
        raise GoogleAuthError("Google identity is missing a subject.")

    email_value = claims.get("email")
    email = str(email_value).strip().lower() if email_value else None
    email_verified = claims.get("email_verified")
    if isinstance(email_verified, str):
        email_verified = email_verified.lower() == "true"

    name = claims.get("name")
    picture = claims.get("picture")

    return GoogleIdentity(
        subject=str(subject),
        email=email,
        email_verified=bool(email_verified),
        name=str(name).strip() if name else None,
        picture=str(picture).strip() if picture else None,
    )


def allowed_redirect_uris() -> set[str]:
    uris: set[str] = set()
    if settings.GOOGLE_REDIRECT_URI.strip():
        uris.add(settings.GOOGLE_REDIRECT_URI.strip())
    for value in settings.GOOGLE_ALLOWED_REDIRECT_URIS.split(","):
        candidate = value.strip()
        if candidate:
            uris.add(candidate)
    # The production web front-end redirects back to ``<FRONTEND_URL>/auth/google``
    # (see frontend/src/services/googleAuthService.ts ``googleRedirectUri``). Derive
    # that URI from the canonical ``FRONTEND_URL`` so the backend always allows the
    # redirect URI the front-end actually sends, instead of requiring operators to
    # also list it in GOOGLE_ALLOWED_REDIRECT_URIS. Only http/https origins are
    # derived this way; platform-specific schemes (e.g. the mobile deep link
    # ``frontend://auth/google``) must still be supplied explicitly via GOOGLE_*.
    frontend = (settings.FRONTEND_URL or "").strip().rstrip("/")
    if frontend.startswith(("http://", "https://")):
        uris.add(f"{frontend}/auth/google")
    return uris


def validate_redirect_uri(redirect_uri: str) -> str:
    candidate = (redirect_uri or "").strip()
    allowed = allowed_redirect_uris()
    if not candidate:
        raise GoogleAuthError("A redirect URI is required.")
    # Accept any loopback URI on any port — the Expo dev server picks a dynamic
    # port on each restart, and a remote host cannot claim a loopback origin.
    if _LOOPBACK_REDIRECT_RE.match(candidate):
        return candidate
    if candidate not in allowed:
        raise GoogleAuthError("The requested redirect URI is not allowed.")
    return candidate


def build_authorization_url(redirect_uri: str, state: str) -> str:
    if not google_oauth_configured():
        raise GoogleAuthError("Google sign-in is not configured.")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
        "include_granted_scopes": "true",
    }
    return f"{settings.GOOGLE_AUTH_URI}?{urlencode(params)}"


def create_google_state() -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        seconds=GOOGLE_STATE_TTL_SECONDS
    )
    return jwt.encode(
        {
            "type": GOOGLE_STATE_TYPE,
            "jti": str(uuid.uuid4()),
            "exp": expire,
        },
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def verify_google_state(state: str) -> bool:
    try:
        payload = jwt.decode(
            state,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except JWTError:
        return False
    return payload.get("type") == GOOGLE_STATE_TYPE


def exchange_google_code(code: str, redirect_uri: str) -> GoogleIdentity:
    if not google_oauth_configured() or not settings.GOOGLE_CLIENT_SECRET:
        raise GoogleAuthError("Google sign-in is not configured.")

    try:
        response = requests.post(
            settings.GOOGLE_TOKEN_URI,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        logger.warning("Google code exchange failed: %s", type(error).__name__)
        raise GoogleAuthError(
            "Unable to exchange the Google authorization code."
        ) from error

    id_token_value = payload.get("id_token")
    if not id_token_value:
        raise GoogleAuthError("Google did not return an identity token.")

    return verify_google_id_token(id_token_value)
