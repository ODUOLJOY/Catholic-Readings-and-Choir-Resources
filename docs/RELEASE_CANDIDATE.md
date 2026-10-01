# Release Candidate Checklist

## Release decision

**NOT APPROVED FOR PRODUCTION.** The local code changes and tests in this
snapshot do not verify hosted storage, external providers, a real staging
database, a complete content corpus, native-device behavior, or a deployed
end-to-end journey.

## Checks completed in this pass

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Backend tests | PASS | 31 tests pass, including hierarchy, calendar/readings selection, choir upload/authorization/moderation, migration fixtures, and unpublished-content access control. |
| Backend compile | PASS | `python -m compileall -q app migrations`. |
| SQLite migration fixture | PASS | Upgrade, backfill, downgrade, and moderation/storage revisions exercised against a legacy fixture. |
| PostgreSQL migration SQL | PASS (offline) | Alembic-generated SQL is inspected by the migration test; no PostgreSQL server or production schema was changed. |
| TypeScript | PASS | `npx tsc --noEmit`. |
| Expo lint | PASS WITH WARNINGS | 0 errors, 52 warnings. Warnings are not treated as a clean lint baseline. |
| Expo web export | PASS | 71 static routes emitted. Exported browser inspection showed exactly the five required tabs: Home, Downloads, Choir, Profile, Admin. |
| Upload and file access | PASS (local API) | Multipart submission, file-type/signature checks, assigned scope, approval gates, authenticated private file delivery, rejected/pending hiding, parish denial, and denial of legacy choir-resource URLs on public static mounts are covered by tests. |
| Live service delivery | NOT RUN | No SMTP, Firebase Storage, push, Daraja, or hosted API transaction was performed. |
| Production migration/deployment | NOT RUN | No live/staging migration, deployment, backup, or restore was performed. |

## Go-live gates

- [ ] Recheck and restore the configured hosting services; prior checks found a
  suspended Render backend and unavailable configured Vercel deployment.
- [ ] Obtain a production schema snapshot; take a database backup and prove
  restore into an isolated staging database.
- [ ] Run the migration preflight and inspect `alembic current` and `history`
  against that restored schema.
- [ ] Review generated PostgreSQL SQL and rehearse all five current additive
  migrations on staging; verify row counts, legacy resource scope, indexes,
  constraints, and API startup.
- [ ] Set `AUTO_CREATE_TABLES=false` in every deployed environment. Configure
  production database and secrets only through the host secret manager.
- [ ] Configure persistent object storage and verify private upload, review,
  approved download, deletion, retention, and cross-parish denial on staging.
- [ ] Run authenticated user, parish music director, choir director, parish
  administrator, moderator, admin, and super-admin journeys.
- [ ] Test account registration/login/logout/session expiry/password reset,
  hierarchy setup/edit, daily readings, language switching, downloads, and
  profile navigation on web and native devices.
- [ ] Obtain and validate authorized directory, liturgical calendar, saint,
  and English/Kiswahili lectionary sources before publishing content.
- [ ] Verify Daraja sandbox initiation, cancellation/failure, callback
  signatures/status, duplicate callbacks, and reconciliation; obtain
  Safaricom production activation before collecting live payments.
- [ ] Verify SMTP delivery/reset links and Firebase/Expo token registration,
  delivery, invalid-token handling, and scheduled jobs using test accounts.
- [ ] Record monitoring, incident contact, data-retention policy, rollback
  window, backup cadence, and deployment owner.

## Safe migration and backup procedure

Do not execute a migration against an unknown production database. From
`backend/`, against a restored staging copy:

```powershell
.\.venv\Scripts\python.exe preflight_migrations.py
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe history
.\.venv\Scripts\alembic.exe upgrade head
```

For PostgreSQL, produce and review offline SQL by configuring the staging
`DATABASE_URL` and running:

```powershell
.\.venv\Scripts\alembic.exe upgrade head --sql
```

Before production, take a provider/database-native backup (for PostgreSQL,
`pg_dump --format=custom --file=<backup-file> <database>`), restore it into an
isolated database (`pg_restore --clean --if-exists --dbname=<restore-db>
<backup-file>`), and rehearse the migration and application checks there.
Never put credentials in shell history or commit backup files. The application
preflight validates only expected legacy tables/columns; it does not prove
backup integrity. If post-migration data has been written, use the verified
backup for rollback rather than assuming downgrade is safe.

## Configuration inventory

Use `backend/.env.example` as a list of variable names and safe local defaults.
Replace placeholders before startup. For production, use the platform's secret
manager and rotate credentials if they may have appeared in logs or shell
history.

| Area | Variables / external action |
| --- | --- |
| Core | `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `AUTO_CREATE_TABLES`. Production must keep automatic table creation disabled. |
| Frontend/API/CORS | Frontend `EXPO_PUBLIC_API_URL`; backend `FRONTEND_URL`, `BASE_URL`, `ALLOWED_ORIGINS`, `DEBUG`. Origins must exactly match deployed origins. |
| Storage | `STORAGE_BACKEND`, `STORAGE_PATH`, `FIREBASE_PROJECT_ID`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_PRIVATE_KEY`; hosted durable storage and credentials remain unverified. Prefer workload identity/ADC over a checked-in key file. |
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`; SMTP provider account and sender verification are external. |
| Daraja | `MPESA_ENVIRONMENT`, `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_PASSKEY`, `MPESA_SHORTCODE`, `MPESA_CALLBACK_URL`, and the transaction/reference settings; production activation requires Safaricom/business approval. |
| Push/scheduling | Firebase project/credential settings and `SCHEDULED_JOB_TOKEN`; provider delivery, device testing, and scheduler setup are outstanding. |
| Admin bootstrap | `BOOTSTRAP_SUPER_ADMIN_EMAIL`; set only to an existing registered and verified account through protected deployment configuration. The application default is blank. |

## Content and product limitations

- Official/licensed readings are not fabricated by the application. No complete
  A/B/C English/Kiswahili lectionary corpus is verified in this repository.
- The calendar implementation is partial and is not an authoritative local
  Kenyan calendar. September 30, 2026 has a regression test for St Jerome, but
  that does not certify all calendar dates or local transfers.
- The directory schema supports Diocese → Deanery → Parish, but a verified
  complete Kenya Catholic directory and data-maintenance source remain needed.
- Local private storage and upload API tests do not prove persistent hosted
  storage, malware scanning, or reliable native/offline transfer.
- A 71-route static export and five visible tabs do not establish every route's
  reachability or the absence of every route-level issue.

**Do not announce a production release until all unchecked gates are completed
and the evidence is reviewed by the database, content, hosting, and payment
owners.**
