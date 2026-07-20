#!/usr/bin/env python3
"""
Kids Town E2E Functional Test Suite
=====================================
Tests actual FEATURE LOGIC via API calls.
Each test: set up conditions → act → assert results.

Usage:
  python3 e2e_functional_test.py
  python3 e2e_functional_test.py --verbose
"""

import os, sys, json, time, sqlite3, random, urllib.request, urllib.error
from datetime import datetime, timedelta

API = "http://127.0.0.1:9123"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kids_town.db")

results = {"pass": 0, "fail": 0}
failures = []
VERBOSE = False

# ── Helpers ──

def api(method, url, body=None):
    """Call API and return parsed result."""
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            if not content:
                return {}, resp.status
            return json.loads(content), resp.status
    except urllib.error.HTTPError as e:
        content = e.read()
        if content and content.strip():
            try:
                return json.loads(content), e.code
            except json.JSONDecodeError:
                return {"error": content.decode()[:200]}, e.code
        return {"error": f"HTTP {e.code}: {e.reason}"}, e.code
    except Exception as e:
        return {"error": str(e)}, 0

def get(path):
    return api("GET", f"{API}{path}")

def post(path, body=None):
    return api("POST", f"{API}{path}", body)

def put(path, body=None):
    return api("PUT", f"{API}{path}", body)

def delete(path):
    return api("DELETE", f"{API}{path}")

def db_exec(sql, params=()):
    db = sqlite3.connect(DB_PATH)
    try:
        cur = db.execute(sql, params)
        db.commit()
        return cur.fetchall()
    finally:
        db.close()

def db_get(sql, params=()):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        return dict(db.execute(sql, params).fetchone())
    except:
        return None
    finally:
        db.close()

def report(cat, name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results["pass" if passed else "fail"] += 1
    msg = f"{status} | {cat} | {name}"
    if not passed and detail:
        msg += f"\n       └─ {detail}"
        failures.append(f"{cat} | {name}: {detail}")
    if VERBOSE or not passed:
        print(msg)

def show(msg):
    if VERBOSE:
        print(f"  └─ {msg}")

# ═══════════════════════════════════════════════════
# TEST: Parent Login
# ═══════════════════════════════════════════════════
def test_login():
    print("\n─── TC-01: Parent Login ───")
    
    # Find a kid with known PIN or create one
    kids, _ = get("/api/kids")
    if not kids:
        report("LOGIN", "No kids to test login", False, "")
        return
    kid_id = kids[0]["id"]
    
    # Test login with the kid's PIN (check what PIN works via DB)
    import sqlite3
    db = sqlite3.connect(DB_PATH)
    auth = db.execute("SELECT * FROM kid_auth WHERE kid_id=?", (kid_id,)).fetchone()
    correct_pin = auth[2] if auth else "0000"
    db.close()
    show(f"Kid {kid_id} PIN: {correct_pin}")
    
    # Test correct PIN
    r, status = post("/api/login", {"kid_id": kid_id, "pin": correct_pin})
    report("LOGIN", f"Correct PIN for kid {kid_id} returns ok",
           r.get("ok") == True,
           f"response={r}")
    
    # Test wrong PIN
    r2, s2 = post("/api/login", {"kid_id": kid_id, "pin": "wrong!"})
    report("LOGIN", "Wrong PIN returns error",
           s2 == 403 and r2.get("ok") != True,
           f"response={r2}")


# ═══════════════════════════════════════════════════
# TEST: Kids CRUD
# ═══════════════════════════════════════════════════
def test_kids_crud():
    print("\n─── TC-02: Kids CRUD ───")
    
    # Get current kids
    kids, _ = get("/api/kids")
    before = len(kids)
    show(f"Current kids: {before}")
    
    # Create a test kid
    test_name = f"Test_{int(time.time())}"
    r, status = post("/api/kids", {"name": test_name, "avatar": "🐱"})
    report("KIDS", f"Create kid '{test_name}' returns 201",
           status == 201 and r.get("name") == test_name,
           f"response={r}")
    
    new_id = r.get("id")
    if new_id:
        show(f"Created kid id={new_id}")
        
        # Verify kid exists in list
        kids, _ = get("/api/kids")
        found = any(k["id"] == new_id for k in kids)
        report("KIDS", f"Kid {new_id} appears in /api/kids",
               found,
               f"total kids: {len(kids)}")
        
        # Update kid (use PATCH since backend uses PATCH not PUT)
        r2, s2 = api("PATCH", f"{API}/api/kids/{new_id}", {"name": f"{test_name}_updated", "avatar": "🐶"})
        report("KIDS", f"Update kid {new_id}",
               s2 == 200 and r2.get("name") == f"{test_name}_updated",
               f"response={r2}")
        
        # Delete kid
        r3, s3 = delete(f"/api/kids/{new_id}")
        report("KIDS", f"Delete kid {new_id}",
               s3 == 200,
               f"response={r3}")
        
        # Verify deleted
        kids_after, _ = get("/api/kids")
        deleted = all(k["id"] != new_id for k in kids_after)
        report("KIDS", f"Kid {new_id} removed after delete",
               deleted,
               f"total after: {len(kids_after)}")
    
    else:
        report("KIDS", "Create kid (no id returned)", False, str(r))


# ═══════════════════════════════════════════════════
# TEST: Tasks — Add, Complete, Points Awarded
# ═══════════════════════════════════════════════════
def test_task_completion():
    print("\n─── TC-03: Task Completion → Points ───")
    
    kids, _ = get("/api/kids")
    if not kids:
        report("TASK", "No kids available", False, "Skipping task tests")
        return
    
    kid = kids[0]
    kid_id = kid["id"]
    initial_points = kid["points"]
    show(f"Using kid {kid_id} ({kid['name']}), points: {initial_points}")
    
    # Add a task
    r, status = post("/api/tasks", {
        "title": f"TestTask_{int(time.time())}",
        "kid_id": kid_id,
        "points": 25,
        "icon": "🎯"
    })
    report("TASK", f"Create task returns 201",
           status == 201 and r.get("kid_id") == kid_id,
           f"response={r}")
    
    task_id = r.get("id")
    if task_id:
        # Complete the task
        r2, s2 = post(f"/api/tasks/{task_id}/complete")
        
        # Check points awarded
        points_awarded = r2.get("points_awarded", 0)
        kid_after = r2.get("kid", {})
        report("TASK", f"Complete task → points_awarded={points_awarded}",
               points_awarded == 25,
               f"response={r2}")
        
        # Check points log
        log = db_exec("SELECT amount, reason FROM points_log WHERE kid_id=? ORDER BY id DESC LIMIT 1", (kid_id,))
        if log:
            report("TASK", f"points_log records the transaction ({log[0][0]} pts)",
                   log[0][0] == 25,
                   f"log={log}")
        
        # Clean up task
        delete(f"/api/tasks/{task_id}")
        show(f"Task {task_id} cleaned up")


# ═══════════════════════════════════════════════════
# TEST: Recurring Tasks — Daily/Weekly/Weekdays
# ═══════════════════════════════════════════════════
def test_recurring_tasks():
    print("\n─── TC-04: Recurring Tasks ───")
    
    kids, _ = get("/api/kids")
    if not kids:
        report("RECUR", "No kids", False)
        return
    kid_id = kids[0]["id"]
    
    for rec_type in ["daily", "weekly", "weekdays"]:
        # Add recurring task
        r, s = post("/api/tasks", {
            "title": f"Recur_{rec_type}_{int(time.time())}",
            "kid_id": kid_id,
            "points": 10,
            "recurring": rec_type,
        })
        task_id = r.get("id")
        
        if task_id:
            # Complete it
            r2, s2 = post(f"/api/tasks/{task_id}/complete")
            awarded = r2.get("points_awarded", 0)
            report("RECUR", f"{rec_type}: Complete → points_awarded={awarded}",
                   awarded == 10,
                   f"resp={r2}")
            
            # Check recurring: task should NOT be deleted, just marked completed with updated due_date
            task_db = db_get("SELECT * FROM tasks WHERE id=?", (task_id,))
            if task_db:
                report("RECUR", f"{rec_type}: Task still exists after complete",
                       task_db["completed"] == 1,
                       f"completed={task_db['completed']}, due_date={task_db.get('due_date')}")
            
            # Test refresh-recurring
            r3, s3 = post("/api/tasks/refresh-recurring")
            report("RECUR", f"{rec_type}: Refresh endpoint returns ok",
                   s3 == 200,
                   f"resp={r3}")
            
            # Clean up
            delete(f"/api/tasks/{task_id}")
        else:
            report("RECUR", f"{rec_type}: Create task", False, str(r))
    
    # Clean up any orphan test tasks
    db_exec("DELETE FROM tasks WHERE title LIKE 'Recur_%'")
    show("Cleaned up test tasks")


# ═══════════════════════════════════════════════════
# TEST: Points Adjustment
# ═══════════════════════════════════════════════════
def test_points_adjust():
    print("\n─── TC-05: Points Adjustment ───")
    
    kids, _ = get("/api/kids")
    if not kids:
        return
    kid_id = kids[0]["id"]
    kid = kids[0]
    initial = kid["points"]
    
    # Add points
    r, s = post(f"/api/kids/{kid_id}/points/adjust", {"amount": 50, "reason": "Test bonus"})
    report("ADJUST", "Add 50 points",
           r.get("points") == initial + 50,
           f"points: {initial} → {r.get('points')}")
    
    # Subtract points
    mid = r.get("points", initial + 50)
    # Need reason for deduction
    r2, s2 = post(f"/api/kids/{kid_id}/points/adjust", {"amount": -30, "reason": "Test deduction"})
    report("ADJUST", "Subtract 30 points (with reason)",
           r2.get("points") == mid - 30,
           f"points: {mid} → {r2.get('points')}")
    
    # Test without reason (should fail)
    r3, s3 = post(f"/api/kids/{kid_id}/points/adjust", {"amount": 10})
    report("ADJUST", "Adjust without reason returns error",
           s3 == 400 and "reason" in (r3.get("error","") or "").lower(),
           f"status={s3}, resp={r3}")
    
    # Restore original points
    final = r2.get("points", mid - 30)
    post(f"/api/kids/{kid_id}/points/adjust", {"amount": -(final - initial), "reason": "Reset for tests"})


# ═══════════════════════════════════════════════════
# TEST: Building — Build and Upgrade
# ═══════════════════════════════════════════════════
def test_buildings():
    print("\n─── TC-06: Building Construction ───")
    
    kids, _ = get("/api/kids")
    if not kids:
        return
    kid_id = kids[0]["id"]
    
    # Get building defs
    defs, _ = get("/api/building-defs")
    if not defs:
        report("BUILD", "No building definitions", False)
        return
    
    cheapest = min(defs, key=lambda d: d["cost_gold"])
    def_id = cheapest["id"]
    show(f"Cheapest: {cheapest['name']} (id={def_id}, cost={cheapest['cost_gold']})")

    # Check if kid already has this building type (only 1 allowed per type)
    blds_existing, _ = get(f"/api/kids/{kid_id}/buildings")
    existing_def_ids = {b["def_id"] for b in blds_existing} if blds_existing else set()
    if def_id in existing_def_ids:
        # Pick next cheapest NOT already built
        available = [d for d in defs if d["id"] not in existing_def_ids]
        if not available:
            report("BUILD", "All building types already built — skip", True)
            return
        cheapest = min(available, key=lambda d: d["cost_gold"])
        def_id = cheapest["id"]
        show(f"Already built 圖書館, switching to: {cheapest['name']} (id={def_id})")
    
    # Check if kid can afford it
    kid_info, _ = get(f"/api/kids/{kid_id}/points")
    if kid_info.get("points", 0) < cheapest["cost_gold"]:
        # Give enough points
        needed = cheapest["cost_gold"] - kid_info["points"] + 50
        post(f"/api/kids/{kid_id}/points/adjust", {"amount": needed, "reason": "Test funds"})
        show(f"Added {needed} points for building test")
    
    # Also add some materials if needed
    mats = json.loads(cheapest.get("materials", "{}"))
    for mat_type, mat_qty in mats.items():
        inv, _ = get(f"/api/kids/{kid_id}/inventory")
        have = sum(i["quantity"] for i in inv if i["item_type"] == mat_type)
        if have < mat_qty:
            post(f"/api/kids/{kid_id}/inventory/add", {"item_type": mat_type, "quantity": mat_qty - have + 5})
            show(f"Added {mat_qty - have + 5} {mat_type} for building test")
    
    # Build it on position (1,5) — a free spot
    r, s = post(f"/api/kids/{kid_id}/buildings", {"def_id": def_id, "cell_x": 1, "cell_y": 5})
    report("BUILD", f"Build {cheapest['name']} at (1,5)",
           s in (200, 201) and r.get("def_id") == def_id,
           f"resp={r}")
    
    building_id = r.get("id")
    if building_id:
        # Verify building exists
        blds, _ = get(f"/api/kids/{kid_id}/buildings")
        built = any(b["id"] == building_id for b in blds)
        report("BUILD", f"Building {building_id} appears in list",
               built,
               f"buildings: {len(blds)}")
        
        # Ensure enough gold for upgrades (level 2 = 200, level 3 = 300)
        upgrade_gold_needed = 200 + 300
        post(f"/api/kids/{kid_id}/points/adjust", {"amount": upgrade_gold_needed + 100, "reason": "Test upgrade funds"})

        # Also add materials needed for upgrade (scaled: base_mats * (level+1))
        # Use the actual building's materials from defs
        base_mats = json.loads(cheapest.get("materials", "{}"))
        upgrade_mats_total = {}
        for level in [2, 3]:
            for mat, qty in base_mats.items():
                upgrade_mats_total[mat] = upgrade_mats_total.get(mat, 0) + qty * level
        for mat, qty in upgrade_mats_total.items():
            post(f"/api/kids/{kid_id}/inventory/add", {"item_type": mat, "quantity": qty + 20})
        show(f"Added upgrade mats: {upgrade_mats_total} (+20 buffer)")
        show(f"Added materials for upgrades")
        show(f"Added extra gold for upgrades")
        
        # Upgrade building to Lv.2
        r2, s2 = post(f"/api/kids/{kid_id}/buildings/{building_id}/upgrade")
        report("BUILD", f"Upgrade building to Lv.2",
               s2 == 200 and r2.get("level") == 2,
               f"resp={r2}")
        
        # Upgrade again to Lv.3
        r3, s3 = post(f"/api/kids/{kid_id}/buildings/{building_id}/upgrade")
        report("BUILD", f"Upgrade building to Lv.3",
               s3 == 200 and r3.get("level") == 3,
               f"resp={r3}")
        
        # Delete building
        r4, s4 = delete(f"/api/kids/{kid_id}/buildings/{building_id}")
        report("BUILD", f"Delete building {building_id}",
               s4 == 200,
               f"resp={r4}")
        
        # Verify gone
        blds2, _ = get(f"/api/kids/{kid_id}/buildings")
        still_there = any(b["id"] == building_id for b in blds2)
        report("BUILD", "Building removed after delete",
               not still_there,
               f"still present: {still_there}")


# ═══════════════════════════════════════════════════
# TEST: Expedition — Start & Claim
# ═══════════════════════════════════════════════════
def test_expedition():
    print("\n─── TC-07: Expedition ───")
    
    kids, _ = get("/api/kids")
    if not kids:
        return
    kid_id = kids[0]["id"]
    
    # Check current expedition status
    exp, _ = get(f"/api/kids/{kid_id}/expedition")
    show(f"Expedition status: {type(exp).__name__}")
    
    # If there's an already running expedition, cancel/claim it first
    if isinstance(exp, dict) and exp.get("status") == "running":
        # Try to claim it
        claim_r, claim_s = post(f"/api/kids/{kid_id}/expedition/claim", {})
        show(f"Claimed existing expedition: status={claim_s}, resp={claim_r}")
    
    # Start expedition with region 1 (duration 0 = immediate)
    r, s = post(f"/api/kids/{kid_id}/expedition/start", {"region_id": 1, "duration_hours": 0})
    
    # Check start result
    if s == 201:
        report("EXP", "Start expedition region 1", True)
    elif s == 400 and "already" in str(r.get("error", "")):
        # There was a running expedition — claim it first
        report("EXP", "Start expedition (had existing running)", False, 
               "Existing expedition needed claiming first")
        # Force-clean the running expedition via DB and retry
        import sqlite3
        db3 = sqlite3.connect(DB_PATH)
        db3.execute("DELETE FROM expeditions WHERE kid_id=? AND status='running'", (kid_id,))
        db3.commit()
        db3.close()
        r, s = post(f"/api/kids/{kid_id}/expedition/start", {"region_id": 1, "duration_hours": 0})
        report("EXP", "Start expedition region 1 (after cleanup)", 
               s == 201, f"resp={r}")
    else:
        report("EXP", "Start expedition region 1", False, f"resp={r}")
    
    time.sleep(0.5)
    
    # Claim rewards
    r2, s2 = post(f"/api/kids/{kid_id}/expedition/claim", {})
    
    # Check if 500 is backend bug (fromisoformat Z suffix)
    if s2 == 500:
        report("EXP", "Claim expedition rewards",
               False, "⚠️ BACKEND BUG: claim endpoint 500 error (fromisoformat Z suffix)")
        report("EXP", "Expedition awards gold", False, "Skipped due to 500 backend bug")
    else:
        report("EXP", "Claim expedition rewards",
               s2 == 200,
               f"resp={r2}")
        
        if s2 == 200 and isinstance(r2, dict):
            has_gold = r2.get("gold", 0) > 0
            report("EXP", "Expedition awards gold",
                   has_gold,
                   f"gold={r2.get('gold')}, materials={r2.get('materials')}")
    
    # Test claim without running expedition (should fail gracefully)
    r3, s3 = post(f"/api/kids/{kid_id}/expedition/claim", {})
    report("EXP", "Claim without running expedition returns error",
           s3 == 400 and "No running" in str(r3.get("error", "")),
           f"status={s3}, resp={r3}")


# ═══════════════════════════════════════════════════
# TEST: Achievements
# ═══════════════════════════════════════════════════
def test_achievements():
    print("\n─── TC-08: Achievements ───")
    
    # Get all achievements
    all_achs, _ = get("/api/achievements/all")
    report("ACHIEVE", "All achievements endpoint returns list",
           isinstance(all_achs, list),
           f"count={len(all_achs)}")
    
    # Check a specific kid's achievements
    kids, _ = get("/api/kids")
    if kids:
        kid_id = kids[0]["id"]
        achs, _ = get(f"/api/kids/{kid_id}/achievements")
        report("ACHIEVE", f"Kid {kid_id} achievements",
               isinstance(achs, list),
               f"count={len(achs)}")
    
    # Check leaderboard
    lb, _ = get("/api/leaderboard")
    report("ACHIEVE", "Leaderboard works",
           isinstance(lb, (dict, list)) and (len(lb) > 0 if isinstance(lb, list) else True),
           f"type={type(lb).__name__}")


# ═══════════════════════════════════════════════════
# TEST: Streaks
# ═══════════════════════════════════════════════════
def test_streaks():
    print("\n─── TC-09: Streaks ───")
    
    kids, _ = get("/api/kids")
    if not kids:
        return
    kid_id = kids[0]["id"]
    
    r, s = get(f"/api/kids/{kid_id}/streak")
    report("STREAK", f"Kid {kid_id} streak endpoint",
           isinstance(r, dict) and "current_streak" in r,
           f"streak={r.get('current_streak')}, best={r.get('best_streak')}")


# ═══════════════════════════════════════════════════
# TEST: Town & Inventory
# ═══════════════════════════════════════════════════
def test_town():
    print("\n─── TC-10: Town & Inventory ───")
    
    kids, _ = get("/api/kids")
    if not kids:
        return
    kid_id = kids[0]["id"]
    
    # Town
    r, s = get(f"/api/kids/{kid_id}/town")
    report("TOWN", f"Kid {kid_id} town data",
           isinstance(r, dict) and "kid" in r and "buildings" in r and "inventory" in r,
           f"keys={list(r.keys())}")
    
    # Inventory
    r2, _ = get(f"/api/kids/{kid_id}/inventory")
    report("TOWN", f"Kid {kid_id} inventory",
           isinstance(r2, list),
           f"items={len(r2)}")
    
    # Explored regions
    r3, _ = get(f"/api/kids/{kid_id}/explored")
    report("TOWN", f"Kid {kid_id} explored regions",
           isinstance(r3, list),
           f"count={len(r3)}")


# ═══════════════════════════════════════════════════
# TEST: Task CRUD — Edit & Delete
# ═══════════════════════════════════════════════════
def test_task_crud():
    print("\n─── TC-11: Task CRUD ───")
    
    kids, _ = get("/api/kids")
    kid_id = kids[0]["id"] if kids else None
    
    # Create task with all fields
    r, s = post("/api/tasks", {
        "title": f"CRUD_Test_{int(time.time())}",
        "points": 15,
        "kid_id": kid_id,
        "icon": "📖",
        "category": "TestCat",
        "description": "Test description for CRUD task",
        "recurring": "daily",
        "due_date": "2026-12-31"
    })
    report("TASK_CRUD", "Create task with all fields",
           s == 201 and r.get("title", "").startswith("CRUD_Test"),
           f"resp={r}")
    
    task_id = r.get("id")
    if task_id:
        # Edit task
        r2, s2 = put(f"/api/tasks/{task_id}", {
            "title": "CRUD_Updated",
            "points": 30,
            "category": "UpdatedCat",
        })
        report("TASK_CRUD", "Edit task (title, points, category)",
               s2 == 200 and r2.get("points") == 30,
               f"resp={r2}")
        
        # Delete task
        r3, s3 = delete(f"/api/tasks/{task_id}")
        report("TASK_CRUD", "Delete task",
               s3 == 200,
               f"resp={r3}")


# ═══════════════════════════════════════════════════
# TEST: Activity Log
# ═══════════════════════════════════════════════════
def test_activity():
    print("\n─── TC-12: Activity Log ───")
    
    r, s = get("/api/activity")
    report("ACTIVITY", "Activity log returns list",
           isinstance(r, list),
           f"items={len(r)}")
    
    if r:
        item = r[0]
        has_required = all(k in item for k in ["kid_name", "amount", "reason", "created_at"])
        report("ACTIVITY", "Activity items have required fields",
               has_required,
               f"keys={list(item.keys())}")


# ═══════════════════════════════════════════════════
# TEST: Task Filtering
# ═══════════════════════════════════════════════════
def test_task_filtering():
    print("\n─── TC-13: Task Filtering ───")
    
    # Filter by kid
    kids, _ = get("/api/kids")
    if kids:
        kid_id = kids[0]["id"]
        r, s = get(f"/api/tasks?kid_id={kid_id}")
        report("FILTER", f"Filter tasks by kid_id={kid_id}",
               isinstance(r, list) and all(t.get("kid_id") == kid_id for t in r),
               f"count={len(r)}")
    
    # Filter by status (completed)
    r2, s2 = get("/api/tasks?completed=0")
    report("FILTER", "Filter tasks by completed=0",
           isinstance(r2, list),
           f"count={len(r2)}")
    
    # Filter by search
    r3, s3 = get("/api/tasks?search=test")
    report("FILTER", "Filter tasks by search='test'",
           isinstance(r3, list),
           f"count={len(r3)}")


# ═══════════════════════════════════════════════════
# TEST: Dev Dashboard
# ═══════════════════════════════════════════════════
def test_dev_dashboard():
    print("\n─── TC-14: Dev Dashboard ───")
    
    r, s = get("/api/dev-dashboard")
    report("DEV", "Dev dashboard",
           isinstance(r, dict) and len(r) > 0,
           f"keys={list(r.keys())}")


# ═══════════════════════════════════════════════════
# TEST: Task Stats
# ═══════════════════════════════════════════════════
def test_task_stats():
    print("\n─── TC-15: Task Stats ───")
    
    r, s = get("/api/tasks/stats")
    report("STATS", "Task stats endpoint",
           isinstance(r, dict) and "overall" in r and "categories" in r,
           f"keys={list(r.keys())}")
    
    # Check overall stats shape
    overall = r.get("overall", {})
    has_stats = all(k in overall for k in ["total", "completed", "pending", "completion_rate"])
    report("STATS", "Overall stats has required fields",
           has_stats,
           f"overall={overall}")


# ═══════════════════════════════════════════════════
# TEST: Role-based Auth Login
# ═══════════════════════════════════════════════════
def test_auth_login():
    print("\n─── TC-16: Role-based Auth Login ───")
    
    r, s = post("/api/auth/login", {"username": "kid", "password": "0000"})
    report("AUTH", "Kid login (correct PIN)",
           s == 200 and r.get("role") == "kid", f"resp={r}")
    
    r2, s2 = post("/api/auth/login", {"username": "kid", "password": "wrong"})
    report("AUTH", "Kid login (wrong PIN)",
           s2 == 403 and "密碼" in str(r2.get("error","")), f"resp={r2}")
    
    r3, s3 = post("/api/auth/login", {"username": "admin", "password": "admin123"})
    report("AUTH", "Admin login (correct)",
           s3 == 200 and r3.get("role") == "admin", f"resp={r3}")
    
    r4, s4 = post("/api/auth/login", {"username": "nonexist", "password": "x"})
    report("AUTH", "Non-existent user",
           s4 == 404, f"resp={r4}")
    
    r5, s5 = post("/api/auth/login", {"username": "test"})
    report("AUTH", "Missing password",
           s5 == 400, f"resp={r5}")


def test_parent_register():
    print("\n─── TC-17: Parent Registration ───")
    
    r, s = post("/api/auth/parent-register", {
        "username": f"tparent_{int(time.time())}",
        "password": "test1234", "name": "Test", "email": "t@t.com"
    })
    pid = r.get("parent", {}).get("id")
    report("PARENT", "Register new parent",
           s == 201 and r.get("ok") == True, f"resp={r}")
    
    if pid:
        r2, s2 = post("/api/auth/link-kid", {"parent_id": pid, "kid_username": "kid"})
        report("PARENT", "Link to kid", s2 == 201, f"resp={r2}")
        
        r3, s3 = get(f"/api/auth/parent-kids?parent_id={pid}")
        report("PARENT", "Get linked kids",
               s3 == 200 and len(r3) > 0, f"count={len(r3)}")
    
    r4, s4 = post("/api/auth/parent-register", {"username": "admin", "password": "test1234"})
    report("PARENT", "Duplicate username", s4 == 409, f"resp={r4}")
    
    r5, s5 = post("/api/auth/parent-register", {"username": "sp_test", "password": "ab"})
    report("PARENT", "Short password", s5 == 400, f"resp={r5}")


# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════
def main():
    global VERBOSE
    if "--verbose" in sys.argv:
        VERBOSE = True
    
    print(f"\n{'='*60}")
    print(f"🧪 Kids Town E2E Functional Test Suite")
    print(f"{'='*60}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API:  {API}")
    print(f"DB:   {DB_PATH}")
    print(f"{'='*60}")
    
    # Run all test cases
    test_login()
    test_kids_crud()
    test_task_completion()
    test_recurring_tasks()
    test_points_adjust()
    test_buildings()
    test_expedition()
    test_achievements()
    test_streaks()
    test_town()
    test_task_crud()
    test_activity()
    test_task_filtering()
    test_dev_dashboard()
    test_task_stats()
    test_auth_login()
    test_parent_register()
    
    # Summary
    print(f"\n{'='*60}")
    total = results["pass"] + results["fail"]
    rate = (results["pass"] / total * 100) if total > 0 else 0
    print(f"📊 SUMMARY: {results['pass']} ✅ PASS  |  {results['fail']} ❌ FAIL  |  {total} TOTAL")
    print(f"   PASS RATE: {rate:.1f}%")
    print(f"{'='*60}")
    
    if failures:
        print(f"\n⚠️  FAILURES ({len(failures)}):")
        for i, f in enumerate(failures):
            print(f"  {i+1}. {f}")
    
    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
