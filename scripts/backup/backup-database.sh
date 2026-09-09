#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# DataShield OSINT - PostgreSQL Backup Script
# ══════════════════════════════════════════════════════════════════════════════
# Features:
# - Full database backup with compression
# - Automatic retention policy
# - S3/MinIO upload
# - Backup encryption
# - Email notifications
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

# Backup configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/datashield}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="datashield_backup_${TIMESTAMP}"
BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.sql"
COMPRESSED_FILE="${BACKUP_FILE}.gz"
ENCRYPTED_FILE="${COMPRESSED_FILE}.enc"

# Database configuration
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-datashield}"
DB_USER="${POSTGRES_USER:-datashield}"
DB_PASSWORD="${POSTGRES_PASSWORD}"

# S3/MinIO configuration
S3_ENABLED="${BACKUP_S3_ENABLED:-true}"
S3_BUCKET="${BACKUP_S3_BUCKET:-datashield-backups}"
S3_ENDPOINT="${BACKUP_S3_ENDPOINT:-}"
S3_ACCESS_KEY="${AWS_ACCESS_KEY_ID:-${MINIO_ACCESS_KEY}}"
S3_SECRET_KEY="${AWS_SECRET_ACCESS_KEY:-${MINIO_SECRET_KEY}}"

# Encryption configuration
ENCRYPTION_ENABLED="${BACKUP_ENCRYPTION_ENABLED:-true}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY}"

# Notification configuration
NOTIFY_EMAIL="${BACKUP_NOTIFY_EMAIL:-}"
NOTIFY_TELEGRAM="${BACKUP_NOTIFY_TELEGRAM:-false}"

# ──────────────────────────────────────────────────────────────────────────────
# Functions
# ──────────────────────────────────────────────────────────────────────────────

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${BACKUP_DIR}/backup.log"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "${BACKUP_DIR}/backup.log" >&2
}

send_notification() {
    local subject="$1"
    local message="$2"
    local status="${3:-info}"
    
    # Email notification
    if [ -n "$NOTIFY_EMAIL" ] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "[$status] $subject" "$NOTIFY_EMAIL"
    fi
    
    # Telegram notification
    if [ "$NOTIFY_TELEGRAM" = "true" ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_DEFAULT_CHAT_ID}" \
            -d text="[$status] $subject: $message" > /dev/null 2>&1 || true
    fi
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check required commands
    for cmd in pg_dump gzip; do
        if ! command -v $cmd &> /dev/null; then
            error "$cmd is not installed"
            exit 1
        fi
    done
    
    # Check backup directory
    if [ ! -d "$BACKUP_DIR" ]; then
        log "Creating backup directory: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
    fi
    
    # Check database connection
    if ! PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
        error "Cannot connect to database"
        send_notification "Backup Failed" "Cannot connect to database $DB_NAME" "ERROR"
        exit 1
    fi
    
    log "Prerequisites check passed"
}

create_backup() {
    log "Starting database backup..."
    log "Database: $DB_NAME"
    log "Backup file: $BACKUP_FILE"
    
    # Create backup with pg_dump
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --no-owner \
        --no-acl \
        --format=plain \
        --file="$BACKUP_FILE" 2>&1 | tee -a "${BACKUP_DIR}/backup.log"
    
    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file was not created"
        send_notification "Backup Failed" "Backup file was not created" "ERROR"
        exit 1
    fi
    
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup created successfully (size: $BACKUP_SIZE)"
}

compress_backup() {
    log "Compressing backup..."
    
    gzip -f "$BACKUP_FILE"
    
    if [ ! -f "$COMPRESSED_FILE" ]; then
        error "Compression failed"
        send_notification "Backup Failed" "Compression failed" "ERROR"
        exit 1
    fi
    
    COMPRESSED_SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
    log "Backup compressed successfully (size: $COMPRESSED_SIZE)"
}

encrypt_backup() {
    if [ "$ENCRYPTION_ENABLED" = "true" ]; then
        log "Encrypting backup..."
        
        if [ -z "$ENCRYPTION_KEY" ]; then
            error "Encryption key not set"
            send_notification "Backup Failed" "Encryption key not configured" "ERROR"
            exit 1
        fi
        
        # Encrypt using OpenSSL
        openssl enc -aes-256-cbc -salt -pbkdf2 \
            -in "$COMPRESSED_FILE" \
            -out "$ENCRYPTED_FILE" \
            -pass pass:"$ENCRYPTION_KEY"
        
        if [ ! -f "$ENCRYPTED_FILE" ]; then
            error "Encryption failed"
            send_notification "Backup Failed" "Encryption failed" "ERROR"
            exit 1
        fi
        
        # Remove unencrypted file
        rm -f "$COMPRESSED_FILE"
        
        FINAL_FILE="$ENCRYPTED_FILE"
        log "Backup encrypted successfully"
    else
        FINAL_FILE="$COMPRESSED_FILE"
        log "Encryption disabled, skipping"
    fi
}

upload_to_s3() {
    if [ "$S3_ENABLED" = "true" ]; then
        log "Uploading backup to S3..."
        
        # Install AWS CLI if not present
        if ! command -v aws &> /dev/null; then
            log "AWS CLI not found, installing..."
            pip install awscli --quiet
        fi
        
        # Configure S3 endpoint if using MinIO
        S3_ARGS=""
        if [ -n "$S3_ENDPOINT" ]; then
            S3_ARGS="--endpoint-url=$S3_ENDPOINT"
        fi
        
        # Upload to S3
        AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" \
        AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
        aws s3 cp "$FINAL_FILE" "s3://${S3_BUCKET}/" $S3_ARGS
        
        if [ $? -eq 0 ]; then
            log "Backup uploaded to S3 successfully"
        else
            error "S3 upload failed"
            send_notification "Backup Warning" "Backup created but S3 upload failed" "WARNING"
        fi
    else
        log "S3 upload disabled, skipping"
    fi
}

cleanup_old_backups() {
    log "Cleaning up old backups (retention: $BACKUP_RETENTION_DAYS days)..."
    
    # Local cleanup
    find "$BACKUP_DIR" -name "datashield_backup_*.sql.gz*" -type f -mtime +$BACKUP_RETENTION_DAYS -delete
    
    DELETED_COUNT=$(find "$BACKUP_DIR" -name "datashield_backup_*.sql.gz*" -type f -mtime +$BACKUP_RETENTION_DAYS 2>/dev/null | wc -l)
    log "Deleted $DELETED_COUNT old local backups"
    
    # S3 cleanup
    if [ "$S3_ENABLED" = "true" ]; then
        log "Cleaning up old S3 backups..."
        
        S3_ARGS=""
        if [ -n "$S3_ENDPOINT" ]; then
            S3_ARGS="--endpoint-url=$S3_ENDPOINT"
        fi
        
        CUTOFF_DATE=$(date -d "$BACKUP_RETENTION_DAYS days ago" +%Y%m%d)
        
        AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" \
        AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
        aws s3 ls "s3://${S3_BUCKET}/" $S3_ARGS | \
        awk '{print $4}' | \
        grep "datashield_backup_" | \
        while read file; do
            FILE_DATE=$(echo "$file" | grep -oP '\d{8}' | head -1)
            if [ "$FILE_DATE" -lt "$CUTOFF_DATE" ]; then
                AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" \
                AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
                aws s3 rm "s3://${S3_BUCKET}/$file" $S3_ARGS
                log "Deleted old S3 backup: $file"
            fi
        done
    fi
}

generate_backup_report() {
    local duration=$1
    local final_size=$(du -h "$FINAL_FILE" | cut -f1)
    
    cat > "${BACKUP_DIR}/backup_report_${TIMESTAMP}.txt" <<EOF
DataShield OSINT - Backup Report
================================
Date: $(date)
Backup Name: $BACKUP_NAME
Database: $DB_NAME
Duration: ${duration}s
Final Size: $final_size
Encrypted: $ENCRYPTION_ENABLED
S3 Upload: $S3_ENABLED
Status: SUCCESS
EOF

    log "Backup report generated"
}

# ──────────────────────────────────────────────────────────────────────────────
# Main Script
# ──────────────────────────────────────────────────────────────────────────────

main() {
    START_TIME=$(date +%s)
    
    log "═══════════════════════════════════════════════════════════════"
    log "DataShield OSINT Database Backup Started"
    log "═══════════════════════════════════════════════════════════════"
    
    # Run backup process
    check_prerequisites
    create_backup
    compress_backup
    encrypt_backup
    upload_to_s3
    cleanup_old_backups
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    generate_backup_report "$DURATION"
    
    log "═══════════════════════════════════════════════════════════════"
    log "Backup completed successfully in ${DURATION}s"
    log "Backup file: $FINAL_FILE"
    log "═══════════════════════════════════════════════════════════════"
    
    send_notification "Backup Successful" "Database backup completed in ${DURATION}s" "SUCCESS"
}

# Trap errors
trap 'error "Backup failed with error"; send_notification "Backup Failed" "An error occurred during backup" "ERROR"; exit 1' ERR

# Run main function
main "$@"
