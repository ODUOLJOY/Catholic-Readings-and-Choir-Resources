# Catholic Readings & Choir Resources

Existing Expo/React Native frontend and FastAPI backend for Catholic readings,
parish directory, choir resources, community features, downloads, and
administration. The project is not approved for production until the release
gates in [`docs/RELEASE_CANDIDATE.md`](./docs/RELEASE_CANDIDATE.md) are closed.

## Project layout

- `frontend/` — Expo Router app (TypeScript; web, Android, and iOS targets).
- `backend/` — FastAPI app, SQLAlchemy models, Alembic migrations, and tests.
- `docs/IMPLEMENTATION_STATUS.md` — verified implementation snapshot and gaps.
- `docs/RELEASE_CANDIDATE.md` — release gates, external dependencies, and
  migration/backup precautions.

## Local development

### Backend

Use Python 3.11 or newer. From PowerShell:

```powershell
Set-Location backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `SECRET_KEY` and `DATABASE_URL` in `backend/.env`. For a disposable,
empty local database only, set `AUTO_CREATE_TABLES=true`; the application
creates its current ORM tables at startup. Do not enable this in production or
use it as a substitute for reviewed migrations on an existing database.

Start the API from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, with OpenAPI at `/docs` and a
database-aware health check at `/health`.

Run checks from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app migrations
```

### Frontend

From `frontend/`:

```powershell
npm ci
$env:EXPO_PUBLIC_API_URL = "http://127.0.0.1:8000"
npx expo start --web
```

For native development use `npx expo start` and open the project on a configured
Android or iOS device. A physical device must use a backend URL reachable from
that device, not `127.0.0.1`.

Frontend checks:

```powershell
npx tsc --noEmit
npm run lint
npx expo export --platform web
```

The configured primary tab bar is Home, Downloads, Choir, Profile, and Admin.
Readings and Payment remain reachable through their feature flows; management
pages are nested under Admin.

## Database and migrations

The deployed schema is not assumed to match the local models. Before applying a
migration to an existing database:

1. Take a database backup and prove that it can be restored to an isolated
   database.
2. Restore a recent production backup to staging.
3. From `backend/`, configure staging `DATABASE_URL`, then run:

   ```powershell
   .\.venv\Scripts\python.exe preflight_migrations.py
   .\.venv\Scripts\alembic.exe current
   .\.venv\Scripts\alembic.exe history
   ```

4. Review the schema and generated SQL against the restored copy; rehearse
   `alembic upgrade head` and the application test suite on staging.
5. Confirm row counts, constraints, and resource visibility, then repeat the
   backup/restore rehearsal before scheduling a production change.

The current additive migration chain includes community tables, choir-resource
parish scope, bilingual reading uniqueness, resource storage keys, and
moderation metadata. The fixture tests exercise SQLite upgrade/backfill/
downgrade and PostgreSQL offline SQL generation. These checks do not establish
the state of any hosted database. Do not run an upgrade against production
without an independently verified backup and approved staging rehearsal. Once
new data is written, restore the backup rather than relying on a downgrade.

## Storage, approvals, and uploads

Uploads are submitted as private, pending choir resources. The API checks
extension, declared MIME type, file signature, size, upload scope, and reviewer
scope. Pending and rejected files are not served by the public choir API.
Approved resource files are delivered only through the authenticated,
parish-authorized API endpoint.
The public `/media` and `/uploads` static mounts suppress any path associated
with a choir-resource database record, including legacy URLs; those records
must use the protected API endpoint.

`STORAGE_BACKEND=local` is suitable only for local development or a host with
durable mounted storage. For hosted deployments configure:

- `STORAGE_BACKEND=firebase`
- `FIREBASE_STORAGE_BUCKET`
- `FIREBASE_PROJECT_ID`
- Google Application Default Credentials/workload identity, or the paired
  `FIREBASE_CLIENT_EMAIL` and `FIREBASE_PRIVATE_KEY` secret variables.

The Firebase adapter uses a private bucket through the server SDK; it does not
make uploaded objects public. Provider credentials, bucket access rules,
durability, and device upload/download behavior still require staging
verification. Existing legacy media files are not migrated by the storage-key
migration, though their registered static URLs are denied by the API.

Reviewers find pending resources in Admin or their authorized parish queue.
Approval records reviewer and timestamp and makes the resource available to
its authorized audience. Rejection records reviewer, timestamp, and reason;
the rejected resource remains hidden and retained for audit. Editing a
published resource returns it to pending review.

## Admin setup and content imports

The initial Super Admin command provisions an existing, verified account
matching `BOOTSTRAP_SUPER_ADMIN_EMAIL`:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app.bootstrap_super_admin
```

Configure the email through the deployment secret/configuration manager; the
application default is intentionally blank. No initial account is created by
this command. Restrict command execution and retain its audit entry.

Admin directory and content-import routes require authorized roles. Only import
records from an authoritative source, validate the file/schema and review the
preview before committing. No complete authoritative Kenyan Catholic
jurisdiction/deanery/parish directory, saints corpus, or licensed bilingual
lectionary corpus is currently verified in this repository. Do not invent
records or reading text.

## External service configuration

Copy `backend/.env.example` to `backend/.env` for local use. Supply production
secrets through the hosting provider's secret manager, never source control.

- **Email/password reset:** configure SMTP host, port, username, password, and
  sender. Delivery and mobile deep-link behavior need a live provider test.
- **M-Pesa:** configure Daraja sandbox values first; production Shortcode/
  PayBill/Till, credentials, callback URL, and business activation require
  Safaricom/provider action. A client-reported result is not payment
  confirmation.
- **Push:** configure Firebase project credentials/ADC and notification-token
  ownership; delivery requires Expo/device/provider testing.
- **CORS/API URL:** configure `ALLOWED_ORIGINS`, `FRONTEND_URL`, `BASE_URL`, and
  frontend `EXPO_PUBLIC_API_URL` to the deployed origins.

See the release candidate document for backup/restore commands, outstanding
external dependencies, and the production release decision.
