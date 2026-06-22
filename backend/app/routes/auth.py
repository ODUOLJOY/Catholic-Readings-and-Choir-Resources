from fastapi import APIRouter

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

users = []

@router.get("/")
def auth_home():
    return {
        "message": "Auth route working"
    }

@router.post("/register")
def register(user: dict):

    users.append(user)

    return {
        "message": "registered successfully",
        "user": user
    }

@router.post("/login")
def login(data: dict):

    email = data.get("email")
    password = data.get("password")

    for user in users:

        if (
            user.get("email") == email
            and
            user.get("password") == password
        ):

            return {
                "success": True,
                "user": user
            }

    return {
        "success": False,
        "message": "invalid credentials"
    }