# Docker Setup Guide for VS Code

## Current Status
✅ VS Code Docker Extension is installed
❌ Docker Desktop/CLI is not available

## What You Need to Do

### Step 1: Install Docker Desktop
The VS Code Docker extension requires Docker Desktop to be installed separately:

1. **Download Docker Desktop:**
   - Go to: https://www.docker.com/products/docker-desktop/
   - Download the Windows version
   - Run the installer

2. **Installation Notes:**
   - Choose "Use WSL 2 instead of Hyper-V" if prompted
   - Allow the installer to enable required Windows features
   - Restart your computer if prompted

3. **Verify Installation:**
   - Look for Docker Desktop in your Start menu
   - Launch Docker Desktop
   - Wait for it to fully initialize (whale icon in system tray)

### Step 2: Test Docker Access
Once Docker Desktop is running:

```powershell
# Test Docker CLI
docker --version

# Test Docker Compose
docker compose version

# Test basic functionality
docker run hello-world
```

### Step 3: Build Your Plex Auto-Prune Container
Once Docker is working:

```powershell
# Navigate to your project
cd D:\guardian

# Build the container
docker compose build

# Test the configuration
docker compose run --rm plex-autoprune-daemon python -c "from main import *; print('Config OK')"

# Start the service
docker compose up -d

# View logs
docker compose logs -f
```

## Alternative: Use VS Code Dev Containers
If you prefer a different approach, you can use VS Code's Dev Containers:

1. Install the "Dev Containers" extension
2. Open Command Palette (Ctrl+Shift+P)
3. Type "Dev Containers: Reopen in Container"
4. This will build and run your project in a container

## Troubleshooting

### If Docker Desktop won't start:
- Enable WSL 2: `wsl --install`
- Enable Hyper-V in Windows Features
- Check antivirus software isn't blocking Docker

### If VS Code can't see Docker:
- Restart VS Code after installing Docker Desktop
- Make sure Docker Desktop is running (check system tray)
- Try refreshing the Docker extension panel in VS Code

### If builds fail:
- Check your .env file has real values (not placeholders)
- Ensure Docker has enough memory allocated (4GB+ recommended)
- Check Windows Defender isn't scanning the project folder

## Using VS Code Docker Extension

Once Docker Desktop is running, you can use VS Code's Docker extension:

1. **View Containers:** Open Docker panel in VS Code sidebar
2. **Build Images:** Right-click docker-compose.yml → "Compose Up"
3. **View Logs:** Right-click container → "View Logs"
4. **Shell Access:** Right-click container → "Attach Shell"

## Quick Commands for Your Project

```powershell
# Build and test everything
docker compose build
docker compose run --rm plex-autoprune-daemon python -c "from main import *; print('✅ All good!')"

# Start in dry-run mode (safe testing)
docker compose up -d

# Check if it's working
docker compose logs -f

# Stop the service
docker compose down
```

Remember to configure your .env file with real values before starting!