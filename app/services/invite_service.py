"""Token generation and validation for magic-link invites."""
import hashlib
import secrets
from datetime import datetime, timezone


def generate_invite_token() -> tuple[str, str]:
    """Return (plaintext_token, token_hash). Never store the plaintext."""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def validate_invite_token(token: str, stored_hash: str, expires_at: datetime) -> bool:
    """Return True if the token matches the hash and has not expired."""
    try:
        actual_hash = hashlib.sha256(token.encode()).hexdigest()
        if actual_hash != stored_hash:
            return False
        now = datetime.now(timezone.utc)
        aware_expires = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        return now < aware_expires
    except Exception:
        return False
