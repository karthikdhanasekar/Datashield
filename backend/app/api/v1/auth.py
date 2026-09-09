"""
DataShield OSINT - Authentication API
Register, login, MFA, token refresh, logout
"""
from datetime import datetime, timezone, timedelta
from typing import Annotated
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, generate_totp_secret,
    get_totp_uri, generate_qr_code, verify_totp, generate_secure_token
)
from app.core.redis_client import add_to_blacklist, cache_set, cache_get
from app.core.config import settings
from app.models.user import User, UserStatus, UserRole, UserSession, AuditLog
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshTokenRequest,
    MFASetupResponse, MFAVerifyRequest, MFAVerifyResponse,
    PasswordResetRequest, PasswordResetConfirm, UserResponse,
    ChangePasswordRequest
)
from app.api.deps import get_current_user, get_current_active_user
from app.services.notification_service import send_verification_email, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def log_audit(
    db: AsyncSession,
    user_id: str,
    action: str,
    request: Request,
    status: str = "success",
    details: dict = None,
):
    """Create an audit log entry."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        status=status,
        details=details or {},
    )
    db.add(log)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register a new user account."""
    # Check for existing user
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    verification_token = generate_secure_token(32)
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        phone_number=body.phone_number,
        role=UserRole.INDIVIDUAL,
        status=UserStatus.PENDING_VERIFICATION,
        email_verification_token=verification_token,
    )
    db.add(user)
    await db.flush()  # Get the ID

    await log_audit(db, str(user.id), "user_register", request)
    await db.commit()
    await db.refresh(user)

    # Send verification email in background
    background_tasks.add_task(
        send_verification_email,
        email=user.email,
        name=user.full_name or "User",
        token=verification_token,
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        status=user.status.value,
        mfa_enabled=user.mfa_enabled,
        email_verified=user.email_verified,
        created_at=str(user.created_at),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate and receive JWT tokens."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        await log_audit(db, None, "login_failed", request, status="failure",
                       details={"email": body.email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Check if email is verified
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before logging in. Check your inbox for the verification link.",
        )

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(status_code=403, detail="Account suspended.")

    # MFA check
    if user.mfa_enabled:
        if not body.mfa_code:
            return TokenResponse(
                access_token="",
                refresh_token="",
                token_type="bearer",
                expires_in=0,
                user_role=user.role.value,
                mfa_required=True,
            )
        if not verify_totp(user.mfa_secret, body.mfa_code):
            await log_audit(db, str(user.id), "mfa_failed", request, status="failure")
            raise HTTPException(status_code=401, detail="Invalid MFA code.")

    # Generate tokens
    access_token = create_access_token(str(user.id), role=user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    # Store session
    from jose import jwt as jose_jwt
    access_payload = decode_token(access_token)
    session = UserSession(
        user_id=user.id,
        jti=access_payload["jti"],
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        expires_at=datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc),
    )
    db.add(session)

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = request.client.host if request.client else None

    await log_audit(db, str(user.id), "login_success", request)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_role=user.role.value,
        mfa_required=False,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Exchange a refresh token for a new access token."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    access_token = create_access_token(str(user.id), role=user.role.value)
    new_refresh = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_role=user.role.value,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Invalidate the current JWT token."""
    from fastapi.security import HTTPBearer
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")
    try:
        payload = decode_token(token)
        jti = payload.get("jti", "")
        exp = payload.get("exp", 0)
        ttl = max(exp - int(datetime.now(timezone.utc).timestamp()), 1)
        await add_to_blacklist(jti, ttl)
    except Exception:
        pass
    await log_audit(db, str(current_user.id), "logout", request)
    await db.commit()


@router.get("/verify-email")
async def verify_email(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Verify email address with token."""
    result = await db.execute(
        select(User).where(User.email_verification_token == token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")

    user.email_verified = True
    user.status = UserStatus.ACTIVE
    user.email_verification_token = None
    await db.commit()
    return {"message": "Email verified successfully. You can now log in."}


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a TOTP secret and QR code for MFA setup."""
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, current_user.email)
    qr = generate_qr_code(uri)

    # Temporarily store secret until verified
    await cache_set(f"mfa_pending:{current_user.id}", secret, ttl=600)

    return MFASetupResponse(secret=secret, qr_code=qr, provisioning_uri=uri)


@router.post("/mfa/verify", response_model=MFAVerifyResponse)
async def verify_mfa_setup(
    body: MFAVerifyRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Confirm MFA setup with a TOTP code."""
    secret = await cache_get(f"mfa_pending:{current_user.id}")
    if not secret:
        raise HTTPException(status_code=400, detail="MFA setup session expired. Please restart setup.")

    if not verify_totp(secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid code. Please try again.")

    # Generate backup codes
    backup_codes = [secrets.token_hex(5).upper() for _ in range(8)]
    hashed_backups = [hashlib.sha256(c.encode()).hexdigest() for c in backup_codes]

    current_user.mfa_secret = secret
    current_user.mfa_enabled = True
    current_user.mfa_backup_codes = hashed_backups
    await db.commit()

    return MFAVerifyResponse(verified=True, backup_codes=backup_codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    body: MFAVerifyRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Disable MFA after confirming current TOTP code."""
    if not current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is not enabled.")
    if not verify_totp(current_user.mfa_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid code.")
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_backup_codes = None
    await db.commit()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    """Get the currently authenticated user's profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        status=current_user.status.value,
        mfa_enabled=current_user.mfa_enabled,
        email_verified=current_user.email_verified,
        created_at=str(current_user.created_at),
    )


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    body: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Request a password reset email."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Always return 202 to prevent user enumeration
    if user:
        token = generate_secure_token(32)
        user.password_reset_token = token
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()
        background_tasks.add_task(
            send_password_reset_email,
            email=user.email,
            name=user.full_name or "User",
            token=token,
        )

    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Reset password using token."""
    result = await db.execute(
        select(User).where(User.password_reset_token == body.token)
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_reset_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")

    if user.password_reset_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token has expired. Request a new one.")

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.commit()

    return {"message": "Password reset successfully."}
