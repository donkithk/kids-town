# Sprites

See [`../ASSETS.md`](../ASSETS.md).

## Approved product sprites

The user formally approved the soft v1 four for product / #20. The formal files are tight RGBA cutouts of that same art (real alpha, no baked checkerboard), suitable to overlay on grass / the battle background. The scorpion is the original soft v1 only.

- `sprite-hero.png` — hero
- `sprite-boar.png` — **APPROVED** 野豬（soft v1 RGBA cutout）
- `sprite-wolf.png` — **APPROVED** 野狼（soft v1 RGBA cutout）
- `sprite-bear.png` — **APPROVED** 白熊（soft v1 RGBA cutout）
- `sprite-scorpion.png` — **APPROVED** 巨蠍（soft v1 original only, RGBA cutout）

Builder may wire these four monster records to the formal files above. Do not wire annoyed, fierce-v2, or cute-hold.

`preview-monsters/sprite-*-preview.png` still have the old checkerboard baked in. They are history only and **must not** be used as the formal sprites.

## Preview archive (history only, not extra product files)

Soft v1 sources, kept as-is:

- `preview-monsters/sprite-boar-preview.png`
- `preview-monsters/sprite-wolf-preview.png`
- `preview-monsters/sprite-bear-preview.png`
- `preview-monsters/sprite-scorpion-preview.png`
- `preview-monsters/00-preview.html`
- `preview-monsters/sprite-wolf-cute-hold.png` — historical hold of the soft wolf. Not a separate approved file. Do not wire this path.

## Not approved

- `preview-monsters/sprite-scorpion-annoyed-preview.png` — mildly annoyed scorpion. **Not approved.** Do not use it in place of `sprite-scorpion.png`.

## Fierce v2 — discarded direction (archived preview only)

Not for approval and not for product.

- `preview-monsters/sprite-boar-fierce-v2.png`
- `preview-monsters/sprite-wolf-fierce-v2.png`
- `preview-monsters/sprite-bear-fierce-v2.png`
- `preview-monsters/sprite-scorpion-fierce-v2.png`
- `preview-monsters/00-preview-fierce-v2.html`
