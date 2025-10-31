# Plex Auto-Prune Daemon

A Docker container that automatically manages Plex user access based on activity levels. Perfect for TrueNAS Scale deployment.

## Features

- **Automatic User Onboarding**: Sends welcome emails to new Plex users
- **Inactivity Monitoring**: Tracks user viewing activity via Tautulli
- **Graduated Warnings**: Sends warning emails before removing inactive users
- **Email Notifications**: Beautiful HTML emails with Centauri branding
- **Discord Integration**: Optional webhook notifications
- **Admin Alerts**: Detailed admin notifications for all actions
- **VIP Protection**: Protect friends and family by email or username
- **Dry Run Mode**: Test configuration without making changes

## TrueNAS Scale Deployment

### Prerequisites

- TrueNAS Scale with Docker/Kubernetes apps enabled
- Plex Media Server with admin access
- Tautulli installed and configured
- SMTP server for email notifications (Gmail, etc.)

### Required Files

Only these files are needed for deployment:
- `Dockerfile` - Container build instructions
- `main.py` - Application code
- `requirements.txt` - Python dependencies
- `.dockerignore` - Build optimization
- `README.md` - This documentation

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLEX_TOKEN` | ✅ | - | Plex authentication token |
| `PLEX_SERVER_NAME` | ✅ | - | Name of your Plex server |
| `TAUTULLI_URL` | ✅ | - | Tautulli base URL |
| `TAUTULLI_API_KEY` | ✅ | - | Tautulli API key |
| `SMTP_HOST` | ✅ | - | SMTP server hostname |
| `SMTP_PORT` | ✅ | - | SMTP server port |
| `SMTP_USERNAME` | ✅ | - | SMTP username |
| `SMTP_PASSWORD` | ✅ | - | SMTP password |
| `SMTP_FROM` | ✅ | - | From email address |
| `ADMIN_EMAIL` | ✅ | - | Admin notification email |
| `WARN_DAYS` | ❌ | 27 | Days before warning |
| `KICK_DAYS` | ❌ | 30 | Days before removal |
| `CHECK_NEW_USERS_SECS` | ❌ | 120 | New user check interval |
| `CHECK_INACTIVITY_SECS` | ❌ | 1800 | Inactivity check interval |
| `DRY_RUN` | ❌ | true | Test mode (no actual removals) |
| `VIP_NAMES` | ❌ | - | VIP usernames to protect (comma-separated) |
| `DISCORD_WEBHOOK` | ❌ | - | Discord webhook URL |

### Getting Required Tokens

**Plex Token:**
1. Log into Plex Web App
2. Open browser dev tools (F12)
3. Go to Network tab, refresh page
4. Look for requests with `X-Plex-Token` header
5. Copy the token value

**Tautulli API Key:**
1. Open Tautulli web interface
2. Go to Settings → Web Interface
3. Copy the API Key

**Gmail App Password:**
1. Enable 2FA on your Google account
2. Go to Google Account settings
3. Security → 2-Step Verification → App passwords
4. Generate app password for "Mail"

## TrueNAS Scale Setup

### 1. Create Custom App

1. **Navigate to Apps** in TrueNAS Scale
2. **Click "Launch Docker Image"**
3. **Configure as follows:**

### 2. Container Configuration

**Application Name:** `plex-autoprune-daemon`
**Container Images:** 
- **Image repository:** `plex-autoprune-daemon` (build locally) or your registry
- **Image tag:** `latest`

### 3. Environment Variables

Add these in the TrueNAS Scale app configuration:

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
VIP_NAMES=friend1,family_member,bestfriend
```

### 4. Storage Configuration

**Host Path:** `/mnt/pool/appdata/plex-autoprune/state`
**Mount Path:** `/app/state`
**Type:** Host Path

### 5. Network Configuration

**Network Mode:** Host Network (recommended for accessing local Tautulli)

## Building the Container

If building locally for TrueNAS Scale:

```bash
# Build the image
docker build -t plex-autoprune-daemon .

# Save for transfer (if needed)
docker save plex-autoprune-daemon > plex-autoprune-daemon.tar
```

## VIP Protection

Protect friends and family from auto-removal:

### Email Protection (Automatic)
- Admin email is automatically protected

### Username Protection  
Add to environment variables:
```
VIP_NAMES=mom,dad,brother,sister,bestfriend
```

## Production Deployment

1. **Set Production Mode** in environment variables:
   ```
   DRY_RUN=false
   ```

2. **Monitor via TrueNAS Scale Logs**
   - Go to Apps → plex-autoprune-daemon → Logs
   - Monitor for successful operations

## File Structure

Essential files for TrueNAS Scale deployment:
```
guardian/
├── Dockerfile          # Container build instructions
├── main.py             # Application code  
├── requirements.txt    # Python dependencies
├── .dockerignore      # Build optimization
└── README.md          # This documentation
```

## Support

For TrueNAS Scale specific issues:
1. Check container logs in TrueNAS Scale UI
2. Verify environment variables are set correctly
3. Ensure network connectivity to Plex and Tautulli services
4. Check storage permissions for `/app/state` directory