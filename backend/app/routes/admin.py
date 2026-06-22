from fastapi import APIRouter

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

@router.get("/")
def admin_home():
    return {
        "message": "Admin route working"
    }

@router.get("/dashboard")
def dashboard():
    return {
        "users": 0,
        "pending_uploads": 0,
        "approved_content": 0
    }