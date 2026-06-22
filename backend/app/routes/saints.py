from fastapi import APIRouter

router = APIRouter(
    prefix="/saints",
    tags=["Saints"]
)

saints = []

@router.get("/")
def get_saints():
    return saints

@router.post("/")
def add_saint(item: dict):

    saints.append(item)

    return {
        "message": "saint added"
    }