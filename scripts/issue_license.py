"""Issue a signed AIControl license code for a sale.

One-time setup (private key stays outside the repo; back it up):
    python scripts/issue_license.py keygen --out ~/.aicontrol/license-signing.pem
    # paste the printed public key into PUBLIC_KEY in app/core/license_key.py

Per sale:
    python scripts/issue_license.py issue --plan business \
        --email buyer@example.com --order pi_123

Expiry: trial 90 days, business/enterprise 395 days (365 + 30 grace).
--days (1-3650) overrides it (internal/demo instances). The key path defaults to
$AICONTROL_LICENSE_SIGNING_KEY, then ~/.aicontrol/license-signing.pem.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)

from app.core.license_key import PLANS, encode_license_code, public_key_to_str

DEFAULT_DAYS = {"trial": 90, "business": 395, "enterprise": 395}
DEFAULT_KEY_PATH = "~/.aicontrol/license-signing.pem"
MAX_DAYS = 3650


def generate_keypair(path: Path) -> str:
    """Write a new private key to path (mode 600) and return the public key.
    Refuses to overwrite: replacing the key invalidates every issued code."""
    path = Path(path).expanduser()
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return public_key_to_str(private_key.public_key())


def load_private_key(path: Path) -> Ed25519PrivateKey:
    key = load_pem_private_key(Path(path).expanduser().read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"{path} is not an Ed25519 private key")
    return key


def issue_code(
    private_key: Ed25519PrivateKey,
    plan: str,
    email: str,
    order: str,
    now: Optional[datetime] = None,
    days: Optional[int] = None,
) -> str:
    if plan not in PLANS:
        raise ValueError(f"plan must be one of {PLANS}, got {plan!r}")
    if days is not None and not 1 <= days <= MAX_DAYS:
        raise ValueError(f"--days must be between 1 and {MAX_DAYS}, got {days}")
    now = now or datetime.now(timezone.utc)
    expires_at = now + timedelta(days=days if days is not None else DEFAULT_DAYS[plan])
    return encode_license_code(private_key, {
        "plan": plan,
        "email": email,
        "order": order,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    })


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Issue signed AIControl license codes")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen", help="create the signing keypair (once)")
    keygen.add_argument("--out", required=True)

    issue = sub.add_parser("issue", help="issue a license code for a sale")
    issue.add_argument("--plan", required=True, choices=PLANS)
    issue.add_argument("--email", required=True)
    issue.add_argument("--order", required=True, help="Stripe payment or invoice ID")
    issue.add_argument("--days", type=int, default=None)
    issue.add_argument(
        "--key", default=os.environ.get("AICONTROL_LICENSE_SIGNING_KEY", DEFAULT_KEY_PATH)
    )

    args = parser.parse_args(argv)

    if args.command == "keygen":
        try:
            public_key = generate_keypair(Path(args.out))
        except FileExistsError as exc:
            print(f"Error: {exc}. Refusing to overwrite the signing key.", file=sys.stderr)
            return 1
        print(f"Private key written to {Path(args.out).expanduser()} -- back it up.")
        print("Public key (paste into PUBLIC_KEY in app/core/license_key.py):")
        print(public_key)
        return 0

    try:
        code = issue_code(load_private_key(Path(args.key)), args.plan, args.email, args.order, days=args.days)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    expires_days = args.days if args.days is not None else DEFAULT_DAYS[args.plan]
    print(f"{args.plan} license for {args.email} (order {args.order}), valid {expires_days} days:")
    print(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
