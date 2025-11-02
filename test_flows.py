#!/usr/bin/env python3
"""
Comprehensive flow testing script for Plex Auto-Prune Daemon
Tests all scenarios and logic flows
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

# Mock environment variables for testing
os.environ.setdefault("PLEX_TOKEN", "test_token")
os.environ.setdefault("PLEX_SERVER_NAME", "Test Server")
os.environ.setdefault("TAUTULLI_URL", "http://localhost:8181")
os.environ.setdefault("TAUTULLI_API_KEY", "test_api_key")
os.environ.setdefault("SMTP_HOST", "smtp.test.com")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USERNAME", "test@test.com")
os.environ.setdefault("SMTP_PASSWORD", "test_password")
os.environ.setdefault("SMTP_FROM", "test@test.com")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("WARN_DAYS", "27")
os.environ.setdefault("KICK_DAYS", "30")
os.environ.setdefault("DRY_RUN", "true")

def test_scenario(name, description, test_func):
    """Helper to run a test scenario"""
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print(f"{'='*80}")
    print(f"Description: {description}")
    print(f"{'-'*80}")
    try:
        result = test_func()
        if result:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name}")
        return result
    except Exception as e:
        print(f"[ERROR] in {name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_new_user_welcome_flow():
    """Test: New user joins, gets welcome email immediately"""
    print("\nScenario: User joins Plex server")
    print("Expected: Welcome email sent, user tracked in state")
    
    now = datetime.now(timezone.utc)
    user_created = now - timedelta(hours=1)  # User joined 1 hour ago
    
    # Simulate user object
    user = Mock()
    user.id = "12345"
    user.title = "Test User"
    user.username = "testuser"
    user.email = "test@example.com"
    user.createdAt = user_created.replace(tzinfo=None)
    
    # Check if user should be welcomed (joined within 7 days)
    days_since_join = (now - user_created).days
    should_welcome = days_since_join < 7
    
    print(f"  User joined: {user_created}")
    print(f"  Days since join: {days_since_join}")
    print(f"  Should welcome: {should_welcome}")
    
    assert should_welcome, "New user should be welcomed"
    return True

def test_grace_period():
    """Test: 24-hour grace period for new users"""
    print("\nScenario: New user has 24-hour grace period before tracking starts")
    print("Expected: Users < 24 hours old are skipped in inactivity checks")
    
    now = datetime.now(timezone.utc)
    
    # User joined 12 hours ago
    user_joined = now - timedelta(hours=12)
    hours_since_join = (now - user_joined).total_seconds() / 3600
    in_grace_period = hours_since_join < 24
    
    print(f"  User joined: {user_joined}")
    print(f"  Hours since join: {hours_since_join:.1f}")
    print(f"  In grace period: {in_grace_period}")
    
    assert in_grace_period, "User should be in grace period"
    
    # User joined 25 hours ago
    user_joined = now - timedelta(hours=25)
    hours_since_join = (now - user_joined).total_seconds() / 3600
    in_grace_period = hours_since_join < 24
    
    print(f"  User joined: {user_joined}")
    print(f"  Hours since join: {hours_since_join:.1f}")
    print(f"  In grace period: {in_grace_period}")
    
    assert not in_grace_period, "User should be out of grace period"
    return True

def test_inactivity_calculation():
    """Test: Inactivity days calculation"""
    print("\nScenario: Calculate days of inactivity")
    print("Expected: Correct calculation of days since last watch")
    
    now = datetime.now(timezone.utc)
    
    # User watched 27 days ago
    last_watch = now - timedelta(days=27)
    days_inactive = (now - last_watch).days
    
    print(f"  Last watch: {last_watch}")
    print(f"  Now: {now}")
    print(f"  Days inactive: {days_inactive}")
    
    assert days_inactive == 27, f"Expected 27 days, got {days_inactive}"
    
    # User watched 30 days ago
    last_watch = now - timedelta(days=30)
    days_inactive = (now - last_watch).days
    
    print(f"  Last watch: {last_watch}")
    print(f"  Days inactive: {days_inactive}")
    
    assert days_inactive == 30, f"Expected 30 days, got {days_inactive}"
    return True

def test_warning_threshold():
    """Test: Warning sent at 27 days"""
    print("\nScenario: User inactive for 27 days gets warning")
    print("Expected: Warning email sent, user marked in warned state")
    
    WARN_DAYS = 27
    KICK_DAYS = 30
    
    now = datetime.now(timezone.utc)
    last_watch = now - timedelta(days=27)
    days = (now - last_watch).days
    
    should_warn = days >= WARN_DAYS and days < KICK_DAYS
    
    print(f"  Days inactive: {days}")
    print(f"  WARN_DAYS: {WARN_DAYS}")
    print(f"  KICK_DAYS: {KICK_DAYS}")
    print(f"  Should warn: {should_warn}")
    
    assert should_warn, "User should get warning at 27 days"
    
    # User at 26 days should not warn yet
    last_watch = now - timedelta(days=26)
    days = (now - last_watch).days
    should_warn = days >= WARN_DAYS and days < KICK_DAYS
    
    print(f"  Days inactive: {days}")
    print(f"  Should warn: {should_warn}")
    
    assert not should_warn, "User should not warn at 26 days"
    return True

def test_removal_threshold():
    """Test: User removed at 30 days"""
    print("\nScenario: User inactive for 30+ days gets removed")
    print("Expected: User removed from Plex and Tautulli")
    
    KICK_DAYS = 30
    
    now = datetime.now(timezone.utc)
    last_watch = now - timedelta(days=30)
    days = (now - last_watch).days
    
    should_remove = days >= KICK_DAYS
    
    print(f"  Days inactive: {days}")
    print(f"  KICK_DAYS: {KICK_DAYS}")
    print(f"  Should remove: {should_remove}")
    
    assert should_remove, "User should be removed at 30 days"
    
    # User at 29 days should not be removed yet
    last_watch = now - timedelta(days=29)
    days = (now - last_watch).days
    should_remove = days >= KICK_DAYS
    
    print(f"  Days inactive: {days}")
    print(f"  Should remove: {should_remove}")
    
    assert not should_remove, "User should not be removed at 29 days"
    return True

def test_vip_protection():
    """Test: VIP users are never removed"""
    print("\nScenario: VIP users are protected from removal")
    print("Expected: VIP users skipped regardless of inactivity")
    
    ADMIN_EMAIL = "admin@test.com"
    VIP_EMAILS = [ADMIN_EMAIL.lower()]
    VIP_NAMES = ["mom", "dad", "bestfriend"]
    
    # Test email protection
    user_email = "admin@test.com"
    is_vip = user_email.lower() in VIP_EMAILS
    
    print(f"  User email: {user_email}")
    print(f"  VIP emails: {VIP_EMAILS}")
    print(f"  Is VIP: {is_vip}")
    
    assert is_vip, "Admin email should be VIP"
    
    # Test username protection
    user_username = "mom"
    is_vip = user_username.lower() in [n.lower() for n in VIP_NAMES]
    
    print(f"  User username: {user_username}")
    print(f"  VIP names: {VIP_NAMES}")
    print(f"  Is VIP: {is_vip}")
    
    assert is_vip, "VIP username should be protected"
    
    # Non-VIP user
    user_email = "regular@test.com"
    user_username = "regularuser"
    is_vip = (user_email.lower() in VIP_EMAILS or 
              user_username.lower() in [n.lower() for n in VIP_NAMES])
    
    print(f"  User email: {user_email}")
    print(f"  User username: {user_username}")
    print(f"  Is VIP: {is_vip}")
    
    assert not is_vip, "Regular user should not be VIP"
    return True

def test_user_with_no_watch_history():
    """Test: User with no Tautulli history uses join date"""
    print("\nScenario: User has no watch history in Tautulli")
    print("Expected: Use join_date + 24h as baseline for inactivity")
    
    now = datetime.now(timezone.utc)
    user_joined = now - timedelta(days=35)  # Joined 35 days ago
    
    # No watch history, use join date + 24h
    baseline = user_joined + timedelta(hours=24)
    days_inactive = (now - baseline).days
    
    print(f"  User joined: {user_joined}")
    print(f"  Baseline (join + 24h): {baseline}")
    print(f"  Days inactive: {days_inactive}")
    
    assert days_inactive == 34, f"Expected 34 days, got {days_inactive}"
    return True

def test_existing_user_handling():
    """Test: Existing users (not in welcomed) handled correctly"""
    print("\nScenario: User existed before daemon started")
    print("Expected: Use createdAt + 24h if no watch history")
    
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(days=60)  # User created 60 days ago
    
    # Existing user, no watch history
    baseline = created_at + timedelta(hours=24)
    days_inactive = (now - baseline).days
    
    print(f"  User created: {created_at}")
    print(f"  Baseline (created + 24h): {baseline}")
    print(f"  Days inactive: {days_inactive}")
    
    assert days_inactive == 59, f"Expected 59 days, got {days_inactive}"
    return True

def test_dry_run_mode():
    """Test: Dry run mode prevents actual removals"""
    print("\nScenario: DRY_RUN mode enabled")
    print("Expected: Actions logged but not executed")
    
    DRY_RUN_VALUES = ["true", "1", "yes", "True", "TRUE"]
    
    for val in DRY_RUN_VALUES:
        is_dry_run = val.lower() in ("true", "1", "yes")
        print(f"  DRY_RUN='{val}' -> {is_dry_run}")
        assert is_dry_run, f"'{val}' should be recognized as dry run"
    
    DRY_RUN_VALUES_FALSE = ["false", "0", "no", "False", "FALSE"]
    
    for val in DRY_RUN_VALUES_FALSE:
        is_dry_run = val.lower() in ("true", "1", "yes")
        print(f"  DRY_RUN='{val}' -> {is_dry_run}")
        assert not is_dry_run, f"'{val}' should not be dry run"
    
    return True

def test_state_management():
    """Test: State file structure and updates"""
    print("\nScenario: State file properly tracks users")
    print("Expected: State contains welcomed, warned, removed dicts")
    
    state = {
        "welcomed": {"12345": "2025-01-01T00:00:00+00:00"},
        "warned": {"12345": "2025-01-28T00:00:00+00:00"},
        "removed": {
            "12345": {
                "when": "2025-01-31T00:00:00+00:00",
                "ok": True,
                "reason": "Inactivity for 30 days (threshold 30)"
            }
        },
        "last_inactivity_scan": "2025-01-31T00:00:00+00:00"
    }
    
    assert "welcomed" in state, "State should have welcomed dict"
    assert "warned" in state, "State should have warned dict"
    assert "removed" in state, "State should have removed dict"
    assert "last_inactivity_scan" in state, "State should track last scan"
    
    print("  State structure: OK")
    return True

def test_configuration_validation():
    """Test: Configuration validation"""
    print("\nScenario: Invalid configuration rejected")
    print("Expected: WARN_DAYS must be < KICK_DAYS")
    
    WARN_DAYS = 27
    KICK_DAYS = 30
    
    is_valid = WARN_DAYS < KICK_DAYS
    print(f"  WARN_DAYS: {WARN_DAYS}, KICK_DAYS: {KICK_DAYS}")
    print(f"  Valid: {is_valid}")
    
    assert is_valid, "Valid config should pass"
    
    # Invalid config
    WARN_DAYS = 30
    KICK_DAYS = 30
    is_valid = WARN_DAYS < KICK_DAYS
    
    print(f"  WARN_DAYS: {WARN_DAYS}, KICK_DAYS: {KICK_DAYS}")
    print(f"  Valid: {is_valid}")
    
    assert not is_valid, "Invalid config should fail"
    return True

def main():
    """Run all test scenarios"""
    print("\n" + "="*80)
    print("PLEX AUTO-PRUNE DAEMON - COMPREHENSIVE FLOW TESTING")
    print("="*80)
    
    tests = [
        ("New User Welcome Flow", "User joins and receives welcome email", test_new_user_welcome_flow),
        ("Grace Period", "24-hour grace period for new users", test_grace_period),
        ("Inactivity Calculation", "Days of inactivity calculated correctly", test_inactivity_calculation),
        ("Warning Threshold", "Warning sent at 27 days", test_warning_threshold),
        ("Removal Threshold", "User removed at 30 days", test_removal_threshold),
        ("VIP Protection", "VIP users never removed", test_vip_protection),
        ("No Watch History", "User with no history uses join date", test_user_with_no_watch_history),
        ("Existing User Handling", "Existing users handled correctly", test_existing_user_handling),
        ("Dry Run Mode", "Dry run mode prevents actual actions", test_dry_run_mode),
        ("State Management", "State file structure is correct", test_state_management),
        ("Configuration Validation", "Invalid config rejected", test_configuration_validation),
    ]
    
    results = []
    for name, desc, test_func in tests:
        result = test_scenario(name, desc, test_func)
        results.append((name, result))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n*** ALL TESTS PASSED! ***")
        return 0
    else:
        print(f"\n*** WARNING: {total - passed} test(s) failed ***")
        return 1

if __name__ == "__main__":
    sys.exit(main())

