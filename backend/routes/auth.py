from fastapi import APIRouter, HTTPException
from backend.core.security import hash_password, verify_password, create_access_token
from backend.db import db
from datetime import datetime

router = APIRouter()

# Step 1 — unique index on startup
db.users.create_index("email", unique=True)

# -----------------------------
# SIGNUP
# -----------------------------
@router.post("/signup")
def signup(data: dict):
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    existing_user = db.users.find_one({"email": email})  # no await
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed = hash_password(password)

    db.users.insert_one({           # no await
        "email": email,
        "password": hashed,
        "created_at": datetime.utcnow()
    })

    return {"message": "User created successfully"}

# -----------------------------
# LOGIN
# -----------------------------
@router.post("/login")
def login(data: dict):
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    user = db.users.find_one({"email": email})  # no await

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Wrong password")

    token = create_access_token({"sub": email})

    return {"access_token": token}
