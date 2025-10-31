import os, time, json, signal, threading, smtplib, requests, math, random
import traceback
from datetime import datetime, timedelta, timezone


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

from email.mime.text import MIMEText
from dateutil import parser as dtp


# Load .env file if it exists (for persistent configuration)
def load_env_file(filepath="/app/.env"):
    """Load environment variables from a file if it exists."""
    if os.path.exists(filepath):
        log(f"Loading environment variables from {filepath}")
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    # Only set if not already in environment (env vars take precedence)
                    if key not in os.environ:
                        os.environ[key] = value
        log("Environment variables loaded from file")
    else:
        log(f"No .env file found at {filepath}, using environment variables only")

# Load .env file before checking required vars
load_env_file()


REQUIRED_ENVS = [
    "PLEX_TOKEN","TAUTULLI_URL","TAUTULLI_API_KEY",
    "SMTP_HOST","SMTP_PORT","SMTP_USERNAME","SMTP_PASSWORD","SMTP_FROM","ADMIN_EMAIL"
]
missing = [k for k in REQUIRED_ENVS if not os.environ.get(k)]
if missing:
    raise SystemExit(f"Missing required env(s): {', '.join(missing)}")


# ---- Config via env ----
PLEX_TOKEN       = os.environ["PLEX_TOKEN"]
PLEX_SERVER_NAME = os.environ.get("PLEX_SERVER_NAME","")
TAUTULLI_URL     = os.environ["TAUTULLI_URL"].rstrip("/")
TAUTULLI_API_KEY = os.environ["TAUTULLI_API_KEY"]

SMTP_HOST        = os.environ["SMTP_HOST"]
SMTP_PORT        = int(os.environ.get("SMTP_PORT","587"))
SMTP_USERNAME    = os.environ["SMTP_USERNAME"]
SMTP_PASSWORD    = os.environ["SMTP_PASSWORD"]
SMTP_FROM        = os.environ["SMTP_FROM"]
ADMIN_EMAIL      = os.environ["ADMIN_EMAIL"]

WARN_DAYS        = int(os.environ.get("WARN_DAYS","27"))
KICK_DAYS        = int(os.environ.get("KICK_DAYS","30"))

CHECK_NEW_USERS_SECS   = int(os.environ.get("CHECK_NEW_USERS_SECS","120"))
CHECK_INACTIVITY_SECS  = int(os.environ.get("CHECK_INACTIVITY_SECS","1800"))

# VIP protection - these users are protected from auto-removal
VIP_EMAILS = [ADMIN_EMAIL.lower()]  # Admin is always VIP
# Add additional VIP usernames from environment variable (comma-separated)
VIP_NAMES_STR = os.environ.get("VIP_NAMES", "")
VIP_NAMES = [name.strip().lower() for name in VIP_NAMES_STR.split(",") if name.strip()]

# Dry run mode - when enabled, no actual removals or emails are sent
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() in ("true", "1", "yes")

STATE_DIR  = "/app/state"
STATE_FILE = f"{STATE_DIR}/state.json"
os.makedirs(STATE_DIR, exist_ok=True)

stop_event = threading.Event()

from plexapi.myplex import MyPlexAccount
import time

def get_plex_account():
    token = os.environ.get("PLEX_TOKEN")
    if not token:
        raise SystemExit("PLEX_TOKEN missing")

    # Use keyword arg so plexapi does TOKEN auth (not username/password)
    return MyPlexAccount(token=token)

def get_plex_server_resource(acct):
    target = os.environ.get("PLEX_SERVER_NAME")
    if not target:
        raise SystemExit("PLEX_SERVER_NAME missing")

    # Be tolerant: some plexapi versions expose .provides == "server"
    # others prefer .product == "Plex Media Server"
    for res in acct.resources():
        if (getattr(res, "provides", None) == "server" or getattr(res, "product", "") == "Plex Media Server"):
            if res.name == target:
                return res
    raise SystemExit(f"Server '{target}' not found in Plex account resources")



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
        "✅ **New User Joined**\n"
        "**Test User** (test@example.com)\n"
        "ID: 99999999"
    )
    send_discord(join_msg)
    log("[test] User Join notification sent")
    time.sleep(1)
    
    # Test 2: Warning
    warning_msg = (
        "⚠️ **Inactivity Warning Sent**\n"
        "**Test User** (test@example.com)\n"
        "Inactive for: 27 days\n"
        "Days until removal: 3"
    )
    send_discord(warning_msg)
    log("[test] Warning notification sent")
    time.sleep(1)
    
    # Test 3: Removal
    removal_msg = (
        "🚫 **User Removed**\n"
        "**Test User** (test@example.com)\n"
        "Reason: Inactivity for 30 days"
    )
    send_discord(removal_msg)
    log("[test] Removal notification sent")
    
    log("[test] ✅ All test notifications sent!")


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"welcomed": {}, "warned": {}, "removed": {}, "last_inactivity_scan": None}
    with open(STATE_FILE,"r") as f:
        return json.load(f)

def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp,"w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp, STATE_FILE)

def send_email(to_addr, subject, html_body):
    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_addr
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USERNAME, SMTP_PASSWORD)
        s.sendmail(SMTP_FROM, [to_addr], msg.as_string())

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

def plex_machine_id():
    # find our server machineIdentifier
    sr = requests.get("https://plex.tv/api/servers", headers=plex_headers(), timeout=30)
    sr.raise_for_status()
    from xml.etree import ElementTree as ET
    root = ET.fromstring(sr.text)
    # If server name not specified, pick the first claimed
    cand = None
    for s in root.findall("Server"):
        if not PLEX_SERVER_NAME or s.attrib.get("name")==PLEX_SERVER_NAME:
            cand = s.attrib.get("machineIdentifier")
            if PLEX_SERVER_NAME: break
    if not cand:
        raise RuntimeError("Could not find Plex server machineIdentifier; check PLEX_SERVER_NAME.")
    return cand

def plex_shared_map(machine_id):
    # https://plex.tv/api/servers/<machineIdentifier>/shared_servers
    url = f"https://plex.tv/api/servers/{machine_id}/shared_servers"
    rr = requests.get(url, headers=plex_headers(), timeout=30)
    rr.raise_for_status()
    from xml.etree import ElementTree as ET
    root = ET.fromstring(rr.text)
    m = {}
    for ss in root.findall("SharedServer"):
        shared_id = ss.attrib.get("id")
        for lu in ss.findall("SharedUser"):
            uid = lu.attrib.get("id")
            m[uid] = shared_id
    return m

def plex_remove_user(user_id, shared_id_map):
    # try DELETE /api/friends/<id>, fallback to /api/shared_servers/<id>
    url = f"https://plex.tv/api/friends/{user_id}"
    r = requests.delete(url, headers=plex_headers(), timeout=30)
    if r.status_code in (200,204):
        return True
    sid = shared_id_map.get(user_id)
    if sid:
        r = requests.delete(f"https://plex.tv/api/shared_servers/{sid}", headers=plex_headers(), timeout=30)
        return r.status_code in (200,204)
    return False

def remove_friend(acct, user_id):
    """Remove a user from Plex server access"""
    try:
        # Get machine ID and shared server mapping
        machine_id = plex_machine_id()
        shared_map = plex_shared_map(machine_id)
        
        # Use the existing plex_remove_user function
        return plex_remove_user(user_id, shared_map)
    except Exception as e:
        log(f"[remove_friend] error removing user {user_id}: {e}")
        return False

def tautulli(cmd, **params):
    payload = {"apikey": TAUTULLI_API_KEY, "cmd": cmd, **params}
    r = requests.get(f"{TAUTULLI_URL}/api/v2", params=payload, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("response",{}).get("result") != "success":
        raise RuntimeError(f"Tautulli API error: {j}")
    return j["response"]["data"]

def tautulli_users():
    return tautulli("get_users")

def tautulli_last_watch(user_id):
    hist = tautulli("get_history", user_id=user_id, length=1, order_column="date", order_dir="desc")
    records = hist.get("data",[])
    if not records:
        return None
    ts = records[0].get("date")
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)

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
    state = load_state()
    welcomed = state.get("welcomed", {})
    removed = state.get("removed", {})
    tick = 0
    while not stop_event.is_set():
        tick += 1
        try:
            log(f"[join] tick {tick} – checking new users…")
            # Retry logic for Plex API calls
            all_users = None
            for attempt in range(3):
                try:
                    all_users = plex_get_users()
                    break
                except Exception as e:
                    if attempt < 2:
                        log(f"[join] Plex API error (attempt {attempt+1}/3), retrying in 5s: {e}")
                        time.sleep(5)
                    else:
                        raise
            
            if all_users is None:
                log("[join] Could not fetch users after 3 attempts, skipping this tick")
                continue
                
            now = datetime.now(timezone.utc)
            new_count = 0
            rejoined_count = 0
            for u in all_users:
                uid = str(u["id"])
                display = u["title"] or u["username"] or "there"
                email = u["email"]
                
                # Check if user was previously removed but is back now
                if uid in removed:
                    log(f"[join] REJOINED: {display} ({email or 'no email'}) id={uid} - was in removed section")
                    
                    if DRY_RUN:
                        log(f"[DRY RUN] Would move {display} from removed to welcomed and send welcome email")
                    else:
                        # Send welcome email for rejoined user
                        if email:
                            try:
                                send_email(email, "Access confirmed", welcome_email_html(display))
                                log(f"[join] welcome sent to rejoined user -> {email}")
                            except Exception as e:
                                log(f"[join] welcome email error: {e}")
                        try:
                            send_email(ADMIN_EMAIL, "Centauri: User rejoined",
                                       admin_join_html({"id": uid, "title": display, "email": email}))
                            log(f"[join] admin notice sent for rejoined user")
                        except Exception as e:
                            log(f"[join] admin email error: {e}")
                        send_discord(f"🔄 User rejoined Plex: {display} ({email or 'no email'}) - previously removed")
                        
                        # Move from removed to welcomed
                        del removed[uid]
                    
                    welcomed[uid] = now.isoformat()
                    rejoined_count += 1
                    continue
                
                if uid in welcomed:
                    continue
                # New user detected (not yet welcomed)
                log(f"[join] NEW: {display} ({email or 'no email'}) id={uid}")
                
                if DRY_RUN:
                    log(f"[DRY RUN] Would send welcome email to {display} ({email or 'no email'})")
                else:
                    if email:
                        try:
                            send_email(email, "Access confirmed", welcome_email_html(display))
                            log(f"[join] welcome sent -> {email}")
                        except Exception as e:
                            log(f"[join] welcome email error: {e}")
                    try:
                        send_email(ADMIN_EMAIL, "Centauri: New member onboarded",
                                   admin_join_html({"id": uid, "title": display, "email": email}))
                        log(f"[join] admin notice sent")
                    except Exception as e:
                        log(f"[join] admin email error: {e}")
                    send_discord(f"👤 New Plex user joined: {display} ({email or 'no email'})")
                
                welcomed[uid] = now.isoformat()
                new_count += 1
            if new_count == 0 and rejoined_count == 0:
                log("[join] no new users")
            elif rejoined_count > 0:
                log(f"[join] {rejoined_count} user(s) rejoined, {new_count} new user(s)")
            state["welcomed"] = welcomed
            state["removed"] = removed
            save_state(state)
        except Exception as e:
            log(f"[join] error: {e}")
            traceback.print_exc()
        time.sleep(CHECK_NEW_USERS_SECS)

def slow_inactivity_watcher():
    log("[inactive] loop thread started")
    state = load_state()
    warned = state.get("warned", {})
    removed = state.get("removed", {})
    welcomed = state.get("welcomed", {})  # Track when users joined
    server = get_plex_server_resource(get_plex_account())
    tick = 0

    while not stop_event.is_set():
        tick += 1
        try:
            log(f"[inactive] tick {tick} – scanning users…")
            
            # Retry logic for Plex API calls
            plex_users = None
            for attempt in range(3):
                try:
                    plex_users = plex_get_users()
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
                
            plex_by_email = {(u["email"] or "").lower(): u for u in plex_users}
            plex_by_username = {(u["username"] or "").lower(): u for u in plex_users}

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

            for tu in t_users:
                tid   = tu.get("user_id")
                tuser = (tu.get("username") or "").lower()
                temail= (tu.get("email") or "").lower()

                pu = plex_by_email.get(temail) or plex_by_username.get(tuser)
                if not pu:
                    continue
                uid = str(pu["id"])
                display = pu["title"] or pu["username"] or "there"
                email = pu["email"]
                username = (pu["username"] or "").lower()

                # Check VIP protection (email or username)
                if (email or "").lower() in VIP_EMAILS or username in VIP_NAMES:
                    log(f"[inactive] skip VIP: {display} ({email or 'no-email'})")
                    continue

                # Grace period: Skip users who joined within the last 24 hours
                if uid in welcomed:
                    try:
                        join_date = datetime.fromisoformat(welcomed[uid])
                        hours_since_join = (now - join_date).total_seconds() / 3600
                        if hours_since_join < 24:
                            log(f"[inactive] skip NEW USER (24hr grace): {display} (joined {hours_since_join:.1f}h ago)")
                            continue
                    except Exception:
                        pass

                last_watch = tautulli_last_watch(tid)
                
                # For users with no watch history, use their join date as the baseline (after 24hr grace)
                if last_watch is None and uid in welcomed:
                    try:
                        join_date = datetime.fromisoformat(welcomed[uid])
                        # Add 24 hours to join date as the starting point for inactivity tracking
                        last_watch = join_date + timedelta(hours=24)
                    except Exception:
                        pass
                if last_watch is None and pu.get("createdAt"):
                    try:
                        created_at = datetime.fromisoformat(pu["createdAt"])
                        last_watch = created_at.replace(tzinfo=timezone.utc)
                    except Exception:
                        pass

                days = KICK_DAYS if last_watch is None else (now - last_watch).days
                log(f"[inactive] {display}: last={last_watch}, days={days}")

                if days >= WARN_DAYS and days < KICK_DAYS and uid not in warned:
                    if DRY_RUN:
                        log(f"[DRY RUN] Would warn {display} ({email or 'no email'}) - {days} days inactive")
                    else:
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
                        send_discord(f"⚠️ Warned {display} (~{days}d inactive)")
                    warned[uid] = now.isoformat()
                    acted = True

                if days >= KICK_DAYS and uid not in removed:
                    reason = f"Inactivity for {days} days (threshold {KICK_DAYS})"
                    
                    if DRY_RUN:
                        log(f"[DRY RUN] Would remove {display} ({email or 'no email'}) - {reason}")
                        ok = False  # Simulated failure in dry run
                    else:
                        ok = remove_friend(get_plex_account(), uid)
                        
                        if ok:
                            # Removal succeeded - notify user and admin
                            if email:
                                try:
                                    send_email(email, "Access revoked", removal_email_html(display))
                                    log(f"[inactive] removal notice sent -> {email}")
                                except Exception as e:
                                    log(f"[inactive] removal email error: {e}")
                            try:
                                send_email(ADMIN_EMAIL, f"Centauri: User removal SUCCESS",
                                           admin_removed_html({"id":uid,"title":display,"email":email}, reason, "SUCCESS"))
                                log("[inactive] admin removal SUCCESS notice sent")
                            except Exception as e:
                                log(f"[inactive] admin removal email error: {e}")
                            send_discord(f"🗑️ Removal ✅ {display} :: {reason}")
                        else:
                            # Removal failed - only notify admin, don't email the user
                            log(f"[inactive] removal FAILED for {display} - user NOT notified")
                            try:
                                send_email(ADMIN_EMAIL, f"Centauri: User removal FAILED",
                                           admin_removed_html({"id":uid,"title":display,"email":email}, reason, "FAILED"))
                                log("[inactive] admin removal FAILED notice sent")
                            except Exception as e:
                                log(f"[inactive] admin removal email error: {e}")
                            send_discord(f"🗑️ Removal ❌ {display} :: {reason}")
                    
                    removed[uid] = {"when": now.isoformat(), "ok": ok, "reason": reason}
                    acted = True

            state["warned"] = warned
            state["removed"] = removed
            state["last_inactivity_scan"] = now.isoformat()
            save_state(state)
            if not acted:
                log("[inactive] no actions this tick")
        except Exception as e:
            log(f"[inactive] error: {e}")
            traceback.print_exc()

        time.sleep(CHECK_INACTIVITY_SECS)
def handle_signal(sig, frame):
    stop_event.set()

if __name__ == "__main__":
    import sys
    
    # Check for test command
    if len(sys.argv) > 1 and sys.argv[1] == "test-discord":
        test_discord_notifications()
        sys.exit(0)
    
    log("Centauri Guardian daemon started.")
    log(f"[config] DRY_RUN mode: {'ENABLED' if DRY_RUN else 'DISABLED'}")
    if DRY_RUN:
        log("[config] ⚠️ DRY_RUN is ON - No emails will be sent, no users will be removed")
    else:
        log("[config] ⚡ LIVE MODE - Emails will be sent and users will be removed")
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    t1 = threading.Thread(target=fast_join_watcher, daemon=True)
    t2 = threading.Thread(target=slow_inactivity_watcher, daemon=True)
    t1.start(); t2.start()
    while not stop_event.is_set():
        time.sleep(1)
