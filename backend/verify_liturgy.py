
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.models import choir, content, download, favorite, liturgical, notification, parish, payment, readings, report, saint, user
from app.services.liturgical_sync import LiturgicalSyncService
from app.services.missal_engine import MissalEngine

def test_liturgy_flow():
    # 1. Use local SQLite for testing
    test_engine = create_engine("sqlite:///:memory:")
    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    db = TestSessionLocal()
    
    # 2. Test Data
    test_data = {
        "date": date(2026, 9, 30),
        "celebration": "Memorial of Saint Jerome, Priest and Doctor of the Church",
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
    
    # 3. Import
    LiturgicalSyncService.import_verified_data(db, test_data)
    
    # 4. Verify Retrieval
    engine = MissalEngine(db)
    result = engine.get_readings(date(2026, 9, 30))
    
    assert result['calendar']['celebration'] == test_data["celebration"]
    assert len(result['calendar']['available_reading_sets']) == 2
    
    # Check Reading Set Data
    types = [rs['type'] for rs in result['calendar']['available_reading_sets']]
    assert "daily" in types
    assert "proper" in types
    
    # 5. Check selection logic
    assert result['calendar']['selected_reading_set']['type'] == "daily"
    assert result['calendar']['selected_reading_set']['lectionary_number'] == "457"
    
    print("Test Passed!")

if __name__ == "__main__":
    test_liturgy_flow()
