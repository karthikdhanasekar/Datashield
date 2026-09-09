"""
DataShield OSINT - Security Middleware
Request validation, security headers, IP filtering, rate limiting
"""
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers
import time
import structlog

from app.core.security_enhanced import (
    SecurityHeaders,
    IPSecurityManager,
    InputValidator,
    SessionSecurity,
    SecurityAuditLogger
)
from app.core.redis_client import redis_client

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════════════
# Security Headers Middleware
# ══════════════════════════════════════════════════════════════════════════════

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add all security headers
        security_headers = SecurityHeaders.get_all_headers()
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response


# ══════════════════════════════════════════════════════════════════════════════
# IP Filtering Middleware
# ══════════════════════════════════════════════════════════════════════════════

class IPFilterMiddleware(BaseHTTPMiddleware):
    """Filter requests based on IP whitelist/blacklist"""
    
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.ip_security = IPSecurityManager()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check if IP is allowed
        if not self.ip_security.is_ip_allowed(client_ip):
            logger.warning(
                "ip_blocked",
                ip=client_ip,
                path=request.url.path,
                method=request.method
            )
            
            # Log security event
            SecurityAuditLogger.log_event(
                event_type="ip_blocked",
                user_id=None,
                ip_address=client_ip,
                details={"path": request.url.path, "method": request.method},
                severity="warning"
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access denied"}
            )
        
        return await call_next(request)
    
    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP from request headers"""
        # Check common proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# SQL Injection Detection Middleware
# ══════════════════════════════════════════════════════════════════════════════

class SQLInjectionDetectionMiddleware(BaseHTTPMiddleware):
    """Detect and block SQL injection attempts"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check query parameters
        for param, value in request.query_params.items():
            if isinstance(value, str) and InputValidator.check_sql_injection(value):
                client_ip = self._get_client_ip(request)
                logger.warning(
                    "sql_injection_attempt",
                    ip=client_ip,
                    path=request.url.path,
                    param=param
                )
                
                # Log security event
                SecurityAuditLogger.log_event(
                    event_type="sql_injection_attempt",
                    user_id=None,
                    ip_address=client_ip,
                    details={
                        "path": request.url.path,
                        "param": param,
                        "value": value[:100]  # Truncate
                    },
                    severity="high"
                )
                
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid request"}
                )
        
        return await call_next(request)
    
    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# Session Fingerprinting Middleware
# ══════════════════════════════════════════════════════════════════════════════

class SessionFingerprintMiddleware(BaseHTTPMiddleware):
    """Detect session hijacking via fingerprinting"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip for non-authenticated endpoints
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)
        
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return await call_next(request)
        
        token = auth_header.split(" ")[1]
        
        # Calculate current fingerprint
        user_agent = request.headers.get("User-Agent", "")
        client_ip = self._get_client_ip(request)
        current_fingerprint = SessionSecurity.calculate_session_fingerprint(
            user_agent, client_ip
        )
        
        # Get stored fingerprint from Redis
        fingerprint_key = f"session_fp:{token[:16]}"
        stored_fingerprint = await redis_client.get(fingerprint_key)
        
        if stored_fingerprint:
            # Verify fingerprint matches
            if stored_fingerprint.decode() != current_fingerprint:
                logger.warning(
                    "session_hijacking_attempt",
                    ip=client_ip,
                    user_agent=user_agent
                )
                
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Session invalid"}
                )
        else:
            # Store fingerprint for new session
            await redis_client.set(
                fingerprint_key,
                current_fingerprint,
                ex=3600  # 1 hour
            )
        
        return await call_next(request)
    
    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# Request Size Limit Middleware
# ══════════════════════════════════════════════════════════════════════════════

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent DoS"""
    
    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header
        content_length = request.headers.get("Content-Length")
        if content_length:
            if int(content_length) > self.max_size:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Request body too large"}
                )
        
        return await call_next(request)


# ══════════════════════════════════════════════════════════════════════════════
# Request Timing Middleware (for monitoring)
# ══════════════════════════════════════════════════════════════════════════════

class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Add request timing information"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log slow requests
        if process_time > 5.0:  # 5 seconds
            logger.warning(
                "slow_request",
                path=request.url.path,
                method=request.method,
                duration=process_time
            )
        
        return response


# ══════════════════════════════════════════════════════════════════════════════
# CORS with Credentials Middleware (Enhanced)
# ══════════════════════════════════════════════════════════════════════════════

class EnhancedCORSMiddleware(BaseHTTPMiddleware):
    """Enhanced CORS middleware with additional security"""
    
    def __init__(
        self,
        app,
        allowed_origins: list[str],
        allow_credentials: bool = True,
        max_age: int = 600
    ):
        super().__init__(app)
        self.allowed_origins = allowed_origins
        self.allow_credentials = allow_credentials
        self.max_age = max_age
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        origin = request.headers.get("Origin")
        
        # Preflight request
        if request.method == "OPTIONS":
            response = Response()
            if origin in self.allowed_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                if self.allow_credentials:
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Max-Age"] = str(self.max_age)
            return response
        
        response = await call_next(request)
        
        # Add CORS headers to response
        if origin in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response


# ══════════════════════════════════════════════════════════════════════════════
# Anti-Bot Detection Middleware
# ══════════════════════════════════════════════════════════════════════════════

class AntiBotMiddleware(BaseHTTPMiddleware):
    """Detect and block automated bot requests"""
    
    # Common bot user agents
    BOT_PATTERNS = [
        'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
        'python-requests', 'scrapy', 'go-http-client'
    ]
    
    # Whitelist legitimate bots
    ALLOWED_BOTS = [
        'googlebot', 'bingbot', 'yandexbot', 'slackbot', 'twitterbot'
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        user_agent = request.headers.get("User-Agent", "").lower()
        
        # Check if it's a whitelisted bot
        if any(allowed in user_agent for allowed in self.ALLOWED_BOTS):
            return await call_next(request)
        
        # Check if it's a suspicious bot
        if any(pattern in user_agent for pattern in self.BOT_PATTERNS):
            client_ip = self._get_client_ip(request)
            logger.info(
                "bot_detected",
                ip=client_ip,
                user_agent=user_agent,
                path=request.url.path
            )
            
            # Could block here or just log
            # return JSONResponse(
            #     status_code=status.HTTP_403_FORBIDDEN,
            #     content={"detail": "Automated requests not allowed"}
            # )
        
        return await call_next(request)
    
    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


__all__ = [
    'SecurityHeadersMiddleware',
    'IPFilterMiddleware',
    'SQLInjectionDetectionMiddleware',
    'SessionFingerprintMiddleware',
    'RequestSizeLimitMiddleware',
    'RequestTimingMiddleware',
    'EnhancedCORSMiddleware',
    'AntiBotMiddleware',
]
