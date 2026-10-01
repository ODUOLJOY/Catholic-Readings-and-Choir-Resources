# Implementation Status

**Snapshot:** 2026-10-02
**Overall status:** NOT PRODUCTION-READY. Local implementation and automated
checks do not replace a staging rehearsal, provider/device test, licensed
content, or verified production deployment.

## Verified in this pass

| Area | Status | Evidence |
| --- | --- | --- |
| Primary navigation | VERIFIED | Expo Router declares Home, Downloads, Choir, Profile, Admin in that order. Browser inspection of the exported app showed exactly those five tabs. |
| Diocese → Deanery → Parish profile selection | PARTIALLY VERIFIED | Profile setup loads saved location, searches each level, filters children by parent, clears lower-level choices on parent changes, supports retry/error states, and saves through the API. Backend hierarchy validation/read/update tests pass. No native-device journey was run. |
| Personal profile edit | IMPLEMENTED / TYPE-CHECKED | Account details, phone, and language are loaded and saved through the authenticated profile API. TypeScript passes; a live authenticated UI journey was not run. |
| Admin role handling | VERIFIED LOCALLY | `admin` and `super_admin` are admitted by Admin guards; super-admin-only actions remain separate. Choir global-resource management tests cover the defined `admin` role. |
| Choir upload and scope | VERIFIED LOCALLY | Multipart upload uses the shared upload endpoint, enforces assigned parish/global scope, validates extension/MIME/signature/size, stores files outside public static directories, and creates pending records. SQLite API tests exercise unauthorized global/unscoped uploads and authorized parish submission. |
| Resource review and downloads | VERIFIED LOCALLY | Reviewer scope is checked server-side; approval/rejection records reviewer and time; edits return resources to pending; pending/rejected resources are hidden; approved files and download history enforce parish access. Local private-file flow and cross-parish denial tests pass. |
| Storage provider integration | PARTIALLY IMPLEMENTED | Local private storage and a Firebase Storage adapter support configured bucket and ADC/secret credentials. Local storage was tested. Firebase bucket credentials, durability, and hosted access have not been exercised. |
| Legacy static-file access | VERIFIED LOCALLY | Public media/upload mounts now deny paths associated with any choir-resource record; regression tests cover legacy media and uploads URLs while preserving ordinary public static files. |
| Liturgical engine | PARTIALLY IMPLEMENTED | Cycle boundaries, seasons, ranks, selection behavior, and the 2026-09-30 St Jerome memorial have focused tests. This is not a complete authoritative Kenyan calendar. |
| Readings language schema/API | PARTIALLY IMPLEMENTED | Date/language lookup and one row per date/language are implemented; SQLite migration and PostgreSQL offline SQL checks pass. The complete licensed English/Kiswahili A/B/C lectionary corpus is not present or verified. |
| Database changes | PARTIALLY VERIFIED | SQLite migration fixture covers the additive migration chain, backfills existing published resources as approved, and checks downgrade protection. PostgreSQL offline SQL generation passes. No staging or production schema was inspected or changed. |

## Verification results

- Backend: **31 tests passed** (`python -m pytest -q`), including a regression check that public content detail hides unpublished drafts.
- Backend syntax/bytecode compilation: passed (`python -m compileall -q app migrations`).
- Frontend TypeScript: passed (`npx tsc --noEmit`).
- Frontend lint: passed with **52 warnings** and no errors; most are existing unused-variable/any-type notices.
- Expo web export: passed; 71 static routes emitted. The rendered exported UI showed exactly five bottom tabs. The exported route count is not a claim that all routes are unique or production-ready.
- Migration suite: SQLite fixture upgrades/backfills/downgrades and PostgreSQL offline SQL generation are included in the passing backend suite.
- Focused security review identified a legacy choir-resource URL exposure through public static mounts. Static URL filtering now blocks registered resource paths, including rejected items, and an API/static-file regression test passes.
- No production migration, deployment, payment transaction, SMTP delivery, Firebase storage operation, or native-device session/upload/download test was performed in this pass.

## Current implementation boundaries

| Feature | Status | Remaining work |
| --- | --- | --- |
| Authentication | PARTIALLY VERIFIED | Registration, login, logout, token refresh, password reset, role redirects, and account state still need complete web/native end-to-end coverage against a running API. SMTP delivery is external. |
| Directory | PARTIALLY IMPLEMENTED | Diocese, deanery, and parish relationships, filtering, validation, and profile association exist. A verified complete Kenyan Catholic directory, provenance, repeatable import validation, and comprehensive administrator workflows remain outstanding. |
| Readings/calendar | PARTIALLY IMPLEMENTED | Language-aware API and tested selection rules exist. The calendar is incomplete; authoritative local transfers/observances, approved data, references/provenance, and complete A/B/C English/Kiswahili text are not verified. Do not fabricate or publish substitute lectionary text. |
| Saints | PARTIALLY IMPLEMENTED | Existing routes/screens and import surfaces are present, but a complete verified saints dataset, provenance, and full API/UI acceptance coverage are absent. |
| Choir uploads | VERIFIED LOCALLY / PROVIDER BLOCKED | Local multipart, private delivery, authorization, and moderation paths pass tests. Static mounts deny paths referenced by choir-resource records, including legacy resource URLs. Configure and test durable hosted storage; run native picker and deployed-browser tests. Legacy files remain on disk and have not been migrated to object storage. |
| Offline/downloads | PARTIALLY IMPLEMENTED | Local caching/download history exist. Reliable conflict-safe synchronization, device storage cleanup, retry/resume, and offline authorization behavior are not fully verified on devices. |
| Favorites/reports | PARTIALLY IMPLEMENTED | Existing APIs and UI are present; cross-feature coverage and offline synchronization are incomplete. |
| Payments | PARTIALLY IMPLEMENTED | Callback reconciliation, metadata validation, and idempotency have mocked tests. Daraja sandbox/live flows and subscription activation are unverified. |
| Email/push | EXTERNAL DEPENDENCY | Provider integration/configuration exists in part. SMTP delivery, Firebase/Expo delivery, invalid-token cleanup, scheduling, and real-device behavior are unverified. |
| Authorization | PARTIALLY VERIFIED | Choir-resource scopes and selected community flows have API tests. A complete route-by-route role matrix for every legacy administrator/moderator endpoint remains required. |
| Operations | NOT VERIFIED | Hosting/database state, backup restore, staging schema, deployment workflows, secret rotation, monitoring, and rollback have not been validated. |

## Migration safety

Current migration revisions are:

1. `20261001_01` — scoped community tables and legacy affiliation backfill.
2. `20261001_02` — nullable choir-resource parish scope.
3. `20261002_01` — date-plus-language reading uniqueness.
4. `20261002_02` — private choir-resource storage keys.
5. `20261002_03` — choir-resource moderation/reviewer metadata.

For an existing database, take and restore-test a backup, restore it into
staging, run `python preflight_migrations.py`, inspect Alembic current/history,
review generated SQL, and rehearse the migration and restore before production.
The preflight confirms required legacy schema only; it is not a backup or
compatibility guarantee. Do not automatically apply migrations to an unknown
live database. After new writes, use the verified backup for rollback rather
than relying on downgrades.

## External dependencies and blockers

- Licensed/approved English and Kiswahili lectionary data and reproduction
  rights, and authoritative saint/calendar sources.
- Authoritative, maintained Kenyan jurisdiction/deanery/parish records.
- Staging and production database access, schema owner approval, backup/restore
  evidence, and migration window.
- Durable storage configuration (`STORAGE_BACKEND=firebase`, bucket, and
  workload identity/credentials) for hosted uploads.
- SMTP credentials and sender/domain verification.
- Safaricom Daraja sandbox/production credentials, callback configuration,
  shortcode activation, and business approval for live payments.
- Firebase/Expo notification credentials and supported-device testing.
- Working hosted frontend/backend deployments and staging user accounts for
  role-journey acceptance. Prior checks recorded Render as suspended and the
  configured Vercel URL as unavailable; recheck them before release.

See the root README for local setup and `RELEASE_CANDIDATE.md` for the
production release gates.
