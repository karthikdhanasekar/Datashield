# DataShield OSINT - Troubleshooting Guide

## 🔴 CRITICAL: Backend Login Fails with ERR_EMPTY_RESPONSE

**Symptoms**:
- Login page loads at `http://localhost:3000`
- When you try to login, it fails with "Login failed"
- Browser console shows: `Failed to load resource: net::ERR_EMPTY_RESPONSE :8000/api/v1/auth/login:1`
- Running `Invoke-WebRequest http://localhost:8000/health` shows "connection was closed unexpectedly"

**Root Cause**: Database migrations haven't run due to missing `PYTHONPATH` environment variable.

### ✅ Quick Fix

Run these commands from the `datashield-osint` folder (NOT the parent folder):

```powershell
# Navigate to the correct directory
cd "C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint"

# Run migrations with PYTHONPATH
docker exec -u root -e PYTHONPATH=/app datashield_backend alembic upgrade head

# Restart backend
docker restart datashield_backend

# Wait for startup
Start-Sleep -Seconds 15

# Test
Invoke-WebRequest http://localhost:8000/health
```

**OR** use the automated fix script:

```powershell
cd "C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint"
.\quick-fix.ps1
```

### 🔍 How to Verify It's Fixed

1. **Test backend health**:
   ```powershell
   Invoke-WebRequest http://localhost:8000/health
   ```
   Should return: `{"status":"healthy","service":"DataShield OSINT","version":"..."}`

2. **Login with default admin account**:
   - Go to: http://localhost:3000
   - Email: `admin@datashield.com`
   - Password: `Admin@DataShield2024!`

### 📌 Common Mistake: Wrong Directory

If you see this error:
```
open C:\Users\karth\Downloads\Online foot print detection with OSINT integration\docker-compose.dev.yml: The system cannot find the file specified.
```

You're in the **parent folder**. You need to be in the **datashield-osint** subfolder:

```powershell
# Wrong (parent folder):
PS C:\Users\karth\Downloads\Online foot print detection with OSINT integration>

# Correct (project folder):
PS C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint>
```

Always run:
```powershell
cd "C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint"
```

### 🐛 Understanding the Error

The error `ModuleNotFoundError: No module named 'app'` happens because:

1. Alembic migrations need to import from the `app` module
2. Python can't find the module without `PYTHONPATH=/app`
3. Without migrations, database tables don't exist
4. Without tables, authentication fails
5. Backend returns empty response instead of proper error

**Solution**: Always add `-e PYTHONPATH=/app` when running alembic commands inside Docker.

---

## 🚨 "localhost refused to connect" on Port 3000

This error means the frontend container is not running or not ready. Follow these steps:

### Step 1: Check if Containers are Running

```powershell
docker compose -f docker-compose.dev.yml ps
```

**Look for**:
- `datashield_frontend` should show `Up` status
- All other containers should also show `Up` or `Up (healthy)`

### Step 2: Check Frontend Container Logs

```powershell
docker compose -f docker-compose.dev.yml logs frontend --tail=50
```

**Common issues you might see**:

#### Issue A: Container is starting
```
frontend_1  | info  - Creating an optimized production build...
```
**Solution**: Wait 2-3 minutes for the build to complete.

#### Issue B: Container crashed
```
frontend_1  | Error: Cannot find module...
```
**Solution**: Rebuild the frontend:
```powershell
docker compose -f docker-compose.dev.yml build frontend
docker compose -f docker-compose.dev.yml up -d frontend
```

#### Issue C: Port conflict
```
Error: Port 3000 is already in use
```
**Solution**: Kill the process using port 3000 or change the port.

### Step 3: Check All Container Status

```powershell
docker compose -f docker-compose.dev.yml ps
```

**Expected output** (all should be "Up"):
```
NAME                      STATUS
datashield_backend        Up (healthy)
datashield_celery_worker  Up
datashield_celery_beat    Up
datashield_elasticsearch  Up (healthy)
datashield_flower         Up
datashield_frontend       Up
datashield_minio          Up (healthy)
datashield_postgres       Up (healthy)
datashield_redis          Up (healthy)
```

### Step 4: Restart Frontend Service

```powershell
docker compose -f docker-compose.dev.yml restart frontend
```

Wait 30 seconds, then try accessing http://localhost:3000 again.

### Step 5: Check if Port 3000 is Accessible

```powershell
# Test if something is listening on port 3000
Test-NetConnection -ComputerName localhost -Port 3000

# Or use netstat
netstat -ano | findstr :3000
```

If nothing is listening, the container isn't running properly.

---

## 🔧 Complete Diagnostic Script

Run this PowerShell script to diagnose all issues:

```powershell
Write-Host "=== DataShield OSINT Diagnostics ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check Docker
Write-Host "1. Checking Docker..." -ForegroundColor Yellow
docker --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Docker not found!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker installed" -ForegroundColor Green
Write-Host ""

# 2. Check if containers are running
Write-Host "2. Checking containers..." -ForegroundColor Yellow
docker compose -f docker-compose.dev.yml ps
Write-Host ""

# 3. Check frontend logs
Write-Host "3. Frontend logs (last 20 lines):" -ForegroundColor Yellow
docker compose -f docker-compose.dev.yml logs frontend --tail=20
Write-Host ""

# 4. Check backend logs
Write-Host "4. Backend logs (last 20 lines):" -ForegroundColor Yellow
docker compose -f docker-compose.dev.yml logs backend --tail=20
Write-Host ""

# 5. Check ports
Write-Host "5. Checking ports..." -ForegroundColor Yellow
$ports = @(3000, 8000, 5432, 6379, 9200)
foreach ($port in $ports) {
    $result = Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue
    if ($result.TcpTestSucceeded) {
        Write-Host "✓ Port $port is open" -ForegroundColor Green
    } else {
        Write-Host "✗ Port $port is not accessible" -ForegroundColor Red
    }
}
Write-Host ""

# 6. Test API health
Write-Host "6. Testing backend API..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:8000/health -TimeoutSec 5
    Write-Host "✓ Backend API is responding: $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "✗ Backend API is not responding" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== Diagnostics Complete ===" -ForegroundColor Cyan
```

---

## 🛠️ Common Solutions

### Solution 1: Complete Restart

```powershell
# Stop everything
docker compose -f docker-compose.dev.yml down

# Wait 5 seconds
Start-Sleep -Seconds 5

# Start everything
docker compose -f docker-compose.dev.yml up -d

# Wait 60 seconds for services to initialize
Start-Sleep -Seconds 60

# Check status
docker compose -f docker-compose.dev.yml ps
```

### Solution 2: Rebuild Frontend

```powershell
# Stop frontend
docker compose -f docker-compose.dev.yml stop frontend

# Remove frontend container
docker compose -f docker-compose.dev.yml rm -f frontend

# Rebuild frontend
docker compose -f docker-compose.dev.yml build --no-cache frontend

# Start frontend
docker compose -f docker-compose.dev.yml up -d frontend

# Watch logs
docker compose -f docker-compose.dev.yml logs -f frontend
```

### Solution 3: Check Frontend Dockerfile

The frontend needs to be built. Check if `frontend/Dockerfile` exists:

```powershell
Test-Path frontend/Dockerfile
```

If it doesn't exist, create it:

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
```

### Solution 4: Check Environment Variables

```powershell
# Check if .env file exists
Get-Content .env | Select-String "NEXT_PUBLIC_API_URL"

# Should show:
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

If missing, add to `.env`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Solution 5: Port Conflict Resolution

If port 3000 is already in use:

```powershell
# Find what's using port 3000
netstat -ano | findstr :3000

# Example output:
# TCP    0.0.0.0:3000    0.0.0.0:0    LISTENING    1234

# Kill the process (replace 1234 with actual PID)
taskkill /PID 1234 /F

# Or change the port in docker-compose.dev.yml
# ports:
#   - "3001:3000"  # Use 3001 instead
```

---

## 📝 Step-by-Step Recovery Process

### Step 1: Clean Slate

```powershell
# Stop and remove everything
docker compose -f docker-compose.dev.yml down -v

# Remove dangling images
docker image prune -f

# Remove stopped containers
docker container prune -f
```

### Step 2: Verify Docker Resources

```powershell
# Check Docker has enough resources
docker system df

# If low on space, clean up
docker system prune -a --volumes
```

### Step 3: Rebuild Everything

```powershell
# Build base image
docker build -f backend/Dockerfile.base -t datashield-base:latest backend/

# Build backend
docker build -t datashield-osint-backend:latest backend/

# Start services
docker compose -f docker-compose.dev.yml up -d
```

### Step 4: Monitor Startup

```powershell
# Watch all logs
docker compose -f docker-compose.dev.yml logs -f

# Press Ctrl+C to stop watching
```

Look for these success messages:
- **PostgreSQL**: `database system is ready to accept connections`
- **Redis**: `Ready to accept connections`
- **Backend**: `Uvicorn running on http://0.0.0.0:8000`
- **Frontend**: `ready - started server on 0.0.0.0:3000`

### Step 5: Verify Each Service

```powershell
# Test backend
Invoke-WebRequest http://localhost:8000/health

# Test frontend
Invoke-WebRequest http://localhost:3000

# Test database
docker exec datashield_postgres pg_isready -U datashield

# Test Redis
docker exec datashield_redis redis-cli ping
```

---

## 🐛 Specific Error Messages

### Error: "Cannot find module"

**Frontend logs show**: `Error: Cannot find module 'next'`

**Solution**:
```powershell
docker compose -f docker-compose.dev.yml exec frontend npm install
docker compose -f docker-compose.dev.yml restart frontend
```

### Error: "ENOENT: no such file or directory"

**Solution**: Missing files in frontend directory
```powershell
# Check if package.json exists
Test-Path frontend/package.json

# If missing, there's a problem with your repository
git status
git pull origin main
```

### Error: "Network error"

**Frontend logs show**: `Network request failed`

**Solution**: Frontend can't reach backend
```powershell
# Check backend is running
docker compose -f docker-compose.dev.yml ps backend

# Check backend logs
docker compose -f docker-compose.dev.yml logs backend --tail=50

# Verify NEXT_PUBLIC_API_URL in .env
Get-Content .env | Select-String "NEXT_PUBLIC_API_URL"
```

### Error: "Port is already allocated"

**Solution**:
```powershell
# Change the port in docker-compose.dev.yml
# Before:
#   ports:
#     - "3000:3000"
# After:
#   ports:
#     - "3001:3000"

# Then restart
docker compose -f docker-compose.dev.yml up -d

# Access at http://localhost:3001
```

---

## 🎯 Quick Health Check Command

Save this as `check-health.ps1`:

```powershell
$services = @{
    "Frontend" = "http://localhost:3000"
    "Backend" = "http://localhost:8000/health"
    "API Docs" = "http://localhost:8000/api/docs"
    "Flower" = "http://localhost:5555"
    "MinIO" = "http://localhost:9001"
}

Write-Host "=== Service Health Check ===" -ForegroundColor Cyan
Write-Host ""

foreach ($service in $services.GetEnumerator()) {
    try {
        $response = Invoke-WebRequest -Uri $service.Value -TimeoutSec 3 -ErrorAction Stop
        Write-Host "✓ $($service.Key) is UP [$($response.StatusCode)]" -ForegroundColor Green
    } catch {
        Write-Host "✗ $($service.Key) is DOWN" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Container Status ===" -ForegroundColor Cyan
docker compose -f docker-compose.dev.yml ps
```

Run it:
```powershell
.\check-health.ps1
```

---

## 💡 Prevention Tips

1. **Always wait for services to initialize**
   ```powershell
   docker compose -f docker-compose.dev.yml up -d
   Start-Sleep -Seconds 60  # Wait 1 minute
   ```

2. **Check logs before accessing**
   ```powershell
   docker compose -f docker-compose.dev.yml logs frontend --tail=10
   ```

3. **Allocate enough Docker resources**
   - Open Docker Desktop
   - Settings → Resources
   - CPU: At least 4
   - Memory: At least 8GB

4. **Keep Docker Desktop updated**
   ```powershell
   docker version
   ```

---

## 🆘 Still Not Working?

1. **Collect diagnostic information**:
   ```powershell
   # Save all logs
   docker compose -f docker-compose.dev.yml logs > logs.txt
   
   # Save container status
   docker compose -f docker-compose.dev.yml ps > status.txt
   
   # Save Docker info
   docker info > docker-info.txt
   ```

2. **Check the specific error in frontend logs**:
   ```powershell
   docker compose -f docker-compose.dev.yml logs frontend > frontend-logs.txt
   notepad frontend-logs.txt
   ```

3. **Try accessing backend directly** (should work even if frontend doesn't):
   - Go to http://localhost:8000/api/docs
   - If this works, the issue is frontend-specific

4. **Share the output** of:
   - `docker compose -f docker-compose.dev.yml ps`
   - `docker compose -f docker-compose.dev.yml logs frontend --tail=50`
   - `docker compose -f docker-compose.dev.yml logs backend --tail=50`

---

**Remember**: Most issues are fixed by simply waiting longer for services to start (60-90 seconds) or doing a complete restart!
