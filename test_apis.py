#!/usr/bin/env python3
"""
Comprehensive API connectivity test for Plex and Tautulli
Run this to verify both APIs are working correctly before deploying
"""

import os
import sys
from datetime import datetime, timezone

# Load environment variables (for Docker, they come from env vars, not .env file)
# Try .env file first (local development), then fall back to environment variables
def load_env():
    """Load environment variables from .env file or use existing env vars"""
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    if key not in os.environ:  # Don't override existing env vars
                        os.environ[key] = value
    except FileNotFoundError:
        pass  # .env file not required if using Docker env vars

load_env()

print("=" * 70)
print("COMPREHENSIVE API CONNECTIVITY TEST")
print("=" * 70)

# ============================================================================
# PLEX API TESTS
# ============================================================================
print("\n" + "=" * 70)
print("PLEX API TESTS")
print("=" * 70)

# Test 1: Import plexapi
print("\n1️⃣  Testing plexapi import...")
try:
    from plexapi.myplex import MyPlexAccount
    print("   ✅ plexapi library imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import plexapi: {e}")
    print("   Install with: pip install plexapi>=4.15.0")
    sys.exit(1)

# Test 2: Check Plex environment variables
print("\n2️⃣  Checking Plex environment variables...")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN")
PLEX_SERVER_NAME = os.environ.get("PLEX_SERVER_NAME")

if not PLEX_TOKEN:
    print("   ❌ PLEX_TOKEN not set")
    sys.exit(1)
print(f"   ✅ PLEX_TOKEN: {PLEX_TOKEN[:10]}...{PLEX_TOKEN[-4:]}")

if not PLEX_SERVER_NAME:
    print("   ⚠️  PLEX_SERVER_NAME not set (optional)")
else:
    print(f"   ✅ PLEX_SERVER_NAME: {PLEX_SERVER_NAME}")

# Test 3: Connect to Plex account
print("\n3️⃣  Connecting to Plex account...")
try:
    account = MyPlexAccount(token=PLEX_TOKEN)
    print(f"   ✅ Connected as: {account.username} ({account.email})")
except Exception as e:
    print(f"   ❌ Failed to connect: {e}")
    sys.exit(1)

# Test 4: Verify removeFriend method exists
print("\n4️⃣  Checking removeFriend method...")
if hasattr(account, 'removeFriend') and callable(getattr(account, 'removeFriend')):
    print("   ✅ removeFriend method is available")
else:
    print("   ❌ removeFriend method not found")
    sys.exit(1)

# Test 5: List all users/friends
print("\n5️⃣  Fetching user list from Plex...")
try:
    users = account.users()
    print(f"   ✅ Found {len(users)} users")
    
    if users:
        print("\n   📋 User List (first 5):")
        for i, user in enumerate(users[:5], 1):
            username = user.username or "N/A"
            email = user.email or "N/A"
            user_id = user.id
            user_type = "Home User" if hasattr(user, 'home') and user.home else "Friend"
            print(f"      {i}. {username} ({email}) - ID: {user_id} - Type: {user_type}")
        if len(users) > 5:
            print(f"      ... and {len(users) - 5} more")
    else:
        print("   ℹ️  No users found (only you)")
    
    plex_user_count = len(users)
    
except Exception as e:
    print(f"   ❌ Failed to fetch users: {e}")
    import traceback
    traceback.print_exc()
    plex_user_count = 0

# Test 6: Check server access
print("\n6️⃣  Checking Plex server access...")
try:
    resources = account.resources()
    servers = [r for r in resources if getattr(r, 'provides', None) == 'server' or
               getattr(r, 'product', '') == 'Plex Media Server']
    
    print(f"   ✅ Found {len(servers)} server(s)")
    
    if PLEX_SERVER_NAME:
        target_server = None
        for server in servers:
            if server.name == PLEX_SERVER_NAME:
                target_server = server
                print(f"   ✅ Target server '{PLEX_SERVER_NAME}' found")
                break
        
        if not target_server:
            print(f"   ⚠️  Warning: Target server '{PLEX_SERVER_NAME}' not found")
            print(f"   Available servers:")
            for server in servers:
                print(f"      - {server.name}")
    else:
        print("   ℹ️  PLEX_SERVER_NAME not set, skipping server check")
        
except Exception as e:
    print(f"   ⚠️  Could not check servers: {e}")

# Test 7: Check plexapi version
print("\n7️⃣  Checking plexapi version...")
try:
    import plexapi
    version = getattr(plexapi, '__version__', 'Unknown')
    print(f"   ✅ plexapi version: {version}")
    
    # Check if version is >= 4.15.0
    if version != 'Unknown':
        try:
            from packaging import version as pkg_version
            if pkg_version.parse(version) >= pkg_version.parse("4.15.0"):
                print(f"   ✅ Version {version} is compatible (>= 4.15.0)")
            else:
                print(f"   ⚠️  Warning: Version {version} is below 4.15.0, may have issues")
        except:
            print(f"   ⚠️  Could not verify version compatibility")
except:
    print("   ⚠️  Could not determine plexapi version")

# ============================================================================
# TAUTULLI API TESTS
# ============================================================================
print("\n" + "=" * 70)
print("TAUTULLI API TESTS")
print("=" * 70)

# Test 8: Check Tautulli environment variables
print("\n8️⃣  Checking Tautulli environment variables...")
TAUTULLI_URL = os.environ.get("TAUTULLI_URL")
TAUTULLI_API_KEY = os.environ.get("TAUTULLI_API_KEY")

if not TAUTULLI_URL:
    print("   ❌ TAUTULLI_URL not set")
    sys.exit(1)
print(f"   ✅ TAUTULLI_URL: {TAUTULLI_URL}")

if not TAUTULLI_API_KEY:
    print("   ❌ TAUTULLI_API_KEY not set")
    sys.exit(1)
print(f"   ✅ TAUTULLI_API_KEY: {TAUTULLI_API_KEY[:10]}...{TAUTULLI_API_KEY[-4:]}")

# Test 9: Test Tautulli API connection
print("\n9️⃣  Testing Tautulli API connection...")
try:
    import requests
    
    # Test basic API connection
    params = {
        "apikey": TAUTULLI_API_KEY,
        "cmd": "ping"
    }
    r = requests.get(f"{TAUTULLI_URL}/api/v2", params=params, timeout=10)
    r.raise_for_status()
    j = r.json()
    
    if j.get("response", {}).get("result") == "success":
        print("   ✅ Tautulli API connection successful")
    else:
        print(f"   ❌ Tautulli API returned error: {j}")
        sys.exit(1)
        
except requests.exceptions.RequestException as e:
    print(f"   ❌ Failed to connect to Tautulli: {e}")
    print(f"   Check if Tautulli is running and accessible at: {TAUTULLI_URL}")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ Tautulli API error: {e}")
    sys.exit(1)

# Test 10: Get Tautulli users
print("\n🔟 Fetching users from Tautulli...")
try:
    params = {
        "apikey": TAUTULLI_API_KEY,
        "cmd": "get_users"
    }
    r = requests.get(f"{TAUTULLI_URL}/api/v2", params=params, timeout=10)
    r.raise_for_status()
    j = r.json()
    
    if j.get("response", {}).get("result") != "success":
        print(f"   ❌ Tautulli API error: {j}")
        sys.exit(1)
    
    tautulli_users = j.get("response", {}).get("data", [])
    print(f"   ✅ Found {len(tautulli_users)} users in Tautulli")
    
    if tautulli_users:
        print("\n   📋 Tautulli User List (first 5):")
        for i, tu in enumerate(tautulli_users[:5], 1):
            username = tu.get("username", "N/A")
            email = tu.get("email", "N/A")
            user_id = tu.get("user_id", "N/A")
            print(f"      {i}. {username} ({email}) - ID: {user_id}")
        if len(tautulli_users) > 5:
            print(f"      ... and {len(tautulli_users) - 5} more")
    
    tautulli_user_count = len(tautulli_users)
    
except Exception as e:
    print(f"   ❌ Failed to fetch Tautulli users: {e}")
    import traceback
    traceback.print_exc()
    tautulli_user_count = 0

# Test 11: Test getting watch history for a user
print("\n1️⃣1️⃣  Testing watch history retrieval...")
try:
    if tautulli_users and len(tautulli_users) > 0:
        test_user_id = tautulli_users[0].get("user_id")
        test_username = tautulli_users[0].get("username", "Unknown")
        
        params = {
            "apikey": TAUTULLI_API_KEY,
            "cmd": "get_history",
            "user_id": test_user_id,
            "length": 1,
            "order_column": "date",
            "order_dir": "desc"
        }
        r = requests.get(f"{TAUTULLI_URL}/api/v2", params=params, timeout=10)
        r.raise_for_status()
        j = r.json()
        
        if j.get("response", {}).get("result") == "success":
            records = j.get("response", {}).get("data", {}).get("data", [])
            if records:
                last_watch = records[0].get("date")
                if last_watch:
                    watch_date = datetime.fromtimestamp(int(last_watch), tz=timezone.utc)
                    print(f"   ✅ Successfully retrieved watch history for user '{test_username}'")
                    print(f"   ✅ Last watch: {watch_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                else:
                    print(f"   ⚠️  User '{test_username}' has watch history but no date field")
            else:
                print(f"   ℹ️  User '{test_username}' has no watch history")
        else:
            print(f"   ❌ Tautulli API error: {j}")
    else:
        print("   ⚠️  No Tautulli users available to test")
        
except Exception as e:
    print(f"   ⚠️  Could not test watch history: {e}")

# Test 12: Compare Plex and Tautulli user counts
print("\n1️⃣2️⃣  Comparing Plex and Tautulli user counts...")
print(f"   Plex users: {plex_user_count}")
print(f"   Tautulli users: {tautulli_user_count}")

if plex_user_count == 0 or tautulli_user_count == 0:
    print("   ⚠️  Warning: One or both APIs returned 0 users")
elif abs(plex_user_count - tautulli_user_count) <= 1:
    print("   ✅ User counts are similar (expected)")
else:
    print(f"   ⚠️  Warning: Significant difference in user counts ({abs(plex_user_count - tautulli_user_count)} difference)")
    print("   This is normal if some users only exist in one system")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

if plex_user_count > 0 and tautulli_user_count > 0:
    print("✅ ALL TESTS PASSED!")
    print("\nBoth Plex and Tautulli APIs are working correctly.")
    print("Your daemon should be able to:")
    print("  ✅ Connect to Plex and list users")
    print("  ✅ Remove users via removeFriend() method")
    print("  ✅ Connect to Tautulli and get watch history")
    print("  ✅ Track user inactivity based on watch times")
else:
    print("⚠️  SOME WARNINGS DETECTED")
    print("Check the test results above for details.")

print("\nNext steps:")
print("  1. Deploy the daemon with DRY_RUN=true to test")
print("  2. Monitor logs: docker logs -f plex-autoprune-daemon")
print("  3. Check health endpoint: curl http://localhost:8080/health")
print("  4. Check metrics: curl http://localhost:8080/metrics")
print("=" * 70)

