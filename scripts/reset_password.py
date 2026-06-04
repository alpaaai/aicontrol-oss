"""Reset (or set) a human user's password directly in the DB.

Usage:
    python scripts/reset_password.py --email hello@aictl.io --password newpassword
"""
import argparse
import asyncio

from sqlalchemy import select, update
from app.models.database import async_session_factory
from app.models.user import User
from app.routers.setup import _hash_password


async def reset(email: str, password: str) -> None:
    if len(password) < 8:
        print("Error: password must be at least 8 characters")
        return

    email = email.lower().strip()

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"Error: no user found with email '{email}'")
            return

        user.password_hash = _hash_password(password)
        user.password_set = True
        await session.commit()

    print(f"Password updated for {email} (role={user.role.value}, is_root={user.is_root})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset a human user's password")
    parser.add_argument("--email", required=True, help="User's email address")
    parser.add_argument("--password", required=True, help="New password (min 8 chars)")
    args = parser.parse_args()
    asyncio.run(reset(args.email, args.password))
