from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# -----------------------------
# CONFIG
# -----------------------------
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_security = HTTPBearer()


# -----------------------------
# PASSWORD
# -----------------------------
def hash_password(password: str):
    password = password[:72]  # 🔥 bcrypt fix
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    plain_password = plain_password[:72]  # 🔥 bcrypt fix
    return pwd_context.verify(plain_password, hashed_password)


# -----------------------------
# TOKEN
# -----------------------------
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# -----------------------------
# AUTH DEPENDENCY (PROTECTION)
# -----------------------------
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    token = credentials.credentials

    from backend.core.security import decode_token  # ensure correct import

    payload = decode_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload.get("sub")