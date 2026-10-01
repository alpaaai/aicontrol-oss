#!/usr/bin/env python3
"""Warn about config fields defined in app.core.config.Settings that are
missing from an existing .env file (e.g. new fields added since the .env
was first generated). Read-only — never writes or modifies .env.

Usage: python3 scripts/check_env_completeness.py [path-to-env]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import Settings  # noqa: E402


def parse_env_keys(env_path: Path) -> set[str]:
    keys = set()
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        keys.add(key.lower())
    return keys


def main() -> int:
    env_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".env")
    if not env_path.is_file():
        print(f"ERROR: {env_path} not found.", file=sys.stderr)
        return 1

    existing_keys = parse_env_keys(env_path)
    missing = [name for name in Settings.model_fields if name.lower() not in existing_keys]

    if not missing:
        print("[ok] .env has all known config fields.")
        return 0

    print("[warn] .env is missing these config fields (Settings defaults will apply):")
    for name in missing:
        field = Settings.model_fields[name]
        default = "<required, no default>" if field.is_required() else repr(field.default)
        print(f"  {name} (default: {default})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
