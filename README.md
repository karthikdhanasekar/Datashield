# DataShield OSINT

**Privacy Protection Platform** — Discover, Monitor, and Remove Your Exposed Personal Data

---

## OSINT Tools Integrated

DataShield uses **real open-source OSINT tools** — not custom scrapers. Every tool is installed as a Python package and called programmatically.

| Tool | What it does | Install | API Key? |
|---|---|---|---|
| **XposedOrNot** | Email breach check — 17B+ records, **free, no key needed** | HTTP API | ❌ Free |
| **Holehe** | Email registration check on 120+ sites (Twitter, Instagram, Adobe…) | `pip install holehe` | ❌ Free |
| **Maigret** | Username OSINT across **3,000+ platforms** — extracts name, location, bio | `pip install maigret` | ❌ Free |
| **Sherlock** | Username hunt across **400+ social networks** | `pip install sherlock-project` | ❌ Free |
| **Social-Analyzer** | Deep profile metadata extraction across 300+ sites | `pip install social-analyzer` | ❌ Free |
| **SpiderFoot modules** | LeakIX + Hunter.io email reachability + DNS records | HTTP calls | ❌ Free |
| **theHarvester** | Harvest emails, subdomains, names via Google/Bing/DuckDuckGo | `pip install theHarvester` | ❌ Free |
| **Shodan** | Scan internet-exposed infrastructure — open ports, CVEs, banners | `pip install shodan` | ✅ Free tier |
| **HIBP** | HaveIBeenPwned — optional extra coverage (700+ breaches, paste lookups) | API call | ✅ Optional ($3.50/mo) |
| **Pwned Passwords** | k-Anonymity password check against 847M+ leaked passwords | API call | ❌ Free |
| **phonenumbers** | Parse, validate, geo-locate phone numbers | `pip install phonenumbers` | ❌ Free |
| **Ahmia.fi** | Dark web (Tor) index search for data exposure indicators | HTTP API | ❌ Free |
| **Google CSE** | Full-text search + document dorks + LinkedIn/Facebook profile dorks | API call | ✅ Free quota |
| **Bing Search** | Secondary search engine coverage | API call | ✅ Free tier |

---

## How OSINT Routing Works

```
User submits scan (email / username / phone / name / domain)
           │
           ▼
  OsintEngine.run_full_osint()   ← master router
           │
    ┌──────┴──────────────────────────────────┐
    │  scan_type = "email"                    │
    │  ├─ HIBP breach check                   │
    │  ├─ Holehe (120+ site registration)     │
    │  ├─ Pastebin/psbdmp scan                │
    │  ├─ Google + Bing search engine         │
    │  ├─ Social media (GitHub/Reddit/Twitter) │
    │  └─ Document scanner (PDF/CSV/DOCX)     │
    │                                         │
    │  scan_type = "username"                 │
    │  ├─ Maigret (3000+ sites)               │
    │  ├─ Social media profiles               │
    │  ├─ Pastebin scan                       │
    │  └─ Search engine                       │
    │                                         │
    │  scan_type = "phone"                    │
    │  ├─ phonenumbers (parse + validate)     │
    │  ├─ Public directory check              │
    │  ├─ Pastebin scan                       │
    │  └─ Search engine                       │
    │                                         │
    │  scan_type = "name"                     │
    │  ├─ theHarvester (email + subdomain)    │
    │  ├─ Search engine                       │
    │  └─ Document scanner                    │
    └─────────────────────────────────────────┘
           │
           ▼
  ExposureClassifier → severity (low/medium/high/critical)
           │
           ▼
  Findings saved to PostgreSQL
           │
           ▼
  Evidence report generated (PDF + JSON + CSV)
```

---

## Quick Start

```bash
git clone <repo>
cd datashield-osint

# 1. Copy environment template
cp .env.example .env

# 2. Edit .env — minimum required:
#    SECRET_KEY, JWT_SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD
#    Optional for full OSINT: HIBP_API_KEY, GOOGLE_SEARCH_API_KEY, SHODAN_API_KEY

# 3. Start all services
docker-compose up -d

# 4. Run database migrations
docker-compose exec backend alembic upgrade head

# 5. Open platform
# Frontend:   http://localhost:3000
# API Docs:   http://localhost:8000/api/docs  (DEBUG=true only)
# Grafana:    http://localhost:3001
# MinIO:      http://localhost:9001
```

---

## API Keys Setup

All tools work in **demo mode without API keys**. Add keys progressively:

### HIBP (HaveIBeenPwned) — Most Important
```
HIBP_API_KEY=your-key
# Get at: https://haveibeenpwned.com/API/Key  (~$3.50/month)
# Unlocks: email breach lookup across 700+ databases
```

### Google Custom Search — For Search + Document Scanner
```
GOOGLE_SEARCH_API_KEY=your-key
GOOGLE_SEARCH_ENGINE_ID=your-cx
# Get at: https://programmablesearchengine.google.com/
# Free: 100 queries/day  |  Paid: $5 per 1000 queries
```

### Bing Search
```
BING_SEARCH_API_KEY=your-key
# Get at: https://azure.microsoft.com/en-us/services/cognitive-services/bing-web-search-api/
# Free: 1000 transactions/month
```

### Shodan — Infrastructure Scanning
```
SHODAN_API_KEY=your-key
# Get at: https://account.shodan.io/  (free tier available)
# Unlocks: exposed ports, CVEs, server banners for domains
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React, TypeScript, TailwindCSS, Shadcn UI |
| Backend | FastAPI (Python 3.11) |
| OSINT Engine | Holehe, Maigret, theHarvester, Shodan, HIBP, phonenumbers |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Task Queue | Celery + Redis Broker |
| Storage | MinIO (S3-compatible) |
| Monitoring | Prometheus + Grafana |
| Container | Docker + Kubernetes Ready |

---

## Security

- JWT Authentication + TOTP MFA
- RBAC (individual / organization / admin)
- Rate Limiting (60 req/min general, 10 scans/hour)
- Audit Logs — every action logged
- Encryption in Transit (TLS via Nginx)
- Passwords: bcrypt
- Evidence integrity: SHA-256 hashing
- OWASP Top 10 protections

---

## Legal & Ethics

DataShield performs **consent-based OSINT only**:
- ✅ Public data only
- ✅ Respects robots.txt where applicable
- ✅ Rate limited to avoid abuse
- ✅ GDPR compliant
- ❌ No hacking or unauthorized access
- ❌ No credential theft
- ❌ No private data collection

---

## License

Proprietary — DataShield OSINT © 2024
