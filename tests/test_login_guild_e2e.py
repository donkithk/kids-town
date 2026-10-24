"""RED Playwright cases for the guild-hall login (mock PR #67).

Visual contract: docs/ui-mocks/login.html at tip 03f11429881b1ae9636f864fa37e5c60862db901.
Case catalog: docs/test-cases/LOGIN_GUILD.md.

These tests exercise /kids/ on the product server. They do not open the static
mock, and they do not change product JS/CSS/HTML. On current main the orange
login card fails the contract.

Fixture: empty temp SQLite, synthetic accounts only. Never reads kids_town.db.
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
    TEST_ADMIN_PASSWORD,
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    connect_db,
    init_empty_db,
    insert_kid,
    make_admin,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KID_USERNAME = "test_login_kid"
KID_NAME = "LoginKid"
PARENT_USERNAME = "test_login_parent"
PARENT_NAME = "Login Parent"
ADMIN_USERNAME = "test_login_admin"
ADMIN_NAME = "Login Admin"
REG_USERNAME = "test_login_new"
REG_PASSWORD = "TestReg!pass1"
REG_NAME = "測試家長"
REG_EMAIL = "test_login_new@example.test"
WRONG_PIN = "9999"
WRONG_PASSWORD = "WrongPass!9"
SLOGAN = "歡迎回到開心的小鎮"
BANNED = "開羅小鎮"
SIGN_ALT = "木牌寫著 Kids Town"
STAGE_W = 1280
STAGE_H = 720
MOCK_TIP = "03f11429881b1ae9636f864fa37e5c60862db901"

# Accessible names from the approved mock. Product may use its own ids.
MODES = {
    "kid": {
        "plaque": "孩子登入",
        "heading": "孩子登入",
        "lead": "請輸入登入名稱與 PIN。不使用密碼。",
        "fields": (("登入名稱", "text", None), ("PIN", "password", "4")),
        "hidden_labels": ("密碼", "管理員名稱", "用戶名稱", "稱呼", "電郵（可選）"),
        "submit": "進入小鎮",
    },
    "parent": {
        "plaque": "家長登入",
        "heading": "家長登入",
        "lead": "請輸入登入名稱與密碼。",
        "fields": (("登入名稱", "text", None), ("密碼", "password", None)),
        "hidden_labels": ("PIN", "管理員名稱", "用戶名稱", "稱呼", "電郵（可選）"),
        "submit": "以家長身份登入",
    },
    "admin": {
        "plaque": "管理員",
        "heading": "管理員登入",
        "lead": "請使用已獲授權的帳戶。不設預設密碼。",
        "fields": (("管理員名稱", "text", None), ("密碼", "password", None)),
        "hidden_labels": ("PIN", "登入名稱", "用戶名稱", "稱呼", "電郵（可選）"),
        "submit": "以管理員身份登入",
    },
    "register": {
        "plaque": "註冊",
        "heading": "註冊家長帳戶",
        "lead": "建立後可管理孩子的登入。密碼至少八個字元。",
        "fields": (
            ("用戶名稱", "text", None),
            ("密碼", "password", "8"),
            ("稱呼", "text", None),
            ("電郵（可選）", "email", None),
        ),
        "hidden_labels": ("PIN", "登入名稱", "管理員名稱"),
        "submit": "建立帳戶",
    },
}
PLAQUES = ("孩子登入", "家長登入", "管理員", "註冊")


def _playwright_unavailable_reason():
    """Skip only when Playwright / Chromium cannot run. Cross-platform."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "playwright package not installed. "
            "Install: pip install -r requirements.txt && python -m playwright install chromium"
        )
    try:
        with sync_playwright() as p:
            exe = p.chromium.executable_path
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


def _launch_chromium(playwright):
    return playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )


def _seed_login_db(dst):
    """Empty schema + three synthetic accounts. No buildings, no production DB."""
    import backend_v2 as backend

    old = backend.DB_PATH
    backend.app.config["TESTING"] = True
    init_empty_db(backend, dst)
    kid = insert_kid(
        dst,
        name=KID_NAME,
        username=KID_USERNAME,
        pin=TEST_KID_PIN,
        level=4,
        points=10,
    )
    db = connect_db(dst)
    db.execute(
        "INSERT INTO parents (username, password, name) VALUES (?, ?, ?)",
        (PARENT_USERNAME, backend.hash_password(TEST_PARENT_PASSWORD), PARENT_NAME),
    )
    parent_id = db.execute(
        "SELECT id FROM parents WHERE username=?", (PARENT_USERNAME,)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO parent_kid (parent_id, kid_id) VALUES (?, ?)",
        (parent_id, kid["id"]),
    )
    db.commit()
    db.close()
    make_admin(dst, username=ADMIN_USERNAME, password=TEST_ADMIN_PASSWORD, name=ADMIN_NAME)
    backend.DB_PATH = old
    return {"kid_id": kid["id"], "parent_id": parent_id}


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    dst = str(tmp_path_factory.mktemp("login-guild") / "test.db")
    ids = _seed_login_db(dst)
    with open(dst + ".ids.json", "w", encoding="utf-8") as fh:
        json.dump(ids, fh)
    return dst


@pytest.fixture(scope="session")
def base_url(test_db_path):
    port = _free_port()
    log_path = test_db_path + ".server.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(REPO, "tests", "_run_server.py"), test_db_path, str(port)],
        cwd=REPO,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**os.environ, "KIDS_TOWN_SECRET_KEY": "login-guild-e2e-secret"},
    )
    if not _wait_port(port, timeout=30):
        logf.flush()
        try:
            detail = open(log_path, encoding="utf-8").read()
        except OSError:
            detail = "(no server log)"
        proc.kill()
        raise AssertionError(f"test server failed to start on {port}:\n{detail}")
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
        browser = _launch_chromium(playwright)
        context = browser.new_context(viewport={"width": STAGE_W, "height": STAGE_H})
        pg = context.new_page()
        pg.set_default_timeout(5000)
        yield pg
        context.close()
        browser.close()


def _open(page, base_url, mode=None):
    url = f"{base_url}/kids/"
    if mode:
        url += f"#{mode}"
    page.goto(url, wait_until="domcontentloaded")


def _legacy_hint(page):
    info = page.evaluate(
        """() => {
          function shown(el) {
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden';
          }
          return {
            title: document.title,
            headings: [...document.querySelectorAll('h1,h2')].filter(shown).map(el => el.innerText.trim()).slice(0, 6),
            placeholders: [...document.querySelectorAll('input')].filter(shown).map(el => el.getAttribute('placeholder') || '').slice(0, 8),
          };
        }"""
    )
    return (
        f" Current product login is still the old card "
        f"(title={info['title']!r}, headings={info['headings']!r}, "
        f"placeholders={info['placeholders']!r}). "
        f"Match mock {MOCK_TIP} with product wiring, not a static copy."
    )


def _visible(locator):
    found = []
    for index in range(locator.count()):
        item = locator.nth(index)
        if item.is_visible():
            found.append(item)
    return found


def _by_role(page, role, name):
    return _visible(page.get_by_role(role, name=name, exact=True))


def _plaques(page, name):
    found = []
    for role in ("radio", "button", "tab"):
        found.extend(_by_role(page, role, name))
    return found


def _fields(page, name):
    return _visible(page.get_by_label(name, exact=True))


def _buttons(page, name):
    return _by_role(page, "button", name)


def _texts(page, text):
    return _visible(page.get_by_text(text, exact=True))


def _headings(page, name):
    return _by_role(page, "heading", name)


PROBE_JS = r"""
() => {
  const SLOGAN = "歡迎回到開心的小鎮";
  const BANNED = "開羅小鎮";
  const SIGN = "木牌寫著 Kids Town";
  function parseColor(c) {
    if (!c) return null;
    const m = String(c).match(/rgba?\(([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)(?:,\s*([0-9.]+))?\)/);
    if (!m) return null;
    return {r: +m[1], g: +m[2], b: +m[3], a: m[4] == null ? 1 : +m[4]};
  }
  function lum(p) { return 0.299 * p.r + 0.587 * p.g + 0.114 * p.b; }
  function isOak(p) {
    if (!p || p.a < 0.9) return false;
    return p.r >= 120 && p.r <= 210 && p.g >= 60 && p.g <= 150 && p.b >= 20 && p.b <= 90
      && p.r > p.g && p.g > p.b;
  }
  function isCream(p) {
    if (!p || p.a < 0.75) return false;
    return p.r >= 248 && p.g >= 236 && p.b >= 220 && p.b <= 252 && (p.r - p.b) >= 8 && p.g >= p.b;
  }
  function isDark(p) {
    return !!(p && p.a >= 0.9 && lum(p) <= 40);
  }
  function ownText(el) {
    return [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join("")
      .replace(/\s+/g, " ").trim();
  }
  function shown(el) {
    if (!el) return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  }
  const headings = [...document.querySelectorAll("h1,h2")].filter(shown).map(el => el.innerText.trim()).slice(0, 8);
  const banned = [];
  if ((document.title || "").includes(BANNED)) banned.push("document.title=" + document.title);
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const parent = walker.currentNode.parentElement;
    if (!parent || parent.closest("script, style")) continue;
    const text = walker.currentNode.textContent || "";
    if (text.includes(BANNED)) {
      banned.push((parent.id || parent.tagName) + ":" + text.trim().slice(0, 80));
    }
  }
  document.querySelectorAll("[placeholder],[aria-label],[alt],[title]").forEach(el => {
    ["placeholder", "aria-label", "alt", "title"].forEach(attr => {
      const value = el.getAttribute(attr) || "";
      if (value.includes(BANNED)) banned.push(attr + "=" + value.slice(0, 80));
    });
  });

  let sloganEl = null;
  for (const el of document.querySelectorAll("body *")) {
    if (!el.closest || el.closest("script, style")) continue;
    const text = ownText(el);
    if ((text === SLOGAN || text.endsWith(SLOGAN)) && shown(el)) {
      sloganEl = el;
      break;
    }
  }

  let stage = null;
  if (sloganEl) {
    let node = sloganEl;
    while (node && node !== document.body) {
      if (node.offsetWidth === 1280 && node.offsetHeight === 720 && shown(node)) {
        stage = node;
        break;
      }
      node = node.parentElement;
    }
  }

  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const scale = Math.min(vw / 1280, vh / 720);
  let stageInfo = null;
  if (stage) {
    const rect = stage.getBoundingClientRect();
    const cs = getComputedStyle(stage);
    const bg = parseColor(cs.backgroundColor);
    const borderW = parseFloat(cs.borderTopWidth) || 0;
    stageInfo = {
      id: stage.id || "",
      offsetWidth: stage.offsetWidth,
      offsetHeight: stage.offsetHeight,
      rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
      expected: {w: 1280 * scale, h: 720 * scale},
      bg: cs.backgroundColor,
      oak: isOak(bg),
      framed: (cs.boxShadow || "").includes("inset") || borderW >= 4,
      centerDx: Math.abs((rect.left + rect.right) / 2 - vw / 2),
      centerDy: Math.abs((rect.top + rect.bottom) / 2 - vh / 2),
    };
  }

  function corner(x, y) {
    const el = document.elementFromPoint(x, y);
    let node = el;
    let hit = null;
    while (node) {
      const parsed = parseColor(getComputedStyle(node).backgroundColor);
      if (parsed && parsed.a > 0.5) {
        hit = {bg: getComputedStyle(node).backgroundColor, dark: isDark(parsed), id: node.id || node.tagName};
        break;
      }
      node = node.parentElement;
    }
    const stageRect = stage ? stage.getBoundingClientRect() : null;
    const outside = !stageRect || x < stageRect.left - 1 || x > stageRect.right + 1
      || y < stageRect.top - 1 || y > stageRect.bottom + 1;
    return {x, y, outside, hit};
  }

  let cream = null;
  if (sloganEl) {
    let node = sloganEl;
    const stop = stage ? stage.parentElement : document.body;
    while (node && node !== stop) {
      const parsed = parseColor(getComputedStyle(node).backgroundColor);
      if (isCream(parsed) && shown(node)) {
        const rect = node.getBoundingClientRect();
        cream = {bg: getComputedStyle(node).backgroundColor, rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height}};
        break;
      }
      node = node.parentElement;
    }
  }

  const root = stage || document.body;
  let hero = null;
  for (const img of root.querySelectorAll("img")) {
    const alt = img.getAttribute("alt") || "";
    if (!shown(img) || !alt.includes(SIGN)) continue;
    const rect = img.getBoundingClientRect();
    hero = {alt, rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height}};
    break;
  }

  const competing = [];
  for (const el of document.querySelectorAll("h1,h2,h3,p,div,span")) {
    const text = ownText(el);
    if (!text.includes("Kids Town") || !shown(el)) continue;
    const size = parseFloat(getComputedStyle(el).fontSize) || 0;
    const tag = el.tagName;
    if (tag === "H1" || tag === "H2" || tag === "H3" || size >= 20) competing.push(tag + ":" + text.slice(0, 60));
  }

  let sheetOverHero = false;
  if (cream && hero) {
    const cx = cream.rect.x + cream.rect.w / 2;
    const cy = cream.rect.y + cream.rect.h / 2;
    sheetOverHero = cx >= hero.rect.x - 1 && cx <= hero.rect.x + hero.rect.w + 1
      && cy >= hero.rect.y - 1 && cy <= hero.rect.y + hero.rect.h + 1;
  }

  return {
    vw, vh, scale,
    title: document.title,
    headings,
    banned,
    slogan: !!sloganEl,
    stage: stageInfo,
    corners: {
      top: corner(Math.max(1, vw / 2), 2),
      left: corner(2, Math.max(1, vh / 2)),
    },
    cream,
    hero,
    competing,
    sheetOverHero,
  };
}
"""


def _probe(page):
    return page.evaluate(PROBE_JS)


def _letterbox_errors(probe, axis):
    errors = []
    stage = probe.get("stage")
    if not probe.get("slogan"):
        errors.append(f"{probe['vw']}×{probe['vh']}: slogan 「{SLOGAN}」 is not visible, so there is no guild login stage")
        return errors
    if not stage:
        errors.append(
            f"{probe['vw']}×{probe['vh']}: slogan is not inside a visible {STAGE_W}×{STAGE_H} oak stage"
        )
        return errors
    rect = stage["rect"]
    expected = stage["expected"]
    if abs(rect["w"] - expected["w"]) > 3 or abs(rect["h"] - expected["h"]) > 3:
        errors.append(
            f"{probe['vw']}×{probe['vh']}: visual stage {rect['w']:.1f}×{rect['h']:.1f} "
            f"!= scaled {expected['w']:.1f}×{expected['h']:.1f} (scale {probe['scale']:.4f})"
        )
    if stage["centerDx"] > 3 or stage["centerDy"] > 3:
        errors.append(
            f"{probe['vw']}×{probe['vh']}: stage is not centered "
            f"(dx={stage['centerDx']:.1f}, dy={stage['centerDy']:.1f})"
        )
    if stage["offsetWidth"] != STAGE_W or stage["offsetHeight"] != STAGE_H:
        errors.append(
            f"unscaled stage is {stage['offsetWidth']}×{stage['offsetHeight']}, want {STAGE_W}×{STAGE_H}"
        )
    if not stage["oak"]:
        errors.append(f"stage background {stage['bg']!r} is not warm oak")
    if not stage["framed"]:
        errors.append("stage has no inset wood frame (inset shadow or border)")
    corner = probe["corners"]["top" if axis == "vertical" else "left"]
    side = "top" if axis == "vertical" else "left"
    if not corner["outside"]:
        errors.append(f"{probe['vw']}×{probe['vh']}: {side} letterbox bar is missing; the stage fills that edge")
    elif not (corner.get("hit") and corner["hit"].get("dark")):
        errors.append(f"{probe['vw']}×{probe['vh']}: {side} letterbox is not a dark bar ({corner})")
    return errors


def _mode_errors(page, mode):
    spec = MODES[mode]
    errors = []
    if len(_headings(page, spec["heading"])) != 1:
        errors.append(f"#{mode}: heading 「{spec['heading']}」 is not the one visible heading")
    if len(_texts(page, spec["lead"])) != 1:
        errors.append(f"#{mode}: lead 「{spec['lead']}」 is not visible")
    if len(_buttons(page, spec["submit"])) != 1:
        errors.append(f"#{mode}: submit 「{spec['submit']}」 is not a visible button")
    for label, kind, min_length in spec["fields"]:
        fields = _fields(page, label)
        if len(fields) != 1:
            errors.append(f"#{mode}: expected one visible field labelled 「{label}」, found {len(fields)}")
            continue
        actual = (fields[0].get_attribute("type") or "text").lower()
        if actual != kind:
            errors.append(f"#{mode}: 「{label}」 type is {actual}, want {kind}")
        if min_length is not None and fields[0].get_attribute("minlength") != min_length:
            errors.append(
                f"#{mode}: 「{label}」 minlength is {fields[0].get_attribute('minlength')!r}, want {min_length}"
            )
    for label in spec["hidden_labels"]:
        shown = _fields(page, label)
        if shown:
            errors.append(f"#{mode}: field 「{label}」 should be hidden while this mode is active")
    if mode == "register":
        email = _fields(page, "電郵（可選）")
        if email and email[0].get_attribute("required") is not None:
            errors.append("#register: 電郵（可選） must stay optional")
    for name in PLAQUES:
        if len(_plaques(page, name)) != 1:
            errors.append(f"#{mode}: mode plaque 「{name}」 is not a visible radio/button/tab")
    return errors


def _assert_login_post(page, button_name, username_label, secret_label, username, secret):
    users = _fields(page, username_label)
    secrets = _fields(page, secret_label)
    buttons = _buttons(page, button_name)
    if not users or not secrets or not buttons:
        raise AssertionError(
            f"cannot submit {button_name!r}: "
            f"field {username_label!r} count={len(users)}, "
            f"field {secret_label!r} count={len(secrets)}, "
            f"button count={len(buttons)}."
            + _legacy_hint(page)
        )
    users[0].fill(username)
    secrets[0].fill(secret)
    try:
        with page.expect_response(
            lambda resp: "/api/auth/login" in resp.url and resp.request.method == "POST",
            timeout=5000,
        ) as info:
            buttons[0].click()
    except Exception as exc:
        raise AssertionError(
            "submit must POST /api/auth/login with the typed secret. "
            "Do not copy the static mock submit handler (it never logs in)."
            + _legacy_hint(page)
        ) from exc
    response = info.value
    posted = response.request.post_data_json or {}
    assert str(posted.get("username", "")).lower() == username.lower(), posted
    assert posted.get("password") == secret, "visible secret must be sent as API password"
    return response


def _fetch_status(page, path):
    return page.evaluate(
        """async (path) => {
          const r = await fetch(path, {credentials: 'same-origin'});
          return r.status;
        }""",
        path,
    )


def _error_text(page):
    statuses = page.get_by_role("status")
    for index in range(statuses.count()):
        item = statuses.nth(index)
        if not item.is_visible():
            continue
        text = item.inner_text().strip()
        if text:
            return text
    blob = page.locator("body").inner_text()
    for token in ("錯誤", "失敗", "不正確", "無法"):
        if token in blob:
            return token
    return ""


def _assert_stays_on_login(page, response):
    assert response.status == 403, response.text()
    body = response.json()
    assert "pin" not in body and "password" not in body
    assert "不會登入" not in page.locator("body").inner_text()
    assert _texts(page, SLOGAN), "wrong secret must keep the login slogan on screen" + _legacy_hint(page)
    app = page.locator("#app")
    assert app.count() == 0 or not app.is_visible(), "wrong secret must not open the app"
    message = _error_text(page)
    assert message, "wrong secret must show a visible error"
    assert "不會驗證" not in message and "靜態設計稿" not in message
    assert "成功" not in message


def _assert_left_login(page):
    assert not _texts(page, SLOGAN), "successful auth must leave the login slogan"
    screen = page.locator("#loginScreen")
    if screen.count() and screen.is_visible():
        box = screen.bounding_box()
        if box and box["width"] > 20 and box["height"] > 20:
            raise AssertionError("successful auth must hide the login screen")


# ── TC-FE-LOGIN-STAGE-01 ─────────────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-STAGE-01")
def test_login_guild_stage_letterboxes(page, base_url):
    """TC-FE-LOGIN-STAGE-01 1280×720 橡木外框喺兩個 viewport 信箱縮放。"""
    errors = []
    for width, height, axis in ((1000, 800, "vertical"), (1600, 720, "horizontal")):
        page.set_viewport_size({"width": width, "height": height})
        _open(page, base_url, "kid")
        errors.extend(_letterbox_errors(_probe(page), axis))
    assert not errors, "\n".join(errors) + _legacy_hint(page)


# ── TC-FE-LOGIN-HERO-01 ──────────────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-HERO-01")
def test_login_guild_hero_cream_overlay_no_competing_title(page, base_url):
    """TC-FE-LOGIN-HERO-01 奶油面板疊喺歡迎圖上；Kids Town 只喺木牌。"""
    page.set_viewport_size({"width": STAGE_W, "height": STAGE_H})
    _open(page, base_url, "kid")
    probe = _probe(page)
    errors = []
    if not probe["hero"]:
        errors.append(
            f"missing a visible hero img whose alt contains 「{SIGN_ALT}」 "
            "(Kids Town only as the painted guild sign)"
        )
    if probe["competing"]:
        errors.append("separate Kids Town text competes with the painted sign: " + ", ".join(probe["competing"]))
    if not probe["cream"]:
        errors.append("slogan is not inside a cream/light panel (mock sheet is rgba(255,248,238,0.9))")
    elif not probe["sheetOverHero"]:
        errors.append("cream panel is not over the hero image")
    if probe["hero"] and probe["stage"]:
        if probe["hero"]["rect"]["w"] < probe["stage"]["rect"]["w"] * 0.6:
            errors.append("hero image does not fill the oak stage")
    assert not errors, "\n".join(errors) + _legacy_hint(page)


# ── TC-FE-LOGIN-COPY-01 ──────────────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-COPY-01")
def test_login_guild_copy_slogan_and_no_cairo_name(page, base_url):
    """TC-FE-LOGIN-COPY-01 口號在欄位旁，畫面冇「開羅小鎮」。"""
    _open(page, base_url, "kid")
    probe = _probe(page)
    errors = []
    if probe["banned"]:
        errors.append("「開羅小鎮」 is on the login screen: " + "; ".join(probe["banned"][:6]))
    if not probe["slogan"]:
        errors.append(f"slogan 「{SLOGAN}」 is missing")
    elif not probe["cream"]:
        errors.append("slogan is not in the cream panel with the active fields")
    assert not errors, "\n".join(errors) + _legacy_hint(page)


# ── TC-FE-LOGIN-MODE-01 ──────────────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-MODE-01")
def test_login_guild_modes_hash_and_plaques(page, base_url):
    """TC-FE-LOGIN-MODE-01 #kid/#parent/#admin/#register 同四塊銘牌切換欄位。"""
    errors = []
    _open(page, base_url, "kid")
    for mode in ("parent", "admin", "register", "kid"):
        plaques = _plaques(page, MODES[mode]["plaque"])
        if len(plaques) != 1:
            errors.append(f"click: plaque 「{MODES[mode]['plaque']}」 missing")
            continue
        plaques[0].click()
        for item in _mode_errors(page, mode):
            errors.append("click " + item)
    for mode in ("kid", "parent", "admin", "register"):
        _open(page, base_url, mode)
        assert page.evaluate("() => location.hash") == f"#{mode}"
        for item in _mode_errors(page, mode):
            errors.append("hash " + item)
    assert not errors, "\n".join(errors) + _legacy_hint(page)


# ── TC-FE-LOGIN-FIELDS-01 ────────────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-FIELDS-01")
def test_login_guild_fields_pin_password_register(page, base_url):
    """TC-FE-LOGIN-FIELDS-01 孩子用 PIN；家長、管理員、註冊用密碼；註冊四欄。"""
    errors = []
    _open(page, base_url, "kid")
    errors.extend(_mode_errors(page, "kid"))
    pin = _fields(page, "PIN")
    if pin and (pin[0].get_attribute("type") or "").lower() != "password":
        errors.append("kid PIN control must be type=password")
    _open(page, base_url, "parent")
    errors.extend(_mode_errors(page, "parent"))
    _open(page, base_url, "admin")
    errors.extend(_mode_errors(page, "admin"))
    _open(page, base_url, "register")
    errors.extend(_mode_errors(page, "register"))
    labels = [label for label, _kind, _min in MODES["register"]["fields"]]
    if labels != ["用戶名稱", "密碼", "稱呼", "電郵（可選）"]:
        errors.append(f"register labels drifted: {labels}")
    shown = _fields(page, "電郵（可選）")
    if len(shown) == 1 and (shown[0].get_attribute("type") or "").lower() != "email":
        errors.append("電郵（可選） must be type=email")
    assert not errors, "\n".join(errors) + _legacy_hint(page)


# ── TC-FE-LOGIN-AUTH-KID-01 ──────────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-AUTH-KID-01")
def test_login_guild_auth_kid_pin(page, base_url):
    """TC-FE-LOGIN-AUTH-KID-01 錯 PIN 留喺登入；對 PIN 離開登入並見到 HUD。"""
    _open(page, base_url, "kid")
    bad = _assert_login_post(page, "進入小鎮", "登入名稱", "PIN", KID_USERNAME, WRONG_PIN)
    _assert_stays_on_login(page, bad)
    assert _fetch_status(page, "/api/auth/session") == 401
    hud = page.locator("#hudNm")
    assert hud.count() == 0 or not hud.is_visible()

    _open(page, base_url, "kid")
    good = _assert_login_post(page, "進入小鎮", "登入名稱", "PIN", KID_USERNAME, TEST_KID_PIN)
    assert good.status == 200, good.text()
    body = good.json()
    assert body.get("role") == "kid", body
    assert "pin" not in body and "password" not in body
    page.locator("#hudNm").wait_for(state="visible", timeout=8000)
    assert page.locator("#hudNm").inner_text().strip() == KID_NAME
    _assert_left_login(page)
    assert _fetch_status(page, "/api/auth/session") == 200


# ── TC-FE-LOGIN-AUTH-PARENT-01 ───────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-AUTH-PARENT-01")
def test_login_guild_auth_parent_password(page, base_url):
    """TC-FE-LOGIN-AUTH-PARENT-01 錯密碼留喺登入；對密碼進入家長管理。"""
    _open(page, base_url, "parent")
    bad = _assert_login_post(
        page, "以家長身份登入", "登入名稱", "密碼", PARENT_USERNAME, WRONG_PASSWORD
    )
    _assert_stays_on_login(page, bad)
    assert _fetch_status(page, "/api/auth/parent-kids") == 401

    _open(page, base_url, "parent")
    good = _assert_login_post(
        page, "以家長身份登入", "登入名稱", "密碼", PARENT_USERNAME, TEST_PARENT_PASSWORD
    )
    assert good.status == 200, good.text()
    body = good.json()
    assert body.get("role") == "parent", body
    assert "password" not in body
    page.get_by_text("小朋友管理", exact=False).first.wait_for(state="visible", timeout=8000)
    _assert_left_login(page)
    assert _fetch_status(page, "/api/auth/parent-kids") == 200


# ── TC-FE-LOGIN-AUTH-ADMIN-01 ────────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-AUTH-ADMIN-01")
def test_login_guild_auth_admin_password(page, base_url):
    """TC-FE-LOGIN-AUTH-ADMIN-01 錯密碼留喺登入；對密碼離開登入並帶管理員 session。"""
    _open(page, base_url, "admin")
    bad = _assert_login_post(
        page, "以管理員身份登入", "管理員名稱", "密碼", ADMIN_USERNAME, WRONG_PASSWORD
    )
    _assert_stays_on_login(page, bad)
    assert _fetch_status(page, "/api/kids") == 401

    _open(page, base_url, "admin")
    good = _assert_login_post(
        page, "以管理員身份登入", "管理員名稱", "密碼", ADMIN_USERNAME, TEST_ADMIN_PASSWORD
    )
    assert good.status == 200, good.text()
    body = good.json()
    assert body.get("role") == "admin", body
    assert "password" not in body
    page.locator("#app").wait_for(state="visible", timeout=8000)
    _assert_left_login(page)
    assert _fetch_status(page, "/api/kids") == 200


# ── TC-FE-LOGIN-AUTH-REGISTER-01 ─────────────────────────────────

@pytest.mark.case_id("TC-FE-LOGIN-AUTH-REGISTER-01")
def test_login_guild_auth_register_then_login(page, base_url):
    """TC-FE-LOGIN-AUTH-REGISTER-01 四欄註冊打現有 API，之後用密碼登入。"""
    _open(page, base_url, "register")
    pairs = (
        ("用戶名稱", REG_USERNAME),
        ("密碼", REG_PASSWORD),
        ("稱呼", REG_NAME),
        ("電郵（可選）", REG_EMAIL),
    )
    missing = [label for label, _value in pairs if len(_fields(page, label)) != 1]
    buttons = _buttons(page, "建立帳戶")
    if missing or len(buttons) != 1:
        raise AssertionError(
            f"register form is not the four-field mock "
            f"(missing={missing}, submit={len(buttons)})."
            + _legacy_hint(page)
        )
    for label, value in pairs:
        _fields(page, label)[0].fill(value)
    try:
        with page.expect_response(
            lambda resp: "/api/auth/parent-register" in resp.url and resp.request.method == "POST",
            timeout=5000,
        ) as info:
            buttons[0].click()
    except Exception as exc:
        raise AssertionError(
            "建立帳戶 must POST /api/auth/parent-register. "
            "Do not copy the static mock submit handler."
            + _legacy_hint(page)
        ) from exc
    response = info.value
    assert response.status == 201, response.text()
    posted = response.request.post_data_json or {}
    assert posted.get("username") == REG_USERNAME
    assert posted.get("password") == REG_PASSWORD
    assert posted.get("name") == REG_NAME
    assert posted.get("email") == REG_EMAIL
    assert "不會登入" not in page.locator("body").inner_text()

    _open(page, base_url, "parent")
    good = _assert_login_post(
        page, "以家長身份登入", "登入名稱", "密碼", REG_USERNAME, REG_PASSWORD
    )
    assert good.status == 200, good.text()
    assert good.json().get("role") == "parent"
    page.get_by_text("小朋友管理", exact=False).first.wait_for(state="visible", timeout=8000)
    _assert_left_login(page)
    assert _fetch_status(page, "/api/auth/parent-kids") == 200
