"""
DataShield OSINT - Security Utilities
JWT handling, password hashing, MFA, RBAC
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
import secrets
import hashlib

import pyotp
import qrcode
import io
import base64
from jose import JWTError, jwt
from passlib.context import CryptContext  # kept for fallback

from app.core.config import settings

# ── Password hashing ─────────────────────────────────────────────────────────
# Use bcrypt directly to avoid passlib version compatibility issues
# with newer bcrypt packages (4.x+)
try:
    import bcrypt as _bcrypt_lib

    def hash_password(password: str) -> str:
        """Hash a plain-text password using bcrypt."""
        return _bcrypt_lib.hashpw(
            password.encode("utf-8"),
            _bcrypt_lib.gensalt(rounds=12),
        ).decode("utf-8")

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain-text password against its bcrypt hash."""
        try:
            return _bcrypt_lib.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception:
            return False

except ImportError:
    # Fallback to passlib if bcrypt not available directly
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)


# ── JWT Tokens ────────────────────────────────────────────────────────────────
def create_access_token(
    subject: Union[str, Any],
    role: str = "individual",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: Union[str, Any]) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(subject),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )


# ── MFA / TOTP ────────────────────────────────────────────────────────────────
def generate_totp_secret() -> str:
    """Generate a new TOTP secret key."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """Get the provisioning URI for an authenticator app."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.TOTP_ISSUER)


def generate_qr_code(totp_uri: str) -> str:
    """Generate a QR code as a base64-encoded PNG string."""
    img = qrcode.make(totp_uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code. Allows 1 interval drift."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ── Evidence Hashing ──────────────────────────────────────────────────────────
def hash_evidence(content: bytes) -> str:
    """Create a SHA-256 hash for evidence integrity verification."""
    return hashlib.sha256(content).hexdigest()


# ── Secure Random Tokens ──────────────────────────────────────────────────────
def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


# ── RBAC Roles ────────────────────────────────────────────────────────────────
ROLES = {
    "individual": 1,
    "organization": 2,
    "admin": 3,
}


def has_permission(user_role: str, required_role: str) -> bool:
    """Check if user has at least the required role level."""
    return ROLES.get(user_role, 0) >= ROLES.get(required_role, 0)
