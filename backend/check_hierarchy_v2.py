"""Check hierarchy data completeness via the running API."""
import json, urllib.request, urllib.error, base64
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

# Login to get admin token for summary endpoint
login_req = urllib.request.Request(BASE + '/api/auth/login',
    data=json.dumps({'email': 'parmenasoduol1318@gmail.com', 'password': 'oduol@1318'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST')
with urllib.request.urlopen(login_req) as r:
    token = json.loads(r.read().decode())['access_token']

# Summary
print('=== SUMMARY (admin) ===')
status, data = get('/api/v1/hierarchy/summary', token=token)
print(f'Status: {status}')
if status == 200:
    for k, v in data.items():
        print(f'  {k}: {v}')

# Get all dioceses (without province_id to list all)
print()
print('=== ALL DIOCESES ===')
status, data = get('/api/v1/hierarchy/dioceses', {'include_ordinariate': True})
all_diocese = {}
for d in data.get('results', []):
    all_diocese[d['id']] = d
    print(f'  id={d["id"]:2d} code={d["code"]:12s} | {d["name"]:40s} | is_arch={d["is_archdiocese"]} | is_mil={d["is_military_ordinariate"]} | deaneries={d["deanery_count"]}')

# Check each diocese for deaneries
print()
print('=== DIOCESES WITH NO DEANERIES ===')
no_deanery = []
for d in data.get('results', []):
    if d['is_military_ordinariate']:
        continue
    # Actually query deaneries for this diocese
    status2, deanery_data = get('/api/v1/hierarchy/deaneries', {'diocese_id': d['id']})
    if status2 == 200:
        count = deanery_data.get('total', 0)
    else:
        count = '?'
    if count == 0:
        no_deanery.append(d)
        print(f'  id={d["id"]} {d["name"]} (code={d["code"]})')
print(f'Total: {len(no_deanery)} dioceses without deaneries')

# Check each deanery for parishes
print()
print('=== DEANERIES WITH NO PARISHES ===')
no_parish = []
total_deaneries = 0
for d in all_diocese.values():
    if d['is_military_ordinariate']:
        continue
    status2, deanery_data = get('/api/v1/hierarchy/deaneries', {'diocese_id': d['id']})
    if status2 != 200:
        continue
    for dean in deanery_data.get('results', []):
        total_deaneries += 1
        status3, parish_data = get('/api/v1/hierarchy/parishes', {'deanery_id': dean['id']})
        if status3 == 200:
            count = parish_data.get('total', 0)
        else:
            count = '?'
        if count == 0:
            no_parish.append((dean, count))
            print(f'  deanery_id={dean["id"]} code={dean["code"]:30s} | {dean["name"]:35s} | diocese_id={dean["deanery_id"] if "deanery_id" in dean else d["id"]} | parishes={count}')

print(f'Total: {len(no_parish)} deaneries without parishes (out of {total_deaneries} total)')

# Check what data is available in ke_hierarchy.py
print()
print('=== ke_hierarchy.py DATA AVAILABILITY ===')
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app.data.ke_hierarchy import ALL_DIOCESES, DEANERIES, DIOCESES, MILITARY_ORDINARIATE

deanery_diocese_codes = set()
for d in DEANERIES:
    deanery_diocese_codes.add(d['diocese_code'])

print(f'DEADERY definitions: {len(DEANERIES)} deaneries across {len(deanery_diocese_codes)} dioceses')
for code in sorted(deanery_diocese_codes):
    dio = next((d for d in ALL_DIOCESES if d['code'] == code), None)
    print(f'  {code} -> {dio["name"] if dio else "???"}')

print()
print(f'Diocese codes in ke_hierarchy.py that are NOT in the DEANERIES list:')
all_diocese_codes = {d['code'] for d in ALL_DIOCESES}
covered = deanery_diocese_codes
uncovered = all_diocese_codes - covered
for code in sorted(uncovered):
    dio = next((d for d in ALL_DIOCESES if d['code'] == code), None)
    print(f'  {code} -> {dio["name"] if dio else "???"}')

print()
print(f'PARISH data in ke_hierarchy.py: only for Archdiocese of Nairobi')
print(f'(ke_hierarchy.py docstring states: "Only the Archdiocese of Nairobi publishes a complete deanery -> parish listing on its official site")')
