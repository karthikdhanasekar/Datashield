# DataShield OSINT — Deployment Guide

## Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- 4GB RAM minimum (8GB recommended)
- 20GB disk space

## Quick Start (Development)

```bash
# 1. Clone the repository
git clone <repo-url>
cd datashield-osint

# 2. Configure environment
cp .env.example .env
# Edit .env — set passwords, API keys, etc.

# 3. Start all services
docker-compose up -d

# 4. Run database migrations
docker-compose exec backend alembic upgrade head

# 5. Access the platform
# Frontend: http://localhost:3000
# API:      http://localhost:8000
# API Docs: http://localhost:8000/api/docs (DEBUG=true only)
# MinIO:    http://localhost:9001
# Grafana:  http://localhost:3001
# Prometheus: http://localhost:9090
```

## Production Deployment

### Step 1: Harden .env

```bash
# Generate secure keys
python3 -c "import secrets; print(secrets.token_urlsafe(64))"  # SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(64))"  # JWT_SECRET_KEY

# Use strong passwords for all services
# Set ENVIRONMENT=production
# Set DEBUG=false
# Configure real SMTP credentials
# Add API keys: HIBP_API_KEY, GOOGLE_SEARCH_API_KEY, OPENAI_API_KEY
```

### Step 2: TLS/SSL Setup

```bash
# Create nginx/ssl directory
mkdir -p nginx/ssl

# Copy your SSL certificates
cp your-cert.pem nginx/ssl/cert.pem
cp your-key.pem nginx/ssl/key.pem

# Or use Let's Encrypt with Certbot
docker run --rm -p 80:80 certbot/certbot certonly \
  --standalone -d yourdomain.com -d www.yourdomain.com \
  --agree-tos --email admin@yourdomain.com
```

### Step 3: Update nginx.conf for HTTPS

Uncomment the HTTPS redirect in `nginx/nginx.conf` and add the SSL server block.

### Step 4: Run Production Stack

```bash
docker-compose -f docker-compose.yml up -d
docker-compose exec backend alembic upgrade head
```

## Kubernetes Deployment

Kubernetes manifests are located in `k8s/` (create per your cluster).

Key resources needed:
- Deployments: backend, frontend, celery-worker, celery-beat
- StatefulSets: postgres, redis, elasticsearch
- Services: ClusterIP for internal, LoadBalancer/Ingress for external
- ConfigMaps: nginx config, prometheus config
- Secrets: DATABASE_URL, REDIS_PASSWORD, JWT_SECRET_KEY, etc.
- PersistentVolumeClaims: postgres-data, minio-data, redis-data

## Database Migrations

```bash
# Create a new migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Apply all pending migrations
docker-compose exec backend alembic upgrade head

# Rollback one migration
docker-compose exec backend alembic downgrade -1
```

## Monitoring

- Prometheus: http://localhost:9090 — metrics collection
- Grafana: http://localhost:3001 — dashboards (admin / GRAFANA_PASSWORD)
- Import the included dashboard from `monitoring/grafana/dashboards/`

## Backup

```bash
# PostgreSQL backup
docker-compose exec postgres pg_dump -U datashield datashield > backup_$(date +%Y%m%d).sql

# Restore
docker-compose exec -T postgres psql -U datashield datashield < backup.sql
```

## Troubleshooting

### Backend won't start
```bash
docker-compose logs backend
# Check DATABASE_URL is correct and postgres is healthy
```

### Celery tasks not running
```bash
docker-compose logs celery_worker
# Check CELERY_BROKER_URL matches REDIS_URL
```

### Scan tasks hanging
```bash
# Monitor Celery via Flower
docker-compose exec celery_worker celery -A app.core.celery_app flower --port=5555
```
