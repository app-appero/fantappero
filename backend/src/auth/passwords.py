"""Password hashing and verification."""

from __future__ import annotations

import bcrypt

BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Return a bcrypt hash for ``plain``."""

    digest = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return digest.decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    """Constant-time bcrypt verification."""

    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
