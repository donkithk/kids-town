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
  TC-FE-TOWN-CHROME-01  城鎮首頁 header（#hdrRes）同公會大廳同一個資源列同高度
  TC-FE-TOWN-CHROME-02  城鎮首頁 #ktFooter 五個 tab，底邊貼齊共享舞台（冇啡色空隙）
  TC-FE-TOWN-CHROME-03  城鎮首頁內容喺同一個 1280×720 art-stage 入面
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
import os
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
    insert_kid,
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


# Town-home chrome is compared at a fixed landscape viewport so the shared
# 1280×720 shell letterboxes (scale = min(1100/1280, 800/720) < 1). Matching
# guild/quest means the on-screen header, footer, and stage — not the unscaled
# .mp / #townCanvasWrapper column.
CHROME_VIEWPORT = {"width": 1100, "height": 800}
CHROME_TOL_PX = 6
STAGE_DESIGN_W = 1280
STAGE_DESIGN_H = 720
FOOTER_TAB_LABELS = ("城鎮首頁", "公會大廳", "任務板", "商店", "背包")
HEADER_MAT_SLOTS = ("wood", "brick", "glass", "gear")
# 公會大廳 is #tab-expedition. There is no #tab-guild.
GUILD_TAB_ID = "tab-expedition"
QUEST_TAB_ID = "tab-tasks"


def _chrome_snapshot(page):
    """On-screen chrome boxes plus the CSS the art-stage shell applies."""
    return page.evaluate(
        """() => {
          const box = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return {
              top: r.top, left: r.left, width: r.width, height: r.height,
              bottom: r.bottom, right: r.right,
              position: cs.position,
              cssWidth: cs.width,
              cssHeight: cs.height,
              cssBottom: cs.bottom,
              display: cs.display,
              // Layout size ignores the letterbox transform, so the shell
              // reads 1280×720 even when the viewport scales it.
              layoutWidth: el.offsetWidth,
              layoutHeight: el.offsetHeight,
            };
          };
          const active = document.querySelector('.tab-content.active');
          const footer = document.querySelector('#ktFooter');
          const stage = document.querySelector('.gsw');
          const footerBox = box(footer);
          const stageBox = box(stage);
          return {
            vw: window.innerWidth,
            vh: window.innerHeight,
            artstage: document.body.classList.contains('kt-artstage'),
            activeTab: active ? active.id : '',
            header: box(document.querySelector('.gh')),
            hdrRes: box(document.querySelector('#hdrRes')),
            mats: Array.from(document.querySelectorAll('#hdrRes .mat')).map(
              (el) => el.getAttribute('data-mat')
            ),
            goldVisible: !!(document.querySelector('#hdrRes #hudCo')),
            footer: footerBox,
            footerLabels: Array.from(
              document.querySelectorAll('#ktFooter .kt-footer-label')
            ).map((el) => (el.textContent || '').trim()),
            stage: stageBox,
            activePanel: box(active),
            townInsideStage: !!(stage && stage.contains(document.querySelector('#tab-town'))),
            viewportGap: footerBox ? window.innerHeight - footerBox.bottom : null,
            stageGap: (footerBox && stageBox) ? stageBox.bottom - footerBox.bottom : null,
          };
        }"""
    )


def _open_town_home(page, base_url):
    """Kid login lands on 城鎮首頁. Fonts aborted so footer flow is deterministic."""
    page.set_viewport_size(CHROME_VIEWPORT)
    page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    _login(page, base_url)
    page.locator("#tab-town.active").wait_for(state="visible", timeout=8000)
    page.locator("#hdrRes").wait_for(state="visible", timeout=8000)
    page.locator("#ktFooter").wait_for(state="visible", timeout=8000)


def _click_footer_tab(page, label, tab_id):
    page.locator("#ktFooter").get_by_role("button", name=label).click()
    page.locator(f"#{tab_id}.active").wait_for(state="visible", timeout=8000)


def _assert_header_slots(page):
    hdr = page.locator("#hdrRes")
    assert hdr.is_visible(), "#hdrRes resource bar must be visible"
    gold = hdr.locator("#hudCo")
    assert gold.is_visible(), "shared header must show the gold chip (#hudCo)"
    assert "💰" in (hdr.inner_text() or ""), "shared header gold chip must show 💰"
    for mat in HEADER_MAT_SLOTS:
        slot = hdr.locator(f'.mat[data-mat="{mat}"]')
        assert slot.count() == 1, f"missing material slot {mat}"
        assert slot.is_visible(), f"material slot {mat} must be visible"


def _assert_reference_artstage(metrics, tab_name):
    """Guild/quest already use the shell. If this fails, the comparison target moved."""
    assert metrics["artstage"], f"{tab_name} should turn on body.kt-artstage"
    assert metrics["activeTab"], metrics
    panel = metrics["activePanel"]
    assert panel is not None, metrics
    assert panel["layoutWidth"] == STAGE_DESIGN_W, (
        f"{tab_name} panel layout width should be the 1280 design size; got {panel}"
    )
    assert panel["layoutHeight"] == STAGE_DESIGN_H, (
        f"{tab_name} panel layout height should be the 720 design size; got {panel}"
    )
    assert panel["position"] == "absolute", (
        f"{tab_name} panel should be position:absolute inside the stage; got {panel}"
    )
    scale = min(metrics["vw"] / STAGE_DESIGN_W, metrics["vh"] / STAGE_DESIGN_H)
    stage = metrics["stage"]
    assert abs(stage["width"] - STAGE_DESIGN_W * scale) <= CHROME_TOL_PX, stage
    assert abs(stage["height"] - STAGE_DESIGN_H * scale) <= CHROME_TOL_PX, stage
    assert abs(metrics["header"]["top"] - stage["top"]) <= CHROME_TOL_PX, metrics
    assert abs(metrics["footer"]["bottom"] - stage["bottom"]) <= CHROME_TOL_PX, metrics
    assert metrics["footer"]["position"] == "absolute", metrics["footer"]
    assert metrics["footer"]["cssBottom"] == "0px", metrics["footer"]


def _delta_msg(label, actual, expected):
    delta = abs(actual - expected)
    return (
        f"{label}: 城鎮首頁 {actual:.1f}px vs 公會大廳 {expected:.1f}px "
        f"(delta {delta:.1f}px, tolerance {CHROME_TOL_PX}px)"
    )


def _assert_close(label, actual, expected):
    assert abs(actual - expected) <= CHROME_TOL_PX, (
        _delta_msg(label, actual, expected)
        + ". 城鎮首頁 must share the 1280×720 art-stage chrome "
        "(body.kt-artstage .gsw letterbox). RED until builder #22; "
        "do not widen this tolerance to fit the old .mp / #townCanvasWrapper map."
    )


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


# ── TC-FE-TOWN-CHROME: 城鎮首頁 shares guild/quest art-stage chrome ──
# RED on current main. Verified: ktSyncArtStage() does not add body.kt-artstage
# for #tab-town, and the absolute 1280×720 rules omit #tab-town. Town home is
# still .mp / #townCanvasWrapper (green map) in normal flow. Builder #22 should
# put 城鎮首頁 on the same shell as 公會大廳 / 任務板. Do not weaken these asserts.


@pytest.mark.case_id("TC-FE-TOWN-CHROME-01")
def test_town_home_header_matches_guild_chrome(page, base_url):
    """TC-FE-TOWN-CHROME-01 城鎮首頁同公會大廳共用 #hdrRes 資源列，高度／位置一致。

    Slots: gold (#hudCo / 💰) + wood / brick / glass / gear. On-screen .gh box
    must match 公會大廳 within CHROME_TOL_PX (letterboxed 1280×720 stage).
    """
    _open_town_home(page, base_url)
    _assert_header_slots(page)
    town = _chrome_snapshot(page)
    assert town["activeTab"] == "tab-town"
    assert town["mats"] == list(HEADER_MAT_SLOTS), town["mats"]
    assert town["goldVisible"]

    _click_footer_tab(page, "公會大廳", GUILD_TAB_ID)
    page.locator("body.kt-artstage").wait_for(state="attached", timeout=8000)
    _assert_header_slots(page)
    guild = _chrome_snapshot(page)
    assert guild["mats"] == town["mats"], (town["mats"], guild["mats"])
    _assert_reference_artstage(guild, "公會大廳")

    _assert_close("header top", town["header"]["top"], guild["header"]["top"])
    _assert_close("header height", town["header"]["height"], guild["header"]["height"])
    _assert_close("header width", town["header"]["width"], guild["header"]["width"])
    _assert_close(
        "resource bar height", town["hdrRes"]["height"], guild["hdrRes"]["height"]
    )


@pytest.mark.case_id("TC-FE-TOWN-CHROME-02")
def test_town_home_footer_aligns_with_guild_stage(page, base_url):
    """TC-FE-TOWN-CHROME-02 #ktFooter 五個 tab，城鎮首頁底邊貼齊共享舞台。

    Order: 城鎮首頁｜公會大廳｜任務板｜商店｜背包. On 公會大廳 the footer is
    absolute bottom:0 of the 1280×720 stage (no gap under the footer inside
    the frame). 城鎮首頁 must land on the same bottom edge.
    """
    _open_town_home(page, base_url)
    footer = page.locator("#ktFooter")
    assert footer.is_visible()
    labels = [
        text.strip()
        for text in footer.locator(".kt-footer-label").all_inner_texts()
    ]
    assert labels == list(FOOTER_TAB_LABELS), labels
    assert (
        footer.get_by_role("button", name="城鎮首頁").get_attribute("aria-current")
        == "page"
    )
    town = _chrome_snapshot(page)

    _click_footer_tab(page, "公會大廳", GUILD_TAB_ID)
    page.locator("body.kt-artstage").wait_for(state="attached", timeout=8000)
    guild = _chrome_snapshot(page)
    assert guild["footerLabels"] == list(FOOTER_TAB_LABELS), guild["footerLabels"]
    _assert_reference_artstage(guild, "公會大廳")

    _assert_close(
        "footer bottom (flush with shared stage)",
        town["footer"]["bottom"],
        guild["footer"]["bottom"],
    )
    _assert_close(
        "gap below footer",
        town["viewportGap"],
        guild["viewportGap"],
    )
    assert town["footer"]["position"] == guild["footer"]["position"], (
        "城鎮首頁 footer position must match 公會大廳 "
        f"(town {town['footer']['position']} / css bottom {town['footer']['cssBottom']}, "
        f"guild {guild['footer']['position']} / {guild['footer']['cssBottom']}). "
        "A sticky footer inside the old map column leaves a brown gap under the bar. "
        "RED until builder #22."
    )
    assert town["footer"]["cssBottom"] == guild["footer"]["cssBottom"], (
        town["footer"],
        guild["footer"],
    )


@pytest.mark.case_id("TC-FE-TOWN-CHROME-03")
def test_town_home_uses_shared_1280x720_stage(page, base_url):
    """TC-FE-TOWN-CHROME-03 城鎮首頁內容包喺同公會／任務一樣嘅 1280×720 stage。

    Reference shell (already on main): body.kt-artstage, .gsw letterboxed to
    1280×720, active panel position:absolute with CSS width/height 1280×720.
    #tab-town must sit inside that shell the same way. The old green
    #townCanvasWrapper / .mp map is not itself the stage.
    """
    _open_town_home(page, base_url)
    assert page.locator("#tab-town #townCanvasWrapper").is_visible()
    town_before = _chrome_snapshot(page)
    assert town_before["townInsideStage"], "#tab-town must live inside .gsw"

    _click_footer_tab(page, "公會大廳", GUILD_TAB_ID)
    page.locator("body.kt-artstage").wait_for(state="attached", timeout=8000)
    guild = _chrome_snapshot(page)
    _assert_reference_artstage(guild, "公會大廳")

    _click_footer_tab(page, "任務板", QUEST_TAB_ID)
    quest = _chrome_snapshot(page)
    _assert_reference_artstage(quest, "任務板")
    _assert_close("quest stage width", quest["stage"]["width"], guild["stage"]["width"])
    _assert_close("quest stage height", quest["stage"]["height"], guild["stage"]["height"])
    assert quest["activePanel"]["layoutWidth"] == guild["activePanel"]["layoutWidth"]
    assert quest["activePanel"]["layoutHeight"] == guild["activePanel"]["layoutHeight"]
    assert quest["activePanel"]["position"] == guild["activePanel"]["position"]

    _click_footer_tab(page, "城鎮首頁", "tab-town")
    page.locator("#tab-town.active").wait_for(state="visible", timeout=8000)
    town = _chrome_snapshot(page)
    assert town["activeTab"] == "tab-town"
    assert town["townInsideStage"]

    assert town["artstage"], (
        "城鎮首頁 must turn on body.kt-artstage, same as 公會大廳／任務板. "
        f"active={town['activeTab']} artstage={town['artstage']}. "
        "RED until builder #22 includes #tab-town in the shared shell."
    )
    panel = town["activePanel"]
    assert panel["layoutWidth"] == STAGE_DESIGN_W, panel
    assert panel["layoutHeight"] == STAGE_DESIGN_H, panel
    assert panel["position"] == guild["activePanel"]["position"], panel
    assert panel["layoutWidth"] == guild["activePanel"]["layoutWidth"], panel
    assert panel["layoutHeight"] == guild["activePanel"]["layoutHeight"], panel
    _assert_close("stage width", town["stage"]["width"], guild["stage"]["width"])
    _assert_close("stage height", town["stage"]["height"], guild["stage"]["height"])
    _assert_close("town panel width", panel["width"], guild["activePanel"]["width"])
    _assert_close("town panel height", panel["height"], guild["activePanel"]["height"])


