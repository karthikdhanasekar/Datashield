# DataShield OSINT — Complete Deployment Guide
> **Step-by-Step Setup for Development, Staging, and Production**

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Development)](#quick-start-development)
3. [Production Deployment - Docker Compose](#production-deployment---docker-compose)
4. [Production Deployment - Kubernetes](#production-deployment---kubernetes)
5. [Post-Deployment Configuration](#post-deployment-configuration)
6. [Verification & Testing](#verification--testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

| Tool | Version | Purpose | Installation |
|------|---------|---------|--------------|
| **Docker** | 24.0+ | Container runtime | [Get Docker](https://docs.docker.com/get-docker/) |
| **Docker Compose** | v2.0+ | Multi-container orchestration | Included with Docker Desktop |
| **Git** | 2.0+ | Version control | [Get Git](https://git-scm.com/downloads) |
| **kubectl** | 1.24+ | Kubernetes CLI (for K8s deployment) | [Install kubectl](https://kubernetes.io/docs/tasks/tools/) |
| **Helm** | 3.0+ | Kubernetes package manager (optional) | [Install Helm](https://helm.sh/docs/intro/install/) |

### System Requirements

#### Development
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Disk**: 20 GB free space

#### Production (Minimum)
- **CPU**: 8 cores
- **RAM**: 16 GB
- **Disk**: 100 GB SSD

#### Production (Recommended)
- **CPU**: 16 cores
- **RAM**: 32 GB
- **Disk**: 200 GB SSD
- **Nodes**: 3+ (for Kubernetes)

### API Keys (Optional but Recommended)

| Service | Purpose | Free Tier | Link |
|---------|---------|-----------|------|
| **HIBP** | Breach detection | No (paid) | [haveibeenpwned.com](https://haveibeenpwned.com/API/Key) |
| **Google CSE** | Search & document discovery | Yes | [Google CSE](https://programmablesearchengine.google.com/) |
| **Shodan** | Infrastructure scanning | Yes | [Shodan](https://account.shodan.io/) |
| **OpenAI** | AI Privacy Advisor | Free trial | [OpenAI](https://platform.openai.com/api-keys) |
| **Twilio** | SMS alerts | Free trial | [Twilio](https://www.twilio.com/) |

---

## Quick Start (Development)

### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-org/datashield-osint.git
cd datashield-osint

# Verify files
ls -la
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration (use your preferred editor)
nano .env
# Or
code .env
```

**Minimum required settings** in `.env`:
```env
SECRET_KEY=your-secret-key-min-32-chars
JWT_SECRET_KEY=your-jwt-secret-key
POSTGRES_PASSWORD=strong_password_123
REDIS_PASSWORD=redis_password_123
MINIO_ROOT_PASSWORD=minio_password_123
```

### Step 3: Build Base Image (First Time Only)

```bash
# This takes ~10 minutes (one-time setup)
docker build -f backend/Dockerfile.base -t datashield-base:latest backend/

# Verify build
docker images | grep datashield-base
```

### Step 4: Build Application Images

```bash
# Build all application images (~2 minutes)
docker build -t datashield-osint-backend:latest backend/

# Verify
docker images | grep datashield-osint
```

### Step 5: Start Services

```bash
# Start all services in development mode
docker compose -f docker-compose.dev.yml up -d

# Check status
docker compose ps
```

**Expected output**:
```
NAME                    STATUS      PORTS
datashield_backend      running     0.0.0.0:8000->8000/tcp
datashield_celery_worker running
datashield_celery_beat  running
datashield_elasticsearch running    0.0.0.0:9200->9200/tcp
datashield_flower       running     0.0.0.0:5555->5555/tcp
datashield_frontend     running     0.0.0.0:3000->3000/tcp
datashield_minio        running     0.0.0.0:9000-9001->9000-9001/tcp
datashield_postgres     running     0.0.0.0:5432->5432/tcp
datashield_redis        running     0.0.0.0:6379->6379/tcp
```

### Step 6: Initialize Database

```bash
# Wait for PostgreSQL to be ready (check logs)
docker compose logs postgres | grep "ready to accept connections"

# Run migrations
docker exec -u root -e PYTHONPATH=/app datashield_backend \
  alembic upgrade head

# Verify migrations
docker exec -u root -e PYTHONPATH=/app datashield_backend \
  alembic current
```

### Step 7: Create Admin User

```bash
# Create default admin user
docker exec -u root -e PYTHONPATH=/app datashield_backend \
  python scripts/create_admin.py

# Default credentials will be displayed:
# Email: admin@datashield.com
# Password: Admin@DataShield2024!
```

### Step 8: Access Application

Open your browser and navigate to:

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/docs
- **Celery Monitor**: http://localhost:5555
- **MinIO Console**: http://localhost:9001

**Login** with the admin credentials from Step 7.

### Step 9: Run a Test Scan

1. Go to http://localhost:3000
2. Login with admin credentials
3. Click **New Scan**
4. Select **Email** scan type
5. Enter: `test@adobe.com`
6. Click **Start Scan**
7. Watch real-time progress
8. View results in **Findings**

### Step 10: Enable Monitoring (Optional)

```bash
# Start monitoring stack
docker compose -f docker-compose.dev.yml --profile monitoring up -d

# Access dashboards
# Grafana: http://localhost:3001 (admin / grafana_dev_pass_2024)
# Prometheus: http://localhost:9090
```

---

## Production Deployment - Docker Compose

### Prerequisites Check

```bash
# Verify Docker version
docker --version
# Should be 24.0.0 or higher

# Verify Docker Compose version
docker compose version
# Should be v2.0.0 or higher

# Check available resources
docker system info | grep -E "CPUs|Total Memory"
```

### Step 1: Prepare Production Environment

```bash
# Navigate to project directory
cd datashield-osint

# Copy production environment template
cp .env.production .env

# Generate secure secrets
openssl rand -hex 32  # For SECRET_KEY
openssl rand -hex 32  # For JWT_SECRET_KEY
openssl rand -base64 32  # For POSTGRES_PASSWORD
```

### Step 2: Configure Production Settings

Edit `.env` with your production values:

```env
# ══════════════════════════════════════════════════════════════════════════════
# REQUIRED - Update these values
# ══════════════════════════════════════════════════════════════════════════════
SECRET_KEY=<generated-secret-key-from-step-1>
JWT_SECRET_KEY=<generated-jwt-secret-from-step-1>
POSTGRES_PASSWORD=<generated-db-password-from-step-1>
REDIS_PASSWORD=<strong-redis-password>
MINIO_ACCESS_KEY=<20-char-access-key>
MINIO_SECRET_KEY=<40-char-secret-key>

# Environment
ENVIRONMENT=production
DEBUG=false

# Domain (replace with your domain)
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
APP_DOMAIN=yourdomain.com

# ══════════════════════════════════════════════════════════════════════════════
# OPTIONAL - API Keys
# ══════════════════════════════════════════════════════════════════════════════
HIBP_API_KEY=your-hibp-key
GOOGLE_SEARCH_API_KEY=your-google-key
GOOGLE_SEARCH_ENGINE_ID=your-search-engine-id
SHODAN_API_KEY=your-shodan-key
OPENAI_API_KEY=sk-your-openai-key

# ══════════════════════════════════════════════════════════════════════════════
# EMAIL - For notifications
# ══════════════════════════════════════════════════════════════════════════════
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
EMAIL_FROM=noreply@yourdomain.com

# ══════════════════════════════════════════════════════════════════════════════
# MONITORING - Alert emails
# ══════════════════════════════════════════════════════════════════════════════
ALERT_EMAIL_CRITICAL=oncall@yourdomain.com
ALERT_EMAIL_WARNINGS=team@yourdomain.com
```

### Step 3: Configure SSL Certificates

#### Option A: Let's Encrypt (Recommended)

```bash
# Create SSL directory
mkdir -p nginx/ssl

# Install certbot (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install certbot

# Generate certificate (replace with your domain)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/

# Set permissions
sudo chmod 644 nginx/ssl/*.pem
```

#### Option B: Self-Signed (Testing Only)

```bash
# Create self-signed certificate
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=yourdomain.com"
```

### Step 4: Update Nginx Configuration

Edit `nginx/nginx.prod.conf` and replace `yourdomain.com` with your actual domain:

```bash
# Replace domain in nginx config
sed -i 's/yourdomain.com/your-actual-domain.com/g' nginx/nginx.prod.conf
```

### Step 5: Build Production Images

```bash
# Build base image (if not already built)
docker build -f backend/Dockerfile.base -t datashield-base:latest backend/

# Build production images with version tag
export VERSION=1.0.0
docker build -t datashield-osint-backend:${VERSION} backend/
docker build -t datashield-osint-frontend:${VERSION} frontend/

# Tag as latest
docker tag datashield-osint-backend:${VERSION} datashield-osint-backend:latest
docker tag datashield-osint-frontend:${VERSION} datashield-osint-frontend:latest
```

### Step 6: Initialize Database

```bash
# Start only database first
docker compose -f docker-compose.prod.yml up -d postgres redis

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
until docker exec datashield_postgres pg_isready -U datashield > /dev/null 2>&1; do
  echo -n "."
  sleep 2
done
echo " Ready!"

# Run migrations
docker compose -f docker-compose.prod.yml run --rm backend \
  alembic upgrade head
```

### Step 7: Start All Services

```bash
# Start all services
docker compose -f docker-compose.prod.yml up -d

# Verify all containers are running
docker compose -f docker-compose.prod.yml ps

# Check logs for any errors
docker compose -f docker-compose.prod.yml logs --tail=50
```

### Step 8: Create Admin User

```bash
# Create admin with custom credentials
docker compose -f docker-compose.prod.yml exec backend \
  python scripts/create_admin.py

# Or specify custom email/password
ADMIN_EMAIL=admin@yourdomain.com ADMIN_PASSWORD=YourSecurePass123! \
docker compose -f docker-compose.prod.yml exec \
  -e ADMIN_EMAIL=admin@yourdomain.com \
  -e ADMIN_PASSWORD=YourSecurePass123! \
  backend python scripts/create_admin.py
```

### Step 9: Configure DNS

Point your domain to the server IP:

```bash
# Get server IP
curl ifconfig.me

# Add DNS records (at your DNS provider):
# A record:     yourdomain.com → YOUR_SERVER_IP
# A record:     www.yourdomain.com → YOUR_SERVER_IP
# A record:     api.yourdomain.com → YOUR_SERVER_IP (if using subdomain)
```

### Step 10: Enable Monitoring & Backups

```bash
# Start monitoring stack
docker compose -f docker-compose.prod.yml --profile monitoring up -d

# Verify monitoring
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3001/api/health # Grafana

# Setup automated backups
chmod +x scripts/backup/backup-database.sh

# Test backup
./scripts/backup/backup-database.sh

# Add to crontab for daily backups at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /path/to/datashield-osint/scripts/backup/backup-database.sh") | crontab -
```

---

## Production Deployment - Kubernetes

### Prerequisites

```bash
# Verify kubectl
kubectl version --client

# Verify cluster access
kubectl cluster-info

# Verify cluster resources
kubectl top nodes
```

### Step 1: Install Prerequisites

```bash
# Install cert-manager for SSL
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Install ingress-nginx
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# Verify installations
kubectl wait --namespace cert-manager \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/instance=cert-manager \
  --timeout=120s

kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

### Step 2: Create Namespace

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Verify
kubectl get namespace datashield
```

### Step 3: Configure Secrets

```bash
# Copy secrets template
cp k8s/secrets.yaml k8s/secrets-prod.yaml

# Generate secrets
echo "SECRET_KEY=$(openssl rand -hex 32)" >> k8s/secrets-prod.yaml
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> k8s/secrets-prod.yaml

# Edit secrets file with your values
nano k8s/secrets-prod.yaml

# Apply secrets (NEVER commit this file!)
kubectl apply -f k8s/secrets-prod.yaml

# Verify (values will be base64 encoded)
kubectl get secret datashield-secrets -n datashield
```

### Step 4: Update ConfigMap

```bash
# Edit configmap with your domain
nano k8s/configmap.yaml

# Update these values:
# - ALLOWED_ORIGINS
# - EMAIL_FROM
# - Any other environment-specific settings

# Apply configmap
kubectl apply -f k8s/configmap.yaml
```

### Step 5: Update Ingress Configuration

```bash
# Edit ingress with your domain
nano k8s/ingress.yaml

# Replace all instances of 'yourdomain.com' with your actual domain
sed -i 's/yourdomain.com/your-actual-domain.com/g' k8s/ingress.yaml

# Update cert-manager issuer email
nano k8s/cert-manager-issuer.yaml
# Change: email: admin@yourdomain.com

# Apply cert-manager configuration
kubectl apply -f k8s/cert-manager-issuer.yaml
```

### Step 6: Build and Push Images

```bash
# Tag for your registry (e.g., GitHub Container Registry)
export REGISTRY=ghcr.io/your-org
export VERSION=1.0.0

# Build images
docker build -t ${REGISTRY}/datashield-backend:${VERSION} backend/
docker build -t ${REGISTRY}/datashield-frontend:${VERSION} frontend/

# Login to registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Push images
docker push ${REGISTRY}/datashield-backend:${VERSION}
docker push ${REGISTRY}/datashield-frontend:${VERSION}

# Update image references in deployment files
find k8s/ -name "*.yaml" -exec sed -i \
  "s|ghcr.io/your-org|${REGISTRY}|g" {} \;
```

### Step 7: Deploy Infrastructure Components

```bash
# Deploy in order:

# 1. PostgreSQL
kubectl apply -f k8s/postgres-statefulset.yaml

# 2. Redis
kubectl apply -f k8s/redis-statefulset.yaml

# 3. Elasticsearch
kubectl apply -f k8s/elasticsearch-statefulset.yaml

# 4. MinIO
kubectl apply -f k8s/minio-statefulset.yaml

# Wait for all to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n datashield --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n datashield --timeout=300s
kubectl wait --for=condition=ready pod -l app=elasticsearch -n datashield --timeout=300s
kubectl wait --for=condition=ready pod -l app=minio -n datashield --timeout=300s
```

### Step 8: Run Database Migrations

```bash
# Create migration job
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  namespace: datashield
spec:
  template:
    spec:
      containers:
      - name: migration
        image: ${REGISTRY}/datashield-backend:${VERSION}
        command: ["alembic", "upgrade", "head"]
        envFrom:
        - configMapRef:
            name: datashield-config
        - secretRef:
            name: datashield-secrets
      restartPolicy: Never
  backoffLimit: 3
EOF

# Wait for migration to complete
kubectl wait --for=condition=complete job/db-migration -n datashield --timeout=300s

# Check migration logs
kubectl logs job/db-migration -n datashield
```

### Step 9: Deploy Application

```bash
# Deploy backend, frontend, and workers
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml

# Deploy networking
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/network-policies.yaml

# Deploy high availability configs
kubectl apply -f k8s/pod-disruption-budget.yaml
kubectl apply -f k8s/resource-quotas.yaml

# Or deploy everything at once with Kustomize
kubectl apply -k k8s/
```

### Step 10: Verify Deployment

```bash
# Check all pods
kubectl get pods -n datashield

# Check services
kubectl get svc -n datashield

# Check ingress
kubectl get ingress -n datashield

# Get external IP
kubectl get svc -n ingress-nginx

# Check SSL certificate
kubectl describe certificate datashield-tls-cert -n datashield

# View logs
kubectl logs -f deployment/datashield-backend -n datashield
```

### Step 11: Configure DNS

```bash
# Get ingress external IP
EXTERNAL_IP=$(kubectl get svc ingress-nginx-controller \
  -n ingress-nginx \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "Configure your DNS:"
echo "A record: yourdomain.com → $EXTERNAL_IP"
echo "A record: www.yourdomain.com → $EXTERNAL_IP"
echo "A record: api.yourdomain.com → $EXTERNAL_IP"
```

### Step 12: Create Admin User

```bash
# Get backend pod name
BACKEND_POD=$(kubectl get pod -n datashield -l app=datashield-backend -o jsonpath='{.items[0].metadata.name}')

# Create admin user
kubectl exec -it $BACKEND_POD -n datashield -- \
  python scripts/create_admin.py

# Or with custom credentials
kubectl exec -it $BACKEND_POD -n datashield -- \
  env ADMIN_EMAIL=admin@yourdomain.com ADMIN_PASSWORD=SecurePass123! \
  python scripts/create_admin.py
```

### Step 13: Enable Monitoring

```bash
# Deploy ServiceMonitor for Prometheus Operator
kubectl apply -f k8s/service-monitor.yaml

# Or install Prometheus stack with Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.adminPassword=YourGrafanaPassword

# Port-forward to access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Access: http://localhost:3000 (admin / YourGrafanaPassword)
```

### Step 14: Setup Automated Backups

```bash
# Deploy backup CronJob
kubectl apply -f k8s/backup-cronjob.yaml

# Verify CronJob
kubectl get cronjob -n datashield

# Manually trigger backup to test
kubectl create job --from=cronjob/database-backup manual-backup -n datashield

# Check backup job status
kubectl get jobs -n datashield
kubectl logs job/manual-backup -n datashield
```

---

## Post-Deployment Configuration

### 1. SSL Certificate Verification

```bash
# Docker Compose
curl -I https://yourdomain.com

# Kubernetes
kubectl describe certificate datashield-tls-cert -n datashield

# Check certificate expiry
echo | openssl s_client -servername yourdomain.com -connect yourdomain.com:443 2>/dev/null | \
  openssl x509 -noout -dates
```

### 2. Configure Email Notifications

Test email configuration:

```bash
# Docker Compose
docker compose exec backend python -c "
from app.services.notification_service import send_email
send_email('test@example.com', 'Test', 'Email configuration works!')
"

# Kubernetes
kubectl exec -it $BACKEND_POD -n datashield -- python -c "
from app.services.notification_service import send_email
send_email('test@example.com', 'Test', 'Email configuration works!')
"
```

### 3. Configure Alert Notifications

```bash
# Update Alertmanager configuration with your details
# Docker Compose: Edit monitoring/alertmanager.yml
# Kubernetes: Create/update alertmanager ConfigMap

# Test Slack webhook
curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test alert from DataShield OSINT"}'
```

### 4. Setup Backups to S3

```bash
# Configure AWS CLI or MinIO client
aws configure
# OR for MinIO
mc alias set myminio https://minio.yourdomain.com ACCESS_KEY SECRET_KEY

# Test backup upload
./scripts/backup/backup-database.sh

# Verify backup in S3
aws s3 ls s3://datashield-backups/
```

### 5. Import Grafana Dashboards

```bash
# Access Grafana
# Docker: http://localhost:3001
# Kubernetes: kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Import dashboards:
# 1. Node Exporter Full (ID: 1860)
# 2. PostgreSQL Database (ID: 9628)
# 3. Redis Dashboard (ID: 11835)
# 4. Nginx Overview (ID: 12708)

# Go to: Dashboards → Import → Enter dashboard ID
```

---

## Verification & Testing

### Health Check

```bash
# Check backend health
curl https://yourdomain.com/health

# Expected response:
# {"status":"healthy","timestamp":"2024-01-15T10:00:00Z","version":"1.0.0"}
```

### API Documentation

```bash
# Access API docs (if DEBUG=true or explicitly enabled)
open https://yourdomain.com/api/docs
```

### Run Test Scan

```bash
# Via UI
1. Login to https://yourdomain.com
2. Go to "New Scan"
3. Select "Email" scan type
4. Enter: test@adobe.com
5. Click "Start Scan"
6. Expected: 10+ breach findings

# Via API
curl -X POST https://yourdomain.com/api/v1/scans/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "email",
    "target": "test@adobe.com"
  }'
```

### Monitoring Verification

```bash
# Check Prometheus targets
curl http://prometheus.yourdomain.com/api/v1/targets

# Check if alerts are loaded
curl http://prometheus.yourdomain.com/api/v1/rules

# Trigger test alert (stop backend to trigger ServiceDown)
docker compose stop backend  # or kubectl scale deployment datashield-backend --replicas=0

# Check Alertmanager
curl http://alertmanager.yourdomain.com/api/v1/alerts
```

### Performance Test

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Simple load test (100 requests, 10 concurrent)
ab -n 100 -c 10 https://yourdomain.com/health

# Check metrics
curl http://prometheus.yourdomain.com/api/v1/query?query=http_requests_total
```

---

## Troubleshooting

### Services Won't Start

```bash
# Docker Compose
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100

# Kubernetes
kubectl get pods -n datashield
kubectl describe pod POD_NAME -n datashield
kubectl logs POD_NAME -n datashield
```

### Database Connection Issues

```bash
# Test database connection
# Docker
docker compose exec backend python -c "
from app.core.database import engine
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('Database connection OK')
"

# Kubernetes
kubectl exec -it $BACKEND_POD -n datashield -- python -c "
from app.core.database import engine
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('Database connection OK')
"
```

### SSL Certificate Issues

```bash
# Check certificate
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Renew Let's Encrypt certificate
sudo certbot renew

# Check cert-manager (Kubernetes)
kubectl get certificate -n datashield
kubectl describe certificate datashield-tls-cert -n datashield
```

### High Memory Usage

```bash
# Check container memory
docker stats

# Kubernetes
kubectl top pods -n datashield

# Restart high-memory pods
docker compose restart backend
# or
kubectl rollout restart deployment datashield-backend -n datashield
```

### Backup Failures

```bash
# Check backup logs
tail -f /var/backups/datashield/backup.log

# Test backup manually
./scripts/backup/backup-database.sh

# Verify S3 access
aws s3 ls s3://datashield-backups/ --region us-east-1
```

### Application Errors

```bash
# View application logs
docker compose logs -f backend

# Kubernetes
kubectl logs -f deployment/datashield-backend -n datashield

# Check for common issues:
# 1. Missing environment variables
# 2. Database migration not run
# 3. Redis connection failed
# 4. Elasticsearch not ready
```

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| **Port already in use** | `docker compose down` or change port in `.env` |
| **Out of disk space** | Run `docker system prune -a` to clean up |
| **Migration fails** | Ensure database is ready, check logs |
| **Frontend can't connect to backend** | Verify `NEXT_PUBLIC_API_URL` in `.env` |
| **SSL certificate not issued** | Check DNS, cert-manager logs, rate limits |
| **Pods crashlooping** | Check resource limits, logs, configuration |
| **Slow performance** | Scale up resources, check database queries |
| **Backups not running** | Verify cron/CronJob, check permissions |

---

## Security Checklist

Before going live, verify:

- [ ] All secrets are strong and unique
- [ ] SSL/TLS certificates are valid
- [ ] Firewall rules are configured
- [ ] Database is not publicly accessible
- [ ] Admin password has been changed
- [ ] Rate limiting is enabled
- [ ] Backups are automated and tested
- [ ] Monitoring alerts are configured
- [ ] Security headers are enabled
- [ ] CORS is properly configured

---

## Performance Optimization

### Database

```sql
-- Create indexes for frequently queried columns
CREATE INDEX idx_scans_user_id ON scans(user_id);
CREATE INDEX idx_scans_created_at ON scans(created_at);
CREATE INDEX idx_findings_scan_id ON findings(scan_id);
CREATE INDEX idx_findings_severity ON findings(severity);
```

### Redis Caching

```python
# Example: Cache frequently accessed data
from app.core.redis_client import redis_client

# Cache user profile for 1 hour
redis_client.setex(f"user:{user_id}", 3600, user_json)
```

### Application Scaling

```bash
# Docker Compose - scale workers
docker compose -f docker-compose.prod.yml up -d --scale celery_worker=5

# Kubernetes - HPA automatically scales, or manual scaling:
kubectl scale deployment datashield-backend --replicas=10 -n datashield
kubectl scale deployment datashield-celery-worker --replicas=15 -n datashield
```

---

## Maintenance

### Daily
- Monitor dashboards for anomalies
- Check alert notifications
- Review error logs

### Weekly
- Review performance metrics
- Check disk space
- Test backup restore
- Update dependencies

### Monthly
- Security audit
- Performance optimization
- Cost analysis
- Disaster recovery drill

---

## Support

- **Documentation**: https://docs.datashield.com
- **GitHub Issues**: https://github.com/your-org/datashield-osint/issues
- **Email**: support@datashield.com
- **Slack**: https://datashield.slack.com

---

## Next Steps

After successful deployment:

1. ✅ Configure monitoring dashboards
2. ✅ Setup automated backups
3. ✅ Enable SSL/TLS
4. ✅ Configure alerting
5. ✅ Test disaster recovery
6. ✅ Performance tuning
7. ✅ Security hardening
8. ✅ Documentation updates

---

*Last Updated: January 15, 2024*  
*Version: 1.0.0*
