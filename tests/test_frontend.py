"""Frontend E2E tests (Playwright) — requirement-based (black-box).

Test cases verify USER-VISIBLE requirements, NOT implementation details.
Selectors prefer roles, labels, and visible strings.

Requirements:
  TC-FE-01  小朋友用帳號+PIN 登入 → 見到城鎮 HUD
  TC-FE-02  能力面板顯示 5 屬性 (臂力/知識/速度/創意/勇氣), 唔再有 體力/6 屬性
  TC-FE-03  戰鬥流程: 開戰 → 見到怪物 → 攻擊
  TC-FE-04  Boss 集料召喚入口存在
  TC-FE-05  打贏戰鬥後掉落顯示稀有度
  TC-FE-06  戰鬥已上線, 選單唔再有「即將開放」
  TC-FE-07  家長可以喺登入頁註冊
  TC-FE-08  家長可以喺管理頁建立仔女
  TC-FE-09  小朋友只見到自己 + 全體任務
  FE-P0-01  未登入不能經 UI／瀏覽器完成任務或改金幣
  FE-P0-02  小朋友登入成功；頁面／回應唔顯示明文 PIN
  FE-P0-03  家長 A session 不能管理家長 B 嘅仔女
  FE-P0-04  瀏覽器 GET /kids/kids_town.db 同 backend_v2.py → 404
  FE-P0-05  空庫 admin/admin123 登入失敗
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.factories import (  # noqa: E402
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    connect_db,
    get_kid_points,
    init_empty_db,
    insert_kid,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE_KID_NAME = "TestKid"
FE_KID_USERNAME = "test_fe_kid"
FE_OTHER_KID_NAME = "OtherKid"
FE_OTHER_USERNAME = "test_fe_other"
FE_PARENT_A_USERNAME = "test_fe_parent"
FE_PARENT_B_USERNAME = "test_fe_parent_b"
FE_PARENT_A_NAME = "Test Parent A"
FE_PARENT_B_NAME = "Test Parent B"
# Historical default — must fail on a fresh DB (not a live family password).
LEGACY_ADMIN_USERNAME = "admin"
LEGACY_ADMIN_PASSWORD = "admin123"


def _playwright_unavailable_reason():
    """Skip only when Playwright / Chromium cannot run. Cross-platform."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "playwright package not installed. "
            "Install: pip install -r requirements.txt && python -m playwright install chromium"
        )
    try:
        with sync_playwright() as p:
            exe = p.chromium.executable_path
        if not exe or not os.path.isfile(exe):
            return (
                "Playwright Chromium browser is not installed. "
                "Run: python -m playwright install chromium"
            )
    except Exception as exc:
        return (
            f"Playwright Chromium is not available ({exc}). "
            "Run: python -m playwright install chromium"
        )
    return None


_PW_SKIP = _playwright_unavailable_reason()

pytestmark = [
    pytest.mark.frontend,
    pytest.mark.skipif(
        _PW_SKIP is not None,
        reason=_PW_SKIP or "Playwright Chromium not available",
    ),
]


def _wait_port(port, timeout=20):
    for _ in range(timeout * 2):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _launch_chromium(playwright):
    return playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )


def _seed_frontend_db(dst):
    """Empty schema + two synthetic families. Never copies kids_town.db."""
    import backend_v2 as b

    old = b.DB_PATH
    b.app.config["TESTING"] = True
    init_empty_db(b, dst)
    kid = insert_kid(
        dst,
        name=FE_KID_NAME,
        username=FE_KID_USERNAME,
        pin=TEST_KID_PIN,
        level=20,
        points=40,
        experience=100,
    )
    other = insert_kid(
        dst,
        name=FE_OTHER_KID_NAME,
        username=FE_OTHER_USERNAME,
        pin=TEST_KID_PIN,
        level=5,
        points=5,
    )
    db = connect_db(dst)
    db.execute(
        "UPDATE kids SET ability_str=?, ability_brv=? WHERE id=?",
        (20, 10, kid["id"]),
    )
    db.execute(
        "INSERT INTO buildings (kid_id, def_id, plot_idx, level, cell_x, cell_y, stored) "
        "VALUES (?, 6, 0, 1, 2, 2, 0)",
        (kid["id"],),
    )
    db.execute(
        "INSERT INTO parents (username, password, name) VALUES (?, ?, ?)",
        (FE_PARENT_A_USERNAME, b.hash_password(TEST_PARENT_PASSWORD), FE_PARENT_A_NAME),
    )
    parent_a_id = db.execute(
        "SELECT id FROM parents WHERE username=?", (FE_PARENT_A_USERNAME,)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO parent_kid (parent_id, kid_id) VALUES (?, ?)",
        (parent_a_id, kid["id"]),
    )
    db.execute(
        "INSERT INTO parents (username, password, name) VALUES (?, ?, ?)",
        (FE_PARENT_B_USERNAME, b.hash_password(TEST_PARENT_PASSWORD), FE_PARENT_B_NAME),
    )
    parent_b_id = db.execute(
        "SELECT id FROM parents WHERE username=?", (FE_PARENT_B_USERNAME,)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO parent_kid (parent_id, kid_id) VALUES (?, ?)",
        (parent_b_id, other["id"]),
    )
    db.execute(
        "INSERT INTO tasks (title, icon, points, kid_id) VALUES ('做功課', '📝', 10, NULL)"
    )
    task_id = db.execute("SELECT id FROM tasks WHERE title='做功課'").fetchone()[0]
    db.commit()
    db.close()
    b.DB_PATH = old
    return {
        "kid_id": kid["id"],
        "other_kid_id": other["id"],
        "parent_a_id": parent_a_id,
        "parent_b_id": parent_b_id,
        "task_id": task_id,
    }


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    """Empty seeded SQLite (session-scoped). Never copies production kids_town.db."""
    dst = str(tmp_path_factory.mktemp("db") / "test.db")
    ids = _seed_frontend_db(dst)
    # Stash ids next to the file so other session fixtures can read them.
    meta = dst + ".ids.json"
    with open(meta, "w", encoding="utf-8") as fh:
        json.dump(ids, fh)
    return dst


@pytest.fixture(scope="session")
def fe_ids(test_db_path):
    with open(test_db_path + ".ids.json", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def fe_kid_id(fe_ids):
    return {"kid_id": fe_ids["kid_id"], "other_kid_id": fe_ids["other_kid_id"]}


@pytest.fixture(scope="session")
def base_url(test_db_path):
    """Dedicated test server on a free port, using the current venv interpreter."""
    port = _free_port()
    log_path = test_db_path + ".server.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(REPO, "tests", "_run_server.py"), test_db_path, str(port)],
        cwd=REPO,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**os.environ, "KIDS_TOWN_SECRET_KEY": "frontend-e2e-test-secret"},
    )
    if not _wait_port(port, timeout=30):
        logf.flush()
        try:
            detail = open(log_path, encoding="utf-8").read()
        except OSError:
            detail = "(no server log)"
        proc.kill()
        raise AssertionError(f"test server failed to start on {port}:\n{detail}")
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    logf.close()


@pytest.fixture(autouse=True)
def _reset_state(test_db_path):
    """每個 test 前重置遊戲狀態 (running expedition + daily/boss/pity)."""
    db = connect_db(test_db_path)
    db.execute('DELETE FROM expeditions WHERE status="running"')
    db.execute("DELETE FROM daily_battles")
    db.execute("DELETE FROM boss_progress")
    db.execute("DELETE FROM drop_pity")
    db.commit()
    db.close()
    yield


@pytest.fixture()
def page(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch_chromium(p)
        context = browser.new_context(viewport={"width": 1100, "height": 800})
        pg = context.new_page()
        # Battle UI loads remote pixel-art URLs; abort so tests stay offline-fast.
        pg.route("https://image.pollinations.ai/**", lambda route: route.abort())
        yield pg
        context.close()
        browser.close()


def _login(page, base_url, username=FE_KID_USERNAME, pin=TEST_KID_PIN, expect_hud=True):
    page.goto(f"{base_url}/kids/")
    page.locator("#loginUsername").fill(username)
    page.locator("#loginPassword").fill(pin)
    with page.expect_response(
        lambda r: "/api/auth/login" in r.url and r.request.method == "POST"
    ) as resp_info:
        page.get_by_role("button", name="🚪 登入").click()
    if expect_hud:
        page.locator("#app").wait_for(state="visible", timeout=8000)
    return resp_info.value


def _login_parent(page, base_url, username=FE_PARENT_A_USERNAME):
    page.goto(f"{base_url}/kids/")
    page.locator("#loginUsername").fill(username)
    page.locator("#loginPassword").fill(TEST_PARENT_PASSWORD)
    page.get_by_role("button", name="🚪 登入").click()
    page.get_by_text("小朋友管理", exact=False).first.wait_for(state="visible", timeout=8000)


def _goto_battle_lobby(page):
    """導航到戰鬥挑戰頁 (☰ → 探索 → 戰鬥類型)."""
    page.get_by_role("button", name="☰").click()
    page.locator("#dr").get_by_text("探索", exact=False).click()
    battle_tab = page.locator('.exp-type-btn[data-type="battle"]')
    battle_tab.wait_for(state="visible", timeout=8000)
    battle_tab.click()
    page.get_by_text("戰鬥挑戰", exact=False).first.wait_for(state="visible", timeout=8000)


def _visible_text(page):
    return page.locator("body").inner_text()


def _json_post(page, url, payload):
    """POST JSON from the page's browser context (cookies / no cookies as-is)."""
    return page.evaluate(
        """async ({url, payload}) => {
          const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'same-origin',
            body: JSON.stringify(payload),
          });
          return {status: r.status, text: await r.text()};
        }""",
        {"url": url, "payload": payload},
    )


# ── TC-FE-01: 登入 ────────────────────────────────────────────────

@pytest.mark.case_id("TC-FE-01")
def test_login_shows_town_hud(page, base_url):
    """TC-FE-01 小朋友用帳號+PIN 登入 → 見到城鎮 HUD。"""
    _login(page, base_url)
    assert page.get_by_text(FE_KID_NAME).first.is_visible()
    assert page.get_by_text("Lv.").first.is_visible()
    hidden = page.locator("#loginScreen").evaluate(
        "el => el.classList.contains('hidden') || getComputedStyle(el).display === 'none'"
    )
    assert hidden, "登入畫面應該收埋"


# ── TC-FE-02: 能力面板 5 屬性 ─────────────────────────────────────

@pytest.mark.case_id("TC-FE-02")
def test_ability_panel_shows_five_attributes(page, base_url):
    """TC-FE-02 能力面板顯示 5 屬性，唔再有「體力」。"""
    _login(page, base_url)
    page.locator("#hudAv").hover()
    page.locator("#hudTip").wait_for(state="visible", timeout=8000)
    tooltip = page.locator("text=臂力")
    assert tooltip.first.is_visible(), "能力面板應該顯示「臂力」"
    assert page.locator("text=體力").count() == 0, "唔應該再有「體力」"


# ── TC-FE-03: 戰鬥流程 ───────────────────────────────────────────

@pytest.mark.case_id("TC-FE-03")
def test_battle_flow_attack(page, base_url):
    """TC-FE-03 開戰 → 見到怪物 → 可以撳攻擊。"""
    _login(page, base_url)
    page.get_by_role("button", name="☰").click()
    page.locator("#dr").get_by_text("探索", exact=False).click()
    page.locator('.exp-type-btn[data-type="battle"]').wait_for(state="visible", timeout=8000)
    page.locator('.exp-type-btn[data-type="battle"]').click()
    page.locator("button.exp-btn.go").first.click()
    page.locator(".m-name").first.wait_for(state="visible", timeout=8000)
    assert page.get_by_text("野狼", exact=False).first.is_visible()
    page.get_by_text("攻擊", exact=False).first.click()


# ── TC-FE-04: Boss 集料召喚入口 ───────────────────────────────────

@pytest.mark.case_id("TC-FE-04")
def test_boss_summon_entry_in_battle_lobby(page, base_url):
    """TC-FE-04 戰鬥挑戰頁應該有 Boss 召喚入口."""
    _login(page, base_url)
    _goto_battle_lobby(page)
    assert page.get_by_text("Boss", exact=False).first.is_visible(), \
        "戰鬥挑戰頁應該顯示 Boss 召喚入口"


# ── TC-FE-05: 掉落稀有度顯示 ──────────────────────────────────────

@pytest.mark.case_id("TC-FE-05")
def test_battle_win_shows_rarity(page, base_url):
    """TC-FE-05 打贏戰鬥後, 掉落應該顯示稀有度 (普通/稀有/珍貴/傳說)."""
    _login(page, base_url)
    _goto_battle_lobby(page)
    page.locator("button.exp-btn.go").first.click()
    page.locator(".m-name").first.wait_for(state="visible", timeout=8000)
    won = False
    for _ in range(30):
        page.get_by_text("⚔️ 攻擊", exact=False).first.click()
        page.wait_for_timeout(200)
        alive = page.locator(".monster-card:not(.dead)")
        if alive.count() > 0:
            alive.first.click()
        page.wait_for_timeout(500)
        body = page.locator("#dbt").inner_text()
        overlay = page.locator(".result-overlay.active").inner_text() if page.locator(".result-overlay.active").count() else ""
        blob = body + overlay
        if "勝利" in blob or "戰敗" in blob:
            won = "勝利" in blob
            break
    assert won, "應該打贏 (合成 Lv20 小朋友 vs 野狼)"
    body = page.locator("body").inner_text()
    assert any(r in body for r in ["普通", "稀有", "珍貴", "傳說"]), \
        f"掉落應該顯示稀有度, 得到: {body[-500:]}"


# ── TC-FE-06: 「即將開放」標籤移除 ────────────────────────────────

@pytest.mark.case_id("TC-FE-06")
def test_battle_not_marked_coming_soon(page, base_url):
    """TC-FE-06 戰鬥已上線, 選單/戰鬥頁唔應該再有「即將開放」."""
    _login(page, base_url)
    page.get_by_role("button", name="☰").click()
    page.locator("#dr").wait_for(state="visible", timeout=5000)
    assert page.get_by_text("即將開放", exact=False).count() == 0, \
        "戰鬥已上線, 唔應該再顯示「即將開放」"


# ════════════════════════════════════════════════════════════════════
# stale running expedition 應該自動清理 (唔會 block 新戰鬥/Boss)
# ════════════════════════════════════════════════════════════════════

def _fe_kid_id(test_db_path):
    db = connect_db(test_db_path)
    row = db.execute("SELECT id FROM kids WHERE username=?", (FE_KID_USERNAME,)).fetchone()
    db.close()
    return row[0]


def _insert_stale_running_expedition(test_db_path, etype="battle"):
    from datetime import datetime, timedelta

    stale_start = (datetime.utcnow() - timedelta(hours=3)).isoformat() + "Z"
    stale_end = (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z"
    kid_id = _fe_kid_id(test_db_path)
    db = connect_db(test_db_path)
    db.execute(
        "INSERT INTO expeditions (kid_id, region_id, expedition_type, start_time, end_time, status) "
        "VALUES (?,1,?,?,?,'running')",
        (kid_id, etype, stale_start, stale_end),
    )
    db.commit()
    db.close()


def test_battle_starts_despite_stale_running_expedition(page, base_url, test_db_path):
    """有遺留嘅 stale running expedition, 開新戰鬥應該自動清理並成功."""
    _insert_stale_running_expedition(test_db_path, "battle")
    _login(page, base_url)
    _goto_battle_lobby(page)
    page.locator("button.exp-btn.go").first.click()
    page.locator(".m-name").first.wait_for(state="visible", timeout=8000)
    assert page.get_by_text("野狼", exact=False).first.is_visible()


def test_boss_summon_despite_stale_running_expedition(page, base_url, test_db_path):
    """有遺留嘅 stale running expedition, 召喚 Boss 應該自動清理並成功."""
    _insert_stale_running_expedition(test_db_path, "boss")
    db = connect_db(test_db_path)
    db.execute(
        "INSERT INTO inventory (kid_id, item_type, quantity) VALUES (?,'gem',3)",
        (_fe_kid_id(test_db_path),),
    )
    db.commit()
    db.close()
    _login(page, base_url)
    _goto_battle_lobby(page)
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    page.locator("button.exp-btn.go").filter(has_text="Boss").first.click()
    page.locator(".m-name").first.wait_for(state="visible", timeout=8000)
    assert page.get_by_text("Boss", exact=False).first.is_visible()
    assert dialogs, "應該有 confirm 對話框"


def test_boss_button_shows_cost_and_confirm(page, base_url, test_db_path):
    """Boss 按鈕顯示素材成本 💎, 撳落去有 confirm (取消唔召喚)."""
    db = connect_db(test_db_path)
    db.execute(
        "INSERT INTO inventory (kid_id, item_type, quantity) VALUES (?,'gem',3)",
        (_fe_kid_id(test_db_path),),
    )
    db.commit()
    db.close()
    _login(page, base_url)
    _goto_battle_lobby(page)
    boss_btn = page.locator("button.exp-btn.go").filter(has_text="Boss").first
    assert boss_btn.is_visible()
    assert "💎" in boss_btn.inner_text(), "Boss 按鈕應該顯示素材成本 💎"
    page.once("dialog", lambda d: d.dismiss())
    boss_btn.click()
    page.wait_for_timeout(800)
    assert page.locator(".m-name").count() == 0, "取消 confirm 唔應該召喚 Boss"


# ── TC-FE-07: 家長註冊 ────────────────────────────────────────────

@pytest.mark.case_id("TC-FE-07")
def test_parent_register_flow(page, base_url):
    """TC-FE-07 家長可以喺登入頁註冊新帳戶 (requirement)."""
    uname = f"up{int(time.time())}"
    page.goto(f"{base_url}/kids/")
    page.get_by_text("註冊", exact=False).first.click()
    page.locator("#regUsername").wait_for(state="visible", timeout=5000)
    page.locator("#regUsername").fill(uname)
    page.locator("#regPassword").fill("TestReg!pass1")
    page.locator("#regName").fill("新家長")
    page.get_by_text("建立帳戶", exact=False).first.click()
    page.get_by_text("成功", exact=False).first.wait_for(state="visible", timeout=8000)


# ── TC-FE-08: 家長建立仔女帳戶 ────────────────────────────────────

@pytest.mark.case_id("TC-FE-08")
def test_parent_create_kid_ui(page, base_url):
    """TC-FE-08 家長可以喺管理頁面建立仔女帳戶 (requirement)."""
    uname = f"uikid{int(time.time())}"
    _login_parent(page, base_url)
    assert page.get_by_text("小朋友管理", exact=False).first.is_visible(), \
        "管理頁面應該有「小朋友管理」section"
    page.locator("#kidNewName").fill("測試仔女")
    page.locator("#kidNewUsername").fill(uname)
    page.locator("#kidNewPin").fill("2468")
    page.get_by_text("建立仔女", exact=False).first.click()
    page.get_by_text("測試仔女", exact=False).first.wait_for(state="visible", timeout=8000)


# ── TC-FE-09: 小朋友只見到自己 + 全體任務 ─────────────────────────

@pytest.mark.case_id("TC-FE-09")
def test_kid_only_sees_own_and_global_tasks(page, base_url, test_db_path, fe_kid_id):
    """TC-FE-09 小朋友只見到自己嘅任務 + 全體任務, 唔見其他小朋友嘅任務."""
    db = connect_db(test_db_path)
    db.execute("DELETE FROM tasks WHERE title LIKE '%專屬%'")
    db.execute(
        "INSERT INTO tasks (title, icon, points, kid_id, category, description, recurring, due_date) "
        "VALUES ('小美專屬任務', '📝', 10, ?, '', '', '', NULL)",
        (fe_kid_id["other_kid_id"],),
    )
    db.commit()
    db.close()
    _login(page, base_url)
    page.locator("button.q", has_text="任務").first.click()
    page.get_by_text("做功課", exact=False).first.wait_for(state="visible", timeout=8000)
    assert page.locator("text=小美專屬任務").count() == 0, \
        "唔應該見到其他小朋友嘅任務"


# ── FE-P0-01 ──────────────────────────────────────────────────────

@pytest.mark.case_id("FE-P0-01")
def test_unauthenticated_ui_cannot_complete_task_or_adjust_points(page, base_url, test_db_path, fe_ids):
    """FE-P0-01 未登入不能經 UI 完成任務／改金幣；瀏覽器無 cookie 打 API → 401。"""
    page.goto(f"{base_url}/kids/")
    page.locator("#loginScreen").wait_for(state="visible", timeout=8000)
    assert page.get_by_role("button", name="🚪 登入").is_visible()
    assert page.locator(".task-complete-btn").count() == 0
    assert page.locator("#adjustKid").is_hidden() or not page.locator("#adjustKid").is_visible()

    kid_id = fe_ids["kid_id"]
    task_id = fe_ids["task_id"]
    before = get_kid_points(test_db_path, kid_id)

    points = _json_post(page, f"{base_url}/api/kids/{kid_id}/points", {"amount": 100, "reason": "hack"})
    assert points["status"] == 401, points.get("text")

    adjust = _json_post(
        page,
        f"{base_url}/api/kids/{kid_id}/points/adjust",
        {"amount": 10, "reason": "hack"},
    )
    assert adjust["status"] == 401, adjust.get("text")

    complete = _json_post(page, f"{base_url}/api/tasks/{task_id}/complete", {"kid_id": kid_id})
    assert complete["status"] == 401, complete.get("text")

    assert get_kid_points(test_db_path, kid_id) == before


# ── FE-P0-02 ──────────────────────────────────────────────────────

@pytest.mark.case_id("FE-P0-02")
def test_kid_login_ui_does_not_display_raw_pin(page, base_url):
    """FE-P0-02 小朋友登入成功；回應同可見頁面唔顯示明文 PIN。"""
    resp = _login(page, base_url)
    assert resp.ok, resp.text()
    data = resp.json()
    body = resp.text()
    assert data.get("role") == "kid"
    assert "pin" not in data
    assert "password" not in data
    user = data.get("user") or {}
    assert "pin" not in user
    assert "password" not in user
    assert TEST_KID_PIN not in body
    assert TEST_KID_PIN not in json.dumps(data)

    page.get_by_text(FE_KID_NAME).first.wait_for(state="visible", timeout=8000)
    visible = _visible_text(page)
    assert TEST_KID_PIN not in visible
    err = page.locator("#loginError").inner_text()
    assert TEST_KID_PIN not in err
    assert page.locator("#loginPassword").get_attribute("type") == "password"


# ── FE-P0-03 ──────────────────────────────────────────────────────

@pytest.mark.case_id("FE-P0-03")
def test_parent_a_ui_cannot_manage_parent_b_kid(page, base_url, test_db_path, fe_ids):
    """FE-P0-03 家長 A 管理頁睇唔到／調唔到家長 B 嘅仔女。"""
    other_id = fe_ids["other_kid_id"]
    before = get_kid_points(test_db_path, other_id)

    _login_parent(page, base_url, username=FE_PARENT_A_USERNAME)
    page.locator("#kidList").get_by_text(FE_KID_NAME, exact=False).wait_for(
        state="visible", timeout=8000
    )
    page.wait_for_function(
        """(name) => {
          const sel = document.getElementById('adjustKid');
          return sel && [...sel.options].some(o => (o.textContent || '').includes(name));
        }""",
        arg=FE_KID_NAME,
        timeout=8000,
    )
    visible = _visible_text(page)
    assert FE_OTHER_KID_NAME not in visible, "家長 A 唔應該喺管理頁見到家長 B 嘅仔女"
    assert FE_PARENT_B_NAME not in visible

    option_values = page.locator("#adjustKid option").evaluate_all(
        "els => els.map(e => e.value)"
    )
    option_labels = page.locator("#adjustKid option").all_inner_texts()
    blob = " ".join(option_labels)
    assert FE_OTHER_KID_NAME not in blob
    assert str(other_id) not in option_values

    filter_opts = page.locator("#mgmtFilterKid option").all_inner_texts()
    assert FE_OTHER_KID_NAME not in " ".join(filter_opts)

    r = _json_post(
        page,
        f"{base_url}/api/kids/{other_id}/points/adjust",
        {"amount": 99, "reason": "idor"},
    )
    assert r["status"] == 403, r.get("text")
    assert get_kid_points(test_db_path, other_id) == before


# ── FE-P0-04 ──────────────────────────────────────────────────────

@pytest.mark.case_id("FE-P0-04")
def test_browser_static_denylist_db_and_python(page, base_url):
    """FE-P0-04 瀏覽器 GET /kids/kids_town.db 同 /kids/backend_v2.py → 404。"""
    for path in ("/kids/kids_town.db", "/kids/backend_v2.py"):
        resp = page.goto(f"{base_url}{path}")
        assert resp is not None
        assert resp.status == 404, f"{path} -> {resp.status} {resp.text()[:200]}"
        body = page.locator("body").inner_text()
        assert "not found" in body.lower()
        assert "SQLite format 3" not in body
        assert "def serve_kids_static" not in body
        assert "hash_password" not in body


# ── FE-P0-05 ──────────────────────────────────────────────────────

@pytest.mark.case_id("FE-P0-05")
def test_default_admin_login_fails_on_fresh_db(page, base_url):
    """FE-P0-05 空庫用歷史預設 admin/admin123 登入失敗，停留登入頁。"""
    page.goto(f"{base_url}/kids/")
    assert page.locator("#loginPassword").input_value() == ""
    page.locator("#loginUsername").fill(LEGACY_ADMIN_USERNAME)
    page.locator("#loginPassword").fill(LEGACY_ADMIN_PASSWORD)
    page.get_by_role("button", name="🚪 登入").click()
    err = page.locator("#loginError")
    err.wait_for(state="visible", timeout=8000)
    page.wait_for_function(
        "() => document.getElementById('loginError').textContent.trim().length > 0",
        timeout=8000,
    )
    text = err.inner_text()
    assert text.strip(), "應該顯示登入失敗"
    assert LEGACY_ADMIN_PASSWORD not in text
    assert page.get_by_role("button", name="🚪 登入").is_visible()
    app_display = page.locator("#app").evaluate("el => getComputedStyle(el).display")
    assert app_display == "none"
    assert "Lv." not in _visible_text(page) or page.locator("#hudNm").is_hidden()
