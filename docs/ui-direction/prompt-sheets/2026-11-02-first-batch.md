# Prompt sheet — 2026-11-02 first batch (town lock)

**Scope:** Town lock assets only. **Monsters deferred** (chibi hero vs realist wolf mismatch — do not ship mismatched battle sprites; no monster prompts in this sheet).  
**Pixels:** come from the user’s image tool. This sheet is **wording only**.  
**Stage:** 1280×720 · layers: BG art / HTML·CSS UI / sprites · **no text in images**.

---

## Reusable style block (English, ~50 words)

```
Hand-painted cozy cottagecore RPG, warm wood and cream, soft upper-left daylight, gentle worn planks and stone, friendly not candy pastel, not dark gothic. Isometric town readable silhouettes, medium outline in warm brown ink, no photoreal, no UI chrome, no letters or numbers, no characters, no baked ground drop shadows.
```

---

## Negatives (all subjects)

`no text, no letters, no HUD, no buttons, no characters, no people, no animals, no baked drop shadow platforms, no candy pastel, no neon, no dark gothic, no photoreal, no 3D render, no watermark`

---

## Subjects — FIRST BATCH ONLY (town lock)

### A) Town outer wood frame / stage chrome texture

- **Asset id (suggested):** `ui-town-wood-frame` / 9-slice chrome  
- **Goal:** Thick illustrated warm-wood outer frame texture suitable for 9-slice; empty center; no icons, no text, no ornaments that read as UI widgets.  
- **Prompt:**  
  `{STYLE} Ornate but simple rectangular wooden window frame and border texture for a cozy kids RPG stage, thick hand-painted oak planks, carved soft bevels, warm brown wood grain, empty transparent or plain cream center for UI, 9-slice friendly corners and straight edges, top-down flat frame layout.`  
- **Size note:** Prefer seamless edge strips + corners; or full 1280×720 frame with large empty center.

### B) Town map grass / dirt isometric feel OR empty town plaza BG

- **Asset id (suggested):** `bg-town-plaza` or isometric grass/dirt tile feel reference  
- **Goal:** 1280×720 empty center for map UI; soft grass + worn dirt paths; isometric readability; **no buildings**.  
- **Prompt:**  
  `{STYLE} Wide 1280x720 isometric cozy town plaza background, lush soft grass and light dirt paths, empty buildable center clearing, distant soft trees and sky only at edges, no buildings, no props clutter, soft daylight meadow green and warm earth, hand-painted illustration.`  
- **Alt (tile feel):** same style, repeating isometric grass and dirt tile sheet energy, soft edges, no structures.

### C) Hero building — 探險公會 / Adventure Guild isometric sprite

- **Asset id (suggested):** `building-adventure-guild`  
- **Goal:** Match Preview guild: stone + wood tower, red banner as **shape only** (no glyphs), transparent background, isometric.  
- **Prompt:**  
  `{STYLE} Single isometric Adventure Guild building sprite, stone and warm wood tower with small roof, friendly cottagecore RPG landmark, red cloth banner shape without any writing, chimney optional, transparent background, clear silhouette, no ground shadow platform, no other buildings.`

---

## Variation grid (change one variable each)

1. **Wood temperature:** slightly lighter plank highlight (`wood-plank` feel) vs deeper oak (`wood-deep` feel) — keep cozy, not grey.  
2. **Grass saturation:** softer muted green vs clearer `grass` mid green — still daylight, not neon.  
3. **Guild stone ratio:** more timber framing vs more pale stone body — keep tower readable.  
4. **Banner:** solid red shape vs faded cloth folds — still **no text**.  
5. **Edge softness:** slightly tighter warm outline vs softer painterly edge — stay hand-painted, not photoreal.

---

## Tool-agnostic params

- **Grok Imagine:** fast exploration; paste style block + one subject; apply negatives in the negative / avoid field if available.  
- **Local SD / ComfyUI:** use for seed control and 9-slice crop iterations; lock seed when comparing variation grid rows.  
- Aspect: prefer **16:9** or exact **1280×720** for B; square / tall canvas OK for C then crop to sprite.  
- Export: PNG + alpha for C and frame corners; JPEG/PNG OK for full BG.

---

## Explicit deferrals

- ❌ Monsters / wolf / any battle foe reskin — **deferred** until outline weight matches hero.  
- ❌ Shop interior icon set (flat emoji gap) — not this batch.  
- ❌ Footer icons / Chinese labels — DOM only.

LOCKED 2026-11-02 · Preview tip e075646 · town lock first batch
