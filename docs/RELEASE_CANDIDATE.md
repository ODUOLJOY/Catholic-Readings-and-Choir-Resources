# Release Candidate Verification

## Release decision

**Not approved for production.** This snapshot records only the local checks actually completed. A passing frontend build or small backend test set is not an end-to-end acceptance result.

## Verification matrix

| Area | Result | Evidence | Production verification |
| :--- | :--- | :--- | :--- |
| Primary tab navigation | PASS (local static-export browser smoke test) | Browser showed exactly Home, Admin, Profile, Payments, Readings, and Downloads. Other feature routes are hidden from the tab bar. Expo export passed with 70 static routes. | Native-device verification not performed. Static-file API request returned 403 without an authenticated backend session. |
| Choir text-node regression | PASS (local web smoke test) | No `Unexpected text node` warning after fixing the blank-search conditional. | Not performed on native devices. |
| Frontend types | PASS | `npx tsc --noEmit`. | Not applicable. |
| Frontend export | PASS | `expo export --platform web`; 70 routes. | Hosting/deployed build not tested. |
| Frontend lint | PASS WITH WARNINGS | 0 errors and 52 warnings. | Warnings remain to review. |
| Backend syntax | PASS | Python compile check. | Not applicable. |
| Backend automated tests | LIMITED PASS | 17 focused tests passed, including hierarchy, password reset, scoped community authorization, API cross-parish messaging denial, unapproved choir-detail denial, migration fixture upgrade/backfill/downgrade, response serialization, email construction, and mocked M-Pesa callback checks. | No broad role-journey or production tests. |
| Configured database | LIMITED PASS | Read-only `SELECT 1` succeeded through the configured SQLAlchemy engine. | No schema inspection or writes; staging/production identity and backup state were not independently verified. |
| Current Render service | BLOCKED | GET `/health` returned HTTP 503 with “This service has been suspended.” | Hosting provider must restore service; no deployment was attempted. |
| Current Vercel deployment | BLOCKED | GET `/` returned HTTP 404 `DEPLOYMENT_NOT_FOUND`. | A valid frontend deployment is not currently reachable at the configured URL. |
| Password reset | LIMITED PASS | Password hash update, token hashing/one-use behavior, missing SMTP handling, and email link composition have tests. | Actual SMTP delivery and native deep linking are unverified; configure SMTP or this route intentionally returns 503. |
| Community roles/membership | LIMITED PASS | Pending parish affiliation does not authorize access; role request self-approval and cross-parish messaging are denied in focused tests. | Full role approval matrix, administrator lifecycle, staging authorization matrix, and bootstrap are not exercised. |
| Community announcements/events/suggestions/prayer/groups | IMPLEMENTED LOCALLY / PARTIAL | Scoped API routes and screens exist; in-app notification preferences and verified-member recipient filtering are implemented. | Broad CRUD/role-scope integration tests, attachments, moderation lifecycle, push/email delivery, and full group UX remain outstanding. |
| Migration | LOCAL FIXTURE PASS / STAGING BLOCKED | Additive migration repeats safely in a SQLite legacy-schema fixture and downgrades without dropping legacy tables. | Actual deployed schema, staging restore, and backup/rollback are not verified. |
| M-Pesa callback processing | LIMITED PASS (mocked) | Provider STK-query result, callback amount/phone/receipt, and repeated callback behavior are unit-tested. | Daraja sandbox/production provider behavior and callback delivery were not tested. |
| Backend local smoke test | LIMITED PASS | In-memory SQLite health check returned 200; choir endpoint returned an empty list. | Production dependencies not tested. |
| Authentication, legacy administration, payments, notifications, downloads, and approved content | NOT VERIFIED END TO END | Prior focused tests plus this pass's 17 backend tests; no full account-through-admin journey. | Not performed against production/staging. |

## Feature trace

| Feature | Frontend | API | Backend | Database/Storage | Authorization | Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Scoped parish membership | Community/Profile request and Admin review screens | Connected | Request, review, and notification handlers | Additive `parish_memberships`; existing parish relation | Active membership required; reviewer scope checked; self-approval denied | Connected and tested (SQLite/API unit checks) |
| Scoped role requests | Request/review screen linked from Profile/Admin | Connected | Workflow creates assignments and audit records | `role_requests`, `role_assignments`, `community_audit_logs` | Role/scope validation; reviewer scope; no self-review | Connected and tested (focused service/API tests) |
| Announcements | Home/community listing and scoped composer | Connected | Draft/publish/scheduled routes | `community_announcements`, in-app notifications | Platform is Super Admin only; scoped audience managed by authorized role | Connected but externally blocked for scheduler/push; route tests limited |
| Events | Community listing and scoped event composer | Connected | Create/publish/list | `community_events`, in-app notifications | Scope assignment and verified member audience | Connected; focused end-to-end coverage incomplete |
| Suggestions | Anonymous submission and scoped review screen | Connected | Submit/list/review | `community_suggestions` | Members submit only in verified scope; reviewers authorized per scope | Connected; broad workflow tests pending |
| Prayer intentions | Private intention screen | Connected | Create/list/react | `prayer_intentions`, `prayer_reactions` | Private owner; parish/diocese require active membership; public content is public | Connected; focused scope tests pending |
| Parish/group messaging | Parish conversation UI | Connected | Create/list/send/report/react/delete/mute/block | Conversation/message/member/reaction tables | Active parish/group membership checked per request | Connected and cross-parish GET/POST/DELETE denial tested |
| Notification preferences | Profile settings screen | Connected | Get/update preferences and in-app notification filtering | `community_notification_preferences`, existing notification table | Authenticated user updates only own settings | Connected; external push delivery not configured/tested |
| Audit log | Admin audit screen | Connected | Scoped audit query | `community_audit_logs` | Super Admin or assigned community admin scopes | Connected; full action matrix pending |
| Music-role access to choir resources | Role request UI exists | Not wired to legacy choir-resource CRUD | Legacy choir resources and file delivery are global | No parish scope on existing resource rows | Music role does not grant legacy global resource administration | Backend/schema/storage blocked pending reviewed scope migration and private file delivery |
| Super Admin provisioning | No password/setup screen; controlled bootstrap command | CLI bootstrap | Existing verified configured account only | Global role assignment | Identity/email check; no source password | Code present; bootstrap execution blocked pending account/migration confirmation |
| Official directory/content, media attachments, moderation lifecycle | Existing screens/services, partial | Existing APIs, partial | Existing partial features | Existing tables/files | Complete end-to-end checks pending | Backend/data/licensing blocked or not verified |

## Release blockers

- No full acceptance test from account creation through daily use and administration.
- No staging comparison or production-schema compatibility check. Startup table creation is now opt-in; an additive Alembic migration is tested only against a local fixture.
- The directory model is limited to Diocese/Deanery/Parish; the required broader hierarchy and verified official data are incomplete.
- Music roles are not yet connected to parish-scoped choir-resource ownership or private file delivery; the existing choir-resource schema is global.
- No verified licensed/approved readings and saints datasets or complete liturgical-calendar edge-case tests.
- New community routes use scoped assignments and verified parish membership, but legacy admin/content/upload/moderation routes still need a route-by-route authorization audit and comprehensive enforcement tests.
- Real secure file storage, upload moderation, downloads/offline synchronization, payment callbacks, and push notifications are unverified.
- Production environment variables, secrets handling, external service configuration, and deployment workflows have not been validated.

## External configuration and data still required

- Approved/licensed lectionary and saint data, including source and translation rights.
- Verified Catholic jurisdiction/deanery/parish directory data and an authorized maintainer.
- Production database and reviewed schema migration.
- Daraja production credentials and business activation, if paid services are enabled.
- Push-notification credentials and supported-device testing, if push delivery is enabled.
- Storage, email, and other provider credentials required by the configured deployment.

### Environment variable inventory

| Purpose | Variables | Status |
| :--- | :--- | :--- |
| Core backend | `DATABASE_URL`, `SECRET_KEY` | Required by application settings. Supply production values through the hosting secret manager. |
| Auth/token policy | `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `BOOTSTRAP_SUPER_ADMIN_EMAIL` | Defaults exist; explicitly review production policy and bootstrap identity. |
| Schema/scheduled work | `AUTO_CREATE_TABLES`, `SCHEDULED_JOB_TOKEN` | `AUTO_CREATE_TABLES` defaults off. Scheduled announcement publishing returns 503 unless a strong job token is configured; no scheduler is configured or tested. |
| Web/CORS | `FRONTEND_URL`, `ALLOWED_ORIGINS`, `BASE_URL`, `DEBUG` | Configure for the deployed frontend/API; never enable debug in production. |
| SMTP password-reset mail | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM` | Not configured in the checked environment; reset mail returns HTTP 503. Delivery not tested. |
| M-Pesa Daraja | `MPESA_ENVIRONMENT`, `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_PASSKEY`, `MPESA_SHORTCODE`, `MPESA_CALLBACK_URL`, `MPESA_ACCOUNT_REFERENCE`, `MPESA_TRANSACTION_DESCRIPTION`, `MPESA_TRANSACTION_TYPE`, `MPESA_MONTHLY_AMOUNT`, `MPESA_RECIPIENT_NUMBER` | Configure only after approved sandbox/live setup; current provider test uses mocked responses. |
| Push notification provider | `FIREBASE_PROJECT_ID`, `FIREBASE_PRIVATE_KEY`, `FIREBASE_CLIENT_EMAIL` | Credential fields are present in the checked environment, but push delivery code/device delivery was not verified. |
| File storage | `STORAGE_PATH`, `MAX_IMAGE_SIZE`, `MAX_AUDIO_SIZE`, `MAX_VIDEO_SIZE`, `MAX_DOCUMENT_SIZE`, `ALLOWED_IMAGE_TYPES`, `ALLOWED_DOCUMENT_TYPES`, `ALLOWED_AUDIO_TYPES`, `ALLOWED_VIDEO_TYPES` | Configured local storage directory does not exist; existing media/uploads behavior is not verified for persistent hosted storage. |

Configure secrets in the deployment secret manager; never copy credential values into logs or source files. Rotate any credentials that may have been exposed in prior logs, terminals, commits, or deployment configuration.

Do not treat sandbox responses, local SQLite checks, static exports, or unverified datasets as evidence of production readiness.

## Required release sequence

1. Inventory deployed secrets without printing values; rotate any credentials that were exposed, then install current credentials in the deployment secret manager.
2. Obtain a production-schema snapshot and backup, restore it into staging, and document a rollback procedure.
3. Establish an Alembic baseline that matches staging exactly; review additive migrations and test both upgrade and rollback on a restored staging copy before production.
4. Complete the authorization matrix across parish, deanery, diocese, moderator, and platform roles; new community role requests exist, but legacy administration and choir-resource permissions remain to be integrated.
5. Load and verify directory and liturgical content only from authorized ecclesial sources; record provenance and licensing before publishing.
6. Configure SMTP, storage, and push credentials as applicable; verify delivery and restricted-file access with test accounts on staging.
7. Run Daraja sandbox initiation, success/cancel/failure/duplicate callback and reconciliation tests; obtain Safaricom production approval and credentials before live transactions.
8. Run user, music-director, parish-admin, moderator, diocesan-admin, and super-admin end-to-end journeys on staging, then deploy and verify health/readiness and rollback.
