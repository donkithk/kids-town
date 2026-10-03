"""Playwright red tests for the battle skill menu (mock 63b81c8).

Viewport is 1280×720 only. Portrait is out of scope.
Empty temp DB and synthetic kids. Never opens the tracked kids_town.db.

Selector contract: docs/test-cases/SKILL_MENU_AND_TEXT.md
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.factories import (  # noqa: E402
    TEST_KID_PIN,
    connect_db,
    init_empty_db,
    insert_building,
    insert_kid,
)
from tests.skill_menu_spec import (  # noqa: E402
    BTN_BACK_MIN_HEIGHT_PX,
    BTN_BACK_MIN_WIDTH_PX,
    PAGE_LABEL_MIN_PX,
    SEL_BTN_BACK,
    SEL_BTN_CLOSE,
    SEL_BTN_NEXT,
    SEL_BTN_PREV,
    SEL_BTN_SKILL,
    SEL_BATTLE_BAR,
    SEL_COMMAND_BAR,
    SEL_M_HP_BAR,
    SEL_M_HP_TEXT,
    SEL_M_NAME,
    SEL_MONSTER_CARD,
    SEL_MP_NOW,
    SEL_PAGE_DOTS,
    SEL_PAGE_LABEL,
    SEL_PLAYER_VITALS,
    SEL_SKILL_CARD,
    SEL_SKILL_DESC,
    SEL_SKILL_ICON,
    SEL_SKILL_NAME,
    SEL_SKILL_PANEL,
    SEL_SKILL_TITLE,
    SEL_WILD_TOAST,
    SEEDED_SKILL_NAMES,
    NOSQUEEZE_GLYPH_MIN_RATIO,
    NOSQUEEZE_MATRIX_EPS,
    NOSQUEEZE_WIDTH_RATIO_MAX,
    NOSQUEEZE_WIDTH_RATIO_MIN,
    SKILL_CARD_MIN_HEIGHT_PX,
    SKILL_CARD_PAD_BLOCK_MIN_PX,
    SKILL_CARD_PAD_INLINE_MIN_PX,
    SKILL_CARD_WIDTH_MAX_PX,
    SKILL_DESC_LINE_RATIO,
    SKILL_DESC_MIN_PX,
    SKILL_FRAME_CLEARANCE_MIN_PX,
    SKILL_GLYPH_EDGE_TOLERANCE_PX,
    SKILL_ICON_BOX_MIN_PX,
    SKILL_ICON_BOX_WIDTH_MIN_PX,
    SKILL_ICON_FONT_MIN_PX,
    SKILL_ICON_INSET_MIN_PX,
    SKILL_ICON_NAME_GAP_MIN_PX,
    SKILL_PANEL_PAD_INLINE_MIN_PX,
    SKILL_MENU_PAGE_SIZE,
    SKILL_NAME_MIN_PX,
    SKILL_PANEL_RECT,
    SKILL_PANEL_RECT_TOLERANCE_PX,
    SKILL_TITLE_MIN_PX,
    TITLE_CONTROL_MIN_PX,
    TOAST_LINE_TOLERANCE_PX,
    TOAST_LONG_MESSAGE,
    TOAST_SHIFT_TOLERANCE_PX,
    TOAST_SHORT_MESSAGE,
    TOAST_WRAP_WIDTH_PX,
    colloquial_hits,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENU_KID6 = "test_menu_kid6"
MENU_KID8 = "test_menu_kid8"
MENU_KID13 = "test_menu_kid13"
MENU_KID22 = "test_menu_kid22"
STAGE_W = 1280
STAGE_H = 720
# `buildingImage is not defined` aborts index.html before service-worker
# registration. This file does not call navigator.serviceWorker.register and
# does not treat that pageerror as allowed. TC-FE-SW-AUTOREG is the assertion.

# Buildings that teach exactly these skills at the given levels.
# Guild Lv1 teaches nothing (偵察 needs Lv2) but battle-start requires it.
_SIX = (
    ("探險公會", 1),
    ("健身室", 4),  # 蓄力 重擊 連擊 鍛鍊的成果
    ("農場", 1),  # 營養餐
    ("商店", 1),  # 金幣袋
)
_EIGHT = _SIX + (("圖書館", 2),)  # 火球 知識的力量
# 8 + 醫院三招 + 強光 + 流星雨 = 13 learned skills, which is 3 menu pages.
_THIRTEEN = _EIGHT + (
    ("醫院", 5),  # 繃帶 急救 全體治療
    ("燈塔", 1),  # 強光
    ("天文台", 1),  # 流星雨
)
# Every seeded skill. Levels are the skill_defs.level_required ceilings.
_ALL22 = (
    ("探險公會", 4),  # 偵察 疾風斬
    ("健身室", 4),  # 蓄力 重擊 連擊 鍛鍊的成果
    ("醫院", 5),  # 繃帶 急救 全體治療
    ("競技場", 5),  # 橫掃 盾擊 必殺
    ("圖書館", 4),  # 火球 冰凍 知識的力量
    ("工坊", 4),  # 修復 強化
    ("農場", 1),  # 營養餐
    ("商店", 1),  # 金幣袋
    ("燈塔", 1),  # 強光
    ("天文台", 1),  # 流星雨
    ("銀行", 1),  # 金錢砸
)


def _playwright_unavailable_reason():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright package not installed"
    try:
        with sync_playwright() as p:
            exe = p.chromium.executable_path
        if not exe or not os.path.isfile(exe):
            return "Playwright Chromium is not installed"
    except Exception as exc:
        return f"Playwright Chromium is not available ({exc})"
    return None


_PW_SKIP = _playwright_unavailable_reason()

pytestmark = [
    pytest.mark.frontend,
    pytest.mark.skipif(_PW_SKIP is not None, reason=_PW_SKIP or "Playwright Chromium not available"),
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


def _learned_names(db_path, kid_id):
    db = connect_db(db_path)
    rows = db.execute(
        """
        SELECT s.name, s.mp_cost, s.description, s.target
          FROM buildings b
          JOIN building_defs d ON d.id = b.def_id
          JOIN skill_defs s
            ON s.bldg_def_id = d.id AND s.level_required <= b.level
         WHERE b.kid_id = ? AND COALESCE(b.stored, 0) = 0
         ORDER BY s.id
        """,
        (kid_id,),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def _seed(dst):
    import backend_v2 as backend

    old = backend.DB_PATH
    backend.app.config["TESTING"] = True
    init_empty_db(backend, dst)
    ids = {}
    for username, name, plan in (
        (MENU_KID6, "Menu Kid 6", _SIX),
        (MENU_KID8, "Menu Kid 8", _EIGHT),
        (MENU_KID13, "Menu Kid 13", _THIRTEEN),
        (MENU_KID22, "Menu Kid 22", _ALL22),
    ):
        kid = insert_kid(dst, name=name, username=username, pin=TEST_KID_PIN, level=20, points=80)
        for index, (building, level) in enumerate(plan):
            def_id = backend_building_id(dst, building)
            insert_building(
                dst,
                kid["id"],
                def_id,
                level=level,
                cell_x=(index * 2) % 8,
                cell_y=(index * 2) // 8,
            )
        ids[username] = kid["id"]
    guild = backend_building_id(dst, "探險公會")
    assert guild == 6, guild
    learned6 = _learned_names(dst, ids[MENU_KID6])
    learned8 = _learned_names(dst, ids[MENU_KID8])
    learned13 = _learned_names(dst, ids[MENU_KID13])
    learned22 = _learned_names(dst, ids[MENU_KID22])
    assert len(learned6) == 6, [row["name"] for row in learned6]
    assert len(learned8) == 8, [row["name"] for row in learned8]
    assert len(learned13) == 13, [row["name"] for row in learned13]
    assert len(learned22) == len(SEEDED_SKILL_NAMES), [row["name"] for row in learned22]
    assert {row["name"] for row in learned22} == set(SEEDED_SKILL_NAMES)
    backend.DB_PATH = old
    return ids


def backend_building_id(db_path, name):
    db = connect_db(db_path)
    row = db.execute("SELECT id FROM building_defs WHERE name=?", (name,)).fetchone()
    db.close()
    assert row, name
    return row["id"]


@pytest.fixture(scope="session")
def menu_db(tmp_path_factory):
    dst = str(tmp_path_factory.mktemp("menu-db") / "menu.db")
    ids = _seed(dst)
    with open(dst + ".ids.json", "w", encoding="utf-8") as handle:
        json.dump(ids, handle)
    return dst


@pytest.fixture(scope="session")
def menu_ids(menu_db):
    with open(menu_db + ".ids.json", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def base_url(menu_db):
    port = _free_port()
    log_path = menu_db + ".server.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(REPO, "tests", "_run_server.py"), menu_db, str(port)],
        cwd=REPO,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**os.environ, "KIDS_TOWN_SECRET_KEY": "skill-menu-e2e-secret"},
    )
    if not _wait_port(port, timeout=30):
        logf.flush()
        detail = open(log_path, encoding="utf-8").read()
        proc.kill()
        raise AssertionError(f"skill-menu server failed on {port}:\n{detail}")
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    logf.close()


@pytest.fixture(autouse=True)
def _reset_fights(menu_db):
    db = connect_db(menu_db)
    db.execute("DELETE FROM expeditions WHERE status='running'")
    db.execute("DELETE FROM daily_battles")
    db.commit()
    db.close()
    yield


@pytest.fixture()
def page(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": STAGE_W, "height": STAGE_H})
        pg = context.new_page()
        pg.route("https://image.pollinations.ai/**", lambda route: route.abort())
        errors = []

        def _remember(text):
            if text and text not in errors:
                errors.append(text)

        pg.on("pageerror", lambda exc: _remember(str(exc)))
        pg.on("console", lambda msg: _remember(msg.text) if msg.type == "error" else None)
        pg.menu_errors = errors
        yield pg
        if errors:
            with open("/tmp/skillmenu-pageerrors.txt", "a", encoding="utf-8") as handle:
                handle.write("\n".join(errors) + "\n")
        context.close()
        browser.close()


def _login(page, base_url, username):
    page.set_viewport_size({"width": STAGE_W, "height": STAGE_H})
    page.goto(f"{base_url}/kids/")
    page.locator("#loginUsername").fill(username)
    page.locator("#loginPassword").fill(TEST_KID_PIN)
    page.get_by_role("button", name="🚪 登入").click()
    page.locator("#app").wait_for(state="visible", timeout=8000)


def _start_and_show_battle(page, kid_id, mp=None, db_path=None):
    """Start region 1 from the logged-in page, optionally patch MP, then open the fight."""
    started = page.evaluate(
        """async (kidId) => {
          const r = await fetch(`/api/kids/${kidId}/expedition/battle-start`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'same-origin',
            body: JSON.stringify({region_id: 1})
          });
          const data = await r.json();
          return {status: r.status, error: data.error || '', mp: data.player_mp, maxMp: data.player_max_mp,
                  skills: (data.skills || []).map(s => ({
                    id: s.id, name: s.name, mp: s.mp_cost, desc: s.description || '', target: s.target
                  }))};
        }""",
        kid_id,
    )
    assert started["status"] == 201, started
    if mp is not None:
        _patch_mp(db_path, kid_id, mp)
    page.evaluate("async () => { await loadTown(); st('expedition'); }")
    page.locator(".battle-scene .m-name").first.wait_for(state="visible", timeout=8000)
    return started


def _patch_mp(db_path, kid_id, mp):
    db = connect_db(db_path)
    row = db.execute(
        "SELECT id, expedition_data FROM expeditions WHERE kid_id=? AND status='running' "
        "ORDER BY id DESC LIMIT 1",
        (kid_id,),
    ).fetchone()
    assert row and row["expedition_data"], "no running battle to patch"
    data = json.loads(row["expedition_data"])
    data["player_mp"] = mp
    db.execute(
        "UPDATE expeditions SET expedition_data=? WHERE id=?",
        (json.dumps(data, ensure_ascii=False), row["id"]),
    )
    db.commit()
    db.close()


def _battle_state(page, kid_id):
    state = page.evaluate(
        """async (kidId) => {
          const r = await fetch(`/api/kids/${kidId}/town`, {credentials: 'same-origin'});
          const raw = await r.text();
          let town = null;
          try { town = JSON.parse(raw); } catch (e) { town = null; }
          if (!r.ok || !town) {
            return {error: raw.slice(0, 180), status: r.status};
          }
          const exp = town.expedition;
          if (!exp) return {error: 'no expedition', status: r.status};
          const bd = typeof exp.expedition_data === 'string'
            ? JSON.parse(exp.expedition_data) : (exp.expedition_data || {});
          return {
            mp: bd.player_mp, maxMp: bd.player_max_mp,
            turns: (bd.turns || []).length, status: bd.status || ''
          };
        }""",
        kid_id,
    )
    assert "error" not in state, state
    return state


def _plain(text):
    compact = re.sub(r"\s+", "", text or "")
    compact = re.sub(r"^[^\u4e00-\u9fff]+", "", compact)
    compact = re.sub(r"[^\u4e00-\u9fff]+$", "", compact)
    return compact


def _bar_buttons(page):
    payload = page.evaluate(
        """() => {
          const scene = document.querySelector('.battle-scene');
          if (!scene) return [];
          const seen = new Set();
          const out = [];
          for (const bar of scene.querySelectorAll('.kt-command-bar, .command-bar')) {
            for (const btn of bar.querySelectorAll('button')) {
              if (btn.closest('#skillPanel')) continue;
              if (seen.has(btn)) continue;
              seen.add(btn);
              out.push({
                id: btn.id || '',
                text: (btn.innerText || '').trim(),
                label: btn.getAttribute('aria-label') || ''
              });
            }
          }
          return out;
        }"""
    )
    return payload


def _bar_labels(page):
    labels = []
    for button in _bar_buttons(page):
        labels.append(_plain(button["text"]) or _plain(button["label"]))
    return labels


def _ui_skill_names(page):
    texts = page.evaluate(
        """() => {
          const out = [];
          const scene = document.querySelector('.battle-scene');
          if (!scene) return out;
          scene.querySelectorAll('button').forEach((btn) => {
            if (btn.closest('#ktFooter')) return;
            out.push((btn.innerText || '').trim());
            const label = btn.getAttribute('aria-label') || '';
            if (label) out.push(label);
          });
          document.querySelectorAll('#skillPanel .skill-name, #skillGrid .skill-name').forEach((el) => {
            out.push((el.textContent || '').trim());
          });
          return out;
        }"""
    )
    return texts


def _names_reachable(page, learned):
    blob = "\n".join(_ui_skill_names(page))
    return [row["name"] for row in learned if row["name"] in blob]


_LAYOUT_JS = """
() => {
  const stage = document.querySelector('body.kt-artstage .gsw.stage');
  const panel = document.getElementById('skillPanel');
  const footer = document.getElementById('ktFooter');
  const bar = document.querySelector('.battle-scene .command-bar')
    || document.querySelector('.battle-scene .kt-command-bar');
  const vitals = document.getElementById('playerVitals');
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      hidden: el.hasAttribute('hidden') || cs.display === 'none' || cs.visibility === 'hidden',
      w: r.width, h: r.height, left: r.left, top: r.top, right: r.right, bottom: r.bottom,
      offsetW: el.offsetWidth, offsetH: el.offsetHeight
    };
  };
  function clipped(el) {
    if (!el) return true;
    let node = el.parentElement;
    const r = el.getBoundingClientRect();
    while (node && node !== document.body) {
      const cs = getComputedStyle(node);
      const mode = cs.overflow + cs.overflowX + cs.overflowY;
      if (/auto|hidden|scroll|clip/.test(mode)) {
        const p = node.getBoundingClientRect();
        if (r.top < p.top - 1 || r.left < p.left - 1 || r.bottom > p.bottom + 1 || r.right > p.right + 1) {
          return true;
        }
      }
      node = node.parentElement;
    }
    return false;
  }
  return {
    stage: box(stage),
    panel: box(panel),
    footer: box(footer),
    bar: box(bar),
    vitals: box(vitals),
    hp: box(document.getElementById('hpNums')),
    mp: box(document.getElementById('mpNums')),
    vitalsClipped: clipped(vitals),
    hpClipped: clipped(document.getElementById('hpNums')),
    mpClipped: clipped(document.getElementById('mpNums')),
    panelClipped: clipped(panel)
  };
}
"""


def _inside(inner, outer, eps=1):
    if not inner or not outer:
        return False
    return (
        inner["w"] > 2
        and inner["h"] > 2
        and inner["left"] >= outer["left"] - eps
        and inner["top"] >= outer["top"] - eps
        and inner["right"] <= outer["right"] + eps
        and inner["bottom"] <= outer["bottom"] + eps
    )


def _overlaps(a, b):
    if not a or not b or a.get("hidden") or b.get("hidden"):
        return False
    return not (
        a["right"] <= b["left"] or a["left"] >= b["right"] or a["bottom"] <= b["top"] or a["top"] >= b["bottom"]
    )


def _menu_snapshot(page):
    return page.evaluate(
        """() => {
          const panel = document.getElementById('skillPanel');
          const grid = document.getElementById('skillGrid');
          const cards = grid ? [...grid.querySelectorAll('.skill-card')].map((card) => ({
            name: (card.querySelector('.skill-name') || {}).textContent || '',
            pill: (card.querySelector('.mp-pill') || {}).textContent || '',
            desc: (card.querySelector('.skill-desc') || {}).textContent || '',
            broke: (card.querySelector('.broke') || {}).textContent || '',
            disabled: card.disabled || card.getAttribute('aria-disabled') === 'true'
          })) : [];
          const label = document.getElementById('pageLabel');
          const prev = document.getElementById('btnPrev');
          const next = document.getElementById('btnNext');
          const dots = document.querySelectorAll('#pageDots .dot');
          const cols = grid ? getComputedStyle(grid).gridTemplateColumns : '';
          return {
            panel: !!panel,
            open: !!(panel && !panel.hidden && getComputedStyle(panel).display !== 'none'),
            cards,
            label: label ? label.textContent.trim() : '',
            prev: prev ? {
              visible: getComputedStyle(prev).display !== 'none',
              aria: prev.getAttribute('aria-disabled'),
              text: (prev.textContent || '').trim()
            } : null,
            next: next ? {
              visible: getComputedStyle(next).display !== 'none',
              aria: next.getAttribute('aria-disabled'),
              text: (next.textContent || '').trim()
            } : null,
            dots: dots.length,
            currentDot: document.querySelectorAll('#pageDots .dot[aria-current="page"]').length,
            columns: cols,
            back: !!document.getElementById('btnBack'),
            close: !!document.getElementById('btnClose')
          };
        }"""
    )


def _open_skill_menu(page):
    button = page.locator("#btnSkill")
    if button.count() == 0:
        return False
    button.click()
    return True


def _fail(case_id, problems):
    assert not problems, case_id + ": " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-BAR")
def test_battle_bar_is_attack_skill_flee(page, base_url, menu_db, menu_ids):
    """Bottom bar is exactly 攻擊 / 技能 / 逃走. No per-skill buttons."""
    _login(page, base_url, MENU_KID6)
    learned = _learned_names(menu_db, menu_ids[MENU_KID6])
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    labels = _bar_labels(page)
    buttons = _bar_buttons(page)
    problems = []
    if labels != ["攻擊", "技能", "逃走"]:
        problems.append(
            f"command bar labels {labels} (buttons {buttons}); "
            "want exactly [攻擊, 技能, 逃走] and no individual skill buttons"
        )
    ids = [button["id"] for button in buttons]
    if ids != ["btnAttack", "btnSkill", "btnFlee"]:
        problems.append(f"command bar ids {ids}; want btnAttack, btnSkill, btnFlee in .command-bar")
    _fail("TC-FE-SKILLMENU-BAR", problems)
    assert len(learned) == 6


@pytest.mark.case_id("TC-FE-SKILLMENU-OPEN")
def test_skill_button_opens_wooden_menu(page, base_url, menu_db, menu_ids):
    """點 技能 opens #skillPanel.skill-panel above the bar. It starts closed."""
    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    problems = []
    before = _menu_snapshot(page)
    if before["open"]:
        problems.append("skill menu must start closed (hidden)")
    if not _open_skill_menu(page):
        problems.append(
            f"no #btnSkill to open the wooden menu; bar is {_bar_labels(page)}"
        )
    else:
        opened = _menu_snapshot(page)
        if not opened["open"]:
            problems.append("#skillPanel did not become visible")
        border = page.evaluate(
            """() => {
              const el = document.getElementById('skillPanel');
              if (!el) return 0;
              return parseFloat(getComputedStyle(el).borderTopWidth) || 0;
            }"""
        )
        if border < 4:
            problems.append(f"#skillPanel wooden frame border is {border}px; mock uses a thick wood border")
    _fail("TC-FE-SKILLMENU-OPEN", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-PAGE6")
def test_six_skills_fill_one_page(page, base_url, menu_db, menu_ids):
    """6 learned skills: all on page 1, label 1 / 1, both pager buttons disabled."""
    _login(page, base_url, MENU_KID6)
    learned = _learned_names(menu_db, menu_ids[MENU_KID6])
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    names = [row["name"] for row in learned]
    problems = []
    reachable = _names_reachable(page, learned)
    missing = [name for name in names if name not in reachable]
    if missing:
        problems.append(
            f"kid learned {names} but the UI only exposes {reachable}; missing {missing}. "
            "The bar currently keeps 3 skill slots, so a 6-skill kid cannot reach the rest"
        )
    if not _open_skill_menu(page):
        problems.append(f"no #btnSkill; bar is {_bar_labels(page)}")
    else:
        snap = _menu_snapshot(page)
        shown = [card["name"].strip() for card in snap["cards"]]
        if shown != names and set(shown) != set(names):
            problems.append(f"page 1 cards {shown}; want all 6 learned skills {names}")
        if len(snap["cards"]) != 6:
            problems.append(f"page 1 has {len(snap['cards'])} cards; want 6")
        if snap["label"] != "1 / 1":
            problems.append(f"page label {snap['label']!r}; want '1 / 1'")
        for key in ("prev", "next"):
            pager = snap[key]
            if not pager or not pager["visible"]:
                problems.append(f"{key} pager missing or hidden")
            elif pager["aria"] != "true":
                problems.append(f"{key} pager aria-disabled={pager['aria']!r}; want 'true' on the only page")
        if snap["dots"] != 1 or snap["currentDot"] != 1:
            problems.append(f"page dots {snap['dots']} current {snap['currentDot']}; want one current dot")
        columns = [part for part in snap["columns"].split() if part]
        if len(columns) != 2:
            problems.append(f"skill grid columns {snap['columns']!r}; want a 2×3 grid")
    _fail("TC-FE-SKILLMENU-PAGE6", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-PAGE8")
def test_eight_skills_page_to_the_remaining_two(page, base_url, menu_db, menu_ids):
    """8 skills: page 1 has 6, page 2 has exactly 2 real cards, pager ends disable."""
    _login(page, base_url, MENU_KID8)
    learned = _learned_names(menu_db, menu_ids[MENU_KID8])
    started = _start_and_show_battle(page, menu_ids[MENU_KID8])
    names = [row["name"] for row in started["skills"]]
    assert len(names) == 8, names
    problems = []
    reachable = _names_reachable(page, learned)
    missing = [name for name in names if name not in reachable]
    if missing:
        problems.append(
            f"8 learned skills {names} are not all reachable; visible {reachable}; missing {missing}"
        )
    if not _open_skill_menu(page):
        problems.append(f"no #btnSkill; bar is {_bar_labels(page)}")
        _fail("TC-FE-SKILLMENU-PAGE8", problems)
        return
    first = _menu_snapshot(page)
    if first["label"] != "1 / 2":
        problems.append(f"first label {first['label']!r}; want '1 / 2'")
    if len(first["cards"]) != SKILL_MENU_PAGE_SIZE:
        problems.append(f"page 1 has {len(first['cards'])} cards; want 6")
    if not first["prev"] or first["prev"]["aria"] != "true":
        problems.append("◀ must be visible and aria-disabled on page 1")
    if not first["next"] or first["next"]["aria"] == "true":
        problems.append("▶ must be enabled on page 1 of 2")
    nxt = page.locator("#btnNext")
    if nxt.count() == 0:
        problems.append("missing #btnNext")
    else:
        nxt.click()
        second = _menu_snapshot(page)
        if second["label"] != "2 / 2":
            problems.append(f"second label {second['label']!r}; want '2 / 2'")
        if len(second["cards"]) != 2:
            problems.append(
                f"page 2 has {len(second['cards'])} .skill-card nodes; want exactly 2, "
                "with the other four slots empty (no placeholder / 未解鎖 cards)"
            )
        placeholders = [
            card for card in second["cards"] if not card["name"].strip() or "未解鎖" in card["name"]
        ]
        if placeholders:
            problems.append(f"page 2 has placeholder cards {placeholders}")
        if not second["next"] or second["next"]["aria"] != "true":
            problems.append("▶ must be aria-disabled on the last page")
        if not second["prev"] or second["prev"]["aria"] == "true":
            problems.append("◀ must be enabled on page 2")
        page.locator("#btnPrev").click()
        back = _menu_snapshot(page)
        if back["label"] != "1 / 2" or len(back["cards"]) != 6:
            problems.append(f"◀ did not return to page 1 ({back['label']}, {len(back['cards'])} cards)")
        shown = {card["name"].strip() for card in first["cards"] + second["cards"]}
        if shown != set(names):
            problems.append(f"paged cards {sorted(shown)} != learned {names}")
    _fail("TC-FE-SKILLMENU-PAGE8", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-CARDS")
def test_each_card_shows_name_mp_and_description(page, base_url, menu_db, menu_ids):
    """Every card shows the skill name, an MP pill, and description text.

    Description wording is not taken from the mock. Colloquial characters are
    rejected here too (case group 2) once the cards exist.
    """
    _login(page, base_url, MENU_KID6)
    learned = {row["name"]: row for row in _learned_names(menu_db, menu_ids[MENU_KID6])}
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    problems = []
    if not _open_skill_menu(page):
        problems.append(f"no skill menu; bar is {_bar_labels(page)}")
        _fail("TC-FE-SKILLMENU-CARDS", problems)
        return
    snap = _menu_snapshot(page)
    if len(snap["cards"]) != 6:
        problems.append(f"expected 6 cards, saw {len(snap['cards'])}")
    for card in snap["cards"]:
        name = card["name"].strip()
        row = learned.get(name)
        if row is None:
            problems.append(f"card name {name!r} is not one of the learned skills")
            continue
        if card["pill"].strip() != f"MP {row['mp_cost']}":
            problems.append(f"{name} MP pill {card['pill']!r}; want 'MP {row['mp_cost']}'")
        if not card["desc"].strip():
            problems.append(f"{name} card has no .skill-desc")
        hits = colloquial_hits(card["desc"])
        if hits:
            problems.append(f"{name} card text {card['desc']!r} contains colloquial {''.join(hits)}")
    _fail("TC-FE-SKILLMENU-CARDS", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-BROKE")
def test_unaffordable_card_shows_mp_not_enough_and_does_not_cast(
    page, base_url, menu_db, menu_ids
):
    """MP cost above current MP: disabled, text 「MP 不夠」, click does not cast."""
    _login(page, base_url, MENU_KID6)
    learned = _learned_names(menu_db, menu_ids[MENU_KID6])
    mp = 3
    _start_and_show_battle(page, menu_ids[MENU_KID6], mp=mp, db_path=menu_db)
    broke = next(row for row in learned if row["mp_cost"] > mp)
    before = _battle_state(page, menu_ids[MENU_KID6])
    problems = []
    if not _open_skill_menu(page):
        problems.append(
            f"no skill menu to show 「MP 不夠」 on {broke['name']} (cost {broke['mp_cost']}, MP {mp}); "
            f"bar is {_bar_labels(page)}"
        )
    else:
        card = page.locator("#skillGrid .skill-card", has_text=broke["name"])
        if card.count() == 0:
            # It may sit on a later page. Walk ▶ until found or the pager stops.
            for _ in range(4):
                if page.locator("#skillGrid .skill-card", has_text=broke["name"]).count():
                    break
                nxt = page.locator("#btnNext")
                if nxt.count() == 0 or nxt.get_attribute("aria-disabled") == "true":
                    break
                nxt.click()
            card = page.locator("#skillGrid .skill-card", has_text=broke["name"])
        if card.count() == 0:
            problems.append(f"no card for unaffordable {broke['name']}")
        else:
            disabled = card.first.get_attribute("aria-disabled") == "true" or card.first.is_disabled()
            text = card.first.inner_text()
            if not disabled:
                problems.append(f"{broke['name']} is not aria-disabled / disabled")
            if "MP 不夠" not in text:
                problems.append(f"{broke['name']} card text {text!r} does not include 「MP 不夠」")
            card.first.click(force=True)
            page.wait_for_timeout(300)
            after = _battle_state(page, menu_ids[MENU_KID6])
            if after["mp"] != before["mp"] or after["turns"] != before["turns"]:
                problems.append(
                    f"clicking unaffordable {broke['name']} cast or consumed a turn: "
                    f"mp {before['mp']} -> {after['mp']}, turns {before['turns']} -> {after['turns']}"
                )
    _fail("TC-FE-SKILLMENU-BROKE", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-CAST")
def test_affordable_card_casts_and_closes_the_menu(page, base_url, menu_db, menu_ids):
    """An affordable self skill (蓄力, not 營養餐) spends its MP cost and closes the menu."""
    _login(page, base_url, MENU_KID6)
    learned = _learned_names(menu_db, menu_ids[MENU_KID6])
    charge = next(row for row in learned if row["name"] == "蓄力")
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    before = _battle_state(page, menu_ids[MENU_KID6])
    problems = []
    if not _open_skill_menu(page):
        problems.append(f"no skill menu to cast from; bar is {_bar_labels(page)}")
        _fail("TC-FE-SKILLMENU-CAST", problems)
        return
    card = page.locator("#skillGrid .skill-card", has_text="蓄力")
    if card.count() == 0:
        problems.append("蓄力 card is not on the open page")
    else:
        card.first.click()
        page.wait_for_timeout(400)
        after = _battle_state(page, menu_ids[MENU_KID6])
        expected = before["mp"] - int(charge["mp_cost"])
        if after["mp"] != expected:
            problems.append(
                f"蓄力 MP {before['mp']} -> {after['mp']}; want {expected} (cost {charge['mp_cost']})"
            )
        snap = _menu_snapshot(page)
        if snap["open"]:
            problems.append("menu stayed open after the cast")
    _fail("TC-FE-SKILLMENU-CAST", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-VITALS")
def test_hp_mp_boxes_stay_inside_the_stage_while_the_menu_is_open(
    page, base_url, menu_db, menu_ids
):
    """#playerVitals / #hpNums / #mpNums sit fully inside the 1280×720 stage and are not clipped."""
    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    problems = []
    if not _open_skill_menu(page):
        problems.append(f"menu is not open, so vitals-during-menu cannot be checked; bar is {_bar_labels(page)}")
    layout = page.evaluate(_LAYOUT_JS)
    stage = layout["stage"]
    if not stage or stage["offsetW"] != STAGE_W or stage["offsetH"] != STAGE_H:
        problems.append(f"stage layout {stage}; want offset {STAGE_W}×{STAGE_H}")
    if not layout["vitals"] or layout["vitals"]["hidden"]:
        problems.append("missing visible #playerVitals (mock HP/MP boxes)")
    else:
        if not _inside(layout["vitals"], stage):
            problems.append(f"#playerVitals is outside the stage: {layout['vitals']} stage {stage}")
        if layout["vitalsClipped"]:
            problems.append("#playerVitals is clipped by an overflow ancestor")
        if _overlaps(layout["vitals"], layout["footer"]):
            problems.append("#playerVitals overlaps #ktFooter")
    for key in ("hp", "mp"):
        box = layout[key]
        if not box or box["hidden"]:
            problems.append(f"missing visible #{'hpNums' if key == 'hp' else 'mpNums'}")
        elif not _inside(box, stage) or layout["hpClipped" if key == "hp" else "mpClipped"]:
            problems.append(f"#{key} box is clipped or outside the stage: {box}")
    _fail("TC-FE-SKILLMENU-VITALS", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-LAYOUT")
def test_skill_menu_sits_above_the_footer_inside_the_stage(page, base_url, menu_db, menu_ids):
    """Menu bottom <= footer top and <= command bar top, and the menu stays inside the stage."""
    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    problems = []
    if not _open_skill_menu(page):
        problems.append(f"no #skillPanel to measure; bar is {_bar_labels(page)}")
        _fail("TC-FE-SKILLMENU-LAYOUT", problems)
        return
    layout = page.evaluate(_LAYOUT_JS)
    panel, stage, footer, bar = layout["panel"], layout["stage"], layout["footer"], layout["bar"]
    if not panel or panel["hidden"]:
        problems.append("#skillPanel is not visible")
    else:
        if not _inside(panel, stage):
            problems.append(f"#skillPanel is outside the 1280×720 stage: panel {panel} stage {stage}")
        if layout["panelClipped"]:
            problems.append("#skillPanel is clipped by overflow")
        if footer and panel["bottom"] > footer["top"] + 1:
            problems.append(
                f"menu overlaps the bottom tab bar: panel.bottom {panel['bottom']:.1f} "
                f"> #ktFooter.top {footer['top']:.1f}"
            )
        if bar and panel["bottom"] > bar["top"] + 1:
            problems.append(
                f"menu overlaps the command bar: panel.bottom {panel['bottom']:.1f} "
                f"> bar.top {bar['top']:.1f}"
            )
    _fail("TC-FE-SKILLMENU-LAYOUT", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-CLOSE")
def test_back_close_and_escape_dismiss_without_casting(page, base_url, menu_db, menu_ids):
    """返回, ✕, and Escape close the menu and do not spend MP or a turn."""
    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    problems = []
    before = _battle_state(page, menu_ids[MENU_KID6])

    def _dismiss(how):
        if not _open_skill_menu(page):
            problems.append(f"cannot open menu before {how}; bar is {_bar_labels(page)}")
            return
        if how == "back":
            control = page.locator("#btnBack")
        elif how == "close":
            control = page.locator("#btnClose")
        else:
            control = None
        if control is not None and control.count() == 0:
            problems.append(f"missing control for {how}")
            return
        if how == "escape":
            page.keyboard.press("Escape")
        else:
            control.click()
        page.wait_for_timeout(200)
        snap = _menu_snapshot(page)
        if snap["open"]:
            problems.append(f"{how} left #skillPanel open")
        after = _battle_state(page, menu_ids[MENU_KID6])
        if after["mp"] != before["mp"] or after["turns"] != before["turns"]:
            problems.append(f"{how} changed mp/turns {before} -> {after}")

    if page.locator("#btnSkill").count() == 0:
        problems.append(f"no #btnSkill; close path cannot be opened. bar is {_bar_labels(page)}")
    else:
        _dismiss("back")
        _dismiss("close")
        _dismiss("escape")
    _fail("TC-FE-SKILLMENU-CLOSE", problems)


def _post_region_battle(page, kid_id):
    """One real region-1 battle-start. Count comes from random.randint(1, 3)."""
    started = page.evaluate(
        """async (kidId) => {
          const r = await fetch(`/api/kids/${kidId}/expedition/battle-start`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'same-origin',
            body: JSON.stringify({region_id: 1})
          });
          const data = await r.json();
          const monsters = data.monsters || [];
          return {
            status: r.status,
            error: data.error || '',
            names: monsters.map((monster) => monster.name || '')
          };
        }""",
        kid_id,
    )
    assert started["status"] == 201, started
    return started


def _show_current_battle(page):
    page.evaluate("async () => { await loadTown(); st('expedition'); }")
    page.locator(".battle-scene .m-name").first.wait_for(state="visible", timeout=8000)


def _start_battle_with_enemy_count(page, kid_id, enemy_count):
    """Restart region 1 until the live encounter has this many 野狼.

    battle_start rolls random.randint(1, 3) for a non-preview kid. A new
    start abandons the previous running battle, which is the game's own path.
    """
    last = None
    for _ in range(40):
        last = _post_region_battle(page, kid_id)
        if len(last["names"]) == enemy_count and all(name == "野狼" for name in last["names"]):
            _show_current_battle(page)
            return last
    raise AssertionError(
        f"region 1 did not roll {enemy_count} 野狼 in 40 battle-starts; last={last}"
    )


_ENEMY_PLATE_JS = """
() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      hidden: cs.display === 'none' || cs.visibility === 'hidden' || el.hasAttribute('hidden'),
      display: cs.display,
      visibility: cs.visibility,
      w: r.width, h: r.height,
      left: r.left, top: r.top, right: r.right, bottom: r.bottom
    };
  };
  const cards = [...document.querySelectorAll('.battle-scene .monster-card')];
  return {
    count: cards.length,
    enemies: cards.map((card) => ({
      nameText: ((card.querySelector('.m-name') || {}).textContent || '').trim(),
      name: box(card.querySelector('.m-name')),
      hpbar: box(card.querySelector('.m-hp-bar')),
      hpnum: box(card.querySelector('.m-hp-text'))
    }))
  };
}
"""

_ENEMY_PARTS = (
    ("name", ".m-name", "name plate"),
    ("hpbar", ".m-hp-bar", "HP bar"),
    ("hpnum", ".m-hp-text", "HP number"),
)


def _intersection_area(a, b):
    if not a or not b:
        return None
    width = min(a["right"], b["right"]) - max(a["left"], b["left"])
    height = min(a["bottom"], b["bottom"]) - max(a["top"], b["top"])
    if width <= 0 or height <= 0:
        return 0.0
    return width * height


def _plate_visible(box):
    return bool(box) and not box["hidden"] and box["w"] > 0 and box["h"] > 0


@pytest.mark.case_id("TC-FE-SKILLMENU-ENEMY-VISIBLE")
@pytest.mark.parametrize("enemy_count", [3, 1], ids=["3-enemies", "1-enemy"])
def test_skill_menu_leaves_enemy_name_and_hp_visible(
    page, base_url, menu_db, menu_ids, enemy_count
):
    """Open skill menu must not cover any enemy name plate, HP bar, or HP number.

    Sprites may sit under the panel. Viewport is 1280×720. Region 1 lines up
    1–3 野狼 the same way battle_start does.
    """
    case_id = "TC-FE-SKILLMENU-ENEMY-VISIBLE"
    _login(page, base_url, MENU_KID6)
    started = _start_battle_with_enemy_count(page, menu_ids[MENU_KID6], enemy_count)
    problems = []
    if not _open_skill_menu(page):
        problems.append(
            f"no #btnSkill, so enemy plates cannot be checked against #skillPanel; "
            f"bar is {_bar_labels(page)}; rolled {started['names']}"
        )
        _fail(f"{case_id} [{enemy_count}]", problems)
        return
    panel_loc = page.locator("#skillPanel")
    try:
        panel_loc.wait_for(state="visible", timeout=3000)
    except Exception:
        problems.append(f"#skillPanel did not become visible; rolled {started['names']}")
        _fail(f"{case_id} [{enemy_count}]", problems)
        return

    plates = page.evaluate(_ENEMY_PLATE_JS)
    layout = page.evaluate(_LAYOUT_JS)
    panel = layout["panel"]
    stage = layout["stage"]
    footer = layout["footer"]
    bar = layout["bar"]
    if plates["count"] != enemy_count:
        problems.append(
            f"battle shows {plates['count']} .monster-card, want {enemy_count}; rolled {started['names']}"
        )
    if not panel or panel["hidden"]:
        problems.append("#skillPanel is not visible")
    else:
        if not _inside(panel, stage):
            problems.append(f"#skillPanel is outside the 1280×720 stage: panel {panel} stage {stage}")
        if layout["panelClipped"]:
            problems.append("#skillPanel is clipped by overflow")
        if footer and panel["bottom"] > footer["top"] + 1:
            problems.append(
                f"menu overlaps the bottom tab bar: panel.bottom {panel['bottom']:.1f} "
                f"> #ktFooter.top {footer['top']:.1f}"
            )
        if bar and panel["bottom"] > bar["top"] + 1:
            problems.append(
                f"menu overlaps the command bar: panel.bottom {panel['bottom']:.1f} "
                f"> bar.top {bar['top']:.1f}"
            )

    ranked = sorted(
        enumerate(plates["enemies"]),
        key=lambda item: (item[1]["name"] or {}).get("left", item[0]),
    )
    side_names = {0: "left", 1: "middle", 2: "right"} if enemy_count == 3 else {0: "only"}
    plate_tops = []
    for side, (index, enemy) in enumerate(ranked):
        label = side_names.get(side, f"slot{side}")
        title = enemy["nameText"] or f"enemy {index}"
        for key, selector, what in _ENEMY_PARTS:
            box = enemy[key]
            where = f"{label} enemy {index} ({title}) {what} {selector}"
            if not _plate_visible(box):
                problems.append(f"{where} is not visible: {box}")
                continue
            if key in ("name", "hpbar"):
                plate_tops.append(box["top"])
            if panel and not panel["hidden"]:
                area = _intersection_area(panel, box)
                if area is None or area > 0:
                    problems.append(
                        f"{where} overlaps #skillPanel by {area:.1f} px² "
                        f"(plate top {box['top']:.1f} bottom {box['bottom']:.1f} "
                        f"left {box['left']:.1f} right {box['right']:.1f}; "
                        f"panel top {panel['top']:.1f} bottom {panel['bottom']:.1f})"
                    )
    if panel and not panel["hidden"] and plate_tops:
        topmost = min(plate_tops)
        gap = topmost - panel["bottom"]
        if gap < 8:
            problems.append(
                f"#skillPanel bottom {panel['bottom']:.1f} is only {gap:.1f}px above "
                f"the topmost enemy name plate/HP bar at {topmost:.1f}; want >= 8px"
            )
    elif panel and not panel["hidden"]:
        problems.append("no visible enemy name plate or HP bar to measure the 8px clearance")
    _fail(f"{case_id} [{enemy_count}]", problems)


def _px(value):
    if value is None:
        return "missing"
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _px_set(values):
    cleaned = sorted({None if value is None else round(float(value), 3) for value in values})
    return ", ".join(_px(value) for value in cleaned)


def _wait_fonts(page):
    page.evaluate("() => (document.fonts && document.fonts.ready) || null")


def _selectors():
    return {
        "panel": SEL_SKILL_PANEL,
        "card": SEL_SKILL_CARD,
        "name": SEL_SKILL_NAME,
        "desc": SEL_SKILL_DESC,
        "icon": SEL_SKILL_ICON,
        "title": SEL_SKILL_TITLE,
        "page": SEL_PAGE_LABEL,
        "back": SEL_BTN_BACK,
        "prev": SEL_BTN_PREV,
        "next": SEL_BTN_NEXT,
        "close": SEL_BTN_CLOSE,
        "mp": SEL_MP_NOW,
        "dots": SEL_PAGE_DOTS,
        "toast": SEL_WILD_TOAST,
        "bar": SEL_COMMAND_BAR,
        "wood": SEL_BATTLE_BAR,
        "monster": SEL_MONSTER_CARD,
        "mName": SEL_M_NAME,
        "mHp": SEL_M_HP_BAR,
        "mHpText": SEL_M_HP_TEXT,
        "vitals": SEL_PLAYER_VITALS,
    }


def _measure_cards(page):
    """Font, padding, and boxes for the visible skill cards. Index names are excluded."""
    _wait_fonts(page)
    return page.evaluate(
        """(sels) => {
          const rect = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return {
              hidden: el.hasAttribute('hidden') || cs.display === 'none' || cs.visibility === 'hidden',
              w: r.width, h: r.height, left: r.left, top: r.top, right: r.right, bottom: r.bottom
            };
          };
          const panelEl = document.querySelector(sels.panel);
          const panel = rect(panelEl);
          const cards = [...document.querySelectorAll(sels.card)].map((card) => {
            const nameEl = card.querySelector(sels.name);
            const descEl = card.querySelector(sels.desc);
            const iconEl = card.querySelector(sels.icon);
            const cardCs = getComputedStyle(card);
            const nameCs = nameEl ? getComputedStyle(nameEl) : null;
            const descCs = descEl ? getComputedStyle(descEl) : null;
            const iconCs = iconEl ? getComputedStyle(iconEl) : null;
            const descBox = rect(descEl);
            return {
              name: nameEl ? (nameEl.textContent || '').trim() : '',
              desc: descEl ? (descEl.textContent || '').trim() : '',
              namePx: nameCs ? parseFloat(nameCs.fontSize) : null,
              descPx: descCs ? parseFloat(descCs.fontSize) : null,
              iconPx: iconCs ? parseFloat(iconCs.fontSize) : null,
              iconBox: rect(iconEl),
              cardBox: rect(card),
              padTop: parseFloat(cardCs.paddingTop),
              padRight: parseFloat(cardCs.paddingRight),
              padBottom: parseFloat(cardCs.paddingBottom),
              padLeft: parseFloat(cardCs.paddingLeft),
              descWhite: descCs ? descCs.whiteSpace : '',
              descH: descBox ? descBox.h : null,
              descScrollW: descEl ? descEl.scrollWidth : null,
              descClientW: descEl ? descEl.clientWidth : null
            };
          });
          const label = document.querySelector(sels.page);
          return {
            panel,
            open: !!(panel && !panel.hidden),
            label: label ? (label.textContent || '').trim() : '',
            cards
          };
        }""",
        _selectors(),
    )


def _measure_title(page):
    _wait_fonts(page)
    return page.evaluate(
        """(sels) => {
          const rect = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return {
              hidden: el.hasAttribute('hidden') || cs.display === 'none' || cs.visibility === 'hidden',
              w: r.width, h: r.height, left: r.left, top: r.top, right: r.right, bottom: r.bottom,
              fontPx: parseFloat(cs.fontSize),
              text: (el.textContent || '').trim()
            };
          };
          const panelEl = document.querySelector(sels.panel);
          const dots = [...document.querySelectorAll(sels.dots)].map((el, index) => {
            const box = rect(el);
            if (box) box.key = 'dot' + index;
            return box;
          });
          return {
            panel: rect(panelEl),
            title: rect(document.querySelector(sels.title)),
            page: rect(document.querySelector(sels.page)),
            back: rect(document.querySelector(sels.back)),
            prev: rect(document.querySelector(sels.prev)),
            next: rect(document.querySelector(sels.next)),
            close: rect(document.querySelector(sels.close)),
            mp: rect(document.querySelector(sels.mp)),
            dots
          };
        }""",
        _selectors(),
    )


def _open_menu_or_problem(page, problems, where):
    if not _open_skill_menu(page):
        problems.append(f"{where}: no {SEL_BTN_SKILL}; bar is {_bar_labels(page)}")
        return False
    try:
        page.locator(SEL_SKILL_PANEL).wait_for(state="visible", timeout=3000)
    except Exception:
        problems.append(f"{where}: {SEL_SKILL_PANEL} did not become visible")
        return False
    return True


def _go_next_skill_page(page):
    nxt = page.locator(SEL_BTN_NEXT)
    if nxt.count() == 0 or nxt.get_attribute("aria-disabled") == "true":
        return False
    nxt.click()
    return True


def _visible(box):
    return bool(box) and not box.get("hidden") and box.get("w", 0) > 2 and box.get("h", 0) > 2


def _insets(inner, outer):
    return {
        "left": inner["left"] - outer["left"],
        "top": inner["top"] - outer["top"],
        "right": outer["right"] - inner["right"],
        "bottom": outer["bottom"] - inner["bottom"],
    }


def _append_card_type_problems(problems, groups):
    """groups is a list of (where, measure-payload)."""
    cards = []
    for where, payload in groups:
        panel = payload.get("panel")
        if not payload.get("open"):
            problems.append(f"{where}: skill menu is not open")
            continue
        if not payload.get("cards"):
            problems.append(f"{where}: no {SEL_SKILL_CARD}")
            continue
        for card in payload["cards"]:
            item = dict(card)
            item["where"] = where
            item["panel"] = panel
            cards.append(item)
    if not cards:
        return

    def _below(key, floor):
        bad = [card for card in cards if card.get(key) is None or card[key] < floor]
        return bad

    name_bad = _below("namePx", SKILL_NAME_MIN_PX)
    if name_bad:
        problems.append(
            f".skill-name font-size {_px_set(card['namePx'] for card in name_bad)}px "
            f"on {len(name_bad)} card(s); want >= {SKILL_NAME_MIN_PX}px"
        )
    desc_bad = _below("descPx", SKILL_DESC_MIN_PX)
    if desc_bad:
        problems.append(
            f".skill-desc font-size {_px_set(card['descPx'] for card in desc_bad)}px "
            f"on {len(desc_bad)} card(s); want >= {SKILL_DESC_MIN_PX}px"
        )
    icon_font_bad = _below("iconPx", SKILL_ICON_FONT_MIN_PX)
    if icon_font_bad:
        problems.append(
            f".skill-icon font-size {_px_set(card['iconPx'] for card in icon_font_bad)}px "
            f"on {len(icon_font_bad)} card(s); want >= {SKILL_ICON_FONT_MIN_PX}px"
        )
    icon_box_bad = []
    for card in cards:
        box = card.get("iconBox")
        if not _visible(box) or box["w"] < SKILL_ICON_BOX_MIN_PX or box["h"] < SKILL_ICON_BOX_MIN_PX:
            icon_box_bad.append(card)
    if icon_box_bad:
        sizes = sorted({
            (
                None if not card.get("iconBox") else round(card["iconBox"]["w"], 3),
                None if not card.get("iconBox") else round(card["iconBox"]["h"], 3),
            )
            for card in icon_box_bad
        })
        shown = ", ".join(
            "missing" if pair[0] is None else f"{_px(pair[0])}×{_px(pair[1])}" for pair in sizes
        )
        problems.append(
            f".skill-icon box {shown} on {len(icon_box_bad)} card(s); "
            f"want >= {SKILL_ICON_BOX_MIN_PX}×{SKILL_ICON_BOX_MIN_PX}"
        )
    pad_bad = [
        card
        for card in cards
        if card["padTop"] < SKILL_CARD_PAD_BLOCK_MIN_PX
        or card["padBottom"] < SKILL_CARD_PAD_BLOCK_MIN_PX
        or card["padLeft"] < SKILL_CARD_PAD_INLINE_MIN_PX
        or card["padRight"] < SKILL_CARD_PAD_INLINE_MIN_PX
    ]
    if pad_bad:
        pads = sorted({
            (
                round(card["padTop"], 3),
                round(card["padRight"], 3),
                round(card["padBottom"], 3),
                round(card["padLeft"], 3),
            )
            for card in pad_bad
        })
        shown = ", ".join(
            f"{_px(top)}px {_px(right)}px {_px(bottom)}px {_px(left)}px" for top, right, bottom, left in pads
        )
        problems.append(
            f".skill-card padding (top right bottom left) {shown}; "
            f"want block >= {SKILL_CARD_PAD_BLOCK_MIN_PX}px and inline >= {SKILL_CARD_PAD_INLINE_MIN_PX}px"
        )
    short_cards = [
        card
        for card in cards
        if not _visible(card.get("cardBox")) or card["cardBox"]["h"] < SKILL_CARD_MIN_HEIGHT_PX
    ]
    if short_cards:
        problems.append(
            f".skill-card height {_px_set((card.get('cardBox') or {}).get('h') for card in short_cards)}px; "
            f"want >= {SKILL_CARD_MIN_HEIGHT_PX}px"
        )
    outside = []
    for card in cards:
        if not _visible(card.get("cardBox")) or not _visible(card.get("panel")):
            outside.append(f"{card['where']} {card['name'] or '?'} missing box")
        elif not _inside(card["cardBox"], card["panel"]):
            box = card["cardBox"]
            panel = card["panel"]
            outside.append(
                f"{card['where']} {card['name']} card "
                f"L{_px(box['left'])} T{_px(box['top'])} R{_px(box['right'])} B{_px(box['bottom'])} "
                f"outside panel L{_px(panel['left'])} T{_px(panel['top'])} "
                f"R{_px(panel['right'])} B{_px(panel['bottom'])}"
            )
    if outside:
        problems.append("cards outside the panel: " + " | ".join(outside))
    inset_bad = []
    for card in cards:
        icon = card.get("iconBox")
        box = card.get("cardBox")
        if not _visible(icon) or not _visible(box):
            inset_bad.append(f"{card['name'] or '?'} icon missing")
            continue
        insets = _insets(icon, box)
        if any(value < SKILL_ICON_INSET_MIN_PX for value in insets.values()):
            inset_bad.append(
                f"{card['name']} inset L{_px(insets['left'])} T{_px(insets['top'])} "
                f"R{_px(insets['right'])} B{_px(insets['bottom'])}"
            )
    if inset_bad:
        shown = inset_bad[:6]
        extra = f" (+{len(inset_bad) - len(shown)} more)" if len(inset_bad) > len(shown) else ""
        problems.append(
            f"icon inset < {SKILL_ICON_INSET_MIN_PX}px from the card border box: "
            + " | ".join(shown)
            + extra
        )
    wrap_bad = []
    overflow_by_name = {}
    for card in cards:
        label = card["name"] or "?"
        font_px = card.get("descPx") or 0
        height = card.get("descH")
        white = card.get("descWhite")
        if white != "nowrap" or height is None or font_px <= 0 or height > font_px * SKILL_DESC_LINE_RATIO + 0.5:
            wrap_bad.append(
                f"{card['where']} {label} white-space {white!r} height {_px(height)}px "
                f"font {_px(font_px)}px"
            )
        scroll_w = card.get("descScrollW")
        client_w = card.get("descClientW")
        if client_w is None or client_w <= 0 or scroll_w is None or scroll_w > client_w + 1:
            delta = -1 if scroll_w is None or client_w is None else scroll_w - client_w
            previous = overflow_by_name.get(label)
            if previous is None or delta > previous[0]:
                overflow_by_name[label] = (
                    delta,
                    f"{label} {card.get('desc')!r} scrollWidth {_px(scroll_w)} clientWidth {_px(client_w)}",
                )
    if wrap_bad:
        shown = wrap_bad[:8]
        extra = f" (+{len(wrap_bad) - len(shown)} more)" if len(wrap_bad) > len(shown) else ""
        problems.append("description is not a single nowrap line: " + " | ".join(shown) + extra)
    if overflow_by_name:
        shown = [item[1] for item in overflow_by_name.values()]
        problems.append(
            f"description overflows on {len(shown)} skill(s): " + " | ".join(shown)
        )


def _collect_skill_pages(page, where):
    """Open the menu and return one payload per page. Empty list if it cannot open."""
    problems_open = []
    if not _open_menu_or_problem(page, problems_open, where):
        return problems_open, []
    pages = []
    for index in range(6):
        payload = _measure_cards(page)
        payload["pageIndex"] = index
        pages.append(payload)
        if not _go_next_skill_page(page):
            break
    return [], pages


@pytest.mark.case_id("TC-FE-SKILLMENU-TYPE")
def test_tc_fe_skillmenu_type_card_text_is_larger(page, base_url, menu_ids):
    """Card name, description, icon, and padding are large enough, and every description fits.

    Covers the 6-skill kid, page 2 of the 8-skill kid, and all 22 seeded skills.
    """
    case_id = "TC-FE-SKILLMENU-TYPE"
    problems = []
    groups = []

    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    open_problems, pages = _collect_skill_pages(page, "6-skill")
    problems.extend(open_problems)
    if pages:
        groups.append(("6-skill", pages[0]))
        if len(pages[0]["cards"]) != 6:
            problems.append(f"6-skill page shows {len(pages[0]['cards'])} cards; want 6")

    _login(page, base_url, MENU_KID8)
    _start_and_show_battle(page, menu_ids[MENU_KID8])
    open_problems, pages = _collect_skill_pages(page, "8-skill")
    problems.extend(open_problems)
    page2 = next((item for item in pages if item.get("pageIndex") == 1), None)
    if page2 is None:
        problems.append("8-skill kid has no page 2 to measure")
    else:
        groups.append(("8-skill page 2", page2))
        if page2.get("label") != "2 / 2":
            problems.append(f"8-skill page 2 label {page2.get('label')!r}; want '2 / 2'")
        if len(page2["cards"]) != 2:
            problems.append(f"8-skill page 2 shows {len(page2['cards'])} cards; want 2")

    _login(page, base_url, MENU_KID22)
    started = _start_and_show_battle(page, menu_ids[MENU_KID22])
    open_problems, pages = _collect_skill_pages(page, "22-skill")
    problems.extend(open_problems)
    seen = []
    for item in pages:
        groups.append((f"22-skill page {item['pageIndex'] + 1}", item))
        seen.extend(card["name"] for card in item["cards"] if card["name"])
    missing = [name for name in SEEDED_SKILL_NAMES if name not in seen]
    if missing:
        problems.append(
            f"22-skill kid battle skills {[row['name'] for row in started['skills']]}; "
            f"menu never showed {missing}"
        )
    _append_card_type_problems(problems, groups)
    _fail(case_id, problems)


_NOSQUEEZE_JS = """(args) => {
  const sels = args.sels;
  const eps = args.eps;
  const spacingPx = (value) => {
    if (value == null || value === 'normal') return 0;
    const n = parseFloat(value);
    return Number.isFinite(n) ? n : null;
  };
  const matrixOf = (transform) => {
    const raw = (transform || 'none').trim();
    if (raw === 'none') return {ok: true, transform: 'none'};
    const matched = raw.match(/^matrix3d\\(([^)]+)\\)$/) || raw.match(/^matrix\\(([^)]+)\\)$/);
    if (!matched) return {ok: false, transform: raw};
    const parts = matched[1].split(',').map((item) => parseFloat(item));
    const three = raw.startsWith('matrix3d');
    const a = parts[0];
    const b = parts[1];
    const c = three ? parts[4] : parts[2];
    const d = three ? parts[5] : parts[3];
    const ok = [a, b, c, d].every((n) => Number.isFinite(n))
      && Math.abs(a - 1) <= eps && Math.abs(b) <= eps
      && Math.abs(c) <= eps && Math.abs(d - 1) <= eps;
    return {ok, transform: raw, a, b, c, d};
  };
  const isCjk = (cp) => (
    (cp >= 0x3000 && cp <= 0x303F)
    || (cp >= 0x4E00 && cp <= 0x9FFF)
    || (cp >= 0xFF00 && cp <= 0xFFEF)
  );
  const panel = document.querySelector(sels.panel);
  const chainOf = (el) => {
    const rows = [];
    let node = el;
    let reached = false;
    while (node) {
      const parsed = matrixOf(getComputedStyle(node).transform);
      const cls = typeof node.className === 'string' ? node.className : '';
      rows.push({
        id: node.id || '',
        cls,
        ok: parsed.ok,
        transform: parsed.transform,
        a: parsed.a, b: parsed.b, c: parsed.c, d: parsed.d
      });
      if (panel && node === panel) {
        reached = true;
        break;
      }
      node = node.parentElement;
    }
    return {rows, reached};
  };
  const glyphsOf = (el, fontPx) => {
    const found = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const text = node.textContent || '';
      for (let i = 0; i < text.length; ) {
        const cp = text.codePointAt(i);
        const size = cp > 0xFFFF ? 2 : 1;
        if (isCjk(cp)) {
          const range = document.createRange();
          range.setStart(node, i);
          range.setEnd(node, i + size);
          let width = 0;
          for (const rect of range.getClientRects()) width = Math.max(width, rect.width);
          found.push({
            ch: String.fromCodePoint(cp),
            width,
            ratio: fontPx > 0 ? width / fontPx : null
          });
        }
        i += size;
      }
    }
    let minRatio = null;
    let minChar = '';
    let minWidth = null;
    for (const glyph of found) {
      if (glyph.ratio == null) continue;
      if (minRatio == null || glyph.ratio < minRatio) {
        minRatio = glyph.ratio;
        minChar = glyph.ch;
        minWidth = glyph.width;
      }
    }
    return {count: found.length, minRatio, minChar, minWidth};
  };
  const sample = (el, role, skill) => {
    if (!el) return {present: false, role, skill};
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const fontPx = parseFloat(cs.fontSize);
    const chain = chainOf(el);
    const glyphs = glyphsOf(el, fontPx);
    return {
      present: true,
      role,
      skill,
      text: (el.textContent || '').trim(),
      letterSpacing: cs.letterSpacing,
      letterSpacingPx: spacingPx(cs.letterSpacing),
      wordSpacing: cs.wordSpacing,
      wordSpacingPx: spacingPx(cs.wordSpacing),
      fontStretch: cs.fontStretch,
      textOverflow: cs.textOverflow,
      whiteSpace: cs.whiteSpace,
      fontPx,
      height: rect.height,
      rectW: rect.width,
      offsetW: el.offsetWidth,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      reachedPanel: chain.reached,
      transforms: chain.rows,
      glyphCount: glyphs.count,
      minRatio: glyphs.minRatio,
      minChar: glyphs.minChar,
      minWidth: glyphs.minWidth
    };
  };
  const cards = [...document.querySelectorAll(sels.card)].map((card) => {
    const nameEl = card.querySelector(sels.name);
    const descEl = card.querySelector(sels.desc);
    const skill = nameEl ? (nameEl.textContent || '').trim() : '';
    return {name: sample(nameEl, 'name', skill), desc: sample(descEl, 'desc', skill)};
  });
  const label = document.querySelector(sels.page);
  return {
    open: !!(panel && !panel.hasAttribute('hidden') && getComputedStyle(panel).display !== 'none'),
    label: label ? (label.textContent || '').trim() : '',
    title: sample(document.querySelector(sels.title), 'title', ''),
    page: sample(label, 'page', ''),
    cards
  };
}"""


def _measure_nosqueeze(page):
    _wait_fonts(page)
    return page.evaluate(
        _NOSQUEEZE_JS,
        {"sels": _selectors(), "eps": NOSQUEEZE_MATRIX_EPS},
    )


def _collect_nosqueeze_pages(page, where):
    problems_open = []
    if not _open_menu_or_problem(page, problems_open, where):
        return problems_open, []
    pages = []
    for index in range(6):
        payload = _measure_nosqueeze(page)
        payload["pageIndex"] = index
        pages.append(payload)
        if not _go_next_skill_page(page):
            break
    return [], pages


def _nosqueeze_label(sample):
    if sample["role"] == "title":
        return f"{SEL_SKILL_TITLE} {sample.get('text')!r}"
    if sample["role"] == "page":
        return f"{SEL_PAGE_LABEL} {sample.get('text')!r}"
    selector = SEL_SKILL_DESC if sample["role"] == "desc" else SEL_SKILL_NAME
    skill = sample.get("skill") or "?"
    return f"{skill} {selector}"


def _append_nosqueeze_problems(problems, samples):
    """samples are measured .skill-desc, .skill-name, title, and page label nodes."""
    spacing_bad = []
    transform_bad = []
    stretch_bad = []
    ellipsis_bad = []
    overflow_bad = []
    wrap_bad = []
    glyph_bad = []
    for sample in samples:
        where = sample["where"]
        label = _nosqueeze_label(sample)
        if not sample.get("present"):
            problems.append(f"{where}: {label} missing")
            continue
        letter = sample.get("letterSpacingPx")
        word = sample.get("wordSpacingPx")
        if letter is None or letter < 0 or word is None or word < 0:
            spacing_bad.append(
                f"{where} {label} letter-spacing {sample.get('letterSpacing')!r} "
                f"({_px(letter)}px) word-spacing {sample.get('wordSpacing')!r} "
                f"({_px(word)}px)"
            )
        if not sample.get("reachedPanel"):
            transform_bad.append(f"{where} {label} is not inside {SEL_SKILL_PANEL}")
        else:
            scaled = [row for row in sample.get("transforms") or [] if not row.get("ok")]
            if scaled:
                shown = scaled[0]
                transform_bad.append(
                    f"{where} {label} transform {shown.get('transform')!r} "
                    f"on #{shown.get('id') or shown.get('cls') or 'element'}"
                )
        offset_w = sample.get("offsetW") or 0
        rect_w = sample.get("rectW")
        ratio = None if offset_w <= 0 or rect_w is None else rect_w / offset_w
        if ratio is None or ratio < NOSQUEEZE_WIDTH_RATIO_MIN or ratio > NOSQUEEZE_WIDTH_RATIO_MAX:
            transform_bad.append(
                f"{where} {label} rect/offsetWidth {_px(ratio)} "
                f"(rect {_px(rect_w)} offset {_px(offset_w)}); "
                f"want {NOSQUEEZE_WIDTH_RATIO_MIN}..{NOSQUEEZE_WIDTH_RATIO_MAX}"
            )
        stretch = (sample.get("fontStretch") or "").strip()
        if stretch not in ("100%", "normal"):
            stretch_bad.append(f"{where} {label} font-stretch {stretch!r}")
        if sample["role"] == "desc":
            if sample.get("textOverflow") == "ellipsis":
                ellipsis_bad.append(f"{where} {label}")
            scroll_w = sample.get("scrollWidth")
            client_w = sample.get("clientWidth")
            if client_w is None or client_w <= 0 or scroll_w is None or scroll_w > client_w + 1:
                overflow_bad.append(
                    f"{label} {sample.get('text')!r} scrollWidth {_px(scroll_w)} "
                    f"clientWidth {_px(client_w)}"
                )
            font_px = sample.get("fontPx") or 0
            height = sample.get("height")
            white = sample.get("whiteSpace")
            if (
                white != "nowrap"
                or height is None
                or font_px <= 0
                or height > font_px * SKILL_DESC_LINE_RATIO + 0.5
            ):
                wrap_bad.append(
                    f"{where} {label} white-space {white!r} height {_px(height)}px "
                    f"font {_px(font_px)}px"
                )
        if sample.get("glyphCount"):
            min_ratio = sample.get("minRatio")
            if min_ratio is None or min_ratio < NOSQUEEZE_GLYPH_MIN_RATIO:
                glyph_bad.append(
                    f"{label} min ratio {_px(min_ratio)} "
                    f"(char {sample.get('minChar')!r} width {_px(sample.get('minWidth'))}px "
                    f"/ font {_px(sample.get('fontPx'))}px)"
                )
    if spacing_bad:
        problems.append(
            "check1 letter-spacing/word-spacing < 0: " + " | ".join(spacing_bad)
        )
    if transform_bad:
        problems.append("check2 scaled transform: " + " | ".join(transform_bad))
    if stretch_bad:
        problems.append("check3 font-stretch: " + " | ".join(stretch_bad))
    if ellipsis_bad:
        problems.append(
            "check4 text-overflow ellipsis: " + " | ".join(ellipsis_bad)
        )
    if overflow_bad:
        problems.append(
            f"check4 description overflows on {len(overflow_bad)} skill(s): "
            + " | ".join(overflow_bad)
        )
    if wrap_bad:
        problems.append("check4 description is not a single nowrap line: " + " | ".join(wrap_bad))
    if glyph_bad:
        problems.append(
            f"check5 CJK glyph width < {NOSQUEEZE_GLYPH_MIN_RATIO}em: " + " | ".join(glyph_bad)
        )


def _extend_nosqueeze(samples, where, payload):
    if not payload.get("open"):
        samples.append({
            "where": where,
            "present": False,
            "role": "title",
            "skill": "",
            "text": "",
        })
        return
    for key in ("title", "page"):
        item = dict(payload.get(key) or {"present": False, "role": key, "skill": ""})
        item["where"] = where
        samples.append(item)
    for card in payload.get("cards") or []:
        for key in ("name", "desc"):
            item = dict(card.get(key) or {"present": False, "role": key, "skill": ""})
            item["where"] = where
            samples.append(item)


@pytest.mark.case_id("TC-FE-SKILLMENU-NOSQUEEZE")
def test_tc_fe_skillmenu_nosqueeze(page, base_url, menu_ids):
    """Descriptions, names, the title, and the page label are not squeezed to fit.

    Same kids as TC-FE-SKILLMENU-TYPE / TITLE: 6 skills, page 2 of 8 skills,
    and every page of the 22-skill kid. Font-size floors stay on TYPE.
    """
    case_id = "TC-FE-SKILLMENU-NOSQUEEZE"
    problems = []
    samples = []

    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    open_problems, pages = _collect_nosqueeze_pages(page, "6-skill")
    problems.extend(open_problems)
    if pages:
        _extend_nosqueeze(samples, "6-skill", pages[0])
        if len(pages[0].get("cards") or []) != 6:
            problems.append(f"6-skill page shows {len(pages[0].get('cards') or [])} cards; want 6")
        if pages[0].get("label") != "1 / 1":
            problems.append(f"6-skill page label {pages[0].get('label')!r}; want '1 / 1'")

    _login(page, base_url, MENU_KID8)
    _start_and_show_battle(page, menu_ids[MENU_KID8])
    open_problems, pages = _collect_nosqueeze_pages(page, "8-skill")
    problems.extend(open_problems)
    page2 = next((item for item in pages if item.get("pageIndex") == 1), None)
    if page2 is None:
        problems.append("8-skill kid has no page 2 to measure")
    else:
        _extend_nosqueeze(samples, "8-skill page 2", page2)
        if page2.get("label") != "2 / 2":
            problems.append(f"8-skill page 2 label {page2.get('label')!r}; want '2 / 2'")
        if len(page2.get("cards") or []) != 2:
            problems.append(f"8-skill page 2 shows {len(page2.get('cards') or [])} cards; want 2")

    _login(page, base_url, MENU_KID22)
    started = _start_and_show_battle(page, menu_ids[MENU_KID22])
    open_problems, pages = _collect_nosqueeze_pages(page, "22-skill")
    problems.extend(open_problems)
    seen = []
    for item in pages:
        _extend_nosqueeze(samples, f"22-skill page {item['pageIndex'] + 1}", item)
        for card in item.get("cards") or []:
            name = (card.get("name") or {}).get("skill") or (card.get("name") or {}).get("text")
            if name:
                seen.append(name)
    missing = [name for name in SEEDED_SKILL_NAMES if name not in seen]
    if pages and missing:
        problems.append(
            f"22-skill kid battle skills {[row['name'] for row in started['skills']]}; "
            f"menu never showed {missing}"
        )
    title = next((item for item in samples if item.get("role") == "title" and item.get("present")), None)
    if title and title.get("text") != "技能":
        problems.append(f"title text {title.get('text')!r}; want '技能'")
    _append_nosqueeze_problems(problems, samples)
    _fail(case_id, problems)


def _append_title_problems(problems, payload, where):
    panel = payload.get("panel")
    if not _visible(panel):
        problems.append(f"{where}: {SEL_SKILL_PANEL} is not visible")
        return
    title = payload.get("title")
    label = payload.get("page")
    back = payload.get("back")
    if not _visible(title):
        problems.append(f"{where}: {SEL_SKILL_TITLE} missing")
    else:
        if title["text"] != "技能":
            problems.append(f"{where}: title text {title['text']!r}; want '技能'")
        if title["fontPx"] < SKILL_TITLE_MIN_PX:
            problems.append(
                f"{where}: title font-size {_px(title['fontPx'])}px; want >= {SKILL_TITLE_MIN_PX}px"
            )
    if not _visible(label):
        problems.append(f"{where}: {SEL_PAGE_LABEL} missing")
    else:
        if not re.fullmatch(r"\d+ / \d+", label["text"] or ""):
            problems.append(f"{where}: page label {label['text']!r}; want 'N / M'")
        if label["fontPx"] < PAGE_LABEL_MIN_PX:
            problems.append(
                f"{where}: page label font-size {_px(label['fontPx'])}px; want >= {PAGE_LABEL_MIN_PX}px"
            )
    if not _visible(back):
        problems.append(f"{where}: {SEL_BTN_BACK} missing")
    elif back["w"] < BTN_BACK_MIN_WIDTH_PX or back["h"] < BTN_BACK_MIN_HEIGHT_PX:
        problems.append(
            f"{where}: 返回 { _px(back['w']) }×{ _px(back['h']) }px; "
            f"want >= {BTN_BACK_MIN_WIDTH_PX}×{BTN_BACK_MIN_HEIGHT_PX}"
        )
    for key, node_id, glyph in (
        ("prev", SEL_BTN_PREV, "◀"),
        ("next", SEL_BTN_NEXT, "▶"),
        ("close", SEL_BTN_CLOSE, "✕"),
    ):
        box = payload.get(key)
        if not _visible(box):
            problems.append(f"{where}: {glyph} {node_id} missing")
        elif box["w"] < TITLE_CONTROL_MIN_PX or box["h"] < TITLE_CONTROL_MIN_PX:
            problems.append(
                f"{where}: {glyph} {node_id} {_px(box['w'])}×{_px(box['h'])}px; "
                f"want >= {TITLE_CONTROL_MIN_PX}×{TITLE_CONTROL_MIN_PX}"
            )
    named = [
        ("title", title),
        ("page", label),
        ("back", back),
        ("prev", payload.get("prev")),
        ("next", payload.get("next")),
        ("close", payload.get("close")),
        ("mp", payload.get("mp")),
    ]
    for index, dot in enumerate(payload.get("dots") or []):
        named.append((f"dot{index}", dot))
    visible = [(name, box) for name, box in named if _visible(box)]
    missing_inside = [name for name, box in named if box is None or not _visible(box)]
    if missing_inside:
        problems.append(f"{where}: title-row control missing or not visible: {', '.join(missing_inside)}")
    outside = []
    for name, box in visible:
        if not _inside(box, panel):
            outside.append(
                f"{name} L{_px(box['left'])} T{_px(box['top'])} R{_px(box['right'])} B{_px(box['bottom'])}"
            )
    if outside:
        problems.append(f"{where}: title-row controls outside the panel: " + " | ".join(outside))
    overlaps = []
    for index, (left_name, left_box) in enumerate(visible):
        for right_name, right_box in visible[index + 1 :]:
            area = _intersection_area(left_box, right_box)
            if area and area > 0:
                overlaps.append(f"{left_name}∩{right_name} {_px(area)} px²")
    if overlaps:
        problems.append(f"{where}: title-row controls overlap: " + " | ".join(overlaps))


@pytest.mark.case_id("TC-FE-SKILLMENU-TITLE")
def test_tc_fe_skillmenu_title_row_is_larger(page, base_url, menu_ids):
    """Title, page label, 返回, and the pager buttons are large, inside the panel, and do not overlap."""
    case_id = "TC-FE-SKILLMENU-TITLE"
    problems = []

    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    if _open_menu_or_problem(page, problems, "6-skill"):
        _append_title_problems(problems, _measure_title(page), "6-skill")

    _login(page, base_url, MENU_KID8)
    _start_and_show_battle(page, menu_ids[MENU_KID8])
    if _open_menu_or_problem(page, problems, "8-skill"):
        if not _go_next_skill_page(page):
            problems.append("8-skill: cannot open page 2 for the title row")
        else:
            payload = _measure_title(page)
            label = (payload.get("page") or {}).get("text")
            if label != "2 / 2":
                problems.append(f"8-skill title row is on label {label!r}; want '2 / 2'")
            _append_title_problems(problems, payload, "8-skill page 2")
    _fail(case_id, problems)


def _set_wild_toast(page, message):
    """Paint #wildToast.

    renderBattleMode writes the node from the last turn log while rebuilding the
    battle DOM. townData is a top-level let, so a Playwright script cannot push
    a turn into it, and no function accepts a message and paints #wildToast.
    textContent is applied to the live node. closeSkillMenu calls renderExpedition,
    which replaces the node, so the caller sets the text again after 返回 / ✕.
    """
    _wait_fonts(page)
    return page.evaluate(
        """({message, toastId}) => {
          const toast = document.querySelector(toastId);
          if (!toast) return {ok: false, why: 'missing ' + toastId, path: 'textContent'};
          const writer = typeof renderBattleMode === 'function' ? 'renderBattleMode' : '';
          toast.textContent = message;
          return {
            ok: toast.textContent === message,
            path: 'textContent',
            writer,
            why: writer
              ? 'renderBattleMode rebuilds #wildToast from lastTurn.log; townData is not reachable from page JS'
              : 'renderBattleMode is not defined'
          };
        }""",
        {"message": message, "toastId": SEL_WILD_TOAST},
    )


def _probe_toast_height(page, message):
    """Height of message at TOAST_WRAP_WIDTH_PX with the live toast font and normal wrapping."""
    return page.evaluate(
        """({message, width, toastId}) => {
          const toast = document.querySelector(toastId);
          const cs = toast ? getComputedStyle(toast) : null;
          const probe = document.createElement('div');
          probe.style.position = 'absolute';
          probe.style.left = '-12000px';
          probe.style.top = '0';
          probe.style.width = width + 'px';
          probe.style.boxSizing = 'border-box';
          probe.style.whiteSpace = 'normal';
          probe.style.fontSize = cs ? cs.fontSize : '16px';
          probe.style.fontWeight = cs ? cs.fontWeight : '800';
          probe.style.fontFamily = cs ? cs.fontFamily : 'sans-serif';
          probe.style.lineHeight = cs ? cs.lineHeight : 'normal';
          probe.style.letterSpacing = cs ? cs.letterSpacing : 'normal';
          probe.style.padding = cs ? cs.padding : '0';
          probe.textContent = message;
          document.body.appendChild(probe);
          const height = probe.getBoundingClientRect().height;
          probe.remove();
          return height;
        }""",
        {"message": message, "width": TOAST_WRAP_WIDTH_PX, "toastId": SEL_WILD_TOAST},
    )


def _toast_layout(page):
    return page.evaluate(
        """(sels) => {
          const rect = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return {
              hidden: el.hasAttribute('hidden') || cs.display === 'none' || cs.visibility === 'hidden',
              w: r.width, h: r.height, left: r.left, top: r.top, right: r.right, bottom: r.bottom
            };
          };
          const toast = document.querySelector(sels.toast);
          const cs = toast ? getComputedStyle(toast) : null;
          const panel = document.querySelector(sels.panel);
          const bar = document.querySelector(sels.bar);
          const wood = document.querySelector(sels.wood);
          const vitals = document.querySelector(sels.vitals);
          const enemies = [...document.querySelectorAll(sels.monster)].map((card) => ({
            idx: card.getAttribute('data-idx') || '',
            card: rect(card),
            name: rect(card.querySelector(sels.mName)),
            hpbar: rect(card.querySelector(sels.mHp)),
            hptext: rect(card.querySelector(sels.mHpText))
          }));
          return {
            toast: toast ? {
              text: toast.textContent || '',
              textOverflow: cs.textOverflow,
              whiteSpace: cs.whiteSpace,
              scrollWidth: toast.scrollWidth,
              clientWidth: toast.clientWidth,
              scrollHeight: toast.scrollHeight,
              clientHeight: toast.clientHeight,
              box: rect(toast)
            } : null,
            panel: rect(panel),
            bar: rect(bar),
            wood: rect(wood),
            vitals: rect(vitals),
            enemies
          };
        }""",
        _selectors(),
    )


def _close_skill_menu(page):
    """Click 返回, or ✕ if 返回 is not there. Returns which control was used."""
    back = page.locator(SEL_BTN_BACK)
    if back.count() and back.is_visible():
        back.click()
        return "back"
    close = page.locator(SEL_BTN_CLOSE)
    if close.count() and close.is_visible():
        close.click()
        return "close"
    return ""


def _nowrap(value):
    return value in ("nowrap", "pre")


@pytest.mark.case_id("TC-FE-TOAST-MENU-ONELINE")
@pytest.mark.parametrize("enemy_count", [3, 1], ids=["3-wolves", "1-wolf"])
def test_tc_fe_toast_menu_oneline(page, base_url, menu_ids, enemy_count):
    """With the skill menu open, a wrapping battle message stays one ellipsized line and misses the panel.

    After 返回 or ✕, the same message is fully visible and misses every enemy name and HP node.
    """
    case_id = "TC-FE-TOAST-MENU-ONELINE"
    _login(page, base_url, MENU_KID6)
    started = _start_battle_with_enemy_count(page, menu_ids[MENU_KID6], enemy_count)
    problems = []
    if not _open_menu_or_problem(page, problems, f"{enemy_count} wolves"):
        _fail(f"{case_id} [{enemy_count}]", problems)
        return

    painted = _set_wild_toast(page, TOAST_SHORT_MESSAGE)
    if not painted.get("ok"):
        problems.append(f"could not paint the short message ({painted})")
        _fail(f"{case_id} [{enemy_count}]", problems)
        return
    short_live = _toast_layout(page)
    short_box = (short_live.get("toast") or {}).get("box")
    if not _visible(short_box):
        problems.append(f"short message did not produce a visible {SEL_WILD_TOAST}")
        _fail(f"{case_id} [{enemy_count}]", problems)
        return
    single_h = short_box["h"]
    probe_short = _probe_toast_height(page, TOAST_SHORT_MESSAGE)
    probe_long = _probe_toast_height(page, TOAST_LONG_MESSAGE)
    if not (probe_long > probe_short + TOAST_LINE_TOLERANCE_PX):
        problems.append(
            f"long message does not wrap to 2+ lines at {TOAST_WRAP_WIDTH_PX}px "
            f"(probe short {_px(probe_short)}px, long {_px(probe_long)}px)"
        )

    painted = _set_wild_toast(page, TOAST_LONG_MESSAGE)
    if not painted.get("ok"):
        problems.append(f"could not paint the long message ({painted})")
    long_live = _toast_layout(page)
    toast = long_live.get("toast") or {}
    box = toast.get("box")
    if not _visible(box):
        problems.append(f"long message did not produce a visible {SEL_WILD_TOAST}; rolled {started['names']}")
    else:
        if box["h"] > single_h + TOAST_LINE_TOLERANCE_PX:
            problems.append(
                f"menu open: {SEL_WILD_TOAST} height {_px(box['h'])}px > single-line "
                f"{_px(single_h)}px + {TOAST_LINE_TOLERANCE_PX}px "
                f"(1100px probe short {_px(probe_short)} long {_px(probe_long)}; "
                f"path {painted.get('path')}: {painted.get('why')})"
            )
        ellipsis = toast.get("textOverflow") == "ellipsis"
        clipped = (toast.get("scrollWidth") or 0) > (toast.get("clientWidth") or 0) + 1
        if not ((ellipsis and _nowrap(toast.get("whiteSpace"))) or clipped):
            problems.append(
                f"menu open: text-overflow {toast.get('textOverflow')!r} "
                f"white-space {toast.get('whiteSpace')!r} "
                f"scrollWidth {_px(toast.get('scrollWidth'))} clientWidth {_px(toast.get('clientWidth'))}; "
                "want ellipsis+nowrap or scrollWidth > clientWidth"
            )
        panel = long_live.get("panel")
        if not _visible(panel):
            problems.append(f"menu open: {SEL_SKILL_PANEL} is not visible")
        else:
            area = _intersection_area(box, panel)
            if area is None or area > 0:
                problems.append(
                    f"menu open: {SEL_WILD_TOAST} intersects {SEL_SKILL_PANEL} by {_px(area)} px² "
                    f"(toast T{_px(box['top'])} B{_px(box['bottom'])} L{_px(box['left'])} R{_px(box['right'])}; "
                    f"panel T{_px(panel['top'])} B{_px(panel['bottom'])} "
                    f"L{_px(panel['left'])} R{_px(panel['right'])})"
                )

    how = _close_skill_menu(page)
    if not how:
        problems.append(f"no {SEL_BTN_BACK} or {SEL_BTN_CLOSE} to close the menu")
    else:
        try:
            page.locator(SEL_SKILL_PANEL).wait_for(state="hidden", timeout=3000)
        except Exception:
            problems.append(f"{how} left {SEL_SKILL_PANEL} visible")
        # The close path re-renders the battle and drops the injected text node.
        painted = _set_wild_toast(page, TOAST_LONG_MESSAGE)
        closed = _toast_layout(page)
        toast = closed.get("toast") or {}
        box = toast.get("box")
        if toast.get("text") != TOAST_LONG_MESSAGE:
            problems.append(
                f"menu closed via {how}: toast text {toast.get('text')!r} "
                f"(paint path {painted.get('path')})"
            )
        if not _visible(box):
            problems.append(f"menu closed: {SEL_WILD_TOAST} is not visible")
        else:
            scroll_w = toast.get("scrollWidth") or 0
            client_w = toast.get("clientWidth") or 0
            scroll_h = toast.get("scrollHeight") or 0
            client_h = toast.get("clientHeight") or 0
            if scroll_w > client_w + 1 or scroll_h > client_h + 1:
                problems.append(
                    f"menu closed: message is truncated scroll {_px(scroll_w)}×{_px(scroll_h)} "
                    f"client {_px(client_w)}×{_px(client_h)}"
                )
            for enemy in closed.get("enemies") or []:
                for key, what in (("name", SEL_M_NAME), ("hpbar", SEL_M_HP_BAR), ("hptext", SEL_M_HP_TEXT)):
                    part = enemy.get(key)
                    if not _visible(part):
                        problems.append(f"menu closed: enemy {enemy.get('idx')} {what} is not visible")
                        continue
                    area = _intersection_area(box, part)
                    if area is None or area > 0:
                        problems.append(
                            f"menu closed: {SEL_WILD_TOAST} intersects enemy {enemy.get('idx')} "
                            f"{what} by {_px(area)} px²"
                        )
    _fail(f"{case_id} [{enemy_count}]", problems)


def _shift_amount(before, after, keys):
    deltas = {}
    for key in keys:
        deltas[key] = abs(after[key] - before[key])
    return deltas


@pytest.mark.case_id("TC-FE-TOAST-NO-SHIFT")
@pytest.mark.parametrize("enemy_count", [3, 1], ids=["3-wolves", "1-wolf"])
def test_tc_fe_toast_no_shift(page, base_url, menu_ids, enemy_count):
    """A 2-line battle message must not move monster cards or cover HP text with the command bar.

    #playerVitals stays where it was. The skill menu stays closed.
    """
    case_id = "TC-FE-TOAST-NO-SHIFT"
    _login(page, base_url, MENU_KID6)
    started = _start_battle_with_enemy_count(page, menu_ids[MENU_KID6], enemy_count)
    problems = []
    if _menu_snapshot(page)["open"]:
        problems.append("skill menu started open; this case measures the closed menu")

    probe_short = _probe_toast_height(page, TOAST_SHORT_MESSAGE)
    probe_long = _probe_toast_height(page, TOAST_LONG_MESSAGE)
    if not (probe_long > probe_short + TOAST_LINE_TOLERANCE_PX):
        problems.append(
            f"long message does not wrap to 2+ lines at {TOAST_WRAP_WIDTH_PX}px "
            f"(probe short {_px(probe_short)}px, long {_px(probe_long)}px)"
        )

    painted = _set_wild_toast(page, TOAST_SHORT_MESSAGE)
    if not painted.get("ok"):
        problems.append(f"could not paint the short message ({painted})")
        _fail(f"{case_id} [{enemy_count}]", problems)
        return
    short_layout = _toast_layout(page)
    painted = _set_wild_toast(page, TOAST_LONG_MESSAGE)
    if not painted.get("ok"):
        problems.append(f"could not paint the long message ({painted}); path note {painted}")
    long_layout = _toast_layout(page)

    short_cards = {enemy["idx"]: enemy for enemy in short_layout.get("enemies") or []}
    long_cards = {enemy["idx"]: enemy for enemy in long_layout.get("enemies") or []}
    if len(short_cards) != enemy_count or len(long_cards) != enemy_count:
        problems.append(
            f"monster cards short {list(short_cards)} long {list(long_cards)}; "
            f"want {enemy_count}; rolled {started['names']}"
        )
    for idx, before in short_cards.items():
        after = long_cards.get(idx)
        if not after or not _visible(before.get("card")) or not _visible(after.get("card")):
            problems.append(f"card {idx} missing between the short and long message")
            continue
        deltas = _shift_amount(before["card"], after["card"], ("top", "left"))
        if deltas["top"] > TOAST_SHIFT_TOLERANCE_PX or deltas["left"] > TOAST_SHIFT_TOLERANCE_PX:
            problems.append(
                f"card {idx} moved top {_px(before['card']['top'])} -> {_px(after['card']['top'])} "
                f"(Δ{_px(deltas['top'])}px) left {_px(before['card']['left'])} -> {_px(after['card']['left'])} "
                f"(Δ{_px(deltas['left'])}px); want <= {TOAST_SHIFT_TOLERANCE_PX}px"
            )
    for state, layout in (("short", short_layout), ("long", long_layout)):
        # The wood strip is the bar HP text runs into. The inner .command-bar
        # sits lower, inside the strip's padding, so check both boxes.
        bars = [(SEL_BATTLE_BAR, layout.get("wood")), (SEL_COMMAND_BAR, layout.get("bar"))]
        if not _visible(layout.get("wood")):
            problems.append(f"{state} message: no visible {SEL_BATTLE_BAR}")
        for selector, bar in bars:
            if not _visible(bar):
                continue
            for enemy in layout.get("enemies") or []:
                hp_text = enemy.get("hptext")
                if not _visible(hp_text):
                    problems.append(f"{state} message: card {enemy.get('idx')} {SEL_M_HP_TEXT} is not visible")
                    continue
                area = _intersection_area(hp_text, bar)
                if area is None or area > 0:
                    problems.append(
                        f"{state} message: card {enemy.get('idx')} {SEL_M_HP_TEXT} intersects "
                        f"{selector} by {_px(area)} px²"
                    )
    before_vitals = short_layout.get("vitals")
    after_vitals = long_layout.get("vitals")
    if not _visible(before_vitals) or not _visible(after_vitals):
        problems.append(f"{SEL_PLAYER_VITALS} missing or hidden, so it is not unaffected")
    else:
        deltas = _shift_amount(before_vitals, after_vitals, ("top", "left", "w", "h"))
        moved = {key: value for key, value in deltas.items() if value > TOAST_SHIFT_TOLERANCE_PX}
        if moved:
            problems.append(
                f"{SEL_PLAYER_VITALS} moved { {key: _px(value) for key, value in moved.items()} }px "
                f"between the short and long message"
            )
    _fail(f"{case_id} [{enemy_count}]", problems)


@pytest.mark.case_id("TC-FE-SKILLMENU-PANEL-RECT")
def test_tc_fe_skillmenu_panel_rect_guard(page, base_url, menu_ids):
    """#skillPanel keeps the ee8a3eb box. TC-FE-SKILLMENU-ENEMY-VISIBLE is unchanged."""
    case_id = "TC-FE-SKILLMENU-PANEL-RECT"
    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    problems = []
    if not _open_menu_or_problem(page, problems, "panel rect"):
        _fail(case_id, problems)
        return
    layout = page.evaluate(_LAYOUT_JS)
    panel = layout.get("panel")
    if not panel or panel.get("hidden"):
        problems.append(f"{SEL_SKILL_PANEL} is not visible")
    else:
        for edge, expected in SKILL_PANEL_RECT.items():
            actual = panel[{"left": "left", "top": "top", "right": "right", "bottom": "bottom"}[edge]]
            if abs(actual - expected) > SKILL_PANEL_RECT_TOLERANCE_PX:
                problems.append(
                    f"{SEL_SKILL_PANEL} {edge} {_px(actual)}px; "
                    f"want { _px(expected) }±{SKILL_PANEL_RECT_TOLERANCE_PX}"
                )
    _fail(case_id, problems)


# Inner line of the wooden #skillPanel. See the comment on
# SKILL_FRAME_CLEARANCE_MIN_PX: border-width plus the furthest inset
# box-shadow reach on each side. A generated ::before/::after tightens it.
_INSET_JS = r"""
() => {
  function splitShadows(css) {
    const text = css || 'none';
    if (!text || text === 'none') return [];
    const parts = [];
    let depth = 0;
    let start = 0;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (ch === '(') depth++;
      else if (ch === ')') depth--;
      else if (ch === ',' && depth === 0) {
        parts.push(text.slice(start, i).trim());
        start = i + 1;
      }
    }
    parts.push(text.slice(start).trim());
    return parts.filter(Boolean);
  }
  function parseShadow(part) {
    const inset = /\binset\b/.test(part);
    const stripped = part.replace(/\([^)]*\)/g, ' ').replace(/\binset\b/g, ' ');
    const nums = [...stripped.matchAll(/(-?[\d.]+)px/g)].map((m) => parseFloat(m[1]));
    const [ox = 0, oy = 0, blur = 0, spread = 0] = nums;
    return { inset, ox, oy, blur, spread };
  }
  function insetReach(cssText) {
    const reach = { left: 0, right: 0, top: 0, bottom: 0 };
    const shadows = [];
    for (const part of splitShadows(cssText)) {
      const sh = parseShadow(part);
      shadows.push(sh);
      if (!sh.inset) continue;
      reach.left = Math.max(reach.left, sh.spread + sh.ox);
      reach.right = Math.max(reach.right, sh.spread - sh.ox);
      reach.top = Math.max(reach.top, sh.spread + sh.oy);
      reach.bottom = Math.max(reach.bottom, sh.spread - sh.oy);
    }
    return { reach, shadows };
  }
  function px(value) {
    if (value == null || value === 'auto') return null;
    const n = parseFloat(value);
    return Number.isFinite(n) ? n : null;
  }
  function tracks(value) {
    if (!value || value === 'none') return [];
    return value.trim().split(/\s+/).filter(Boolean);
  }
  function boxOf(el) {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, w: r.width, h: r.height };
  }
  function clearance(box, inner) {
    if (!box) return null;
    return {
      left: box.left - inner.left,
      top: box.top - inner.top,
      right: inner.right - box.right,
      bottom: inner.bottom - box.bottom
    };
  }
  const panel = document.getElementById('skillPanel');
  if (!panel) return { open: false, why: 'missing #skillPanel' };
  const cs = getComputedStyle(panel);
  const open = !panel.hidden && cs.display !== 'none' && cs.visibility !== 'hidden';
  const pr = panel.getBoundingClientRect();
  const border = {
    left: parseFloat(cs.borderLeftWidth) || 0,
    right: parseFloat(cs.borderRightWidth) || 0,
    top: parseFloat(cs.borderTopWidth) || 0,
    bottom: parseFloat(cs.borderBottomWidth) || 0
  };
  const parsed = insetReach(cs.boxShadow);
  const reach = parsed.reach;
  const inner = {
    left: pr.left + border.left + reach.left,
    right: pr.right - border.right - reach.right,
    top: pr.top + border.top + reach.top,
    bottom: pr.bottom - border.bottom - reach.bottom
  };
  const pseudos = [];
  for (const name of ['::before', '::after']) {
    const pcs = getComputedStyle(panel, name);
    const content = pcs.content || 'none';
    const generated = content !== 'none' && content !== 'normal';
    const positioned = pcs.position === 'absolute' || pcs.position === 'fixed';
    const info = { name, content, position: pcs.position, generated, positioned, tightened: false };
    if (generated && positioned) {
      const top = px(pcs.top);
      const right = px(pcs.right);
      const bottom = px(pcs.bottom);
      const left = px(pcs.left);
      if (top != null && right != null && bottom != null && left != null) {
        const pre = insetReach(pcs.boxShadow).reach;
        const pb = {
          left: parseFloat(pcs.borderLeftWidth) || 0,
          right: parseFloat(pcs.borderRightWidth) || 0,
          top: parseFloat(pcs.borderTopWidth) || 0,
          bottom: parseFloat(pcs.borderBottomWidth) || 0
        };
        const pseudoInner = {
          left: pr.left + left + pb.left + pre.left,
          right: pr.right - right - pb.right - pre.right,
          top: pr.top + top + pb.top + pre.top,
          bottom: pr.bottom - bottom - pb.bottom - pre.bottom
        };
        inner.left = Math.max(inner.left, pseudoInner.left);
        inner.right = Math.min(inner.right, pseudoInner.right);
        inner.top = Math.max(inner.top, pseudoInner.top);
        inner.bottom = Math.min(inner.bottom, pseudoInner.bottom);
        info.tightened = true;
      }
    }
    pseudos.push(info);
  }
  const named = [
    ['#skillTitle', document.getElementById('skillTitle')],
    ['#mpNow', document.getElementById('mpNow')],
    ['#btnPrev', document.getElementById('btnPrev')],
    ['#pageLabel', document.getElementById('pageLabel')],
    ['#btnBack', document.getElementById('btnBack')],
    ['#btnClose', document.getElementById('btnClose')]
  ];
  const chrome = named.map(([name, el]) => {
    const box = boxOf(el);
    return { name, text: el ? (el.textContent || '').trim() : '', box, clearance: clearance(box, inner) };
  });
  const dots = [...document.querySelectorAll('#pageDots .dot')].map((el, index) => {
    const box = boxOf(el);
    return { name: '#pageDots .dot[' + index + ']', box, clearance: clearance(box, inner) };
  });
  const grid = document.getElementById('skillGrid');
  const gcs = grid ? getComputedStyle(grid) : null;
  const cards = [...document.querySelectorAll('#skillGrid .skill-card')].map((el) => {
    const box = boxOf(el);
    const nameEl = el.querySelector('.skill-name');
    return {
      name: nameEl ? (nameEl.textContent || '').trim() : '?',
      box,
      clearance: clearance(box, inner)
    };
  });
  return {
    open,
    paddingLeft: parseFloat(cs.paddingLeft) || 0,
    paddingRight: parseFloat(cs.paddingRight) || 0,
    paddingTop: parseFloat(cs.paddingTop) || 0,
    paddingBottom: parseFloat(cs.paddingBottom) || 0,
    border,
    reach,
    inner,
    panel: { left: pr.left, top: pr.top, right: pr.right, bottom: pr.bottom, w: pr.width, h: pr.height },
    pseudos,
    chrome,
    dots,
    cards,
    columns: gcs ? tracks(gcs.gridTemplateColumns) : [],
    rows: gcs ? tracks(gcs.gridTemplateRows) : []
  };
}
"""

_ICON_JS = r"""
() => {
  function boxOf(el) {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, w: r.width, h: r.height };
  }
  function glyphOf(icon) {
    const node = [...icon.childNodes].find((n) => n.nodeType === Node.TEXT_NODE && (n.textContent || '').trim());
    if (!node) return null;
    const range = document.createRange();
    range.selectNodeContents(node);
    const list = [...range.getClientRects()];
    if (!list.length) return null;
    const left = Math.min(...list.map((r) => r.left));
    const top = Math.min(...list.map((r) => r.top));
    const right = Math.max(...list.map((r) => r.right));
    const bottom = Math.max(...list.map((r) => r.bottom));
    return { left, top, right, bottom, w: right - left, h: bottom - top };
  }
  const label = document.getElementById('pageLabel');
  const cards = [...document.querySelectorAll('#skillGrid .skill-card')].map((card) => {
    const icon = card.querySelector('.skill-icon');
    const name = card.querySelector('.skill-name');
    const desc = card.querySelector('.skill-desc');
    const iconCs = icon ? getComputedStyle(icon) : null;
    return {
      name: name ? (name.textContent || '').trim() : '',
      icon: boxOf(icon),
      glyph: icon ? glyphOf(icon) : null,
      nameBox: boxOf(name),
      descBox: boxOf(desc),
      fontPx: iconCs ? parseFloat(iconCs.fontSize) : null,
      card: boxOf(card)
    };
  });
  return { label: label ? (label.textContent || '').trim() : '', cards };
}
"""

_DOTS_JS = r"""
() => {
  function boxOf(el) {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, w: r.width, h: r.height };
  }
  function holdsPager(el) {
    return !!(el && el.querySelector && (el.querySelector('#btnPrev') || el.querySelector('#btnNext')));
  }
  const labelEl = document.getElementById('pageLabel');
  const prev = document.getElementById('btnPrev');
  const next = document.getElementById('btnNext');
  const dots = [...document.querySelectorAll('#pageDots .dot')].map((el, index) => {
    const box = boxOf(el);
    const chain = [];
    let node = el;
    while (node && node.id !== 'skillPanel') {
      const holds = holdsPager(node);
      chain.push({
        id: node.id || '',
        cls: String(node.className || ''),
        pe: getComputedStyle(node).pointerEvents,
        holds
      });
      if (holds) break;
      node = node.parentElement;
    }
    const center = box ? { x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2 } : null;
    let hit = null;
    if (center) {
      const target = document.elementFromPoint(center.x, center.y);
      hit = {
        tag: target ? target.tagName : '',
        id: target && target.id ? target.id : '',
        cls: target && target.className ? String(target.className) : '',
        isDot: !!(target && target.closest && target.closest('.dot'))
      };
    }
    return { index, current: el.getAttribute('aria-current'), box, chain, center, hit };
  });
  return {
    label: labelEl ? (labelEl.textContent || '').trim() : '',
    prev: boxOf(prev),
    next: boxOf(next),
    nextDisabled: next ? next.getAttribute('aria-disabled') : null,
    prevDisabled: prev ? prev.getAttribute('aria-disabled') : null,
    dots
  };
}
"""


def _pseudo_summary(pseudos):
    generated = [item for item in pseudos or [] if item.get("generated")]
    if not generated:
        return "no ::before/::after"
    parts = []
    for item in generated:
        flag = "tightened the inner line" if item.get("tightened") else "not tightened"
        parts.append(f"{item['name']} content {item.get('content')!r} {item.get('position')} {flag}")
    return "; ".join(parts)


def _bad_clearance(clearance, floor):
    if not clearance:
        return (("missing", None),)
    return tuple(
        (side, clearance[side])
        for side in ("left", "top", "right", "bottom")
        if clearance[side] + 1e-3 < floor
    )


def _group_clearance(items, floor):
    """Group controls that miss the frame by the same sides."""
    groups = []
    index = {}
    for item in items:
        bad = _bad_clearance(item.get("clearance"), floor)
        if not bad:
            continue
        if bad not in index:
            index[bad] = []
            groups.append((bad, index[bad]))
        index[bad].append(item.get("name") or "?")
    lines = []
    for bad, names in groups:
        if bad == (("missing", None),):
            lines.append(", ".join(names) + ": missing box")
            continue
        shown = ", ".join(f"{side} {_px(value)}" for side, value in bad)
        lines.append(", ".join(names) + ": " + shown)
    return lines


def _frame_line(payload):
    border = payload.get("border") or {}
    reach = payload.get("reach") or {}
    inner = payload.get("inner") or {}
    panel = payload.get("panel") or {}
    return (
        "frame inner line = border box "
        f"L{_px(panel.get('left'))} T{_px(panel.get('top'))} "
        f"R{_px(panel.get('right'))} B{_px(panel.get('bottom'))} "
        "inset by border "
        f"L{_px(border.get('left'))} R{_px(border.get('right'))} "
        f"T{_px(border.get('top'))} B{_px(border.get('bottom'))} "
        "+ inset-shadow reach "
        f"L{_px(reach.get('left'))} R{_px(reach.get('right'))} "
        f"T{_px(reach.get('top'))} B{_px(reach.get('bottom'))} "
        f"({_pseudo_summary(payload.get('pseudos'))}): "
        f"L{_px(inner.get('left'))} T{_px(inner.get('top'))} "
        f"R{_px(inner.get('right'))} B{_px(inner.get('bottom'))}"
    )


def _read_skill_pages(page, problems, where, expected_pages, measure):
    if not _open_menu_or_problem(page, problems, where):
        return []
    pages = []
    for _ in range(8):
        pages.append(measure(page))
        if len(pages) >= expected_pages:
            break
        if not _go_next_skill_page(page):
            break
    if len(pages) != expected_pages:
        label = pages[-1].get("label") if pages else ""
        problems.append(
            f"{where}: measured {len(pages)} skill page(s) {label!r}; want {expected_pages}"
        )
    return pages


def _append_inset_problems(problems, screens):
    """screens is (where, payload). The frame sentence is included only on failure."""
    start = len(problems)
    live = []
    for where, payload in screens:
        if not payload or not payload.get("open"):
            problems.append(f"{where}: {SEL_SKILL_PANEL} is not open ({(payload or {}).get('why')})")
            continue
        live.append((where, payload))
    if not live:
        return
    pad_bad = [
        (where, payload["paddingLeft"], payload["paddingRight"])
        for where, payload in live
        if payload["paddingLeft"] + 1e-3 < SKILL_PANEL_PAD_INLINE_MIN_PX
        or payload["paddingRight"] + 1e-3 < SKILL_PANEL_PAD_INLINE_MIN_PX
    ]
    if pad_bad:
        shown = "; ".join(
            f"{where} padding-left {_px(left)}px padding-right {_px(right)}px"
            for where, left, right in pad_bad
        )
        problems.append(f"{shown}; want >= {SKILL_PANEL_PAD_INLINE_MIN_PX}px")
    frame_notes = []
    seen_frames = set()
    widths = []
    for where, payload in live:
        inner = payload.get("inner") or {}
        key = tuple(round(inner.get(side) or 0, 3) for side in ("left", "top", "right", "bottom"))
        if key not in seen_frames:
            seen_frames.add(key)
            frame_notes.append(f"{where}: {_frame_line(payload)}")
        columns = payload.get("columns") or []
        rows = payload.get("rows") or []
        if len(columns) != 2 or len(rows) != 3:
            problems.append(
                f"{where}: grid columns {columns or 'none'} rows {rows or 'none'}; want 2 columns x 3 rows"
            )
        cards = payload.get("cards") or []
        for index, card in enumerate(cards):
            box = card.get("box")
            if not box or box["h"] + 1e-3 < SKILL_CARD_MIN_HEIGHT_PX:
                problems.append(
                    f"{where}: {card.get('name') or '?'} height {_px((box or {}).get('h'))}px; "
                    f"want >= {SKILL_CARD_MIN_HEIGHT_PX}px"
                )
            if box:
                widths.append(box["w"])
            for later in cards[index + 1 :]:
                area = _intersection_area(box, later.get("box"))
                if area and area > 0.5:
                    problems.append(
                        f"{where}: {card.get('name')} overlaps {later.get('name')} by {_px(area)} px²"
                    )
        items = list(payload.get("chrome") or []) + list(payload.get("dots") or []) + [
            {"name": card.get("name") or "card", "clearance": card.get("clearance")} for card in cards
        ]
        grouped = _group_clearance(items, SKILL_FRAME_CLEARANCE_MIN_PX)
        if grouped:
            problems.append(
                f"{where}: closer than {SKILL_FRAME_CLEARANCE_MIN_PX}px to the frame inner line: "
                + " | ".join(grouped)
            )
    if widths and any(value > SKILL_CARD_WIDTH_MAX_PX + 0.01 for value in widths):
        problems.append(
            f"card width {_px_set(widths)}px; want <= {SKILL_CARD_WIDTH_MAX_PX}"
        )
    elif widths and len(problems) > start:
        problems.append(f"card width {_px_set(widths)}px (informational)")
    if frame_notes and len(problems) > start:
        for offset, note in enumerate(frame_notes):
            problems.insert(start + offset, note)


def _measure_inset(page):
    _wait_fonts(page)
    return page.evaluate(_INSET_JS)


@pytest.mark.case_id("TC-FE-SKILLMENU-INSET")
def test_tc_fe_skillmenu_inset(page, base_url, menu_ids):
    """Panel side padding stays at least 12px, and content stays 4px inside the wood.

    The inner line is the border box inset by border-width plus the furthest
    inset box-shadow reach. At 8ac7b0d that is an 8px border plus a 6px spread,
    and the panel has no ::before or ::after.
    """
    case_id = "TC-FE-SKILLMENU-INSET"
    problems = []
    screens = []

    _login(page, base_url, MENU_KID6)
    _start_and_show_battle(page, menu_ids[MENU_KID6])
    for index, payload in enumerate(_read_skill_pages(page, problems, "6-skill", 1, _measure_inset)):
        screens.append(("6-skill" if index == 0 else f"6-skill page {index + 1}", payload))

    _login(page, base_url, MENU_KID8)
    _start_and_show_battle(page, menu_ids[MENU_KID8])
    for index, payload in enumerate(_read_skill_pages(page, problems, "8-skill", 2, _measure_inset)):
        screens.append((f"8-skill page {index + 1}", payload))

    _login(page, base_url, MENU_KID22)
    _start_and_show_battle(page, menu_ids[MENU_KID22])
    for index, payload in enumerate(_read_skill_pages(page, problems, "22-skill", 4, _measure_inset)):
        screens.append((f"22-skill page {index + 1}", payload))

    _append_inset_problems(problems, screens)
    _fail(case_id, problems)


def _rects_overlap(left, right, tol):
    if not left or not right:
        return None
    overlap_x = min(left["right"], right["right"]) - max(left["left"], right["left"])
    overlap_y = min(left["bottom"], right["bottom"]) - max(left["top"], right["top"])
    if overlap_x > tol and overlap_y > tol:
        return overlap_x, overlap_y
    return None


def _append_icon_problems(problems, pages):
    cards = []
    for where, payload in pages:
        for card in (payload or {}).get("cards") or []:
            item = dict(card)
            item["where"] = where
            cards.append(item)
    if not cards:
        problems.append(f"no {SEL_SKILL_ICON} to measure")
        return
    seen = [card["name"] for card in cards if card.get("name")]
    missing = [name for name in SEEDED_SKILL_NAMES if name not in seen]
    if missing:
        problems.append(f"menu never showed {missing}")

    font_bad = [
        card for card in cards
        if card.get("fontPx") is None or card["fontPx"] + 1e-3 < SKILL_ICON_FONT_MIN_PX
    ]
    if font_bad:
        problems.append(
            f".skill-icon font-size {_px_set(card.get('fontPx') for card in font_bad)}px "
            f"on {len(font_bad)}/{len(cards)}; want >= {SKILL_ICON_FONT_MIN_PX}px"
        )
    width_bad = [
        card for card in cards
        if not card.get("icon") or card["icon"]["w"] + 1e-3 < SKILL_ICON_BOX_WIDTH_MIN_PX
    ]
    if width_bad:
        problems.append(
            f".skill-icon box width {_px_set((card.get('icon') or {}).get('w') for card in width_bad)}px "
            f"height {_px_set((card.get('icon') or {}).get('h') for card in width_bad)}px "
            f"on {len(width_bad)}/{len(cards)}; want width >= {SKILL_ICON_BOX_WIDTH_MIN_PX}px"
        )

    outside_box = []
    outside_card = []
    gap_bad = []
    overlap_bad = []
    missing_glyph = []
    for card in cards:
        label = card.get("name") or "?"
        glyph = card.get("glyph")
        icon = card.get("icon")
        name_box = card.get("nameBox")
        desc_box = card.get("descBox")
        card_box = card.get("card")
        if not glyph or not icon:
            missing_glyph.append(label)
            continue
        # Horizontal containment only. Emoji ink taller than the box is a font
        # metric and is not a failure by itself.
        if (
            glyph["left"] < icon["left"] - SKILL_GLYPH_EDGE_TOLERANCE_PX
            or glyph["right"] > icon["right"] + SKILL_GLYPH_EDGE_TOLERANCE_PX
        ):
            outside_box.append(
                f"{label} glyph {_px(glyph['w'])}×{_px(glyph['h'])} "
                f"box {_px(icon['w'])}×{_px(icon['h'])} "
                f"inset L{_px(glyph['left'] - icon['left'])} R{_px(icon['right'] - glyph['right'])}"
            )
        if card_box and (
            glyph["left"] < card_box["left"] - SKILL_GLYPH_EDGE_TOLERANCE_PX
            or glyph["top"] < card_box["top"] - SKILL_GLYPH_EDGE_TOLERANCE_PX
            or glyph["right"] > card_box["right"] + SKILL_GLYPH_EDGE_TOLERANCE_PX
            or glyph["bottom"] > card_box["bottom"] + SKILL_GLYPH_EDGE_TOLERANCE_PX
        ):
            outside_card.append(
                f"{label} L{_px(glyph['left'] - card_box['left'])} T{_px(glyph['top'] - card_box['top'])} "
                f"R{_px(card_box['right'] - glyph['right'])} B{_px(card_box['bottom'] - glyph['bottom'])}"
            )
        if name_box:
            gap_box = name_box["left"] - icon["right"]
            gap_glyph = name_box["left"] - glyph["right"]
            if (
                gap_box + 1e-3 < SKILL_ICON_NAME_GAP_MIN_PX
                or gap_glyph + 1e-3 < SKILL_ICON_NAME_GAP_MIN_PX
            ):
                gap_bad.append(f"{label} box-gap {_px(gap_box)} glyph-gap {_px(gap_glyph)}")
        else:
            gap_bad.append(f"{label} missing .skill-name")
        for other, what in ((name_box, SEL_SKILL_NAME), (desc_box, SEL_SKILL_DESC)):
            hit = _rects_overlap(glyph, other, SKILL_GLYPH_EDGE_TOLERANCE_PX)
            if hit:
                overlap_bad.append(f"{label} ∩ {what} x {_px(hit[0])} y {_px(hit[1])}")
    if missing_glyph:
        problems.append("icon glyph missing: " + ", ".join(missing_glyph))

    def _show(rows):
        shown = rows[:4]
        extra = f" (+{len(rows) - len(shown)} more)" if len(rows) > len(shown) else ""
        return " | ".join(shown) + extra

    if outside_box:
        problems.append(
            "glyph not horizontally inside .skill-icon "
            f"(tolerance {SKILL_GLYPH_EDGE_TOLERANCE_PX}px; vertical overflow of the box is allowed): "
            + _show(outside_box)
        )
    if outside_card:
        problems.append("glyph outside the card: " + _show(outside_card))
    if gap_bad:
        problems.append(
            f"gap from icon box/glyph to .skill-name < {SKILL_ICON_NAME_GAP_MIN_PX}px: " + _show(gap_bad)
        )
    if overlap_bad:
        problems.append("glyph overlaps skill text: " + _show(overlap_bad))


def _measure_icons(page):
    _wait_fonts(page)
    return page.evaluate(_ICON_JS)


@pytest.mark.case_id("TC-FE-SKILLMENU-ICON")
def test_tc_fe_skillmenu_icon(page, base_url, menu_ids):
    """Emoji ink stays in the 36px icon box horizontally, 6px from the skill name.

    The glyph may be taller than the box because of font metrics. It still has
    to stay inside the card and clear of .skill-name and .skill-desc.
    """
    case_id = "TC-FE-SKILLMENU-ICON"
    problems = []
    _login(page, base_url, MENU_KID22)
    _start_and_show_battle(page, menu_ids[MENU_KID22])
    pages = []
    for index, payload in enumerate(_read_skill_pages(page, problems, "22-skill", 4, _measure_icons)):
        pages.append((f"22-skill page {index + 1}", payload))
    _append_icon_problems(problems, pages)
    _fail(case_id, problems)


def _page_fraction(label):
    match = re.fullmatch(r"(\d+) / (\d+)", label or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _measure_dots(page):
    _wait_fonts(page)
    return page.evaluate(_DOTS_JS)


def _append_dot_chrome_problems(problems, state, where, expected_pages):
    label = state.get("label") or ""
    fraction = _page_fraction(label)
    if fraction is None:
        problems.append(f"{where}: #pageLabel {label!r}; want 'N / {expected_pages}'")
        page_no = None
        total = None
    else:
        page_no, total = fraction
        if total != expected_pages:
            problems.append(f"{where}: #pageLabel {label!r}; want {expected_pages} pages")
    dots = state.get("dots") or []
    if total is not None and len(dots) != total:
        problems.append(f"{where} {label}: {len(dots)} dots; want {total}")
    if page_no is not None:
        currents = [dot["index"] for dot in dots if dot.get("current") == "page"]
        if currents != [page_no - 1]:
            problems.append(f"{where} {label}: active dot {currents}; want [{page_no - 1}]")
    offenders = []
    hits = []
    for dot in dots:
        for entry in dot.get("chain") or []:
            if entry.get("holds"):
                continue
            if entry.get("pe") != "none":
                who = entry.get("id") or entry.get("cls") or "dot"
                offenders.append((who, entry.get("pe")))
        hit = dot.get("hit") or {}
        if hit.get("isDot"):
            hits.append(f"dot{dot['index']} -> {hit.get('tag')}.{hit.get('cls')}")
    if offenders:
        shown = ", ".join(f"{name} {value!r}" for name, value in sorted(set(offenders)))
        problems.append(
            f"{where} {label}: pointer-events {shown}; want 'none' on each dot "
            "and on a container that does not hold ◀ ▶"
        )
    if hits:
        problems.append(f"{where} {label}: elementFromPoint hit a dot: " + ", ".join(hits))
    for key, glyph in (("prev", "◀"), ("next", "▶")):
        box = state.get(key)
        if not box or box["w"] + 1e-3 < TITLE_CONTROL_MIN_PX or box["h"] + 1e-3 < TITLE_CONTROL_MIN_PX:
            problems.append(
                f"{where} {label}: {glyph} {_px((box or {}).get('w'))}×{_px((box or {}).get('h'))}px; "
                f"want >= {TITLE_CONTROL_MIN_PX}×{TITLE_CONTROL_MIN_PX}"
            )


def _return_to_label(page, label):
    for _ in range(6):
        current = page.locator(SEL_PAGE_LABEL).inner_text().strip()
        if current == label:
            return
        now = _page_fraction(current)
        want = _page_fraction(label)
        if now and want and now[0] > want[0]:
            prev = page.locator(SEL_BTN_PREV)
            if prev.count() and prev.get_attribute("aria-disabled") != "true":
                prev.click()
                continue
        nxt = page.locator(SEL_BTN_NEXT)
        if nxt.count() and nxt.get_attribute("aria-disabled") != "true":
            nxt.click()
            continue
        return


def _dot_clicks_do_not_turn(page, problems, where):
    """Real mouse clicks at dot centers. A locator click would ignore pointer-events."""
    state = _measure_dots(page)
    label = state.get("label") or ""
    clicks = []
    for dot in state.get("dots") or []:
        center = dot.get("center")
        if not center:
            problems.append(f"{where} {label}: dot{dot['index']} has no center to click")
            continue
        page.mouse.click(center["x"], center["y"])
        after = page.locator(SEL_PAGE_LABEL).inner_text().strip()
        if after != label:
            clicks.append(
                f"dot{dot['index']} ({_px(center['x'])},{_px(center['y'])}) {label!r} -> {after!r}"
            )
            _return_to_label(page, label)
    if clicks:
        problems.append(f"{where}: mouse click at a dot center changed #pageLabel: " + "; ".join(clicks))


def _walk_skill_pages(page, problems, where, expected_pages):
    forward = []
    for _ in range(expected_pages + 2):
        state = _measure_dots(page)
        forward.append(state.get("label") or "")
        _append_dot_chrome_problems(problems, state, where, expected_pages)
        if state.get("nextDisabled") == "true":
            break
        nxt = page.locator(SEL_BTN_NEXT)
        if nxt.count() == 0:
            problems.append(f"{where}: no {SEL_BTN_NEXT}")
            break
        nxt.click()
    want_forward = [f"{index} / {expected_pages}" for index in range(1, expected_pages + 1)]
    if forward != want_forward:
        problems.append(f"{where}: ▶ walk {forward}; want {want_forward}")
    back = []
    for _ in range(expected_pages):
        prev = page.locator(SEL_BTN_PREV)
        if prev.count() == 0 or prev.get_attribute("aria-disabled") == "true":
            break
        prev.click()
        back.append(page.locator(SEL_PAGE_LABEL).inner_text().strip())
    want_back = [f"{index} / {expected_pages}" for index in range(expected_pages - 1, 0, -1)]
    if back != want_back:
        problems.append(f"{where}: ◀ walk {back}; want {want_back}")


def _go_last_skill_page(page):
    for _ in range(6):
        nxt = page.locator(SEL_BTN_NEXT)
        if nxt.count() == 0 or nxt.get_attribute("aria-disabled") == "true":
            return
        nxt.click()


@pytest.mark.case_id("TC-FE-SKILLMENU-DOTS")
def test_tc_fe_skillmenu_dots_are_indicator_only(page, base_url, menu_ids):
    """Page dots do not receive clicks. ◀ and ▶ still turn every page.

    13 learned skills are 3 pages. 22 learned skills are 4 pages. Dot size is
    not asserted: three or more dots may stay 26px wide.
    """
    case_id = "TC-FE-SKILLMENU-DOTS"
    problems = []

    _login(page, base_url, MENU_KID13)
    _start_and_show_battle(page, menu_ids[MENU_KID13])
    if _open_menu_or_problem(page, problems, "13-skill"):
        _walk_skill_pages(page, problems, "13-skill", 3)
        _dot_clicks_do_not_turn(page, problems, "13-skill page 1")
        _go_last_skill_page(page)
        _dot_clicks_do_not_turn(page, problems, "13-skill last page")

    _login(page, base_url, MENU_KID22)
    _start_and_show_battle(page, menu_ids[MENU_KID22])
    if _open_menu_or_problem(page, problems, "22-skill"):
        _walk_skill_pages(page, problems, "22-skill", 4)
        _dot_clicks_do_not_turn(page, problems, "22-skill page 1")
        _go_last_skill_page(page)
        _dot_clicks_do_not_turn(page, problems, "22-skill last page")

    _fail(case_id, problems)
