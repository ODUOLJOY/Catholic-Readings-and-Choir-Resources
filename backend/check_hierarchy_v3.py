"""Check hierarchy data completeness via the running API."""
import json, urllib.request, urllib.error, sys
from urllib.parse import urlencode

BASE = 'http://127.0.0.1:8000'

def get(path, params=None, token=None):
    url = BASE + path
    if params:
        url = url + '?' + urlencode(params)
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

out = open('hierarchy_report.txt', 'w', encoding='utf-8')

def log(msg=''):
    print(msg)
    out.write(msg + '\n')

# Login
login_req = urllib.request.Request(BASE + '/api/auth/login',
    data=json.dumps({'email': 'parmenasoduol1318@gmail.com', 'password': 'oduol@1318'}).encode(),
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(login_req) as r:
    token = json.loads(r.read().decode())['access_token']
log('Logged in as super admin.')
log()

# Summary
log('=== SUMMARY (admin) ===')
status, data = get('/api/v1/hierarchy/summary', token=token)
log(f'Status: {status}')
if status == 200:
    for k, v in data.items():
        log(f'  {k}: {v}')
log()

# Get all dioceses
log('=== ALL DIOCESES ===')
status, data = get('/api/v1/hierarchy/dioceses', {'include_ordinariate': True})
all_diocese = {}
for d in data.get('results', []):
    all_diocese[d['id']] = d
    mil = ' [MILITARY]' if d['is_military_ordinariate'] else ''
    log("  id=%2d code=%-12s | %-40s | arch=%s | mil=%s | deaneries=%d%s" % (d['id'], d['code'], d['name'], d['is_archdiocese'], d['is_military_ordinariate'], d['deanery_count'], mil))
log()

# Check each diocese for actual deaneries
log('=== DIOCESES WITH NO DEANERIES (actual query) ===')
no_deanery = []
for did, d in sorted(all_diocese.items()):
    if d['is_military_ordinariate']:
        continue
    status2, deanery_data = get('/api/v1/hierarchy/deaneries', {'diocese_id': did})
    actual_count = deanery_data.get('total', 0) if status2 == 200 else '?'
    if actual_count == 0:
        no_deanery.append(d)
        log(f"  id={d['id']} {d['name']} (code={d['code']})")
log(f'Total: {len(no_deanery)} dioceses without deaneries')
log()

# Check each deanery for parishes
log('=== DEANERIES WITH NO PARISHES ===')
no_parish = []
total_dean = 0
for did in sorted(all_diocese.keys()):
    d = all_diocese[did]
    if d['is_military_ordinariate']:
        continue
    status2, deanery_data = get('/api/v1/hierarchy/deaneries', {'diocese_id': did})
    if status2 != 200:
        continue
    for dean in deanery_data.get('results', []):
        total_dean += 1
        status3, parish_data = get('/api/v1/hierarchy/parishes', {'deanery_id': dean['id']})
        count = parish_data.get('total', 0) if status3 == 200 else '?'
        if count == 0:
            no_parish.append(dean)
            log("  deanery_id=%d code=%-30s | %-35s | parishes=%s" % (dean['id'], dean['code'], dean['name'], count))
log(f'Total: {len(no_parish)} deaneries without parishes (out of {total_dean} total)')
log()

# ke_hierarchy.py data
sys.path.insert(0, '.')
from app.data.ke_hierarchy import ALL_DIOCESES, DEANERIES

deanery_diocese_codes = set()
for d in DEANERIES:
    deanery_diocese_codes.add(d['diocese_code'])

log('=== ke_hierarchy.py DATA AVAILABILITY ===')
log(f'DEADERY definitions: {len(DEANERIES)} deaneries across {len(deanery_diocese_codes)} dioceses')
for code in sorted(deanery_diocese_codes):
    dio = next((d for d in ALL_DIOCESES if d['code'] == code), None)
    log(f'  {code} -> {dio["name"] if dio else "???"},' if dio else f'  {code} -> ???')
log()

all_diocese_codes = {d['code'] for d in ALL_DIOCESES}
uncovered = sorted(all_diocese_codes - deanery_diocese_codes)
log(f'Diocese codes in ke_hierarchy.py NOT covered by DEANERIES list ({len(uncovered)}):')
for code in uncovered:
    dio = next((d for d in ALL_DIOCESES if d['code'] == code), None)
    if dio:
        log(f"  {code} -> {dio['name']}")
    else:
        log(f'  {code} -> ???')
log()

# Parish data availability
log('=== PARISH DATA AVAILABILITY ===')
log('ke_hierarchy.py PARISH_ROWS: parish names only for Archdiocese of Nairobi (17 deaneries, 127 parishes)')
log('Source: https://archdioceseofnairobi.org/official deanery/parish listing')
log()

# Sources
log('=== AVAILABLE DATA SOURCES ===')
log('1. ke_hierarchy.py DEANERY_ROWS - deanery names + source URLs for:')
log('   - Archdiocese of Nairobi (17 deaneries)')
log('   - Diocese of Ngong (7 deaneries)')
log('   - Diocese of Kitui (6 deaneries)')
log('   - Archdiocese of Nyeri (8 deaneries)')
log('   - Diocese of Meru (8 deaneries)')
log("   - Diocese of Murang'a (8 deaneries)")
log('   - Archdiocese of Mombasa (12 deaneries)')
log('   - Diocese of Kitale (7 deaneries)')
log(f'   Total: {len(DEANERIES)} deaneries')
log()
log('2. ke_hierarchy.py PARISH_ROWS - parish names only for Archdiocese of Nairobi')
log('   (from https://archdioceseofnairobi.org)')
log()
log('3. KCCB official registry: https://kccb.or.ke/dioceses/')
log('   Source for ALL dioceses/provinces. Could be scraped for deanery/parish data.')
log()
log('4. Individual diocesan websites (URLs in ke_hierarchy.py DEANERY_ROWS)')

out.close()
