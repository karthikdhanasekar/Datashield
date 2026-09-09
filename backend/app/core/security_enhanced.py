"""
DataShield OSINT - Enhanced Security Module
Production-grade security features including encryption, CSP, input validation
"""
from typing import Optional, Dict, List, Any
import secrets
import hashlib
import hmac
import re
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network, IPv4Address, IPv6Address
import bleach
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend

from app.core.config import settings


# ══════════════════════════════════════════════════════════════════════════════
# Data Encryption
# ══════════════════════════════════════════════════════════════════════════════

class DataEncryption:
    """Handle encryption/decryption of sensitive data at rest"""
    
    def __init__(self, key: Optional[str] = None):
        """Initialize with encryption key from settings or provided key"""
        if key is None:
            key = getattr(settings, 'ENCRYPTION_KEY', None)
        
        if not key:
            # Generate a key if none exists (dev only - production MUST set this)
            import warnings
            warnings.warn("No ENCRYPTION_KEY found - generating temporary key")
            key = Fernet.generate_key().decode()
        
        # Ensure key is bytes
        if isinstance(key, str):
            key = key.encode()
        
        self.cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return base64 encoded string"""
        if not plaintext:
            return ""
        encrypted = self.cipher.encrypt(plaintext.encode())
        return encrypted.decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64 encoded ciphertext"""
        if not ciphertext:
            return ""
        try:
            decrypted = self.cipher.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception:
            return ""
    
    @staticmethod
    def derive_key_from_password(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())


# ══════════════════════════════════════════════════════════════════════════════
# Input Validation & Sanitization
# ══════════════════════════════════════════════════════════════════════════════

class InputValidator:
    """Validate and sanitize user inputs to prevent injection attacks"""
    
    # Regex patterns for common validations
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,50}$')
    DOMAIN_PATTERN = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$')
    
    # SQL injection keywords
    SQL_KEYWORDS = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 
                    'ALTER', 'EXEC', 'UNION', 'SCRIPT', '--', '/*', '*/', 'xp_']
    
    @staticmethod
    def sanitize_html(text: str, allowed_tags: Optional[List[str]] = None) -> str:
        """Remove dangerous HTML/JavaScript"""
        if allowed_tags is None:
            allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'a']
        return bleach.clean(text, tags=allowed_tags, strip=True)
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        if not email or len(email) > 254:
            return False
        return bool(InputValidator.EMAIL_PATTERN.match(email))
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username format"""
        return bool(InputValidator.USERNAME_PATTERN.match(username))
    
    @staticmethod
    def validate_domain(domain: str) -> bool:
        """Validate domain name format"""
        if len(domain) > 253:
            return False
        return bool(InputValidator.DOMAIN_PATTERN.match(domain))
    
    @staticmethod
    def check_sql_injection(text: str) -> bool:
        """Check if text contains SQL injection patterns"""
        text_upper = text.upper()
        for keyword in InputValidator.SQL_KEYWORDS:
            if keyword in text_upper:
                return True
        return False
    
    @staticmethod
    def validate_scan_type(scan_type: str) -> bool:
        """Validate scan type is allowed"""
        allowed = ['email', 'username', 'phone', 'name', 'domain', 'ip', 'full']
        return scan_type.lower() in allowed


# ══════════════════════════════════════════════════════════════════════════════
# IP Security & Rate Limiting
# ══════════════════════════════════════════════════════════════════════════════

class IPSecurityManager:
    """Manage IP whitelists, blacklists, and geographic restrictions"""
    
    def __init__(self):
        self.whitelist: List[str] = []
        self.blacklist: List[str] = []
        self._load_lists()
    
    def _load_lists(self):
        """Load IP lists from settings"""
        if hasattr(settings, 'IP_WHITELIST') and settings.IP_WHITELIST:
            self.whitelist = [ip.strip() for ip in settings.IP_WHITELIST.split(',')]
        if hasattr(settings, 'IP_BLACKLIST') and settings.IP_BLACKLIST:
            self.blacklist = [ip.strip() for ip in settings.IP_BLACKLIST.split(',')]
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Check if IP address is allowed"""
        try:
            ip_obj = ip_address(ip)
            
            # Check blacklist first
            if self._is_in_list(ip_obj, self.blacklist):
                return False
            
            # If whitelist exists, IP must be in it
            if self.whitelist:
                return self._is_in_list(ip_obj, self.whitelist)
            
            return True
        except ValueError:
            return False
    
    def _is_in_list(self, ip: IPv4Address | IPv6Address, ip_list: List[str]) -> bool:
        """Check if IP is in the list (supports CIDR notation)"""
        for list_entry in ip_list:
            try:
                if '/' in list_entry:
                    # CIDR notation
                    if ip in ip_network(list_entry, strict=False):
                        return True
                else:
                    # Single IP
                    if ip == ip_address(list_entry):
                        return True
            except ValueError:
                continue
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Content Security Policy
# ══════════════════════════════════════════════════════════════════════════════

class CSPBuilder:
    """Build Content Security Policy headers"""
    
    @staticmethod
    def get_default_csp() -> str:
        """Get default CSP for production"""
        directives = {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],  # Next.js needs these
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:", "https:"],
            "font-src": ["'self'", "data:"],
            "connect-src": ["'self'", "https://api.yourdomain.com", "wss://api.yourdomain.com"],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "upgrade-insecure-requests": []
        }
        
        csp_parts = []
        for directive, sources in directives.items():
            if sources:
                csp_parts.append(f"{directive} {' '.join(sources)}")
            else:
                csp_parts.append(directive)
        
        return "; ".join(csp_parts)


# ══════════════════════════════════════════════════════════════════════════════
# Secure Headers
# ══════════════════════════════════════════════════════════════════════════════

class SecurityHeaders:
    """Generate security headers for HTTP responses"""
    
    @staticmethod
    def get_all_headers() -> Dict[str, str]:
        """Get all security headers for production"""
        headers = {
            # HSTS
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # XSS Protection
            "X-XSS-Protection": "1; mode=block",
            
            # Content type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Permissions policy
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            
            # CSP
            "Content-Security-Policy": CSPBuilder.get_default_csp(),
            
            # Remove server header
            "Server": "DataShield"
        }
        
        return headers


# ══════════════════════════════════════════════════════════════════════════════
# API Key Management
# ══════════════════════════════════════════════════════════════════════════════

class APIKeyManager:
    """Manage API keys for external integrations"""
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key"""
        return f"ds_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def verify_api_key(api_key: str, hashed_key: str) -> bool:
        """Verify API key against stored hash"""
        return hmac.compare_digest(
            APIKeyManager.hash_api_key(api_key),
            hashed_key
        )


# ══════════════════════════════════════════════════════════════════════════════
# Request Signing (for webhooks)
# ══════════════════════════════════════════════════════════════════════════════

class RequestSigner:
    """Sign and verify webhook requests"""
    
    @staticmethod
    def sign_payload(payload: str, secret: str) -> str:
        """Create HMAC signature for payload"""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def verify_signature(payload: str, signature: str, secret: str) -> bool:
        """Verify HMAC signature"""
        expected = RequestSigner.sign_payload(payload, secret)
        return hmac.compare_digest(signature, expected)


# ══════════════════════════════════════════════════════════════════════════════
# Password Policy Enforcement
# ══════════════════════════════════════════════════════════════════════════════

class PasswordPolicy:
    """Enforce password complexity requirements"""
    
    MIN_LENGTH = 12
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL = True
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password against policy
        Returns: (is_valid, error_message)
        """
        if len(password) < PasswordPolicy.MIN_LENGTH:
            return False, f"Password must be at least {PasswordPolicy.MIN_LENGTH} characters"
        
        if PasswordPolicy.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if PasswordPolicy.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if PasswordPolicy.REQUIRE_DIGITS and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        
        if PasswordPolicy.REQUIRE_SPECIAL and not any(c in PasswordPolicy.SPECIAL_CHARS for c in password):
            return False, f"Password must contain at least one special character: {PasswordPolicy.SPECIAL_CHARS}"
        
        # Check against common passwords
        if PasswordPolicy.is_common_password(password):
            return False, "This password is too common. Please choose a stronger password"
        
        return True, None
    
    @staticmethod
    def is_common_password(password: str) -> bool:
        """Check if password is in common passwords list"""
        common = [
            'password', '12345678', 'qwerty', 'abc123', 'password123',
            'admin', 'letmein', 'welcome', 'monkey', '1234567890'
        ]
        return password.lower() in common


# ══════════════════════════════════════════════════════════════════════════════
# Session Security
# ══════════════════════════════════════════════════════════════════════════════

class SessionSecurity:
    """Manage secure session handling"""
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate cryptographically secure session ID"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def calculate_session_fingerprint(user_agent: str, ip_address: str) -> str:
        """Create session fingerprint to detect session hijacking"""
        data = f"{user_agent}:{ip_address}".encode()
        return hashlib.sha256(data).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# Audit Logging
# ══════════════════════════════════════════════════════════════════════════════

class SecurityAuditLogger:
    """Log security-related events for audit trail"""
    
    @staticmethod
    def log_event(
        event_type: str,
        user_id: Optional[int],
        ip_address: str,
        details: Dict[str, Any],
        severity: str = "info"
    ) -> Dict[str, Any]:
        """
        Create security audit log entry
        Returns dict that should be saved to database
        """
        return {
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
            "event_id": secrets.token_hex(16)
        }


# ══════════════════════════════════════════════════════════════════════════════
# Exports
# ══════════════════════════════════════════════════════════════════════════════

# Create singleton instances
data_encryptor = DataEncryption()
input_validator = InputValidator()
ip_security = IPSecurityManager()
api_key_manager = APIKeyManager()

__all__ = [
    'DataEncryption',
    'InputValidator',
    'IPSecurityManager',
    'CSPBuilder',
    'SecurityHeaders',
    'APIKeyManager',
    'RequestSigner',
    'PasswordPolicy',
    'SessionSecurity',
    'SecurityAuditLogger',
    'data_encryptor',
    'input_validator',
    'ip_security',
    'api_key_manager',
]
