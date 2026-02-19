from __future__ import annotations
import bcrypt
import hashlib


def _prehash(password: str) -> bytes:
    # 64-character hex string -> encode to bytes for bcrypt
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(raw_password: str) -> str:
    hashed = bcrypt.hashpw(_prehash(raw_password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        _prehash(plain),
        hashed.encode("utf-8")
    )
