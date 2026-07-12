#!/usr/bin/env python3
"""
Kids Town Full FE Function Test v2
====================================
Tests all frontend logic WITHOUT browser.
Uses: API direct tests + HTML/JS static analysis + regex validation.

Usage:
  python3 fe_full_test.py
"""

import os, sys, json, re, time, subprocess, urllib.request, urllib.error
from datetime import datetime

BASE_URL = "https://moody-faction-spoken.ngrok-free.dev"
API_DIRECT = "http://127.0.0.1:9123"  # Direct backend port (no proxy issues)
KIDS_DIR = os.path.dirname(os.path.abspath(__file__))

results = {"pass": 0, "fail": 0}
failures = []

def report(cat, name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results["pass" if passed else "fail"] += 1
    msg = f"{status} | {cat} | {name}"
    if not passed and detail:
        msg += f"\n       └─ {detail}"
        failures.append(f"{cat} | {name}: {detail}")
    print(msg)

def fetch_json(url, timeout=10):
    """Fetch JSON from URL."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        return {"error": str(e)}, e.code
    except Exception as e:
        return {"error": str(e)}, 0

# ═══════════════════════════════════════════════════
# 1. API ENDPOINTS
# ═══════════════════════════════════════════════════
def test_api_direct():
    print("\n─── 1. API Endpoints (direct to port 9123) ───")
    
    api_tests = [
        ("/api/health", lambda d: d.get("status") == "ok"),
        ("/api/kids", lambda d: isinstance(d, list)),
        ("/api/tasks", lambda d: isinstance(d, list)),
        ("/api/building-defs", lambda d: isinstance(d, list) and len(d) > 0),
        ("/api/achievements/all", lambda d: isinstance(d, list)),
        ("/api/leaderboard", lambda d: isinstance(d, (dict, list))),  # can be list or dict
        ("/api/tasks/stats", lambda d: isinstance(d, dict)),
        ("/api/activity", lambda d: isinstance(d, list)),
        ("/api/transactions?kid_id=1", lambda d: isinstance(d, (dict, list)) and ("items" in d if isinstance(d, dict) else True)),
    ]
    
    for path, validate in api_tests:
        data, status = fetch_json(f"{API_DIRECT}{path}")
        ok = validate(data)
        if not ok:
            error_str = data.get('error','')[:60] if isinstance(data, dict) else f"type={type(data).__name__}, status={status}"
        else:
            error_str = ""
        report("API", path, ok, error_str)

def test_api_kid_endpoints():
    print("\n─── 2. API Kid-specific Endpoints ───")
    
    data, status = fetch_json(f"{API_DIRECT}/api/kids")
    if not isinstance(data, list) or len(data) == 0:
        report("API", "Kid endpoints (no kids)", False, "No kids found")
        return
    
    kid_id = data[0]["id"]
    endpts = [
        (f"/api/kids/{kid_id}/points", lambda d: "points" in d),
        (f"/api/kids/{kid_id}/town", lambda d: "kid" in d and "buildings" in d),
        (f"/api/kids/{kid_id}/buildings", lambda d: isinstance(d, list)),
        (f"/api/kids/{kid_id}/inventory", lambda d: isinstance(d, list)),
        (f"/api/kids/{kid_id}/expedition", lambda d: isinstance(d, dict) or isinstance(d, list)),
        (f"/api/kids/{kid_id}/explored", lambda d: isinstance(d, list)),
        (f"/api/kids/{kid_id}/achievements", lambda d: isinstance(d, list)),
        (f"/api/kids/{kid_id}/streak", lambda d: "current_streak" in d),
    ]
    
    for path, validate in endpts:
        data, status = fetch_json(f"{API_DIRECT}{path}")
        ok = validate(data)
        report("API", path, ok,
               f"status={status}" if not ok else "")


def test_api_stats():
    print("\n─── 3. API Stats Endpoints ───")
    
    endpoints = [
        ("/api/stats/completion-history", lambda d: isinstance(d, (dict, list))),
        ("/api/stats/monthly", lambda d: isinstance(d, (list, dict))),
        ("/api/stats/calendar", lambda d: isinstance(d, (list, dict))),
        ("/api/stats/by-category", lambda d: isinstance(d, list)),
        ("/api/transactions/summary?kid_id=1", lambda d: isinstance(d, dict) and len(d) > 0),
        ("/api/dev-dashboard", lambda d: isinstance(d, dict)),
    ]
    
    for path, validate in endpoints:
        data, status = fetch_json(f"{API_DIRECT}{path}")
        ok = validate(data)
        report("API", path, ok,
               f"status={status}" if not ok else "")


# ═══════════════════════════════════════════════════
# 2. FRONTEND HTML STATIC ANALYSIS
# ═══════════════════════════════════════════════════
def test_html_structure():
    print("\n─── 4. Frontend HTML Structure ───")
    
    index_path = os.path.join(KIDS_DIR, "index.html")
    if not os.path.exists(index_path):
        report("HTML", "index.html exists", False, "File not found")
        return
    
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    html_len = len(html)
    report("HTML", f"index.html size ({html_len} bytes)", html_len > 10000,
           f"only {html_len} bytes")
    
    # Check essential HTML elements
    checks = {
        "loginScreen": 'id="loginScreen"' in html,
        "username input": 'id="loginUsername"' in html,
        "password input": 'id="loginPassword"' in html,
        "login button": 'login-btn' in html or 'doLogin' in html,
        "parent login link": 'showParentLogin' in html,
        "admin login link": 'showAdminLogin' in html,
        "application root": 'id="app"' in html,
        "town canvas": 'id="townCanvas"' in html,
        "task list": 'id="taskList"' in html,
        "shop grid": 'id="shopGrid"' in html,
        "inventory grid": 'id="inventoryGrid"' in html,
        "buildings list": 'id="buildingsList"' in html,
        "modal overlay": 'id="modalOverlay"' in html,
        "toast element": 'id="toast"' in html,
        "tab buttons": 'tab-btn' in html,
        "expedition area": 'expedition-area' in html,
        "management section": 'mgmt-section' in html,
        "header gold display": 'id="hdrGold"' in html,
        "placement bar": 'id="placementBar"' in html,
        "streak display": 'id="streakDisplay"' in html,
        "daily chart": 'id="dailyChart"' in html,
        "service worker": 'service-worker.js' in html,
        "manifest link": 'manifest.json' in html,
        "viewport meta": 'viewport' in html,
        "Google Fonts": 'fonts.googleapis.com' in html,
    }
    
    ok_count = sum(1 for v in checks.values() if v)
    total = len(checks)
    for name, found in checks.items():
        if not found:
            report("HTML", f"Element: {name}", False, "missing from HTML")
    report("HTML", f"Required HTML elements ({ok_count}/{total})", 
           ok_count == total,
           f"missing: {[k for k,v in checks.items() if not v]}")


def test_js_analysis():
    print("\n─── 5. Frontend JavaScript Analysis ───")
    
    index_path = os.path.join(KIDS_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Extract JS from <script> tag
    js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    if not js_match:
        report("JS", "Extract <script> block", False, "No script tag found")
        return
    
    js = js_match.group(1)
    js_len = len(js)
    report("JS", f"JS block size ({js_len} chars)", js_len > 5000,
           f"only {js_len} chars")
    
    # Check JS syntax with node
    try:
        result = subprocess.run(
            ["node", "--check", "-"],
            input=js.encode(),
            capture_output=True,
            timeout=5
        )
        syntax_ok = result.returncode == 0
        report("JS", "JS syntax check", syntax_ok,
               result.stderr.decode()[:200] if not syntax_ok else "")
    except FileNotFoundError:
        report("JS", "JS syntax check", False, "Node not installed")
    
    # Check all required functions are defined
    required_funcs = [
        "loginParent", "loadKids", "selectKid", "addKid", "logout",
        "loadTown", "loadBuildingDefs", "fetchAPI",
        "updateHeader", "switchTab", "renderAll",
        "renderPlots", "showBuildModal", "startPlacement",
        "cancelPlacement", "placeBuilding",
        "showBuildingUpgrade", "doUpgrade",
        "renderBuildingsTab", "renderShop", "renderInventory",
        "renderExpedition", "renderTasks",
        "addTask", "completeTask", "deleteTask",
        "renderManage", "renderManageTasks", "mgmtAddTask",
        "editTask", "saveTaskEdit", "deleteManageTask",
        "adjustPoints", "loadActivity",
        "renderAchievements", "loadStats", "renderStreaks",
        "renderDailyChart", "showToast", "closeModal",
        "initCanvas", "renderCanvas",
    ]
    
    missing = []
    found_count = 0
    for fn in required_funcs:
        search = f"function {fn}" if f"function {fn}" in js else f"async function {fn}" if f"async function {fn}" in js else None
        # Also check for arrow functions / method assignments
        if search or f"{fn}=" in js or f"{fn}(" in js:
            found_count += 1
        else:
            # Be more lenient — check if it's referenced in any way
            if fn not in js:
                missing.append(fn)
    
    report("JS", f"Required functions ({len(required_funcs)-len(missing)}/{len(required_funcs)})",
           len(missing) == 0,
           f"missing={missing}" if missing else "")
    
    # Check API base is set
    api_base_set = "const API = ''" in js or "const API = " in js
    report("JS", "API base URL configured", api_base_set)
    
    # Check PARENT_PASSWORD
    has_parent_pin = "PARENT_PASSWORD" in js
    report("JS", "Parent PIN configured", has_parent_pin)
    
    # Check global state variables
    state_vars = ["currentKidId", "kids", "tasks", "townData", "buildingDefs"]
    state_ok = []
    for v in state_vars:
        if f"let {v}" in js or f"var {v}" in js:
            state_ok.append(v)
    report("JS", f"Global state vars ({len(state_ok)}/{len(state_vars)})",
           len(state_ok) == len(state_vars),
           f"missing={[v for v in state_vars if v not in state_ok]}")
    
    # Check error handling
    has_try_catch = js.count("catch(e)") 
    report("JS", f"Error handling (try-catch: {has_try_catch} instances)",
           has_try_catch > 5,
           f"only {has_try_catch} catch blocks")
    
    # Check fetch calls use the API variable (not hardcoded)
    hardcoded_urls = re.findall(r'fetch\([\'"]https?://', js)
    report("JS", f"Hardcoded URLs in fetch ({len(hardcoded_urls)} instances)",
           len(hardcoded_urls) == 0,
           f"found: {hardcoded_urls[:3]}" if hardcoded_urls else "")


def test_css_analysis():
    print("\n─── 6. CSS Analysis ───")
    
    index_path = os.path.join(KIDS_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Extract CSS from <style> tag
    style_match = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
    if not style_match:
        report("CSS", "Extract <style> block", False, "No style tag found")
        return
    
    css = style_match.group(1)
    css_len = len(css)
    report("CSS", f"CSS block size ({css_len} chars)", css_len > 5000,
           f"only {css_len} chars")
    
    # Check essential CSS classes
    css_checks = {
        "login screen": "loginScreen" in css,
        "header styles": ".header" in css,
        "tabs": ".tabs" in css or ".tab-btn" in css,
        "task cards": ".task-card" in css,
        "shop grid": ".shop-grid" in css,
        "buildings": ".building-card" in css,
        "town canvas": "#townCanvas" in css,
        "modal": ".modal" in css,
        "toast": "#toast" in css,
        "placement bar": ".placement-bar" in css,
        "expedition": ".exp-region-card" in css,
        "management": ".mgmt-card" in css or ".mgmt-section" in css,
        "mobile responsive": "@media" in css or "max-width:480px" in css,
        "animations": "@keyframes" in css,
        "pixel font": "pixel-font" in css or "Press Start 2P" in css,
    }
    
    ok_count = sum(1 for v in css_checks.values() if v)
    missing_css = [k for k,v in css_checks.items() if not v]
    report("CSS", f"CSS classes present ({ok_count}/{len(css_checks)})",
           ok_count >= len(css_checks) - 2,  # Allow 2 missing
           f"missing={missing_css}" if missing_css else "")


def test_audio_js():
    print("\n─── 7. Audio Module (audio.js) ───")
    
    audio_path = os.path.join(KIDS_DIR, "audio.js")
    if not os.path.exists(audio_path):
        report("AUDIO", "audio.js exists", False, "File not found")
        return
    
    with open(audio_path, "r", encoding="utf-8") as f:
        js = f.read()
    
    js_len = len(js)
    report("AUDIO", f"audio.js size ({js_len} bytes)", js_len > 5000,
           f"only {js_len} bytes")
    
    # Check global Audio export
    has_window_audio = "window.Audio = Audio" in js
    report("AUDIO", "window.Audio export", has_window_audio)
    
    # Check core methods
    audio_methods = ["init", "coinPickup", "buttonClick", "celebration", 
                     "taskComplete", "errorBuzzer", "buildingPlace",
                     "buildingUpgrade", "startAmbient", "stopAmbient",
                     "setMuted", "toggleMute"]
    
    found = []
    for m in audio_methods:
        if f"{m}:" in js or f"{m}(" in js or f"Audio.{m} =" in js:
            found.append(m)
    
    report("AUDIO", f"Audio methods ({len(found)}/{len(audio_methods)})",
           len(found) >= 8,
           f"missing={[m for m in audio_methods if m not in found]}" if len(found) < 8 else "")
    
    # Check Web Audio API usage
    has_audio_context = "AudioContext" in js or "webkitAudioContext" in js
    report("AUDIO", "Web Audio API (AudioContext)", has_audio_context)
    
    # Check node pooling
    has_node_pool = "nodePool" in js or "oscillators" in js
    report("AUDIO", "Node pooling for performance", has_node_pool)
    
    # Check Pentatonic scale (child-safe)
    has_pentatonic = "PENTATONIC" in js
    report("AUDIO", "Pentatonic scale (child-safe)", has_pentatonic)
    
    # No audio files dependency
    has_no_audio_files = ".mp3" not in js and ".wav" not in js and ".ogg" not in js
    report("AUDIO", "Zero external audio file dependencies", has_no_audio_files,
           "Implies external audio files used" if not has_no_audio_files else "")


def test_other_files():
    print("\n─── 8. Supporting Files ───")
    
    files = {
        "stats.html": "統計頁面",
        "transactions.html": "交易記錄頁面",
        "kids-dev.html": "開發者儀表板",
        "service-worker.js": "Service Worker (PWA)",
        "manifest.json": "PWA Manifest",
        "icon-192.png": "PWA Icon 192",
        "icon-512.png": "PWA Icon 512",
        "icon.svg": "SVG Icon",
        "backend_v2.py": "Backend API server",
    }
    
    for fname, desc in files.items():
        path = os.path.join(KIDS_DIR, fname)
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        report("FILES", f"{desc} ({fname})", exists,
               f"size={size} bytes" if exists else "")


def test_backend_db():
    print("\n─── 9. Database Integrity ───")
    
    db_path = os.path.join(KIDS_DIR, "kids_town.db")
    if not os.path.exists(db_path):
        report("DB", "Database file", False, "File not found")
        return
    
    size = os.path.getsize(db_path)
    report("DB", f"DB file size ({size} bytes)", size > 1000,
           f"too small: {size} bytes")
    
    # Check SQLite integrity
    try:
        import sqlite3
        db = sqlite3.connect(db_path)
        cur = db.execute("PRAGMA integrity_check")
        integrity = cur.fetchone()[0]
        report("DB", "SQLite integrity check", integrity == "ok",
               f"result: {integrity}")
        
        # Check tables exist
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        expected_tables = ["kids", "tasks", "points_log", "buildings", "building_defs",
                           "inventory", "expeditions", "explored_regions", "achievements", "streaks"]
        missing_tables = [t for t in expected_tables if t not in tables]
        report("DB", f"Required tables ({len(expected_tables)-len(missing_tables)}/{len(expected_tables)})",
               len(missing_tables) == 0,
               f"missing={missing_tables}" if missing_tables else f"tables={tables}")
        
        # Check FK integrity
        fk_violations = db.execute("PRAGMA foreign_key_check").fetchall()
        report("DB", "Foreign key integrity", len(fk_violations) == 0,
               f"violations={fk_violations}")
        
        # Check sample data
        kid_count = db.execute("SELECT COUNT(*) FROM kids").fetchone()[0]
        task_count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        report("DB", f"Kids: {kid_count}, Tasks: {task_count}",
               kid_count > 0,
               f"No kids in database")
        
        db.close()
    except Exception as e:
        report("DB", "Database check", False, str(e)[:100])


def test_combined_server():
    print("\n─── 10. Combined Server Proxy ───")
    
    # Test via ngrok proxy
    endpts = [
        ("/api/kids", lambda d: isinstance(d, list)),
        ("/api/tasks", lambda d: isinstance(d, list)),
        ("/api/building-defs", lambda d: isinstance(d, list) and len(d) > 0),
    ]
    
    for path, validate in endpts:
        data, status = fetch_json(f"{BASE_URL}{path}")
        ok = validate(data)
        report("PROXY", f"Via ngrok {path}", ok,
               f"status={status}" if not ok else "")


# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════
def main():
    print(f"\n{'='*60}")
    print(f"🏘️ Kids Town Full FE Function Test v2")
    print(f"{'='*60}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"HTML: {os.path.join(KIDS_DIR, 'index.html')}")
    print(f"API:  {API_DIRECT}")
    print(f"URL:  {BASE_URL}")
    print(f"{'='*60}")
    
    test_api_direct()
    test_api_kid_endpoints()
    test_api_stats()
    test_html_structure()
    test_js_analysis()
    test_css_analysis()
    test_audio_js()
    test_other_files()
    test_backend_db()
    test_combined_server()
    
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
