import sys
import os
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.locations import Diocese, Deanery
from app.models.parish import Parish

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def verify():
    db = SessionLocal()
    
    jurisdictions = db.query(Diocese).all()
    print(f"Total jurisdictions: {len(jurisdictions)}")
    
    deaneries = db.query(Deanery).all()
    print(f"Total deaneries: {len(deaneries)}")
    
    parishes = db.query(Parish).all()
    print(f"Total parishes: {len(parishes)}")
    
    for p in parishes:
        print(f"Parish: {p.name}, Deanery: {p.deanery.name if p.deanery else 'None'}")
        
    db.close()

if __name__ == "__main__":
    verify()
