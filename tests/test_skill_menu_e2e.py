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
    SKILL_MENU_PAGE_SIZE,
    colloquial_hits,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENU_KID6 = "test_menu_kid6"
MENU_KID8 = "test_menu_kid8"
STAGE_W = 1280
STAGE_H = 720
# Known page error on current main. Recorded, not asserted.
KNOWN_PAGEERROR = "buildingImage is not defined"

# Buildings that teach exactly these skills at the given levels.
# Guild Lv1 teaches nothing (偵察 needs Lv2) but battle-start requires it.
_SIX = (
    ("探險公會", 1),
    ("健身室", 4),  # 蓄力 重擊 連擊 鍛鍊的成果
    ("農場", 1),  # 營養餐
    ("商店", 1),  # 金幣袋
)
_EIGHT = _SIX + (("圖書館", 2),)  # 火球 知識的力量


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
    assert len(learned6) == 6, [row["name"] for row in learned6]
    assert len(learned8) == 8, [row["name"] for row in learned8]
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
