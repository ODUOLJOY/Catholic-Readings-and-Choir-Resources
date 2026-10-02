"""Report auth env key presence only. Never print values."""
from pathlib import Path

from dotenv import dotenv_values

# Raw line presence (including empties / duplicates)
raw: dict[str, list[str]] = {}
for line in Path(".env").read_text(encoding="utf-8", errors="ignore").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    raw.setdefault(k.strip(), []).append("EMPTY" if not v.strip().strip('"').strip("'") else "NONEMPTY")

keys = [
    "SECRET_KEY",
    "DATABASE_URL",
    "BOOTSTRAP_SUPER_ADMIN_EMAIL",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REDIRECT_URI",
    "GOOGLE_ALLOWED_REDIRECT_URIS",
    "FRONTEND_URL",
    "SMTP_HOST",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
    "ALLOWED_ORIGINS",
]
print("=== raw .env occurrences ===")
for k in keys:
    occ = raw.get(k)
    if not occ:
        print(f"{k}: ABSENT")
    else:
        print(f"{k}: {len(occ)}x -> {','.join(occ)}")

# Effective values via python-dotenv (later wins)
try:
    effective = dotenv_values(".env")
except Exception:
    effective = {}
print("=== effective nonempty (dotenv later-wins) ===")
for k in keys:
    v = effective.get(k)
    if v is None:
        print(f"{k}: ABSENT")
    elif str(v).strip():
        print(f"{k}: PRESENT")
    else:
        print(f"{k}: EMPTY")
