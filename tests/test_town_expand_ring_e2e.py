"""Locked expandable ring around the live 8×8 town. Red on current main.

Design: PR #72 tip 52a5bb06297725045774378427184204d8054823
`docs/ui-mocks/town-expandable.html`. These tests drive `/kids/` after a
real kid login. They do not open the static mock, and they do not change
product code.

Contract (see docs/test-cases/TOWN_EXPAND_RING.md):
  TC-FE-EXPAND-RING-01  buildable map stays the center 8×8; one locked ring
  TC-FE-EXPAND-RING-02  locked styling and the two legend labels
  TC-FE-EXPAND-RING-03  locked click toasts the exact sentence and does not select
  TC-FE-EXPAND-RING-04  locked cells are not a placement target

No unlock flow. No footprint / edge-adjacency asserts (#71).
Temporary SQLite and a synthetic kid only. Never opens kids_town.db.
"""
from __future__ import annotations

import hashlib
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
    init_empty_db,
    insert_kid,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_DB = os.path.join(REPO, "kids_town.db")
PROD_SHA256 = "c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb"

KID_USERNAME = "test_expand_kid"
KID_NAME = "Expand Kid"

LOCKED_TOAST = "此格尚未解鎖，暫時不能建造。"
BUILDABLE_LEGEND = "可建區域（8×8）"
LOCKED_LEGEND = "可擴建（未解鎖）"
# Scene-1 empty pad, already on main. The locked sentence must not replace it.
SCENE1_EMPTY_TOAST = "想在這裏興建？請先按「我要起屋」。"

# One-cell ring around 0..7. Spoken 欄/行 are data-col/row + 1, so the ring
# reads as 0 or 9. Matches the mock's labelFor().
SAMPLE_LOCKED = ((-1, -1), (-1, 3), (3, -1), (8, 4), (4, 8), (8, 8))


def _ring_coords():
    coords = []
    for row in range(-1, 9):
        for col in range(-1, 9):
            if 0 <= col <= 7 and 0 <= row <= 7:
                continue
            coords.append((col, row))
    return coords


RING_COORDS = _ring_coords()
assert len(RING_COORDS) == 36
assert len({(col, row) for col in range(8) for row in range(8)}) == 64


def _locked_aria(col, row):
    return f"未解鎖格子（欄 {col + 1}，行 {row + 1}）"


def _playwright_unavailable_reason():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "playwright package not installed. "
            "Install: pip install -r requirements.txt && python -m playwright install chromium"
        )
    try:
        with sync_playwright() as playwright:
            exe = playwright.chromium.executable_path
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


def _prod_sha256():
    digest = hashlib.sha256()
    with open(PROD_DB, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_prod_db_untouched():
    assert os.path.isfile(PROD_DB), "tracked kids_town.db is missing"
    assert _prod_sha256() == PROD_SHA256, "tracked kids_town.db changed; tests must not write it"


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
    """Empty schema plus one synthetic kid. No buildings, so the 8×8 is empty."""
    import backend_v2 as backend

    assert os.path.abspath(dst) != os.path.abspath(PROD_DB)
    old = backend.DB_PATH
    backend.app.config["TESTING"] = True
    init_empty_db(backend, dst)
    kid = insert_kid(
        dst,
        name=KID_NAME,
        username=KID_USERNAME,
        pin=TEST_KID_PIN,
        level=8,
        points=800,
        experience=40,
    )
    backend.DB_PATH = old
    return {"kid_id": kid["id"]}


@pytest.fixture(scope="session")
def expand_db(tmp_path_factory):
    _assert_prod_db_untouched()
    dst = str(tmp_path_factory.mktemp("expand-ring-db") / "expand.db")
    ids = _seed(dst)
    with open(dst + ".ids.json", "w", encoding="utf-8") as handle:
        json.dump(ids, handle)
    yield dst
    _assert_prod_db_untouched()


@pytest.fixture(scope="session")
def expand_ids(expand_db):
    with open(expand_db + ".ids.json", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def base_url(expand_db):
    port = _free_port()
    log_path = expand_db + ".server.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(REPO, "tests", "_run_server.py"), expand_db, str(port)],
        cwd=REPO,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**os.environ, "KIDS_TOWN_SECRET_KEY": "expand-ring-e2e-secret"},
    )
    if not _wait_port(port, timeout=30):
        logf.flush()
        try:
            detail = open(log_path, encoding="utf-8").read()
        except OSError:
            detail = "(no server log)"
        proc.kill()
        raise AssertionError(f"expand-ring e2e server failed on {port}:\n{detail}")
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
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        pg = context.new_page()
        pg.route("https://image.pollinations.ai/**", lambda route: route.abort())
        yield pg
        context.close()
        browser.close()


def _login(page, base_url):
    page.goto(f"{base_url}/kids/")
    page.locator("#loginUsername").wait_for(state="visible", timeout=8000)
    page.locator("#loginUsername").fill(KID_USERNAME)
    page.locator("#loginPassword").fill(TEST_KID_PIN)
    with page.expect_response(
        lambda response: "/api/auth/login" in response.url and response.request.method == "POST"
    ) as caught:
        page.get_by_role("button", name="進入小鎮").click()
    login = caught.value
    assert login.status == 200, login.text()
    page.locator("#app").wait_for(state="visible", timeout=8000)
    page.locator("#loginScreen").wait_for(state="hidden", timeout=8000)
    page.wait_for_function(
        """() => {
          const map = document.getElementById('townMap');
          const pads = document.querySelectorAll('#townMap .village.is-iso > .pad');
          const btn = document.querySelector('#townMap .cell-btn');
          const label = (map && map.getAttribute('aria-label')) || '';
          return pads.length >= 64 && btn
            && (btn.getAttribute('aria-label') || '').indexOf('空地') !== -1
            && label.indexOf('場景 1') !== -1;
        }""",
        timeout=8000,
    )


def _int_or_none(value):
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


_READ_PADS_JS = """
() => [...document.querySelectorAll('#townMap .village.is-iso > .pad')].map((pad) => {
  const cs = getComputedStyle(pad);
  const btn = pad.querySelector(':scope > .cell-btn');
  const slab = pad.querySelector(':scope > .slab');
  const lock = pad.querySelector(':scope > .lock-icon, :scope > svg.lock-icon');
  const shade = pad.querySelector(':scope > .shade');
  const mark = pad.querySelector(':scope > .mark');
  function shown(el) {
    if (!el) return false;
    if (el.hidden) return false;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    const box = el.getBoundingClientRect();
    return box.width > 1 && box.height > 1;
  }
  const btnStyle = btn ? getComputedStyle(btn) : null;
  return {
    dataCol: pad.getAttribute('data-col'),
    dataRow: pad.getAttribute('data-row'),
    cVar: cs.getPropertyValue('--c').trim(),
    rVar: cs.getPropertyValue('--r').trim(),
    zone: pad.getAttribute('data-zone') || '',
    className: pad.className || '',
    aria: btn ? (btn.getAttribute('aria-label') || '') : '',
    ariaDisabled: btn ? btn.getAttribute('aria-disabled') : null,
    tabIndex: btn ? btn.tabIndex : null,
    pressed: btn ? btn.getAttribute('aria-pressed') : null,
    cursor: btnStyle ? btnStyle.cursor : '',
    slabFilter: slab ? getComputedStyle(slab).filter : '',
    slabSrc: slab ? (slab.getAttribute('src') || '') : '',
    lockShown: shown(lock),
    shadeShown: shown(shade),
    markShown: shown(mark),
    padW: pad.getBoundingClientRect().width,
    padH: pad.getBoundingClientRect().height,
    left: pad.offsetLeft,
    top: pad.offsetTop
  };
})
"""


def _read_pads(page):
    parsed = []
    for item in page.evaluate(_READ_PADS_JS):
        data_col = _int_or_none(item.get("dataCol"))
        data_row = _int_or_none(item.get("dataRow"))
        cvar = _int_or_none(item.get("cVar"))
        rvar = _int_or_none(item.get("rVar"))
        if data_col is None or data_row is None:
            col, row = cvar, rvar
            coord_from = "css"
        else:
            col, row = data_col, data_row
            coord_from = "data"
        parsed.append(
            {
                **item,
                "col": col,
                "row": row,
                "data_col": data_col,
                "data_row": data_row,
                "cvar": cvar,
                "rvar": rvar,
                "coord_from": coord_from,
                "classes": set((item.get("className") or "").split()),
            }
        )
    return parsed


def _by_coord(cells):
    found = {}
    dupes = []
    for cell in cells:
        if cell["col"] is None or cell["row"] is None:
            continue
        key = (cell["col"], cell["row"])
        if key in found:
            dupes.append(key)
        found[key] = cell
    return found, dupes


def _is_inner(col, row):
    return col is not None and row is not None and 0 <= col <= 7 and 0 <= row <= 7


def _geometry_problems(cells):
    """TC-FE-EXPAND-RING-01. Inner 8×8 may already be drawn via --c/--r."""
    problems = []
    found, dupes = _by_coord(cells)
    if dupes:
        problems.append(f"duplicate pad coordinates {dupes}")
    inner_keys = [(col, row) for col in range(8) for row in range(8)]
    missing_inner = [key for key in inner_keys if key not in found]
    extra = [key for key in found if key not in inner_keys and key not in RING_COORDS]
    missing_ring = [key for key in RING_COORDS if key not in found]
    unpositioned = [
        cell["className"] for cell in cells if cell["col"] is None or cell["row"] is None
    ]
    if unpositioned:
        problems.append(f"{len(unpositioned)} pads have neither data-col/data-row nor --c/--r")
    if missing_inner:
        problems.append(f"buildable 8×8 missing cells {missing_inner}")
    if len(cells) != 100:
        problems.append(f"pad count {len(cells)}, want 100 (64 buildable + 36 locked)")
    if missing_ring:
        problems.append(
            f"locked ring missing {len(missing_ring)}/36 cells, "
            f"for example {missing_ring[:8]}"
        )
    if extra:
        problems.append(f"cells outside the 10×10 frame (−1..8) {extra}")

    inner_cells = [found[key] for key in inner_keys if key in found]
    no_data = [cell for cell in inner_cells if cell["coord_from"] != "data"]
    if no_data:
        sample = no_data[0]
        problems.append(
            f"{len(no_data)} inner pads have no data-col/data-row "
            f"(example class {sample['className']!r}, --c={sample['cvar']}, --r={sample['rvar']}). "
            "Set data-col and data-row to the same integers as --c and --r."
        )
    mismatched = [
        cell
        for cell in inner_cells
        if cell["data_col"] is not None
        and (cell["data_col"] != cell["cvar"] or cell["data_row"] != cell["rvar"])
    ]
    if mismatched:
        sample = mismatched[0]
        problems.append(
            f"data-col/data-row disagrees with --c/--r on "
            f"({sample['data_col']},{sample['data_row']}) vs ({sample['cvar']},{sample['rvar']})"
        )
    not_buildable_zone = [cell for cell in inner_cells if cell["zone"] != "buildable"]
    if not_buildable_zone:
        sample = not_buildable_zone[0]
        problems.append(
            f"{len(not_buildable_zone)} inner pads lack data-zone='buildable' "
            f"(example ({sample['col']},{sample['row']}) zone {sample['zone']!r} "
            f"class {sample['className']!r})"
        )
    not_buildable_class = [cell for cell in inner_cells if "is-buildable" not in cell["classes"]]
    if not_buildable_class:
        sample = not_buildable_class[0]
        problems.append(
            f"{len(not_buildable_class)} inner pads lack class is-buildable "
            f"(example ({sample['col']},{sample['row']}) class {sample['className']!r}). "
            "Keep the scene class (is-quiet / is-empty-hot / is-chosen) and add is-buildable."
        )
    locked_inner = [
        (cell["col"], cell["row"])
        for cell in inner_cells
        if "is-locked" in cell["classes"] or cell["zone"] == "locked"
    ]
    if locked_inner:
        problems.append(f"inner 8×8 cells marked locked {locked_inner}")

    ring_cells = [found[key] for key in RING_COORDS if key in found]
    bad_ring_zone = [
        (cell["col"], cell["row"], cell["zone"])
        for cell in ring_cells
        if cell["zone"] != "locked" or "is-locked" not in cell["classes"]
    ]
    if bad_ring_zone:
        problems.append(
            f"ring cells missing data-zone='locked' or class is-locked, "
            f"for example {bad_ring_zone[:6]}"
        )
    ring_from_css = [cell for cell in ring_cells if cell["coord_from"] != "data"]
    if ring_from_css:
        problems.append(
            f"{len(ring_from_css)} ring pads are positioned only by --c/--r; "
            "set data-col and data-row as well"
        )

    if not missing_ring and not missing_inner:
        tops_inner = [found[key]["top"] for key in inner_keys]
        lefts_inner = [found[key]["left"] for key in inner_keys]
        tops_ring = [found[key]["top"] for key in RING_COORDS]
        lefts_ring = [found[key]["left"] for key in RING_COORDS]
        if not (min(tops_ring) < min(tops_inner)):
            problems.append(
                f"ring does not extend north of the 8×8 "
                f"(ring top {min(tops_ring)} , inner top {min(tops_inner)})"
            )
        if not (max(tops_ring) > max(tops_inner)):
            problems.append(
                f"ring does not extend south of the 8×8 "
                f"(ring top {max(tops_ring)} , inner top {max(tops_inner)})"
            )
        if not (min(lefts_ring) < min(lefts_inner)):
            problems.append(
                f"ring does not extend west of the 8×8 "
                f"(ring left {min(lefts_ring)} , inner left {min(lefts_inner)})"
            )
        if not (max(lefts_ring) > max(lefts_inner)):
            problems.append(
                f"ring does not extend east of the 8×8 "
                f"(ring left {max(lefts_ring)} , inner left {max(lefts_inner)})"
            )
    return problems


def _style_problems(cell):
    col, row = cell["col"], cell["row"]
    where = f"({col},{row})"
    problems = []
    if "is-locked" not in cell["classes"]:
        problems.append(f"{where} missing class is-locked (class {cell['className']!r})")
    if cell["zone"] != "locked":
        problems.append(f"{where} data-zone {cell['zone']!r}, want 'locked'")
    want = _locked_aria(col, row)
    if cell["aria"] != want:
        problems.append(f"{where} aria-label {cell['aria']!r}, want {want!r}")
    if cell["ariaDisabled"] != "true":
        problems.append(f"{where} aria-disabled {cell['ariaDisabled']!r}, want 'true'")
    if cell["tabIndex"] != -1:
        problems.append(f"{where} tabIndex {cell['tabIndex']!r}, want -1")
    if cell["cursor"] != "not-allowed":
        problems.append(f"{where} cursor {cell['cursor']!r}, want 'not-allowed'")
    if not cell["lockShown"]:
        problems.append(f"{where} svg.lock-icon is not visible")
    if not cell["shadeShown"]:
        problems.append(f"{where} .shade hatch is not visible")
    filt = cell["slabFilter"] or ""
    for token in ("grayscale", "brightness", "saturate"):
        if token not in filt:
            problems.append(f"{where} slab filter {filt!r} missing {token}")
            break
    if "ground-tile" not in (cell["slabSrc"] or ""):
        problems.append(f"{where} slab src {cell['slabSrc']!r}, want ground-tile.svg")
    if cell["markShown"]:
        problems.append(f"{where} .mark is visible; a locked cell is not a gold selectable plot")
    selectable = cell["classes"] & {
        "is-quiet", "is-empty", "is-empty-hot", "is-chosen", "is-preview", "is-valid", "is-illegal",
    }
    if selectable:
        problems.append(
            f"{where} still has a buildable scene class {sorted(selectable)}; "
            "a locked cell is only is-locked"
        )
    if cell["pressed"] == "true":
        problems.append(f"{where} aria-pressed is true")
    if cell["padW"] < 2 or cell["padH"] < 2:
        problems.append(f"{where} pad box {cell['padW']:.1f}×{cell['padH']:.1f} is not painted")
    return problems


def _visible_exact_count(page, text):
    locator = page.locator("#townMap").get_by_text(text, exact=True)
    count = 0
    for index in range(locator.count()):
        try:
            if locator.nth(index).is_visible():
                count += 1
        except Exception:
            continue
    return count


def _hud(page):
    return page.evaluate(
        """() => {
          const text = (id) => {
            const el = document.getElementById(id);
            return el ? (el.textContent || '').trim() : '';
          };
          const mat = (name) => {
            const el = document.querySelector('#hdrRes .mat[data-mat="' + name + '"] .n');
            return el ? (el.textContent || '').trim() : '';
          };
          return {
            gold: text('hudCo'),
            wood: mat('wood'),
            brick: mat('brick'),
            glass: mat('glass'),
            gear: mat('gear')
          };
        }"""
    )


def _scene_label(page):
    return page.evaluate(
        """() => {
          const map = document.getElementById('townMap');
          return map ? (map.getAttribute('aria-label') || '') : '';
        }"""
    )


def _sheet_hidden(page):
    return page.evaluate(
        """() => {
          const el = document.getElementById('actionSheet');
          if (!el) return true;
          const style = getComputedStyle(el);
          return !!el.hidden || style.display === 'none' || style.visibility === 'hidden';
        }"""
    )


def _place_bar_hidden(page):
    return page.evaluate(
        """() => {
          const bar = document.getElementById('uxPlaceBar');
          if (!bar) return true;
          const style = getComputedStyle(bar);
          return !!bar.hidden || style.display === 'none' || style.visibility === 'hidden';
        }"""
    )


def _placement_bar_inactive(page):
    return page.evaluate(
        """() => {
          const bar = document.getElementById('placementBar');
          return !bar || !bar.classList.contains('active');
        }"""
    )


def _chosen(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('#townMap .pad.is-chosen')].map((pad) => {
          const cs = getComputedStyle(pad);
          return {
            dataCol: pad.getAttribute('data-col'),
            dataRow: pad.getAttribute('data-row'),
            c: cs.getPropertyValue('--c').trim(),
            r: cs.getPropertyValue('--r').trim(),
            zone: pad.getAttribute('data-zone') || '',
            className: pad.className || ''
          };
        })"""
    )


def _clear_toast(page):
    page.evaluate(
        """() => {
          const el = document.getElementById('toast');
          if (!el) return;
          el.textContent = '';
          el.style.display = 'none';
        }"""
    )


def _toast_now(page):
    return page.evaluate(
        """() => {
          const el = document.getElementById('toast');
          if (!el) return {text: '', display: 'missing', cls: ''};
          const style = getComputedStyle(el);
          return {
            text: (el.textContent || '').trim(),
            display: style.display,
            visibility: style.visibility,
            cls: el.className || ''
          };
        }"""
    )


def _assert_toast_exact(page, case_id, expected):
    last = None
    deadline = time.time() + 1.6
    while time.time() < deadline:
        last = _toast_now(page)
        visible = last["display"] != "none" and last["visibility"] != "hidden"
        if last["text"] == expected and visible:
            return last
        page.wait_for_timeout(40)
    pytest.fail(
        f"{case_id}: #toast must be visible and exactly {expected!r}. got {last}"
    )


def _building_count(db_path, kid_id):
    db = connect_db(db_path)
    count = db.execute(
        "SELECT COUNT(*) AS n FROM buildings WHERE kid_id=?",
        (kid_id,),
    ).fetchone()["n"]
    db.close()
    return count


def _arm_building_posts(page):
    posts = []

    def _on_request(request):
        if request.method == "POST" and "/buildings" in request.url:
            posts.append(request.url)

    page.on("request", _on_request)
    return posts


def _locked_button(page, col, row):
    return page.locator(
        f'#townMap .pad[data-col="{col}"][data-row="{row}"] > .cell-btn'
    )


def _require_locked_button(page, case_id, col, row):
    button = _locked_button(page, col, row)
    count = button.count()
    assert count == 1, (
        f"{case_id}: need exactly one locked .cell-btn at data-col={col} data-row={row}, "
        f"found {count}. The outer ring is not on the live #townMap."
    )
    return button


def _mouse_click_center(page, locator):
    """Pointer click. aria-disabled must not block it: the toast is the point."""
    locator.scroll_into_view_if_needed(timeout=3000)
    box = locator.bounding_box()
    assert box and box["width"] > 1 and box["height"] > 1, (
        f"locked control has no painted box: {box}"
    )
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def _enter_scene2(page):
    page.get_by_role("button", name="我要起屋").click()
    page.wait_for_function(
        """() => {
          const map = document.getElementById('townMap');
          const label = (map && map.getAttribute('aria-label')) || '';
          return label.indexOf('場景 2') !== -1
            && document.querySelector('#townMap .pad.is-empty-hot .cell-btn');
        }""",
        timeout=8000,
    )


def _select_origin(page):
    """Select the buildable origin (0, 0). Does not assert the gold-cell set."""
    target = page.get_by_role("button", name="第 1 欄第 1 行，空地，點選即可選擇")
    assert target.count() >= 1, (
        "TC-FE-EXPAND-RING-04: scene 2 must still expose the buildable cell "
        "「第 1 欄第 1 行」 so a locked click can be compared with a real selection."
    )
    _mouse_click_center(page, target.first)
    page.wait_for_function(
        """() => {
          const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
            const cs = getComputedStyle(el);
            return cs.getPropertyValue('--c').trim() === '0'
              && cs.getPropertyValue('--r').trim() === '0';
          });
          return pad && pad.classList.contains('is-chosen');
        }""",
        timeout=4000,
    )


# ── TC-FE-EXPAND-RING-01 ─────────────────────────────────────────


@pytest.mark.case_id("TC-FE-EXPAND-RING-01")
def test_expand_ring_buildable_8x8_stays_centered(page, base_url, expand_db):
    """TC-FE-EXPAND-RING-01 可建區維持正中 8×8，外圍剛好一圈鎖住。"""
    del expand_db
    _login(page, base_url)
    cells = _read_pads(page)
    problems = _geometry_problems(cells)
    assert not problems, (
        "TC-FE-EXPAND-RING-01: the live town keeps a centered buildable 8×8 "
        "(data-col/data-row 0..7, data-zone=buildable, class is-buildable) and adds "
        "exactly one locked ring (36 cells, coordinates −1..8 outside that square, "
        "data-zone=locked, class is-locked). No second ring and no playable cell "
        "outside 0..7. Do not change COLS/ROWS or TOWN_PLACE_COLS.\n"
        + "\n".join(problems)
    )


# ── TC-FE-EXPAND-RING-02 ─────────────────────────────────────────


@pytest.mark.case_id("TC-FE-EXPAND-RING-02")
def test_expand_ring_locked_styling_and_labels(page, base_url, expand_db):
    """TC-FE-EXPAND-RING-02 鎖住的格子看得到，而且不是可選的金色空地。"""
    del expand_db
    _login(page, base_url)
    cells = _read_pads(page)
    found, _dupes = _by_coord(cells)
    problems = []
    if _visible_exact_count(page, BUILDABLE_LEGEND) < 1:
        problems.append(
            f"#townMap is missing visible text {BUILDABLE_LEGEND!r}"
        )
    if _visible_exact_count(page, LOCKED_LEGEND) < 1:
        problems.append(f"#townMap is missing visible text {LOCKED_LEGEND!r}")
    missing = [key for key in RING_COORDS if key not in found]
    if missing:
        problems.append(f"no locked pads to style, missing {len(missing)}/36")
    for key in RING_COORDS:
        cell = found.get(key)
        if cell is None:
            continue
        problems.extend(_style_problems(cell))
    for cell in cells:
        if not _is_inner(cell["col"], cell["row"]):
            continue
        if "ground-tile" in (cell["slabSrc"] or "") and "is-locked" not in cell["classes"]:
            problems.append(
                f"inner ({cell['col']},{cell['row']}) uses ground-tile; "
                "buildable slabs stay ground-plot.svg"
            )
        filt = cell["slabFilter"] or ""
        if "grayscale" in filt and "is-locked" not in cell["classes"]:
            problems.append(
                f"inner ({cell['col']},{cell['row']}) slab is dimmed like a locked cell"
            )
    assert not problems, (
        "TC-FE-EXPAND-RING-02: each locked ring cell is painted as expandable-but-locked "
        "(class is-locked, ground-tile.svg, grayscale/brightness/saturate on the slab, "
        "visible .shade and svg.lock-icon, cursor not-allowed, aria-disabled=true, "
        "tabIndex -1, aria-label 「未解鎖格子（欄 N，行 M）」). It is not is-empty-hot, "
        "is-chosen, or a visible gold .mark. #townMap shows the legend strings. "
        "Do not copy the mock kicker 「靜態設計稿」.\n"
        + "\n".join(problems[:40])
        + (f"\n… {len(problems) - 40} more" if len(problems) > 40 else "")
    )


# ── TC-FE-EXPAND-RING-03 ─────────────────────────────────────────


@pytest.mark.case_id("TC-FE-EXPAND-RING-03")
def test_expand_ring_locked_click_toast_does_not_select(
    page, base_url, expand_db, expand_ids
):
    """TC-FE-EXPAND-RING-03 點鎖住的格子只出那句提示，不選中。"""
    _login(page, base_url)
    posts = _arm_building_posts(page)
    before_hud = _hud(page)
    before_rows = _building_count(expand_db, expand_ids["kid_id"])
    assert _chosen(page) == [], "scene 1 must not start with a selected pad"
    assert _sheet_hidden(page)

    # The buildable cell keeps today's scene-1 sentence. The locked sentence
    # is only for the ring.
    _clear_toast(page)
    buildable = page.get_by_role("button", name="第 1 欄第 1 行，空地")
    assert buildable.count() >= 1, "scene 1 buildable cell 「第 1 欄第 1 行」 is missing"
    _mouse_click_center(page, buildable.first)
    _assert_toast_exact(page, "TC-FE-EXPAND-RING-03", SCENE1_EMPTY_TOAST)
    assert _chosen(page) == [], "clicking a scene-1 buildable empty pad must not select it"

    for col, row in SAMPLE_LOCKED:
        button = _require_locked_button(page, "TC-FE-EXPAND-RING-03", col, row)
        _clear_toast(page)
        _mouse_click_center(page, button)
        _assert_toast_exact(page, "TC-FE-EXPAND-RING-03", LOCKED_TOAST)
        chosen = _chosen(page)
        assert chosen == [], (
            f"TC-FE-EXPAND-RING-03: mouse click on locked ({col},{row}) selected {chosen}"
        )
        pressed = button.get_attribute("aria-pressed")
        assert pressed != "true", (
            f"TC-FE-EXPAND-RING-03: locked ({col},{row}) aria-pressed={pressed!r}"
        )

    col, row = SAMPLE_LOCKED[0]
    button = _require_locked_button(page, "TC-FE-EXPAND-RING-03", col, row)
    _clear_toast(page)
    button.focus()
    page.keyboard.press("Enter")
    _assert_toast_exact(page, "TC-FE-EXPAND-RING-03", LOCKED_TOAST)
    assert _chosen(page) == [], (
        f"TC-FE-EXPAND-RING-03: keyboard activation selected a pad: {_chosen(page)}"
    )
    assert _sheet_hidden(page), "locked click must not open #actionSheet"
    assert _placement_bar_inactive(page), "locked click must not activate #placementBar"
    assert "場景 1" in _scene_label(page), _scene_label(page)
    assert _hud(page) == before_hud, (_hud(page), before_hud)
    assert posts == [], f"locked click posted a building: {posts}"
    assert _building_count(expand_db, expand_ids["kid_id"]) == before_rows


# ── TC-FE-EXPAND-RING-04 ─────────────────────────────────────────


@pytest.mark.case_id("TC-FE-EXPAND-RING-04")
def test_expand_ring_locked_not_placeable_keeps_selection(
    page, base_url, expand_db, expand_ids
):
    """TC-FE-EXPAND-RING-04 建造場景裡，鎖住的格子不能當放置目標。"""
    _login(page, base_url)
    _enter_scene2(page)
    cells = _read_pads(page)
    found, _dupes = _by_coord(cells)
    hot_outside = []
    for cell in cells:
        if "is-empty-hot" not in cell["classes"] and "is-chosen" not in cell["classes"]:
            continue
        if cell["zone"] == "locked" or "is-locked" in cell["classes"] or not _is_inner(cell["col"], cell["row"]):
            hot_outside.append((cell["col"], cell["row"], cell["zone"], cell["className"]))
    missing = [key for key in RING_COORDS if key not in found or found[key]["zone"] != "locked"]
    assert not missing, (
        "TC-FE-EXPAND-RING-04: scene 2 still needs the 36 locked ring cells "
        f"(data-zone=locked). Missing {len(missing)}/36, for example {missing[:8]}. "
        "A locked cell must not become the placement pad."
    )
    assert not hot_outside, (
        "TC-FE-EXPAND-RING-04: locked or off-grid pads are gold/selectable: "
        f"{hot_outside}. The gold set stays inside the buildable 8×8. "
        "This case does not list which inner origins are legal."
    )

    posts = _arm_building_posts(page)
    before_hud = _hud(page)
    before_rows = _building_count(expand_db, expand_ids["kid_id"])
    _select_origin(page)
    chosen_before = _chosen(page)
    assert len(chosen_before) == 1, chosen_before
    assert chosen_before[0]["c"] == "0" and chosen_before[0]["r"] == "0", chosen_before
    assert chosen_before[0]["zone"] != "locked"

    for col, row in ((-1, 0), (8, 7)):
        button = _require_locked_button(page, "TC-FE-EXPAND-RING-04", col, row)
        _clear_toast(page)
        _mouse_click_center(page, button)
        _assert_toast_exact(page, "TC-FE-EXPAND-RING-04", LOCKED_TOAST)
        assert _chosen(page) == chosen_before, (
            f"TC-FE-EXPAND-RING-04: after locked ({col},{row}), selection changed "
            f"from {chosen_before} to {_chosen(page)}"
        )
        assert "場景 2" in _scene_label(page), _scene_label(page)
        assert _place_bar_hidden(page), "locked click must not open scene 3 (#uxPlaceBar)"
        assert _sheet_hidden(page)
        assert _placement_bar_inactive(page)

    assert _hud(page) == before_hud, (_hud(page), before_hud)
    assert posts == [], f"locked click posted a building: {posts}"
    assert _building_count(expand_db, expand_ids["kid_id"]) == before_rows
