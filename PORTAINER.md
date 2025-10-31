# Portainer Deployment Guide

## Method 1: Using Portainer Stacks (Recommended)

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create a **private** repository named `guardian` (or your preferred name)
3. **DO NOT** initialize with README (we already have one)

### Step 2: Push Code to GitHub

Open PowerShell in your `d:\guardian` folder and run:

```powershell
# Initialize git (if not already done)
git init

# Add all files (except those in .gitignore)
git add .

# Commit
git commit -m "Initial commit - Centauri Guardian daemon"

# Add your GitHub repository
git remote add origin https://github.com/YOUR_USERNAME/guardian.git

# Push to GitHub
git push -u origin main
```

### Step 3: Deploy in Portainer

1. **Log into Portainer** on your TrueNAS
2. Go to **Stacks** → **Add stack**
3. Choose **Git Repository** method
4. Fill in:
   - **Name**: `centauri-guardian`
   - **Repository URL**: `https://github.com/YOUR_USERNAME/guardian.git`
   - **Repository reference**: `refs/heads/main`
   - **Compose path**: `portainer-stack.yml`
   - **Authentication**: If private repo, add your GitHub credentials

5. **Environment variables** - Add these:

```env
PLEX_TOKEN=your_plex_token_here
PLEX_SERVER_NAME=your_server_name_here
TAUTULLI_URL=http://your_tautulli_url:8181
TAUTULLI_API_KEY=your_tautulli_api_key_here
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
SMTP_FROM=your_email@gmail.com
ADMIN_EMAIL=your_admin_email@gmail.com
DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
WARN_DAYS=27
KICK_DAYS=30
CHECK_NEW_USERS_SECS=120
CHECK_INACTIVITY_SECS=1800
VIP_NAMES=username1,username2
DRY_RUN=true
```

6. Click **Deploy the stack**

### Step 4: Copy State File (First Time Only)

After deployment, copy your existing `state.json` to preserve user tracking:

1. In Portainer, go to **Containers** → `plex-autoprune-daemon`
2. Click **Console** → **Connect**
3. Or use SSH to copy the file to the volume

```bash
# From TrueNAS/host
docker cp /path/to/your/state.json plex-autoprune-daemon:/app/state/state.json
```

---

## Method 2: Manual Container Deployment

### Step 1: Create GitHub Repository & Push (same as above)

### Step 2: Clone on TrueNAS

```bash
# SSH into TrueNAS
ssh admin@your-truenas-ip

# Clone repository
cd /mnt/your-pool/apps
git clone https://github.com/YOUR_USERNAME/guardian.git
cd guardian

# Copy and configure environment
cp .env.example .env
nano .env  # Edit with your credentials
```

### Step 3: Deploy in Portainer

1. **Log into Portainer**
2. Go to **Containers** → **Add container**
3. Fill in:
   - **Name**: `plex-autoprune-daemon`
   - **Image**: Leave blank (we'll build from Dockerfile)
   - **Build method**: `Build from Dockerfile`
   - **Dockerfile path**: `/mnt/your-pool/apps/guardian/Dockerfile`
   
4. **Volumes**:
   - Container: `/app/state`
   - Host: `/mnt/your-pool/apps/guardian/state`

5. **Env file**: `/mnt/your-pool/apps/guardian/.env`

6. **Restart policy**: `Unless stopped`

7. Click **Deploy container**

---

## Method 3: Using Portainer Custom Template

### Create Custom Template

1. In Portainer, go to **App Templates** → **Custom Templates** → **Add Custom Template**

2. Fill in:
   - **Title**: `Centauri Guardian - Plex Auto-Pruner`
   - **Description**: `Automated Plex user management with inactivity monitoring`
   - **Icon URL**: `https://raw.githubusercontent.com/plexinc/plex-media-player/master/resources/images/icon.png`
   - **Platform**: `Linux`
   - **Type**: `Stack`

3. **Template content** - Paste `portainer-stack.yml` contents

4. Save template

5. Deploy from **App Templates** anytime with one click!

---

## Updating the Daemon

### If using Git Repository method:

1. Push changes to GitHub:
   ```bash
   git add .
   git commit -m "Update daemon"
   git push
   ```

2. In Portainer:
   - Go to **Stacks** → `centauri-guardian`
   - Click **Pull and redeploy**
   - Done! ✅

### If using manual method:

1. SSH to TrueNAS:
   ```bash
   cd /mnt/your-pool/apps/guardian
   git pull
   ```

2. In Portainer:
   - Go to **Containers** → `plex-autoprune-daemon`
   - Click **Recreate**
   - Enable **Pull latest image**
   - Click **Recreate**

---

## Testing

### View Logs
1. **Portainer** → **Containers** → `plex-autoprune-daemon` → **Logs**

### Test Discord Notifications
1. **Portainer** → **Containers** → `plex-autoprune-daemon` → **Console**
2. Click **Connect**
3. Run:
   ```bash
   python main.py test-discord
   ```

### Check State File
1. **Portainer** → **Containers** → `plex-autoprune-daemon` → **Console**
2. Run:
   ```bash
   cat /app/state/state.json
   ```

---

## Backup State File

**Before major updates**, backup your state file:

```bash
# From TrueNAS
docker cp plex-autoprune-daemon:/app/state/state.json ~/guardian-state-backup.json
```

Or in Portainer Console:
```bash
cat /app/state/state.json
# Copy the output and save locally
```

---

## Security Checklist

✅ GitHub repository is **private**  
✅ `.env` file is in `.gitignore` (never committed)  
✅ `state/` folder is in `.gitignore` (never committed)  
✅ Environment variables entered in Portainer (not in stack file)  
✅ State file backed up before updates  

---

## Troubleshooting

### Stack won't deploy
- Check environment variables are all filled in
- Verify GitHub repository is accessible
- Check Portainer has internet access to clone repo

### Container keeps restarting
- Check logs: **Containers** → **Logs**
- Verify all required environment variables are set
- Test Plex token and Tautulli API key

### No emails being sent
- Check SMTP credentials in environment variables
- Verify `DRY_RUN=false` for production
- Check logs for email errors
