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
    init_empty_db,
    insert_building,
    insert_kid,
    inventory_map,
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


def _login(page, base_url):
    page.goto(f"{base_url}/kids/")
    page.locator("#loginUsername").fill(KID_USERNAME)
    page.locator("#loginPassword").fill(TEST_KID_PIN)
    page.get_by_role("button", name="🚪 登入").click()
    page.locator("#app").wait_for(state="visible", timeout=8000)
    page.locator("#village .cell-btn").first.wait_for(state="attached", timeout=8000)


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
    page.reload()
    page.locator("#app").wait_for(state="visible", timeout=8000)
    try:
        page.locator("#loginScreen").wait_for(state="hidden", timeout=8000)
    except Exception as exc:
        raise AssertionError(
            "TC-FE-WAREHOUSE-UNSTORE: after reload, #loginScreen must be hidden "
            "so the town and #ktFooter are visible. The footer pixel check compares "
            "the town footer, not the login wall. " + str(exc)
        ) from exc
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
