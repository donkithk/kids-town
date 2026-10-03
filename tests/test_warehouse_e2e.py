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


def _acted_cell(reaction):
    preview = [tuple(item) for item in reaction.get("preview") or []]
    chosen = [tuple(item) for item in reaction.get("chosen") or []]
    if len(preview) == 1:
        return preview[0]
    if len(preview) > 1:
        return preview
    if len(chosen) == 1:
        return chosen[0]
    if chosen:
        return chosen
    return None


def _reaction_blame(cell, kind, reaction, unstore):
    """Return (bucket, detail). bucket is neighbor, reaction, or None."""
    acted = _acted_cell(reaction)
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
            return "reaction", f"selected {reaction.get('chosen')} toast {toast!r}"
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
    midpoint. The expected reaction is the rendered state of the cell that
    contains the point: gold selects it, a building footprint toasts
    已經有建築物, and any other empty cell toasts 放不下. Points that
    elementFromPoint puts on the open palette are left out of the denominator
    and must not select a cell.
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
        neighbor = reaction = panel_hits = chrome_skipped = exposed = geometry = 0
        examples = []
        panel_examples = []
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
                    # Palette click-through is a point elementFromPoint puts on
                    # the panel. A bbox corner outside the rounded panel is an
                    # exposed map point, not a panel point.
                    if cover.get("kind") == "panel":
                        dismiss_selection(page)
                        tap_point(page, point["x"], point["y"])
                        hit = read_reaction(page)
                        acted = _acted_cell(hit)
                        if acted is not None or "場景 3" in (hit.get("scene") or ""):
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
            "examples": examples,
            "panel_examples": panel_examples,
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
            panel_points = 576 - counts["exposed"] - counts["chrome"] - counts["geometry"]
            correct = counts["exposed"] - counts["neighbor"] - counts["reaction"]
            summary = (
                f"{mode} {width}x{height}: {correct}/{counts['exposed']} exposed, "
                f"panel-excluded {panel_points}, chrome-excluded {counts['chrome']}, "
                f"neighbor-mis {counts['neighbor']}, reaction-mis {counts['reaction']}, "
                f"panel-selections {counts['panel']}, geometry {counts['geometry']}"
            )
            summaries.append(summary)
            if panel_points + counts["exposed"] + counts["chrome"] + counts["geometry"] != 576:
                problems.append(f"{summary} did not account for 576 points")
            if counts["neighbor"] or counts["reaction"]:
                problems.append(summary + " | " + " | ".join(counts["examples"]))
            if counts["panel"]:
                problems.append(
                    summary + " panel ate a cell: " + " | ".join(counts["panel_examples"])
                )
            if mode == "picked" and panel_points == 0:
                problems.append(f"{mode} {width}x{height}: open palette covered no sample points")
            if mode == "bare" and panel_points:
                problems.append(
                    f"{mode} {width}x{height}: palette was closed but excluded {panel_points} points"
                )

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


def _chosen_cells(reaction):
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
            chosen = _chosen_cells(read_reaction(page))
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
    chosen = _chosen_cells(reaction)
    if chosen:
        try:
            press_cell(page, chosen[0][0], chosen[0][1], "Enter")
        except AssertionError:
            pass
        _silence_toast(page)
        reaction = read_reaction(page)
        chosen = _chosen_cells(reaction)
    if chosen and "場景 3" not in (reaction.get("scene") or ""):
        if _shift_selection_to_reachable_gold(page):
            dismiss_selection(page)
            _silence_toast(page)
            reaction = read_reaction(page)
            chosen = _chosen_cells(reaction)
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


@pytest.mark.case_id("TC-FE-TAP-BAR-NOTHROUGH")
def test_tap_bar_nothrough(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-TAP-BAR-NOTHROUGH 實心介面要吃掉點擊，格子不能被選中。

    動作列、清單面板、頂部 HUD、頁尾，以及打開的面板，背景格點的
    elementFromPoint 必須落在該介面，而且點下去不得選中格子。
    info／成功提示和放置特效是 pointer-events:none。提示還顯示時，
    壓在提示底下的金色格仍要用菱形中心點中。
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
            if _acted_cell(hit) is not None or "場景 3" in (hit.get("scene") or ""):
                selected += 1
                if len(examples) < 6:
                    examples.append(
                        f"tap ({point['x']:.0f},{point['y']:.0f}) selected {_acted_cell(hit)}"
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
    toast_box = _surface_box(page, "#toast")
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
    # 1280×720 puts the fixed bottom toast over gold (4,5)'s diamond centre.
    # The cell has to be in the rendered gold set; a non-gold cell must toast
    # instead of selecting, so it cannot be the overlap target.
    gold = (4, 5)
    rendered_gold = set(_mark_gold_cells(page))
    if gold not in rendered_gold:
        problems.append(
            f"{gold} is not in the rendered gold set; the toast-overlap tap "
            "only applies to a gold cell"
        )
    centre = cell_points(page, gold[0], gold[1])["points"]["centre"]
    covers = bool(toast_box) and point_in_rect(centre, toast_box)
    if not covers:
        problems.append(
            f"toast rect {toast_box} does not cover gold {gold} diamond centre "
            f"({centre['x']:.0f},{centre['y']:.0f}) text {toast_state.get('text')!r}"
        )
        summaries.append("toast-gold: (4,5) not covered")
    else:
        tap_point(page, centre["x"], centre["y"])
        hit = read_reaction(page)
        acted = _acted_cell(hit)
        ok = acted == gold and "場景 3" not in (hit.get("scene") or "")
        summaries.append(f"toast-gold: {gold} covered -> {acted}")
        if not ok:
            problems.append(
                f"gold {gold} under the visible toast was not selected (got {acted}, "
                f"toast {hit.get('toast')!r})"
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


def _toast_pair_problems(page, first, second, expected_first, expected_second, same_text):
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
    page.wait_for_timeout(420)
    before2 = _now_ms(page)
    tap_point(page, point_b["x"], point_b["y"])
    after2 = _now_ms(page)
    page.wait_for_timeout(3100)
    payload = page.evaluate(
        """() => {
          const probe = window.__toastProbe;
          if (!probe) return null;
          probe.stop();
          return { samples: probe.samples, anims: probe.anims };
        }"""
    )
    label = "same" if same_text else "different"
    if not payload:
        return [f"{label}: probe did not start"]
    samples = payload["samples"]
    anims = payload["anims"]
    problems = []
    gap = before2 - after1
    if gap < 280 or gap > 700:
        problems.append(f"{label}: taps were {gap:.0f}ms apart, want about 300-500")
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
        opaque = [item for item in samples if item["t"] >= after1 and item.get("opacity", 0) >= 0.9]
        if not opaque:
            problems.append(f"{label}: opacity never reached 0.9")
        else:
            rose = opaque[0]["t"]
            dipped = [
                item for item in samples
                if rose <= item["t"] <= before2 and item.get("opacity", 0) < 0.9
            ]
            if dipped:
                problems.append(
                    f"{label}: opacity dipped to {dipped[0].get('opacity'):.2f} between taps"
                )
            replay_dip = [
                item for item in samples
                if after2 <= item["t"] <= after2 + 350 and item.get("opacity", 0) < 0.9
            ]
            if replay_dip:
                problems.append(
                    f"{label}: opacity dipped to {replay_dip[0].get('opacity'):.2f} "
                    "just after the second tap"
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
    """TC-FE-TOAST-TIMER-RESET 連續兩個提示要從第二下重新計時。

    兩下真實點擊大約相隔 420ms。用 rAF 抽 #toast 的 display、opacity、
    文字和節點，並聽 animationstart。同一句（放不下點兩次）不得重播
    進場動畫，而且要維持到第二下之後至少 1.9 秒、約 2.8 秒前消失。
    換句（放不下然後已經有）要在約 150ms 內改文字，計時同樣從第二下算。
    同一條裡各跑 3 次。
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
        for same, second, expected_second in (
            (True, unfit, CANNOT_FIT_TOAST),
            (False, occupied, OCCUPIED_TOAST),
        ):
            found = _toast_pair_problems(
                page, unfit, second, CANNOT_FIT_TOAST, expected_second, same
            )
            problems.extend(f"trial {trial}: {item}" for item in found)
    print(
        "TC-FE-TOAST-TIMER-RESET "
        + (f"{len(problems)} problems" if problems else "same 3/3, different 3/3")
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
