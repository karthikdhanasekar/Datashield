# Quick Fix for DataShield Backend Login Issues
# Run this from the datashield-osint folder

Write-Host "Quick Fix: Running migrations and restarting backend..." -ForegroundColor Cyan
cd "C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint"

# Run migrations with PYTHONPATH
docker exec -u root -e PYTHONPATH=/app datashield_backend alembic upgrade head

# Restart backend
docker restart datashield_backend

# Wait for startup
Write-Host "Waiting 15 seconds for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Test
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 10 -UseBasicParsing
    Write-Host "✓ Backend is working!" -ForegroundColor Green
    Write-Host "Login at: http://localhost:3000" -ForegroundColor Cyan
    Write-Host "Email: admin@datashield.com" -ForegroundColor White
    Write-Host "Password: Admin@DataShield2024!" -ForegroundColor White
} catch {
    Write-Host "✗ Backend still not responding" -ForegroundColor Red
    Write-Host "Check logs: docker logs datashield_backend --tail=30" -ForegroundColor Yellow
}
