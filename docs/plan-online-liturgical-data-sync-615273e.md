# Plan — Vercel vs. Render deployment: CORS blocks login + liturgy

## Overview
The Vercel-hosted frontend (`https://catholic-readings-and-choir-resourc.vercel.app`)
cannot call the Render backend: every request is blocked by the browser with
`Access to XMLHttpRequest at '...onrender.com/api/...' from origin '...vercel.app'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present`.
Locally it works because the dev origin `http://localhost:8081` is matched by the
loopback regex in `app.core.config.LOOPBACK_ORIGIN_RE`.

Root cause is two layers:
1. **Operational (primary): Render env vars were NOT synced.** `git push` →
   Render auto-rebuild, but `render.yaml` edits to `ALLOWED_ORIGINS` /
   `FRONTEND_URL` do NOT reach the running service until the operator clicks
   **"Sync changes"** in the Render dashboard (or edits the env var there).
   "Clearing build cache and deploying" rebuilds the image but leaves the stale
   Dashboard env vars (old Netlify origin) in place — exactly the symptom the
   user sees after redeploy.
2. **Code (root fragility): CORS allow-list is a SEPARATE env var from
   `FRONTEND_URL`.** They can drift, which is what produced this outage. There is
   no reason two env vars must both be correct: `FRONTEND_URL` is already the
   canonical frontend origin (it drives Google redirect-URI derivation and
   password-reset / email-verification links). CORS should trust it directly.

## Implementation approach

## Verified deployment state (checked, no edits yet)
- `backend/.env` is gitignored → **not** shipped to Render; production env comes
  only from the **Render Dashboard**.
- Dashboard `FRONTEND_URL` is still the stale Netlify URL
  (`https://stellular-clafoutis-ad641c.netlify.app`) and there is **no "Sync
  changes" UI** in this Render environment. Dashboard env vars override
  `render.yaml` after provisioning, so commit `6e9109a` (which corrected both
  `render.yaml` and `config.py` defaults) is **inert on Render until the
  Dashboard vars are edited directly**. This is exactly why login + liturgy still
  fail after "clearing build cache and deploying": the image rebuilt but the
  stale env vars still govern CORS and redirect URIs.
- CORS allow-list is `_allowed_origins` in `app/main.py` (sourced from
  `settings.ALLOWED_ORIGINS`, which the stale Dashboard var overrides).
- `FRONTEND_URL` is the canonical frontend origin (drives Google redirect-URI
  derivation `services/google_auth.allowed_redirect_uris()` + reset/verify email
  links in `services/email.py`).

### Step 1 — Make CORS derive from `FRONTEND_URL` (single source of truth) [code hardening]
File: `backend/app/main.py`. Append the cleaned `settings.FRONTEND_URL` origin to
`_allowed_origins`. Strictly additive + deduped; zero behavior change for local/dev
(localhost FRONTEND_URL is already allow-listed):

```python
_allowed_origins = [origin for origin in settings.ALLOWED_ORIGINS if origin != "*"]
_frontend_origin = (settings.FRONTEND_URL or "").strip().rstrip("/")
if _frontend_origin.startswith(("http://", "https://")) and _frontend_origin not in _allowed_origins:
    _allowed_origins.append(_frontend_origin)
```

### Step 2 — `render.yaml` / `config.py` (already committed in 6e9109a)
Already correct: both list
`https://catholic-readings-and-choir-resourc.vercel.app`. This commit makes a
single correct env var sufficient, so future deploys don't re-drift.

### Step 3 — User operational step (CANNOT be done from code; required either way)
Either option below, on the **Render dashboard → service → Environment →
Environment Variables**:
- Edit `FRONTEND_URL` → `https://catholic-readings-and-choir-resourc.vercel.app`
  and **Save** (triggers a redeploy).
- With Option B only, that *single* edit also fixes CORS. With Option A you must
  additionally edit `ALLOWED_ORIGINS` to add the Vercel origin and Save.

## Options (user must pick; both need the Step 3 Dashboard edit)

### Option A — No code change (fastest)
Edit the Dashboard `ALLOWED_ORIGINS` list to add
`https://catholic-readings-and-choir-resourc.vercel.app`, and edit `FRONTEND_URL`
to the Vercel origin. Save + redeploy. Leaves the dual-var drift risk.

### Option B — Code hardening (recommended, durable)
Implement Step 1 (CORS trusts `FRONTEND_URL`), commit + push (Render
auto-redeploys the new image), then edit **only** `FRONTEND_URL` in the Dashboard
to the Vercel origin and Save+redeploy. CORS + Google redirect-URI + email links
all follow from that single var; future origin changes need one edit.

**Recommendation: Option B.** Also paste `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`
(from Google Cloud Console) into the Dashboard if Google sign-in is wanted
(`sync: false`; not the cause of login/liturgy failure — that is CORS).

## Local backend won't restart on the new `.env` (operational, not a code defect)
The user re-ran `uvicorn app.main:app --reload` in a terminal that resolved
`uvicorn`/`python` to the **system Python 3.12** (`C:\Users\hp\AppData\Local\Programs\Python\Python3.12`),
which has no `sqlalchemy` → `ModuleNotFoundError: No module named 'sqlalchemy'`
in the worker spawn. A second attempt hit `WinError 10013` (port 8000 already in use
by leftover processes). The project venv (`.venv`, Python 3.11.5, sqlalchemy
2.0.40) is correct and has all deps.

### Fix steps
1. Free port 8000: `taskkill /F /PID 6060 /PID 1732 /PID 30228` (stale uvicorn
   workers; PID 28828 is `WmiPrvSE`, not the backend, and is left alone).
2. Start with the **venv** interpreter so deps resolve:
   `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
3. Verify: `curl http://127.0.0.1:8000/health` → `{"status":"healthy",...}` and
   `OPTIONS /api/auth/login` with `Origin: https://catholic-readings-and-choir-resourc.vercel.app`
   → `200` + `access-control-allow-origin: https://catholic-readings-and-choir-resourc.vercel.app`.

## Testing strategy
- Local: `.\.venv\Scripts\python.exe -m pytest test_api_integration.py test_runtime_error_repair.py -q`
  green (CORS/login/liturgy); `OPTIONS /api/auth/login` from the Vercel origin now
  returns `200` + `ACAO`; `GET /api/v1/liturgy/today?region=KE` → `200`.
- `/health` → healthy; manual browser login + liturgy load on localhost.

## Phone/LAN testing + local backend restart (this turn)

### Root causes
1. Local backend won't start → two failure modes:
   - bare `uvicorn` resolves to **system Python 3.12** (no `sqlalchemy`) →
     `ModuleNotFoundError`; must invoke via the **project venv**.
   - `WinError 10013` on port 8000 → a leftover process (my temp `backend-dev`
     instance) still holds the socket; must free 8000 first.
2. Phone/LAN dev rejected by CORS → `LOOPBACK_ORIGIN_RE` only matches
   `localhost|127.0.0.1|[::1]`; a phone origin like `http://192.168.1.50:8081`
   matches neither the `allow_origins` list nor the regex → Starlette returns
   `400 Disallowed` (no `ACAO`) → browser reports a CORS/network error.

### Fix 1 — operational (free port + venv launch)
Kill the temp instance on 8000, then launch with the venv on `0.0.0.0` so LAN
devices can reach it. `.env` (local-only, gitignored) is already corrected
(`FRONTEND_URL`, `ALLOWED_ORIGINS`, `GOOGLE_*_REDIRECT_URI` → Vercel).

### Fix 2 — code: dev-gated LAN origins (secure by default)
`backend/app/core/config.py`:
```python
# After LOOPBACK_ORIGIN_RE:
LAN_ORIGIN_RE = re.compile(
    r"^https?://(?:"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|169\.254\.\d{1,3}\.\d{1,3}"
    r")(?::\d{1,5})?$", re.IGNORECASE,
)

def origin_regex(allow_lan: bool = False) -> re.Pattern[str]:
    if allow_lan:
        return re.compile("|".join([LOOPBACK_ORIGIN_RE.pattern, LAN_ORIGIN_RE.pattern]), re.IGNORECASE)
    return LOOPBACK_ORIGIN_RE

def is_allowed_origin(origin, allowed_origins, allow_lan: bool = False) -> bool:
    if not origin: return False
    candidate = origin.strip().rstrip("/")
    if candidate == "*": return False
    if candidate in allowed_origins or LOOPBACK_ORIGIN_RE.match(candidate): return True
    return allow_lan and LAN_ORIGIN_RE.match(candidate) is not None
```
Add field `ALLOW_LAN_ORIGINS: bool = False` (CORS section). Default `False` keeps
production safe; the existing 2-arg `is_allowed_origin` callers stay compatible via
the default.

`backend/app/main.py`:
- import: `from app.core.config import is_allowed_origin, origin_regex, settings`
  (drop `LOOPBACK_ORIGIN_RE` — now unused here).
- `allow_origin_regex=origin_regex(settings.ALLOW_LAN_ORIGINS)`.
- `_cors_headers`: `is_allowed_origin(origin, _allowed_origins, allow_lan=settings.ALLOW_LAN_ORIGINS)`.

`backend/.env` (local) — append:
```
# Local dev only: permit private/LAN origins for phone/tablet dev. NEVER on Render.
ALLOW_LAN_ORIGINS=True
```

Frontend (no code change): on the phone set
`EXPO_PUBLIC_API_URL=http://192.168.1.50:8000` (your LAN IP) so the dev client
points at the `0.0.0.0`-bound backend.

### Security note
`ALLOW_LAN_ORIGINS` widens credentialed-CORS to anyone on the same Wi-Fi — an
explicit dev-only trade-off, defaulting off, and never set in `render.yaml`.

## Testing strategy
- `pytest test_api_integration.py test_runtime_error_repair.py -q` green (no
  signature regression; loopback still allowed, LAN still rejected when flag off).
- Start venv backend `0.0.0.0:8000`; `curl` OPTIONS preflight with
  `Origin: http://192.168.1.50:8081` → `200` + `ACAO` = that LAN origin (flag on),
  and `http://localhost:8081` → `200` (regression). `/health` 200, login 401,
  `/api/v1/liturgy/today?region=KE` 200. Then stop the instance to free 8000 and
  hand the launch command back to the user.

## Testing strategy
- `python -m pytest test_api_integration.py -q -p no:cacheprovider -p no:asyncio` (CORS + login + liturgy routes): all green; default `FRONTEND_URL` is localhost and already allow-listed, so no behavior change in tests.
- `python -c "import ast; ast.parse(open('backend/app/main.py').read())"` compiles.
- Post-deploy: browser console has no CORS errors; `POST /api/auth/login` and
  `GET /api/v1/liturgy/today` return 200; `/health` → `healthy`.
