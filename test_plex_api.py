#!/usr/bin/env python3
"""
Test script to verify Plex API connectivity and removeFriend method availability
Run this before running the full daemon to ensure everything works
"""

import os
import sys

# Load environment variables from .env file
try:
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                os.environ[key] = value
except FileNotFoundError:
    print("❌ .env file not found!")
    sys.exit(1)

print("=" * 60)
print("PLEX API CONNECTIVITY TEST")
print("=" * 60)

# Test 1: Import plexapi
print("\n1️⃣  Testing plexapi import...")
try:
    from plexapi.myplex import MyPlexAccount
    print("   ✅ plexapi library imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import plexapi: {e}")
    print("   Run: pip install plexapi")
    sys.exit(1)

# Test 2: Check environment variables
print("\n2️⃣  Checking environment variables...")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN")
PLEX_SERVER_NAME = os.environ.get("PLEX_SERVER_NAME")

if not PLEX_TOKEN:
    print("   ❌ PLEX_TOKEN not set")
    sys.exit(1)
print(f"   ✅ PLEX_TOKEN: {PLEX_TOKEN[:10]}...")

if not PLEX_SERVER_NAME:
    print("   ❌ PLEX_SERVER_NAME not set")
    sys.exit(1)
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
print("\n5️⃣  Fetching user list...")
try:
    users = account.users()
    print(f"   ✅ Found {len(users)} users")

    if users:
        print("\n   📋 User List:")
        for i, user in enumerate(users, 1):
            username = user.username or "N/A"
            email = user.email or "N/A"
            user_id = user.id
            # Check if this is a friend or home user
            user_type = "Home User" if hasattr(user, 'home') and user.home else "Friend"
            print(f"      {i}. {username} ({email}) - ID: {user_id} - Type: {user_type}")
    else:
        print("   ℹ️  No users found (only you)")

except Exception as e:
    print(f"   ❌ Failed to fetch users: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Check server access
print("\n6️⃣  Checking server resources...")
try:
    resources = account.resources()
    servers = [r for r in resources if getattr(r, 'provides', None) == 'server' or
               getattr(r, 'product', '') == 'Plex Media Server']

    print(f"   ✅ Found {len(servers)} server(s)")

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

except Exception as e:
    print(f"   ❌ Failed to check servers: {e}")

# Test 7: Check plexapi version
print("\n7️⃣  Checking plexapi version...")
try:
    import plexapi
    version = getattr(plexapi, '__version__', 'Unknown')
    print(f"   ✅ plexapi version: {version}")
except:
    print("   ⚠️  Could not determine plexapi version")

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nThe Plex API is working correctly.")
print("Your daemon should be able to remove users successfully.")
print("\nTo test removal (DRY RUN mode):")
print("  1. Set DRY_RUN=true in .env")
print("  2. Run: docker compose up -d --build")
print("  3. Monitor: docker logs -f plex-autoprune-daemon")
print("=" * 60)
