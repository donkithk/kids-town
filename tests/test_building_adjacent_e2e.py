"""TC-FE-BUILD-ADJACENT-02 — scene 2 gold and toasts for a shared edge.

Playwright against a temp DB. Does not open kids_town.db.
Uses system Chrome when Playwright's downloaded Chromium is absent.
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
    connect_db,
    get_kid_points,
    grant_inventory,
    init_empty_db,
    insert_building,
    insert_kid,
    inventory_map,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KID_USERNAME = "test_adjacent_kid"
KID_NAME = "Adjacent Kid"
OCCUPIED_TOAST = "這個位置已經有建築物。"
UNFIT_TOAST = "這個位置放不下這座建築物。"
SCENE3_OCCUPIED_TOAST = "這裏已有「健身室」，不能放置。"
PLACED_TOAST = "起好「醫院」。"
INFO_BG = "rgb(107, 79, 42)"
INFO_FG = "rgb(255, 248, 231)"
SUCCESS_BG = "rgb(21, 128, 61)"


def _launch_browser(playwright):
    """Bundled Chromium first (CI), then the system Chrome channel."""
    args = ["--no-sandbox", "--disable-dev-shm-usage"]
    errors = []
    for kwargs in ({"headless": True, "args": args}, {"channel": "chrome", "headless": True, "args": args}):
        try:
            return playwright.chromium.launch(**kwargs)
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError(" | ".join(errors))


def _playwright_unavailable_reason():
    try:
        import playwright  # noqa: F401
    except ImportError:
        return "playwright package not installed"
    return None


_PW_SKIP = _playwright_unavailable_reason()

pytestmark = [
    pytest.mark.frontend,
    pytest.mark.skipif(_PW_SKIP is not None, reason=_PW_SKIP or "Chrome not available"),
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


def _seed(dst):
    import backend_v2 as backend

    old = backend.DB_PATH
    backend.app.config["TESTING"] = True
    init_empty_db(backend, dst)
    kid = insert_kid(
        dst,
        name=KID_NAME,
        username=KID_USERNAME,
        pin=TEST_KID_PIN,
        level=8,
        points=8000,
        experience=40,
    )
    db = connect_db(dst)
    gym = db.execute("SELECT id FROM building_defs WHERE name=?", ("健身室",)).fetchone()
    db.close()
    insert_building(dst, kid["id"], gym["id"], level=1, stored=0, cell_x=0, cell_y=0)
    grant_inventory(dst, kid["id"], {"wood": 80, "brick": 80, "gear": 20, "gem": 5, "glass": 5})
    backend.DB_PATH = old
    return {"kid_id": kid["id"]}


@pytest.fixture()
def adjacent_db(tmp_path):
    dst = str(tmp_path / "adjacent.db")
    ids = _seed(dst)
    with open(dst + ".ids.json", "w", encoding="utf-8") as handle:
        json.dump(ids, handle)
    return dst


@pytest.fixture()
def base_url(adjacent_db):
    port = _free_port()
    log_path = adjacent_db + ".server.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(REPO, "tests", "_run_server.py"), adjacent_db, str(port)],
        cwd=REPO,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**os.environ, "KIDS_TOWN_SECRET_KEY": "adjacent-e2e-secret"},
    )
    if not _wait_port(port, timeout=30):
        logf.flush()
        detail = open(log_path, encoding="utf-8").read()
        proc.kill()
        raise AssertionError(f"adjacent e2e server failed on {port}:\n{detail}")
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    logf.close()


@pytest.fixture()
def page(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        pg = context.new_page()
        pg.route("https://image.pollinations.ai/**", lambda route: route.abort())
        yield pg
        context.close()
        browser.close()


def _login(page, base_url):
    page.goto(f"{base_url}/kids/")
    page.locator("#form-kid #loginUsername").fill(KID_USERNAME)
    page.locator("#form-kid #loginPassword").fill(TEST_KID_PIN)
    page.locator("#form-kid").get_by_role("button", name="進入小鎮").click()
    try:
        page.locator("#app").wait_for(state="visible", timeout=15000)
    except Exception as exc:
        status = ""
        err = page.locator("#loginError")
        if err.count():
            status = err.inner_text()
        raise AssertionError(f"login did not open #app. #loginError={status!r}") from exc
    page.locator("#loginScreen").wait_for(state="hidden", timeout=8000)
    page.locator("#village .cell-btn").first.wait_for(state="attached", timeout=8000)


def _click_cell(page, cell_x, cell_y):
    col = cell_x + 1
    row = cell_y + 1
    pad = page.locator("#townMap").get_by_role(
        "button",
        name=__import__("re").compile(rf"第\s*{col}\s*欄第\s*{row}\s*行"),
    )
    assert pad.count() > 0, f"missing pad 第 {col} 欄第 {row} 行"
    pad.first.click()


def _toast(page):
    try:
        page.wait_for_function(
            """() => {
              const el = document.getElementById('toast');
              return !!(el && el.style.display === 'block' && (el.textContent || '').length);
            }""",
            timeout=1600,
        )
    except Exception:
        pass
    return page.evaluate(
        """() => {
          const el = document.getElementById('toast');
          if (!el) return { missing: true };
          const cs = getComputedStyle(el);
          return {
            text: el.textContent || '',
            className: el.className || '',
            background: cs.backgroundColor,
            color: cs.color
          };
        }"""
    )


def _gold_cells(page):
    raw = page.evaluate(
        r"""() => {
          const cells = [];
          for (const pad of document.querySelectorAll('#townMap .pad')) {
            const hot = pad.classList.contains('is-empty-hot') || pad.classList.contains('is-chosen');
            const mark = pad.querySelector(':scope > .mark');
            if (!hot || !mark || mark.hidden) continue;
            const cs = getComputedStyle(mark);
            const box = mark.getBoundingClientRect();
            const visible = cs.display !== 'none' && cs.visibility !== 'hidden'
              && box.width > 1 && box.height > 1;
            const filter = cs.filter || '';
            const gold = filter.includes('212') && filter.includes('160') && filter.includes('23');
            if (!visible || !gold) continue;
            const btn = pad.querySelector('.cell-btn');
            const label = btn ? (btn.getAttribute('aria-label') || '') : '';
            const match = label.match(/第\s*(\d+)\s*欄第\s*(\d+)\s*行/);
            if (!match) continue;
            cells.push([Number(match[1]) - 1, Number(match[2]) - 1]);
          }
          return cells;
        }"""
    )
    return sorted((item[0], item[1]) for item in raw)


def _cell_probe(page):
    return page.evaluate(
        r"""() => {
          function box(el) {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, bottom: r.bottom };
          }
          function padAt(c, r) {
            for (const pad of document.querySelectorAll('#townMap .pad')) {
              const cs = getComputedStyle(pad);
              if (Number(cs.getPropertyValue('--c')) === c && Number(cs.getPropertyValue('--r')) === r) {
                return pad;
              }
            }
            return null;
          }
          const origin = padAt(0, 0);
          const between = padAt(1, 0);
          const touch = padAt(2, 0);
          const sprite = origin && origin.querySelector('.sprite');
          const shadow = origin && origin.querySelector('[data-contact-shadow]');
          const label = (pad) => {
            const btn = pad && pad.querySelector('.cell-btn');
            return btn ? (btn.getAttribute('aria-label') || '') : '';
          };
          return {
            scene: (document.getElementById('townMap') || {}).getAttribute('aria-label') || '',
            originLabel: label(origin),
            betweenLabel: label(between),
            touchLabel: label(touch),
            sprite: sprite && !sprite.hidden ? box(sprite) : null,
            shadow: shadow && !shadow.hidden ? box(shadow) : null,
            between: box(between),
            touch: box(touch),
            origin: box(origin)
          };
        }"""
    )


def _info_problems(toast, expected):
    problems = []
    if (toast.get("text") or "") != expected:
        problems.append(f"toast text {toast.get('text')!r}, expected {expected!r}")
    classes = set((toast.get("className") or "").split())
    if "info" not in classes or "error" in classes:
        problems.append(f"toast class {toast.get('className')!r}, expected info and not error")
    if toast.get("background") != INFO_BG:
        problems.append(f"toast background {toast.get('background')!r}, expected {INFO_BG}")
    if toast.get("color") != INFO_FG:
        problems.append(f"toast color {toast.get('color')!r}, expected {INFO_FG}")
    return problems


@pytest.mark.case_id("TC-FE-BUILD-ADJACENT-02")
def test_scene2_allows_edge_adjacent_origin_and_blocks_overlap_cell(
    page, base_url, adjacent_db
):
    """TC-FE-BUILD-ADJACENT-02 Scene 2 gold includes the touching origin.

    健身室 is already at (0,0). (2,0) is a legal 2×2 origin and must be gold.
    (1,0) overlaps that footprint and must not be gold. Clicking (1,0) before
    a building is chosen toasts 「這個位置已經有建築物。」 After 醫院 is chosen,
    the same cell toasts 「這個位置放不下這座建築物。」 Confirming (2,0) places
    醫院, HTTP 201, toast 「起好「醫院」。」
    """
    ids = json.load(open(adjacent_db + ".ids.json", encoding="utf-8"))
    kid_id = ids["kid_id"]
    before_points = get_kid_points(adjacent_db, kid_id)
    before_items = inventory_map(adjacent_db, kid_id)
    _login(page, base_url)
    scene1 = _cell_probe(page)
    page.locator("#btnBuild").click()
    page.locator("#readyBar").wait_for(state="visible", timeout=8000)
    gold_before = set(_gold_cells(page))
    _click_cell(page, 1, 0)
    covered_toast = _toast(page)
    page.locator("#listLauncher").click()
    page.locator("#palette").wait_for(state="visible", timeout=8000)
    hospital = page.locator("#palette").get_by_role("button", name=__import__("re").compile(r"醫院"))
    assert hospital.count() > 0, "建築清單 has no 醫院"
    hospital.first.click()
    gold_after = set(_gold_cells(page))
    _click_cell(page, 1, 0)
    unfit_toast = _toast(page)
    _click_cell(page, 2, 0)
    page.locator("#btnToScene3").click()
    page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
    scene3 = _cell_probe(page)
    _click_cell(page, 0, 0)
    scene3_occupied = _toast(page)
    _click_cell(page, 1, 0)
    scene3_unfit = _toast(page)
    with page.expect_response(
        lambda resp: (
            resp.request.method == "POST"
            and "/buildings" in resp.url
            and "/unstored" not in resp.url
            and "/move" not in resp.url
            and "/store" not in resp.url
        ),
        timeout=8000,
    ) as posted:
        page.locator("#btnUxConfirm").click()
    page.wait_for_function(
        """(expected) => {
          const el = document.getElementById('toast');
          const map = document.getElementById('townMap');
          const text = el ? (el.textContent || '') : '';
          const scene = map ? (map.getAttribute('aria-label') || '') : '';
          return text === expected && scene.indexOf('場景 1') !== -1;
        }""",
        arg=PLACED_TOAST,
        timeout=8000,
    )
    placed_toast = _toast(page)
    probe = _cell_probe(page)
    db = connect_db(adjacent_db)
    rows = db.execute(
        """
        SELECT bd.name, b.cell_x, b.cell_y, b.level, COALESCE(b.stored, 0) AS stored
          FROM buildings b JOIN building_defs bd ON bd.id = b.def_id
         WHERE b.kid_id=?
         ORDER BY b.id
        """,
        (kid_id,),
    ).fetchall()
    cost = db.execute(
        "SELECT cost_gold, materials FROM building_defs WHERE name=?",
        ("醫院",),
    ).fetchone()
    db.close()
    problems = []
    if (2, 0) not in gold_before:
        problems.append(f"(2,0) was not gold before a building was chosen. gold={sorted(gold_before)}")
    if (1, 0) in gold_before or (0, 0) in gold_before:
        problems.append(f"overlap or origin cell was gold before choose: {sorted(gold_before)}")
    if (2, 0) not in gold_after:
        problems.append(f"(2,0) was not gold after 醫院 was chosen. gold={sorted(gold_after)}")
    if (1, 0) in gold_after:
        problems.append(f"(1,0) stayed gold after 醫院 was chosen: {sorted(gold_after)}")
    problems.extend(_info_problems(covered_toast, OCCUPIED_TOAST))
    problems.extend(_info_problems(unfit_toast, UNFIT_TOAST))
    problems.extend(_info_problems(scene3_occupied, SCENE3_OCCUPIED_TOAST))
    problems.extend(_info_problems(scene3_unfit, UNFIT_TOAST))
    if posted.value.status != 201:
        problems.append(f"place HTTP {posted.value.status} {posted.value.text()[:240]}")
    else:
        payload = posted.value.json()
        if (payload.get("cell_x"), payload.get("cell_y")) != (2, 0):
            problems.append(f"place body cell {payload.get('cell_x'), payload.get('cell_y')}")
    if (placed_toast.get("text") or "") != PLACED_TOAST:
        problems.append(f"success toast {placed_toast.get('text')!r}, expected {PLACED_TOAST!r}")
    if "info" in (placed_toast.get("className") or "") or "error" in (placed_toast.get("className") or ""):
        problems.append(f"success toast class {placed_toast.get('className')!r}, expected neither info nor error")
    if placed_toast.get("background") != SUCCESS_BG:
        problems.append(f"success toast background {placed_toast.get('background')!r}, expected {SUCCESS_BG}")
    found = [dict(row) for row in rows]
    hospital_row = next((row for row in found if row["name"] == "醫院"), None)
    gym_row = next((row for row in found if row["name"] == "健身室"), None)
    if not hospital_row or (hospital_row["cell_x"], hospital_row["cell_y"], hospital_row["stored"], hospital_row["level"]) != (2, 0, 0, 1):
        problems.append(f"醫院 row {hospital_row}")
    if not gym_row or (gym_row["cell_x"], gym_row["cell_y"], gym_row["stored"]) != (0, 0, 0):
        problems.append(f"健身室 row {gym_row}")
    gold_cost = int(cost["cost_gold"] or 0)
    materials = json.loads(cost["materials"] or "{}")
    after_points = get_kid_points(adjacent_db, kid_id)
    after_items = inventory_map(adjacent_db, kid_id)
    if after_points != before_points - gold_cost:
        problems.append(f"gold {before_points} -> {after_points}, expected -{gold_cost}")
    for item_type, qty in materials.items():
        have = after_items.get(item_type, 0)
        want = before_items.get(item_type, 0) - qty
        if have != want:
            problems.append(f"{item_type} {have}, expected {want}")
    # Geometry is evidence for the false-gap note. It does not change pass/fail.
    print("ADJACENT_SCENE1 " + json.dumps(scene1, ensure_ascii=False))
    print("ADJACENT_SCENE3 " + json.dumps(scene3, ensure_ascii=False))
    print("ADJACENT_AFTER " + json.dumps(probe, ensure_ascii=False))
    assert not problems, "TC-FE-BUILD-ADJACENT-02: " + " | ".join(problems)
