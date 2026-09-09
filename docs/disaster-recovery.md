# DataShield OSINT - Disaster Recovery Plan

## Table of Contents

1. [Overview](#overview)
2. [Recovery Objectives](#recovery-objectives)
3. [Backup Strategy](#backup-strategy)
4. [Disaster Scenarios](#disaster-scenarios)
5. [Recovery Procedures](#recovery-procedures)
6. [Testing](#testing)
7. [Contact Information](#contact-information)

---

## Overview

This document outlines the disaster recovery (DR) procedures for the DataShield OSINT platform. It provides step-by-step instructions for recovering from various failure scenarios.

### Key Metrics

- **RTO (Recovery Time Objective)**: 4 hours
- **RPO (Recovery Point Objective)**: 1 hour
- **Maximum Tolerable Downtime (MTD)**: 24 hours

---

## Recovery Objectives

### Priority Levels

| Priority | Component | RTO | RPO |
|----------|-----------|-----|-----|
| P0 (Critical) | PostgreSQL Database | 2 hours | 1 hour |
| P0 (Critical) | Authentication Service | 2 hours | 1 hour |
| P1 (High) | API Backend | 4 hours | 4 hours |
| P1 (High) | Redis Cache | 4 hours | N/A |
| P2 (Medium) | Elasticsearch | 8 hours | 24 hours |
| P2 (Medium) | MinIO Storage | 8 hours | 24 hours |
| P3 (Low) | Frontend | 1 hour | N/A |
| P3 (Low) | Monitoring | 12 hours | N/A |

---

## Backup Strategy

### Automated Backups

#### Database Backups
- **Frequency**: Daily at 2:00 AM UTC
- **Retention**: 30 days local, 90 days S3
- **Type**: Full backup + WAL archiving
- **Encryption**: AES-256
- **Location**: 
  - Primary: S3/MinIO bucket `datashield-backups`
  - Secondary: Local storage `/var/backups/datashield`

#### File Storage Backups
- **Frequency**: Daily at 3:00 AM UTC
- **Retention**: 30 days
- **Type**: Incremental
- **Location**: S3 bucket `datashield-evidence-backups`

#### Configuration Backups
- **Frequency**: On every change
- **Type**: Git repository
- **Location**: Private Git repository

### Backup Verification

Automated backup verification runs weekly:

```bash
# Verify latest backup
./scripts/backup/verify-backup.sh

# Expected output:
# ✓ Backup file exists
# ✓ Backup file is not corrupt
# ✓ Backup can be decompressed
# ✓ Backup can be decrypted
# ✓ SQL syntax is valid
```

---

## Disaster Scenarios

### Scenario 1: Database Corruption

**Symptoms**:
- Database connection errors
- Data inconsistency
- PostgreSQL crash loops

**Impact**: Complete service outage

**Recovery Procedure**: [See Database Recovery](#database-recovery)

**Estimated Recovery Time**: 2-4 hours

---

### Scenario 2: Complete Infrastructure Loss

**Symptoms**:
- All services unavailable
- Infrastructure provider outage
- Data center failure

**Impact**: Complete service outage

**Recovery Procedure**: [See Complete Infrastructure Recovery](#complete-infrastructure-recovery)

**Estimated Recovery Time**: 4-8 hours

---

### Scenario 3: Data Breach / Ransomware

**Symptoms**:
- Unauthorized access detected
- Data encrypted by ransomware
- Suspicious database modifications

**Impact**: Service outage, potential data loss

**Recovery Procedure**: [See Security Incident Recovery](#security-incident-recovery)

**Estimated Recovery Time**: 8-24 hours

---

### Scenario 4: Accidental Data Deletion

**Symptoms**:
- User reports missing data
- Database table truncated
- Audit logs show deletion

**Impact**: Partial data loss

**Recovery Procedure**: [See Point-in-Time Recovery](#point-in-time-recovery)

**Estimated Recovery Time**: 1-2 hours

---

## Recovery Procedures

### Database Recovery

#### Prerequisites
- Access to backup storage (S3)
- Database credentials
- kubectl/docker access

#### Steps

1. **Assess the Situation**

```bash
# Check database status
kubectl get pods -n datashield | grep postgres
# or
docker compose ps postgres

# Check database logs
kubectl logs -f postgres-0 -n datashield
# or
docker compose logs postgres
```

2. **Stop All Database Connections**

```bash
# Kubernetes
kubectl scale deployment datashield-backend --replicas=0 -n datashield
kubectl scale deployment datashield-celery-worker --replicas=0 -n datashield

# Docker Compose
docker compose stop backend celery_worker celery_beat
```

3. **List Available Backups**

```bash
./scripts/backup/restore-database.sh -l
```

4. **Restore from Latest Backup**

```bash
# Kubernetes
kubectl exec -it postgres-0 -n datashield -- bash
./scripts/backup/restore-database.sh -s datashield_backup_20240115_020000.sql.gz.enc -y

# Docker Compose
docker compose exec postgres bash
./scripts/backup/restore-database.sh -f /backups/datashield_backup_20240115_020000.sql.gz.enc -y
```

5. **Verify Database**

```bash
# Check table counts
psql -U datashield -d datashield -c "\dt"
psql -U datashield -d datashield -c "SELECT COUNT(*) FROM users;"
psql -U datashield -d datashield -c "SELECT COUNT(*) FROM scans;"
```

6. **Restart Services**

```bash
# Kubernetes
kubectl scale deployment datashield-backend --replicas=3 -n datashield
kubectl scale deployment datashield-celery-worker --replicas=3 -n datashield

# Docker Compose
docker compose up -d
```

7. **Verify Application**

```bash
curl https://yourdomain.com/health
curl https://api.yourdomain.com/health
```

---

### Complete Infrastructure Recovery

#### Prerequisites
- New infrastructure provisioned
- DNS access
- Backup access
- SSL certificates

#### Steps

1. **Provision New Infrastructure**

```bash
# Option A: Kubernetes
kubectl create namespace datashield
kubectl apply -k k8s/

# Option B: Docker
docker compose -f docker-compose.prod.yml up -d
```

2. **Configure DNS**

Point DNS to new infrastructure:
```
A record: yourdomain.com → NEW_IP
A record: api.yourdomain.com → NEW_IP
```

3. **Restore Database**

```bash
./scripts/backup/restore-database.sh -s latest -y
```

4. **Restore MinIO Data**

```bash
# Sync from backup bucket
aws s3 sync s3://datashield-evidence-backups/ \
    s3://datashield-evidence/ \
    --endpoint-url=${S3_ENDPOINT}
```

5. **Restore Elasticsearch Indices**

```bash
# Restore from snapshot
./scripts/backup/restore-elasticsearch.sh
```

6. **Update Configuration**

```bash
# Update secrets
kubectl create secret generic datashield-secrets \
    --from-env-file=.env.production \
    --dry-run=client -o yaml | kubectl apply -f -
```

7. **Verify SSL Certificates**

```bash
# Check cert-manager
kubectl get certificate -n datashield
kubectl describe certificate datashield-tls-cert -n datashield
```

8. **Run Smoke Tests**

```bash
./scripts/testing/smoke-tests.sh
```

**Estimated Total Time**: 4-8 hours

---

### Security Incident Recovery

#### Immediate Actions (Within 15 minutes)

1. **Isolate the System**

```bash
# Block all external traffic
kubectl apply -f k8s/emergency-network-policy.yaml

# Or stop services
docker compose stop
```

2. **Capture Evidence**

```bash
# Save logs
kubectl logs -n datashield --all-containers=true > incident-logs-$(date +%Y%m%d).log

# Database dump for forensics
pg_dump -Fc > forensic-dump-$(date +%Y%m%d).backup
```

3. **Notify Team**

- Security team
- Management
- Legal (if required)
- Customers (if data breach confirmed)

#### Investigation Phase (1-4 hours)

4. **Analyze the Breach**

```bash
# Check audit logs
kubectl exec -it postgres-0 -n datashield -- psql -U datashield -d datashield \
    -c "SELECT * FROM audit_logs WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY created_at DESC;"

# Check authentication attempts
grep "authentication failure" /var/log/datashield/*.log

# Check file modifications
find /var/lib/datashield -type f -mtime -1 -ls
```

5. **Identify Compromised Accounts**

```sql
-- Check for suspicious logins
SELECT user_id, ip_address, user_agent, created_at
FROM audit_logs
WHERE event_type = 'login'
AND created_at > NOW() - INTERVAL '48 hours'
ORDER BY created_at DESC;
```

#### Recovery Phase (4-24 hours)

6. **Restore from Clean Backup**

```bash
# Restore from backup before breach
./scripts/backup/restore-database.sh -s datashield_backup_20240114_020000.sql.gz.enc -y
```

7. **Reset All Credentials**

```bash
# Rotate all API keys
./scripts/admin/rotate-api-keys.sh

# Force password reset for all users
./scripts/admin/force-password-reset.sh

# Rotate JWT secrets
./scripts/admin/rotate-jwt-secrets.sh
```

8. **Apply Security Patches**

```bash
# Update all services
./scripts/deployment/update-all.sh

# Apply security patches
kubectl set image deployment/datashield-backend \
    backend=ghcr.io/your-org/datashield-backend:security-patch-v1.2.1 \
    -n datashield
```

9. **Enhance Security**

```bash
# Enable stricter network policies
kubectl apply -f k8s/strict-network-policies.yaml

# Enable MFA for all users
./scripts/admin/enforce-mfa.sh

# Update firewall rules
./scripts/security/update-firewall.sh
```

10. **Resume Operations**

```bash
# Remove isolation
kubectl delete -f k8s/emergency-network-policy.yaml

# Gradual rollout
kubectl scale deployment datashield-backend --replicas=1 -n datashield
# Monitor for 30 minutes
kubectl scale deployment datashield-backend --replicas=3 -n datashield
```

#### Post-Incident (1-2 weeks)

11. **Post-Incident Review**

- Document timeline
- Identify root cause
- Update runbooks
- Improve security controls

12. **Notify Affected Parties**

- Prepare incident report
- Notify customers if required
- Report to authorities if legally required

---

### Point-in-Time Recovery

**Use Case**: Recover database to specific timestamp before corruption/deletion

```bash
# 1. List WAL archives
aws s3 ls s3://datashield-backups/wal-archive/

# 2. Restore to specific time
./scripts/backup/pitr-restore.sh "2024-01-15 14:30:00 UTC"

# 3. Verify recovery
psql -U datashield -d datashield -c "SELECT NOW();"
```

**Recovery Time**: 1-2 hours  
**Data Loss**: Minimal (up to last WAL archive, typically < 5 minutes)

---

## Testing

### Monthly DR Drill Schedule

| Week | Test Scenario | Duration |
|------|---------------|----------|
| Week 1 | Database restore test | 2 hours |
| Week 2 | Service failover test | 1 hour |
| Week 3 | Full infrastructure recovery (staging) | 4 hours |
| Week 4 | Security incident simulation | 3 hours |

### DR Drill Checklist

```bash
# 1. Announce drill
./scripts/testing/announce-dr-drill.sh

# 2. Capture current state
./scripts/testing/capture-state.sh

# 3. Execute recovery procedure
# (Follow relevant procedure above)

# 4. Verify recovery
./scripts/testing/verify-recovery.sh

# 5. Document results
./scripts/testing/generate-dr-report.sh

# 6. Rollback
./scripts/testing/rollback-drill.sh
```

### Success Criteria

- [ ] RTO met (< 4 hours)
- [ ] RPO met (< 1 hour data loss)
- [ ] All services operational
- [ ] Data integrity verified
- [ ] SSL certificates valid
- [ ] Monitoring functional
- [ ] User authentication working

---

## Contact Information

### Emergency Contacts

| Role | Name | Phone | Email | Backup |
|------|------|-------|-------|--------|
| Incident Commander | [Name] | +1-XXX-XXX-XXXX | email@domain.com | [Backup Name] |
| Database Admin | [Name] | +1-XXX-XXX-XXXX | dba@domain.com | [Backup Name] |
| Security Lead | [Name] | +1-XXX-XXX-XXXX | security@domain.com | [Backup Name] |
| DevOps Lead | [Name] | +1-XXX-XXX-XXXX | devops@domain.com | [Backup Name] |

### External Contacts

- **Cloud Provider Support**: support@provider.com
- **DNS Provider**: dns-support@provider.com
- **Security Vendor**: security@vendor.com
- **Legal**: legal@company.com

### Communication Channels

- **Primary**: Slack #incident-response
- **Secondary**: Microsoft Teams
- **Emergency**: Conference bridge +1-XXX-XXX-XXXX

---

## Document Control

- **Version**: 1.0
- **Last Updated**: 2024-01-15
- **Next Review**: 2024-04-15
- **Owner**: DevOps Team
- **Approved By**: CTO

---

## Appendix

### A. Emergency Network Policy

Save as `k8s/emergency-network-policy.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: emergency-lockdown
  namespace: datashield
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  # Deny all traffic
```

### B. Backup Verification Script

Location: `scripts/backup/verify-backup.sh`

### C. Recovery Time Log Template

| Step | Start Time | End Time | Duration | Status | Notes |
|------|------------|----------|----------|--------|-------|
| 1. Assessment | | | | | |
| 2. Isolation | | | | | |
| 3. Backup Restore | | | | | |
| 4. Verification | | | | | |
| 5. Service Restart | | | | | |
| **TOTAL** | | | | | |
