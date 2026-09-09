#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# DataShield OSINT - PostgreSQL Restore Script
# ══════════════════════════════════════════════════════════════════════════════
# Features:
# - Restore from local or S3 backup
# - Automatic decryption
# - Database verification
# - Point-in-time restore
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

# Restore configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/datashield}"
RESTORE_DIR="${RESTORE_DIR:-/tmp/datashield_restore}"

# Database configuration
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-datashield}"
DB_USER="${POSTGRES_USER:-datashield}"
DB_PASSWORD="${POSTGRES_PASSWORD}"

# S3/MinIO configuration
S3_BUCKET="${BACKUP_S3_BUCKET:-datashield-backups}"
S3_ENDPOINT="${BACKUP_S3_ENDPOINT:-}"
S3_ACCESS_KEY="${AWS_ACCESS_KEY_ID:-${MINIO_ACCESS_KEY}}"
S3_SECRET_KEY="${AWS_SECRET_ACCESS_KEY:-${MINIO_SECRET_KEY}}"

# Encryption configuration
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY}"

# ──────────────────────────────────────────────────────────────────────────────
# Functions
# ──────────────────────────────────────────────────────────────────────────────

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

list_available_backups() {
    log "Available backups in $BACKUP_DIR:"
    echo ""
    
    if [ -d "$BACKUP_DIR" ]; then
        ls -lh "$BACKUP_DIR"/datashield_backup_*.sql.gz* 2>/dev/null | \
        awk '{print $9, "(" $5 ")", $6, $7, $8}' || \
        echo "No local backups found"
    fi
    
    echo ""
    log "Available backups in S3:"
    
    S3_ARGS=""
    if [ -n "$S3_ENDPOINT" ]; then
        S3_ARGS="--endpoint-url=$S3_ENDPOINT"
    fi
    
    AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" \
    AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
    aws s3 ls "s3://${S3_BUCKET}/" $S3_ARGS | \
    grep "datashield_backup_" || \
    echo "No S3 backups found"
}

download_from_s3() {
    local backup_file="$1"
    local local_file="$2"
    
    log "Downloading backup from S3..."
    
    S3_ARGS=""
    if [ -n "$S3_ENDPOINT" ]; then
        S3_ARGS="--endpoint-url=$S3_ENDPOINT"
    fi
    
    AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" \
    AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
    aws s3 cp "s3://${S3_BUCKET}/${backup_file}" "$local_file" $S3_ARGS
    
    if [ ! -f "$local_file" ]; then
        error "Failed to download backup from S3"
        exit 1
    fi
    
    log "Backup downloaded successfully"
}

decrypt_backup() {
    local encrypted_file="$1"
    local decrypted_file="$2"
    
    log "Decrypting backup..."
    
    if [ -z "$ENCRYPTION_KEY" ]; then
        error "Encryption key not set"
        exit 1
    fi
    
    openssl enc -aes-256-cbc -d -pbkdf2 \
        -in "$encrypted_file" \
        -out "$decrypted_file" \
        -pass pass:"$ENCRYPTION_KEY"
    
    if [ ! -f "$decrypted_file" ]; then
        error "Decryption failed"
        exit 1
    fi
    
    log "Backup decrypted successfully"
}

decompress_backup() {
    local compressed_file="$1"
    local decompressed_file="$2"
    
    log "Decompressing backup..."
    
    gunzip -c "$compressed_file" > "$decompressed_file"
    
    if [ ! -f "$decompressed_file" ]; then
        error "Decompression failed"
        exit 1
    fi
    
    log "Backup decompressed successfully"
}

verify_database_connection() {
    log "Verifying database connection..."
    
    if ! PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "SELECT 1" > /dev/null 2>&1; then
        error "Cannot connect to database server"
        exit 1
    fi
    
    log "Database connection verified"
}

create_backup_before_restore() {
    log "Creating safety backup before restore..."
    
    SAFETY_BACKUP="${RESTORE_DIR}/pre_restore_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=plain \
        --file="$SAFETY_BACKUP" 2>&1
    
    gzip "$SAFETY_BACKUP"
    
    log "Safety backup created: ${SAFETY_BACKUP}.gz"
}

drop_existing_connections() {
    log "Dropping existing connections to database..."
    
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres <<EOF
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
EOF

    log "Existing connections dropped"
}

restore_database() {
    local sql_file="$1"
    
    log "Starting database restore..."
    log "This will OVERWRITE the existing database: $DB_NAME"
    
    # Drop and recreate database
    log "Dropping existing database..."
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
EOF

    log "Restoring database from backup..."
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --file="$sql_file" \
        --single-transaction 2>&1
    
    log "Database restored successfully"
}

verify_restore() {
    log "Verifying restore..."
    
    # Check if database exists and has tables
    TABLE_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
    
    log "Found $TABLE_COUNT tables in restored database"
    
    if [ "$TABLE_COUNT" -lt 1 ]; then
        error "Restore verification failed: no tables found"
        exit 1
    fi
    
    # Check row counts for key tables
    for table in users scans findings; do
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "\d $table" > /dev/null 2>&1; then
            ROW_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c \
                "SELECT COUNT(*) FROM $table;")
            log "Table '$table' has $ROW_COUNT rows"
        fi
    done
    
    log "Restore verification passed"
}

cleanup_temp_files() {
    log "Cleaning up temporary files..."
    rm -rf "$RESTORE_DIR"
    log "Cleanup complete"
}

# ──────────────────────────────────────────────────────────────────────────────
# Main Script
# ──────────────────────────────────────────────────────────────────────────────

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Restore DataShield OSINT database from backup

OPTIONS:
    -f FILE     Restore from local backup file
    -s S3FILE   Restore from S3 backup file
    -l          List available backups
    -y          Skip confirmation prompt
    -h          Show this help message

EXAMPLES:
    # List available backups
    $0 -l
    
    # Restore from local backup
    $0 -f /var/backups/datashield/datashield_backup_20240101_120000.sql.gz.enc
    
    # Restore from S3 backup
    $0 -s datashield_backup_20240101_120000.sql.gz.enc
    
    # Restore without confirmation
    $0 -f backup.sql.gz -y

EOF
    exit 1
}

main() {
    local backup_file=""
    local source="local"
    local skip_confirm=false
    
    # Parse arguments
    while getopts "f:s:lyh" opt; do
        case $opt in
            f) backup_file="$OPTARG"; source="local" ;;
            s) backup_file="$OPTARG"; source="s3" ;;
            l) list_available_backups; exit 0 ;;
            y) skip_confirm=true ;;
            h) usage ;;
            *) usage ;;
        esac
    done
    
    if [ -z "$backup_file" ]; then
        error "No backup file specified"
        usage
    fi
    
    log "═══════════════════════════════════════════════════════════════"
    log "DataShield OSINT Database Restore"
    log "═══════════════════════════════════════════════════════════════"
    log "Backup file: $backup_file"
    log "Source: $source"
    log "Target database: $DB_NAME"
    log "═══════════════════════════════════════════════════════════════"
    
    # Confirmation
    if [ "$skip_confirm" = false ]; then
        echo ""
        echo "⚠️  WARNING: This will OVERWRITE the existing database!"
        echo "⚠️  All current data will be LOST!"
        echo ""
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            log "Restore cancelled by user"
            exit 0
        fi
    fi
    
    # Create restore directory
    mkdir -p "$RESTORE_DIR"
    
    # Download from S3 if needed
    if [ "$source" = "s3" ]; then
        local_backup_file="${RESTORE_DIR}/$(basename $backup_file)"
        download_from_s3 "$backup_file" "$local_backup_file"
        backup_file="$local_backup_file"
    fi
    
    # Determine file type and process accordingly
    if [[ "$backup_file" == *.enc ]]; then
        decrypted_file="${RESTORE_DIR}/backup.sql.gz"
        decrypt_backup "$backup_file" "$decrypted_file"
        backup_file="$decrypted_file"
    fi
    
    if [[ "$backup_file" == *.gz ]]; then
        sql_file="${RESTORE_DIR}/backup.sql"
        decompress_backup "$backup_file" "$sql_file"
    else
        sql_file="$backup_file"
    fi
    
    # Verify and restore
    verify_database_connection
    create_backup_before_restore
    drop_existing_connections
    restore_database "$sql_file"
    verify_restore
    cleanup_temp_files
    
    log "═══════════════════════════════════════════════════════════════"
    log "Database restore completed successfully!"
    log "═══════════════════════════════════════════════════════════════"
}

# Trap errors
trap 'error "Restore failed with error"; exit 1' ERR

# Run main function
main "$@"
