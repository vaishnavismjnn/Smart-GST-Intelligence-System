from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from backend.core.security import SECRET_KEY, ALGORITHM
from backend.db import collection
from bson import ObjectId

router = APIRouter()
bearer_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/records")
def get_records(
    user_email: str = Depends(get_current_user),
    page: int = 1,
    limit: int = 10,
    search: str = None
):
    # Build filter
    query = {"user_email": user_email}

    # Search by merchant or invoice number
    if search:
        query["$or"] = [
            {"MERCHANT":   {"$regex": search, "$options": "i"}},
            {"INVOICE_NO": {"$regex": search, "$options": "i"}}
        ]

    # Pagination
    skip = (page - 1) * limit
    total = collection.count_documents(query)
    records = list(collection.find(query).skip(skip).limit(limit))

    # Convert ObjectId to string
    for r in records:
        r["_id"] = str(r["_id"])

    return {
        "total":   total,
        "page":    page,
        "limit":   limit,
        "records": records
    }