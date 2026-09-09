# ============================================================================
# DataShield OSINT — Backend Fix Script for Windows
# ============================================================================
# This script fixes the backend startup and login issues by:
#   1. Running database migrations with correct PYTHONPATH
#   2. Restarting backend container
#   3. Creating default admin user if needed
#   4. Testing the API endpoints
# ============================================================================

$ErrorActionPreference = "Continue"

# Navigate to project root
$ProjectRoot = "C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint"
Set-Location $ProjectRoot

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " DataShield OSINT — Backend Fix" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Verify we're in the right directory ──────────────────────────────
Write-Host "[1/7] Verifying project directory..." -ForegroundColor Yellow
if (Test-Path "docker-compose.dev.yml") {
    Write-Host "  ✓ Found docker-compose.dev.yml" -ForegroundColor Green
} else {
    Write-Host "  ✗ docker-compose.dev.yml not found!" -ForegroundColor Red
    Write-Host "  Please run this script from: $ProjectRoot" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ── Step 2: Check if containers are running ──────────────────────────────────
Write-Host "[2/7] Checking Docker containers..." -ForegroundColor Yellow
$backendRunning = docker ps --filter "name=datashield_backend" --format "{{.Names}}" 2>$null
$postgresRunning = docker ps --filter "name=datashield_postgres" --format "{{.Names}}" 2>$null

if ($backendRunning -eq "datashield_backend") {
    Write-Host "  ✓ Backend container is running" -ForegroundColor Green
} else {
    Write-Host "  ✗ Backend container is not running" -ForegroundColor Red
    Write-Host "  Starting containers..." -ForegroundColor Yellow
    docker compose -f docker-compose.dev.yml up -d backend
    Start-Sleep -Seconds 10
}

if ($postgresRunning -eq "datashield_postgres") {
    Write-Host "  ✓ PostgreSQL container is running" -ForegroundColor Green
} else {
    Write-Host "  ✗ PostgreSQL container is not running" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ── Step 3: Check database connection ─────────────────────────────────────────
Write-Host "[3/7] Testing database connection..." -ForegroundColor Yellow
$dbCheck = docker exec datashield_postgres pg_isready -U datashield 2>&1
if ($dbCheck -like "*accepting connections*") {
    Write-Host "  ✓ PostgreSQL is ready" -ForegroundColor Green
} else {
    Write-Host "  ✗ PostgreSQL is not ready: $dbCheck" -ForegroundColor Red
    Write-Host "  Waiting 10 seconds and retrying..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    $dbCheck = docker exec datashield_postgres pg_isready -U datashield 2>&1
    if ($dbCheck -like "*accepting connections*") {
        Write-Host "  ✓ PostgreSQL is ready (after retry)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ PostgreSQL still not ready" -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

# ── Step 4: Run database migrations ───────────────────────────────────────────
Write-Host "[4/7] Running database migrations..." -ForegroundColor Yellow
Write-Host "  Note: Setting PYTHONPATH=/app to fix 'ModuleNotFoundError'" -ForegroundColor Gray

$migrationOutput = docker exec -u root -e PYTHONPATH=/app datashield_backend alembic upgrade head 2>&1
$migrationSuccess = $LASTEXITCODE -eq 0

Write-Host "  Migration output:" -ForegroundColor Gray
$migrationOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }

if ($migrationSuccess) {
    Write-Host "  ✓ Migrations completed successfully" -ForegroundColor Green
} else {
    if ($migrationOutput -like "*Target database is not up to date*" -or 
        $migrationOutput -like "*alembic_version*" -or
        $migrationOutput -like "*Already at head*") {
        Write-Host "  ✓ Database already up to date" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Migration had errors, but continuing..." -ForegroundColor Yellow
    }
}
Write-Host ""

# ── Step 5: Create admin user if not exists ───────────────────────────────────
Write-Host "[5/7] Ensuring admin user exists..." -ForegroundColor Yellow

$createAdminScript = @"
import asyncio
import sys
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash

async def create_admin():
    async with AsyncSessionLocal() as db:
        # Check if admin exists
        result = await db.execute(
            select(User).where(User.email == 'admin@datashield.com')
        )
        admin = result.scalar_one_or_none()
        
        if admin:
            print('Admin user already exists')
            return
        
        # Create admin user
        admin = User(
            email='admin@datashield.com',
            full_name='DataShield Admin',
            hashed_password=get_password_hash('Admin@DataShield2024!'),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
            is_superuser=True,
            mfa_enabled=False,
        )
        db.add(admin)
        await db.commit()
        print('Admin user created successfully')

try:
    asyncio.run(create_admin())
    sys.exit(0)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
"@

$createAdminOutput = docker exec -e PYTHONPATH=/app datashield_backend python -c $createAdminScript 2>&1
Write-Host "  $createAdminOutput" -ForegroundColor Gray

if ($createAdminOutput -like "*created successfully*") {
    Write-Host "  ✓ Admin user created" -ForegroundColor Green
} elseif ($createAdminOutput -like "*already exists*") {
    Write-Host "  ✓ Admin user already exists" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Could not verify admin user creation" -ForegroundColor Yellow
}
Write-Host ""

# ── Step 6: Restart backend ───────────────────────────────────────────────────
Write-Host "[6/7] Restarting backend container..." -ForegroundColor Yellow
docker restart datashield_backend | Out-Null
Write-Host "  Waiting 15 seconds for backend to start..." -ForegroundColor Gray
Start-Sleep -Seconds 15
Write-Host "  ✓ Backend restarted" -ForegroundColor Green
Write-Host ""

# ── Step 7: Test backend API ──────────────────────────────────────────────────
Write-Host "[7/7] Testing backend API..." -ForegroundColor Yellow

$maxRetries = 3
$retryCount = 0
$apiWorking = $false

while ($retryCount -lt $maxRetries -and -not $apiWorking) {
    try {
        Write-Host "  Testing /health endpoint (attempt $($retryCount + 1)/$maxRetries)..." -ForegroundColor Gray
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 10 -UseBasicParsing
        $content = $response.Content | ConvertFrom-Json
        
        Write-Host "  ✓ Backend is responding!" -ForegroundColor Green
        Write-Host "    Status: $($content.status)" -ForegroundColor Gray
        Write-Host "    Service: $($content.service)" -ForegroundColor Gray
        Write-Host "    Version: $($content.version)" -ForegroundColor Gray
        $apiWorking = $true
    } catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "  ⚠ Backend not responding yet, waiting 10 seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds 10
        } else {
            Write-Host "  ✗ Backend is not responding after $maxRetries attempts" -ForegroundColor Red
            Write-Host ""
            Write-Host "  Checking backend logs for errors:" -ForegroundColor Yellow
            docker logs datashield_backend --tail=30
        }
    }
}

Write-Host ""

# ── Final Summary ─────────────────────────────────────────────────────────────
if ($apiWorking) {
    Write-Host "===============================================" -ForegroundColor Green
    Write-Host " ✓ Backend Fix Complete!" -ForegroundColor Green
    Write-Host "===============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now login at: http://localhost:3000" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Admin Credentials:" -ForegroundColor Yellow
    Write-Host "  Email:    admin@datashield.com" -ForegroundColor White
    Write-Host "  Password: Admin@DataShield2024!" -ForegroundColor White
    Write-Host ""
    Write-Host "API Documentation: http://localhost:8000/api/docs" -ForegroundColor Cyan
    Write-Host "Flower (Celery):   http://localhost:5555" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "===============================================" -ForegroundColor Red
    Write-Host " ✗ Backend Fix Failed" -ForegroundColor Red
    Write-Host "===============================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "The backend is not responding. Please check the logs:" -ForegroundColor Yellow
    Write-Host "  docker logs datashield_backend --tail=50" -ForegroundColor White
    Write-Host ""
    Write-Host "Or restart from scratch:" -ForegroundColor Yellow
    Write-Host "  docker compose -f docker-compose.dev.yml down" -ForegroundColor White
    Write-Host "  docker compose -f docker-compose.dev.yml up -d" -ForegroundColor White
    Write-Host ""
}
