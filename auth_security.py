import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash


load_dotenv()
_password_hash = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "")
TOKEN_LIFETIME_HOURS = 8


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    if len(JWT_SECRET_KEY) < 32:
        raise RuntimeError("AUTH_SECRET_KEY debe tener al menos 32 caracteres.")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(hours=TOKEN_LIFETIME_HOURS)},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    if len(JWT_SECRET_KEY) < 32:
        raise RuntimeError("AUTH_SECRET_KEY debe tener al menos 32 caracteres.")
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
