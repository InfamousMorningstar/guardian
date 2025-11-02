# Plex Auto-Prune Daemon

**Automatically manage Plex user access based on viewing activity.** This daemon monitors your Plex server, sends welcome emails to new users, warns inactive users, and removes users who haven't watched anything in 30 days.

## 📺 What This App Does

### The 30-Day Activity Rule

**Simple:** Watch at least one thing every 30 days, or lose access automatically.

### Timeline for New Users

```
┌─────────────────────────────────────────────────────────────────┐
│                     NEW USER LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────┘

Day 0  (0h)  → User joins Plex
             └─ ✅ Welcome email sent instantly
             └─ 📝 Tracked in welcomed list

Day 0-1      → 24-Hour Grace Period
             └─ ⏸️  No inactivity tracking
             └─ 🎬 User can explore without pressure

Day 1  (24h) → Tracking Begins
             └─ ⏱️  Inactivity clock starts
             └─ Baseline: join_date + 24 hours
             
             Two paths from here:
             
             ✅ USER WATCHES SOMETHING:
                └─ Timer resets to last watch date
                └─ They're safe! Clock resets every time they watch
             
             ⚠️  USER NEVER WATCHES:
                Day 27-28 → Warning email sent
                           ("3 days left to watch or lose access")
                
                Day 30-31 → Removed automatically
                           └─ Removed from Plex
                           └─ Removed from Tautulli database
                           └─ Removal email sent
                           └─ Admin notified

┌─────────────────────────────────────────────────────────────────┐
│  TL;DR: Watch something within first 30 days (after 24h grace) │
│         then watch at least once per 30 days to keep access    │
└─────────────────────────────────────────────────────────────────┘
```

### Timeline for Existing Users

If you deploy this daemon and already have users on your Plex:

- **No 24h grace needed** (they're existing users)
- **Has watch history in Tautulli?** → Last watch date used
- **No watch history?** → `Plex createdAt + 24h` used as baseline
- **Can't determine join date?** → User is SKIPPED (safety first)
- Same 27-day warning, 30-day removal threshold

### What Gets Removed

When the 30-day threshold is reached:

1. ✅ **User removed from Plex** - Access revoked via official PlexAPI
2. ✅ **User removed from Tautulli** - Database cleanup (watch history deleted)
3. ✅ **Removal email sent to user** - Professional notification
4. ✅ **Admin notification sent** - You get a detailed report
5. ✅ **Discord alert** (optional) - Webhook notification
6. ✅ **State tracking updated** - Marked in `state.json`

### VIP Protection

**Never remove specific users** regardless of activity:

- ✅ Admin email (automatic)
- ✅ Specific usernames (via `VIP_NAMES` env variable)
- ✅ VIP check happens BEFORE any removal logic

Example: `VIP_NAMES=mom,dad,brother,bestfriend`

### Dry Run Mode

**Test before going live:**

```
DRY_RUN=true   → Logs what WOULD happen, no actual removals
DRY_RUN=false  → Live mode, users actually get removed
```

**Recommendation:** Run in dry run mode for 24-48 hours first, check logs, then switch to live mode.

---

## Recent Updates (v2.0)

### Major Improvements
- ✅ **Switched to Official PlexAPI Library**: Now uses the official `plexapi` library for all Plex operations
- ✅ **Fixed Removal Issues**: Updated to Plex API v2 endpoints (fixes deprecated `/api/friends` endpoint)
- ✅ **Tautulli Database Cleanup**: Automatically removes users from Tautulli database when removed from Plex
- ✅ **Improved Error Handling**: Better logging and diagnostics for troubleshooting
- ✅ **Smart Re-processing**: Automatically detects failed removals and retries
- ✅ **Test Utilities**: Added `test_plex_api.py` for pre-flight verification
- ✅ **Enhanced Documentation**: New `API_VERIFICATION.md` explains how everything works

### Breaking Changes
- ⚠️ **No .env File Loading**: Container now uses only environment variables (proper Docker pattern)
- ⚠️ **Requires plexapi 4.15.0+**: Earlier versions use deprecated endpoints

## Features

- **Automatic User Onboarding**: Sends welcome emails to new Plex users
- **Inactivity Monitoring**: Tracks user viewing activity via Tautulli
- **Graduated Warnings**: Sends warning emails before removing inactive users
- **Automatic Cleanup**: Removes users from both Plex AND Tautulli database
- **Email Notifications**: Beautiful HTML emails with Centauri branding
- **Discord Integration**: Optional webhook notifications
- **Admin Alerts**: Detailed admin notifications for all actions
- **VIP Protection**: Protect friends and family by email or username
- **Dry Run Mode**: Test configuration without making changes
- **Smart Recovery**: Automatically re-processes failed removals

## TrueNAS Scale Deployment

### Prerequisites

- TrueNAS Scale with Docker/Kubernetes apps enabled
- Plex Media Server with admin access
- Tautulli installed and configured
- SMTP server for email notifications (Gmail, etc.)

### Required Files

Deployment files:
- `Dockerfile` - Container build instructions
- `main.py` - Application code
- `portainer-stack.yml` - TrueNAS/Portainer deployment config

Documentation:
- `README.md` - This documentation
- `API_VERIFICATION.md` - Plex API verification guide
- `test_plex_api.py` - Pre-flight connectivity test

Development:
- `requirements.txt` - Python dependencies (for reference)
- `docker-compose.yml` - Local development setup
- `.dockerignore` - Build optimization

### Testing Before Deployment

**NEW: Pre-flight API Test**

Before deploying, you can verify Plex connectivity:

```bash
# Install dependencies
pip install plexapi requests python-dateutil

# Run the test script
python test_plex_api.py
```

This will:
- ✅ Verify plexapi library works
- ✅ Test Plex token authentication
- ✅ List all current users
- ✅ Confirm `removeFriend` method exists
- ✅ Check server access

**No users will be removed** - it's read-only testing.

## How Inactivity Tracking Works

### The Math Behind the Magic

**New User Example:**
```
User "Alice" joins: 2025-11-01 at 10:00 AM

Hour 0-24:        Grace period (completely skipped)
                  Log: "skip NEW USER (24hr grace): Alice (joined 5.2h ago)"

After 24 hours:   Tracking begins
                  
                  Scenario A: Alice watches a movie on Day 2
                  └─ last_watch = 2025-11-03 10:00 AM (actual watch time)
                  └─ days = 0 (just watched)
                  └─ Status: ✅ Safe
                  
                  Scenario B: Alice never watches anything
                  └─ last_watch = 2025-11-01 10:00 AM + 24h = 2025-11-02 10:00 AM
                  └─ days = (now - baseline).days
                  
                  Day 27: days = 25 → No action yet
                  Day 28: days = 26 → No action yet
                  Day 29: days = 27 → ⚠️  WARNING EMAIL SENT
                  Day 30: days = 28 → Still monitoring...
                  Day 31: days = 29 → Still monitoring...
                  Day 32: days = 30 → 🗑️ REMOVED
```

**Existing User Example:**
```
User "Bob" was added before daemon started

Daemon checks Bob:
  1. Check Tautulli: Does Bob have watch history?
     YES → Use last watch date from Tautulli
     NO  → Use Plex createdAt + 24h as baseline
     
  2. Calculate: days = (now - last_watch).days
  
  3. Compare:
     days >= 27 and days < 30 → Send warning
     days >= 30                → Remove user
```

### Key Safety Features
- ✅ **Watch history always wins**: If Tautulli has watch data, that's the primary source
- ✅ **Fair to existing users**: Both new and existing users get the `+24h` grace in baseline calculation
- ✅ **Safety first**: Users with unknown join dates are skipped, not assumed inactive
- ✅ **VIP protection**: VIP users (by email or username) are never removed regardless of activity

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

### For TrueNAS Scale (Portainer)

**Option 1: Build from GitHub (Recommended)**
```yaml
# In portainer-stack.yml
build:
  context: https://github.com/InfamousMorningstar/Plex-Auto-Prune.git#main
  dockerfile: Dockerfile
```

**Option 2: Build Locally**
```bash
# Clone the repository
git clone https://github.com/InfamousMorningstar/Plex-Auto-Prune.git
cd Plex-Auto-Prune

# Build the image
docker build -t plex-autoprune-daemon .

# Save for transfer (if needed)
docker save plex-autoprune-daemon > plex-autoprune-daemon.tar
```

### Dependencies
The Dockerfile automatically installs:
- `plexapi>=4.15.0` - Official Plex API library (includes v2 endpoint fix)
- `requests>=2.31.0` - HTTP library
- `python-dateutil>=2.8.2` - Date parsing

**Important:** Version 4.15.0+ of plexapi is required for proper user removal (fixes deprecated `/api/friends` endpoint).

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

### Step 1: Test First (Recommended)

1. **Set Dry Run Mode** in environment variables:
   ```
   DRY_RUN=true
   ```

2. **Deploy and Monitor**:
   - Deploy to TrueNAS Scale using Portainer
   - Monitor logs: Apps → plex-autoprune-daemon → Logs
   - Verify users are detected correctly
   - Check that removals would work (logged but not executed)

3. **Run API Test** (optional):
   ```bash
   # SSH into TrueNAS or container
   python3 test_plex_api.py
   ```

### Step 2: Go Live

1. **Set Production Mode**:
   ```
   DRY_RUN=false
   ```

2. **Redeploy**:
   - Update environment variable in Portainer
   - Restart the stack

3. **Monitor Operations**:
   - Check container logs regularly
   - Verify admin emails are received
   - Monitor Discord notifications (if configured)
   - Check state file: `/app/state/state.json`

### What Gets Removed

When a user is removed for inactivity:
- ✅ **Removed from Plex** - Access revoked via PlexAPI
- ✅ **Removed from Tautulli** - User data deleted from database
- ✅ **State tracking updated** - Marked in `state.json`
- ✅ **Notifications sent** - Admin email + Discord (if configured)
- ✅ **User emailed** - Removal notice (if email available)

### Monitoring & Logs

**Successful Removal:**
```
[remove_friend] Attempting to remove user: JohnDoe (john@example.com) (ID: 123456)
[remove_friend] Successfully removed user: JohnDoe (john@example.com) (ID: 123456)
[tautulli] ✅ Successfully deleted user_id 123456 from Tautulli
[inactive] removal notice sent -> john@example.com
🗑️ Removal ✅ JohnDoe (+ Tautulli DB) :: Inactivity for 30 days
```

**Failed Removal:**
```
[remove_friend] ❌ Exception removing user JohnDoe: [error details]
[inactive] skipping user email - removal failed for JohnDoe
🗑️ Removal ❌ JohnDoe :: Inactivity for 30 days
```

### Troubleshooting

**Users not being removed?**
1. Check `DRY_RUN=false` is set
2. Verify Plex token has admin permissions
3. Check container logs for errors
4. Run `test_plex_api.py` to verify connectivity
5. See `API_VERIFICATION.md` for detailed diagnostics

**Removals fail but container is working?**
1. Check plexapi version: `docker exec plex-autoprune-daemon pip show plexapi`
2. Ensure version is 4.15.0 or higher
3. Token might not have removal permissions
4. Users might be "Home Users" instead of "Friends" (different API)

**Tautulli deletion fails?**
1. Verify `TAUTULLI_API_KEY` is correct
2. Check Tautulli API permissions
3. Ensure network connectivity to Tautulli

## File Structure

```
guardian/
├── Dockerfile              # Container build instructions
├── main.py                 # Application code (1100+ lines)
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Local development setup
├── portainer-stack.yml     # TrueNAS/Portainer deployment
├── .dockerignore          # Build optimization
├── README.md              # Main documentation
├── API_VERIFICATION.md    # Plex API verification guide
├── test_plex_api.py       # Pre-flight connectivity test
└── state/
    └── state.json         # Runtime state (auto-generated)
```

## Additional Resources

- **API Verification Guide**: See `API_VERIFICATION.md` for detailed information about:
  - How the Plex API integration works
  - Why `removeFriend()` is the correct method
  - Verification and testing procedures
  - Troubleshooting removal issues

- **GitHub Repository**: https://github.com/InfamousMorningstar/Plex-Auto-Prune

## Changelog

### v2.0 (November 2025)
- **Breaking:** Switched to official plexapi library for all Plex operations
- **Breaking:** Removed .env file loading (use environment variables only)
- **Added:** Automatic Tautulli database cleanup on user removal
- **Added:** Smart re-processing of failed removals
- **Added:** Pre-flight API test script (`test_plex_api.py`)
- **Added:** Comprehensive API verification documentation
- **Fixed:** User removal using deprecated Plex API endpoints
- **Fixed:** Better error handling and logging
- **Improved:** DRY_RUN mode now simulates success instead of failure

### v1.0 (October 2025)
- Initial release with manual API calls
- Basic user management functionality

## Support

For TrueNAS Scale specific issues:
1. Check container logs in TrueNAS Scale UI
2. Verify environment variables are set correctly
3. Ensure network connectivity to Plex and Tautulli services
4. Check storage permissions for `/app/state` directory