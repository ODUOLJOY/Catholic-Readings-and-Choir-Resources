# Implementation Plan: Kenya Hierarchy — All Missing Dioceses & Parishes

## Overview

**Status: Kapsabet (39 parishes) and Ngong (15 parishes) already integrated.**
This plan targets the remaining **15 dioceses** that still lack verified parish
data. The database currently holds **341 parishes** across **57 deaneries** in
7 dioceses. The goal is to push as high as possible using only verified data
(Priority 1–5 sources), with no fabrication.

## Current State (post Kapsabet + Ngong integration)

### A. Deaneries with names but 0 parishes (need parish extraction)
| Diocese | Code | Deaneries | Parish Claim | Challenge |
|---------|------|-----------|--------------|-----------|
| Meru | KE-NRY-MER | 8 | Unknown | WordPress, `/parish/` link JS-rendered |
| Murang'a | KE-NRY-MRG | 8 | 56 | Elementor, 7 deanery sub-pages discoverable |
| Kitale | KE-KSM-KTL | 7 | 35 | Elementor, deanery names in text only |
| Mombasa | KE-MBA-MBA | 12 | Unknown | 16KB page, `/parishes/` redirects infinitely |

### B. Dioceses with no deaneries (need fresh scraping)
| Diocese | Code | HTML Avail. | Notes |
|---------|------|-------------|-------|
| Marsabit | KE-NRY-MSB | 188KB | WordPress, `/our-parishes/` link found |
| Isiolo | KE-NRY-ISL | 77KB | WordPress, `/parishes/` link found |
| Bungoma | KE-KSM-BUN | 21KB | Check if KCCB redirect |
| Kisii | KE-KSM-KSI | 21KB | No official site in DIOCESES |
| Kericho | KE-NRB-KRC | 20KB | No official site in DIOCESES |
| Machakos | KE-NRB-MKS | 22KB | No official site in DIOCESES |
| Nakuru | KE-NRB-NKR | 23KB | No official site in DIOCESES |
| Kisumu | KE-KSM-KSM | 30KB | DNS fails; HTML from catholic-hierarchy.org |
| Eldoret | KE-KSM-ELD | 28KB | DNS fails for all domain variants |
| Embun | KE-NRY-EMB | 2.6KB | Too small |
| Homa Bay | KE-KSM-HBY | 3KB | Too small |
| Nyahururu | KE-NRY-NYH | 124KB | Lorem Ipsum dummy text |
| Garissa | KE-MBA-GRS | — | No HTML |
| Kakamega | KE-KSM-KAK | 20KB | Redirects to gambling site |
| Malindi | KE-MBA-MLD | 8KB | Account Suspended page |
| Maralal | KE-NRY-MRL | — | Redirects to gambling site |

## Implementation Approach

### Phase 1: Extract from existing HTML (Meru, Murang'a, Kitale, Mombasa)

All four have deaneries already in `DEANERY_ROWS` — only parish data is missing.

**1a. Murang'a** — highest confidence:
- 7 deanery sub-page URLs discovered:
  `catholicdioceseofmuranga.org/index.php/{baricho|gatanga|gaichanjiru|kianyaga|maragua|mwea|tuthu}/`
  (the "Murang'a" Deanery itself has no separate sub-page URL — look for parishes
  in the main page text instead)
- Fetch each sub-page with `urllib` + browser User-Agent. Parse with
  BeautifulSoup to extract parish names from headings, paragraphs, or list items.
- Expected: up to 56 parish names across 8 deaneries.

**1b. Meru:**
- Has `/deaneries/` and `/parish/` page links.
- Fetch `/deaneries/` page; if it lists deanery sub-pages, follow them.
- Expected: variable — may be 0 if JS-rendered.

**1c. Kitale:**
- 7 "deanery" mentions found in 105KB HTML text. Look for deanery sub-page URLs
  in `<script>` data or nav menus. Try WordPress REST API:
  `catholickitale.org/wp-json/wp/v2/`
- Expected: variable — may be 0 if JS-rendered.

**1d. Mombasa:**
- `/parishes/` → infinite redirect. Try `/index.php/deaneries/{name}/` pattern.
- Expected: likely 0 — keep as pending.

**Decision rule**: If parish names are extracted and can be mapped to a deanery,
add them to `PARISH_ROWS` with 4-tuple format and remove the diocese from
`DIOCESES_WITH_DEANERIES_BUT_PENDING_PARISHES`. If not, keep the diocese in
the pending list.

### Phase 2: Fresh scrape 12 sites with HTML or reachable domains

Target the dioceses with HTML snapshots that haven't been fully parsed:

```python
# Reuse the same fetch pattern from the existing scripts:
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."}
req = urllib.request.Request(url, headers=headers)
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="replace")
```

**2a. Marsabit** (`marsabitdiocese.org`):
- Has `/our-parishes/` link. Fetch it directly.
- If deaneries aren't known, attempt to discover them from parish location names.

**2b. Isiolo** (`cdisiolo.org`):
- Has `/parishes/` link. Fetch it directly.

**2c–2l. Remaining 10 dioceses** (Bungoma, Kisii, Kericho, Machakos, Nakuru,
Kisumu, Eldoret, Homa Bay, Embu, Nyahururu):
- Try KCCB directory URLs, then official websites from the `DIOCESES` table.
- If DNS fails or site is unreachable, skip and keep in
  `DIOCESES_WITHOUT_OFFICIAL_DEANERY_DATA`.

### Phase 3: Update `ke_hierarchy.py`

For each diocese that yields verified parish names:

1. **Add parish tuples** to `PARISH_ROWS` (4-tuple format):
   ```python
   ("Deanery Name", "Parish Name", None, "KE-XXX-YYY"),
   ```
   Deanery names must exactly match `DEANERY_ROWS` for `_DEANERY_BY_DIOCESE`
   resolution.

2. **Add new deaneries** (if any) to `DEANERY_ROWS` before `PARISH_ROWS` entries
   reference them:
   ```python
   ("KE-NRY-MSB", "Marsabit Deanery", "https://marsabitdiocese.org", VERIFIED),
   ```

3. **Update status lists**:
   - Remove successfully-scraped dioceses from
     `DIOCESES_WITH_DEANERIES_BUT_PENDING_PARISHES`
   - Remove newly-verified dioceses from
     `DIOCESES_WITHOUT_OFFICIAL_DEANERY_DATA` (update the dict with a note)

4. **Update docstring** totals in the `PARISHES` comment block.

5. **Deanery name collisions**: 4-tuple `dioese_code` disambiguator handles this
   automatically via `_DEANERY_BY_DIOCESE`.

### Phase 4: Seed DB, verify, regenerate reports

1. **Seed** — run `seed_kenya_catholic_directory.py` 3× (idempotency check):
   - Run 1: N added, M updated, 0 skipped
   - Run 2+3: 0 added, all updated, 0 skipped

2. **Tests** — run:
   ```
   .venv\Scripts\python -m pytest test_ecclesiastical_hierarchy.py test_hierarchy_registration.py -v
   ```
   All 58 tests must pass.

3. **Completeness check** — run `check_hierarchy_completeness.py` against the
   live API to confirm new counts.

4. **Regenerate reports** — update
   `kenya_hierarchy_completeness_2026.json` and `.md`.

## Constraints

- **No fabricated data**: Deanery-parish mappings must be explicit in source HTML.
- **Python 3.11.5** via `backend/.venv/Scripts/python.exe`
- **`requests` NOT available** — use `urllib.request` with browser User-Agent
- **`bs4` + `lxml` available** in venv
- **Deanery collisions** handled via 4-tuple format + `_DEANERY_BY_DIOCESE`
- **Idempotent seeding** required
- **All 58 tests must pass**

## Success Criteria

1. Deaneries with 0 parishes reduced from 35 → as low as possible
2. No orphan deanery codes in `build_parishes()`
3. No duplicate parish names within the same deanery
4. All 58 tests pass
5. Seed idempotent (0 added on 2nd+ run)
6. Reports regenerated with updated counts
