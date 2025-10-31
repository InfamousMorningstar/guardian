#!/bin/bash

# Plex Auto-Prune Daemon - Docker Test Script
# This script builds and tests the Docker container

set -e  # Exit on any error

echo "🔧 Testing Plex Auto-Prune Daemon Docker Setup"
echo "=============================================="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available"
    echo "Please install Docker Compose or update Docker Desktop"
    exit 1
fi

echo "✅ Docker is available"

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from example..."
    cp .env.example .env
    echo "❗ Please edit .env file with your actual configuration before running!"
    echo "   Required: PLEX_TOKEN, PLEX_SERVER_NAME, TAUTULLI_URL, TAUTULLI_API_KEY"
    echo "   Required: SMTP settings for email notifications"
    exit 1
fi

echo "✅ Environment file found"

# Validate that required environment variables are not using placeholder values
if grep -q "your_.*_here" .env; then
    echo "❗ Some environment variables still have placeholder values"
    echo "   Please update your .env file with actual values"
    echo "   Check: PLEX_TOKEN, TAUTULLI_API_KEY, SMTP credentials"
    exit 1
fi

echo "✅ Environment variables appear to be configured"

# Build the Docker image
echo "🔨 Building Docker image..."
if command -v docker-compose &> /dev/null; then
    docker-compose build
else
    docker compose build
fi

echo "✅ Docker image built successfully"

# Test configuration validation (dry run)
echo "🧪 Testing configuration validation..."
if command -v docker-compose &> /dev/null; then
    docker-compose run --rm plex-autoprune-daemon python -c "
import os
from main import *
print('✅ Configuration validation passed')
print(f'✅ Plex Token: {PLEX_TOKEN[:10]}...')
print(f'✅ Tautulli URL: {TAUTULLI_URL}')
print(f'✅ SMTP Host: {SMTP_HOST}')
print(f'✅ Admin Email: {ADMIN_EMAIL}')
print(f'✅ Warn Days: {WARN_DAYS}')
print(f'✅ Kick Days: {KICK_DAYS}')
print(f'✅ Dry Run: {os.environ.get(\"DRY_RUN\", \"true\")}')
"
else
    docker compose run --rm plex-autoprune-daemon python -c "
import os
from main import *
print('✅ Configuration validation passed')
print(f'✅ Plex Token: {PLEX_TOKEN[:10]}...')
print(f'✅ Tautulli URL: {TAUTULLI_URL}')
print(f'✅ SMTP Host: {SMTP_HOST}')
print(f'✅ Admin Email: {ADMIN_EMAIL}')
print(f'✅ Warn Days: {WARN_DAYS}')
print(f'✅ Kick Days: {KICK_DAYS}')
print(f'✅ Dry Run: {os.environ.get(\"DRY_RUN\", \"true\")}')
"
fi

echo "✅ Configuration test passed"

# Test Plex connectivity
echo "🔗 Testing Plex connectivity..."
if command -v docker-compose &> /dev/null; then
    docker-compose run --rm plex-autoprune-daemon python -c "
from main import get_plex_account, get_plex_server_resource
try:
    acct = get_plex_account()
    print(f'✅ Connected to Plex account: {acct.username}')
    server = get_plex_server_resource(acct)
    print(f'✅ Found Plex server: {server.name}')
except Exception as e:
    print(f'❌ Plex connection failed: {e}')
    exit(1)
"
else
    docker compose run --rm plex-autoprune-daemon python -c "
from main import get_plex_account, get_plex_server_resource
try:
    acct = get_plex_account()
    print(f'✅ Connected to Plex account: {acct.username}')
    server = get_plex_server_resource(acct)
    print(f'✅ Found Plex server: {server.name}')
except Exception as e:
    print(f'❌ Plex connection failed: {e}')
    exit(1)
"
fi

# Test Tautulli connectivity
echo "📊 Testing Tautulli connectivity..."
if command -v docker-compose &> /dev/null; then
    docker-compose run --rm plex-autoprune-daemon python -c "
from main import tautulli_users
try:
    users = tautulli_users()
    print(f'✅ Connected to Tautulli, found {len(users)} users')
except Exception as e:
    print(f'❌ Tautulli connection failed: {e}')
    exit(1)
"
else
    docker compose run --rm plex-autoprune-daemon python -c "
from main import tautulli_users
try:
    users = tautulli_users()
    print(f'✅ Connected to Tautulli, found {len(users)} users')
except Exception as e:
    print(f'❌ Tautulli connection failed: {e}')
    exit(1)
"
fi

echo ""
echo "🎉 All tests passed! The Docker setup is working correctly."
echo ""
echo "To start the daemon:"
if command -v docker-compose &> /dev/null; then
    echo "  docker-compose up -d"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "To stop the daemon:"
    echo "  docker-compose down"
else
    echo "  docker compose up -d"
    echo ""
    echo "To view logs:"
    echo "  docker compose logs -f"
    echo ""
    echo "To stop the daemon:"
    echo "  docker compose down"
fi
echo ""
echo "⚠️  Remember: Set DRY_RUN=false in .env when ready for production!"