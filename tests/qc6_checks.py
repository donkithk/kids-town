"""Geometry helpers for the QC6 tap, contrast, focus, and inert cases.

Product code is not imported. Callers pass a Playwright page that is already
on the town map.
"""
from __future__ import annotations

import math
import struct
import zlib

REQUIRED_STROKE = (0x7C, 0x2D, 0x12)  # #7c2d12
GOLD_STROKE = (0xD4, 0xA0, 0x17)  # #d4a017
RING_CREAM = (0xFF, 0xF8, 0xE7)  # #fff8e7 inner focus stroke
RING_BROWN = (0x6B, 0x4F, 0x2A)  # #6b4f2a outer focus stroke
GRASS_FALLBACK = (0x7E, 0xAE, 0x52)  # #7eae52
GOLD_FILL = (0xFF, 0xF3, 0xC4)  # #fff3c4
GOLD_FILL_ALPHA = 0.62
# Backgrounds that sit against the selected line. Dark gold is only required
# where a sample actually lands on it.
ADJACENT_BACKGROUNDS = {
    "grass": (0x7E, 0xAE, 0x52),  # #7eae52 outer grass
    "empty": (0xD5, 0xE6, 0xB4),  # #d5e6b4 empty cell fill
    "gold": (0xF2, 0xDF, 0x97),  # #f2df97 gold cell fill
    "dark-gold": (0xEA, 0xD3, 0x81),  # #ead381
}


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


def hex_of(rgb):
    if not rgb:
        return None
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def nearest_background(rgb, limit=36):
    """Name of a known adjacent fill, or None when the pixel is something else."""
    if not rgb:
        return None
    best_name = None
    best = limit * limit + 1
    for name, color in ADJACENT_BACKGROUNDS.items():
        dist = sum((rgb[i] - color[i]) ** 2 for i in range(3))
        if dist < best:
            best = dist
            best_name = name
    if best_name is None or best > limit * limit:
        return None
    return best_name


def _paeth(left, up, up_left):
    estimate = left + up - up_left
    da = abs(estimate - left)
    db = abs(estimate - up)
    dc = abs(estimate - up_left)
    if da <= db and da <= dc:
        return left
    if db <= dc:
        return up
    return up_left


def png_rgb(data):
    """Decode an 8-bit RGB or RGBA PNG. Returns width, height, rows of RGB tuples."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a png")
    pos = 8
    width = height = color_type = None
    chunks = []
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
            if bit_depth != 8 or color_type not in (2, 6):
                raise ValueError(f"unsupported png {bit_depth} {color_type}")
        elif kind == b"IDAT":
            chunks.append(chunk)
        elif kind == b"IEND":
            break
    channels = 3 if color_type == 2 else 4
    raw = zlib.decompress(b"".join(chunks))
    stride = width * channels
    rows = []
    index = 0
    previous = bytearray(stride)
    for _y in range(height):
        filt = raw[index]
        index += 1
        row = bytearray(raw[index : index + stride])
        index += stride
        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up = previous[x]
            up_left = previous[x - channels] if x >= channels else 0
            if filt == 0:
                pass
            elif filt == 1:
                row[x] = (row[x] + left) & 255
            elif filt == 2:
                row[x] = (row[x] + up) & 255
            elif filt == 3:
                row[x] = (row[x] + ((left + up) // 2)) & 255
            elif filt == 4:
                row[x] = (row[x] + _paeth(left, up, up_left)) & 255
            else:
                raise ValueError(f"png filter {filt}")
        previous = row
        if channels == 4:
            rows.append([tuple(row[x : x + 3]) for x in range(0, stride, 4)])
        else:
            rows.append([tuple(row[x : x + 3]) for x in range(0, stride, 3)])
    return width, height, rows


def _median_rgb(pixels):
    if not pixels:
        return None
    channels = list(zip(*pixels))
    return tuple(sorted(channel)[len(channel) // 2] for channel in channels)


def selected_mark_geometry(page):
    """Viewport diamond of the chosen mark. Vertices follow the painted top face."""
    return page.evaluate(
        r"""
() => {
  const pad = document.querySelector('#townMap .pad.is-chosen');
  if (!pad) return null;
  const mark = pad.querySelector(':scope > .mark');
  if (!mark || mark.hidden) return null;
  const box = mark.getBoundingClientRect();
  const cs = getComputedStyle(pad);
  const c = parseInt(cs.getPropertyValue('--c'), 10);
  const r = parseInt(cs.getPropertyValue('--r'), 10);
  const left = box.left, top = box.top, w = box.width, h = box.height;
  const cx = left + w / 2;
  const cy = top + h * (50 / 120);
  return {
    c, r,
    edge: c === 0 || r === 0 || c === 7 || r === 7,
    left, top, width: w, height: h,
    cx, cy,
    verts: [
      {x: cx, y: top},
      {x: left + w, y: cy},
      {x: cx, y: top + h * (100 / 120)},
      {x: left, y: cy}
    ]
  };
}
"""
    )


def _rgb_dist(left, right):
    return sum((left[i] - right[i]) ** 2 for i in range(3))


def sample_line_backgrounds(png_bytes, geom, clip, stroke_rgb=None):
    """Pixel colours on the selected line and the fills actually beside it.

    Samples sit in CSS pixels. The line sample is the centreline pixel closest
    to the computed stroke (a neighbour's fill can cover the shared edge).
    Background samples are 10–22px outside the diamond, past the stroke and
    its drop shadow. A fill counts only when several pixels match it, so a
    couple of antialiased specks are not a background.
    """
    width, height, rows = png_rgb(png_bytes)
    origin_x = clip["x"]
    origin_y = clip["y"]

    def at(x, y):
        ix = int(round(x - origin_x))
        iy = int(round(y - origin_y))
        if ix < 0 or iy < 0 or ix >= width or iy >= height:
            return None
        return rows[iy][ix]

    verts = [(point["x"], point["y"]) for point in geom["verts"]]
    center = (geom["cx"], geom["cy"])
    stroke_pixels = []
    buckets = {name: [] for name in ADJACENT_BACKGROUNDS}
    for index, start in enumerate(verts):
        end = verts[(index + 1) % 4]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1:
            continue
        nx, ny = -dy / length, dx / length
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        if (mid_x + nx - center[0]) ** 2 + (mid_y + ny - center[1]) ** 2 < (
            mid_x - nx - center[0]
        ) ** 2 + (mid_y - ny - center[1]) ** 2:
            nx, ny = -nx, -ny
        for step in range(1, 9):
            t = step / 9
            x = start[0] + dx * t
            y = start[1] + dy * t
            band = []
            for offset in range(-4, 5):
                pixel = at(x + nx * offset, y + ny * offset)
                if not pixel:
                    continue
                if stroke_rgb:
                    band.append((_rgb_dist(pixel, stroke_rgb), pixel))
                else:
                    band.append((-_line_score(pixel), pixel))
            if band:
                band.sort(key=lambda item: item[0])
                stroke_pixels.append(band[0][1])
            for dist in (10, 14, 18, 22):
                pixel = at(x + nx * dist, y + ny * dist)
                name = nearest_background(pixel)
                if name:
                    buckets[name].append(pixel)
    present = {
        name: pixels for name, pixels in buckets.items() if len(pixels) >= 8
    }
    # Shared edges are covered by the neighbour's fill. Keep the samples that
    # still match the computed stroke; those are the edges this cell paints.
    matched = stroke_pixels
    if stroke_rgb:
        near = [pixel for pixel in stroke_pixels if _rgb_dist(pixel, stroke_rgb) <= 55 * 55]
        if len(near) >= 6:
            matched = near
    return {
        "stroke": _median_rgb(matched),
        "strokeCount": len(matched),
        "backgrounds": {
            name: {"color": _median_rgb(pixels), "count": len(pixels)}
            for name, pixels in present.items()
        },
    }


def _line_score(rgb):
    """How far a pixel is from the nearest named fill. The stroke scores higher."""
    return min(
        sum((rgb[i] - color[i]) ** 2 for i in range(3))
        for color in ADJACENT_BACKGROUNDS.values()
    )


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


def gold_point_inside(page, rect, limit=1):
    """A visible gold-diamond point inside rect that elementFromPoint leaves on the map.

    ``limit`` 1 returns that point or None, the same shape as before.
    A larger limit returns a list. Those extra points skip buttons that
    are not the cell's own button, and take at most two points per cell.
    """
    if not rect:
        return None if limit == 1 else []
    return page.evaluate(
        """(args) => {
          const rect = args.rect;
          const limit = args.limit || 1;
          const map = document.getElementById('townMap');
          const village = document.getElementById('village');
          if (!map || !village) return limit === 1 ? null : [];
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
          const found = [];
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
            let taken = 0;
            let nextPad = false;
            for (let y = b.top + 4; y <= b.bottom - 4 && !nextPad; y += 7) {
              for (let x = b.left + 4; x <= b.right - 4; x += 7) {
                if (Math.abs(x - cx) / hw + Math.abs(y - cy) / hh > 0.9) continue;
                if (!open(x, y, c, r)) continue;
                if (limit > 1) {
                  const el = document.elementFromPoint(x, y);
                  const btn = el && el.closest && el.closest('button');
                  if (btn && !(btn.classList.contains('cell-btn') && btn.closest('.pad') === pad)) {
                    continue;
                  }
                }
                const point = {x, y, c, r};
                if (limit === 1) return point;
                found.push(point);
                taken += 1;
                if (found.length >= limit) return found;
                if (taken >= 2) { nextPad = true; break; }
              }
            }
          }
          if (limit === 1) return null;
          return found;
        }""",
        {"rect": rect, "limit": limit},
    )


def any_visible_gold_point(page):
    return gold_point_inside(
        page,
        {"left": 0, "top": 0, "right": 4000, "bottom": 4000},
    )


def visible_gold_points(page, limit=8):
    """Several visible gold points, skipping buttons that are not that cell."""
    return gold_point_inside(
        page,
        {"left": 0, "top": 0, "right": 4000, "bottom": 4000},
        limit=limit,
    ) or []


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
  const rotateBits = [];
  if (rotate) {
    rotateBits.push(rotate);
    rotateBits.push(...rotate.querySelectorAll('button, a, input, select, textarea, [tabindex]'));
  }
  const box = drawer ? drawer.getBoundingClientRect() : null;
  const rcs = rotate ? getComputedStyle(rotate) : null;
  return {
    drawerCount: buttons.length,
    drawerTab: buttons.filter(tabbable).map(label),
    drawerOpen: !!(drawer && drawer.classList.contains('o')),
    drawerClass: drawer ? drawer.className : 'missing',
    drawerPointer: drawer ? getComputedStyle(drawer).pointerEvents : 'missing',
    drawerLeft: box ? box.left : null,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    rotateDisplay: rcs ? rcs.display : 'missing',
    rotateVisibility: rcs ? rcs.visibility : 'missing',
    rotateInert: !!(rotate && (rotate.inert || rotate.getAttribute('aria-hidden') === 'true')),
    rotateTab: rotateBits.filter(tabbable).length,
    rotateText: rotate ? (rotate.textContent || '') : ''
  };
}
"""
    )


def border_edge_points(rect):
    """Corners and edge midpoints: on the border, 0.5px inside, and 1.5px inside.

    Inside is toward the rectangle centre, along both axes at a corner and
    along the normal at an edge midpoint.
    """
    left = rect["left"]
    top = rect["top"]
    right = rect["right"]
    bottom = rect["bottom"]
    cx = (left + right) / 2
    cy = (top + bottom) / 2
    insets = (("edge", 0.0), ("in-0.5", 0.5), ("in-1.5", 1.5))
    corners = (
        ("top-left", left, top, 1, 1),
        ("top-right", right, top, -1, 1),
        ("bottom-left", left, bottom, 1, -1),
        ("bottom-right", right, bottom, -1, -1),
    )
    edges = (
        ("top", cx, top, 0, 1),
        ("bottom", cx, bottom, 0, -1),
        ("left", left, cy, 1, 0),
        ("right", right, cy, -1, 0),
    )
    points = []
    for name, x, y, ix, iy in corners + edges:
        for label, dist in insets:
            points.append({
                "name": f"{name}-{label}",
                "x": x + ix * dist,
                "y": y + iy * dist,
            })
    return points


def bar_gap_band(page):
    """Strip between the bottom bar's lower edge and the map's bottom edge.

    The height is the bar's bottom offset inside the map (about 8px before
    the stage scale). It is not the village scrollport.
    """
    return page.evaluate(
        r"""
() => {
  function shown(el) {
    if (!el) return null;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return null;
    if (Number(cs.opacity) === 0) return null;
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) return null;
    return box;
  }
  const map = shown(document.getElementById('townMap'));
  const bar = shown(document.getElementById('readyBar'))
    || shown(document.getElementById('uxPlaceBar'));
  if (!map || !bar) return null;
  const top = bar.bottom;
  const bottom = map.bottom;
  if (bottom - top < 2) return null;
  return {
    left: map.left,
    right: map.right,
    top,
    bottom,
    height: bottom - top,
    barTop: bar.top,
    barBottom: bar.bottom,
    mapBottom: map.bottom
  };
}
"""
    )


def cell_clip_band(page):
    """Grass below the overflow that actually clips cells, down to the map.

    The clip is whichever ancestor cuts the pads, discovered from computed
    overflow. Callers must not treat a particular id as the clip.
    """
    return page.evaluate(
        r"""
() => {
  const mapEl = document.getElementById('townMap');
  const pad = document.querySelector('#townMap .pad');
  if (!mapEl || !pad) return null;
  const map = mapEl.getBoundingClientRect();
  let clipBottom = null;
  let clipLeft = map.left;
  let clipRight = map.right;
  for (let node = pad.parentElement; node && node !== document.body; node = node.parentElement) {
    const cs = getComputedStyle(node);
    const box = node.getBoundingClientRect();
    const clipsY = cs.overflowY === 'hidden' || cs.overflowY === 'auto'
      || cs.overflowY === 'scroll' || cs.overflowY === 'clip';
    const clipsX = cs.overflowX === 'hidden' || cs.overflowX === 'auto'
      || cs.overflowX === 'scroll' || cs.overflowX === 'clip';
    if (clipsY && box.height > 2) {
      clipBottom = clipBottom == null ? box.bottom : Math.min(clipBottom, box.bottom);
    }
    if (clipsX && box.width > 2) {
      clipLeft = Math.max(clipLeft, box.left);
      clipRight = Math.min(clipRight, box.right);
    }
  }
  const footer = document.getElementById('ktFooter');
  const footTop = footer ? footer.getBoundingClientRect().top : map.bottom;
  if (clipBottom == null) return null;
  const top = clipBottom;
  const bottom = Math.min(map.bottom, footTop);
  if (bottom - top < 8) return null;
  return {
    left: clipLeft,
    right: clipRight,
    top,
    bottom,
    clipBottom,
    mapBottom: map.bottom
  };
}
"""
    )


def cell_visibility(page, cell_x, cell_y, x=None, y=None):
    """How many sampled pixels of a cell diamond sit inside the real clip.

    The clip is the tightest overflow ancestor of the pads. A cell that is
    entirely outside that clip has visible == 0. `pointOnVisible` is true
    only when (x, y) lies on that visible fragment.
    """
    return page.evaluate(
        r"""
([c, r, px, py]) => {
  const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
    const cs = getComputedStyle(el);
    return parseInt(cs.getPropertyValue('--c'), 10) === c
      && parseInt(cs.getPropertyValue('--r'), 10) === r;
  });
  if (!pad) return {error: 'missing pad', visible: 0, samples: 0, pointOnVisible: false};
  const slab = pad.querySelector(':scope > .slab');
  if (!slab) return {error: 'missing slab', visible: 0, samples: 0, pointOnVisible: false};
  const box = slab.getBoundingClientRect();
  const cx = box.left + box.width / 2;
  const cy = box.top + box.height * (50 / 120);
  const hw = box.width / 2;
  const hh = box.height * (50 / 120);
  let clip = null;
  for (let node = pad.parentElement; node && node !== document.body; node = node.parentElement) {
    const cs = getComputedStyle(node);
    const b = node.getBoundingClientRect();
    const clipsY = ['hidden', 'auto', 'scroll', 'clip'].includes(cs.overflowY);
    const clipsX = ['hidden', 'auto', 'scroll', 'clip'].includes(cs.overflowX);
    if (!clipsX && !clipsY) continue;
    const next = {
      left: clipsX ? b.left : -1e9,
      right: clipsX ? b.right : 1e9,
      top: clipsY ? b.top : -1e9,
      bottom: clipsY ? b.bottom : 1e9
    };
    if (!clip) clip = next;
    else {
      clip = {
        left: Math.max(clip.left, next.left),
        right: Math.min(clip.right, next.right),
        top: Math.max(clip.top, next.top),
        bottom: Math.min(clip.bottom, next.bottom)
      };
    }
  }
  function insideClip(x, y) {
    return !!clip && x >= clip.left && x <= clip.right && y >= clip.top && y <= clip.bottom;
  }
  function insideDiamond(x, y) {
    if (hw < 2 || hh < 2) return false;
    return Math.abs(x - cx) / hw + Math.abs(y - cy) / hh <= 1;
  }
  let samples = 0;
  let visible = 0;
  const step = 4;
  for (let y = box.top; y <= box.top + box.height; y += step) {
    for (let x = box.left; x <= box.left + box.width; x += step) {
      if (!insideDiamond(x, y)) continue;
      samples += 1;
      if (insideClip(x, y)) visible += 1;
    }
  }
  const pointOnVisible = px != null && py != null && insideDiamond(px, py) && insideClip(px, py);
  return {visible, samples, pointOnVisible, clip};
}
""",
        [cell_x, cell_y, x, y],
    )


def village_box(page):
    """Border box of `#village`, the scrollport that clips cells."""
    return page.evaluate(
        """() => {
          const el = document.getElementById('village');
          if (!el) return null;
          const box = el.getBoundingClientRect();
          if (box.width < 2 || box.height < 2) return null;
          return {
            left: box.left, top: box.top, right: box.right, bottom: box.bottom,
            width: box.width, height: box.height
          };
        }"""
    )


def cell_under_point(page, x, y):
    """Cell the iso hit-test would choose, or None.

    The point has to sit inside the `#village` border box. The cell is the
    same rounding the map uses (half a step from the grid origin), so a
    point the map itself would miss is not a visible cell.
    """
    return page.evaluate(
        """([px, py]) => {
          const village = document.getElementById('village');
          const pad = document.querySelector('#townMap .pad');
          if (!village || !pad) return null;
          const v = village.getBoundingClientRect();
          if (px < v.left || px > v.right || py < v.top || py > v.bottom) return null;
          if (v.width < 1 || v.height < 1 || pad.offsetWidth < 1) return null;
          const scaleX = v.width / village.offsetWidth || 1;
          const scaleY = v.height / village.offsetHeight || 1;
          const local = {
            x: (px - v.left) / scaleX + village.scrollLeft,
            y: (py - v.top) / scaleY + village.scrollTop
          };
          const s = pad.offsetWidth / 160;
          const stepX = 84 * s;
          const stepY = 50 * s;
          if (!stepX || !stepY) return null;
          const originX = pad.offsetLeft + 80 * s;
          const originY = pad.offsetTop + 121 * s;
          const dx = local.x - originX;
          const dy = local.y - originY;
          const cf = 0.5 * (dx / stepX + dy / stepY);
          const rf = 0.5 * (dy / stepY - dx / stepX);
          const c = Math.round(cf);
          const r = Math.round(rf);
          if (Math.abs(cf - c) > 0.501 || Math.abs(rf - r) > 0.501) return null;
          if (c < 0 || r < 0 || c >= 8 || r >= 8) return null;
          return {c, r};
        }""",
        [x, y],
    )


def scroll_for_cell_point(page, x, y, cell_x, cell_y):
    """Scroll `#village` so the iso hit-test maps (x, y) to that cell.

    The point also has to stay inside the village border box. Leaves the
    scroll on the fitted value when one exists.
    """
    return page.evaluate(
        """([px, py, wantC, wantR]) => {
          const village = document.getElementById('village');
          const pad = document.querySelector('#townMap .pad');
          if (!village || !pad) return {ok: false, reason: 'missing'};
          const max = Math.max(0, village.scrollHeight - village.clientHeight);
          const saved = village.scrollTop;
          function hit() {
            const v = village.getBoundingClientRect();
            if (px < v.left || px > v.right || py < v.top || py > v.bottom) return null;
            if (v.width < 1 || pad.offsetWidth < 1) return null;
            const scaleX = v.width / village.offsetWidth || 1;
            const scaleY = v.height / village.offsetHeight || 1;
            const localY = (py - v.top) / scaleY + village.scrollTop;
            const localX = (px - v.left) / scaleX + village.scrollLeft;
            const s = pad.offsetWidth / 160;
            const stepX = 84 * s;
            const stepY = 50 * s;
            const dx = localX - (pad.offsetLeft + 80 * s);
            const dy = localY - (pad.offsetTop + 121 * s);
            const cf = 0.5 * (dx / stepX + dy / stepY);
            const rf = 0.5 * (dy / stepY - dx / stepX);
            const c = Math.round(cf);
            const r = Math.round(rf);
            if (Math.abs(cf - c) > 0.501 || Math.abs(rf - r) > 0.501) return null;
            if (c !== wantC || r !== wantR) return null;
            return 0.501 - Math.max(Math.abs(cf - c), Math.abs(rf - r));
          }
          let best = null;
          let bestSlack = -1;
          for (let s = 0; s <= max; s += 1) {
            village.scrollTop = s;
            const slack = hit();
            if (slack != null && slack > bestSlack) {
              bestSlack = slack;
              best = s;
            }
          }
          if (best == null) {
            village.scrollTop = saved;
            return {ok: false, max, scroll: saved};
          }
          village.scrollTop = best;
          const v = village.getBoundingClientRect();
          return {
            ok: true,
            max,
            scroll: village.scrollTop,
            slack: bestSlack,
            villageBottom: v.bottom
          };
        }""",
        [x, y, cell_x, cell_y],
    )


def _inclusive_span(lo, hi):
    """Integers ix with lo <= ix <= hi."""
    first = math.ceil(lo - 1e-9)
    last = math.floor(hi + 1e-9)
    if first < lo:
        first += 1
    if last > hi:
        last -= 1
    if first > last:
        return None
    return first, last


def _past_edge(edge, outward, pixels):
    """Integer at least `pixels` px outside `edge`.

    outward +1 grows (bottom, right): ``ceil(edge) + pixels``.
    outward -1 shrinks (top, left): ``floor(edge) - pixels``.
    ``pixels`` of 1 is the first coordinate a click can be required to
    reach. The open interval (edge, that integer) is the 0–1px band
    browsers still hit-test as the control, and is not a sample.
    """
    if pixels < 1:
        raise ValueError(pixels)
    if outward > 0:
        return math.ceil(edge) + pixels
    return math.floor(edge) - pixels


def point_rect_gap(rect, x, y):
    """Distance from a point to the closed border box. 0 when inside or on it."""
    dx = 0.0
    if x < rect["left"]:
        dx = rect["left"] - x
    elif x > rect["right"]:
        dx = x - rect["right"]
    dy = 0.0
    if y < rect["top"]:
        dy = rect["top"] - y
    elif y > rect["bottom"]:
        dy = y - rect["bottom"]
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return math.hypot(dx, dy)


def in_fractional_outer_band(rect, x, y):
    """True when the point is outside the rect by less than 1px.

    Hit-testing still targets the control there (a bar top of 555.55 keeps
    y=555, a tools left of 1134.55 keeps x=1134). Must-reach samples skip
    this band. A point inside or on the rect is not in the band.
    """
    gap = point_rect_gap(rect, x, y)
    return 0.0 < gap < 1.0


def inclusive_border_samples(rect):
    """Integer pixels on the inclusive border: corners and edge midpoints.

    A pixel is included only when it lies inside the border box, so the
    edge row or column itself is blocked and a half-pixel outside is not.
    """
    span_x = _inclusive_span(rect["left"], rect["right"])
    span_y = _inclusive_span(rect["top"], rect["bottom"])
    if span_x is None or span_y is None:
        return []
    x0, x1 = span_x
    y0, y1 = span_y
    mx = (x0 + x1) // 2
    my = (y0 + y1) // 2
    specs = (
        ("top", mx, y0),
        ("bottom", mx, y1),
        ("left", x0, my),
        ("right", x1, my),
        ("top-left", x0, y0),
        ("top-right", x1, y0),
        ("bottom-left", x0, y1),
        ("bottom-right", x1, y1),
    )
    points = []
    seen = set()
    for name, x, y in specs:
        if (x, y) in seen:
            continue
        if not (rect["left"] <= x <= rect["right"] and rect["top"] <= y <= rect["bottom"]):
            continue
        seen.add((x, y))
        points.append({"name": name, "x": float(x), "y": float(y)})
    return points


def outside_edge_points(rect):
    """Integers at least 1px outside each edge, at the integer midpoint.

    The first sample on each side is ``floor(top) - 1``, ``ceil(bottom) + 1``,
    ``floor(left) - 1``, or ``ceil(right) + 1``. A second sample is one pixel
    further out. Nothing in the 0–1px band outside the rect is returned, and
    the sample stays on the edge's span rather than past a corner.
    """
    span_x = _inclusive_span(rect["left"], rect["right"])
    span_y = _inclusive_span(rect["top"], rect["bottom"])
    if span_x is None or span_y is None:
        return []
    x0, x1 = span_x
    y0, y1 = span_y
    mx = (x0 + x1) // 2
    my = (y0 + y1) // 2
    points = []
    for pixels in (1, 2):
        candidates = (
            (f"top-{pixels}", mx, _past_edge(rect["top"], -1, pixels)),
            (f"bottom-{pixels}", mx, _past_edge(rect["bottom"], 1, pixels)),
            (f"left-{pixels}", _past_edge(rect["left"], -1, pixels), my),
            (f"right-{pixels}", _past_edge(rect["right"], 1, pixels), my),
        )
        for name, x, y in candidates:
            if in_fractional_outer_band(rect, x, y):
                continue
            if point_rect_gap(rect, x, y) + 1e-6 < pixels:
                continue
            outside_x = x < rect["left"] or x > rect["right"]
            outside_y = y < rect["top"] or y > rect["bottom"]
            if outside_x == outside_y:
                continue
            if outside_x and not (rect["top"] <= y <= rect["bottom"]):
                continue
            if outside_y and not (rect["left"] <= x <= rect["right"]):
                continue
            points.append({"name": name, "x": float(x), "y": float(y), "step": pixels})
    return points


def integer_border_row(rect):
    """Integer-pixel points on the top border row of a live rect.

    Clicks land on whole pixels. The row is the integer y that sits on the
    top edge and still inside the 1px inset the hit test currently ignores.
    """
    top = rect["top"]
    left = rect["left"]
    right = rect["right"]
    y = int(top) if abs(top - round(top)) < 1e-6 else int(top + 1 - 1e-9)
    if y < top - 1e-6 or y >= top + 1:
        y = int(round(top))
    points = []
    x = int(left) if abs(left - round(left)) < 1e-6 else int(left + 1 - 1e-9)
    end = int(right)
    while x <= end:
        points.append({"name": f"top-int-{x}", "x": float(x), "y": float(y)})
        x += 1
    return points


def focus_ring_shape(page, cell_x, cell_y):
    """Cell top-face diamond and the painted focus diamond, in viewport pixels.

    The ring diamond is the outer stroke path of the focus-visible ring.
    A layout box that is only a clip is not the ring. The cell diamond is the
    slab's top face: full slab width, 100/120 of the slab height, centred
    10 viewBox units above the slab centre.
    """
    return page.evaluate(
        r"""
([c, r]) => {
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
  const painted = !!(after && after.content && after.content !== 'none' && after.content !== 'normal');
  const btnBox = btn.getBoundingClientRect();
  const slabBox = slab.getBoundingClientRect();
  const scaleX = btn.offsetWidth > 0 ? btnBox.width / btn.offsetWidth : 1;
  const scaleY = btn.offsetHeight > 0 ? btnBox.height / btn.offsetHeight : 1;
  const ringLeft = btnBox.left + (parseFloat(after.left) || 0) * scaleX;
  const ringTop = btnBox.top + (parseFloat(after.top) || 0) * scaleY;
  const ringBoxW = (parseFloat(after.width) || 0) * scaleX;
  const ringBoxH = (parseFloat(after.height) || 0) * scaleY;
  const bg = (after && after.backgroundImage) || '';
  let decoded = bg;
  try { decoded = decodeURIComponent(bg); } catch (err) { decoded = bg; }
  const vb = /viewBox=['"]\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)/.exec(decoded);
  const vbW = vb ? Number(vb[1]) : ringBoxW;
  const vbH = vb ? Number(vb[2]) : ringBoxH;
  function mapPoint(px, py) {
    return {
      x: ringLeft + (vbW ? (px / vbW) * ringBoxW : px),
      y: ringTop + (vbH ? (py / vbH) * ringBoxH : py)
    };
  }
  const polyRe = /<polygon\b([^>]*)>/g;
  const polys = [];
  let match;
  while ((match = polyRe.exec(decoded))) {
    const attrs = match[1];
    const points = /points=['"]([^'"]+)['"]/.exec(attrs);
    if (!points) continue;
    const nums = points[1].trim().split(/[\s,]+/).map(Number);
    const pts = [];
    for (let i = 0; i + 1 < nums.length; i += 2) {
      if (Number.isFinite(nums[i]) && Number.isFinite(nums[i + 1])) {
        pts.push(mapPoint(nums[i], nums[i + 1]));
      }
    }
    const stroke = /stroke=['"]#([0-9a-fA-F]{6})['"]/.exec(attrs);
    const width = /stroke-width=['"]([0-9.]+)['"]/.exec(attrs);
    polys.push({
      pts,
      stroke: stroke ? stroke[1].toLowerCase() : null,
      width: width ? Number(width[1]) : null,
      dashed: /stroke-dasharray=/.test(attrs)
    });
  }
  function tipsFrom(pts) {
    if (!pts || pts.length < 4) return null;
    const north = pts.reduce((a, b) => (b.y < a.y ? b : a));
    const south = pts.reduce((a, b) => (b.y > a.y ? b : a));
    const east = pts.reduce((a, b) => (b.x > a.x ? b : a));
    const west = pts.reduce((a, b) => (b.x < a.x ? b : a));
    return {N: north, E: east, S: south, W: west};
  }
  let ringTips = tipsFrom(polys.length ? polys[0].pts : null);
  if (!ringTips && ringBoxW > 2 && ringBoxH > 2) {
    const rcx = ringLeft + ringBoxW / 2;
    const rcy = ringTop + ringBoxH / 2;
    ringTips = {
      N: {x: rcx, y: ringTop},
      E: {x: ringLeft + ringBoxW, y: rcy},
      S: {x: rcx, y: ringTop + ringBoxH},
      W: {x: ringLeft, y: rcy}
    };
  }
  const face = 10 * (slabBox.width / 168);
  const cx = slabBox.left + slabBox.width / 2;
  const cy = slabBox.top + slabBox.height / 2 - face;
  const halfW = slabBox.width / 2;
  const halfH = slabBox.height * (50 / 120);
  const cellTips = {
    N: {x: cx, y: cy - halfH},
    E: {x: cx + halfW, y: cy},
    S: {x: cx, y: cy + halfH},
    W: {x: cx - halfW, y: cy}
  };
  const ringCx = ringTips ? (ringTips.E.x + ringTips.W.x) / 2 : null;
  const ringCy = ringTips ? (ringTips.N.y + ringTips.S.y) / 2 : null;
  return {
    painted,
    error: ringTips ? null : 'focus ring diamond was not painted',
    outer: polys[0] ? {stroke: polys[0].stroke, width: polys[0].width, dashed: polys[0].dashed} : null,
    inner: polys[1] ? {stroke: polys[1].stroke, width: polys[1].width, dashed: polys[1].dashed} : null,
    dx: ringCx == null ? null : ringCx - cx,
    dy: ringCy == null ? null : ringCy - cy,
    cell: {
      cx, cy, halfW, halfH,
      width: halfW * 2,
      height: halfH * 2,
      tips: cellTips
    },
    ring: ringTips ? {
      cx: ringCx,
      cy: ringCy,
      width: ringTips.E.x - ringTips.W.x,
      height: ringTips.S.y - ringTips.N.y,
      tips: ringTips
    } : null
  };
}
""",
        [cell_x, cell_y],
    )


def sample_selected_edges(png_bytes, geom, clip):
    """Brown vs gold pixels along the middle of each selected-diamond edge.

    Five samples per edge, away from the corners. Each sample looks 1px
    either side of the centreline so a 3px stroke is hit, and a neighbour's
    wider dash is not counted unless it covers that centreline.
    """
    width, height, rows = png_rgb(png_bytes)
    origin_x = clip["x"]
    origin_y = clip["y"]

    def at(x, y):
        ix = int(round(x - origin_x))
        iy = int(round(y - origin_y))
        if ix < 0 or iy < 0 or ix >= width or iy >= height:
            return None
        return rows[iy][ix]

    verts = [(point["x"], point["y"]) for point in geom["verts"]]
    names = ("NE", "SE", "SW", "NW")
    found = {}
    for index, name in enumerate(names):
        start = verts[index]
        end = verts[(index + 1) % 4]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / length, dx / length
        brown = gold = other = 0
        # Nine samples along the middle of the edge, clear of the corners.
        for step_index in range(9):
            step = 0.2 + step_index * (0.6 / 8)
            x = start[0] + dx * step
            y = start[1] + dy * step
            best_brown = 10 ** 9
            best_gold = 10 ** 9
            for offset in (-1, 0, 1):
                pixel = at(x + nx * offset, y + ny * offset)
                if not pixel:
                    continue
                best_brown = min(best_brown, _rgb_dist(pixel, REQUIRED_STROKE))
                best_gold = min(best_gold, _rgb_dist(pixel, GOLD_STROKE))
            if best_brown <= 55 * 55 and best_brown <= best_gold:
                brown += 1
            elif best_gold <= 55 * 55:
                gold += 1
            else:
                other += 1
        found[name] = {"brown": brown, "gold": gold, "other": other}
    return found


# Screenshot noise and antialiasing. A real fill moves pixels much further.
_UNCHANGED_DIST = 20 * 20
# Ring ink is read only outside the cell, out to this many pixels.
_RING_OUTSIDE_BAND = 8.0


def _diamond_outside(cell, x, y):
    """Signed pixels from the top-face edge. Negative is inside the cell."""
    half_w = cell.get("halfW") or 0
    half_h = cell.get("halfH") or 0
    if half_w < 1 or half_h < 1:
        return None
    span = abs(x - cell["cx"]) / half_w + abs(y - cell["cy"]) / half_h
    apothem = (half_w * half_h) / math.hypot(half_w, half_h)
    return (span - 1.0) * apothem


def _in_badge(face, x, y):
    box = face.get("badge") if face else None
    if not box:
        return False
    return (box["left"] - 2) <= x <= (box["right"] + 2) and (box["top"] - 2) <= y <= (
        box["bottom"] + 2
    )


def ring_pixel_report(png_before, png_after, cell, clip):
    """Ring ink outside the cell only, in the band out to 8px.

    Badge, ground, and sprite pixels inside the polygon are ignored, so a
    light badge cannot count as ``#fff8e7``. A pixel counts only when it
    changed from the unfocused baseline and reads as ring cream or ring
    brown, not ``#7c2d12``. Overlap is that ink within 1px of the edge,
    where the selected line's outer fringe sits.
    """
    _bw, _bh, before_rows = png_rgb(png_before)
    width, height, after_rows = png_rgb(png_after)
    half_w = cell.get("halfW") or 0
    half_h = cell.get("halfH") or 0
    if half_w < 2 or half_h < 2 or not before_rows or not after_rows:
        return {"cream": 0, "brown": 0, "overlap": 0, "solid": 0}
    origin_x = clip["x"]
    origin_y = clip["y"]
    cream = brown = overlap = solid = 0
    for iy, row in enumerate(after_rows):
        for ix, pixel in enumerate(row):
            x = origin_x + ix
            y = origin_y + iy
            outside = _diamond_outside(cell, x, y)
            if outside is None:
                continue
            if -2.5 <= outside <= 1.5 and _clear_brown(pixel):
                solid += 1
            if outside <= 0 or outside > _RING_OUTSIDE_BAND:
                continue
            before = _shot_pixel(before_rows, clip, x, y)
            if not before or _rgb_dist(before, pixel) <= _UNCHANGED_DIST:
                continue
            if not _ring_ink(pixel):
                continue
            if _rgb_dist(pixel, RING_CREAM) <= _rgb_dist(pixel, RING_BROWN):
                cream += 1
            else:
                brown += 1
            if outside <= 1.0:
                overlap += 1
    return {"cream": cream, "brown": brown, "overlap": overlap, "solid": solid}


def cell_top_face(page, cell_x, cell_y):
    """Slab top-face diamond in viewport pixels, plus the 「此格」 badge box.

    The diamond is the cell, not the chosen-mark element. A padded mark box
    is larger than the cell and must not be used as the edge.
    """
    return page.evaluate(
        r"""
([c, r]) => {
  const pad = [...document.querySelectorAll('#townMap .pad')].find((el) => {
    const cs = getComputedStyle(el);
    return parseInt(cs.getPropertyValue('--c'), 10) === c
      && parseInt(cs.getPropertyValue('--r'), 10) === r;
  });
  if (!pad) return {error: 'missing pad'};
  const slab = pad.querySelector(':scope > .slab');
  if (!slab) return {error: 'missing slab'};
  const box = slab.getBoundingClientRect();
  if (box.width < 2 || box.height < 2) return {error: 'empty slab'};
  const face = 10 * (box.width / 168);
  const cx = box.left + box.width / 2;
  const cy = box.top + box.height / 2 - face;
  const halfW = box.width / 2;
  const halfH = box.height * (50 / 120);
  const badge = pad.querySelector(':scope > .badge');
  let badgeBox = null;
  if (badge && !badge.hidden) {
    const b = badge.getBoundingClientRect();
    if (b.width > 2 && b.height > 2) {
      badgeBox = {
        left: b.left, top: b.top, right: b.right, bottom: b.bottom,
        text: (badge.textContent || '').trim()
      };
    }
  }
  return {
    c, r, cx, cy, halfW, halfH,
    width: halfW * 2,
    height: halfH * 2,
    edge: c === 0 || r === 0 || c === 7 || r === 7,
    gold: pad.classList.contains('is-empty-hot'),
    chosen: pad.classList.contains('is-chosen'),
    tips: {
      N: {x: cx, y: cy - halfH},
      E: {x: cx + halfW, y: cy},
      S: {x: cx, y: cy + halfH},
      W: {x: cx - halfW, y: cy}
    },
    badge: badgeBox
  };
}
""",
        [cell_x, cell_y],
    )


def _shot_pixel(rows, clip, x, y):
    width = len(rows[0]) if rows else 0
    height = len(rows)
    ix = int(round(x - clip["x"]))
    iy = int(round(y - clip["y"]))
    if ix < 0 or iy < 0 or ix >= width or iy >= height:
        return None
    return rows[iy][ix]


def _clear_brown(pixel):
    return bool(pixel) and _rgb_dist(pixel, REQUIRED_STROKE) <= 40 * 40


def _clear_gold(pixel):
    if not pixel:
        return False
    gold = _rgb_dist(pixel, GOLD_STROKE)
    brown = _rgb_dist(pixel, REQUIRED_STROKE)
    return gold <= 42 * 42 and gold + 40 < brown


def _ring_cream(pixel):
    """Inner band of the focus ring. The selected line's fringe is not cream."""
    if not pixel:
        return False
    cream = _rgb_dist(pixel, RING_CREAM)
    return cream <= 40 * 40 and cream <= _rgb_dist(pixel, RING_BROWN)


def _ring_ink(pixel):
    if not pixel or _clear_brown(pixel):
        return False
    if _ring_cream(pixel):
        return True
    brown = _rgb_dist(pixel, RING_BROWN)
    return brown <= 42 * 42 and brown + 80 < _rgb_dist(pixel, REQUIRED_STROKE)


def _face_edges(face):
    """Five points along each diamond edge, with an outward unit normal."""
    tips = face["tips"]
    order = ("N", "E", "S", "W")
    names = ("NE", "SE", "SW", "NW")
    center = (face["cx"], face["cy"])
    edges = []
    for index, name in enumerate(names):
        start = tips[order[index]]
        end = tips[order[(index + 1) % 4]]
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / length, dx / length
        mid_x = (start["x"] + end["x"]) / 2
        mid_y = (start["y"] + end["y"]) / 2
        if (mid_x + nx - center[0]) ** 2 + (mid_y + ny - center[1]) ** 2 < (
            mid_x - nx - center[0]
        ) ** 2 + (mid_y - ny - center[1]) ** 2:
            nx, ny = -nx, -ny
        points = []
        for step in range(5):
            t = 0.25 + step * 0.125
            points.append((start["x"] + dx * t, start["y"] + dy * t))
        edges.append({"name": name, "points": points, "nx": nx, "ny": ny})
    return edges


def edge_outward_points(face, distance):
    """Midpoint of each edge, stepped outside the cell along the normal."""
    points = []
    for edge in _face_edges(face):
        x, y = edge["points"][2]
        points.append({
            "name": edge["name"],
            "x": x + edge["nx"] * distance,
            "y": y + edge["ny"] * distance,
        })
    return points


def _interior_points(face):
    """Centre, and points 8px inside each edge."""
    points = [{"name": "centre", "x": face["cx"], "y": face["cy"]}]
    for edge in _face_edges(face):
        x, y = edge["points"][2]
        points.append({
            "name": edge["name"],
            "x": x - edge["nx"] * 8,
            "y": y - edge["ny"] * 8,
        })
        x0, y0 = edge["points"][1]
        x1, y1 = edge["points"][3]
        for label, px, py in (("a", x0, y0), ("b", x1, y1)):
            points.append({
                "name": f"{edge['name']}-{label}",
                "x": px - edge["nx"] * 8,
                "y": py - edge["ny"] * 8,
            })
    return points


def _interior_sample(before_rows, after_rows, face, clip, point, allow_badge):
    """One interior point against the unselected, unfocused baseline.

    The 「此格」 badge is allowed to change only when the cell is selected.
    """
    after = _shot_pixel(after_rows, clip, point["x"], point["y"])
    before = _shot_pixel(before_rows, clip, point["x"], point["y"])
    badge = bool(allow_badge and _in_badge(face, point["x"], point["y"]))
    if before and after:
        dist = _rgb_dist(before, after)
    else:
        dist = 10 ** 9
    # A sprite that is already near #7c2d12 is not a new fill.
    appeared = _clear_brown(after) and not _clear_brown(before)
    return {
        "name": point["name"],
        "brown": appeared,
        "near": badge or dist <= _UNCHANGED_DIST,
        "badge": badge,
        "dist": 0 if dist >= 10 ** 9 else int(dist ** 0.5),
        "after": hex_of(after),
        "before": hex_of(before),
    }


def selection_pixel_report(png_before, png_after, face, clip, allow_badge=True):
    """Interior diff, stroke width, and badge from two CSS-pixel screenshots.

    Positive offsets are outside the cell edge. The stroke centreline sits
    0.5–1.5px inside, which is judged by the outer brown edge landing 0–1px
    outside the cell. The run is 2–4px wide. Interior points at least 8px
    in must match the baseline; the badge region is skipped only when selected.
    """
    _bw, _bh, before_rows = png_rgb(png_before)
    _aw, _ah, after_rows = png_rgb(png_after)
    interior = [
        _interior_sample(before_rows, after_rows, face, clip, point, allow_badge)
        for point in _interior_points(face)
    ]
    edges = {}
    for edge in _face_edges(face):
        widths = []
        outers = []
        insets = []
        brown = gold = 0
        for x, y in edge["points"]:
            flags = []
            for offset in range(-12, 13):
                pixel = _shot_pixel(
                    after_rows, clip,
                    x + edge["nx"] * offset,
                    y + edge["ny"] * offset,
                )
                flags.append(_clear_brown(pixel))
            run = _run_touching_edge(flags, zero_index=12)
            if run is None:
                widths.append(0)
                outers.append(None)
                insets.append(None)
            else:
                start, end = run
                widths.append(end - start + 1)
                outers.append(end - 12)
                insets.append(12 - (start + end) / 2.0)
            best_brown = 10 ** 9
            best_gold = 10 ** 9
            for offset in (-2, -1, 0, 1):
                pixel = _shot_pixel(
                    after_rows, clip,
                    x + edge["nx"] * offset,
                    y + edge["ny"] * offset,
                )
                if not pixel:
                    continue
                best_brown = min(best_brown, _rgb_dist(pixel, REQUIRED_STROKE))
                best_gold = min(best_gold, _rgb_dist(pixel, GOLD_STROKE))
            if best_brown <= 42 * 42 and best_brown <= best_gold:
                brown += 1
            elif _clear_gold_dist(best_gold):
                gold += 1
        finite = [(outer, inset) for outer, inset in zip(outers, insets) if outer is not None]
        widest = max(range(len(widths)), key=lambda index: widths[index]) if widths else 0
        edges[edge["name"]] = {
            "width": max(widths) if widths else 0,
            "outer": max((item[0] for item in finite), default=None),
            "inset": None if not widths else insets[widest],
            "brown": brown,
            "gold": gold,
            "samples": len(edge["points"]),
        }
    badge = {"present": False, "cream": 0, "brown": 0, "text": ""}
    box = face.get("badge")
    if box:
        badge["present"] = True
        badge["text"] = box.get("text") or ""
        cream = (255, 246, 210)
        y = box["top"]
        while y <= box["bottom"]:
            x = box["left"]
            while x <= box["right"]:
                pixel = _shot_pixel(after_rows, clip, x, y)
                if _clear_brown(pixel):
                    badge["brown"] += 1
                elif pixel and _rgb_dist(pixel, cream) <= 48 * 48:
                    badge["cream"] += 1
                x += 1
            y += 1
    return {"interior": interior, "edges": edges, "badge": badge}


def _clear_gold_dist(gold_dist):
    return gold_dist <= 42 * 42


def _run_touching_edge(flags, zero_index):
    """Inclusive index run of brown pixels that contains the edge, or the nearest run."""
    runs = []
    start = None
    for index, flag in enumerate(flags):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(flags) - 1))
    if not runs:
        return None
    for run in runs:
        if run[0] <= zero_index <= run[1]:
            return run
    return min(runs, key=lambda run: min(abs(run[0] - zero_index), abs(run[1] - zero_index)))


def focus_pixel_report(png_before, png_after, face, clip, allow_badge=False):
    """Interior diff and the ring's inner edge from screenshots.

    Interior points at least 8px in must match the unselected, unfocused
    baseline. The badge region is ignored only when ``allow_badge`` is set
    (the cell is selected). Ring ink is a pixel that changed into ``#fff8e7``
    or ``#6b4f2a``. The inner edge is about 2px outside and must not sit on
    the selected line. A ``#7c2d12`` pixel more than 1px outside the cell is
    the filled focus diamond, not the dashed ring.
    """
    _bw, _bh, before_rows = png_rgb(png_before)
    _aw, _ah, after_rows = png_rgb(png_after)
    interior = [
        _interior_sample(before_rows, after_rows, face, clip, point, allow_badge)
        for point in _interior_points(face)
    ]
    edges = {}
    for edge in _face_edges(face):
        firsts = []
        brown_outside = 0
        ink = 0
        for x, y in edge["points"]:
            first = None
            for offset in range(0, 11):
                pixel = _shot_pixel(
                    after_rows, clip,
                    x + edge["nx"] * offset,
                    y + edge["ny"] * offset,
                )
                before = _shot_pixel(
                    before_rows, clip,
                    x + edge["nx"] * offset,
                    y + edge["ny"] * offset,
                )
                changed = bool(
                    before and pixel and _rgb_dist(before, pixel) > _UNCHANGED_DIST
                )
                if offset >= 2 and changed and _clear_brown(pixel):
                    brown_outside += 1
                if first is None and changed and _ring_ink(pixel):
                    first = offset
            if first is not None:
                ink += 1
                firsts.append(first)
        edges[edge["name"]] = {
            "first": firsts,
            "ink": ink,
            "samples": len(edge["points"]),
            "brown_outside": brown_outside,
        }
    return {"interior": interior, "edges": edges}


# Whole-screen stroke count. Tighter than the fill check so sprite wood
# (#6b4428, about 36 away from #7c2d12) is not the selected line.
_STROKE_COUNT_TOL = 8 * 8


def count_stroke_pixels(png_bytes):
    """Pixels that are the selected outline ``#7c2d12``."""
    _width, _height, rows = png_rgb(png_bytes)
    count = 0
    for row in rows:
        for pixel in row:
            if pixel and _rgb_dist(pixel, REQUIRED_STROKE) <= _STROKE_COUNT_TOL:
                count += 1
    return count


def changed_pixel_count(png_before, png_after):
    """Pixels whose colour moved past the screenshot noise tolerance."""
    _bw, _bh, before_rows = png_rgb(png_before)
    width, height, after_rows = png_rgb(png_after)
    if not before_rows or not after_rows or len(before_rows) != height or len(before_rows[0]) != width:
        return None
    count = 0
    for iy, row in enumerate(after_rows):
        before = before_rows[iy]
        for ix, pixel in enumerate(row):
            if _rgb_dist(before[ix], pixel) > _UNCHANGED_DIST:
                count += 1
    return count


def paint_layer_state(page):
    """Computed box of the chosen-mark layer and the focus-ring layer.

    An SVG ``hidden`` attribute does not imply ``display: none``. A layer is
    gone only when its computed display is ``none`` or it has no box.
    """
    return page.evaluate(
        r"""() => {
          function describe(id) {
            const el = document.getElementById(id);
            if (!el) return {id, present: false, gone: true, display: 'none', width: 0, height: 0};
            const cs = getComputedStyle(el);
            const box = el.getBoundingClientRect();
            const gone = cs.display === 'none' || cs.visibility === 'hidden'
              || box.width < 1 || box.height < 1;
            return {
              id,
              present: true,
              tag: el.tagName,
              gone,
              display: cs.display,
              hidden: el.hasAttribute('hidden'),
              width: box.width,
              height: box.height,
              left: box.left,
              top: box.top
            };
          }
          const marks = [...document.querySelectorAll('#townMap .pad > .mark')].filter((el) => {
            const cs = getComputedStyle(el);
            const box = el.getBoundingClientRect();
            return cs.display !== 'none' && cs.visibility !== 'hidden' && box.width > 1 && box.height > 1;
          });
          return {
            mark: describe('chosenMarkPaint'),
            ring: describe('focusRingPaint'),
            visibleCellMarks: marks.length
          };
        }"""
    )


def ring_layer_pixels(page):
    """Painted pixels on the focus-ring layer itself, not the map under it.

    A canvas reports non-transparent backing-store pixels. Any other visible
    ring element reports its CSS-pixel box area. ``display: none`` is 0.
    """
    return page.evaluate(
        r"""() => {
          function layerPixels(el) {
            if (!el) return {pixels: 0, display: 'none', tag: null, hidden: true};
            const cs = getComputedStyle(el);
            const box = el.getBoundingClientRect();
            const gone = cs.display === 'none' || cs.visibility === 'hidden'
              || box.width < 1 || box.height < 1;
            if (gone) {
              return {pixels: 0, display: cs.display, tag: el.tagName, hidden: el.hasAttribute('hidden')};
            }
            if (el.tagName === 'CANVAS' && el.width > 0 && el.height > 0) {
              let pixels = 0;
              try {
                const data = el.getContext('2d').getImageData(0, 0, el.width, el.height).data;
                for (let i = 3; i < data.length; i += 4) {
                  if (data[i] >= 128) pixels += 1;
                }
              } catch (err) {
                return {pixels: -1, display: cs.display, tag: el.tagName, error: String(err)};
              }
              return {pixels, display: cs.display, tag: 'CANVAS', width: box.width, height: box.height};
            }
            return {
              pixels: Math.round(box.width * box.height),
              display: cs.display,
              tag: el.tagName,
              width: box.width,
              height: box.height,
              hidden: el.hasAttribute('hidden')
            };
          }
          const ring = layerPixels(document.getElementById('focusRingPaint'));
          const lift = layerPixels(document.getElementById('focusRingLift'));
          return {
            pixels: (ring.pixels || 0) + (lift.pixels || 0),
            display: ring.display,
            tag: ring.tag,
            hidden: ring.hidden,
            width: ring.width,
            height: ring.height,
            lift: lift.pixels || 0,
            liftDisplay: lift.display
          };
        }"""
    )


def _edge_slots(face):
    """Diamond edges as start/end, outward normal, and length."""
    tips = face["tips"]
    order = ("N", "E", "S", "W")
    names = ("NE", "SE", "SW", "NW")
    center = (face["cx"], face["cy"])
    slots = []
    for index, name in enumerate(names):
        start = tips[order[index]]
        end = tips[order[(index + 1) % 4]]
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        mid_x = (start["x"] + end["x"]) / 2
        mid_y = (start["y"] + end["y"]) / 2
        if (mid_x + nx - center[0]) ** 2 + (mid_y + ny - center[1]) ** 2 < (
            mid_x - nx - center[0]
        ) ** 2 + (mid_y - ny - center[1]) ** 2:
            nx, ny = -nx, -ny
        slots.append({
            "name": name,
            "sx": start["x"],
            "sy": start["y"],
            "dx": dx,
            "dy": dy,
            "length": length,
            "nx": nx,
            "ny": ny,
        })
    return slots


def _slot_of(face, x, y, vertex_clear):
    """Edge whose line is closest, when the point is clear of both vertices."""
    best = None
    for slot in _edge_slots(face):
        length = slot["length"]
        t = ((x - slot["sx"]) * slot["dx"] + (y - slot["sy"]) * slot["dy"]) / (length * length)
        if t < 0 or t > 1:
            continue
        along = t * length
        if along < vertex_clear or along > length - vertex_clear:
            continue
        cross = abs((x - slot["sx"]) * slot["dy"] - (y - slot["sy"]) * slot["dx"]) / length
        if best is None or cross < best[0]:
            best = (cross, slot["name"], along)
    if best is None:
        return None
    return best[1], best[2]


def stroke_near_cell(png_bytes, face, clip, band=6.0):
    """``#7c2d12`` pixels just outside or on the cell, per edge.

    ``outer`` is the furthest brown pixel's signed distance on that edge.
    The selected line's outer edge is 0–1.5 screen px outside the live face.
    """
    width, height, rows = png_rgb(png_bytes)
    edges = {slot["name"]: [] for slot in _edge_slots(face)}
    total = 0
    for iy, row in enumerate(rows):
        y = clip["y"] + iy + 0.5
        for ix, pixel in enumerate(row):
            if not pixel or _rgb_dist(pixel, REQUIRED_STROKE) > _STROKE_COUNT_TOL:
                continue
            x = clip["x"] + ix + 0.5
            outside = _diamond_outside(face, x, y)
            if outside is None or outside < -2.5 or outside > band:
                continue
            slot = _slot_of(face, x, y, 3.0)
            if not slot:
                continue
            edges[slot[0]].append(outside)
            total += 1
    report = {}
    for name, distances in edges.items():
        report[name] = {
            "count": len(distances),
            "outer": None if not distances else max(distances),
        }
    report["total"] = total
    return report


def _clip_pixel(rows, clip, x, y):
    if not rows:
        return None
    ix = int(math.floor(x - clip["x"]))
    iy = int(math.floor(y - clip["y"]))
    if iy < 0 or iy >= len(rows) or ix < 0 or ix >= len(rows[0]):
        return None
    return rows[iy][ix]


def _device_at(rows, clip, x, y, dpr):
    """Colour of the device pixel that contains a CSS point, and that pixel's centre."""
    if not rows or dpr <= 0:
        return None, None, None
    ix = int(math.floor((x - clip["x"]) * dpr))
    iy = int(math.floor((y - clip["y"]) * dpr))
    if iy < 0 or iy >= len(rows) or ix < 0 or ix >= len(rows[0]):
        return None, None, None
    centre_x = clip["x"] + (ix + 0.5) / dpr
    centre_y = clip["y"] + (iy + 0.5) / dpr
    return rows[iy][ix], centre_x, centre_y


def ring_inner_gaps(png_before, png_after, face, clip, vertex_clear=3.0, samples=24):
    """Inner gap of the painted ring, in screen px, on each edge.

    At least ``samples`` stations per edge, each at least ``vertex_clear``
    screen px from both vertices. Each station walks outward in 0.1 screen
    px steps. The gap is the first step that lands on the cream band
    (``#fff8e7``) and stays cream for the next few steps. A brown fringe
    from the selected line is not the ring. The result is screen px.
    """
    _bw, _bh, before_rows = png_rgb(png_before)
    _aw, _ah, after_rows = png_rgb(png_after)
    report = {}
    if not before_rows or not after_rows or len(before_rows) != len(after_rows):
        return {slot["name"]: {"min": None, "samples": 0} for slot in _edge_slots(face)}
    for slot in _edge_slots(face):
        length = slot["length"]
        # The painted dash stops short of each vertex. Stay at least 3px
        # out, and also clear of that intentional corner gap.
        clear = max(vertex_clear, length * 0.12)
        span = length - 2 * clear
        gaps = []
        if span <= 1:
            report[slot["name"]] = {"min": None, "samples": 0, "max": None}
            continue
        count = max(samples, 20)
        for index in range(count):
            along = clear + span * (index + 0.5) / count
            t = along / length
            ox = slot["sx"] + slot["dx"] * t
            oy = slot["sy"] + slot["dy"] * t
            def _cream_at(dist):
                x = ox + slot["nx"] * dist
                y = oy + slot["ny"] * dist
                after = _clip_pixel(after_rows, clip, x, y)
                before = _clip_pixel(before_rows, clip, x, y)
                return bool(
                    after and before
                    and _rgb_dist(before, after) > _UNCHANGED_DIST
                    and _ring_cream(after)
                )

            gap = None
            steps = int(_RING_OUTSIDE_BAND / 0.1)
            for step in range(1, steps + 1):
                dist = round(step * 0.1, 1)
                if not _cream_at(dist):
                    continue
                # The cream band is about 3px. A one-pixel fringe does not count.
                run = sum(1 for extra in range(4) if _cream_at(round(dist + extra * 0.1, 1)))
                if run < 3:
                    continue
                gap = dist
                break
            if gap is not None:
                gaps.append(gap)
        report[slot["name"]] = {
            "min": None if not gaps else min(gaps),
            "max": None if not gaps else max(gaps),
            "samples": len(gaps),
            "stations": count,
        }
    return report


def ring_device_gaps(png_before, png_after, face, clip, dpr=1, samples=24):
    """Inner cream edge in screen px, read at device-pixel centres.

    At least 24 stations per edge. Each station is at least 3 screen px
    clear of the corner opening (the unpainted 10% plus 3px). The walk is
    0.1 screen px. The gap is the outside distance of the device-pixel
    centre where three consecutive steps are cream. Min must be ≥2 and
    max ≤4.
    """
    _bw, _bh, before_rows = png_rgb(png_before)
    _aw, _ah, after_rows = png_rgb(png_after)
    dpr = dpr or 1
    report = {}
    if not before_rows or not after_rows or len(before_rows) != len(after_rows):
        return {slot["name"]: {"min": None, "max": None, "samples": 0, "stations": 0}
                for slot in _edge_slots(face)}
    for slot in _edge_slots(face):
        length = slot["length"]
        clear = max(3.0, length * 0.10 + 3.0)
        span = length - 2 * clear
        gaps = []
        count = max(samples, 24)
        if span <= 1:
            report[slot["name"]] = {"min": None, "max": None, "samples": 0, "stations": count}
            continue
        for index in range(count):
            along = clear + span * (index + 0.5) / count
            t = along / length
            ox = slot["sx"] + slot["dx"] * t
            oy = slot["sy"] + slot["dy"] * t

            def _cream_centre(dist, _ox=ox, _oy=oy):
                x = _ox + slot["nx"] * dist
                y = _oy + slot["ny"] * dist
                after, cx, cy = _device_at(after_rows, clip, x, y, dpr)
                before, _bx, _by = _device_at(before_rows, clip, x, y, dpr)
                if not after or not before or not _ring_cream(after):
                    return None
                if _rgb_dist(before, after) <= _UNCHANGED_DIST:
                    return None
                # The gap is the device-pixel centre, not the walk step.
                outside = _diamond_outside(face, cx, cy)
                if outside is None:
                    return None
                return outside

            gap = None
            steps = int(_RING_OUTSIDE_BAND / 0.1)
            run = []
            for step in range(1, steps + 1):
                dist = round(step * 0.1, 1)
                outside = _cream_centre(dist)
                if outside is None:
                    run = []
                    continue
                run.append(outside)
                if len(run) < 3:
                    continue
                # Half-up to 0.1px so 1.75 reports as 1.8, not banker's 1.8/1.2.
                gap = math.floor(run[0] * 10 + 0.5) / 10
                break
            if gap is not None:
                gaps.append(gap)
        ordered = sorted(gaps)
        median = None
        if ordered:
            mid = len(ordered) // 2
            median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
        report[slot["name"]] = {
            "min": None if not gaps else min(gaps),
            "max": None if not gaps else max(gaps),
            "median": None if median is None else round(median, 2),
            "samples": len(gaps),
            "stations": count,
        }
    return report


def _round_pt(value):
    return round(value, 2)


def ring_vertex_gaps(png_before, png_after, face, clip, dpr=1):
    """Straight-line gap between the inner ends of the two cream bands at a tip.

    The gap is not the distance from the tip to a band. Each edge's solid
    run is the cream pixels along that edge. The vertex gap is the screen
    distance between the two run-ends that meet there. Solid fraction is
    the run length divided by the on-screen edge.
    """
    _bw, _bh, before_rows = png_rgb(png_before)
    _aw, _ah, after_rows = png_rgb(png_after)
    dpr = dpr or 1
    empty = {
        "length": None,
        "edges": {},
        "vertices": {},
        "error": "clip size changed",
    }
    if not before_rows or not after_rows or len(before_rows) != len(after_rows):
        return empty
    slots = _edge_slots(face)
    edges = {}
    for slot in slots:
        length = slot["length"]
        step = 0.25
        hits = []
        along = 0.0
        while along <= length:
            t = along / length if length else 0
            bx = slot["sx"] + slot["dx"] * t
            by = slot["sy"] + slot["dy"] * t
            found = None
            offset = 1.5
            while offset <= 6.5:
                x = bx + slot["nx"] * offset
                y = by + slot["ny"] * offset
                after, cx, cy = _device_at(after_rows, clip, x, y, dpr)
                before, _bx, _by = _device_at(before_rows, clip, x, y, dpr)
                if (
                    after and before
                    and _rgb_dist(before, after) > _UNCHANGED_DIST
                    and _ring_cream(after)
                ):
                    found = (cx, cy, along)
                    break
                offset += 0.5
            if found:
                hits.append(found)
            along += step
        if hits:
            start = min(hits, key=lambda item: item[2])
            end = max(hits, key=lambda item: item[2])
            solid = (end[2] - start[2]) / length if length else 0
        else:
            start = end = None
            solid = 0
        edges[slot["name"]] = {
            "length": _round_pt(length),
            "solid": round(solid, 3),
            "start": None if not start else {"x": _round_pt(start[0]), "y": _round_pt(start[1])},
            "end": None if not end else {"x": _round_pt(end[0]), "y": _round_pt(end[1])},
        }
    # NE starts at N and ends at E. SE starts at E and ends at S.
    # SW starts at S and ends at W. NW starts at W and ends at N.
    pairs = {
        "N": ("NW", "end", "NE", "start"),
        "E": ("NE", "end", "SE", "start"),
        "S": ("SE", "end", "SW", "start"),
        "W": ("SW", "end", "NW", "start"),
    }
    vertices = {}
    for name, (edge_a, side_a, edge_b, side_b) in pairs.items():
        a = (edges.get(edge_a) or {}).get(side_a)
        b = (edges.get(edge_b) or {}).get(side_b)
        gap = None
        if a and b:
            gap = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
        vertices[name] = {
            "gap": None if gap is None else round(gap, 2),
            "a": a,
            "b": b,
            "a_edge": edge_a,
            "b_edge": edge_b,
        }
    length = slots[0]["length"] if slots else None
    return {
        "length": None if length is None else _round_pt(length),
        "edges": edges,
        "vertices": vertices,
    }


def stroke_outer_rays(png_bytes, face, clip):
    """Painted outer boundary of ``#7c2d12`` on each edge, in screen px.

    Each station walks out along the normal in 0.02 screen px steps. The
    outer edge is the last step that is still the stroke. That is the
    boundary of the painted pixel, past the pixel centre.
    """
    _width, _height, rows = png_rgb(png_bytes)
    report = {}
    for slot in _edge_slots(face):
        length = slot["length"]
        clear = max(3.0, length * 0.12)
        span = length - 2 * clear
        exits = []
        if span <= 1 or not rows:
            report[slot["name"]] = {"outer": None, "samples": 0}
            continue
        for index in range(24):
            along = clear + span * (index + 0.5) / 24
            t = along / length
            ox = slot["sx"] + slot["dx"] * t
            oy = slot["sy"] + slot["dy"] * t
            last = None
            for step in range(0, 160):
                dist = step * 0.02
                x = ox + slot["nx"] * dist
                y = oy + slot["ny"] * dist
                pixel = _clip_pixel(rows, clip, x, y)
                if pixel and _rgb_dist(pixel, REQUIRED_STROKE) <= _STROKE_COUNT_TOL:
                    last = dist
                elif last is not None and dist > last + 0.4:
                    break
            if last is not None:
                exits.append(last)
        report[slot["name"]] = {
            "outer": None if not exits else round(max(exits), 2),
            "samples": len(exits),
        }
    return report


def bar_ink_count(png_bytes, shot_clip, guard):
    """Selected-line, ring-cream, and ring-brown pixels inside ``guard``.

    Tolerances stay inside the bar fill (``#faf6ef``) and the wood text
    (``#8b5e3c``), so a status-sentence change is not ink.
    """
    _width, _height, rows = png_rgb(png_bytes)
    if not rows:
        return 0
    count = 0
    y = guard["y"]
    while y < guard["y"] + guard["height"]:
        x = guard["x"]
        while x < guard["x"] + guard["width"]:
            pixel = _clip_pixel(rows, shot_clip, x + 0.5, y + 0.5)
            if pixel:
                stroke = _rgb_dist(pixel, REQUIRED_STROKE) <= _STROKE_COUNT_TOL
                cream = _rgb_dist(pixel, RING_CREAM) <= 5 * 5
                brown = _rgb_dist(pixel, RING_BROWN) <= 12 * 12
                if stroke or cream or brown:
                    count += 1
            x += 1
        y += 1
    return count


def paint_overlay_count(png_before, png_after, shot_clip, guard):
    """New selected-line or ring-cream pixels inside ``guard``.

    ``shot_clip`` is the screenshot origin. ``guard`` is the inset bar or
    drawer, in the same viewport coordinates. The ready bar's wood text
    matches the ring's brown, so only ``#7c2d12`` and ``#fff8e7`` count.
    """
    _bw, _bh, before_rows = png_rgb(png_before)
    width, height, after_rows = png_rgb(png_after)
    if not before_rows or len(before_rows) != height or len(before_rows[0]) != width:
        return None
    count = 0
    y = guard["y"]
    while y < guard["y"] + guard["height"]:
        x = guard["x"]
        while x < guard["x"] + guard["width"]:
            after = _clip_pixel(after_rows, shot_clip, x, y)
            before = _clip_pixel(before_rows, shot_clip, x, y)
            if after and before and _rgb_dist(before, after) > _UNCHANGED_DIST:
                # The bar fill is #faf6ef, about 10px from the ring cream, and
                # its wood text matches the ring brown. Only the solid dash
                # and the #7c2d12 line count.
                stroke = _rgb_dist(after, REQUIRED_STROKE) <= _STROKE_COUNT_TOL
                cream = _rgb_dist(after, RING_CREAM) <= 5 * 5
                if stroke or cream:
                    count += 1
            x += 1
        y += 1
    return count


def _point_in_rect(rect, x, y):
    return rect["left"] <= x <= rect["right"] and rect["top"] <= y <= rect["bottom"]


def ring_edge_report(png_before, png_after, face, visible, clip, solids=None, vertex_clear=3.0):
    """Whether the cream band is clipped inside the visible map.

    Stations sit on the solid part of each edge, at least 3 screen px from
    the vertices and clear of the corner dash. A station inside ``visible``
    and not under solid UI must be ring ink. A station outside the visible
    map may be missing; that is the only allowed clip.
    """
    _bw, _bh, before_rows = png_rgb(png_before)
    _aw, _ah, after_rows = png_rgb(png_after)
    inside_missing = inside_hit = outside_missing = outside_hit = 0
    details = []
    if not before_rows or not after_rows or len(before_rows) != len(after_rows):
        return {"error": "clip size changed", "inside_missing": -1, "inside_hit": 0,
                "outside_missing": 0, "outside_hit": 0}
    for slot in _edge_slots(face):
        length = slot["length"]
        clear = max(vertex_clear, length * 0.12)
        span = length - 2 * clear
        if span <= 1:
            continue
        for index in range(12):
            along = clear + span * (index + 0.5) / 12
            t = along / length
            ox = slot["sx"] + slot["dx"] * t
            oy = slot["sy"] + slot["dy"] * t
            for dist in (3.4, 3.8, 4.2):
                x = ox + slot["nx"] * dist
                y = oy + slot["ny"] * dist
                after = _clip_pixel(after_rows, clip, x, y)
                before = _clip_pixel(before_rows, clip, x, y)
                ink = bool(
                    after and before
                    and _rgb_dist(before, after) > _UNCHANGED_DIST
                    and _ring_ink(after)
                )
                inside = _point_in_rect(visible, x, y)
                if inside and solids:
                    if any(_point_in_rect(rect, x, y) for rect in solids if rect):
                        continue
                if inside:
                    if ink:
                        inside_hit += 1
                    else:
                        inside_missing += 1
                        if len(details) < 4:
                            details.append(f"{slot['name']}@{dist:.1f}")
                elif ink:
                    outside_hit += 1
                else:
                    outside_missing += 1
    return {
        "inside_missing": inside_missing,
        "inside_hit": inside_hit,
        "outside_missing": outside_missing,
        "outside_hit": outside_hit,
        "details": details,
    }


def point_is_ring_ink(png_bytes, points, clip):
    """Whether each viewport point's pixel is focus-ring cream or brown."""
    width, height, rows = png_rgb(png_bytes)
    origin_x = clip["x"]
    origin_y = clip["y"]
    found = []
    for point in points:
        ix = int(round(point["x"] - origin_x))
        iy = int(round(point["y"] - origin_y))
        pixel = None
        if 0 <= ix < width and 0 <= iy < height:
            pixel = rows[iy][ix]
        ring = False
        if pixel:
            cream = _rgb_dist(pixel, RING_CREAM)
            brown = _rgb_dist(pixel, RING_BROWN)
            near = cream <= 40 * 40 or brown <= 45 * 45
            if "r" in point:
                sprite = (int(point["r"]), int(point["g"]), int(point["b"]))
                # A sprite that is already brown must not count as the ring.
                ring = near and min(cream, brown) + 120 < _rgb_dist(pixel, sprite)
            else:
                ring = near
        found.append({"ring": ring, "rgb": pixel, "x": point["x"], "y": point["y"], "edge": point.get("edge")})
    return found
