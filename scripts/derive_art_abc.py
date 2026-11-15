#!/usr/bin/env python3
"""Deterministic cutouts of the locked 2026-11-04 A–C JPEGs.

Originals are never rewritten. This writes three derived PNGs:

  A  ui-town-wood-frame-cutout.png
     Flood-fill the connected cream interior (and the disconnected cream
     margin outside the rounded wood) to alpha 0. The wood rails and the
     dark inner bevel stay opaque. No 9-slice grid is invented.

  B  is not derived. The locked plaza is a painted 6×6 diamond, plank cross,
     and slate ring. It does not register to the live 8×8, and it extends
     outside the map rectangle. This script does not emit a backdrop.

  C  building-adventure-guild-cutout.png
     Flood-fill cream from the canvas edges, punch enclosed cream holes,
     defringe the halo, then crop to the opaque bounding box so the sprite
     is the building rather than a cream square. The stone plinth and any
     painted grass tufts stay; they are not cream.

Thresholds are color distances measured on these files (cream vs wood /
stone), not footprint, anchor, or shadow numbers.
"""
from __future__ import annotations

import hashlib
import os
from collections import deque

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "assets", "art-locked-2026-11-04")
ORIGINAL = os.path.join(ART, "originals")
DERIVED = os.path.join(ART, "derived")

# Cream vs the next material on these JPEGs. See DERIVE.md.
FRAME_CREAM_MAX = 22.0
GUILD_CREAM_MAX = 26.0
GUILD_HOLE_MAX = 16.0
GUILD_FRINGE_MAX = 58.0

LOCKED_SHA256 = {
    "ui-town-wood-frame.jpg": "a5c8cee063d25580469f4309465ce3c02bbceced9bfcfb306826f315611b1fa2",
    "bg-town-plaza.jpg": "57835c6a555e260d6ed688968866087c420ecbf83767413bf8a2e0f5fd29a388",
    "building-adventure-guild.jpg": "f42e42122f8539b85db1f605939e96375d7e59619053f97af79c6b5dafc410e0",
}


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dist(color, ref) -> float:
    return (
        (color[0] - ref[0]) ** 2
        + (color[1] - ref[1]) ** 2
        + (color[2] - ref[2]) ** 2
    ) ** 0.5


def _flood(rgb, alpha, seeds, accept) -> None:
    width, height = rgb.size
    src = rgb.load()
    dst = alpha.load()
    seen = bytearray(width * height)
    queue = deque()
    for x, y in seeds:
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        index = y * width + x
        if seen[index]:
            continue
        seen[index] = 1
        if accept(src[x, y]):
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        dst[x, y] = 0
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            index = ny * width + nx
            if seen[index]:
                continue
            seen[index] = 1
            if accept(src[nx, ny]):
                queue.append((nx, ny))


def _neighbors4(x, y, width, height):
    if x > 0:
        yield x - 1, y
    if x + 1 < width:
        yield x + 1, y
    if y > 0:
        yield x, y - 1
    if y + 1 < height:
        yield x, y + 1


def derive_frame(path: str) -> Image.Image:
    rgb = Image.open(path).convert("RGB")
    width, height = rgb.size
    if (width, height) != (1280, 720):
        raise SystemExit(f"frame is {width}x{height}, expected 1280x720")
    src = rgb.load()
    ref = src[width // 2, height // 2]
    out = rgb.convert("RGBA")
    alpha = out.getchannel("A")

    def cream(color) -> bool:
        return _dist(color, ref) <= FRAME_CREAM_MAX

    _flood(rgb, alpha, [(width // 2, height // 2)], cream)
    # Outer rounded-corner margin is a slightly cooler cream and is not
    # connected to the center. Only seed a corner that is itself cream.
    # The bottom-right canvas corner is wood and must stay opaque.
    def margin_cream(color) -> bool:
        return color[0] > 220 and color[1] > 210 and color[2] > 190 and _dist(color, ref) < 48

    for seed in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        if not margin_cream(src[seed]):
            continue
        corner = src[seed]

        def corner_cream(color, corner=corner) -> bool:
            return _dist(color, corner) <= FRAME_CREAM_MAX and color[0] > 200

        _flood(rgb, alpha, [seed], corner_cream)
    out.putalpha(alpha)
    return out



def _guild_colored(color, ref) -> bool:
    """True when a fringe pixel is paint (banner, grass, glass), not cream halo."""
    r, g, b = (int(color[0]), int(color[1]), int(color[2]))
    if g > r + 12 and g > b + 8 and g > 70:
        return True
    if r > g + 28 and r > b + 28 and r > 120:
        return True
    if b > r + 8 and b > g - 10 and b > 70 and _dist(color, ref) > 40:
        return True
    return False


def derive_guild(path: str) -> Image.Image:
    rgb = Image.open(path).convert("RGB")
    width, height = rgb.size
    if (width, height) != (1024, 1024):
        raise SystemExit(f"guild is {width}x{height}, expected 1024x1024")
    src = rgb.load()
    ref = src[0, 0]
    out = rgb.convert("RGBA")
    alpha = out.getchannel("A")

    def cream(limit):
        def accept(color) -> bool:
            return _dist(color, ref) <= limit

        return accept

    edge = []
    for x in range(width):
        edge.append((x, 0))
        edge.append((x, height - 1))
    for y in range(height):
        edge.append((0, y))
        edge.append((width - 1, y))
    _flood(rgb, alpha, edge, cream(GUILD_CREAM_MAX))
    # Enclosed cream (a chimney opening, a gap under the plinth) is still background.
    holes = []
    alpha_px = alpha.load()
    for y in range(height):
        for x in range(width):
            if alpha_px[x, y] and _dist(src[x, y], ref) <= GUILD_HOLE_MAX:
                holes.append((x, y))
    _flood(rgb, alpha, holes, cream(GUILD_HOLE_MAX))
    # One-pixel halo: cream mixed into the outline becomes partial alpha.
    alpha_px = alpha.load()
    updates = []
    for y in range(height):
        for x in range(width):
            if alpha_px[x, y] == 0:
                continue
            touches = False
            for nx, ny in _neighbors4(x, y, width, height):
                if alpha_px[nx, ny] == 0:
                    touches = True
                    break
            if not touches:
                continue
            color = src[x, y]
            if _guild_colored(color, ref):
                continue
            distance = _dist(color, ref)
            if distance >= GUILD_FRINGE_MAX:
                continue
            span = GUILD_FRINGE_MAX - GUILD_CREAM_MAX
            updates.append((x, y, int(round(255 * (distance - GUILD_CREAM_MAX) / span))))
    for x, y, value in updates:
        alpha_px[x, y] = max(0, min(255, value))
    out.putalpha(alpha)
    bbox = out.getchannel("A").getbbox()
    if not bbox:
        raise SystemExit("guild cutout is empty")
    # Crop to the painted building. The pad anchors the bottom of this crop.
    return out.crop(bbox)


def _write_png(image: Image.Image, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image.save(path, "PNG", optimize=True)


def derive_all() -> None:
    for name, expected in LOCKED_SHA256.items():
        path = os.path.join(ORIGINAL, name)
        actual = _sha256(path)
        if actual != expected:
            raise SystemExit(f"{name} sha256 {actual} != locked {expected}")
    _write_png(derive_frame(os.path.join(ORIGINAL, "ui-town-wood-frame.jpg")), os.path.join(DERIVED, "ui-town-wood-frame-cutout.png"))
    _write_png(
        derive_guild(os.path.join(ORIGINAL, "building-adventure-guild.jpg")),
        os.path.join(DERIVED, "building-adventure-guild-cutout.png"),
    )


if __name__ == "__main__":
    derive_all()
