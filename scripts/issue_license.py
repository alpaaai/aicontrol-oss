#!/usr/bin/env python3
"""
Offline license key generator for AIControl.

Usage:
  AICONTROL_PRIVATE_KEY_PATH=~/aicontrol-private.pem \
    python scripts/issue_license.py \
    --company "Aon" \
    --email "admin@aon.com" \
    --plan enterprise \
    --days 365

Outputs a signed JWT to stdout. Paste into customer's .env as AICONTROL_LICENSE_KEY.
"""
import argparse
import base64
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


def load_private_key(path: str):
    pem = Path(path).expanduser().read_bytes()
    return load_pem_private_key(pem, password=None)


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def issue_license(company: str, email: str, plan: str, days: int, private_key_path: str) -> str:
    """Generate a signed RS256 JWT license key."""
    assert plan in ("community", "business", "enterprise"), \
        f"Invalid plan: {plan}. Must be community, business, or enterprise."

    private_key = load_private_key(private_key_path)

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)

    payload = {
        "iss": "aictl.io",
        "jti": str(uuid.uuid4()),
        "company": company,
        "email": email,
        "plan": plan,
        "issued_at": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }

    header = {"alg": "RS256", "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64url_encode(signature)

    token = f"{header_b64}.{payload_b64}.{sig_b64}"

    print(f"License issued:", file=sys.stderr)
    print(f"  Company:  {company}", file=sys.stderr)
    print(f"  Email:    {email}", file=sys.stderr)
    print(f"  Plan:     {plan}", file=sys.stderr)
    print(f"  Expires:  {expires.strftime('%Y-%m-%d')} ({days} days)", file=sys.stderr)
    print(f"  JTI:      {payload['jti']}", file=sys.stderr)
    print(f"\nAICONTROL_LICENSE_KEY={token}")

    return token


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Issue AIControl license key")
    parser.add_argument("--company", required=True, help="Customer company name")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--plan", required=True, choices=["community", "business", "enterprise"])
    parser.add_argument("--days", type=int, default=365, help="License validity in days")
    parser.add_argument(
        "--key",
        default=os.environ.get("AICONTROL_PRIVATE_KEY_PATH", ""),
        help="Path to RSA private key PEM file (or set AICONTROL_PRIVATE_KEY_PATH)",
    )
    args = parser.parse_args()

    if not args.key:
        print("ERROR: --key or AICONTROL_PRIVATE_KEY_PATH required", file=sys.stderr)
        sys.exit(1)

    issue_license(args.company, args.email, args.plan, args.days, args.key)
