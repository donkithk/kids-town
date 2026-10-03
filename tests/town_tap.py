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
  return {
    c, r, cx, cy, hw, hh,
    points,
    label,
    button: {
      present: !!btn,
      aria: label,
      disabled: !!(btn && btn.disabled),
      tabIndex: btn ? btn.tabIndex : -1
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

_DISMISS_JS = r"""
() => {
  const map = document.getElementById('townMap');
  const scene = map ? (map.getAttribute('aria-label') || '') : '';
  if (scene.includes('場景 3')) {
    const cancel = document.getElementById('btnUxCancel');
    if (cancel) cancel.click();
  } else {
    const pad = document.querySelector('#townMap .pad.is-chosen');
    const btn = pad && pad.querySelector('.cell-btn');
    const slab = pad && pad.querySelector(':scope > .slab');
    if (btn) {
      const box = slab ? slab.getBoundingClientRect() : btn.getBoundingClientRect();
      btn.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        clientX: box.left + box.width / 2,
        clientY: box.top + box.height / 2,
        view: window
      }));
    }
  }
  const toast = document.getElementById('toast');
  if (toast) {
    toast.style.display = 'none';
    toast.textContent = '';
    toast.className = '';
  }
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


def tap_cell_centre(page, cell_x, cell_y, timeout=None):
    """Pointer-tap the visual diamond centre. `timeout` is unused.

    Callers used to pass a locator timeout. The coordinate tap does not wait
    on the button's hit target.
    """
    del timeout
    data = cell_points(page, cell_x, cell_y)
    centre = data["points"]["centre"]
    tap_point(page, centre["x"], centre["y"])
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
    """Leave scene 3 or clear the chosen pad, then hide a leftover toast."""
    page.evaluate(_DISMISS_JS)


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
