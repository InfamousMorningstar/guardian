# Plex Auto-Prune Daemon - Comprehensive Project Analysis

## Executive Summary

**Project Status:** ✅ **PRODUCTION READY** with minor recommendations

The Plex Auto-Prune Daemon is a well-architected Python daemon that automatically manages Plex Media Server users based on viewing activity. It successfully handles all core flows, has good error handling, and includes safety features like dry-run mode and VIP protection.

**Overall Assessment:** The project is **GOOD** and production-ready, with strong attention to edge cases, error handling, and user safety.

---

## What This Project Does

### Core Functionality

1. **New User Onboarding**
   - Detects new Plex users (within 7 days of joining)
   - Sends welcome emails with server rules and guidelines
   - Tracks users in state file

2. **Inactivity Monitoring**
   - Monitors user viewing activity via Tautulli
   - Calculates days since last watch
   - Enforces 30-day inactivity rule (watch at least once per 30 days)

3. **Warning System**
   - Sends warning emails at 27 days of inactivity
   - Gives users 3 days notice before removal

4. **Automatic Removal**
   - Removes users from Plex after 30 days of inactivity
   - Cleans up Tautulli database (removes watch history)
   - Sends removal notification emails
   - Notifies admin via email and Discord (optional)

5. **VIP Protection**
   - Admin email automatically protected
   - Additional VIP usernames via `VIP_NAMES` environment variable
   - VIP users never removed regardless of activity

6. **Dry Run Mode**
   - Test mode that logs actions without executing them
   - Prevents accidental removals during testing

---

## All Flows Analyzed

### Flow 1: New User Lifecycle

```
1. User joins Plex server
   ↓
2. Daemon checks for new users (every 120 seconds)
   ↓
3. If user joined within 7 days:
   - Send welcome email
   - Send admin notification
   - Send Discord notification
   - Add to welcomed dict in state
   ↓
4. 24-hour grace period begins (no inactivity tracking)
   ↓
5. After 24 hours:
   - Inactivity tracking begins
   - Baseline: join_date + 24 hours
   ↓
6. If user watches something:
   - Timer resets to last watch date
   - User is safe
   ↓
7. If user never watches:
   - Day 27: Warning email sent
   - Day 30: User removed
```

**✅ Status:** Flow works correctly

### Flow 2: Inactivity Warning

```
1. Inactivity check runs (every 1800 seconds / 30 minutes)
   ↓
2. For each user:
   - Get last watch date from Tautulli
   - If no watch history, use join_date + 24h
   - Calculate days inactive
   ↓
3. If days >= 27 AND days < 30 AND not warned yet:
   - Send warning email to user
   - Send admin notification
   - Send Discord notification
   - Mark in warned dict
```

**✅ Status:** Flow works correctly

### Flow 3: User Removal

```
1. Inactivity check runs
   ↓
2. For each user:
   - Calculate days inactive
   - Check VIP protection (skip if VIP)
   ↓
3. If days >= 30 AND not removed yet:
   - Check DRY_RUN mode
   ↓
4a. If DRY_RUN=true:
   - Log what would happen
   - Don't actually remove
   ↓
4b. If DRY_RUN=false:
   - Remove user from Plex (removeFriend or unshare)
   - Delete user from Tautulli database
   - Send removal email to user
   - Send admin notification
   - Send Discord notification
   - Mark in removed dict
```

**✅ Status:** Flow works correctly

### Flow 4: State Management

```
1. State file: /app/state/state.json
   Structure:
   {
     "welcomed": { "user_id": "timestamp" },
     "warned": { "user_id": "timestamp" },
     "removed": { "user_id": { "when": "timestamp", "ok": bool, "reason": "string" } },
     "last_inactivity_scan": "timestamp"
   }
   ↓
2. State is reloaded each iteration (allows cross-thread updates)
   ↓
3. State is saved atomically (write to .tmp, then replace)
   ↓
4. Failed removals are tracked and can be retried
```

**✅ Status:** Flow works correctly

### Flow 5: Error Recovery

```
1. API calls have 3-retry logic:
   - Attempt 1: Try API call
   - If fails: Wait 5s, retry
   - If fails: Wait 5s, retry
   - If fails: Skip this tick, continue next iteration
   ↓
2. Email sending errors are caught and logged
   - User actions continue even if emails fail
   ↓
3. Failed removals are tracked in state
   - Can be automatically retried if user still exists
   ↓
4. Thread monitoring:
   - Main thread monitors worker threads
   - If thread dies: Log fatal error and exit
```

**✅ Status:** Flow works correctly

---

## Test Results

All 11 test scenarios passed:

1. ✅ New User Welcome Flow
2. ✅ Grace Period (24 hours)
3. ✅ Inactivity Calculation
4. ✅ Warning Threshold (27 days)
5. ✅ Removal Threshold (30 days)
6. ✅ VIP Protection
7. ✅ No Watch History Handling
8. ✅ Existing User Handling
9. ✅ Dry Run Mode
10. ✅ State Management
11. ✅ Configuration Validation

---

## Code Quality Assessment

### Strengths ✅

1. **Excellent Error Handling**
   - All API calls wrapped in try/except
   - 3-retry logic for transient failures
   - Graceful degradation (skip tick on failure, retry next iteration)

2. **Safety Features**
   - Dry run mode prevents accidental actions
   - VIP protection for important users
   - 24-hour grace period for new users
   - Configuration validation (WARN_DAYS < KICK_DAYS)

3. **State Management**
   - Atomic writes (write to .tmp, then replace)
   - State reloaded each iteration (thread-safe)
   - Tracks failed removals for retry

4. **Robust User Matching**
   - Matches Tautulli users to Plex users by email and username
   - Handles data mismatches gracefully
   - Two-step verification for departed users

5. **Comprehensive Logging**
   - All actions logged with timestamps
   - Clear prefixes ([join], [inactive], etc.)
   - Error details with stack traces

6. **Thread Safety**
   - State reloaded each iteration
   - No shared mutable state between threads
   - Thread monitoring with automatic exit on failure

7. **Email Templates**
   - Professional HTML emails
   - Dark mode support
   - Mobile-responsive design
   - All actions logged for audit trail

### Potential Issues & Recommendations ⚠️

#### 1. **State File Race Condition (Minor)**

**Issue:** Two threads could potentially read state simultaneously, modify it, and overwrite each other's changes.

**Current Mitigation:** State is reloaded each iteration, which minimizes the window. However, if both threads modify state in the same second, one change could be lost.

**Recommendation:** 
- Option A: Use file locking (fcntl on Linux, msvcrt on Windows)
- Option B: Accept minor risk (current approach is acceptable for this use case)
- **Priority:** Low (rare edge case, state reloaded frequently)

**Code Location:** `main.py` lines 897, 1020, 1004, 1219

#### 2. **Missing `PLEX_SERVER_NAME` Validation (Minor)**

**Issue:** If `PLEX_SERVER_NAME` is empty, `get_plex_server_resource()` will fail. However, the function is only called in `slow_inactivity_watcher()`, but `server` variable is never used.

**Recommendation:**
- Remove unused `server` variable from `slow_inactivity_watcher()` (line 1013)
- Or validate `PLEX_SERVER_NAME` is required only if actually needed
- **Priority:** Low (code works but has unused variable)

#### 3. **Email Failure Handling (Minor)**

**Issue:** If email sending fails, the action (welcome/warn/remove) continues but user/admin doesn't get notified.

**Current Behavior:** Errors are caught and logged, action continues.

**Recommendation:** 
- Current behavior is acceptable (don't block core functionality for email failures)
- Consider adding retry queue for failed emails
- **Priority:** Low (email failures don't break core functionality)

#### 4. **Discord Webhook Failure (Minor)**

**Issue:** Discord notifications fail silently if webhook is invalid/missing.

**Current Behavior:** Errors are caught and logged, continues silently.

**Recommendation:**
- Current behavior is acceptable (Discord is optional notification)
- **Priority:** Low

#### 5. **Tautulli User Matching (Minor)**

**Issue:** If a Tautulli user's email/username changes, they won't be matched and will be skipped.

**Current Behavior:** Warning logged, user skipped.

**Recommendation:**
- Consider matching by Tautulli user_id if it matches Plex user_id
- Or document this limitation
- **Priority:** Low (rare edge case)

#### 6. **Hardcoded Email Links (Minor)**

**Issue:** Email templates have hardcoded links to specific domains (ahmxd.net, etc.)

**Recommendation:**
- Make links configurable via environment variables
- **Priority:** Low (project-specific branding)

#### 7. **No Health Check Endpoint (Nice-to-Have)**

**Recommendation:**
- Add HTTP health check endpoint (simple HTTP server on port 8080)
- Allows monitoring tools to check daemon status
- **Priority:** Low (nice-to-have feature)

---

## Security Assessment

### Security Strengths ✅

1. **No Hardcoded Secrets**
   - All credentials via environment variables
   - Proper Docker patterns

2. **Input Validation**
   - Configuration validated at startup
   - Email addresses validated via SMTP send attempt

3. **Error Messages**
   - Error messages don't leak sensitive data
   - Stack traces only in logs (not exposed)

4. **VIP Protection**
   - Admin email automatically protected
   - Additional VIP list configurable

### Security Recommendations 🔒

1. **State File Permissions**
   - Ensure state file has restricted permissions (600)
   - Contains user tracking data

2. **Environment Variable Validation**
   - Consider validating email format
   - Validate URL format for TAUTULLI_URL

**Priority:** Low (current security is acceptable)

---

## Performance Assessment

### Performance Strengths ✅

1. **Efficient API Calls**
   - Caches user lists per tick
   - Only queries when needed

2. **Configurable Intervals**
   - New user check: 120 seconds (default)
   - Inactivity check: 1800 seconds (30 minutes, default)

3. **Non-Blocking Operations**
   - Email sending doesn't block main loop
   - API failures don't crash daemon

### Performance Considerations ⚡

1. **State File Size**
   - If thousands of users removed, state file could grow large
   - Consider pruning old removed entries (>90 days)

**Priority:** Low (only becomes issue with very large user base)

---

## Testing Assessment

### Test Coverage ✅

- ✅ All core flows tested
- ✅ Edge cases covered
- ✅ Configuration validation tested
- ✅ State management tested

### Missing Tests (Nice-to-Have)

- Integration tests with actual Plex API (would require test account)
- Email delivery tests
- Discord webhook tests

**Priority:** Low (unit tests cover logic, integration tests are nice-to-have)

---

## Documentation Assessment

### Documentation Strengths ✅

1. **Comprehensive README**
   - Clear explanation of functionality
   - Setup instructions
   - Configuration guide
   - Troubleshooting section

2. **API Verification Guide**
   - Explains Plex API usage
   - Verification steps
   - Troubleshooting tips

3. **Code Comments**
   - Functions documented
   - Complex logic explained

### Documentation Recommendations 📝

1. **Add Architecture Diagram**
   - Visual representation of flows
   - Component interactions

**Priority:** Low (existing docs are good)

---

## Deployment Assessment

### Deployment Strengths ✅

1. **Docker Support**
   - Dockerfile provided
   - docker-compose.yml for local dev
   - portainer-stack.yml for production

2. **Environment Variables**
   - All configuration via env vars
   - No .env file required (proper Docker pattern)

3. **State Persistence**
   - State directory mounted as volume
   - Survives container restarts

### Deployment Recommendations 🚀

1. **Health Check**
   - Add health check endpoint
   - Allows orchestration tools to monitor

2. **Metrics/Monitoring**
   - Consider adding Prometheus metrics
   - Track: users checked, warnings sent, removals, errors

**Priority:** Low (current deployment is production-ready)

---

## Final Verdict

### Overall Rating: **8.5/10** ⭐⭐⭐⭐

**Is this good?** ✅ **YES**

**Why it's good:**
1. ✅ All flows work correctly (tested)
2. ✅ Excellent error handling
3. ✅ Safety features (dry run, VIP protection)
4. ✅ Comprehensive logging
5. ✅ Production-ready code quality
6. ✅ Good documentation
7. ✅ Proper Docker patterns

**Minor improvements recommended:**
1. Fix unused `server` variable (line 1013)
2. Consider file locking for state file (optional)
3. Add health check endpoint (nice-to-have)

**Conclusion:** This is a **well-built, production-ready project** with excellent attention to edge cases, error handling, and user safety. The minor issues identified are not blockers and the code demonstrates good software engineering practices.

---

## Recommendations Priority

### High Priority
- None (all critical issues addressed)

### Medium Priority
- Remove unused `server` variable (line 1013)
- Document Tautulli matching limitations

### Low Priority
- File locking for state file
- Health check endpoint
- Metrics/monitoring
- Prune old removed entries from state

---

## Test Execution Summary

```
11/11 tests passed

✅ New User Welcome Flow
✅ Grace Period
✅ Inactivity Calculation
✅ Warning Threshold
✅ Removal Threshold
✅ VIP Protection
✅ No Watch History
✅ Existing User Handling
✅ Dry Run Mode
✅ State Management
✅ Configuration Validation
```

**All scenarios tested and working correctly!**

---

Generated: 2025-11-02
Analysis Tool: Comprehensive Flow Testing Script + Code Review

