import json
import sys
import os
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.models.locations import Diocese, Deanery
from app.models.parish import Parish

# Add the current directory to sys.path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def seed():
    db = SessionLocal()
    
    # KCCB Jurisdictions
    jurisdictions = {
        "Nairobi": [
            ("Archdiocese of Nairobi", "arch_nbo"),
            ("Diocese of Kitui", "dio_kti"),
            ("Diocese of Machakos", "dio_mks"),
            ("Diocese of Nakuru", "dio_nku"),
            ("Diocese of Ngong", "dio_ngo"),
            ("Military Ordinariate", "mil_ord"),
            ("Diocese of Kericho", "dio_krc"),
            ("Diocese of Wote", "dio_wte"),
        ],
        "Nyeri": [
            ("Archdiocese of Nyeri", "arch_nyr"),
            ("Diocese of Meru", "dio_mer"),
            ("Diocese of Marsabit", "dio_msb"),
            ("Diocese of Murang'a", "dio_mrg"),
            ("Diocese of Embu", "dio_emb"),
            ("Diocese of Nyahururu", "dio_nyh"),
            ("Diocese of Maralal", "dio_mrl"),
            ("Diocese of Isiolo", "dio_isl"),
        ],
        "Kisumu": [
            ("Archdiocese of Kisumu", "arch_ksm"),
            ("Diocese of Eldoret", "dio_eld"),
            ("Diocese of Kisii", "dio_ksi"),
            ("Diocese of Lodwar", "dio_lod"),
            ("Diocese of Kakamega", "dio_kak"),
            ("Diocese of Bungoma", "dio_bun"),
            ("Diocese of Homa Bay", "dio_hby"),
            ("Diocese of Kitale", "dio_ktl"),
            ("Diocese of Kapsabet", "dio_kap"),
        ],
        "Mombasa": [
            ("Archdiocese of Mombasa", "arch_mba"),
            ("Diocese of Garissa", "dio_grs"),
            ("Diocese of Malindi", "dio_mld"),
        ]
    }

    print("Seeding jurisdictions...")
    for province, dioceses in jurisdictions.items():
        for name, code in dioceses:
            diocese = db.query(Diocese).filter(Diocese.code == code).first()
            if not diocese:
                diocese = Diocese(name=name, code=code)
                db.add(diocese)
                print(f"Added Diocese: {name}")
            else:
                print(f"Diocese already exists: {name}")
    db.commit()

    # Load directory data for Deaneries and Parishes
    if os.path.exists('kenya_directory.json'):
        print("Seeding locations from JSON...")
        with open('kenya_directory.json', 'r') as f:
            directory_data = json.load(f)
        
        for diocese_code, diocese_data in directory_data.items():
            diocese = db.query(Diocese).filter(Diocese.code == diocese_code).first()
            if not diocese:
                print(f"Jurisdiction {diocese_code} not found in database. Skipping.")
                continue
            
            for deanery_code, deanery_data in diocese_data.get("deaneries", {}).items():
                deanery = db.query(Deanery).filter(Deanery.code == deanery_code).first()
                if not deanery:
                    deanery = Deanery(name=deanery_data["name"], code=deanery_code, diocese=diocese)
                    db.add(deanery)
                    db.commit()
                    print(f"Added Deanery: {deanery_data['name']}")
                
                for parish_data in deanery_data.get("parishes", []):
                    parish_code = parish_data["code"]
                    parish = db.query(Parish).filter(Parish.code == parish_code).first()
                    if not parish:
                        parish = Parish(name=parish_data["name"], code=parish_code, deanery=deanery, diocese_id=diocese.id)
                        db.add(parish)
                        db.commit()
                        print(f"Added Parish: {parish_data['name']}")
    else:
        print("kenya_directory.json not found, skipping additional deaneries/parishes.")

    db.close()
    print("Seeding complete.")

if __name__ == "__main__":
    seed()
