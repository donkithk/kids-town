"""Locked A–C art preview. Empty DB only. Does not open kids_town.db for writes.

TC-ART-ABC-01..04 are file and source contracts.
TC-FE-ART-ABC-01..03 drive /kids/ in Chromium.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import socket
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.factories import (  # noqa: E402
    TEST_KID_PIN,
    init_empty_db,
    insert_kid,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(REPO, "assets", "art-locked-2026-11-04")
PROD_DB = os.path.join(REPO, "kids_town.db")
PROD_SHA256 = "c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb"

LOCKED_SHA256 = {
    "ui-town-wood-frame.jpg": "a5c8cee063d25580469f4309465ce3c02bbceced9bfcfb306826f315611b1fa2",
    "bg-town-plaza.jpg": "57835c6a555e260d6ed688968866087c420ecbf83767413bf8a2e0f5fd29a388",
    "building-adventure-guild.jpg": "f42e42122f8539b85db1f605939e96375d7e59619053f97af79c6b5dafc410e0",
}

KID_USERNAME = "test_art_kid"
KID_NAME = "Art Kid"


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _derive():
    path = os.path.join(REPO, "scripts", "derive_art_abc.py")
    spec = importlib.util.spec_from_file_location("derive_art_abc", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rgba(path):
    from PIL import Image

    return Image.open(path).convert("RGBA")


def _dist(color, ref):
    return sum((int(a) - int(b)) ** 2 for a, b in zip(color, ref)) ** 0.5


def _prod_untouched():
    assert os.path.isfile(PROD_DB)
    assert _sha256(PROD_DB) == PROD_SHA256


@pytest.mark.case_id("TC-ART-ABC-01")
def test_locked_originals_and_cutout_alpha():
    """TC-ART-ABC-01 鎖定 JPEG 雜湊；木框中空、公會四角透明且沒有奶油底。"""
    _prod_untouched()
    for name, expected in LOCKED_SHA256.items():
        actual = _sha256(os.path.join(ART, "originals", name))
        assert actual == expected, name
    assert not os.path.exists(os.path.join(ART, "derived", "bg-town-plaza-meadow.png"))

    frame = _rgba(os.path.join(ART, "derived", "ui-town-wood-frame-cutout.png"))
    assert frame.size == (1280, 720)
    px = frame.load()
    assert px[640, 360][3] == 0
    assert px[0, 0][3] == 0
    assert px[24, 360][3] == 255
    assert px[640, 30][3] == 255
    assert px[640, 700][3] == 255
    assert px[1279, 719][3] == 255

    guild = _rgba(os.path.join(ART, "derived", "building-adventure-guild-cutout.png"))
    assert guild.size != (1024, 1024)
    assert guild.size[0] < 1024 and guild.size[1] < 1024
    gw, gh = guild.size
    gp = guild.load()
    assert gp[0, 0][3] == 0
    assert gp[gw - 1, 0][3] == 0
    assert gp[0, gh - 1][3] == 0
    assert gp[gw - 1, gh - 1][3] == 0
    ref = (251, 239, 215)
    cream = 0
    opaque = 0
    for y in range(gh):
        for x in range(gw):
            pixel = gp[x, y]
            if pixel[3] > 200:
                opaque += 1
                if _dist(pixel[:3], ref) < 12:
                    cream += 1
    assert opaque > 1000
    assert cream == 0


@pytest.mark.case_id("TC-ART-ABC-02")
def test_derive_matches_committed_cutouts():
    """TC-ART-ABC-02 再跑切圖，像素與已提交的 PNG 相同。"""
    module = _derive()
    from PIL import Image

    fresh_frame = module.derive_frame(os.path.join(ART, "originals", "ui-town-wood-frame.jpg"))
    committed_frame = Image.open(os.path.join(ART, "derived", "ui-town-wood-frame-cutout.png")).convert("RGBA")
    assert fresh_frame.tobytes() == committed_frame.tobytes()
    fresh_guild = module.derive_guild(os.path.join(ART, "originals", "building-adventure-guild.jpg"))
    committed_guild = Image.open(os.path.join(ART, "derived", "building-adventure-guild-cutout.png")).convert("RGBA")
    assert fresh_guild.tobytes() == committed_guild.tobytes()


@pytest.mark.case_id("TC-ART-ABC-03")
def test_grid_and_plaza_gate_stay_in_source():
    """TC-ART-ABC-03 地圖仍是 8×8；廣場圖沒有拿來當格子。"""
    js = open(os.path.join(REPO, "town-four-scene.js"), encoding="utf-8").read()
    css = open(os.path.join(REPO, "town-four-scene.css"), encoding="utf-8").read()
    html = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
    backend = open(os.path.join(REPO, "backend_v2.py"), encoding="utf-8").read()
    assert re.search(r"var COLS = 8;", js)
    assert re.search(r"var ROWS = 8;", js)
    assert "ax + aSize <= bx" in js
    assert "bg-town-plaza.jpg is not applied" in js
    assert "bg-town-plaza" not in css
    assert "bg-town-plaza" not in html
    assert "--s: 0.85" in css
    assert '"探險公會": 2' in backend
    assert "今日已在此區域獲勝，請明日再來。" in backend
    assert "<html" in html and "kt-art-abc" not in html.split("<html", 1)[1].split(">", 1)[0]


@pytest.mark.case_id("TC-ART-ABC-04")
def test_static_serves_cutout_and_original_jpeg(client):
    """TC-ART-ABC-04 切圖 PNG 與原 JPEG 可讀；Python 原始碼仍是 404。"""
    png = client.get(
        "/kids/assets/art-locked-2026-11-04/derived/ui-town-wood-frame-cutout.png"
    )
    assert png.status_code == 200, png.get_data(as_text=True)[:200]
    assert png.data[:8] == b"\x89PNG\r\n\x1a\n"
    jpg = client.get("/kids/assets/art-locked-2026-11-04/originals/bg-town-plaza.jpg")
    assert jpg.status_code == 200, jpg.get_data(as_text=True)[:200]
    assert jpg.data[:3] == b"\xff\xd8\xff"
    assert jpg.headers.get("Content-Type", "").startswith("image/jpeg")
    denied = client.get("/kids/backend_v2.py")
    assert denied.status_code == 404


def _preview_server_module():
    path = os.path.join(REPO, "scripts", "art_abc_preview_server.py")
    spec = importlib.util.spec_from_file_location("art_abc_preview_server", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.case_id("TC-ART-ABC-05")
def test_preview_port_isolated_from_shared_9123(tmp_path):
    """TC-ART-ABC-05 預設仍是 9123；9124 只聽臨時庫，不改 kids_town.db。"""
    import urllib.request

    module = _preview_server_module()
    assert module.resolve_port([]) == 9123
    assert module.resolve_port(["--port", "9124"]) == 9124
    old = os.environ.get("ART_PREVIEW_PORT")
    os.environ["ART_PREVIEW_PORT"] = "9124"
    try:
        assert module.resolve_port([]) == 9124
        assert module.resolve_port(["--port", "9130"]) == 9130
    finally:
        if old is None:
            os.environ.pop("ART_PREVIEW_PORT", None)
        else:
            os.environ["ART_PREVIEW_PORT"] = old
    with pytest.raises(SystemExit):
        module.resolve_port(["--port", "0"])

    _prod_untouched()
    db_path = str(tmp_path / "art-preview.db")
    env = os.environ.copy()
    env.pop("ART_PREVIEW_PORT", None)
    env["ART_PREVIEW_DB"] = db_path
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(REPO, "scripts", "art_abc_preview_server.py"), "--port", "9124"],
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if not _wait_port(9124, timeout=20):
            out = ""
            if proc.stdout:
                proc.terminate()
                out = proc.stdout.read()
            raise AssertionError(f"preview server did not bind 9124:\n{out}")
        with urllib.request.urlopen("http://127.0.0.1:9124/kids/?art=abc", timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            assert resp.status == 200
        assert "kt-art-abc" in body
        assert os.path.abspath(db_path) != os.path.abspath(PROD_DB)
        assert os.path.isfile(db_path)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    _prod_untouched()


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


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_port(port, timeout=30):
    import time

    for _ in range(timeout * 2):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def _place(db_path, kid_id, name, cell_x, cell_y):
    import sqlite3

    db = sqlite3.connect(db_path)
    row = db.execute("SELECT id FROM building_defs WHERE name=?", (name,)).fetchone()
    assert row, name
    db.execute(
        "INSERT INTO buildings (kid_id, def_id, plot_idx, level, cell_x, cell_y, stored) "
        "VALUES (?, ?, 0, 1, ?, ?, 0)",
        (kid_id, row[0], cell_x, cell_y),
    )
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def art_base_url(tmp_path_factory):
    if _PW_SKIP:
        pytest.skip(_PW_SKIP)
    _prod_untouched()
    dst = str(tmp_path_factory.mktemp("art-abc-db") / "art.db")
    import backend_v2 as backend

    init_empty_db(backend, dst)
    kid = insert_kid(
        dst,
        name=KID_NAME,
        username=KID_USERNAME,
        pin=TEST_KID_PIN,
        level=8,
        points=800,
    )
    _place(dst, kid["id"], "健身室", 0, 0)
    _place(dst, kid["id"], "探險公會", 2, 0)
    port = _free_port()
    log_path = dst + ".server.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(REPO, "tests", "_run_server.py"), dst, str(port)],
        cwd=REPO,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**os.environ, "KIDS_TOWN_SECRET_KEY": "art-abc-preview-secret"},
    )
    if not _wait_port(port):
        logf.flush()
        detail = open(log_path, encoding="utf-8").read()
        proc.kill()
        raise AssertionError(f"art preview server failed on {port}:\n{detail}")
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    logf.close()
    _prod_untouched()


@pytest.fixture()
def page(art_base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        pg = context.new_page()
        yield pg
        context.close()
        browser.close()


def _login(page, base_url, query=""):
    page.goto(f"{base_url}/kids/{query}")
    page.locator("#loginUsername").wait_for(state="visible", timeout=8000)
    page.locator("#loginUsername").fill(KID_USERNAME)
    page.locator("#loginPassword").fill(TEST_KID_PIN)
    with page.expect_response(
        lambda response: "/api/auth/login" in response.url and response.request.method == "POST"
    ) as caught:
        page.get_by_role("button", name="進入小鎮").click()
    assert caught.value.status == 200, caught.value.text()
    page.locator("#townMap").wait_for(state="visible", timeout=8000)
    page.wait_for_function(
        """() => document.querySelectorAll('#townMap .pad[data-zone="buildable"]').length === 64
          && document.querySelectorAll('#townMap .pad[data-zone="locked"]').length === 36""",
        timeout=8000,
    )


def _pad_width(page):
    return page.evaluate(
        """() => {
          const pad = document.querySelector('#townMap .pad[data-zone="buildable"]');
          return pad ? pad.offsetWidth : 0;
        }"""
    )


@pytest.mark.case_id("TC-FE-ART-ABC-01")
def test_art_preview_is_off_until_requested(page, art_base_url):
    """TC-FE-ART-ABC-01 預設不套木框；選單有「開啟美術預覽」。"""
    _login(page, art_base_url)
    shown = page.evaluate(
        """() => {
          const frame = document.getElementById('artAbcFrame');
          const cs = frame ? getComputedStyle(frame) : null;
          return {
            cls: document.documentElement.classList.contains('kt-art-abc'),
            display: cs ? cs.display : '',
            label: (document.getElementById('artAbcLabel') || {}).textContent || ''
          };
        }"""
    )
    assert shown["cls"] is False
    assert shown["display"] == "none"
    assert shown["label"] == "開啟美術預覽"
    guild = page.locator("#townMap .sprite").evaluate_all(
        "nodes => nodes.map(n => n.getAttribute('src') || '')"
    )
    assert any("bldg-expedition-guild" in src for src in guild)
    assert all("building-adventure-guild-cutout" not in src for src in guild)


@pytest.mark.case_id("TC-FE-ART-ABC-02")
def test_art_on_keeps_grid_scale_and_clicks(page, art_base_url):
    """TC-FE-ART-ABC-02 開啟後仍是 8×8、均勻縮放，鎖定格與空地的點擊沒有偏。"""
    _login(page, art_base_url)
    off_width = _pad_width(page)
    _login(page, art_base_url, "?art=abc")
    page.locator("#artAbcFrame").wait_for(state="visible", timeout=8000)
    info = page.evaluate(
        """() => {
          const stage = document.getElementById('stage');
          const frame = document.getElementById('artAbcFrame');
          const village = document.getElementById('village');
          const s = parseFloat(getComputedStyle(village).getPropertyValue('--s'));
          const frameMatrix = getComputedStyle(frame).transform;
          const frameParts = frameMatrix.startsWith('matrix(')
            ? frameMatrix.slice(7, -1).split(',').map(Number)
            : [];
          const matrix = getComputedStyle(stage).transform;
          const parts = matrix.startsWith('matrix(')
            ? matrix.slice(7, -1).split(',').map(Number)
            : [];
          const scaleX = parts[0];
          const scaleY = parts[3];
          const expect = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
          const footer = document.querySelector('#ktFooter .kt-footer-tab');
          const fbox = footer.getBoundingClientRect();
          const hit = document.elementFromPoint(fbox.left + fbox.width / 2, fbox.top + fbox.height / 2);
          return {
            offsetW: stage.offsetWidth,
            offsetH: stage.offsetHeight,
            scaleX, scaleY, expect,
            s,
            frameScale: frameParts.length ? frameParts[0] : 1,
            framePE: getComputedStyle(frame).pointerEvents,
            overflow: getComputedStyle(village).overflow,
            fits: village.scrollWidth <= village.clientWidth + 2
              && village.scrollHeight <= village.clientHeight + 2,
            buildable: document.querySelectorAll('#townMap .pad[data-zone="buildable"]').length,
            locked: document.querySelectorAll('#townMap .pad[data-zone="locked"]').length,
            footerHit: !!(hit && hit.closest && hit.closest('#ktFooter .kt-footer-tab'))
          };
        }"""
    )
    assert info["offsetW"] == 1280 and info["offsetH"] == 720
    assert 0.3 < info["s"] < 0.85
    assert info["frameScale"] > 1.02
    assert abs(info["scaleX"] - info["scaleY"]) < 0.01
    assert abs(info["scaleX"] - info["expect"]) < 0.03
    assert info["framePE"] == "none"
    assert info["overflow"] == "hidden"
    assert info["fits"] is True
    assert info["buildable"] == 64 and info["locked"] == 36
    assert _pad_width(page) < off_width
    assert info["footerHit"] is True

    page.set_viewport_size({"width": 800, "height": 600})
    page.wait_for_timeout(200)
    scaled = page.evaluate(
        """() => {
          const stage = document.getElementById('stage');
          const matrix = getComputedStyle(stage).transform;
          const parts = matrix.slice(7, -1).split(',').map(Number);
          const expect = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
          return {
            offsetW: stage.offsetWidth,
            offsetH: stage.offsetHeight,
            scaleX: parts[0],
            scaleY: parts[3],
            expect
          };
        }"""
    )
    assert scaled["offsetW"] == 1280 and scaled["offsetH"] == 720
    assert abs(scaled["scaleX"] - scaled["scaleY"]) < 0.01
    assert abs(scaled["scaleX"] - scaled["expect"]) < 0.03
    assert scaled["expect"] < 0.9

    page.set_viewport_size({"width": 1280, "height": 720})
    locked = page.locator("#townMap .pad.is-locked .cell-btn").first
    locked.scroll_into_view_if_needed()
    box = locked.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_function(
        """() => (document.getElementById('toast') || {}).textContent
          === '此格尚未解鎖，暫時不能建造。'""",
        timeout=4000,
    )
    empty = page.locator("#townMap .pad[data-col='3'][data-row='3'] .cell-btn")
    empty.scroll_into_view_if_needed()
    ebox = empty.bounding_box()
    page.mouse.click(ebox["x"] + ebox["width"] / 2, ebox["y"] + ebox["height"] / 2)
    page.wait_for_function(
        """() => (document.getElementById('toast') || {}).textContent
          === '想在這裏興建？請先按「我要起屋」。'""",
        timeout=4000,
    )


def _open_menu(page):
    page.locator(".gh .mb").click()
    page.locator("#dr.o").wait_for(state="visible", timeout=4000)
    page.locator("#btnArtAbc").wait_for(state="visible", timeout=4000)


def _menu_inside_stage(page):
    return page.evaluate(
        """() => {
          const stage = document.getElementById('stage').getBoundingClientRect();
          const drawer = document.getElementById('dr').getBoundingClientRect();
          const close = document.querySelector('#dr .dc').getBoundingClientRect();
          const toggle = document.getElementById('btnArtAbc').getBoundingClientRect();
          function inside(box) {
            return box.width > 20 && box.height > 20
              && box.left >= stage.left - 1 && box.top >= stage.top - 1
              && box.right <= stage.right + 1 && box.bottom <= stage.bottom + 1;
          }
          return {
            drawer: inside(drawer),
            close: inside(close),
            toggle: inside(toggle),
            bg: getComputedStyle(document.getElementById('dr')).backgroundColor
          };
        }"""
    )


@pytest.mark.case_id("TC-FE-ART-ABC-04")
def test_menu_stays_on_stage_and_footer_still_navigates(page, art_base_url):
    """TC-FE-ART-ABC-04 主目錄留在舞台內；底欄不會被遮罩吃掉點擊。"""
    _login(page, art_base_url, "?art=abc")
    _open_menu(page)
    on = _menu_inside_stage(page)
    assert on["drawer"] and on["close"] and on["toggle"], on
    assert on["bg"] not in ("rgb(240, 248, 255)", "rgba(240, 248, 255, 1)")
    page.get_by_role("button", name="公會大廳").click()
    page.locator("#tab-expedition.tab-content.active").wait_for(state="visible", timeout=4000)
    assert page.locator("#dov").evaluate("el => getComputedStyle(el).display") == "none"

    page.goto(f"{art_base_url}/kids/?art=off")
    page.locator("#townMap").wait_for(state="visible", timeout=8000)
    _open_menu(page)
    off = _menu_inside_stage(page)
    assert off["drawer"] and off["close"] and off["toggle"], off


@pytest.mark.case_id("TC-FE-ART-ABC-03")
def test_guild_cutout_has_no_cream_and_keeps_name(page, art_base_url):
    """TC-FE-ART-ABC-03 探險公會用去背圖，名字仍是 DOM，健身室仍是舊 SVG。"""
    _login(page, art_base_url, "?art=abc")
    page.wait_for_function(
        """() => {
          const img = document.querySelector('#townMap .sprite.is-locked-guild');
          return img && img.complete && img.naturalWidth > 0;
        }""",
        timeout=8000,
    )
    sample = page.evaluate(
        """() => {
          const img = document.querySelector('#townMap .sprite.is-locked-guild');
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0);
          const corner = ctx.getImageData(0, 0, 1, 1).data;
          const pad = img.closest('.pad');
          const shadow = pad.querySelector('[data-contact-shadow]');
          const cap = pad.querySelector('.cap');
          const gym = [...document.querySelectorAll('#townMap .sprite')].find((node) => {
            return (node.getAttribute('src') || '').indexOf('bldg-gym') !== -1;
          });
          return {
            src: img.getAttribute('src') || '',
            w: img.naturalWidth,
            h: img.naturalHeight,
            alpha: corner[3],
            cap: cap ? cap.textContent : '',
            shadow: !!(shadow && !shadow.hidden),
            gym: gym ? gym.getAttribute('src') : ''
          };
        }"""
    )
    assert "building-adventure-guild-cutout.png" in sample["src"]
    assert sample["w"] != 1024 and sample["h"] != 1024
    assert sample["alpha"] == 0
    assert sample["cap"] == "探險公會"
    assert sample["shadow"] is True
    assert "bldg-gym-iso" in sample["gym"]
    assert "cutout" not in sample["gym"]
