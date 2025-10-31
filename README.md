# Plex Auto-Prune Daemon

A Docker container that automatically manages Plex user access based on activity levels. Perfect for TrueNAS Scale deployment.

## Email Templates

All notification emails use a **terminal-style design** with Centauri branding. View the HTML showcase:

👉 **[Email Templates Preview](email-preview.html)** - Open this file in your browser to see all 5 email templates

Templates include:
- 🎉 **Welcome Email** - Sent to new users
- ⚠️ **Warning Email** - Sent at 27 days of inactivity
- 🚫 **Removal Email** - Sent when user is removed at 30 days
- 👤 **Admin Join Notification** - Admin alert for new users
- ❌ **Admin Removal Notification** - Admin alert for removed users

## Features

- **Automatic User Onboarding**: Sends welcome emails to new Plex users
- **Inactivity Monitoring**: Tracks user viewing activity via Tautulli
- **Graduated Warnings**: Sends warning emails before removing inactive users
- **Email Notifications**: Beautiful HTML emails with Centauri branding
- **Discord Integration**: Optional webhook notifications
- **Admin Alerts**: Detailed admin notifications for all actions
- **VIP Protection**: Protect friends and family by email or username
- **Dry Run Mode**: Test configuration without making changes
- **Rejoined User Detection**: Automatically re-welcomes users who rejoin after removal

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

## TrueNAS Scale Setup (Portainer)

### 1. Create .env File on TrueNAS

SSH into your TrueNAS and create the environment file:

```bash
# Create the config directory
mkdir -p /mnt/app-pool/config/autoprune/state

# Create the .env file
nano /mnt/app-pool/config/autoprune/.env
```

Add your environment variables:
```bash
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
DISCORD_WEBHOOK=your_discord_webhook_url
WARN_DAYS=27
KICK_DAYS=30
CHECK_NEW_USERS_SECS=120
CHECK_INACTIVITY_SECS=1800
VIP_NAMES=friend1,friend2,family_member
DRY_RUN=true
```

**Save and exit** (Ctrl+O, Enter, Ctrl+X in nano)

### 2. Deploy Stack in Portainer

1. Open Portainer on TrueNAS
2. Go to **Stacks** → **Add Stack**
3. Name: `autoprune`
4. Build method: **Git Repository**
   - Repository URL: `https://github.com/InfamousMorningstar/guardian`
   - Repository reference: `refs/heads/main`
   - Compose path: `portainer-stack.yml`
5. Click **Deploy the stack**

### 3. Benefits of This Approach

✅ **Environment variables persist** - Stored in `/mnt/app-pool/config/autoprune/.env`  
✅ **Easy updates** - Just "Pull and redeploy" in Portainer  
✅ **No credential loss** - `.env` file stays on TrueNAS  
✅ **Git-based deployment** - Always deploy latest code from GitHub  
✅ **Backup friendly** - Just backup `/mnt/app-pool/config/autoprune/`

### 4. Updating the Container

When you push code changes to GitHub:
1. Go to Portainer → Stacks → autoprune
2. Click **Pull and redeploy**
3. Environment variables automatically loaded from `.env` file
4. No need to re-enter credentials! 🎉

## TrueNAS Scale Setup (Native Docker App)

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

Essential files for deployment:
```
guardian/
├── Dockerfile              # Container build instructions
├── main.py                 # Application code  
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Local development
├── portainer-stack.yml     # TrueNAS/Portainer deployment
├── email-preview.html      # Email templates showcase
├── .dockerignore          # Build optimization
├── .gitignore             # Git exclusions
├── .env.example           # Environment variables template
└── README.md              # This documentation
```

## Support

For TrueNAS Scale specific issues:
1. Check container logs in TrueNAS Scale UI
2. Verify environment variables are set correctly
3. Ensure network connectivity to Plex and Tautulli services
4. Check storage permissions for `/app/state` directory