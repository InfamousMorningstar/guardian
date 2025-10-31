@echo off
REM Plex Auto-Prune Daemon - Docker Test Script (Windows)
REM This script builds and tests the Docker container

echo 🔧 Testing Plex Auto-Prune Daemon Docker Setup
echo ==============================================

REM Check if Docker is available
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed or not in PATH
    echo Please install Docker Desktop: https://www.docker.com/products/docker-desktop
    exit /b 1
)

echo ✅ Docker is available

REM Check for .env file
if not exist ".env" (
    echo ⚠️  No .env file found. Creating from example...
    copy .env.example .env
    echo ❗ Please edit .env file with your actual configuration before running!
    echo    Required: PLEX_TOKEN, PLEX_SERVER_NAME, TAUTULLI_URL, TAUTULLI_API_KEY
    echo    Required: SMTP settings for email notifications
    exit /b 1
)

echo ✅ Environment file found

REM Check for placeholder values
findstr /C:"your_" .env >nul
if %errorlevel% equ 0 (
    echo ❗ Some environment variables still have placeholder values
    echo    Please update your .env file with actual values
    echo    Check: PLEX_TOKEN, TAUTULLI_API_KEY, SMTP credentials
    exit /b 1
)

echo ✅ Environment variables appear to be configured

REM Build the Docker image
echo 🔨 Building Docker image...
docker compose build
if %errorlevel% neq 0 (
    echo ❌ Docker build failed
    exit /b 1
)

echo ✅ Docker image built successfully

REM Test configuration validation
echo 🧪 Testing configuration validation...
docker compose run --rm plex-autoprune-daemon python -c "import os; from main import *; print('✅ Configuration validation passed'); print(f'✅ Plex Token: {PLEX_TOKEN[:10]}...'); print(f'✅ Tautulli URL: {TAUTULLI_URL}'); print(f'✅ SMTP Host: {SMTP_HOST}'); print(f'✅ Admin Email: {ADMIN_EMAIL}'); print(f'✅ Warn Days: {WARN_DAYS}'); print(f'✅ Kick Days: {KICK_DAYS}'); print(f'✅ Dry Run: {os.environ.get(\"DRY_RUN\", \"true\")}')"
if %errorlevel% neq 0 (
    echo ❌ Configuration test failed
    exit /b 1
)

echo ✅ Configuration test passed

REM Test Plex connectivity
echo 🔗 Testing Plex connectivity...
docker compose run --rm plex-autoprune-daemon python -c "from main import get_plex_account, get_plex_server_resource; acct = get_plex_account(); print(f'✅ Connected to Plex account: {acct.username}'); server = get_plex_server_resource(acct); print(f'✅ Found Plex server: {server.name}')"
if %errorlevel% neq 0 (
    echo ❌ Plex connection test failed
    exit /b 1
)

REM Test Tautulli connectivity
echo 📊 Testing Tautulli connectivity...
docker compose run --rm plex-autoprune-daemon python -c "from main import tautulli_users; users = tautulli_users(); print(f'✅ Connected to Tautulli, found {len(users)} users')"
if %errorlevel% neq 0 (
    echo ❌ Tautulli connection test failed
    exit /b 1
)

echo.
echo 🎉 All tests passed! The Docker setup is working correctly.
echo.
echo To start the daemon:
echo   docker compose up -d
echo.
echo To view logs:
echo   docker compose logs -f
echo.
echo To stop the daemon:
echo   docker compose down
echo.
echo ⚠️  Remember: Set DRY_RUN=false in .env when ready for production!