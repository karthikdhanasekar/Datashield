# DataShield OSINT — API Reference

Base URL: `http://localhost:8000/api/v1`  
Interactive docs (dev only): `http://localhost:8000/api/docs`

All protected endpoints require: `Authorization: Bearer <access_token>`

---

## Authentication

### POST /auth/register
Register a new user account.

**Body:**
```json
{
  "email": "user@example.com",
  "password": "Strong@Pass1",
  "full_name": "John Doe",
  "phone_number": "+919876543210"
}
```
**Response:** `201 Created` — UserResponse

---

### POST /auth/login
Authenticate and receive JWT tokens.

**Body:**
```json
{
  "email": "user@example.com",
  "password": "Strong@Pass1",
  "mfa_code": "123456"
}
```
**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_role": "individual",
  "mfa_required": false
}
```

---

### POST /auth/refresh
Exchange a refresh token for a new access token.

**Body:** `{ "refresh_token": "eyJ..." }`

---

### POST /auth/logout
Invalidate the current access token.

---

### POST /auth/mfa/setup
Generate TOTP secret and QR code.

**Response:**
```json
{
  "secret": "BASE32SECRET",
  "qr_code": "base64png...",
  "provisioning_uri": "otpauth://totp/..."
}
```

### POST /auth/mfa/verify
Confirm MFA setup with a 6-digit code.

**Body:** `{ "code": "123456" }`

---

### GET /auth/me
Get current user profile.

---

## Scans

### POST /scans/
Create and start an OSINT scan.

**Body:**
```json
{
  "scan_type": "email",
  "query_value": "target@example.com",
  "modules": ["breach", "holehe", "search_engine", "social_media", "paste", "document"]
}
```

**Scan types:** `email` | `username` | `phone` | `name` | `address` | `aadhaar` | `pan` | `passport` | `social_profile` | `full`

**Modules:** `breach` | `holehe` | `maigret` | `social_media` | `search_engine` | `document` | `paste` | `phone` | `shodan`

**Response:** `202 Accepted` — ScanStatusResponse

---

### GET /scans/
List all scans for the current user.

**Query params:** `page`, `page_size`, `status`

---

### GET /scans/{scan_id}
Get scan status + all findings.

**Response:**
```json
{
  "scan": {
    "id": "uuid",
    "scan_type": "email",
    "status": "completed",
    "progress": 100,
    "total_findings": 12,
    "critical_count": 2,
    "high_count": 4,
    "medium_count": 5,
    "low_count": 1,
    "exposure_score": 72.0,
    "modules_run": ["breach", "holehe"],
    "modules_completed": ["breach", "holehe"]
  },
  "findings": [...]
}
```

---

### GET /scans/dashboard/exposure-score
Get user's overall exposure score with recommendations.

---

### GET /scans/{scan_id}/report/{fmt}
Download evidence report. `fmt` = `pdf` | `json` | `csv`

---

### PATCH /scans/findings/{finding_id}
Update finding (mark false positive or verified).

**Body:** `{ "is_false_positive": true }`

---

## Takedowns

### POST /takedowns/preview
Preview generated email before sending.

**Body:**
```json
{
  "finding_id": "uuid",
  "template_type": "gdpr_removal"
}
```

**Template types:** `privacy_removal` | `gdpr_removal` | `right_to_be_forgotten` | `dmca_personal_data`

---

### POST /takedowns/
Create and send a takedown request.

### GET /takedowns/
List all takedown requests. Query: `status`, `page`, `page_size`

### PATCH /takedowns/{id}/status
Update takedown status.

**Body:** `{ "status": "removed", "note": "Confirmed removed" }`

**Status values:** `pending` | `sent` | `acknowledged` | `in_progress` | `removed` | `rejected` | `escalated`

---

## Monitors

### POST /monitors/
Create URL monitor.

**Body:**
```json
{
  "target_url": "https://example.com/leaked-data",
  "monitor_interval": "weekly",
  "alert_on_reappear": true,
  "alert_on_new_leak": true
}
```

### GET /monitors/
List all monitors.

### DELETE /monitors/{id}
Remove a monitor.

---

## Complaints

### POST /complaints/
Generate cybercrime complaint package.

**Body:**
```json
{
  "incident_summary": "My personal data was leaked...",
  "finding_ids": ["uuid1", "uuid2"],
  "jurisdiction": "India",
  "authority_name": "National Cyber Crime Reporting Portal",
  "authority_url": "https://cybercrime.gov.in"
}
```

---

## Notifications

### GET /notifications/
List notifications. Query: `unread_only=true`

### POST /notifications/{id}/read
Mark a notification as read.

### POST /notifications/read-all
Mark all notifications as read.

---

## AI Advisor

### POST /ai/chat
Chat with AI privacy advisor.

**Body:**
```json
{
  "message": "What should I do about my password exposure?",
  "include_context": true
}
```

### POST /ai/analyze
Analyze scan findings with AI.

**Body:** `{ "scan_id": "uuid" }`

---

## Admin (requires admin role)

### GET /admin/users
List all users. Query: `role`, `status`, `page`, `page_size`

### PATCH /admin/users/{id}/status
Update user status. Query: `new_status=active|suspended|inactive`

### PATCH /admin/users/{id}/role
Update user role. Query: `new_role=individual|organization|admin`

### GET /admin/analytics/overview
Platform-wide analytics.

### GET /admin/analytics/exposure-trends
Exposure trend data. Query: `days=30`

### GET /admin/audit-logs
View audit logs. Query: `action`, `page`, `page_size`

---

## Health

### GET /health
Basic health check.

### GET /health/ready
Readiness check — verifies Redis connection.

### GET /metrics
Prometheus metrics (internal only in production).
