"""Tap an iso cell at its visual ground-tile diamond, not the button box.

The diamond is the slab image's bounding box: vertices are the midpoints of
that box's edges. Pointer taps use page.mouse at those viewport coordinates.
The per-cell button stays the keyboard and screen-reader target.
"""
from __future__ import annotations

import re

_PAD_LABEL = re.compile(r"第\s*(\d+)\s*欄第\s*(\d+)\s*行")

# 35% of the way from the diamond centre to each vertex and each edge
# midpoint. Those eight points, plus the centre, sit strictly inside.
SAMPLE_FRACTION = 0.35

_CELL_POINTS_JS = r"""
([c, r]) => {
  const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
    const cs = getComputedStyle(el);
    return parseInt(cs.getPropertyValue('--c'), 10) === c
      && parseInt(cs.getPropertyValue('--r'), 10) === r;
  });
  const scene = (document.getElementById('townMap') || {}).getAttribute
    ? (document.getElementById('townMap').getAttribute('aria-label') || '')
    : '';
  const pads = document.querySelectorAll('#townMap .pad').length;
  if (!pad) return { missingSlab: true, reason: 'no pad', pads, scene };
  const slab = pad.querySelector(':scope > .slab');
  if (!slab) return { missingSlab: true, reason: 'no slab', pads, scene };
  const box = slab.getBoundingClientRect();
  if (box.width < 2 || box.height < 2) {
    const cs = getComputedStyle(slab);
    return {
      missingSlab: true,
      reason: 'empty box',
      pads,
      scene,
      width: box.width,
      height: box.height,
      display: cs.display,
      visibility: cs.visibility
    };
  }
  const cx = box.left + box.width / 2;
  const cy = box.top + box.height / 2;
  const hw = box.width / 2;
  const hh = box.height / 2;
  const toward = (x, y) => ({ x: cx + 0.35 * (x - cx), y: cy + 0.35 * (y - cy) });
  const points = {
    centre: { x: cx, y: cy },
    'vertex-top': toward(cx, box.top),
    'vertex-right': toward(box.right, cy),
    'vertex-bottom': toward(cx, box.bottom),
    'vertex-left': toward(box.left, cy),
    'edge-top-right': toward(cx + hw / 2, cy - hh / 2),
    'edge-bottom-right': toward(cx + hw / 2, cy + hh / 2),
    'edge-bottom-left': toward(cx - hw / 2, cy + hh / 2),
    'edge-top-left': toward(cx - hw / 2, cy - hh / 2)
  };
  const btn = pad.querySelector(':scope > .cell-btn');
  const label = btn ? (btn.getAttribute('aria-label') || '') : '';
  const btnBox = btn ? btn.getBoundingClientRect() : null;
  return {
    c, r, cx, cy, hw, hh,
    points,
    vertices: {
      top: { x: cx, y: box.top },
      right: { x: box.right, y: cy },
      bottom: { x: cx, y: box.bottom },
      left: { x: box.left, y: cy }
    },
    label,
    button: {
      present: !!btn,
      aria: label,
      disabled: !!(btn && btn.disabled),
      tabIndex: btn ? btn.tabIndex : -1,
      x: btnBox && btnBox.width > 2 ? btnBox.left + btnBox.width / 2 : null,
      y: btnBox && btnBox.height > 2 ? btnBox.top + btnBox.height / 2 : null
    }
  };
}
"""

_OVERLAYS_JS = r"""
() => {
  const pick = (el, role) => {
    if (!el || el.hidden) return null;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return null;
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) return null;
    return {
      role,
      id: el.id || '',
      left: box.left,
      top: box.top,
      right: box.right,
      bottom: box.bottom
    };
  };
  const out = [];
  const palette = pick(document.getElementById('palette'), 'panel');
  if (palette) out.push(palette);
  for (const id of ['readyBar', 'uxPlaceBar', 'actionSheet', 'listLauncher', 'ktFooter']) {
    const hit = pick(document.getElementById(id), 'chrome');
    if (hit) out.push(hit);
  }
  const hud = document.querySelector('#app .gh');
  const hudHit = pick(hud, 'chrome');
  if (hudHit) out.push(hudHit);
  const tools = document.querySelector('#townMap .tools');
  const toolHit = pick(tools, 'chrome');
  if (toolHit) out.push(toolHit);
  return out;
}
"""

_REACTION_JS = r"""
() => {
  const toast = document.getElementById('toast');
  const map = document.getElementById('townMap');
  const shown = !!(toast && toast.style.display === 'block' && (toast.textContent || '').trim());
  const chosen = [];
  const preview = [];
  for (const pad of document.querySelectorAll('#townMap .pad')) {
    const btn = pad.querySelector('.cell-btn');
    const label = btn ? (btn.getAttribute('aria-label') || '') : '';
    const match = /第\s*(\d+)\s*欄第\s*(\d+)\s*行/.exec(label);
    if (!match) continue;
    const cell = [Number(match[1]) - 1, Number(match[2]) - 1];
    const badge = pad.querySelector(':scope > .badge');
    let badgeText = '';
    if (badge && !badge.hidden) {
      const cs = getComputedStyle(badge);
      const box = badge.getBoundingClientRect();
      if (cs.display !== 'none' && cs.visibility !== 'hidden' && box.width > 1) {
        badgeText = (badge.textContent || '').trim();
      }
    }
    if (pad.classList.contains('is-chosen') || label.includes('已選此格') || badgeText === '此格') {
      chosen.push(cell);
    }
    if (
      pad.classList.contains('is-preview')
      || label.includes('擺放預覽')
      || badgeText === '預覽'
    ) {
      preview.push(cell);
    }
  }
  return {
    scene: map ? (map.getAttribute('aria-label') || '') : '',
    toast: shown ? (toast.textContent || '').trim() : '',
    toastClass: shown ? (toast.className || '') : '',
    chosen,
    preview
  };
}
"""

# Real pointer clicks. A synthetic MouseEvent on the cell button does not
# clear state.pad on builds whose map listener only trusts the event's
# coordinates, so the next sample toggles the cell off or leaves it selected.
_CHOSEN_POINT_JS = r"""
() => {
  const map = document.getElementById('townMap');
  const scene = map ? (map.getAttribute('aria-label') || '') : '';
  if (scene.includes('場景 3')) return { scene3: true, points: [] };
  for (const pad of document.querySelectorAll('#townMap .pad')) {
    const btn = pad.querySelector(':scope > .cell-btn');
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
      || label.includes('已選此格')
      || badgeText === '此格';
    if (!chosen) continue;
    const slab = pad.querySelector(':scope > .slab');
    const slabBox = slab ? slab.getBoundingClientRect() : null;
    const btnBox = btn ? btn.getBoundingClientRect() : null;
    const points = [];
    if (btnBox && btnBox.width > 2 && btnBox.height > 2) {
      points.push({
        x: btnBox.left + btnBox.width / 2,
        y: btnBox.top + btnBox.height / 2,
        name: 'button'
      });
    }
    if (slabBox && slabBox.width > 2 && slabBox.height > 2) {
      const cx = slabBox.left + slabBox.width / 2;
      const cy = slabBox.top + slabBox.height / 2;
      const hw = slabBox.width / 2;
      const hh = slabBox.height / 2;
      const toward = (px, py) => ({
        x: cx + 0.35 * (px - cx),
        y: cy + 0.35 * (py - cy)
      });
      const named = [
        ['centre', { x: cx, y: cy }],
        ['vertex-top', toward(cx, slabBox.top)],
        ['vertex-right', toward(slabBox.right, cy)],
        ['vertex-bottom', toward(cx, slabBox.bottom)],
        ['vertex-left', toward(slabBox.left, cy)],
        ['edge-top-right', toward(cx + hw / 2, cy - hh / 2)],
        ['edge-bottom-right', toward(cx + hw / 2, cy + hh / 2)],
        ['edge-bottom-left', toward(cx - hw / 2, cy + hh / 2)],
        ['edge-top-left', toward(cx - hw / 2, cy - hh / 2)]
      ];
      for (const [name, point] of named) points.push({ x: point.x, y: point.y, name });
    }
    const cs = getComputedStyle(pad);
    return {
      scene3: false,
      c: parseInt(cs.getPropertyValue('--c'), 10),
      r: parseInt(cs.getPropertyValue('--r'), 10),
      points
    };
  }
  return { scene3: false, points: [] };
}
"""

_HIDE_TOAST_JS = r"""
() => {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.style.display = 'none';
  toast.textContent = '';
  toast.className = '';
}
"""

# elementFromPoint, not the CSS box. Rounded corners and shadows sit inside
# the box without covering the pixel, and a bar can cover a pixel its box
# measurement missed.
_COVER_JS = r"""
([x, y]) => {
  const el = document.elementFromPoint(x, y);
  if (!el) return { kind: 'none', inMap: false, cell: false, foreignButton: false };
  const map = document.getElementById('townMap');
  const cell = !!(el.closest && el.closest(
    '#townMap .cell-btn, #townMap .hit-sliver, #townMap .pad'
  ));
  const describe = {
    kind: 'open',
    inMap: !!(map && (el === map || map.contains(el))),
    cell,
    foreignButton: !!(el.closest && el.closest('button') && !el.closest('.cell-btn')),
    id: el.id || '',
    cls: String(el.className || '').slice(0, 80)
  };
  const toast = document.getElementById('toast');
  if (toast && (el === toast || toast.contains(el))) {
    describe.kind = 'toast';
    return describe;
  }
  if (el.closest && el.closest('.fx-burst, [data-town-fx]')) {
    describe.kind = 'fx';
    return describe;
  }
  const layers = [
    ['#palette', 'panel'],
    ['#readyBar', 'chrome'],
    ['#uxPlaceBar', 'chrome'],
    ['#ktFooter', 'chrome'],
    ['#app .gh', 'chrome'],
    ['#townMap .tools', 'chrome'],
    ['#listLauncher', 'chrome'],
    ['#actionSheet', 'chrome'],
    ['#btnBuild', 'chrome'],
    ['#upgradeConfirm', 'chrome'],
    ['#modalOverlay', 'chrome']
  ];
  for (const [sel, kind] of layers) {
    const root = document.querySelector(sel);
    if (!root) continue;
    const cs = getComputedStyle(root);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (root.hidden) continue;
    const box = root.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) continue;
    if (el === root || root.contains(el)) {
      describe.kind = kind;
      describe.selector = sel;
      return describe;
    }
  }
  return describe;
}
"""

_FOCUS_JS = r"""
([c, r]) => {
  const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
    const cs = getComputedStyle(el);
    return parseInt(cs.getPropertyValue('--c'), 10) === c
      && parseInt(cs.getPropertyValue('--r'), 10) === r;
  });
  const btn = pad && pad.querySelector(':scope > .cell-btn');
  if (!btn) return false;
  btn.focus();
  return document.activeElement === btn;
}
"""

_ACCESS_JS = r"""
() => [...document.querySelectorAll('#townMap .pad')].map((pad) => {
  const cs = getComputedStyle(pad);
  const btn = pad.querySelector(':scope > .cell-btn');
  const label = btn ? (btn.getAttribute('aria-label') || '') : '';
  return {
    c: parseInt(cs.getPropertyValue('--c'), 10),
    r: parseInt(cs.getPropertyValue('--r'), 10),
    aria: label,
    present: !!btn,
    disabled: !!(btn && btn.disabled),
    tabIndex: btn ? btn.tabIndex : -1
  };
})
"""

_SPRITE_POINT_JS = r"""
() => {
  const pads = [...document.querySelectorAll('#townMap .pad')].map((pad) => {
    const cs = getComputedStyle(pad);
    const c = parseInt(cs.getPropertyValue('--c'), 10);
    const r = parseInt(cs.getPropertyValue('--r'), 10);
    const slab = pad.querySelector(':scope > .slab');
    const sprite = pad.querySelector(':scope > img.sprite, :scope > .sprite');
    const box = slab ? slab.getBoundingClientRect() : null;
    let spriteBox = null;
    if (sprite && !sprite.hidden) {
      const spriteCs = getComputedStyle(sprite);
      const sbox = sprite.getBoundingClientRect();
      if (spriteCs.display !== 'none' && sbox.width > 2 && sbox.height > 2) {
        spriteBox = { left: sbox.left, top: sbox.top, right: sbox.right, bottom: sbox.bottom };
      }
    }
    const label = (pad.querySelector('.cell-btn') || {}).getAttribute
      ? (pad.querySelector('.cell-btn').getAttribute('aria-label') || '')
      : '';
    return {
      c, r, label,
      empty: !spriteBox,
      cx: box ? box.left + box.width / 2 : 0,
      cy: box ? box.top + box.height / 2 : 0,
      hw: box ? box.width / 2 : 0,
      hh: box ? box.height / 2 : 0,
      sprite: spriteBox
    };
  }).filter((pad) => pad.hw > 2 && pad.hh > 2);
  const inside = (pad, x, y) => Math.abs(x - pad.cx) / pad.hw + Math.abs(y - pad.cy) / pad.hh < 0.98;
  const contains = (rect, x, y) => x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  for (const back of pads) {
    if (!back.empty) continue;
    for (const front of pads) {
      if (!front.sprite || front.c === back.c && front.r === back.r) continue;
      if (back.r >= front.r) continue;
      for (let i = 1; i <= 5; i += 1) {
        for (let j = 1; j <= 5; j += 1) {
          const x = back.cx + back.hw * ((i / 3) - 1) * 0.7;
          const y = back.cy + back.hh * ((j / 3) - 1) * 0.7;
          if (!inside(back, x, y) || !contains(front.sprite, x, y)) continue;
          return {
            x, y,
            c: back.c, r: back.r,
            frontC: front.c, frontR: front.r,
            frontLabel: front.label
          };
        }
      }
    }
  }
  return null;
}
"""


def point_in_rect(point, rect):
    return (
        rect["left"] <= point["x"] <= rect["right"]
        and rect["top"] <= point["y"] <= rect["bottom"]
    )


def cell_points(page, cell_x, cell_y):
    """Scroll the slab into view and return its diamond sample points."""
    data = page.evaluate(_CELL_POINTS_JS, [cell_x, cell_y])
    if not data or data.get("missingSlab"):
        raise AssertionError(
            f"cell ({cell_x},{cell_y}) has no visible ground slab to measure the diamond: {data}"
        )
    return data


def overlay_rects(page):
    return page.evaluate(_OVERLAYS_JS)


def tap_point(page, x, y):
    page.mouse.click(x, y)


def element_at(page, x, y):
    """Topmost element at a viewport point, and whether it is a map cell."""
    return page.evaluate(
        """([x, y]) => {
          const el = document.elementFromPoint(x, y);
          if (!el) return null;
          const map = document.getElementById('townMap');
          const cell = el.closest && el.closest(
            '#townMap .cell-btn, #townMap .hit-sliver, #townMap .pad'
          );
          return {
            tag: el.tagName,
            id: el.id || '',
            cls: String(el.className || '').slice(0, 140),
            inMap: !!(map && (el === map || map.contains(el))),
            cell: !!cell
          };
        }""",
        [x, y],
    )


def point_cover(page, x, y):
    """What elementFromPoint assigns this pixel to.

    `panel` and `chrome` are solid UI that may eat the click. `toast` and
    `fx` are not: those layers are required to be pointer-events none.
    """
    return page.evaluate(_COVER_JS, [x, y])


def _point_reaches_map(cover):
    if not cover:
        return False
    if cover.get("kind") in ("panel", "chrome", "none"):
        return False
    if cover.get("foreignButton"):
        return False
    return bool(cover.get("inMap"))


def _point_can_toggle(cover):
    """A pixel the map listener will turn into a cell.

    Solid UI that is not itself a button still reaches the capture listener,
    which hit-tests the coordinates. A footer tab or bar button returns early.
    """
    if not cover or cover.get("foreignButton"):
        return False
    if cover.get("kind") in ("none",):
        return False
    return True


_FALLBACK_NAMES = (
    "vertex-top",
    "vertex-left",
    "vertex-right",
    "edge-top-left",
    "edge-top-right",
    "vertex-bottom",
    "edge-bottom-left",
    "edge-bottom-right",
)


_CELL_AT_JS = r"""
([x, y]) => {
  const village = document.getElementById('village');
  const pads = [...document.querySelectorAll('#townMap .pad')];
  if (!village || !pads.length) return null;
  const rect = village.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return null;
  const scaleX = rect.width / village.offsetWidth || 1;
  const scaleY = rect.height / village.offsetHeight || 1;
  const inside = (x - rect.left) / scaleX;
  if (inside < 0 || inside > village.clientWidth) return null;
  const px = (x - rect.left) / scaleX + village.scrollLeft;
  const py = (y - rect.top) / scaleY + village.scrollTop;
  const pad0 = pads[0];
  const s = pad0.offsetWidth / 160;
  const stepX = 84 * s;
  const stepY = 50 * s;
  const dx = px - (pad0.offsetLeft + 80 * s);
  const dy = py - (pad0.offsetTop + 121 * s);
  if (!stepX || !stepY) return null;
  const cf = 0.5 * (dx / stepX + dy / stepY);
  const rf = 0.5 * (dy / stepY - dx / stepX);
  const c = Math.round(cf);
  const r = Math.round(rf);
  if (Math.abs(cf - c) > 0.501 || Math.abs(rf - r) > 0.501) return null;
  if (c < 0 || r < 0 || c >= 8 || r >= 8) return null;
  return { c: c, r: r };
}
"""


def _product_cell_at(page, x, y):
    return page.evaluate(_CELL_AT_JS, [x, y])


def _activate_point(page, cell_x, cell_y, data):
    """An interior diamond point the product hit-test assigns to this cell.

    Prefer a pixel that is not covered. If every such pixel is solid UI,
    use one that is not a foreign button so the map listener still runs.
    """
    points = [data["points"]["centre"]]
    button = data.get("button") or {}
    if button.get("x") is not None and button.get("y") is not None:
        points.append({"x": button["x"], "y": button["y"]})
        # The hit diamond extends above the button. A footer or bar can
        # cover the button centre while a point a few pixels higher is
        # still this cell and still inside the slab diamond.
        for dy in (-16, -32, -48, 16):
            nudged = {"x": button["x"], "y": button["y"] + dy}
            half_w = data["hw"]
            half_h = data["hh"]
            if half_w > 0 and half_h > 0:
                span = (
                    abs(nudged["x"] - data["cx"]) / half_w
                    + abs(nudged["y"] - data["cy"]) / half_h
                )
                if span < 0.98:
                    points.append(nudged)
    for name in _FALLBACK_NAMES:
        points.append(data["points"][name])
    ranked = []
    for point in points:
        hit = _product_cell_at(page, point["x"], point["y"])
        if not hit or hit.get("c") != cell_x or hit.get("r") != cell_y:
            continue
        cover = point_cover(page, point["x"], point["y"])
        ranked.append((point, cover))
    for point, cover in ranked:
        if _point_reaches_map(cover):
            return point
    for point, cover in ranked:
        if _point_can_toggle(cover):
            return point
    return data["points"]["centre"]


def _scroll_cell_into_view(page, cell_x, cell_y):
    """Bring the pad into the viewport before measuring the diamond.

    Bottom-row slabs sit below a 720px viewport. A coordinate click there
    never lands. Scrolling the pad (not the window) lifts the diamond
    above the footer without following a footer tab.
    """
    page.evaluate(
        """([c, r]) => {
          const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
            const cs = getComputedStyle(el);
            return parseInt(cs.getPropertyValue('--c'), 10) === c
              && parseInt(cs.getPropertyValue('--r'), 10) === r;
          });
          if (pad) pad.scrollIntoView({ block: 'center', inline: 'nearest' });
        }""",
        [cell_x, cell_y],
    )


def tap_cell_centre(page, cell_x, cell_y, timeout=None):
    """Pointer-tap the visual diamond centre. `timeout` is unused.

    Callers used to pass a locator timeout. The coordinate tap does not wait
    on the button's hit target. When the centre itself is under solid UI,
    another interior diamond point that elementFromPoint leaves on the map
    is used. The cell button's centre is one of those points: it sits inside
    the slab diamond, on the product's hit origin.
    """
    del timeout
    _scroll_cell_into_view(page, cell_x, cell_y)
    data = cell_points(page, cell_x, cell_y)
    target = _activate_point(page, cell_x, cell_y, data)
    tap_point(page, target["x"], target["y"])
    return data


def tap_labeled_button(page, locator):
    """Read 欄/行 from a cell button, then tap that cell's diamond centre."""
    label = locator.get_attribute("aria-label") or ""
    match = _PAD_LABEL.search(label)
    if not match:
        raise AssertionError(f"cell button aria has no 欄/行: {label!r}")
    cell_x = int(match.group(1)) - 1
    cell_y = int(match.group(2)) - 1
    tap_cell_centre(page, cell_x, cell_y)
    return cell_x, cell_y


def read_reaction(page):
    return page.evaluate(_REACTION_JS)


def dismiss_selection(page):
    """Leave scene 3 or clear the chosen pad, then hide a leftover toast.

    Scene 2 toggles, so the click has to land on the chosen cell. The cell
    button centre is tried first; the slab centre and the upper vertex are
    the fallbacks when that pixel is solid UI.
    """
    info = page.evaluate(_CHOSEN_POINT_JS) or {}
    if info.get("scene3"):
        cancel = page.locator("#btnUxCancel")
        if cancel.count() and cancel.first.is_visible():
            cancel.first.click()
    else:
        want = (info.get("c"), info.get("r"))
        points = []
        for point in info.get("points") or []:
            hit = _product_cell_at(page, point["x"], point["y"])
            if hit and (hit.get("c"), hit.get("r")) == want:
                points.append(point)
        if not points:
            points = info.get("points") or []
        covers = [(point, point_cover(page, point["x"], point["y"])) for point in points]

        def _click_until_clear(predicate):
            for point, cover in covers:
                if not predicate(cover):
                    continue
                tap_point(page, point["x"], point["y"])
                if not (read_reaction(page).get("chosen") or []):
                    return True
            return False

        if not _click_until_clear(_point_reaches_map):
            _click_until_clear(_point_can_toggle)
    page.evaluate(_HIDE_TOAST_JS)


def focus_cell(page, cell_x, cell_y):
    return page.evaluate(_FOCUS_JS, [cell_x, cell_y])


def press_cell(page, cell_x, cell_y, key):
    focused = focus_cell(page, cell_x, cell_y)
    if not focused:
        raise AssertionError(f"cell ({cell_x},{cell_y}) button did not take focus")
    page.keyboard.press(key)


def cell_access(page):
    return page.evaluate(_ACCESS_JS)


def sprite_overlap_point(page):
    """A point inside an empty back cell's diamond and a front building's sprite."""
    return page.evaluate(_SPRITE_POINT_JS)
