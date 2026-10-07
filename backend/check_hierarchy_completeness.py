"""Walk the live hierarchy API and report on data completeness.

Reports:
  1. Which dioceses have NO deaneries.
  2. Which deaneries have NO parishes.
  3. Per-diocese deanery and parish counts.

Uses the local API server (http://127.0.0.1:8000) which has a live,
working connection pool to the Supabase PostgreSQL database. The API
returns paginated envelopes with a "results" key, and the diocese and
deanery endpoints already include pre-computed counts
(deanery_count / parish_count), so one request per level suffices.
"""

import json
import urllib.request
from collections import defaultdict

BASE = "http://127.0.0.1:8000"


def get(path):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def results(envelope):
    """Return the 'results' list from a paginated envelope."""
    if isinstance(envelope, list):
        return envelope
    if isinstance(envelope, dict) and "results" in envelope:
        return envelope["results"]
    if isinstance(envelope, dict) and "items" in envelope:
        return envelope["items"]
    return [envelope]


def main():
    countries = results(get("/api/v1/hierarchy/countries"))
    print("=== COUNTRIES ===")
    for c in countries:
        print(f"  id={c['id']} code={c.get('code')} name={c.get('name')}")

    ke = next((c for c in countries if c.get("code") == "KE"), None)
    if ke is None:
        print("ERROR: Kenya not found.")
        return

    provinces = results(get(f"/api/v1/hierarchy/provinces?country_id={ke['id']}&limit=200"))
    print(f"\n=== PROVINCES (Kenya: {len(provinces)}) ===")
    for p in provinces:
        print(f"  id={p['id']} code={p.get('code')} name={p.get('name')}")

    # Fetch ALL dioceses (every jurisdiction, geographic + military) in one call.
    all_dioceses = results(get("/api/v1/hierarchy/dioceses?include_ordinariate=true&limit=200"))

    total_dioceses = 0
    dioceses_no_deaneries = []
    all_deaneries = []  # list of deanery dicts

    print(f"\n=== DIOCESES ({len(all_dioceses)} total jurisdictions) ===")
    for d in all_dioceses:
        total_dioceses += 1
        did = d["id"]
        dname = d.get("name")
        is_mil = d.get("is_military_ordinariate", False)
        nd = d.get("deanery_count", 0)

        marker = " [MILITARY]" if is_mil else ""
        print(f"  {dname} (id={did}, code={d.get('code')}, arch={d.get('is_archdiocese')}) "
              f"-> {nd} deaneries{marker}")

        # Only fetch deaneries if the diocese has any.
        if nd > 0 and not is_mil:
            deaneries = results(get(f"/api/v1/hierarchy/deaneries?diocese_id={did}&limit=200"))
            total_parishes = 0
            deanery_names = []
            for de in deaneries:
                all_deaneries.append((de, dname, did))
                npc = de.get("parish_count", 0)
                total_parishes += npc
                deanery_names.append(f"{de.get('name')} (parishes={npc})")
                if npc == 0:
                    dioceses_no_deaneries.append((d, de, npc))
            print(f"      Deaneries: {deanery_names}")
            print(f"    => {len(deaneries)} deaneries, {total_parishes} total parishes")
        elif nd == 0 and not is_mil:
            dioceses_no_deaneries.append((d, None, 0))

    # ---- Analysis ----
    print("\n" + "=" * 70)
    print("=== COMPLETENESS ANALYSIS ===")

    # 1. Dioceses with no deaneries
    no_dean_diocese_set = {}
    for d, de, npc in [(item[0], item[1], item[2]) for item in dioceses_no_deaneries]:
        pass
    # Recompute cleanly: dioceses with deanery_count == 0 (excluding military)
    dioceses_no_deaneries_only = [
        d for d in all_dioceses if d.get("deanery_count", 0) == 0 and not d.get("is_military_ordinariate", False)
    ]
    print(f"\n1. DIOCESES WITH NO DEANERIES ({len(dioceses_no_deaneries_only)} of {total_dioceses}):")
    for d in dioceses_no_deaneries_only:
        print(f"   - {d.get('name')} (id={d['id']}, code={d.get('code')}) "
              f"verification={d.get('verification_status')} website={d.get('website')}")

    # 2. Deaneries with no parishes
    deaneries_no_parishes = []
    for de, dname, did in all_deaneries:
        if de.get("parish_count", 0) == 0:
            deaneries_no_parishes.append((de, dname, did))
    print(f"\n2. DEANERIES WITH NO PARISHES ({len(deaneries_no_parishes)} of {len(all_deaneries)}):")
    by_diocese = defaultdict(list)
    for de, dname, did in deaneries_no_parishes:
        by_diocese[(dname, did)].append(de)
    for (dname, did), deans in sorted(by_diocese.items()):
        print(f"   [{dname} id={did}] ({len(deans)} deaneries without parishes):")
        for de in deans:
            src = de.get("source_url", "N/A")
            print(f"      - {de.get('name')} (code={de.get('code')}, id={de['id']}) source={src}")

    # 3. Deaneries WITH parishes (brief)
    deaneries_with_parishes = [
        (de, dname, did) for de, dname, did in all_deaneries
        if de.get("parish_count", 0) > 0
    ]
    print(f"\n3. DEANERIES WITH PARISHES ({len(deaneries_with_parishes)} of {len(all_deaneries)}):")
    for de, dname, did in sorted(deaneries_with_parishes, key=lambda x: x[1]):
        print(f"   [{dname}] {de.get('name')} -> {de.get('parish_count')} parishes "
              f"(source={de.get('source_url')})")

    # Overall totals
    total_dean = len(all_deaneries)
    total_dean_no_par = len(deaneries_no_parishes)
    total_dean_with_par = len(deaneries_with_parishes)
    total_par = sum(de.get("parish_count", 0) for de, _, _ in all_deaneries)
    print(f"\n=== TOTALS ===")
    print(f"  Dioceses (geographic, excl military): {total_dioceses - 1}")
    print(f"  Deaneries:  {total_dean}")
    print(f"  Parishes:   {total_par}")
    print(f"  Deaneries with 0 parishes: {total_dean_no_par} ({total_dean_no_par/total_dean*100:.0f}%)")
    print(f"  Deaneries with >0 parishes: {total_dean_with_par} ({total_dean_with_par/total_dean*100:.0f}%)")


if __name__ == "__main__":
    main()
