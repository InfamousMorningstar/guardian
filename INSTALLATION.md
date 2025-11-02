# Quick Installation Guide

This guide will help you get the Plex Auto-Prune Daemon up and running in minutes.

## 🚀 Quick Start (Copy & Paste)

### Step 1: Create Project Directory

```bash
mkdir -p ~/plex-autoprune
cd ~/plex-autoprune
```

### Step 2: Create docker-compose.yml

Copy and paste the template below, then edit the placeholder values:

```yaml
version: '3.8'

services:
  autoprune:
    build:
      context: https://github.com/InfamousMorningstar/guardian.git#main
      dockerfile: Dockerfile
    container_name: plex-autoprune-daemon
    restart: unless-stopped
    network_mode: host
    environment:
      PYTHONUNBUFFERED: "1"
      TZ: America/Edmonton  # Change to your timezone
      
      # REQUIRED - Replace with your values
      PLEX_TOKEN: "YOUR_PLEX_TOKEN_HERE"
      PLEX_SERVER_NAME: "YOUR_PLEX_SERVER_NAME_HERE"
      TAUTULLI_URL: "http://YOUR_TAUTULLI_IP:8181"
      TAUTULLI_API_KEY: "YOUR_TAUTULLI_API_KEY_HERE"
      SMTP_HOST: "smtp.gmail.com"
      SMTP_PORT: "587"
      SMTP_USERNAME: "your_email@gmail.com"
      SMTP_PASSWORD: "your_app_password"
      SMTP_FROM: "Your Name <your_email@gmail.com>"
      ADMIN_EMAIL: "admin@example.com"
      
      # OPTIONAL - Discord notifications
      DISCORD_WEBHOOK: ""
      LINK_DISCORD: ""
      
      # OPTIONAL - Configuration (defaults shown)
      WARN_DAYS: "27"
      KICK_DAYS: "30"
      CHECK_NEW_USERS_SECS: "120"
      CHECK_INACTIVITY_SECS: "1800"
      DRY_RUN: "true"  # Set to "false" for live mode
      VIP_NAMES: "mom,dad,brother"  # Usernames to protect
      HEALTH_CHECK_PORT: "8080"
      LOG_LEVEL: "INFO"
    
    volumes:
      - ./state:/app/state
```

**Save this as `docker-compose.yml` in your project directory.**

### Step 3: Get Required Tokens & Keys

#### Plex Token

1. Open Plex Web App and log in
2. Open browser developer tools (F12)
3. Go to Network tab
4. Refresh the page
5. Find any request and look for `X-Plex-Token` header
6. Copy the token value

#### Plex Server Name

1. Open Plex Web App
2. Look at your server name in the top left
3. Copy exactly as shown (case-sensitive)

#### Tautulli API Key

1. Open Tautulli web interface
2. Go to Settings → Web Interface
3. Copy the API Key

#### Tautulli URL

- Format: `http://IP_ADDRESS:PORT`
- Default port: `8181`
- Example: `http://192.168.1.100:8181`
- **Note**: If running on the same machine, you can use `http://localhost:8181`

#### Gmail App Password (for email)

1. Enable 2FA on your Google account
2. Go to Google Account → Security → 2-Step Verification
3. Click "App passwords"
4. Select "Mail" and generate password
5. Copy the 16-character password (not your regular Gmail password!)

### Step 4: Edit docker-compose.yml

Replace all the placeholder values:

```yaml
PLEX_TOKEN: "abc123xyz..."              # Your Plex token
PLEX_SERVER_NAME: "My Plex Server"       # Your server name
TAUTULLI_URL: "http://192.168.1.100:8181" # Your Tautulli URL
TAUTULLI_API_KEY: "abc123..."            # Your Tautulli API key
SMTP_USERNAME: "youremail@gmail.com"     # Your Gmail address
SMTP_PASSWORD: "abcd efgh ijkl mnop"     # Your Gmail app password
SMTP_FROM: "Plex Admin <youremail@gmail.com>"  # Your display name
ADMIN_EMAIL: "admin@example.com"        # Where to send notifications
TZ: "America/New_York"                   # Your timezone
```

### Step 5: Start the Container

```bash
docker-compose up -d
```

### Step 6: Check Logs

```bash
docker-compose logs -f
```

You should see:
```
[INFO] Centauri Guardian daemon starting...
[INFO] Configuration: WARN_DAYS=27, KICK_DAYS=30, DRY_RUN=true
[INFO] [join] loop thread started
[INFO] [inactive] loop thread started
[INFO] [health] Health check server started on port 8080
```

### Step 7: Test First (Recommended)

**Keep `DRY_RUN: "true"` for at least 24 hours** to:
- Verify users are detected correctly
- Check that warnings would be sent
- Ensure emails are working
- Review logs for any issues

When ready to go live, change:
```yaml
DRY_RUN: "false"
```

Then restart:
```bash
docker-compose restart
```

## 📋 Template Files

We've included template files in the `templates/` folder for reference:

- `templates/docker-compose.yml` - Full docker-compose with comments
- `templates/.env.example` - Environment variables template (if using .env file)

## 🐳 Docker Compose Commands

```bash
# Start the daemon
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the daemon
docker-compose down

# Restart the daemon
docker-compose restart

# View container status
docker-compose ps
```

## 🔧 TrueNAS Scale / Portainer Installation

For TrueNAS Scale or Portainer, use the `portainer-stack.yml` template:

1. Copy `templates/docker-compose.yml` content
2. Replace placeholder values
3. Paste into Portainer Stack editor
4. Adjust volume path if needed:
   ```yaml
   volumes:
     - /mnt/pool/appdata/plex-autoprune/state:/app/state
   ```

## 🎯 What to Expect

### First Run (Dry Run Mode)

- ✅ Detects all existing users
- ✅ Logs welcome emails that would be sent
- ✅ Checks inactivity for all users
- ✅ Logs warnings/removals that would happen
- ❌ **No actual emails sent** (in dry run)
- ❌ **No users removed** (in dry run)

### After Going Live

- ✅ Sends welcome emails to new users
- ✅ Sends warning emails after 27 days inactive
- ✅ Removes users after 30 days inactive
- ✅ Sends admin notifications
- ✅ Sends Discord notifications (if configured)

## 🔍 Verification

### Check Health Status

```bash
curl http://localhost:8080/health
```

Should return:
```json
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "metrics": { ... },
  "dry_run": true
}
```

### Check Metrics

```bash
curl http://localhost:8080/metrics
```

## ⚙️ Configuration Options

### Polling Intervals

- `CHECK_NEW_USERS_SECS`: How often to check for new users (default: 120 = 2 minutes)
- `CHECK_INACTIVITY_SECS`: How often to check inactivity (default: 1800 = 30 minutes)

### Removal Thresholds

- `WARN_DAYS`: Days inactive before warning (default: 27)
- `KICK_DAYS`: Days inactive before removal (default: 30)

### VIP Protection

Add usernames to protect from auto-removal:
```yaml
VIP_NAMES: "mom,dad,brother,sister,bestfriend"
```

## 📝 Troubleshooting

### Container won't start?

1. Check logs: `docker-compose logs`
2. Verify all required environment variables are set
3. Ensure Plex token and Tautulli API key are correct

### No emails being sent?

1. Check `DRY_RUN` is set to `"false"`
2. Verify SMTP credentials (especially app password for Gmail)
3. Check spam folder
4. Review logs for email errors

### Users not being removed?

1. Ensure `DRY_RUN: "false"`
2. Check Plex token has admin permissions
3. Verify users are actually inactive for 30+ days
4. Check VIP protection isn't blocking removal

### Can't connect to Tautulli?

1. Verify `TAUTULLI_URL` is correct
2. Check if using `localhost` vs actual IP
3. Ensure Tautulli is accessible from container
4. Try `network_mode: host` (already set in template)

## 🆘 Need Help?

- Check the main [README.md](README.md) for detailed documentation
- Review [API_VERIFICATION.md](API_VERIFICATION.md) for API troubleshooting
- Check container logs: `docker-compose logs -f`

## ✅ That's It!

Your daemon should now be running and monitoring your Plex users. Remember to keep it in `DRY_RUN: "true"` mode for at least 24 hours to verify everything works correctly before going live!

