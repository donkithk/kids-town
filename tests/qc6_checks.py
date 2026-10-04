"""Geometry helpers for the QC6 tap, contrast, focus, and inert cases.

Product code is not imported. Callers pass a Playwright page that is already
on the town map.
"""
from __future__ import annotations

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


def ring_pixel_report(png_bytes, cell, clip):
    """Ring-coloured pixels inside the selected stroke, and whether both ring inks show.

    The solid line is a 3px band centred on the cell diamond. A ring pixel
    on or inside that band overlaps the selected outline.
    """
    width, height, rows = png_rgb(png_bytes)
    half_w = cell.get("halfW") or 0
    half_h = cell.get("halfH") or 0
    if half_w < 2 or half_h < 2:
        return {"cream": 0, "brown": 0, "overlap": 0, "solid": 0}
    cx = cell["cx"]
    cy = cell["cy"]
    apothem = (half_w * half_h) / ((half_w * half_w + half_h * half_h) ** 0.5)
    band = 1 + (1.5 / apothem if apothem else 0)
    origin_x = clip["x"]
    origin_y = clip["y"]
    cream = brown = overlap = solid = 0
    for iy, row in enumerate(rows):
        for ix, pixel in enumerate(row):
            x = origin_x + ix
            y = origin_y + iy
            span = abs(x - cx) / half_w + abs(y - cy) / half_h
            dist_cream = _rgb_dist(pixel, RING_CREAM)
            dist_brown = _rgb_dist(pixel, RING_BROWN)
            dist_solid = _rgb_dist(pixel, REQUIRED_STROKE)
            if dist_solid <= 55 * 55 and 0.82 <= span <= 1.18:
                solid += 1
            ringish = None
            if dist_cream <= 40 * 40 and dist_cream <= dist_solid:
                ringish = "cream"
            elif dist_brown <= 45 * 45 and dist_brown <= dist_solid:
                ringish = "brown"
            if ringish == "cream":
                cream += 1
            elif ringish == "brown":
                brown += 1
            if ringish and span <= band:
                overlap += 1
    return {"cream": cream, "brown": brown, "overlap": overlap, "solid": solid}


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
