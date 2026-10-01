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
PRICE_RE = re.compile(r"💰|升級要|確定先至扣資源|\d+\s*(?:金幣|木材|磚|玻璃|齒輪|寶石)")


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
        "#btnToScene3 「去擺位置」 when that step is shown, then Scene 3 ghost "
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
FORMAL_STORED_HINT = "「圖書館」在存倉中，可直接放回，不扣除資源。"
UNSTORE_SCENE2_HINT = "請點選空地，放回「圖書館」。不扣除金幣和材料。"
IDLE_SCENE2_HINT = "點金色空地，或者打開清單揀一座未起嘅屋。"
GYM_PICKED_HINT = "已揀「健身室」同呢格空地。"
SCENE3_CHARGE_HINT = "確定先至扣資源。取消唔會扣。"
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
    legal = _legal_origins(placed)
    gold = _gold_cells(page)
    problems = []
    if gold != legal:
        extra = sorted(set(gold) - set(legal))
        missing = sorted(set(legal) - set(gold))
        problems.append(
            f"gold cells != legal origins. gold={len(gold)} legal={len(legal)} "
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
    if IDLE_SCENE2_HINT in visible or "已揀「圖書館」同呢格空地。" in visible:
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
    idle = _hint(page)
    assert idle["ready"] == IDLE_SCENE2_HINT, idle
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
    assert "未起" in gym_label and "已起" not in gym_label, gym_label
    gym_btn.first.click()
    picked = _hint(page)
    assert picked["ready"] == GYM_PICKED_HINT, picked
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
    confirm_hint = _hint(page)
    assert confirm_hint["place"] == SCENE3_CHARGE_HINT, confirm_hint
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


@pytest.mark.case_id("TC-FE-WAREHOUSE-COPY-FORMAL")
def test_formal_placement_copy(page, base_url, warehouse_db, warehouse_ids):
    """TC-FE-WAREHOUSE-COPY-FORMAL 放置文案改為書面語。"""
    kid_id = warehouse_ids["kid_id"]
    _reset_kid(
        warehouse_db,
        kid_id,
        buildings=[{"name": BUILDING_NAME, "level": 2, "stored": 1, "cell_x": 20, "cell_y": 12}],
    )
    _login(page, base_url)
    _enter_new_build_scene2(page)
    problems = []
    scene2 = _hint(page)
    visible = _visible_text(page)
    if scene2["back"].strip() != "返回地圖":
        problems.append(f"#btnUxBack is {scene2['back'].strip()!r}, expected 返回地圖")
    if "返去睇地圖" in visible:
        problems.append("visible DOM still contains 返去睇地圖")
    if scene2["go"].strip() != "選擇位置":
        problems.append(f"#btnToScene3 is {scene2['go'].strip()!r}, expected 選擇位置")
    if "去擺位置" in visible:
        problems.append("visible DOM still contains 去擺位置")

    gold = [cell for cell in _gold_cells(page) if cell[0] <= 6 and cell[1] <= 6]
    assert gold, "COPY-FORMAL: new-build Scene 2 has no cell with index <= 6"
    cell_x, cell_y = gold[0]
    _click_cell(page, cell_x, cell_y)
    labels = _aria_labels(page)
    expected_label = f"第 {cell_x + 1} 欄第 {cell_y + 1} 行，已選此格"
    selected = [label for label in labels if label.startswith(f"第 {cell_x + 1} 欄第 {cell_y + 1} 行")]
    if expected_label not in selected:
        problems.append(
            f"selected aria-label {selected!r}, expected {expected_label!r} "
            "(coordinate prefix plus 已選此格)"
        )
    stale = [label for label in labels if "已揀呢格" in label]
    if stale:
        problems.append(f"aria-label still contains 已揀呢格: {stale}")

    page.locator("#listLauncher").click()
    page.locator("#palette").wait_for(state="visible", timeout=8000)
    library = page.locator("#palette").get_by_role("button", name=re.compile(r"圖書館"))
    assert library.count() > 0, "missing 圖書館 in the building list"
    library.first.click()
    page.wait_for_timeout(200)
    after = _hint(page)
    hint_text = after["ready"] if after["readyOn"] else after["place"]
    if hint_text != FORMAL_STORED_HINT:
        problems.append(
            f"stored-copy hint {hint_text!r}, expected {FORMAL_STORED_HINT!r}. "
            f"readyOn={after['readyOn']} ready={after['ready']!r} "
            f"placeOn={after['placeOn']} place={after['place']!r} scene={after['scene']!r}"
        )
    visible_after = _visible_text(page)
    for bit in COLLOQUIAL_BITS:
        if bit in visible_after or bit in hint_text:
            problems.append(f"colloquial {bit} still visible")
    if re.search(r"\d|💰|金幣", hint_text or ""):
        problems.append(f"stored-copy hint contains a price or 金幣: {hint_text!r}")

    opened = _open_takeout_scene2(page)
    if opened:
        problems.append(
            "unstore Scene 2 was not reached, so the back button was checked on new-build Scene 2. "
            + opened
        )
    else:
        unstore = _hint(page)
        unstore_visible = _visible_text(page)
        if "場景 2" not in unstore["scene"]:
            problems.append(f"取出 did not stay on Scene 2. {unstore}")
        if unstore["back"].strip() != "返回地圖":
            problems.append(f"unstore #btnUxBack is {unstore['back'].strip()!r}")
        if "返去睇地圖" in unstore_visible:
            problems.append("unstore Scene 2 visible DOM contains 返去睇地圖")
        if unstore["go"].strip() != "選擇位置":
            problems.append(f"unstore #btnToScene3 is {unstore['go'].strip()!r}")
        if "去擺位置" in unstore_visible:
            problems.append("unstore Scene 2 visible DOM contains 去擺位置")
    assert not problems, "TC-FE-WAREHOUSE-COPY-FORMAL: " + " | ".join(problems)
