from fastapi import APIRouter, HTTPException
from backend.core.security import hash_password, verify_password, create_access_token

router = APIRouter()

# 🔥 TEMP storage (later MongoDB)
fake_users_db = {
    "test@test.com": {          # ✅ always exists even after reload
        "email": "test@test.com",
        "password": hash_password("test123")
    }
}


# -----------------------------
# SIGNUP
# -----------------------------
@router.post("/signup")
def signup(data: dict):
    email = data.get("email")
    password = data.get("password")

    # 🔥 FIX: validate input
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    if email in fake_users_db:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed = hash_password(password)

    fake_users_db[email] = {
        "email": email,
        "password": hashed
    }

    return {"message": "User created successfully"}

# -----------------------------
# LOGIN
# -----------------------------
@router.post("/login")
def login(data: dict):
    email = data.get("email")
    password = data.get("password")

    # 🔥 FIX
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    user = fake_users_db.get(email)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Wrong password")

    token = create_access_token({"sub": email})

    return {"access_token": token}