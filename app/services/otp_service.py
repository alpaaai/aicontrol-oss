import secrets
import structlog
from datetime import datetime, timedelta

log = structlog.get_logger()

_otp_store: dict[str, dict] = {}

OTP_EXPIRY_MINUTES = 10
OTP_LENGTH = 6


def generate_otp(email: str) -> str:
    code = str(secrets.randbelow(10**OTP_LENGTH)).zfill(OTP_LENGTH)
    _otp_store[email] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES),
        "used": False,
    }
    log.info("otp_generated", email=email, code=code)
    print(f"\n{'='*40}")
    print(f"  OTP CODE for {email}: {code}")
    print(f"  Expires in {OTP_EXPIRY_MINUTES} minutes")
    print(f"{'='*40}\n")
    return code


def verify_otp(email: str, code: str) -> bool:
    entry = _otp_store.get(email)
    if not entry:
        return False
    if entry["used"]:
        return False
    if datetime.utcnow() > entry["expires_at"]:
        return False
    if entry["code"] != code:
        return False
    entry["used"] = True
    return True


def clear_otp(email: str) -> None:
    _otp_store.pop(email, None)
