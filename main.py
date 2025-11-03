import os, sys, time, json, signal, threading, smtplib, requests, math, random
import traceback
import re
import shutil
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.utils import formataddr
from html import escape
from dateutil import parser as dtp

# Try to import file locking modules
try:
    import fcntl  # Unix file locking
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

try:
    import msvcrt  # Windows file locking
    WINDOWS = True
except ImportError:
    WINDOWS = False

# ============================================================================
# Enhanced Logging with Levels
# ============================================================================

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
CURRENT_LOG_LEVEL = LOG_LEVELS.get(LOG_LEVEL, 1)

def _log(level_name: str, msg: str):
    """Internal log function with level"""
    level = LOG_LEVELS.get(level_name.upper(), 1)
    if level < CURRENT_LOG_LEVEL:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = level_name.upper()[:5]
    print(f"[{ts}] [{prefix}] {msg}", flush=True)

# Backward compatibility - default to INFO
def log(msg: str):
    _log("INFO", msg)

def log_debug(msg: str): _log("DEBUG", msg)
def log_info(msg: str): _log("INFO", msg)
def log_warn(msg: str): _log("WARNING", msg)
def log_error(msg: str): _log("ERROR", msg)
def log_critical(msg: str): _log("CRITICAL", msg)




# ============================================================================
# Early CLI Command Check (before env validation)
# ============================================================================

def show_help_early():
    """Show help message (works without env vars)"""
    print("Centauri Guardian CLI Commands")
    print("=" * 80)
    print()
    print("Usage: python main.py <command> [identifier]")
    print()
    print("Commands:")
    print("  remove-welcomed <email|username|id>  - Remove user from welcomed list")
    print("  remove-warned <email|username|id>     - Remove user from warned list")
    print("  remove-removed <email|username|id>    - Remove user from removed list")
    print("  reset-user <email|username|id>        - Remove user from all lists")
    print("  list-welcomed                         - List all welcomed users")
    print("  list-warned                           - List all warned users")
    print("  list-removed                          - List all removed users")
    print("  test-discord                          - Send test Discord notifications")
    print()
    print("Examples:")
    print("  python main.py remove-welcomed 'test@example.com'")
    print("  python main.py remove-welcomed 'testuser'")
    print("  python main.py remove-welcomed '123456789'")
    print("  python main.py reset-user 'test@example.com'")
    print("  python main.py list-welcomed")
    print()

# Check for help command before env validation
if len(sys.argv) > 1:
    cmd = sys.argv[1].lower()
    if cmd in ("help", "-h", "--help"):
        show_help_early()
        sys.exit(0)

# ============================================================================
# Configuration Validation & Loading
# ============================================================================

REQUIRED_ENVS = [
    "PLEX_TOKEN","TAUTULLI_URL","TAUTULLI_API_KEY",
    "SMTP_HOST","SMTP_PORT","SMTP_USERNAME","SMTP_PASSWORD","SMTP_FROM","ADMIN_EMAIL"
]
missing = [k for k in REQUIRED_ENVS if not os.environ.get(k)]
if missing:
    raise SystemExit(f"Missing required env(s): {', '.join(missing)}")

def validate_email(email: str) -> bool:
    """Validate email format - handles both plain email and 'Name <email>' format"""
    if not email:
        return False
    
    # Extract email from "Display Name <email@domain.com>" format if present
    email_match = re.search(r'<([^>]+)>', email)
    if email_match:
        # Extract email from angle brackets
        email = email_match.group(1)
    else:
        # Use email as-is (plain format)
        email = email.strip()
    
    # Validate email format
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_url(url: str) -> bool:
    """Validate URL format"""
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False

def validate_int(value: str, default: int, min_val: int = 1, max_val: int = 365) -> int:
    """Validate and convert integer with bounds"""
    try:
        val = int(value) if value else default
        if val < min_val or val > max_val:
            log_warn(f"Value {val} out of range [{min_val}, {max_val}], using default {default}")
            return default
        return val
    except (ValueError, TypeError):
        log_warn(f"Invalid integer value '{value}', using default {default}")
        return default

# Load and validate configuration
PLEX_TOKEN = os.environ["PLEX_TOKEN"]
PLEX_SERVER_NAME = os.environ.get("PLEX_SERVER_NAME", "")
TAUTULLI_URL = os.environ["TAUTULLI_URL"].rstrip("/")
TAUTULLI_API_KEY = os.environ["TAUTULLI_API_KEY"]

if not validate_url(TAUTULLI_URL):
    raise SystemExit(f"Invalid TAUTULLI_URL: {TAUTULLI_URL}")

SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = validate_int(os.environ.get("SMTP_PORT", "587"), 587, 1, 65535)
SMTP_USERNAME = os.environ["SMTP_USERNAME"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
SMTP_FROM = os.environ["SMTP_FROM"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]

# Validate emails (extract from "Name <email>" format if needed)
def extract_email(value: str) -> str:
    """Extract email address from 'Name <email>' format or return as-is"""
    email_match = re.search(r'<([^>]+)>', value)
    if email_match:
        return email_match.group(1)
    return value.strip()

if not validate_email(SMTP_FROM):
    raise SystemExit(f"Invalid SMTP_FROM email: {SMTP_FROM}")
if not validate_email(ADMIN_EMAIL):
    raise SystemExit(f"Invalid ADMIN_EMAIL: {ADMIN_EMAIL}")

# Extract email addresses (for use with formataddr)
SMTP_FROM_EMAIL = extract_email(SMTP_FROM)
ADMIN_EMAIL_ADDR = extract_email(ADMIN_EMAIL)

WARN_DAYS = validate_int(os.environ.get("WARN_DAYS", "27"), 27, 1, 90)
KICK_DAYS = validate_int(os.environ.get("KICK_DAYS", "30"), 30, 1, 365)

if WARN_DAYS >= KICK_DAYS:
    raise SystemExit(f"Configuration error: WARN_DAYS ({WARN_DAYS}) must be less than KICK_DAYS ({KICK_DAYS})")

CHECK_NEW_USERS_SECS = validate_int(os.environ.get("CHECK_NEW_USERS_SECS", "120"), 120, 60, 3600)
CHECK_INACTIVITY_SECS = validate_int(os.environ.get("CHECK_INACTIVITY_SECS", "1800"), 1800, 300, 86400)

DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ("true", "1", "yes")

VIP_EMAILS = [ADMIN_EMAIL.lower()]
VIP_NAMES_STR = os.environ.get("VIP_NAMES", "")
VIP_NAMES = [name.strip().lower() for name in VIP_NAMES_STR.split(",") if name.strip()]

# Health check port
HEALTH_CHECK_PORT = validate_int(os.environ.get("HEALTH_CHECK_PORT", "8080"), 8080, 1024, 65535)

STATE_DIR = "/app/state"
STATE_FILE = f"{STATE_DIR}/state.json"
STATE_BACKUP_DIR = f"{STATE_DIR}/backups"
STATE_LOCK_FILE = f"{STATE_FILE}.lock"

os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(STATE_BACKUP_DIR, exist_ok=True)

# Thread-safe state lock
state_lock = threading.Lock()

# Metrics tracking
metrics = {
    "start_time": datetime.now(timezone.utc).isoformat(),
    "users_welcomed": 0,
    "users_warned": 0,
    "users_removed": 0,
    "emails_sent": 0,
    "emails_failed": 0,
    "api_errors": 0,
    "state_saves": 0,
    "state_loads": 0,
    "last_activity": None
}

stop_event = threading.Event()

# Email retry queue
email_retry_queue = []
email_queue_lock = threading.Lock()

# Email rate limiting
email_rate_lock = threading.Lock()
last_email_time = 0
EMAIL_DELAY_SECONDS = 2  # Minimum seconds between emails
MAX_EMAILS_PER_MINUTE = 10  # Gmail limit is ~100/hour, but be conservative
email_send_times = []  # Track send times for rate limiting

from plexapi.myplex import MyPlexAccount

def get_plex_account():
    token = os.environ.get("PLEX_TOKEN")
    if not token:
        raise SystemExit("PLEX_TOKEN missing")

    # Use keyword arg so plexapi does TOKEN auth (not username/password)
    return MyPlexAccount(token=token)

def get_plex_server_resource(acct):
    """Get Plex server resource (validation only, server name is optional)"""
    target = os.environ.get("PLEX_SERVER_NAME")
    if not target:
        return None  # Server name is optional
    
    try:
        for res in acct.resources():
            if (getattr(res, "provides", None) == "server" or 
                getattr(res, "product", "") == "Plex Media Server"):
                if res.name == target:
                    return res
        log_warn(f"Server '{target}' not found in Plex account resources")
        return None
    except Exception as e:
        log_warn(f"Error getting server resource: {e}")
        return None



# ---- Utils ----
def send_discord(message):
    url = os.environ.get("DISCORD_WEBHOOK")
    if not url:
        log("[discord] webhook missing, skipping")
        return

    payload = {"content": message}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 204 and r.status_code != 200:
            log(f"[discord] error {r.status_code}: {r.text}")
    except Exception as e:
        log(f"[discord] exception: {e}")


def test_discord_notifications():
    """Send test Discord notifications for all event types"""
    log("[test] Sending Discord test notifications...")
    
    # Test 1: User Join
    join_msg = (
        "✅ New User Joined\n\n"
        "Test User (test@example.com)\n"
        "ID: 99999999"
    )
    send_discord(join_msg)
    log("[test] User Join notification sent")
    time.sleep(1)
    
    # Test 2: Warning
    warning_msg = (
        "⚠️ Inactivity Warning Sent\n\n"
        "Test User (test@example.com)\n"
        "Inactive for: 27 days\n"
        "Days until removal: 3"
    )
    send_discord(warning_msg)
    log("[test] Warning notification sent")
    time.sleep(1)
    
    # Test 3: Removal
    removal_msg = (
        "🚫 User Removed\n\n"
        "Test User (test@example.com)\n"
        "Reason: Inactivity for 30 days"
    )
    send_discord(removal_msg)
    log("[test] Removal notification sent")
    
    log("[test] ✅ All test notifications sent!")


# ============================================================================
# State Management with Backup & Recovery
# ============================================================================

def load_state():
    """Load state file with error handling and recovery"""
    default_state = {
        "welcomed": {},
        "warned": {},
        "removed": {},
        "last_inactivity_scan": None
    }
    
    if not os.path.exists(STATE_FILE):
        return default_state
    
    with state_lock:
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            
            # Validate state structure
            if not isinstance(state, dict):
                raise ValueError("State is not a dictionary")
            
            # Ensure all required keys exist
            for key in default_state:
                if key not in state:
                    state[key] = default_state[key]
            
            metrics["state_loads"] += 1
            return state
            
        except json.JSONDecodeError as e:
            log_error(f"State file JSON decode error: {e}, attempting recovery...")
            return _recover_state_from_backup(default_state)
            
        except Exception as e:
            log_error(f"Error loading state: {e}, attempting recovery...")
            return _recover_state_from_backup(default_state)

def _recover_state_from_backup(default_state):
    """Attempt to recover state from backup"""
    if not os.path.exists(STATE_BACKUP_DIR):
        log_warn("No backup directory found, using default state")
        return default_state
    
    backup_files = sorted([f for f in os.listdir(STATE_BACKUP_DIR) 
                          if f.startswith("state.json.backup.")], 
                         reverse=True)[:5]
    
    for backup_file in backup_files:
        backup_path = os.path.join(STATE_BACKUP_DIR, backup_file)
        try:
            with open(backup_path, "r") as f:
                state = json.load(f)
                log_warn(f"Recovered state from backup: {backup_file}")
                return state
        except Exception as e:
            log_warn(f"Backup {backup_file} failed: {e}")
            continue
    
    log_warn("No valid backup found, using default state")
    return default_state

def save_state(state, backup=True):
    """Save state file atomically with backup"""
    try:
        # Create backup before writing
        if backup and os.path.exists(STATE_FILE):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(STATE_BACKUP_DIR, f"state.json.backup.{timestamp}")
            try:
                shutil.copy2(STATE_FILE, backup_file)
                # Keep only last 10 backups
                backups = sorted([os.path.join(STATE_BACKUP_DIR, f) 
                                 for f in os.listdir(STATE_BACKUP_DIR)
                                 if f.startswith("state.json.backup.")])
                for old_backup in backups[:-10]:
                    try:
                        os.remove(old_backup)
                    except:
                        pass
            except Exception as e:
                log_warn(f"Backup creation failed: {e}")
        
        # Atomic write with lock
        with state_lock:
            tmp_file = STATE_FILE + ".tmp"
            with open(tmp_file, "w") as f:
                json.dump(state, f, indent=2, sort_keys=True)
                f.flush()
                if hasattr(os, 'fsync'):
                    os.fsync(f.fileno())  # Force write to disk
            
            # Atomic replace
            os.replace(tmp_file, STATE_FILE)
            
            # Set secure permissions (Unix)
            if not WINDOWS:
                try:
                    os.chmod(STATE_FILE, 0o600)
                except:
                    pass
        
        metrics["state_saves"] += 1
        return True
        
    except Exception as e:
        log_error(f"Failed to save state: {e}")
        traceback.print_exc()
        return False

# ============================================================================
# Email Functions with Retry Queue
# ============================================================================

def send_email(to_addr, subject, html_body, retry=True):
    """Send email with retry support and rate limiting"""
    global last_email_time, email_send_times
    
    if not validate_email(to_addr):
        log_error(f"[email] Invalid email address: {to_addr}")
        metrics["emails_failed"] += 1
        return False
    
    # Rate limiting: Check if we're sending too fast
    with email_rate_lock:
        now = time.time()
        
        # Clean up send times older than 1 minute
        email_send_times[:] = [t for t in email_send_times if now - t < 60]
        
        # Check rate limit (max emails per minute)
        if len(email_send_times) >= MAX_EMAILS_PER_MINUTE:
            wait_time = 60 - (now - email_send_times[0])
            if wait_time > 0:
                log_debug(f"[email] Rate limit reached ({MAX_EMAILS_PER_MINUTE}/min), waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                now = time.time()
                email_send_times[:] = [t for t in email_send_times if now - t < 60]
        
        # Enforce minimum delay between emails
        time_since_last = now - last_email_time
        if time_since_last < EMAIL_DELAY_SECONDS:
            wait_time = EMAIL_DELAY_SECONDS - time_since_last
            log_debug(f"[email] Rate limiting: waiting {wait_time:.1f}s before next email")
            time.sleep(wait_time)
            now = time.time()
        
        # Update tracking
        last_email_time = now
        email_send_times.append(now)
    
    try:
        msg = MIMEText(html_body, "html")
        msg["Subject"] = subject
        # Use SMTP_FROM as-is if it contains display name, otherwise use formataddr
        if "<" in SMTP_FROM and ">" in SMTP_FROM:
            msg["From"] = SMTP_FROM
        else:
            msg["From"] = formataddr(("Centauri Guardian", SMTP_FROM))
        msg["To"] = to_addr
        
        # Add retry logic for connection issues
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                    s.starttls()
                    s.login(SMTP_USERNAME, SMTP_PASSWORD)
                    # Use extracted email for sendmail (SMTP server needs just the email)
                    from_email = SMTP_FROM_EMAIL if 'SMTP_FROM_EMAIL' in globals() else extract_email(SMTP_FROM)
                    s.sendmail(from_email, [to_addr], msg.as_string())
                
                metrics["emails_sent"] += 1
                log_debug(f"[email] Sent email to {to_addr}: {subject}")
                return True
                
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPException, ConnectionError, OSError) as e:
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 5  # Exponential backoff: 5s, 10s, 15s
                    log_warn(f"[email] Connection error (attempt {attempt + 1}/{max_attempts}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    raise  # Re-raise on final attempt
        
    except Exception as e:
        metrics["emails_failed"] += 1
        log_error(f"[email] Failed to send email to {to_addr}: {e}")
        
        # Add to retry queue if retry enabled
        if retry:
            with email_queue_lock:
                email_retry_queue.append({
                    "to": to_addr,
                    "subject": subject,
                    "body": html_body,
                    "retries": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        return False

def process_email_retry_queue():
    """Process emails in retry queue"""
    if not email_retry_queue:
        return
    
    with email_queue_lock:
        retry_items = [item for item in email_retry_queue if item["retries"] < 3]
        email_retry_queue.clear()
    
    for item in retry_items:
        item["retries"] += 1
        success = send_email(item["to"], item["subject"], item["body"], retry=False)
        
        if not success and item["retries"] < 3:
            # Re-add to queue
            with email_queue_lock:
                email_retry_queue.append(item)
        elif not success:
            log_warn(f"[email] Giving up on email to {item['to']} after {item['retries']} retries")

def plex_headers():
    return {
        "X-Plex-Token": PLEX_TOKEN,
        "X-Plex-Product": "Centauri-Autoprune",
        "X-Plex-Client-Identifier": "centauri-autoprune",
    }

def plex_get_users():
    # https://plex.tv/api/users
    r = requests.get("https://plex.tv/api/users", headers=plex_headers(), timeout=30)
    r.raise_for_status()
    from xml.etree import ElementTree as ET
    root = ET.fromstring(r.text)
    users = []
    for u in root.findall("User"):
        users.append({
            "id": u.attrib.get("id"),
            "title": u.attrib.get("title"),
            "username": u.attrib.get("username"),
            "email": u.attrib.get("email"),
            "thumb": u.attrib.get("thumb"),
            "friend": u.attrib.get("friend"),         # "1" if shared
            "home": u.attrib.get("home"),
            "createdAt": u.attrib.get("createdAt")
        })
    return users

def remove_friend(acct, plex_user):
    """Remove a user from Plex server access using plexapi library

    Args:
        acct: MyPlexAccount object
        plex_user: MyPlexUser object or user identifier (email/username/id)

    Returns:
        bool: True if removal succeeded, False otherwise
    """
    user_id = "unknown"
    try:
        # Extract identifier for logging
        if hasattr(plex_user, 'email'):
            user_id = f"{plex_user.username or plex_user.email} (ID: {plex_user.id})"
        else:
            user_id = str(plex_user)

        log(f"[remove_friend] Attempting to remove user: {user_id}")
        log(f"[remove_friend] User object type: {type(plex_user)}")
        
        # Check if user is a friend or has shared server access
        is_friend = hasattr(plex_user, 'friend') and plex_user.friend
        log(f"[remove_friend] Is friend: {is_friend}, Has servers: {len(getattr(plex_user, 'servers', []))}")

        # Method 1: Try removeFriend first (for actual friends)
        try:
            acct.removeFriend(plex_user)
            log(f"[remove_friend] ✅ Successfully removed friend: {user_id}")
            return True
        except Exception as e1:
            log(f"[remove_friend] removeFriend failed: {e1}, trying server unshare...")
            
            # Method 2: Unshare all servers from this user (for shared access users)
            try:
                # Get all servers and unshare from this user
                servers_removed = 0
                for resource in acct.resources():
                    if hasattr(resource, 'provides') and resource.provides == 'server':
                        try:
                            # Use the MyPlexUser.removeAccess() method
                            plex_user.removeAccess(resource)
                            servers_removed += 1
                            log(f"[remove_friend] Unshared server '{resource.name}' from {user_id}")
                        except Exception as e2:
                            log(f"[remove_friend] Failed to unshare '{resource.name}': {e2}")
                
                if servers_removed > 0:
                    log(f"[remove_friend] ✅ Successfully unshared {servers_removed} server(s) from {user_id}")
                    return True
                else:
                    log(f"[remove_friend] ❌ No servers to unshare from {user_id}")
                    return False
                    
            except Exception as e2:
                log(f"[remove_friend] ❌ Server unshare failed: {e2}")
                traceback.print_exc()
                return False

    except Exception as e:
        log(f"[remove_friend] ❌ Fatal exception removing user {user_id}: {e}")
        log(f"[remove_friend] Exception type: {type(e).__name__}")
        traceback.print_exc()
        return False

def tautulli(cmd, **params):
    """Call Tautulli API with error handling"""
    payload = {"apikey": TAUTULLI_API_KEY, "cmd": cmd, **params}
    try:
        r = requests.get(f"{TAUTULLI_URL}/api/v2", params=payload, timeout=30)
        r.raise_for_status()
        j = r.json()
        if j.get("response", {}).get("result") != "success":
            metrics["api_errors"] += 1
            raise RuntimeError(f"Tautulli API error: {j}")
        return j["response"]["data"]
    except requests.RequestException as e:
        metrics["api_errors"] += 1
        raise RuntimeError(f"Tautulli API request failed: {e}")

def tautulli_users():
    return tautulli("get_users")

def tautulli_delete_user(user_id):
    """Delete a user from Tautulli database (including all their history)
    
    Args:
        user_id (str): The Tautulli user_id to delete
        
    Returns:
        bool: True if deletion succeeded, False otherwise
    """
    try:
        log(f"[tautulli] Attempting to delete user_id {user_id} from Tautulli database...")
        tautulli("delete_user", user_id=str(user_id))
        log(f"[tautulli] ✅ Successfully deleted user_id {user_id} from Tautulli")
        return True
    except Exception as e:
        log(f"[tautulli] ❌ Failed to delete user_id {user_id}: {e}")
        traceback.print_exc()
        return False

def tautulli_last_watch(user_id):
    """Get last watch date for a user"""
    try:
        hist = tautulli("get_history", user_id=user_id, length=1, 
                       order_column="date", order_dir="desc")
        records = hist.get("data", [])
        if not records:
            return None
        
        ts = records[0].get("date")
        if ts is None:
            return None
        
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        
    except Exception as e:
        log_warn(f"[tautulli] Error getting last watch for user {user_id}: {e}")
        return None

# ---- Email templates ----
# ---------- Centauri Email UI (paste below your imports) ----------

from datetime import datetime, timezone
from html import escape

CENTAURI_NAME = "Centauri"
CENTAURI_COLOR = "#7A5CFF"  # primary accent (purple)
CENTAURI_ACCENT_WARN = "#FFB200"
CENTAURI_ACCENT_DANGER = "#E63946"
CENTAURI_TEXT = "#111111"
CENTAURI_TEXT_MUTED = "#666666"
CENTAURI_BG = "#F7F8FA"

# Footer links (edit if you prefer different URLs)
LINK_PLEX = "https://app.plex.tv"
LINK_OVERSEERR = "https://overseerr.ahmxd.net"
LINK_PORTFOLIO = "https://portfolio.ahmxd.net"
LINK_DISCORD = "https://discord.com/users/699763177315106836"

def _now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def _centauri_emblem_svg(size=28, color=CENTAURI_COLOR):
    # Minimal inline SVG emblem: concentric orbits forming a stylized “C”
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" role="img">
      <defs>
        <linearGradient id="g1" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="{color}" stop-opacity="1"/>
          <stop offset="100%" stop-color="{color}" stop-opacity="0.45"/>
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="28" fill="none" stroke="url(#g1)" stroke-width="3"/>
      <path d="M44 20a16 16 0 1 0 0 24" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round"/>
      <circle cx="46" cy="18" r="3" fill="{color}" />
    </svg>
    """.strip()

def _styles():
    # Light inline CSS; most clients will respect the basics.
    return f"""
    <style>
      /* Dark mode hint; many clients ignore, but harmless */
      @media (prefers-color-scheme: dark) {{
        .cx-wrap {{ background:#0B0D10 !important; }}
        .cx-card {{ background:#121418 !important; color:#E6E8EA !important; }}
        .cx-muted {{ color:#A7ADB4 !important; }}
        .cx-rule {{ border-color:#2A2F36 !important; }}
      }}
      .cx-wrap {{
        margin:0; padding:24px; background:{CENTAURI_BG};
      }}
      .cx-card {{
        margin:0 auto; max-width:700px; border-radius:14px; padding:24px 22px;
        background:#FFFFFF; color:{CENTAURI_TEXT};
        box-shadow:0 8px 28px rgba(16,24,40,0.08);
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
        font-size:15px; line-height:1.6;
        position:relative; overflow:hidden;
      }}
      .cx-watermark {{
        position:absolute; inset:auto -40px -40px auto; opacity:0.08; pointer-events:none;
        transform:rotate(-12deg);
      }}
      .cx-header {{
        display:flex; align-items:center; gap:12px; margin-bottom:12px;
      }}
      .cx-title {{
        margin:0; font-size:18px; font-weight:700;
      }}
      .cx-subtitle {{ margin:2px 0 0 0; color:{CENTAURI_TEXT_MUTED}; font-size:13px; }}
      .cx-rule {{ border:0; border-top:1px solid #E7E9ED; margin:16px 0; }}
      .cx-muted {{ color:{CENTAURI_TEXT_MUTED}; font-size:13px; }}
      .cx-kv b {{ font-weight:600; }}
      .cx-footer {{
        margin-top:18px; padding-top:14px; border-top:1px solid #E7E9ED; font-size:13px;
        display:flex; flex-wrap:wrap; gap:10px; align-items:center; justify-content:flex-start;
      }}
      .cx-btns a {{
        display:inline-block; margin-right:10px; text-decoration:none; font-weight:600;
        padding:7px 11px; border-radius:8px; border:1px solid #E7E9ED; color:#0F172A;
      }}
      .cx-badge {{
        display:inline-block; font-size:12px; padding:3px 8px; border-radius:999px; background:#EEF2FF; color:{CENTAURI_COLOR};
        border:1px solid #E7E9ED; vertical-align:middle;
      }}
    </style>
    """.strip()

def _shell(title, subtitle, body_html, accent=CENTAURI_COLOR, include_audit=None):
    # include_audit: optional dict of audit fields to render in admin emails
    wm_svg = _centauri_emblem_svg(160, accent)
    audit_html = ""
    if include_audit:
        rows = "".join(
            f"<tr><td style='padding:4px 0;white-space:nowrap;'><b>{escape(str(k))}</b></td>"
            f"<td style='padding:4px 8px;'>:</td><td style='padding:4px 0;'>{escape(str(v))}</td></tr>"
            for k, v in include_audit.items()
        )
        audit_html = f"""
        <hr class="cx-rule">
        <div class="cx-muted" style="margin-top:6px;">Audit trail</div>
        <table cellspacing="0" cellpadding="0" style="margin-top:6px; font-size:13px;">{rows}</table>
        """.strip()

    return f"""
    <div class="cx-wrap">
      {_styles()}
      <div class="cx-card">
        <div class="cx-watermark">{wm_svg}</div>
        <div class="cx-header">
          {_centauri_emblem_svg(28, accent)}
          <div>
            <h1 class="cx-title" style="color:{accent};">{escape(title)}</h1>
            <div class="cx-subtitle">{escape(subtitle)}</div>
          </div>
        </div>

        {body_html}

        {audit_html}

        <div class="cx-footer">
          <span class="cx-badge">{CENTAURI_NAME}</span>
          <span class="cx-muted">Sent {escape(_now_iso())}</span>
          <div class="cx-btns" style="margin-left:auto;">
            <a href="{LINK_PLEX}">Plex</a>
            <a href="{LINK_OVERSEERR}">Overseerr</a>
            <a href="{LINK_PORTFOLIO}">Portfolio</a>
            <a href="{LINK_DISCORD}">Discord</a>
          </div>
        </div>
      </div>
    </div>
    """.strip()

# ---------- Event templates ----------

def welcome_email_html(display_name: str) -> str:
    body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Centauri — Welcome + House Rules</title>
</head>
<body style="margin:0; padding:40px 20px; background:#0a0e14; font-family:'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;">
  
  <table role="presentation" width="100%" style="max-width:700px; margin:0 auto; background:#0f1419; border:1px solid #1f2937; border-radius:8px;">
    <tr><td style="padding:32px;">
      
      <!-- HEADER -->
      <div style="margin-bottom:24px;">
        <div style="color:#6b7280; font-size:12px; margin-bottom:8px;">$ centauri access grant --user={escape(display_name)}</div>
        <div style="height:2px; background:#1f2937; margin:12px 0;"></div>
      </div>

      <!-- WELCOME BANNER -->
      <table role="presentation" width="100%" style="background:#1a1f26; border-left:3px solid #7A5CFF; padding:24px; margin-bottom:20px;">
        <tr><td>
          <div style="text-align:center; margin-bottom:16px; font-size:48px;">🎬</div>
          <div style="color:#7A5CFF; font-size:16px; font-weight:700; margin-bottom:8px; text-align:center;">ACCESS GRANTED</div>
          <div style="color:#e5e7eb; font-size:14px; text-align:center; margin-bottom:16px;">
            Welcome to Centauri Cinema Network
          </div>
          <div style="color:#9ca3af; font-size:12px; line-height:1.8; text-align:center;">
            <span style="color:#10b981;">✓</span> Official apps only &nbsp;·&nbsp; 
            <span style="color:#3b82f6;">✓</span> Direct Play preferred &nbsp;·&nbsp; 
            <span style="color:#f59e0b;">✓</span> Watch ≥ once/30 days
          </div>
        </td></tr>
      </table>

      <!-- QUICK ACTIONS -->
      <div style="margin-bottom:24px;">
        <div style="color:#6b7280; font-size:11px; margin-bottom:8px;">QUICK ACCESS:</div>
        <div style="margin-bottom:8px;">
          <a href="https://app.plex.tv" style="display:inline-block; background:#3b82f6; color:#fff; padding:10px 20px; text-decoration:none; border-radius:4px; font-size:13px; font-weight:700; margin-right:8px;">
            $ plex --start-watching
          </a>
          <a href="https://request.ahmxd.net" style="display:inline-block; background:#7A5CFF; color:#fff; padding:10px 20px; text-decoration:none; border-radius:4px; font-size:13px; font-weight:700;">
            $ overseerr --request-content
          </a>
        </div>
      </div>

      <!-- TL;DR -->
      <div style="margin-bottom:20px;">
        <div style="color:#3b82f6; font-size:12px; font-weight:700; margin-bottom:12px;">TL;DR — THE THREE LAWS OF CENTAURI</div>
        <div style="padding:16px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
          <div style="color:#e5e7eb; font-size:13px; line-height:1.9; margin-bottom:10px;">
            <span style="color:#10b981;">🎬</span> Use <strong>official Plex apps</strong> (not a browser) for best buffering and compatibility.
          </div>
          <div style="color:#e5e7eb; font-size:13px; line-height:1.9; margin-bottom:10px;">
            <span style="color:#3b82f6;">⚡</span> Prefer <strong>Direct Play</strong>. Transcoding makes my GPU cry pixelated tears.
          </div>
          <div style="color:#e5e7eb; font-size:13px; line-height:1.9;">
            <span style="color:#f59e0b;">📅</span> <strong>30-Day Inactivity Rule:</strong> no watch activity in 30 days = <span style="color:#dc2626; font-weight:700;">auto-purge</span>. DM me for a re-invite if there's room.
          </div>
        </div>
      </div>

      <!-- HOUSE RULES -->
      <div style="margin-bottom:20px;">
        <div style="color:#10b981; font-size:12px; font-weight:700; margin-bottom:12px;">📜 HOUSE RULES (SHORT, SWEET, ENFORCEABLE)</div>
        <div style="padding:16px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
          <div style="color:#9ca3af; font-size:12px; line-height:1.9;">
            <div style="margin-bottom:8px;"><span style="color:#3b82f6;">1.</span> <span style="color:#e5e7eb;"><strong>Use official Plex apps</strong> for your device. Browsers are a last resort (they love to transcode).</span></div>
            <div style="margin-bottom:8px;"><span style="color:#3b82f6;">2.</span> <span style="color:#e5e7eb;"><strong>Direct Play</strong> & "<strong>Original</strong>" quality when you can. Lower bitrate one step before changing audio settings.</span></div>
            <div style="margin-bottom:8px;"><span style="color:#3b82f6;">3.</span> <span style="color:#e5e7eb;"><strong>30-day activity:</strong> watch at least one thing every 30 days or the system assumes you ghosted me. <span style="color:#dc2626;">Access revoked.</span></span></div>
            <div style="margin-bottom:8px;"><span style="color:#3b82f6;">4.</span> <span style="color:#e5e7eb;"><strong>Requests =&gt; Overseerr</strong> (title + year + language). I'm fast, not psychic.</span></div>
            <div><span style="color:#3b82f6;">5.</span> <span style="color:#e5e7eb;"><strong>Network sanity:</strong> Ethernet if possible; otherwise sit closer to the router like it owes you money.</span></div>
          </div>
        </div>
      </div>

      <!-- DIRECT PLAY EXPLAINER -->
      <div style="margin-bottom:20px;">
        <div style="color:#f59e0b; font-size:12px; font-weight:700; margin-bottom:12px;">🎯 DIRECT PLAY &gt; TRANSCODE</div>
        <div style="padding:16px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
          <div style="color:#9ca3af; font-size:12px; line-height:1.9;">
            <div style="margin-bottom:8px;"><span style="color:#6b7280;">→</span> <span style="color:#e5e7eb;"><strong>Direct Play</strong> = device supports the file as-is → fastest start, best quality, minimal server load.</span></div>
            <div style="margin-bottom:8px;"><span style="color:#6b7280;">→</span> <span style="color:#e5e7eb;"><strong>Transcoding</strong> = server converts on the fly (CPU/GPU heavy). Sometimes necessary; never Plan A.</span></div>
            <div><span style="color:#6b7280;">→</span> <span style="color:#e5e7eb;">Use a <strong>dedicated Plex app</strong>, set quality to <strong>Original</strong>, and keep weird audio toggles off unless you need them.</span></div>
          </div>
        </div>
      </div>

      <!-- OFFICIAL APP LINKS -->
      <div style="margin-bottom:20px;">
        <div style="color:#7A5CFF; font-size:12px; font-weight:700; margin-bottom:12px;">📲 GET THE PLEX APP</div>
        <div style="padding:16px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
          <div style="color:#9ca3af; font-size:11px; line-height:1.8;">
            <div style="margin-bottom:12px;">
              <div style="color:#6b7280; font-size:10px; margin-bottom:6px;">MOBILE & TV:</div>
              • <a href="https://www.plex.tv/apps-devices/" style="color:#3b82f6; text-decoration:none;">All Apps & Devices (Official)</a><br>
              • <a href="https://play.google.com/store/apps/details?id=com.plexapp.android" style="color:#3b82f6; text-decoration:none;">Android / Google TV / Android TV</a><br>
              • <a href="https://apps.apple.com/us/app/plex-watch-live-tv-and-movies/id383457673" style="color:#3b82f6; text-decoration:none;">iPhone / iPad / Apple TV*</a><br>
              • <a href="https://channelstore.roku.com/details/319af1cdcf66a4bba38b45800bca85a6%3A3a7f1fed11646046bf9aa206cdbe3911/plex-free-movies-and-tv" style="color:#3b82f6; text-decoration:none;">Roku Channel</a><br>
              • <a href="https://www.amazon.com/Plex-Inc/dp/B004Y1WCDE" style="color:#3b82f6; text-decoration:none;">Amazon Fire TV</a>
            </div>
            <div>
              <div style="color:#6b7280; font-size:10px; margin-bottom:6px;">DESKTOP & CONSOLES:</div>
              • <a href="https://apps.microsoft.com/detail/xp9cdqw6ml4nqn?gl=US&hl=en-US" style="color:#3b82f6; text-decoration:none;">Windows (Desktop app)</a><br>
              • <a href="https://support.plex.tv/articles/downloads-on-desktop/" style="color:#3b82f6; text-decoration:none;">macOS (Desktop app)</a><br>
              • <a href="https://support.plex.tv/articles/204080173-which-smart-tv-models-are-supported/" style="color:#3b82f6; text-decoration:none;">Samsung / LG / VIZIO (Smart TVs)</a><br>
              • <a href="https://support.plex.tv/articles/categories/player-apps-platforms/xbox/" style="color:#3b82f6; text-decoration:none;">Xbox (how to install)</a><br>
              • <a href="https://support.plex.tv/articles/categories/player-apps-platforms/playstation/" style="color:#3b82f6; text-decoration:none;">PlayStation (how to install)</a>
            </div>
            <div style="margin-top:8px; color:#6b7280; font-size:10px;">
              *On Apple TV, install Plex from the tvOS App Store or start at plex.tv/apps-devices
            </div>
          </div>
        </div>
      </div>

      <!-- FAQ -->
      <div style="margin-bottom:20px;">
        <div style="color:#10b981; font-size:12px; font-weight:700; margin-bottom:12px;">❓ FAQ (BECAUSE YOU WERE GOING TO ASK ANYWAY)</div>
        <div style="padding:16px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
          <div style="color:#9ca3af; font-size:12px; line-height:1.8;">
            <div style="margin-bottom:12px;">
              <div style="color:#e5e7eb; font-weight:700; margin-bottom:4px;">Q: It buffers—whose fault is it?</div>
              <div>A: If other titles play fine, it's likely Wi-Fi. Try Ethernet or drop one quality step. If it keeps transcoding, install the dedicated app and pick <em>Original</em>.</div>
            </div>
            <div style="margin-bottom:12px;">
              <div style="color:#e5e7eb; font-weight:700; margin-bottom:4px;">Q: Can I stream away from home?</div>
              <div>A: Yes—note Plex's 2025 change: remote playback may require <em>Plex Pass</em> or a <em>Remote Watch Pass</em>. Local network streaming is free. (Details on Plex support.)</div>
            </div>
            <div style="margin-bottom:12px;">
              <div style="color:#e5e7eb; font-weight:700; margin-bottom:4px;">Q: How do I request stuff?</div>
              <div>A: Use Overseerr → <a href="https://request.ahmxd.net" style="color:#3b82f6; text-decoration:none;">request.ahmxd.net</a> with the year + language. Be specific, future-you will thank you.</div>
            </div>
            <div style="margin-bottom:12px;">
              <div style="color:#e5e7eb; font-weight:700; margin-bottom:4px;">Q: Do I need to change audio settings?</div>
              <div>A: Only if you have a receiver/soundbar that supports passthrough. Random toggles = surprise transcodes.</div>
            </div>
            <div>
              <div style="color:#e5e7eb; font-weight:700; margin-bottom:4px;">Q: I got purged—now what?</div>
              <div>A: DM me on Discord and I'll re-enable access if there's room. Watching one thing per month keeps the purge away.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- CONTACT -->
      <div style="margin-bottom:20px; padding:16px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
        <div style="color:#10b981; font-size:12px; font-weight:700; margin-bottom:8px;">🛰️ NEED HELP? PING ME</div>
        <div style="color:#e5e7eb; font-size:12px;">
          Discord: <a href="https://discord.com/users/699763177315106836" style="color:#3b82f6; text-decoration:none;">@infamous_morningstar</a>
        </div>
      </div>

      <!-- FOOTER -->
      <div style="height:2px; background:#1f2937; margin:20px 0;"></div>
      <div style="color:#6b7280; font-size:10px; line-height:1.8;">
        🍿 <strong style="color:#e5e7eb;">Centauri Cinema Network</strong> — where bits become blockbusters and my sleep schedule doesn't exist.<br>
        🐧 Powered by Linux, RAID-Z, and sheer stubbornness. (Also coffee. Unmeasured.)<br>
        💾 If it buffers, assume I'm upgrading something important. Or I tripped over a cable. Either way: cinematic suspense.<br>
        🕹️ Requests go to <span style="color:#e5e7eb;">Overseerr</span>, complaints go straight to <span style="color:#3b82f6;">/dev/null</span>.<br>
        🪐 <em>Stay tuned, stay mad, stay streaming — Centauri out.</em>
      </div>

    </td></tr>
  </table>

</body>
</html>
    """
    return body



def warn_email_html(display_name: str, days: int) -> str:
    days_left = KICK_DAYS - days
    body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Centauri — Inactivity Warning</title>
</head>
<body style="margin:0; padding:40px 20px; background:#0a0e14; font-family:'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;">
  
  <table role="presentation" width="100%" style="max-width:600px; margin:0 auto; background:#0f1419; border:1px solid #1f2937; border-radius:8px;">
    <tr><td style="padding:32px;">
      
      <!-- HEADER -->
      <div style="margin-bottom:24px;">
        <div style="color:#6b7280; font-size:12px; margin-bottom:8px;">$ centauri status --user={escape(display_name)}</div>
        <div style="height:2px; background:#1f2937; margin:12px 0;"></div>
      </div>

      <!-- STATUS BLOCK -->
      <table role="presentation" width="100%" style="background:#1a1f26; border-left:3px solid #f59e0b; padding:20px; margin-bottom:20px;">
        <tr><td>
          <div style="color:#f59e0b; font-size:14px; font-weight:700; margin-bottom:12px;">⚠ STATUS: INACTIVE_WARNING</div>
          <div style="color:#e5e7eb; font-size:13px; line-height:1.8;">
            <div style="margin-bottom:6px;">USER ········· {escape(display_name)}</div>
            <div style="margin-bottom:6px;">LAST_ACTIVE ··· {days} days ago</div>
            <div style="margin-bottom:6px;">THRESHOLD ····· {KICK_DAYS} days</div>
            <div style="color:#f59e0b;">TIME_LEFT ····· {days_left} days</div>
          </div>
        </td></tr>
      </table>

      <!-- MESSAGE -->
      <div style="color:#9ca3af; font-size:13px; line-height:1.7; margin-bottom:20px;">
        <div style="margin-bottom:12px;">Hey {escape(display_name)},</div>
        <div style="margin-bottom:12px;">Your account has been idle for <span style="color:#f59e0b; font-weight:700;">{days} days</span>. My system automatically removes inactive accounts after {KICK_DAYS} days to make room for active viewers.</div>
        <div style="margin-bottom:12px; padding:12px; background:#1a1f26; border-left:2px solid #3b82f6;">
          <span style="color:#3b82f6;">→</span> Watch anything to reset your activity timer<br>
          <span style="color:#6b7280;">  (even a 5-minute episode counts)</span>
        </div>
      </div>

      <!-- ACTIONS -->
      <div style="margin-bottom:24px;">
        <div style="color:#6b7280; font-size:11px; margin-bottom:8px;">AVAILABLE ACTIONS:</div>
        <div style="margin-bottom:8px;">
          <a href="https://app.plex.tv" style="display:inline-block; background:#10b981; color:#000; padding:10px 20px; text-decoration:none; border-radius:4px; font-size:13px; font-weight:700;">
            $ plex --open
          </a>
        </div>
        <div>
          <a href="https://request.ahmxd.net" style="display:inline-block; background:#1f2937; color:#9ca3af; padding:10px 20px; text-decoration:none; border-radius:4px; font-size:13px; border:1px solid #374151;">
            $ request --new-content
          </a>
        </div>
      </div>

      <!-- FOOTER -->
      <div style="height:2px; background:#1f2937; margin:20px 0;"></div>
      <div style="color:#6b7280; font-size:11px; line-height:1.6;">
        Centauri Media Server<br>
        Automated inactivity monitoring · guardian@centauri
      </div>

    </td></tr>
  </table>

</body>
</html>
    """
    return body

def removal_email_html(display_name: str) -> str:
    body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Centauri — Access Removed</title>
</head>
<body style="margin:0; padding:40px 20px; background:#0a0e14; font-family:'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;">
  
  <table role="presentation" width="100%" style="max-width:600px; margin:0 auto; background:#0f1419; border:1px solid #1f2937; border-radius:8px;">
    <tr><td style="padding:32px;">
      
      <!-- HEADER -->
      <div style="margin-bottom:24px;">
        <div style="color:#6b7280; font-size:12px; margin-bottom:8px;">$ centauri remove --user={escape(display_name)} --reason=inactivity</div>
        <div style="height:2px; background:#1f2937; margin:12px 0;"></div>
      </div>

      <!-- STATUS BLOCK -->
      <table role="presentation" width="100%" style="background:#1a1f26; border-left:3px solid #dc2626; padding:20px; margin-bottom:20px;">
        <tr><td>
          <div style="color:#dc2626; font-size:14px; font-weight:700; margin-bottom:12px;">✗ STATUS: ACCESS_REMOVED</div>
          <div style="color:#e5e7eb; font-size:13px; line-height:1.8;">
            <div style="margin-bottom:6px;">USER ········· {escape(display_name)}</div>
            <div style="margin-bottom:6px;">REASON ········ Inactivity threshold reached</div>
            <div style="margin-bottom:6px;">THRESHOLD ····· {KICK_DAYS} days</div>
            <div style="color:#dc2626;">ACTION ········ Account removed</div>
          </div>
        </td></tr>
      </table>

      <!-- MESSAGE -->
      <div style="color:#9ca3af; font-size:13px; line-height:1.7; margin-bottom:20px;">
        <div style="margin-bottom:12px;">Hey {escape(display_name)},</div>
        <div style="margin-bottom:12px;">Your Centauri account has been automatically removed after <span style="color:#dc2626; font-weight:700;">{KICK_DAYS} days</span> of inactivity. This is part of my automated system to make room for active viewers.</div>
        <div style="margin-bottom:12px; padding:12px; background:#1a1f26; border-left:2px solid #6b7280;">
          <span style="color:#9ca3af;">→ No data was stored or shared</span><br>
          <span style="color:#9ca3af;">→ Re-access available if capacity allows</span><br>
          <span style="color:#9ca3af;">→ Just reach out to request re-add</span>
        </div>
      </div>

      <!-- RE-ACCESS -->
      <div style="margin-bottom:24px; padding:16px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
        <div style="color:#10b981; font-size:12px; font-weight:700; margin-bottom:8px;">WANT BACK IN?</div>
        <div style="color:#9ca3af; font-size:12px; line-height:1.6; margin-bottom:12px;">
          Reply to this email or send me a Discord DM.<br>
          If there's space on the server, I'll re-add you!
        </div>
        <div>
          <a href="{LINK_DISCORD}" style="display:inline-block; background:#5865F2; color:#fff; padding:8px 16px; text-decoration:none; border-radius:4px; font-size:12px; font-weight:700;">
            $ discord --dm
          </a>
        </div>
      </div>

      <!-- FOOTER -->
      <div style="height:2px; background:#1f2937; margin:20px 0;"></div>
      <div style="color:#6b7280; font-size:11px; line-height:1.6;">
        Centauri Media Server<br>
        Automated account management · guardian@centauri<br>
        Thanks for being part of the community 🎬
      </div>

    </td></tr>
  </table>

</body>
</html>
    """
    return body

def admin_join_html(user: dict) -> str:
    name = user.get('title') or user.get('username') or "User"
    email = user.get('email') or "Not provided"
    uid = user.get('id') or "N/A"
    timestamp = _now_iso()
    
    body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Centauri — New User Joined</title>
</head>
<body style="margin:0; padding:40px 20px; background:#0a0e14; font-family:'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;">
  
  <table role="presentation" width="100%" style="max-width:600px; margin:0 auto; background:#0f1419; border:1px solid #1f2937; border-radius:8px;">
    <tr><td style="padding:32px;">
      
      <!-- HEADER -->
      <div style="margin-bottom:24px;">
        <div style="color:#6b7280; font-size:12px; margin-bottom:8px;">$ guardian event --type=user_joined</div>
        <div style="height:2px; background:#1f2937; margin:12px 0;"></div>
      </div>

      <!-- EVENT -->
      <table role="presentation" width="100%" style="background:#1a1f26; border-left:3px solid #10b981; padding:20px; margin-bottom:20px;">
        <tr><td>
          <div style="color:#10b981; font-size:14px; font-weight:700; margin-bottom:12px;">✓ EVENT: USER_JOINED</div>
          <div style="color:#e5e7eb; font-size:13px; line-height:1.8;">
            <div style="margin-bottom:6px;">NAME ·········· {escape(name)}</div>
            <div style="margin-bottom:6px;">EMAIL ········· {escape(email)}</div>
            <div style="margin-bottom:6px;">USER_ID ······· {escape(str(uid))}</div>
            <div style="color:#6b7280;">TIMESTAMP ····· {escape(timestamp)}</div>
          </div>
        </td></tr>
      </table>

      <!-- STATUS -->
      <div style="margin-bottom:20px; padding:12px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
        <div style="color:#10b981; font-size:12px; margin-bottom:4px;">✓ Welcome email sent successfully</div>
        <div style="color:#6b7280; font-size:11px;">User has been notified of server access</div>
      </div>

      <!-- FOOTER -->
      <div style="height:2px; background:#1f2937; margin:20px 0;"></div>
      <div style="color:#6b7280; font-size:11px; line-height:1.6;">
        Centauri Guardian · guardian@centauri<br>
        Automated user monitoring system
      </div>

    </td></tr>
  </table>

</body>
</html>
    """
    return body

def admin_removed_html(user: dict, reason: str, status: str) -> str:
    name = user.get('title') or user.get('username') or "User"
    email = user.get('email') or "Not provided"
    uid = user.get('id') or "N/A"
    timestamp = _now_iso()
    is_success = status.upper() == "SUCCESS"
    border_color = "#10b981" if is_success else "#dc2626"
    status_text = "REMOVAL_SUCCESS" if is_success else "REMOVAL_FAILED"
    
    body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Centauri — User Removed</title>
</head>
<body style="margin:0; padding:40px 20px; background:#0a0e14; font-family:'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;">
  
  <table role="presentation" width="100%" style="max-width:600px; margin:0 auto; background:#0f1419; border:1px solid #1f2937; border-radius:8px;">
    <tr><td style="padding:32px;">
      
      <!-- HEADER -->
      <div style="margin-bottom:24px;">
        <div style="color:#6b7280; font-size:12px; margin-bottom:8px;">$ guardian remove --user={escape(name)} --status={status.lower()}</div>
        <div style="height:2px; background:#1f2937; margin:12px 0;"></div>
      </div>

      <!-- EVENT -->
      <table role="presentation" width="100%" style="background:#1a1f26; border-left:3px solid {border_color}; padding:20px; margin-bottom:20px;">
        <tr><td>
          <div style="color:{border_color}; font-size:14px; font-weight:700; margin-bottom:12px;">{'✓' if is_success else '✗'} STATUS: {status_text}</div>
          <div style="color:#e5e7eb; font-size:13px; line-height:1.8;">
            <div style="margin-bottom:6px;">NAME ·········· {escape(name)}</div>
            <div style="margin-bottom:6px;">EMAIL ········· {escape(email)}</div>
            <div style="margin-bottom:6px;">USER_ID ······· {escape(str(uid))}</div>
            <div style="color:#6b7280;">TIMESTAMP ····· {escape(timestamp)}</div>
          </div>
        </td></tr>
      </table>

      <!-- REASON -->
      <div style="margin-bottom:20px; padding:12px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
        <div style="color:#f59e0b; font-size:11px; font-weight:700; margin-bottom:4px;">REMOVAL REASON:</div>
        <div style="color:#e5e7eb; font-size:12px;">{escape(reason)}</div>
      </div>

      <!-- EMAIL STATUS -->
      <div style="margin-bottom:20px; padding:12px; background:#1a1f26; border-radius:6px; border:1px solid #374151;">
        <div style="color:{border_color}; font-size:12px; margin-bottom:4px;">{'✓ Removal email sent' if is_success else '✗ Removal attempt failed'}</div>
        <div style="color:#6b7280; font-size:11px;">{'User has been notified' if is_success else 'Check logs for error details'}</div>
      </div>

      <!-- FOOTER -->
      <div style="height:2px; background:#1f2937; margin:20px 0;"></div>
      <div style="color:#6b7280; font-size:11px; line-height:1.6;">
        Centauri Guardian · guardian@centauri<br>
        Automated user monitoring system
      </div>

    </td></tr>
  </table>

</body>
</html>
    """
    return body
# ---------- End Centauri Email UI ----------

# ---- Core workers ----
def fast_join_watcher():
    log("[join] loop thread started")
    acct = get_plex_account()
    tick = 0
    while not stop_event.is_set():
        tick += 1
        try:
            # Reload state each iteration to see updates from other threads
            state = load_state()
            welcomed = state.get("welcomed", {})
            log(f"[join] tick {tick} – checking new users…")
            # Retry logic for Plex API calls
            friends = None
            for attempt in range(3):
                try:
                    friends = acct.users()
                    break
                except Exception as e:
                    if attempt < 2:
                        log(f"[join] Plex API error (attempt {attempt+1}/3), retrying in 5s: {e}")
                        time.sleep(5)
                    else:
                        raise
            
            if friends is None:
                log("[join] Could not fetch users after 3 attempts, skipping this tick")
                continue
                
            now = datetime.now(timezone.utc)
            
            # Check if this is the first scan (before cleanup logic)
            # On first scan, don't cleanup departed users - we're still building the welcomed list
            is_first_scan_check = tick == 1 or len(welcomed) == 0
            
            # Clean up departed users - remove from all tracking dicts (welcomed, warned, removed) if no longer in Plex
            # Use TWO API calls to verify they're truly gone (prevents false positives from API failures)
            # Skip cleanup on first scan to avoid removing users before they're processed
            warned = state.get("warned", {})
            removed = state.get("removed", {})
            current_user_ids = {str(u.id) for u in friends}
            
            # Check all state dicts for departed users
            all_tracked_ids = set(welcomed.keys()) | set(warned.keys()) | set(removed.keys())
            potentially_departed = [uid for uid in all_tracked_ids if uid not in current_user_ids]
            departed_count = 0
            
            # Only run cleanup if NOT first scan (to avoid false positives)
            if potentially_departed and not is_first_scan_check:
                log(f"[join] Found {len(potentially_departed)} potentially departed users, verifying...")
                time.sleep(2)  # Brief pause before second check
                
                # Second API call to confirm
                try:
                    verify_friends = acct.users()
                    verify_ids = {str(u.id) for u in verify_friends}
                    
                    # Only remove if STILL not in the list after second check
                    confirmed_departed = [uid for uid in potentially_departed if uid not in verify_ids]
                    
                    cleaned_welcomed = 0
                    cleaned_warned = 0
                    cleaned_removed = 0
                    
                    for uid in confirmed_departed:
                        log(f"[join] DEPARTED (verified): User {uid} no longer in Plex, removing from all tracking")
                        
                        # Remove from welcomed dict
                        if uid in welcomed:
                            del welcomed[uid]
                            cleaned_welcomed += 1
                        
                        # Remove from warned dict
                        if uid in warned:
                            del warned[uid]
                            cleaned_warned += 1
                        
                        # Remove from removed dict (if manually removed by admin)
                        if uid in removed:
                            del removed[uid]
                            cleaned_removed += 1
                    
                    departed_count = len(confirmed_departed)
                    if confirmed_departed:
                        state["welcomed"] = welcomed
                        state["warned"] = warned
                        state["removed"] = removed
                        save_state(state)
                        cleanup_summary = []
                        if cleaned_welcomed > 0:
                            cleanup_summary.append(f"{cleaned_welcomed} from welcomed")
                        if cleaned_warned > 0:
                            cleanup_summary.append(f"{cleaned_warned} from warned")
                        if cleaned_removed > 0:
                            cleanup_summary.append(f"{cleaned_removed} from removed")
                        log(f"[join] Cleaned up {departed_count} departed user(s): {', '.join(cleanup_summary)}")
                    else:
                        log(f"[join] False alarm - all {len(potentially_departed)} users still present in Plex")
                        
                except Exception as e:
                    log(f"[join] Could not verify departed users (API error), skipping cleanup: {e}")
                    # Don't remove anyone if verification fails
            
            # Check if this is the first scan (welcomed dict is empty or very small)
            # On first scan, all users are existing - add them silently without emails
            # Use tick == 1 as primary indicator, or empty welcomed dict
            # Note: is_first_scan_check was already calculated above, but we recalculate here
            # using the current welcomed dict (which may have been updated during cleanup)
            is_first_scan = tick == 1 or len(welcomed) == 0
            
            new_count = 0
            for u in friends:
                uid = str(u.id)
                if uid in welcomed:
                    continue
                
                try:
                    display = u.title or u.username or "there"
                    user_email = (u.email or "").lower()
                    
                    # Check if user is VIP (skip welcome emails for VIPs)
                    is_vip = False
                    if user_email in VIP_EMAILS:
                        is_vip = True
                    elif display.lower() in VIP_NAMES:
                        is_vip = True
                    
                    # First scan: All users are existing users - add them silently (no emails)
                    if is_first_scan:
                        # Use Plex createdAt if available, otherwise use current time as join date
                        created = None
                        try:
                            if getattr(u, "createdAt", None):
                                created = u.createdAt.replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                        join_date = created if created else now
                        
                        log(f"[join] EXISTING (first scan, silent track): {display} ({u.email or 'no email'}) id={uid} - join date: {join_date.isoformat()}")
                        welcomed[uid] = join_date.isoformat()
                        new_count += 1
                        continue
                except Exception as e:
                    log_error(f"[join] Error processing user ID {uid}: {e}")
                    traceback.print_exc()
                    # Continue to next user - don't skip processing other users due to one error
                    continue
                
                # After first scan: User not in welcomed = truly new user
                # Use detection timestamp (now) as their join date
                join_date = now
                
                # Skip VIP users (don't send welcome emails)
                if is_vip:
                    log(f"[join] NEW (VIP, skip email): {display} ({u.email or 'no email'}) id={uid} - join date: {now.isoformat()}")
                    welcomed[uid] = join_date.isoformat()
                    new_count += 1
                    continue
                
                # New user detected - send welcome email
                log_info(f"[join] NEW: {display} ({u.email or 'no email'}) id={uid} - join date: {now.isoformat()} (detected now)")
                log_info(f"[join] Sending welcome email to {display} ({u.email or 'no email'})")
                
                if u.email:
                    try:
                        send_email(u.email, "Access confirmed", welcome_email_html(display))
                        log(f"[join] welcome sent -> {u.email}")
                    except Exception as e:
                        log_error(f"[join] welcome email error: {e}")
                
                try:
                    send_email(ADMIN_EMAIL, "Centauri: New member onboarded",
                               admin_join_html({"id": uid, "title": display, "email": u.email}))
                    log(f"[join] admin notice sent")
                except Exception as e:
                    log_error(f"[join] admin email error: {e}")
                
                send_discord(
                    f"✅ New User Joined\n\n"
                    f"{display} ({u.email or 'no email'})\n"
                    f"ID: {uid}"
                )
                welcomed[uid] = join_date.isoformat()
                new_count += 1
                metrics["users_welcomed"] += 1
            if new_count == 0:
                log("[join] no new users")
            
            # Summary: Log all users detected vs tracked
            total_users_in_plex = len(friends)
            total_tracked = len(welcomed)
            if total_users_in_plex != total_tracked:
                log_warn(f"[join] User count mismatch: {total_users_in_plex} users in Plex, but {total_tracked} in welcomed dict")
                # Log which users are in Plex but not tracked
                plex_user_ids = {str(u.id) for u in friends}
                tracked_user_ids = set(welcomed.keys())
                missing_users = plex_user_ids - tracked_user_ids
                if missing_users:
                    missing_details = []
                    for mu_id in missing_users:
                        for u in friends:
                            if str(u.id) == mu_id:
                                missing_details.append(f"{u.title or u.username} (ID: {mu_id})")
                                break
                    log_warn(f"[join] Users in Plex but not in welcomed dict: {', '.join(missing_details)}")
            else:
                log_debug(f"[join] All {total_users_in_plex} users are tracked in welcomed dict")
            
            # Always save state to persist welcomed dict updates
            log_debug(f"[join] Saving state with {len(welcomed)} users in welcomed dict")
            state["welcomed"] = welcomed
            save_state(state)
            log_debug(f"[join] State saved successfully")
            
            # Process email retry queue
            process_email_retry_queue()
            
            metrics["last_activity"] = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            log_error(f"[join] error: {e}")
            traceback.print_exc()
        time.sleep(CHECK_NEW_USERS_SECS)

def slow_inactivity_watcher():
    log("[inactive] loop thread started")
    acct = get_plex_account()
    
    # Get owner account info for matching (owner account won't be in friends list)
    owner_username = None
    owner_email = None
    try:
        if hasattr(acct, 'username'):
            owner_username = (acct.username or "").lower()
        if hasattr(acct, 'email'):
            owner_email = (acct.email or "").lower()
    except Exception:
        pass
    
    # Validate server exists (but don't store unused variable)
    if PLEX_SERVER_NAME:
        server = get_plex_server_resource(acct)
        if not server:
            log_warn(f"[inactive] Server '{PLEX_SERVER_NAME}' not found, continuing anyway")
    
    tick = 0

    while not stop_event.is_set():
        tick += 1
        try:
            # Reload state each iteration to see updates from other threads
            state = load_state()
            warned = state.get("warned", {})
            removed = state.get("removed", {})
            welcomed = state.get("welcomed", {})  # Track when users joined
            log(f"[inactive] tick {tick} – scanning users…")
            
            # Retry logic for Plex API calls
            plex_users = None
            for attempt in range(3):
                try:
                    plex_users = acct.users()
                    break
                except Exception as e:
                    if attempt < 2:
                        log(f"[inactive] Plex API error (attempt {attempt+1}/3), retrying in 5s: {e}")
                        time.sleep(5)
                    else:
                        raise
            
            if plex_users is None:
                log("[inactive] Could not fetch users after 3 attempts, skipping this tick")
                continue
                
            # Build mapping dictionaries for efficient lookup
            plex_by_email = {(u.email or "").lower(): u for u in plex_users}
            plex_by_username = {(u.username or "").lower(): u for u in plex_users}
            plex_by_id = {str(u.id): u for u in plex_users}
            
            # Also build by "title" field (Plex display name)
            plex_by_title = {(u.title or "").lower(): u for u in plex_users if u.title}

            # Retry logic for Tautulli API calls
            t_users = None
            for attempt in range(3):
                try:
                    t_users = tautulli("get_users")
                    break
                except Exception as e:
                    if attempt < 2:
                        log(f"[inactive] Tautulli API error (attempt {attempt+1}/3), retrying in 5s: {e}")
                        time.sleep(5)
                    else:
                        raise
            
            if t_users is None:
                log("[inactive] Could not fetch Tautulli users after 3 attempts, skipping this tick")
                continue
            now = datetime.now(timezone.utc)
            acted = False
            
            # Clean up removed users that are still present (failed removals or re-added users)
            # This allows them to be processed again
            users_to_unmark = []
            for removed_uid in list(removed.keys()):
                # Check if this "removed" user is still in Plex
                for pu in plex_users:
                    if str(pu.id) == removed_uid:
                        removal_info = removed[removed_uid]
                        log(f"[inactive] User {pu.title or pu.username} (ID: {removed_uid}) marked as removed but still present in Plex!")
                        log(f"[inactive] Previous removal: {removal_info.get('when')}, ok={removal_info.get('ok')}")
                        log(f"[inactive] Unmarking for re-processing...")
                        users_to_unmark.append(removed_uid)
                        break
            
            # Remove them from the removed dict AND re-add to welcomed dict with grace period
            for uid_to_unmark in users_to_unmark:
                del removed[uid_to_unmark]
                # Give them a fresh 24-hour grace period since they were re-added
                welcomed[uid_to_unmark] = now.isoformat()
                log(f"[inactive] Re-tracked user {uid_to_unmark} with new 24h grace period")
                acted = True
            
            # Save state immediately after cleanup to prevent loss on crash
            if acted:
                state["removed"] = removed
                state["welcomed"] = welcomed
                save_state(state)
                log(f"[inactive] Saved state after unmarking {len(users_to_unmark)} user(s)")
                acted = False  # Reset for main processing loop

            for tu in t_users:
                tid   = tu.get("user_id")
                tuser = (tu.get("username") or "").lower()
                temail= (tu.get("email") or "").lower()

                # Skip Tautulli's "local" user (ID: 0) - represents local plays, not a Plex user account
                if tid == 0 or tid == "0" or tuser == "local":
                    log_debug(f"[inactive] Skipping Tautulli local user (ID: {tid}) - not a Plex user account")
                    continue

                # Try multiple matching strategies
                pu = None
                
                # Strategy 1: Match by email (most reliable)
                if temail:
                    pu = plex_by_email.get(temail)
                    if pu:
                        log_debug(f"[inactive] Matched Tautulli user '{tuser or temail}' to Plex user by email")
                
                # Strategy 2: Match by username
                if not pu and tuser:
                    pu = plex_by_username.get(tuser)
                    if pu:
                        log_debug(f"[inactive] Matched Tautulli user '{tuser}' to Plex user by username")
                
                # Strategy 3: Match by title (display name)
                if not pu and tuser:
                    # Try matching Tautulli username against Plex title
                    pu = plex_by_title.get(tuser)
                    if pu:
                        log_debug(f"[inactive] Matched Tautulli user '{tuser}' to Plex user by title")
                
                # Strategy 4: Try matching by removing .0 suffix (username.0 -> username)
                if not pu and tuser and tuser.endswith('.0'):
                    base_username = tuser[:-2]  # Remove '.0'
                    pu = plex_by_username.get(base_username) or plex_by_title.get(base_username)
                    if pu:
                        log_debug(f"[inactive] Matched Tautulli user '{tuser}' to Plex user '{base_username}' (removed .0 suffix)")
                
                if not pu:
                    # Try one more strategy: Check if this is the owner account
                    # Plex owner account might not be in friends list - check against owner info
                    owner_match = False
                    if owner_username:
                        # Try exact match or without .0 suffix
                        owner_match = (tuser == owner_username or 
                                      (tuser.endswith('.0') and tuser[:-2] == owner_username))
                    if not owner_match and owner_email:
                        owner_match = (temail == owner_email)
                    
                    if owner_match:
                        # This is the owner account - skip it (owner can't be removed anyway)
                        log_debug(f"[inactive] Skipping Tautulli user '{tuser or temail}' (ID: {tid}) - this is the Plex owner account")
                        continue
                    
                    # Log available Plex users for debugging (only if LOG_LEVEL is DEBUG)
                    log_warn(f"[inactive] WARNING: Tautulli user '{tuser or temail}' (ID: {tid}) not found in Plex users")
                    if CURRENT_LOG_LEVEL <= LOG_LEVELS["DEBUG"]:
                        log_debug(f"[inactive] Tautulli data: username='{tuser}', email='{temail}', id={tid}")
                        log_debug(f"[inactive] Available Plex usernames: {[u.username for u in plex_users if u.username]}")
                        log_debug(f"[inactive] Available Plex emails: {[u.email for u in plex_users if u.email]}")
                        if owner_username:
                            log_debug(f"[inactive] Plex owner username: {owner_username}")
                        if owner_email:
                            log_debug(f"[inactive] Plex owner email: {owner_email}")
                    continue
                uid = str(pu.id)
                display = pu.title or pu.username or "there"
                email = pu.email
                username = (pu.username or "").lower()

                # Check VIP protection (email or username)
                if (email or "").lower() in VIP_EMAILS or username in VIP_NAMES:
                    log(f"[inactive] skip VIP: {display} ({email or 'no-email'})")
                    continue

                # Check Tautulli watch history FIRST - Tautulli always wins when available
                # This ensures daemon matches Tautulli stats at all times
                last_watch = tautulli_last_watch(tid)
                
                # If user has watch history, use it directly (skip grace period - watch time is authoritative)
                # This applies to both new users (who watched within 24h) and existing users
                if last_watch is not None:
                    # User has watch history - use it directly, Tautulli time is authoritative
                    # Skip all the grace period and baseline logic - go straight to inactivity calculation
                    log(f"[inactive] {display}: Using Tautulli watch time: {last_watch.isoformat()} (daemon matches Tautulli)")
                else:
                    # No watch history - apply grace period for new users
                    # Grace period: Skip users who joined within the last 24 hours
                    # Also fix users who were incorrectly added with recent dates (should be existing users)
                    if uid in welcomed:
                        try:
                            join_date = datetime.fromisoformat(welcomed[uid])
                            hours_since_join = (now - join_date).total_seconds() / 3600
                            
                            # If user has a very recent join date (< 24 hours), check if they're actually existing
                            # Fix their date if they have createdAt older than their welcomed date
                            if hours_since_join < 24:
                                # Check if they have createdAt (they existed before being added to welcomed)
                                if getattr(pu, "createdAt", None):
                                    try:
                                        created_at = pu.createdAt.replace(tzinfo=timezone.utc)
                                        # If their actual createdAt is older than their welcomed date, fix it
                                        if created_at < join_date:
                                            welcomed[uid] = created_at.isoformat()
                                            join_date = created_at
                                            log(f"[inactive] {display}: Fixed join date from recent ({hours_since_join:.1f}h ago) to actual createdAt: {created_at.isoformat()}")
                                            hours_since_join = (now - join_date).total_seconds() / 3600
                                    except Exception:
                                        pass
                            
                            if hours_since_join < 24:
                                log(f"[inactive] skip NEW USER (24hr grace): {display} (joined {hours_since_join:.1f}h ago)")
                                continue
                        except Exception:
                            pass
                    
                    # For users with no watch history, use their join date as the baseline (after 24hr grace)
                    if last_watch is None and uid in welcomed:
                        try:
                            join_date = datetime.fromisoformat(welcomed[uid])
                            # Add 24 hours to join date as the starting point for inactivity tracking
                            last_watch = join_date + timedelta(hours=24)
                        except Exception as e:
                            # If we can't parse the existing join date, don't overwrite it
                            # Try to use it anyway (might be a different format) or use createdAt fallback
                            log_debug(f"[inactive] {display}: Could not parse existing welcomed date: {e}")
                            # Don't overwrite existing welcomed entry
                    
                    # For existing users (not in welcomed dict), use createdAt + 24h to be fair
                    if last_watch is None and uid not in welcomed and getattr(pu, "createdAt", None):
                        try:
                            created_at = pu.createdAt.replace(tzinfo=timezone.utc)
                            # Add 24 hours to give existing users the same grace period
                            last_watch = created_at + timedelta(hours=24)
                            # Add them to welcomed dict for future tracking
                            welcomed[uid] = created_at.isoformat()
                            log(f"[inactive] {display}: Added to welcomed dict with createdAt: {created_at.isoformat()}")
                        except Exception:
                            pass

                    # If we still can't determine when they joined AND they're not in welcomed dict,
                    # Use a date far in the past (6 months ago) so they're treated as existing users
                    # This prevents them from getting a fresh 24h grace period (they're existing, not new)
                    if last_watch is None and uid not in welcomed:
                        # Use 6 months ago as default join date for existing users with unknown join dates
                        default_join_date = now - timedelta(days=180)
                        welcomed[uid] = default_join_date.isoformat()
                        # Use default join date + 24h as baseline for tracking
                        last_watch = default_join_date + timedelta(hours=24)
                        log(f"[inactive] {display}: No join date found, using default (6 months ago) for existing user")
                        log(f"[inactive] {display}: Using default join date + 24h as baseline: {last_watch.isoformat()}")
                
                # If still no last_watch and user is in welcomed (but date couldn't be parsed), skip gracefully
                if last_watch is None:
                    log_warn(f"[inactive] {display}: SKIPPING - cannot determine join date or last watch time (user in welcomed but date unparseable)")
                    continue
                
                days = (now - last_watch).days
                log(f"[inactive] {display}: last={last_watch}, days={days}")

                if days >= WARN_DAYS and days < KICK_DAYS and uid not in warned:
                    if email:
                        try:
                            send_email(email, "Inactivity notice", warn_email_html(display, days))
                            log(f"[inactive] warn sent -> {email}")
                        except Exception as e:
                            log(f"[inactive] warn email error: {e}")
                    try:
                        send_email(ADMIN_EMAIL, f"Centauri: Warning sent to {display}",
                                   f"<p>Warned ~{days}d inactive: {display} ({email or 'no-email'})</p>")
                        log("[inactive] admin warn notice sent")
                    except Exception as e:
                        log(f"[inactive] admin warn email error: {e}")
                    days_left = KICK_DAYS - days
                    send_discord(
                        f"⚠️ Inactivity Warning Sent\n\n"
                        f"{display} ({email or 'no email'})\n"
                        f"Inactive for: {days} days\n"
                        f"Days until removal: {days_left}"
                    )
                    warned[uid] = now.isoformat()
                    metrics["users_warned"] += 1
                    acted = True

                if days >= KICK_DAYS and uid not in removed:
                    reason = f"Inactivity for {days} days (threshold {KICK_DAYS})"

                    if DRY_RUN:
                        log(f"[inactive] DRY_RUN: Would remove {display} ({email or 'no-email'}) - {reason}")
                        ok = True  # Simulate success in dry run
                        tautulli_deleted = True  # Simulate success in dry run
                    else:
                        # Pass the MyPlexUser object to remove_friend
                        ok = remove_friend(acct, pu)
                        
                        # If Plex removal succeeded, also delete from Tautulli database
                        tautulli_deleted = False
                        if ok:
                            tautulli_deleted = tautulli_delete_user(tid)
                            if not tautulli_deleted:
                                log(f"[inactive] ⚠️ User removed from Plex but Tautulli deletion failed for {display}")

                    # Only send removal email to user if removal succeeded (and not in dry run)
                    if ok and email and not DRY_RUN:
                        try:
                            send_email(email, "Access revoked", removal_email_html(display))
                            log(f"[inactive] removal notice sent -> {email}")
                        except Exception as e:
                            log(f"[inactive] removal email error: {e}")
                    elif not ok:
                        log(f"[inactive] skipping user email - removal failed for {display}")

                    # Always notify admin of attempt (success or failure)
                    if not DRY_RUN:
                        try:
                            send_email(ADMIN_EMAIL, f"Centauri: User removal {'SUCCESS' if ok else 'FAILED'}",
                                       admin_removed_html({"id":uid,"title":display,"email":email}, reason,
                                                          "SUCCESS" if ok else "FAILED"))
                            log("[inactive] admin removal notice sent")
                        except Exception as e:
                            log(f"[inactive] admin removal email error: {e}")
                    
                    # Discord notification for removal
                    removal_reason = f"Inactivity for {days} days"
                    send_discord(
                        f"🚫 User Removed\n\n"
                        f"{display} ({email or 'no email'})\n"
                        f"Reason: {removal_reason}"
                    )
                    removed[uid] = {"when": now.isoformat(), "ok": ok, "reason": reason, "tautulli_deleted": tautulli_deleted}
                    if ok:
                        metrics["users_removed"] += 1
                    acted = True

            state["welcomed"] = welcomed  # Preserve welcomed dict (modified by this thread during grace period checks)
            state["warned"] = warned
            state["removed"] = removed
            # Preserve welcomed dict from state (modified by join watcher)
            # Don't overwrite with our local copy which might be stale
            state["last_inactivity_scan"] = now.isoformat()
            save_state(state)
            
            metrics["last_activity"] = now.isoformat()
            
            if not acted:
                log_debug("[inactive] no actions this tick")
            
            # Process email retry queue
            process_email_retry_queue()
            
        except Exception as e:
            log_error(f"[inactive] error: {e}")
            traceback.print_exc()

        time.sleep(CHECK_INACTIVITY_SECS)

# ============================================================================
# Health Check HTTP Server
# ============================================================================

def health_check_server():
    """Run HTTP health check server"""
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    
                    health_data = {
                        "status": "healthy",
                        "uptime_seconds": (datetime.now(timezone.utc) - 
                                         datetime.fromisoformat(metrics["start_time"])).total_seconds(),
                        "metrics": metrics,
                        "dry_run": DRY_RUN,
                        "threads": {
                            "join_watcher": t1.is_alive() if 't1' in globals() else False,
                            "inactivity_watcher": t2.is_alive() if 't2' in globals() else False
                        }
                    }
                    
                    self.wfile.write(json.dumps(health_data, indent=2).encode())
                elif self.path == "/metrics":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(metrics, indent=2).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                log_debug(f"[health] {format % args}")
        
        server = HTTPServer(("0.0.0.0", HEALTH_CHECK_PORT), HealthHandler)
        log_info(f"[health] Health check server started on port {HEALTH_CHECK_PORT}")
        
        while not stop_event.is_set():
            server.handle_request()
            
    except Exception as e:
        log_warn(f"[health] Failed to start health check server: {e}")

# ============================================================================
# CLI Commands for State Management
# ============================================================================

def find_user_by_identifier(identifier):
    """Find user ID by email, username, or ID itself"""
    try:
        acct = get_plex_account()
        users = acct.users()
        
        # Try matching by ID first
        for u in users:
            if str(u.id) == str(identifier):
                return str(u.id), u
        
        # Try matching by email
        identifier_lower = identifier.lower()
        for u in users:
            if u.email and u.email.lower() == identifier_lower:
                return str(u.id), u
        
        # Try matching by username
        for u in users:
            if u.username and u.username.lower() == identifier_lower:
                return str(u.id), u
        
        # Try matching by title/display name
        for u in users:
            if u.title and u.title.lower() == identifier_lower:
                return str(u.id), u
        
        return None, None
    except Exception as e:
        log_error(f"[cli] Error finding user: {e}")
        return None, None

def cmd_remove_welcomed(identifier):
    """Remove user from welcomed list"""
    uid, user = find_user_by_identifier(identifier)
    if not uid:
        print(f"❌ User '{identifier}' not found in Plex")
        return False
    
    state = load_state()
    welcomed = state.get("welcomed", {})
    
    if uid not in welcomed:
        print(f"ℹ️  User {user.title or user.username} (ID: {uid}) is not in welcomed list")
        return False
    
    del welcomed[uid]
    state["welcomed"] = welcomed
    save_state(state)
    
    print(f"✅ Removed {user.title or user.username} (ID: {uid}) from welcomed list")
    print(f"   They will receive a welcome email on the next scan")
    return True

def cmd_remove_warned(identifier):
    """Remove user from warned list"""
    uid, user = find_user_by_identifier(identifier)
    if not uid:
        print(f"❌ User '{identifier}' not found in Plex")
        return False
    
    state = load_state()
    warned = state.get("warned", {})
    
    if uid not in warned:
        print(f"ℹ️  User {user.title or user.username} (ID: {uid}) is not in warned list")
        return False
    
    del warned[uid]
    state["warned"] = warned
    save_state(state)
    
    print(f"✅ Removed {user.title or user.username} (ID: {uid}) from warned list")
    return True

def cmd_remove_removed(identifier):
    """Remove user from removed list"""
    uid, user = find_user_by_identifier(identifier)
    if not uid:
        print(f"❌ User '{identifier}' not found in Plex")
        return False
    
    state = load_state()
    removed = state.get("removed", {})
    
    if uid not in removed:
        print(f"ℹ️  User {user.title or user.username} (ID: {uid}) is not in removed list")
        return False
    
    del removed[uid]
    state["removed"] = removed
    save_state(state)
    
    print(f"✅ Removed {user.title or user.username} (ID: {uid}) from removed list")
    return True

def cmd_reset_user(identifier):
    """Remove user from all lists (complete reset)"""
    uid, user = find_user_by_identifier(identifier)
    if not uid:
        print(f"❌ User '{identifier}' not found in Plex")
        return False
    
    state = load_state()
    welcomed = state.get("welcomed", {})
    warned = state.get("warned", {})
    removed = state.get("removed", {})
    
    removed_from = []
    if uid in welcomed:
        del welcomed[uid]
        removed_from.append("welcomed")
    if uid in warned:
        del warned[uid]
        removed_from.append("warned")
    if uid in removed:
        del removed[uid]
        removed_from.append("removed")
    
    if not removed_from:
        print(f"ℹ️  User {user.title or user.username} (ID: {uid}) is not in any tracking list")
        return False
    
    state["welcomed"] = welcomed
    state["warned"] = warned
    state["removed"] = removed
    save_state(state)
    
    print(f"✅ Reset {user.title or user.username} (ID: {uid})")
    print(f"   Removed from: {', '.join(removed_from)}")
    if "welcomed" in removed_from:
        print(f"   They will receive a welcome email on the next scan")
    return True

def cmd_list_welcomed():
    """List all welcomed users"""
    state = load_state()
    welcomed = state.get("welcomed", {})
    
    if not welcomed:
        print("ℹ️  No users in welcomed list")
        return
    
    try:
        acct = get_plex_account()
        users = acct.users()
        user_map = {str(u.id): u for u in users}
        
        print(f"✅ Welcomed Users ({len(welcomed)}):")
        print("-" * 80)
        for uid, join_date in sorted(welcomed.items(), key=lambda x: x[1]):
            user = user_map.get(uid)
            if user:
                print(f"  • {user.title or user.username} ({user.email or 'no email'}) - ID: {uid}")
                print(f"    Joined: {join_date}")
            else:
                print(f"  • User ID: {uid} (not found in Plex)")
                print(f"    Joined: {join_date}")
    except Exception as e:
        print(f"❌ Error listing users: {e}")

def cmd_list_warned():
    """List all warned users"""
    state = load_state()
    warned = state.get("warned", {})
    
    if not warned:
        print("ℹ️  No users in warned list")
        return
    
    try:
        acct = get_plex_account()
        users = acct.users()
        user_map = {str(u.id): u for u in users}
        
        print(f"⚠️  Warned Users ({len(warned)}):")
        print("-" * 80)
        for uid, warn_date in sorted(warned.items(), key=lambda x: x[1]):
            user = user_map.get(uid)
            if user:
                print(f"  • {user.title or user.username} ({user.email or 'no email'}) - ID: {uid}")
                print(f"    Warned: {warn_date}")
            else:
                print(f"  • User ID: {uid} (not found in Plex)")
                print(f"    Warned: {warn_date}")
    except Exception as e:
        print(f"❌ Error listing users: {e}")

def cmd_list_removed():
    """List all removed users"""
    state = load_state()
    removed = state.get("removed", {})
    
    if not removed:
        print("ℹ️  No users in removed list")
        return
    
    try:
        acct = get_plex_account()
        users = acct.users()
        user_map = {str(u.id): u for u in users}
        
        print(f"🚫 Removed Users ({len(removed)}):")
        print("-" * 80)
        for uid, removal_info in sorted(removed.items(), key=lambda x: x[1].get("when", "")):
            if isinstance(removal_info, dict):
                when = removal_info.get("when", "unknown")
                reason = removal_info.get("reason", "unknown")
                ok = removal_info.get("ok", False)
                status = "✅" if ok else "❌"
            else:
                when = removal_info if isinstance(removal_info, str) else "unknown"
                reason = "unknown"
                ok = True
                status = "?"
            
            user = user_map.get(uid)
            if user:
                print(f"  {status} {user.title or user.username} ({user.email or 'no email'}) - ID: {uid}")
                print(f"    Removed: {when}")
                print(f"    Reason: {reason}")
            else:
                print(f"  {status} User ID: {uid} (not found in Plex)")
                print(f"    Removed: {when}")
                print(f"    Reason: {reason}")
    except Exception as e:
        print(f"❌ Error listing users: {e}")

def cmd_help():
    """Show help for CLI commands"""
    print("Centauri Guardian CLI Commands")
    print("=" * 80)
    print()
    print("Usage: python main.py <command> [identifier]")
    print()
    print("Commands:")
    print("  remove-welcomed <email|username|id>  - Remove user from welcomed list")
    print("  remove-warned <email|username|id>     - Remove user from warned list")
    print("  remove-removed <email|username|id>    - Remove user from removed list")
    print("  reset-user <email|username|id>        - Remove user from all lists")
    print("  list-welcomed                         - List all welcomed users")
    print("  list-warned                           - List all warned users")
    print("  list-removed                          - List all removed users")
    print("  test-discord                          - Send test Discord notifications")
    print()
    print("Examples:")
    print("  python main.py remove-welcomed 'test@example.com'")
    print("  python main.py remove-welcomed 'testuser'")
    print("  python main.py remove-welcomed '123456789'")
    print("  python main.py reset-user 'test@example.com'")
    print("  python main.py list-welcomed")
    print()

def handle_cli_command():
    """Handle CLI commands - returns True if command was handled, False otherwise"""
    if len(sys.argv) < 2:
        return False
    
    command = sys.argv[1].lower()
    
    if command == "help" or command == "-h" or command == "--help":
        cmd_help()
        return True
    
    if command == "remove-welcomed":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide user identifier (email, username, or ID)")
            print("   Example: python main.py remove-welcomed 'test@example.com'")
            return True
        identifier = " ".join(sys.argv[2:])
        cmd_remove_welcomed(identifier)
        return True
    
    if command == "remove-warned":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide user identifier (email, username, or ID)")
            print("   Example: python main.py remove-warned 'test@example.com'")
            return True
        identifier = " ".join(sys.argv[2:])
        cmd_remove_warned(identifier)
        return True
    
    if command == "remove-removed":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide user identifier (email, username, or ID)")
            print("   Example: python main.py remove-removed 'test@example.com'")
            return True
        identifier = " ".join(sys.argv[2:])
        cmd_remove_removed(identifier)
        return True
    
    if command == "reset-user":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide user identifier (email, username, or ID)")
            print("   Example: python main.py reset-user 'test@example.com'")
            return True
        identifier = " ".join(sys.argv[2:])
        cmd_reset_user(identifier)
        return True
    
    if command == "list-welcomed":
        cmd_list_welcomed()
        return True
    
    if command == "list-warned":
        cmd_list_warned()
        return True
    
    if command == "list-removed":
        cmd_list_removed()
        return True
    
    if command == "test-discord":
        test_discord_notifications()
        return True
    
    return False

# ============================================================================
# Signal Handlers & Graceful Shutdown
# ============================================================================

def handle_signal(sig, frame):
    """Handle shutdown signals gracefully"""
    log_info(f"Received signal {sig}, initiating graceful shutdown...")
    stop_event.set()

def graceful_shutdown():
    """Perform graceful shutdown"""
    log_info("Performing graceful shutdown...")
    
    # Save final state
    try:
        state = load_state()
        save_state(state)
    except:
        pass
    
    # Log final metrics
    log_info(f"Final metrics: {json.dumps(metrics, indent=2)}")
    
    log_info("Shutdown complete")

if __name__ == "__main__":
    import atexit
    
    # Register shutdown handler
    atexit.register(graceful_shutdown)
    
    # Check for CLI commands first
    if handle_cli_command():
        sys.exit(0)
    
    log_info("Centauri Guardian daemon starting...")
    log_info(f"Configuration: WARN_DAYS={WARN_DAYS}, KICK_DAYS={KICK_DAYS}, DRY_RUN={DRY_RUN}")
    log_info(f"VIP protection: {len(VIP_EMAILS)} email(s) + {len(VIP_NAMES)} username(s)")
    
    if DRY_RUN:
        log_warn("DRY_RUN MODE ENABLED - No users will be removed, no emails will be sent")
    else:
        log_info("LIVE MODE - User removals and emails will be sent")
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    # Start worker threads
    t1 = threading.Thread(target=fast_join_watcher, daemon=True, name="JoinWatcher")
    t2 = threading.Thread(target=slow_inactivity_watcher, daemon=True, name="InactivityWatcher")
    t3 = threading.Thread(target=health_check_server, daemon=True, name="HealthCheck")
    
    t1.start()
    t2.start()
    t3.start()
    
    log_info("All threads started")
    
    # Monitor threads
    try:
        while not stop_event.is_set():
            time.sleep(5)
            if not t1.is_alive():
                log_critical("FATAL: fast_join_watcher thread died unexpectedly!")
                stop_event.set()
                sys.exit(1)
            if not t2.is_alive():
                log_critical("FATAL: slow_inactivity_watcher thread died unexpectedly!")
                stop_event.set()
                sys.exit(1)
    except KeyboardInterrupt:
        log_info("Received keyboard interrupt")
    finally:
        graceful_shutdown()
        log_info("Centauri Guardian daemon stopped.")
