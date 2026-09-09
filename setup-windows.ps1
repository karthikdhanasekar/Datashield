# DataShield OSINT - Windows PowerShell Setup Script
# Run this script in PowerShell to build and start the platform

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DataShield OSINT - Windows Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "✓ Docker is installed: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not installed or not running!" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Red
    exit 1
}

# Check if Docker is running
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Docker is not running! Please start Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker is running" -ForegroundColor Green
Write-Host ""

# Check if .env file exists
if (-Not (Test-Path ".env")) {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✓ .env file created. Please edit it with your settings." -ForegroundColor Green
    } else {
        Write-Host "✗ .env.example not found!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ .env file exists" -ForegroundColor Green
}
Write-Host ""

# Step 1: Build base image
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 1: Building base image (this may take ~10 minutes)..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

docker build -f backend/Dockerfile.base -t datashield-base:latest backend/

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to build base image!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Base image built successfully" -ForegroundColor Green
Write-Host ""

# Step 2: Build application images
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 2: Building application images..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

docker build -t datashield-osint-backend:latest backend/

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to build backend image!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Backend image built successfully" -ForegroundColor Green
Write-Host ""

# Step 3: Start services
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 3: Starting services..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

docker compose -f docker-compose.dev.yml up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to start services!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Services started successfully" -ForegroundColor Green
Write-Host ""

# Wait for services to be ready
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Step 4: Run database migrations
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 4: Running database migrations..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

docker exec -u root datashield_backend powershell -Command "Set-Location /app; alembic upgrade head"

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠ Migrations might have failed. Checking logs..." -ForegroundColor Yellow
    docker logs datashield_backend --tail=20
} else {
    Write-Host "✓ Database migrations completed" -ForegroundColor Green
}
Write-Host ""

# Step 5: Create admin user
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 5: Creating admin user..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

docker exec -u root datashield_backend powershell -Command "Set-Location /app; python scripts/create_admin.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠ Admin user creation might have failed." -ForegroundColor Yellow
} else {
    Write-Host "✓ Admin user created" -ForegroundColor Green
}
Write-Host ""

# Final status
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services are running at:" -ForegroundColor Yellow
Write-Host "  Frontend:      http://localhost:3000" -ForegroundColor White
Write-Host "  Backend API:   http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs:      http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  Flower:        http://localhost:5555" -ForegroundColor White
Write-Host "  MinIO Console: http://localhost:9001" -ForegroundColor White
Write-Host ""
Write-Host "Default admin credentials:" -ForegroundColor Yellow
Write-Host "  Email:    admin@datashield.com" -ForegroundColor White
Write-Host "  Password: Admin@DataShield2024!" -ForegroundColor White
Write-Host ""
Write-Host "To view logs: docker compose -f docker-compose.dev.yml logs -f" -ForegroundColor Cyan
Write-Host "To stop:      docker compose -f docker-compose.dev.yml down" -ForegroundColor Cyan
Write-Host ""
