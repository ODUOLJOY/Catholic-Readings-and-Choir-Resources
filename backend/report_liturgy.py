from app.db.database import SessionLocal
from app.models.liturgical import LiturgicalDay, ReadingSet

db = SessionLocal()

total_days = db.query(LiturgicalDay).count()
total_reading_sets = db.query(ReadingSet).count()
strictly_proper = db.query(ReadingSet).filter(ReadingSet.selection_status == "strictly_proper").count()
suggested = db.query(ReadingSet).filter(ReadingSet.selection_status == "suggested").count()
weekday_default = db.query(ReadingSet).filter(ReadingSet.selection_status == "weekday_default").count()
common_option = db.query(ReadingSet).filter(ReadingSet.selection_status == "common_option").count()
alternative = db.query(ReadingSet).filter(ReadingSet.selection_status == "alternative").count()

print(f"Total calendar days: {total_days}")
print(f"Total ReadingSets: {total_reading_sets}")
print(f"Strictly Proper: {strictly_proper}")
print(f"Suggested: {suggested}")
print(f"Weekday Default: {weekday_default}")
print(f"Common Option: {common_option}")
print(f"Alternative: {alternative}")
db.close()
