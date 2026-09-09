# Point-in-Time Recovery (PITR) Guide

## Overview

Point-in-Time Recovery allows you to restore your database to any specific moment, not just to the time of a backup. This is achieved through PostgreSQL's Write-Ahead Logging (WAL) mechanism.

## Setup WAL Archiving

### 1. Configure PostgreSQL

Edit `postgresql.conf`:

```conf
# Enable WAL archiving
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /archive/%f && cp %p /archive/%f'
archive_timeout = 60  # Force a log file switch every 60 seconds

# WAL configuration
max_wal_senders = 3
wal_keep_size = 1GB
```

### 2. Create Archive Directory

```bash
# Create WAL archive directory
mkdir -p /var/lib/postgresql/archive
chown postgres:postgres /var/lib/postgresql/archive
chmod 700 /var/lib/postgresql/archive
```

### 3. Restart PostgreSQL

```bash
docker compose restart postgres
# or
kubectl rollout restart statefulset/postgres -n datashield
```

## Continuous Archiving Script

Create `/scripts/backup/archive-wal.sh`:

```bash
#!/bin/bash
# Archive WAL files to S3

WAL_FILE="$1"
WAL_PATH="$2"
S3_BUCKET="${BACKUP_S3_BUCKET}"
S3_PREFIX="wal-archive"

# Upload to S3
aws s3 cp "$WAL_PATH" \
    "s3://${S3_BUCKET}/${S3_PREFIX}/${WAL_FILE}" \
    --endpoint-url="${S3_ENDPOINT}"

# Verify upload
if [ $? -eq 0 ]; then
    exit 0
else
    exit 1
fi
```

Update `postgresql.conf`:

```conf
archive_command = '/scripts/backup/archive-wal.sh %f %p'
```

## Creating a Base Backup

```bash
# Create base backup
pg_basebackup -h localhost -U datashield \
    -D /backups/base_backup_$(date +%Y%m%d_%H%M%S) \
    -Ft -z -Xs -P

# Upload to S3
tar -czf base_backup.tar.gz /backups/base_backup_*
aws s3 cp base_backup.tar.gz s3://${S3_BUCKET}/base-backups/
```

## Performing Point-in-Time Recovery

### 1. Stop Database

```bash
docker compose stop postgres
# or
kubectl scale statefulset postgres --replicas=0 -n datashield
```

### 2. Backup Current Data

```bash
mv /var/lib/postgresql/data /var/lib/postgresql/data.old
```

### 3. Restore Base Backup

```bash
# Download base backup
aws s3 cp s3://${S3_BUCKET}/base-backups/base_backup.tar.gz .

# Extract
mkdir -p /var/lib/postgresql/data
tar -xzf base_backup.tar.gz -C /var/lib/postgresql/data
```

### 4. Create Recovery Configuration

Create `/var/lib/postgresql/data/recovery.conf`:

```conf
# Restore to specific time
restore_command = 'aws s3 cp s3://${S3_BUCKET}/wal-archive/%f %p'
recovery_target_time = '2024-01-15 14:30:00 UTC'
recovery_target_action = 'promote'

# Or restore to specific transaction
# recovery_target_xid = '12345'

# Or restore to latest
# recovery_target = 'immediate'
```

For PostgreSQL 12+, create `/var/lib/postgresql/data/postgresql.auto.conf`:

```conf
restore_command = 'aws s3 cp s3://${S3_BUCKET}/wal-archive/%f %p'
recovery_target_time = '2024-01-15 14:30:00 UTC'
```

And create signal file:

```bash
touch /var/lib/postgresql/data/recovery.signal
```

### 5. Start Database

```bash
docker compose start postgres
# or
kubectl scale statefulset postgres --replicas=1 -n datashield
```

### 6. Verify Recovery

```bash
# Check PostgreSQL logs
docker compose logs -f postgres

# Connect and verify
psql -h localhost -U datashield -d datashield -c "SELECT NOW();"
```

## Automated PITR Script

Create `/scripts/backup/pitr-restore.sh`:

```bash
#!/bin/bash
set -euo pipefail

RECOVERY_TIME="$1"
BASE_BACKUP="${2:-latest}"

echo "Point-in-Time Recovery to: $RECOVERY_TIME"

# Stop database
docker compose stop postgres

# Backup current data
mv /var/lib/postgresql/data /var/lib/postgresql/data.$(date +%Y%m%d_%H%M%S)

# Download and extract base backup
if [ "$BASE_BACKUP" = "latest" ]; then
    BASE_BACKUP=$(aws s3 ls s3://${S3_BUCKET}/base-backups/ | sort | tail -n 1 | awk '{print $4}')
fi

aws s3 cp "s3://${S3_BUCKET}/base-backups/${BASE_BACKUP}" base_backup.tar.gz
mkdir -p /var/lib/postgresql/data
tar -xzf base_backup.tar.gz -C /var/lib/postgresql/data

# Create recovery configuration
cat > /var/lib/postgresql/data/postgresql.auto.conf <<EOF
restore_command = 'aws s3 cp s3://${S3_BUCKET}/wal-archive/%f %p --endpoint-url=${S3_ENDPOINT}'
recovery_target_time = '${RECOVERY_TIME}'
EOF

touch /var/lib/postgresql/data/recovery.signal

# Start database
docker compose start postgres

echo "PITR initiated. Monitor logs:"
echo "docker compose logs -f postgres"
```

## WAL-G Integration (Advanced)

WAL-G is a more sophisticated backup tool:

```bash
# Install WAL-G
wget https://github.com/wal-g/wal-g/releases/download/v2.0.0/wal-g-pg-ubuntu-20.04-amd64.tar.gz
tar -xzf wal-g-pg-ubuntu-20.04-amd64.tar.gz
mv wal-g-pg-ubuntu-20.04-amd64 /usr/local/bin/wal-g

# Configure
export WALG_S3_PREFIX="s3://${S3_BUCKET}/wal-g"
export AWS_ACCESS_KEY_ID="${MINIO_ACCESS_KEY}"
export AWS_SECRET_ACCESS_KEY="${MINIO_SECRET_KEY}"
export AWS_ENDPOINT="${S3_ENDPOINT}"

# Create backup
wal-g backup-push /var/lib/postgresql/data

# List backups
wal-g backup-list

# Restore
wal-g backup-fetch /var/lib/postgresql/data LATEST
```

Update `postgresql.conf`:

```conf
archive_command = 'wal-g wal-push %p'
restore_command = 'wal-g wal-fetch %f %p'
```

## Backup Schedule Recommendations

1. **Full Backup**: Daily at 2 AM
2. **WAL Archiving**: Continuous (every 60 seconds)
3. **Base Backup**: Weekly on Sunday
4. **Retention**:
   - Full backups: 30 days
   - WAL archives: 30 days
   - Base backups: 90 days

## Testing Recovery

Regularly test your backup and recovery process:

```bash
# Monthly recovery drill
./scripts/backup/test-recovery.sh

# Verify recovery time
time ./scripts/backup/pitr-restore.sh "2024-01-15 14:00:00 UTC"
```

## Monitoring

Monitor WAL archiving:

```sql
-- Check archiver status
SELECT * FROM pg_stat_archiver;

-- Check replication lag
SELECT
    now() - pg_last_xact_replay_timestamp() AS replication_lag,
    pg_is_in_recovery() AS in_recovery;
```

## Troubleshooting

### WAL Files Not Archiving

```bash
# Check archive status
SELECT archived_count, failed_count 
FROM pg_stat_archiver;

# Check permissions
ls -la /var/lib/postgresql/archive/

# Check archive_command manually
su - postgres -c "pg_archivecleanup /var/lib/postgresql/archive 000000010000000000000001"
```

### Recovery Stuck

```bash
# Check recovery status
SELECT pg_is_in_recovery();

# Check last replayed WAL
SELECT pg_last_wal_replay_lsn();

# Force promotion if needed
SELECT pg_wal_replay_resume();
```

## References

- [PostgreSQL PITR Documentation](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [WAL-G Documentation](https://github.com/wal-g/wal-g)
- [pgBackRest](https://pgbackrest.org/)
