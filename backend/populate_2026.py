from datetime import date
from sqlalchemy.orm import sessionmaker
from app.database import init_db
from app.db.database import engine
from app.services.liturgical_sync import LiturgicalSyncService

init_db()
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

test_data_2026 = [
    {
        "date": date(2026, 1, 6),
        "celebration": "The Epiphany of the Lord",
        "rank": "solemnity",
        "liturgical_color": "white",
        "liturgical_year": "A",
        "season": "Christmas Time",
        "source": "USCCB",
        "reading_sets": [
            {
                "type": "proper",
                "selection_status": "strictly_proper",
                "lectionary_number": "20",
                "first_reading": "Isaiah 60:1-6",
                "psalm": "Psalm 72:1-2, 7-8, 10-11, 12-13",
                "second_reading": "Ephesians 3:2-3a, 5-6",
                "gospel": "Matthew 2:1-12"
            }
        ]
    },
    {
        "date": date(2026, 9, 30),
        "celebration": "Saint Jerome",
        "rank": "memorial",
        "liturgical_color": "white",
        "liturgical_year": "A",
        "season": "Ordinary Time",
        "source": "USCCB",
        "reading_sets": [
            {
                "type": "daily",
                "selection_status": "weekday_default",
                "lectionary_number": "457",
                "first_reading": "Job 9:1-12, 14-16",
                "psalm": "Psalm 88:10bc-11, 12-13, 14-15",
                "gospel": "Luke 9:57-62"
            },
            {
                "type": "proper",
                "selection_status": "suggested",
                "lectionary_number": "648",
                "first_reading": "2 Timothy 3:14-17",
                "psalm": "Psalm 119:9-14",
                "gospel": "Matthew 13:47-52"
            }
        ]
    }
]

for data in test_data_2026:
    LiturgicalSyncService.import_verified_data(db, data)
    print(f"Imported {data['date']}")

db.commit()
db.close()
print("2026 Data Import Complete")
