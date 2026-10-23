"""TC-FE-WAREHOUSE-UNSTORE — 存倉清單取出到 8×8 地圖。

Playwright。臨時庫、合成小朋友。唔會打開 kids_town.db。

main 上存倉清單的卡片寫「按此放置」，呼叫 startUnstoreBuilding，
打開 #placementBar 並隱藏 #townMap（24×16 .valid-plot）。
呢條案例要求「取出」之後喺 8×8 地圖上揀格。選擇器合約見
docs/test-cases/WAREHOUSE_PLACEMENT.md。
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import socket
import struct
import subprocess
import sys
import time
import zlib

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.qc6_checks import (  # noqa: E402
    any_visible_gold_point,
    bar_masked_diff,
    cell_top_face,
    changed_pixel_count,
    corner_level_delta,
    count_stroke_pixels,
    focus_pixel_report,
    focus_ring_delta,
    focus_ring_shape,
    paint_cover_report,
    paint_overlay_count,
    ring_band_walk,
    ring_device_gaps,
    ring_layer_pixels,
    ring_pixel_report,
    ring_vertex_gaps,
    selection_pixel_report,
    set_village_scroll,
    stroke_near_cell,
    surface_rect,
)
from tests.town_tap import (  # noqa: E402
    _activate_point,
    _scroll_cell_into_view,
    cell_points,
    dismiss_selection,
    tap_cell_centre,
    tap_point,
)
from tests.factories import (  # noqa: E402
    TEST_KID_PIN,
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
KID_USERNAME = "test_warehouse_kid"
KID_NAME = "Warehouse Kid"
BUILDING_NAME = "圖書館"
# 1-based label on the iso pad. DB cell is (1, 1).
CELL_COL = 2
CELL_ROW = 2
CELL_X = 1
CELL_Y = 1
FOOTER_STRUCTURE = os.path.join(REPO, "tests", "fixtures", "kt_footer_main.json")
# Numeric prices and the new-build charge sentence. Saying that nothing is deducted,
# without an amount, is not a price.
PRICE_RE = re.compile(
    r"💰|升級要|確定先至扣資源|按「確定放置」後才扣除資源|\d+\s*(?:金幣|木材|磚|玻璃|齒輪|寶石)"
)


def _playwright_unavailable_reason():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright package not installed"
    try:
        with sync_playwright() as playwright:
            exe = playwright.chromium.executable_path
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
        points=800,
        experience=40,
    )
    db = connect_db(dst)
    def_row = db.execute(
        "SELECT id FROM building_defs WHERE name=?",
        (BUILDING_NAME,),
    ).fetchone()
    db.close()
    assert def_row, BUILDING_NAME
    building_id = insert_building(
        dst,
        kid["id"],
        def_row["id"],
        level=2,
        stored=1,
        cell_x=20,
        cell_y=12,
    )
    backend.DB_PATH = old
    return {"kid_id": kid["id"], "building_id": building_id}


@pytest.fixture(scope="session")
def warehouse_db(tmp_path_factory):
    dst = str(tmp_path_factory.mktemp("warehouse-db") / "warehouse.db")
    ids = _seed(dst)
    with open(dst + ".ids.json", "w", encoding="utf-8") as handle:
        json.dump(ids, handle)
    return dst


@pytest.fixture(scope="session")
def warehouse_ids(warehouse_db):
    with open(warehouse_db + ".ids.json", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def base_url(warehouse_db):
    port = _free_port()
    log_path = warehouse_db + ".server.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(REPO, "tests", "_run_server.py"), warehouse_db, str(port)],
        cwd=REPO,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**os.environ, "KIDS_TOWN_SECRET_KEY": "warehouse-e2e-secret"},
    )
    if not _wait_port(port, timeout=30):
        logf.flush()
        detail = open(log_path, encoding="utf-8").read()
        proc.kill()
        raise AssertionError(f"warehouse e2e server failed on {port}:\n{detail}")
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


def _submit_login(page):
    page.locator("#loginUsername").fill(KID_USERNAME)
    page.locator("#loginPassword").fill(TEST_KID_PIN)
    page.get_by_role("button", name="🚪 登入").click()
    page.locator("#app").wait_for(state="visible", timeout=8000)
    page.locator("#loginScreen").wait_for(state="hidden", timeout=8000)


def _login(page, base_url):
    page.goto(f"{base_url}/kids/")
    _submit_login(page)
    page.locator("#village .cell-btn").first.wait_for(state="attached", timeout=8000)


def _resume_town_after_reload(page):
    """Reload, then log in again when the login wall is showing.

    main has no session restore, so a reload returns to #loginScreen.
    The check is the town after the kid is back in, not that the cookie
    kept the wall hidden.
    """
    page.reload()
    page.wait_for_function(
        """() => {
          const login = document.getElementById('loginScreen');
          const app = document.getElementById('app');
          if (!login || !app) return false;
          const shown = (el) => {
            const cs = getComputedStyle(el);
            const box = el.getBoundingClientRect();
            return cs.display !== 'none' && cs.visibility !== 'hidden'
              && box.width > 1 && box.height > 1;
          };
          return shown(login) || shown(app);
        }""",
        timeout=8000,
    )
    login_on = page.locator("#loginScreen").evaluate(
        """el => {
          const cs = getComputedStyle(el);
          const box = el.getBoundingClientRect();
          return cs.display !== 'none' && cs.visibility !== 'hidden'
            && box.width > 1 && box.height > 1;
        }"""
    )
    if login_on:
        _submit_login(page)
    page.locator("#loginScreen").wait_for(state="hidden", timeout=8000)
    page.locator("#app").wait_for(state="visible", timeout=8000)
    page.locator("#townMap").wait_for(state="visible", timeout=8000)
    page.locator("#ktFooter").wait_for(state="visible", timeout=8000)


def _open_store(page):
    drawer = page.locator("#dr")
    if not drawer.evaluate("el => el.classList.contains('o')"):
        page.get_by_role("button", name="☰").click()
        page.locator("#dr.o").wait_for(state="visible", timeout=8000)
    page.locator("#dr").get_by_role("button", name=re.compile(r"存倉")).click()
    page.locator("#tab-store.active").wait_for(state="visible", timeout=8000)
    page.locator("#storedBuildings").wait_for(state="visible", timeout=8000)


def _decode_png(data):
    """8-bit non-interlaced PNG → (width, height, channels, raw rows)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("footer capture is not a PNG")
    pos = 8
    width = height = color_type = None
    idat = b""
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
            if bit_depth != 8 or color_type not in (2, 6):
                raise AssertionError(f"unsupported footer PNG {bit_depth=} {color_type=}")
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
    channels = 4 if color_type == 6 else 3
    raw = zlib.decompress(idat)
    stride = width * channels
    rows = []
    index = 0
    prev = bytearray(stride)

    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

    for _y in range(height):
        filt = raw[index]
        index += 1
        row = bytearray(raw[index:index + stride])
        index += stride
        if filt == 1:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                row[x] = (row[x] + left) & 255
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 255
        elif filt == 3:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 255
        elif filt == 4:
            for x in range(stride):
                a = row[x - channels] if x >= channels else 0
                b = prev[x]
                c = prev[x - channels] if x >= channels else 0
                row[x] = (row[x] + paeth(a, b, c)) & 255
        elif filt != 0:
            raise AssertionError(f"unsupported PNG filter {filt}")
        prev = row
        rows.append(bytes(row))
    return width, height, channels, b"".join(rows)


def _rgb_channel_diff(left, right):
    """Sum of absolute RGB channel differences. Alpha is ignored."""
    lw, lh, lc, lraw = _decode_png(left)
    rw, rh, rc, rraw = _decode_png(right)
    if (lw, lh) != (rw, rh):
        return None, f"size {lw}x{lh} vs {rw}x{rh}"
    total = 0
    for i in range(lw * lh):
        lb = i * lc
        rb = i * rc
        total += abs(lraw[lb] - rraw[rb]) + abs(lraw[lb + 1] - rraw[rb + 1]) + abs(lraw[lb + 2] - rraw[rb + 2])
    return total, f"{lw}x{lh}"


def _footer_png(page):
    page.locator("#ktFooter").wait_for(state="visible", timeout=8000)
    page.wait_for_function(
        "() => document.querySelectorAll('#ktFooter .kt-footer-tab.has-icon').length >= 5",
        timeout=8000,
    )
    return page.locator("#ktFooter").screenshot(animations="disabled")


_FOOTER_STRUCTURE_JS = r"""
() => {
  const root = document.querySelector("#ktFooter");
  if (!root) return null;
  function roundHalf(n) {
    return Math.round(n * 2) / 2;
  }
  function takesBox(el) {
    return el.id === "ktFooter"
      || el.classList.contains("kt-footer-tab")
      || el.classList.contains("kt-footer-icon")
      || el.classList.contains("kt-footer-icon-wrap");
  }
  function pathOf(el) {
    const parts = [];
    let cur = el;
    while (cur && cur !== root) {
      const parent = cur.parentElement;
      const idx = parent ? Array.prototype.indexOf.call(parent.children, cur) : 0;
      parts.push(cur.tagName.toLowerCase() + "[" + idx + "]");
      cur = parent;
    }
    parts.push("#ktFooter");
    return parts.reverse().join(">");
  }
  const clone = root.cloneNode(true);
  clone.querySelectorAll("[src]").forEach((img) => {
    const raw = img.getAttribute("src") || "";
    try {
      const url = new URL(raw, location.href);
      img.setAttribute("src", url.pathname + url.search);
    } catch (err) {}
  });
  const html = clone.outerHTML.replace(/>\s+</g, "><").trim();
  const nodes = [root].concat(Array.from(root.querySelectorAll("*")));
  const items = nodes.map((el) => {
    const cs = getComputedStyle(el);
    const item = {
      path: pathOf(el),
      display: cs.display,
      position: cs.position,
      fontFamily: cs.fontFamily,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      lineHeight: cs.lineHeight,
      color: cs.color,
      backgroundColor: cs.backgroundColor,
      borderTop: cs.borderTop,
      borderRight: cs.borderRight,
      borderBottom: cs.borderBottom,
      borderLeft: cs.borderLeft,
      paddingTop: cs.paddingTop,
      paddingRight: cs.paddingRight,
      paddingBottom: cs.paddingBottom,
      paddingLeft: cs.paddingLeft,
      marginTop: cs.marginTop,
      marginRight: cs.marginRight,
      marginBottom: cs.marginBottom,
      marginLeft: cs.marginLeft,
      gap: cs.gap,
      zIndex: cs.zIndex,
      opacity: cs.opacity,
      transform: cs.transform,
      visibility: cs.visibility,
      pointerEvents: cs.pointerEvents
    };
    if (takesBox(el)) {
      const box = el.getBoundingClientRect();
      item.box = { w: roundHalf(box.width), h: roundHalf(box.height) };
    }
    return item;
  });
  return { html: html, nodes: items };
}
"""


def _footer_structure(page):
    _footer_png(page)
    payload = page.evaluate(_FOOTER_STRUCTURE_JS)
    assert payload and payload.get("html"), "TC-FE-WAREHOUSE-UNSTORE: #ktFooter is missing"
    payload["html_sha256"] = hashlib.sha256(payload["html"].encode("utf-8")).hexdigest()
    return payload


def _footer_structure_diff(live, expected):
    problems = []
    if live.get("html_sha256") != expected.get("html_sha256"):
        problems.append(
            "outerHTML sha256 "
            f"{live.get('html_sha256')} != {expected.get('html_sha256')}"
        )
    if live.get("html") != expected.get("html"):
        problems.append("normalized #ktFooter outerHTML differs from main")
    live_nodes = live.get("nodes") or []
    exp_nodes = expected.get("nodes") or []
    if len(live_nodes) != len(exp_nodes):
        problems.append(f"descendant count {len(live_nodes)} != {len(exp_nodes)}")
    for index, (got, want) in enumerate(zip(live_nodes, exp_nodes)):
        if got != want:
            problems.append(f"node[{index}] {got.get('path')}: {got} != {want}")
            if len(problems) >= 4:
                break
    return problems


def _assert_footer_structure(page, when):
    live = _footer_structure(page)
    if os.environ.get("WAREHOUSE_DUMP_FOOTER") == "1":
        os.makedirs(os.path.dirname(FOOTER_STRUCTURE), exist_ok=True)
        with open(FOOTER_STRUCTURE, "w", encoding="utf-8") as handle:
            json.dump(live, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    assert os.path.isfile(FOOTER_STRUCTURE), (
        "TC-FE-WAREHOUSE-UNSTORE: missing tests/fixtures/kt_footer_main.json "
        "(#ktFooter structure captured from main)."
    )
    with open(FOOTER_STRUCTURE, encoding="utf-8") as handle:
        expected = json.load(handle)
    problems = _footer_structure_diff(live, expected)
    assert not problems, (
        "TC-FE-WAREHOUSE-UNSTORE: #ktFooter structure must match main "
        f"{when}. " + " | ".join(problems)
    )


def _assert_footer_pixels(before, after, when):
    diff, detail = _rgb_channel_diff(before, after)
    assert diff == 0, (
        "TC-FE-WAREHOUSE-UNSTORE: #ktFooter RGB pixel diff must be 0 "
        f"{when}. Actual diff={diff} ({detail}). "
        "The two screenshots are from this same run."
    )


def _arm_placement_bar_watch(page):
    page.evaluate(
        """() => {
          window.__ktBarBad = false;
          const bar = document.getElementById('placementBar');
          if (!bar) return;
          const note = () => {
            const cs = getComputedStyle(bar);
            const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
            if (bar.classList.contains('active') || visible) window.__ktBarBad = true;
          };
          note();
          new MutationObserver(note).observe(bar, {attributes: true, attributeFilter: ['class', 'style']});
        }"""
    )


def _placement_surface(page):
    return page.evaluate(
        """() => {
          const bar = document.getElementById('placementBar');
          const map = document.getElementById('townMap');
          const cs = bar ? getComputedStyle(bar) : null;
          const mapCs = map ? getComputedStyle(map) : null;
          const mapBox = map ? map.getBoundingClientRect() : null;
          return {
            barActive: !!(bar && bar.classList.contains('active')),
            barVisible: !!(cs && cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0'),
            mapVisible: !!(map && mapCs && mapCs.visibility !== 'hidden' && mapCs.display !== 'none'
              && mapBox && mapBox.width > 1 && mapBox.height > 1),
            sawBar: !!window.__ktBarBad,
            scene: map ? (map.getAttribute('aria-label') || '') : '',
            mapClass: map ? map.className : ''
          };
        }"""
    )


def _assert_pick_surface(page, when):
    surface = _placement_surface(page)
    assert surface["mapVisible"], (
        "TC-FE-WAREHOUSE-UNSTORE: while picking, #townMap must be the visible 8×8 map "
        f"({when}). Actual {surface}."
    )
    assert not surface["barActive"] and not surface["barVisible"] and not surface["sawBar"], (
        "TC-FE-WAREHOUSE-UNSTORE: #placementBar must not be .active or visible at any point "
        f"({when}). Actual {surface}. "
        "#placementBar.active hides #townMap and shows the legacy 24×16 grid."
    )
    assert page.locator(".valid-plot").count() == 0, (
        "TC-FE-WAREHOUSE-UNSTORE: 取出 must not show .valid-plot."
    )


def _place_chrome_text(page):
    return page.evaluate(
        """() => {
          const parts = [];
          for (const sel of ['#uxPlaceBar', '#placeStatus', '#btnUxConfirm', '#readyBar', '#readyStatus']) {
            const el = document.querySelector(sel);
            if (!el || el.hidden) continue;
            const cs = getComputedStyle(el);
            const box = el.getBoundingClientRect();
            if (cs.display === 'none' || cs.visibility === 'hidden' || box.width < 1 || box.height < 1) continue;
            parts.push(el.innerText || '');
          }
          for (const el of document.querySelectorAll('#uxPlaceBar .pal-cost, #townMap .pal-cost, #sheetCost')) {
            const cs = getComputedStyle(el);
            const box = el.getBoundingClientRect();
            if (el.hidden || cs.display === 'none' || cs.visibility === 'hidden' || box.width < 1 || box.height < 1) continue;
            parts.push(el.innerText || '');
          }
          const ghost = document.querySelector('#townMap .pad.is-preview .ghost, #townMap .ghost');
          const pad = ghost && ghost.closest('.pad');
          if (pad) parts.push(pad.innerText || '');
          return parts.join('\\n');
        }"""
    )


def _building_row(db_path, building_id):
    db = connect_db(db_path)
    row = db.execute(
        """
        SELECT b.id, b.level, b.cell_x, b.cell_y, COALESCE(b.stored, 0) AS stored, bd.name
          FROM buildings b
          JOIN building_defs bd ON bd.id = b.def_id
         WHERE b.id=?
        """,
        (building_id,),
    ).fetchone()
    db.close()
    return dict(row) if row else None


@pytest.mark.case_id("TC-FE-WAREHOUSE-UNSTORE")
def test_storage_takeout_places_on_8x8_and_persists(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-WAREHOUSE-UNSTORE 存倉「取出」走新建造同一條四場景路。

    場景 2 在 #townMap 揀空格 → 場景 3 ghost 與「確定放置」，不顯示價錢。
    落地後 [data-town-fx="place"] 出現（與新建造 celebrate("place") 相同）。
    main 的清單是「按此放置」，會打開 #placementBar。
    """
    kid_id = warehouse_ids["kid_id"]
    building_id = warehouse_ids["building_id"]
    _login(page, base_url)
    pads = page.locator("#village .cell-btn").count()
    assert pads == 64, f"expected 64 pads on the 8×8 map before takeout, got {pads}"
    _assert_footer_structure(page, "before the takeout flow")
    footer_before = _footer_png(page)
    _assert_footer_pixels(
        footer_before,
        _footer_png(page),
        "between two captures before the takeout flow",
    )
    points_before = get_kid_points(warehouse_db, kid_id)
    mats_before = inventory_map(warehouse_db, kid_id)
    _arm_placement_bar_watch(page)
    _open_store(page)
    store_text = page.locator("#storedBuildings").inner_text()
    cards = page.locator("#storedBuildings .build-card").count()
    takeout = page.locator('[data-testid="warehouse-takeout"]')
    named = page.locator("#tab-store").get_by_role("button", name="取出")
    count_node = page.locator('[data-testid="warehouse-count"]')
    takeout_n = takeout.count()
    named_n = named.count()
    assert takeout_n + named_n >= 1, (
        "TC-FE-WAREHOUSE-UNSTORE: expected the storage list to offer 取出 "
        "(data-testid=warehouse-takeout, or a button whose accessible name is 取出) "
        f"with bounding-box height >= 44px for stored {BUILDING_NAME} Lv.2. "
        "The flow is the new-build path: Scene 2 pick on the visible 8×8 #townMap "
        f"第 {CELL_COL} 欄第 {CELL_ROW} 行 (DB cell {CELL_X},{CELL_Y}), "
        "#btnToScene3 「選擇位置」 when that step is shown, then Scene 3 ghost "
        "(#uxPlaceBar, #placeStatus, #btnUxConfirm 「確定放置」) with no price, "
        "then [data-town-fx=\"place\"], the building on that cell, storage count 1 → 0, "
        "no gold/material change, the same placement after reload, and #ktFooter "
        "pixels unchanged within this run. #placementBar must never be .active or visible. "
        f"Actual: takeout controls={takeout_n}, buttons named 取出={named_n}, "
        f"warehouse-count present={count_node.count()}, "
        f"legacy cards={cards}, list text={store_text!r}. "
        "The existing card calls startUnstoreBuilding (index.html), which adds "
        "#placementBar.active and hides #townMap (town-four-scene.css), so the kid "
        "picks a 24×16 .valid-plot instead of an 8×8 cell. "
        f"Seeded row id {building_id} is still stored; points stayed {points_before}."
    )

    control = takeout.first if takeout_n else named.first
    box = control.bounding_box()
    assert box and box["height"] >= 44, (
        "TC-FE-WAREHOUSE-UNSTORE: 取出 bounding-box height must be >= 44px. "
        f"Actual box={box}."
    )
    control.click()
    _assert_pick_surface(page, "after 取出")
    pad = page.locator("#townMap").get_by_role(
        "button",
        name=re.compile(rf"第\s*{CELL_COL}\s*欄第\s*{CELL_ROW}\s*行"),
    )
    assert pad.count() > 0, f"missing 8×8 pad 第 {CELL_COL} 欄第 {CELL_ROW} 行 inside #townMap"
    pad_box = pad.first.bounding_box()
    map_box = page.locator("#townMap").bounding_box()
    assert pad_box and map_box and (
        pad_box["x"] >= map_box["x"] - 1
        and pad_box["y"] >= map_box["y"] - 1
        and pad_box["x"] + pad_box["width"] <= map_box["x"] + map_box["width"] + 1
        and pad_box["y"] + pad_box["height"] <= map_box["y"] + map_box["height"] + 1
    ), (
        "TC-FE-WAREHOUSE-UNSTORE: the tap target must be a cell on the visible #townMap. "
        f"pad={pad_box} map={map_box}."
    )
    pad.first.click()
    _assert_pick_surface(page, "while picking the cell")
    _assert_footer_pixels(footer_before, _footer_png(page), "while picking a cell")
    advance = page.locator("#btnToScene3")
    if advance.count() and advance.first.is_visible() and advance.first.is_enabled():
        advance.first.click()
    _assert_pick_surface(page, "on the ghost confirm step")
    page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
    page.locator("#townMap .ghost").filter(visible=True).first.wait_for(state="visible", timeout=8000)
    chrome = _place_chrome_text(page)
    assert not PRICE_RE.search(chrome), (
        "TC-FE-WAREHOUSE-UNSTORE: unstore ghost/confirm must not show a price or cost. "
        f"Actual place chrome={chrome!r}."
    )
    confirm = page.locator("#btnUxConfirm")
    assert confirm.count() and confirm.first.is_visible() and confirm.first.is_enabled(), (
        "TC-FE-WAREHOUSE-UNSTORE: Scene 3 must show enabled #btnUxConfirm 「確定放置」."
    )
    with page.expect_response(
        lambda resp: resp.request.method == "POST" and "/unstored" in resp.url,
        timeout=8000,
    ) as info:
        confirm.first.click()
    assert info.value.status in (200, 201), (
        f"unstored HTTP {info.value.status}: {info.value.text()[:300]}"
    )
    page.locator('[data-town-fx="place"]').first.wait_for(state="attached", timeout=4000)
    _assert_pick_surface(page, "after confirm")
    page.locator("#townMap .cap", has_text=BUILDING_NAME).first.wait_for(
        state="visible", timeout=8000
    )
    _open_store(page)
    if count_node.count():
        after_count = int((count_node.first.inner_text() or "0").strip() or "0")
    else:
        after_count = page.locator('[data-testid="warehouse-takeout"]').count()
        if after_count == 0:
            after_count = page.locator("#tab-store").get_by_role("button", name="取出").count()
    assert after_count == 0, (
        f"expected storage count 0 after takeout, got {after_count}. "
        f"List text={page.locator('#storedBuildings').inner_text()!r}"
    )
    _resume_town_after_reload(page)
    page.locator("#townMap .cap", has_text=BUILDING_NAME).first.wait_for(
        state="visible", timeout=8000
    )
    label = page.locator("#townMap").get_by_role(
        "button",
        name=re.compile(rf"第\s*{CELL_COL}\s*欄第\s*{CELL_ROW}\s*行.*{BUILDING_NAME}"),
    )
    assert label.count() > 0, (
        f"after reload, 第 {CELL_COL} 欄第 {CELL_ROW} 行 should name {BUILDING_NAME}"
    )
    row = _building_row(warehouse_db, building_id)
    assert row["stored"] == 0, row
    assert (row["cell_x"], row["cell_y"]) == (CELL_X, CELL_Y), row
    assert row["level"] == 2, row
    assert get_kid_points(warehouse_db, kid_id) == points_before
    assert inventory_map(warehouse_db, kid_id) == mats_before
    _assert_footer_structure(page, "after the takeout flow")
    _assert_footer_pixels(footer_before, _footer_png(page), "after the takeout flow")


@pytest.mark.case_id("TC-FE-WAREHOUSE-CARD")
def test_storage_card_shows_name_level_and_takeout_only(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-WAREHOUSE-CARD 存倉卡片只顯示名稱、等級和「取出」。

    「按此放置」不得出現。main 的卡片仍有這句。
    """
    kid_id = warehouse_ids["kid_id"]
    stored = _building_row(warehouse_db, warehouse_ids["building_id"])
    if not stored or stored["stored"] != 1:
        from tests.factories import insert_building

        db = connect_db(warehouse_db)
        def_row = db.execute(
            "SELECT id FROM building_defs WHERE name=?",
            ("農場",),
        ).fetchone()
        db.close()
        insert_building(
            warehouse_db,
            kid_id,
            def_row["id"],
            level=1,
            stored=1,
            cell_x=18,
            cell_y=10,
        )
    _login(page, base_url)
    _open_store(page)
    store_text = page.locator("#storedBuildings").inner_text()
    takeout_n = page.locator('[data-testid="warehouse-takeout"]').count()
    named_n = page.locator("#tab-store").get_by_role("button", name="取出").count()
    problems = []
    if "按此放置" in store_text:
        problems.append(
            "card text still contains 按此放置; the card must show the building name, "
            "level, and 取出 only"
        )
    if takeout_n + named_n < 1:
        problems.append("missing 取出 button on the storage card")
    if "Lv" not in store_text:
        problems.append(f"card text has no level; text={store_text!r}")
    assert not problems, (
        "TC-FE-WAREHOUSE-CARD: expected name, level, and 取出 only. "
        f"Actual list text={store_text!r}. " + " | ".join(problems)
    )


MAP_N = 8
FOOTPRINT = 2
UNSTORE_SCENE2_HINT = "請點選空地，放回「圖書館」。不扣除金幣和材料。"
IDLE_SCENE2_HINT = "請點選金色空地，或打開清單選擇要興建的建築物。"
EMPTY_PICKED_HINT = "已選擇空地。請打開清單，選擇要興建的建築物。"
GYM_PICKED_HINT = "已選擇「健身室」和這個位置。"
SCENE3_CHARGE_HINT = "按「確定放置」後才扣除資源；取消不會扣除。"
OLD_IDLE_SCENE2_HINT = "點金色空地，或者打開清單揀一座未起嘅屋。"
OLD_EMPTY_PICKED_HINT = "已揀空地。打開清單，揀一座未起嘅屋。"
OLD_GYM_PICKED_HINT = "已揀「健身室」同呢格空地。"
OLD_SCENE3_CHARGE_HINT = "確定先至扣資源。取消唔會扣。"
FULL_TOWN_TOAST = "城鎮沒有空位，請先收起或移動其他建築。"
CANNOT_FIT_TOAST = "這個位置放不下這座建築物。"
OCCUPIED_TOAST = "這個位置已經有建築物。"
OCCUPIED_RED = "該位置已被建築物佔用"
CANCEL_TOAST = "已取消，資源未扣除"
INFO_BG = "rgb(107, 79, 42)"
INFO_FG = "rgb(255, 248, 231)"
# Placement copy only. mocks/ and other screens stay out. Backlog lines are skipped
# inside these files so an upgrade/savings phrase does not fail this scan.
# 「㨒」 in the coordinator note is U+3A12; the file uses 「㩒」 U+3A52. The scan
# matches the shared tails 「要放返出嚟」 and 「入去揀建築物放返」 so either glyph fails.
COPY_SOURCE_FILES = (
    "index.html",
    "town-four-scene.js",
    "town-four-scene.css",
    "backend_v2.py",
    "service-worker.js",
)
BACKLOG_LINE_MARKERS = (
    "打唔中",
    "金幣唔夠",
    "確定先至扣，取消只關",
    "領唔到",
    "再點一塊金色空地",
    "撳「升級」會彈出確認窗",
    "升級唔到",
    "先揀位置，再按「確認」建造",
    "㩒此放置",
    "㨒此放置",
    "選擇要起嘅建築",
)
OLD_COPY_FRAGMENTS = (
    "未起嘅屋",
    "同呢格空地",
    "確定先至扣資源",
    "撳一下就揀",
    "已經有屋，唔可以放",
    "撳一下就搬去呢格",
    "，放返",
    "想喺呢度起屋",
    "唔可以放",
    "放唔返",
    "起唔到",
    "存倉吉咗",
    "要放返出嚟",
    "入去揀建築物放返",
    "呢格",
    "已起",
    "未起",
    "確定收起呢棟",
    "睇地圖",
)
COLLOQUIAL_BITS = ("喺存倉", "用存倉放返", "唔使再扣資源")
WAREHOUSE_BAR_TEXT = "📍 選擇位置放置倉庫建築"

_GOLD_CELLS_JS = r"""
() => {
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
}
"""

_BAR_JS = r"""
() => {
  const bar = document.getElementById('placementBar');
  if (!bar) return { missing: true };
  const cs = getComputedStyle(bar);
  const box = bar.getBoundingClientRect();
  return {
    active: bar.classList.contains('active'),
    display: cs.display,
    background: cs.backgroundColor,
    width: box.width,
    height: box.height,
    text: bar.innerText || ''
  };
}
"""

_HINT_JS = r"""
() => {
  function shown(el) {
    if (!el || el.hidden) return false;
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden'
      && box.width > 1 && box.height > 1;
  }
  const ready = document.getElementById('readyStatus');
  const place = document.getElementById('placeStatus');
  const map = document.getElementById('townMap');
  return {
    ready: ready ? ready.textContent : '',
    readyOn: shown(ready),
    place: place ? place.textContent : '',
    placeOn: shown(place),
    scene: map ? (map.getAttribute('aria-label') || '') : '',
    back: (document.getElementById('btnUxBack') || {}).textContent || '',
    go: (document.getElementById('btnToScene3') || {}).textContent || ''
  };
}
"""


def _overlaps(origin, other, footprint=FOOTPRINT):
    ax, ay = origin
    bx, by = other
    return not (
        ax + footprint <= bx
        or bx + footprint <= ax
        or ay + footprint <= by
        or by + footprint <= ay
    )


def _legal_origins(occupied):
    max_origin = MAP_N - FOOTPRINT
    return [
        (x, y)
        for y in range(max_origin + 1)
        for x in range(max_origin + 1)
        if not any(_overlaps((x, y), cell) for cell in occupied)
    ]


def _def_id_by_name(db_path, name):
    db = connect_db(db_path)
    row = db.execute("SELECT id, cost_gold, materials FROM building_defs WHERE name=?", (name,)).fetchone()
    db.close()
    assert row, name
    return dict(row)


def _reset_kid(db_path, kid_id, points=800, items=None, buildings=None):
    """Replace this kid's buildings, tiles, inventory, and gold. Session server reads the file."""
    db = connect_db(db_path)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.execute("DELETE FROM town_tiles WHERE kid_id=?", (kid_id,))
    db.execute("DELETE FROM inventory WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    set_kid_points(db_path, kid_id, points)
    if items:
        grant_inventory(db_path, kid_id, items)
    ids = []
    for spec in buildings or []:
        def_row = _def_id_by_name(db_path, spec["name"])
        ids.append(insert_building(
            db_path,
            kid_id,
            def_row["id"],
            level=spec.get("level", 1),
            stored=spec.get("stored", 0),
            cell_x=spec.get("cell_x", 0),
            cell_y=spec.get("cell_y", 0),
        ))
    return ids


def _hint(page):
    return page.evaluate(_HINT_JS)


def _visible_text(page):
    return page.locator("body").inner_text()


def _colloquial_product_hits():
    """Old placement fragments in the warehouse/build files.

    tests/, docs/, and mocks/ are out of scope. Upgrade, savings, and the
    「再點一塊金色空地」 line are backlog: a line that contains one of those
    markers is not scanned.
    """
    hits = []
    for name in COPY_SOURCE_FILES:
        path = os.path.join(REPO, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                if any(marker in line for marker in BACKLOG_LINE_MARKERS):
                    continue
                for bit in OLD_COPY_FRAGMENTS:
                    if bit in line:
                        hits.append(f"{name}:{lineno} contains {bit}")
    return hits


def _colloquial_visible(problems, where, text):
    for bit in COLLOQUIAL_BITS:
        if bit in (text or ""):
            problems.append(f"{where} still shows {bit}")


def _aria_labels(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('[aria-label]')]
          .map((el) => el.getAttribute('aria-label') || '')"""
    )


def _gold_cells(page):
    raw = page.evaluate(_GOLD_CELLS_JS)
    return sorted((item[0], item[1]) for item in raw)


def _click_cell(page, cell_x, cell_y):
    col = cell_x + 1
    row = cell_y + 1
    pad = page.locator("#townMap").get_by_role(
        "button",
        name=re.compile(rf"第\s*{col}\s*欄第\s*{row}\s*行"),
    )
    assert pad.count() > 0, f"missing pad 第 {col} 欄第 {row} 行"
    pad.first.click()


def _enter_new_build_scene2(page):
    page.locator("#btnBuild").click()
    page.locator("#readyBar").wait_for(state="visible", timeout=8000)
    page.locator("#townMap").wait_for(state="visible", timeout=8000)


def _toast_state(page):
    return page.evaluate(
        """() => {
          const el = document.getElementById('toast');
          if (!el) return { missing: true };
          const cs = getComputedStyle(el);
          return {
            text: el.textContent || '',
            className: el.className || '',
            display: el.style.display || '',
            background: cs.backgroundColor,
            color: cs.color
          };
        }"""
    )


def _open_takeout_scene2(page):
    """Press 取出. Returns a problem string when the control is missing."""
    _open_store(page)
    takeout = page.locator('[data-testid="warehouse-takeout"]')
    named = page.locator("#tab-store").get_by_role("button", name="取出")
    if takeout.count() == 0 and named.count() == 0:
        return (
            "no 取出 control "
            f"(warehouse-takeout={takeout.count()}, named={named.count()}). "
            f"List={page.locator('#storedBuildings').inner_text()!r}"
        )
    control = takeout.first if takeout.count() else named.first
    control.click()
    page.locator("#townMap").wait_for(state="visible", timeout=8000)
    return None


@pytest.mark.case_id("TC-FE-WAREHOUSE-CARD-BODY")
def test_storage_card_body_does_not_start_unstore(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-WAREHOUSE-CARD-BODY 卡片本體不可取出。只有「取出」進入場景 2。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        buildings=[{"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12}],
    )
    _login(page, base_url)
    _arm_placement_bar_watch(page)
    _open_store(page)
    page.evaluate(
        """() => {
          window.__ktUnstoreCalls = 0;
          const orig = window.startUnstoreBuilding;
          window.startUnstoreBuilding = function () {
            window.__ktUnstoreCalls += 1;
            if (typeof orig === 'function') return orig.apply(this, arguments);
          };
        }"""
    )
    card = page.locator("#storedBuildings .build-card").first
    assert card.count() == 1, page.locator("#storedBuildings").inner_text()
    card_meta = card.evaluate(
        """el => {
          const name = [...el.querySelectorAll('div')].find((node) => (node.textContent || '').includes('圖書館'));
          const probe = name || el;
          return {
            onclick: el.getAttribute('onclick'),
            cursor: getComputedStyle(el).cursor,
            nameOnclick: probe.getAttribute('onclick'),
            nameCursor: getComputedStyle(probe).cursor,
            html: el.outerHTML
          };
        }"""
    )
    name = card.locator("div").filter(has_text=BUILDING_NAME).first
    name.click()
    page.wait_for_timeout(300)
    calls = page.evaluate("() => window.__ktUnstoreCalls || 0")
    bar = page.evaluate(_BAR_JS)
    surface = _placement_surface(page)
    problems = []
    if calls:
        problems.append(f"clicking the card body called startUnstoreBuilding {calls} time(s)")
    if card_meta.get("onclick"):
        problems.append(f"card has onclick={card_meta['onclick']!r}")
    if card_meta.get("cursor") == "pointer":
        problems.append("card computed cursor is pointer")
    if bar.get("active") or surface.get("barActive") or surface.get("sawBar"):
        problems.append(f"#placementBar became active {bar}")
    if bar.get("width", 0) > 1 or bar.get("height", 0) > 1 or bar.get("display") != "none":
        problems.append(
            "#placementBar must stay display:none and 0×0. "
            f"display={bar.get('display')} box={bar.get('width')}×{bar.get('height')} "
            f"background={bar.get('background')}"
        )
    if page.locator(".valid-plot").count():
        problems.append(".valid-plot appeared")
    visible = _visible_text(page)
    if WAREHOUSE_BAR_TEXT in visible:
        problems.append(f"visible text contains {WAREHOUSE_BAR_TEXT}")
    if not problems:
        opened = _open_takeout_scene2(page)
        if opened:
            problems.append("取出 did not open Scene 2: " + opened)
        else:
            scene = _hint(page)
            if "場景 2" not in scene["scene"]:
                problems.append(f"取出 did not land on Scene 2. Actual {scene}")
            bar_after = page.evaluate(_BAR_JS)
            if bar_after.get("active") or bar_after.get("display") != "none":
                problems.append(f"取出 activated #placementBar {bar_after}")
    assert not problems, (
        "TC-FE-WAREHOUSE-CARD-BODY: the card body must not start unstore. "
        f"html={card_meta.get('html')!r}. " + " | ".join(problems)
    )


@pytest.mark.case_id("TC-FE-WAREHOUSE-SCENE2-LEGAL")
def test_unstore_scene2_gold_matches_legal_origins(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-WAREHOUSE-SCENE2-LEGAL 取出場景 2 的金色格等於合法原點。"""
    kid_id = warehouse_ids["kid_id"]
    placed = ((0, 0), (4, 4))
    _reset_kid(
        warehouse_db,
        kid_id,
        buildings=[
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
            {"name": "健身室", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": "農場", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 4},
        ],
    )
    before_points = get_kid_points(warehouse_db, kid_id)
    before_items = inventory_map(warehouse_db, kid_id)
    _login(page, base_url)
    _arm_placement_bar_watch(page)
    opened = _open_takeout_scene2(page)
    assert opened is None, (
        "TC-FE-WAREHOUSE-SCENE2-LEGAL: 取出 must open unstore Scene 2 on #townMap. " + opened
    )
    scene = _hint(page)
    assert "場景 2" in scene["scene"], f"expected unstore Scene 2, got {scene}"
    legal = set(_legal_origins(placed))
    gold_list = _gold_cells(page)
    gold = set(gold_list)
    problems = []
    if len(gold_list) != len(gold):
        dupes = sorted({cell for cell in gold_list if gold_list.count(cell) > 1})
        problems.append(f"duplicate gold cells {dupes}")
    if gold != legal:
        extra = sorted(gold - legal)
        missing = sorted(legal - gold)
        problems.append(
            f"gold cells != legal origins as sets. gold={len(gold)} legal={len(legal)} "
            f"extra={extra} missing={missing}"
        )
    _click_cell(page, 0, 0)
    try:
        page.wait_for_function(
            """() => {
              const el = document.getElementById('toast');
              return !!(el && el.style.display === 'block' && (el.textContent || '').length);
            }""",
            timeout=1500,
        )
    except Exception:
        pass
    toast = _toast_state(page)
    if toast.get("text") != "這個位置已經有建築物。":
        problems.append(f"toast text {toast.get('text')!r}, expected 這個位置已經有建築物。")
    classes = set((toast.get("className") or "").split())
    if "info" not in classes or "error" in classes:
        problems.append(f"toast class {toast.get('className')!r}, expected info and not error")
    if toast.get("background") != "rgb(107, 79, 42)":
        problems.append(f"toast background {toast.get('background')!r}, expected rgb(107, 79, 42)")
    if get_kid_points(warehouse_db, kid_id) != before_points or inventory_map(warehouse_db, kid_id) != before_items:
        problems.append(
            "resources changed "
            f"points {before_points}->{get_kid_points(warehouse_db, kid_id)} "
            f"items {before_items}->{inventory_map(warehouse_db, kid_id)}"
        )
    assert not problems, "TC-FE-WAREHOUSE-SCENE2-LEGAL: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-WAREHOUSE-SCENE3-CANCEL")
def test_unstore_cancel_returns_to_unstore_scene2(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-WAREHOUSE-SCENE3-CANCEL 取消預覽回到取出場景 2，不是普通建造。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        buildings=[{"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12}],
    )
    before_points = get_kid_points(warehouse_db, kid_id)
    before_items = inventory_map(warehouse_db, kid_id)
    _login(page, base_url)
    _arm_placement_bar_watch(page)
    opened = _open_takeout_scene2(page)
    assert opened is None, (
        "TC-FE-WAREHOUSE-SCENE3-CANCEL: 取出 must open unstore Scene 2. " + opened
    )
    _click_cell(page, 0, 0)
    advance = page.locator("#btnToScene3")
    if advance.count() and advance.first.is_visible() and advance.first.is_enabled():
        advance.first.click()
    page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
    page.locator("#btnUxCancel").click()
    page.locator("#readyStatus").wait_for(state="visible", timeout=8000)
    hint = _hint(page)
    visible = _visible_text(page)
    bar = page.evaluate(_BAR_JS)
    problems = []
    if hint["ready"] != UNSTORE_SCENE2_HINT:
        problems.append(
            f"#readyStatus {hint['ready']!r}, expected {UNSTORE_SCENE2_HINT!r}. "
            f"placeStatus={hint['place']!r} scene={hint['scene']!r}"
        )
    if "場景 2" not in hint["scene"]:
        problems.append(f"expected Scene 2 after cancel, got {hint['scene']!r}")
    for bit in COLLOQUIAL_BITS:
        if bit in visible:
            problems.append(f"visible text still contains {bit}")
    new_build_bits = (
        IDLE_SCENE2_HINT,
        OLD_IDLE_SCENE2_HINT,
        "已選擇「圖書館」和這個位置。",
        "已揀「圖書館」同呢格空地。",
        EMPTY_PICKED_HINT,
        OLD_EMPTY_PICKED_HINT,
    )
    if any(bit in visible for bit in new_build_bits):
        problems.append("cancel returned to the normal new-build hint")
    if bar.get("active") or bar.get("display") != "none":
        problems.append(f"#placementBar active after cancel {bar}")
    if get_kid_points(warehouse_db, kid_id) != before_points or inventory_map(warehouse_db, kid_id) != before_items:
        problems.append("resources changed on cancel")
    assert not problems, "TC-FE-WAREHOUSE-SCENE3-CANCEL: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-BUILD-SCENE2-NOREGRESS")
def test_new_build_scene2_still_places_and_charges_once(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-BUILD-SCENE2-NOREGRESS 普通新建造場景 2 仍可放置並只扣一次目錄價。

    點選的格子兩邊索引都不超過 6。不用索引 7。
    """
    kid_id = warehouse_ids["kid_id"]
    gym = _def_id_by_name(warehouse_db, "健身室")
    materials = json.loads(gym["materials"] or "{}")
    assert gym["cost_gold"] == 200, gym
    assert materials == {"wood": 10, "brick": 5}, materials
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        items={"wood": 10, "brick": 5},
        buildings=[],
    )
    before_points = get_kid_points(warehouse_db, kid_id)
    before_items = inventory_map(warehouse_db, kid_id)
    _login(page, base_url)
    _enter_new_build_scene2(page)
    idle_text = _hint(page)["ready"]
    gold = _gold_cells(page)
    legal_gold = [cell for cell in gold if cell[0] <= MAP_N - FOOTPRINT and cell[1] <= MAP_N - FOOTPRINT]
    assert legal_gold, f"new-build Scene 2 has no gold cell with index <= 6. gold={gold}"
    cell_x, cell_y = legal_gold[0]
    assert cell_x <= 6 and cell_y <= 6
    _click_cell(page, cell_x, cell_y)
    page.locator("#listLauncher").click()
    page.locator("#palette").wait_for(state="visible", timeout=8000)
    gym_btn = page.locator("#palette").get_by_role("button", name=re.compile(r"健身室"))
    assert gym_btn.count() > 0, "missing 健身室 in the building list"
    gym_label = gym_btn.first.get_attribute("aria-label") or ""
    unbuilt = ("未興建" in gym_label or "未起" in gym_label) and "已興建" not in gym_label
    if "已起" in gym_label and "未起" not in gym_label and "未興建" not in gym_label:
        unbuilt = False
    assert unbuilt, gym_label
    gym_btn.first.click()
    picked_text = _hint(page)["ready"]
    posts = []

    def _capture(response):
        url = response.url
        if (
            response.request.method == "POST"
            and "/buildings" in url
            and "/unstored" not in url
            and "/move" not in url
            and "/store" not in url
        ):
            posts.append(response)

    page.on("response", _capture)
    page.locator("#btnToScene3").click()
    page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
    charge_text = _hint(page)["place"]
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
    page.wait_for_timeout(400)
    assert len(posts) == 1, [(item.status, item.url) for item in posts]
    assert posted.value.status == 201, f"HTTP {posted.value.status} {posted.value.text()[:300]}"
    after_points = get_kid_points(warehouse_db, kid_id)
    after_items = inventory_map(warehouse_db, kid_id)
    assert after_points == before_points - gym["cost_gold"], (before_points, after_points, gym["cost_gold"])
    for item_type, qty in materials.items():
        assert after_items.get(item_type, 0) == before_items.get(item_type, 0) - qty, (
            item_type, before_items, after_items
        )
    db = connect_db(warehouse_db)
    rows = db.execute(
        """
        SELECT b.cell_x, b.cell_y, b.level, COALESCE(b.stored, 0) AS stored, bd.name
          FROM buildings b JOIN building_defs bd ON bd.id = b.def_id
         WHERE b.kid_id=?
        """,
        (kid_id,),
    ).fetchall()
    db.close()
    assert len(rows) == 1, [dict(row) for row in rows]
    placed = dict(rows[0])
    assert placed["name"] == "健身室" and placed["stored"] == 0 and placed["level"] == 1, placed
    assert (placed["cell_x"], placed["cell_y"]) == (cell_x, cell_y), placed
    copy_problems = []
    if idle_text != IDLE_SCENE2_HINT:
        copy_problems.append(f"#readyStatus {idle_text!r}, expected {IDLE_SCENE2_HINT!r}")
    if picked_text != GYM_PICKED_HINT:
        copy_problems.append(f"picked #readyStatus {picked_text!r}, expected {GYM_PICKED_HINT!r}")
    if charge_text != SCENE3_CHARGE_HINT:
        copy_problems.append(f"#placeStatus {charge_text!r}, expected {SCENE3_CHARGE_HINT!r}")
    assert not copy_problems, "TC-FE-BUILD-SCENE2-NOREGRESS copy: " + " | ".join(copy_problems)




def _wait_toast(page, timeout=1600):
    try:
        page.wait_for_function(
            """() => {
              const el = document.getElementById('toast');
              return !!(el && el.style.display === 'block' && (el.textContent || '').length);
            }""",
            timeout=timeout,
        )
    except Exception:
        pass
    return _toast_state(page)


def _toast_info_problems(toast, expected):
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


def _kid_rows(db_path, kid_id):
    db = connect_db(db_path)
    rows = db.execute(
        """
        SELECT b.id, b.def_id, b.level, b.cell_x, b.cell_y,
               COALESCE(b.stored, 0) AS stored, bd.name
          FROM buildings b JOIN building_defs bd ON bd.id = b.def_id
         WHERE b.kid_id=?
         ORDER BY b.id
        """,
        (kid_id,),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def _resources_same(db_path, kid_id, points, items):
    return get_kid_points(db_path, kid_id) == points and inventory_map(db_path, kid_id) == items


_MARK_GOLD_JS = r"""
() => {
  const cells = [];
  for (const pad of document.querySelectorAll('#townMap .pad')) {
    const mark = pad.querySelector(':scope > .mark');
    if (!mark || mark.hidden) continue;
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
}
"""


def _mark_gold_cells(page):
    raw = page.evaluate(_MARK_GOLD_JS)
    return [(item[0], item[1]) for item in raw]


def _scene_aria(page):
    return page.locator("#townMap").get_attribute("aria-label") or ""


def _full_blockers():
    origins = (
        (0, 0), (2, 0), (5, 0),
        (0, 2), (2, 2), (5, 2),
        (0, 5), (2, 5), (5, 5),
    )
    rows = [
        {"name": "健身室", "level": 1, "stored": 0, "cell_x": x, "cell_y": y}
        for x, y in origins
    ]
    rows.append({"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12})
    return rows


def _relogin(page, base_url):
    page.goto(f"{base_url}/kids/")
    page.wait_for_timeout(400)
    login = page.locator("#loginScreen")
    shown = False
    try:
        shown = login.count() > 0 and login.is_visible()
    except Exception:
        shown = False
    if shown:
        _submit_login(page)
    page.locator("#village .cell-btn").first.wait_for(state="attached", timeout=8000)


def _pick_unbuilt(page, name):
    page.locator("#listLauncher").click()
    page.locator("#palette").wait_for(state="visible", timeout=8000)
    btn = page.locator("#palette").get_by_role("button", name=re.compile(name))
    if btn.count() == 0:
        return None
    btn.first.click()
    return btn.first.get_attribute("aria-label") or ""


@pytest.mark.case_id("TC-FE-WAREHOUSE-COPY-FORMAL")
def test_formal_placement_copy(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-WAREHOUSE-COPY-FORMAL 放置文案改為書面語。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        buildings=[
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 4},
        ],
    )
    _login(page, base_url)
    problems = []
    scene_label = page.locator("#townMap").get_attribute("aria-label") or ""
    if scene_label != "場景 1 · 查看地圖":
        problems.append(
            f"#townMap aria-label {scene_label!r}, expected 場景 1 · 查看地圖"
        )
    for hit in _colloquial_product_hits():
        problems.append("product source: " + hit)
    for filename, needle in (
        ("town-four-scene.js", "未能放回"),
        ("town-four-scene.js", "未能興建"),
        ("index.html", "未能興建"),
    ):
        path = os.path.join(REPO, filename)
        text = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
        if needle not in text:
            problems.append(f"{filename} is missing the new fallback {needle}")

    page.locator("#townMap").get_by_role(
        "button", name=re.compile(r"第\s*1\s*欄第\s*1\s*行"),
    ).first.click()
    scene1_toast = _wait_toast(page)
    if scene1_toast.get("text") != "想在這裏興建？請先按「我要起屋」。":
        problems.append(
            "scene 1 empty tap toast "
            f"{scene1_toast.get('text')!r}, expected 想在這裏興建？請先按「我要起屋」。"
        )

    _enter_new_build_scene2(page)
    scene2 = _hint(page)
    visible = _visible_text(page)
    if scene2["ready"] != IDLE_SCENE2_HINT:
        problems.append(f"idle #readyStatus {scene2['ready']!r}, expected {IDLE_SCENE2_HINT!r}")
    if scene2["back"].strip() != "返回地圖":
        problems.append(f"#btnUxBack is {scene2['back'].strip()!r}, expected 返回地圖")
    if "返去睇地圖" in visible:
        problems.append("visible DOM still contains 返去睇地圖")
    if scene2["go"].strip() != "選擇位置":
        problems.append(f"#btnToScene3 is {scene2['go'].strip()!r}, expected 選擇位置")
    if "去擺位置" in visible:
        problems.append("visible DOM still contains 去擺位置")
    labels = _aria_labels(page)
    if not any("空地，點選即可選擇" in label for label in labels):
        problems.append(f"no empty-cell aria 「空地，點選即可選擇」. sample={labels[:3]!r}")
    if not any("商店，已興建" in label for label in labels):
        problems.append(f"placed 商店 aria is not 「商店，已興建」. sample={labels[:4]!r}")
    if any("，已起" in label or label.endswith("已起") for label in labels):
        problems.append("cell aria still contains 已起")

    _click_cell(page, 0, 0)
    picked_empty = _hint(page)
    if picked_empty["ready"] != EMPTY_PICKED_HINT:
        problems.append(
            f"empty-cell #readyStatus {picked_empty['ready']!r}, expected {EMPTY_PICKED_HINT!r}"
        )
    labels = _aria_labels(page)
    if "第 1 欄第 1 行，已選此格" not in labels:
        selected = [label for label in labels if label.startswith("第 1 欄第 1 行")]
        problems.append(f"selected aria {selected!r}, expected 第 1 欄第 1 行，已選此格")
    if any("已揀呢格" in label or "呢格" in label for label in labels):
        stale = [label for label in labels if "呢格" in label]
        problems.append(f"aria still contains 呢格: {stale[:4]}")
    badge = page.locator("#townMap .pad.is-chosen .badge")
    try:
        badge_text = (badge.first.inner_text() or "").strip() if badge.count() else ""
    except Exception:
        badge_text = ""
    if badge_text != "此格":
        problems.append(f"chosen badge {badge_text!r}, expected 此格")

    page.locator("#listLauncher").click()
    page.locator("#palette").wait_for(state="visible", timeout=8000)
    counter = (page.locator("#placedCount").inner_text() or "").strip()
    if not counter.startswith("已興建"):
        problems.append(f"#placedCount {counter!r}, expected 已興建 N")
    shop = page.locator("#palette").get_by_role("button", name=re.compile(r"商店"))
    gym = page.locator("#palette").get_by_role("button", name=re.compile(r"健身室"))
    library = page.locator("#palette").get_by_role("button", name=re.compile(r"圖書館"))
    shop_label = shop.first.get_attribute("aria-label") if shop.count() else ""
    gym_label = gym.first.get_attribute("aria-label") if gym.count() else ""
    library_label = library.first.get_attribute("aria-label") if library.count() else ""
    if shop_label != "商店，已興建":
        problems.append(f"list aria {shop_label!r}, expected 商店，已興建")
    if gym_label != "健身室，未興建":
        problems.append(f"list aria {gym_label!r}, expected 健身室，未興建")
    if library_label != "圖書館，放回":
        problems.append(f"list aria {library_label!r}, expected 圖書館，放回")
    shop_text = shop.first.inner_text() if shop.count() else ""
    if "已興建" not in shop_text:
        problems.append(f"list badge text {shop_text!r}, expected 已興建")
    library_text = library.first.inner_text() if library.count() else ""
    if "存倉" not in library_text:
        problems.append(f"stored list badge {library_text!r}, expected 存倉")
    _colloquial_visible(problems, "建築清單", _visible_text(page))

    if gym.count():
        gym.first.click()
        chosen = _hint(page)
        if chosen["ready"] != GYM_PICKED_HINT:
            problems.append(f"picked #readyStatus {chosen['ready']!r}, expected {GYM_PICKED_HINT!r}")
        go = page.locator("#btnToScene3")
        if go.count() and go.first.is_enabled():
            go.first.click()
            page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
            place = _hint(page)
            if place["place"] != SCENE3_CHARGE_HINT:
                problems.append(f"#placeStatus {place['place']!r}, expected {SCENE3_CHARGE_HINT!r}")
            move_labels = _aria_labels(page)
            if not any("可以放置，點選即可移到此格" in label for label in move_labels):
                problems.append("scene 3 has no 「可以放置，點選即可移到此格」 aria")
            if any("已經有屋，唔可以放" in label or "撳一下就搬" in label for label in move_labels):
                problems.append("scene 3 aria still has the old move/blocked wording")
            shop_pad = page.locator("#townMap").get_by_role("button", name=re.compile(r"商店"))
            if shop_pad.count():
                shop_pad.first.click()
                occupied = _wait_toast(page)
                if occupied.get("text") != "這裏已有「商店」，不能放置。":
                    problems.append(
                        "scene 3 occupied toast "
                        f"{occupied.get('text')!r}, expected 這裏已有「商店」，不能放置。"
                    )
            page.evaluate("() => { window.fetchAPI = async () => { throw new Error(''); }; }")
            confirm = page.locator("#btnUxConfirm")
            if confirm.count() and confirm.first.is_visible() and confirm.first.is_enabled():
                confirm.first.click()
                built = _wait_toast(page)
                if built.get("text") != "未能興建":
                    problems.append(f"new-build failure toast {built.get('text')!r}, expected 未能興建")
            else:
                problems.append("new-build confirm was not enabled, so 未能興建 was not shown")
        else:
            problems.append("「選擇位置」 did not enable, so scene 3 copy was not shown")
    else:
        problems.append("missing 健身室 in the building list")

    _relogin(page, base_url)
    _open_store(page)
    page.evaluate("() => { if (typeof showStoredBuildingsModal === 'function') showStoredBuildingsModal(); }")
    page.wait_for_timeout(300)
    modal = page.locator("#modalContent").inner_text() if page.locator("#modalContent").count() else ""
    if "請點選要放回地圖的建築物" not in modal:
        problems.append(f"storage modal {modal!r} missing 請點選要放回地圖的建築物")
    page.evaluate("() => { if (typeof closeModal === 'function') closeModal(); }")
    page.evaluate("() => { if (typeof showDecoModal === 'function') showDecoModal(0, 0); }")
    page.wait_for_timeout(400)
    deco = page.locator("#modalContent").inner_text() if page.locator("#modalContent").count() else ""
    if "點選進入，選擇要放回的建築物" not in deco:
        problems.append(f"deco modal {deco!r} missing 點選進入，選擇要放回的建築物")
    page.evaluate("() => { if (typeof closeModal === 'function') closeModal(); }")

    opened = _open_takeout_scene2(page)
    if opened:
        problems.append("unstore Scene 2 was not reached. " + opened)
    else:
        unstore = _hint(page)
        unstore_visible = _visible_text(page)
        if "場景 2" not in unstore["scene"]:
            problems.append(f"取出 did not stay on Scene 2. {unstore}")
        if unstore["back"].strip() != "返回地圖":
            problems.append(f"unstore #btnUxBack is {unstore['back'].strip()!r}")
        if unstore["go"].strip() != "選擇位置":
            problems.append(f"unstore #btnToScene3 is {unstore['go'].strip()!r}")
        _colloquial_visible(problems, "unstore Scene 2", unstore_visible)
        _click_cell(page, 0, 0)
        advance = page.locator("#btnToScene3")
        if advance.count() and advance.first.is_visible() and advance.first.is_enabled():
            advance.first.click()
        page.evaluate("() => { window.fetchAPI = async () => { throw new Error(''); }; }")
        confirm = page.locator("#btnUxConfirm")
        try:
            confirm.wait_for(state="visible", timeout=4000)
        except Exception:
            confirm = page.locator("#btnUxConfirm")
        if confirm.count() and confirm.first.is_visible():
            if confirm.first.is_enabled():
                confirm.first.click()
                failed = _wait_toast(page)
                if failed.get("text") != "未能放回":
                    problems.append(f"unstore failure toast {failed.get('text')!r}, expected 未能放回")
            else:
                problems.append("unstore confirm was disabled, so 未能放回 was not shown")
        else:
            problems.append("unstore confirm was not reached, so 未能放回 was not shown")

    shop_rows = [
        row for row in _kid_rows(warehouse_db, kid_id)
        if row["name"] == "商店" and row["stored"] == 0
    ]
    dialogs = []

    def _on_store_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", _on_store_dialog)
    if not shop_rows:
        problems.append("no placed 商店, so the store confirm was not opened")
    else:
        shop_id = shop_rows[0]["id"]
        opened = page.evaluate(
            """async (bid) => {
              if (typeof showBuildingUpgrade !== 'function') return false;
              await showBuildingUpgrade(bid);
              return true;
            }""",
            shop_id,
        )
        clicked = False
        store_btn = page.locator("#modalContent .btn-store")
        if opened and store_btn.count():
            try:
                store_btn.first.click(timeout=3000)
                clicked = True
            except Exception:
                clicked = False
        if not clicked:
            page.evaluate(
                "(bid) => { if (typeof storeBuilding === 'function') storeBuilding(bid); }",
                shop_id,
            )
        page.wait_for_timeout(300)
    if not any("確定收起這座建築物？" in msg for msg in dialogs):
        problems.append(
            f"store confirm {dialogs!r}, expected a dialog containing 確定收起這座建築物？"
        )
    if any("呢棟" in msg for msg in dialogs):
        problems.append(f"store confirm still contains 呢棟: {dialogs!r}")
    page.remove_listener("dialog", _on_store_dialog)

    _reset_kid(warehouse_db, kid_id, buildings=[])
    _relogin(page, base_url)
    _open_store(page)
    empty_list = page.locator("#storedBuildings").inner_text() or ""
    if "📦 存倉是空的，暫時沒有建築物。" not in empty_list:
        problems.append(f"empty storage list {empty_list!r}")
    page.evaluate("() => { if (typeof showStoredBuildingsModal === 'function') showStoredBuildingsModal(); }")
    empty_toast = _wait_toast(page)
    if empty_toast.get("text") != "📦 存倉是空的":
        problems.append(f"empty storage toast {empty_toast.get('text')!r}, expected 📦 存倉是空的")
    assert not problems, "TC-FE-WAREHOUSE-COPY-FORMAL: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-WAREHOUSE-RETURN-MAP")
@pytest.mark.parametrize("mode", ["new-build", "unstore"])
def test_return_map_leaves_scene2(page, base_url, warehouse_db, warehouse_ids, mode):
    """TC-FE-WAREHOUSE-RETURN-MAP 「返回地圖」回到場景 1，不扣資源。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12}],
    )
    before_points = get_kid_points(warehouse_db, kid_id)
    before_items = inventory_map(warehouse_db, kid_id)
    before_rows = _kid_rows(warehouse_db, kid_id)
    _login(page, base_url)
    if mode == "unstore":
        opened = _open_takeout_scene2(page)
        assert opened is None, "TC-FE-WAREHOUSE-RETURN-MAP: " + opened
    else:
        _enter_new_build_scene2(page)
    scene_before = _scene_aria(page)
    assert "場景 2" in scene_before, scene_before
    back = page.locator("#btnUxBack")
    assert back.count() and back.first.is_visible(), "missing #btnUxBack"
    label = (back.first.inner_text() or "").strip()
    back.first.click()
    page.wait_for_timeout(300)
    scene_after = _scene_aria(page)
    problems = []
    if label != "返回地圖":
        problems.append(f"#btnUxBack is {label!r}, expected 返回地圖")
    if "場景 1" not in scene_after:
        problems.append(f"after 返回地圖, aria is {scene_after!r}, expected 場景 1 (was {scene_before!r})")
    if not _resources_same(warehouse_db, kid_id, before_points, before_items):
        problems.append("resources changed")
    if mode == "unstore" and _kid_rows(warehouse_db, kid_id) != before_rows:
        problems.append(
            f"stored row changed {before_rows!r} -> {_kid_rows(warehouse_db, kid_id)!r}"
        )
    assert not problems, "TC-FE-WAREHOUSE-RETURN-MAP " + mode + ": " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-WAREHOUSE-TAKEOUT-FULL")
@pytest.mark.parametrize("entry", ["takeout", "list"])
def test_takeout_full_town_stays_put(page, base_url, warehouse_db, warehouse_ids, entry):
    """TC-FE-WAREHOUSE-TAKEOUT-FULL 滿圖時取出不得進入場景 2。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=_full_blockers())
    before_points = get_kid_points(warehouse_db, kid_id)
    before_items = inventory_map(warehouse_db, kid_id)
    before_rows = _kid_rows(warehouse_db, kid_id)
    _login(page, base_url)
    if entry == "list":
        _enter_new_build_scene2(page)
        page.locator("#listLauncher").click()
        page.locator("#palette").wait_for(state="visible", timeout=8000)
        library = page.locator("#palette").get_by_role("button", name=re.compile(r"圖書館"))
        assert library.count() > 0, "建築清單 has no 圖書館"
        library.first.click()
    else:
        _open_store(page)
        takeout = page.locator('[data-testid="warehouse-takeout"]')
        if takeout.count() == 0:
            takeout = page.locator("#tab-store").get_by_role("button", name="取出")
        assert takeout.count() > 0, (
            "TC-FE-WAREHOUSE-TAKEOUT-FULL: storage card has no 取出 button. "
            f"List={page.locator('#storedBuildings').inner_text()!r}"
        )
        takeout.first.click()
    page.wait_for_timeout(250)
    toast = _wait_toast(page)
    problems = _toast_info_problems(toast, FULL_TOWN_TOAST)
    scene = _scene_aria(page)
    if entry == "takeout":
        store_open = page.locator("#tab-store.active").count() > 0
        if "場景 2" in scene or not store_open:
            problems.append(
                f"取出 left the storage screen. scene={scene!r} store_open={store_open}"
            )
    else:
        palette_open = page.locator("#palette").is_visible()
        ready = _hint(page)["ready"]
        if not palette_open or ready == UNSTORE_SCENE2_HINT or "放回「圖書館」" in ready:
            problems.append(
                "list click entered unstore Scene 2. "
                f"palette_open={palette_open} scene={scene!r} ready={ready!r}"
            )
    if not _resources_same(warehouse_db, kid_id, before_points, before_items):
        problems.append("resources changed")
    if _kid_rows(warehouse_db, kid_id) != before_rows:
        problems.append("stored row changed")
    assert not problems, "TC-FE-WAREHOUSE-TAKEOUT-FULL " + entry + ": " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL")
def test_new_build_scene2_gold_matches_legal_origins(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL 新建造場景 2 的金色格等於合法原點。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        items={"wood": 40, "brick": 20},
        buildings=[{"name": "商店", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 4}],
    )
    _login(page, base_url)
    _enter_new_build_scene2(page)
    legal = set(_legal_origins([(4, 4)]))
    gold_list = _mark_gold_cells(page)
    gold = set(gold_list)
    problems = []
    if len(gold_list) != len(gold):
        dupes = sorted({cell for cell in gold_list if gold_list.count(cell) > 1})
        problems.append(f"duplicate gold cells {dupes}")
    if gold != legal:
        problems.append(
            f"scene 2 gold != legal origins. gold={len(gold)} legal={len(legal)} "
            f"extra={sorted(gold - legal)[:12]} missing={sorted(legal - gold)[:12]}"
        )
    _click_cell(page, 0, 0)
    _pick_unbuilt(page, "健身室")
    page.locator("#btnToScene3").click()
    page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
    scene3 = _mark_gold_cells(page)
    scene3_set = set(scene3)
    footprint = {(0, 0), (1, 0), (0, 1), (1, 1)}
    if len(scene3_set) > len(legal):
        problems.append(f"scene 3 gold count {len(scene3_set)} > legal {len(legal)}")
    outside = sorted(cell for cell in scene3_set if cell not in legal and cell not in footprint)
    if outside:
        problems.append(f"scene 3 gold outside legal origins and the preview footprint: {outside[:12]}")
    assert not problems, "TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-WAREHOUSE-OFFGRID-TOAST")
@pytest.mark.parametrize("mode", ["unstore", "new-build"])
def test_offgrid_cell_uses_cannot_fit_toast(page, base_url, warehouse_db, warehouse_ids, mode):
    """TC-FE-WAREHOUSE-OFFGRID-TOAST 放不下與已經有建築物用不同提示。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "健身室", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
        ],
    )
    before_points = get_kid_points(warehouse_db, kid_id)
    before_items = inventory_map(warehouse_db, kid_id)
    before_rows = _kid_rows(warehouse_db, kid_id)
    _login(page, base_url)
    if mode == "unstore":
        opened = _open_takeout_scene2(page)
        assert opened is None, "TC-FE-WAREHOUSE-OFFGRID-TOAST: " + opened
    else:
        _enter_new_build_scene2(page)
        _pick_unbuilt(page, "醫院")
    problems = []
    edge = page.locator("#townMap").get_by_role("button", name=re.compile(r"第\s*8\s*欄第\s*1\s*行"))
    if edge.count() == 0:
        target = (1, 0)
    else:
        target = (7, 0)
    _click_cell(page, *target)
    toast = _wait_toast(page)
    problems.extend(_toast_info_problems(toast, CANNOT_FIT_TOAST))
    _click_cell(page, 1, 0)
    collide = _wait_toast(page)
    problems.extend(
        [f"collision (1,0): {item}" for item in _toast_info_problems(collide, CANNOT_FIT_TOAST)]
    )
    _click_cell(page, 0, 0)
    occupied = _wait_toast(page)
    problems.extend(
        [f"occupied (0,0): {item}" for item in _toast_info_problems(occupied, OCCUPIED_TOAST)]
    )
    if not _resources_same(warehouse_db, kid_id, before_points, before_items):
        problems.append("resources changed")
    if _kid_rows(warehouse_db, kid_id) != before_rows:
        problems.append("rows changed")
    assert not problems, "TC-FE-WAREHOUSE-OFFGRID-TOAST " + mode + ": " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-WAREHOUSE-CANCEL-TOAST-INFO")
@pytest.mark.parametrize("mode", ["new-build", "unstore"])
def test_cancel_toast_uses_info_style(page, base_url, warehouse_db, warehouse_ids, mode):
    """TC-FE-WAREHOUSE-CANCEL-TOAST-INFO 取消提示維持原文，但用 info 棕底。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        items={"wood": 40, "brick": 20},
        buildings=[{"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12}],
    )
    _login(page, base_url)
    if mode == "unstore":
        opened = _open_takeout_scene2(page)
        assert opened is None, "TC-FE-WAREHOUSE-CANCEL-TOAST-INFO: " + opened
        _click_cell(page, 0, 0)
    else:
        _enter_new_build_scene2(page)
        _click_cell(page, 0, 0)
        _pick_unbuilt(page, "健身室")
        page.locator("#btnToScene3").click()
    advance = page.locator("#btnToScene3")
    if advance.count() and advance.first.is_visible() and advance.first.is_enabled():
        advance.first.click()
    page.locator("#btnUxCancel").wait_for(state="visible", timeout=8000)
    page.locator("#btnUxCancel").click()
    toast = _wait_toast(page)
    problems = []
    if toast.get("text") != CANCEL_TOAST:
        problems.append(f"toast text {toast.get('text')!r}, expected {CANCEL_TOAST!r}")
    classes = set((toast.get("className") or "").split())
    if "info" not in classes or "error" in classes:
        problems.append(f"toast class {toast.get('className')!r}, expected info")
    if toast.get("background") != INFO_BG:
        problems.append(f"toast background {toast.get('background')!r}, expected {INFO_BG}")
    if toast.get("color") != INFO_FG:
        problems.append(f"toast color {toast.get('color')!r}, expected {INFO_FG}")
    assert not problems, "TC-FE-WAREHOUSE-CANCEL-TOAST-INFO " + mode + ": " + " | ".join(problems)


_BAR_METRICS_JS = r"""
(spec) => {
  const stage = document.querySelector('body.kt-artstage .gsw');
  let scale = 1;
  if (stage && stage.offsetWidth) {
    const stageBox = stage.getBoundingClientRect();
    scale = stageBox.width / stage.offsetWidth;
  }
  if (!scale || !isFinite(scale)) scale = 1;
  const out = [];
  for (const item of spec) {
    const el = document.getElementById(item.id);
    if (!el) { out.push({id: item.id, missing: true, scale}); continue; }
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    const shown = cs.display !== 'none' && cs.visibility !== 'hidden' && !el.hidden
      && box.width > 1 && box.height > 1;
    let lines = el.getClientRects().length;
    try {
      const range = document.createRange();
      range.selectNodeContents(el);
      lines = range.getClientRects().length;
    } catch (err) { /* keep the element rect count */ }
    const rendered = box.height;
    out.push({
      id: item.id,
      text: (el.innerText || '').trim(),
      shown,
      whiteSpace: cs.whiteSpace,
      renderedHeight: rendered,
      layoutHeight: rendered / scale,
      scale,
      computedHeight: parseFloat(cs.height) || 0,
      padL: parseFloat(cs.paddingLeft) || 0,
      padR: parseFloat(cs.paddingRight) || 0,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      width: box.width,
      lines: lines,
      lineHeight: parseFloat(cs.lineHeight) || 0
    });
  }
  return out;
}
"""


def _bar_metrics(page, spec):
    return page.evaluate(_BAR_METRICS_JS, spec)


def _border_box_height(row):
    """Border box from getBoundingClientRect, with the art-stage scale removed.

    The stage is transform:scale(...). At 1280×720 the scale is 1, so this is
    the raw rect height (border included). Computed style height is not used:
    a content-box 48px plus 3px borders is 54px on screen and must fail 46±1.
    """
    if row.get("layoutHeight") is not None:
        return float(row["layoutHeight"])
    return float(row.get("renderedHeight") or row.get("height") or 0)


def _height_band_problem(row, target, kind):
    height = _border_box_height(row)
    if abs(height - target) <= 1.05:
        return None
    rendered = float(row.get("renderedHeight") or height)
    scale = float(row.get("scale") or 1)
    computed = row.get("computedHeight")
    return (
        f"{row.get('id')} {kind} border-box {height:.1f}px "
        f"(getBoundingClientRect {rendered:.1f} / scale {scale:.3f}, "
        f"computed height {computed}), expected {target}±1"
    )


def _button_metric_problems(row, min_width, widths_required):
    problems = []
    if row.get("missing") or not row.get("shown"):
        return [f"{row.get('id')} is not visible"]
    if row.get("scrollWidth", 0) > row.get("clientWidth", 0):
        problems.append(
            f"{row['id']} overflow scrollWidth {row.get('scrollWidth')} > clientWidth {row.get('clientWidth')}"
        )
    height_problem = _height_band_problem(row, 46, "button")
    if height_problem:
        problems.append(height_problem)
    if not widths_required:
        return problems
    if row.get("whiteSpace") != "nowrap":
        problems.append(f"{row['id']} white-space {row.get('whiteSpace')!r}, expected nowrap")
    if row.get("padL", 0) < 13 or row.get("padR", 0) < 13:
        problems.append(
            f"{row['id']} padding {row.get('padL'):.1f}/{row.get('padR'):.1f} < 13 (14−1)"
        )
    if row.get("width", 0) < min_width:
        problems.append(f"{row['id']} width {row.get('width'):.1f} < {min_width}")
    return problems


def _hint_line_problems(row):
    if row.get("missing") or not row.get("shown"):
        return [f"{row.get('id')} hint is not visible"]
    if row.get("lines", 0) != 1:
        return [
            f"{row['id']} wraps onto {row.get('lines')} lines "
            f"(text {row.get('text')!r}, height {row.get('height')})"
        ]
    return []


@pytest.mark.case_id("TC-FE-WAREHOUSE-BAR-NOOVERFLOW")
def test_place_bar_buttons_do_not_overflow(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-WAREHOUSE-BAR-NOOVERFLOW 底欄按鈕不溢出，提示維持一行。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        items={"wood": 40, "brick": 20},
        buildings=[],
    )
    _login(page, base_url)
    _enter_new_build_scene2(page)
    _click_cell(page, 0, 0)
    _pick_unbuilt(page, "健身室")
    problems = []
    buttons_s2 = [
        {"id": "btnUxBack", "min": 90},
        {"id": "btnToScene3", "min": 90},
    ]
    buttons_s3 = [
        {"id": "btnUxCancel", "min": 58},
        {"id": "btnUxConfirm", "min": 90},
    ]
    for width, height, widths in ((1280, 720, True), (1100, 800, True), (390, 720, False)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(200)
        for row in _bar_metrics(
            page,
            [{"id": item["id"]} for item in buttons_s2]
            + [{"id": "readyStatus"}, {"id": "readyBar"}],
        ):
            spec = next((item for item in buttons_s2 if item["id"] == row.get("id")), None)
            if spec:
                problems.extend(
                    f"{width}x{height} {item}"
                    for item in _button_metric_problems(row, spec["min"], widths)
                )
            elif row.get("id") == "readyBar":
                band = _height_band_problem(row, 64, "bar")
                if band:
                    problems.append(f"{width}x{height} {band}")
                elif row.get("missing") or not row.get("shown"):
                    problems.append(f"{width}x{height} #readyBar is not visible")
            elif row.get("id") == "readyStatus" and widths:
                problems.extend(f"{width}x{height} {item}" for item in _hint_line_problems(row))
    page.set_viewport_size({"width": 1280, "height": 720})
    page.locator("#btnToScene3").click()
    page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
    for width, height, widths in ((1280, 720, True), (1100, 800, True), (390, 720, False)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(200)
        for row in _bar_metrics(
            page,
            [{"id": item["id"]} for item in buttons_s3]
            + [{"id": "placeStatus"}, {"id": "uxPlaceBar"}],
        ):
            spec = next((item for item in buttons_s3 if item["id"] == row.get("id")), None)
            if spec:
                problems.extend(
                    f"{width}x{height} {item}"
                    for item in _button_metric_problems(row, spec["min"], widths)
                )
            elif row.get("id") == "uxPlaceBar":
                band = _height_band_problem(row, 64, "bar")
                if band:
                    problems.append(f"{width}x{height} {band}")
                elif row.get("missing") or not row.get("shown"):
                    problems.append(f"{width}x{height} #uxPlaceBar is not visible")
            elif row.get("id") == "placeStatus" and widths:
                problems.extend(f"{width}x{height} {item}" for item in _hint_line_problems(row))
    assert not problems, "TC-FE-WAREHOUSE-BAR-NOOVERFLOW: " + " | ".join(problems)


_MAP_FIT_JS = r"""
() => {
  const frame = document.getElementById('townMap');
  const fr = frame.getBoundingClientRect();
  const gold = [];
  let goldLeft = null;
  let goldRight = null;
  for (const pad of document.querySelectorAll('#townMap .pad')) {
    const mark = pad.querySelector(':scope > .mark');
    if (!mark || mark.hidden) continue;
    const cs = getComputedStyle(mark);
    const box = mark.getBoundingClientRect();
    const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && box.width > 1 && box.height > 1;
    const filter = cs.filter || '';
    if (!visible || !(filter.includes('212') && filter.includes('160') && filter.includes('23'))) continue;
    const padBox = pad.getBoundingClientRect();
    const btn = pad.querySelector('.cell-btn');
    const label = btn ? (btn.getAttribute('aria-label') || '') : '';
    if (goldLeft === null || padBox.left < goldLeft) goldLeft = padBox.left;
    if (goldRight === null || padBox.right > goldRight) goldRight = padBox.right;
    if (padBox.left < fr.left - 1 || padBox.right > fr.right + 1) {
      gold.push({
        label, left: Math.round(padBox.left), right: Math.round(padBox.right),
        frameLeft: Math.round(fr.left), frameRight: Math.round(fr.right)
      });
    }
  }
  const sprites = [];
  const spriteBoxes = [];
  for (const img of document.querySelectorAll('#townMap img.sprite')) {
    if (img.hidden) continue;
    const cs = getComputedStyle(img);
    const box = img.getBoundingClientRect();
    if (cs.display === 'none' || cs.visibility === 'hidden' || box.width < 2) continue;
    spriteBoxes.push({
      alt: img.alt || '', left: Math.round(box.left), right: Math.round(box.right)
    });
    if (box.left < fr.left - 1 || box.right > fr.right + 1) {
      sprites.push({
        alt: img.alt || '', left: Math.round(box.left), right: Math.round(box.right),
        frameLeft: Math.round(fr.left), frameRight: Math.round(fr.right)
      });
    }
  }
  return {
    scrollWidth: frame.scrollWidth,
    clientWidth: frame.clientWidth,
    frameLeft: Math.round(fr.left),
    frameRight: Math.round(fr.right),
    goldLeft: goldLeft == null ? null : Math.round(goldLeft),
    goldRight: goldRight == null ? null : Math.round(goldRight),
    gold,
    sprites,
    spriteBoxes
  };
}
"""


@pytest.mark.case_id("TC-FE-TOWN-MAP-FIT")
def test_town_map_fits_horizontally(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TOWN-MAP-FIT 1280×720 地圖橫向不裁切、不出現橫向捲動。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        buildings=[
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 6},
            {"name": "農場", "level": 1, "stored": 0, "cell_x": 6, "cell_y": 0},
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
        ],
    )
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    page.wait_for_timeout(200)
    problems = []

    def _check(where):
        measured = page.evaluate(_MAP_FIT_JS)
        if measured["scrollWidth"] > measured["clientWidth"]:
            problems.append(
                f"{where} scrollWidth {measured['scrollWidth']} > clientWidth {measured['clientWidth']} "
                f"(frame {measured['frameLeft']}..{measured['frameRight']})"
            )
        if measured["gold"]:
            problems.append(f"{where} gold clipped {measured['gold'][:4]}")
        if measured["sprites"]:
            problems.append(f"{where} sprites clipped {measured['sprites'][:4]}")
        return measured

    def _dump(label, measured):
        if not measured:
            return f"{label} not measured"
        return (
            f"{label} scroll {measured['scrollWidth']}/{measured['clientWidth']} "
            f"frame {measured['frameLeft']}..{measured['frameRight']} "
            f"gold {measured.get('goldLeft')}..{measured.get('goldRight')} "
            f"sprites {measured.get('spriteBoxes')}"
        )

    scene1 = _check("scene 1")
    _enter_new_build_scene2(page)
    scene2 = _check("new-build scene 2")
    opened = _open_takeout_scene2(page)
    if opened:
        problems.append("unstore scene 2 was not reached. " + opened)
        scene_unstore = None
    else:
        scene_unstore = _check("unstore scene 2")
    summary = " || ".join(
        (
            _dump("scene1", scene1),
            _dump("scene2", scene2),
            _dump("unstore", scene_unstore),
        )
    )
    print("TC-FE-TOWN-MAP-FIT " + summary)
    assert not problems, "TC-FE-TOWN-MAP-FIT: " + " | ".join(problems) + " || " + summary


RANGE_ERROR = "位置超出地圖範圍（0 至 7）"
MIN_FP_NAME = "郵箱"


def _cell_choice(page, cell_x, cell_y):
    col = cell_x + 1
    row = cell_y + 1
    return page.evaluate(
        """([col, row]) => {
          const prefix = '第 ' + col + ' 欄第 ' + row + ' 行';
          const btn = [...document.querySelectorAll('#townMap .cell-btn')].find((el) =>
            (el.getAttribute('aria-label') || '').startsWith(prefix)
          );
          if (!btn) return { missing: true, label: '', badge: '', chosen: false };
          const pad = btn.closest('.pad');
          const badge = pad ? pad.querySelector(':scope > .badge') : null;
          let badgeText = '';
          if (badge && !badge.hidden) {
            const cs = getComputedStyle(badge);
            const box = badge.getBoundingClientRect();
            if (cs.display !== 'none' && cs.visibility !== 'hidden' && box.width > 1) {
              badgeText = (badge.textContent || '').trim();
            }
          }
          const label = btn.getAttribute('aria-label') || '';
          return {
            missing: false,
            label,
            badge: badgeText,
            chosen: !!(pad && pad.classList.contains('is-chosen')) || label.includes('已選此格') || badgeText === '此格'
          };
        }""",
        [col, row],
    )


def _selected_cell_problems(choice, cell, selected):
    """selected=True means the cell must show as the chosen pad."""
    problems = []
    where = f"({cell[0]},{cell[1]})"
    if choice.get("missing"):
        return [f"{where} pad is missing"]
    is_on = bool(choice.get("chosen"))
    if selected and not is_on:
        problems.append(f"{where} was not selected. aria={choice.get('label')!r} badge={choice.get('badge')!r}")
    if not selected and is_on:
        problems.append(
            f"{where} stayed selected. aria={choice.get('label')!r} badge={choice.get('badge')!r}"
        )
    return problems


def _go_disabled(page):
    go = page.locator("#btnToScene3")
    if go.count() == 0 or not go.first.is_visible():
        return False, "missing"
    return go.first.is_disabled(), (go.first.inner_text() or "").strip()


def _install_min_footprint_catalog(page):
    """GET /api/building-defs gains footprint. Existing rows are 2; one new row is 1.

    ba93ca9's catalog objects have no footprint, width, height, or size key.
    town-four-scene.js uses a hard-coded FOOTPRINT = 2. The product must read
    `footprint` (square side) from each def. A missing key stays 2, so the
    default catalog still treats (5,7) as unfit.
    """
    seen = {"keys": None}

    def handle(route):
        response = route.fetch()
        try:
            data = response.json()
        except Exception:
            route.fulfill(status=response.status, body=response.body())
            return
        if not isinstance(data, list):
            route.fulfill(status=response.status, body=response.body())
            return
        for item in data:
            if isinstance(item, dict):
                if seen["keys"] is None:
                    seen["keys"] = sorted(item.keys())
                item["footprint"] = 2
        data.append({
            "id": 9001,
            "icon": "📮",
            "name": MIN_FP_NAME,
            "cost_gold": 10,
            "materials": "{}",
            "effect": "1×1",
            "buff_type": "",
            "buff_vals": "[]",
            "max_level": 1,
            "unlock_region": None,
            "footprint": 1,
        })
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(data),
        )

    page.route("**/api/building-defs", handle)
    return seen


def _force_confirm_400(page, mode):
    def handle(route):
        request = route.request
        url = request.url
        if request.method != "POST":
            route.continue_()
            return
        unstore = "/unstored" in url
        build = (
            "/buildings" in url
            and not unstore
            and "/move" not in url
            and "/store" not in url
            and "/upgrade" not in url
        )
        if (mode == "unstore" and unstore) or (mode == "new-build" and build):
            route.fulfill(
                status=400,
                content_type="application/json",
                body=json.dumps({"error": RANGE_ERROR}),
            )
            return
        route.continue_()

    page.route("**/api/kids/**", handle)


def _server_error_problems(toast, phrase):
    text = toast.get("text") or ""
    if phrase not in text:
        return []
    classes = set((toast.get("className") or "").split())
    if "error" in classes:
        return [f"red .error showed {text!r}"]
    return [f"showed server wording {text!r}"]


def _must_not_enter_scene3(page, origin, phrase):
    """Choosing a building must not carry an unfit origin into Scene 3."""
    problems = []
    disabled, label = _go_disabled(page)
    if disabled:
        return problems
    problems.append(f"「選擇位置」 enabled after {origin} (button {label!r})")
    page.locator("#btnToScene3").click()
    page.wait_for_timeout(250)
    scene = _scene_aria(page)
    if "場景 3" in scene:
        problems.append(f"reached Scene 3 with origin {origin}. scene={scene!r}")
    confirm = page.locator("#btnUxConfirm")
    if confirm.count() and confirm.first.is_visible():
        confirm.first.click()
        toast = _wait_toast(page)
        problems.extend(_server_error_problems(toast, phrase))
        classes = set((toast.get("className") or "").split())
        if "error" in classes:
            problems.append(f"confirm toast used .error {toast.get('text')!r}")
    return problems


@pytest.mark.case_id("TC-FE-BUILD-UNFIT-PRESELECT")
def test_unfit_cell_is_not_preselected(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-BUILD-UNFIT-PRESELECT (a) 未選建築時，放不下或已佔用的格不能選。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0}],
    )
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    problems = []
    gold = set(_mark_gold_cells(page))
    for cell in ((5, 7),):
        if cell in gold:
            problems.append(f"{cell} is gold before a building is chosen")
        _click_cell(page, *cell)
        toast = _wait_toast(page)
        problems.extend(_toast_info_problems(toast, CANNOT_FIT_TOAST))
        problems.extend(_server_error_problems(toast, RANGE_ERROR))
        problems.extend(_selected_cell_problems(_cell_choice(page, *cell), cell, False))
    _pick_unbuilt(page, "工坊")
    hint = _hint(page)["ready"]
    if hint == "已選擇「工坊」和這個位置。":
        problems.append(f"picking 工坊 kept the unfit cell. hint={hint!r}")
    problems.extend(_must_not_enter_scene3(page, (5, 7), RANGE_ERROR))
    _relogin(page, base_url)
    _enter_new_build_scene2(page)
    occupied = (1, 0)
    gold = set(_mark_gold_cells(page))
    if occupied in gold:
        problems.append(f"{occupied} footprint cell is gold before a building is chosen")
    _click_cell(page, *occupied)
    toast = _wait_toast(page)
    problems.extend(
        [f"occupied {occupied}: {item}" for item in _toast_info_problems(toast, OCCUPIED_TOAST)]
    )
    problems.extend(_server_error_problems(toast, OCCUPIED_RED))
    problems.extend(_selected_cell_problems(_cell_choice(page, *occupied), occupied, False))
    _pick_unbuilt(page, "工坊")
    hint = _hint(page)["ready"]
    if hint == "已選擇「工坊」和這個位置。":
        problems.append(f"picking 工坊 kept occupied {occupied}. hint={hint!r}")
    problems.extend(_must_not_enter_scene3(page, occupied, OCCUPIED_RED))
    assert not problems, "TC-FE-BUILD-UNFIT-PRESELECT: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-BUILD-UNFIT-PRESELECT")
@pytest.mark.parametrize("mode", ["new-build", "unstore"])
def test_confirm_400_returns_to_scene2(page, base_url, warehouse_db, warehouse_ids, mode):
    """TC-FE-BUILD-UNFIT-PRESELECT (c) 伺服器 400 時回到場景 2，不顯示原始錯誤。"""
    kid_id = warehouse_ids["kid_id"]
    if mode == "unstore":
        _reset_kid(
            warehouse_db,
            kid_id,
            points=800,
            buildings=[{"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12}],
        )
    else:
        _reset_kid(
            warehouse_db,
            kid_id,
            points=800,
            items={"wood": 40, "brick": 20},
            buildings=[],
        )
    before_points = get_kid_points(warehouse_db, kid_id)
    before_items = inventory_map(warehouse_db, kid_id)
    before_rows = _kid_rows(warehouse_db, kid_id)
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    if mode == "unstore":
        opened = _open_takeout_scene2(page)
        assert opened is None, "TC-FE-BUILD-UNFIT-PRESELECT: " + opened
        _click_cell(page, 0, 0)
    else:
        _enter_new_build_scene2(page)
        _click_cell(page, 0, 0)
        _pick_unbuilt(page, "健身室")
    advance = page.locator("#btnToScene3")
    if advance.count() and advance.first.is_visible() and advance.first.is_enabled():
        advance.first.click()
    page.locator("#btnUxConfirm").wait_for(state="visible", timeout=8000)
    _force_confirm_400(page, mode)
    page.locator("#btnUxConfirm").click()
    toast = _wait_toast(page)
    problems = _toast_info_problems(toast, CANNOT_FIT_TOAST)
    text = toast.get("text") or ""
    if RANGE_ERROR in text or "位置超出" in text:
        problems.append(f"toast showed the raw server error {text!r}")
    if "error" in set((toast.get("className") or "").split()):
        problems.append(f"toast used .error {toast.get('className')!r}")
    scene = _scene_aria(page)
    if "場景 2" not in scene:
        problems.append(f"stayed on {scene!r}, expected 場景 2")
    if "場景 3" in scene:
        problems.append("still stuck in Scene 3")
    if not _resources_same(warehouse_db, kid_id, before_points, before_items):
        problems.append("resources changed")
    if _kid_rows(warehouse_db, kid_id) != before_rows:
        problems.append("rows changed")
    assert not problems, "TC-FE-BUILD-UNFIT-PRESELECT " + mode + ": " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-BUILD-UNFIT-PRESELECT-MINFP")
def test_smallest_catalog_footprint_golds_index_7(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-BUILD-UNFIT-PRESELECT-MINFP 未選建築時金格跟目錄最小足跡。

    這也是 (b) 的介面路徑：先選 (5,7)，再選 2×2 的工坊。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    seen = _install_min_footprint_catalog(page)
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    problems = []
    keys = seen["keys"]
    gold = set(_mark_gold_cells(page))
    if (5, 7) not in gold:
        problems.append(
            f"(5,7) is not gold before a building is chosen. "
            f"catalog keys={keys}. Injected footprint=1 on {MIN_FP_NAME}, footprint=2 on the rest."
        )
    _click_cell(page, 5, 7)
    problems.extend(_selected_cell_problems(_cell_choice(page, 5, 7), (5, 7), True))
    _pick_unbuilt(page, "工坊")
    toast = _wait_toast(page)
    problems.extend(
        [f"after 工坊: {item}" for item in _toast_info_problems(toast, CANNOT_FIT_TOAST)]
    )
    problems.extend(_selected_cell_problems(_cell_choice(page, 5, 7), (5, 7), False))
    hint = _hint(page)["ready"]
    kept = "工坊" in hint
    if not kept:
        pressed = page.locator("#palette").get_by_role("button", name=re.compile(r"工坊"))
        kept = pressed.count() > 0 and (pressed.first.get_attribute("aria-pressed") == "true")
    if not kept:
        problems.append(f"工坊 was cleared with the cell. hint={hint!r}")
    if "和這個位置" in hint:
        problems.append(f"unfit cell still counted as chosen. hint={hint!r}")
    if not (hint.startswith("請點選金色空地") or ("工坊" in hint and "金色空地" in hint)):
        problems.append(
            f"hint {hint!r} should start with 請點選金色空地, "
            "or be the building-specific 金色空地 sentence"
        )
    disabled, label = _go_disabled(page)
    if not disabled:
        problems.append(f"「選擇位置」 enabled before a fitting cell (button {label!r})")
    gold_after = set(_mark_gold_cells(page))
    if (5, 7) in gold_after:
        problems.append("(5,7) is still gold after choosing the 2×2 工坊")
    if (0, 0) not in gold_after and (6, 6) not in gold_after:
        problems.append(f"no 2×2 origin stayed gold. sample={sorted(gold_after)[:8]}")
    if disabled:
        _click_cell(page, 0, 0)
        enabled_now, label_now = _go_disabled(page)
        if enabled_now:
            problems.append(
                f"「選擇位置」 stayed disabled after a 2×2 gold cell (button {label_now!r})"
            )
    assert not problems, "TC-FE-BUILD-UNFIT-PRESELECT-MINFP: " + " | ".join(problems)


_PAL_CLIP_JS = r"""
() => {
  const buttons = [...document.querySelectorAll('#palette .pal-btn')];
  return buttons.map((btn) => {
    const cs = getComputedStyle(btn);
    const borderBottom = parseFloat(cs.borderBottomWidth) || 0;
    const btnBox = btn.getBoundingClientRect();
    const second = btn.querySelector('.pal-cost');
    const secondBox = second ? second.getBoundingClientRect() : null;
    const gap = secondBox ? (btnBox.bottom - borderBottom - secondBox.bottom) : null;
    return {
      text: (btn.innerText || '').replace(/\\s+/g, ' ').trim(),
      second: second ? (second.textContent || '').trim() : '',
      className: btn.className || '',
      scrollHeight: btn.scrollHeight,
      clientHeight: btn.clientHeight,
      gap,
      borderBottom
    };
  });
}
"""


@pytest.mark.case_id("TC-FE-PAL-BTN-NOCLIP")
def test_palette_buttons_do_not_clip(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-PAL-BTN-NOCLIP 建築清單按鈕不可裁掉第二行。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
        ],
    )
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    page.locator("#listLauncher").click()
    page.locator("#palette .pal-btn").first.wait_for(state="visible", timeout=8000)
    rows = page.evaluate(_PAL_CLIP_JS)
    problems = []
    if not rows:
        problems.append("palette has no .pal-btn")
    saw_stored = saw_built = saw_unbuilt = False
    for row in rows:
        label = row.get("text") or row.get("second") or "?"
        scroll_h = row.get("scrollHeight") or 0
        client_h = row.get("clientHeight") or 0
        if scroll_h > client_h:
            problems.append(
                f"{label!r} scrollHeight {scroll_h} > clientHeight {client_h}"
            )
        gap = row.get("gap")
        if gap is None:
            problems.append(f"{label!r} has no second line")
        elif gap < 4 - 0.05:
            problems.append(
                f"{label!r} second line {row.get('second')!r} is {gap:.1f}px above "
                "the inner bottom border, expected >= 4"
            )
        kind = row.get("className") or ""
        second = row.get("second") or ""
        if "is-stored" in kind or second == "存倉":
            saw_stored = True
        if "is-placed" in kind or second in ("已興建", "已起"):
            saw_built = True
        if "is-stored" not in kind and "is-placed" not in kind and ("💰" in second or second[:1].isdigit()):
            saw_unbuilt = True
    if not saw_stored:
        problems.append("no stored palette row (存倉)")
    if not saw_built:
        problems.append("no built palette row (已興建)")
    if not saw_unbuilt:
        problems.append("no unbuilt palette row (price)")
    assert not problems, "TC-FE-PAL-BTN-NOCLIP: " + " | ".join(problems)




# --- focus-ring pixel polish (TC-FE-* from PR 64, rebased onto main) ---


def _close_sheet(page):
    sheet = page.locator("#actionSheet")
    close = page.locator("#btnCloseSheet")
    if sheet.count() and close.count():
        try:
            if sheet.first.is_visible() and close.first.is_visible():
                close.first.click(timeout=2000)
                page.wait_for_timeout(150)
        except Exception:
            pass


def _silence_toast(page):
    page.evaluate(
        """() => {
          const el = document.getElementById('toast');
          if (!el) return;
          el.style.display = 'none';
          el.style.animation = 'none';
          el.textContent = '';
        }"""
    )


def _select_cell(page, cell_x, cell_y):
    dismiss_selection(page)
    _silence_toast(page)
    data = cell_points(page, cell_x, cell_y)
    point = _activate_point(page, cell_x, cell_y, data)
    tap_point(page, point["x"], point["y"])
    page.wait_for_timeout(150)
    _silence_toast(page)


def _cancel_scene3(page):
    if "場景 3" not in _scene_aria(page):
        return
    cancel = page.locator("#btnUxCancel")
    try:
        if cancel.count() and cancel.first.is_visible():
            cancel.first.click(timeout=2000)
            page.wait_for_timeout(150)
    except Exception:
        pass
    _silence_toast(page)


def _restore_scene1(page):
    if "場景 1" in _scene_aria(page):
        _close_sheet(page)
        return
    back = page.locator("#btnUxBack")
    try:
        if back.count() and back.first.is_visible():
            back.first.click()
            page.wait_for_timeout(150)
    except Exception:
        pass
    _close_sheet(page)


def _ensure_bank_def(db_path):
    db = connect_db(db_path)
    row = db.execute("SELECT id FROM building_defs WHERE name=?", ("銀行",)).fetchone()
    if not row:
        db.execute(
            """
            INSERT INTO building_defs
                (icon, name, cost_gold, materials, effect, buff_type, buff_vals, max_level)
            VALUES ('🏦', '銀行', 150, '{}', '', 'ledger', '[1]', 5)
            """
        )
        db.commit()
        row = db.execute("SELECT id FROM building_defs WHERE name=?", ("銀行",)).fetchone()
    db.close()
    return row["id"]


def _ring_clip(page, shape):
    tips = list(shape["cell"]["tips"].values()) + list(shape["ring"]["tips"].values())
    xs = [tip["x"] for tip in tips]
    ys = [tip["y"] for tip in tips]
    view = page.viewport_size
    left = max(0, min(xs) - 12)
    top = max(0, min(ys) - 12)
    right = min(view["width"], max(xs) + 12)
    bottom = min(view["height"], max(ys) + 12)
    return {"x": left, "y": top, "width": max(1, right - left), "height": max(1, bottom - top)}


def _blur_focus(page):
    page.evaluate(
        "() => { const el = document.activeElement; if (el && el.blur) el.blur(); }"
    )


def _paint_clip(page, face, margin=28):
    tips = list(face["tips"].values())
    xs = [tip["x"] for tip in tips]
    ys = [tip["y"] for tip in tips]
    badge = face.get("badge")
    if badge:
        xs.extend((badge["left"], badge["right"]))
        ys.extend((badge["top"], badge["bottom"]))
    view = page.viewport_size
    left = max(0, min(xs) - margin)
    top = max(0, min(ys) - margin)
    right = min(view["width"], max(xs) + margin)
    bottom = min(view["height"], max(ys) + margin)
    return {
        "x": left,
        "y": top,
        "width": max(1, right - left),
        "height": max(1, bottom - top),
    }


def _hot_cells(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('#townMap .pad.is-empty-hot')].map((pad) => {
          const cs = getComputedStyle(pad);
          const c = parseInt(cs.getPropertyValue('--c'), 10);
          const r = parseInt(cs.getPropertyValue('--r'), 10);
          return {c, r, edge: c === 0 || r === 0 || c === 7 || r === 7};
        }).filter((cell) => Number.isFinite(cell.c) && Number.isFinite(cell.r))"""
    ) or []


def _shot(page, clip):
    return page.screenshot(clip=clip, scale="css", type="png")


def _full_shot(page):
    return page.screenshot(scale="css", type="png")


def _focus_visible_cell(page, cell_x, cell_y):
    return page.evaluate(
        """([c, r]) => {
          const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
            const cs = getComputedStyle(el);
            return parseInt(cs.getPropertyValue('--c'), 10) === c
              && parseInt(cs.getPropertyValue('--r'), 10) === r;
          });
          const btn = pad && pad.querySelector(':scope > .cell-btn');
          if (!btn) return false;
          btn.focus({focusVisible: true});
          return document.activeElement === btn;
        }""",
        [cell_x, cell_y],
    )


def _require_clean_paint(page, problems, label):
    """Baseline shots must not already contain the selected line or the ring."""
    brown = count_stroke_pixels(_full_shot(page))
    ring = ring_layer_pixels(page) or {}
    if brown:
        problems.append(f"{label}: {brown} #7c2d12 px before the baseline")
    if ring.get("pixels"):
        problems.append(
            f"{label}: ring layer has {ring.get('pixels')} px "
            f"({ring.get('tag')} display {ring.get('display')}) before the baseline"
        )


def _wrap_problems(report, label):
    problems = []
    for name in ("NE", "SE", "SW", "NW"):
        edge = report.get(name) or {}
        outer = edge.get("outer")
        if edge.get("count", 0) < 8 or outer is None or outer < 0 or outer > 1.5:
            problems.append(
                f"{label} {name}: outer {outer} count {edge.get('count')}, "
                "want 0–1.5px outside the live cell"
            )
    return problems


def _rect_clip(page, rect):
    if not rect:
        return None
    view = page.viewport_size
    left = max(0, rect["left"])
    top = max(0, rect["top"])
    right = min(view["width"], rect["right"])
    bottom = min(view["height"], rect["bottom"])
    if right - left < 2 or bottom - top < 2:
        return None
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def _open_palette(page):
    if page.locator("#palette").is_visible():
        return
    page.locator("#listLauncher").click()
    page.locator("#palette").wait_for(state="visible", timeout=8000)


def _go_town_tab(page):
    page.locator('#ktFooter [data-kt-nav="town"]').click()
    page.locator("#tab-town.active").wait_for(state="visible", timeout=8000)


def _ensure_scene2(page):
    if "場景 3" in _scene_aria(page):
        _cancel_scene3(page)
    if "場景 2" not in _scene_aria(page):
        _go_town_tab(page)
        _enter_new_build_scene2(page)


def _align_device_clip(clip, dpr):
    """Snap a CSS clip onto the device-pixel grid the screenshot uses."""
    dpr = dpr or 1
    x0 = math.floor(clip["x"] * dpr) / dpr
    y0 = math.floor(clip["y"] * dpr) / dpr
    x1 = math.floor((clip["x"] + clip["width"]) * dpr) / dpr
    y1 = math.floor((clip["y"] + clip["height"]) * dpr) / dpr
    if x1 - x0 < 2 or y1 - y0 < 2:
        return clip
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


def _device_shot(page, clip):
    return page.screenshot(clip=clip, scale="device", type="png")


def _dpr(page):
    return page.evaluate("() => window.devicePixelRatio || 1") or 1


def _cells_near_bar(page, width):
    """Cells whose south tip sits on the ready bar. 1280 uses (3,4) and (2,5)."""
    rows = page.evaluate(
        """() => {
          const bar = document.getElementById('readyBar');
          if (!bar) return [];
          const barBox = bar.getBoundingClientRect();
          const cells = [];
          for (const pad of document.querySelectorAll('#townMap .pad')) {
            const btn = pad.querySelector(':scope > .cell-btn');
            const label = btn ? (btn.getAttribute('aria-label') || '') : '';
            const slab = pad.querySelector(':scope > .slab');
            if (!slab) continue;
            const box = slab.getBoundingClientRect();
            if (box.width < 2) continue;
            const face = 10 * (box.width / 168);
            const cy = box.top + box.height / 2 - face;
            const halfH = box.height * (50 / 120);
            const south = cy + halfH;
            const cs = getComputedStyle(pad);
            cells.push({
              c: parseInt(cs.getPropertyValue('--c'), 10),
              r: parseInt(cs.getPropertyValue('--r'), 10),
              south: south,
              barTop: barBox.top,
              gap: barBox.top - south,
              empty: label.includes('空地')
            });
          }
          return cells;
        }"""
    ) or []
    if width == 1280:
        wanted = {(3, 4), (2, 5)}
        named = [row for row in rows if (row["c"], row["r"]) in wanted]
        return named
    empty = [row for row in rows if row.get("empty")]
    near = [row for row in empty if -40 <= row.get("gap", 99) <= 24]
    if len(near) < 2:
        near = list(empty)
    near.sort(key=lambda row: abs(row["gap"]))
    picked = []
    for row in near:
        if any(item["c"] == row["c"] and item["r"] == row["r"] for item in picked):
            continue
        picked.append(row)
        if len(picked) == 2:
            break
    return picked


def _overlay_rects(page):
    """Visible bar and palette painted extents, in viewport CSS px.

    The extent is the border box plus the live ``::before`` outset. The
    band walk still grows that rect by 1px. A 48px palette hole is not a
    cover, so samples in that dead zone are not skipped.
    """
    report = paint_cover_report(page) or {}
    rects = []
    for row in report.get("covers") or []:
        if row.get("id") not in ("readyBar", "uxPlaceBar", "palette"):
            continue
        extent = row.get("extent") or {}
        if extent.get("right", 0) - extent.get("left", 0) < 2:
            continue
        rects.append({"id": row.get("id"), **extent})
    return rects


def _bar_text_rects(page, selector):
    """Client rects of every text node in the bar, padded by 1px."""
    return page.evaluate(
        """(selector) => {
          const root = document.querySelector(selector);
          if (!root) return [];
          const rects = [];
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode())) {
            if (!node.textContent || !node.textContent.trim()) continue;
            const range = document.createRange();
            range.selectNodeContents(node);
            for (const box of range.getClientRects()) {
              if (box.width < 0.4 && box.height < 0.4) continue;
              rects.push({
                left: box.left - 1,
                top: box.top - 1,
                right: box.right + 1,
                bottom: box.bottom + 1
              });
            }
          }
          return rects;
        }""",
        selector,
    ) or []


_PAINT_GUARD_JS = r"""() => {
  function layerName(el) {
    const id = el.id || '';
    const cls = el.getAttribute ? (el.getAttribute('class') || '') : '';
    return (id + ' ' + cls).trim();
  }
  function shown(el) {
    if (!el || el.hidden) return false;
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
      const cs = getComputedStyle(node);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      if (Number(cs.opacity) === 0) return false;
      if (node === document.documentElement) break;
    }
    const box = el.getBoundingClientRect();
    if (!(box.width > 1 && box.height > 1)) return false;
    const viewW = window.innerWidth;
    const viewH = window.innerHeight;
    if (box.right <= 0 || box.bottom <= 0 || box.left >= viewW || box.top >= viewH) return false;
    return true;
  }
  function isStackingContext(el) {
    if (!el || el.nodeType !== 1) return false;
    if (el === document.documentElement) return true;
    const cs = getComputedStyle(el);
    const pos = cs.position;
    const z = cs.zIndex;
    if (z !== 'auto' && (pos === 'absolute' || pos === 'relative' || pos === 'fixed' || pos === 'sticky')) {
      return true;
    }
    if (parseFloat(cs.opacity) < 1) return true;
    if (cs.transform && cs.transform !== 'none') return true;
    if (cs.filter && cs.filter !== 'none') return true;
    if (cs.perspective && cs.perspective !== 'none') return true;
    if (cs.clipPath && cs.clipPath !== 'none') return true;
    if (cs.maskImage && cs.maskImage !== 'none') return true;
    if (cs.isolation === 'isolate') return true;
    if (cs.mixBlendMode && cs.mixBlendMode !== 'normal') return true;
    if (/\b(layout|paint|strict|content)\b/.test(cs.contain || '')) return true;
    if (/transform|opacity|filter|perspective/.test(cs.willChange || '')) return true;
    return false;
  }
  function chain(el) {
    const list = [];
    for (let node = el; node; node = node.parentElement) list.push(node);
    return list;
  }
  function commonContext(a, b) {
    const others = new Set(chain(b));
    for (const node of chain(a)) {
      if (node === a || node === b) continue;
      if (others.has(node) && isStackingContext(node)) return node;
    }
    return document.documentElement;
  }
  function participant(el, context) {
    let node = el;
    while (node && node.parentElement && node.parentElement !== context) node = node.parentElement;
    if (!node || node === context) node = el;
    const cs = getComputedStyle(node);
    const positioned = cs.position === 'absolute' || cs.position === 'relative'
      || cs.position === 'fixed' || cs.position === 'sticky';
    const numeric = positioned && cs.zIndex !== 'auto' && Number.isFinite(parseFloat(cs.zIndex));
    return {z: numeric ? parseFloat(cs.zIndex) : 0};
  }
  function addLayer(found, seen, el, kind) {
    if (!el || seen.has(el)) return;
    seen.add(el);
    found.push({el, kind});
  }
  const layers = [];
  const seen = new Set();
  addLayer(layers, seen, document.getElementById('focusRingPaint'), 'ring');
  addLayer(layers, seen, document.getElementById('focusRingLift'), 'ring');
  addLayer(layers, seen, document.getElementById('chosenMarkPaint'), 'mark');
  document.querySelectorAll('#townMap canvas, #townMap svg').forEach((el) => {
    const name = layerName(el).toLowerCase();
    const paint = el.tagName.toLowerCase() === 'canvas' || el.tagName.toLowerCase() === 'svg';
    if (!paint) return;
    if (el.id === 'focusRingPaint' || el.id === 'focusRingLift' || /ring|focus-lift|focuslift/.test(name)) {
      addLayer(layers, seen, el, 'ring');
    } else if (el.id === 'chosenMarkPaint' || /mark/.test(name)) {
      addLayer(layers, seen, el, 'mark');
    }
  });
  function paintedExtent(el) {
    const box = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const before = getComputedStyle(el, '::before');
    const content = before.content || '';
    const live = content !== 'none' && content !== 'normal'
      && before.display !== 'none' && before.visibility !== 'hidden';
    let left = 0, top = 0, right = 0, bottom = 0;
    if (live) {
      function side(offset, edge, margin) {
        if (offset == null || offset === 'auto') return 0;
        const n = parseFloat(offset);
        if (!Number.isFinite(n)) return 0;
        return Math.max(0, -(edge + n + (parseFloat(margin) || 0)));
      }
      left = side(before.left, parseFloat(cs.borderLeftWidth) || 0, before.marginLeft);
      top = side(before.top, parseFloat(cs.borderTopWidth) || 0, before.marginTop);
      right = side(before.right, parseFloat(cs.borderRightWidth) || 0, before.marginRight);
      bottom = side(before.bottom, parseFloat(cs.borderBottomWidth) || 0, before.marginBottom);
    }
    return {
      left: box.left - left, top: box.top - top,
      right: box.right + right, bottom: box.bottom + bottom
    };
  }
  const covers = [];
  for (const sel of ['#readyBar', '#uxPlaceBar', '#palette', '#townMap .cta', '#actionSheet']) {
    const el = document.querySelector(sel);
    if (!shown(el)) continue;
    const extent = paintedExtent(el);
    covers.push({id: el.id, el, left: extent.left, top: extent.top, right: extent.right, bottom: extent.bottom});
  }
  const z = [];
  for (const layer of layers) {
    for (const cover of covers) {
      const ctx = commonContext(layer.el, cover.el);
      const lz = participant(layer.el, ctx);
      const cz = participant(cover.el, ctx);
      if (!(lz.z < cz.z)) {
        z.push({
          layer: layer.el.id || layerName(layer.el),
          kind: layer.kind,
          against: cover.id,
          layerZ: lz.z,
          againstZ: cz.z,
          context: ctx.id || ctx.tagName
        });
      }
    }
  }
  function intersects(box, cover) {
    return box.left < cover.right - 0.5 && box.right > cover.left + 0.5
      && box.top < cover.bottom - 0.5 && box.bottom > cover.top + 0.5;
  }
  function localPoint(svg, x, y) {
    if (typeof svg.createSVGPoint !== 'function') return null;
    const pt = svg.createSVGPoint();
    pt.x = x;
    pt.y = y;
    const ctm = svg.getScreenCTM && svg.getScreenCTM();
    if (!ctm) return null;
    return pt.matrixTransform(ctm.inverse());
  }
  function hitsGeometry(shape, local) {
    try {
      if (typeof shape.isPointInFill === 'function' && shape.isPointInFill(local)) return true;
    } catch (err) { /* not a geometry element */ }
    try {
      if (typeof shape.isPointInStroke === 'function' && shape.isPointInStroke(local)) return true;
    } catch (err) { /* no stroke */ }
    return false;
  }
  function resolveClip(svg) {
    const raw = (svg.getAttribute('clip-path') || '') + ' ' + (getComputedStyle(svg).clipPath || '');
    const match = raw.match(/url\(["']?#([^)"']+)/);
    if (!match) return null;
    return document.getElementById(match[1]);
  }
  function canvasInk(canvas, coverList) {
    const hits = [];
    const box = canvas.getBoundingClientRect();
    if (!(box.width > 1) || !(canvas.width > 0)) return hits;
    let ctx = null;
    try { ctx = canvas.getContext('2d', {willReadFrequently: true}); } catch (err) { ctx = null; }
    if (!ctx) {
      hits.push({layer: canvas.id || 'canvas', kind: 'canvas', cover: '', detail: 'no 2d context'});
      return hits;
    }
    const sx = canvas.width / box.width;
    const sy = canvas.height / box.height;
    for (const cover of coverList) {
      const x0 = Math.max(0, Math.floor((cover.left - box.left) * sx));
      const y0 = Math.max(0, Math.floor((cover.top - box.top) * sy));
      const x1 = Math.min(canvas.width, Math.ceil((cover.right - box.left) * sx));
      const y1 = Math.min(canvas.height, Math.ceil((cover.bottom - box.top) * sy));
      if (x1 - x0 < 1 || y1 - y0 < 1) continue;
      let data;
      try { data = ctx.getImageData(x0, y0, x1 - x0, y1 - y0).data; }
      catch (err) {
        hits.push({layer: canvas.id || 'canvas', kind: 'canvas', cover: cover.id, detail: 'getImageData failed'});
        continue;
      }
      let ink = 0;
      for (let i = 3; i < data.length; i += 4) if (data[i] !== 0) ink += 1;
      if (ink) {
        hits.push({layer: canvas.id || 'canvas', kind: 'canvas', cover: cover.id, detail: ink + ' device px with alpha'});
      }
    }
    return hits;
  }
  function svgHits(svg, coverList) {
    const shapes = [...svg.querySelectorAll('rect, path, polygon, polyline, circle, ellipse, line')];
    const clip = resolveClip(svg);
    const label = svg.id || layerName(svg);
    if (clip) {
      const clipShapes = [...clip.querySelectorAll('rect, path, polygon, polyline, circle, ellipse')];
      for (const cover of coverList) {
        for (let gy = 1; gy <= 5; gy += 1) {
          for (let gx = 1; gx <= 7; gx += 1) {
            const x = cover.left + (cover.right - cover.left) * gx / 8;
            const y = cover.top + (cover.bottom - cover.top) * gy / 6;
            const local = localPoint(svg, x, y);
            if (!local) continue;
            let painted = false;
            for (const shape of shapes) {
              if (hitsGeometry(shape, local)) { painted = true; break; }
            }
            if (!painted) continue;
            let inside = clipShapes.length === 0;
            for (const shape of clipShapes) {
              if (hitsGeometry(shape, local)) { inside = true; break; }
            }
            if (inside) {
              return [{layer: label, kind: 'svg-clip', cover: cover.id, detail: 'bar point is inside the clipped geometry'}];
            }
          }
        }
      }
      return [];
    }
    const hits = [];
    for (const shape of shapes) {
      const box = shape.getBoundingClientRect();
      if (box.width < 0.2 && box.height < 0.2) continue;
      for (const cover of coverList) {
        if (!intersects(box, cover)) continue;
        hits.push({
          layer: label,
          kind: 'svg-bbox',
          cover: cover.id,
          detail: shape.tagName.toLowerCase() + ' client bbox intersects'
        });
        return hits;
      }
    }
    return hits;
  }
  const geometry = [];
  const method = [];
  for (const layer of layers) {
    if (!shown(layer.el)) {
      method.push({id: layer.el.id || layerName(layer.el), method: 'hidden'});
      continue;
    }
    const tag = layer.el.tagName.toLowerCase();
    if (tag === 'canvas') {
      method.push({id: layer.el.id || 'canvas', method: 'canvas-alpha'});
      geometry.push(...canvasInk(layer.el, covers));
    } else if (tag === 'svg') {
      const clipped = !!resolveClip(layer.el);
      method.push({id: layer.el.id || layerName(layer.el), method: clipped ? 'svg-clip' : 'svg-bbox'});
      geometry.push(...svgHits(layer.el, covers));
    }
  }
  const dom = [];
  document.querySelectorAll('.place-bar, #readyBar, #uxPlaceBar, #palette, #townMap .cta, #actionSheet').forEach((host) => {
    host.querySelectorAll('canvas, svg, [id*="ring" i], [id*="mark" i], [id*="focus-lift" i], [class*="ring" i], [class*="mark" i], [class*="focus-lift" i]').forEach((el) => {
      if (el === host) return;
      dom.push({
        host: host.id || (host.getAttribute('class') || ''),
        tag: el.tagName.toLowerCase(),
        id: el.id || '',
        className: (el.getAttribute('class') || '').slice(0, 80)
      });
    });
  });
  const textShadow = [];
  const shadowSeen = new Set();
  document.querySelectorAll('#readyStatus, #placeStatus, .place-bar p').forEach((el) => {
    if (shadowSeen.has(el)) return;
    shadowSeen.add(el);
    const value = getComputedStyle(el).textShadow;
    if (value && value !== 'none') textShadow.push({id: el.id || el.tagName, value});
  });
  function nearStandIn(color) {
    const match = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/.exec(color || '');
    if (!match) return false;
    const dr = Number(match[1]) - 255;
    const dg = Number(match[2]) - 254;
    const db = Number(match[3]) - 197;
    return dr * dr + dg * dg + db * db <= 25;
  }
  function looks3d(transform) {
    if (!transform || transform === 'none') return false;
    return /matrix3d|translateZ|translate3d|rotateX|rotateY|perspective/i.test(transform);
  }
  const mask = [];
  const maskSel = '#readyBar, #uxPlaceBar, #palette, #townMap .cta, #actionSheet, .place-bar, #focusRingPaint, #focusRingLift, #chosenMarkPaint';
  document.querySelectorAll(maskSel).forEach((el) => {
    const cs = getComputedStyle(el);
    const id = el.id || (el.getAttribute('class') || '').slice(0, 48) || el.tagName;
    if (cs.filter && cs.filter !== 'none') mask.push({id, kind: 'filter', value: cs.filter});
    if (looks3d(cs.transform)) mask.push({id, kind: 'transform3d', value: cs.transform});
    if (cs.textShadow && cs.textShadow !== 'none') mask.push({id, kind: 'text-shadow', value: cs.textShadow});
    if (cs.mixBlendMode && cs.mixBlendMode !== 'normal') mask.push({id, kind: 'blend', value: cs.mixBlendMode});
    if (nearStandIn(cs.backgroundColor)) mask.push({id, kind: 'fffec5', value: cs.backgroundColor});
  });
  document.querySelectorAll('.place-bar [fill], #readyBar [fill], #uxPlaceBar [fill], #palette [fill], #townMap .cta [fill], #actionSheet [fill]').forEach((el) => {
    const fill = (el.getAttribute('fill') || '').toLowerCase();
    if (fill === '#fffec5' || fill === '#fff8e7') {
      mask.push({id: el.id || el.tagName.toLowerCase(), kind: 'fill', value: fill});
    }
  });
  return {
    textShadow,
    mask: mask.slice(0, 8),
    dom: dom.slice(0, 6),
    z: z.slice(0, 8),
    geometry: geometry.slice(0, 6),
    method,
    layers: layers.map((layer) => ({
      id: layer.el.id || layerName(layer.el),
      kind: layer.kind,
      tag: layer.el.tagName.toLowerCase()
    }))
  };
}"""


def _paint_guard_problems(page, label, problems):
    """Stacking, canvas/SVG coverage, DOM parent, and bar text-shadow.

    The ring and the selected mark are pointer-events:none, so this does not
    use elementsFromPoint. SVG paint with no clip-path is judged by each
    drawn shape's client bbox (it must miss every visible bar and the
    palette). A clip-path url is judged by isPointInFill on a grid inside
    those rects. A canvas ring is judged by getImageData alpha.
    """
    report = page.evaluate(_PAINT_GUARD_JS) or {}
    if not any("text-shadow" in item for item in problems):
        for row in report.get("textShadow") or []:
            problems.append(
                f"{label}: bar sentence #{row.get('id')} text-shadow is "
                f"{row.get('value')!r}, want none"
            )
    for row in report.get("mask") or []:
        problems.append(
            f"{label}: {row.get('id')} {row.get('kind')} {row.get('value')!r} "
            "masks paint (want no filter, text-shadow, 3d transform, "
            "blend, or #fffec5 layer)"
        )
    for row in report.get("dom") or []:
        name = row.get("id") or row.get("className") or row.get("tag")
        problems.append(
            f"{label}: {row.get('tag')} {name} is a descendant of {row.get('host')}"
        )
    for row in report.get("z") or []:
        problems.append(
            f"{label}: {row.get('kind')} {row.get('layer')} z {row.get('layerZ')} "
            f"is not below {row.get('against')} z {row.get('againstZ')} "
            f"(context {row.get('context')})"
        )
    for row in report.get("geometry") or []:
        problems.append(
            f"{label}: {row.get('layer')} {row.get('kind')} {row.get('detail')} "
            f"({row.get('cover')})"
        )
    print(
        f"TC-FE-PAINT-UNDER-UI guards {label} scene {_scene_aria(page)!r} "
        f"method {report.get('method')} layers {report.get('layers')} "
        f"z {report.get('z')} geom {report.get('geometry')} "
        f"dom {report.get('dom')} shadow {report.get('textShadow')} "
        f"mask {report.get('mask')}",
        flush=True,
    )


def _bar_sentence(page):
    """Visible status text of the place bar. Hidden sentences are not included."""
    return page.evaluate(
        """() => {
          const parts = [];
          for (const sel of ['#readyStatus', '#placeStatus']) {
            const el = document.querySelector(sel);
            if (!el) continue;
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') continue;
            const box = el.getBoundingClientRect();
            if (box.width < 1 || box.height < 1) continue;
            parts.push((el.textContent || '').replace(/\\s+/g, ' ').trim());
          }
          return parts.join('\\n');
        }"""
    ) or ""


def _hide_mark_paint(page):
    """Test-only. Hide the mark paint layer with visibility, not display.

    The sentence and the bar's border stay laid out. Ring layers are left
    alone. Each element's previous inline visibility is stored so it can
    be restored.
    """
    return page.evaluate(
        """() => {
          const saved = [];
          const seen = new Set();
          function add(el) {
            if (!el || seen.has(el)) return;
            const tag = el.tagName.toLowerCase();
            if (tag !== 'svg' && tag !== 'canvas') return;
            const name = ((el.id || '') + ' ' + (el.getAttribute('class') || '')).toLowerCase();
            if (el.id !== 'chosenMarkPaint' && /ring|focus-lift|focuslift/.test(name)) return;
            if (el.id !== 'chosenMarkPaint' && !/mark/.test(name)) return;
            seen.add(el);
            saved.push(el.id || name);
            el.setAttribute('data-kt-mark-vis', el.style.visibility || '');
            el.style.visibility = 'hidden';
          }
          add(document.getElementById('chosenMarkPaint'));
          document.querySelectorAll('#townMap canvas, #townMap svg').forEach(add);
          return saved;
        }"""
    ) or []


def _restore_mark_paint(page):
    page.evaluate(
        """() => {
          document.querySelectorAll('[data-kt-mark-vis]').forEach((el) => {
            el.style.visibility = el.getAttribute('data-kt-mark-vis') || '';
            el.removeAttribute('data-kt-mark-vis');
          });
        }"""
    )


def _open_scene3_for_guard(page):
    if "場景 3" in (_scene_aria(page) or ""):
        return True
    _ensure_scene2(page)
    dismiss_selection(page)
    _blur_focus(page)
    _open_palette(page)
    choice = page.locator('#palette [aria-label*="未興建"]')
    if not choice.count():
        return False
    choice.first.click()
    page.wait_for_timeout(80)
    gold = _gold_cells(page)
    if not gold:
        return False
    _click_cell(page, gold[0][0], gold[0][1])
    go = page.locator("#btnToScene3")
    if not go.count() or not go.is_enabled():
        return False
    go.click()
    page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
    return "場景 3" in (_scene_aria(page) or "")


def _tab_to_cell(page, cell_x, cell_y):
    """Move keyboard focus onto a cell with Tab, not element.focus()."""
    prepared = page.evaluate(
        """([c, r]) => {
          const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
            const cs = getComputedStyle(el);
            return parseInt(cs.getPropertyValue('--c'), 10) === c
              && parseInt(cs.getPropertyValue('--r'), 10) === r;
          });
          const btn = pad && pad.querySelector(':scope > .cell-btn');
          if (!btn) return {ok: false};
          const buttons = [...document.querySelectorAll('#townMap .cell-btn')];
          const index = buttons.indexOf(btn);
          if (index < 0) return {ok: false};
          const prev = index > 0 ? buttons[index - 1] : document.body;
          prev.focus();
          return {ok: true, index};
        }""",
        [cell_x, cell_y],
    )
    if not prepared or not prepared.get("ok"):
        return False
    page.keyboard.press("Tab")
    page.wait_for_timeout(40)
    return bool(page.evaluate(
        """([c, r]) => {
          const el = document.activeElement;
          const pad = el && el.closest ? el.closest('.pad') : null;
          if (!pad || !el.matches(':focus-visible')) return false;
          const cs = getComputedStyle(pad);
          return parseInt(cs.getPropertyValue('--c'), 10) === c
            && parseInt(cs.getPropertyValue('--r'), 10) === r;
        }""",
        [cell_x, cell_y],
    ))


def _painted_extent(page, selector):
    report = paint_cover_report(page) or {}
    for row in report.get("covers") or []:
        if row.get("selector") == selector:
            return row.get("extent")
    return surface_rect(page, selector)


def _place_cell_over_cta(page):
    """Scroll a free cell so its south tip lies on the scene-1 build button."""
    return page.evaluate(
        """() => {
          const cta = document.querySelector('#townMap .cta');
          const village = document.getElementById('village');
          if (!cta || !village) return {ok: false, reason: 'missing'};
          const cs = getComputedStyle(cta);
          const box = cta.getBoundingClientRect();
          if (cs.display === 'none' || box.width < 2 || box.height < 2) {
            return {ok: false, reason: 'hidden'};
          }
          const pads = [...document.querySelectorAll('#townMap .pad')];
          let pad = pads.find((el) => {
            const style = getComputedStyle(el);
            return parseInt(style.getPropertyValue('--c'), 10) === 3
              && parseInt(style.getPropertyValue('--r'), 10) === 4;
          }) || pads[0];
          if (!pad) return {ok: false, reason: 'no cell'};
          const style = getComputedStyle(pad);
          const c = parseInt(style.getPropertyValue('--c'), 10);
          const r = parseInt(style.getPropertyValue('--r'), 10);
          function southOf(el) {
            const slab = el.querySelector(':scope > .slab');
            const slabBox = slab.getBoundingClientRect();
            const face = 10 * (slabBox.width / 168);
            const cy = slabBox.top + slabBox.height / 2 - face;
            const halfH = slabBox.height * (50 / 120);
            return cy + halfH;
          }
          const scale = village.getBoundingClientRect().width / village.offsetWidth || 1;
          const ctaBox = cta.getBoundingClientRect();
          const target = (ctaBox.top + ctaBox.bottom) / 2;
          const delta = (southOf(pad) - target) / scale;
          const max = Math.max(0, village.scrollHeight - village.clientHeight);
          village.scrollTop = Math.max(0, Math.min(max, village.scrollTop + delta));
          const south = southOf(pad);
          const now = cta.getBoundingClientRect();
          return {
            ok: south >= now.top - 2 && south <= now.bottom + 2,
            c, r, south, top: now.top, bottom: now.bottom, scroll: village.scrollTop
          };
        }"""
    ) or {"ok": False}


# --- pixel polish (expected red). Coarse checks stay above. ---
# Strict thresholds copied from 399222f. Mixed cases use a -PX id so the
# coarse id on this branch stays the 6 CSS px / exposed-edge contract.


@pytest.mark.case_id("TC-FE-FOCUS-RING-CENTRE")
def test_focus_ring_centre(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-FOCUS-RING-CENTRE 鍵盤焦点環的中心要對上菱形頂面的中心。

    頂面中心在地磚外框中心上方 10 個視圖單位。1280×720 與 390×844 都要在 ±1px 內。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0}],
    )
    _login(page, base_url)
    problems = []
    for width, height in ((1280, 720), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        if "場景 2" not in _scene_aria(page):
            _enter_new_build_scene2(page)
        page.wait_for_timeout(150)
        point = any_visible_gold_point(page)
        if not point:
            problems.append(f"{width}x{height}: no visible gold cell")
            continue
        delta = focus_ring_delta(page, point["c"], point["r"]) or {}
        dx = delta.get("dx")
        dy = delta.get("dy")
        print(
            f"TC-FE-FOCUS-RING-CENTRE {width}x{height} cell {point['c'], point['r']} "
            f"dx {dx} dy {dy} painted {delta.get('painted')}"
        )
        if not delta.get("painted") or dx is None or dy is None:
            problems.append(f"{width}x{height}: focus ring was not painted ({delta})")
            continue
        if abs(dx) > 1 or abs(dy) > 1:
            problems.append(
                f"{width}x{height}: ring centre is ({dx:.1f},{dy:.1f}) px from the "
                f"top-face centre, want ±1 (face offset {delta.get('face')})"
            )
    assert not problems, "TC-FE-FOCUS-RING-CENTRE: " + " | ".join(problems)


def _ring_offsets(shape):
    cell = shape["cell"]["tips"]
    ring = shape["ring"]["tips"]
    return {
        "N": cell["N"]["y"] - ring["N"]["y"],
        "S": ring["S"]["y"] - cell["S"]["y"],
        "E": ring["E"]["x"] - cell["E"]["x"],
        "W": cell["W"]["x"] - ring["W"]["x"],
    }


def _ring_gaps(shape):
    center = {"x": shape["cell"]["cx"], "y": shape["cell"]["cy"]}
    cell = shape["cell"]["tips"]
    ring = shape["ring"]["tips"]
    pairs = (("NE", "N", "E"), ("SE", "E", "S"), ("SW", "S", "W"), ("NW", "W", "N"))
    gaps = {}
    for name, a, b in pairs:
        cell_a, cell_b = cell[a], cell[b]
        ring_a, ring_b = ring[a], ring[b]
        mx = (cell_a["x"] + cell_b["x"]) / 2
        my = (cell_a["y"] + cell_b["y"]) / 2
        rx = (ring_a["x"] + ring_b["x"]) / 2
        ry = (ring_a["y"] + ring_b["y"]) / 2
        dx = ring_b["x"] - ring_a["x"]
        dy = ring_b["y"] - ring_a["y"]
        length = (dx * dx + dy * dy) ** 0.5 or 1
        dist = abs((mx - ring_a["x"]) * dy - (my - ring_a["y"]) * dx) / length
        cell_r = ((mx - center["x"]) ** 2 + (my - center["y"]) ** 2) ** 0.5
        ring_r = ((rx - center["x"]) ** 2 + (ry - center["y"]) ** 2) ** 0.5
        gaps[name] = dist if ring_r + 0.2 >= cell_r else -dist
    return gaps


@pytest.mark.case_id("TC-FE-FOCUS-RING-SHAPE")
def test_focus_ring_shape(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-FOCUS-RING-SHAPE 焦點環是頂面菱形繞中心均勻放大。

    四個尖角沿各自的軸在格子尖角外 2–4px（橫向因為比例可以到約 8px），
    每條邊在格子邊外 2–4px，寬高比和格子相差不超過 2%。1280 的 (3,3)
    大約 150–157 × 89–93。中心仍在 ±1px。選中又聚焦時，環不得壓到
    #7c2d12 實線。不鎖線寬。畫出來的內緣用裝置像素中心：24 站只放在
    沒被看得見的確認欄或調色盤蓋住的那段（活矩形外擴 1px，再離開尖角
    開口加 3px）。24 站裡至少 22 站要打中真正的環奶油 #fff8e7
    （平方距離約 25，#fffec5 不算）。看得見的邊短於 12px 就跳過。
    0.1px 步進，連續 3 個樣本。最小值 ≥2、最大值 ≤4 螢幕 px。
    1280、1100、390，捲動 0 和 366，deviceScaleFactor 1 和 2。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    problems = []
    summaries = []
    cells = ((6, 0, "edge"), (3, 3, "interior"))
    for width, height in ((1280, 720), (1100, 800), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        if "場景 2" not in _scene_aria(page):
            _enter_new_build_scene2(page)
        for cell_x, cell_y, role in cells:
            _scroll_cell_into_view(page, cell_x, cell_y)
            dismiss_selection(page)
            shape = focus_ring_shape(page, cell_x, cell_y) or {}
            if shape.get("error") or not shape.get("ring"):
                problems.append(f"{width}x{height} {role} {shape.get('error')}")
                continue
            offsets = _ring_offsets(shape)
            gaps = _ring_gaps(shape)
            cell = shape["cell"]
            ring = shape["ring"]
            cell_ratio = cell["width"] / cell["height"] if cell["height"] else 0
            ring_ratio = ring["width"] / ring["height"] if ring["height"] else 0
            aspect = abs(ring_ratio / cell_ratio - 1) if cell_ratio else 1
            summaries.append(
                f"{width}x{height} {role} {cell_x, cell_y} "
                f"ring {ring['width']:.1f}x{ring['height']:.1f} "
                f"cell {cell['width']:.1f}x{cell['height']:.1f} "
                f"aspect {aspect:.1%} offsets { {k: round(v, 2) for k, v in offsets.items()} }"
            )
            dx, dy = shape.get("dx"), shape.get("dy")
            if dx is None or abs(dx) > 1 or abs(dy) > 1:
                problems.append(
                    f"{width}x{height} {role}: centre ({dx},{dy}) is outside ±1px"
                )
            if aspect > 0.02:
                problems.append(
                    f"{width}x{height} {role}: ring aspect {ring_ratio:.3f} vs "
                    f"cell {cell_ratio:.3f} ({aspect:.1%})"
                )
            for name, offset in offsets.items():
                limit = 4 if name in ("N", "S") else 8
                if offset < 2 or offset > limit:
                    problems.append(
                        f"{width}x{height} {role}: {name} tip is {offset:.2f}px "
                        f"outside, want 2–{limit}"
                    )
            for name, gap in gaps.items():
                if gap < 2 or gap > 4:
                    problems.append(
                        f"{width}x{height} {role}: {name} edge is {gap:.2f}px "
                        "outside the cell, want 2–4"
                    )
            if width == 1280 and (cell_x, cell_y) == (3, 3):
                if not (150 <= ring["width"] <= 157 and 89 <= ring["height"] <= 93):
                    problems.append(
                        f"1280 (3,3) ring {ring['width']:.1f}x{ring['height']:.1f}, "
                        "want about 150–157 x 89–93"
                    )
            outer = shape.get("outer") or {}
            inner = shape.get("inner") or {}
            if (outer.get("stroke") or "").lower() != "6b4f2a":
                problems.append(f"{width}x{height} {role}: outer stroke {outer.get('stroke')}")
            if (inner.get("stroke") or "").lower() != "fff8e7":
                problems.append(f"{width}x{height} {role}: inner stroke {inner.get('stroke')}")
            if not outer.get("dashed") or not inner.get("dashed"):
                problems.append(f"{width}x{height} {role}: focus ring is not dashed")
            _select_cell(page, cell_x, cell_y)
            _scroll_cell_into_view(page, cell_x, cell_y)
            focused = focus_ring_shape(page, cell_x, cell_y) or {}
            if not focused.get("ring"):
                problems.append(f"{width}x{height} {role}: ring missing while selected")
                continue
            both = _ring_offsets(focused)
            if both["E"] <= 1.5 or both["W"] <= 1.5:
                problems.append(
                    f"{width}x{height} {role}: E/W tips sit inside the solid line "
                    f"(E {both['E']:.2f}, W {both['W']:.2f})"
                )
            clip = _ring_clip(page, focused)
            _blur_focus(page)
            _silence_toast(page)
            before = page.screenshot(clip=clip, scale="css", type="png")
            focus_ring_shape(page, cell_x, cell_y)
            page.wait_for_timeout(40)
            png = page.screenshot(clip=clip, scale="css", type="png")
            report = ring_pixel_report(before, png, focused["cell"], clip)
            if report["overlap"]:
                problems.append(
                    f"{width}x{height} {role}: {report['overlap']} ring pixels "
                    "in the 1px band outside the cell lie on the selected line"
                )
            if report["solid"] < 8:
                problems.append(
                    f"{width}x{height} {role}: selected line #7c2d12 was not painted "
                    f"(solid pixels {report['solid']})"
                )
    problems.extend(_device_ring_gaps(page, "dsf1"))
    problems.extend(_focus_ring_gaps_at_scale(page, base_url, 2))
    print("TC-FE-FOCUS-RING-SHAPE " + " || ".join(summaries))
    assert not problems, "TC-FE-FOCUS-RING-SHAPE: " + " | ".join(problems[:12])


@pytest.mark.case_id("TC-FE-FOCUS-RING-NO-FILL-PX")
def test_focus_ring_no_fill_px(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-FOCUS-RING-NO-FILL-PX 焦點環只畫虛線，不填滿格子。

    未選中只聚焦時，邊內 8px 的每一點都要和未選中、未聚焦的底圖一致，
    不排除徽章位置。選中時才排除徽章區域。中心不能是 #7c2d12。
    環的內緣約在格子外 2px（2–4px），不得壓到褐線。
    選中又聚焦時，褐線外緣在格子外 0–1px。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": "圖書館", "level": 1, "stored": 0, "cell_x": 6, "cell_y": 0}],
    )
    _login(page, base_url)
    problems = []
    summaries = []

    def _check_focus(width, height, role, cell, selected):
        _scroll_cell_into_view(page, cell[0], cell[1])
        dismiss_selection(page)
        _blur_focus(page)
        _silence_toast(page)
        page.wait_for_timeout(200)
        _require_clean_paint(page, problems, f"{width}x{height} {role} baseline")
        face = cell_top_face(page, cell[0], cell[1]) or {}
        if face.get("error") or not face.get("tips"):
            problems.append(f"{width}x{height} {role} {face.get('error')}")
            return
        clip = _paint_clip(page, face)
        before = _shot(page, clip)
        if selected:
            _select_cell(page, cell[0], cell[1])
            _silence_toast(page)
            chosen_face = cell_top_face(page, cell[0], cell[1]) or {}
            if not chosen_face.get("chosen"):
                problems.append(f"{width}x{height} {role}: did not stay selected")
                return
            face["badge"] = chosen_face.get("badge")
        focus_ring_shape(page, cell[0], cell[1])
        page.wait_for_timeout(40)
        after = _shot(page, clip)
        focus = focus_pixel_report(
            before, after, face, clip, allow_badge=selected
        )
        brown_in = [item["name"] for item in focus["interior"] if item["brown"]]
        drifted = [item["name"] for item in focus["interior"] if not item["near"]]
        if brown_in:
            sample = next(item for item in focus["interior"] if item["brown"])
            problems.append(
                f"{width}x{height} {role}: interior {','.join(brown_in)} "
                f"is #7c2d12 ({sample['after']})"
            )
        if drifted:
            sample = next(item for item in focus["interior"] if not item["near"])
            problems.append(
                f"{width}x{height} {role}: interior {','.join(drifted)} "
                f"left the baseline ({sample['before']} → {sample['after']}, "
                f"Δ{sample['dist']})"
            )
        ink_bits = []
        for name, edge_report in focus["edges"].items():
            ink_bits.append(f"{name}:{edge_report['ink']}/{edge_report['samples']}")
            if edge_report["brown_outside"]:
                problems.append(
                    f"{width}x{height} {role} {name}: "
                    f"{edge_report['brown_outside']} #7c2d12 pixels outside the cell"
                )
            if edge_report["ink"] < 2:
                problems.append(
                    f"{width}x{height} {role} {name}: ring ink "
                    f"{edge_report['ink']}/{edge_report['samples']}"
                )
            else:
                off = [
                    item for item in edge_report["first"]
                    if item < 2 or item > 4
                ]
                if off:
                    problems.append(
                        f"{width}x{height} {role} {name}: ring inner edge at "
                        f"{edge_report['first']}, want 2–4px outside"
                    )
        if selected:
            stroke = selection_pixel_report(
                before, after, face, clip, allow_badge=True
            )
            for name, edge_report in stroke["edges"].items():
                if edge_report["width"] < 2 or edge_report["width"] > 4:
                    problems.append(
                        f"{width}x{height} {role} selected {name}: brown run "
                        f"{edge_report['width']}px, want 2–4"
                    )
                outer = edge_report["outer"]
                if outer is None or outer < 0 or outer > 1:
                    problems.append(
                        f"{width}x{height} {role} selected {name}: brown outer edge "
                        f"{outer}px, want 0–1 (centreline inset 0.5–1.5)"
                    )
        _blur_focus(page)
        centre = next(item for item in focus["interior"] if item["name"] == "centre")
        summaries.append(
            f"{width}x{height} {role} ({cell[0]},{cell[1]}) "
            f"centre {centre['before']}→{centre['after']} "
            f"ring {','.join(ink_bits)}"
        )

    for width, height in ((1280, 720), (1100, 800), (390, 844)):
        _relogin(page, base_url)
        page.set_viewport_size({"width": width, "height": height})
        _enter_new_build_scene2(page)
        assert _pick_unbuilt(page, "工坊"), f"{width}x{height}: 工坊 missing"
        hot = _hot_cells(page)
        interior = next((cell for cell in hot if not cell["edge"]), None)
        edge = next((cell for cell in hot if cell["edge"]), None)
        if not interior or not edge:
            problems.append(f"{width}x{height}: missing a gold interior or edge cell")
            continue
        _check_focus(width, height, "gold", (interior["c"], interior["r"]), False)
        _check_focus(width, height, "edge", (edge["c"], edge["r"]), False)
        _check_focus(width, height, "sprite", (6, 0), False)
        _check_focus(width, height, "gold+selected", (interior["c"], interior["r"]), True)
        _check_focus(width, height, "edge+selected", (edge["c"], edge["r"]), True)
    print("TC-FE-FOCUS-RING-NO-FILL-PX " + " || ".join(summaries))
    assert not problems, "TC-FE-FOCUS-RING-NO-FILL-PX: " + " | ".join(problems[:12])


def _device_gap_problems(gaps, label):
    """Min ≥2, max ≤4, at least 22 of 24 stations on the unoccluded edge."""
    problems = []
    bits = []
    for name in ("NE", "SE", "SW", "NW"):
        edge = gaps.get(name) or {}
        bits.append(
            f"{name} {edge.get('min')}/{edge.get('median')}/{edge.get('max')} "
            f"n={edge.get('samples')}/{edge.get('stations')} "
            f"vis={edge.get('visible')} legacy={edge.get('legacy_visible')}"
            + (" skipped" if edge.get("skipped") else "")
        )
        if edge.get("skipped"):
            continue
        samples = edge.get("samples", 0)
        if samples < 22 or edge.get("min") is None or edge.get("max") is None:
            problems.append(
                f"{label} {name}: {samples} of {edge.get('stations')} unoccluded "
                f"stations hit cream (visible {edge.get('visible')}px, "
                f"legacy {edge.get('legacy_visible')}/24), want ≥22"
            )
            continue
        if edge["min"] < 2 or edge["max"] > 4:
            problems.append(
                f"{label} {name}: inner gap {edge['min']:.2f}–{edge['max']:.2f}px, "
                "want 2–4 screen px"
            )
    return problems, " ".join(bits)


def _device_ring_gaps(page, scale_label):
    """(3,3) at scroll 0 and 366. Device-pixel centres, 0.1px walk."""
    problems = []
    dpr = _dpr(page)
    for width, height in ((1280, 720), (1100, 800), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(80)
        if "場景 2" not in _scene_aria(page):
            _enter_new_build_scene2(page)
        for scroll in (0, 366):
            dismiss_selection(page)
            _blur_focus(page)
            _silence_toast(page)
            set_village_scroll(page, scroll)
            page.wait_for_timeout(80)
            _scroll_cell_into_view(page, 3, 3)
            # Keep the requested scroll when the cell is already on screen.
            set_village_scroll(page, scroll)
            page.wait_for_timeout(80)
            _blur_focus(page)
            page.wait_for_timeout(200)
            label = f"{scale_label} {width}x{height} scroll {scroll}"
            _require_clean_paint(page, problems, label)
            face = cell_top_face(page, 3, 3) or {}
            if face.get("error") or not face.get("tips"):
                problems.append(f"{label}: {face.get('error')}")
                continue
            clip = _align_device_clip(_paint_clip(page, face, margin=16), dpr)
            before = _device_shot(page, clip)
            if not _focus_visible_cell(page, 3, 3):
                problems.append(f"{label}: cell did not focus")
                continue
            page.wait_for_timeout(40)
            gaps = ring_device_gaps(
                before,
                _device_shot(page, clip),
                face,
                clip,
                dpr=dpr,
                occluders=_overlay_rects(page),
            )
            found, text = _device_gap_problems(gaps, label)
            problems.extend(found)
            print(f"TC-FE-FOCUS-RING-SHAPE {text}", flush=True)
            _blur_focus(page)
    return problems


def _focus_ring_gaps_at_scale(page, base_url, scale):
    """Painted inner edge at another deviceScaleFactor. Screen px, not stage px."""
    browser = page.context.browser
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        device_scale_factor=scale,
    )
    problems = []
    other = context.new_page()
    try:
        other.route("https://image.pollinations.ai/**", lambda route: route.abort())
        _login(other, base_url)
        _enter_new_build_scene2(other)
        problems.extend(_device_ring_gaps(other, f"dsf{scale}"))
    finally:
        context.close()
    return problems


@pytest.mark.case_id("TC-FE-MARK-FOLLOWS-SCROLL-PX")
def test_mark_follows_scroll_px(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-MARK-FOLLOWS-SCROLL-PX 捲動 0 和 366 時，選中線仍包住同一格。

    外緣在活格子外 0–1.5px，這條不因確認欄裁切而放寬。焦點環的內緣用
    ring_device_gaps，和 TC-FE-FOCUS-RING-SHAPE 同一套站：24 站只放在
    沒被欄或調色盤蓋住的那段，至少 22 站打中 #fff8e7，短於 12px 就跳過。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    set_village_scroll(page, 0)
    _select_cell(page, 3, 3)
    _blur_focus(page)
    problems = []
    dpr = _dpr(page)
    for scroll in (0, 366):
        moved = set_village_scroll(page, scroll)
        page.wait_for_timeout(80)
        face = cell_top_face(page, 3, 3) or {}
        if not face.get("tips"):
            problems.append(f"scroll {scroll}: {face.get('error')}")
            continue
        clip = _paint_clip(page, face, margin=20)
        near = stroke_near_cell(_shot(page, clip), face, clip)
        print(f"TC-FE-MARK-FOLLOWS-SCROLL-PX {scroll} {moved} {near}", flush=True)
        problems.extend(_wrap_problems(near, f"scroll {scroll}"))
        _blur_focus(page)
        page.wait_for_timeout(150)
        device_clip = _align_device_clip(clip, dpr)
        before = _device_shot(page, device_clip)
        if not _focus_visible_cell(page, 3, 3):
            problems.append(f"scroll {scroll}: cell did not focus")
            continue
        page.wait_for_timeout(40)
        gaps = ring_device_gaps(
            before,
            _device_shot(page, device_clip),
            face,
            device_clip,
            dpr=dpr,
            occluders=_overlay_rects(page),
        )
        found, text = _device_gap_problems(gaps, f"scroll {scroll} ring")
        print(f"TC-FE-MARK-FOLLOWS-SCROLL-PX ring {text}", flush=True)
        problems.extend(found)
        _blur_focus(page)
    assert not problems, "TC-FE-MARK-FOLLOWS-SCROLL-PX: " + " | ".join(problems)


def _diff_bar_outside_text(before, after, clip, rects, label, problems):
    diff = bar_masked_diff(before, after, clip, rects)
    sample = (diff or {}).get("sample")
    count = None if diff is None else diff.get("count")
    print(
        f"TC-FE-PAINT-UNDER-UI-PX {label} masked-diff {count} sample {sample} "
        f"more {(diff or {}).get('samples')}",
        flush=True,
    )
    if count is None:
        problems.append(f"{label}: bar screenshots differ in size")
    elif count:
        painted = ""
        if sample:
            painted = f" ({sample.get('before')} → {sample.get('after')} at {sample.get('x')},{sample.get('y')})"
        problems.append(f"{label}: {count} px changed outside text rects{painted}")


def _paint_near_bar_px(page):
    """Focus and select cells whose south tip meets the ready bar."""
    problems = []
    if page.locator("#actionSheet").is_visible():
        _close_sheet(page)
        page.wait_for_timeout(150)
    _ensure_scene2(page)
    for width, height in ((1280, 720), (1100, 800), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(80)
        if "場景 2" not in _scene_aria(page):
            _enter_new_build_scene2(page)
        set_village_scroll(page, 0)
        page.wait_for_timeout(80)
        cells = _cells_near_bar(page, width)
        print(f"TC-FE-PAINT-UNDER-UI-PX near-bar {width}x{height} {cells}", flush=True)
        if len(cells) < 2 and width != 1280:
            problems.append(f"{width}x{height}: found {len(cells)} cells near the bar")
        if width == 1280 and {(item['c'], item['r']) for item in cells} != {(3, 4), (2, 5)}:
            problems.append(f"1280 near-bar cells {cells}, want (3,4) and (2,5)")
        for cell in cells:
            dismiss_selection(page)
            _blur_focus(page)
            page.evaluate(
                """() => {
                  const pad = document.querySelector('#townMap .pad.is-chosen');
                  const btn = pad && pad.querySelector(':scope > .cell-btn');
                  if (btn) btn.click();
                }"""
            )
            _blur_focus(page)
            _silence_toast(page)
            page.wait_for_timeout(200)
            label_base = f"{width}x{height} ({cell['c']},{cell['r']})"
            _require_clean_paint(page, problems, label_base)
            bar_name = "#uxPlaceBar" if page.locator("#uxPlaceBar").is_visible() else "#readyBar"
            rect = surface_rect(page, bar_name)
            clip = _rect_clip(page, rect)
            if not clip:
                problems.append(f"{label_base}: {bar_name} has no on-screen rect")
                continue
            # Both diffs use this selected cell, so the bar sentence matches.
            # The corner of the rounded border is still inside the rect and
            # still compared; only a sentence change used to move it.
            _select_cell(page, cell["c"], cell["r"])
            _blur_focus(page)
            page.wait_for_timeout(80)
            select_label = f"{label_base} select"
            _paint_guard_problems(page, select_label, problems)
            sentence_on = _bar_sentence(page)
            rects_on = _bar_text_rects(page, bar_name)
            marked = _shot(page, clip)
            hidden = _hide_mark_paint(page)
            try:
                if not hidden:
                    problems.append(f"{select_label}: mark layer not found to hide")
                page.wait_for_timeout(40)
                sentence_off = _bar_sentence(page)
                rects_off = _bar_text_rects(page, bar_name)
                unmarked = _shot(page, clip)
            finally:
                _restore_mark_paint(page)
            print(
                f"TC-FE-PAINT-UNDER-UI-PX {select_label} sentence {sentence_on!r} "
                f"vs {sentence_off!r} mark-hidden {hidden}",
                flush=True,
            )
            if sentence_on != sentence_off:
                problems.append(
                    f"{select_label}: bar sentence {sentence_on!r} != {sentence_off!r}"
                )
            _diff_bar_outside_text(
                unmarked,
                marked,
                clip,
                rects_on + rects_off,
                select_label,
                problems,
            )
            if not _focus_visible_cell(page, cell["c"], cell["r"]):
                problems.append(f"{label_base} focus: did not focus")
                continue
            page.wait_for_timeout(80)
            focus_label = f"{label_base} focus"
            _paint_guard_problems(page, focus_label, problems)
            sentence_focus = _bar_sentence(page)
            rects_focus = _bar_text_rects(page, bar_name)
            focused = _shot(page, clip)
            _blur_focus(page)
            page.wait_for_timeout(80)
            sentence_blur = _bar_sentence(page)
            rects_blur = _bar_text_rects(page, bar_name)
            blurred = _shot(page, clip)
            print(
                f"TC-FE-PAINT-UNDER-UI-PX {focus_label} sentence {sentence_focus!r} "
                f"vs {sentence_blur!r}",
                flush=True,
            )
            if sentence_focus != sentence_blur:
                problems.append(
                    f"{focus_label}: bar sentence {sentence_focus!r} != {sentence_blur!r}"
                )
            _diff_bar_outside_text(
                blurred,
                focused,
                clip,
                rects_focus + rects_blur,
                focus_label,
                problems,
            )
            _blur_focus(page)
    return problems


def _band_problems(report, label):
    """Holes longer than 1 device px, and every inner gap in [2.0, 4.0]."""
    problems = []
    bits = []
    edges = (report or {}).get("edges") or {}
    if not edges:
        problems.append(f"{label}: {(report or {}).get('error') or 'no edge report'}")
        return problems, ""
    for name in ("NE", "SE", "SW", "NW"):
        edge = edges.get(name) or {}
        bits.append(
            f"{name} {edge.get('min')}/{edge.get('max')} speck={edge.get('speck')} n={edge.get('samples')} "
            f"hole={edge.get('hole')} along {edge.get('start')}-{edge.get('end')}"
            + (" skipped" if edge.get("skipped") else "")
            + (" missing" if edge.get("missing") else "")
        )
        if edge.get("skipped"):
            continue
        if edge.get("missing") or not edge.get("samples"):
            problems.append(
                f"{label} {name}: no solid cream between the vertex-gap endpoints"
            )
            continue
        if edge.get("hole", 0) > 1:
            problems.append(
                f"{label} {name}: cream hole {edge.get('hole')} device px, want ≤1"
            )
        gap_min = edge.get("min")
        gap_max = edge.get("max")
        if gap_min is None or gap_max is None or gap_min < 2 or gap_max > 4:
            problems.append(
                f"{label} {name}: inner gap {gap_min}–{gap_max}, want 2.0–4.0"
            )
    return problems, " ".join(bits)


def _band_on_cell(page, label, focus="api", scroll=0):
    """Walk (3,3). ``focus`` is ``api`` or ``tab``."""
    problems = []
    dpr = _dpr(page)
    dismiss_selection(page)
    _blur_focus(page)
    _silence_toast(page)
    set_village_scroll(page, scroll)
    page.wait_for_timeout(80)

    def _focus():
        if focus == "tab":
            return _tab_to_cell(page, 3, 3)
        return _focus_visible_cell(page, 3, 3)

    def _moved(left, right):
        if not left or not right or not left.get("tips") or not right.get("tips"):
            return True
        return abs(left["cx"] - right["cx"]) > 0.5 or abs(left["cy"] - right["cy"]) > 0.5

    # Land keyboard scroll first, then photograph the unfocused cell there.
    if not _focus():
        problems.append(f"{label}: cell did not take {focus} focus")
        return problems
    page.wait_for_timeout(40)
    _blur_focus(page)
    page.wait_for_timeout(120)
    _require_clean_paint(page, problems, label)
    face = cell_top_face(page, 3, 3) or {}
    if face.get("error") or not face.get("tips"):
        problems.append(f"{label}: {face.get('error')}")
        return problems
    clip = _align_device_clip(_paint_clip(page, face, margin=16), dpr)
    before = _device_shot(page, clip)
    if not _focus():
        problems.append(f"{label}: cell did not take {focus} focus for the ring")
        return problems
    page.wait_for_timeout(40)
    face_now = cell_top_face(page, 3, 3) or {}
    if _moved(face, face_now):
        _blur_focus(page)
        page.wait_for_timeout(80)
        face = cell_top_face(page, 3, 3) or {}
        if not face.get("tips"):
            problems.append(f"{label}: face moved and could not be reread")
            return problems
        clip = _align_device_clip(_paint_clip(page, face, margin=16), dpr)
        before = _device_shot(page, clip)
        if not _focus():
            problems.append(f"{label}: cell did not take {focus} focus after the reshoot")
            return problems
        page.wait_for_timeout(40)
        face_now = cell_top_face(page, 3, 3) or {}
        if _moved(face, face_now):
            problems.append(f"{label}: focusing moved the cell between the two shots")
            return problems
    face = face_now
    report = ring_band_walk(
        before,
        _device_shot(page, clip),
        face,
        clip,
        dpr=dpr,
        occluders=_overlay_rects(page),
    )
    found, text = _band_problems(report, label)
    problems.extend(found)
    print(f"TC-FE-RING-BAND-WALK {label} {text}", flush=True)
    _blur_focus(page)
    return problems


def _band_matrix(page, scale_label, focus="api"):
    problems = []
    scrolls = (0, 366)
    viewports = ((1280, 720), (1100, 800), (390, 844))
    if scale_label != "dsf1":
        viewports = ((1280, 720), (1100, 800))
    for width, height in viewports:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(80)
        if "場景 2" not in _scene_aria(page):
            _enter_new_build_scene2(page)
        for scroll in scrolls:
            set_village_scroll(page, scroll)
            page.wait_for_timeout(40)
            label = f"{scale_label} {width}x{height} scroll {scroll}"
            # 1100 dsf2 is the Tab path. Other stations stay on focus().
            mode = focus
            if scale_label == "dsf2" and width == 1100:
                mode = "tab"
                label = f"{scale_label} {width}x{height} scroll {scroll} Tab (3,3)"
            problems.extend(_band_on_cell(page, label, mode, scroll))
    return problems


def _hide_ring_paint(page):
    return page.evaluate(
        """() => {
          const el = document.getElementById('focusRingPaint');
          if (!el) return false;
          el.setAttribute('data-kt-ring-vis', el.style.visibility || '');
          el.style.visibility = 'hidden';
          return true;
        }"""
    )


def _restore_ring_paint(page):
    page.evaluate(
        """() => {
          document.querySelectorAll('[data-kt-ring-vis]').forEach((el) => {
            el.style.visibility = el.getAttribute('data-kt-ring-vis') || '';
            el.removeAttribute('data-kt-ring-vis');
          });
        }"""
    )


def _corner_pair(page, selector, label, problems):
    """Bar or palette corners, ring shown against ring hidden. ≤2 levels."""
    rect = surface_rect(page, selector)
    if not rect:
        problems.append(f"{label}: {selector} has no rect")
        return
    grown = {
        "left": rect["left"] - 6,
        "top": rect["top"] - 6,
        "right": rect["right"] + 6,
        "bottom": rect["bottom"] + 6,
    }
    clip = _align_device_clip(_rect_clip(page, grown), _dpr(page))
    if not clip:
        problems.append(f"{label}: {selector} clip is empty")
        return
    shown = _device_shot(page, clip)
    hidden_ok = _hide_ring_paint(page)
    try:
        if not hidden_ok:
            problems.append(f"{label}: ring layer not found to hide")
        page.wait_for_timeout(40)
        hidden = _device_shot(page, clip)
    finally:
        _restore_ring_paint(page)
    delta = corner_level_delta(hidden, shown, 22, dpr=_dpr(page))
    sample = (delta or {}).get("sample")
    print(
        f"TC-FE-PAINT-UNDER-UI-PX corner {label} {selector} "
        f"max {None if not delta else delta.get('max')} "
        f"over {None if not delta else delta.get('over')} sample {sample}",
        flush=True,
    )
    if not delta or delta.get("max") is None:
        problems.append(f"{label} {selector}: corner shots differ in size")
    elif delta["max"] > 2:
        painted = ""
        if sample:
            painted = (
                f" ({sample.get('before')} → {sample.get('after')} "
                f"Δ{sample.get('delta')} at {sample.get('x')},{sample.get('y')})"
            )
        problems.append(
            f"{label} {selector}: corner antialias Δ{delta['max']} levels{painted}, want ≤2"
        )


def _hug_problems_px(page, label, problems, expect):
    """Clip hole must hug the painted extent within 1 device px.

    ``expect`` is ``palette`` or ``cta``. A missing cover is itself a
    failure, so a hidden control cannot skip the check.
    """
    report = paint_cover_report(page) or {}
    covers = report.get("covers") or []
    dpr = report.get("dpr") or 1
    brief = []
    for row in covers:
        outward = row.get("outward")
        if outward:
            sides = {name: round(value, 2) for name, value in outward.items()}
        else:
            sides = None
        brief.append(
            f"{row.get('id')} outset {row.get('outset')} outward {sides} "
            f"ringHits {row.get('ringHits')}"
        )
    print(f"TC-FE-PAINT-UNDER-UI-PX hug {label} dpr {dpr} {'; '.join(brief)}", flush=True)
    wanted = "btnBuild" if expect == "cta" else "palette"
    if not any(row.get("id") == wanted for row in covers):
        problems.append(f"{label}: {wanted} has no painted extent")
        return
    for row in covers:
        name = row.get("id")
        outward = row.get("outward")
        if outward:
            worst = max(outward.values())
            tight = min(outward.values())
            if worst > 1:
                css = worst / dpr
                zone = " dead zone" if css >= 40 else ""
                problems.append(
                    f"{label} {name}: hug cut {worst:.1f} device px "
                    f"({css:.1f} CSS px){zone}, want ≤1 device px"
                )
            elif tight < -1:
                problems.append(
                    f"{label} {name}: clip is {abs(tight):.1f} device px inside "
                    f"the painted extent, want ≤1"
                )
        elif row.get("ringHits"):
            problems.append(
                f"{label} {name}: ring meets the painted extent and is not cut to it"
            )


def _corner_levels(page, scale_label):
    """Ring-present vs ring-hidden at the rounded bar and palette corners."""
    problems = []
    dpr_note = scale_label
    viewports = ((1280, 720),) if scale_label == "dsf1" else ((1100, 800),)
    for width, height in viewports:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(80)
        if "場景 2" not in (_scene_aria(page) or ""):
            _enter_new_build_scene2(page)
        _open_palette(page)
        dismiss_selection(page)
        _blur_focus(page)
        set_village_scroll(page, 0)
        page.wait_for_timeout(80)
        label = f"{dpr_note} {width}x{height}"
        if not _focus_visible_cell(page, 3, 3):
            problems.append(f"{label}: cell did not focus")
            continue
        page.wait_for_timeout(40)
        _corner_pair(page, "#readyBar", label, problems)
        _corner_pair(page, "#palette", label, problems)
        _hug_problems_px(page, label, problems, "palette")
        _blur_focus(page)
    return problems


def _scene1_cta_px(page, problems):
    """Scene 1 build button is a cover: no ring paint in its rect, and the guard."""
    page.set_viewport_size({"width": 1280, "height": 720})
    page.wait_for_timeout(80)
    _restore_scene1(page)
    page.wait_for_timeout(80)
    if "場景 1" not in (_scene_aria(page) or ""):
        problems.append(f"scene1 cta: landed in {_scene_aria(page)!r}")
        return
    placed = _place_cell_over_cta(page) or {}
    print(f"TC-FE-PAINT-UNDER-UI-PX scene1 cta place {placed}", flush=True)
    cell = (placed.get("c"), placed.get("r"))
    if not placed.get("ok") or cell[0] is None:
        problems.append(f"scene1 cta: could not lay a cell on the button ({placed})")
        return
    dismiss_selection(page)
    _blur_focus(page)
    page.wait_for_timeout(80)
    rect = _painted_extent(page, "#townMap .cta")
    clip = _rect_clip(page, rect)
    if not clip:
        problems.append("scene1 cta: button has no on-screen rect")
        return
    before = _shot(page, clip)
    if not _focus_visible_cell(page, cell[0], cell[1]):
        problems.append(f"scene1 cta: ({cell[0]},{cell[1]}) did not focus")
        return
    page.wait_for_timeout(40)
    _paint_guard_problems(page, "scene1 cta", problems)
    _hug_problems_px(page, "scene1 cta", problems, "cta")
    after = _shot(page, clip)
    diff = changed_pixel_count(before, after)
    print(f"TC-FE-PAINT-UNDER-UI-PX scene1 cta diff {diff}", flush=True)
    if diff is None:
        problems.append("scene1 cta: screenshots differ in size")
    elif diff:
        problems.append(f"scene1 cta: {diff} px changed inside .cta")
    _blur_focus(page)


def _guard_sweep_px(page, problems):
    """Z-order of the ring and mark across scene, scroll, resize, and a sheet."""
    page.set_viewport_size({"width": 1280, "height": 720})
    page.wait_for_timeout(80)
    if "場景 2" not in (_scene_aria(page) or ""):
        _enter_new_build_scene2(page)
    _open_palette(page)
    set_village_scroll(page, 366)
    page.wait_for_timeout(80)
    _focus_visible_cell(page, 3, 3)
    page.wait_for_timeout(40)
    _paint_guard_problems(page, "scene2 palette scroll 366", problems)
    _blur_focus(page)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(80)
    if "場景 2" not in (_scene_aria(page) or ""):
        _enter_new_build_scene2(page)
    _focus_visible_cell(page, 3, 3)
    page.wait_for_timeout(40)
    _paint_guard_problems(page, "scene2 resize 390", problems)
    _blur_focus(page)
    page.set_viewport_size({"width": 1280, "height": 720})
    page.wait_for_timeout(80)
    if not _open_scene3_for_guard(page):
        problems.append("scene 3 guard: #uxPlaceBar did not open")
    else:
        _focus_visible_cell(page, 3, 3)
        page.wait_for_timeout(40)
        _paint_guard_problems(page, "scene3 uxPlaceBar", problems)
        _blur_focus(page)
    _cancel_scene3(page)
    _scene1_cta_px(page, problems)
    _scroll_cell_into_view(page, 6, 0)
    tap_cell_centre(page, 6, 0)
    try:
        page.locator("#actionSheet").wait_for(state="visible", timeout=8000)
    except Exception:
        problems.append("sheet guard: #actionSheet did not open")
    else:
        _blur_focus(page)
        page.wait_for_timeout(40)
        _paint_guard_problems(page, "sheet open", problems)
        _close_sheet(page)


@pytest.mark.case_id("TC-FE-PAINT-UNDER-UI-PX")
def test_paint_under_ui_px(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-PAINT-UNDER-UI-PX 選中線和焦點環不得畫進清單、確認欄、抽屜或銀行面板。

    基準是清單打開、沒有選中、沒有焦點。捲動 0 和 366 各比一次。
    鍵盤打開銀行面板時，面板矩形裡的差也是 0。
    #readyBar 和抽屜是 guard，現在通過，保持通過。
    底尖靠近確認欄的格子（1280 是 (3,4)、(2,5)；其他視窗用活矩形挑）
    兩次像素差的句子都必須相同，文字也要斷言相等。聚焦：該格已選中，
    失焦和聚焦各拍一張。選中線：同一格保持選中且失焦，一張標記層在畫，
    另一張把標記層設成 visibility:hidden（測完還原）。文字節點矩形
    （外擴 1px）以外的像素差是 0。不放寬容差，也不把圓角帶排除。
    確認欄句子的 text-shadow 是 none。圓角外面的三角仍在矩形裡，
    不得有環或選中線，也不要求那裡看得到環。
    焦點環和選中標記在最近的共同堆疊上下文裡，有效 z 必須嚴格低於
    每一個看得見的確認欄、調色盤，以及場景 1 的 `.cta`（#btnBuild）。
    蓋住的範圍是畫出來的外緣：border box，加上當時 `::before` 伸出
    border box 的距離（計算樣式，沒有生成或沒有伸出就是 0）。不是 4px，
    也不是 48px。環的 clip 洞每一邊離這條外緣不得超過 1 個裝置像素。
    向外超過 1 是死區（調色盤外 48 螢幕 px 的洞要紅）。環的盒子壓在
    外緣上卻沒有對上的洞，也是沒裁。場景 1 先把一格的南尖捲到
    「我要起屋」上再聚焦，按鈕畫出來的外緣裡像素差是 0。
    場景 3、面板打開、捲動 366、改視窗都查。環若是 canvas，這些蓋住的
    矩形對到的裝置像素 alpha 全是 0；若是沒有 clip 的 SVG，畫出來的圖形
    外框不得和它們相交。`.place-bar`、確認欄、調色盤、`.cta` 裡面不得掛著
    環或標記的繪製元素。
    確認欄和調色盤四個角（外框再外擴 6px，角上 22px 見方，不含環色和
    選中褐）在環畫著和把環層設成 visibility:hidden 時，每通道相差 ≤2。
    """
    kid_id = warehouse_ids["kid_id"]
    _ensure_bank_def(warehouse_db)
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": "銀行", "level": 1, "stored": 0, "cell_x": 6, "cell_y": 0}],
    )
    _login(page, base_url)
    problems = []

    def _diff_ui(scroll, kind):
        set_village_scroll(page, scroll)
        page.wait_for_timeout(80)
        _open_palette(page)
        _blur_focus(page)
        page.wait_for_timeout(200)
        rects = {
            "palette": surface_rect(page, "#palette"),
            "readyBar": surface_rect(page, "#readyBar"),
            "drawer": surface_rect(page, "#dr"),
        }
        clips = {name: _rect_clip(page, rect) for name, rect in rects.items()}
        before = {}
        for name, clip in clips.items():
            before[name] = _shot(page, clip) if clip else None
        if kind == "focus":
            if not _focus_visible_cell(page, 0, 6):
                problems.append(f"scroll {scroll}: (0,6) did not focus")
                return
            page.wait_for_timeout(80)
        else:
            back = page.locator("#btnUxBack")
            if back.count() and back.first.is_visible():
                back.first.click()
                page.wait_for_timeout(150)
            _ensure_scene2(page)
            set_village_scroll(page, scroll)
            _select_cell(page, 0, 6)
            _blur_focus(page)
            _open_palette(page)
            page.wait_for_timeout(120)
        for name, clip in clips.items():
            if not clip or before.get(name) is None:
                print(f"TC-FE-PAINT-UNDER-UI-PX scroll {scroll} {kind} {name} offscreen", flush=True)
                continue
            after = _shot(page, clip)
            diff = changed_pixel_count(before[name], after)
            brown = count_stroke_pixels(after)
            print(
                f"TC-FE-PAINT-UNDER-UI-PX scroll {scroll} {kind} {name} diff {diff} brown {brown}",
                flush=True,
            )
            if diff is None:
                problems.append(f"scroll {scroll} {kind} {name}: screenshot size changed")
            elif name in ("readyBar", "drawer"):
                # The ready bar's own sentence changes when a cell is chosen.
                # The guard is the paint layer, inset past the shared village edge.
                guard_clip = {
                    "x": clip["x"] + 4,
                    "y": clip["y"] + 4,
                    "width": max(1, clip["width"] - 8),
                    "height": max(1, clip["height"] - 8),
                }
                guard_diff = paint_overlay_count(before[name], after, clip, guard_clip)
                if guard_diff:
                    problems.append(
                        f"guard {name} scroll {scroll} {kind}: {guard_diff} paint px"
                    )
            elif diff:
                problems.append(
                    f"scroll {scroll} {kind} {name}: {diff} px changed inside the live rect "
                    f"({brown} #7c2d12)"
                )

    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    _diff_ui(0, "focus")
    dismiss_selection(page)
    _blur_focus(page)
    _relogin(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    _diff_ui(0, "select")
    _relogin(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    _diff_ui(366, "focus")
    _relogin(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    _diff_ui(366, "select")

    _relogin(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _restore_scene1(page)
    _scroll_cell_into_view(page, 6, 0)
    tap_cell_centre(page, 6, 0)
    page.locator("#actionSheet").wait_for(state="visible", timeout=8000)
    _blur_focus(page)
    page.wait_for_timeout(200)
    sheet = surface_rect(page, "#actionSheet")
    sheet_clip = _rect_clip(page, sheet)
    if not sheet_clip:
        problems.append("bank sheet has no on-screen rect for the baseline")
    else:
        before_sheet = _shot(page, sheet_clip)
        _close_sheet(page)
        page.wait_for_timeout(150)
        if not _focus_visible_cell(page, 6, 0):
            problems.append("bank cell did not take keyboard focus")
        else:
            page.keyboard.press("Enter")
            page.wait_for_timeout(250)
            if not page.locator("#actionSheet").is_visible():
                problems.append("keyboard did not open the bank sheet")
            else:
                after_sheet = _shot(page, sheet_clip)
                diff = changed_pixel_count(before_sheet, after_sheet)
                ring = ring_layer_pixels(page) or {}
                print(
                    f"TC-FE-PAINT-UNDER-UI-PX bank diff {diff} ring {ring.get('pixels')}",
                    flush=True,
                )
                if diff:
                    problems.append(
                        f"bank sheet: {diff} px changed inside the sheet "
                        f"(ring layer {ring.get('pixels')} px)"
                    )
    problems.extend(_paint_near_bar_px(page))
    problems.extend(_corner_levels(page, "dsf1"))
    browser = page.context.browser
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        device_scale_factor=2,
    )
    other = context.new_page()
    try:
        other.route("https://image.pollinations.ai/**", lambda route: route.abort())
        _login(other, base_url)
        _enter_new_build_scene2(other)
        problems.extend(_corner_levels(other, "dsf2"))
    finally:
        context.close()
    _guard_sweep_px(page, problems)
    assert not problems, "TC-FE-PAINT-UNDER-UI-PX: " + " | ".join(problems[:12])


def _vertex_matrix(page, scale_label):
    """Four viewports. Gap is the chord between cream-band ends, not tip-to-band."""
    problems = []
    dpr = _dpr(page)
    viewports = ((1280, 720), (1100, 800), (390, 844), (844, 390))
    for width, height in viewports:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(100)
        if "場景 2" not in _scene_aria(page):
            _enter_new_build_scene2(page)
        dismiss_selection(page)
        _blur_focus(page)
        _silence_toast(page)
        set_village_scroll(page, 0)
        _scroll_cell_into_view(page, 3, 3)
        page.wait_for_timeout(200)
        label = f"{scale_label} {width}x{height}"
        _require_clean_paint(page, problems, label)
        face = cell_top_face(page, 3, 3) or {}
        if face.get("error") or not face.get("tips"):
            problems.append(f"{label}: {face.get('error')}")
            continue
        clip = _align_device_clip(_paint_clip(page, face, margin=24), dpr)
        before = _device_shot(page, clip)
        if not _focus_visible_cell(page, 3, 3):
            problems.append(f"{label}: cell did not focus")
            continue
        page.wait_for_timeout(40)
        report = ring_vertex_gaps(before, _device_shot(page, clip), face, clip, dpr=dpr)
        length = report.get("length")
        vertices = report.get("vertices") or {}
        edges = report.get("edges") or {}
        bits = []
        for name in ("N", "E", "S", "W"):
            vertex = vertices.get(name) or {}
            a = vertex.get("a") or {}
            b = vertex.get("b") or {}
            bits.append(
                f"{name} {vertex.get('gap')} "
                f"({a.get('x')},{a.get('y')})-({b.get('x')},{b.get('y')})"
            )
        solid_bits = " ".join(
            f"{name} {((edges.get(name) or {}).get('solid'))}"
            for name in ("NE", "SE", "SW", "NW")
        )
        print(
            f"TC-FE-RING-VERTEX-GAP {label} length {length} "
            + " ".join(bits)
            + " solid "
            + solid_bits,
            flush=True,
        )
        gaps = {}
        for name in ("N", "E", "S", "W"):
            gap = (vertices.get(name) or {}).get("gap")
            gaps[name] = gap
            a = (vertices.get(name) or {}).get("a") or {}
            b = (vertices.get(name) or {}).get("b") or {}
            coord = f"({a.get('x')},{a.get('y')})-({b.get('x')},{b.get('y')})"
            if gap is None or gap < 4 or gap > 10:
                problems.append(f"{label} {name}: gap {gap}px {coord}, want 4–10")
        if None not in (gaps["N"], gaps["S"]) and abs(gaps["N"] - gaps["S"]) > 2:
            problems.append(
                f"{label}: |N−S| {abs(gaps['N'] - gaps['S']):.2f}px, want ≤2"
            )
        if None not in (gaps["E"], gaps["W"]) and abs(gaps["E"] - gaps["W"]) > 2:
            problems.append(
                f"{label}: |E−W| {abs(gaps['E'] - gaps['W']):.2f}px, want ≤2"
            )
        if length is not None and length >= 40:
            for name in ("NE", "SE", "SW", "NW"):
                solid = (edges.get(name) or {}).get("solid")
                if solid is None or solid < 0.80:
                    problems.append(
                        f"{label} {name}: solid {solid} on a {length}px edge, want ≥0.80"
                    )
        _blur_focus(page)
    return problems


def _vertex_at_scale(page, base_url, scale):
    browser = page.context.browser
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        device_scale_factor=scale,
    )
    problems = []
    other = context.new_page()
    try:
        other.route("https://image.pollinations.ai/**", lambda route: route.abort())
        _login(other, base_url)
        _enter_new_build_scene2(other)
        problems.extend(_vertex_matrix(other, f"dsf{scale}"))
    finally:
        context.close()
    return problems


@pytest.mark.case_id("TC-FE-RING-VERTEX-GAP")
def test_ring_vertex_gap(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-RING-VERTEX-GAP 尖角開口是兩條實線帶內端的直線距離。

    不是尖角到帶的距離。每條開口 4–10 螢幕 px。對角（北對南、東對西）相差 ≤2px。
    邊上實線比例 ≥0.80 只在螢幕邊長 ≥40px 時要求。視窗 1280×720、1100×800、
    390×844、844×390，deviceScaleFactor 1 和 2。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    problems = []
    problems.extend(_vertex_matrix(page, "dsf1"))
    problems.extend(_vertex_at_scale(page, base_url, 2))
    assert not problems, "TC-FE-RING-VERTEX-GAP: " + " | ".join(problems[:12])


@pytest.mark.case_id("TC-FE-RING-BAND-WALK")
def test_ring_band_walk(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-RING-BAND-WALK 實線奶油帶裡不得有超過 1 裝置像素的洞。

    四個尖角的開口是 TC-FE-RING-VERTEX-GAP 的那兩個內端，設計 5–8px、
    接受 4–10px，不算洞。連續走的只是每一條邊兩個內端之間的那段。
    步進是 1 個裝置像素。那段裡面，沒有奶油的連續樣本不得長過 1 裝置像素，
    每一個打中奶油的樣本內緣都在 2.0–4.0。內端外面、走進尖角開口的部分不查。
    欄和調色盤蓋住的樣本跳過，不算洞。
    1100×800、deviceScaleFactor 2，捲動 0 和 366，用 Tab 把焦點送到 (3,3)，
    不是 element.focus()。那一組的內緣也要在 2.0–4.0，洞不得長過 1 裝置像素。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    problems = []
    problems.extend(_band_matrix(page, "dsf1"))
    browser = page.context.browser
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        device_scale_factor=2,
    )
    other = context.new_page()
    try:
        other.route("https://image.pollinations.ai/**", lambda route: route.abort())
        _login(other, base_url)
        _enter_new_build_scene2(other)
        problems.extend(_band_matrix(other, "dsf2"))
    finally:
        context.close()
    assert not problems, "TC-FE-RING-BAND-WALK: " + " | ".join(problems[:12])
