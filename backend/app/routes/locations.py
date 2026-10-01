from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.locations import Diocese, Deanery
from app.models.parish import Parish
from app.models.user import User
from app.core.dependencies import get_current_user
from app.routes.admin import require_admin

router = APIRouter(prefix="/api/v1/locations", tags=["Locations"])

@router.get("/admin/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    
    total_dioceses = db.query(Diocese).count()
    archdioceses = db.query(Diocese).filter(Diocese.code.startswith("arch_")).count()
    dioceses = db.query(Diocese).filter(Diocese.code.startswith("dio_")).count()
    military_ordinariate = db.query(Diocese).filter(Diocese.code == "mil_ord").count()
    
    total_deaneries = db.query(Deanery).count()
    total_parishes = db.query(Parish).count()
    
    verified_parishes = db.query(Parish).filter(Parish.verification_status == "verified").count()
    needs_review_parishes = db.query(Parish).filter(Parish.verification_status == "needs_review").count()
    
    return {
        "total_jurisdictions": total_dioceses,
        "archdioceses": archdioceses,
        "dioceses": dioceses,
        "military_ordinariate": military_ordinariate,
        "total_deaneries": total_deaneries,
        "total_parishes": total_parishes,
        "verified_parishes": verified_parishes,
        "needs_review_parishes": needs_review_parishes
    }

@router.get("/dioceses")
def get_dioceses(db: Session = Depends(get_db)):
    return db.query(Diocese).all()

@router.get("/parishes")
def get_all_parishes(db: Session = Depends(get_db)):
    return db.query(Parish).all()

@router.get("/deaneries")
def get_all_deaneries(db: Session = Depends(get_db)):
    return db.query(Deanery).all()

@router.get("/deaneries/{deanery_id}/parishes")
def get_parishes(deanery_id: int, db: Session = Depends(get_db)):
    return db.query(Parish).filter(Parish.deanery_id == deanery_id).all()

@router.post("/deaneries")
def create_deanery(
    name: str, 
    code: str, 
    diocese_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    deanery = Deanery(name=name, code=code, diocese_id=diocese_id)
    db.add(deanery)
    db.commit()
    db.refresh(deanery)
    return deanery

@router.post("/parishes")
def create_parish(
    name: str, 
    code: str, 
    deanery_id: int, 
    diocese_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    # Validate hierarchy server-side
    deanery = db.query(Deanery).filter(Deanery.id == deanery_id, Deanery.diocese_id == diocese_id).first()
    if not deanery:
        raise HTTPException(status_code=400, detail="Invalid hierarchy")
        
    parish = Parish(name=name, code=code, deanery_id=deanery_id, diocese_id=diocese_id)
    db.add(parish)
    db.commit()
    db.refresh(parish)
    return parish

@router.put("/parishes/{parish_id}")
def update_parish(
    parish_id: int,
    name: str,
    deanery_id: int,
    diocese_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found")
    
    # Validate hierarchy server-side
    deanery = db.query(Deanery).filter(Deanery.id == deanery_id, Deanery.diocese_id == diocese_id).first()
    if not deanery:
        raise HTTPException(status_code=400, detail="Invalid hierarchy")
        
    parish.name = name
    parish.deanery_id = deanery_id
    parish.diocese_id = diocese_id
    db.commit()
    db.refresh(parish)
    return parish

@router.delete("/parishes/{parish_id}")
def delete_parish(
    parish_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found")
    
    db.delete(parish)
    db.commit()
    return {"message": "Parish deleted"}

@router.post("/import")
def bulk_import(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    
    results = {
        "jurisdictions_processed": 0,
        "deaneries_added": 0,
        "deaneries_updated": 0,
        "parishes_added": 0,
        "parishes_updated": 0,
        "duplicates_skipped": 0,
        "invalid_records": 0,
        "errors": []
    }
    
    try:
        for jurisdiction_code, jurisdiction_data in data.items():
            results["jurisdictions_processed"] += 1
            diocese = db.query(Diocese).filter(Diocese.code == jurisdiction_code).first()
            if not diocese:
                results["errors"].append(f"Jurisdiction {jurisdiction_code} not found")
                results["invalid_records"] += 1
                continue
                
            for deanery_code, deanery_data in jurisdiction_data.get("deaneries", {}).items():
                deanery = db.query(Deanery).filter(Deanery.code == deanery_code).first()
                if not deanery:
                    deanery = Deanery(name=deanery_data["name"], code=deanery_code, diocese_id=diocese.id)
                    db.add(deanery)
                    results["deaneries_added"] += 1
                else:
                    deanery.name = deanery_data["name"]
                    results["deaneries_updated"] += 1
                db.commit()
                
                for parish_data in deanery_data.get("parishes", []):
                    parish_code = parish_data["code"]
                    parish = db.query(Parish).filter(Parish.code == parish_code).first()
                    if not parish:
                        parish = Parish(
                            name=parish_data["name"], 
                            code=parish_code, 
                            deanery_id=deanery.id, 
                            diocese_id=diocese.id,
                            verification_status="needs_review"
                        )
                        db.add(parish)
                        results["parishes_added"] += 1
                    else:
                        parish.name = parish_data["name"]
                        results["parishes_updated"] += 1
                    db.commit()
                    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return results