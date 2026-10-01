# Frontend Reality Audit

## Verification scope

Reviewed the Expo Router frontend and exercised the local web build against a local backend. This is a focused code and smoke-test audit, not a full end-to-end or production certification.

## Screen and navigation status

| Area | Status | Verified facts | Remaining work |
| :--- | :--- | :--- | :--- |
| Primary navigation | VERIFIED (LOCAL WEB) | Static-export browser displayed exactly Home, Admin, Profile, Payments, Readings, and Downloads. | Verify on supported native devices and a working deployment. |
| Home | PARTIAL | Uses the existing liturgy API and links to the community hub, readings, choir, and downloads. | Verify approved content, cache freshness, empty/error states, and parish-specific content. |
| Readings and calendar | PARTIAL | Screens call existing backend APIs; TypeScript and web export pass. | Verify lectionary source/licensing, calendar edge cases, local calendars, and offline behavior. |
| Saints | PARTIAL | List/detail screens exist. | Verify published data, provenance, administration, and complete user flows. |
| Choir | PARTIAL / LOCAL API TESTED | Public resource detail hides unapproved records; newly uploaded parish resources are filtered by membership/role and served through an authenticated API file route. | Legacy rows remain global; browser session with live API, native behavior, and hosted persistent storage remain unverified. |
| Search | PARTIAL | Existing Explore screen searches readings. | Add and verify discovery across supported content types and result navigation. |
| Downloads/offline | PARTIAL | File caching now authenticates the resource lookup/download and derives the extension from the resource metadata, including scoped API file routes. | Device filesystem behavior, large transfer recovery/progress, synchronization, and offline opening remain unverified. |
| Profile and parish setup | PARTIAL | Shows community membership status, parish hierarchy, approved scoped roles, and links to role/community/notification screens. | Verify persistent account flows; add the broader country/jurisdiction model and change-parish workflow. |
| Community | PARTIAL | Community hub, membership requests, scoped role requests, announcements, events, suggestions, private prayer intentions, and parish chat call the backend APIs. | Verify complete journeys, attachments, push, moderation, group UX, and error recovery. |
| Admin | PARTIAL / LOCAL API TESTED | Multipart upload now sends a browser-readable Blob or native URI file, preserves multipart boundary generation, and displays parish scopes; scoped resource approval/edit/reject routes pass TestClient coverage. | Native picker interaction, live browser-backend upload, remaining legacy route authorization, and hosted storage remain unverified. |

## Local checks

- `npx tsc --noEmit`: passed.
- `npx expo export --platform web`: passed; 70 routes exported.
- `npm run lint`: passed with 0 errors and 52 warnings.
- Local backend API tests exercise upload multipart fields, pending/approved states, role-scoped moderation, protected parish files, and cross-parish download-history denial; browser/native picker and device file transfer remain unverified.
- Local static-export browser smoke test: exactly six visible primary tabs and no reproduced Choir text-node warning. The static page's API request is unauthenticated and returned 403.

These checks do not establish production behavior, native-device compatibility, or completion of the listed features.

## Priority follow-up

1. Verify real account/session flows and backend-enforced role/scope restrictions on staging.
2. Implement and validate the country and Catholic jurisdiction hierarchy using verified directory data.
3. Verify licensed, approved readings and saints datasets, including calendar edge cases.
4. Test secure uploads/moderation and real downloads/offline behavior.
5. Complete cross-category search and end-to-end coverage for profile, admin, and content journeys.
