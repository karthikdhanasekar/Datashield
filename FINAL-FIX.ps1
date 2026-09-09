# ============================================================================
# DataShield OSINT - FINAL FIX for Login Issues
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " DataShield OSINT - Final Fix" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Navigate to correct directory
$ProjectRoot = "C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint"
Set-Location $ProjectRoot
Write-Host "[1/5] Changed to project directory" -ForegroundColor Green
Write-Host ""

# Step 2: Stop and restart containers with new .env
Write-Host "[2/5] Restarting all containers with updated .env..." -ForegroundColor Yellow
docker compose -f docker-compose.dev.yml down
Start-Sleep -Seconds 5
docker compose -f docker-compose.dev.yml up -d
Write-Host "      Waiting 30 seconds for containers to start..." -ForegroundColor Gray
Start-Sleep -Seconds 30
Write-Host "      Containers restarted" -ForegroundColor Green
Write-Host ""

# Step 3: Check database is ready
Write-Host "[3/5] Checking database..." -ForegroundColor Yellow
$maxRetries = 5
$retryCount = 0
$dbReady = $false

while ($retryCount -lt $maxRetries -and -not $dbReady) {
    $dbCheck = docker exec datashield_postgres pg_isready -U datashield 2>&1
    if ($dbCheck -like "*accepting connections*") {
        Write-Host "      Database is ready" -ForegroundColor Green
        $dbReady = $true
    } else {
        $retryCount++
        Write-Host "      Waiting for database... (attempt $retryCount/$maxRetries)" -ForegroundColor Gray
        Start-Sleep -Seconds 5
    }
}

if (-not $dbReady) {
    Write-Host "      ERROR: Database not ready" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 4: Run migrations
Write-Host "[4/5] Running database migrations..." -ForegroundColor Yellow
$migrationResult = docker exec -e PYTHONPATH=/app datashield_backend alembic upgrade head 2>&1
Write-Host "      Migration output:" -ForegroundColor Gray
$migrationResult | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
Write-Host "      Migrations completed" -ForegroundColor Green
Write-Host ""

# Step 5: Test backend
Write-Host "[5/5] Testing backend API..." -ForegroundColor Yellow
docker restart datashield_backend | Out-Null
Write-Host "      Waiting 20 seconds for backend..." -ForegroundColor Gray
Start-Sleep -Seconds 20

$maxRetries = 5
$retryCount = 0
$apiWorking = $false

while ($retryCount -lt $maxRetries -and -not $apiWorking) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 10 -UseBasicParsing
        $content = $response.Content | ConvertFrom-Json
        Write-Host "      Backend is responding!" -ForegroundColor Green
        Write-Host "      Status: $($content.status)" -ForegroundColor Gray
        $apiWorking = $true
    } catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "      Waiting for backend... (attempt $retryCount/$maxRetries)" -ForegroundColor Gray
            Start-Sleep -Seconds 10
        }
    }
}

Write-Host ""

# Final summary
if ($apiWorking) {
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host " SUCCESS! Backend is now working!" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Login at: http://localhost:3000" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Credentials:" -ForegroundColor Yellow
    Write-Host "  Email:    admin@datashield.com" -ForegroundColor White
    Write-Host "  Password: Admin@DataShield2024!" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "=============================================" -ForegroundColor Red
    Write-Host " Backend still not responding" -ForegroundColor Red
    Write-Host "=============================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check logs with:" -ForegroundColor Yellow
    Write-Host "  docker logs datashield_backend --tail=50" -ForegroundColor White
    Write-Host ""
}
