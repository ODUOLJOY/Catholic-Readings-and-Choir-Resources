import warnings; warnings.filterwarnings('ignore')
from app.db.database import SessionLocal
from app.models.locations import Country, EcclesiasticalProvince, Diocese, Deanery
from app.models.parish import Parish
from sqlalchemy import func

db = SessionLocal()

print('=== DIOCESES WITH DEANERY/PARISH COUNTS ===')
stmt = db.query(
    Diocese.id, Diocese.code, Diocese.name,
    func.count(Deanery.id).label('deanery_count'),
).outerjoin(Deanery, Deanery.diocese_id == Diocese.id
).group_by(Diocese.id, Diocese.code, Diocese.name
).order_by(Diocese.id)
counts = stmt.all()

no_deanery = []
for row in counts:
    dno = row.deanery_count or 0
    print(f'  id={row.id:2d} {row.code:12s} | {row.name:40s} | deaneries={dno}')
    if dno == 0 and not row.name.startswith('Military'):
        no_deanery.append(row)

print()
print('=== DIOCESES WITH NO DEANERIES ===')
for row in no_deanery:
    print(f'  {row.name} (code={row.code})')
print(f'Total: {len(no_deanery)} dioceses without deaneries')

print()
print('=== DEANERIES WITH PARISH COUNTS ===')
stmt2 = db.query(
    Deanery.id, Deanery.code, Deanery.name, Deanery.diocese_id,
    func.count(Parish.id).label('parish_count'),
).outerjoin(Parish, Parish.deanery_id == Deanery.id
).group_by(Deanery.id, Deanery.code, Deanery.name, Deanery.diocese_id
).order_by(Deanery.diocese_id, Deanery.id)
dc = stmt2.all()

no_parish = []
for row in dc:
    pno = row.parish_count or 0
    print(f'  id={row.id:3d} code={row.code:30s} | {row.name:35s} | dio={row.diocese_id:2d} | parishes={pno}')
    if pno == 0:
        no_parish.append(row)

print()
print('=== DEANERIES WITH NO PARISHES ===')
for row in no_parish:
    print(f'  {row.name} (code={row.code}, diocese_id={row.diocese_id})')
print(f'Total: {len(no_parish)} deaneries without parishes')

print()
print('=== TOTALS ===')
print(f'  Countries={db.query(Country).count()} Provinces={db.query(EcclesiasticalProvince).count()} Dioceses={db.query(Diocese).count()} Deaneries={db.query(Deanery).count()} Parishes={db.query(Parish).count()}')

# Also check the ke_hierarchy.py data to see what deanery/parish data is available
print()
print('=== ke_hierarchy.py AVAILABLE DATA ===')
from app.data.ke_hierarchy import ALL_DIOCESES, DEANERIES, DIOCESES
deanery_diocese_codes = set()
for d in DEANERIES:
    deanery_diocese_codes.add(d['diocese_code'])
print(f'DEANERIES list covers {len(DEANERIES)} deaneries across {len(deanery_diocese_codes)} dioceses:')
for code in sorted(deanery_diocese_codes):
    dio = next((d for d in ALL_DIOCESES if d['code'] == code), None)
    print(f'  {code} -> {dio["name"] if dio else "???"}')

# Parishes - check what parish rows exist in the data
print()
print(f'PARISH_ROWS in ke_hierarchy.py: data only for Archdiocese of Nairobi')
print(f'(ke_hierarchy.py docstring: "Only the Archdiocese of Nairobi publishes a complete deanery -> parish listing")')

db.close()
