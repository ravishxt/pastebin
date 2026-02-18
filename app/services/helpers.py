from __future__ import annotations
import bcrypt
import hashlib
import base64
from app.security import pwd_context

def _prehash(password: str) -> str:
    # 64-character hex string (safe for bcrypt)
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(raw_password: str) -> str:
    return pwd_context.hash(_prehash(raw_password))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_prehash(plain), hashed)