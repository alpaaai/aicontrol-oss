"""Activation-code generation and verification.

Adapted from app/services/invite_service.py's generate_invite_token pattern
(token generation half only). Unlike an invite token, an activation code has
no expiry — verify_activation_code does not take or check an expires_at.
"""
import hashlib
import hmac
import secrets


def generate_activation_code() -> tuple[str, str]:
    """Return (plaintext_code, code_hash). Never store the plaintext."""
    code = secrets.token_urlsafe(32)
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    return code, code_hash


def verify_activation_code(code: str, stored_hash: str) -> bool:
    """Return True if code hashes to stored_hash. No expiry check."""
    actual_hash = hashlib.sha256(code.encode()).hexdigest()
    return hmac.compare_digest(actual_hash, stored_hash)
