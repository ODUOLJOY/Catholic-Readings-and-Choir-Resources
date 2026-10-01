# Implementation Status - Catholic Readings & Choir Resources App

## Baseline Audit (Phase 1)
- **Date:** 2026-09-30

### 1. Duplicates & Obsolete Code
- [ ] Identify redundant database columns in `Parish` model.
- [ ] Identify duplicate authentication routes (if any remain).
- [ ] Check for unused services.

### 2. Placeholders & Mocks
- [ ] Remove hardcoded demonstration data in Home, Choir, and Readings screens.
- [ ] Ensure all API calls are connected to real backend endpoints.

### 3. API & Contracts
- [ ] Verify frontend API calls against FastAPI endpoints.

### 4. Database & Migrations
- [ ] Audit hierarchy model (`Diocese`, `Deanery`, `Parish`) for consistency.
- [ ] Prepare safe migration for hierarchy normalization.

## Current Phase: Phase 1 (Baseline & Audit)
Status: In Progress
