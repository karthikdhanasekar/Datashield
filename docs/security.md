# DataShield OSINT — Security Guide

## Authentication Architecture

### JWT Token Flow

```
Client                          Server
  │                               │
  │── POST /auth/login ──────────►│
  │                               │ Verify password (bcrypt)
  │                               │ Check MFA if enabled
  │◄── access_token (30min) ─────│
  │◄── refresh_token (7 days) ───│
  │                               │
  │── API request + Bearer ──────►│
  │                               │ Decode JWT
  │                               │ Check blacklist (Redis)
  │                               │ Load user from DB
  │◄── response ─────────────────│
  │                               │
  │── POST /auth/refresh ────────►│
  │◄── new access_token ─────────│
  │                               │
  │── POST /auth/logout ─────────►│
  │                               │ Add JTI to Redis blacklist
  │◄── 204 No Content ───────────│
```

### Token Security Properties

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Access token TTL | 30 minutes |
| Refresh token TTL | 7 days |
| Revocation | Redis JTI blacklist |
| Unique ID (JTI) | Yes — `secrets.token_hex(16)` |
| Claims | sub, role, type, exp, iat, jti |

---

## Multi-Factor Authentication (TOTP)

- Standard TOTP (RFC 6238) compatible with Google Authenticator, Authy, 1Password
- 30-second window, 1-interval drift tolerance
- Secret: 32-char Base32 string (pyotp)
- Backup codes: 8 × 10-char hex codes, SHA-256 hashed in DB
- Setup requires confirming a valid code before MFA is activated
- Disable requires current valid TOTP code

---

## Password Security

- Hashing: **bcrypt** with automatic random salt (passlib)
- Minimum requirements enforced at API level:
  - 8+ characters
  - Uppercase + lowercase
  - Digit
  - Special character (`!@#$%^&*`)
- Password reset tokens: `secrets.token_urlsafe(32)`, 1-hour TTL
- k-Anonymity check available (HIBP Pwned Passwords API)

---

## Role-Based Access Control (RBAC)

```
individual (level 1)
    ↓ can also access ↓
organization (level 2)
    ↓ can also access ↓
admin (level 3)
```

| Resource | Individual | Organization | Admin |
|----------|-----------|--------------|-------|
| Own scans/findings | ✅ | ✅ | ✅ |
| Team member scans | ❌ | ✅ | ✅ |
| User management | ❌ | ❌ | ✅ |
| Platform analytics | ❌ | ❌ | ✅ |
| Audit logs | ❌ | ❌ | ✅ |
| System config | ❌ | ❌ | ✅ |

---

## Rate Limiting

Enforced at two layers: **Nginx** and **slowapi (FastAPI)**

| Endpoint | Limit |
|----------|-------|
| All API endpoints | 60 req/min per IP |
| POST /auth/login | 5 req/min per IP |
| POST /scans/ | 10 scans/hour per user |
| POST /auth/register | 3 req/min per IP |

Exceeding limits returns `429 Too Many Requests`.

---

## OWASP Top 10 Protections

| Threat | Mitigation |
|--------|-----------|
| A01 Broken Access Control | RBAC + ownership checks on every resource |
| A02 Cryptographic Failures | bcrypt passwords, TLS in transit, encrypted storage |
| A03 Injection | SQLAlchemy ORM (parameterized), Pydantic input validation |
| A04 Insecure Design | Least privilege, audit logging, consent-based OSINT |
| A05 Security Misconfiguration | Security headers, no debug in prod, env-based config |
| A06 Vulnerable Components | Pinned dependencies, Trivy scanning in CI/CD |
| A07 Auth Failures | JWT + MFA + brute-force rate limiting + token blacklist |
| A08 Integrity Failures | Evidence SHA-256 hashing, signed JWTs |
| A09 Logging Failures | Structured audit logs for all mutations |
| A10 SSRF | httpx with timeout limits, no user-controlled redirects |

---

## Security Headers

All responses include:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## Data Encryption

### In Transit
- All production traffic via TLS 1.2+ (Nginx)
- Internal services communicate within Docker network

### At Rest
- PostgreSQL: Encrypted disk at cloud provider level
- MinIO: Server-side encryption for evidence files
- Sensitive fields (MFA secrets): Consider field-level encryption for high-security deployments

---

## Audit Logging

Every authenticated action is recorded in `audit_logs`:

```json
{
  "user_id": "uuid",
  "action": "scan_created",
  "resource_type": "scan",
  "resource_id": "uuid",
  "ip_address": "1.2.3.4",
  "user_agent": "Mozilla/5.0...",
  "status": "success",
  "created_at": "2024-01-01T00:00:00Z"
}
```

Logged actions include: `user_register`, `login_success`, `login_failed`, `logout`, `mfa_failed`, `scan_created`, `takedown_created`, `finding_updated`, `complaint_created`.

---

## Ethical OSINT Policy

DataShield strictly follows these principles:

1. **Consent-based only** — users scan their own data
2. **Public data only** — no authenticated access to third-party services
3. **Rate limited** — respects target server resources
4. **No credential theft** — password checks use k-Anonymity (no full hash sent)
5. **No private data** — social media checks use public APIs/endpoints only
6. **Audit trail** — every scan is logged with timestamp and user
7. **Legal templates** — takedowns use GDPR/privacy law compliant language
8. **No active scanning** — Shodan queries existing database, no port scanning

---

## Incident Response

1. **Suspected breach**: Rotate `SECRET_KEY` and `JWT_SECRET_KEY` immediately → all tokens invalidated
2. **Compromised account**: Use admin panel to suspend user, review audit logs
3. **Rate limit abuse**: Review `/admin/audit-logs` by IP, block at Nginx
4. **Evidence integrity**: Verify `report_hash` (SHA-256) against downloaded file

---

## Security Checklist for Production

- [ ] Strong random `SECRET_KEY` and `JWT_SECRET_KEY` (64+ chars)
- [ ] All DB/Redis/MinIO passwords changed from defaults
- [ ] `DEBUG=false` in `.env`
- [ ] TLS certificate installed in `nginx/ssl/`
- [ ] Nginx HTTPS redirect enabled
- [ ] Prometheus `/metrics` endpoint blocked externally
- [ ] API docs (`/api/docs`) disabled in production
- [ ] Regular backups of PostgreSQL
- [ ] Grafana admin password changed
- [ ] Docker containers running as non-root users ✅ (already configured)
