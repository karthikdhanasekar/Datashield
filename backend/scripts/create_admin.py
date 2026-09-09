"""
DataShield OSINT — Admin User Creation Script
==============================================
Creates the first admin account in the database.

Usage:
  docker exec -u root -e PYTHONPATH=/app datashield_backend \
    python scripts/create_admin.py

  Or with custom credentials:
    ADMIN_EMAIL=admin@company.com ADMIN_PASSWORD=Secure@123 \
    python scripts/create_admin.py
"""
import asyncio
import os
import sys

# Add /app to path when run inside container
sys.path.insert(0, "/app")


async def create_admin():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal, init_db
    from app.core.security import hash_password
    from app.models.user import User, UserRole, UserStatus
    import uuid

    email    = os.environ.get("ADMIN_EMAIL",    "admin@datashield.com")
    password = os.environ.get("ADMIN_PASSWORD", "Admin@DataShield2024!")
    name     = os.environ.get("ADMIN_NAME",     "DataShield Admin")

    print(f"\n🛡  DataShield OSINT — Admin User Setup")
    print(f"   Email:    {email}")
    print(f"   Password: {'*' * len(password)}")
    print(f"   Name:     {name}\n")

    await init_db()

    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        existing = await db.execute(
            select(User).where(User.email == email)
        )
        user = existing.scalar_one_or_none()

        if user:
            # Update role to admin if user exists but isn't admin
            if user.role != UserRole.ADMIN:
                user.role   = UserRole.ADMIN
                user.status = UserStatus.ACTIVE
                user.email_verified = True
                await db.commit()
                print(f"✅ Existing user '{email}' promoted to admin.")
            else:
                print(f"✅ Admin user '{email}' already exists.")
        else:
            # Create new admin
            new_admin = User(
                id=uuid.uuid4(),
                email=email,
                hashed_password=hash_password(password),
                full_name=name,
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                email_verified=True,
                mfa_enabled=False,
            )
            db.add(new_admin)
            await db.commit()
            print(f"✅ Admin user created successfully!")

        print(f"\n   Login at:  http://localhost:3000/auth/login")
        print(f"   API docs:  http://localhost:8000/api/docs\n")


if __name__ == "__main__":
    asyncio.run(create_admin())
