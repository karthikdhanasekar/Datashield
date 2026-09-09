# DataShield OSINT — Developer Setup Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Docker Desktop | 24+ | Required |
| Docker Compose | v2+ | Bundled with Docker Desktop |
| Git | Any | |

---

## Quick Start (5 commands)

```bash
git clone <repo-url> datashield-osint
cd datashield-osint

# 1. Copy env template
cp .env.example .env   # or edit .env directly — dev defaults are already set

# 2. Build the base image (only needed once, ~10 min)
docker build -f backend/Dockerfile.base -t datashield-base:latest backend/

# 3. Build app images (fast, ~30s)
docker build -t datashield-osint-backend:latest \
             -t datashield-osint-celery_worker:latest \
             -t datashield-osint-celery_beat:latest backend/

# 4. Start all services
docker compose -f docker-compose.dev.yml up -d

# 5. Run database migrations
docker exec -u root -e PYTHONPATH=/app datashield_backend \
  alembic upgrade head
```

Open **http://localhost:3000** — you're live.

---

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend | 3000 | http://localhost:3000 |
| Backend API | 8000 | http://localhost:8000 |
| API Docs | 8000 | http://localhost:8000/api/docs *(DEBUG=true)* |
| Flower (Celery monitor) | 5555 | http://localhost:5555 |
| MinIO console | 9001 | http://localhost:9001 |
| **Optional: Grafana** | 3001 | `--profile monitoring` |
| **Optional: Prometheus** | 9090 | `--profile monitoring` |
| **Optional: Elasticsearch** | 9200 | `--profile search` |

---

## Optional Monitoring Stack

```bash
# Enable Prometheus + Grafana
docker compose -f docker-compose.dev.yml --profile monitoring up -d
# → Grafana: http://localhost:3001 (admin / grafana_dev_pass_2024)

# Enable Elasticsearch (full-text search — requires ~1 GB RAM)
docker compose -f docker-compose.dev.yml --profile search up -d
# (without ES, search falls back to PostgreSQL ILIKE — works fine)
```

---

## Create First Admin User

```bash
docker exec -u root -e PYTHONPATH=/app datashield_backend \
  python scripts/create_admin.py
```

Default credentials: `admin@datashield.com` / `Admin@DataShield2024!`

Override with env vars:
```bash
ADMIN_EMAIL=you@company.com ADMIN_PASSWORD=YourPass@123 \
  docker exec -u root -e PYTHONPATH=/app \
    -e ADMIN_EMAIL=you@company.com \
    -e ADMIN_PASSWORD=YourPass@123 \
  datashield_backend python scripts/create_admin.py
```

---

## Run Tests

```bash
# Full test suite (105 tests) inside the container
docker exec -e PYTHONPATH=/app datashield_backend pytest tests/ -v

# Quick summary only
docker exec -e PYTHONPATH=/app datashield_backend pytest tests/ -q

# Specific test file
docker exec -e PYTHONPATH=/app datashield_backend pytest tests/test_integration.py -v
```

---

## OSINT API Keys (Optional)

The platform works **without any API keys** using free/fallback sources:

| What works free (no key) | What needs a key |
|--------------------------|-----------------|
| XposedOrNot breach check (17B+ records) | HIBP (extra breach coverage) |
| Holehe email registration (120+ sites) | Google CSE (document dorks, LinkedIn/Facebook dorks) |
| Maigret username (3000+ sites) | Bing Search (secondary search) |
| Sherlock username (400+ sites) | Shodan (infrastructure scans) |
| Social-Analyzer (300+ sites) | OpenAI (AI Privacy Advisor) |
| SpiderFoot modules (LeakIX, Hunter.io, DNS) | Twilio (SMS alerts) |
| Ahmia dark web indicators | SMTP (email alerts) |
| Pwned Passwords k-anonymity | Telegram (instant alerts — free but needs bot setup) |

### Adding keys to `.env`

```env
# Breach — optional extra coverage (~$3.50/mo)
HIBP_API_KEY=your-key                 # https://haveibeenpwned.com/API/Key

# Search engine dorks (LinkedIn, Facebook, documents)
GOOGLE_SEARCH_API_KEY=AIzaSy...       # https://console.cloud.google.com
GOOGLE_SEARCH_ENGINE_ID=017abc...     # https://programmablesearchengine.google.com

# Bing backup
BING_SEARCH_API_KEY=your-key          # https://portal.azure.com → Bing Search v7

# Infrastructure scan (free tier)
SHODAN_API_KEY=your-key               # https://account.shodan.io

# AI Advisor
OPENAI_API_KEY=sk-proj-...            # https://platform.openai.com/api-keys

# Telegram instant alerts (free — see Settings → Notifications for setup guide)
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_DEFAULT_CHAT_ID=123456789
```

After editing `.env`, reload the containers:
```bash
docker compose -f docker-compose.dev.yml up -d --force-recreate --no-deps backend celery_worker
```

---

## Live Scan Test

After setup, verify the full pipeline works:

1. Open http://localhost:3000
2. Register → Login (you can verify email in the backend logs)
3. Go to **New Scan** → choose **Email** → enter any email
4. Watch the real-time scan progress (WebSocket-powered)
5. Results appear in **Findings** after scan completes

Expected findings for known test emails:
```
test@adobe.com    → 11 breaches (Adobe, LinkedIn, ShareThis, etc.)
testinghypothesis2@gmail.com → Twitter (HIGH), Instagram (HIGH),
                               Replit (MEDIUM), Google Scholar (MEDIUM)
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Backend won't start | `docker logs datashield_backend` — usually DB connection issue |
| Migrations fail | Ensure postgres is healthy: `docker ps` → check `(healthy)` |
| Celery tasks stuck | `docker logs datashield_celery_worker` |
| Scans stuck at 0% | Redis must be running: `docker exec datashield_redis redis-cli ping` |
| MinIO 403 | Check `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` in `.env` match |
| ES connection errors | Expected when running without `--profile search` — graceful fallback |
| social-analyzer not importable | Rebuild base image to install to system site-packages |
| psbdmp DNS fails | Expected — psbdmp.ws DNS blocked; paste search degrades gracefully |

---

## Project Structure

```
datashield-osint/
├── backend/
│   ├── app/
│   │   ├── api/v1/              REST API endpoints
│   │   ├── core/                Config, DB, security, Redis
│   │   ├── models/              SQLAlchemy ORM models
│   │   ├── osint/               19 OSINT tool adapters
│   │   │   ├── osint_engine.py          Master orchestrator
│   │   │   ├── breach_monitor.py        XposedOrNot + HIBP
│   │   │   ├── holehe_adapter.py        Email registration (120+ sites)
│   │   │   ├── maigret_adapter.py       Username OSINT (3000+ sites)
│   │   │   ├── sherlock_adapter.py      Username hunt (400+ sites)
│   │   │   ├── social_analyzer_adapter.py  Profile metadata (300+ sites)
│   │   │   ├── spiderfoot_adapter.py    LeakIX + Hunter.io + DNS
│   │   │   ├── theharvester_adapter.py  Email/subdomain harvest
│   │   │   ├── linkedin_osint.py        LinkedIn via search dorks
│   │   │   ├── instagram_osint.py       Instagram + Facebook
│   │   │   ├── darkweb_osint.py         Ahmia dark web indicators
│   │   │   ├── shodan_adapter.py        Infrastructure scanning
│   │   │   ├── search_engine.py         Google + Bing
│   │   │   ├── social_media.py          GitHub/Reddit/Twitter
│   │   │   ├── pastebin_scraper.py      Paste site search
│   │   │   ├── phone_osint.py           Phone number OSINT
│   │   │   ├── document_scanner.py      PDF/doc exposure
│   │   │   ├── username_osint.py        Sherlock-style HTTP (50+ sites)
│   │   │   └── exposure_classifier.py   Severity scoring
│   │   ├── schemas/             Pydantic models
│   │   ├── services/            Business logic
│   │   │   ├── notification_service.py  Email + SMS + Telegram
│   │   │   ├── report_service.py        PDF/JSON/CSV reports
│   │   │   ├── takedown_service.py      GDPR/DMCA takedowns
│   │   │   ├── ai_advisor.py            GPT-4o privacy advisor
│   │   │   └── elasticsearch_service.py Search indexing
│   │   └── tasks/               Celery async tasks
│   ├── scripts/
│   │   └── create_admin.py      Admin user creation
│   ├── tests/                   105 tests (auth, OSINT, scans, integration)
│   ├── Dockerfile
│   └── Dockerfile.base          Base image with all deps
├── frontend/
│   └── src/app/dashboard/       23 pages
│       ├── page.tsx             Dashboard
│       ├── scan/                New scan + live status (WebSocket)
│       ├── findings/            Finding viewer
│       ├── search/              Full-text search + export
│       ├── takedowns/           Takedown management
│       ├── monitoring/          URL monitoring
│       ├── reports/             Evidence reports
│       ├── ai-advisor/          AI chat
│       └── settings/            Profile + MFA + Telegram setup
├── nginx/                       Reverse proxy config
├── monitoring/                  Prometheus + Grafana dashboards
├── k8s/                         Kubernetes manifests
├── docs/                        API, architecture, deployment, security
├── docker-compose.yml           Production stack
├── docker-compose.dev.yml       Dev stack (profiles: monitoring, search)
└── .env                         Environment config
```
