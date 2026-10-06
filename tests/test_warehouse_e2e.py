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
    ADJACENT_BACKGROUNDS,
    GOLD_STROKE,
    REQUIRED_STROKE,
    any_visible_gold_point,
    bar_gap_band,
    cell_clip_band,
    cell_top_face,
    edge_outward_points,
    cell_under_point,
    cell_visibility,
    chosen_mark_paint,
    contrast_ratio,
    corner_insets,
    focus_pixel_report,
    focus_ring_shape,
    gold_point_inside,
    hex_of,
    hidden_tab_state,
    in_fractional_outer_band,
    inclusive_border_samples,
    integer_border_row,
    map_hit_at,
    outside_edge_points,
    off_visible_probes,
    open_solid_rects,
    parse_hex,
    point_is_ring_ink,
    sample_line_backgrounds,
    sample_selected_edges,
    selection_pixel_report,
    count_stroke_pixels,
    changed_pixel_count,
    png_rgb,
    paint_layer_state,
    ring_layer_pixels,
    stroke_near_cell,
    stroke_outer_rays,
    paint_cover_report,
    ring_edge_report,
    paint_overlay_count,
    bar_ink_count,
    selected_mark_geometry,
    scroll_for_cell_point,
    set_village_scroll,
    solid_selector,
    surface_rect,
    village_box,
    visible_gold_points,
    toast_off_visible_probes,
    visible_gold_under_toast,
)
from tests.town_tap import (  # noqa: E402
    _activate_point,
    _scroll_cell_into_view,
    cell_access,
    cell_points,
    dismiss_selection,
    point_cover,
    point_in_rect,
    press_cell,
    read_reaction,
    sprite_overlap_point,
    tap_cell_centre,
    tap_labeled_button,
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
    tap_cell_centre(page, CELL_X, CELL_Y)
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


def _click_cell(page, cell_x, cell_y, timeout=None):
    """Pointer-tap the cell's visual diamond centre, not the button box."""
    col = cell_x + 1
    row = cell_y + 1
    pad = page.locator("#townMap").get_by_role(
        "button",
        name=re.compile(rf"第\s*{col}\s*欄第\s*{row}\s*行"),
    )
    assert pad.count() > 0, f"missing pad 第 {col} 欄第 {row} 行"
    tap_cell_centre(page, cell_x, cell_y, timeout=timeout)


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


_RENDERED_PADS_JS = r"""
() => {
  const cells = [];
  for (const pad of document.querySelectorAll('#townMap .pad')) {
    const cs = getComputedStyle(pad);
    const c = parseInt(cs.getPropertyValue('--c'), 10);
    const r = parseInt(cs.getPropertyValue('--r'), 10);
    if (!Number.isFinite(c) || !Number.isFinite(r)) continue;
    const sprite = pad.querySelector(':scope > img.sprite, :scope > .sprite');
    const cap = pad.querySelector(':scope > .cap');
    let name = '';
    if (sprite && !sprite.hidden) {
      const scs = getComputedStyle(sprite);
      const box = sprite.getBoundingClientRect();
      if (scs.display !== 'none' && scs.visibility !== 'hidden' && box.width > 2 && box.height > 2) {
        name = (sprite.getAttribute('alt') || '').trim();
      }
    }
    if (!name && cap && !cap.hidden) {
      const ccs = getComputedStyle(cap);
      if (ccs.display !== 'none' && ccs.visibility !== 'hidden') {
        name = (cap.textContent || '').trim();
      }
    }
    cells.push({c, r, name});
  }
  return cells;
}
"""


def _rendered_tap_kinds(page, catalog):
    """select, occupied, or unfit from the painted map.

    Gold is the rendered gold-mark set. Covered cells are the footprints of
    the buildings whose sprites are actually on the map (catalog side, default
    2). A gold cell is selectable even if a footprint also lists it. Every
    other empty cell, overlap or out of the grid, is unfit.
    """
    gold = set(_mark_gold_cells(page))
    by_name = {item.get("name"): _square_side(item) for item in catalog}
    covered = set()
    for fact in page.evaluate(_RENDERED_PADS_JS):
        name = fact.get("name") or ""
        if not name:
            continue
        side = by_name.get(name, 2)
        for dy in range(side):
            for dx in range(side):
                cell = (fact["c"] + dx, fact["r"] + dy)
                if 0 <= cell[0] < MAP_N and 0 <= cell[1] < MAP_N:
                    covered.add(cell)
    kinds = {}
    for y in range(MAP_N):
        for x in range(MAP_N):
            cell = (x, y)
            if cell in gold:
                kinds[cell] = "select"
            elif cell in covered:
                kinds[cell] = "occupied"
            else:
                kinds[cell] = "unfit"
    return kinds


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

    tap_cell_centre(page, 0, 0)
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
                tap_labeled_button(page, shop_pad.first)
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
    # (1,0) is inside the gym footprint at (0,0). It is covered, not an empty overlap.
    _click_cell(page, 1, 0)
    covered = _wait_toast(page)
    problems.extend(
        [f"covered (1,0): {item}" for item in _toast_info_problems(covered, OCCUPIED_TOAST)]
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


def _clear_toast(page):
    page.evaluate(
        """() => {
          const el = document.getElementById('toast');
          if (!el) return;
          el.style.display = 'none';
          el.textContent = '';
          el.className = '';
        }"""
    )


def _chosen_cells(page):
    return page.evaluate(
        """() => {
          const hits = [];
          for (const pad of document.querySelectorAll('#townMap .pad')) {
            const btn = pad.querySelector('.cell-btn');
            const label = btn ? (btn.getAttribute('aria-label') || '') : '';
            const badge = pad.querySelector(':scope > .badge');
            let badgeText = '';
            if (badge && !badge.hidden) {
              const cs = getComputedStyle(badge);
              const box = badge.getBoundingClientRect();
              if (cs.display !== 'none' && cs.visibility !== 'hidden' && box.width > 1) {
                badgeText = (badge.textContent || '').trim();
              }
            }
            const chosen = pad.classList.contains('is-chosen')
              || label.includes('已選此格') || label.includes('已揀呢格')
              || badgeText === '此格' || badgeText === '呢格';
            if (chosen) hits.push(label || badgeText || '?');
          }
          return hits;
        }"""
    )


def _visible_errors(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('.error')].filter((el) => {
          const cs = getComputedStyle(el);
          const box = el.getBoundingClientRect();
          return cs.display !== 'none' && cs.visibility !== 'hidden'
            && box.width > 1 && (el.textContent || '').trim();
        }).map((el) => (el.textContent || '').trim().slice(0, 80))"""
    )


def _reject_ui_problems(page, toast, mode, building_name, forbidden):
    """Scene 3 confirm failed closed: info toast, Scene 2, selection cleared."""
    problems = list(_toast_info_problems(toast, CANNOT_FIT_TOAST))
    scene = _scene_aria(page)
    if "場景 2" not in scene:
        problems.append(f"scene {scene!r}, expected 場景 2")
    if "場景 3" in scene:
        problems.append(f"still in 場景 3 ({scene!r})")
    chosen = _chosen_cells(page)
    if chosen:
        problems.append(f"cell still chosen: {chosen[:4]}")
    disabled, label = _go_disabled(page)
    if not disabled:
        problems.append(f"「選擇位置」 enabled (button {label!r})")
    hint = _hint(page)["ready"]
    if mode == "unstore":
        expected = f"請點選空地，放回「{building_name}」。不扣除金幣和材料。"
        if hint != expected:
            problems.append(f"hint {hint!r}, expected {expected!r}")
    else:
        if not str(hint).startswith("請點選金色空地"):
            problems.append(f"hint {hint!r} should start with 請點選金色空地")
        pressed = False
        btn = page.locator("#palette").get_by_role(
            "button", name=re.compile(re.escape(building_name))
        )
        if btn.count() and btn.first.get_attribute("aria-pressed") == "true":
            pressed = True
        if building_name not in (hint or "") and not pressed:
            problems.append(f"building {building_name} was cleared. hint={hint!r}")
    toast_text = toast.get("text") or ""
    body = page.locator("body").inner_text() if any(len(phrase) > 2 for phrase in forbidden) else ""
    for phrase in forbidden:
        if not phrase:
            continue
        if phrase in toast_text:
            problems.append(f"toast contains {phrase!r}")
        if len(phrase) > 2 and phrase in body:
            problems.append(f"page contains {phrase!r}")
    errors = _visible_errors(page)
    if errors:
        problems.append(f"visible .error {errors[:3]}")
    return problems


def _catalog_defs(base_url):
    """Live `/api/building-defs` order. That array is the catalog order."""
    import urllib.request

    with urllib.request.urlopen(base_url + "/api/building-defs", timeout=15) as resp:
        data = json.loads(resp.read().decode())
    assert isinstance(data, list) and data, f"/api/building-defs returned {data!r}"
    return data


def _square_side(item):
    if not isinstance(item, dict) or item.get("footprint") in (None, ""):
        return 2
    try:
        size = int(item.get("footprint"))
    except (TypeError, ValueError):
        return 2
    return size if size >= 1 else 2


def _sw_facts():
    path = os.path.join(REPO, "service-worker.js")
    text = open(path, encoding="utf-8").read()
    cache = re.search(r"const\s+CACHE_NAME\s*=\s*['\"]([^'\"]+)['\"]", text)
    static = re.search(r"const\s+STATIC_CACHE\s*=\s*['\"]([^'\"]+)['\"]", text)
    block = re.search(r"const\s+PRECACHE_URLS\s*=\s*\[(.*?)\]", text, re.S)
    assert cache and static and block, "service-worker.js is missing cache constants"
    urls = re.findall(r"['\"]([^'\"]+)['\"]", block.group(1))
    return cache.group(1), static.group(1), urls


def _wait_active_worker(page, timeout=10000):
    """Poll until getRegistration() has an active worker.

    A Promise is truthy, so the predicate must return a boolean. Returning
    the registration promise would make wait_for_function succeed immediately.
    """
    try:
        page.wait_for_function(
            """() => {
              const slot = window.__ktSw || (window.__ktSw = { pending: false, active: false });
              if (!slot.pending) {
                slot.pending = true;
                navigator.serviceWorker.getRegistration().then((reg) => {
                  slot.active = !!(reg && reg.active);
                  slot.pending = false;
                }).catch(() => { slot.pending = false; });
              }
              return slot.active === true;
            }""",
            timeout=timeout,
        )
        return True
    except Exception:
        return False


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
    """TC-FE-BUILD-UNFIT-PRESELECT (c) 伺服器 400 回到場景 2，清掉選格，按鈕停用。"""
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
    building = BUILDING_NAME if mode == "unstore" else "健身室"
    problems = _reject_ui_problems(page, toast, mode, building, [RANGE_ERROR, "Request failed"])
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


def _open_scene3(page, mode):
    if mode == "unstore":
        opened = _open_takeout_scene2(page)
        assert opened is None, "TC-FE-CONFIRM: " + opened
        _click_cell(page, 0, 0)
    else:
        _enter_new_build_scene2(page)
        _click_cell(page, 0, 0)
        _pick_unbuilt(page, "健身室")
    advance = page.locator("#btnToScene3")
    if advance.count() and advance.first.is_visible() and advance.first.is_enabled():
        advance.first.click()
    page.locator("#btnUxConfirm").wait_for(state="visible", timeout=8000)


def _force_confirm_response(page, mode, status, body, content_type):
    def handle(route):
        request = route.request
        if request.method != "POST":
            route.continue_()
            return
        url = request.url
        unstore = "/unstored" in url
        build = (
            "/buildings" in url
            and not unstore
            and "/move" not in url
            and "/store" not in url
            and "/upgrade" not in url
        )
        if (mode == "unstore" and unstore) or (mode == "new-build" and build):
            route.fulfill(status=status, content_type=content_type, body=body)
            return
        route.continue_()

    page.route("**/api/kids/**", handle)


_GENERIC_BODIES = (
    ("plain", 400, "text/plain", "Bad Request", ("Bad Request", "Request failed")),
    ("detail", 400, "application/json", json.dumps({"detail": "x"}), ("Request failed", '{"detail":"x"}')),
    (
        "occupied",
        409,
        "application/json",
        json.dumps({"error": OCCUPIED_RED}, ensure_ascii=False),
        (OCCUPIED_RED, "Request failed"),
    ),
    ("empty", 422, "text/plain", "", ("Request failed",)),
)


@pytest.mark.case_id("TC-FE-CONFIRM-GENERIC-4XX")
@pytest.mark.parametrize("mode", ["new-build", "unstore"])
@pytest.mark.parametrize(
    "label,status,content_type,body,forbidden",
    _GENERIC_BODIES,
    ids=[item[0] for item in _GENERIC_BODIES],
)
def test_confirm_generic_4xx(
    page, base_url, warehouse_db, warehouse_ids, mode, label, status, content_type, body, forbidden
):
    """TC-FE-CONFIRM-GENERIC-4XX 確認 POST 的未知 4xx 也回到場景 2。"""
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
    _open_scene3(page, mode)
    _force_confirm_response(page, mode, status, body, content_type)
    page.locator("#btnUxConfirm").click()
    toast = _wait_toast(page)
    building = BUILDING_NAME if mode == "unstore" else "健身室"
    problems = _reject_ui_problems(page, toast, mode, building, list(forbidden))
    if not _resources_same(warehouse_db, kid_id, before_points, before_items):
        problems.append("resources changed")
    if _kid_rows(warehouse_db, kid_id) != before_rows:
        problems.append("rows changed")
    assert not problems, (
        f"TC-FE-CONFIRM-GENERIC-4XX {mode} {label} HTTP {status}: " + " | ".join(problems)
    )


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


def _placed_blocks(rows, catalog):
    by_name = {item.get("name"): _square_side(item) for item in catalog}
    blocks = []
    for row in rows:
        if row.get("stored"):
            continue
        blocks.append((row["cell_x"], row["cell_y"], by_name.get(row["name"], 2), row["name"]))
    return blocks


def _cell_classes(blocks, catalog):
    """Gold, covered, and empty-unfit cells for the min catalog footprint."""
    sides = [_square_side(item) for item in catalog] or [2]
    min_fp = min(sides)
    gold, covered, empty_unfit = [], [], []
    for y in range(MAP_N):
        for x in range(MAP_N):
            hit = None
            for ox, oy, size, name in blocks:
                if ox <= x < ox + size and oy <= y < oy + size:
                    hit = name
                    break
            if hit:
                covered.append((x, y))
                continue
            fits = x + min_fp <= MAP_N and y + min_fp <= MAP_N
            overlap = False
            if fits:
                for ox, oy, size, _name in blocks:
                    if not (
                        x + min_fp <= ox
                        or ox + size <= x
                        or y + min_fp <= oy
                        or oy + size <= y
                    ):
                        overlap = True
                        break
            if fits and not overlap:
                gold.append((x, y))
            else:
                empty_unfit.append((x, y))
    return gold, covered, empty_unfit, min_fp


@pytest.mark.case_id("TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP")
def test_unfit_preselect_overlap(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP 未選建築時，空但重疊的格不能選。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "健身室", "level": 1, "stored": 0, "cell_x": 3, "cell_y": 0},
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 6},
        ],
    )
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    catalog = _catalog_defs(base_url)
    blocks = _placed_blocks(_kid_rows(warehouse_db, kid_id), catalog)
    gold, covered, _empty, min_fp = _cell_classes(blocks, catalog)
    problems = []
    rendered = set(_mark_gold_cells(page))
    if (2, 0) in rendered or (2, 0) in set(gold):
        problems.append(f"(2,0) is gold. rendered={sorted(rendered)[:8]} min_fp={min_fp}")
    before_rows = _kid_rows(warehouse_db, kid_id)
    before_hint = _hint(page)["ready"]
    _clear_toast(page)
    _click_cell(page, 2, 0)
    toast = _wait_toast(page)
    problems.extend(
        [f"(2,0): {item}" for item in _toast_info_problems(toast, CANNOT_FIT_TOAST)]
    )
    problems.extend(_selected_cell_problems(_cell_choice(page, 2, 0), (2, 0), False))
    after_hint = _hint(page)["ready"]
    if after_hint != before_hint:
        problems.append(f"hint changed from {before_hint!r} to {after_hint!r}")
    if "已選擇空地" in (after_hint or "") or "已揀空地" in (after_hint or ""):
        problems.append(f"hint looks selected: {after_hint!r}")
    disabled, label = _go_disabled(page)
    if not disabled:
        problems.append(f"「選擇位置」 enabled after (2,0) (button {label!r})")

    _relogin(page, base_url)
    _enter_new_build_scene2(page)
    rendered = set(_mark_gold_cells(page))
    gold, covered, empty_unfit, min_fp = _cell_classes(blocks, catalog)
    gold_set, covered_set = set(gold), set(covered)
    if rendered != gold_set:
        problems.append(
            f"rendered gold != computed gold (min footprint {min_fp}). "
            f"extra={sorted(rendered - gold_set)[:12]} missing={sorted(gold_set - rendered)[:12]}"
        )
    selectable = []
    for y in range(MAP_N):
        for x in range(MAP_N):
            cell = (x, y)
            _close_sheet(page)
            _clear_toast(page)
            try:
                _click_cell(page, x, y, timeout=3000)
            except Exception as exc:
                problems.append(f"{cell} click failed: {type(exc).__name__}: {exc}")
                _close_sheet(page)
                continue
            if cell in gold_set:
                choice = _cell_choice(page, x, y)
                if choice.get("chosen"):
                    selectable.append(cell)
                    _click_cell(page, x, y)
                    if _cell_choice(page, x, y).get("chosen"):
                        problems.append(f"{cell} stayed selected after the second tap")
                else:
                    problems.append(
                        f"gold {cell} was not selected. aria={choice.get('label')!r}"
                    )
                continue
            toast = _wait_toast(page, timeout=900)
            expected = OCCUPIED_TOAST if cell in covered_set else CANNOT_FIT_TOAST
            kind = "covered" if cell in covered_set else "empty-unfit"
            problems.extend(
                [f"{kind} {cell}: {item}" for item in _toast_info_problems(toast, expected)]
            )
            problems.extend(_selected_cell_problems(_cell_choice(page, x, y), cell, False))
            _close_sheet(page)
    if set(selectable) != rendered:
        problems.append(
            f"selectable {sorted(selectable)[:12]} != rendered gold {sorted(rendered)[:12]}"
        )
    if set(selectable) != gold_set:
        problems.append(
            f"selectable != computed gold. extra={sorted(set(selectable) - gold_set)[:8]} "
            f"missing={sorted(gold_set - set(selectable))[:8]}"
        )
    if _kid_rows(warehouse_db, kid_id) != before_rows:
        problems.append("rows changed")
    assert not problems, (
        "TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP: " + " | ".join(problems[:24])
        + (f" | ... {len(problems) - 24} more" if len(problems) > 24 else "")
    )


def _remember_pageerrors(page):
    found = []

    def _keep(exc):
        found.append(str(exc))

    page.on("pageerror", _keep)
    return found


@pytest.mark.case_id("TC-FE-SW-AUTOREG")
def test_sw_autoregisters_without_pageerror(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-SW-AUTOREG 頁面自己註冊 service worker，而且沒有 pageerror。"""
    kid_id = warehouse_ids["kid_id"]
    catalog = _catalog_defs(base_url)
    farm = next((item for item in catalog if "農" in (item.get("name") or "")), None)
    assert farm, "catalog has no building whose name contains 農"
    cache_name, _static_name, _urls = _sw_facts()
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": farm["name"], "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0}],
    )
    errors = _remember_pageerrors(page)
    page.goto(f"{base_url}/kids/")
    active = _wait_active_worker(page, timeout=10000)
    keys = page.evaluate("() => caches.keys()")
    _submit_login(page)
    page.locator("#village .cell-btn").first.wait_for(state="attached", timeout=8000)
    sweep = []
    try:
        scene = _scene_aria(page)
        if "場景 1" not in scene:
            sweep.append(f"scene 1 aria {scene!r}")
        _enter_new_build_scene2(page)
        page.locator("#listLauncher").click()
        page.locator("#palette").wait_for(state="visible", timeout=8000)
        page.locator("#ktFooter").get_by_role("button", name=re.compile("任務板")).click()
        page.wait_for_timeout(300)
        drawer = page.locator("#dr")
        if not drawer.evaluate("el => el.classList.contains('o')"):
            page.get_by_role("button", name="☰").click()
            page.locator("#dr.o").wait_for(state="visible", timeout=8000)
        page.locator("#dr").get_by_role("button", name=re.compile("儲蓄目標")).click()
        page.wait_for_timeout(300)
        page.locator("#ktFooter").get_by_role("button", name=re.compile("城鎮")).click()
        page.locator("#townMap").wait_for(state="visible", timeout=8000)
        _click_cell(page, 0, 0)
        page.wait_for_timeout(300)
    except Exception as exc:
        sweep.append(f"sweep stopped: {type(exc).__name__}: {exc}")
    problems = list(sweep)
    if not active:
        reg = page.evaluate(
            """() => navigator.serviceWorker.getRegistration().then((reg) => {
              if (!reg) return { registration: false };
              return {
                registration: true,
                active: !!(reg.active),
                state: reg.active ? reg.active.state : (reg.installing && reg.installing.state) || ''
              };
            })"""
        )
        problems.append(f"no active service worker. registration={reg}")
    if cache_name not in (keys or []):
        problems.append(f"caches.keys() {keys} does not include {cache_name}")
    if errors:
        problems.append("pageerror: " + " || ".join(errors))
    assert not problems, "TC-FE-SW-AUTOREG: " + " | ".join(problems)


def _cache_urls(page, cache_name):
    return page.evaluate(
        """async (name) => {
          const keys = await caches.keys();
          if (!keys.includes(name)) return { missing: true, keys };
          const cache = await caches.open(name);
          const reqs = await cache.keys();
          return { missing: false, keys, urls: reqs.map((req) => req.url) };
        }""",
        cache_name,
    )


def _scene1_layout(page):
    return page.evaluate(
        """() => {
          const map = document.getElementById('townMap');
          const village = document.querySelector('#townMap .village.is-iso');
          const parent = map ? map.parentElement : null;
          const tab = document.querySelector('#ktFooter .kt-footer-tab');
          const mapBox = map ? map.getBoundingClientRect() : null;
          const parentBox = parent ? parent.getBoundingClientRect() : null;
          const vcs = village ? getComputedStyle(village) : null;
          const shown = (el) => {
            if (!el) return false;
            const cs = getComputedStyle(el);
            const box = el.getBoundingClientRect();
            return cs.display !== 'none' && cs.visibility !== 'hidden' && box.width > 1 && box.height > 1;
          };
          return {
            aria: map ? (map.getAttribute('aria-label') || '') : '',
            mapShown: shown(map),
            s: vcs ? (vcs.getPropertyValue('--s') || '').trim() : '',
            left: mapBox && parentBox ? mapBox.left - parentBox.left : null,
            right: mapBox && parentBox ? parentBox.right - mapBox.right : null,
            parentClass: parent ? (parent.className || '') : '',
            nowrap: tab ? getComputedStyle(tab).whiteSpace : ''
          };
        }"""
    )


@pytest.mark.case_id("TC-FE-SW-PRECACHE")
def test_sw_precache_includes_four_scene(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-SW-PRECACHE 目前的 cache 含四場景 css/js，離線仍是場景 1。"""
    cache_name, _static_name, urls = _sw_facts()
    problems = []
    for needle in ("town-four-scene.css", "town-four-scene.js"):
        if not any(needle in url for url in urls):
            problems.append(f"PRECACHE_URLS missing {needle}. urls={urls}")
    if not any(url.rstrip("/").endswith("index.html") or url.rstrip("/").endswith("/kids") for url in urls):
        problems.append(f"PRECACHE_URLS missing index.html. urls={urls}")
    page.goto(f"{base_url}/kids/")
    active = _wait_active_worker(page, timeout=10000)
    if not active:
        keys = page.evaluate("() => caches.keys()")
        problems.append(f"service worker did not become active. caches.keys()={keys}")
    else:
        cached = _cache_urls(page, cache_name)
        if cached.get("missing"):
            problems.append(f"cache {cache_name} is absent. keys={cached.get('keys')}")
        else:
            found = " ".join(cached.get("urls") or [])
            for needle in ("town-four-scene.css", "town-four-scene.js", "index.html"):
                if needle not in found:
                    problems.append(
                        f"cache {cache_name} missing {needle}. urls={cached.get('urls')}"
                    )
    try:
        _submit_login(page)
        page.locator("#townMap").wait_for(state="visible", timeout=8000)
        page.context.set_offline(True)
        page.reload(timeout=8000, wait_until="domcontentloaded")
        page.locator("#townMap").wait_for(state="visible", timeout=8000)
        layout = _scene1_layout(page)
        if "場景 1" not in (layout.get("aria") or "") or not layout.get("mapShown"):
            problems.append(f"offline Scene 1 not shown. layout={layout}")
        try:
            scale = float(layout.get("s") or "nan")
        except ValueError:
            scale = float("nan")
        if abs(scale - 0.85) > 0.001:
            problems.append(f"--s is {layout.get('s')!r}, expected 0.85")
        left, right = layout.get("left"), layout.get("right")
        if left is None or right is None or abs(left - right) > 1:
            problems.append(
                f"#townMap gaps vs .{layout.get('parentClass')} left={left} right={right}, expected equal ±1px"
            )
        if layout.get("nowrap") != "nowrap":
            problems.append(f"footer tab white-space {layout.get('nowrap')!r}, expected nowrap")
    except Exception as exc:
        problems.append(f"offline Scene 1 did not render: {type(exc).__name__}: {exc}")
    finally:
        try:
            page.context.set_offline(False)
        except Exception:
            pass
    assert not problems, "TC-FE-SW-PRECACHE: " + " | ".join(problems)


def _install_stale_sw(page, cache_name, static_name):
    source = open(os.path.join(REPO, "service-worker.js"), encoding="utf-8").read()
    stale_cache = cache_name + "-test"
    stale_static = static_name + "-test"
    script = re.sub(
        r"const\s+CACHE_NAME\s*=\s*['\"][^'\"]+['\"]",
        f"const CACHE_NAME = '{stale_cache}'",
        source,
        count=1,
    )
    script = re.sub(
        r"const\s+STATIC_CACHE\s*=\s*['\"][^'\"]+['\"]",
        f"const STATIC_CACHE = '{stale_static}'",
        script,
        count=1,
    )

    def serve_sw(route):
        route.fulfill(status=200, content_type="application/javascript", body=script)

    def serve_doc(route):
        if route.request.resource_type != "document":
            route.fallback()
            return
        response = route.fetch()
        html = response.text()
        if "<body" in html:
            html = html.replace("<body", '<body data-sw-stale="1"', 1)
        route.fulfill(status=response.status, content_type="text/html", body=html)

    page.route("**/kids/**", serve_doc)
    page.route("**/service-worker.js", serve_sw)
    return serve_doc, serve_sw, stale_cache, stale_static


@pytest.mark.case_id("TC-FE-SW-UPGRADE-CLEANUP")
def test_sw_upgrade_drops_old_kids_town_cache(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-SW-UPGRADE-CLEANUP 新的 worker 清掉舊 kids-town cache，留著別的 cache。"""
    cache_name, static_name, _urls = _sw_facts()
    serve_doc, serve_sw, stale_cache, stale_static = _install_stale_sw(page, cache_name, static_name)
    problems = []
    page.goto(f"{base_url}/kids/", wait_until="domcontentloaded")
    old_active = _wait_active_worker(page, timeout=10000)
    if not old_active:
        keys = page.evaluate("() => caches.keys()")
        problems.append(f"stale worker {stale_cache} did not activate. caches.keys()={keys}")
    page.evaluate(
        """async () => {
          const cache = await caches.open('other-app-cache');
          await cache.put('/other-app-marker', new Response('keep'));
        }"""
    )
    page.unroute("**/service-worker.js", serve_sw)
    page.unroute("**/kids/**", serve_doc)
    controlled = {"controlled": False}
    for _turn in range(2):
        page.reload(wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(400)
        controlled = page.evaluate(
            """() => {
              const worker = navigator.serviceWorker.controller;
              if (!worker) return { controlled: false };
              return { controlled: true, scriptURL: worker.scriptURL || '', state: worker.state || '' };
            }"""
        )
        keys = page.evaluate("() => caches.keys()")
        kids = [name for name in keys if name.startswith("kids-town-v")]
        if (
            controlled.get("controlled")
            and "service-worker.js" in (controlled.get("scriptURL") or "")
            and kids == [cache_name]
            and stale_cache not in keys
        ):
            break
    try:
        login = page.locator("#loginScreen")
        if login.count() and login.is_visible():
            _submit_login(page)
        page.locator("#townMap").wait_for(state="visible", timeout=8000)
    except Exception as exc:
        problems.append(f"town did not render after upgrade: {type(exc).__name__}: {exc}")
    keys = page.evaluate("() => caches.keys()")
    kids = [name for name in keys if name.startswith("kids-town-v")]
    script = controlled.get("scriptURL") or ""
    if not controlled.get("controlled") or "service-worker.js" not in script:
        problems.append(f"controller {controlled!r}, expected an activated /service-worker.js")
    elif controlled.get("state") not in ("activated", ""):
        problems.append(f"controller state {controlled.get('state')!r}, expected activated")
    if kids != [cache_name]:
        problems.append(
            f"kids-town-v caches {kids}, expected only {cache_name}. all keys={keys}"
        )
    if stale_cache in keys or stale_static in keys or any(name.endswith("-test") for name in keys):
        problems.append(f"old test cache still present. keys={keys}")
    if "other-app-cache" not in keys:
        problems.append(f"other-app-cache was deleted. keys={keys}")
    stale_attr = page.evaluate("() => document.body.getAttribute('data-sw-stale')")
    if stale_attr:
        problems.append(f"body still has data-sw-stale={stale_attr!r}")
    layout = _scene1_layout(page)
    if layout.get("aria") != "場景 1 · 查看地圖":
        problems.append(f"aria {layout.get('aria')!r}, expected 場景 1 · 查看地圖")
    try:
        scale = float(layout.get("s") or "nan")
    except ValueError:
        scale = float("nan")
    if abs(scale - 0.85) > 0.001:
        problems.append(f"--s is {layout.get('s')!r}, expected 0.85")
    assert not problems, "TC-FE-SW-UPGRADE-CLEANUP: " + " | ".join(problems)


_PAL_ORDER_JS = r"""
() => {
  const grid = document.getElementById('paletteGrid');
  if (!grid) return { missing: true, children: [], rows: [] };
  const children = [...grid.children];
  return {
    missing: false,
    strangers: children.filter((el) => !el.classList.contains('pal-btn')).map((el) =>
      (el.tagName || '') + (el.className ? '.' + el.className : '') + ' ' + (el.textContent || '').trim().slice(0, 40)
    ),
    rows: children.filter((el) => el.classList.contains('pal-btn')).map((btn) => {
      const box = btn.getBoundingClientRect();
      const name = btn.querySelector('.pal-name');
      const cost = btn.querySelector('.pal-cost');
      return {
        name: name ? (name.textContent || '').trim() : '',
        cost: (cost ? cost.textContent : '').trim(),
        className: btn.className || '',
        top: box.top,
        left: box.left
      };
    })
  };
}
"""


def _palette_kind(row):
    cost = row.get("cost") or ""
    kind = row.get("className") or ""
    if "is-placed" in kind or cost in ("已興建", "已起"):
        return "built"
    if "is-stored" in kind or cost == "存倉":
        return "stored"
    if "💰" in cost:
        return "unbuilt"
    return "other"


def _expected_palette(catalog, rows):
    """Stored, then unbuilt, then built. Each group keeps `/api/building-defs` order."""
    placed = {row["def_id"] for row in rows if not row.get("stored")}
    stored = {row["def_id"] for row in rows if row.get("stored") and row["def_id"] not in placed}
    groups = {"stored": [], "unbuilt": [], "built": []}
    for item in catalog:
        def_id = item.get("id")
        if def_id in placed:
            groups["built"].append(item)
        elif def_id in stored:
            groups["stored"].append(item)
        else:
            groups["unbuilt"].append(item)
    ordered = groups["stored"] + groups["unbuilt"] + groups["built"]
    return ordered, groups


@pytest.mark.case_id("TC-FE-PAL-ORDER")
@pytest.mark.parametrize("layout", ["mixed", "no-stored", "none-built"])
def test_palette_group_order(page, base_url, warehouse_db, warehouse_ids, layout):
    """TC-FE-PAL-ORDER 建築清單依存倉、未建、已興建分組，組內保持目錄順序。"""
    kid_id = warehouse_ids["kid_id"]
    catalog = _catalog_defs(base_url)
    assert len(catalog) >= 6, f"catalog has {len(catalog)} defs"
    if layout == "mixed":
        stored_at = (1, 4)
        built_at = (0, 2)
    elif layout == "no-stored":
        stored_at = ()
        built_at = (0, 3)
    else:
        stored_at = (2, 5)
        built_at = ()
    buildings = []
    origins = ((0, 0), (4, 0), (0, 4))
    for index in stored_at:
        buildings.append({
            "name": catalog[index]["name"],
            "level": 1,
            "stored": 1,
            "cell_x": 20 + index,
            "cell_y": 12,
        })
    for slot, index in enumerate(built_at):
        origin = origins[slot]
        buildings.append({
            "name": catalog[index]["name"],
            "level": 1,
            "stored": 0,
            "cell_x": origin[0],
            "cell_y": origin[1],
        })
    _reset_kid(warehouse_db, kid_id, points=800, buildings=buildings)
    fresh = _catalog_defs(base_url)
    expected, groups = _expected_palette(fresh, _kid_rows(warehouse_db, kid_id))
    expected_names = [item.get("name") for item in expected]
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    page.locator("#listLauncher").click()
    page.locator("#paletteGrid .pal-btn").first.wait_for(state="visible", timeout=8000)
    snapshot = page.evaluate(_PAL_ORDER_JS)
    problems = []
    if snapshot.get("missing"):
        problems.append("#paletteGrid is missing")
    strangers = snapshot.get("strangers") or []
    if strangers:
        problems.append(f"palette grid has non-button children {strangers}")
    rows = snapshot.get("rows") or []
    dom_names = [row.get("name") for row in rows]
    visual = sorted(rows, key=lambda row: (row.get("top") or 0, row.get("left") or 0))
    visual_names = [row.get("name") for row in visual]
    if dom_names != expected_names:
        problems.append(f"DOM order {dom_names} != grouped catalog order {expected_names}")
    if visual_names != expected_names:
        problems.append(f"visual top-to-bottom {visual_names} != {expected_names}")
    for index in range(1, len(rows)):
        if (rows[index].get("top") or 0) + 0.5 < (rows[index - 1].get("top") or 0):
            problems.append(
                f"DOM neighbour tops go backwards at {rows[index].get('name')!r}"
            )
            break
    kinds = [_palette_kind(row) for row in rows]
    expected_kinds = (["stored"] * len(groups["stored"])) + (["unbuilt"] * len(groups["unbuilt"])) + (
        ["built"] * len(groups["built"])
    )
    if kinds != expected_kinds:
        problems.append(f"group markers {kinds} != {expected_kinds}")
    present = [name for name in expected_kinds]
    if layout == "no-stored" and "stored" in present:
        problems.append("stored group should be absent")
    if layout == "none-built" and "built" in present:
        problems.append("built group should be absent")
    if layout == "no-stored" and kinds and kinds[0] != "unbuilt":
        problems.append(f"list starts with {kinds[0]!r}, expected unbuilt")
    assert not problems, "TC-FE-PAL-ORDER " + layout + ": " + " | ".join(problems)


_SAMPLE_NAMES = (
    "centre",
    "vertex-top",
    "vertex-right",
    "vertex-bottom",
    "vertex-left",
    "edge-top-right",
    "edge-bottom-right",
    "edge-bottom-left",
    "edge-top-left",
)
_SELECTABLE_ARIA = ("點選即可選擇", "已選此格", "可以放置")
_TAP_VIEWPORTS = ((1100, 800), (390, 844))


def _strictly_inside(data, point):
    half_w = data["hw"]
    half_h = data["hh"]
    if half_w <= 0 or half_h <= 0:
        return False
    span = abs(point["x"] - data["cx"]) / half_w + abs(point["y"] - data["cy"]) / half_h
    return span < 1 - 1e-6


def _as_cells(value):
    """Turn a cell, a pair, or a list of pairs into a list of (c, r)."""
    if value is None or value == "" or value == []:
        return []
    if isinstance(value, tuple) and len(value) == 2 and not isinstance(value[0], (list, tuple)):
        return [(int(value[0]), int(value[1]))]
    if (
        isinstance(value, list)
        and len(value) == 2
        and not isinstance(value[0], (list, tuple))
        and all(isinstance(item, (int, float)) for item in value)
    ):
        return [(int(value[0]), int(value[1]))]
    cells = []
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                cells.append((int(item[0]), int(item[1])))
    return cells


def selection_of(reaction):
    """The cell a reaction dict recorded, from preview, chosen, or acted.

    Raw ``read_reaction`` dicts carry ``chosen`` and ``preview``. Probe
    dicts from ``_map_reaction`` carry the same cell under ``acted`` and
    may omit the other keys. Either shape must yield the cell, never None
    when one of those fields is set.
    """
    if not reaction:
        return None
    preview = _as_cells(reaction.get("preview"))
    chosen = _as_cells(reaction.get("chosen"))
    if len(preview) == 1:
        return preview[0]
    if len(preview) > 1:
        return preview
    if len(chosen) == 1:
        return chosen[0]
    if chosen:
        return chosen
    if "acted" not in reaction or reaction.get("acted") is None:
        return None
    acted = _as_cells(reaction.get("acted"))
    if len(acted) == 1:
        return acted[0]
    if acted:
        return acted
    return None


def reaction_happened(reaction, ready=None, ignore_toast=None):
    """True when the dict records a selection, a toast, or an open sheet.

    Selection counts from ``acted``, ``chosen``, or ``preview``. A scene-3
    jump and the 「已選擇空地」 status count too: both are reactions even
    when the cell list is empty. ``ignore_toast`` drops a toast that was
    already on screen before the tap.
    """
    if not reaction:
        return False
    if ready is None:
        ready = reaction.get("ready") or ""
    toast = reaction.get("toast") or ""
    if ignore_toast is not None and toast == ignore_toast:
        toast = ""
    scene = reaction.get("scene") or ""
    return bool(
        selection_of(reaction) is not None
        or toast
        or reaction.get("sheet")
        or "場景 3" in scene
        or "已選擇空地" in (ready or "")
    )


def _acted_cell(reaction):
    return selection_of(reaction)


def _reaction_blame(cell, kind, reaction, unstore):
    """Return (bucket, detail). bucket is neighbor, reaction, or None."""
    acted = selection_of(reaction)
    scene = reaction.get("scene") or ""
    toast = reaction.get("toast") or ""
    if isinstance(acted, tuple) and acted != cell:
        where = "preview" if "場景 3" in scene else "selected"
        return "neighbor", f"{where} {acted}"
    if isinstance(acted, list):
        return "neighbor", f"several cells {acted}"
    if kind == "select":
        if unstore:
            if "場景 3" not in scene:
                return "reaction", f"scene {scene!r} toast {toast!r}"
            if acted != cell:
                return "reaction", f"scene 3 preview {acted}"
            return None, ""
        if "場景 3" in scene:
            return "neighbor", f"scene 3 preview {acted}"
        if acted != cell:
            return "reaction", f"selected {acted} toast {toast!r}"
        return None, ""
    if acted is not None:
        expected = OCCUPIED_TOAST if kind == "occupied" else CANNOT_FIT_TOAST
        if isinstance(acted, tuple) and acted == cell:
            return "reaction", f"selected {acted}, expected {expected!r}, got {toast!r}"
        return "neighbor", f"selected {acted}"
    expected = OCCUPIED_TOAST if kind == "occupied" else CANNOT_FIT_TOAST
    if toast != expected:
        return "reaction", f"toast {toast!r}, expected {expected!r}"
    if "場景 3" in scene:
        return "neighbor", "scene 3"
    return None, ""


def _palette_pressed(page, name):
    btn = page.locator("#palette").get_by_role("button", name=re.compile(re.escape(name)))
    if btn.count() == 0:
        return False
    try:
        return btn.first.is_visible() and btn.first.get_attribute("aria-pressed") == "true"
    except Exception:
        return False


def _ensure_picked_build(page, name):
    """Back to new-build scene 2 with `name` pressed and no cell selected."""
    _close_sheet(page)
    scene = _scene_aria(page)
    hint = (_hint(page).get("ready") or "")
    palette_open = False
    try:
        palette_open = page.locator("#palette").is_visible()
    except Exception:
        palette_open = False
    if "場景 2" not in scene or "放回" in hint or not palette_open:
        if "場景 1" not in scene:
            back = page.locator("#btnUxBack")
            try:
                if back.count() and back.first.is_visible():
                    back.first.click()
            except Exception:
                pass
        _enter_new_build_scene2(page)
        _pick_unbuilt(page, name)
    elif not _palette_pressed(page, name):
        btn = page.locator("#palette").get_by_role("button", name=re.compile(re.escape(name)))
        if btn.count():
            btn.first.click()
        else:
            _pick_unbuilt(page, name)
    dismiss_selection(page)


def _aria_wording_problem(aria, kind):
    """Covered and unfit labels must contain the toast sentence verbatim."""
    text = aria or ""
    if kind == "occupied":
        problems = []
        if OCCUPIED_TOAST not in text:
            problems.append(f"missing exact {OCCUPIED_TOAST!r}")
        if "已興建" in text:
            problems.append("contains 已興建")
        if CANNOT_FIT_TOAST in text:
            problems.append(f"contains {CANNOT_FIT_TOAST!r}")
        if problems:
            return f"aria {text!r}: " + "; ".join(problems)
        return None
    if kind == "unfit":
        problems = []
        if CANNOT_FIT_TOAST not in text:
            problems.append(f"missing exact {CANNOT_FIT_TOAST!r}")
        if "已興建" in text:
            problems.append("contains 已興建")
        if OCCUPIED_TOAST in text:
            problems.append(f"contains {OCCUPIED_TOAST!r}")
        if problems:
            return f"aria {text!r}: " + "; ".join(problems)
        return None
    if OCCUPIED_TOAST in text or CANNOT_FIT_TOAST in text or "已興建" in text:
        return f"gold aria {text!r} uses a reject sentence"
    if not any(bit in text for bit in _SELECTABLE_ARIA):
        return f"gold aria {text!r} missing selectable wording"
    return None


@pytest.mark.case_id("TC-FE-TAP-OFFCENTER")
def test_tap_offcenter(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TAP-OFFCENTER 菱形內偏離中心的點必須打中那一格。

    Samples come from the ground slab's box, not the cell button. Each of
    nine points is the centre or 35% of the way toward a vertex or an edge
    midpoint. Exposed means the point lies inside the live `#village` border
    box and outside every open solid UI rect. Those points must hit the cell
    that contains them: gold selects it, a building footprint toasts
    已經有建築物, and any other empty cell toasts 放不下. A point outside
    `#village`, or inside an open solid UI rect, must not select, toast, or
    open a sheet, even when elementFromPoint is still the map.
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": "農場", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 3},
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
        ],
    )
    catalog = _catalog_defs(base_url)
    _login(page, base_url)
    problems = []
    summaries = []
    changes = []

    def _setup(mode, width, height):
        _relogin(page, base_url)
        page.set_viewport_size({"width": width, "height": height})
        if mode == "unstore":
            opened = _open_takeout_scene2(page)
            assert opened is None, f"TC-FE-TAP-OFFCENTER unstore: {opened}"
        elif mode == "picked":
            _enter_new_build_scene2(page)
            picked = _pick_unbuilt(page, "健身室")
            assert picked, "TC-FE-TAP-OFFCENTER: 健身室 was not in the palette"
            assert page.locator("#palette").is_visible(), "palette closed after picking 健身室"
        else:
            _enter_new_build_scene2(page)
        page.locator("#townMap .pad > .slab").first.wait_for(state="attached", timeout=8000)

    def _sweep(mode, width, height):
        unstore = mode == "unstore"
        kinds = _rendered_tap_kinds(page, catalog)
        solid_rects = open_solid_rects(page)
        village = village_box(page)
        if not village:
            problems.append(f"{mode} {width}x{height}: #village box missing")
        sanity = _require_helper_sees_selection(page, f"offcenter {mode} {width}x{height}")
        if sanity:
            problems.append(sanity)
        neighbor = reaction = panel_hits = chrome_skipped = exposed = geometry = 0
        fall = fall_hits = outside = outside_hits = 0
        examples = []
        panel_examples = []
        fall_examples = []
        outside_examples = []
        for y in range(MAP_N):
            for x in range(MAP_N):
                cell = (x, y)
                kind = kinds[cell]
                data = cell_points(page, x, y)
                # Diamond vertices are the slab box's edge midpoints. A drift
                # here is the helper, not the product hit-test.
                verts = data.get("vertices") or {}
                for edge, vx, vy in (
                    ("top", data["cx"], data["cy"] - data["hh"]),
                    ("right", data["cx"] + data["hw"], data["cy"]),
                    ("bottom", data["cx"], data["cy"] + data["hh"]),
                    ("left", data["cx"] - data["hw"], data["cy"]),
                ):
                    got = verts.get(edge) or {}
                    if abs(got.get("x", 0) - vx) > 0.5 or abs(got.get("y", 0) - vy) > 0.5:
                        problems.append(
                            f"{mode} {width}x{height} {cell} vertex-{edge} "
                            f"{got} != bbox midpoint ({vx:.1f},{vy:.1f})"
                        )
                for name in _SAMPLE_NAMES:
                    point = data["points"][name]
                    if not _strictly_inside(data, point):
                        geometry += 1
                        problems.append(
                            f"{mode} {width}x{height} {cell} {name} is not strictly inside the slab diamond"
                        )
                        continue
                    cover = point_cover(page, point["x"], point["y"])
                    # Open visible solid UI eats every point inside its bounding
                    # rect, including the transparent corner outside the radius.
                    # elementFromPoint falling through to the map does not make
                    # that point an exposed cell sample.
                    solid = solid_selector(solid_rects, point["x"], point["y"])
                    if solid and cover.get("kind") not in ("panel", "chrome"):
                        fall += 1
                        dismiss_selection(page)
                        _silence_toast(page)
                        tap_point(page, point["x"], point["y"])
                        hit = read_reaction(page)
                        acted = selection_of(hit)
                        ready = (_hint(page).get("ready") or "")
                        observed = dict(hit)
                        observed["ready"] = ready
                        if reaction_happened(observed):
                            fall_hits += 1
                            if len(fall_examples) < 8:
                                fall_examples.append(
                                    f"rect {solid} {cell} {name} "
                                    f"({point['x']:.0f},{point['y']:.0f}) "
                                    f"selected {acted} toast {hit.get('toast')!r} "
                                    f"ready {ready!r}"
                                )
                        if mode == "picked":
                            _ensure_picked_build(page, "健身室")
                        else:
                            dismiss_selection(page)
                            _silence_toast(page)
                        continue
                    if cover.get("kind") == "panel":
                        dismiss_selection(page)
                        tap_point(page, point["x"], point["y"])
                        hit = read_reaction(page)
                        acted = selection_of(hit)
                        if reaction_happened(hit):
                            panel_hits += 1
                            if len(panel_examples) < 8:
                                panel_examples.append(
                                    f"panel {cell} {name} ({point['x']:.0f},{point['y']:.0f}) "
                                    f"selected {acted} scene {hit.get('scene')!r}"
                                )
                        if mode == "picked":
                            _ensure_picked_build(page, "健身室")
                        else:
                            dismiss_selection(page)
                        continue
                    if cover.get("kind") == "chrome" or not cover.get("inMap"):
                        chrome_skipped += 1
                        continue
                    # The map still receives clicks below #village. Those
                    # points are the gap and the grass, not exposed cells.
                    if not village or not point_in_rect(point, village):
                        outside += 1
                        changes.append(
                            f"{mode} {width}x{height} {cell} {name} "
                            f"({point['x']:.1f},{point['y']:.1f}) "
                            f"exposed {cell} → no reaction"
                        )
                        dismiss_selection(page)
                        _silence_toast(page)
                        if _sheet_open(page):
                            _close_sheet(page)
                        tap_point(page, point["x"], point["y"])
                        hit = read_reaction(page)
                        acted = selection_of(hit)
                        ready = (_hint(page).get("ready") or "")
                        sheet = _sheet_open(page)
                        observed = dict(hit)
                        observed["ready"] = ready
                        observed["sheet"] = sheet
                        if reaction_happened(observed):
                            outside_hits += 1
                            if len(outside_examples) < 8:
                                outside_examples.append(
                                    f"{cell} {name} ({point['x']:.0f},{point['y']:.0f}) "
                                    f"selected {acted} toast {hit.get('toast')!r} "
                                    f"sheet {sheet}"
                                )
                        if mode == "picked":
                            _ensure_picked_build(page, "健身室")
                        else:
                            dismiss_selection(page)
                            _silence_toast(page)
                            if _sheet_open(page):
                                _close_sheet(page)
                        continue
                    exposed += 1
                    dismiss_selection(page)
                    tap_point(page, point["x"], point["y"])
                    hit = read_reaction(page)
                    bucket, detail = _reaction_blame(cell, kind, hit, unstore)
                    if bucket == "neighbor":
                        neighbor += 1
                    elif bucket == "reaction":
                        reaction += 1
                    if bucket and len(examples) < 10:
                        examples.append(
                            f"{cell} {name} ({point['x']:.0f},{point['y']:.0f}) "
                            f"kind {kind}: {detail}"
                        )
        return {
            "exposed": exposed,
            "neighbor": neighbor,
            "reaction": reaction,
            "panel": panel_hits,
            "chrome": chrome_skipped,
            "geometry": geometry,
            "fall": fall,
            "fall_hits": fall_hits,
            "outside": outside,
            "outside_hits": outside_hits,
            "examples": examples,
            "panel_examples": panel_examples,
            "fall_examples": fall_examples,
            "outside_examples": outside_examples,
        }

    for width, height in _TAP_VIEWPORTS:
        _setup("bare", width, height)
        probe = sprite_overlap_point(page)
        if probe:
            cell_points(page, probe["c"], probe["r"])
            probe = sprite_overlap_point(page)
        if not probe:
            problems.append(
                f"{width}x{height} sprite: no empty back-cell diamond overlaps a front sprite. "
                "Seed is 商店 (0,0) and 農場 (4,3)."
            )
            summaries.append(f"sprite {width}x{height}: no overlap point")
        else:
            back = (probe["c"], probe["r"])
            front = (probe["frontC"], probe["frontR"])
            kinds = _rendered_tap_kinds(page, catalog)
            kind = kinds.get(back, "unfit")
            dismiss_selection(page)
            tap_point(page, probe["x"], probe["y"])
            hit = read_reaction(page)
            bucket, detail = _reaction_blame(back, kind, hit, False)
            acted = _acted_cell(hit)
            sprite_bad = bucket is not None or acted == front
            if sprite_bad:
                problems.append(
                    f"{width}x{height} sprite: tap inside {kind} {back} over "
                    f"{probe.get('frontLabel')!r} {front} at ({probe['x']:.0f},{probe['y']:.0f}) "
                    f"-> {detail or acted}"
                )
            summaries.append(
                f"sprite {width}x{height}: {kind} {back} over {front} "
                + ("FAIL" if sprite_bad else "ok")
            )

        for mode in ("bare", "picked", "unstore"):
            _setup(mode, width, height)
            counts = _sweep(mode, width, height)
            panel_points = (
                576
                - counts["exposed"]
                - counts["chrome"]
                - counts["geometry"]
                - counts["fall"]
                - counts["outside"]
            )
            correct = counts["exposed"] - counts["neighbor"] - counts["reaction"]
            summary = (
                f"{mode} {width}x{height}: {correct}/{counts['exposed']} exposed, "
                f"outside-village {counts['outside']}, "
                f"panel-excluded {panel_points}, chrome-excluded {counts['chrome']}, "
                f"rect-fallthrough {counts['fall']}, "
                f"neighbor-mis {counts['neighbor']}, reaction-mis {counts['reaction']}, "
                f"panel-selections {counts['panel']}, rect-selections {counts['fall_hits']}, "
                f"outside-reactions {counts['outside_hits']}, "
                f"geometry {counts['geometry']}"
            )
            summaries.append(summary)
            if (
                panel_points
                + counts["exposed"]
                + counts["chrome"]
                + counts["geometry"]
                + counts["fall"]
                + counts["outside"]
                != 576
            ):
                problems.append(f"{summary} did not account for 576 points")
            if counts["neighbor"] or counts["reaction"]:
                problems.append(summary + " | " + " | ".join(counts["examples"]))
            if counts["panel"]:
                problems.append(
                    summary + " panel ate a cell: " + " | ".join(counts["panel_examples"])
                )
            if counts["fall_hits"]:
                problems.append(
                    summary
                    + " rounded-rect fallthrough selected or toasted: "
                    + " | ".join(counts["fall_examples"])
                )
            if counts["outside_hits"]:
                problems.append(
                    summary
                    + " outside #village reacted: "
                    + " | ".join(counts["outside_examples"])
                )
            if mode == "picked" and panel_points == 0:
                problems.append(f"{mode} {width}x{height}: open palette covered no sample points")
            if mode == "bare" and panel_points:
                problems.append(
                    f"{mode} {width}x{height}: palette was closed but excluded {panel_points} points"
                )

    print(f"TC-FE-TAP-OFFCENTER EXPECT-CHANGES {len(changes)}", flush=True)
    for line in changes:
        print("OFFCENTER-CHANGE " + line, flush=True)
    print("TC-FE-TAP-OFFCENTER " + " || ".join(summaries))
    assert not problems, "TC-FE-TAP-OFFCENTER: " + " || ".join(problems[:12])


def _palette_covers_cell_button(page, cell_x, cell_y):
    """True when the focused cell button's centre is the open palette."""
    return bool(page.evaluate(
        """([c, r]) => {
          const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
            const cs = getComputedStyle(el);
            return parseInt(cs.getPropertyValue('--c'), 10) === c
              && parseInt(cs.getPropertyValue('--r'), 10) === r;
          });
          const btn = pad && pad.querySelector(':scope > .cell-btn');
          if (!btn) return false;
          const box = btn.getBoundingClientRect();
          if (box.width < 1 || box.height < 1) return false;
          const top = document.elementFromPoint(
            box.left + box.width / 2,
            box.top + box.height / 2
          );
          const palette = document.getElementById('palette');
          if (!top || !palette) return false;
          const shown = palette.offsetParent !== null || getComputedStyle(palette).display !== 'none';
          if (!shown) return false;
          return top === palette || palette.contains(top);
        }""",
        [cell_x, cell_y],
    ))


def _reaction_chosen(reaction):
    chosen = []
    for item in reaction.get("chosen") or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            chosen.append((item[0], item[1]))
    return chosen


def _shift_selection_to_reachable_gold(page):
    """Move a stuck selection onto a gold cell the pointer can toggle off.

    A second key on the selected cell deselects it (OVERLAP's second tap).
    Some tips swallow that keyboard click in picked scene 2, so Enter cannot
    clear a cell the pointer cannot reach. Selecting a different gold cell
    the pointer can hit moves the selection to a place a tap can clear.
    """
    cells = page.evaluate(
        """() => [...document.querySelectorAll('#townMap .pad.is-empty-hot')].map((pad) => {
          const cs = getComputedStyle(pad);
          return [parseInt(cs.getPropertyValue('--c'), 10), parseInt(cs.getPropertyValue('--r'), 10)];
        })"""
    ) or []
    for raw in cells:
        cell_x, cell_y = raw
        data = cell_points(page, cell_x, cell_y)
        if not data or not data.get("points"):
            continue
        candidates = [data["points"].get("centre")]
        button = data.get("button") or {}
        if button.get("x") is not None and button.get("y") is not None:
            candidates.append({"x": button["x"], "y": button["y"]})
        for point in candidates:
            if not point:
                continue
            cover = point_cover(page, point["x"], point["y"])
            if cover.get("kind") in ("panel", "chrome", "toast") or not cover.get("inMap"):
                continue
            if cover.get("foreignButton"):
                continue
            tap_point(page, point["x"], point["y"])
            chosen = _reaction_chosen(read_reaction(page))
            if chosen == [(cell_x, cell_y)]:
                return True
    return False


def _clear_cell_selection(page):
    """Clear a chosen cell before the next key.

    OVERLAP requires a second tap on a selected gold cell to deselect it.
    Enter and Space share that toggle, so each key has to start unselected.
    A pointer dismiss misses a cell under the open palette. Enter on that
    button clears it when the product honours the key. When the product
    swallows that second key, the selection is moved to a reachable gold
    cell and cleared with a pointer tap.
    """
    dismiss_selection(page)
    reaction = read_reaction(page)
    if "場景 3" in (reaction.get("scene") or ""):
        dismiss_selection(page)
        reaction = read_reaction(page)
    chosen = _reaction_chosen(reaction)
    if chosen:
        try:
            press_cell(page, chosen[0][0], chosen[0][1], "Enter")
        except AssertionError:
            pass
        _silence_toast(page)
        reaction = read_reaction(page)
        chosen = _reaction_chosen(reaction)
    if chosen and "場景 3" not in (reaction.get("scene") or ""):
        if _shift_selection_to_reachable_gold(page):
            dismiss_selection(page)
            _silence_toast(page)
            reaction = read_reaction(page)
            chosen = _reaction_chosen(reaction)
    if chosen or "場景 3" in (reaction.get("scene") or ""):
        return f"selection remained after clear: {reaction.get('chosen')}"
    return None


@pytest.mark.case_id("TC-FE-CELL-ARIA-MATCH")
@pytest.mark.parametrize("mode", ["picked", "unstore"])
def test_cell_aria_matches_tap(page, base_url, warehouse_db, warehouse_ids, mode):
    """TC-FE-CELL-ARIA-MATCH 格子的無障礙字要和點下去的提示同一類。

    Covered cells, including non-anchors such as (1,0), say 已經有建築物.
    Empty cells that overlap or leave the grid say 放不下. Gold cells say
    they can be chosen. Kinds come from the rendered gold marks and sprites,
    the same split as the off-centre sweep. Every cell keeps a focusable
    button. Enter and Space each start from a cleared selection, because a
    second activation of a selected cell toggles it off, and each key must
    match a first tap. A cell under the open palette still receives the key.
    Clearing does not depend on that second key: some tips swallow it.
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": "農場", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 3},
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
        ],
    )
    catalog = _catalog_defs(base_url)
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    if mode == "unstore":
        opened = _open_takeout_scene2(page)
        assert opened is None, "TC-FE-CELL-ARIA-MATCH: " + opened
    else:
        _enter_new_build_scene2(page)
        assert _pick_unbuilt(page, "健身室"), "健身室 missing from the palette"
    kinds = _rendered_tap_kinds(page, catalog)
    sprite_origins = {
        (fact["c"], fact["r"])
        for fact in page.evaluate(_RENDERED_PADS_JS)
        if fact.get("name")
    }
    access = { (item["c"], item["r"]): item for item in cell_access(page) }
    problems = []
    if kinds.get((1, 0)) != "occupied":
        problems.append(
            "rendered map does not class non-anchor (1,0) as covered "
            f"(kind={kinds.get((1, 0))!r}); 商店 sprite should occupy it and it should not be gold"
        )
    aria_miss = key_miss = anchor_miss = nonanchor_miss = 0
    palette_focus = []
    for y in range(MAP_N):
        for x in range(MAP_N):
            cell = (x, y)
            kind = kinds[cell]
            item = access.get(cell)
            if item is None or not item.get("present") or not item.get("aria"):
                problems.append(f"{cell} has no focusable button with an aria-label")
                aria_miss += 1
                continue
            if item.get("disabled") or item.get("tabIndex", -1) < 0:
                problems.append(
                    f"{cell} button is not focusable "
                    f"(disabled={item.get('disabled')} tabIndex={item.get('tabIndex')})"
                )
            wording = _aria_wording_problem(item.get("aria") or "", kind)
            if wording:
                aria_miss += 1
                if kind == "occupied" and cell in sprite_origins:
                    anchor_miss += 1
                    role = "anchor "
                elif kind == "occupied":
                    nonanchor_miss += 1
                    role = "non-anchor "
                else:
                    role = ""
                if len(problems) < 16:
                    problems.append(f"{role}{cell} {kind}: {wording}")
            if _palette_covers_cell_button(page, x, y) and cell not in palette_focus:
                palette_focus.append(cell)
            for key in ("Enter", "Space"):
                stuck = _clear_cell_selection(page)
                if stuck:
                    key_miss += 1
                    if len(problems) < 16:
                        problems.append(f"{cell} {key}: {stuck}")
                    continue
                try:
                    press_cell(page, x, y, key)
                except AssertionError as exc:
                    key_miss += 1
                    if len(problems) < 16:
                        problems.append(f"{cell} {key}: {exc}")
                    continue
                hit = read_reaction(page)
                bucket, detail = _reaction_blame(cell, kind, hit, mode == "unstore")
                if bucket:
                    key_miss += 1
                    if len(problems) < 16:
                        problems.append(f"{cell} {key} {kind}: {detail}")
    summary = (
        f"{mode}: aria-mismatches {aria_miss} "
        f"(anchor {anchor_miss}, non-anchor {nonanchor_miss}), "
        f"key-mismatches {key_miss}, "
        f"palette-covered focus {palette_focus or 'none'}"
    )
    print("TC-FE-CELL-ARIA-MATCH " + summary)
    assert not problems, "TC-FE-CELL-ARIA-MATCH " + summary + ": " + " | ".join(problems[:16])


_OWNED_FORMAL = "你已經興建了這種建築物。"
_OWNED_COLLOQUIAL = "你已經興建咗呢種建築物"


def _surface_box(page, selector):
    return page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (!el || el.hidden) return null;
          const cs = getComputedStyle(el);
          if (cs.display === 'none' || cs.visibility === 'hidden') return null;
          const box = el.getBoundingClientRect();
          if (box.width < 2 || box.height < 2) return null;
          return {left: box.left, top: box.top, right: box.right, bottom: box.bottom};
        }""",
        selector,
    )


def _control_boxes(page, selector):
    return page.evaluate(
        """(sel) => {
          const root = document.querySelector(sel);
          if (!root) return [];
          return [...root.querySelectorAll('button, a, input, [role="button"]')].map((el) => {
            const box = el.getBoundingClientRect();
            return {left: box.left, top: box.top, right: box.right, bottom: box.bottom};
          }).filter((box) => box.right - box.left > 2 && box.bottom - box.top > 2);
        }""",
        selector,
    )


def _background_grid(rect, holes, step=16):
    points = []
    y = rect["top"] + 6
    while y < rect["bottom"] - 3:
        x = rect["left"] + 6
        while x < rect["right"] - 3:
            point = {"x": x, "y": y}
            if not any(point_in_rect(point, hole) for hole in holes):
                points.append(point)
            x += step
        y += step
    return points


def _hit_owner(page, x, y, selector):
    return page.evaluate(
        """([x, y, sel]) => {
          const el = document.elementFromPoint(x, y);
          const root = document.querySelector(sel);
          const cell = el && el.closest && el.closest(
            '#townMap .cell-btn, #townMap .hit-sliver, #village .cell-btn'
          );
          return {
            inside: !!(el && root && (el === root || root.contains(el))),
            cell: !!cell,
            got: el ? (el.id || el.getAttribute('aria-label') || el.className || el.tagName) : null
          };
        }""",
        [x, y, selector],
    )


def _inset_points(box):
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2
    points = [("centre", cx, cy)]
    if box["width"] > 20:
        points.append(("left", box["x"] + 8, cy))
        points.append(("right", box["x"] + box["width"] - 8, cy))
    if box["height"] > 20:
        points.append(("top", cx, box["y"] + 8))
        points.append(("bottom", cx, box["y"] + box["height"] - 8))
    return points


def _ensure_town_map(page):
    town = page.locator("#townMap")
    try:
        if town.count() and town.is_visible():
            return
    except Exception:
        pass
    tab = page.locator('#ktFooter [data-kt-nav="town"]')
    if tab.count():
        try:
            tab.first.click()
            page.wait_for_timeout(200)
        except Exception:
            pass


def _sheet_opened_by_tap(sheet_before, sheet_after):
    """True only when this tap opened #actionSheet.

    A sheet that was already open is the surface under test, not a reaction.
    """
    return bool(sheet_after) and not bool(sheet_before)


def _selection_leaked(page, sheet_before=False):
    hit = read_reaction(page)
    ready = (_hint(page).get("ready") or "")
    observed = dict(hit)
    observed["ready"] = ready
    observed["sheet"] = _sheet_opened_by_tap(sheet_before, _sheet_open(page))
    acted = selection_of(observed)
    return reaction_happened(observed), acted, hit, ready


def _scene2_tap_mode(page, mode, build_name):
    """Scene 2 with the palette open (picked) or closed (bare)."""
    _close_sheet(page)
    scene = _scene_aria(page)
    # Scene 3 hides #readyBar, so #btnUxBack is not visible. Cancel returns
    # to scene 2; #btnBuild itself is only visible in scene 1.
    if "場景 3" in scene:
        cancel = page.locator("#btnUxCancel")
        try:
            if cancel.count() and cancel.first.is_visible():
                cancel.first.click(timeout=2000)
                page.wait_for_timeout(150)
        except Exception:
            pass
        _silence_toast(page)
        scene = _scene_aria(page)
    hint = (_hint(page).get("ready") or "")
    if "場景 2" not in scene or "放回" in hint:
        back = page.locator("#btnUxBack")
        try:
            if "場景 1" not in scene and back.count() and back.first.is_visible():
                back.first.click()
                page.wait_for_timeout(150)
        except Exception:
            pass
        _enter_new_build_scene2(page)
    if mode == "picked":
        open_palette = False
        try:
            open_palette = page.locator("#palette").is_visible()
        except Exception:
            open_palette = False
        if not open_palette or not _palette_pressed(page, build_name):
            _ensure_picked_build(page, build_name)
        return
    _close_sheet(page)
    try:
        if page.locator("#palette").is_visible():
            back = page.locator("#btnUxBack")
            if back.count() and back.first.is_visible():
                back.first.click()
                page.wait_for_timeout(150)
            _enter_new_build_scene2(page)
    except Exception:
        _enter_new_build_scene2(page)


def _open_shop_sheet(page):
    try:
        if not page.locator("#palette").is_visible():
            launcher = page.locator("#listLauncher")
            if launcher.count() == 0 or not launcher.first.is_visible():
                return False
            launcher.first.click()
            page.locator("#palette").wait_for(state="visible", timeout=4000)
    except Exception:
        return False
    shop = page.locator("#palette").get_by_role("button", name=re.compile("商店"))
    if shop.count() == 0:
        return False
    shop.first.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(200)
    sheet = page.locator("#actionSheet")
    try:
        return bool(sheet.count() and sheet.first.is_visible())
    except Exception:
        return False


def _bar_rect_leaks(page, base_url):
    """Corners of open solid UI, including the transparent radius, must not hit a cell."""
    problems = []
    summaries = []
    viewports = ((1280, 720), (1100, 800), (390, 844))
    for width, height in viewports:
        for mode in ("bare", "picked"):
            _relogin(page, base_url)
            page.set_viewport_size({"width": width, "height": height})
            _enter_new_build_scene2(page)
            if mode == "picked":
                assert _pick_unbuilt(page, "工坊"), f"{width}x{height}: 工坊 missing"
            sanity = _require_helper_sees_selection(page, f"rect {mode} {width}x{height}")
            if sanity:
                problems.append(sanity)
            seen = set()
            sheet_opened = False
            for scroll in (0, 300, 366, "max"):
                _scene2_tap_mode(page, mode, "工坊")
                placed = set_village_scroll(page, scroll)
                actual = None if not placed else round(placed.get("scroll") or 0, 1)
                if scroll != 0 and actual in seen:
                    summaries.append(
                        f"rect {mode} {width}x{height} scroll {scroll} clamped {actual}"
                    )
                    continue
                seen.add(actual)
                surfaces = [("bar", "#readyBar"), ("hud", "#app .gh")]
                if mode == "picked":
                    surfaces.insert(0, ("palette", "#palette"))
                else:
                    surfaces.insert(0, ("launcher", "#listLauncher"))
                leaked = probed = 0
                examples = []

                def _probe(name, rect):
                    nonlocal leaked, probed
                    if not rect:
                        return
                    for point in corner_insets(rect):
                        if (
                            point["x"] < 1
                            or point["y"] < 1
                            or point["x"] >= width - 1
                            or point["y"] >= height - 1
                        ):
                            continue
                        probed += 1
                        owner = map_hit_at(page, point["x"], point["y"]) or {}
                        reasons = []
                        if owner.get("map") or owner.get("cell"):
                            reasons.append(f"elementFromPoint {owner.get('got')!r}")
                        dismiss_selection(page)
                        _silence_toast(page)
                        if not (owner.get("button") and not owner.get("map")):
                            sheet_before = _sheet_open(page)
                            tap_point(page, point["x"], point["y"])
                            bad, acted, hit, ready = _selection_leaked(page, sheet_before)
                            if bad:
                                reasons.append(
                                    f"selected {acted} toast {hit.get('toast')!r} ready {ready!r}"
                                )
                            dismiss_selection(page)
                            _silence_toast(page)
                            _ensure_town_map(page)
                        if reasons:
                            leaked += 1
                            if len(examples) < 8:
                                examples.append(
                                    f"{name} {point['name']} "
                                    f"({point['x']:.0f},{point['y']:.0f}) "
                                    + "; ".join(reasons)
                                )

                for name, selector in surfaces:
                    _probe(name, surface_rect(page, selector))
                set_village_scroll(page, scroll if scroll != "max" else "max")
                if _open_shop_sheet(page):
                    sheet_opened = True
                    _probe("sheet", surface_rect(page, "#actionSheet"))
                    _close_sheet(page)
                summaries.append(
                    f"rect {mode} {width}x{height} scroll {actual}: "
                    f"probed {probed}, leaked {leaked}"
                )
                if leaked:
                    problems.append(
                        f"rect {mode} {width}x{height} scroll {actual}: "
                        f"{leaked}/{probed} | " + " | ".join(examples)
                    )
                elif probed == 0:
                    problems.append(
                        f"rect {mode} {width}x{height} scroll {actual}: no corner points"
                    )
            if not sheet_opened:
                problems.append(f"rect {mode} {width}x{height}: #actionSheet did not open")
    return problems, summaries


def _tap_visible_gold(page, point):
    dismiss_selection(page)
    _silence_toast(page)
    tap_point(page, point["x"], point["y"])
    hit = read_reaction(page)
    acted = selection_of(hit)
    want = (point["c"], point["r"])
    ok = acted == want and "場景 3" not in (hit.get("scene") or "")
    return ok, acted, hit


def _gold_in_saved_rect(page, rect):
    point = gold_point_inside(page, rect)
    if point:
        return point
    for scroll in (0, 180, 360, "max"):
        set_village_scroll(page, scroll)
        point = gold_point_inside(page, rect)
        if point:
            return point
    return None


def _bar_guard_checks(page, base_url):
    """Closed or inert UI must not eat a tap on a visible gold cell.

    These guards are expected to pass on the current product. They are not
    extra red cases.
    """
    problems = []
    summaries = []
    _relogin(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    sanity = _require_helper_sees_selection(page, "guard")
    if sanity:
        problems.append(sanity)
    launcher = page.locator("#listLauncher")
    if launcher.count() and launcher.first.is_visible():
        launcher.first.click()
        page.locator("#palette").wait_for(state="visible", timeout=8000)
    palette_rect = surface_rect(page, "#palette")
    if not palette_rect:
        summaries.append("guard palette: cannot open, former-rect skipped")
    else:
        back = page.locator("#btnUxBack")
        back.first.click()
        page.wait_for_timeout(200)
        _enter_new_build_scene2(page)
        still = False
        try:
            still = page.locator("#palette").is_visible()
        except Exception:
            still = False
        if still:
            summaries.append(
                "guard palette: still open after 返回地圖 and 我要起屋; former-rect skipped"
            )
        else:
            point = _gold_in_saved_rect(page, palette_rect)
            if not point:
                problems.append("guard palette: no visible gold cell in the former rect")
            else:
                ok, acted, hit = _tap_visible_gold(page, point)
                summaries.append(
                    f"guard palette-closed: former rect {point['c'], point['r']} -> {acted}"
                )
                if not ok:
                    problems.append(
                        f"guard palette-closed: gold {point['c'], point['r']} "
                        f"in the former rect selected {acted} toast {hit.get('toast')!r}"
                    )
    _scene2_tap_mode(page, "bare", "工坊")
    menu = page.locator("#app .gh .mb")
    if menu.count() and menu.first.is_visible():
        menu.first.click()
        page.wait_for_timeout(350)
        drawer_rect = surface_rect(page, "#dr")
        closer = page.locator("#dr .dc")
        if closer.count():
            closer.first.click()
            page.wait_for_timeout(350)
        else:
            page.evaluate("() => { if (typeof td === 'function') td(); }")
            page.wait_for_timeout(350)
        if not drawer_rect:
            summaries.append("guard drawer: opened rect missing; collapsed gold tap only")
            drawer_rect = {"left": 0, "top": 0, "right": 4000, "bottom": 4000}
        point = _gold_in_saved_rect(page, drawer_rect)
        if not point:
            problems.append("guard drawer: no visible gold cell after the drawer collapsed")
        else:
            ok, acted, hit = _tap_visible_gold(page, point)
            summaries.append(f"guard drawer-collapsed: {point['c'], point['r']} -> {acted}")
            if not ok:
                problems.append(
                    f"guard drawer-collapsed: gold {point['c'], point['r']} "
                    f"selected {acted} toast {hit.get('toast')!r}"
                )
    else:
        problems.append("guard drawer: menu button missing, could not exercise collapse")
    _scene2_tap_mode(page, "bare", "工坊")
    sheet_was_open = _open_shop_sheet(page)
    sheet_rect = surface_rect(page, "#actionSheet") if sheet_was_open else None
    if sheet_was_open:
        _close_sheet(page)
    sheet_open = False
    try:
        sheet_open = page.locator("#actionSheet").is_visible()
    except Exception:
        sheet_open = False
    if sheet_open:
        summaries.append("guard sheet: could not close; former-rect skipped")
    else:
        target = sheet_rect or {"left": 0, "top": 0, "right": 4000, "bottom": 4000}
        point = _gold_in_saved_rect(page, target)
        if not point:
            problems.append("guard sheet-closed: no visible gold cell")
        else:
            ok, acted, hit = _tap_visible_gold(page, point)
            label = "former sheet rect" if sheet_rect else "unopened sheet"
            summaries.append(f"guard {label}: {point['c'], point['r']} -> {acted}")
            if not ok:
                problems.append(
                    f"guard {label}: gold {point['c'], point['r']} "
                    f"selected {acted} toast {hit.get('toast')!r}"
                )
    hidden_hits = page.evaluate(
        r"""
() => {
  const map = document.getElementById('townMap');
  const mapBox = map ? map.getBoundingClientRect() : null;
  function hidden(el) {
    if (!el || el === document.body || el === document.documentElement) return false;
    const cs = getComputedStyle(el);
    if (el.inert) return 'inert';
    if (cs.visibility === 'hidden') return 'visibility';
    if (Number(cs.opacity) === 0) return 'opacity';
    if (cs.display === 'none') return 'display';
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) return null;
    if (box.right < 0 || box.bottom < 0 || box.left > innerWidth || box.top > innerHeight) {
      return 'offscreen';
    }
    if (mapBox) {
      const ix = Math.min(box.right, mapBox.right) - Math.max(box.left, mapBox.left);
      const iy = Math.min(box.bottom, mapBox.bottom) - Math.max(box.top, mapBox.top);
      if (ix <= 0 || iy <= 0) return 'outside-map';
    }
    return null;
  }
  const hits = [];
  for (const el of document.querySelectorAll('[id]')) {
    const why = hidden(el);
    if (!why || why === 'display') continue;
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) continue;
    hits.push({
      id: el.id, why,
      left: box.left, top: box.top, right: box.right, bottom: box.bottom
    });
  }
  return hits.slice(0, 12);
}
"""
    ) or []
    blocked = 0
    for item in hidden_hits:
        point = gold_point_inside(page, item)
        if not point:
            continue
        ok, acted, hit = _tap_visible_gold(page, point)
        if not ok:
            blocked += 1
            problems.append(
                f"guard hidden #{item['id']} ({item['why']}) ate gold "
                f"{point['c'], point['r']} -> {acted} toast {hit.get('toast')!r}"
            )
    summaries.append(f"guard hidden-elements: scanned {len(hidden_hits)}, blocked {blocked}")
    _silence_toast(page)
    page.evaluate("() => { if (typeof showToast === 'function') showToast('放置完成'); }")
    point = any_visible_gold_point(page)
    if not point:
        problems.append("guard toast: no visible gold cell while the toast is up")
    else:
        dismiss_selection(page)
        tap_point(page, point["x"], point["y"])
        hit = read_reaction(page)
        acted = _acted_cell(hit)
        ok = acted == (point["c"], point["r"]) and "場景 3" not in (hit.get("scene") or "")
        summaries.append(f"guard toast-not-eating: {point['c'], point['r']} -> {acted}")
        if not ok:
            problems.append(
                f"guard toast ate visible gold {point['c'], point['r']} "
                f"(got {acted}, toast {hit.get('toast')!r})"
            )
    if point:
        burst_pe = page.evaluate(
            """([x, y]) => {
              const host = document.getElementById('townMap') || document.body;
              const burst = document.createElement('div');
              burst.className = 'fx-burst';
              burst.setAttribute('data-town-fx', 'place');
              burst.style.position = 'fixed';
              burst.style.left = (x - 24) + 'px';
              burst.style.top = (y - 24) + 'px';
              burst.style.width = '48px';
              burst.style.height = '48px';
              burst.style.zIndex = '80';
              host.appendChild(burst);
              const pe = getComputedStyle(burst).pointerEvents;
              burst.remove();
              return pe;
            }""",
            [point["x"], point["y"]],
        )
        if burst_pe != "none":
            problems.append(f"guard vfx pointer-events is {burst_pe!r}, expected none")
        else:
            host_point = point
            page.evaluate(
                """([x, y]) => {
                  const host = document.getElementById('townMap') || document.body;
                  const burst = document.createElement('div');
                  burst.id = 'qc6Burst';
                  burst.className = 'fx-burst';
                  burst.setAttribute('data-town-fx', 'place');
                  burst.style.position = 'fixed';
                  burst.style.left = (x - 24) + 'px';
                  burst.style.top = (y - 24) + 'px';
                  burst.style.width = '48px';
                  burst.style.height = '48px';
                  burst.style.zIndex = '80';
                  host.appendChild(burst);
                }""",
                [host_point["x"], host_point["y"]],
            )
            dismiss_selection(page)
            tap_point(page, host_point["x"], host_point["y"])
            hit = read_reaction(page)
            acted = _acted_cell(hit)
            ok = acted == (host_point["c"], host_point["r"])
            page.evaluate("() => { const el = document.getElementById('qc6Burst'); if (el) el.remove(); }")
            summaries.append(f"guard vfx-not-eating: {host_point['c'], host_point['r']} -> {acted}")
            if not ok:
                problems.append(
                    f"guard vfx ate visible gold {host_point['c'], host_point['r']} (got {acted})"
                )
    if not problems:
        summaries.append("guards: PASS")
    return problems, summaries


@pytest.mark.case_id("TC-FE-TAP-BAR-NOTHROUGH")
def test_tap_bar_nothrough(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TAP-BAR-NOTHROUGH 只有打開而且看得見的實心介面可以吃掉點擊。

    外框矩形的四個角，包括圓角外面的透明區，都不得打中格子。
    提示蓋住看得見的金色菱形時，點那一塊要選中；蓋不住時，點提示不得選格。
    收起的清單、抽屜、未打開的面板，以及 toast／特效，不得吃掉看得見的金格。
    後面這組是 guard，用來防止實心介面擋太多。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": "農場", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 3},
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
        ],
    )
    catalog = _catalog_defs(base_url)
    blocks = _placed_blocks(_kid_rows(warehouse_db, kid_id), catalog)
    _login(page, base_url)
    page.set_viewport_size({"width": 1100, "height": 800})
    _enter_new_build_scene2(page)
    assert _pick_unbuilt(page, "健身室"), "健身室 missing"
    problems = []
    summaries = []

    def _grid_surface(name, selector):
        rect = _surface_box(page, selector)
        if not rect:
            problems.append(f"{name} has no rendered box")
            summaries.append(f"{name}: missing")
            return
        holes = _control_boxes(page, selector)
        points = _background_grid(rect, holes)
        selected = stolen = on_surface = 0
        examples = []
        for point in points:
            owner = _hit_owner(page, point["x"], point["y"], selector)
            # The CSS box includes rounded corners and gaps. A point counts
            # only when elementFromPoint is actually this surface.
            if not owner or not owner.get("inside"):
                continue
            on_surface += 1
            if owner.get("cell"):
                stolen += 1
                if len(examples) < 4:
                    examples.append(
                        f"hit ({point['x']:.0f},{point['y']:.0f}) -> {owner}"
                    )
            dismiss_selection(page)
            tap_point(page, point["x"], point["y"])
            hit = read_reaction(page)
            if reaction_happened(hit):
                selected += 1
                if len(examples) < 6:
                    examples.append(
                        f"tap ({point['x']:.0f},{point['y']:.0f}) "
                        f"selected {selection_of(hit)} toast {hit.get('toast')!r}"
                    )
            dismiss_selection(page)
        summaries.append(
            f"{name}: background {on_surface}, selected {selected}, hit-stolen {stolen}"
        )
        if not on_surface:
            problems.append(f"{name} background grid was empty")
        if selected or stolen:
            problems.append(
                f"{name}: selected {selected}, hit-stolen {stolen} of {on_surface} | "
                + " | ".join(examples)
            )

    for selector, label in (
        ("#readyBar button", "action-bar button"),
        ("#ktFooter .kt-footer-tab", "footer tab"),
    ):
        nodes = page.locator(selector)
        stolen = 0
        checked = 0
        sample = []
        for index in range(nodes.count()):
            node = nodes.nth(index)
            box = node.bounding_box()
            if not box or box["width"] < 8 or box["height"] < 8:
                continue
            ident = (
                node.get_attribute("data-kt-nav")
                or node.get_attribute("id")
                or node.inner_text()
                or str(index)
            ).strip().split("\n")[0][:24]
            for edge, x, y in _inset_points(box):
                checked += 1
                owner = page.evaluate(
                    """([x, y]) => {
                      const el = document.elementFromPoint(x, y);
                      if (!el) return {ok: false, cell: false, got: null};
                      const cell = el.closest && el.closest(
                        '#townMap .cell-btn, #townMap .hit-sliver, #village .cell-btn'
                      );
                      return {
                        ok: !cell,
                        cell: !!cell,
                        got: el.id || el.getAttribute('data-kt-nav') || el.className || el.tagName
                      };
                    }""",
                    [x, y],
                )
                target = page.evaluate(
                    """([x, y, sx, sy, sw, sh]) => {
                      const el = document.elementFromPoint(x, y);
                      if (!el) return false;
                      const stack = document.elementsFromPoint
                        ? document.elementsFromPoint(x, y)
                        : [el];
                      return stack.some((node) => {
                        const box = node.getBoundingClientRect();
                        return Math.abs(box.left - sx) < 1.5 && Math.abs(box.top - sy) < 1.5
                          && Math.abs(box.width - sw) < 1.5 && Math.abs(box.height - sh) < 1.5
                          && (node === el || node.contains(el));
                      });
                    }""",
                    [x, y, box["x"], box["y"], box["width"], box["height"]],
                )
                if owner.get("cell") or not target:
                    stolen += 1
                    if len(sample) < 6:
                        sample.append(f"{label} {ident} {edge} -> {owner.get('got')!r}")
        summaries.append(f"{label}: probed {checked}, stolen {stolen}")
        if stolen:
            problems.append(f"{label} hit stolen {stolen}/{checked} | " + " | ".join(sample))

    shop = page.locator("#palette").get_by_role("button", name=re.compile("商店"))
    if shop.count() == 0:
        problems.append("palette has no 商店 button to open the sheet")
    else:
        shop.first.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
    sheet = page.locator("#actionSheet")
    sheet_open = False
    try:
        sheet_open = sheet.count() and sheet.first.is_visible()
    except Exception:
        sheet_open = False
    if not sheet_open:
        problems.append("placed 商店 did not open #actionSheet")
        summaries.append("sheet: not open")
    else:
        _grid_surface("sheet", "#actionSheet")
        _close_sheet(page)

    _grid_surface("action-bar", "#readyBar")
    _grid_surface("palette", "#palette")
    _grid_surface("hud", "#app .gh")
    _grid_surface("footer", "#ktFooter")

    page.set_viewport_size({"width": 1280, "height": 720})
    _relogin(page, base_url)
    _enter_new_build_scene2(page)
    _pick_unbuilt(page, "健身室")
    dismiss_selection(page)
    # Occupied (0,0) shows the info toast. Read its box in the same beat:
    # showToast hides it after 2s, and a later keyboard click does not
    # refresh it on builds that ignore clientX 0.
    tap_cell_centre(page, 0, 0)
    toast_state = page.evaluate(
        """() => {
          const el = document.getElementById('toast');
          if (!el) return {missing: true};
          const cs = getComputedStyle(el);
          const burst = document.createElement('div');
          burst.className = 'fx-burst';
          (document.getElementById('townMap') || document.body).appendChild(burst);
          const burstPe = getComputedStyle(burst).pointerEvents;
          burst.remove();
          return {
            text: el.textContent || '',
            className: el.className || '',
            display: el.style.display || '',
            pointerEvents: cs.pointerEvents,
            burst: burstPe
          };
        }"""
    )
    if toast_state.get("pointerEvents") != "none":
        problems.append(
            f"info/toast pointer-events is {toast_state.get('pointerEvents')!r}, expected none"
        )
    if toast_state.get("burst") != "none":
        problems.append(
            f"placement .fx-burst pointer-events is {toast_state.get('burst')!r}, expected none"
        )
    # Only a gold diamond that is actually visible under the toast may be
    # selected. A hidden cell under the toast is not that target.
    overlap = visible_gold_under_toast(page)
    if overlap:
        want = (overlap["c"], overlap["r"])
        dismiss_selection(page)
        tap_point(page, overlap["x"], overlap["y"])
        hit = read_reaction(page)
        acted = selection_of(hit)
        ok = acted == want and "場景 3" not in (hit.get("scene") or "")
        summaries.append(f"toast-gold: visible {want} -> {acted}")
        if not ok:
            problems.append(
                f"visible gold {want} under the toast was not selected "
                f"(got {acted}, toast {hit.get('toast')!r})"
            )
    else:
        toast_hits = []
        for point in toast_off_visible_probes(page):
            dismiss_selection(page)
            sheet_before = _sheet_open(page)
            tap_point(page, point["x"], point["y"])
            leaked, acted, hit, ready = _selection_leaked(page, sheet_before)
            if leaked:
                if len(toast_hits) < 6:
                    toast_hits.append(
                        f"{point['why']} ({point['x']:.0f},{point['y']:.0f}) "
                        f"selected {acted} toast {hit.get('toast')!r} ready {ready!r}"
                    )
            _ensure_town_map(page)
        summaries.append(
            f"toast-gold: no visible gold under the toast; "
            f"off-visible taps selected {len(toast_hits)}"
        )
        if toast_hits:
            problems.append(
                "toast covers no visible gold cell, but taps on it selected a cell: "
                + " | ".join(toast_hits)
            )
    page.evaluate("() => { if (typeof showToast === 'function') showToast('放置完成'); }")
    success_pe = page.evaluate(
        """() => {
          const el = document.getElementById('toast');
          return el ? getComputedStyle(el).pointerEvents : 'missing';
        }"""
    )
    if success_pe != "none":
        problems.append(f"success toast pointer-events is {success_pe!r}, expected none")
    summaries.append(
        f"toast pointer-events {toast_state.get('pointerEvents')!r} "
        f"burst {toast_state.get('burst')!r}"
    )

    for nav, tab_id in (("tasks", "tab-tasks"), ("expedition", "tab-expedition"), ("town", "tab-town")):
        tab = page.locator(f'#ktFooter [data-kt-nav="{nav}"]')
        box = tab.bounding_box() if tab.count() else None
        if not box:
            problems.append(f"footer tab {nav} has no box")
            continue
        tap_point(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(200)
        active = page.locator(f"#{tab_id}.active").count() > 0
        summaries.append(f"footer-nav {nav}: {'ok' if active else 'FAIL'}")
        if not active:
            problems.append(f"tapping footer tab {nav} did not show #{tab_id}")

    rect_problems, rect_summaries = _bar_rect_leaks(page, base_url)
    problems.extend(rect_problems)
    summaries.extend(rect_summaries)
    edge_problems, edge_summaries = _bar_border_leaks(page, base_url)
    for item in edge_problems:
        print("NOTHROUGH-PROBLEM " + item, flush=True)
    problems.extend(edge_problems)
    summaries.extend(edge_summaries)
    guard_problems, guard_summaries = _bar_guard_checks(page, base_url)
    problems.extend(guard_problems)
    summaries.extend(guard_summaries)

    print("TC-FE-TAP-BAR-NOTHROUGH " + " || ".join(summaries))
    assert not problems, "TC-FE-TAP-BAR-NOTHROUGH: " + " || ".join(problems[:10])


_TOAST_PROBE_START_JS = r"""
() => {
  const toast = document.getElementById('toast');
  const samples = [];
  const anims = [];
  const node = toast;
  const onAnim = (event) => {
    const target = event.target;
    if (!toast || (target !== toast && !toast.contains(target))) return;
    anims.push({
      t: performance.now(),
      name: event.animationName || '',
      onToast: target === toast
    });
  };
  document.addEventListener('animationstart', onAnim, true);
  const tick = () => {
    const el = document.getElementById('toast');
    const cs = el ? getComputedStyle(el) : null;
    const opacity = cs ? parseFloat(cs.opacity) : 0;
    samples.push({
      t: performance.now(),
      display: el ? (el.style.display || '') : 'missing',
      visibility: cs ? cs.visibility : 'missing',
      opacity: Number.isFinite(opacity) ? opacity : 0,
      text: el ? (el.textContent || '') : '',
      sameNode: el === node && !!el
    });
    window.__toastProbeFrame = requestAnimationFrame(tick);
  };
  window.__toastProbeFrame = requestAnimationFrame(tick);
  window.__toastProbe = { samples, anims, stop() {
    cancelAnimationFrame(window.__toastProbeFrame);
    document.removeEventListener('animationstart', onAnim, true);
  } };
  return true;
}
"""


def _now_ms(page):
    return page.evaluate("() => performance.now()")


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


def _toast_pair_problems(
    page, first, second, expected_first, expected_second, same_text, gap_ms=420
):
    """Two real taps, then rAF samples of #toast. Returns problem strings."""
    _scroll_cell_into_view(page, *first)
    _scroll_cell_into_view(page, *second)
    point_a = _activate_point(page, first[0], first[1], cell_points(page, *first))
    point_b = _activate_point(page, second[0], second[1], cell_points(page, *second))
    dismiss_selection(page)
    _silence_toast(page)
    page.evaluate(_TOAST_PROBE_START_JS)
    before1 = _now_ms(page)
    tap_point(page, point_a["x"], point_a["y"])
    after1 = _now_ms(page)
    page.wait_for_timeout(gap_ms)
    before2 = _now_ms(page)
    tap_point(page, point_b["x"], point_b["y"])
    after2 = _now_ms(page)
    page.wait_for_timeout(3400)
    payload = page.evaluate(
        """() => {
          const probe = window.__toastProbe;
          if (!probe) return null;
          probe.stop();
          return { samples: probe.samples, anims: probe.anims };
        }"""
    )
    label = ("same" if same_text else "different") + f"@{gap_ms}"
    if not payload:
        return [f"{label}: probe did not start"]
    samples = payload["samples"]
    anims = payload["anims"]
    problems = []
    gap = before2 - after1
    if gap < gap_ms - 280 or gap > gap_ms + 280:
        problems.append(
            f"{label}: taps were {gap:.0f}ms apart, want about {gap_ms}"
        )
    if not samples:
        return problems + [f"{label}: no rAF samples"]
    if any(not item.get("sameNode") for item in samples):
        problems.append(f"{label}: #toast node was replaced")

    def _shown(item):
        return item.get("display") == "block" and item.get("visibility") != "hidden"

    visible = [item for item in samples if _shown(item)]
    if not any(after1 - 30 <= item["t"] <= after1 + 200 and _shown(item) for item in samples):
        problems.append(
            f"{label}: toast was not shown within 200ms of the first tap "
            f"(text {samples[-1].get('text')!r})"
        )
    hold_until = after2 + 1900
    dropped = [
        item for item in samples
        if after1 <= item["t"] <= hold_until and not _shown(item)
    ]
    # Ignore samples from before the toast has appeared.
    appeared = [item["t"] for item in samples if item["t"] >= before1 and _shown(item)]
    if appeared:
        first_on = appeared[0]
        dropped = [item for item in dropped if item["t"] >= first_on]
    if dropped:
        early = dropped[0]
        problems.append(
            f"{label}: toast hid {(early['t'] - after2):.0f}ms after the second tap "
            f"(display {early.get('display')!r}); it must stay up until 1.9s"
        )
    elif not any(hold_until - 150 <= item["t"] <= hold_until + 80 and _shown(item) for item in samples):
        problems.append(f"{label}: no sample still showing the toast at ~1.9s after the second tap")
    late = [item for item in samples if item["t"] >= after2 + 2700]
    if not late:
        problems.append(f"{label}: sampling stopped before 2.7s after the second tap")
    elif any(_shown(item) for item in late):
        problems.append(f"{label}: toast still shown at ~2.8s after the second tap")

    if same_text:
        floor = 0.99
        full = [
            item for item in samples
            if item["t"] >= before1 and _shown(item) and item.get("opacity", 0) >= floor
        ]
        if not full:
            problems.append(f"{label}: opacity never held at {floor}")
        else:
            rose = full[0]["t"]
            after_rose = [item for item in samples if item["t"] >= rose]
            dipped = None
            for item in after_rose:
                if not _shown(item) or item.get("opacity", 0) < floor:
                    dipped = item
                    break
            if dipped is None:
                problems.append(f"{label}: toast never left full opacity")
            else:
                returned = [
                    item for item in after_rose
                    if item["t"] > dipped["t"] + 20
                    and _shown(item)
                    and item.get("opacity", 0) >= floor
                ]
                if returned:
                    problems.append(
                        f"{label}: opacity fell to {float(dipped.get('opacity') or 0):.2f} "
                        f"{(dipped['t'] - before1):.0f}ms after the first tap, then returned to "
                        f"{float(returned[0].get('opacity') or 0):.2f}"
                    )
                else:
                    hidden = [
                        item for item in after_rose
                        if item["t"] >= dipped["t"] and not _shown(item)
                    ]
                    if not hidden:
                        problems.append(f"{label}: fade started but the toast never hid")
                    else:
                        fade_ms = hidden[0]["t"] - dipped["t"]
                        if fade_ms > 350:
                            problems.append(
                                f"{label}: final fade lasted {fade_ms:.0f}ms, want <= 350"
                            )
            held = [
                item for item in samples
                if hold_until - 80 <= item["t"] <= hold_until + 120
                and _shown(item)
                and item.get("opacity", 0) >= floor
            ]
            if not held:
                problems.append(
                    f"{label}: opacity was not still >= {floor} at 1.9s after the second tap"
                )
        replayed = [
            item for item in anims
            if before2 - 5 <= item["t"] <= after2 + 40
        ]
        if replayed:
            problems.append(
                f"{label}: animationstart replayed on the second tap "
                f"({replayed[0].get('name')!r})"
            )
        opened = [item for item in anims if before1 - 20 <= item["t"] <= after1 + 80]
        if not opened:
            problems.append(f"{label}: first tap did not fire animationstart")
        wrong_text = [
            item for item in visible
            if expected_first not in (item.get("text") or "")
        ]
        if wrong_text:
            problems.append(f"{label}: text {wrong_text[0].get('text')!r}")
    else:
        switched = [
            item for item in samples
            if item["t"] >= before2 and expected_second in (item.get("text") or "")
        ]
        if not switched:
            problems.append(
                f"{label}: text never became {expected_second!r} "
                f"(last {samples[-1].get('text')!r})"
            )
        elif switched[0]["t"] - before2 > 250:
            problems.append(
                f"{label}: text switched {(switched[0]['t'] - before2):.0f}ms "
                "after the second tap, want within ~150ms"
            )
        stale = [
            item for item in visible
            if item["t"] >= before2 + 200 and expected_second not in (item.get("text") or "")
        ]
        if stale:
            problems.append(f"{label}: text left the second sentence ({stale[0].get('text')!r})")
    return problems


@pytest.mark.case_id("TC-FE-TOAST-TIMER-RESET")
def test_toast_timer_resets(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TOAST-TIMER-RESET 同一句提示的 opacity 不可中途掉下去。

    同一句在第一下之後 1.0 秒和 1.6 秒各再點一次。opacity 升到 0.99 之後
    必須維持到隱藏計時開始，中間不得掉回 0 再跳回 1。第二下之後至少 1.9 秒
    仍是滿透明度，最後淡出不超過約 0.35 秒。不得重播 animationstart。
    換句仍是大約 420ms，文字要改成已經有建築物。各跑 3 次。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0}],
    )
    catalog = _catalog_defs(base_url)
    _login(page, base_url)
    page.set_viewport_size({"width": 1100, "height": 800})
    _enter_new_build_scene2(page)
    kinds = _rendered_tap_kinds(page, catalog)
    unfit = next(
        (cell for cell in ((7, 0), (5, 7), (7, 7)) if kinds.get(cell) == "unfit"),
        (7, 0),
    )
    occupied = next(
        (cell for cell in ((0, 0), (1, 0)) if kinds.get(cell) == "occupied"),
        None,
    )
    if occupied is None:
        sprites = [fact for fact in page.evaluate(_RENDERED_PADS_JS) if fact.get("name")]
        if sprites:
            occupied = (sprites[0]["c"], sprites[0]["r"])
    assert occupied is not None, (
        "TC-FE-TOAST-TIMER-RESET needs a rendered building sprite to toast 已經有建築物"
    )
    problems = []
    for trial in (1, 2, 3):
        _relogin(page, base_url)
        page.set_viewport_size({"width": 1100, "height": 800})
        _enter_new_build_scene2(page)
        dismiss_selection(page)
        for same, second, expected_second, gap_ms in (
            (True, unfit, CANNOT_FIT_TOAST, 1000),
            (True, unfit, CANNOT_FIT_TOAST, 1600),
            (False, occupied, OCCUPIED_TOAST, 420),
        ):
            found = _toast_pair_problems(
                page, unfit, second, CANNOT_FIT_TOAST, expected_second, same, gap_ms
            )
            problems.extend(f"trial {trial}: {item}" for item in found)
    print(
        "TC-FE-TOAST-TIMER-RESET "
        + (f"{len(problems)} problems" if problems else "same@1000 3/3, same@1600 3/3, different 3/3")
    )
    assert not problems, "TC-FE-TOAST-TIMER-RESET: " + " | ".join(problems[:12])


@pytest.mark.case_id("TC-API-AUTOPLACE-FORMAL")
def test_autoplace_formal_shown(page, base_url, warehouse_db, warehouse_ids):
    """TC-API-AUTOPLACE-FORMAL 省略座標的自動放置，已放置時用書面語。

    錯誤句必須正好是「你已經興建了這種建築物。」。畫面若把這句顯示出來
    （showBuildFailure），不得改回「你已經興建咗呢種建築物」。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": BUILDING_NAME, "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0}],
    )
    def_id = _def_id_by_name(warehouse_db, BUILDING_NAME)["id"]
    _login(page, base_url)
    shown = page.evaluate(
        """async ({defId, kidId}) => {
          const res = await fetch('/api/kids/' + kidId + '/buildings', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({def_id: defId})
          });
          let data = {};
          try { data = await res.json(); } catch (err) { data = {}; }
          const message = (data && data.error) || '';
          if (typeof showBuildFailure === 'function') showBuildFailure(message);
          const toast = document.getElementById('toast');
          return {
            status: res.status,
            error: message,
            toast: toast ? (toast.textContent || '') : ''
          };
        }""",
        {"defId": def_id, "kidId": kid_id},
    )
    problems = []
    if shown.get("status") != 400:
        problems.append(f"HTTP {shown.get('status')}, expected 400")
    if shown.get("error") != _OWNED_FORMAL:
        problems.append(f"error {shown.get('error')!r}, expected {_OWNED_FORMAL!r}")
    if _OWNED_COLLOQUIAL in (shown.get("error") or ""):
        problems.append("response still uses 你已經興建咗呢種建築物")
    if _OWNED_FORMAL not in (shown.get("toast") or ""):
        problems.append(f"toast {shown.get('toast')!r} does not show {_OWNED_FORMAL!r}")
    if _OWNED_COLLOQUIAL in (shown.get("toast") or ""):
        problems.append("toast still shows 你已經興建咗呢種建築物")
    assert not problems, "TC-API-AUTOPLACE-FORMAL: " + " | ".join(problems)


def _parse_css_rgb(text):
    match = re.search(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", text or "")
    if not match:
        return None
    return tuple(int(match.group(i)) for i in range(1, 4))


# regress-61-003b81f.md, scrollTop 0, toast visible. These viewport points
# sit on the toast/footer band and select an off-screen cell.
_REGRESS_TOAST_FOOTER = {
    (1280, 720): (
        (640.0, 618.4),
        (640.0, 630.2),
        (640.0, 642.1),
        (640.0, 640.0),
    ),
    (1100, 800): (
        (550.0, 697.3),
        (550.0, 709.1),
        (550.0, 721.0),
    ),
}


def _show_probe_toast(page):
    """Make #toast display:block the way the regress probe did, before the click."""
    page.evaluate(
        """() => {
          if (typeof showToast === 'function') showToast('探針', 'info');
        }"""
    )


def _toast_footer_layout(page):
    return page.evaluate(
        """() => {
          function box(el) {
            if (!el) return null;
            const b = el.getBoundingClientRect();
            return {left: b.left, top: b.top, right: b.right, bottom: b.bottom};
          }
          const toast = document.getElementById('toast');
          return {
            toast: box(toast),
            footer: box(document.getElementById('ktFooter')),
            map: box(document.getElementById('townMap')),
            display: toast ? toast.style.display : 'missing'
          };
        }"""
    ) or {}


def _inside(box, x, y):
    if not box:
        return False
    return box["left"] <= x <= box["right"] and box["top"] <= y <= box["bottom"]


def _regress_toast_footer_points(page, width, height):
    """Exact regress clicks, an 8px grid around them, and the footer overlap.

    The overlap is the 8px where the toast covers #ktFooter, plus points just
    below the map's visible bottom edge that still sit in the footer.
    """
    exact = _REGRESS_TOAST_FOOTER[(width, height)]
    points = [{"x": x, "y": y, "why": "regress"} for x, y in exact]
    for x, y in exact:
        for dx, dy in ((-8, 0), (8, 0), (0, -8), (0, 8), (-8, -8), (8, 8), (-8, 8), (8, -8)):
            points.append({"x": x + dx, "y": y + dy, "why": "regress-grid"})
    layout = _toast_footer_layout(page)
    toast = layout.get("toast") or {}
    footer = layout.get("footer") or {}
    map_box = layout.get("map") or {}
    center_x = exact[0][0]
    if toast and footer:
        top = max(toast["top"], footer["top"])
        bottom = min(toast["bottom"], footer["top"] + 8, footer["bottom"])
        y = top
        guard = 0
        while y <= bottom + 0.1 and guard < 6:
            for x in (center_x - 16, center_x, center_x + 16):
                points.append({"x": x, "y": y, "why": "toast-footer-8"})
            y += 4
            guard += 1
    if map_box and footer:
        edge = min(map_box["bottom"], footer["top"])
        for dy in (2, 6, 8):
            py = edge + dy
            if footer["top"] - 1 <= py <= footer["bottom"]:
                points.append({"x": center_x, "y": py, "why": "below-map-in-footer"})
    kept = []
    seen = set()
    for point in points:
        x, y = point["x"], point["y"]
        if x < 1 or y < 1 or x >= width - 1 or y >= height - 1:
            continue
        key = (round(x, 1), round(y, 1))
        if key in seen:
            continue
        seen.add(key)
        kept.append(point)
    return kept, layout


@pytest.mark.case_id("TC-FE-TAP-VISIBLE-ONLY")
def test_tap_visible_only(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TAP-VISIBLE-ONLY 看不見的地圖範圍不得選格，也不得出提示。

    點必須落在 #townMap 四邊都被捲動區、動作列、頁尾和視窗裁過的可見矩形裡，
    而且落在菱形看得見的那一段。可見矩形外面的點，包括動作列上方的窄條、
    捲下去之後的上緣、下緣、頁尾後面，以及提示蓋住頁尾的那一帶，
    都不得選格、不得把 #readyStatus 改成已選擇空地、不得新出提示。
    1280×720 與 1100×800 在捲動 0、提示已顯示時，要點回歸報告的頁尾座標。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": "農場", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 3},
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
        ],
    )
    _login(page, base_url)
    problems = []
    summaries = []
    for width, height in ((1100, 800), (390, 844), (1280, 720)):
        for mode in ("bare", "picked", "unstore"):
            _relogin(page, base_url)
            page.set_viewport_size({"width": width, "height": height})
            if mode == "unstore":
                opened = _open_takeout_scene2(page)
                assert opened is None, f"TC-FE-TAP-VISIBLE-ONLY unstore: {opened}"
            elif mode == "picked":
                _enter_new_build_scene2(page)
                assert _pick_unbuilt(page, "工坊"), "工坊 missing from the palette"
            else:
                _enter_new_build_scene2(page)
            sanity = _require_helper_sees_selection(
                page, f"visible-only {mode} {width}x{height}"
            )
            if sanity:
                problems.append(sanity)
            for scroll in (0, "max"):
                set_village_scroll(page, scroll)
                probes = off_visible_probes(page)
                points = probes.get("points") or []
                label = f"{mode} {width}x{height} scroll {probes.get('scroll')}"
                if not points:
                    problems.append(f"{label}: off-visible sweep was empty")
                    summaries.append(f"{label}: empty")
                    continue
                leaks = []
                hidden_hits = 0
                tapped = 0
                for point in points:
                    if point.get("cell"):
                        hidden_hits += 1
                    owner = map_hit_at(page, point["x"], point["y"]) or {}
                    if owner.get("button") and not owner.get("map"):
                        continue
                    tapped += 1
                    dismiss_selection(page)
                    _silence_toast(page)
                    sheet_before = _sheet_open(page)
                    tap_point(page, point["x"], point["y"])
                    leaked, acted, hit, ready = _selection_leaked(page, sheet_before)
                    if leaked and len(leaks) < 6:
                        cell = point.get("cell")
                        leaks.append(
                            f"{point['why']} ({point['x']:.0f},{point['y']:.0f}) "
                            f"cellAt {cell} selected {acted} toast {hit.get('toast')!r} "
                            f"ready {ready!r}"
                        )
                    elif leaked:
                        leaks.append("more")
                    _ensure_town_map(page)
                    if "場景 2" not in _scene_aria(page) and mode != "unstore":
                        _scene2_tap_mode(page, mode if mode != "bare" else "bare", "工坊")
                        set_village_scroll(page, scroll)
                real_leaks = [item for item in leaks if item != "more"]
                summaries.append(
                    f"{label}: probes {len(points)}, tapped {tapped}, "
                    f"hidden-cell {hidden_hits}, leaks {len(leaks)}"
                )
                if real_leaks:
                    problems.append(f"{label}: " + " | ".join(real_leaks))
            if (width, height) == (1280, 720):
                dismiss_selection(page)
                _silence_toast(page)
                page.evaluate(
                    "() => { if (typeof showToast === 'function') showToast('已選擇空地。'); }"
                )
                toast_points = toast_off_visible_probes(page)
                toast_leaks = []
                for point in toast_points:
                    dismiss_selection(page)
                    tap_point(page, point["x"], point["y"])
                    hit = read_reaction(page)
                    ready = (_hint(page).get("ready") or "")
                    acted = selection_of(hit)
                    # The toast was already showing, so its text is not a new leak.
                    observed = dict(hit)
                    observed["toast"] = ""
                    observed["ready"] = ready
                    leaked = reaction_happened(observed)
                    if leaked and len(toast_leaks) < 4:
                        toast_leaks.append(
                            f"{point['why']} ({point['x']:.0f},{point['y']:.0f}) "
                            f"selected {acted} ready {ready!r}"
                        )
                    _ensure_town_map(page)
                summaries.append(
                    f"{mode} toast-strip: points {len(toast_points)}, leaks {len(toast_leaks)}"
                )
                if not toast_points:
                    problems.append(f"{mode} 1280x720: toast off-visible strip was empty")
                if toast_leaks:
                    problems.append(
                        f"{mode} 1280x720 toast strip: " + " | ".join(toast_leaks)
                    )
            if (width, height) in _REGRESS_TOAST_FOOTER and mode in ("bare", "picked"):
                set_village_scroll(page, 0)
                dismiss_selection(page)
                _show_probe_toast(page)
                band, layout = _regress_toast_footer_points(page, width, height)
                band_leaks = []
                regress_leaks = 0
                for point in band:
                    dismiss_selection(page)
                    _show_probe_toast(page)
                    tap_point(page, point["x"], point["y"])
                    hit = read_reaction(page)
                    ready = (_hint(page).get("ready") or "")
                    acted = selection_of(hit)
                    toast_text = hit.get("toast") or ""
                    observed = dict(hit)
                    observed["ready"] = ready
                    leaked = reaction_happened(observed, ignore_toast="探針")
                    if point["why"] == "regress" and leaked:
                        regress_leaks += 1
                    if leaked and len(band_leaks) < 6:
                        band_leaks.append(
                            f"{point['why']} ({point['x']:.1f},{point['y']:.1f}) "
                            f"selected {acted} toast {toast_text!r} ready {ready!r}"
                        )
                    elif leaked:
                        band_leaks.append("more")
                    _ensure_town_map(page)
                    if "場景 2" not in _scene_aria(page) and mode != "unstore":
                        _scene2_tap_mode(page, mode, "工坊")
                        set_village_scroll(page, 0)
                real_band = [item for item in band_leaks if item != "more"]
                toast_box = layout.get("toast")
                summaries.append(
                    f"{mode} {width}x{height} toast-footer: points {len(band)}, "
                    f"leaks {len(band_leaks)}, regress-leaks {regress_leaks}/"
                    f"{len(_REGRESS_TOAST_FOOTER[(width, height)])} "
                    f"toast-box {toast_box}"
                )
                if not band:
                    problems.append(f"{mode} {width}x{height}: toast-footer band was empty")
                if real_band:
                    problems.insert(
                        0,
                        f"{mode} {width}x{height} toast-footer: " + " | ".join(real_band),
                    )
    print("TC-FE-TAP-VISIBLE-ONLY " + " || ".join(summaries))
    assert not problems, "TC-FE-TAP-VISIBLE-ONLY: " + " || ".join(problems[:8])


def _select_cell(page, cell_x, cell_y):
    dismiss_selection(page)
    _silence_toast(page)
    data = cell_points(page, cell_x, cell_y)
    point = _activate_point(page, cell_x, cell_y, data)
    tap_point(page, point["x"], point["y"])
    page.wait_for_timeout(150)
    _silence_toast(page)


def _clip_mark(page, geom, margin=24):
    view = page.viewport_size
    left = max(0, geom["left"] - margin)
    top = max(0, geom["top"] - margin)
    right = min(view["width"], geom["left"] + geom["width"] + margin)
    bottom = min(view["height"], geom["top"] + geom["height"] + margin)
    return {
        "x": left,
        "y": top,
        "width": max(1, right - left),
        "height": max(1, bottom - top),
    }


def _contrast_cell(page, cell_x, cell_y, role):
    """Computed stroke, plus contrast of the painted line against adjacent fills."""
    _select_cell(page, cell_x, cell_y)
    geom = selected_mark_geometry(page)
    problems = []
    summary = f"{role} ({cell_x},{cell_y})"
    if not geom or (geom.get("c"), geom.get("r")) != (cell_x, cell_y):
        problems.append(f"{role} ({cell_x},{cell_y}) did not stay selected")
        return problems, summary + " not selected"
    if role == "edge" and not geom.get("edge"):
        problems.append(f"edge cell ({cell_x},{cell_y}) is not on the map rim")
    if role == "interior" and geom.get("edge"):
        problems.append(f"interior cell ({cell_x},{cell_y}) is on the map rim")
    clip = _clip_mark(page, geom)
    png = page.screenshot(clip=clip, scale="css", type="png")
    paint = chosen_mark_paint(page)
    computed = parse_hex((paint.get("chosen") or {}).get("stroke"))
    sampled = sample_line_backgrounds(png, geom, clip, computed)
    stroke_px = sampled.get("stroke")
    if computed and stroke_px and sum(
        (stroke_px[i] - computed[i]) ** 2 for i in range(3)
    ) > 55 * 55:
        problems.append(
            f"{role} ({cell_x},{cell_y}) painted line {hex_of(stroke_px)} "
            f"is not computed stroke {hex_of(computed)}"
        )
        stroke_px = computed
    backgrounds = sampled.get("backgrounds") or {}
    parts = [f"painted {hex_of(stroke_px)} n={sampled.get('strokeCount')}"]
    for name in ADJACENT_BACKGROUNDS:
        found = backgrounds.get(name)
        if not found:
            continue
        ratio = contrast_ratio(stroke_px, found["color"]) if stroke_px else 0
        parts.append(
            f"{name} {hex_of(found['color'])} x{found['count']} contrast {ratio:.2f}"
        )
        if ratio < 3:
            problems.append(
                f"{role} ({cell_x},{cell_y}) contrast against {name} "
                f"{ratio:.2f} < 3 (line {hex_of(stroke_px)}, fill {hex_of(found['color'])})"
            )
    if role == "edge" and "grass" not in backgrounds:
        problems.append(
            f"edge cell ({cell_x},{cell_y}) did not border outer grass #7eae52"
        )
    if role == "interior" and not any(
        name in backgrounds for name in ("empty", "gold", "dark-gold")
    ):
        problems.append(
            f"interior cell ({cell_x},{cell_y}) did not border a cell fill"
        )
    return problems, summary + " " + ", ".join(parts)


@pytest.mark.case_id("TC-FE-SELECTED-CONTRAST")
def test_selected_contrast(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-SELECTED-CONTRAST 選中格的實線要是 #7c2d12、3px。

    對比從畫面上的像素量：線旁邊實際出現的外圍草地、空地填色、金色填色，
    以及出現了的深金，都要至少 3:1。邊緣格要挨到草地，內部格要挨到格子填色。
    顏色不得跟金色格虛線 #d4a017 相同。金色虛線本身維持 #d4a017。
    """
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
    summaries = []
    for role, cell in (("edge", (6, 0)), ("interior", (4, 3))):
        cell_problems, summary = _contrast_cell(page, cell[0], cell[1], role)
        problems.extend(cell_problems)
        summaries.append(summary)
    paint = chosen_mark_paint(page)
    chosen = paint.get("chosen") or {}
    gold = paint.get("gold") or {}
    stroke = parse_hex(chosen.get("stroke"))
    if stroke != REQUIRED_STROKE:
        problems.append(f"chosen stroke {chosen.get('stroke')!r}, expected #7c2d12")
    if chosen.get("width") != 3:
        problems.append(f"chosen stroke-width {chosen.get('width')!r}, expected 3")
    if chosen.get("dashed"):
        problems.append("chosen mark is dashed; the selected line is solid")
    if stroke == GOLD_STROKE:
        problems.append("chosen stroke matches the gold dashed outline #d4a017")
    gold_stroke = parse_hex(gold.get("stroke"))
    if gold_stroke != GOLD_STROKE or not gold.get("dashed"):
        problems.append(
            f"gold outline {gold.get('stroke')!r} dashed {gold.get('dashed')!r}, "
            "expected #d4a017 dashed"
        )
    summaries.append(
        f"computed stroke {chosen.get('stroke')} width {chosen.get('width')} "
        f"gold {gold.get('stroke')}"
    )
    print("TC-FE-SELECTED-CONTRAST " + " || ".join(summaries))
    assert not problems, "TC-FE-SELECTED-CONTRAST: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-FOCUS-RING-VISIBLE")
def test_focus_ring_visible(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-FOCUS-RING-VISIBLE 焦點環在三個視窗的四條邊都看得到。

    尖角開口可以空。點選不畫環，Tab 才畫。不量中心 ±1px，也不量內緣 2–4。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    problems = []
    for width, height in ((1280, 720), (1100, 800), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        if "場景 2" not in (_scene_aria(page) or ""):
            _enter_new_build_scene2(page)
        dismiss_selection(page)
        _blur_focus(page)
        _scroll_cell_into_view(page, 3, 3)
        set_village_scroll(page, 0)
        page.wait_for_timeout(80)
        label = f"{width}x{height}"
        tap_cell_centre(page, 3, 3)
        page.wait_for_timeout(80)
        tapped = page.evaluate(
            """() => !!document.querySelector('#townMap .cell-btn:focus-visible')"""
        )
        ring = ring_layer_pixels(page) or {}
        print(
            f"TC-FE-FOCUS-RING-VISIBLE {label} tap focus-visible {tapped} "
            f"ring {ring.get('pixels')} {ring.get('display')}",
            flush=True,
        )
        if tapped or ring.get("pixels"):
            problems.append(
                f"{label}: tap showed the focus ring "
                f"(focus-visible {tapped}, layer {ring.get('pixels')} px)"
            )
        dismiss_selection(page)
        _blur_focus(page)
        page.wait_for_timeout(40)
        if not _tab_to_cell(page, 3, 3):
            problems.append(f"{label}: Tab did not focus (3,3)")
            continue
        page.wait_for_timeout(40)
        tabbed = page.evaluate(
            """() => !!document.querySelector('#townMap .cell-btn:focus-visible')"""
        )
        if not tabbed:
            problems.append(f"{label}: Tab did not set :focus-visible")
        _coarse_edge_ring(page, 3, 3, label + " Tab", problems, require_all=True)
    assert not problems, "TC-FE-FOCUS-RING-VISIBLE: " + " | ".join(problems[:12])


def _rotate_hidden_guard(page, label):
    """While #ktRotate is actually hidden, it must not be a tab stop.

    A viewport where the overlay is shown is not a failure. Forcing it
    visible with an inline style is not a product state.
    """
    state = hidden_tab_state(page)
    display = state.get("rotateDisplay")
    visibility = state.get("rotateVisibility")
    tab = state.get("rotateTab") or 0
    hidden = display == "none" or visibility == "hidden"
    detail = (
        f"guard rotate {label}: display {display} visibility {visibility} tab {tab}"
    )
    if "請轉橫向" not in (state.get("rotateText") or ""):
        return state, detail, "rotate overlay is missing 請轉橫向"
    if not hidden:
        return state, detail + " (shown, hidden-focus check skipped)", None
    if tab:
        return state, detail, f"{detail} is in the tab order"
    return state, detail + " PASS", None


@pytest.mark.case_id("TC-FE-HIDDEN-INERT")
def test_hidden_inert(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-HIDDEN-INERT 收起的抽屜不在 Tab 順序裡。

    抽屜收起（class `dr`、沒有 `o`、移出畫面）時，13 顆按鈕不得成為 Tab 停點。
    打開之後要回來。`#ktRotate` 只有在它真的隱藏時才要求離開 Tab 順序；
    橫向桌面的 display:none 若已不在 Tab 順序，是通過的 guard，不是紅測。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    problems = []
    summaries = []
    closed = hidden_tab_state(page)
    left = closed.get("drawerLeft")
    left_text = f"{left:.0f}" if isinstance(left, (int, float)) else "?"
    print(
        "TC-FE-HIDDEN-INERT collapsed "
        f"class {closed.get('drawerClass')!r} open {closed.get('drawerOpen')} "
        f"x={left_text} "
        f"tab {len(closed.get('drawerTab') or [])}/{closed.get('drawerCount')}"
    )
    if closed.get("drawerCount") != 13:
        problems.append(f"drawer has {closed.get('drawerCount')} buttons, expected 13")
    if closed.get("drawerOpen"):
        problems.append("drawer already has class o; collapsed tab order was not measured")
    elif closed.get("drawerTab"):
        problems.append(
            "collapsed drawer "
            f"(class {closed.get('drawerClass')}, offscreen x={left_text}) "
            "is in the tab order: " + ", ".join(closed["drawerTab"])
        )
    menu = page.locator("#app .gh .mb")
    assert menu.count() and menu.first.is_visible(), "menu button missing"
    menu.first.click()
    page.wait_for_timeout(400)
    opened = hidden_tab_state(page)
    if not opened.get("drawerOpen"):
        problems.append("drawer did not open from the menu button")
    missing = (opened.get("drawerCount") or 0) - len(opened.get("drawerTab") or [])
    if opened.get("drawerOpen") and missing:
        problems.append(f"open drawer left {missing} buttons out of the tab order")
    closer = page.locator("#dr .dc")
    if closer.count():
        closer.first.click()
        page.wait_for_timeout(300)
    for label, size in (("1280x720", (1280, 720)), ("390x844", (390, 844))):
        page.set_viewport_size({"width": size[0], "height": size[1]})
        page.wait_for_timeout(200)
        _state, detail, guard_problem = _rotate_hidden_guard(page, label)
        summaries.append(detail)
        if guard_problem:
            problems.append(guard_problem)
    if not any(item.startswith("guard rotate") and "PASS" not in item and "skipped" not in item
               for item in problems):
        if all("PASS" in item or "skipped" in item for item in summaries):
            summaries.append("guard rotate: PASS")
    print("TC-FE-HIDDEN-INERT " + " || ".join(summaries))
    assert not problems, "TC-FE-HIDDEN-INERT: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-PLACE-OWNED-FORMAL")
def test_place_owned_formal_shown(page, base_url, warehouse_db, warehouse_ids):
    """TC-API-PLACE-OWNED-FORMAL 指定格子的已放置建築，畫面也用書面語。

    POST 帶 cell_x、cell_y。錯誤句正好是「你已經興建了這種建築物。」。
    showBuildFailure 放進 #toast 的字不得是「你已經興建咗呢種建築物」。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": BUILDING_NAME, "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0}],
    )
    def_id = _def_id_by_name(warehouse_db, BUILDING_NAME)["id"]
    _login(page, base_url)
    shown = page.evaluate(
        """async ({defId, kidId}) => {
          const res = await fetch('/api/kids/' + kidId + '/buildings', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({def_id: defId, cell_x: 4, cell_y: 4})
          });
          let data = {};
          try { data = await res.json(); } catch (err) { data = {}; }
          const message = (data && data.error) || '';
          if (typeof showBuildFailure === 'function') showBuildFailure(message);
          const toast = document.getElementById('toast');
          return {
            status: res.status,
            error: message,
            toast: toast ? (toast.textContent || '') : ''
          };
        }""",
        {"defId": def_id, "kidId": kid_id},
    )
    problems = []
    if shown.get("status") != 400:
        problems.append(f"HTTP {shown.get('status')}, expected 400")
    if shown.get("error") != _OWNED_FORMAL:
        problems.append(f"error {shown.get('error')!r}, expected {_OWNED_FORMAL!r}")
    if _OWNED_COLLOQUIAL in (shown.get("error") or ""):
        problems.append("response still uses 你已經興建咗呢種建築物")
    if _OWNED_FORMAL not in (shown.get("toast") or ""):
        problems.append(f"toast {shown.get('toast')!r} does not show {_OWNED_FORMAL!r}")
    if _OWNED_COLLOQUIAL in (shown.get("toast") or ""):
        problems.append("toast still shows 你已經興建咗呢種建築物")
    assert not problems, "TC-API-PLACE-OWNED-FORMAL: " + " | ".join(problems)


def _sheet_open(page):
    sheet = page.locator("#actionSheet")
    try:
        return bool(sheet.count() and sheet.first.is_visible())
    except Exception:
        return False


def _map_reaction(page, x, y):
    """One real mouse click, read by ``reaction_happened``.

    The returned dict keeps ``chosen`` and ``preview`` from the page and
    also stores that cell under ``acted``, so a later reader that looks at
    only one of those keys still sees the selection.
    """
    dismiss_selection(page)
    _silence_toast(page)
    if _sheet_open(page):
        _close_sheet(page)
    tap_point(page, x, y)
    hit = read_reaction(page)
    sheet = _sheet_open(page)
    ready = (_hint(page).get("ready") or "")
    observed = dict(hit)
    observed["sheet"] = sheet
    observed["ready"] = ready
    acted = selection_of(observed)
    observed["acted"] = acted
    leaked = reaction_happened(observed)
    return {
        "leaked": leaked,
        "reacted": leaked,
        "acted": acted,
        "chosen": hit.get("chosen") or [],
        "preview": hit.get("preview") or [],
        "toast": hit.get("toast") or "",
        "sheet": sheet,
        "scene": hit.get("scene") or "",
        "ready": ready,
    }


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


def _require_helper_sees_selection(page, label):
    """Tap a visible gold cell through ``_map_reaction`` and ``_reaction_blame``.

    The helper must report that cell. A miss here means the reader is blind,
    so the test fails instead of treating a real selection as no reaction.
    Scene 3 is cancelled afterwards so the following probes stay put.
    """
    if "場景 2" not in _scene_aria(page) and "場景 3" not in _scene_aria(page):
        return f"{label}: helper sanity needs scene 2, got {_scene_aria(page)!r}"
    points = visible_gold_points(page, 6) or []
    if not points:
        return f"{label}: helper sanity found no visible gold cell"
    unstore = "放回" in ((_hint(page).get("ready") or ""))
    last = "no tap"
    for point in points:
        cell = (int(point["c"]), int(point["r"]))
        reaction = _map_reaction(page, point["x"], point["y"])
        seen = selection_of(reaction)
        if unstore:
            if seen == cell and "場景 3" in (reaction.get("scene") or ""):
                _cancel_scene3(page)
                return None
        else:
            bucket, detail = _reaction_blame(cell, "select", reaction, False)
            if seen == cell and not bucket and "場景 3" not in (reaction.get("scene") or ""):
                dismiss_selection(page)
                _silence_toast(page)
                return None
            last = (
                f"saw {seen} blame {detail!r} toast {reaction.get('toast')!r} "
                f"scene {reaction.get('scene')!r}"
            )
        if "場景 3" in _scene_aria(page):
            _cancel_scene3(page)
        if unstore:
            last = (
                f"saw {seen} toast {reaction.get('toast')!r} "
                f"scene {reaction.get('scene')!r}"
            )
    return f"{label}: helper sanity did not report the tapped cell ({last})"


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


_GROK_GAP = ((640.0, 609.0), (930.5, 609.0), (404.4, 609.0))
_GROK_GRASS = ((349.5, 577.0), (155.8, 544.0), (219.0, 544.0))
_BORDER_VIEWPORTS = ((1280, 720), (1100, 800), (1100, 844))
_BORDER_SCROLLS = (0, 300, 366)
_PALETTE_REVERSE = ((254, 490), (254, 505))


def _gap_samples(band):
    span = band["right"] - band["left"]
    # Near the bar's lower edge, where the 1280 repro sits about 1px into the strip.
    y = band["top"] + min(1.0, max(0.4, (band["bottom"] - band["top"]) * 0.35))
    points = []
    for index in range(11):
        points.append({
            "x": band["left"] + span * (index + 0.5) / 11,
            "y": y,
            "why": "band",
        })
    return points


@pytest.mark.case_id("TC-FE-TAP-BAR-GAP-BAND")
def test_tap_bar_gap_band(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TAP-BAR-GAP-BAND 底欄和地圖下緣之間的窄條不得打中藏起來的格。

    窄條的 y 用畫面矩形：底欄下緣到地圖下緣。1280×720 大約 8px，1100×800
    大約 6.9px。一個點只有落在那一格看得見的部分（可見像素 > 0）才可以選格。
    窄條上的格是 0px。1280 捲動 0 要點 (640,609)、(930.5,609)、(404.4,609)。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": "農場", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 3},
            {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
        ],
    )
    _login(page, base_url)
    problems = []
    summaries = []
    for width, height in ((1280, 720), (1100, 800)):
        for mode in ("bare", "picked"):
            _relogin(page, base_url)
            page.set_viewport_size({"width": width, "height": height})
            _enter_new_build_scene2(page)
            if mode == "picked":
                assert _pick_unbuilt(page, "工坊"), "工坊 missing"
            set_village_scroll(page, 0)
            band = bar_gap_band(page)
            if not band or band.get("height", 0) < 2:
                problems.append(f"{mode} {width}x{height}: gap band missing")
                continue
            points = _gap_samples(band)
            if (width, height) == (1280, 720):
                for x, y in _GROK_GAP:
                    points.append({"x": x, "y": y, "why": "grok"})
            leaks = []
            grok_hits = []
            sanity = _require_helper_sees_selection(page, f"gap {mode} {width}x{height}")
            if sanity:
                problems.append(sanity)
            set_village_scroll(page, 0)
            for point in points:
                reaction = _map_reaction(page, point["x"], point["y"])
                visible = None
                on_visible = None
                acted = reaction["acted"] if isinstance(reaction["acted"], tuple) else None
                if acted:
                    vis = cell_visibility(page, acted[0], acted[1], point["x"], point["y"]) or {}
                    visible = vis.get("visible")
                    on_visible = vis.get("pointOnVisible")
                bad = reaction_happened(reaction) or (
                    acted is not None and (not visible or not on_visible)
                )
                if bad:
                    leaks.append(point["why"])
                    if len(leaks) <= 6 or point["why"] == "grok":
                        leaks.append(
                            f"{point['why']} ({point['x']:.1f},{point['y']:.1f}) "
                            f"cell {acted} visible {visible} toast {reaction['toast']!r}"
                        )
                if point["why"] == "grok":
                    grok_hits.append(
                        f"({point['x']:.1f},{point['y']:.1f}) "
                        f"{'LEAK' if bad else 'quiet'} cell {acted} visible {visible} "
                        f"toast {reaction['toast']!r} sheet {reaction['sheet']}"
                    )
                _ensure_town_map(page)
                if "場景 2" not in _scene_aria(page):
                    _scene2_tap_mode(page, mode, "工坊")
                    set_village_scroll(page, 0)
            summaries.append(
                f"{mode} {width}x{height} gap h={band['height']:.2f} "
                f"points {len(points)} leaks {sum(1 for item in leaks if not item.startswith('band') and not item.startswith('grok') or ' ' in item)} "
                f"grok {grok_hits}"
            )
            # Count real leak records (the ones with a space are the details).
            details = [item for item in leaks if " " in item]
            if details:
                problems.insert(0, f"{mode} {width}x{height} gap: " + " | ".join(details[:6]))
            elif not any(point["why"] == "band" for point in points):
                problems.append(f"{mode} {width}x{height}: no band samples")
    print("TC-FE-TAP-BAR-GAP-BAND " + " || ".join(summaries))
    assert not problems, "TC-FE-TAP-BAR-GAP-BAND: " + " || ".join(problems[:8])


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


def _grass_samples(band):
    points = []
    columns, rows = 8, 4
    width = band["right"] - band["left"]
    height = band["bottom"] - band["top"]
    for row in range(rows):
        y = band["top"] + height * (row + 0.5) / rows
        for col in range(columns):
            x = band["left"] + width * (col + 0.5) / columns
            points.append({"x": x, "y": y, "why": "grass"})
    return points


def _on_button(page, x, y):
    return page.evaluate(
        """([x, y]) => {
          const el = document.elementFromPoint(x, y);
          if (!el || !el.closest) return false;
          return !!el.closest('button, a, [role="button"]');
        }""",
        [x, y],
    )


@pytest.mark.case_id("TC-FE-TAP-SCENE-GRASS-EDGE")
def test_tap_scene_grass_edge(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TAP-SCENE-GRASS-EDGE 場景 1 村子下面的草地不得選格、出提示或開面板。

    草地的上緣是真正把格子裁掉的捲動區，不寫死是哪一個元素。1280×720 要點
    (349.5,577)、(155.8,544)、(219,544)。少建築和滿鎮（含銀行）各跑一次。
    """
    kid_id = warehouse_ids["kid_id"]
    _ensure_bank_def(warehouse_db)
    few = [
        {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
        {"name": "農場", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 3},
        {"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12},
    ]
    full_names = (
        "商店", "農場", "圖書館", "健身室", "醫院", "探險公會",
        "工坊", "燈塔", "競技場", "天文台", "銀行",
    )
    full = []
    slot = 0
    for name in full_names:
        full.append({
            "name": name,
            "level": 1,
            "stored": 0,
            "cell_x": (slot % 4) * 2,
            "cell_y": (slot // 4) * 2,
        })
        slot += 1
    _login(page, base_url)
    problems = []
    summaries = []
    for label, buildings in (("few", few), ("full", full)):
        _reset_kid(warehouse_db, kid_id, points=800, buildings=buildings)
        _relogin(page, base_url)
        page.set_viewport_size({"width": 1280, "height": 720})
        _enter_new_build_scene2(page)
        sanity = _require_helper_sees_selection(page, f"grass {label}")
        if sanity:
            problems.append(sanity)
        _restore_scene1(page)
        set_village_scroll(page, 0)
        band = cell_clip_band(page)
        if not band:
            problems.append(f"{label}: grass band missing")
            continue
        points = []
        for point in _grass_samples(band):
            if _on_button(page, point["x"], point["y"]):
                continue
            points.append(point)
        for x, y in _GROK_GRASS:
            points.append({"x": x, "y": y, "why": "grok"})
        leaks = []
        grok_hits = []
        for point in points:
            reaction = _map_reaction(page, point["x"], point["y"])
            if reaction_happened(reaction) or "場景 1" not in (reaction["scene"] or _scene_aria(page)):
                if len(leaks) < 8 or point["why"] == "grok":
                    leaks.append(
                        f"{point['why']} ({point['x']:.1f},{point['y']:.1f}) "
                        f"cell {reaction['acted']} toast {reaction['toast']!r} "
                        f"sheet {reaction['sheet']} scene {reaction['scene']!r}"
                    )
            if point["why"] == "grok":
                grok_hits.append(
                    leaks[-1] if reaction_happened(reaction) else f"({point['x']:.1f},{point['y']:.1f}) quiet"
                )
            _restore_scene1(page)
            set_village_scroll(page, 0)
        summaries.append(
            f"{label} grass {band['top']:.1f}-{band['bottom']:.1f} "
            f"points {len(points)} leaks {len(leaks)} grok {grok_hits}"
        )
        if leaks:
            problems.insert(0, f"{label}: " + " | ".join(leaks[:6]))
        if len(points) < 24:
            problems.append(f"{label}: only {len(points)} grass points")
    print("TC-FE-TAP-SCENE-GRASS-EDGE " + " || ".join(summaries))
    assert not problems, "TC-FE-TAP-SCENE-GRASS-EDGE: " + " || ".join(problems[:8])


def _probe_blocked(page, x, y, width, height):
    if x < 1 or y < 1 or x >= width - 1 or y >= height - 1:
        return None
    reaction = _map_reaction(page, x, y)
    if not reaction_happened(reaction):
        return None
    return (
        f"({x:.1f},{y:.1f}) cell {reaction['acted']} "
        f"toast {reaction['toast']!r} sheet {reaction['sheet']}"
    )


def _box_contains(rect, x, y):
    return bool(
        rect
        and rect["left"] <= x <= rect["right"]
        and rect["top"] <= y <= rect["bottom"]
    )


def _reverse_expectation(cell, kind):
    if cell is None:
        return "no reaction"
    if kind == "select":
        return f"selects {cell}"
    return f"reaches {cell} ({kind})"


def _point_target(page, x, y):
    try:
        return page.evaluate(
            """([x, y]) => {
              const el = document.elementFromPoint(x, y);
              if (!el) return "none";
              const id = el.id ? "#" + el.id : "";
              const raw = typeof el.className === "string" ? el.className : "";
              const cls = raw.trim().split(/\\s+/).filter(Boolean).slice(0, 3).join(".");
              return el.tagName.toLowerCase() + id + (cls ? "." + cls : "");
            }""",
            [x, y],
        )
    except Exception:
        return "?"


def _probe_reverse(page, x, y, width, height, kinds, expect_cell=None):
    """Map reach for a point at least 1px outside solid UI.

    A visible cell (inside `#village` and on a top face) must receive the
    tap: gold selects it, any other cell toasts that cell's sentence.
    Silence there is over-blocking. No visible cell means no reaction.
    `expect_cell` requires that exact cell to be selected.
    """
    if x < 1 or y < 1 or x >= width - 1 or y >= height - 1:
        return "outside-viewport", f"({int(x)},{int(y)}) outside the viewport"
    live = cell_under_point(page, x, y)
    cell = None if not live else (int(live["c"]), int(live["r"]))
    if expect_cell is not None and cell != expect_cell:
        return "geometry", f"({int(x)},{int(y)}) live {cell} != {expect_cell}"
    reaction = _map_reaction(page, x, y)
    if expect_cell is not None:
        if reaction["acted"] == expect_cell and "場景 3" not in (reaction["scene"] or ""):
            return None, f"selects {expect_cell}"
        return "miss", (
            f"({int(x)},{int(y)}) expected select {expect_cell}, "
            f"got {reaction['acted']} toast {reaction['toast']!r} "
            f"scene {reaction['scene']!r} target {_point_target(page, x, y)}"
        )
    if cell is None:
        if reaction_happened(reaction):
            return "leak", (
                f"({int(x)},{int(y)}) no visible cell but "
                f"cell {reaction['acted']} toast {reaction['toast']!r} "
                f"sheet {reaction['sheet']} target {_point_target(page, x, y)}"
            )
        return None, "no reaction"
    kind = kinds.get(cell, "unfit")
    bucket, detail = _reaction_blame(cell, kind, reaction, False)
    if bucket:
        reached = detail or "no reaction"
        return "miss", (
            f"({int(x)},{int(y)}) visible {cell} kind {kind}: {reached} "
            f"target {_point_target(page, x, y)}"
        )
    return None, _reverse_expectation(cell, kind)


def _restore_scene2(page, scroll):
    _ensure_town_map(page)
    if "場景 2" not in _scene_aria(page):
        _scene2_tap_mode(page, "picked", "工坊")
    set_village_scroll(page, scroll)


def _enter_scene3(page, scroll):
    """Open scene 3 at this scroll. Try several gold points; do not move the scroll."""
    _scene2_tap_mode(page, "picked", "工坊")
    set_village_scroll(page, scroll)
    points = visible_gold_points(page, 8)
    if not points:
        return "no visible gold cell"
    last = "scene 3 control missing"
    for gold in points:
        if "場景 2" not in _scene_aria(page):
            _scene2_tap_mode(page, "picked", "工坊")
            set_village_scroll(page, scroll)
        dismiss_selection(page)
        _silence_toast(page)
        tap_point(page, gold["x"], gold["y"])
        page.wait_for_timeout(150)
        advance = page.locator("#btnToScene3")
        ready = advance.count() and advance.first.is_visible() and advance.first.is_enabled()
        if not ready:
            last = (
                f"scene 3 control missing after "
                f"({int(gold['c'])},{int(gold['r'])})"
            )
            continue
        advance.first.click()
        page.wait_for_timeout(200)
        set_village_scroll(page, scroll)
        if "場景 3" not in _scene_aria(page):
            last = f"still {_scene_aria(page)!r}"
            _scene2_tap_mode(page, "picked", "工坊")
            set_village_scroll(page, scroll)
            continue
        return None
    return last


def _fractional_band_hit(rects, x, y):
    """A solid control whose 0–1px outer band contains this point, if any."""
    for rect in rects:
        if in_fractional_outer_band(rect, x, y):
            return rect
    return None


def _bar_border_leaks(page, base_url):
    """Integer border pixels, plus integers at least 1px outside.

    On the border box, including the edge row and column, the tap is blocked.
    A must-reach point is floor(top)-1, ceil(bottom)+1, floor(left)-1, or
    ceil(right)+1 (and one pixel further). The 0–1px band outside a control
    is not asserted: hit-testing still targets the control there. Points
    outside #village are a different rule and stay must-not-react.
    """
    catalog = _catalog_defs(base_url)
    problems = []
    summaries = []
    changes = []
    palette_hits = {point: [] for point in _PALETTE_REVERSE}
    print(
        "NOTHROUGH-DROP on-edge .5 samples are not asserted: "
        "(294.5,163.5) at 1280 scroll 300 and 366; "
        "(177,163.5) at 1280 scroll 366; "
        "(976.5,244.3) at 1100x844 scroll 366; "
        "(976.5,222.3) at 1100x800 scroll 0, 300, and 366",
        flush=True,
    )
    for width, height in _BORDER_VIEWPORTS:
        _relogin(page, base_url)
        page.set_viewport_size({"width": width, "height": height})
        _enter_new_build_scene2(page)
        assert _pick_unbuilt(page, "工坊"), f"{width}x{height}: 工坊 missing"
        sanity = _require_helper_sees_selection(page, f"border {width}x{height}")
        if sanity:
            problems.append(sanity)
        kinds = _rendered_tap_kinds(page, catalog)
        seen = set()
        for scroll in _BORDER_SCROLLS:
            _scene2_tap_mode(page, "picked", "工坊")
            placed = set_village_scroll(page, scroll)
            actual = None if not placed else round(placed.get("scroll") or 0, 1)
            blocked = []
            reverse = []
            rects = {}
            for name, selector in (
                ("palette", "#palette"),
                ("tools", "#townMap .tools"),
                ("bar", "#readyBar"),
            ):
                rect = surface_rect(page, selector)
                rects[name] = rect
                if not rect:
                    problems.append(f"{width}x{height} scroll {scroll}: {name} missing")
                    continue
                if name != "bar":
                    for point in inclusive_border_samples(rect):
                        point = dict(point)
                        point["who"] = name
                        blocked.append(point)
                for point in outside_edge_points(rect):
                    point = dict(point)
                    point["who"] = name
                    reverse.append(point)
            if width == 1280 and scroll == 366:
                tools = rects.get("tools") or {}
                outside = [
                    point for point in reverse
                    if point.get("who") == "tools" and point.get("name") == "bottom-1"
                ]
                first_out = None if not outside else outside[0]["y"]
                print(
                    f"NOTHROUGH-TOOLS 1280 scroll {actual} "
                    f"bottom {tools.get('bottom')} right {tools.get('right')} "
                    f"left {tools.get('left')} top {tools.get('top')} "
                    f"ceil(bottom)+1 {first_out}",
                    flush=True,
                )
            if width == 1280 and (scroll == 0 or actual not in seen):
                for name, selector in (("bar", "#readyBar"), ("palette", "#palette")):
                    rect = rects.get(name) or surface_rect(page, selector)
                    if not rect:
                        continue
                    for point in integer_border_row(rect):
                        point = dict(point)
                        point["who"] = name + "-top"
                        blocked.append(point)
            seen.add(actual)
            solids = open_solid_rects(page)
            print(
                f"TC-FE-TAP-BAR-NOTHROUGH border {width}x{height} "
                f"scroll {actual} blocked {len(blocked)} reverse {len(reverse)}",
                flush=True,
            )
            leaks = []
            reverse_miss = []
            skipped = 0
            for point in blocked:
                detail = _probe_blocked(page, point["x"], point["y"], width, height)
                if not detail:
                    continue
                if len(leaks) < 6:
                    leaks.append(f"{point['who']} {point['name']} {detail}")
                else:
                    leaks.append("more")
                _restore_scene2(page, scroll)
            for point in reverse:
                covered = solid_selector(solids, point["x"], point["y"])
                if covered:
                    skipped += 1
                    continue
                band = _fractional_band_hit(solids, point["x"], point["y"])
                if band:
                    skipped += 1
                    print(
                        f"NOTHROUGH-BAND {width}x{height} scroll {scroll} "
                        f"{point.get('who')} {point.get('name')} "
                        f"({int(point['x'])},{int(point['y'])}) "
                        f"within 1px of {band.get('sel')}, not asserted",
                        flush=True,
                    )
                    continue
                status, detail = _probe_reverse(
                    page, point["x"], point["y"], width, height, kinds
                )
                if str(point.get("name") or "").startswith("top-"):
                    print(
                        f"NOTHROUGH-TOP {width}x{height} scroll {scroll} "
                        f"{point.get('who')} {point.get('name')} "
                        f"({int(point['x'])},{int(point['y'])}) {detail}",
                        flush=True,
                    )
                if status:
                    if len(reverse_miss) < 6:
                        reverse_miss.append(f"{point['who']} {point['name']} {detail}")
                    else:
                        reverse_miss.append("more")
                _restore_scene2(page, scroll)
            real = [item for item in leaks if item != "more"]
            real_reverse = [item for item in reverse_miss if item != "more"]
            summaries.append(
                f"border {width}x{height} scroll {actual}: "
                f"blocked {len(blocked)} leaks {len(leaks)} "
                f"reverse {len(reverse)} skipped {skipped} miss {len(reverse_miss)}"
            )
            if real:
                problems.append(
                    f"border {width}x{height} scroll {actual}: " + " | ".join(real[:6])
                )
            if real_reverse:
                problems.append(
                    f"reverse {width}x{height} scroll {actual}: "
                    + " | ".join(real_reverse[:6])
                )
        for px, py in _PALETTE_REVERSE:
            for scroll in (0, 300, 366):
                _scene2_tap_mode(page, "picked", "工坊")
                set_village_scroll(page, scroll)
                palette = surface_rect(page, "#palette")
                solids = open_solid_rects(page)
                probe_x, probe_y = px, py
                if palette and in_fractional_outer_band(palette, px, py):
                    probe_x = math.ceil(palette["right"]) + 1
                    print(
                        f"NOTHROUGH-PALETTE ({px},{py}) {width}x{height} "
                        f"scroll {scroll} within 1px of palette "
                        f"(right {palette['right']}), not asserted; "
                        f"using ({probe_x},{py})",
                        flush=True,
                    )
                elif _box_contains(palette, px, py):
                    print(
                        f"NOTHROUGH-PALETTE ({px},{py}) {width}x{height} "
                        f"scroll {scroll} inside palette",
                        flush=True,
                    )
                    continue
                elif solid_selector(solids, px, py):
                    print(
                        f"NOTHROUGH-PALETTE ({px},{py}) {width}x{height} "
                        f"scroll {scroll} covered",
                        flush=True,
                    )
                    continue
                if _fractional_band_hit(solids, probe_x, probe_y) or solid_selector(
                    solids, probe_x, probe_y
                ):
                    print(
                        f"NOTHROUGH-PALETTE ({probe_x},{probe_y}) {width}x{height} "
                        f"scroll {scroll} still on a control, not asserted",
                        flush=True,
                    )
                    continue
                live = cell_under_point(page, probe_x, probe_y)
                cell = None if not live else (int(live["c"]), int(live["r"]))
                print(
                    f"NOTHROUGH-PALETTE ({probe_x},{probe_y}) {width}x{height} "
                    f"scroll {scroll} cell {cell}",
                    flush=True,
                )
                expect = cell if cell == (0, 5) else None
                status, detail = _probe_reverse(
                    page, probe_x, probe_y, width, height, kinds, expect_cell=expect
                )
                if cell == (0, 5) and not status:
                    palette_hits[(px, py)].append(
                        f"{width}x{height} scroll {scroll} at ({probe_x},{probe_y})"
                    )
                if status:
                    problems.append(
                        f"palette reverse ({probe_x},{probe_y}) {width}x{height} "
                        f"scroll {scroll}: {detail}"
                    )
                else:
                    summaries.append(
                        f"palette ({probe_x},{probe_y}) {width}x{height} "
                        f"scroll {scroll} cell {cell} {detail}"
                    )
        _scene2_tap_mode(page, "picked", "工坊")
        set_village_scroll(page, 0)
        _click_cell(page, 2, 2)
        advance = page.locator("#btnToScene3")
        if advance.count() and advance.first.is_visible() and advance.first.is_enabled():
            advance.first.click()
            page.wait_for_timeout(200)
        place = surface_rect(page, "#uxPlaceBar")
        if width != 1280 or not place:
            if width == 1280:
                problems.append("place bar missing for the top-edge sweep")
        else:
            leaks = []
            row = integer_border_row(place)
            for point in row:
                detail = _probe_blocked(page, point["x"], point["y"], width, height)
                if detail and len(leaks) < 4:
                    leaks.append(detail)
                elif detail:
                    leaks.append("more")
            summaries.append(
                f"place-bar top {width}x{height}: points {len(row)} leaks {len(leaks)}"
            )
            if leaks:
                problems.append(
                    "place-bar top: " + " | ".join(item for item in leaks if item != "more")
                )
        for scroll in _BORDER_SCROLLS:
            opened = _enter_scene3(page, scroll)
            print(
                f"NOTHROUGH-PLACE {width}x{height} scroll {scroll} "
                f"{opened or 'open'}",
                flush=True,
            )
            if opened:
                problems.append(
                    f"place bar {width}x{height} scroll {scroll}: {opened}"
                )
                summaries.append(
                    f"place-bar reverse {width}x{height} scroll {scroll}: "
                    f"not opened ({opened})"
                )
                continue
            place = surface_rect(page, "#uxPlaceBar")
            if not place:
                problems.append(f"place bar missing {width}x{height} scroll {scroll}")
                continue
            place_kinds = _rendered_tap_kinds(page, catalog)
            solids = open_solid_rects(page)
            outside = outside_edge_points(place)
            misses = []
            skipped = 0
            for point in outside:
                if solid_selector(solids, point["x"], point["y"]):
                    skipped += 1
                    continue
                if _fractional_band_hit(solids, point["x"], point["y"]):
                    skipped += 1
                    continue
                status, detail = _probe_reverse(
                    page, point["x"], point["y"], width, height, place_kinds
                )
                if status:
                    if len(misses) < 4:
                        misses.append(f"{point['name']} {detail}")
                    else:
                        misses.append("more")
                if "場景 3" not in _scene_aria(page):
                    reopened = _enter_scene3(page, scroll)
                    if reopened:
                        misses.append(f"left scene 3 ({reopened})")
                        break
                    solids = open_solid_rects(page)
            summaries.append(
                f"place-bar reverse {width}x{height} scroll {scroll}: "
                f"points {len(outside)} skipped {skipped} miss {len(misses)}"
            )
            real = [item for item in misses if item != "more"]
            if real:
                problems.append(
                    f"place-bar reverse {width}x{height} scroll {scroll}: "
                    + " | ".join(real[:4])
                )
    for px, py in _PALETTE_REVERSE:
        where = palette_hits[(px, py)]
        if not where:
            problems.append(
                f"({px},{py}) never landed on (0,5) outside the palette"
            )
        else:
            print(
                f"NOTHROUGH-REVERSE ({px},{py}) selects (0,5) at {where}",
                flush=True,
            )
    print(f"TC-FE-TAP-BAR-NOTHROUGH EXPECT-CHANGES {len(changes)}", flush=True)
    for line in changes:
        print("NOTHROUGH-CHANGE " + line, flush=True)
    return problems, summaries


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


@pytest.mark.case_id("TC-FE-SELECTED-OVER-GOLD")
def test_selected_over_gold(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-SELECTED-OVER-GOLD 選中實線要畫在金色虛線上面。

    (0,0) 和 (3,3) 的四條邊，每條邊中段 9 個點都要是 #7c2d12，不能是 #d4a017。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    problems = []
    summaries = []
    for cell_x, cell_y in ((0, 0), (3, 3)):
        _scroll_cell_into_view(page, cell_x, cell_y)
        _select_cell(page, cell_x, cell_y)
        geom = selected_mark_geometry(page)
        if not geom or (geom.get("c"), geom.get("r")) != (cell_x, cell_y):
            problems.append(f"({cell_x},{cell_y}) did not stay selected")
            continue
        clip = _clip_mark(page, geom, margin=8)
        png = page.screenshot(clip=clip, scale="css", type="png")
        edges = sample_selected_edges(png, geom, clip)
        parts = []
        for name, counts in edges.items():
            parts.append(f"{name} {counts['brown']}/9 brown {counts['gold']}/9 gold")
            if counts["brown"] < 9 or counts["gold"]:
                problems.append(
                    f"({cell_x},{cell_y}) {name} {counts['brown']}/9 visible as #7c2d12 "
                    f"({counts['gold']} look like #d4a017)"
                )
        summaries.append(f"({cell_x},{cell_y}) " + ", ".join(parts))
    print("TC-FE-SELECTED-OVER-GOLD " + " || ".join(summaries))
    assert not problems, "TC-FE-SELECTED-OVER-GOLD: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-FOCUS-RING-ABOVE-SPRITE")
def test_focus_ring_above_sprite(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-FOCUS-RING-ABOVE-SPRITE 有建築的格子，焦點環要畫在建築圖上面。

    沿四條邊、和建築圖重疊的位置抽樣。那些像素要是 #fff8e7 或 #6b4f2a。
    選中線畫在菱形裡面。建築圖蓋住線的那段，螢幕上要是 #7c2d12。
    圖沒蓋到的邊不算被蓋住。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[{"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0}],
    )
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _scroll_cell_into_view(page, 0, 0)
    shape = focus_ring_shape(page, 0, 0) or {}
    problems = []
    if not shape.get("ring"):
        problems.append(f"focus ring missing ({shape.get('error')})")
    else:
        sprite = page.evaluate(
            """([c, r]) => {
              const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
                const cs = getComputedStyle(el);
                return parseInt(cs.getPropertyValue('--c'), 10) === c
                  && parseInt(cs.getPropertyValue('--r'), 10) === r;
              });
              const img = pad && pad.querySelector(':scope > .sprite');
              if (!img || img.hidden) return null;
              const box = img.getBoundingClientRect();
              return {left: box.left, top: box.top, right: box.right, bottom: box.bottom};
            }""",
            [0, 0],
        )
        if not sprite:
            problems.append("shop sprite is not visible")
        else:
            tips = shape["ring"]["tips"]
            order = ("N", "E", "S", "W")
            samples = []
            for index, name in enumerate(("NE", "SE", "SW", "NW")):
                start = tips[order[index]]
                end = tips[order[(index + 1) % 4]]
                for step_index in range(15):
                    t = 0.12 + step_index * (0.76 / 14)
                    x = start["x"] + (end["x"] - start["x"]) * t
                    y = start["y"] + (end["y"] - start["y"]) * t
                    if sprite["left"] <= x <= sprite["right"] and sprite["top"] <= y <= sprite["bottom"]:
                        samples.append({"x": x, "y": y, "edge": name})
            opaque = page.evaluate(
                """([c, r, points]) => {
                  const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
                    const cs = getComputedStyle(el);
                    return parseInt(cs.getPropertyValue('--c'), 10) === c
                      && parseInt(cs.getPropertyValue('--r'), 10) === r;
                  });
                  const img = pad && pad.querySelector(':scope > .sprite');
                  if (!img || img.hidden) return {error: 'missing sprite'};
                  const w = img.naturalWidth || 0;
                  const h = img.naturalHeight || 0;
                  if (w < 2 || h < 2) return {error: 'sprite not loaded'};
                  const box = img.getBoundingClientRect();
                  const canvas = document.createElement('canvas');
                  canvas.width = w;
                  canvas.height = h;
                  const ctx = canvas.getContext('2d', {willReadFrequently: true});
                  try {
                    ctx.drawImage(img, 0, 0, w, h);
                  } catch (err) {
                    return {error: String(err)};
                  }
                  const pixels = [];
                  for (const point of points) {
                    if (point.x < box.left || point.x > box.right || point.y < box.top || point.y > box.bottom) {
                      pixels.push({a: 0, r: 0, g: 0, b: 0});
                      continue;
                    }
                    const ix = Math.max(0, Math.min(w - 1, Math.round((point.x - box.left) / box.width * (w - 1))));
                    const iy = Math.max(0, Math.min(h - 1, Math.round((point.y - box.top) / box.height * (h - 1))));
                    let data;
                    try {
                      data = ctx.getImageData(ix, iy, 1, 1).data;
                    } catch (err) {
                      return {error: String(err)};
                    }
                    pixels.push({a: data[3], r: data[0], g: data[1], b: data[2]});
                  }
                  return {pixels};
                }""",
                [0, 0, samples],
            )
            if not opaque or opaque.get("error"):
                problems.append(f"sprite alpha {opaque}")
            else:
                covered = []
                for sample, pixel in zip(samples, opaque.get("pixels") or []):
                    if not pixel or pixel.get("a", 0) < 160:
                        continue
                    item = dict(sample)
                    item.update(r=pixel["r"], g=pixel["g"], b=pixel["b"])
                    covered.append(item)
                if len(covered) < 8:
                    problems.append(
                        f"sprite covers only {len(covered)} ring-edge samples"
                    )
                else:
                    clip = _ring_clip(page, shape)
                    png = page.screenshot(clip=clip, scale="css", type="png")
                    painted = point_is_ring_ink(png, covered, clip)
                    by_edge = {}
                    for item in painted:
                        by_edge.setdefault(item["edge"], []).append(item)
                    parts = []
                    for name, items in by_edge.items():
                        hit = sum(1 for item in items if item["ring"])
                        parts.append(f"{name} {hit}/{len(items)}")
                        if len(items) >= 3 and hit < 3:
                            problems.append(
                                f"{name}: {hit}/{len(items)} ring pixels above the sprite"
                            )
                    print("TC-FE-FOCUS-RING-ABOVE-SPRITE " + ", ".join(parts))
        _select_cell(page, 0, 0)
        _blur_focus(page)
        page.wait_for_timeout(40)
        face = cell_top_face(page, 0, 0) or {}
        if not face.get("tips"):
            problems.append(f"selected line has no face ({face.get('error')})")
        else:
            clip = _paint_clip(page, face, margin=8)
            png = _shot(page, clip)
            _width, _height, rows = png_rgb(png)
            tips = face["tips"]
            order = ("N", "E", "S", "W")
            centre = (face["cx"], face["cy"])
            stations = []
            for index, name in enumerate(("NE", "SE", "SW", "NW")):
                start = tips[order[index]]
                end = tips[order[(index + 1) % 4]]
                dx = end["x"] - start["x"]
                dy = end["y"] - start["y"]
                length = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / length, dx / length
                mid_x = (start["x"] + end["x"]) / 2
                mid_y = (start["y"] + end["y"]) / 2
                if (mid_x + nx - centre[0]) ** 2 + (mid_y + ny - centre[1]) ** 2 < (
                    mid_x - nx - centre[0]
                ) ** 2 + (mid_y - ny - centre[1]) ** 2:
                    nx, ny = -nx, -ny
                for step_index in range(5):
                    t = 0.3 + step_index * 0.1
                    # The stroke is inset about 1.5px, not on the diamond edge.
                    stations.append({
                        "edge": name,
                        "x": start["x"] + dx * t - nx * 1.5,
                        "y": start["y"] + dy * t - ny * 1.5,
                    })
            opaque = page.evaluate(
                """([c, r, points]) => {
                  const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
                    const cs = getComputedStyle(el);
                    return parseInt(cs.getPropertyValue('--c'), 10) === c
                      && parseInt(cs.getPropertyValue('--r'), 10) === r;
                  });
                  const img = pad && pad.querySelector(':scope > .sprite');
                  if (!img || img.hidden) return {error: 'missing sprite'};
                  const w = img.naturalWidth || 0;
                  const h = img.naturalHeight || 0;
                  if (w < 2 || h < 2) return {error: 'sprite not loaded'};
                  const box = img.getBoundingClientRect();
                  const canvas = document.createElement('canvas');
                  canvas.width = w;
                  canvas.height = h;
                  const ctx = canvas.getContext('2d', {willReadFrequently: true});
                  try { ctx.drawImage(img, 0, 0, w, h); }
                  catch (err) { return {error: String(err)}; }
                  return points.map((point) => {
                    if (point.x < box.left || point.x > box.right || point.y < box.top || point.y > box.bottom) {
                      return 0;
                    }
                    const ix = Math.max(0, Math.min(w - 1, Math.round((point.x - box.left) / box.width * (w - 1))));
                    const iy = Math.max(0, Math.min(h - 1, Math.round((point.y - box.top) / box.height * (h - 1))));
                    try { return ctx.getImageData(ix, iy, 1, 1).data[3]; }
                    catch (err) { return 0; }
                  });
                }""",
                [0, 0, stations],
            )
            if not isinstance(opaque, list):
                problems.append(f"selected line sprite alpha {opaque}")
            else:
                line_bits = []
                by_edge = {}
                for station, alpha in zip(stations, opaque):
                    by_edge.setdefault(station["edge"], []).append((station, alpha or 0))
                for name, items in by_edge.items():
                    covered = [(station, alpha) for station, alpha in items if alpha >= 160]
                    hits = 0
                    for station, _alpha in covered:
                        ix = int(round(station["x"] - clip["x"]))
                        iy = int(round(station["y"] - clip["y"]))
                        # The stroke is about 3px. One CSS pixel off the
                        # centre still is the line, not a sub-pixel walk.
                        found = False
                        for oy in range(-1, 2):
                            for ox in range(-1, 2):
                                py = iy + oy
                                px = ix + ox
                                if not rows or py < 0 or px < 0 or py >= len(rows) or px >= len(rows[0]):
                                    continue
                                pixel = rows[py][px]
                                dist = (
                                    (pixel[0] - 0x7C) ** 2
                                    + (pixel[1] - 0x2D) ** 2
                                    + (pixel[2] - 0x12) ** 2
                                )
                                if dist <= 55 * 55:
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            hits += 1
                    line_bits.append(f"{name} {hits}/{len(covered)}")
                    if len(covered) >= 3 and hits < 3:
                        problems.append(
                            f"selected line {name}: {hits}/{len(covered)} "
                            "#7c2d12 where the sprite covers the stroke"
                        )
                print("TC-FE-FOCUS-RING-ABOVE-SPRITE line " + ", ".join(line_bits))
    assert not problems, "TC-FE-FOCUS-RING-ABOVE-SPRITE: " + " | ".join(problems)


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


def _pad_is_gold(page, cell_x, cell_y):
    return bool(page.evaluate(
        """([c, r]) => {
          const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
            const cs = getComputedStyle(el);
            return parseInt(cs.getPropertyValue('--c'), 10) === c
              && parseInt(cs.getPropertyValue('--r'), 10) === r;
          });
          return !!(pad && pad.classList.contains('is-empty-hot'));
        }""",
        [cell_x, cell_y],
    ))


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


def _gold_edges(page, face):
    """SE/SW edges whose outside neighbour is still a gold cell."""
    distance = max(14.0, (face.get("halfH") or 0) * 0.55)
    found = []
    for point in edge_outward_points(face, distance):
        if point["name"] not in ("SE", "SW"):
            continue
        live = cell_under_point(page, point["x"], point["y"])
        if not live:
            continue
        cell = (int(live["c"]), int(live["r"]))
        if cell == (face["c"], face["r"]):
            continue
        if _pad_is_gold(page, cell[0], cell[1]):
            found.append(point["name"])
    return found


@pytest.mark.case_id("TC-FE-SELECTED-NO-FILL")
def test_selected_no_fill(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-SELECTED-NO-FILL 選中格只畫一條在格子裡面的實線。

    中心和每條邊內 8px 要和未選中、未聚焦的底圖一致，中心不能是 #7c2d12。
    選中時「此格」徽章的區域除外。褐線寬 2–4px，外緣在格子外 0–1px
    （中線內縮 0.5–1.5px 用這條外緣判斷）。
    東南、西南若鄰格是金格，邊帶上的像素是 #7c2d12 不是 #d4a017。
    「此格」徽章要看得見。外緣用像素中心的帶符號距離，0–1.5px。
    1100×800、deviceScaleFactor 1 要量 (0,0)。視窗 1280×720、1100×800、390×844。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    problems = []
    summaries = []
    for width, height in ((1280, 720), (1100, 800), (390, 844)):
        _relogin(page, base_url)
        page.set_viewport_size({"width": width, "height": height})
        _enter_new_build_scene2(page)
        assert _pick_unbuilt(page, "工坊"), f"{width}x{height}: 工坊 missing"
        hot = _hot_cells(page)
        interior = [cell for cell in hot if not cell["edge"]]
        edge = [cell for cell in hot if cell["edge"]]
        chosen = []
        if interior:
            chosen.append((interior[0], "interior"))
        if len(interior) > 1:
            chosen.append((interior[1], "interior-b"))
        if edge:
            chosen.append((edge[0], "edge"))
        if width == 1100 and not any(
            cell["c"] == 0 and cell["r"] == 0 for cell, _role in chosen
        ):
            chosen.append(({"c": 0, "r": 0, "edge": True}, "corner-00"))
        if len(chosen) < 2:
            problems.append(f"{width}x{height}: not enough selectable cells")
            continue
        for cell, role in chosen:
            _scroll_cell_into_view(page, cell["c"], cell["r"])
            dismiss_selection(page)
            _blur_focus(page)
            _silence_toast(page)
            page.wait_for_timeout(200)
            _require_clean_paint(page, problems, f"{width}x{height} {role} baseline")
            face = cell_top_face(page, cell["c"], cell["r"]) or {}
            if face.get("error") or not face.get("tips"):
                problems.append(f"{width}x{height} {role} {face.get('error')}")
                continue
            clip = _paint_clip(page, face)
            before = _shot(page, clip)
            _select_cell(page, cell["c"], cell["r"])
            _blur_focus(page)
            _silence_toast(page)
            chosen_face = cell_top_face(page, cell["c"], cell["r"]) or {}
            if not chosen_face.get("chosen"):
                problems.append(
                    f"{width}x{height} {role} ({cell['c']},{cell['r']}) did not stay selected"
                )
                continue
            face["badge"] = chosen_face.get("badge")
            after = _shot(page, clip)
            report = selection_pixel_report(before, after, face, clip)
            brown_in = [item["name"] for item in report["interior"] if item["brown"]]
            drifted = [item["name"] for item in report["interior"] if not item["near"]]
            widths = []
            near = stroke_near_cell(after, face, clip)
            rays = stroke_outer_rays(after, face, clip)
            outers = []
            for name, edge_report in report["edges"].items():
                widths.append(f"{name}:{edge_report['width']}")
                # Boundary of the painted pixel along the normal, not its centre.
                outer = (rays.get(name) or {}).get("outer")
                if outer is None:
                    outer = (near.get(name) or {}).get("outer")
                outers.append(None if outer is None else round(outer, 2))
                if edge_report["width"] < 2 or edge_report["width"] > 4:
                    problems.append(
                        f"{width}x{height} {role} {name}: brown run "
                        f"{edge_report['width']}px, want 2–4"
                    )
                if outer is None or outer < 0 or outer > 1.5:
                    problems.append(
                        f"{width}x{height} {role} {name}: brown outer edge "
                        f"{outer}px, want 0–1.5"
                    )
            if brown_in:
                sample = next(item for item in report["interior"] if item["brown"])
                problems.append(
                    f"{width}x{height} {role}: interior {','.join(brown_in)} "
                    f"is #7c2d12 ({sample['after']})"
                )
            if drifted:
                sample = next(item for item in report["interior"] if not item["near"])
                problems.append(
                    f"{width}x{height} {role}: interior {','.join(drifted)} "
                    f"left the baseline ({sample['before']} → {sample['after']}, "
                    f"Δ{sample['dist']})"
                )
            badge = report["badge"]
            if badge.get("text") != "此格" or badge.get("cream", 0) < 8:
                problems.append(
                    f"{width}x{height} {role}: 「此格」 badge cream "
                    f"{badge.get('cream')} text {badge.get('text')!r}"
                )
            for name in _gold_edges(page, face):
                edge_report = report["edges"][name]
                if edge_report["brown"] < 4 or edge_report["gold"]:
                    problems.append(
                        f"{width}x{height} {role} {name}: "
                        f"{edge_report['brown']}/{edge_report['samples']} #7c2d12, "
                        f"{edge_report['gold']} look like #d4a017"
                    )
            centre = next(item for item in report["interior"] if item["name"] == "centre")
            summaries.append(
                f"{width}x{height} {role} ({cell['c']},{cell['r']}) "
                f"centre {centre['before']}→{centre['after']} "
                f"widths {','.join(widths)} outer {outers} "
                f"inset {[edge_report['inset'] for edge_report in report['edges'].values()]} "
                f"badge {badge.get('cream')}"
            )
    print("TC-FE-SELECTED-NO-FILL " + " || ".join(summaries))
    assert not problems, "TC-FE-SELECTED-NO-FILL: " + " | ".join(problems[:12])


@pytest.mark.case_id("TC-FE-FOCUS-RING-NO-FILL")
def test_focus_ring_no_fill(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-FOCUS-RING-NO-FILL 焦點環只畫虛線，不填滿格子。

    未選中只聚焦時，邊內 8px 的每一點都要和未選中、未聚焦的底圖一致，
    不排除徽章位置。選中時才排除徽章區域。中心不能是 #7c2d12。
    每條邊要看得到環色。內緣 2–4px 和褐線外緣 0–1px 是像素打磨，不在這條。
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
    print("TC-FE-FOCUS-RING-NO-FILL " + " || ".join(summaries))
    assert not problems, "TC-FE-FOCUS-RING-NO-FILL: " + " | ".join(problems[:12])


@pytest.mark.case_id("TC-FE-TAP-VILLAGE-HALFPX")
def test_tap_village_halfpx(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TAP-VILLAGE-HALFPX 村子下緣外面半像素不得打中格子。

    場景 1、捲動 0。y 是 #village 外框 bottom+0.5（1280 約 541.5，390 約 477.6）。
    那一列不得有反應。同一條案例裡，底邊往內 1.5px、落在看得見的格上的點，
    仍要選中那一格。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=800,
        buildings=[
            {"name": "商店", "level": 1, "stored": 0, "cell_x": 0, "cell_y": 0},
            {"name": "農場", "level": 1, "stored": 0, "cell_x": 4, "cell_y": 3},
        ],
    )
    _login(page, base_url)
    problems = []
    summaries = []
    for width, height in ((1280, 720), (390, 844)):
        _relogin(page, base_url)
        page.set_viewport_size({"width": width, "height": height})
        _restore_scene1(page)
        set_village_scroll(page, 0)
        if "場景 1" not in _scene_aria(page):
            problems.append(f"{width}x{height}: not scene 1 ({_scene_aria(page)!r})")
            continue
        box = village_box(page)
        if not box:
            problems.append(f"{width}x{height}: #village missing")
            continue
        y = box["bottom"] + 0.5
        print(
            f"VILLAGE-HALFPX {width}x{height} bottom {box['bottom']:.2f} y {y:.2f}",
            flush=True,
        )
        solids = open_solid_rects(page)
        reacted = []
        probed = 0
        x = box["left"] + 4
        while x < box["right"] - 4:
            if not solid_selector(solids, x, y):
                probed += 1
                reaction = _map_reaction(page, x, y)
                if reaction_happened(reaction):
                    if len(reacted) < 6:
                        reacted.append(
                            f"({x:.1f},{y:.1f}) cell {reaction['acted']} "
                            f"toast {reaction['toast']!r} sheet {reaction['sheet']}"
                        )
                    else:
                        reacted.append("more")
                if "場景 1" not in _scene_aria(page):
                    _restore_scene1(page)
                    set_village_scroll(page, 0)
            x += 8
        real = [item for item in reacted if item != "more"]
        summaries.append(
            f"{width}x{height} halfpx probed {probed} reactions {len(reacted)}"
        )
        if real:
            problems.append(
                f"{width}x{height} y={y:.2f}: " + " | ".join(real)
            )
        _enter_new_build_scene2(page)
        assert _pick_unbuilt(page, "工坊"), f"{width}x{height}: 工坊 missing"
        set_village_scroll(page, 0)
        box = village_box(page)
        if not box:
            problems.append(f"{width}x{height}: #village missing for the control")
            continue
        y_in = box["bottom"] - 1.5
        control = None
        tried = 0
        x = box["left"] + 8
        while x < box["right"] - 8:
            live = cell_under_point(page, x, y_in)
            if live and _pad_is_gold(page, int(live["c"]), int(live["r"])):
                if not solid_selector(open_solid_rects(page), x, y_in):
                    cell = (int(live["c"]), int(live["r"]))
                    tried += 1
                    reaction = _map_reaction(page, x, y_in)
                    if reaction["acted"] == cell and "場景 3" not in (reaction["scene"] or ""):
                        control = (x, y_in, cell)
                        break
            x += 6
        if not control:
            problems.append(
                f"{width}x{height}: no point at y={y_in:.2f} selected its cell "
                f"({tried} gold points tried)"
            )
        else:
            summaries.append(
                f"{width}x{height} control selects {control[2]} "
                f"at ({control[0]:.1f},{y_in:.1f})"
            )
    print("TC-FE-TAP-VILLAGE-HALFPX " + " || ".join(summaries))
    assert not problems, "TC-FE-TAP-VILLAGE-HALFPX: " + " | ".join(problems[:8])


_SERVER_FORMAL = "你已經興建了這種建築物。"
_RAW_MARKERS = ("field required", "[", "{", "detail")


def _toast_body(toast):
    if isinstance(toast, dict):
        return toast.get("text") or ""
    return toast or ""


def _toast_is_generic(text):
    return CANNOT_FIT_TOAST in (text or "")


def _raw_toast_problems(text):
    problems = []
    raw = text or ""
    lowered = raw.lower()
    for marker in _RAW_MARKERS:
        if marker.lower() in lowered or marker in raw:
            problems.append(f"toast contains {marker!r}")
    letters = re.sub(r"[^A-Za-z]+", "", raw)
    if letters and re.fullmatch(r"[ -~]+", raw.strip() or ""):
        problems.append(f"toast is an ASCII message {raw!r}")
    if not _toast_is_generic(raw):
        problems.append(f"toast {raw!r} is not {_SERVER_FORMAL and CANNOT_FIT_TOAST!r}")
    return problems


@pytest.mark.case_id("TC-FE-PLACE-SERVER-MSG")
def test_place_server_msg(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-PLACE-SERVER-MSG 確定放置要顯示伺服器的書面語，而不是改成放不下。

    場景 3 還開著時，另一個請求先把同一種建築建好。確定之後提示必須正好是
    伺服器那句「你已經興建了這種建築物。」。沒有可顯示的中文 detail 時
    （陣列、沒有 detail、英文 detail）仍是「這個位置放不下這座建築物。」，
    而且不得出現英文或 JSON。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        points=5000,
        items={"wood": 80, "brick": 80, "glass": 20, "gear": 40, "gem": 10},
        buildings=[],
    )
    workshop = _def_id_by_name(warehouse_db, "工坊")
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    assert _pick_unbuilt(page, "工坊"), "工坊 missing"
    _click_cell(page, 2, 2)
    advance = page.locator("#btnToScene3")
    assert advance.count() and advance.first.is_enabled(), "cannot open scene 3"
    advance.first.click()
    page.locator("#btnUxConfirm").wait_for(state="visible", timeout=8000)
    placed = page.evaluate(
        """async ({kidId, defId}) => {
          const res = await fetch('/api/kids/' + kidId + '/buildings', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({def_id: defId, cell_x: 4, cell_y: 4})
          });
          let data = {};
          try { data = await res.json(); } catch (err) { data = {}; }
          return {status: res.status, error: data.error || '', detail: data.detail || ''};
        }""",
        {"kidId": kid_id, "defId": workshop["id"]},
    )
    problems = []
    if placed.get("status") not in (200, 201):
        problems.append(f"background place HTTP {placed.get('status')} {placed.get('error')!r}")
    _silence_toast(page)
    page.locator("#btnUxConfirm").click()
    toast = _toast_body(_wait_toast(page))
    message = re.sub(r"^[❌\s]+", "", toast or "")
    if message != _SERVER_FORMAL:
        problems.append(
            f"toast {toast!r} is not the server message {_SERVER_FORMAL!r}"
        )
    if CANNOT_FIT_TOAST in (toast or ""):
        problems.append("toast rewrote the server message as 這個位置放不下這座建築物。")
    print(
        "TC-FE-PLACE-SERVER-MSG race "
        f"background {placed.get('status')} {placed.get('error')!r} toast {toast!r}"
    )

    guards = (
        (
            "detail-array",
            422,
            json.dumps({
                "detail": [{
                    "loc": ["body", "def_id"],
                    "msg": "field required",
                    "type": "value_error.missing",
                }]
            }),
        ),
        ("no-detail", 400, json.dumps({"error": "nope"})),
        ("english-detail", 400, json.dumps({"detail": "field required"})),
    )
    for label, status, body in guards:
        _relogin(page, base_url)
        page.set_viewport_size({"width": 1280, "height": 720})
        _reset_kid(
            warehouse_db,
            kid_id,
            points=5000,
            items={"wood": 80, "brick": 80, "gear": 40},
            buildings=[],
        )
        _enter_new_build_scene2(page)
        assert _pick_unbuilt(page, "健身室"), "健身室 missing"
        _click_cell(page, 2, 2)
        page.locator("#btnToScene3").click()
        page.locator("#btnUxConfirm").wait_for(state="visible", timeout=8000)
        _force_confirm_response(page, "new-build", status, body, "application/json")
        _silence_toast(page)
        page.locator("#btnUxConfirm").click()
        guard_toast = _toast_body(_wait_toast(page))
        page.unroute("**/api/kids/**")
        found = _raw_toast_problems(guard_toast)
        print(f"TC-FE-PLACE-SERVER-MSG guard {label}: {guard_toast!r}")
        if found:
            problems.append(f"guard {label}: " + " | ".join(found))
    assert not problems, "TC-FE-PLACE-SERVER-MSG: " + " | ".join(problems)


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


def _grid_corners(page):
    return page.evaluate(
        """() => {
          let maxC = -1, maxR = -1, n = 0;
          for (const pad of document.querySelectorAll('#townMap .pad')) {
            const cs = getComputedStyle(pad);
            const c = parseInt(cs.getPropertyValue('--c'), 10);
            const r = parseInt(cs.getPropertyValue('--r'), 10);
            if (!Number.isFinite(c) || !Number.isFinite(r)) continue;
            n += 1;
            if (c > maxC) maxC = c;
            if (r > maxR) maxR = r;
          }
          return {maxC, maxR, n};
        }"""
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


def _mark_cleared(page):
    """Brown pixels on the whole screen, and whether the mark layer is painted."""
    brown = count_stroke_pixels(_full_shot(page))
    layer = paint_layer_state(page) or {}
    mark = layer.get("mark") or {}
    return brown, bool(mark.get("gone"))


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


def _gap_problems(gaps, label):
    problems = []
    bits = []
    for name in ("NE", "SE", "SW", "NW"):
        edge = gaps.get(name) or {}
        bits.append(f"{name} {edge.get('min')} n={edge.get('samples')}")
        if edge.get("samples", 0) < 20 or edge.get("min") is None:
            problems.append(
                f"{label} {name}: {edge.get('samples')} samples, want ≥20"
            )
        elif edge["min"] < 2 or edge["min"] > 4:
            problems.append(
                f"{label} {name}: inner gap {edge['min']:.2f}px, want 2–4 screen px"
            )
    return problems, " ".join(bits)


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


@pytest.mark.case_id("TC-FE-MARK-CLEARED")
def test_mark_cleared(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-MARK-CLEARED 取消、回地圖、切到任務板之後，選中線要消失。

    全畫面 #7c2d12 為 0。畫選中線的元素（#chosenMarkPaint，或當時那個元素）
    計算樣式是 display:none，或者沒有盒子。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    problems = []
    _select_cell(page, 3, 3)
    _blur_focus(page)
    dismiss_selection(page)
    _silence_toast(page)
    page.wait_for_timeout(200)
    brown, gone = _mark_cleared(page)
    print(f"TC-FE-MARK-CLEARED cancel brown {brown} gone {gone}", flush=True)
    if brown or not gone:
        problems.append(f"after cancel: {brown} #7c2d12 px, mark layer gone={gone}")
    _restore_scene1(page)
    page.wait_for_timeout(200)
    brown, gone = _mark_cleared(page)
    print(f"TC-FE-MARK-CLEARED map brown {brown} gone {gone} scene {_scene_aria(page)}", flush=True)
    if "場景 1" not in _scene_aria(page):
        problems.append(f"return to map landed in {_scene_aria(page)!r}")
    if brown or not gone:
        problems.append(f"after returning to the map: {brown} #7c2d12 px, mark layer gone={gone}")
    _enter_new_build_scene2(page)
    _select_cell(page, 3, 3)
    page.locator('#ktFooter [data-kt-nav="tasks"]').click()
    page.locator("#tab-tasks.active").wait_for(state="visible", timeout=8000)
    page.wait_for_timeout(200)
    brown, gone = _mark_cleared(page)
    print(f"TC-FE-MARK-CLEARED tasks brown {brown} gone {gone}", flush=True)
    if brown or not gone:
        problems.append(f"on the task board: {brown} #7c2d12 px, mark layer gone={gone}")
    assert not problems, "TC-FE-MARK-CLEARED: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-MARK-KEPT-READYBAR")
def test_mark_kept_readybar(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-MARK-KEPT-READYBAR 場景 3 換一格之後，確定欄在等確認，選中線仍要包住新格。

    場景 3 的確認欄是 #uxPlaceBar（#readyBar 只在場景 2）。新格周圍 #7c2d12 要多於 0。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    assert _pick_unbuilt(page, "工坊"), "工坊 missing"
    _select_cell(page, 2, 2)
    page.locator("#btnToScene3").click()
    page.locator("#uxPlaceBar").wait_for(state="visible", timeout=8000)
    tap_cell_centre(page, 4, 3)
    page.wait_for_timeout(200)
    problems = []
    if "場景 3" not in _scene_aria(page):
        problems.append(f"not scene 3 ({_scene_aria(page)!r})")
    confirm = page.locator("#uxPlaceBar").is_visible() or page.locator("#readyBar").is_visible()
    if not confirm:
        problems.append("confirm bar is not visible")
    face = cell_top_face(page, 4, 3) or {}
    if face.get("error") or not face.get("tips"):
        problems.append(f"cell (4,3) {face.get('error')}")
    else:
        clip = _paint_clip(page, face, margin=16)
        near = stroke_near_cell(_shot(page, clip), face, clip)
        print(
            f"TC-FE-MARK-KEPT-READYBAR total {near.get('total')} "
            f"ux {page.locator('#uxPlaceBar').is_visible()} "
            f"ready {page.locator('#readyBar').is_visible()}",
            flush=True,
        )
        if near.get("total", 0) <= 0:
            problems.append(
                f"(4,3) has {near.get('total')} #7c2d12 px around it while the confirm bar is up"
            )
    assert not problems, "TC-FE-MARK-KEPT-READYBAR: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-MARK-RESTORE-AFTER-SHEET")
def test_mark_restore_after_sheet(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-MARK-RESTORE-AFTER-SHEET 選中一格，打開面板再關上，選中線要回到同一格。"""
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
    _select_cell(page, 3, 3)
    _open_palette(page)
    page.locator("#palette").get_by_role("button", name=re.compile(r"商店")).click()
    page.locator("#actionSheet").wait_for(state="visible", timeout=8000)
    _close_sheet(page)
    page.locator("#actionSheet").wait_for(state="hidden", timeout=8000)
    page.wait_for_timeout(150)
    face = cell_top_face(page, 3, 3) or {}
    problems = []
    if not face.get("chosen"):
        problems.append("(3,3) is not chosen after the sheet closes")
    if face.get("tips"):
        clip = _paint_clip(page, face, margin=16)
        near = stroke_near_cell(_shot(page, clip), face, clip)
        print(f"TC-FE-MARK-RESTORE-AFTER-SHEET {near}", flush=True)
        problems.extend(_wrap_problems(near, "(3,3)"))
    else:
        problems.append(f"cell face {face.get('error')}")
    assert not problems, "TC-FE-MARK-RESTORE-AFTER-SHEET: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-RING-CLEARED")
def test_ring_cleared(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-RING-CLEARED 失焦、換場景、切分頁之後，焦點環層在畫面上是 0 像素。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    problems = []

    def _check(label):
        page.wait_for_timeout(200)
        ring = ring_layer_pixels(page) or {}
        print(f"TC-FE-RING-CLEARED {label} {ring}", flush=True)
        if ring.get("pixels"):
            problems.append(
                f"{label}: ring layer {ring.get('pixels')} px "
                f"({ring.get('tag')} display {ring.get('display')})"
            )

    if not _focus_visible_cell(page, 3, 3):
        problems.append("cell did not take focus")
    _blur_focus(page)
    _check("after blur")
    if not _focus_visible_cell(page, 3, 3):
        problems.append("cell did not take focus again")
    _restore_scene1(page)
    _check("after scene change")
    if "場景 1" not in _scene_aria(page):
        problems.append(f"scene change landed in {_scene_aria(page)!r}")
    _enter_new_build_scene2(page)
    if not _focus_visible_cell(page, 3, 3):
        problems.append("cell did not take focus before the tab")
    page.locator('#ktFooter [data-kt-nav="tasks"]').click()
    page.locator("#tab-tasks.active").wait_for(state="visible", timeout=8000)
    _check("after tab switch")
    assert not problems, "TC-FE-RING-CLEARED: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-MARK-FOLLOWS-SCROLL")
def test_mark_follows_scroll(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-MARK-FOLLOWS-SCROLL 捲動 0 和 366 時，選中線仍包住同一格。

    外緣在活格子外 0–1.5px，這條不因確認欄裁切而放寬。裝置像素內緣
    2.0–4.0 和 22/24 站是像素打磨，不在這條。
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
    for scroll in (0, 366):
        moved = set_village_scroll(page, scroll)
        page.wait_for_timeout(80)
        face = cell_top_face(page, 3, 3) or {}
        if not face.get("tips"):
            problems.append(f"scroll {scroll}: {face.get('error')}")
            continue
        clip = _paint_clip(page, face, margin=20)
        near = stroke_near_cell(_shot(page, clip), face, clip)
        print(f"TC-FE-MARK-FOLLOWS-SCROLL {scroll} {moved} {near}", flush=True)
        problems.extend(_wrap_problems(near, f"scroll {scroll}"))
        _blur_focus(page)
    assert not problems, "TC-FE-MARK-FOLLOWS-SCROLL: " + " | ".join(problems)


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
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const box = el.getBoundingClientRect();
    return box.width > 1 && box.height > 1;
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


def _inset_clip(clip, pad):
    """Viewport clip shrunk by ``pad`` CSS px on every side."""
    return {
        "x": clip["x"] + pad,
        "y": clip["y"] + pad,
        "width": max(1, clip["width"] - 2 * pad),
        "height": max(1, clip["height"] - 2 * pad),
    }


def _strict_bar_ink(before, after, clip, label, problems):
    """Strict ring cream, #fffec5, or #7c2d12 inside the bar, inset 2px.

    Not a same-sentence pixel diff. Antialias that is not a strict match
    does not count.
    """
    ink = paint_overlay_count(before, after, clip, _inset_clip(clip, 2))
    print(f"TC-FE-PAINT-UNDER-UI {label} interior ink {ink}", flush=True)
    if ink is None:
        problems.append(f"{label}: bar screenshots differ in size")
    elif ink:
        problems.append(
            f"{label}: {ink} strict ring px inside the bar, inset 2px"
        )


def _paint_near_bar(page):
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
        print(f"TC-FE-PAINT-UNDER-UI near-bar {width}x{height} {cells}", flush=True)
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
                f"TC-FE-PAINT-UNDER-UI {select_label} sentence {sentence_on!r} "
                f"vs {sentence_off!r} mark-hidden {hidden}",
                flush=True,
            )
            if sentence_on != sentence_off:
                problems.append(
                    f"{select_label}: bar sentence {sentence_on!r} != {sentence_off!r}"
                )
            _strict_bar_ink(
                unmarked, marked, clip, select_label, problems
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
                f"TC-FE-PAINT-UNDER-UI {focus_label} sentence {sentence_focus!r} "
                f"vs {sentence_blur!r}",
                flush=True,
            )
            if sentence_focus != sentence_blur:
                problems.append(
                    f"{focus_label}: bar sentence {sentence_focus!r} != {sentence_blur!r}"
                )
            _strict_bar_ink(
                blurred, focused, clip, focus_label, problems
            )
            _blur_focus(page)
    return problems


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


_DEAD_ZONE_CSS_PX = 6.0


def _hug_problems(page, label, problems, expect):
    """Clip hole must stay within about 6 CSS px of the painted extent.

    ``expect`` is ``palette`` or ``cta``. A missing cover is itself a
    failure, so a hidden control cannot skip the check. The extent is the
    border box plus the live ``::before`` outset (0 when the pseudo does
    not stick out). Farther out is a dead zone. A ring box that meets the
    extent with no hole is not cut.
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
    print(f"TC-FE-PAINT-UNDER-UI hug {label} dpr {dpr} {'; '.join(brief)}", flush=True)
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
            css = worst / dpr
            tight_css = tight / dpr
            if css > _DEAD_ZONE_CSS_PX:
                zone = " dead zone" if css >= 40 else ""
                problems.append(
                    f"{label} {name}: hug cut {worst:.1f} device px "
                    f"({css:.1f} CSS px){zone}, want ≤{_DEAD_ZONE_CSS_PX:.0f} CSS px"
                )
            elif tight_css < -_DEAD_ZONE_CSS_PX:
                problems.append(
                    f"{label} {name}: clip is {abs(tight_css):.1f} CSS px inside "
                    f"the painted extent, want ≤{_DEAD_ZONE_CSS_PX:.0f}"
                )
        elif row.get("ringHits"):
            problems.append(
                f"{label} {name}: ring meets the painted extent and is not cut to it"
            )


def _painted_extent(page, selector):
    report = paint_cover_report(page) or {}
    for row in report.get("covers") or []:
        if row.get("selector") == selector:
            return row.get("extent")
    return surface_rect(page, selector)


def _ring_ink_pixel(pixel):
    """Cream or ring-brown, loose enough that a real dash counts.

    Strict cream (5*5) is reserved for paint that landed inside UI.
    """
    if not pixel:
        return False
    cream = (pixel[0] - 0xFF) ** 2 + (pixel[1] - 0xF8) ** 2 + (pixel[2] - 0xE7) ** 2
    brown = (pixel[0] - 0x6B) ** 2 + (pixel[1] - 0x4F) ** 2 + (pixel[2] - 0x2A) ** 2
    return cream <= 40 * 40 or brown <= 42 * 42


def _cover_pad_hit(x, y, covers, pad):
    for cover in covers:
        if (
            cover["left"] - pad <= x <= cover["right"] + pad
            and cover["top"] - pad <= y <= cover["bottom"] + pad
        ):
            return True
    return False


def _coarse_edge_ring(page, cell_x, cell_y, label, problems, require_all=False):
    """Uncovered part of each ring edge shows ring. Corner notches are skipped.

    Stations within 6 CSS px of a painted cover are the allowed dead pad,
    not a hole. This does not measure inner-gap or device-pixel continuity.
    """
    face = cell_top_face(page, cell_x, cell_y) or {}
    if not face.get("tips"):
        problems.append(f"{label}: {face.get('error') or 'no face'}")
        return
    clip = _paint_clip(page, face, margin=24)
    if not _focus_visible_cell(page, cell_x, cell_y):
        problems.append(f"{label}: cell did not focus")
        return
    page.wait_for_timeout(40)
    _width, _height, rows = png_rgb(_shot(page, clip))
    covers = []
    for row in (paint_cover_report(page) or {}).get("covers") or []:
        extent = row.get("extent") or {}
        if extent.get("right", 0) - extent.get("left", 0) > 2:
            covers.append(extent)
    tips = face["tips"]
    order = ("N", "E", "S", "W")
    names = ("NE", "SE", "SW", "NW")
    centre = (face["cx"], face["cy"])
    bits = []
    for index, name in enumerate(names):
        start = tips[order[index]]
        end = tips[order[(index + 1) % 4]]
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        mid_x = (start["x"] + end["x"]) / 2
        mid_y = (start["y"] + end["y"]) / 2
        if (mid_x + nx - centre[0]) ** 2 + (mid_y + ny - centre[1]) ** 2 < (
            mid_x - nx - centre[0]
        ) ** 2 + (mid_y - ny - centre[1]) ** 2:
            nx, ny = -nx, -ny
        clear = max(8.0, length * 0.12)
        span = length - 2 * clear
        # Corner notches are allowed. A 390 edge is about 25px, so an 8px
        # notch at each end still leaves a middle. Only an edge with no
        # middle past the notch is skipped. The old 12px station floor is
        # a polish skip, not this check.
        if span < 4:
            bits.append(f"{name} notch {length:.0f}")
            if require_all:
                problems.append(
                    f"{label} {name}: no middle past the corner notch "
                    f"(edge {length:.0f}px)"
                )
            continue
        hits = 0
        seen = 0
        step = 4.0
        along = clear
        while along <= length - clear + 0.1:
            t = along / length
            ox = start["x"] + dx * t
            oy = start["y"] + dy * t
            probe_x = ox + nx * 3
            probe_y = oy + ny * 3
            along += step
            if _cover_pad_hit(probe_x, probe_y, covers, _DEAD_ZONE_CSS_PX):
                continue
            seen += 1
            found = False
            for dist in (2.0, 3.0, 4.0):
                x = ox + nx * dist
                y = oy + ny * dist
                ix = int(round(x - clip["x"]))
                iy = int(round(y - clip["y"]))
                if not rows or iy < 0 or ix < 0 or iy >= len(rows) or ix >= len(rows[0]):
                    continue
                pixel = rows[iy][ix]
                if _ring_ink_pixel(pixel):
                    found = True
                    break
            if found:
                hits += 1
        bits.append(f"{name} {hits}/{seen}")
        if seen == 0 and require_all:
            problems.append(f"{label} {name}: no uncovered station on the edge")
        elif seen and (require_all or seen >= 3) and hits * 5 < seen * 4:
            problems.append(
                f"{label} {name}: ring on {hits}/{seen} uncovered stations "
                "(corner notches and the 6px cover pad are skipped)"
            )
    print(f"TC-FE-PAINT-UNDER-UI edge {label} ({cell_x},{cell_y}) {' '.join(bits)}", flush=True)
    _blur_focus(page)


def _cell_near_palette(page):
    """A free cell whose diamond sits beside the open palette."""
    return page.evaluate(
        """() => {
          const pal = document.getElementById('palette');
          if (!pal) return null;
          const box = pal.getBoundingClientRect();
          const cs = getComputedStyle(pal);
          if (cs.display === 'none' || box.width < 2) return null;
          let best = null;
          for (const pad of document.querySelectorAll('#townMap .pad')) {
            const style = getComputedStyle(pad);
            const c = parseInt(style.getPropertyValue('--c'), 10);
            const r = parseInt(style.getPropertyValue('--r'), 10);
            const slab = pad.querySelector(':scope > .slab');
            if (!slab) continue;
            const face = slab.getBoundingClientRect();
            if (face.width < 2) continue;
            const gap = face.left - box.right;
            if (gap < -20 || gap > 80) continue;
            if (!best || gap < best.gap) best = {c, r, gap};
          }
          return best;
        }"""
    )


def _dead_zone_and_edges(page, scale_label):
    """Palette hole ≤6 CSS px, and ring still shows on the uncovered edge."""
    problems = []
    viewports = ((1280, 720), (1100, 800), (390, 844))
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
        label = f"{scale_label} {width}x{height}"
        near = _cell_near_palette(page) or {}
        cell = (near.get("c"), near.get("r"))
        if cell[0] is None:
            cell = (3, 3)
        if not _focus_visible_cell(page, cell[0], cell[1]):
            problems.append(f"{label}: cell did not focus")
            continue
        page.wait_for_timeout(40)
        _hug_problems(page, label, problems, "palette")
        _blur_focus(page)
        _coarse_edge_ring(page, cell[0], cell[1], label + " palette", problems)
        for item in _cells_near_bar(page, width)[:1]:
            _coarse_edge_ring(
                page, item["c"], item["r"], f"{label} bar", problems
            )
    return problems


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


def _scene1_cta(page, problems):
    """Scene 1 build button is a cover: no ring paint in its rect, and the guard."""
    page.set_viewport_size({"width": 1280, "height": 720})
    page.wait_for_timeout(80)
    _restore_scene1(page)
    page.wait_for_timeout(80)
    if "場景 1" not in (_scene_aria(page) or ""):
        problems.append(f"scene1 cta: landed in {_scene_aria(page)!r}")
        return
    placed = _place_cell_over_cta(page) or {}
    print(f"TC-FE-PAINT-UNDER-UI scene1 cta place {placed}", flush=True)
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
    _hug_problems(page, "scene1 cta", problems, "cta")
    after = _shot(page, clip)
    guard = _inset_clip(clip, 2)
    ink = paint_overlay_count(before, after, clip, guard)
    print(f"TC-FE-PAINT-UNDER-UI scene1 cta interior ink {ink}", flush=True)
    if ink is None:
        problems.append("scene1 cta: screenshots differ in size")
    elif ink:
        problems.append(
            f"scene1 cta: {ink} strict ring px inside .cta, inset 2px"
        )
    _blur_focus(page)


def _guard_sweep(page, problems):
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
    _scene1_cta(page, problems)
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


@pytest.mark.case_id("TC-FE-PAINT-UNDER-UI")
def test_paint_under_ui(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-PAINT-UNDER-UI 環和選中線不得畫進介面，裁切洞不得留下死區。

    清單、確認欄、抽屜、銀行面板、場景 1 的 `.cta`，向內縮 2px 的內部
    不得有嚴格的環色 `#fff8e7`、代替色 `#fffec5`，或選中線 `#7c2d12`。
    不要求整塊像素差是 0，也不量圓角抗鋸齒。
    裁切洞離畫出來的外緣（border box 加當時 `::before` 的伸出）不得超過
    約 6 CSS px。調色盤外 48 CSS px 的洞要紅。環壓在外緣上卻沒有洞，是沒裁。
    挨著調色盤或確認欄的格子，沒被蓋住的邊要看得到環。尖角開口可以空。
    離外緣 6 CSS px 以內的站略過。不量內緣 2–4，也不量 1 個裝置像素的洞。
    欄、調色盤、`.cta`、面板和環層不得用補色、text-shadow、filter 或
    translateZ 把漆蓋掉。欄上句子的 text-shadow 仍是 none。
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
                print(f"TC-FE-PAINT-UNDER-UI scroll {scroll} {kind} {name} offscreen", flush=True)
                continue
            after = _shot(page, clip)
            diff = changed_pixel_count(before[name], after)
            brown = count_stroke_pixels(after)
            print(
                f"TC-FE-PAINT-UNDER-UI scroll {scroll} {kind} {name} diff {diff} brown {brown}",
                flush=True,
            )
            if diff is None:
                problems.append(f"scroll {scroll} {kind} {name}: screenshot size changed")
            else:
                # Interior only. Antialias on the painted edge is outside
                # the 2px inset and is not a strict cream match.
                guard_clip = _inset_clip(clip, 2)
                guard_diff = paint_overlay_count(before[name], after, clip, guard_clip)
                if guard_diff:
                    problems.append(
                        f"guard {name} scroll {scroll} {kind}: {guard_diff} "
                        "strict ring px inset 2px"
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
                ink = paint_overlay_count(
                    before_sheet, after_sheet, sheet_clip, _inset_clip(sheet_clip, 2)
                )
                ring = ring_layer_pixels(page) or {}
                print(
                    f"TC-FE-PAINT-UNDER-UI bank ink {ink} ring {ring.get('pixels')}",
                    flush=True,
                )
                if ink:
                    problems.append(
                        f"bank sheet: {ink} strict ring px inset 2px "
                        f"(ring layer {ring.get('pixels')} px)"
                    )
    problems.extend(_paint_near_bar(page))
    problems.extend(_dead_zone_and_edges(page, "dsf1"))
    _guard_sweep(page, problems)
    assert not problems, "TC-FE-PAINT-UNDER-UI: " + " | ".join(problems[:12])


def _place_focus_ring_source():
    """Body of placeFocusRing in the product script, or the whole file."""
    path = os.path.join(REPO, "town-four-scene.js")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(
        r"function placeFocusRing\(\)\s*\{",
        text,
    )
    if not match:
        return text, False
    start = match.end()
    depth = 1
    index = start
    while index < len(text) and depth:
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        index += 1
    return text[start:index], True


@pytest.mark.case_id("TC-FE-RING-SAMPLER")
def test_ring_sampler_not_mirrored():
    """TC-FE-RING-SAMPLER 產品不得照著測試的 24 站幾何去挖環。

    placeFocusRing 不得用 samples = 24 建 blocked 站圖，也不得用
    (s + 0.5) / samples 對上站心再 hold 住不畫。沒有既有案例把內縮
    鎖成字面 0.45，這條不檢查那個數字。
    """
    body, found = _place_focus_ring_source()
    problems = []
    if not found:
        problems.append("town-four-scene.js has no function placeFocusRing")
    if re.search(r"samples\s*=\s*24", body) and re.search(r"\bblocked\b", body):
        problems.append(
            "placeFocusRing builds a samples=24 blocked map "
            "(the test sampler in ring_device_gaps)"
        )
    if re.search(r"\(\s*s\s*\+\s*0\.5\s*\)\s*/\s*samples", body):
        problems.append(
            "placeFocusRing walks stations with (s + 0.5) / samples"
        )
    if re.search(r"hold\s*=\s*blocked\b", body):
        problems.append("placeFocusRing holds paint off the blocked sampler pixels")
    assert not problems, "TC-FE-RING-SAMPLER: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-NATIVE-FOCUS")
def test_native_focus(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-NATIVE-FOCUS focus 和 blur 必須仍是瀏覽器原生方法。

    產品腳本不得指派 HTMLElement.prototype.focus。
    """
    _login(page, base_url)
    native = page.evaluate(
        """() => ({
          focus: HTMLElement.prototype.focus.toString(),
          blur: HTMLElement.prototype.blur.toString()
        })"""
    )
    problems = []
    if "[native code]" not in (native.get("focus") or ""):
        problems.append(f"HTMLElement.prototype.focus is {native.get('focus')!r}")
    if "[native code]" not in (native.get("blur") or ""):
        problems.append(f"HTMLElement.prototype.blur is {native.get('blur')!r}")
    assign = re.compile(r"HTMLElement\s*\.\s*prototype\s*\.\s*focus\s*=")
    for name in ("town-four-scene.js", "audio.js", "service-worker.js", "check_js.js"):
        path = os.path.join(REPO, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                if assign.search(line):
                    problems.append(f"{name}:{lineno} assigns HTMLElement.prototype.focus")
    print(f"TC-FE-NATIVE-FOCUS focus {native.get('focus')!r}", flush=True)
    assert not problems, "TC-FE-NATIVE-FOCUS: " + " | ".join(problems)


@pytest.mark.case_id("TC-FE-RING-EDGE")
def test_ring_edge(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-RING-EDGE 角落格的焦點環不得被村子裁掉還留在看得見的地圖裡。

    格子是 8×8 時角落是 (0,0)、(7,0)、(0,7)、(7,7)。看得見的地圖是 #village
    外框和視窗的交集，實心介面底下的點不算。裁掉的部分必須整段落在這塊外面。
    """
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(warehouse_db, kid_id, points=800, buildings=[])
    _login(page, base_url)
    page.set_viewport_size({"width": 1280, "height": 720})
    _enter_new_build_scene2(page)
    corners = _grid_corners(page) or {}
    max_c = corners.get("maxC")
    max_r = corners.get("maxR")
    problems = []
    if max_c != 7 or max_r != 7:
        problems.append(f"grid corners are (0,0)–({max_c},{max_r}), not 8×8")
    cells = ((0, 0), (max_c, 0), (0, max_r), (max_c, max_r))
    print(f"TC-FE-RING-EDGE grid {corners}", flush=True)
    for cell in cells:
        if cell[0] is None or cell[1] is None or cell[0] < 0:
            problems.append(f"missing corner {cell}")
            continue
        _scroll_cell_into_view(page, cell[0], cell[1])
        _blur_focus(page)
        page.wait_for_timeout(150)
        face = cell_top_face(page, cell[0], cell[1]) or {}
        visible = village_box(page)
        if not face.get("tips") or not visible:
            problems.append(f"{cell}: face {face.get('error')} village {visible}")
            continue
        view = page.viewport_size
        visible = {
            "left": max(visible["left"], 0),
            "top": max(visible["top"], 0),
            "right": min(visible["right"], view["width"]),
            "bottom": min(visible["bottom"], view["height"]),
        }
        clip = _paint_clip(page, face, margin=28)
        before = _shot(page, clip)
        if not _focus_visible_cell(page, cell[0], cell[1]):
            problems.append(f"{cell}: did not focus")
            continue
        page.wait_for_timeout(40)
        report = ring_edge_report(
            before, _shot(page, clip), face, visible, clip, open_solid_rects(page)
        )
        print(f"TC-FE-RING-EDGE {cell} {report}", flush=True)
        if report.get("inside_missing"):
            problems.append(
                f"{cell}: {report['inside_missing']} ring samples missing inside the visible map "
                f"({report.get('inside_hit')} hit, {report.get('outside_missing')} missing outside, "
                f"{report.get('details')})"
            )
    assert not problems, "TC-FE-RING-EDGE: " + " | ".join(problems)


