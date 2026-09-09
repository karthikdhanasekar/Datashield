# DataShield OSINT — System Architecture

## Overview

DataShield OSINT is built as a cloud-native, microservices-inspired monolith with a clear separation between the API layer, OSINT engine, task queue, and data persistence.

```
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX Reverse Proxy                      │
│                    (Rate Limiting, TLS, Headers)                  │
└────────────────┬──────────────────────┬────────────────────────┘
                 │                      │
        ┌────────▼──────┐     ┌─────────▼────────┐
        │   Next.js 14   │     │   FastAPI Backend  │
        │   Frontend     │     │   (8000)           │
        │   (3000)       │     └─────────┬──────────┘
        └────────────────┘               │
                                ┌────────┴───────────────────────┐
                                │         Core Services           │
                                ├────────────────────────────────┤
                                │  Auth (JWT + MFA)              │
                                │  RBAC (individual/org/admin)   │
                                │  Rate Limiter (slowapi)        │
                                │  Audit Logger                  │
                                │  Prometheus Metrics            │
                                └────────┬───────────────────────┘
                                         │
              ┌──────────────────────────┼─────────────────────────┐
              │                          │                          │
    ┌─────────▼──────┐      ┌────────────▼───────┐    ┌───────────▼──────┐
    │  PostgreSQL     │      │   Redis Cache       │    │  Celery Workers   │
    │  (Primary DB)   │      │   + Sessions        │    │  (Scan/Monitor/   │
    │                 │      │   + Rate Limits     │    │   Notify/Report)  │
    └─────────────────┘      └────────────────────┘    └──────────────────┘
                                                                  │
                                          ┌───────────────────────┤
                          ┌───────────────┘                       │
               ┌──────────▼──────┐                     ┌─────────▼──────┐
               │  OSINT Engine   │                     │  External APIs  │
               ├─────────────────┤                     ├────────────────┤
               │  BreachMonitor  │                     │  HIBP API       │
               │  SearchEngine   │                     │  Google Search  │
               │  SocialMedia    │                     │  Bing Search    │
               │  DocumentScan   │                     │  OpenAI GPT-4   │
               │  ExposureClass  │                     │  Twilio SMS     │
               └─────────────────┘                     └────────────────┘
```

## Data Flow

### Scan Request Flow
```
User → POST /api/v1/scans/ → Create ScanRequest (PENDING)
     → Dispatch Celery task → run_osint_scan()
     → Run modules in parallel → breach, search, social, document
     → Classify severity → ExposureClassifier
     → Persist Finding records → PostgreSQL
     → Calculate exposure score → Update ScanRequest
     → Create notification → Notification table
     → User polls GET /api/v1/scans/{id} → get results
```

### Takedown Flow
```
User → POST /api/v1/takedowns/ → Discover website contacts (WHOIS)
     → Generate email from template → GDPR/Privacy/RTBF
     → Store TakedownRequest → status: PENDING
     → Celery: send_takedown_request_task → SMTP send
     → status → SENT → next_follow_up_at = +14 days
     → Celery Beat: send_pending_reminders → daily
     → After 3 follow-ups → auto ESCALATED
     → User: mark as REMOVED → Finding.is_removed = True
```

### Monitoring Flow
```
Celery Beat: run_monitoring_cycle (hourly)
     → Select all active MonitorConfig where next_check_at <= now
     → Dispatch check_single_monitor per URL
     → HTTP HEAD request → check accessibility
     → Record MonitorCheckHistory
     → If status changed to "exposed" after "removed" → alert notification
```

## Database Schema

### Core Tables
- `users` — User accounts, roles, MFA, verification
- `organizations` — Organization/team accounts
- `user_sessions` — Active JWT sessions
- `audit_logs` — All user actions

### Scan Tables
- `scan_requests` — Scan jobs and status
- `findings` — Individual exposure records
- `evidence_reports` — Generated PDF/JSON/CSV reports

### Takedown Tables
- `takedown_requests` — Removal requests
- `takedown_status_history` — Status change timeline
- `monitor_configs` — URL monitoring configuration
- `monitor_check_history` — Check results
- `cybercrime_complaints` — Complaint packages

### Notification Tables
- `notifications` — User notification records

## Security Architecture

### Authentication
- JWT access tokens (30 min expiry)
- JWT refresh tokens (7 day expiry)
- Token blacklist via Redis (logout revocation)
- TOTP-based MFA (Google Authenticator compatible)
- Backup codes (8 codes, SHA-256 hashed)

### Authorization
- RBAC: individual → organization → admin
- All routes protected with `get_current_active_user`
- Sensitive routes require email verification

### Data Protection
- Passwords: bcrypt with automatic salting
- Evidence hashes: SHA-256
- Sensitive search values masked in display (Aadhaar, PAN, phone)
- Database SSL in production
- S3/MinIO for evidence file storage (not in DB)

### Input Validation
- Pydantic v2 schema validation on all inputs
- Query value sanitization and length limits
- SQL injection prevention via SQLAlchemy ORM
- XSS protection via security headers

### Rate Limiting
- 60 requests/minute per IP (general)
- 10 scans/hour per user
- 5 login attempts/minute per IP
- Nginx upstream rate limiting as additional layer

## Scalability

### Horizontal Scaling
- Backend: stateless FastAPI, scale with multiple replicas
- Celery workers: scale independently by queue
- All state in PostgreSQL + Redis (no local state)

### Queue Architecture
```
Queue: scans        → run_osint_scan tasks (CPU/IO intensive)
Queue: monitoring   → check_single_monitor tasks (IO bound)
Queue: notifications → email/SMS delivery
Queue: takedowns    → email sending
Queue: reports      → PDF/CSV generation
```

### Caching Strategy
- Exposure score: cached 1 hour per user
- API responses: React Query client-side caching
- Session data: Redis with TTL matching token expiry
