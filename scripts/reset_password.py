"""Reset a user's password directly in the DB.

Usage:
    python scripts/reset_password.py --email hello@aictl.io --password "NewPassw0rd!"
    python scripts/reset_password.py --email hello@aictl.io   # prompts for password
"""
import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.models.database import async_session_factory
from app.models.user import User
from app.routers.setup import _hash_password


async def reset(email: str, password: str) -> None:
    if len(password) < 8:
        print("Error: password must be at least 8 characters")
        return

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"Error: no user found with email '{email}'")
            return

        user.password_hash = _hash_password(password)
        user.password_set = True
        user.is_active = True
        await session.commit()

    print(f"\nPassword reset for {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset an AIControl user's password")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", default=None, help="New password (prompts if omitted)")
    args = parser.parse_args()

    pw = args.password or getpass.getpass("New password: ")
    asyncio.run(reset(args.email, pw))
