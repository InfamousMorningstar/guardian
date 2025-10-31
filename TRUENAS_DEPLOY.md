# TrueNAS Scale Deployment Guide

## Essential Files Only

For TrueNAS Scale deployment, you only need these files:
- `Dockerfile` - Container build instructions
- `main.py` - Application code  
- `requirements.txt` - Python dependencies
- `.dockerignore` - Build optimization

## Quick Deploy Steps

### 1. Build Container (Optional)
```bash
# If building locally
docker build -t plex-autoprune-daemon .
```

### 2. TrueNAS Scale App Configuration

**Application Name:** `plex-autoprune-daemon`

**Container Image:** 
- Repository: `plex-autoprune-daemon` (or your registry)
- Tag: `latest`

**Environment Variables:**
```
PLEX_TOKEN=your_plex_token_here
PLEX_SERVER_NAME=your_plex_server_name
TAUTULLI_URL=http://192.168.1.113:8181
TAUTULLI_API_KEY=your_tautulli_api_key
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=your_email@gmail.com
ADMIN_EMAIL=admin@example.com
WARN_DAYS=27
KICK_DAYS=30
CHECK_NEW_USERS_SECS=120
CHECK_INACTIVITY_SECS=1800
DRY_RUN=true
VIP_NAMES=friend1,family_member
```

**Storage:**
- Host Path: `/mnt/pool/appdata/plex-autoprune/state`
- Mount Path: `/app/state`

**Network:** Host Network (recommended)

### 3. Monitor
- Check logs in TrueNAS Scale Apps UI
- Set `DRY_RUN=false` when ready for production

## Files You Can Delete

These files are NOT needed for TrueNAS Scale:
- `docker-compose.yml` (TrueNAS uses its own orchestration)
- `.env` / `.env.example` (use TrueNAS environment variables instead)
- Test scripts and guides (functionality is built into TrueNAS)