"""Password hashing and simple signed API tokens."""
import hashlib
import hmac
import os

from app.config import get_settings

settings = get_settings()
_PBKDF2_ROUNDS = 120_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(rounds)
        ).hex()
    except ValueError:
        return False
    return hmac.compare_digest(candidate, digest)


def make_token(username: str) -> str:
    """Deterministic signed token per user: sign(username).hex."""
    sig = hmac.new(settings.token_secret.encode(), username.encode(), hashlib.sha256).hexdigest()
    return f"wb_{username}_{sig[:32]}"
