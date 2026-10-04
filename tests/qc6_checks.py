"""Geometry helpers for the QC6 tap, contrast, focus, and inert cases.

Product code is not imported. Callers pass a Playwright page that is already
on the town map.
"""
from __future__ import annotations

REQUIRED_STROKE = (0xB4, 0x53, 0x09)  # #b45309
GOLD_STROKE = (0xD4, 0xA0, 0x17)  # #d4a017
GRASS_FALLBACK = (0x7E, 0xAE, 0x52)  # #7eae52
GOLD_FILL = (0xFF, 0xF3, 0xC4)  # #fff3c4
GOLD_FILL_ALPHA = 0.62


def _channel(value):
    value = value / 255.0
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    red, green, blue = rgb
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(left, right):
    hi = max(luminance(left), luminance(right))
    lo = min(luminance(left), luminance(right))
    return (hi + 0.05) / (lo + 0.05)


def composite(fg, alpha, bg):
    return tuple(int(round(fg[i] * alpha + bg[i] * (1 - alpha))) for i in range(3))


def parse_hex(text):
    if not text:
        return None
    raw = text.strip().lstrip("#")
    if len(raw) != 6:
        return None
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return None


def _solid_rects_js():
    return r"""
() => {
  const map = document.getElementById('townMap');
  const mapBox = map ? map.getBoundingClientRect() : null;
  const sels = [
    '#palette', '#readyBar', '#uxPlaceBar', '#ktFooter', '#app .gh',
    '#townMap .tools', '#listLauncher', '#actionSheet', '#btnBuild',
    '#upgradeConfirm', '#modalOverlay'
  ];
  function eats(el) {
    if (!el || el.hidden || el.inert) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (Number(cs.opacity) === 0) return false;
    if (cs.pointerEvents === 'none') return false;
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) return false;
    if (box.right < 0 || box.bottom < 0 || box.left > innerWidth || box.top > innerHeight) {
      return false;
    }
    if (!mapBox) return false;
    const ix = Math.min(box.right, mapBox.right) - Math.max(box.left, mapBox.left);
    const iy = Math.min(box.bottom, mapBox.bottom) - Math.max(box.top, mapBox.top);
    return ix > 0 && iy > 0;
  }
  const rects = [];
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (!eats(el)) continue;
    const box = el.getBoundingClientRect();
    rects.push({
      sel, left: box.left, top: box.top, right: box.right, bottom: box.bottom
    });
  }
  return rects;
}
"""


def open_solid_rects(page):
    """Bounding rects of open, visible solid UI that intersects #townMap."""
    return page.evaluate(_solid_rects_js()) or []


def solid_selector(rects, x, y):
    for rect in rects:
        if rect["left"] <= x <= rect["right"] and rect["top"] <= y <= rect["bottom"]:
            return rect["sel"]
    return None


_CLIP_JS = r"""
() => {
  const map = document.getElementById('townMap');
  const village = document.getElementById('village');
  if (!map || !village) return null;
  function clientBox(el) {
    const box = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      left: box.left + (parseFloat(cs.borderLeftWidth) || 0),
      top: box.top + (parseFloat(cs.borderTopWidth) || 0),
      right: box.right - (parseFloat(cs.borderRightWidth) || 0),
      bottom: box.bottom - (parseFloat(cs.borderBottomWidth) || 0)
    };
  }
  function intersect(a, b) {
    if (!a || !b) return null;
    const left = Math.max(a.left, b.left);
    const top = Math.max(a.top, b.top);
    const right = Math.min(a.right, b.right);
    const bottom = Math.min(a.bottom, b.bottom);
    if (right - left < 1 || bottom - top < 1) return null;
    return {left, top, right, bottom};
  }
  const viewport = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
  const clip = intersect(intersect(viewport, clientBox(map)), clientBox(village));
  const blockers = [];
  for (const sel of ['#readyBar', '#uxPlaceBar', '#ktFooter']) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) continue;
    blockers.push({left: box.left, top: box.top, right: box.right, bottom: box.bottom, sel});
  }
  function inClip(x, y) {
    return !!(clip && x >= clip.left && x <= clip.right && y >= clip.top && y <= clip.bottom);
  }
  function blocked(x, y) {
    return blockers.some((b) => x >= b.left && x <= b.right && y >= b.top && y <= b.bottom);
  }
  function inVisible(x, y) {
    return inClip(x, y) && !blocked(x, y);
  }
  function cellAt(x, y) {
    const rect = village.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    const scaleX = rect.width / village.offsetWidth || 1;
    const scaleY = rect.height / village.offsetHeight || 1;
    const inside = (x - rect.left) / scaleX;
    if (inside < 0 || inside > village.clientWidth) return null;
    const px = (x - rect.left) / scaleX + village.scrollLeft;
    const py = (y - rect.top) / scaleY + village.scrollTop;
    const pad0 = document.querySelector('#townMap .pad');
    if (!pad0) return null;
    const s = pad0.offsetWidth / 160;
    const stepX = 84 * s;
    const stepY = 50 * s;
    if (!stepX || !stepY) return null;
    const dx = px - (pad0.offsetLeft + 80 * s);
    const dy = py - (pad0.offsetTop + 121 * s);
    const cf = 0.5 * (dx / stepX + dy / stepY);
    const rf = 0.5 * (dy / stepY - dx / stepX);
    const c = Math.round(cf);
    const r = Math.round(rf);
    if (Math.abs(cf - c) > 0.501 || Math.abs(rf - r) > 0.501) return null;
    if (c < 0 || r < 0 || c >= 8 || r >= 8) return null;
    return {c, r};
  }
  function diamonds() {
    const out = [];
    for (const pad of document.querySelectorAll('#townMap .pad')) {
      const slab = pad.querySelector(':scope > .slab');
      if (!slab) continue;
      const b = slab.getBoundingClientRect();
      if (b.width < 2 || b.height < 2) continue;
      const cs = getComputedStyle(pad);
      const c = parseInt(cs.getPropertyValue('--c'), 10);
      const r = parseInt(cs.getPropertyValue('--r'), 10);
      const cx = b.left + b.width / 2;
      const cy = b.top + b.height / 2;
      const verts = [
        {x: cx, y: b.top}, {x: b.right, y: cy},
        {x: cx, y: b.bottom}, {x: b.left, y: cy}
      ];
      let visible = 0;
      const step = 8;
      for (let y = b.top; y <= b.bottom; y += step) {
        for (let x = b.left; x <= b.right; x += step) {
          const hw = b.width / 2;
          const hh = b.height / 2;
          if (Math.abs(x - cx) / hw + Math.abs(y - cy) / hh > 1) continue;
          if (inVisible(x, y)) visible += 1;
        }
      }
      const mark = pad.querySelector(':scope > .mark');
      let gold = false;
      if (mark && !mark.hidden) {
        const mcs = getComputedStyle(mark);
        const mb = mark.getBoundingClientRect();
        const filter = mcs.filter || '';
        gold = mcs.display !== 'none' && mcs.visibility !== 'hidden' && mb.width > 1
          && filter.includes('212') && filter.includes('160') && filter.includes('23');
      }
      out.push({c, r, cx, cy, hw: b.width / 2, hh: b.height / 2, visible, gold, verts});
    }
    return out;
  }
  return {
    clip, blockers, diamonds: diamonds(),
    scroll: village.scrollTop,
    max: Math.max(0, village.scrollHeight - village.clientHeight)
  };
}
"""


def _geometry(page):
    return page.evaluate(_CLIP_JS)


def off_visible_probes(page):
    """Points outside #townMap's visible rect, including the listed edge strips.

    A point inside the village scrollport and not on the bar or footer is
    visible, so it is not returned. Hidden-cell hits (product cellAt still
    names a cell) are kept ahead of points that hit nothing.
    """
    geo = _geometry(page)
    if not geo or not geo.get("clip"):
        return {"points": [], "clip": None, "scroll": None, "max": None}
    clip = geo["clip"]
    blockers = geo.get("blockers") or []

    def in_visible(x, y):
        if not (clip["left"] <= x <= clip["right"] and clip["top"] <= y <= clip["bottom"]):
            return False
        for blocker in blockers:
            if blocker["left"] <= x <= blocker["right"] and blocker["top"] <= y <= blocker["bottom"]:
                return False
        return True

    raw = []

    def add(x, y, why):
        if x < -4 or y < -4 or x > 2000 or y > 2000:
            return
        if in_visible(x, y):
            return
        raw.append({"x": x, "y": y, "why": why})

    mid_y = (clip["top"] + clip["bottom"]) / 2
    for y in (clip["top"] + 16, mid_y, clip["bottom"] - 8):
        add(clip["left"] - 4, y, "left-edge")
        add(clip["left"] - 8, y, "left-edge")
        add(clip["right"] + 4, y, "right-edge")
        add(clip["right"] + 8, y, "right-edge")
    x = clip["left"] + 10
    while x < clip["right"] - 4:
        add(x, clip["top"] - 2, "top-edge")
        add(x, clip["top"] - 8, "top-edge")
        add(x, clip["bottom"] + 2, "bottom-edge")
        add(x, clip["bottom"] + 8, "bottom-edge")
        add(x, clip["bottom"] + 18, "below-village")
        x += 28
    bar = next((item for item in blockers if item.get("sel") == "#readyBar"), None)
    if bar:
        x = bar["left"] + 6
        while x < bar["right"] - 4:
            add(x, bar["top"] - 1, "above-bar")
            add(x, bar["top"] + 3, "bar-strip")
            add(x, bar["top"] + 8, "bar-strip")
            x += 24
        for cx, cy, ix, iy, name in (
            (bar["left"], bar["top"], 1, 1, "bar-corner"),
            (bar["right"], bar["top"], -1, 1, "bar-corner"),
            (bar["left"], bar["bottom"], 1, -1, "bar-corner"),
            (bar["right"], bar["bottom"], -1, -1, "bar-corner"),
        ):
            add(cx + ix * 3, cy + iy * 3, name)
            add(cx + ix * 5, cy + iy * 5, name)
    footer = next((item for item in blockers if item.get("sel") == "#ktFooter"), None)
    if footer:
        x = footer["left"] + 12
        while x < footer["right"] - 8:
            add(x, footer["top"] + 8, "footer")
            add(x, (footer["top"] + footer["bottom"]) / 2, "footer")
            x += 40
    # Classify with the product hit-test. Keep two hits per hidden cell and
    # a few misses per region so the sweep cannot pass with an empty set.
    classified = page.evaluate(
        """(points) => {
          const village = document.getElementById('village');
          const pad0 = document.querySelector('#townMap .pad');
          function cellAt(x, y) {
            if (!village || !pad0) return null;
            const rect = village.getBoundingClientRect();
            if (rect.width < 1) return null;
            const scaleX = rect.width / village.offsetWidth || 1;
            const scaleY = rect.height / village.offsetHeight || 1;
            const inside = (x - rect.left) / scaleX;
            if (inside < 0 || inside > village.clientWidth) return null;
            const px = (x - rect.left) / scaleX + village.scrollLeft;
            const py = (y - rect.top) / scaleY + village.scrollTop;
            const s = pad0.offsetWidth / 160;
            const stepX = 84 * s, stepY = 50 * s;
            if (!stepX || !stepY) return null;
            const dx = px - (pad0.offsetLeft + 80 * s);
            const dy = py - (pad0.offsetTop + 121 * s);
            const cf = 0.5 * (dx / stepX + dy / stepY);
            const rf = 0.5 * (dy / stepY - dx / stepX);
            const c = Math.round(cf), r = Math.round(rf);
            if (Math.abs(cf - c) > 0.501 || Math.abs(rf - r) > 0.501) return null;
            if (c < 0 || r < 0 || c >= 8 || r >= 8) return null;
            return {c, r};
          }
          return points.map((point) => {
            const hit = cellAt(point.x, point.y);
            return Object.assign({}, point, {cell: hit});
          });
        }""",
        raw,
    ) or []
    kept = []
    per_cell = {}
    per_why = {}
    for point in classified:
        cell = point.get("cell")
        if cell:
            key = (cell.get("c"), cell.get("r"), point["why"])
            if per_cell.get(key, 0) >= 2:
                continue
            per_cell[key] = per_cell.get(key, 0) + 1
            kept.append(point)
            continue
        why = point["why"]
        if per_why.get(why, 0) >= 3:
            continue
        per_why[why] = per_why.get(why, 0) + 1
        kept.append(point)
    return {
        "points": kept,
        "clip": clip,
        "scroll": geo.get("scroll"),
        "max": geo.get("max"),
        "raw": len(raw),
    }


def toast_off_visible_probes(page):
    """Toast-box points that are outside the visible map, plus 8px under it."""
    return page.evaluate(
        r"""
() => {
  const toast = document.getElementById('toast');
  const map = document.getElementById('townMap');
  const village = document.getElementById('village');
  if (!toast || toast.style.display === 'none' || !map || !village) return [];
  const box = toast.getBoundingClientRect();
  if (box.width < 2 || box.height < 2) return [];
  function clientBox(el) {
    const b = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      left: b.left + (parseFloat(cs.borderLeftWidth) || 0),
      top: b.top + (parseFloat(cs.borderTopWidth) || 0),
      right: b.right - (parseFloat(cs.borderRightWidth) || 0),
      bottom: b.bottom - (parseFloat(cs.borderBottomWidth) || 0)
    };
  }
  function intersect(a, b) {
    const left = Math.max(a.left, b.left);
    const top = Math.max(a.top, b.top);
    const right = Math.min(a.right, b.right);
    const bottom = Math.min(a.bottom, b.bottom);
    if (right - left < 1 || bottom - top < 1) return null;
    return {left, top, right, bottom};
  }
  const viewport = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
  const clip = intersect(intersect(viewport, clientBox(map)), clientBox(village));
  const blockers = ['#readyBar', '#uxPlaceBar', '#ktFooter'].map((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return null;
    const b = el.getBoundingClientRect();
    return {left: b.left, top: b.top, right: b.right, bottom: b.bottom};
  }).filter(Boolean);
  function inVisible(x, y) {
    if (!clip || x < clip.left || x > clip.right || y < clip.top || y > clip.bottom) return false;
    return !blockers.some((b) => x >= b.left && x <= b.right && y >= b.top && y <= b.bottom);
  }
  const points = [];
  for (let x = box.left + 8; x < box.right - 4; x += 22) {
    const samples = [
      [x, box.top + box.height / 2, 'toast-body'],
      [x, box.bottom - 4, 'toast-lower'],
      [x, box.bottom + 8, 'toast-under-8']
    ];
    for (const [px, py, why] of samples) {
      if (py < 0 || py > innerHeight || px < 0 || px > innerWidth) continue;
      if (inVisible(px, py)) continue;
      points.push({x: px, y: py, why});
    }
  }
  return points.slice(0, 24);
}
"""
    ) or []


def visible_gold_under_toast(page):
    """A point on a gold diamond that is inside the visible map and the toast."""
    return page.evaluate(
        r"""
() => {
  const toast = document.getElementById('toast');
  if (!toast || toast.style.display === 'none') return null;
  const toastBox = toast.getBoundingClientRect();
  const map = document.getElementById('townMap');
  const village = document.getElementById('village');
  if (!map || !village) return null;
  function clientBox(el) {
    const b = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      left: b.left + (parseFloat(cs.borderLeftWidth) || 0),
      top: b.top + (parseFloat(cs.borderTopWidth) || 0),
      right: b.right - (parseFloat(cs.borderRightWidth) || 0),
      bottom: b.bottom - (parseFloat(cs.borderBottomWidth) || 0)
    };
  }
  function intersect(a, b) {
    const left = Math.max(a.left, b.left), top = Math.max(a.top, b.top);
    const right = Math.min(a.right, b.right), bottom = Math.min(a.bottom, b.bottom);
    if (right - left < 1 || bottom - top < 1) return null;
    return {left, top, right, bottom};
  }
  const clip = intersect(
    intersect({left: 0, top: 0, right: innerWidth, bottom: innerHeight}, clientBox(map)),
    clientBox(village)
  );
  const blockers = ['#readyBar', '#uxPlaceBar', '#ktFooter', '#palette', '#actionSheet', '#app .gh']
    .map((sel) => {
      const el = document.querySelector(sel);
      if (!el || el.hidden) return null;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.pointerEvents === 'none') return null;
      if (Number(cs.opacity) === 0) return null;
      const b = el.getBoundingClientRect();
      if (b.width < 2) return null;
      return {left: b.left, top: b.top, right: b.right, bottom: b.bottom};
    }).filter(Boolean);
  function inVisible(x, y) {
    if (!clip || x < clip.left || x > clip.right || y < clip.top || y > clip.bottom) return false;
    if (blockers.some((b) => x >= b.left && x <= b.right && y >= b.top && y <= b.bottom)) return false;
    return x >= toastBox.left && x <= toastBox.right && y >= toastBox.top && y <= toastBox.bottom;
  }
  for (const pad of document.querySelectorAll('#townMap .pad')) {
    const mark = pad.querySelector(':scope > .mark');
    if (!mark || mark.hidden) continue;
    const mcs = getComputedStyle(mark);
    const filter = mcs.filter || '';
    if (!(filter.includes('212') && filter.includes('160') && filter.includes('23'))) continue;
    const slab = pad.querySelector(':scope > .slab');
    if (!slab) continue;
    const b = slab.getBoundingClientRect();
    const cx = b.left + b.width / 2;
    const cy = b.top + b.height / 2;
    const hw = b.width / 2;
    const hh = b.height / 2;
    if (hw < 2 || hh < 2) continue;
    const cs = getComputedStyle(pad);
    const c = parseInt(cs.getPropertyValue('--c'), 10);
    const r = parseInt(cs.getPropertyValue('--r'), 10);
    for (let y = b.top; y <= b.bottom; y += 6) {
      for (let x = b.left; x <= b.right; x += 6) {
        if (Math.abs(x - cx) / hw + Math.abs(y - cy) / hh > 0.92) continue;
        if (!inVisible(x, y)) continue;
        return {x, y, c, r};
      }
    }
  }
  return null;
}
"""
    )


def set_village_scroll(page, value):
    return page.evaluate(
        """(value) => {
          const village = document.getElementById('village');
          if (!village) return null;
          const max = Math.max(0, village.scrollHeight - village.clientHeight);
          const next = value === 'max' ? max : Math.min(Number(value) || 0, max);
          village.scrollTop = next;
          return {scroll: village.scrollTop, max};
        }""",
        value,
    )


def corner_insets(rect, distances=(3, 5, 7)):
    """Points diagonally inward from each corner of a bounding rect."""
    corners = (
        ("top-left", rect["left"], rect["top"], 1, 1),
        ("top-right", rect["right"], rect["top"], -1, 1),
        ("bottom-left", rect["left"], rect["bottom"], 1, -1),
        ("bottom-right", rect["right"], rect["bottom"], -1, -1),
    )
    points = []
    for name, x, y, ix, iy in corners:
        for distance in distances:
            points.append({
                "name": f"{name}+{distance}",
                "x": x + ix * distance,
                "y": y + iy * distance,
            })
    return points


def map_hit_at(page, x, y):
    return page.evaluate(
        """([x, y]) => {
          const el = document.elementFromPoint(x, y);
          if (!el) return {map: false, cell: false, button: false, got: null};
          const map = document.getElementById('townMap');
          const cell = !!(el.closest && el.closest(
            '#townMap .pad, #townMap .cell-btn, #townMap .slab, #townMap .mark, #townMap .hit-sliver, #village'
          ));
          const button = !!(el.closest && el.closest('button, a, [role="button"]'));
          const onMap = el === map || cell || !!(map && map.contains(el) && (el.id === 'village' || el.id === 'townMap'));
          return {
            map: !!(cell || el === map || (el.closest && el.closest('#village'))),
            cell,
            button,
            got: el.id || (typeof el.className === 'string' ? el.className : el.tagName)
          };
        }""",
        [x, y],
    )


def surface_rect(page, selector):
    return page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (!el || el.hidden) return null;
          const cs = getComputedStyle(el);
          if (cs.display === 'none' || cs.visibility === 'hidden') return null;
          if (Number(cs.opacity) === 0) return null;
          const box = el.getBoundingClientRect();
          if (box.width < 2 || box.height < 2) return null;
          return {left: box.left, top: box.top, right: box.right, bottom: box.bottom,
                  width: box.width, height: box.height};
        }""",
        selector,
    )


def gold_point_inside(page, rect):
    """A visible gold-diamond point inside rect that elementFromPoint leaves on the map."""
    if not rect:
        return None
    return page.evaluate(
        """(rect) => {
          const map = document.getElementById('townMap');
          const village = document.getElementById('village');
          if (!map || !village) return null;
          function clientBox(el) {
            const b = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return {
              left: b.left + (parseFloat(cs.borderLeftWidth) || 0),
              top: b.top + (parseFloat(cs.borderTopWidth) || 0),
              right: b.right - (parseFloat(cs.borderRightWidth) || 0),
              bottom: b.bottom - (parseFloat(cs.borderBottomWidth) || 0)
            };
          }
          function intersect(a, b) {
            const left = Math.max(a.left, b.left), top = Math.max(a.top, b.top);
            const right = Math.min(a.right, b.right), bottom = Math.min(a.bottom, b.bottom);
            if (right - left < 1 || bottom - top < 1) return null;
            return {left, top, right, bottom};
          }
          const clip = intersect(
            intersect({left: 0, top: 0, right: innerWidth, bottom: innerHeight}, clientBox(map)),
            clientBox(village)
          );
          const blockers = ['#readyBar', '#uxPlaceBar', '#ktFooter', '#palette', '#actionSheet',
            '#listLauncher', '#app .gh', '#townMap .tools'].map((sel) => {
            const el = document.querySelector(sel);
            if (!el || el.hidden) return null;
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || cs.pointerEvents === 'none') return null;
            if (Number(cs.opacity) === 0 || el.inert) return null;
            const b = el.getBoundingClientRect();
            if (b.width < 2 || b.height < 2) return null;
            if (b.right < 0 || b.bottom < 0 || b.left > innerWidth || b.top > innerHeight) return null;
            return {left: b.left, top: b.top, right: b.right, bottom: b.bottom};
          }).filter(Boolean);
          function cellAt(x, y) {
            const vrect = village.getBoundingClientRect();
            if (vrect.width < 1) return null;
            const pad0 = document.querySelector('#townMap .pad');
            if (!pad0) return null;
            const scaleX = vrect.width / village.offsetWidth || 1;
            const scaleY = vrect.height / village.offsetHeight || 1;
            const inside = (x - vrect.left) / scaleX;
            if (inside < 0 || inside > village.clientWidth) return null;
            const px = (x - vrect.left) / scaleX + village.scrollLeft;
            const py = (y - vrect.top) / scaleY + village.scrollTop;
            const s = pad0.offsetWidth / 160;
            const stepX = 84 * s;
            const stepY = 50 * s;
            if (!stepX || !stepY) return null;
            const dx = px - (pad0.offsetLeft + 80 * s);
            const dy = py - (pad0.offsetTop + 121 * s);
            const cf = 0.5 * (dx / stepX + dy / stepY);
            const rf = 0.5 * (dy / stepY - dx / stepX);
            const cc = Math.round(cf);
            const rr = Math.round(rf);
            if (Math.abs(cf - cc) > 0.501 || Math.abs(rf - rr) > 0.501) return null;
            if (cc < 0 || rr < 0 || cc >= 8 || rr >= 8) return null;
            return {c: cc, r: rr};
          }
          function open(x, y, c, r) {
            if (!clip || x < clip.left || x > clip.right || y < clip.top || y > clip.bottom) return false;
            if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) return false;
            if (blockers.some((b) => x >= b.left && x <= b.right && y >= b.top && y <= b.bottom)) return false;
            const el = document.elementFromPoint(x, y);
            if (!el || !(el.closest && el.closest('#townMap, #village'))) return false;
            const hit = cellAt(x, y);
            return !!(hit && hit.c === c && hit.r === r);
          }
          for (const pad of document.querySelectorAll('#townMap .pad')) {
            const mark = pad.querySelector(':scope > .mark');
            if (!mark || mark.hidden) continue;
            const mcs = getComputedStyle(mark);
            const filter = mcs.filter || '';
            if (!(filter.includes('212') && filter.includes('160') && filter.includes('23'))) continue;
            const slab = pad.querySelector(':scope > .slab');
            if (!slab) continue;
            const b = slab.getBoundingClientRect();
            const cx = b.left + b.width / 2, cy = b.top + b.height / 2;
            const hw = b.width / 2, hh = b.height / 2;
            if (hw < 2 || hh < 2) continue;
            const cs = getComputedStyle(pad);
            const c = parseInt(cs.getPropertyValue('--c'), 10);
            const r = parseInt(cs.getPropertyValue('--r'), 10);
            for (let y = b.top + 4; y <= b.bottom - 4; y += 7) {
              for (let x = b.left + 4; x <= b.right - 4; x += 7) {
                if (Math.abs(x - cx) / hw + Math.abs(y - cy) / hh > 0.9) continue;
                if (!open(x, y, c, r)) continue;
                return {x, y, c, r};
              }
            }
          }
          return null;
        }""",
        rect,
    )


def any_visible_gold_point(page):
    return gold_point_inside(
        page,
        {"left": 0, "top": 0, "right": 4000, "bottom": 4000},
    )


_STROKE_RE_SRC = r"""
async () => {
  function parse(text) {
    if (!text) return null;
    const stroke = text.match(/stroke\s*=\s*['"]#([0-9a-fA-F]{6})['"]/);
    const width = text.match(/stroke-width\s*=\s*['"]([0-9.]+)['"]/);
    const dash = /stroke-dasharray\s*=/.test(text);
    const fill = text.match(/fill\s*=\s*['"]#([0-9a-fA-F]{6})['"]/);
    const opacity = text.match(/fill-opacity\s*=\s*['"]([0-9.]+)['"]/);
    return {
      stroke: stroke ? stroke[1].toLowerCase() : null,
      width: width ? Number(width[1]) : null,
      dashed: dash,
      fill: fill ? fill[1].toLowerCase() : null,
      fillOpacity: opacity ? Number(opacity[1]) : null,
      text: text.slice(0, 240)
    };
  }
  async function read(img) {
    if (!img) return null;
    const attr = img.getAttribute('src') || '';
    if (attr.startsWith('data:')) {
      const comma = attr.indexOf(',');
      const body = comma >= 0 ? attr.slice(comma + 1) : attr;
      try { return parse(decodeURIComponent(body)); } catch (err) { return parse(body); }
    }
    try {
      const res = await fetch(img.src);
      return parse(await res.text());
    } catch (err) {
      return {error: String(err), src: attr.slice(0, 80)};
    }
  }
  const chosenPad = document.querySelector('#townMap .pad.is-chosen');
  const chosen = chosenPad && chosenPad.querySelector(':scope > .mark');
  const gold = [...document.querySelectorAll('#townMap .pad.is-empty-hot > .mark')].find((img) => {
    const pad = img.closest('.pad');
    return pad && !pad.classList.contains('is-chosen');
  });
  const map = document.getElementById('townMap');
  const bg = map ? getComputedStyle(map).backgroundColor : '';
  return {chosen: await read(chosen), gold: await read(gold), background: bg};
}
"""


def chosen_mark_paint(page):
    return page.evaluate(_STROKE_RE_SRC)


def focus_ring_delta(page, cell_x, cell_y):
    """Viewport delta from the focus ring centre to the top-face diamond centre.

    The top face sits 10 viewBox units above the slab bbox centre. The ring
    is measured from :focus-visible::after, scaled by the button's rendered
    size so a stage transform is included.
    """
    return page.evaluate(
        """([c, r]) => {
          const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
            const cs = getComputedStyle(el);
            return parseInt(cs.getPropertyValue('--c'), 10) === c
              && parseInt(cs.getPropertyValue('--r'), 10) === r;
          });
          if (!pad) return {error: 'missing pad'};
          const slab = pad.querySelector(':scope > .slab');
          const btn = pad.querySelector(':scope > .cell-btn');
          if (!slab || !btn) return {error: 'missing slab or button'};
          btn.focus({focusVisible: true});
          const after = getComputedStyle(btn, '::after');
          const painted = after && after.content && after.content !== 'none' && after.content !== 'normal';
          const btnBox = btn.getBoundingClientRect();
          const slabBox = slab.getBoundingClientRect();
          const scaleX = btn.offsetWidth > 0 ? btnBox.width / btn.offsetWidth : 1;
          const scaleY = btn.offsetHeight > 0 ? btnBox.height / btn.offsetHeight : 1;
          const ringW = (parseFloat(after.width) || 0) * scaleX;
          const ringH = (parseFloat(after.height) || 0) * scaleY;
          const ringLeft = btnBox.left + (parseFloat(after.left) || 0) * scaleX;
          const ringTop = btnBox.top + (parseFloat(after.top) || 0) * scaleY;
          const ringCx = ringLeft + ringW / 2;
          const ringCy = ringTop + ringH / 2;
          const face = 10 * (slabBox.width / 168);
          const hitCx = slabBox.left + slabBox.width / 2;
          const hitCy = slabBox.top + slabBox.height / 2 - face;
          return {
            painted: !!painted,
            content: after ? after.content : '',
            dx: ringCx - hitCx,
            dy: ringCy - hitCy,
            ring: {x: ringCx, y: ringCy, w: ringW, h: ringH},
            hit: {x: hitCx, y: hitCy},
            face
          };
        }""",
        [cell_x, cell_y],
    )


def hidden_tab_state(page):
    return page.evaluate(
        r"""
() => {
  function tabbable(el) {
    if (!el || el.disabled) return false;
    const tag = el.tagName;
    const native = tag === 'BUTTON' || tag === 'A' || tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA';
    if (!native && el.tabIndex < 0) return false;
    if (el.tabIndex < 0) return false;
    for (let node = el; node; node = node.parentElement) {
      if (node.inert) return false;
      const cs = getComputedStyle(node);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    }
    return true;
  }
  function label(el) {
    return (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 16);
  }
  const drawer = document.getElementById('dr');
  const buttons = drawer ? [...drawer.querySelectorAll('button')] : [];
  const rotate = document.getElementById('ktRotate');
  const rotateBits = rotate ? [...rotate.querySelectorAll('button, a, input, select, textarea, [tabindex]')] : [];
  return {
    drawerCount: buttons.length,
    drawerTab: buttons.filter(tabbable).map(label),
    drawerOpen: !!(drawer && drawer.classList.contains('o')),
    drawerPointer: drawer ? getComputedStyle(drawer).pointerEvents : 'missing',
    rotateDisplay: rotate ? getComputedStyle(rotate).display : 'missing',
    rotateInert: !!(rotate && (rotate.inert || rotate.getAttribute('aria-hidden') === 'true')),
    rotateTab: rotateBits.filter(tabbable).length,
    rotateText: rotate ? (rotate.textContent || '') : ''
  };
}
"""
    )


def set_rotate_shown(page, shown):
    page.evaluate(
        """(shown) => {
          const el = document.getElementById('ktRotate');
          if (!el) return;
          if (shown) el.style.display = 'block';
          else el.style.display = '';
        }""",
        shown,
    )
