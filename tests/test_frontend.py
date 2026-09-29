"""Frontend E2E tests (Playwright) — requirement-based (black-box).

Test cases verify USER-VISIBLE requirements, NOT implementation details.
Selectors prefer roles, labels, and visible strings.

Requirements:
  TC-FE-01  小朋友用帳號+PIN 登入 → 見到城鎮 HUD
  TC-FE-02  能力面板顯示 5 屬性 (臂力/知識/速度/創意/勇氣), 唔再有 體力/6 屬性
  TC-FE-03  戰鬥流程: 開戰 → 見到怪物 → 攻擊
  TC-FE-04  Boss 集料召喚入口存在
  TC-FE-05  打贏戰鬥後掉落顯示稀有度
  TC-FE-06  戰鬥已上線：無「即將開放」；Boss 顯示 💎 成本；取消 confirm 唔召喚
  TC-FE-10  打贏過嘅區域今日再開戰會被每日上限擋住
  TC-FE-07  家長可以喺登入頁註冊
  TC-FE-08  家長可以喺管理頁建立仔女
  TC-FE-09  小朋友只見到自己 + 全體任務
  TC-FE-JOURNEY-01  家長指派任務 → 小朋友完成 → HUD 金幣同完成回饋
  TC-FE-CEREMONY-01  真實 complete（唔 mock）後 toast／HUD 顯示金幣 + XP 數字 + 材料（唔只金幣）
  TC-FE-PLACE-SHOP-01  商店 建造 → startPlacement → 點空地／確認 → 地圖出現建築
  TC-FE-PLACE-BUILD-01  建築 tab 建造 → startPlacement → 點空地／確認 → 地圖出現建築
  TC-FE-TOWN-UX-01..05  四場景起屋（真實資料地圖 → 清單 → ghost 擺位 → 升級）。
  TC-FE-TOWN-FX-01/02  新起同升級嘅金星慶祝；升級金星要喺 action sheet 上面睇到。
  TC-FE-TOWN-HIT-01/02/03  背面格 hit-test、1100×800 同 1280×720 信箱撳格、軟橢圓接觸陰影。
  TC-FE-TOWN-MOTION-01/02  慶祝層 pointer-events:none；動畫掣跟 prefers-reduced-motion，開／關撳先寫 localStorage。
  TC-FE-TOWN-GRID-01  四場景地圖係 8×8。
  TC-FE-TOWN-STORE-LEGACY-01  格外（或無合法格）且 stored=0 嘅屋，載入時收進存倉 stored=1，保留種類同等級。
  TC-FE-TOWN-STORE-LEGACY-02  收倉之後唔好畫喺地圖、唔好當地圖「已起」；用現有存倉流程放返空地，唔扣資源。
  篩選 `-k 'town_grid or store_legacy'`。
  TC-FE-TOWN-STORE-LIST-01  已存倉（stored=1）嘅屋，場景 2 建築清單唔好當未起兼標價錢，亦唔好入「確定先至扣資源」。
  TC-FE-TOWN-STORE-PLACE-01  用存倉／#placementBar／unstored 放返，地圖見到屋，金幣材料唔變，同一行 stored=0。
  TC-FE-TOWN-STORE-CONFIRM-01  唔好同時見到扣資源確認文案同「你已經興建咗呢種建築物」；正確放返之後資源唔變。
  篩選 `-k 'store_list or store_place or store_confirm'`。
  TC-FE-TOWN-STORE-UX-01  清單放返存倉屋要留喺四場景 8×8。唔好 `#placementBar.active`、
  唔好藏 `#townMap`、唔好露出 24×16 `.valid-plot`／`↘️`。確認走 POST `/unstored`。
  篩選 `-k store_ux`。
  TC-FE-TOWN-UX-UPGRADE-COST-01  撳已起屋打開 #actionSheet，sheet 或確認層要顯示金幣同材料 need。
  TC-FE-TOWN-UX-UPGRADE-COST-02  資源唔夠就唔好撳得，亦唔好 POST /upgrade。
  TC-FE-TOWN-UX-UPGRADE-CONFIRM-01  第一撳 #btnUpgrade 只開確認；取消唔 POST；確定先至升級同扣 HUD。
  對齊設計稿 3b4671d：撳屋 → #actionSheet 顯示成本 → 確認 → 升級。唔係一撳升級。
  篩選 `-k 'upgrade_cost or upgrade_confirm'`。唔改 UX-05／store_ux 斷言。
  TC-FE-TOWN-UX-SHEET-BUFF-01  已起屋面板：#sheetFns 冇 .fn；可見 #sheetBuff 顯示而家等級 buff。
  TC-FE-TOWN-UX-SHEET-BUFF-02  唔好有 FN 假動作；打開或撳舊 stub 都唔好 toast「整好一件道具」。
  工坊 Lv.3：buff_type build_speed，buff_vals[2]＝4（種子 [2,3,4,5,6]）。篩選 `-k sheet_buff`。
  唔改 upgrade_cost／upgrade_confirm／UX-05／store_ux 斷言。
  FE-P0-01  未登入不能經 UI／瀏覽器完成任務或改金幣
  FE-P0-02  小朋友登入成功；頁面／回應唔顯示明文 PIN
  FE-P0-03  家長 A session 不能管理家長 B 嘅仔女
  FE-P0-04  瀏覽器 GET /kids/kids_town.db 同 backend_v2.py → 404
  FE-P0-05  空庫 admin/admin123 登入失敗
  FE-P0-06  登出後同一瀏覽器 context 寫入 API → 401，UI 返登入牆
  FE-XSS-01 任務標題 markup 唔當 HTML 執行（對應 P0-TC-XSS-01 DOM）
  FE-XSS-02 小朋友顯示名 markup 唔當 HTML 執行（對應 P0-TC-XSS-02 DOM）
"""
from __future__ import annotations

import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.factories import (  # noqa: E402
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    building_def_id,
    connect_db,
    get_kid_points,
    grant_inventory,
    init_empty_db,
    insert_building,
    insert_kid,
    inventory_map,
    set_kid_points,
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
FE_XSS_BOLD_TITLE = "<b>粗體</b>"
FE_XSS_IMG_TITLE = (
    '<img src="https://xss.example.test/probe.png" onerror="window.__xssHit=1">'
)
FE_XSS_KID_NAME = "<img src=x onerror=alert(1)>"
FE_XSS_KID_USERNAME = "test_fe_xss"
JOURNEY_TASK_TITLE = "JOURNEY-洗碗"
JOURNEY_TASK_POINTS = 12
CEREMONY_REAL_TASK_TITLE = "TC-FE-CEREMONY-洗碗"
CEREMONY_REAL_TASK_POINTS = 10
PLACE_SHOP_BUILDING = "圖書館"
PLACE_TAB_BUILDING = "健身室"
MAT_UI_TOKENS = {
    "wood": ("🪵", "木材", "wood"),
    "brick": ("🧱", "磚", "brick"),
    "glass": ("🪟", "玻璃", "glass"),
    "gear": ("⚙️", "齒輪", "gear"),
    "gem": ("💎", "寶石", "gem"),
    "fur": ("🦊", "毛皮", "fur"),
    "dragon_scale": ("🐉", "龍鱗", "dragon_scale"),
}


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


def _assert_write_apis_401(page, base_url, fe_ids):
    kid_id = fe_ids["kid_id"]
    task_id = fe_ids["task_id"]
    points = _json_post(
        page, f"{base_url}/api/kids/{kid_id}/points", {"amount": 100, "reason": "after-logout"}
    )
    assert points["status"] == 401, points.get("text")
    adjust = _json_post(
        page,
        f"{base_url}/api/kids/{kid_id}/points/adjust",
        {"amount": 10, "reason": "after-logout"},
    )
    assert adjust["status"] == 401, adjust.get("text")
    complete = _json_post(
        page, f"{base_url}/api/tasks/{task_id}/complete", {"kid_id": kid_id}
    )
    assert complete["status"] == 401, complete.get("text")


def _ui_logout(page):
    """Click the harness-visible 登出 control and wait for the login wall."""
    drawer = page.locator("#dr")
    opened = drawer.evaluate("el => el.classList.contains('o')")
    if not opened:
        page.get_by_role("button", name="☰").click()
        page.locator("#dr.o").wait_for(state="visible", timeout=8000)
    with page.expect_response(
        lambda r: "/api/auth/logout" in r.url and r.request.method == "POST"
    ) as resp_info:
        drawer.get_by_role("button", name="登出").click()
    assert resp_info.value.ok, resp_info.value.text()
    page.locator("#loginScreen").wait_for(state="visible", timeout=8000)
    page.get_by_role("button", name="🚪 登入").wait_for(state="visible", timeout=8000)
    app_display = page.locator("#app").evaluate("el => getComputedStyle(el).display")
    assert app_display == "none", "登出後應該返去登入牆"


def _give_gems(test_db_path, qty=3):
    db = connect_db(test_db_path)
    db.execute(
        "INSERT INTO inventory (kid_id, item_type, quantity) VALUES (?,'gem',?)",
        (_fe_kid_id(test_db_path), qty),
    )
    db.commit()
    db.close()


def _hud_gold(page):
    return int(page.locator("#hudCo").inner_text().strip() or "0")


def _hud_mat_count(page, mat):
    loc = page.locator(f'#hdrRes .mat[data-mat="{mat}"] .n')
    if loc.count() == 0:
        return 0
    return int(loc.first.inner_text().strip() or "0")


def _open_drawer(page):
    drawer = page.locator("#dr")
    opened = drawer.evaluate("el => el.classList.contains('o')")
    if not opened:
        page.get_by_role("button", name="☰").click()
        page.locator("#dr.o").wait_for(state="visible", timeout=8000)
    return drawer


def _goto_town_map(page):
    """建築 tab 嘅 startPlacement 唔會自動 st('town')；E2E 跟商店一樣切去地圖。

    Tiny harness: call st('town') instead of ☰ drawer, so the overlay cannot
    swallow the next map click. Product still does not auto-switch — (B).
    """
    town = page.locator("#tab-town")
    classes = town.get_attribute("class") or ""
    if "active" not in classes.split():
        page.evaluate("() => { if (typeof st === 'function') st('town'); }")
    page.locator("#tab-town.active").wait_for(state="visible", timeout=8000)
    page.locator("#townCanvasWrapper").wait_for(state="visible", timeout=8000)


def _fund_and_clear_building(test_db_path, kid_id, building_name):
    """Test-only: enough gold/mats to click 建造, and no pre-placed copy of that def."""
    set_kid_points(test_db_path, kid_id, 5000)
    grant_inventory(
        test_db_path,
        kid_id,
        {"wood": 80, "brick": 50, "glass": 20, "gear": 30, "gem": 10},
    )
    def_id_value = building_def_id(test_db_path, building_name)
    db = connect_db(test_db_path)
    db.execute(
        "DELETE FROM buildings WHERE kid_id=? AND def_id=?",
        (kid_id, def_id_value),
    )
    db.commit()
    db.close()
    return def_id_value


def _click_build_on_card(page, container, building_name):
    card = page.locator(container).locator(
        ".shop-item, .building-card", has_text=building_name
    ).first
    card.wait_for(state="visible", timeout=8000)
    btn = card.get_by_role("button", name="建造")
    assert btn.is_enabled(), (
        f"{building_name} 建造 should be enabled after fixture gold/materials seed"
    )
    btn.click()


def _building_origins(test_db_path, kid_id):
    db = connect_db(test_db_path)
    rows = db.execute(
        "SELECT cell_x, cell_y FROM buildings WHERE kid_id=?", (kid_id,)
    ).fetchall()
    db.close()
    return [{"x": r["cell_x"] or 0, "y": r["cell_y"] or 0} for r in rows]


def _pick_free_valid_plot(page, origins):
    """Choose a 2×2 that does not overlap existing building origins (DB).

    `let townData` is not on window, so occupancy is passed from SQLite.
    Frontend .valid-plot overlay uses plot_idx, not cell_x/cell_y.
    """
    picked = page.evaluate(
        """(origins) => {
          const used = new Set();
          (origins || []).forEach(b => {
            const x = b.x || 0, y = b.y || 0;
            for (let dy = 0; dy < 2; dy++)
              for (let dx = 0; dx < 2; dx++)
                used.add((x + dx) + ',' + (y + dy));
          });
          const plots = [...document.querySelectorAll('.valid-plot')];
          for (const el of plots) {
            const px = parseInt(el.dataset.px, 10);
            const py = parseInt(el.dataset.py, 10);
            let ok = true;
            for (let dy = 0; dy < 2 && ok; dy++)
              for (let dx = 0; dx < 2 && ok; dx++)
                if (used.has((px + dx) + ',' + (py + dy))) ok = false;
            if (ok) return {px, py};
          }
          return null;
        }""",
        origins,
    )
    assert picked, f"no free .valid-plot; origins={origins}"
    return picked


def _finish_placement_on_empty_cell(page, building_name, test_db_path, kid_id):
    """startPlacement 之後：見到放置 bar → 點綠色空地 → 確認 → 地圖出現建築。

    Product uses `.valid-plot` (2×2 green overlay) rather than `.empty-cell`
    (empty-cell clicks are ignored while placementDefId is set). Confirm is
    required by the current UI (selectPlacePos + confirmPlaceBuilding).
    """
    _goto_town_map(page)
    bar = page.locator("#placementBar")
    bar.wait_for(state="visible", timeout=8000)
    assert "active" in (bar.get_attribute("class") or ""), (
        "startPlacement must show #placementBar.active"
    )
    page.locator(".valid-plot").first.wait_for(state="visible", timeout=8000)
    before = page.locator(".town-building").count()
    picked = _pick_free_valid_plot(page, _building_origins(test_db_path, kid_id))
    # Product stacks overlapping 2×2 hit targets. Dispatch the DOM click so
    # selectPlacePos runs. (B) still walks this on a real device.
    page.locator(
        f'.valid-plot[data-px="{picked["px"]}"][data-py="{picked["py"]}"]'
    ).first.dispatch_event("click")
    confirm = bar.get_by_role("button", name="確認建造")
    confirm.wait_for(state="visible", timeout=8000)
    with page.expect_response(
        lambda r: r.request.method == "POST"
        and "/buildings" in r.url
        and "/move" not in r.url
        and "/upgrade" not in r.url
        and "/unstored" not in r.url
    ) as resp_info:
        confirm.click()
    assert resp_info.value.status in (200, 201), resp_info.value.text()
    page.locator(f'.town-building img[alt="{building_name}"]').first.wait_for(
        state="attached", timeout=8000
    )
    after = page.locator(".town-building").count()
    assert after >= before, (
        f"map should gain a building after place; before={before} after={after}"
    )
    visible = _visible_text(page) + (
        page.locator("#toast").inner_text() if page.locator("#toast").count() else ""
    )
    assert building_name in visible or "建築完成" in visible or after > before


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
    page.get_by_text(FE_KID_NAME).first.wait_for(state="visible", timeout=8000)
    page.locator("#hudAv").hover()
    page.locator("#hudAv").dispatch_event("mouseover")
    page.wait_for_function(
        "() => (document.getElementById('hudTip') || {}).innerHTML.includes('臂力')",
        timeout=8000,
    )
    html = page.locator("#hudTip").inner_html()
    assert "臂力" in html, "能力面板應該顯示「臂力」"
    assert "體力" not in html, "唔應該再有「體力」"


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


# ── TC-FE-06: 戰鬥已上線（Boss 成本／confirm；唔再得「即將開放」） ─

@pytest.mark.case_id("TC-FE-06")
def test_battle_lobby_boss_cost_confirm_not_coming_soon(page, base_url, test_db_path):
    """TC-FE-06 戰鬥已上線：無「即將開放」；Boss 顯示 💎 成本；取消 confirm 唔召喚。"""
    _give_gems(test_db_path)
    _login(page, base_url)
    page.get_by_role("button", name="☰").click()
    page.locator("#dr").wait_for(state="visible", timeout=5000)
    assert page.get_by_text("即將開放", exact=False).count() == 0, \
        "戰鬥已上線, 唔應該再顯示「即將開放」"
    page.locator("#dr").get_by_text("探索", exact=False).click()
    battle_tab = page.locator('.exp-type-btn[data-type="battle"]')
    battle_tab.wait_for(state="visible", timeout=8000)
    battle_tab.click()
    page.get_by_text("戰鬥挑戰", exact=False).first.wait_for(state="visible", timeout=8000)
    boss_btn = page.locator("button.exp-btn.go").filter(has_text="Boss").first
    assert boss_btn.is_visible(), "戰鬥挑戰頁應該顯示 Boss 召喚入口"
    assert "💎" in boss_btn.inner_text(), "Boss 按鈕應該顯示素材成本 💎"
    page.once("dialog", lambda d: d.dismiss())
    boss_btn.click()
    page.wait_for_timeout(800)
    assert page.locator(".m-name").count() == 0, "取消 confirm 唔應該召喚 Boss"


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


# ── TC-FE-10: 區域每日戰鬥上限 ────────────────────────────────────

@pytest.mark.case_id("TC-FE-10")
def test_battle_daily_region_limit_blocks_second_start(page, base_url, test_db_path):
    """TC-FE-10 今日已打贏嘅區域再開戰 → API 400，UI 提示今日已打過。"""
    kid_id = _fe_kid_id(test_db_path)
    db = connect_db(test_db_path)
    db.execute(
        "INSERT OR IGNORE INTO daily_battles (kid_id, region_id, battle_date) VALUES (?,?,?)",
        (kid_id, 1, date.today().isoformat()),
    )
    db.commit()
    db.close()
    _login(page, base_url)
    _goto_battle_lobby(page)
    with page.expect_response(
        lambda r: "battle-start" in r.url and r.request.method == "POST"
    ) as resp_info:
        page.locator("button.exp-btn.go").filter(has_text="戰鬥").first.click()
    assert resp_info.value.status == 400, resp_info.value.text()
    data = resp_info.value.json()
    assert "今日" in (data.get("error") or ""), data
    page.locator("#toast").wait_for(state="visible", timeout=8000)
    toast = page.locator("#toast").inner_text()
    assert "今日" in toast, toast
    assert page.locator(".m-name").count() == 0, "每日上限唔應該開到戰鬥"


# ── FE-P0-06: 登出後寫入 API 401 ──────────────────────────────────

@pytest.mark.case_id("FE-P0-06")
def test_logout_then_write_apis_return_401(page, base_url, test_db_path, fe_ids):
    """FE-P0-06 登出後同一瀏覽器 context POST points/adjust/complete → 401。"""
    kid_id = fe_ids["kid_id"]
    before = get_kid_points(test_db_path, kid_id)

    _login(page, base_url)
    _ui_logout(page)
    _assert_write_apis_401(page, base_url, fe_ids)
    assert get_kid_points(test_db_path, kid_id) == before

    _login_parent(page, base_url)
    _ui_logout(page)
    _assert_write_apis_401(page, base_url, fe_ids)
    assert get_kid_points(test_db_path, kid_id) == before


# ── TC-FE-JOURNEY-01: 家長指派 → 小朋友完成 ───────────────────────

@pytest.mark.case_id("TC-FE-JOURNEY-01")
def test_parent_assigns_task_kid_completes_hud_gold(page, base_url, test_db_path, fe_ids):
    """TC-FE-JOURNEY-01 家長建立/指派任務 → 小朋友見到並完成 → HUD 金幣同完成回饋。"""
    kid_id = fe_ids["kid_id"]
    db = connect_db(test_db_path)
    db.execute("DELETE FROM tasks WHERE title LIKE 'JOURNEY-%'")
    db.commit()
    db.close()

    _login_parent(page, base_url)
    page.locator("#mgmtNewKid").wait_for(state="visible", timeout=8000)
    page.wait_for_function(
        """(name) => {
          const sel = document.getElementById('mgmtNewKid');
          return sel && [...sel.options].some(o => (o.textContent || '').includes(name) && o.value);
        }""",
        arg=FE_KID_NAME,
        timeout=8000,
    )
    page.locator("#mgmtNewTitle").fill(JOURNEY_TASK_TITLE)
    page.locator("#mgmtNewPts").fill(str(JOURNEY_TASK_POINTS))
    page.locator("#mgmtNewKid").select_option(value=str(kid_id))
    page.locator("button.create-btn", has_text="新增").first.click()
    page.get_by_text(JOURNEY_TASK_TITLE, exact=False).first.wait_for(state="visible", timeout=8000)

    _login(page, base_url)
    page.locator("button.q", has_text="任務").first.click()
    card = page.locator(".task-card", has_text=JOURNEY_TASK_TITLE).first
    card.wait_for(state="visible", timeout=8000)
    gold_before = int(page.locator("#hudCo").inner_text().strip() or "0")
    card.locator(".task-complete-btn").click()
    page.get_by_text("任務完成", exact=False).first.wait_for(state="visible", timeout=8000)
    page.wait_for_function(
        "(before) => parseInt((document.getElementById('hudCo') || {}).textContent, 10) > before",
        arg=gold_before,
        timeout=8000,
    )
    gold_after = int(page.locator("#hudCo").inner_text().strip() or "0")
    assert gold_after >= gold_before + JOURNEY_TASK_POINTS
    visible = _visible_text(page)
    assert "🪙" in visible or str(JOURNEY_TASK_POINTS) in visible
    db = connect_db(test_db_path)
    row = db.execute(
        "SELECT completed, points FROM tasks WHERE title=?", (JOURNEY_TASK_TITLE,)
    ).fetchone()
    db.close()
    assert row is not None and row["completed"] == 1
    assert get_kid_points(test_db_path, kid_id) == gold_after


# ── FE-XSS-01 / FE-XSS-02: DOM encoding（對應 P0-TC-XSS-*）────────

def _task_title_el(page, needle):
    titles = page.locator("#taskList .task-title")
    titles.first.wait_for(state="visible", timeout=8000)
    for i in range(titles.count()):
        el = titles.nth(i)
        blob = (el.text_content() or "") + (el.inner_html() or "")
        if needle in blob:
            return el
    raise AssertionError(f"task title containing {needle!r} not found")


@pytest.mark.case_id("FE-XSS-01")
def test_task_title_markup_is_plain_text_not_html(page, base_url, test_db_path, fe_ids):
    """FE-XSS-01 任務標題含 markup 時只顯示純文字，唔插入 unsafe innerHTML。

    Maps to P0-TC-XSS-01 DOM. Product encodes titles via escapeHtml() before
    interpolating into task-card innerHTML (textContent shows literal tags).
    """
    kid_id = fe_ids["kid_id"]
    db = connect_db(test_db_path)
    db.execute("DELETE FROM tasks WHERE title LIKE '%粗體%' OR title LIKE '%xss.example.test%'")
    db.execute(
        "INSERT INTO tasks (title, icon, points, kid_id, category, description, recurring, due_date) "
        "VALUES (?, '📝', 5, ?, '', '', '', NULL)",
        (FE_XSS_BOLD_TITLE, kid_id),
    )
    db.execute(
        "INSERT INTO tasks (title, icon, points, kid_id, category, description, recurring, due_date) "
        "VALUES (?, '📝', 5, ?, '', '', '', NULL)",
        (FE_XSS_IMG_TITLE, kid_id),
    )
    db.commit()
    db.close()

    xss_urls = []
    page.route("https://xss.example.test/**", lambda route: route.abort())
    page.on("request", lambda req: xss_urls.append(req.url) if "xss.example.test" in req.url else None)

    _login(page, base_url)
    page.locator("button.q", has_text="任務").first.click()
    bold_el = _task_title_el(page, "粗體")
    text = bold_el.text_content() or ""
    html = bold_el.inner_html() or ""
    assert page.locator("#taskList .task-title b, #taskList .task-title strong").count() == 0, (
        "attacker <b> must not become a real bold element"
    )
    assert "<b>" in text or "&lt;b&gt;" in html, (
        f"tags should show as text; text={text!r} html={html!r}"
    )

    img_el = _task_title_el(page, "xss.example.test")
    assert img_el.locator("img").count() == 0, "task title must not insert an <img> from markup"
    assert page.locator("#taskList .task-title img").count() == 0
    hit = page.evaluate("() => window.__xssHit")
    assert hit != 1, "img onerror must not run"
    assert not any("xss.example.test" in u for u in xss_urls), xss_urls


@pytest.mark.case_id("FE-XSS-02")
def test_kid_display_name_markup_is_plain_text_in_hud(page, base_url, test_db_path):
    """FE-XSS-02 小朋友顯示名含 img onerror 時 HUD 用文字，唔執行 onerror。

    Maps to P0-TC-XSS-02 DOM. HUD #hudNm already uses textContent (partial support).
    """
    db = connect_db(test_db_path)
    row = db.execute(
        "SELECT id FROM kids WHERE username=?", (FE_XSS_KID_USERNAME,)
    ).fetchone()
    db.close()
    if not row:
        insert_kid(
            test_db_path,
            name=FE_XSS_KID_NAME,
            username=FE_XSS_KID_USERNAME,
            pin=TEST_KID_PIN,
            level=5,
            points=0,
        )

    alerts = []
    page.on("dialog", lambda d: (alerts.append(d.message), d.dismiss()))
    _login(page, base_url, username=FE_XSS_KID_USERNAME)
    hud = page.locator("#hudNm")
    hud.wait_for(state="visible", timeout=8000)
    text = hud.text_content() or ""
    assert FE_XSS_KID_NAME in text or "<img" in text, text
    assert hud.locator("img").count() == 0, "HUD name must not create an img from the display name"
    assert hud.locator("b, script").count() == 0
    av_imgs = page.locator("#hudAv img")
    if av_imgs.count():
        src = av_imgs.first.get_attribute("src") or ""
        assert src != "x"
        assert "onerror=alert" not in src
    assert not alerts, alerts


# ── P1-TC-CER-FE-01: ceremony UX (Playwright mock; Phase 1 RED) ──

CEREMONY_TASK_TITLE = "P1-CER-FE-洗碗"


@pytest.mark.phase1
@pytest.mark.case_id("P1-TC-CER-FE-01")
def test_complete_task_ceremony_shows_xp_materials_achievements(
    page, base_url, test_db_path, fe_ids
):
    """P1-TC-CER-FE-01 completeTask 必須顯示 XP／材料／成就，唔只 toast 金幣。

    Playwright mock of POST /api/tasks/<id>/complete returning CER-01 shape.
    This is the automatable (A) UI assert when Chromium is available.
    Source-contract twin: tests/test_frontend_ceremony.py (weak).
    Stronger real-API twin: TC-FE-CEREMONY-01 (no route mock).
    (B) manual checklist still required — do not treat mock/grep as full UX sign-off.
    """
    kid_id = fe_ids["kid_id"]
    db = connect_db(test_db_path)
    db.execute("DELETE FROM tasks WHERE title=?", (CEREMONY_TASK_TITLE,))
    db.execute(
        "INSERT INTO tasks (title, icon, points, kid_id, category, description, recurring, due_date) "
        "VALUES (?, '📝', 10, ?, '', '', '', NULL)",
        (CEREMONY_TASK_TITLE, kid_id),
    )
    db.commit()
    task_id = db.execute(
        "SELECT id FROM tasks WHERE title=?", (CEREMONY_TASK_TITLE,)
    ).fetchone()[0]
    db.close()

    ceremony = {
        "points_awarded": 10,
        "experience_gained": 5,
        "experience_bonus": 2,
        "experience_total": 7,
        "material_drops": ["wood"],
        "achievements": [
            {"badge": "first_task", "title": "第一次任務", "icon": "🌟"}
        ],
        "pending_approval": False,
        "kid": {
            "points": 50,
            "level": 1,
            "experience": 7,
            "experience_in_level": 7,
            "experience_for_next": 25,
        },
    }

    def _fulfill_complete(route):
        url = route.request.url
        if route.request.method == "POST" and f"/api/tasks/{task_id}/complete" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(ceremony),
            )
            return
        route.continue_()

    page.route("**/api/tasks/**", _fulfill_complete)
    _login(page, base_url)
    page.locator("button.q", has_text="任務").first.click()
    card = page.locator(".task-card", has_text=CEREMONY_TASK_TITLE).first
    card.wait_for(state="visible", timeout=8000)
    card.locator(".task-complete-btn").click()
    page.locator("#toast").wait_for(state="visible", timeout=8000)
    visible = _visible_text(page) + (page.locator("#toast").inner_text() or "")
    assert "7" in visible or "XP" in visible or "經驗" in visible or "+2" in visible, (
        f"ceremony UI must show XP (experience_total=7); got {visible!r}"
    )
    assert any(token in visible for token in ("wood", "木材", "🪵")), visible
    assert "🪙" in visible or "10" in visible
    assert any(token in visible for token in ("第一次任務", "🌟", "first_task", "成就")), visible


# ── TC-FE-CEREMONY-01: real complete (no mock) gold + XP + materials ──

@pytest.mark.case_id("TC-FE-CEREMONY-01")
def test_real_task_complete_ceremony_shows_gold_xp_and_materials(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-CEREMONY-01 真實 POST /complete（唔 mock route）後，可見回饋唔只金幣。

    Empty-DB synthetic kid. If product toast is gold-only, this case stays RED
    for the KT builder — do not weaken asserts to fake green.
    """
    kid_id = fe_ids["kid_id"]
    db = connect_db(test_db_path)
    db.execute("DELETE FROM tasks WHERE title=?", (CEREMONY_REAL_TASK_TITLE,))
    db.execute(
        "INSERT INTO tasks (title, icon, points, kid_id, category, description, recurring, due_date) "
        "VALUES (?, '📝', ?, ?, '', '', '', NULL)",
        (CEREMONY_REAL_TASK_TITLE, CEREMONY_REAL_TASK_POINTS, kid_id),
    )
    db.commit()
    db.close()

    _login(page, base_url)
    gold_before = _hud_gold(page)
    mats_before = {mat: _hud_mat_count(page, mat) for mat in ("wood", "brick", "glass", "gear")}

    page.locator("button.q", has_text="任務").first.click()
    card = page.locator(".task-card", has_text=CEREMONY_REAL_TASK_TITLE).first
    card.wait_for(state="visible", timeout=8000)
    with page.expect_response(
        lambda r: r.request.method == "POST" and "/complete" in r.url
    ) as resp_info:
        card.locator(".task-complete-btn").click()
    assert resp_info.value.ok, resp_info.value.text()
    payload = resp_info.value.json()
    awarded = int(payload.get("points_awarded") or 0)
    xp_total = int(payload.get("experience_total") or payload.get("experience_gained") or 0)
    drops = payload.get("material_drops") or []
    assert awarded >= CEREMONY_REAL_TASK_POINTS, payload
    assert xp_total > 0, f"API must award XP; got {payload}"
    assert drops, f"API must drop at least one material; got {payload}"

    page.locator("#toast").wait_for(state="visible", timeout=8000)
    toast = page.locator("#toast").inner_text() or ""
    page.get_by_text("任務完成", exact=False).first.wait_for(state="visible", timeout=8000)
    page.wait_for_function(
        "(before) => parseInt((document.getElementById('hudCo') || {}).textContent, 10) > before",
        arg=gold_before,
        timeout=8000,
    )
    gold_after = _hud_gold(page)
    visible = _visible_text(page) + toast
    blob = toast + visible

    gold_ui = (
        "🪙" in blob
        or str(awarded) in toast
        or gold_after >= gold_before + awarded
    )
    xp_ui = (
        f"XP+{xp_total}" in blob
        or f"XP＋{xp_total}" in blob
        or f"經驗+{xp_total}" in blob
        or f"經驗＋{xp_total}" in blob
        or ("XP" in toast and str(xp_total) in toast)
        or ("經驗" in toast and str(xp_total) in toast)
        or (f"⭐{xp_total}" in toast)
        or (f"⭐XP+{xp_total}" in blob)
    )
    mat_tokens = []
    for drop in drops:
        mat_tokens.extend(MAT_UI_TOKENS.get(drop, (drop,)))
    mat_in_toast = any(token in blob for token in mat_tokens)
    mat_hud_bumped = False
    for drop in drops:
        if drop in mats_before and _hud_mat_count(page, drop) > mats_before[drop]:
            mat_hud_bumped = True
            break
    mat_ui = mat_in_toast or mat_hud_bumped

    assert gold_ui, f"ceremony must show gold; toast={toast!r} hud {gold_before}->{gold_after}"
    assert xp_ui, (
        "ceremony UI must show an XP number (toast/panel), not gold-only. "
        f"experience_total={xp_total}; toast={toast!r}. "
        "Keep this case RED until the product surfaces XP — do not weaken."
    )
    assert mat_ui, (
        "ceremony UI must show a material cue (🪵/wood/木材 or HUD count bump), "
        f"not gold-only. drops={drops}; toast={toast!r}; "
        f"hud_before={mats_before}."
    )


# ── TC-FE-PLACE-SHOP-01 / TC-FE-PLACE-BUILD-01: build → place E2E ──

@pytest.mark.case_id("TC-FE-PLACE-SHOP-01")
def test_shop_build_enters_placement_and_building_appears_on_map(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-PLACE-SHOP-01 商店「建造」→ startPlacement → 點空地 → 地圖出現建築。"""
    kid_id = fe_ids["kid_id"]
    _fund_and_clear_building(test_db_path, kid_id, PLACE_SHOP_BUILDING)
    _login(page, base_url)
    page.locator("button.b", has_text="背包").first.click()
    page.locator("#tab-shop.active").wait_for(state="visible", timeout=8000)
    page.locator("#shopGrid").get_by_text(PLACE_SHOP_BUILDING, exact=False).first.wait_for(
        state="visible", timeout=8000
    )
    _click_build_on_card(page, "#shopGrid", PLACE_SHOP_BUILDING)
    _finish_placement_on_empty_cell(page, PLACE_SHOP_BUILDING, test_db_path, kid_id)
    db = connect_db(test_db_path)
    row = db.execute(
        "SELECT b.id FROM buildings b JOIN building_defs d ON d.id=b.def_id "
        "WHERE b.kid_id=? AND d.name=?",
        (kid_id, PLACE_SHOP_BUILDING),
    ).fetchone()
    db.close()
    assert row is not None, f"{PLACE_SHOP_BUILDING} should be persisted after shop place"


@pytest.mark.case_id("TC-FE-PLACE-BUILD-01")
def test_buildings_tab_build_enters_placement_and_building_appears_on_map(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-PLACE-BUILD-01 建築 tab「建造」→ startPlacement → 點空地 → 地圖出現建築。

    Stronger E2E twin of weak source P1-TC-PLC-FE-01. Product 建築 tab does not
    call st('town'); after 建造 the harness switches to the town tab (same as
    shopBuild). (B) still checks that kids can find the map on a real device.
    """
    kid_id = fe_ids["kid_id"]
    _fund_and_clear_building(test_db_path, kid_id, PLACE_TAB_BUILDING)
    _login(page, base_url)
    drawer = _open_drawer(page)
    drawer.get_by_text("建築管理", exact=False).click()
    page.locator("#tab-buildings.active").wait_for(state="visible", timeout=8000)
    page.locator("#availableBuildingsList").get_by_text(
        PLACE_TAB_BUILDING, exact=False
    ).first.wait_for(state="visible", timeout=8000)
    _click_build_on_card(page, "#availableBuildingsList", PLACE_TAB_BUILDING)
    _finish_placement_on_empty_cell(page, PLACE_TAB_BUILDING, test_db_path, kid_id)
    db = connect_db(test_db_path)
    row = db.execute(
        "SELECT b.id FROM buildings b JOIN building_defs d ON d.id=b.def_id "
        "WHERE b.kid_id=? AND d.name=?",
        (kid_id, PLACE_TAB_BUILDING),
    ).fetchone()
    db.close()
    assert row is not None, f"{PLACE_TAB_BUILDING} should be persisted after 建築 tab place"


# ── TC-FE-TOWN-UX / HIT / MOTION: four-scene town build (red on main) ──
#
# Design: mock tip 3b4671d (PR #27, do not merge). Product /kids/ town home
# does not have this sheet flow yet. These cases must stay red until a builder
# lands 「我要起屋」→ 建築清單 → 擺位置 → 升級. Do not satisfy them with the
# old #placementBar path (TC-FE-PLACE-SHOP-01 / TC-FE-PLACE-BUILD-01 stay).

TOWN_UX_RED = (
    "Missing four-scene town build UX on /kids/ town home "
    "(design mock tip 3b4671d / PR #27, do not merge). "
    "The old shop／建築 #placementBar flow is a different case and does not pass this one. "
    "Builder work: land the sheet flow before turning this green."
)
TOWN_UX_SEED = (("商店", 0, 2), ("圖書館", 2, 1), ("農場", 4, 0))
TOWN_UX_UNBUILT = "健身室"
_PAD_LABEL = re.compile(r"第\s*(\d+)\s*欄第\s*(\d+)\s*行")
_PAD_PROBE_JS = r"""
() => {
  const buttons = [...document.querySelectorAll('button')].filter((btn) => {
    const label = btn.getAttribute('aria-label') || btn.textContent || '';
    return /第\s*\d+\s*欄/.test(label);
  });
  const goldish = (el) => {
    if (!el) return false;
    const cs = getComputedStyle(el);
    const blob = [
      cs.borderTopColor, cs.borderColor, cs.boxShadow, cs.outlineColor,
      cs.backgroundColor, el.className || ''
    ].join(' ');
    return /212,\s*160,\s*23|240,\s*193,\s*75|d4a017|f0c14b/i.test(blob);
  };
  let empty = 0;
  let framed = 0;
  for (const btn of buttons) {
    const label = btn.getAttribute('aria-label') || '';
    if (!/空地/.test(label)) continue;
    empty += 1;
    const pad = btn.closest('.pad') || btn.parentElement;
    const mark = pad && pad.querySelector('.mark, .focus-ring');
    let markShown = false;
    if (mark && !mark.hidden) {
      const cs = getComputedStyle(mark);
      markShown = cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
    }
    if (goldish(pad) || goldish(mark) || goldish(btn) || markShown) framed += 1;
  }
  return {count: buttons.length, empty, framed};
}
"""
_OCCLUSION_JS = r"""
() => {
  const parse = (label) => {
    const m = /第\s*(\d+)\s*欄第\s*(\d+)\s*行/.exec(label || '');
    return m ? {c: Number(m[1]), r: Number(m[2])} : null;
  };
  const buttons = [...document.querySelectorAll('button')].map((btn) => {
    const label = btn.getAttribute('aria-label') || '';
    const pos = parse(label);
    if (!pos) return null;
    const pad = btn.closest('.pad') || btn.parentElement;
    const sprite = pad && pad.querySelector('img.sprite, .sprite');
    let spriteBox = null;
    if (sprite && !sprite.hidden) {
      const cs = getComputedStyle(sprite);
      const box = sprite.getBoundingClientRect();
      if (cs.display !== 'none' && box.width > 2 && box.height > 2) {
        spriteBox = {left: box.left, top: box.top, right: box.right, bottom: box.bottom};
      }
    }
    const box = btn.getBoundingClientRect();
    return {
      label,
      pos,
      empty: /空地/.test(label),
      sprite: spriteBox,
      left: box.left,
      top: box.top,
      width: box.width,
      height: box.height
    };
  }).filter(Boolean);
  const contains = (rect, x, y) => x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  for (const back of buttons) {
    if (!back.empty || back.width < 2) continue;
    for (let i = 1; i <= 3; i += 1) {
      for (let j = 1; j <= 3; j += 1) {
        const x = back.left + (back.width * i) / 4;
        const y = back.top + (back.height * j) / 4;
        for (const front of buttons) {
          if (front.empty || !front.sprite) continue;
          if (front.pos.c === back.pos.c && front.pos.r === back.pos.r) continue;
          if (back.pos.r >= front.pos.r) continue;
          if (!contains(front.sprite, x, y)) continue;
          return {x, y, back: back.label, front: front.label, c: back.pos.c, r: back.pos.r};
        }
      }
    }
  }
  return null;
}
"""


def _town_ux_fail(case_id, detail):
    pytest.fail(f"{case_id}: {detail} {TOWN_UX_RED}")


def _role_visible(page, role, name):
    loc = page.get_by_role(role, name=name)
    try:
        return loc.count() > 0 and loc.first.is_visible()
    except Exception:
        return False


def _seed_town_ux_plot(test_db_path, kid_id):
    """Library / farm / shop on the map; gym unbuilt; HUD can afford a place and an upgrade.

    Balances are whatever the product HUD shows after this seed. Cases assert
    equality and deltas, not the mock demo purse (💰6000 → 5800 → 5750).
    """
    set_kid_points(test_db_path, kid_id, 8000)
    grant_inventory(
        test_db_path,
        kid_id,
        {"wood": 400, "brick": 300, "glass": 40, "gear": 120, "gem": 20},
    )
    db = connect_db(test_db_path)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    for name, cell_x, cell_y in TOWN_UX_SEED:
        insert_building(
            test_db_path,
            kid_id,
            building_def_id(test_db_path, name),
            level=1,
            cell_x=cell_x,
            cell_y=cell_y,
        )


def _open_town_home(page, base_url):
    _login(page, base_url)
    page.locator("body.kt-artstage #tab-town.active").wait_for(state="visible", timeout=8000)
    page.locator("#townCanvasWrapper, #townMap, #village").first.wait_for(
        state="visible", timeout=8000
    )
    page.wait_for_function(
        "() => parseInt((document.getElementById('hudCo') || {}).textContent, 10) > 0",
        timeout=8000,
    )
    try:
        page.locator("#tab-town .town-building img, #tab-town .sprite, #tab-town .pad").first.wait_for(
            state="attached", timeout=8000
        )
    except Exception:
        pass


def _hud_snapshot(page):
    return {
        "gold": _hud_gold(page),
        "wood": _hud_mat_count(page, "wood"),
        "brick": _hud_mat_count(page, "brick"),
        "glass": _hud_mat_count(page, "glass"),
        "gear": _hud_mat_count(page, "gear"),
    }


def _assert_hud_equal(before, after, case_id, why):
    assert after == before, (
        f"{case_id}: {why} HUD must stay {before}, got {after}. "
        "Cancel and browsing empty pads never deduct."
    )


def _assert_hud_deducted(before, after, case_id, why):
    assert all(after[key] <= before[key] for key in before), (
        f"{case_id}: {why} must not increase HUD resources; {before} -> {after}"
    )
    assert any(after[key] < before[key] for key in before), (
        f"{case_id}: {why} must deduct at least one HUD resource (gold or material); "
        f"{before} -> {after}. Read the chips; do not hard-code the mock demo purse."
    )


def _toast_text(page):
    parts = []
    for sel in ("#toast", "[role=status]"):
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        try:
            text = loc.first.inner_text() or ""
        except Exception:
            text = ""
        if text.strip():
            parts.append(text.strip())
    return " ".join(parts)


def _pad_probe(page):
    return page.evaluate(_PAD_PROBE_JS)


def _stage_metrics(page):
    stage = page.locator("body.kt-artstage .gsw").first
    if stage.count() == 0:
        return {"w": 0, "h": 0, "rw": 0.0, "rh": 0.0}
    return stage.evaluate(
        """(el) => {
          const rect = el.getBoundingClientRect();
          return {w: el.offsetWidth, h: el.offsetHeight, rw: rect.width, rh: rect.height};
        }"""
    )


def _require_build_cta(page, case_id, detail):
    if _role_visible(page, "button", "我要起屋"):
        return page.get_by_role("button", name="我要起屋").first
    _town_ux_fail(case_id, detail + " Entry CTA 「我要起屋」 is not on the town home.")
    return None


def _building_on_town(page, name):
    labels = _iso_pad_labels(page)
    if any(name in label for label in labels):
        return True
    img = page.locator(f'#tab-town .pad img[alt="{name}"], #townMap img[alt="{name}"], #village img[alt="{name}"]')
    try:
        if img.count() > 0 and img.first.is_visible():
            return True
    except Exception:
        pass
    return False


def _iso_pad_labels(page):
    """Accessible names on the iso scene map only. Legacy .town-building and the footer do not count."""
    return page.evaluate(
        """() => [...document.querySelectorAll(
          '#townMap .pad button, #village .pad button, .village.is-iso .pad button, #townMap .cap, #village .cap, .village.is-iso .cap'
        )].map((el) => (el.getAttribute('aria-label') || el.textContent || '').trim()).filter(Boolean)"""
    )


def _motion_store(page):
    return page.evaluate(
        """() => Object.fromEntries(
          Object.keys(localStorage)
            .filter((key) => key.toLowerCase().includes('motion'))
            .map((key) => [key, localStorage.getItem(key)])
        )"""
    )


def _open_building_list(page):
    heading = page.get_by_role("heading", name="建築清單")
    if heading.count() > 0 and heading.first.is_visible():
        return
    launcher = page.get_by_role("button", name=re.compile(r"建築清單"))
    if launcher.count() == 0 or not launcher.first.is_visible():
        _town_ux_fail(
            "TC-FE-TOWN-UX-02",
            "Scene 2 must show a 「建築清單」 launcher or an open list after 「我要起屋」.",
        )
    launcher.first.click()
    page.get_by_role("heading", name="建築清單").first.wait_for(state="visible", timeout=8000)


def _go_place_button(page):
    return page.get_by_role("button", name=re.compile(r"去擺位置"))


def _enter_scene2(page, case_id, detail=None):
    cta = _require_build_cta(
        page,
        case_id,
        detail
        or "Scene 2 must open from 「我要起屋」: gold frames on empty pads, a building list that marks built ones 「已起」, and 「去擺位置」 disabled until a free pad and an unbuilt building are chosen.",
    )
    cta.click()
    page.get_by_role("button", name=re.compile(r"第\s*\d+\s*欄")).first.wait_for(
        state="visible", timeout=8000
    )


def _pick_pad_and_unbuilt(page):
    """Select one empty pad and 健身室 so 「去擺位置」 can enable."""
    empty = page.get_by_role("button", name=re.compile(r"空地"))
    if empty.count() == 0:
        _town_ux_fail("TC-FE-TOWN-UX-02", "Scene 2 has no empty-pad button (accessible name contains 空地).")
    empty.first.click()
    _open_building_list(page)
    gym = page.get_by_role("button", name=re.compile(rf"{TOWN_UX_UNBUILT}"))
    picked = None
    for i in range(gym.count()):
        btn = gym.nth(i)
        label = (btn.get_attribute("aria-label") or "") + (btn.inner_text() or "")
        if "已起" in label:
            continue
        if btn.is_visible():
            picked = btn
            break
    if picked is None:
        _town_ux_fail(
            "TC-FE-TOWN-UX-02",
            f"Building list must offer unbuilt {TOWN_UX_UNBUILT} (not marked 已起).",
        )
    picked.click()


def _enter_scene3(page, case_id, detail=None):
    _enter_scene2(
        page,
        case_id,
        detail
        or "Scene 3 擺位置 needs the sheet flow (semi-transparent preview, move, blocked occupied pad, 取消 without deduct, 確定 deducts).",
    )
    probe = _pad_probe(page)
    assert probe["empty"] > 0 and probe["framed"] == probe["empty"], (
        f"{case_id}: scene 2 empty pads must all show a gold frame "
        f"(empty={probe['empty']} framed={probe['framed']}). "
        "Scene 1 must not be left glowing."
    )
    go = _go_place_button(page)
    if go.count() == 0 or not go.first.is_visible():
        _town_ux_fail(case_id, "Scene 2 must show 「去擺位置」.")
    assert go.first.is_disabled(), (
        f"{case_id}: 「去擺位置」 stays disabled until a free pad and an unbuilt building are both chosen."
    )
    _pick_pad_and_unbuilt(page)
    assert go.first.is_enabled(), (
        f"{case_id}: 「去擺位置」 enables only after a free pad and unbuilt {TOWN_UX_UNBUILT} are chosen."
    )
    go.first.click()
    page.get_by_role("button", name=re.compile(r"取消")).first.wait_for(state="visible", timeout=8000)


def _preview_opacity(page):
    return page.evaluate(
        """() => {
          const nodes = [...document.querySelectorAll(
            '#tab-town .ghost, #townMap .ghost, #village .ghost, .pad.is-preview .ghost, .pad.is-preview img'
          )];
          for (const img of nodes) {
            if (img.hidden) continue;
            const cs = getComputedStyle(img);
            if (cs.display === 'none' || cs.visibility === 'hidden') continue;
            const opacity = parseFloat(cs.opacity);
            if (opacity < 0.95) return opacity;
          }
          return null;
        }"""
    )


def _sheet_level(page):
    sheet = page.locator(
        "#actionSheet, .action-sheet, [aria-label*='升級或打開功能']"
    ).first
    if sheet.count() == 0 or not sheet.is_visible():
        return None, ""
    text = sheet.inner_text() or ""
    nums = [int(n) for n in re.findall(r"Lv\.?\s*(\d+)", text)]
    return (nums[0] if nums else None), text


def _placed_names(test_db_path, kid_id):
    db = connect_db(test_db_path)
    rows = db.execute(
        "SELECT d.name FROM buildings b JOIN building_defs d ON d.id=b.def_id "
        "WHERE b.kid_id=? AND COALESCE(b.stored, 0)=0",
        (kid_id,),
    ).fetchall()
    db.close()
    return [r["name"] for r in rows]


@pytest.mark.case_id("TC-FE-TOWN-UX-01")
def test_town_ux_scene1_map_cta_and_empty_pad_does_not_spend(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-01 場景 1：真實資料嘅已起屋出現喺等角地圖，空地唔發光，我要起屋，點空地唔扣。"""
    kid_id = fe_ids["kid_id"]
    _seed_town_ux_plot(test_db_path, kid_id)
    _open_town_home(page, base_url)
    missing = []
    stage = _stage_metrics(page)
    if stage["w"] != 1280 or stage["h"] != 720:
        missing.append(f"art-stage layout {stage['w']}×{stage['h']} (want 1280×720)")
    labels = _iso_pad_labels(page)
    placed_blob = "\n".join(labels)
    for name, _x, _y in TOWN_UX_SEED:
        if name not in placed_blob:
            missing.append(f"scene-1 iso map missing real placed {name}")
    if any(TOWN_UX_UNBUILT in label and "空地" not in label for label in labels):
        missing.append(f"unplaced {TOWN_UX_UNBUILT} must not show as a scene-1 building")
    if not _role_visible(page, "button", "我要起屋"):
        missing.append("CTA 「我要起屋」")
    probe = _pad_probe(page)
    if probe["count"] == 0 or probe["empty"] == 0:
        missing.append("iso empty pads（button「第 N 欄第 M 行…空地」）")
    elif probe["framed"] != 0:
        missing.append(f"scene 1 empty pads must not glow (framed={probe['framed']})")
    if missing:
        _town_ux_fail(
            "TC-FE-TOWN-UX-01",
            "Scene 1 睇地圖 must show placed buildings from the kid's real data "
            "(seeded 圖書館／農場／商店 on the iso map; unplaced 健身室 must not appear as built). "
            "Legacy .town-building sprites and the footer 「商店」 tab do not count. "
            "Also quiet empty pads (no gold frames) and CTA 「我要起屋」. "
            "Tapping an empty pad must not deduct HUD resources. "
            f"Missing: {', '.join(missing)}.",
        )
    before = _hud_snapshot(page)
    page.get_by_role("button", name=re.compile(r"空地")).first.click()
    page.wait_for_timeout(600)
    _assert_hud_equal(
        before,
        _hud_snapshot(page),
        "TC-FE-TOWN-UX-01",
        "tapping an empty pad in scene 1",
    )
    assert TOWN_UX_UNBUILT not in _placed_names(test_db_path, kid_id)


@pytest.mark.case_id("TC-FE-TOWN-UX-02")
def test_town_ux_scene2_gold_pads_and_building_list(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-02 場景 2：金框空地、清單「已起」、揀齊先至「去擺位置」。"""
    _seed_town_ux_plot(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    _enter_scene2(page, "TC-FE-TOWN-UX-02")
    probe = _pad_probe(page)
    assert probe["empty"] > 0 and probe["framed"] == probe["empty"], (
        "TC-FE-TOWN-UX-02: after 「我要起屋」, every empty pad shows a gold frame. "
        f"empty={probe['empty']} framed={probe['framed']}. {TOWN_UX_RED}"
    )
    go = _go_place_button(page)
    if go.count() == 0 or not go.first.is_visible():
        _town_ux_fail("TC-FE-TOWN-UX-02", "Scene 2 must show 「去擺位置」.")
    assert go.first.is_disabled(), (
        "TC-FE-TOWN-UX-02: 「去擺位置」 is disabled before a pad and an unbuilt building are chosen."
    )
    _open_building_list(page)
    built_marks = page.get_by_text("已起", exact=False)
    assert built_marks.count() >= 3, (
        "TC-FE-TOWN-UX-02: the building list marks buildings that are already up with 「已起」 "
        f"(saw {built_marks.count()})."
    )
    for name, _x, _y in TOWN_UX_SEED:
        marked = page.get_by_role("button", name=re.compile(rf"{name}[\s\S]*已起|已起[\s\S]*{name}"))
        assert marked.count() > 0, f"TC-FE-TOWN-UX-02: {name} must be marked 已起"
    _pick_pad_and_unbuilt(page)
    assert go.first.is_enabled(), (
        "TC-FE-TOWN-UX-02: 「去擺位置」 enables only after a free pad and an unbuilt building are chosen."
    )


@pytest.mark.case_id("TC-FE-TOWN-UX-03")
def test_town_ux_scene3_cancel_does_not_deduct(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-03 場景 3：半透明預覽、可搬去空地、佔用格擋住、取消唔扣。"""
    kid_id = fe_ids["kid_id"]
    _seed_town_ux_plot(test_db_path, kid_id)
    _open_town_home(page, base_url)
    _enter_scene3(
        page,
        "TC-FE-TOWN-UX-03",
        "Scene 3 取消 must leave HUD unchanged and toast 「已取消，資源未扣除」 after a semi-transparent preview that can move, while an occupied pad stays blocked.",
    )
    opacity = _preview_opacity(page)
    assert opacity is not None and opacity < 0.95, (
        "TC-FE-TOWN-UX-03: scene 3 must show a semi-transparent placement preview "
        f"(ghost opacity={opacity}). {TOWN_UX_RED}"
    )
    before = _hud_snapshot(page)
    other = page.get_by_role("button", name=re.compile(r"可以放|空地"))
    moved = False
    for i in range(min(other.count(), 8)):
        btn = other.nth(i)
        label = btn.get_attribute("aria-label") or ""
        if "預覽" in label or not btn.is_visible():
            continue
        btn.click()
        moved = True
        break
    assert moved, "TC-FE-TOWN-UX-03: scene 3 must allow moving the preview onto another empty pad."
    page.wait_for_timeout(400)
    _assert_hud_equal(before, _hud_snapshot(page), "TC-FE-TOWN-UX-03", "moving the preview")
    occupied = page.locator("#townMap, #village, #tab-town").get_by_role(
        "button", name=re.compile(r"圖書館")
    )
    assert occupied.count() > 0, "TC-FE-TOWN-UX-03: occupied 圖書館 pad must be tappable in scene 3."
    occupied.first.click()
    page.wait_for_timeout(400)
    blocked = _toast_text(page)
    assert ("唔可以" in blocked) or ("已經有" in blocked), (
        "TC-FE-TOWN-UX-03: an occupied pad is blocked "
        f"(toast should say 唔可以放 / 已經有). toast={blocked!r}"
    )
    _assert_hud_equal(before, _hud_snapshot(page), "TC-FE-TOWN-UX-03", "tapping an occupied pad")
    page.get_by_role("button", name=re.compile(r"^取消$|取消")).first.click()
    try:
        page.wait_for_function(
            """() => {
              const node = document.getElementById('toast');
              const text = (node && (node.innerText || node.textContent)) || '';
              return text.includes('已取消') && text.includes('未扣除');
            }""",
            timeout=4000,
        )
    except Exception:
        _town_ux_fail(
            "TC-FE-TOWN-UX-03",
            "取消 must toast like 「已取消，資源未扣除」 "
            f"(got {_toast_text(page)!r}) and return without placing.",
        )
    page.wait_for_timeout(400)
    _assert_hud_equal(before, _hud_snapshot(page), "TC-FE-TOWN-UX-03", "cancel")
    assert TOWN_UX_UNBUILT not in _placed_names(test_db_path, kid_id), (
        "TC-FE-TOWN-UX-03: cancel must not persist the building."
    )


@pytest.mark.case_id("TC-FE-TOWN-UX-04")
def test_town_ux_scene3_confirm_deducts_and_opens_sheet(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-04 場景 3 確定：扣 HUD、座落建築、打開場景 4。"""
    kid_id = fe_ids["kid_id"]
    _seed_town_ux_plot(test_db_path, kid_id)
    _open_town_home(page, base_url)
    _enter_scene3(
        page,
        "TC-FE-TOWN-UX-04",
        "Scene 3 確定 must deduct HUD resources, place the building, and open the scene 4 upgrade sheet.",
    )
    before = _hud_snapshot(page)
    confirm = page.get_by_role("button", name=re.compile(r"確定"))
    if confirm.count() == 0 or not confirm.first.is_visible():
        _town_ux_fail("TC-FE-TOWN-UX-04", "Scene 3 must show 「確定」／「確定放置」.")
    assert confirm.first.is_enabled(), "TC-FE-TOWN-UX-04: 確定 is enabled when the preview pad is free and affordable."
    confirm.first.click()
    try:
        page.wait_for_function(
            """(goldBefore) => {
              const el = document.getElementById('hudCo');
              if (!el) return false;
              const gold = parseInt(el.textContent, 10);
              return Number.isFinite(gold) && gold < goldBefore;
            }""",
            arg=before["gold"],
            timeout=8000,
        )
    except Exception:
        after = _hud_snapshot(page)
        _town_ux_fail(
            "TC-FE-TOWN-UX-04",
            "確定 must deduct resources and update the header chips "
            f"(HUD {before} -> {after}).",
        )
    after = _hud_snapshot(page)
    _assert_hud_deducted(before, after, "TC-FE-TOWN-UX-04", "confirm place")
    assert _building_on_town(page, TOWN_UX_UNBUILT), (
        f"TC-FE-TOWN-UX-04: {TOWN_UX_UNBUILT} must appear on the town map after 確定."
    )
    assert TOWN_UX_UNBUILT in _placed_names(test_db_path, kid_id)
    upgrade = page.get_by_role("button", name=re.compile(r"升級"))
    try:
        upgrade.first.wait_for(state="visible", timeout=8000)
    except Exception:
        _town_ux_fail(
            "TC-FE-TOWN-UX-04",
            "After 確定, scene 4 must open (upgrade／feature sheet visible).",
        )


@pytest.mark.case_id("TC-FE-TOWN-UX-05")
def test_town_ux_scene4_upgrade_feature_and_hud(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-05 場景 4：升級加等級並扣資源；功能掣有可見結果；HUD 跟上。"""
    kid_id = fe_ids["kid_id"]
    _seed_town_ux_plot(test_db_path, kid_id)
    _open_town_home(page, base_url)
    _enter_scene3(
        page,
        "TC-FE-TOWN-UX-05",
        "Scene 4 must raise the building level, deduct the upgrade from the HUD, and show a visible result from a feature button.",
    )
    page.get_by_role("button", name=re.compile(r"確定")).first.click()
    upgrade = page.get_by_role("button", name=re.compile(r"升級"))
    try:
        upgrade.first.wait_for(state="visible", timeout=8000)
    except Exception:
        _town_ux_fail("TC-FE-TOWN-UX-05", "Scene 4 upgrade control did not open after place.")
    level_before, _sheet_before = _sheet_level(page)
    assert level_before is not None, (
        "TC-FE-TOWN-UX-05: the upgrade sheet must show a level (Lv.N)."
    )
    hud_before = _hud_snapshot(page)
    upgrade.first.click()
    try:
        page.wait_for_function(
            """(prev) => {
              const sheet = document.querySelector(
                '#actionSheet, .action-sheet, [aria-label*="升級或打開功能"]'
              );
              if (!sheet) return false;
              const match = (sheet.innerText || '').match(/Lv\\.?\\s*(\\d+)/);
              return match && Number(match[1]) > prev;
            }""",
            arg=level_before,
            timeout=8000,
        )
    except Exception:
        level_after, text = _sheet_level(page)
        _town_ux_fail(
            "TC-FE-TOWN-UX-05",
            f"Upgrade must raise the sheet level above Lv.{level_before} "
            f"(saw {level_after}, sheet={text!r}).",
        )
    hud_after = _hud_snapshot(page)
    _assert_hud_deducted(hud_before, hud_after, "TC-FE-TOWN-UX-05", "upgrade")
    opener = page.get_by_role("button", name=re.compile(r"打開功能"))
    if opener.count() and opener.first.is_visible() and opener.first.is_enabled():
        opener.first.click()
    sheet = page.locator("#actionSheet, .action-sheet, [aria-label*='升級或打開功能']").first
    skip = re.compile(r"升級|打開功能|取消|確定|返去|收起|我要起屋|去擺位置|動畫|重置|已起")
    feature = None
    buttons = sheet.get_by_role("button")
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        label = ((btn.inner_text() or "") + " " + (btn.get_attribute("aria-label") or "")).strip()
        if skip.search(label) or not btn.is_visible() or not btn.is_enabled():
            continue
        feature = btn
        break
    if feature is None:
        _town_ux_fail(
            "TC-FE-TOWN-UX-05",
            "Scene 4 must expose at least one feature button with a visible result.",
        )
    before_blob = (sheet.inner_text() or "") + _toast_text(page)
    feature.click()
    page.wait_for_timeout(500)
    after_blob = (sheet.inner_text() or "") + _toast_text(page)
    assert after_blob != before_blob and len(after_blob.strip()) > 0, (
        "TC-FE-TOWN-UX-05: the feature button must show a visible result "
        f"(sheet/toast unchanged: {after_blob!r})."
    )
    assert _hud_snapshot(page) == hud_after, (
        "TC-FE-TOWN-UX-05: header chips stay on the post-upgrade balance after the feature result "
        f"(want {hud_after}, got {_hud_snapshot(page)})."
    )


@pytest.mark.case_id("TC-FE-TOWN-HIT-01")
def test_town_ux_hit_back_pad_not_front_sprite(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-HIT-01 背面格被前面建築遮住時，撳落去選背面格，唔係棟建築。

    Runs at the letterboxed 1100×800 viewport and again at 1280×720.
    """
    _seed_town_ux_plot(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    if _pad_probe(page)["count"] == 0:
        stage = _stage_metrics(page)
        _town_ux_fail(
            "TC-FE-TOWN-HIT-01",
            "Iso hit-test needs pad buttons 「第 N 欄第 M 行」. "
            "A tap on a back-row diamond covered by a front building sprite "
            "must select that back pad, not the sprite, at viewport 1100×800 "
            f"(stage layout {stage['w']}×{stage['h']}, visual {stage['rw']:.1f}×{stage['rh']:.1f}) "
            "and at 1280×720. "
            "Do not use the old .valid-plot / .town-building stack as a stand-in.",
        )
    _enter_scene2(
        page,
        "TC-FE-TOWN-HIT-01",
        "Back-row diamond occluded by a front building must win the hit test at 1100×800 and 1280×720.",
    )
    for width, height in ((1100, 800), (1280, 720)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(200)
        hit = page.evaluate(_OCCLUSION_JS)
        if not hit:
            _town_ux_fail(
                "TC-FE-TOWN-HIT-01",
                f"No back empty pad is visually covered by a front building sprite at {width}×{height}. "
                "Seed is 商店 (0,2), 圖書館 (2,1), 農場 (4,0). "
                "The occluded back pad must win the hit test.",
            )
        page.mouse.click(hit["x"], hit["y"])
        chosen = page.get_by_role(
            "button",
            name=re.compile(rf"第\s*{hit['c']}\s*欄第\s*{hit['r']}\s*行[\s\S]*已揀"),
        )
        assert chosen.count() > 0 and chosen.first.is_visible(), (
            "TC-FE-TOWN-HIT-01: the click on the occluded point must select back pad "
            f"第 {hit['c']} 欄第 {hit['r']} 行 (已揀) at {width}×{height}, "
            f"not the front building {hit['front']!r}."
        )


@pytest.mark.case_id("TC-FE-TOWN-HIT-02")
def test_town_ux_letterbox_pad_hit_alignment(page, base_url, test_db_path, fe_ids):
    """TC-FE-TOWN-HIT-02 1100×800 同 1280×720 信箱下，撳格視覺中心仍然選中嗰格。"""
    _seed_town_ux_plot(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    assert page.viewport_size["width"] == 1100
    assert page.viewport_size["height"] == 800
    stage = _stage_metrics(page)
    if _pad_probe(page)["count"] == 0:
        _town_ux_fail(
            "TC-FE-TOWN-HIT-02",
            "Letterbox pad alignment needs iso pad hit targets at viewport 1100×800 "
            "and at 1280×720. "
            f"Current viewport is 1100×800; art-stage layout is {stage['w']}×{stage['h']} "
            f"(visual {stage['rw']:.1f}×{stage['rh']:.1f}). "
            "A 1280×720 scaled stage alone does not pass: the click at a pad's "
            "visual center must select that pad, not a neighbor.",
        )
    _enter_scene2(
        page,
        "TC-FE-TOWN-HIT-02",
        "Pad visual-center hits must stay on that pad at 1100×800 and 1280×720.",
    )
    for width, height in ((1100, 800), (1280, 720)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(200)
        stage = _stage_metrics(page)
        scale = min(width / 1280, height / 720)
        assert stage["w"] == 1280 and stage["h"] == 720, stage
        assert abs(stage["rw"] - 1280 * scale) < 2, stage
        assert abs(stage["rh"] - 720 * scale) < 2, stage
        target = page.get_by_role("button", name=re.compile(r"空地")).first
        label = target.get_attribute("aria-label") or ""
        match = _PAD_LABEL.search(label)
        assert match, f"TC-FE-TOWN-HIT-02: empty pad label missing 欄/行 at {width}×{height}: {label!r}"
        box = target.bounding_box()
        assert box, f"TC-FE-TOWN-HIT-02: empty pad has no box at {width}×{height}"
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        chosen = page.get_by_role(
            "button",
            name=re.compile(
                rf"第\s*{match.group(1)}\s*欄第\s*{match.group(2)}\s*行[\s\S]*已揀"
            ),
        )
        assert chosen.count() > 0, (
            "TC-FE-TOWN-HIT-02: clicking the pad's visual center under letterbox scale "
            f"at {width}×{height} must select 第 {match.group(1)} 欄第 {match.group(2)} 行, "
            "not a neighbor."
        )


_SHADOW_PROBE_JS = r"""
() => {
  const pads = [...document.querySelectorAll('.village.is-iso .pad, #village .pad, #townMap .pad')];
  const out = [];
  for (const pad of pads) {
    const btn = pad.querySelector('button');
    const label = (btn && (btn.getAttribute('aria-label') || '')) || '';
    const shadow = pad.querySelector(':scope > .shadow, :scope > [data-contact-shadow]');
    if (!shadow || shadow.hidden) continue;
    const cs = getComputedStyle(shadow);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const sbox = shadow.getBoundingClientRect();
    const pbox = pad.getBoundingClientRect();
    if (sbox.width < 2 || sbox.height < 2) continue;
    const bg = (cs.backgroundImage || '') + ' ' + (cs.background || '');
    out.push({
      label,
      w: sbox.width,
      h: sbox.height,
      filter: cs.filter || '',
      bg,
      overflow: getComputedStyle(pad).overflow,
      crosses: sbox.left < pbox.left - 0.5 || sbox.right > pbox.right + 0.5,
      pe: cs.pointerEvents
    });
  }
  return out;
}
"""


def _assert_soft_oval_shadows(page, width, height):
    shadows = page.evaluate(_SHADOW_PROBE_JS)
    assert shadows, (
        f"TC-FE-TOWN-HIT-03: placed buildings need a visible contact shadow at {width}×{height}."
    )
    blob = " ".join(item["label"] for item in shadows)
    for name, _x, _y in TOWN_UX_SEED:
        assert name in blob, (
            f"TC-FE-TOWN-HIT-03: real placed {name} has no contact shadow at {width}×{height}."
        )
    for shadow in shadows:
        assert shadow["w"] > shadow["h"] * 1.3, (
            f"TC-FE-TOWN-HIT-03: contact shadow must be a wide oval at {width}×{height}: {shadow}"
        )
        assert re.search(r"radial-gradient", shadow["bg"], re.I) and re.search(r"ellipse", shadow["bg"], re.I), (
            f"TC-FE-TOWN-HIT-03: contact shadow must be a soft radial ellipse at {width}×{height}: {shadow['bg']!r}"
        )
        assert "blur" in shadow["filter"] or re.search(r"rgba\([^)]*,\s*0(?:\.0+)?\)", shadow["bg"]), (
            f"TC-FE-TOWN-HIT-03: contact shadow must fade softly (blur or transparent edge): {shadow}"
        )
        assert shadow["crosses"], (
            f"TC-FE-TOWN-HIT-03: the oval must cross the pad seam onto the neighbor plot: {shadow}"
        )
        assert shadow["overflow"] == "visible", shadow
        assert shadow["pe"] == "none", shadow


@pytest.mark.case_id("TC-FE-TOWN-HIT-03")
def test_town_ux_hit_soft_oval_contact_shadows(page, base_url, test_db_path, fe_ids):
    """TC-FE-TOWN-HIT-03 已起屋有軟橢圓接觸陰影，信箱 1100×800 同 1280×720 都仲係橢圓。"""
    _seed_town_ux_plot(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    stage = _stage_metrics(page)
    if not page.evaluate(_SHADOW_PROBE_JS):
        _town_ux_fail(
            "TC-FE-TOWN-HIT-03",
            "Placed buildings on the iso map need a soft oval contact shadow "
            "(radial-gradient ellipse, blurred, wider than the pad so it crosses the seam, "
            "pointer-events none). "
            f"Checked under the 1100×800 letterbox (stage layout {stage['w']}×{stage['h']}, "
            f"visual {stage['rw']:.1f}×{stage['rh']:.1f}) and it must still hold at viewport 1280×720. "
            "The legacy town map does not draw this contact shadow.",
        )
    for width, height in ((1100, 800), (1280, 720)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(200)
        _assert_soft_oval_shadows(page, width, height)


def _wait_visible_gold_stars(page, selector):
    page.wait_for_function(
        """(sel) => [...document.querySelectorAll(sel)].some((el) => {
          const cs = getComputedStyle(el);
          const box = el.getBoundingClientRect();
          return cs.display !== 'none' && cs.visibility !== 'hidden'
            && box.width > 1 && box.height > 1
            && parseFloat(cs.opacity) > 0.35;
        })""",
        arg=selector,
        timeout=4000,
    )


@pytest.mark.case_id("TC-FE-TOWN-FX-01")
def test_town_ux_fx_place_shows_gold_stars(page, base_url, test_db_path, fe_ids):
    """TC-FE-TOWN-FX-01 確定起屋之後，地圖上睇到金星慶祝（唔係戰鬥 spark）。"""
    _seed_town_ux_plot(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    _enter_scene3(
        page,
        "TC-FE-TOWN-FX-01",
        "Confirming a new build must show a visible gold-star celebration on the map "
        "(.fx-burst.is-place .fx-bit.is-star). Battle .spark-burst does not count.",
    )
    page.get_by_role("button", name=re.compile(r"確定")).first.click()
    try:
        _wait_visible_gold_stars(page, ".fx-burst.is-place .fx-bit.is-star")
    except Exception:
        _town_ux_fail(
            "TC-FE-TOWN-FX-01",
            "New-build gold stars were not visible (.fx-burst.is-place .fx-bit.is-star). "
            "Battle .spark-burst does not count.",
        )
    on_sheet = page.evaluate(
        """() => {
          const star = document.querySelector('.fx-burst.is-place .fx-bit.is-star');
          return !!(star && star.closest('#actionSheet, .action-sheet'));
        }"""
    )
    assert not on_sheet, (
        "TC-FE-TOWN-FX-01: the place celebration plays on the new building before the sheet covers it."
    )


@pytest.mark.case_id("TC-FE-TOWN-FX-02")
def test_town_ux_fx_upgrade_shows_gold_stars_on_sheet(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-FX-02 升級金星要喺打開緊嘅 action sheet 上面睇到。"""
    _seed_town_ux_plot(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    _enter_scene3(
        page,
        "TC-FE-TOWN-FX-02",
        "Upgrade must show a visible gold-star celebration on the open action sheet "
        "(.action-sheet .fx-burst.is-upgrade .fx-bit.is-star), in front of the panel.",
    )
    page.get_by_role("button", name=re.compile(r"確定")).first.click()
    upgrade = page.get_by_role("button", name=re.compile(r"升級"))
    try:
        upgrade.first.wait_for(state="visible", timeout=8000)
    except Exception:
        _town_ux_fail(
            "TC-FE-TOWN-FX-02",
            "Scene 4 action sheet did not open, so the upgrade gold-star burst cannot sit on it.",
        )
    upgrade.first.click()
    try:
        _wait_visible_gold_stars(
            page,
            "#actionSheet .fx-burst.is-upgrade .fx-bit.is-star, .action-sheet .fx-burst.is-upgrade .fx-bit.is-star",
        )
    except Exception:
        _town_ux_fail(
            "TC-FE-TOWN-FX-02",
            "Upgrade gold stars were not visible on the open action sheet.",
        )
    hosted = page.evaluate(
        """() => {
          const sheet = document.querySelector('#actionSheet, .action-sheet');
          if (!sheet || sheet.hidden) return false;
          const burst = sheet.querySelector('.fx-burst.is-upgrade');
          return !!(burst && sheet.contains(burst));
        }"""
    )
    assert hosted, "TC-FE-TOWN-FX-02: the upgrade burst must be a child of the open action sheet."


@pytest.mark.case_id("TC-FE-TOWN-MOTION-01")
def test_town_ux_motion_burst_pointer_events_none(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-MOTION-01 放置／升級慶祝層 pointer-events:none，唔好截走撳擊。"""
    _seed_town_ux_plot(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    _enter_scene3(
        page,
        "TC-FE-TOWN-MOTION-01",
        "Place/upgrade celebration bursts (.fx-burst or [data-town-fx]) must use pointer-events:none and must not steal taps. Battle .spark-burst does not count.",
    )
    page.get_by_role("button", name=re.compile(r"確定")).first.click()
    burst = page.locator(".fx-burst, [data-town-fx]")
    try:
        burst.first.wait_for(state="attached", timeout=4000)
    except Exception:
        _town_ux_fail(
            "TC-FE-TOWN-MOTION-01",
            "Place must show a town celebration burst (.fx-burst or [data-town-fx]). "
            "Battle .spark-burst does not count. The layer and its children need "
            "pointer-events:none so a tap still reaches the pad underneath.",
        )
    stolen = page.evaluate(
        """() => {
          const nodes = [...document.querySelectorAll('.fx-burst, .fx-burst *, [data-town-fx], [data-town-fx] *')];
          const bad = [];
          for (const el of nodes) {
            const pe = getComputedStyle(el).pointerEvents;
            if (pe !== 'none') bad.push((el.className || el.tagName) + ':' + pe);
          }
          const host = document.querySelector('.fx-burst, [data-town-fx]');
          if (!host) return {bad, hit: 'missing'};
          const rect = host.getBoundingClientRect();
          const top = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
          const hitBurst = !!(top && (top === host || host.contains(top)));
          return {bad, hitBurst};
        }"""
    )
    assert not stolen["bad"] and not stolen["hitBurst"], (
        "TC-FE-TOWN-MOTION-01: celebration layers must use pointer-events:none "
        f"and must not be the hit target. got={stolen}"
    )


@pytest.mark.case_id("TC-FE-TOWN-MOTION-02")
def test_town_ux_motion_toggle_follows_reduced_motion_until_click(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-MOTION-02 未有 localStorage 時跟 prefers-reduced-motion；撳掣先寫低並覆蓋。"""
    _seed_town_ux_plot(test_db_path, fe_ids["kid_id"])
    page.emulate_media(reduced_motion="reduce")
    page.goto(f"{base_url}/kids/")
    page.evaluate("() => localStorage.clear()")
    _login(page, base_url)
    page.locator("body.kt-artstage #tab-town.active").wait_for(state="visible", timeout=8000)
    reduced = page.evaluate(
        "() => window.matchMedia('(prefers-reduced-motion: reduce)').matches"
    )
    assert reduced, "TC-FE-TOWN-MOTION-02: prefers-reduced-motion: reduce must be emulated"
    stored = page.evaluate(
        "() => Object.keys(localStorage).filter((key) => key.toLowerCase().includes('motion'))"
    )
    assert stored == [], (
        "TC-FE-TOWN-MOTION-02: first visit must not write a motion localStorage key "
        f"(saw {stored})."
    )
    toggle = page.get_by_role("button", name=re.compile(r"動畫"))
    if toggle.count() == 0 or not toggle.first.is_visible():
        _town_ux_fail(
            "TC-FE-TOWN-MOTION-02",
            "Town home must expose an 動畫 開/關 toggle. "
            "With no localStorage and prefers-reduced-motion: reduce, it defaults off. "
            "Only an explicit on click and an explicit off click write a localStorage key "
            "whose name contains 'motion'. That stored on value overrides reduced motion "
            "on the next load. Loading the town must not write the key.",
        )
    btn = toggle.first
    label = (btn.inner_text() or "") + " " + (btn.get_attribute("aria-label") or "")
    pressed = btn.get_attribute("aria-pressed")
    assert ("關" in label) or pressed == "false", (
        "TC-FE-TOWN-MOTION-02: reduced motion with empty storage defaults the toggle off "
        f"(label={label!r} aria-pressed={pressed!r})."
    )
    btn.click()
    written = page.evaluate(
        """() => Object.fromEntries(
          Object.keys(localStorage)
            .filter((key) => key.toLowerCase().includes('motion'))
            .map((key) => [key, localStorage.getItem(key)])
        )"""
    )
    assert written, (
        "TC-FE-TOWN-MOTION-02: the click must write localStorage (key name contains 'motion'). "
        "Do not persist the preference before that click."
    )
    label_on = (btn.inner_text() or "") + " " + (btn.get_attribute("aria-label") or "")
    pressed_on = btn.get_attribute("aria-pressed")
    assert ("開" in label_on) or pressed_on == "true", (
        f"TC-FE-TOWN-MOTION-02: after the click the toggle is on (label={label_on!r})."
    )
    page.reload()
    page.locator("body.kt-artstage #tab-town.active, #loginUsername").first.wait_for(
        state="visible", timeout=8000
    )
    if page.locator("#loginUsername").is_visible():
        page.locator("#loginUsername").fill(FE_KID_USERNAME)
        page.locator("#loginPassword").fill(TEST_KID_PIN)
        page.get_by_role("button", name="🚪 登入").click()
        page.locator("body.kt-artstage #tab-town.active").wait_for(state="visible", timeout=8000)
    kept = page.evaluate(
        "() => window.matchMedia('(prefers-reduced-motion: reduce)').matches"
    )
    assert kept, "reduced-motion emulation should still be on after reload"
    again = page.get_by_role("button", name=re.compile(r"動畫")).first
    again.wait_for(state="visible", timeout=8000)
    label_kept = (again.inner_text() or "") + " " + (again.get_attribute("aria-label") or "")
    pressed_kept = again.get_attribute("aria-pressed")
    assert ("開" in label_kept) or pressed_kept == "true", (
        "TC-FE-TOWN-MOTION-02: the stored on choice overrides prefers-reduced-motion "
        f"on the next visit (label={label_kept!r} aria-pressed={pressed_kept!r})."
    )
    on_value = _motion_store(page)
    again.click()
    off_value = _motion_store(page)
    assert off_value and off_value != on_value, (
        "TC-FE-TOWN-MOTION-02: the explicit off click must rewrite the motion localStorage value "
        f"(on={on_value!r} off={off_value!r}). Do not delete the key and fall back to the system default."
    )
    label_off = (again.inner_text() or "") + " " + (again.get_attribute("aria-label") or "")
    pressed_off = again.get_attribute("aria-pressed")
    assert ("關" in label_off) or pressed_off == "false", (
        "TC-FE-TOWN-MOTION-02: after the off click the toggle shows 關 "
        f"(label={label_off!r} aria-pressed={pressed_off!r})."
    )


# ── TC-FE-TOWN-GRID / STORE-LEGACY: 8×8 map, warehouse the rows outside it ──
#
# Acceptance is COLS=8 ROWS=8 in scenes 1–3. Rows with a cell outside
# col 0..7 × row 0..7, or with no legal cell, and stored=0, must become
# stored=1 when the town loads. Keep the same row id, def_id, and level.
# Scene 1 must not paint them. The build list must not lock them as map-「已起」.
# Place them back from the existing 存倉 tab onto an empty pad. That path
# must not deduct resources. Do not use 「去擺位置」 as the place-back path.

TOWN_GRID_COLS = 8
TOWN_GRID_ROWS = 8
# (name, cell_x, cell_y, level). Inside the 8×8 grid; must stay placed.
TOWN_LEGACY_IN_GRID = ("工坊", 4, 1, 1)
# Outside 0..7 × 0..7. 銀行 is not in seed_building_defs.
TOWN_LEGACY_OUT = (
    ("圖書館", 17, 1, 3),
    ("健身室", 15, 5, 1),
    ("農場", 9, 5, 2),
    ("醫院", 17, 13, 1),
    ("探險公會", 9, 13, 1),
)
# No legal cell (NULL coordinates), stored=0. Must also enter the warehouse.
TOWN_LEGACY_NO_CELL = ("燈塔", 1)

_TOWN_GRID_PROBE_JS = r"""
() => {
  const buttons = [...document.querySelectorAll('#townMap .pad button, #village .pad button')];
  const cells = new Set();
  let maxC = 0;
  let maxR = 0;
  for (const btn of buttons) {
    const label = btn.getAttribute('aria-label') || '';
    const m = /第\s*(\d+)\s*欄第\s*(\d+)\s*行/.exec(label);
    if (!m) continue;
    const c = Number(m[1]);
    const r = Number(m[2]);
    if (c > maxC) maxC = c;
    if (r > maxR) maxR = r;
    cells.add(c + ',' + r);
  }
  return {cols: maxC, rows: maxR, count: cells.size};
}
"""


def _town_grid_problem(page, scene):
    """1-based label span must be COLS×ROWS in every four-scene map."""
    size = page.evaluate(_TOWN_GRID_PROBE_JS)
    want = TOWN_GRID_COLS * TOWN_GRID_ROWS
    if (
        size["cols"] == TOWN_GRID_COLS
        and size["rows"] == TOWN_GRID_ROWS
        and size["count"] == want
    ):
        return None
    return (
        f"scene {scene} map is {size['cols']}×{size['rows']} ({size['count']} pads); "
        f"want {TOWN_GRID_COLS}×{TOWN_GRID_ROWS} ({want} pads, "
        f"col 0..{TOWN_GRID_COLS - 1} × row 0..{TOWN_GRID_ROWS - 1})"
    )


def _store_legacy_fail(case_id, detail):
    pytest.fail(
        f"{case_id}: {detail} "
        "On town load, every stored=0 building whose cell is outside 0..7×0..7 "
        "or has no legal cell must be set to stored=1 (warehouse) on the same row, "
        "keeping def_id and level. After that, scene 1 must not show it and the "
        "build list must not lock it as map-「已起」. Place it back from the existing "
        "存倉 tab onto an empty pad without spending resources."
    )


def _insert_legacy_building(test_db_path, kid_id, name, level, cell_x, cell_y, stored=0):
    """Seed one row. cell_x/cell_y may be None (no legal cell)."""
    def_id_value = building_def_id(test_db_path, name)
    db = connect_db(test_db_path)
    cur = db.execute(
        "INSERT INTO buildings (kid_id, def_id, plot_idx, level, cell_x, cell_y, stored) "
        "VALUES (?, ?, 0, ?, ?, ?, ?)",
        (kid_id, def_id_value, level, cell_x, cell_y, stored),
    )
    db.commit()
    bid = cur.lastrowid
    db.close()
    return {"id": bid, "def_id": def_id_value, "name": name, "level": level}


def _seed_town_store_legacy(test_db_path, kid_id):
    """In-grid 工坊 plus out-of-grid and cell-less rows, all stored=0.

    Synthetic kid only. Balances are high so a mistaken new-build could deduct.
    No production DB and no real PIN.
    """
    set_kid_points(test_db_path, kid_id, 8000)
    grant_inventory(
        test_db_path,
        kid_id,
        {"wood": 400, "brick": 300, "glass": 40, "gear": 120, "gem": 20},
    )
    db = connect_db(test_db_path)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    seeded = []
    name, cell_x, cell_y, level = TOWN_LEGACY_IN_GRID
    row = _insert_legacy_building(
        test_db_path, kid_id, name, level, cell_x, cell_y, stored=0
    )
    row.update(cell_x=cell_x, cell_y=cell_y, warehouse=False)
    seeded.append(row)
    for name, cell_x, cell_y, level in TOWN_LEGACY_OUT:
        row = _insert_legacy_building(
            test_db_path, kid_id, name, level, cell_x, cell_y, stored=0
        )
        row.update(cell_x=cell_x, cell_y=cell_y, warehouse=True)
        seeded.append(row)
    name, level = TOWN_LEGACY_NO_CELL
    row = _insert_legacy_building(
        test_db_path, kid_id, name, level, None, None, stored=0
    )
    row.update(cell_x=None, cell_y=None, warehouse=True)
    seeded.append(row)
    return seeded


def _building_rows(test_db_path, kid_id):
    db = connect_db(test_db_path)
    rows = db.execute(
        "SELECT b.id, b.def_id, d.name AS name, b.cell_x, b.cell_y, "
        "COALESCE(b.stored, 0) AS stored, b.level "
        "FROM buildings b JOIN building_defs d ON d.id=b.def_id "
        "WHERE b.kid_id=? ORDER BY b.id",
        (kid_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def _rows_named(rows, name):
    return [row for row in rows if row["name"] == name]


def _iso_visible_names(page):
    """Names painted on the iso scene (sprite alt or caption), not the legacy canvas."""
    return page.evaluate(
        """() => {
          const out = [];
          const nodes = document.querySelectorAll(
            '#townMap .sprite, #townMap .cap, #village .sprite, #village .cap, #townMap .ghost'
          );
          for (const el of nodes) {
            if (el.hidden) continue;
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') continue;
            const text = (el.alt || el.textContent || '').trim();
            if (text) out.push(text);
          }
          return out;
        }"""
    )


def _palette_button(page, name):
    return page.locator("#paletteGrid").get_by_role(
        "button", name=re.compile(re.escape(name))
    )


def _control_blob(btn):
    return ((btn.get_attribute("aria-label") or "") + " " + (btn.inner_text() or "")).strip()


def _pad_button(page, col_1, row_1):
    return page.get_by_role(
        "button",
        name=re.compile(rf"第\s*{col_1}\s*欄第\s*{row_1}\s*行"),
    )


def _select_empty_pad(page, col_1, row_1):
    """Click one iso pad. Labels are 1-based; DB cells are 0-based."""
    btn = _pad_button(page, col_1, row_1)
    assert btn.count() > 0, f"missing pad 第 {col_1} 欄第 {row_1} 行"
    target = None
    for i in range(btn.count()):
        item = btn.nth(i)
        if item.is_visible():
            target = item
            break
    assert target is not None, f"pad 第 {col_1} 欄第 {row_1} 行 is not visible"
    target.click()
    return col_1 - 1, row_1 - 1


def _resource_snapshot(page, test_db_path, kid_id):
    return {
        "hud": _hud_snapshot(page),
        "points": get_kid_points(test_db_path, kid_id),
        "inventory": inventory_map(test_db_path, kid_id),
    }


def _open_store_tab(page):
    """Existing drawer path: ☰ → 存倉. Does not use the four-scene build list."""
    _open_drawer(page)
    page.get_by_role("button", name=re.compile(r"存倉")).first.click()
    page.locator("#tab-store.active").wait_for(state="visible", timeout=8000)
    page.wait_for_function(
        """() => {
          const el = document.getElementById('storedBuildings');
          if (!el) return false;
          const text = el.innerText || '';
          return text.includes('存倉吉咗') || !!el.querySelector('.build-card');
        }""",
        timeout=8000,
    )


def _pick_in_grid_valid_plot(page):
    """A legacy .valid-plot whose 2×2 stays inside col 0..7 × row 0..7."""
    return page.evaluate(
        """() => {
          const plots = [...document.querySelectorAll('.valid-plot')];
          for (const el of plots) {
            const px = parseInt(el.dataset.px, 10);
            const py = parseInt(el.dataset.py, 10);
            if (px >= 0 && py >= 0 && px <= 6 && py <= 6) return {px, py};
          }
          return null;
        }"""
    )


@pytest.mark.case_id("TC-FE-TOWN-GRID-01")
def test_town_grid_map_is_8x8(page, base_url, test_db_path, fe_ids):
    """TC-FE-TOWN-GRID-01 場景 1–3 嘅可建地圖係 8×8。"""
    kid_id = fe_ids["kid_id"]
    db = connect_db(test_db_path)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    _open_town_home(page, base_url)
    problems = []
    grid = _town_grid_problem(page, 1)
    if grid:
        problems.append(grid)
    _enter_scene2(page, "TC-FE-TOWN-GRID-01")
    grid = _town_grid_problem(page, 2)
    if grid:
        problems.append(grid)
    _select_empty_pad(page, 1, 1)
    _open_building_list(page)
    picked = None
    buttons = page.locator("#paletteGrid button")
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        try:
            if not btn.is_visible():
                continue
        except Exception:
            continue
        blob = _control_blob(btn)
        if "未起" in blob and "已起" not in blob:
            picked = btn
            break
    if picked is None:
        problems.append("scene 2 list has no visible 未起 building, so scene 3 was not opened")
    else:
        picked.click()
        go = _go_place_button(page)
        enabled = False
        try:
            enabled = go.count() > 0 and go.first.is_visible() and go.first.is_enabled()
        except Exception:
            enabled = False
        if not enabled:
            problems.append("「去擺位置」 stayed disabled, so scene 3 was not measured")
        else:
            go.first.click()
            page.locator("#btnUxCancel").wait_for(state="visible", timeout=8000)
            grid = _town_grid_problem(page, 3)
            if grid:
                problems.append(grid)
    if problems:
        pytest.fail(
            "TC-FE-TOWN-GRID-01: the four-scene buildable map must be 8×8 "
            "(COLS=8 ROWS=8, 64 pads, col 0..7 × row 0..7) in scenes 1, 2, and 3. "
            + " | ".join(problems)
        )


@pytest.mark.case_id("TC-FE-TOWN-STORE-LEGACY-01")
def test_town_store_legacy_migrates_out_of_grid_to_stored(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-STORE-LEGACY-01 載入城鎮時，格外或無合法格而且 stored=0 嘅屋收進存倉。"""
    kid_id = fe_ids["kid_id"]
    seeded = _seed_town_store_legacy(test_db_path, kid_id)
    before = {row["id"]: row for row in seeded}
    _open_town_home(page, base_url)
    rows = _building_rows(test_db_path, kid_id)
    problems = []
    if len(rows) != len(seeded):
        problems.append(
            f"town load changed the building count ({len(seeded)} -> {len(rows)}). "
            "Keep the same rows."
        )
    by_id = {row["id"]: row for row in rows}
    for bid, expect in before.items():
        row = by_id.get(bid)
        if row is None:
            problems.append(f"row id {bid} ({expect['name']}) is missing after town load")
            continue
        if row["def_id"] != expect["def_id"] or row["level"] != expect["level"] or row["name"] != expect["name"]:
            problems.append(
                f"{expect['name']} id={bid} must keep def_id={expect['def_id']} "
                f"and level={expect['level']}; saw {row}"
            )
        if expect["warehouse"]:
            if row["stored"] != 1:
                cell = (row["cell_x"], row["cell_y"])
                problems.append(
                    f"{expect['name']} id={bid} is still stored=0 at cell {cell}. "
                    "Town load must put this out-of-grid or cell-less row into the "
                    "warehouse (stored=1) without changing def_id or level."
                )
        elif row["stored"] != 0 or (row["cell_x"], row["cell_y"]) != (4, 1):
            problems.append(
                f"in-grid 工坊 must stay stored=0 at (4,1); saw {row}"
            )
    if problems:
        _store_legacy_fail("TC-FE-TOWN-STORE-LEGACY-01", " | ".join(problems))


@pytest.mark.case_id("TC-FE-TOWN-STORE-LEGACY-02")
def test_town_store_legacy_place_from_store_without_spend(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-STORE-LEGACY-02 收倉後唔喺地圖、唔鎖「已起」；存倉放返空地唔扣資源。"""
    kid_id = fe_ids["kid_id"]
    seeded = _seed_town_store_legacy(test_db_path, kid_id)
    library = next(row for row in seeded if row["name"] == "圖書館")
    workshop = next(row for row in seeded if row["name"] == "工坊")
    _open_town_home(page, base_url)
    before = _resource_snapshot(page, test_db_path, kid_id)
    problems = []

    labels = _iso_pad_labels(page)
    visible = _iso_visible_names(page)
    blob = "\n".join(labels + visible)
    in_name, in_x, in_y, _level = TOWN_LEGACY_IN_GRID
    in_label = f"第 {in_x + 1} 欄第 {in_y + 1} 行"
    if in_name not in blob or in_label not in blob:
        problems.append(
            f"scene 1 must keep in-grid {in_name} at {in_label}. "
            f"iso labels={labels!r} visible={visible!r}"
        )
    for row in seeded:
        if not row["warehouse"]:
            continue
        if row["name"] in blob:
            problems.append(
                f"scene 1 still shows {row['name']} "
                f"(cell {row['cell_x']},{row['cell_y']}). "
                "A warehouse row must not paint on the iso map."
            )

    _enter_scene2(page, "TC-FE-TOWN-STORE-LEGACY-02")
    _open_building_list(page)
    for row in seeded:
        btn = _palette_button(page, row["name"])
        if btn.count() == 0:
            problems.append(f"{row['name']} is missing from the building list")
            continue
        control = _control_blob(btn.first)
        if row["warehouse"]:
            if "已起" in control:
                problems.append(
                    f"{row['name']} is locked as map-「已起」 ({control!r}). "
                    "After the warehouse patch it must not block picking as a placed building."
                )
        elif "已起" not in control:
            problems.append(
                f"in-grid 工坊 must stay marked 已起 ({control!r})"
            )

    _open_store_tab(page)
    store_text = page.locator("#storedBuildings").inner_text() or ""
    if "存倉吉咗" in store_text or page.locator("#storedBuildings .build-card").count() == 0:
        missing = [
            f"{row['name']} Lv.{row['level']}"
            for row in seeded
            if row["warehouse"]
        ]
        problems.append(
            "存倉 is empty, so the legacy rows cannot be placed from storage. "
            f"Expected cards {missing}. Saw {store_text!r}."
        )
    else:
        for row in seeded:
            if not row["warehouse"]:
                continue
            card = page.locator("#storedBuildings .build-card", has_text=row["name"])
            card_text = card.first.inner_text() if card.count() else ""
            if card.count() == 0 or f"Lv.{row['level']}" not in card_text:
                problems.append(
                    f"存倉 must list {row['name']} Lv.{row['level']} (按此放置). "
                    f"Saw {card_text!r}."
                )
        library_card = page.locator("#storedBuildings .build-card", has_text="圖書館")
        if library_card.count() == 0:
            problems.append("存倉 has no 圖書館 card to place back")
        else:
            library_card.first.click()
            bar = page.locator("#placementBar")
            active = "active" in (bar.get_attribute("class") or "")
            if not active:
                problems.append(
                    "clicking the 存倉 card must start the existing place-from-storage "
                    "flow (#placementBar.active). Do not use 「去擺位置」."
                )
            else:
                _goto_town_map(page)
                try:
                    page.locator(".valid-plot").first.wait_for(state="visible", timeout=8000)
                except Exception:
                    problems.append("place-from-storage did not show a .valid-plot on the town map")
                else:
                    picked = _pick_in_grid_valid_plot(page)
                    if not picked:
                        problems.append(
                            "no .valid-plot with origin inside 0..6 × 0..6 "
                            "(the 2×2 must stay inside the 8×8 grid)"
                        )
                    else:
                        page.locator(
                            f'.valid-plot[data-px="{picked["px"]}"][data-py="{picked["py"]}"]'
                        ).first.dispatch_event("click")
                        confirm = page.locator("#placementBar").get_by_role(
                            "button", name=re.compile(r"確認")
                        )
                        try:
                            confirm.first.wait_for(state="visible", timeout=8000)
                        except Exception:
                            problems.append(
                                "selecting an empty pad did not show 「確認建造」 "
                                "on the place-from-storage bar"
                            )
                        else:
                            try:
                                with page.expect_response(
                                    lambda r: r.request.method == "POST"
                                    and "/buildings/" in r.url,
                                    timeout=8000,
                                ) as resp_info:
                                    confirm.first.click()
                                resp = resp_info.value
                            except Exception as exc:
                                problems.append(
                                    f"confirm did not finish a place-from-storage request ({exc})"
                                )
                            else:
                                if "/unstored" not in resp.url:
                                    problems.append(
                                        "confirm must POST the existing unstored endpoint "
                                        f"for the stored row, not a new build. url={resp.url}"
                                    )
                                if resp.status not in (200, 201):
                                    problems.append(
                                        f"unstored failed HTTP {resp.status}: {resp.text()[:300]}"
                                    )
                                page.wait_for_timeout(400)
                                placed = _rows_named(
                                    _building_rows(test_db_path, kid_id), "圖書館"
                                )
                                if (
                                    len(placed) != 1
                                    or placed[0]["id"] != library["id"]
                                    or placed[0]["level"] != 3
                                    or placed[0]["stored"] != 0
                                    or placed[0]["def_id"] != library["def_id"]
                                    or not (
                                        placed[0]["cell_x"] is not None
                                        and placed[0]["cell_y"] is not None
                                        and 0 <= placed[0]["cell_x"] < TOWN_GRID_COLS
                                        and 0 <= placed[0]["cell_y"] < TOWN_GRID_ROWS
                                    )
                                ):
                                    problems.append(
                                        "圖書館 must stay the same row (id, def_id, level 3) "
                                        "and land stored=0 on a cell inside 0..7 × 0..7. "
                                        f"saw {placed!r} picked={picked!r}"
                                    )
                                on_iso = any(
                                    "圖書館" in label for label in _iso_pad_labels(page)
                                )
                                on_canvas = page.locator(
                                    '#townBuildings img[alt="圖書館"]'
                                ).count() > 0
                                if not on_iso and not on_canvas:
                                    problems.append(
                                        "after place-from-storage, 圖書館 is not on the "
                                        f"iso map or the town canvas. toast={_toast_text(page)!r}"
                                    )

    after = _resource_snapshot(page, test_db_path, kid_id)
    if (
        after["hud"] != before["hud"]
        or after["points"] != before["points"]
        or after["inventory"] != before["inventory"]
    ):
        problems.append(
            "placing from 存倉 must not deduct coins or materials "
            f"(hud {before['hud']} -> {after['hud']}, "
            f"points {before['points']} -> {after['points']}, "
            f"inventory {before['inventory']} -> {after['inventory']})"
        )
    workshops = _rows_named(_building_rows(test_db_path, kid_id), "工坊")
    if (
        len(workshops) != 1
        or workshops[0]["id"] != workshop["id"]
        or workshops[0]["stored"] != 0
        or (workshops[0]["cell_x"], workshops[0]["cell_y"]) != (4, 1)
        or workshops[0]["level"] != 1
    ):
        problems.append(
            f"in-grid 工坊 must stay id={workshop['id']} stored=0 level 1 at (4,1). "
            f"saw {workshops!r}"
        )
    if problems:
        _store_legacy_fail("TC-FE-TOWN-STORE-LEGACY-02", " | ".join(problems))


# ── TC-FE-TOWN-STORE-LIST / PLACE / CONFIRM: stored row is not a new build ──
#
# stored=1 means the kid already owns that building. Scene 2 建築清單 must not
# sell it as 未起 with a gold price, and 確定放置 must not POST /buildings.
# That create call dup-checks stored rows and returns 400
# 「你已經興建咗呢種建築物」. The correct place is the existing 存倉 tab:
# #placementBar and POST /buildings/<id>/unstored, with no spend.
# Filter: `-k 'store_list or store_place or store_confirm'`.

STORE_PALETTE_GUILD = "探險公會"
STORE_PALETTE_WORKSHOP = "工坊"
SPEND_CONFIRM_COPY = "確定先至扣資源"
ALREADY_BUILT_COPY = "你已經興建咗呢種建築物"


def _store_palette_fail(case_id, detail):
    pytest.fail(
        f"{case_id}: {detail} "
        "A stored=1 building is already owned. The four-scene 建築清單 must not "
        "show it as unbuilt with a price, and 確定 must not POST /buildings "
        f"(the dup check includes stored rows and answers 400 {ALREADY_BUILT_COPY}). "
        "Place it from 存倉 with #placementBar and POST /buildings/<id>/unstored, "
        "without spending gold or materials."
    )


def _seed_town_store_palette(test_db_path, kid_id):
    """On-map 工坊 stored=0 plus 探險公會 already stored=1.

    Synthetic kid only. Balances are high so a mistaken new-build could deduct
    and still be seen. No production DB and no real PIN.
    """
    set_kid_points(test_db_path, kid_id, 8000)
    grant_inventory(
        test_db_path,
        kid_id,
        {"wood": 400, "brick": 300, "glass": 40, "gear": 120, "gem": 20},
    )
    db = connect_db(test_db_path)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    workshop = _insert_legacy_building(
        test_db_path, kid_id, STORE_PALETTE_WORKSHOP, 1, 4, 1, stored=0
    )
    workshop.update(cell_x=4, cell_y=1)
    # Already warehoused. Old cell is outside 0..7×0..7; stored stays 1.
    guild = _insert_legacy_building(
        test_db_path, kid_id, STORE_PALETTE_GUILD, 1, 9, 13, stored=1
    )
    guild.update(cell_x=9, cell_y=13)
    return {"workshop": workshop, "guild": guild}


def _palette_control(page, name):
    btn = _palette_button(page, name)
    if btn.count() == 0:
        return None, ""
    return btn.first, _control_blob(btn.first)


def _offered_as_unbuilt_with_price(control):
    """New-build row: 「未起」 and/or a gold price. 「已起」 is the on-map lock."""
    if not control:
        return False
    return ("未起" in control) or ("💰" in control)


def _workshop_row_ok(test_db_path, kid_id, workshop):
    rows = _rows_named(_building_rows(test_db_path, kid_id), STORE_PALETTE_WORKSHOP)
    return (
        len(rows) == 1
        and rows[0]["id"] == workshop["id"]
        and rows[0]["stored"] == 0
        and rows[0]["level"] == 1
        and (rows[0]["cell_x"], rows[0]["cell_y"]) == (4, 1)
        and rows[0]["def_id"] == workshop["def_id"]
    )


def _guild_placed_same_row(test_db_path, kid_id, guild):
    rows = _rows_named(_building_rows(test_db_path, kid_id), STORE_PALETTE_GUILD)
    if len(rows) != 1:
        return False, rows
    row = rows[0]
    ok = (
        row["id"] == guild["id"]
        and row["def_id"] == guild["def_id"]
        and row["level"] == guild["level"]
        and row["stored"] == 0
        and row["cell_x"] is not None
        and row["cell_y"] is not None
        and 0 <= row["cell_x"] < TOWN_GRID_COLS
        and 0 <= row["cell_y"] < TOWN_GRID_ROWS
    )
    return ok, rows


def _resources_unchanged(before, after):
    return (
        after["hud"] == before["hud"]
        and after["points"] == before["points"]
        and after["inventory"] == before["inventory"]
    )


def _resource_delta(before, after):
    return (
        f"hud {before['hud']} -> {after['hud']}, "
        f"points {before['points']} -> {after['points']}, "
        f"inventory {before['inventory']} -> {after['inventory']}"
    )


def _enter_new_build_confirm(page, name):
    """Pick an empty pad and name in scene 2. Return place-status text, or None.

    None means the list did not enable 「去擺位置」 for this building, so the
    new-build spend confirm was not entered.
    """
    _select_empty_pad(page, 1, 1)
    _open_building_list(page)
    btn, control = _palette_control(page, name)
    if btn is None or not _offered_as_unbuilt_with_price(control):
        if btn is None:
            return None
        if "已起" in control and "未起" not in control and "💰" not in control:
            return None
    btn.click()
    go = _go_place_button(page)
    try:
        enabled = go.count() > 0 and go.first.is_visible() and go.first.is_enabled()
    except Exception:
        enabled = False
    if not enabled:
        return None
    go.first.click()
    try:
        page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
        page.locator("#placeStatus").wait_for(state="visible", timeout=8000)
    except Exception:
        return ""
    return page.locator("#placeStatus").inner_text() or ""


def _place_guild_from_store(page, guild):
    """存倉 card → #placementBar → in-grid .valid-plot → 確認. Like STORE-LEGACY-02.

    Returns a list of problems. Empty means the unstored place finished.
    """
    problems = []
    _open_store_tab(page)
    store_text = page.locator("#storedBuildings").inner_text() or ""
    card = page.locator("#storedBuildings .build-card", has_text=STORE_PALETTE_GUILD)
    card_text = card.first.inner_text() if card.count() else ""
    if "存倉吉咗" in store_text or card.count() == 0:
        problems.append(
            f"存倉 has no {STORE_PALETTE_GUILD} card to place "
            f"(Lv.{guild['level']}). Saw {store_text!r}."
        )
        return problems
    if f"Lv.{guild['level']}" not in card_text:
        problems.append(
            f"存倉 must list {STORE_PALETTE_GUILD} Lv.{guild['level']} (按此放置). "
            f"Saw {card_text!r}."
        )
        return problems
    card.first.click()
    bar = page.locator("#placementBar")
    if "active" not in (bar.get_attribute("class") or ""):
        problems.append(
            "clicking the 存倉 card must start #placementBar.active "
            "(place-from-storage). Do not use 「去擺位置」."
        )
        return problems
    _goto_town_map(page)
    try:
        page.locator(".valid-plot").first.wait_for(state="visible", timeout=8000)
    except Exception:
        problems.append("place-from-storage did not show a .valid-plot on the town map")
        return problems
    picked = _pick_in_grid_valid_plot(page)
    if not picked:
        problems.append(
            "no .valid-plot with origin inside 0..6 × 0..6 "
            "(the 2×2 must stay inside the 8×8 grid)"
        )
        return problems
    page.locator(
        f'.valid-plot[data-px="{picked["px"]}"][data-py="{picked["py"]}"]'
    ).first.dispatch_event("click")
    confirm = page.locator("#placementBar").get_by_role("button", name=re.compile(r"確認"))
    try:
        confirm.first.wait_for(state="visible", timeout=8000)
    except Exception:
        problems.append("selecting an empty pad did not show 「確認建造」 on #placementBar")
        return problems
    try:
        with page.expect_response(
            lambda r: r.request.method == "POST" and "/buildings/" in r.url,
            timeout=8000,
        ) as resp_info:
            confirm.first.click()
        resp = resp_info.value
    except Exception as exc:
        problems.append(f"confirm did not finish a place-from-storage request ({exc})")
        return problems
    if "/unstored" not in resp.url:
        problems.append(
            "confirm must POST /buildings/<id>/unstored for the stored row, "
            f"not a new build. url={resp.url}"
        )
    if resp.status not in (200, 201):
        problems.append(f"unstored failed HTTP {resp.status}: {resp.text()[:300]}")
    page.wait_for_timeout(400)
    return problems


def _guild_visible_on_map(page):
    labels = _iso_pad_labels(page)
    visible = _iso_visible_names(page)
    on_iso = any(STORE_PALETTE_GUILD in label for label in labels + visible)
    on_canvas = page.locator(f'#townBuildings img[alt="{STORE_PALETTE_GUILD}"]').count() > 0
    return on_iso or on_canvas, labels, visible


def _submit_ux_confirm(page):
    """Click four-scene 確定放置 and return response, toast, body, status text."""
    confirm = page.locator("#btnUxConfirm")
    with page.expect_response(
        lambda r: r.request.method == "POST" and "/buildings" in r.url,
        timeout=8000,
    ) as resp_info:
        confirm.click()
    resp = resp_info.value
    page.wait_for_timeout(300)
    toast = _toast_text(page)
    try:
        body = resp.text()
    except Exception:
        body = ""
    try:
        status_after = page.locator("#placeStatus").inner_text() or ""
    except Exception:
        status_after = ""
    return resp, toast, body, status_after


def _assert_guild_place_outcome(page, test_db_path, kid_id, guild, workshop, before, problems):
    """Map, same row stored=0, resources, and the on-map 工坊."""
    on_map, _labels, visible = _guild_visible_on_map(page)
    if not on_map:
        problems.append(
            f"map does not show {STORE_PALETTE_GUILD} "
            f"(iso/canvas names {visible!r}, toast={_toast_text(page)!r})"
        )
    ok, rows = _guild_placed_same_row(test_db_path, kid_id, guild)
    if not ok:
        problems.append(
            f"{STORE_PALETTE_GUILD} must stay the same row "
            f"(id={guild['id']}, def_id={guild['def_id']}, level {guild['level']}) "
            f"and land stored=0 inside 0..7 × 0..7. saw {rows!r}"
        )
    after = _resource_snapshot(page, test_db_path, kid_id)
    if not _resources_unchanged(before, after):
        problems.append(
            "placing the stored building must not deduct coins or materials "
            f"({_resource_delta(before, after)})"
        )
    if not _workshop_row_ok(test_db_path, kid_id, workshop):
        problems.append(
            f"on-map {STORE_PALETTE_WORKSHOP} must stay id={workshop['id']} "
            f"stored=0 level 1 at (4,1). "
            f"saw {_rows_named(_building_rows(test_db_path, kid_id), STORE_PALETTE_WORKSHOP)!r}"
        )


@pytest.mark.case_id("TC-FE-TOWN-STORE-LIST-01")
def test_town_store_list_does_not_sell_stored_guild(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-STORE-LIST-01 存倉嘅探險公會唔好喺建築清單當未起兼標價錢。"""
    kid_id = fe_ids["kid_id"]
    seeded = _seed_town_store_palette(test_db_path, kid_id)
    _open_town_home(page, base_url)
    problems = []
    labels = _iso_pad_labels(page)
    blob = "\n".join(labels + _iso_visible_names(page))
    if STORE_PALETTE_WORKSHOP not in blob or "第 5 欄第 2 行" not in blob:
        problems.append(
            f"scene 1 must keep on-map {STORE_PALETTE_WORKSHOP} at 第 5 欄第 2 行. "
            f"labels={labels!r}"
        )
    if STORE_PALETTE_GUILD in blob:
        problems.append(
            f"scene 1 must not paint stored {STORE_PALETTE_GUILD}. labels={labels!r}"
        )
    _enter_scene2(page, "TC-FE-TOWN-STORE-LIST-01")
    _open_building_list(page)
    _btn, shop_control = _palette_control(page, STORE_PALETTE_WORKSHOP)
    if "已起" not in shop_control:
        problems.append(
            f"on-map {STORE_PALETTE_WORKSHOP} must stay 已起 ({shop_control!r})"
        )
    _btn, guild_control = _palette_control(page, STORE_PALETTE_GUILD)
    if _offered_as_unbuilt_with_price(guild_control):
        problems.append(
            f"{STORE_PALETTE_GUILD} is listed as unbuilt with a price ({guild_control!r}). "
            "stored=1 must not be a new-build row."
        )
    status = _enter_new_build_confirm(page, STORE_PALETTE_GUILD)
    if status is not None and SPEND_CONFIRM_COPY in status:
        problems.append(
            f"choosing stored {STORE_PALETTE_GUILD} entered the new-build path "
            f"({status!r}). That confirm spends; place-from-storage does not."
        )
    if not _workshop_row_ok(test_db_path, kid_id, seeded["workshop"]):
        problems.append(
            f"on-map {STORE_PALETTE_WORKSHOP} row changed while opening the list. "
            f"saw {_rows_named(_building_rows(test_db_path, kid_id), STORE_PALETTE_WORKSHOP)!r}"
        )
    if problems:
        _store_palette_fail("TC-FE-TOWN-STORE-LIST-01", " | ".join(problems))


@pytest.mark.case_id("TC-FE-TOWN-STORE-PLACE-01")
def test_town_store_place_from_warehouse_without_spend(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-STORE-PLACE-01 放返存倉探險公會必須走 unstored，地圖見到、唔扣資源。

    The building list currently offers this stored row as a new build. That
    confirm has to be the 存倉 / #placementBar / unstored path (STORE-LEGACY-02).
    When the list no longer opens 「確定先至扣資源」, place from the 存倉 tab.
    """
    kid_id = fe_ids["kid_id"]
    seeded = _seed_town_store_palette(test_db_path, kid_id)
    guild = seeded["guild"]
    workshop = seeded["workshop"]
    _open_town_home(page, base_url)
    before = _resource_snapshot(page, test_db_path, kid_id)
    problems = []
    on_map, labels, visible = _guild_visible_on_map(page)
    if on_map:
        problems.append(
            f"stored {STORE_PALETTE_GUILD} is already on the map before place. "
            f"labels={labels!r} visible={visible!r}"
        )
    _enter_scene2(page, "TC-FE-TOWN-STORE-PLACE-01")
    _open_building_list(page)
    status = _enter_new_build_confirm(page, STORE_PALETTE_GUILD)
    if status is not None and SPEND_CONFIRM_COPY in status:
        try:
            resp, toast, body, status_after = _submit_ux_confirm(page)
        except Exception as exc:
            problems.append(
                f"list confirm showed {status!r} but did not finish a place "
                f"({exc}). Correct path is 存倉 #placementBar POST /unstored."
            )
        else:
            problems.append(
                "place did not use 存倉 / #placementBar / POST /buildings/<id>/unstored. "
                f"The list confirm showed {status_after or status!r} and "
                f"POST {resp.url} HTTP {resp.status} {body[:180]}. toast={toast!r}. "
                "The 400 is before any deduct, so gold and materials stay put, "
                "but the stored row is not placed."
            )
        _assert_guild_place_outcome(
            page, test_db_path, kid_id, guild, workshop, before, problems
        )
    else:
        problems.extend(_place_guild_from_store(page, guild))
        _assert_guild_place_outcome(
            page, test_db_path, kid_id, guild, workshop, before, problems
        )
    if problems:
        _store_palette_fail("TC-FE-TOWN-STORE-PLACE-01", " | ".join(problems))


@pytest.mark.case_id("TC-FE-TOWN-STORE-CONFIRM-01")
def test_town_store_confirm_does_not_pair_spend_copy_with_already_built(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-STORE-CONFIRM-01 唔好同時出現扣資源文案同「你已經興建咗呢種建築物」。"""
    kid_id = fe_ids["kid_id"]
    seeded = _seed_town_store_palette(test_db_path, kid_id)
    guild = seeded["guild"]
    _open_town_home(page, base_url)
    before = _resource_snapshot(page, test_db_path, kid_id)
    problems = []
    _enter_scene2(page, "TC-FE-TOWN-STORE-CONFIRM-01")
    _open_building_list(page)
    _btn, guild_control = _palette_control(page, STORE_PALETTE_GUILD)
    status = _enter_new_build_confirm(page, STORE_PALETTE_GUILD)
    spend_shown = bool(status) and SPEND_CONFIRM_COPY in status
    if spend_shown:
        try:
            resp, toast, body, status_after = _submit_ux_confirm(page)
        except Exception as exc:
            problems.append(
                f"{SPEND_CONFIRM_COPY} is on screen ({status!r}) but confirm "
                f"did not finish a buildings POST ({exc}). "
                f"palette={guild_control!r}"
            )
        else:
            spend_still = SPEND_CONFIRM_COPY in status or SPEND_CONFIRM_COPY in status_after
            already = ALREADY_BUILT_COPY in toast or ALREADY_BUILT_COPY in body
            new_build = "/unstored" not in resp.url and resp.url.rstrip("/").endswith("/buildings")
            if spend_still and already:
                problems.append(
                    f"spend-confirm copy is shown together with {ALREADY_BUILT_COPY}. "
                    f"status={status_after!r} toast={toast!r} "
                    f"HTTP {resp.status} {body[:180]} url={resp.url} "
                    f"palette={guild_control!r}"
                )
            elif spend_still and new_build:
                problems.append(
                    "確定 posted a new build (/buildings) for a stored row "
                    f"while showing {SPEND_CONFIRM_COPY}. "
                    f"HTTP {resp.status} {body[:180]} url={resp.url} toast={toast!r}"
                )
    problems.extend(_place_guild_from_store(page, guild))
    after = _resource_snapshot(page, test_db_path, kid_id)
    if not _resources_unchanged(before, after):
        problems.append(
            "after the correct 存倉 place, gold and materials must be unchanged "
            f"({_resource_delta(before, after)})"
        )
    ok, rows = _guild_placed_same_row(test_db_path, kid_id, guild)
    if not ok:
        problems.append(
            f"correct place must keep the same {STORE_PALETTE_GUILD} row and "
            f"set stored=0 inside the 8×8 map. saw {rows!r}"
        )
    if problems:
        _store_palette_fail("TC-FE-TOWN-STORE-CONFIRM-01", " | ".join(problems))


# ── TC-FE-TOWN-STORE-UX: warehouse place stays on the four-scene 8×8 pad ──
#
# After #35, the 建築清單 warehouse row calls placeFromStore, which calls
# legacy startUnstoreBuilding. That adds #placementBar.active. The sibling
# rule `#placementBar.active ~ #townMap { visibility:hidden }` hides the iso
# map and leaves the 24×16 #townCanvasWrapper .valid-plot / ↘️ grid.
# Acceptance: stay on the four-scene 8×8 pad and confirm with POST /unstored.
# Filter: `-k store_ux`.

_STORE_UX_CHROME_JS = r"""
() => {
  const bar = document.getElementById('placementBar');
  const map = document.getElementById('townMap');
  const wrap = document.getElementById('townCanvasWrapper');
  const barCs = bar ? getComputedStyle(bar) : null;
  const mapCs = map ? getComputedStyle(map) : null;
  const wrapCs = wrap ? getComputedStyle(wrap) : null;
  const plots = [...document.querySelectorAll('#townCanvasWrapper .valid-plot')];
  let arrows = 0;
  let confirmCells = 0;
  let faintPlots = 0;
  for (const el of plots) {
    const text = el.innerText || '';
    if (text.includes('↘️')) arrows += 1;
    if (text.includes('按確認')) confirmCells += 1;
    const opacity = parseFloat(getComputedStyle(el).opacity || '1');
    if (opacity < 0.9) faintPlots += 1;
  }
  const confirmBtn = bar ? bar.querySelector('.confirm-btn') : null;
  const pads = [...document.querySelectorAll('#townMap .pad button, #village .pad button')];
  let visiblePads = 0;
  for (const el of pads) {
    const cs = getComputedStyle(el);
    if (cs.visibility !== 'hidden' && cs.display !== 'none') visiblePads += 1;
  }
  const stage = document.querySelector('body.kt-artstage .gsw');
  const tab = document.getElementById('tab-town');
  function clipRoot() {
    return stage || tab || document.documentElement;
  }
  function rectOf(el) {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {
      x: Math.round(r.x), y: Math.round(r.y),
      w: Math.round(r.width), h: Math.round(r.height),
      sw: el.scrollWidth, cw: el.clientWidth
    };
  }
  function cutBy(el, root) {
    if (!el || !root) return null;
    const rect = el.getBoundingClientRect();
    const box = root.getBoundingClientRect();
    const width = Math.min(rect.right, box.right) - Math.max(rect.left, box.left);
    const height = Math.min(rect.bottom, box.bottom) - Math.max(rect.top, box.top);
    return {
      fullW: Math.round(rect.width),
      fullH: Math.round(rect.height),
      visW: Math.round(Math.max(0, width)),
      visH: Math.round(Math.max(0, height)),
      cut: width < rect.width - 2 || height < rect.height - 2
    };
  }
  function visibleChars(el, root) {
    if (!el || !root) return '';
    const box = root.getBoundingClientRect();
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let out = '';
    let node;
    while ((node = walker.nextNode())) {
      const text = node.textContent || '';
      for (let i = 0; i < text.length; i += 1) {
        const range = document.createRange();
        range.setStart(node, i);
        range.setEnd(node, i + 1);
        const rects = range.getClientRects();
        let seen = false;
        for (const r of rects) {
          const w = Math.min(r.right, box.right) - Math.max(r.left, box.left);
          const h = Math.min(r.bottom, box.bottom) - Math.max(r.top, box.top);
          if (w > 0.4 && h > 0.4) { seen = true; break; }
        }
        if (seen) out += text[i];
        range.detach();
      }
    }
    return out.replace(/\s+/g, ' ').trim();
  }
  const span = bar ? bar.querySelector('span') : null;
  const root = clipRoot();
  const visibleBar = visibleChars(bar, root);
  const visibleConfirm = visibleChars(confirmBtn, root);
  const barCut = cutBy(bar, root);
  const confirmCut = cutBy(confirmBtn, root);
  const spanCut = cutBy(span, root);
  return {
    barClass: bar ? bar.className : '',
    barActive: !!(bar && bar.classList.contains('active')),
    barDisplay: barCs ? barCs.display : '',
    barBg: barCs ? barCs.backgroundColor : '',
    barText: bar ? (bar.innerText || '').replace(/\s+/g, ' ').trim() : '',
    barClipped: !!(barCut && barCut.cut) || !!(spanCut && spanCut.cut) || !!(confirmCut && confirmCut.cut),
    confirmText: confirmBtn ? (confirmBtn.textContent || '').trim() : '',
    confirmClipped: !!(confirmCut && confirmCut.cut),
    visibleBar: visibleBar,
    visibleConfirm: visibleConfirm,
    barCut: barCut,
    spanCut: spanCut,
    confirmCut: confirmCut,
    barBox: rectOf(bar),
    spanBox: rectOf(span),
    confirmBox: rectOf(confirmBtn),
    mapVisibility: mapCs ? mapCs.visibility : '',
    mapPointer: mapCs ? mapCs.pointerEvents : '',
    scene: map ? (map.getAttribute('aria-label') || '') : '',
    mapClass: map ? map.className : '',
    plotCount: plots.length,
    arrowCount: arrows,
    confirmCells: confirmCells,
    faintPlots: faintPlots,
    visiblePads: visiblePads,
    domPads: pads.length,
    wrapShown: !!(wrapCs && wrapCs.display !== 'none' && wrapCs.visibility !== 'hidden'),
  };
}
"""


def _store_ux_fail(case_id, detail):
    pytest.fail(
        f"{case_id}: {detail} "
        "Placing a stored building from the four-scene 建築清單 must stay on the "
        "visible 8×8 iso pad. #placementBar must not gain class active, because "
        "#placementBar.active ~ #townMap { visibility:hidden } hides the town map "
        "and exposes the legacy 24×16 #townCanvasWrapper .valid-plot / ↘️ grid "
        "and the purple 「確認建造」 bar. Confirm with POST /buildings/<id>/unstored "
        "on that four-scene pad. Gold and materials stay unchanged, and the same "
        "row becomes stored=0."
    )


def _store_ux_chrome(page):
    return page.evaluate(_STORE_UX_CHROME_JS)


def _wait_warehouse_place_ui(page):
    """Legacy bar paints immediately; the 24×16 plots follow loadTown."""
    page.wait_for_function(
        """() => {
          const bar = document.getElementById('placementBar');
          const map = document.getElementById('townMap');
          const active = !!(bar && bar.classList.contains('active'));
          const scene3 = !!(map && /is-scene-3/.test(map.className || ''));
          const confirm = document.getElementById('btnUxConfirm');
          let confirmOn = false;
          if (confirm) {
            const cs = getComputedStyle(confirm);
            const bar = confirm.closest('#uxPlaceBar');
            confirmOn = !!bar && !bar.hidden && cs.visibility !== 'hidden' && cs.display !== 'none';
          }
          return active || scene3 || confirmOn;
        }""",
        timeout=8000,
    )
    if page.locator("#placementBar.active").count() == 0:
        return
    try:
        page.wait_for_function(
            "() => document.querySelectorAll('#townCanvasWrapper .valid-plot').length >= 48",
            timeout=8000,
        )
    except Exception:
        pass


def _reveal_legacy_confirm(page):
    """Select one legacy plot so the purple 「確認建造」 state is on screen.

    Does not click the confirm button, so this does not POST.
    """
    plots = page.locator("#townCanvasWrapper .valid-plot")
    if plots.count() == 0:
        return
    plots.first.dispatch_event("click")
    try:
        page.locator("#placementBar .confirm-btn").wait_for(state="attached", timeout=4000)
    except Exception:
        return
    try:
        page.wait_for_function(
            """() => [...document.querySelectorAll('#townCanvasWrapper .valid-plot')]
              .some((el) => (el.innerText || '').includes('按確認'))""",
            timeout=8000,
        )
    except Exception:
        pass


def _collapsed(text):
    return re.sub(r"\s+", "", text or "")


def _confirm_fragment(chrome):
    """On-screen confirm copy when the purple bar is truncated.

    Preview leaves only a piece such as 「確認」. A full 「確認建造」 that is
    still the legacy purple strip is reported by the caller separately.
    """
    visible = chrome.get("visibleBar") or ""
    visible_confirm = chrome.get("visibleConfirm") or ""
    full = chrome.get("barText") or ""
    painted = _collapsed(visible)
    dom = _collapsed(full)
    clipped = bool(chrome.get("barClipped") or chrome.get("confirmClipped"))
    if clipped or (dom and painted and painted != dom and "確認" in painted):
        shown = visible_confirm or visible
        return shown or "確認"
    if "確認" in painted and "確認建造" not in painted and (
        "確認建造" in dom or "確認建造" in (chrome.get("confirmText") or "")
    ):
        return visible_confirm or visible or "確認"
    return None


def _legacy_place_problems(chrome):
    """Acceptance violations while a stored building is being placed.

    The preview failure is the legacy purple #placementBar (often clipped so
    only 「確認」 remains), a faint ↘️ / .valid-plot flood, and green 「按確認」
    cells, instead of the four-scene 8×8 iso pad.
    """
    problems = []
    if chrome["barActive"]:
        fragment = _confirm_fragment(chrome)
        if fragment:
            problems.append(
                "purple #placementBar is clipped/truncated: the visible confirm "
                f"copy is only {fragment!r} (preview leaves 「確認」). "
                f"DOM text was {chrome['barText']!r}, background={chrome['barBg']!r}"
            )
        else:
            problems.append(
                "#placementBar has class active. It is the legacy purple confirm "
                f"strip (background={chrome['barBg']!r}, display={chrome['barDisplay']!r}, "
                f"on-screen {chrome.get('visibleBar')!r}). "
                "Preview clips this same strip so only 「確認」 remains. "
                "That bar must not appear while placing a stored building"
            )
    if chrome["mapVisibility"] == "hidden":
        problems.append(
            "#townMap computed visibility is hidden "
            f"(pointer-events={chrome['mapPointer']!r}). "
            "#placementBar.active ~ #townMap { visibility:hidden } hides the four-scene map"
        )
    if chrome["plotCount"] >= 48 or chrome["arrowCount"] >= 24 or chrome.get("faintPlots", 0) >= 24:
        problems.append(
            "#townCanvasWrapper exposes a large legacy placement grid of faint "
            f"per-cell icons: {chrome.get('faintPlots', 0)} faint .valid-plot, "
            f"{chrome['plotCount']} .valid-plot total, and {chrome['arrowCount']} ↘️ "
            f"(wrap shown={chrome['wrapShown']}). "
            "That is the broken 24×16-style UI, not the four-scene 8×8 iso pad"
        )
    if chrome["confirmCells"]:
        problems.append(
            f"{chrome['confirmCells']} green .valid-plot cell(s) show 「按確認」"
        )
    on_iso = (
        chrome["mapVisibility"] != "hidden"
        and chrome["visiblePads"] == TOWN_GRID_COLS * TOWN_GRID_ROWS
        and "場景" in (chrome["scene"] or "")
    )
    if not on_iso:
        problems.append(
            "placement left the visible four-scene 8×8 iso pad "
            f"(visible pads {chrome['visiblePads']}, dom pads {chrome['domPads']}, "
            f"aria={chrome['scene']!r}, class={chrome['mapClass']!r})"
        )
    return problems


def _four_scene_confirm_button(page):
    """Confirm control on the iso sheet. The legacy #placementBar button does not count."""
    buttons = page.locator("#townMap").get_by_role(
        "button", name=re.compile(r"確定放置|確定|確認")
    )
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        try:
            if not btn.is_visible():
                continue
        except Exception:
            continue
        label = _control_blob(btn)
        if "取消" in label:
            continue
        return btn
    return None


def _confirm_stored_on_four_scene(page):
    """Pick an iso pad if needed, then POST /unstored from the four-scene confirm."""
    problems = []
    scene = page.locator("#townMap").get_attribute("aria-label") or ""
    if "場景 3" not in scene:
        try:
            _select_empty_pad(page, 1, 1)
        except Exception as exc:
            problems.append(f"four-scene empty pad was not usable ({exc})")
            return problems
        go = _go_place_button(page)
        try:
            if go.count() and go.first.is_visible() and go.first.is_enabled():
                go.first.click()
        except Exception:
            pass
    confirm = _four_scene_confirm_button(page)
    if confirm is None:
        problems.append(
            "no four-scene confirm (確定放置 / 確定) on the visible 8×8 iso pad, "
            "so POST /buildings/<id>/unstored did not run. "
            "The legacy #placementBar 「確認建造」 button does not count."
        )
        return problems
    try:
        with page.expect_response(
            lambda r: r.request.method == "POST" and "/buildings/" in r.url,
            timeout=8000,
        ) as resp_info:
            confirm.click()
        resp = resp_info.value
    except Exception as exc:
        problems.append(f"four-scene confirm did not POST /unstored ({exc})")
        return problems
    if "/unstored" not in resp.url:
        problems.append(
            "confirm must POST /buildings/<id>/unstored for the stored row. "
            f"url={resp.url} HTTP {resp.status}"
        )
    elif resp.status not in (200, 201):
        try:
            body = resp.text()[:300]
        except Exception:
            body = ""
        problems.append(f"unstored failed HTTP {resp.status}: {body}")
    page.wait_for_timeout(400)
    return problems


@pytest.mark.case_id("TC-FE-TOWN-STORE-UX-01")
def test_town_store_ux_place_stays_on_four_scene(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-STORE-UX-01 清單放返存倉屋要留喺四場景 8×8，確認走 unstored。"""
    kid_id = fe_ids["kid_id"]
    seeded = _seed_town_store_palette(test_db_path, kid_id)
    guild = seeded["guild"]
    workshop = seeded["workshop"]
    _open_town_home(page, base_url)
    before = _resource_snapshot(page, test_db_path, kid_id)
    case_id = "TC-FE-TOWN-STORE-UX-01"
    _enter_scene2(page, case_id)
    _open_building_list(page)
    btn, control = _palette_control(page, STORE_PALETTE_GUILD)
    problems = []
    if btn is None:
        problems.append(f"建築清單 has no {STORE_PALETTE_GUILD} row to place")
        _store_ux_fail(case_id, " | ".join(problems))
    if "放返" not in control and "存倉" not in control:
        problems.append(
            f"warehouse row should be the list place control (存倉 / 放返), "
            f"saw {control!r}"
        )
    btn.click()
    try:
        _wait_warehouse_place_ui(page)
    except Exception as exc:
        problems.append(f"place did not start from the 建築清單 row ({exc})")
        _store_ux_fail(case_id, " | ".join(problems))
    chrome = _store_ux_chrome(page)
    if chrome["barActive"] and chrome["plotCount"] > 0 and "確認建造" not in chrome["confirmText"]:
        _reveal_legacy_confirm(page)
        chrome = _store_ux_chrome(page)
    problems.extend(_legacy_place_problems(chrome))
    if problems:
        problems.append(
            "Did not confirm on the four-scene 8×8 pad, so POST /buildings/<id>/unstored "
            "was not sent from that UI. Gold, materials, and the stored row were left as seeded."
        )
    else:
        problems.extend(_confirm_stored_on_four_scene(page))
        _assert_guild_place_outcome(
            page, test_db_path, kid_id, guild, workshop, before, problems
        )
    if problems:
        _store_ux_fail(case_id, " | ".join(problems))


# ── TC-FE-TOWN-UX-UPGRADE-*: scene 4 cost + confirm (red on #38 tip) ──
#
# Design mock tip 3b4671d (PR #27, do not merge) scene 4:
#   tap a placed building → #actionSheet shows the cost → confirm → then upgrade.
#   Not a one-click upgrade. Mock ids: #actionSheet, #sheetTitle, #sheetLevel,
#   #sheetNote, #btnUpgrade. The mock's demo purse (💰50 🪵2) is only the shape;
#   product numbers follow upgrade_building:
#   gold = max(1, floor(level * 100 * shop discount)), mats = base * (level + 1).
# On #38 tip, onUpgrade() POSTs on the first click and #btnUpgrade is only 「升級」.
# 整道具／接任務 stay out of scope. Do not weaken UX-05 or store_ux.

UPGRADE_UX_TARGET = "健身室"
UPGRADE_UX_LEVEL = 2
UPGRADE_UX_SHOP = "商店"
_UPGRADE_CONFIRM_NAME = re.compile(r"確定|確認")
_UPGRADE_PLACE_CONFIRM = re.compile(r"確定放置|確認建造|去擺位置")
_UPGRADE_CANCEL_NAME = re.compile(r"取消")
_UPGRADE_SHORT_RE = re.compile(r"唔夠|不足|未夠|不夠|買唔起")
UPGRADE_UX_RED = (
    "Design mock 3b4671d scene 4 is tap building → #actionSheet showing gold and "
    "material need → confirm → then upgrade. Not one click. "
    "On this tip #btnUpgrade is only 「升級」 and the first tap POSTs /upgrade. "
    "Show the backend cost in or near #actionSheet (or on the confirm layer): "
    "gold = floor(level*100 × shop discount), materials = base×(level+1) "
    "(have/need or at least need). The mock's 💰50 🪵2 is the demo shape, not the amount. "
    "Short resources must disable #btnUpgrade or the confirm, and must not POST. "
    "A full purse: the first #btnUpgrade tap only opens confirmation "
    "(cost, building name, level); 取消 does not POST; only confirm POSTs. "
    "整道具／接任務 are out of scope."
)


def _upgrade_ux_fail(case_id, detail):
    pytest.fail(f"{case_id}: {detail} {UPGRADE_UX_RED}")


def _upgrade_quote(test_db_path, kid_id, name):
    """Same charge as upgrade_building: discounted gold, materials scaled by level+1."""
    db = connect_db(test_db_path)
    row = db.execute(
        """
        SELECT b.level AS level, bd.materials AS materials
        FROM buildings b
        JOIN building_defs bd ON bd.id = b.def_id
        WHERE b.kid_id=? AND bd.name=? AND COALESCE(b.stored, 0)=0
        ORDER BY b.id DESC LIMIT 1
        """,
        (kid_id, name),
    ).fetchone()
    shop = db.execute(
        """
        SELECT b.level AS level, bd.buff_vals AS buff_vals
        FROM buildings b
        JOIN building_defs bd ON bd.id = b.def_id
        WHERE b.kid_id=? AND bd.buff_type='discount' AND COALESCE(b.stored, 0)=0
        ORDER BY b.level DESC LIMIT 1
        """,
        (kid_id,),
    ).fetchone()
    db.close()
    assert row, f"placed {name} missing from the synthetic kid"
    level = int(row["level"])
    base_gold = level * 100
    gold = base_gold
    if shop and shop["buff_vals"]:
        vals = json.loads(shop["buff_vals"] or "[]")
        if vals:
            idx = max(0, min(int(shop["level"] or 1) - 1, len(vals) - 1))
            gold = max(1, math.floor(base_gold * float(vals[idx])))
    raw = json.loads(row["materials"] or "{}")
    mats = {}
    for key, qty in raw.items():
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            mats[str(key)] = qty * (level + 1)
    return {
        "name": name,
        "level": level,
        "base_gold": base_gold,
        "gold": gold,
        "mats": mats,
    }


def _seed_upgrade_sheet(test_db_path, kid_id, *, gold, wood, brick):
    """Lv.1 商店 (discount 0.9) plus Lv.2 健身室. Quote is floor(200×0.9)=180, wood 30, brick 15.

    Synthetic kid only. No production DB and no real PIN.
    """
    set_kid_points(test_db_path, kid_id, gold)
    grant_inventory(
        test_db_path,
        kid_id,
        {"wood": wood, "brick": brick, "glass": 7, "gear": 9, "gem": 3},
    )
    db = connect_db(test_db_path)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    insert_building(
        test_db_path,
        kid_id,
        building_def_id(test_db_path, UPGRADE_UX_SHOP),
        level=1,
        cell_x=0,
        cell_y=2,
    )
    insert_building(
        test_db_path,
        kid_id,
        building_def_id(test_db_path, UPGRADE_UX_TARGET),
        level=UPGRADE_UX_LEVEL,
        cell_x=2,
        cell_y=1,
    )
    quote = _upgrade_quote(test_db_path, kid_id, UPGRADE_UX_TARGET)
    assert quote["level"] == UPGRADE_UX_LEVEL, quote
    assert quote["base_gold"] == UPGRADE_UX_LEVEL * 100, quote
    assert quote["gold"] == 180, quote  # floor(2*100*0.9) with the Lv.1 shop
    assert quote["mats"] == {"wood": 30, "brick": 15}, quote  # base*(level+1)
    return quote


def _placed_level(test_db_path, kid_id, name):
    db = connect_db(test_db_path)
    row = db.execute(
        """
        SELECT b.level AS level FROM buildings b
        JOIN building_defs bd ON bd.id = b.def_id
        WHERE b.kid_id=? AND bd.name=? AND COALESCE(b.stored, 0)=0
        ORDER BY b.id DESC LIMIT 1
        """,
        (kid_id, name),
    ).fetchone()
    db.close()
    assert row, f"placed {name} missing"
    return int(row["level"])


def _has_whole_number(text, number):
    return re.search(rf"(?<!\d){int(number)}(?!\d)", text or "") is not None


def _missing_upgrade_needs(text, quote):
    missing = []
    if not _has_whole_number(text, quote["gold"]):
        missing.append(f"gold {quote['gold']}")
    for mat, qty in sorted(quote["mats"].items()):
        if not _has_whole_number(text, qty):
            missing.append(f"{mat} {qty}")
    return missing


def _upgrade_surface_text(page):
    """#actionSheet and a confirm layer next to it. Header chips do not count.

    Mock ids (3b4671d): #actionSheet, #sheetTitle, #sheetLevel, #sheetNote, #btnUpgrade.
    """
    return page.evaluate(
        """() => {
          const chunks = [];
          const take = (el) => {
            if (!el) return;
            const cs = getComputedStyle(el);
            if (el.hidden || cs.display === 'none' || cs.visibility === 'hidden') return;
            chunks.push(el.innerText || '');
            const label = el.getAttribute && el.getAttribute('aria-label');
            if (label) chunks.push(label);
          };
          ['actionSheet', 'sheetTitle', 'sheetLevel', 'sheetNote', 'btnUpgrade'].forEach((id) => {
            take(document.getElementById(id));
          });
          document.querySelectorAll(
            '#actionSheet [data-upgrade-confirm], [data-upgrade-confirm], .upgrade-confirm, [role="dialog"]'
          ).forEach(take);
          return chunks.join('\\n');
        }"""
    )


def _upgrade_button(page):
    loc = page.locator("#actionSheet #btnUpgrade, #btnUpgrade")
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if btn.is_visible():
                return btn
        except Exception:
            continue
    named = page.get_by_role("button", name=re.compile(r"升級"))
    for i in range(named.count()):
        btn = named.nth(i)
        try:
            if btn.is_visible():
                return btn
        except Exception:
            continue
    return None


def _button_label(btn):
    try:
        text = btn.inner_text() or ""
    except Exception:
        text = ""
    try:
        aria = btn.get_attribute("aria-label") or ""
    except Exception:
        aria = ""
    return (text + " " + aria).strip()


def _buttons_under(page, root_sel, pattern, *, skip=None):
    root = page.locator(root_sel)
    if root.count() == 0:
        return []
    loc = root.get_by_role("button", name=pattern)
    found = []
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if not btn.is_visible():
                continue
        except Exception:
            continue
        label = _button_label(btn)
        if skip is not None and skip.search(label):
            continue
        found.append(btn)
    return found


def _upgrade_confirm_buttons(page):
    """Confirm controls in #actionSheet or a dialog. Place-bar 確定放置 does not count."""
    found = []
    for sel in ("#actionSheet", "[role='dialog']", "[data-upgrade-confirm]", ".upgrade-confirm"):
        found.extend(
            _buttons_under(page, sel, _UPGRADE_CONFIRM_NAME, skip=_UPGRADE_PLACE_CONFIRM)
        )
    return found


def _upgrade_cancel_buttons(page):
    found = []
    for sel in ("#actionSheet", "[role='dialog']", "[data-upgrade-confirm]", ".upgrade-confirm"):
        found.extend(_buttons_under(page, sel, _UPGRADE_CANCEL_NAME))
    return found


def _control_blocked(btn, surface):
    """Disabled, aria-disabled, pointer-events:none, or a visible short-resource phrase."""
    try:
        if not btn.is_enabled():
            return True
    except Exception:
        return True
    aria = ""
    try:
        aria = (btn.get_attribute("aria-disabled") or "").lower()
    except Exception:
        aria = ""
    if aria == "true":
        return True
    try:
        pe = btn.evaluate("el => getComputedStyle(el).pointerEvents")
    except Exception:
        pe = ""
    if pe == "none":
        return True
    return _UPGRADE_SHORT_RE.search(surface or "") is not None


def _watch_upgrade_posts(page):
    hits = []

    def on_response(resp):
        req = resp.request
        url = req.url or ""
        if (
            req.method == "POST"
            and "/buildings/" in url
            and url.rstrip("/").endswith("/upgrade")
        ):
            hits.append({"url": url, "status": resp.status})

    page.on("response", on_response)
    return hits


def _chip_snapshot(page, quote):
    snap = {"gold": _hud_gold(page)}
    mats = set(quote["mats"]) | {"wood", "brick", "glass", "gear"}
    for mat in sorted(mats):
        snap[mat] = _hud_mat_count(page, mat)
    return snap


def _expected_after_upgrade(before, quote):
    after = dict(before)
    after["gold"] = before["gold"] - quote["gold"]
    for mat, qty in quote["mats"].items():
        after[mat] = before.get(mat, 0) - qty
    return after


def _open_scene4_sheet(page, case_id, name):
    """Tap a placed building on scene 1. Mock 3b4671d opens #actionSheet from that tap."""
    pad = page.locator("#townMap, #village").get_by_role(
        "button",
        name=re.compile(rf"第\s*\d+\s*欄第\s*\d+\s*行，{re.escape(name)}(?:，|$)"),
    )
    if pad.count() == 0 or not pad.first.is_visible():
        _upgrade_ux_fail(
            case_id,
            f"Scene 1 has no tappable pad for placed {name}. "
            "Design mock 3b4671d: tap the building to open #actionSheet.",
        )
    pad.first.click()
    sheet = page.locator("#actionSheet")
    try:
        sheet.wait_for(state="visible", timeout=8000)
    except Exception:
        _upgrade_ux_fail(
            case_id,
            f"Tapping placed {name} did not open #actionSheet. "
            "Design mock 3b4671d scene 4 is that sheet, then cost, then confirm.",
        )
    title = (page.locator("#sheetTitle").inner_text() or "").strip()
    if name not in title:
        _upgrade_ux_fail(
            case_id,
            f"#sheetTitle should name {name} after the tap, saw {title!r}.",
        )
    upgrade = page.locator("#actionSheet #btnUpgrade")
    if upgrade.count() == 0 or not upgrade.first.is_visible():
        upgrade = _upgrade_button(page)
        if upgrade is None:
            _upgrade_ux_fail(case_id, "#actionSheet has no visible #btnUpgrade.")
        return upgrade
    return upgrade.first


def _confirm_region_text(btn):
    try:
        return btn.evaluate(
            """(el) => {
              const root = el.closest(
                '#actionSheet, .action-sheet, [role="dialog"], [data-upgrade-confirm], .upgrade-confirm'
              ) || el.parentElement;
              const label = el.getAttribute('aria-label') || '';
              return ((root && root.innerText) || '') + '\\n' + label;
            }"""
        )
    except Exception:
        return _button_label(btn)


@pytest.mark.case_id("TC-FE-TOWN-UX-UPGRADE-COST-01")
def test_town_ux_upgrade_cost_sheet_shows_gold_and_mats(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-UPGRADE-COST-01 撳屋打開 #actionSheet，上面或確認層要有金幣同材料 need。"""
    case_id = "TC-FE-TOWN-UX-UPGRADE-COST-01"
    kid_id = fe_ids["kid_id"]
    quote = _seed_upgrade_sheet(test_db_path, kid_id, gold=5000, wood=80, brick=40)
    _open_town_home(page, base_url)
    posts = _watch_upgrade_posts(page)
    upgrade = _open_scene4_sheet(page, case_id, UPGRADE_UX_TARGET)
    surface = _upgrade_surface_text(page)
    label = _button_label(upgrade)
    missing = _missing_upgrade_needs(surface, quote)
    if missing and not _upgrade_confirm_buttons(page):
        upgrade.click()
        page.wait_for_timeout(1200)
        surface = _upgrade_surface_text(page)
        for btn in _upgrade_confirm_buttons(page):
            surface += "\n" + _confirm_region_text(btn)
        missing = _missing_upgrade_needs(surface, quote)
    problems = []
    if missing:
        problems.append(
            "After tapping the building, #actionSheet / #btnUpgrade / #sheetNote "
            "(or the confirm layer the first #btnUpgrade tap opens) must show gold need "
            f"{quote['gold']} (floor({quote['base_gold']}×0.9 Lv.1 商店 discount)) "
            f"and materials {quote['mats']} (base×(level+1)); have/need or at least need. "
            f"Missing {missing}. #btnUpgrade={label!r}. Sheet={surface!r}."
        )
    if posts:
        problems.append(
            "The first #btnUpgrade tap POSTed /upgrade "
            f"({posts}) instead of opening a confirm layer near #actionSheet. "
            f"Level is now {_placed_level(test_db_path, kid_id, UPGRADE_UX_TARGET)}."
        )
    if problems:
        _upgrade_ux_fail(case_id, " | ".join(problems))


@pytest.mark.case_id("TC-FE-TOWN-UX-UPGRADE-COST-02")
def test_town_ux_upgrade_cost_insufficient_does_not_post(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-UPGRADE-COST-02 材料唔夠：升級／確認唔好撳得，亦唔好 POST。"""
    case_id = "TC-FE-TOWN-UX-UPGRADE-COST-02"
    kid_id = fe_ids["kid_id"]
    quote = _seed_upgrade_sheet(test_db_path, kid_id, gold=5000, wood=80, brick=14)
    _open_town_home(page, base_url)
    posts = _watch_upgrade_posts(page)
    upgrade = _open_scene4_sheet(page, case_id, UPGRADE_UX_TARGET)
    hud_before = _chip_snapshot(page, quote)
    surface = _upgrade_surface_text(page)
    if upgrade.is_enabled() and not _control_blocked(upgrade, surface):
        upgrade.click()
        page.wait_for_timeout(1200)
        surface = _upgrade_surface_text(page)
    confirms = _upgrade_confirm_buttons(page)
    enabled_confirm = [
        btn for btn in confirms if btn.is_enabled() and not _control_blocked(btn, surface)
    ]
    if enabled_confirm and not posts:
        enabled_confirm[0].click()
        page.wait_for_timeout(1200)
        surface = _upgrade_surface_text(page)
    problems = []
    if posts:
        problems.append(
            "insufficient brick (have 14, need "
            f"{quote['mats']['brick']}) must not call POST /upgrade; saw {posts}. "
            "A 400 from the API still counts as a call."
        )
    spend_open = bool(enabled_confirm) or (
        not confirms and upgrade.is_enabled() and not _control_blocked(upgrade, surface)
    )
    if spend_open:
        problems.append(
            "upgrade/confirm stays actionable while brick is short "
            f"(have 14, need {quote['mats']['brick']}; gold {quote['gold']} is enough). "
            f"Label={_button_label(upgrade)!r}. Surface={surface!r}."
        )
    level_now = _placed_level(test_db_path, kid_id, UPGRADE_UX_TARGET)
    if level_now != UPGRADE_UX_LEVEL:
        problems.append(f"level changed {UPGRADE_UX_LEVEL} -> {level_now} without enough brick.")
    hud_after = _chip_snapshot(page, quote)
    if hud_after != hud_before:
        problems.append(f"HUD changed while resources were short: {hud_before} -> {hud_after}.")
    brick_now = inventory_map(test_db_path, kid_id).get("brick")
    if brick_now != 14:
        problems.append(f"brick inventory changed from 14 to {brick_now}.")
    if problems:
        _upgrade_ux_fail(case_id, " | ".join(problems))


@pytest.mark.case_id("TC-FE-TOWN-UX-UPGRADE-CONFIRM-01")
def test_town_ux_upgrade_confirm_cancel_then_post(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-UPGRADE-CONFIRM-01 唔好即刻升級；取消唔 POST；確定先扣。"""
    case_id = "TC-FE-TOWN-UX-UPGRADE-CONFIRM-01"
    kid_id = fe_ids["kid_id"]
    quote = _seed_upgrade_sheet(test_db_path, kid_id, gold=5000, wood=80, brick=40)
    _open_town_home(page, base_url)
    posts = _watch_upgrade_posts(page)
    upgrade = _open_scene4_sheet(page, case_id, UPGRADE_UX_TARGET)
    hud_before = _chip_snapshot(page, quote)
    level_before = _placed_level(test_db_path, kid_id, UPGRADE_UX_TARGET)
    label = _button_label(upgrade)
    upgrade.click()
    page.wait_for_timeout(1200)
    confirms = _upgrade_confirm_buttons(page)
    cancels = _upgrade_cancel_buttons(page)
    problems = []
    if posts:
        problems.append(
            f"the first #btnUpgrade tap POSTed /upgrade ({posts}); "
            f"label was {label!r}. That tap must only open confirmation near #actionSheet."
        )
    level_mid = _placed_level(test_db_path, kid_id, UPGRADE_UX_TARGET)
    if level_mid != level_before:
        problems.append(
            f"level changed {level_before} -> {level_mid} before 確定. "
            "升級 must not spend on the first click."
        )
    if not confirms:
        problems.append(
            "no confirmation button inside #actionSheet or a confirm dialog "
            "(確定／確認, not 確定放置) appeared after the first #btnUpgrade tap."
        )
    else:
        copy = "\n".join(_confirm_region_text(btn) for btn in confirms)
        if UPGRADE_UX_TARGET not in copy:
            problems.append(f"confirm step must show the building name {UPGRADE_UX_TARGET}. copy={copy!r}")
        shown_level = re.search(r"(?:Lv\.?\s*|等級\s*)(\d+)", copy)
        shown_n = int(shown_level.group(1)) if shown_level else None
        if shown_n not in (level_before, level_before + 1):
            problems.append(
                f"confirm step must show the building level (Lv.{level_before} or Lv.{level_before + 1}). "
                f"copy={copy!r}"
            )
        missing = _missing_upgrade_needs(copy, quote)
        if missing:
            problems.append(
                "confirm step must show the resources to deduct "
                f"(gold {quote['gold']}, mats {quote['mats']}). Missing {missing}. copy={copy!r}"
            )
    if problems:
        _upgrade_ux_fail(case_id, " | ".join(problems))

    if not cancels:
        _upgrade_ux_fail(case_id, "confirm step has no 取消 button.")
    cancels[0].click()
    page.wait_for_timeout(800)
    problems = []
    if posts:
        problems.append(f"取消 must not POST /upgrade; saw {posts}.")
    level_cancel = _placed_level(test_db_path, kid_id, UPGRADE_UX_TARGET)
    if level_cancel != level_before:
        problems.append(f"取消 changed the level {level_before} -> {level_cancel}.")
    hud_cancel = _chip_snapshot(page, quote)
    if hud_cancel != hud_before:
        problems.append(f"取消 changed the HUD {hud_before} -> {hud_cancel}.")
    if problems:
        _upgrade_ux_fail(case_id, " | ".join(problems))

    upgrade = _upgrade_button(page)
    if upgrade is None:
        upgrade = _open_scene4_sheet(page, case_id, UPGRADE_UX_TARGET)
    upgrade.click()
    page.wait_for_timeout(800)
    if posts:
        _upgrade_ux_fail(
            case_id,
            f"the second 升級 POSTed before 確定 ({posts}).",
        )
    confirms = _upgrade_confirm_buttons(page)
    enabled = [btn for btn in confirms if btn.is_enabled()]
    if not enabled:
        _upgrade_ux_fail(case_id, "確認／確定 was not visible and enabled after 升級.")
    with page.expect_response(
        lambda r: r.request.method == "POST"
        and "/buildings/" in r.url
        and r.url.rstrip("/").endswith("/upgrade"),
        timeout=8000,
    ) as posted:
        enabled[0].click()
    if posted.value.status not in (200, 201):
        _upgrade_ux_fail(
            case_id,
            f"確定 must POST /upgrade successfully, got HTTP {posted.value.status}.",
        )
    try:
        page.wait_for_function(
            """(gold) => {
              const el = document.getElementById('hudCo');
              return el && parseInt(el.textContent, 10) === gold;
            }""",
            arg=hud_before["gold"] - quote["gold"],
            timeout=8000,
        )
    except Exception:
        pass
    sheet_level, sheet_text = _sheet_level(page)
    level_after = _placed_level(test_db_path, kid_id, UPGRADE_UX_TARGET)
    hud_after = _chip_snapshot(page, quote)
    want = _expected_after_upgrade(hud_before, quote)
    problems = []
    if level_after != level_before + 1:
        problems.append(f"DB level should be {level_before + 1}, got {level_after}.")
    if sheet_level != level_before + 1:
        problems.append(
            f"sheet level should be Lv.{level_before + 1}, saw {sheet_level}. sheet={sheet_text!r}"
        )
    if hud_after != want:
        problems.append(
            f"HUD should drop gold {quote['gold']} and mats {quote['mats']}: "
            f"{hud_before} -> {hud_after}, want {want}."
        )
    if len(posts) != 1:
        problems.append(f"確定 should send exactly one POST /upgrade, saw {posts}.")
    if problems:
        _upgrade_ux_fail(case_id, " | ".join(problems))


# ── TC-FE-TOWN-UX-SHEET-BUFF-*: placed sheet shows the level buff, not fake FN ──
#
# Already-placed scene 4 must not render FN / onFn stubs (整道具／修理／接任務／出發)
# that only toast and rewrite #sheetNote. Show this building's current-level buff
# from API buff_type + buff_vals[level-1] (same index as get_building_buff).
# Dedicated visible node: #sheetBuff. Product does not have that id yet, so these
# stay red. Do not weaken upgrade_cost, upgrade_confirm, UX-05, or store_ux.

SHEET_BUFF_NAME = "工坊"
SHEET_BUFF_LEVEL = 3
SHEET_BUFF_TYPE = "build_speed"
SHEET_BUFF_VALS = [2, 3, 4, 5, 6]
SHEET_BUFF_INDEX = SHEET_BUFF_LEVEL - 1
SHEET_BUFF_VALUE = SHEET_BUFF_VALS[SHEET_BUFF_INDEX]
SHEET_BUFF_STUB_LABELS = (
    "整道具",
    "修理",
    "接任務",
    "出發",
    "借書",
    "還書",
    "鍛鍊",
    "休息一下",
    "收成",
    "澆水",
    "買賣",
    "睇貨架",
    "睇醫生",
    "休息",
    "望海",
    "開燈",
    "練習",
    "比試",
    "觀星",
    "記錄",
    "睇一看",
)
SHEET_BUFF_STUB_PHRASES = (
    "整好一件道具",
    "修理好咗",
    "接咗一個任務",
    "準備出發",
    "借咗一本故事書",
    "書還好咗",
    "做完一輪鍛鍊",
    "休息好咗",
    "收成一籃菜",
    "澆完水",
    "買賣完成",
    "睇完貨架",
    "睇完醫生",
    "望咗一望海",
    "燈亮咗",
    "練習完一輪",
    "比試完一場",
    "觀完星",
    "寫低記錄",
)
SHEET_BUFF_RED = (
    "A placed building's #actionSheet must not render fake FN buttons "
    "(#sheetFns .fn, including 整道具／修理／接任務／出發) and must not toast "
    "FN_COPY lines such as 工坊：整好一件道具. "
    "Show the current-level buff in a visible #sheetBuff. "
    f"工坊 Lv.{SHEET_BUFF_LEVEL} {SHEET_BUFF_TYPE} uses buff_vals[{SHEET_BUFF_INDEX}] "
    f"from {SHEET_BUFF_VALS} → {SHEET_BUFF_VALUE}. "
    "Readable text or aria-label must include that number and either the buff_type "
    f"or a multiplier mark (×{SHEET_BUFF_VALUE} / x{SHEET_BUFF_VALUE}). "
    "The seed effect 「建築速度 x2」 is the static blurb, not the Lv.3 value. "
    "#sheetNote, the toast, and #sheetCost do not count as #sheetBuff. "
    "Leave #btnUpgrade, the upgrade cost chip, and #upgradeConfirm unchanged."
)


def _sheet_buff_fail(case_id, detail):
    pytest.fail(f"{case_id}: {detail} {SHEET_BUFF_RED}")


def _format_buff_number(value):
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return format(value, "g")


def _readable_level_buff(text, buff_type, value):
    """True when text shows buff_vals[level-1] plus buff_type or a × / x mark.

    Exact Chinese wording is not required. The static seed effect is not enough
    when its number is a different level (工坊 effect is x2; Lv.3 is 4).
    """
    raw = text or ""
    token = _format_buff_number(value)
    has_number = re.search(rf"(?<!\d){re.escape(token)}(?!\d)", raw) is not None
    has_type = bool(buff_type) and buff_type in raw
    has_mult = re.search(
        rf"(?:×|✕|x|X|\*|＊)\s*{re.escape(token)}(?!\d)",
        raw,
    ) is not None
    return has_number and (has_type or has_mult)


def _placed_level_buff(test_db_path, kid_id, name):
    """buff_vals[level-1] for the placed row. Same index as get_building_buff."""
    db = connect_db(test_db_path)
    row = db.execute(
        """
        SELECT b.level AS level, bd.name AS name, bd.buff_type AS buff_type,
               bd.buff_vals AS buff_vals, bd.effect AS effect
        FROM buildings b
        JOIN building_defs bd ON bd.id = b.def_id
        WHERE b.kid_id=? AND bd.name=? AND COALESCE(b.stored, 0)=0
        ORDER BY b.id DESC LIMIT 1
        """,
        (kid_id, name),
    ).fetchone()
    db.close()
    assert row, f"placed {name} missing from the synthetic kid"
    vals = json.loads(row["buff_vals"] or "[]")
    level = int(row["level"])
    assert vals, f"{name} buff_vals is empty"
    index = max(0, min(level - 1, len(vals) - 1))
    return {
        "name": row["name"],
        "level": level,
        "buff_type": row["buff_type"] or "",
        "vals": vals,
        "index": index,
        "value": vals[index],
        "effect": row["effect"] or "",
    }


def _seed_sheet_buff_workshop(test_db_path, kid_id):
    """Placed 工坊 Lv.3 only. build_speed buff_vals[2] is 4.

    Synthetic kid only. No production DB and no real PIN.
    """
    set_kid_points(test_db_path, kid_id, 8000)
    grant_inventory(
        test_db_path,
        kid_id,
        {"wood": 400, "brick": 300, "glass": 40, "gear": 120, "gem": 20},
    )
    db = connect_db(test_db_path)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    insert_building(
        test_db_path,
        kid_id,
        building_def_id(test_db_path, SHEET_BUFF_NAME),
        level=SHEET_BUFF_LEVEL,
        cell_x=4,
        cell_y=1,
    )
    buff = _placed_level_buff(test_db_path, kid_id, SHEET_BUFF_NAME)
    assert buff["level"] == SHEET_BUFF_LEVEL, buff
    assert buff["buff_type"] == SHEET_BUFF_TYPE, buff
    assert buff["vals"] == SHEET_BUFF_VALS, buff
    assert buff["index"] == SHEET_BUFF_INDEX, buff
    assert buff["value"] == SHEET_BUFF_VALUE, buff
    return buff


def _open_placed_building_sheet(page, case_id, name):
    """Tap a placed building on scene 1 so #actionSheet opens."""
    pad = page.locator("#townMap, #village").get_by_role(
        "button",
        name=re.compile(rf"第\s*\d+\s*欄第\s*\d+\s*行，{re.escape(name)}(?:，|$)"),
    )
    if pad.count() == 0 or not pad.first.is_visible():
        _sheet_buff_fail(
            case_id,
            f"Scene 1 has no tappable pad for placed {name}.",
        )
    pad.first.click()
    sheet = page.locator("#actionSheet")
    try:
        sheet.wait_for(state="visible", timeout=8000)
    except Exception:
        _sheet_buff_fail(
            case_id,
            f"Tapping placed {name} did not open #actionSheet.",
        )
    title = (page.locator("#sheetTitle").inner_text() or "").strip()
    if name not in title:
        _sheet_buff_fail(
            case_id,
            f"#sheetTitle should name {name} after the tap, saw {title!r}.",
        )


def _visible_fn_labels(page):
    loc = page.locator("#sheetFns .fn")
    labels = []
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if not btn.is_visible():
                continue
        except Exception:
            continue
        labels.append((btn.inner_text() or "").strip() or _button_label(btn))
    return labels


def _stub_buttons_outside_fn_class(page):
    """FN labels rendered as buttons even if they drop class .fn."""
    root = page.locator("#actionSheet")
    if root.count() == 0:
        return []
    buttons = root.locator("button")
    found = []
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        try:
            if not btn.is_visible():
                continue
        except Exception:
            continue
        classes = (btn.get_attribute("class") or "").split()
        if "fn" in classes:
            continue
        text = (btn.inner_text() or "").strip()
        if text in SHEET_BUFF_STUB_LABELS:
            found.append(text)
    return found


def _read_sheet_buff(page):
    loc = page.locator("#sheetBuff")
    if loc.count() == 0:
        return {"present": False, "visible": False, "text": "", "aria": ""}
    el = loc.first
    try:
        visible = el.is_visible()
    except Exception:
        visible = False
    try:
        data = el.evaluate(
            """(node) => ({
              text: (node.innerText || node.textContent || '').trim(),
              aria: (node.getAttribute('aria-label') || '').trim()
            })"""
        )
    except Exception:
        data = {"text": "", "aria": ""}
    return {
        "present": True,
        "visible": visible,
        "text": data.get("text") or "",
        "aria": data.get("aria") or "",
    }


def _toast_textcontent(page):
    """#toast text, including after the fade hides the node."""
    try:
        return page.evaluate(
            """() => {
              const el = document.getElementById('toast');
              return el ? (el.textContent || '') : '';
            }"""
        )
    except Exception:
        return _toast_text(page)


def _sheet_note_text(page):
    loc = page.locator("#sheetNote")
    if loc.count() == 0:
        return ""
    try:
        return loc.first.inner_text() or ""
    except Exception:
        return ""


def _stub_phrases_in(*chunks):
    blob = "\n".join(chunks)
    return [phrase for phrase in SHEET_BUFF_STUB_PHRASES if phrase in blob]


def _click_stub_fn(page):
    """Click 整道具 if it is there, otherwise the first visible .fn. Return its label."""
    loc = page.locator("#sheetFns .fn")
    target = None
    label = ""
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if not btn.is_visible():
                continue
        except Exception:
            continue
        text = (btn.inner_text() or "").strip()
        if text == "整道具":
            target = btn
            label = text
            break
        if target is None:
            target = btn
            label = text
    if target is None:
        return None
    target.click()
    page.wait_for_timeout(400)
    return label


@pytest.mark.case_id("TC-FE-TOWN-UX-SHEET-BUFF-01")
def test_town_ux_sheet_buff_shows_level_buff_without_fn(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-SHEET-BUFF-01 已起工坊：#sheetFns 冇 .fn，#sheetBuff 顯示 Lv.3 ×4。"""
    case_id = "TC-FE-TOWN-UX-SHEET-BUFF-01"
    buff = _seed_sheet_buff_workshop(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    _open_placed_building_sheet(page, case_id, SHEET_BUFF_NAME)
    problems = []
    level_text = (page.locator("#sheetLevel").inner_text() or "").strip()
    if not re.search(rf"Lv\.?\s*{buff['level']}(?!\d)", level_text):
        problems.append(
            f"#sheetLevel should show Lv.{buff['level']} for the placed workshop, "
            f"saw {level_text!r}."
        )
    fn_labels = _visible_fn_labels(page)
    if fn_labels:
        problems.append(
            f"#sheetFns has {len(fn_labels)} .fn button(s) {fn_labels}; want zero "
            "(no 整道具／修理／接任務／出發 stubs)."
        )
    extra = _stub_buttons_outside_fn_class(page)
    if extra:
        problems.append(f"stub action buttons without class fn: {extra}.")
    reading = _read_sheet_buff(page)
    blob = f"{reading['text']}\n{reading['aria']}"
    if not reading["present"]:
        problems.append(
            "#sheetBuff is missing. The open sheet must show a visible #sheetBuff for "
            f"{buff['name']} Lv.{buff['level']} {buff['buff_type']} "
            f"buff_vals[{buff['index']}]={buff['value']} from {buff['vals']}."
        )
    elif not reading["visible"]:
        problems.append(
            f"#sheetBuff is in the DOM but not visible. "
            f"text={reading['text']!r} aria={reading['aria']!r}."
        )
    elif not _readable_level_buff(blob, buff["buff_type"], buff["value"]):
        problems.append(
            "#sheetBuff must show the current-level buff: "
            f"number {buff['value']} and either {buff['buff_type']!r} or a multiplier "
            f"(×{buff['value']} / x{buff['value']}). "
            f"Seed effect {buff['effect']!r} is not that value. "
            f"text={reading['text']!r} aria={reading['aria']!r}."
        )
    if problems:
        _sheet_buff_fail(case_id, " | ".join(problems))


@pytest.mark.case_id("TC-FE-TOWN-UX-SHEET-BUFF-02")
def test_town_ux_sheet_buff_no_stub_toast(
    page, base_url, test_db_path, fe_ids
):
    """TC-FE-TOWN-UX-SHEET-BUFF-02 唔好有 .fn 假動作，亦唔好 toast 工坊：整好一件道具。"""
    case_id = "TC-FE-TOWN-UX-SHEET-BUFF-02"
    _seed_sheet_buff_workshop(test_db_path, fe_ids["kid_id"])
    _open_town_home(page, base_url)
    _open_placed_building_sheet(page, case_id, SHEET_BUFF_NAME)
    note_before = _sheet_note_text(page)
    toast_before = _toast_textcontent(page)
    problems = []
    early = _stub_phrases_in(note_before, toast_before)
    if early:
        problems.append(
            "opening the placed-building sheet already showed a fake FN result "
            f"{early}. note={note_before!r} toast={toast_before!r}."
        )
    fn_labels = _visible_fn_labels(page)
    if fn_labels:
        clicked = _click_stub_fn(page)
        note_after = _sheet_note_text(page)
        toast_after = _toast_textcontent(page)
        later = _stub_phrases_in(note_after, toast_after)
        problems.append(
            f"#sheetFns still has a fake FN click path: .fn buttons {fn_labels}."
        )
        if later:
            problems.append(
                f"clicking {clicked!r} produced stub copy {later}. "
                f"note={note_after!r} toast={toast_after!r}."
            )
    if problems:
        _sheet_buff_fail(case_id, " | ".join(problems))
