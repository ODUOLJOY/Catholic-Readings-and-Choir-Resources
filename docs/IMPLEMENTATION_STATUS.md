# Implementation Status - Catholic Readings & Choir Resources App

## Verification snapshot

- **Date:** 2026-10-01
- **Status:** Core defects and an initial scoped-community slice are implemented and locally tested. The application is **not production-ready**; substantial requirements and deployment verification remain.

## Completed and locally verified in this pass

- Consolidated legacy database access onto the application's canonical SQLAlchemy engine, session, and model base; configured in-memory SQLite pooling for tests.
- Removed the duplicate parish-request ORM definition and corrected report/bookmark relationships that blocked mapper setup.
- Added a diocese-specific deanery listing endpoint and validated profile location assignments against their parent relationships.
- Fixed password reset persistence to update the actual password hash; reset tokens are hashed at rest, one-use, sent through configured SMTP, and are not returned by the API.
- Restricted direct role changes to super administrators and removed password hashes from administrator user-list responses.
- M-Pesa success callbacks now require a matching Daraja STK-query result and matching amount, phone number, and receipt metadata; repeated successful callbacks do not extend the same payment twice.
- Added focused SQLite tests for valid and invalid hierarchy assignments, password reset, role-change authorization, user response serialization, and M-Pesa callback validation/idempotency.
- Added scoped parish membership review and role requests that create audited role assignments; existing user-selected parishes are backfilled as pending membership rather than trusted access.
- Added community endpoints/models for scoped announcements and events, private suggestions/prayer intentions, groups, parish/group conversations, message reports/reactions, notification preferences, and audit records.
- Added a secure Super Admin bootstrap command that requires an existing verified account matching configured identity; no password is embedded in source.
- Added additive Alembic migration tooling and a migration fixture test. Automatic `create_all` at startup is now opt-in; production schema was not altered.
- Added community, role-request, membership-review, notification-preference, audit, and administrator UI routes, linked from Home, Profile, and Admin.
- Added API-level tests denying cross-parish message GET/POST/DELETE and rejecting unsupported message updates, plus scoped-role checks and repeated migration/backfill checks.
- Changed `/health` to check database connectivity and return an unavailable status on database failure.
- Configured CORS from application settings while retaining existing configured origins.
- Configured the primary tab route list to exactly Home, Admin, Profile, Payments, Readings, and Downloads; other feature routes remain nested/hidden. Local static-export browser smoke test shows exactly these six tabs.
- Fixed malformed admin-directory JSX, invalid Home reading navigation, frontend type errors, and the Choir empty-search text-node warning.

## Verification results

- Backend compile check: passed.
- Backend tests: 17 passed. These are focused SQLite/service/API authorization tests, not a broad acceptance or production suite.
- Frontend TypeScript check: passed.
- Expo web export: passed; 70 static routes exported.
- Frontend lint: 0 errors, 52 warnings.
- Community authorization API tests: cross-parish conversation GET/POST/DELETE denied; unsupported message PUT returned 405; parish-scoped role checks and self-approval denial passed.
- Migration fixture test: additive schema upgrade, pending affiliation backfill, repeated upgrade, downgrade, and preservation of legacy tables passed against in-memory SQLite.
- Local browser smoke test: exactly six tabs rendered. Because the page was opened as a static file, its API request received 403 without an authenticated backend session.
- Configured database read-only `SELECT 1`: passed; no schema or user data was changed.
- SMTP delivery, push delivery, and Daraja were not exercised. The Render `/health` endpoint returned 503 with a suspended-service response; the configured Vercel URL returned 404 `DEPLOYMENT_NOT_FOUND`.

## Outstanding audit and implementation work

| Priority | Status | Evidence / blocker |
| :--- | :--- | :--- |
| 1. Security and authorization | PARTIAL / LOCALLY TESTED | New community routes enforce scoped role assignments and verified parish membership; cross-parish messaging and role-scope tests pass. Legacy content/storage/admin endpoints still need a complete route-by-route scope review and broader adversarial tests. |
| 2. Catholic directory | PARTIAL | Existing Diocese/Deanery/Parish relationships and profile checks remain. Country/jurisdiction variants, outstations, scoped operators, full duplicate-safe imports, and verified official records are missing. |
| 3. Database and migration safety | PARTIAL / STAGING BLOCKED | An additive Alembic migration and in-memory legacy-schema upgrade/backfill/downgrade test exist. No staging schema comparison, backup/restore, or production migration was performed. |
| 4. Administrative role requests | PARTIAL / LOCALLY TESTED | Scoped role requests, review states, approval-generated assignments, revocation checks, and audit rows exist. Supporting-document upload and the full administrator lifecycle UI remain incomplete. |
| 5. Community features | PARTIAL / LOCALLY TESTED | Scoped announcements/events, suggestions, prayer intentions, groups, conversations/messages, reporting, notification preferences, and audit endpoints/UI exist. Attachments, full moderation workflows, push delivery, read receipts, and full group-management UI remain incomplete. |
| 6. Readings and approved content | BLOCKED BY DATA / PARTIAL | Existing liturgical service remains; authorized English/Kiswahili datasets, provenance, approvals, and full local-calendar testing are not verified. |
| 7. Choir, uploads, moderation, offline | PARTIAL / NOT VERIFIED | Public detail now hides unapproved resources. Existing choir-resource rows and static file delivery are global, so parish-scoped Music Director permissions are not wired in; secure storage, moderation, and device offline sync remain unverified. |
| 8. M-Pesa and subscriptions | PARTIAL / MOCKED TESTS | Provider STK-query reconciliation and callback metadata checks have mocked tests. Daraja sandbox initiation/callback and live approval/credentials remain unverified. |
| 9. Email, push, operations | PARTIAL / EXTERNAL CONFIG REQUIRED | SMTP is not configured in the checked environment. Firebase credential fields are present but delivery is untested; scheduled-job token is absent. |
| 10. Regression and release | BLOCKED / LOCALLY TESTED | Backend compile/import and 17 tests, frontend typecheck/lint/web export, and six-tab static browser smoke test run. Current Render service is suspended and Vercel deployment is missing; no full role-journey E2E or native-device test was run. |

- **Authentication:** Reset-token handling and SMTP message construction have focused tests. Actual SMTP delivery, reset deep links on native devices, token expiry under production clocks, registration, logout, account status, and cross-platform secure storage are not verified end to end. Forgot-password returns 503 unless SMTP is configured.
- **Directory:** Current relational scope remains Diocese/Deanery/Parish. Country, Catholic jurisdiction variants, outstations, safe repeatable imports, import preview, and scoped directory administration remain outstanding. No official Kenya directory was imported or verified.
- **Schema changes:** An additive Alembic migration is present and tested only on an in-memory legacy-schema fixture. No production migration was created/applied, and the exact deployed schema is unknown. `AUTO_CREATE_TABLES` defaults to false; enable it only in an explicit development setup.
- **Authorization:** New community membership and role assignment paths are scope-checked. Some legacy administration/content routes and moderator boundaries have not received a complete scope audit. The initial Super Admin bootstrap command has not been run.
- **Music roles:** Scoped music roles can be approved, but they do not administer the legacy globally-scoped choir resource records or their public file URLs. Scope migration and private file delivery must be completed before granting that capability.
- **Readings and saints:** Approved content datasets, source provenance, licensing, local calendars, and full calendar edge-case coverage remain unverified.
- **Content lifecycle:** Secure private uploads, approval/report workflows, audit history, and storage authorization require further implementation and verification.
- **Offline and notifications:** Real device file downloads, synchronization, push-token lifecycle, and scheduled notification delivery have not been verified.
- **Payments:** Callback-to-provider status cross-checking and metadata consistency/idempotency have unit tests with mocked Daraja responses. Sandbox initiation/delivery, reconciliation, production credentials/approval, and live subscription activation remain unverified.
- **Deployment:** Read-only database connectivity succeeded locally. Remote Render health returns 503 (service suspended) and the Vercel deployment URL returns 404 (`DEPLOYMENT_NOT_FOUND`). SMTP is not configured; Firebase credential fields exist but delivery is untested; Daraja was not contacted; scheduled-job token is absent; local configured storage directory is absent.

## Next priorities

1. Compare the additive migration against a restored staging schema and verify backup/rollback before applying it outside local fixtures.
2. Complete scope checks and API tests for every legacy admin, upload, moderation, and resource-management route.
3. Finish message attachment/read-state, reporting/moderation workflows, and role/admin lifecycle UI; run member/admin journeys.
4. Resolve the 52 outstanding frontend lint warnings without unrelated bulk edits.
5. Verify authentication, content approval, and restricted storage against staging and real configured services.
6. Establish authorized directory/content sources and finish offline, payment, notification, and deployment verification before release.
