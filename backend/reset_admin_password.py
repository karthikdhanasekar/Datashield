"""Reset admin password script"""
import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password

async def reset_admin_password():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == 'admin@datashield.com'))
        admin = result.scalar_one_or_none()
        
        if not admin:
            print('ERROR: Admin user not found')
            return
        
        # Reset password to: Admin@DataShield2024!
        admin.hashed_password = hash_password('Admin@DataShield2024!')
        await db.commit()
        print('✓ Admin password reset successfully!')
        print('')
        print('Login with:')
        print('  Email:    admin@datashield.com')
        print('  Password: Admin@DataShield2024!')

if __name__ == '__main__':
    asyncio.run(reset_admin_password())
