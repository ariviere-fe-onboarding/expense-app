"""Password hashing and opaque tokens, built on the standard library."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def hash_password(password: str) -> str:
    """Return a salted scrypt hash in the form 'scrypt$<salt hex>$<hash hex>'."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash in constant time."""
    scheme, _, rest = stored.partition("$")
    salt_hex, _, digest_hex = rest.partition("$")
    if scheme != "scrypt" or not salt_hex or not digest_hex:
        return False
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def new_token() -> str:
    """Return an unguessable URL-safe token."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """Return the SHA-256 hex digest stored in place of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
