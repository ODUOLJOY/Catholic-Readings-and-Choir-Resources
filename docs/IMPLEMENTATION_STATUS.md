# Implementation Status - Catholic Readings & Choir Resources App

## Baseline Audit (Phase 1)
- **Date:** 2026-09-30

### 1. Duplicates & Obsolete Code
- [✓] Identify redundant database columns in `Parish` model. (Identified: string-based `diocese`, `archdiocese`)
- [ ] Identify duplicate authentication routes (if any remain).
- [ ] Check for unused services.

### 2. Placeholders & Mocks
- [ ] Remove hardcoded demonstration data in Home, Choir, and Readings screens.
- [ ] Ensure all API calls are connected to real backend endpoints.

### 3. API & Contracts
- [✓] Verify frontend API calls against FastAPI endpoints.

### 4. Database & Migrations
- [✓] Audit hierarchy model (`Diocese`, `Deanery`, `Parish`) for consistency.
- [✓] Prepare safe migration for hierarchy normalization. (Removed redundant string columns from `Parish` model)

### 5. Profile Location System
- [✓] Validate Parish location update endpoint in backend.

## Current Phase: Phase 4 (Kenya Catholic Directory Administration)
Status: In Progress
