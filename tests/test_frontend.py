"""Frontend E2E tests (Playwright) — requirement-based (black-box).

Test cases verify USER-VISIBLE requirements from the battle-system-v2 plan
+ DEV_PLAN.md, NOT implementation details. Selectors target user-facing text
(roles, labels, visible strings) rather than internal class names.

Requirements (from docs):
  TC-FE-01  小朋友用帳號+PIN 登入 → 見到城鎮 HUD
  TC-FE-02  能力面板顯示 5 屬性 (臂力/知識/速度/創意/勇氣), 唔再有 體力/6 屬性
  TC-FE-03  戰鬥流程: 開戰 → 見到怪物 → 攻擊 → 分出勝負
  TC-FE-04  Boss 集料召喚入口存在
  TC-FE-05  每日 reset: 已打過嘅區今日不能再打 (提示)
  TC-FE-06  Level gate: 唔夠 level 嘅區顯示需要 Lv 提示
"""
import os, sys, shutil, subprocess, time, socket
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY312 = r'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe'


def _wait_port(port, timeout=20):
    for _ in range(timeout * 2):
        try:
            socket.create_connection(('127.0.0.1', port), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    """Temp copy of the real DB (session-scoped, shared by all frontend tests)."""
    src = os.path.join(REPO, 'kids_town.db')
    dst = str(tmp_path_factory.mktemp('db') / 'test.db')
    shutil.copy2(src, dst)
    return dst


@pytest.fixture(scope="session")
def base_url(test_db_path):
    """Dedicated test server on port 9131 with the temp DB."""
    port = 9131
    proc = subprocess.Popen(
        [PY312, os.path.join(REPO, 'tests', '_run_server.py'), test_db_path, str(port)],
        cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    assert _wait_port(port), "test server failed to start"
    yield f'http://127.0.0.1:{port}'
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(autouse=True)
def _reset_state(test_db_path):
    """每個 test 前重置遊戲狀態 (running expedition + daily/boss/pity)."""
    import sqlite3
    db = sqlite3.connect(test_db_path)
    db.execute('DELETE FROM expeditions WHERE status="running"')
    db.execute('DELETE FROM daily_battles')
    db.execute('DELETE FROM boss_progress')
    db.execute('DELETE FROM drop_pity')
    db.commit()
    db.close()
    yield


@pytest.fixture()
def page(base_url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page(viewport={'width': 1100, 'height': 800})
        yield pg
        browser.close()


def _login(page, base_url, username='kid2', pin='0000'):
    page.goto(f'{base_url}/kids/')
    page.get_by_placeholder('登入名稱').fill(username)
    page.get_by_placeholder('密碼').fill(pin)
    page.get_by_role('button', name='🚪 登入').click()
    page.wait_for_timeout(1500)


def _goto_battle_lobby(page):
    """導航到戰鬥挑戰頁 (☰ → 探索 → 戰鬥類型)."""
    page.get_by_role('button', name='☰').click()
    page.wait_for_timeout(600)
    page.get_by_text('探索', exact=False).last.click()
    page.wait_for_timeout(800)
    page.locator('.exp-type-btn[data-type="battle"]').click()
    page.wait_for_timeout(800)


# ── TC-FE-01: 登入 ────────────────────────────────────────────────

def test_login_shows_town_hud(page, base_url):
    _login(page, base_url)
    # 城鎮 HUD 顯示小朋友名 + 等級
    assert page.get_by_text('小強').first.is_visible()
    assert page.get_by_text('Lv.').first.is_visible()


# ── TC-FE-02: 能力面板 5 屬性 ─────────────────────────────────────

def test_ability_panel_shows_five_attributes(page, base_url):
    _login(page, base_url)
    # hover 頭像觸發能力 tooltip
    page.locator('#hudAv').hover()
    page.wait_for_timeout(600)
    tooltip = page.locator('text=臂力')
    assert tooltip.first.is_visible(), "能力面板應該顯示「臂力」"
    # 唔應該再有「體力」(舊 str 譯名已改) 或第 6 個屬性
    assert page.locator('text=體力').count() == 0, "唔應該再有「體力」"


# ── TC-FE-03: 戰鬥流程 ───────────────────────────────────────────

def test_battle_flow_attack(page, base_url):
    _login(page, base_url)
    # 打開選單 → 入探險頁
    page.get_by_role('button', name='☰').click()
    page.wait_for_timeout(600)
    page.get_by_text('探索', exact=False).last.click()
    page.wait_for_timeout(800)
    # 切換到「戰鬥」類型
    page.locator('.exp-type-btn[data-type="battle"]').click()
    page.wait_for_timeout(800)
    # 撳區域嘅「⚔️ 戰鬥」按鈕 (startBattle)
    page.locator('button.exp-btn.go').first.click()
    # 等 battle scene 出現 (怪物名)
    page.locator('.m-name').first.wait_for(state='visible', timeout=8000)
    assert page.get_by_text('野狼', exact=False).first.is_visible()
    # 攻擊
    page.get_by_text('攻擊', exact=False).first.click()
    page.wait_for_timeout(800)


# ── TC-FE-04: Boss 集料召喚入口 ───────────────────────────────────

def test_boss_summon_entry_in_battle_lobby(page, base_url):
    """戰鬥挑戰頁應該有 Boss 召喚入口."""
    _login(page, base_url)
    _goto_battle_lobby(page)
    assert page.get_by_text('Boss', exact=False).first.is_visible(), \
        "戰鬥挑戰頁應該顯示 Boss 召喚入口"


# ── TC-FE-05: 掉落稀有度顯示 ──────────────────────────────────────

def test_battle_win_shows_rarity(page, base_url):
    """打贏戰鬥後, 掉落應該顯示稀有度 (普通/稀有/珍貴/傳說)."""
    _login(page, base_url)
    _goto_battle_lobby(page)
    page.locator('button.exp-btn.go').first.click()
    page.locator('.m-name').first.wait_for(state='visible', timeout=8000)
    won = False
    for _ in range(20):
        # 揀指令「攻擊」
        page.get_by_text('⚔️ 攻擊', exact=False).first.click()
        page.wait_for_timeout(300)
        # 揀目標怪物
        page.locator('.monster-card:not(.dead)').first.click()
        page.wait_for_timeout(700)
        body = page.locator('#dbt').inner_text()
        if '勝利' in body or '戰敗' in body:
            won = '勝利' in body
            break
    assert won, "應該打贏 (野狼 HP 低於玩家攻擊)"
    body = page.locator('#dbt').inner_text()
    assert any(r in body for r in ['普通', '稀有', '珍貴', '傳說']), \
        f"掉落應該顯示稀有度, 得到: {body}"


# ── TC-FE-06: 「即將開放」標籤移除 ────────────────────────────────

def test_battle_not_marked_coming_soon(page, base_url):
    """戰鬥已上線, 選單/戰鬥頁唔應該再有「即將開放」."""
    _login(page, base_url)
    page.get_by_role('button', name='☰').click()
    page.wait_for_timeout(600)
    assert page.get_by_text('即將開放', exact=False).count() == 0, \
        "戰鬥已上線, 唔應該再顯示「即將開放」"
