# DataShield OSINT - Windows Setup Guide

## 🚨 Quick Fix for Your Error

Your error occurred because:
1. **PowerShell doesn't use `\` for line continuation** (it uses backticks `` ` ``)
2. **The command was split incorrectly** across multiple lines

## ✅ Solution: Use Single-Line Commands

Instead of the multi-line command, use this **single-line** version:

```powershell
docker build -t datashield-osint-backend:latest backend/
```

That's it! You only need ONE image tag, not three.

## 🎯 Complete Windows Setup (Choose One Method)

### Method 1: Automated Script (Recommended)

Simply run the PowerShell script:

```powershell
# Set execution policy (one-time, if needed)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Run setup script
.\setup-windows.ps1
```

This script will:
- ✅ Check Docker is running
- ✅ Build base image
- ✅ Build application image
- ✅ Start all services
- ✅ Run migrations
- ✅ Create admin user

### Method 2: Manual Step-by-Step

#### Step 1: Verify Docker

```powershell
# Check Docker version
docker --version

# Ensure Docker is running
docker ps
```

#### Step 2: Create .env File

```powershell
# Copy template
Copy-Item .env.example .env

# Edit with your preferred editor
notepad .env
# Or
code .env
```

#### Step 3: Build Base Image

```powershell
docker build -f backend/Dockerfile.base -t datashield-base:latest backend/
```

This takes ~10 minutes. Wait for it to complete.

#### Step 4: Build Application Image

```powershell
docker build -t datashield-osint-backend:latest backend/
```

This takes ~1-2 minutes.

#### Step 5: Start All Services

```powershell
docker compose -f docker-compose.dev.yml up -d
```

#### Step 6: Check Services Are Running

```powershell
docker compose ps
```

You should see 8-9 containers running.

#### Step 7: Wait for Services to Initialize

```powershell
# Wait 30 seconds for all services to be ready
Start-Sleep -Seconds 30

# Check PostgreSQL is ready
docker logs datashield_postgres --tail=20
```

Look for: "database system is ready to accept connections"

#### Step 8: Run Database Migrations

```powershell
docker exec -u root datashield_backend bash -c "cd /app && alembic upgrade head"
```

If you get an error about bash not found, try:

```powershell
docker exec -u root datashield_backend sh -c "cd /app && alembic upgrade head"
```

#### Step 9: Create Admin User

```powershell
docker exec -u root datashield_backend python scripts/create_admin.py
```

Note the admin credentials that are displayed.

#### Step 10: Access the Application

Open your browser:
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/docs
- **Flower**: http://localhost:5555

## 🐛 Common Issues on Windows

### Issue 1: "docker: command not found"

**Solution**: Docker Desktop is not installed or not in PATH.

```powershell
# Check if Docker is in PATH
$env:Path -split ';' | Select-String -Pattern 'Docker'

# If not found, restart PowerShell or add to PATH
```

### Issue 2: "Docker daemon is not running"

**Solution**: Start Docker Desktop from the Start Menu.

### Issue 3: "Cannot connect to Docker daemon"

**Solution**: 
```powershell
# Restart Docker Desktop
# Or in PowerShell (as Administrator):
Restart-Service docker
```

### Issue 4: Line Continuation Errors

**Solution**: In PowerShell, use backticks or single-line commands:

```powershell
# ❌ DON'T (bash style - doesn't work in PowerShell)
docker build -t image:tag \
  -f Dockerfile .

# ✅ DO (PowerShell style with backticks)
docker build -t image:tag `
  -f Dockerfile .

# ✅ OR (single line - preferred)
docker build -t image:tag -f Dockerfile .
```

### Issue 5: "Permission denied" on volumes

**Solution**: Enable file sharing in Docker Desktop.

1. Open Docker Desktop
2. Go to Settings → Resources → File Sharing
3. Add your project folder
4. Click "Apply & Restart"

### Issue 6: Slow performance

**Solution**: Allocate more resources to Docker.

1. Open Docker Desktop
2. Go to Settings → Resources
3. Increase CPUs to 4+
4. Increase Memory to 8GB+
5. Click "Apply & Restart"

### Issue 7: Container keeps restarting

```powershell
# Check container logs
docker logs datashield_backend --tail=50

# Check all container status
docker compose -f docker-compose.dev.yml ps

# Restart specific service
docker compose -f docker-compose.dev.yml restart backend
```

### Issue 8: Port already in use

```powershell
# Find what's using port 3000
netstat -ano | findstr :3000

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or change the port in .env
# FRONTEND_PORT=3001
```

## 📝 Useful Commands

### View Logs

```powershell
# All services
docker compose -f docker-compose.dev.yml logs -f

# Specific service
docker compose -f docker-compose.dev.yml logs -f backend

# Last 50 lines
docker compose -f docker-compose.dev.yml logs --tail=50 backend
```

### Stop Services

```powershell
# Stop all services
docker compose -f docker-compose.dev.yml down

# Stop and remove volumes (WARNING: deletes data)
docker compose -f docker-compose.dev.yml down -v
```

### Restart Services

```powershell
# Restart all
docker compose -f docker-compose.dev.yml restart

# Restart specific service
docker compose -f docker-compose.dev.yml restart backend
```

### Access Container Shell

```powershell
# Backend container
docker exec -it datashield_backend bash

# If bash not found
docker exec -it datashield_backend sh

# PostgreSQL
docker exec -it datashield_postgres psql -U datashield -d datashield
```

### Clean Up

```powershell
# Remove all stopped containers
docker container prune -f

# Remove unused images
docker image prune -a -f

# Remove all (containers, images, volumes, networks)
docker system prune -a --volumes -f
```

## 🔧 Debugging

### Check Service Health

```powershell
# Check if all containers are running
docker compose -f docker-compose.dev.yml ps

# Expected status: All should show "Up" or "Up (healthy)"
```

### Test Database Connection

```powershell
docker exec datashield_backend python -c "from app.core.database import engine; print('DB OK' if engine else 'DB Error')"
```

### Test Redis Connection

```powershell
docker exec datashield_redis redis-cli ping
# Should output: PONG
```

### Check API Health

```powershell
# Using PowerShell
Invoke-WebRequest http://localhost:8000/health

# Or using curl (if installed)
curl http://localhost:8000/health
```

## 🚀 Next Steps

After successful setup:

1. **Login to the application**
   - Go to http://localhost:3000
   - Use admin credentials from Step 9

2. **Run a test scan**
   - Click "New Scan"
   - Select "Email"
   - Enter: `test@adobe.com`
   - Click "Start Scan"

3. **Enable monitoring** (optional)
   ```powershell
   docker compose -f docker-compose.dev.yml --profile monitoring up -d
   ```
   - Grafana: http://localhost:3001 (admin / grafana_dev_pass_2024)
   - Prometheus: http://localhost:9090

## 💡 Tips for Windows Users

1. **Use Windows Terminal** instead of old PowerShell
   - Better color support
   - Multiple tabs
   - Better copy/paste

2. **Install Windows Subsystem for Linux (WSL2)** for better Docker performance
   ```powershell
   wsl --install
   ```

3. **Use Git Bash** if you prefer bash commands
   - Comes with Git for Windows
   - Supports bash-style commands

4. **Use VS Code** with these extensions:
   - Docker
   - Remote - Containers
   - Python
   - ESLint

5. **Set Docker Desktop to use WSL2 backend**
   - Settings → General → "Use the WSL 2 based engine"

## 📚 Additional Resources

- [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- [Windows Terminal](https://aka.ms/terminal)
- [Git for Windows](https://git-scm.com/download/win)
- [WSL2 Installation](https://learn.microsoft.com/en-us/windows/wsl/install)
- [VS Code](https://code.visualstudio.com/)

## ⚠️ Important Notes

1. **Antivirus**: Some antivirus software may interfere with Docker. Add Docker Desktop to exclusions if you experience issues.

2. **Hyper-V**: Docker Desktop requires Hyper-V on Windows 10 Pro/Enterprise or WSL2 on Windows 10/11 Home.

3. **File Paths**: Windows uses backslashes (`\`) but Docker uses forward slashes (`/`). Always use forward slashes in Dockerfiles and docker-compose.yml.

4. **Line Endings**: Ensure your editor uses LF (Unix) line endings, not CRLF (Windows), especially for shell scripts.

## 🆘 Still Having Issues?

1. Check logs: `docker compose -f docker-compose.dev.yml logs`
2. Check Docker Desktop logs: Settings → Troubleshoot → View logs
3. Restart Docker Desktop
4. Restart your computer
5. Reinstall Docker Desktop

---

**Need Help?** Open an issue on GitHub with:
- Your Windows version
- Docker version
- Error messages
- Output of `docker compose ps`
- Output of `docker compose logs backend --tail=50`
