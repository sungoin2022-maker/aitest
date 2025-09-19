"""Password hashing utilities using the standard library."""
from __future__ import annotations

import hashlib
import hmac
import os


def hash_password(password: str, *, iterations: int = 120_000) -> str:
    if not isinstance(password, str):
        raise TypeError("Password must be a string")
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{iterations}${salt.hex()}${derived.hex()}"


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        iteration_str, salt_hex, hash_hex = stored_hash.split("$")
        iterations = int(iteration_str)
    except (ValueError, AttributeError):
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)
