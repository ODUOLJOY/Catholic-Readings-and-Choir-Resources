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

## Testing strategy
- `python -m pytest test_api_integration.py -q -p no:cacheprovider -p no:asyncio` (CORS + login + liturgy routes): all green; default `FRONTEND_URL` is localhost and already allow-listed, so no behavior change in tests.
- `python -c "import ast; ast.parse(open('backend/app/main.py').read())"` compiles.
- Post-deploy: browser console has no CORS errors; `POST /api/auth/login` and
  `GET /api/v1/liturgy/today` return 200; `/health` → `healthy`.
