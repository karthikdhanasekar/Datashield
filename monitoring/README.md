# DataShield OSINT - Monitoring & Alerting Guide

## Overview

Comprehensive monitoring stack using Prometheus, Grafana, and Alertmanager.

## Quick Start

### Docker Compose

```bash
# Start monitoring stack
docker compose --profile monitoring up -d

# Access Grafana
open http://localhost:3001
# Default credentials: admin / grafana_dev_pass_2024

# Access Prometheus
open http://localhost:9090

# Access Alertmanager
open http://localhost:9093
```

### Kubernetes

```bash
# Deploy monitoring stack
kubectl apply -f k8s/service-monitor.yaml

# Or use Prometheus Operator
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --values monitoring/helm-values.yaml
```

## Components

### 1. Prometheus

**Purpose**: Metrics collection and storage

**Key Metrics**:
- HTTP request rate, latency, errors
- Database connections, query performance
- System resources (CPU, memory, disk)
- Application-specific OSINT metrics
- Celery worker performance

**Configuration**: `monitoring/prometheus.yml`

### 2. Grafana

**Purpose**: Visualization and dashboards

**Pre-built Dashboards**:
1. **System Overview** - Overall platform health
2. **Application Performance** - API metrics, response times
3. **Database Health** - PostgreSQL, Redis, Elasticsearch metrics
4. **OSINT Operations** - Scan performance, success rates
5. **Security Dashboard** - Authentication failures, rate limits
6. **Infrastructure** - Node metrics, resource usage

**Access**: http://localhost:3001

### 3. Alertmanager

**Purpose**: Alert routing and notifications

**Alert Channels**:
- Email (SMTP)
- Slack
- PagerDuty
- Telegram
- Custom webhooks

**Configuration**: `monitoring/alertmanager.yml`

## Alert Severity Levels

| Level | Response Time | Notification | Examples |
|-------|---------------|--------------|----------|
| **Critical** | Immediate | Email + Slack + PagerDuty | Service down, data loss |
| **Warning** | 30 minutes | Email + Slack | High resource usage, errors |
| **Info** | Review during business hours | Slack only | Rate limits hit |

## Alert Rules

### Application Alerts (`monitoring/alerts/application.yml`)

- Service availability
- Error rates (>5% warning, >10% critical)
- Response time (>2s warning, >5s critical)
- Authentication failures
- Celery queue backlog
- SSL certificate expiration

### Infrastructure Alerts (`monitoring/alerts/infrastructure.yml`)

- CPU usage (>80% warning, >95% critical)
- Memory usage (>80% warning, >90% critical)
- Disk space (<20% warning, <10% critical)
- System load
- Container restarts
- Kubernetes pod health

### Database Alerts (`monitoring/alerts/database.yml`)

- PostgreSQL down
- Connection exhaustion (>80% warning)
- Slow queries (>300s)
- Replication lag
- Redis memory usage
- Elasticsearch cluster health

## Exporters

### Required Exporters

```yaml
# docker-compose.monitoring.yml
services:
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    environment:
      DATA_SOURCE_NAME: "postgresql://datashield:password@postgres:5432/datashield?sslmode=disable"
    ports:
      - "9187:9187"

  redis-exporter:
    image: oliver006/redis_exporter:latest
    environment:
      REDIS_ADDR: "redis:6379"
      REDIS_PASSWORD: "redis_password"
    ports:
      - "9121:9121"

  node-exporter:
    image: prom/node-exporter:latest
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
    ports:
      - "9100:9100"

  blackbox-exporter:
    image: prom/blackbox-exporter:latest
    ports:
      - "9115:9115"
    volumes:
      - ./monitoring/blackbox.yml:/config/blackbox.yml
```

## Custom Metrics

### Backend Metrics

The FastAPI backend exposes custom metrics at `/metrics`:

```python
# Example metrics exposed
http_requests_total{method="GET",endpoint="/api/v1/scans",status="200"}
http_request_duration_seconds{endpoint="/api/v1/scans"}
osint_scan_started_total{scan_type="email"}
osint_scan_completed_total{scan_type="email",status="success"}
osint_scan_duration_seconds{scan_type="email"}
auth_login_failed_total{reason="invalid_password"}
celery_task_duration_seconds{task="scan_email"}
```

### Adding Custom Metrics

```python
from prometheus_client import Counter, Histogram

# Counter
scan_counter = Counter(
    'osint_scan_total',
    'Total OSINT scans',
    ['scan_type', 'status']
)

# Histogram
scan_duration = Histogram(
    'osint_scan_duration_seconds',
    'OSINT scan duration',
    ['scan_type']
)

# Usage
scan_counter.labels(scan_type='email', status='success').inc()
with scan_duration.labels(scan_type='email').time():
    perform_scan()
```

## Grafana Dashboards

### Dashboard IDs (Import from grafana.com)

- **Node Exporter Full**: 1860
- **PostgreSQL Database**: 9628
- **Redis Dashboard**: 11835
- **Nginx Overview**: 12708
- **Docker Container & Host Metrics**: 10619

### Custom Dashboards

Located in `monitoring/grafana/dashboards/`:

1. `datashield-overview.json` - Platform overview
2. `datashield-api.json` - API performance
3. `datashield-osint.json` - OSINT operations
4. `datashield-security.json` - Security metrics

## Alert Testing

### Test Alert Rules

```bash
# Test Prometheus rules
promtool check rules monitoring/alerts/*.yml

# Test alert expression
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=up{job="datashield-backend"} == 0'
```

### Trigger Test Alert

```bash
# Stop backend to trigger ServiceDown alert
docker compose stop backend

# Check alerts in Prometheus
open http://localhost:9090/alerts

# Check Alertmanager
open http://localhost:9093/#/alerts
```

### Silence Alerts

```bash
# Via Alertmanager UI
open http://localhost:9093/#/silences

# Via API
curl -X POST http://localhost:9093/api/v1/silences \
  -H 'Content-Type: application/json' \
  -d '{
    "matchers": [{"name": "alertname", "value": "HighCPUUsage", "isRegex": false}],
    "startsAt": "2024-01-15T10:00:00Z",
    "endsAt": "2024-01-15T12:00:00Z",
    "createdBy": "admin",
    "comment": "Planned maintenance"
  }'
```

## Notification Channels

### Email Configuration

Set in `.env`:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@yourdomain.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL_CRITICAL=oncall@yourdomain.com
ALERT_EMAIL_WARNINGS=team@yourdomain.com
```

### Slack Configuration

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

Create webhook at: https://api.slack.com/messaging/webhooks

### PagerDuty Configuration

```env
PAGERDUTY_ROUTING_KEY=your-integration-key
```

Get key from: PagerDuty → Services → Integrations

### Telegram Configuration

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_DEFAULT_CHAT_ID=123456789
```

## Monitoring Best Practices

### 1. Alert Fatigue Prevention

- Set appropriate thresholds
- Use `for` duration to avoid flapping
- Group related alerts
- Use inhibit rules

### 2. Dashboard Organization

- Overview dashboard for quick health check
- Detailed dashboards per component
- Use variables for filtering
- Add links between related dashboards

### 3. Retention Policy

```yaml
# Prometheus retention (prometheus.yml)
storage:
  tsdb:
    retention.time: 30d
    retention.size: 50GB
```

### 4. High Availability

For production, deploy Prometheus and Alertmanager in HA mode:

```bash
# Multiple Prometheus instances
docker compose up -d --scale prometheus=3

# Alertmanager cluster
--cluster.peer=alertmanager-1:9094
--cluster.peer=alertmanager-2:9094
```

## Troubleshooting

### Prometheus Not Scraping

```bash
# Check targets
curl http://localhost:9090/api/v1/targets

# Check service discovery
curl http://localhost:9090/api/v1/targets/metadata
```

### Alerts Not Firing

```bash
# Check alert rules
curl http://localhost:9090/api/v1/rules

# Test expression
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=YOUR_ALERT_EXPRESSION'
```

### No Notifications

```bash
# Check Alertmanager logs
docker compose logs alertmanager

# Test SMTP
docker compose exec alertmanager \
  amtool check-config /etc/alertmanager/config.yml
```

## Performance Tuning

### Prometheus

```yaml
global:
  scrape_interval: 15s  # Increase for less load
  evaluation_interval: 15s

# Reduce cardinality
metric_relabel_configs:
  - source_labels: [__name__]
    regex: 'high_cardinality_metric.*'
    action: drop
```

### Grafana

- Enable caching
- Use time range variables
- Limit number of series per query
- Use recording rules for complex queries

## Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
