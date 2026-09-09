"""
DataShield OSINT - API Dependencies
FastAPI dependency injection: auth, RBAC, rate limiting, DB
"""
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_token, has_permission
from app.core.redis_client import is_blacklisted
from app.models.user import User, UserStatus

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate the current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        jti: str = payload.get("jti", "")

        if user_id is None or token_type != "access":
            raise credentials_exception

        # Check token blacklist (logout)
        if await is_blacklisted(jti):
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended. Contact support.",
        )

    if user.status == UserStatus.INACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account inactive.",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure user is active and email verified."""
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email address.",
        )
    return current_user


def require_role(required_role: str):
    """Factory for role-based access control dependencies."""
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if not has_permission(current_user.role.value, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )
        return current_user
    return role_checker


# Convenience role dependencies
RequireIndividual = Depends(require_role("individual"))
RequireOrganization = Depends(require_role("organization"))
RequireAdmin = Depends(require_role("admin"))


def get_pagination(page: int = 1, page_size: int = 20) -> dict:
    """Standard pagination parameters."""
    from app.core.config import settings
    page_size = min(page_size, settings.MAX_PAGE_SIZE)
    page = max(page, 1)
    return {"page": page, "page_size": page_size, "offset": (page - 1) * page_size}
