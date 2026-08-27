"""Report or clean leaked test/demo-artifact rows in the dev database.

Uses the same sweep definitions as tests/conftest.py's autouse cleanup
fixtures (scripts/db_hygiene.py) -- catches junk left behind by manual
dev/demo runs (onboard_agent.py, issue_token.py, hand-testing a feature)
that pytest's own cleanup never touches.

Usage:
    PYTHONPATH=/home/deven/aicontrol python scripts/db_hygiene_check.py
    PYTHONPATH=/home/deven/aicontrol python scripts/db_hygiene_check.py --fix
"""
import argparse
import asyncio
import sys

from app.models.database import async_session_factory
from scripts import db_hygiene


def format_report(counts: dict[str, int]) -> str:
    leaked = {label: n for label, n in counts.items() if n > 0}
    if not leaked:
        return "No leaked test/demo rows found."
    lines = ["Leaked test/demo rows found:"]
    for label, n in leaked.items():
        lines.append(f"  {label}: {n}")
    return "\n".join(lines)


async def main(fix: bool) -> int:
    async with async_session_factory() as session:
        counts = await db_hygiene.count_leaked(session)
        print(format_report(counts))

        if not any(counts.values()):
            return 0

        if not fix:
            print("\nRun with --fix to delete these rows.")
            return 1

        errors = await db_hygiene.clean_all(session)
        remaining = await db_hygiene.count_leaked(session)
        print(f"\nCleaned. Remaining: {format_report(remaining)}")
        if errors:
            for label, message in errors.items():
                print(f"  error cleaning {label}: {message}", file=sys.stderr)
            return 1
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="delete leaked rows instead of only reporting them")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.fix)))
