# GENERATE_PROMPTS.md — Ready-to-paste English image prompts

Kids Town Asset Kit v1. Style baseline for every prompt:

- Warm wood cozy / cottagecore / hand-drawn RPG illustration
- Soft natural lighting, gentle colors, child-friendly
- **No text, letters, numbers, UI chrome, watermarks, or signatures in the image**
- Backgrounds: exactly **1280×720** landscape, full-bleed scene
- Sprites: **transparent background**, single subject, clean silhouette

Paste one block per generation job. Negative hints are included at the end of each prompt.

---

## Backgrounds (`bg/`)

### `bg-guild-quest-room`

```
Hand-drawn cottagecore RPG illustration of a warm wooden guild quest room interior, landscape 1280x720. Honey oak beams, plank walls, soft afternoon window light, empty cork or wooden quest board on the back wall with blank pinned parchment rectangles (no writing), cozy rugs, small plants, lantern glow. Central floor and mid wall kept visually calm as empty space for UI cards. Bottom strip slightly simpler for a future tab bar. Warm wood palette #8b5e3c family, cream highlights. No characters, no people, no silhouettes, no UI buttons, no HUD, no text, no letters, no logos. Soft painterly edges, storybook game art.
Negative: text, letters, numbers, watermark, UI chrome, fantasy HUD, character, person, NPC, readable signs, photorealistic, dark horror, neon
```

### `bg-honour-ceremony`

```
Hand-drawn cottagecore RPG backdrop of a village honour ceremony pavilion, landscape 1280x720. Wooden award gazebo or open-air stage with flower garlands, soft fabric drapes, gentle golden sparkle dust, distant cottages and trees under warm sunset light. Large clear empty center area for a certificate panel overlay. Decorative sides richer; bottom edge calmer for UI. Warm wood, cream cloth, soft gold accents #d4a017. No characters, no people, no silhouettes, no certificate text, no names, no seals with letters, no UI chrome, no text. Storybook hand-painted game background.
Negative: text, letters, numbers, watermark, name plate, stamp text, characters, crowd, UI buttons, photorealistic, dark, scary
```

### `bg-wilderness-grass`

```
Hand-drawn sunny wilderness battle meadow, landscape 1280x720, cottagecore RPG scene art. Lush grass #7cb342, dirt path, soft blue sky #87ceeb with fluffy clouds, distant low hills or trees. Clear open ground left-front for a hero stance and right-front for an enemy stance, but paint only grass and path—no creatures. Calm mid-bottom band for action UI. Warm cheerful daylight, painterly brush strokes. No characters, no monsters, no animals, no HP bars, no buttons, no text, no logos.
Negative: text, UI, HUD, health bar, character, boar, monster, silhouette of person, watermark, photorealistic, night, blood
```

---

## UI components (`ui/`)

> Prefer implementing these in CSS/SVG. Use image prompts only when you need painted textures or mock fill-ins. Still: **no text in the image**.

### `ui-quest-card`

```
UI asset, cream parchment quest card mounted on a light wood plaque, soft hand-drawn cottagecore RPG style, front view flat design friendly for CSS. Rounded corners, subtle paper fiber, thin wood border #c4a06a, soft drop shadow. Blank face—no titles, no icons with letters. Transparent outside the card. Approximate landscape card proportions, tall enough for two text lines. Warm cream #faf6ef and wood #8b5e3c palette.
Negative: text, letters, numbers, buttons with labels, characters, busy background, photorealistic
```

### `ui-tab-bar`

```
Wide wooden grain UI tab bar texture strip for a mobile game, cottagecore RPG, seamless warm oak planks #8b5e3c to #a67c52, soft top highlight edge, slight wear, hand-painted feel. Landscape width feel, short height bar. No icons, no labels, no text, no buttons drawn on. Transparent above the bar top curve if possible. Flat-friendly game UI texture.
Negative: text, icons, five labeled tabs drawn in, characters, neon, flat vector sterile corporate
```

### `ui-btn-claim`

```
Gold claim button shape only, glossy warm gold gradient #f0c14b to #d4a017, rounded pill or 12px corners, soft bevel, cottagecore RPG UI, centered blank face with no label. Transparent background. Size suitable for a large tap target. Hand-drawn soft edges, not photoreal metal.
Negative: text, Chinese characters, English word Claim, icons, busy ornament covering center
```

### `ui-badge-pending`

```
Small pill badge base for pending status, soft amber fill #fff3d6 with #e8a317 outline, rounded capsule, blank center for overlay text, cottagecore RPG UI sticker, transparent background, hand-drawn soft.
Negative: text, letters, checkmarks with words
```

### `ui-badge-awarded`

```
Small pill badge base for awarded honour status, warm cream fill #fff5e0 with deep honour red outline #9b2c2c, optional tiny abstract seal flourish without letters, blank center, cottagecore RPG UI, transparent background.
Negative: text, Chinese, English, readable stamp words
```

### `ui-hud-chip-gold`

```
HUD resource chip, horizontal capsule, cream body, thin gold border #d4a017, left side small gold coin icon only (no numbers), right side empty for digits, cottagecore RPG UI, transparent background, hand-drawn soft.
Negative: numbers, text, dollar signs as typography, characters
```

### `ui-hud-chip-exp`

```
HUD EXP chip, horizontal capsule, aged paper fill #f3e6c8, thin wood border #8b5e3c, left side small star or leaf icon only, right side empty for digits, cottagecore RPG UI, transparent background.
Negative: numbers, letters, EXP text written in image
```

### `ui-honour-panel`

```
Honour certificate panel asset, thick cream paper certificate inside a warm wooden frame, rounded 20px feel, large empty circular seal area in lower center with abstract floral engraving but no letters, blank title and name bands, cottagecore RPG award UI, soft gold accents, transparent outside the panel, roughly 4:3 panel. No text of any kind.
Negative: text, names, dates, Chinese seal script, Latin motto, signatures, barcodes
```

---

## Battle sprites (`sprites/`)

### `sprite-hero-front`

```
Hand-drawn cottagecore RPG sprite of a friendly kid adventurer, front view facing camera, transparent background, single character only. Soft cloak or small backpack, warm tunic colors, cheerful expression, child-safe design. Centered on 256x256 style framing with padding at feet. Clean silhouette, no text, no UI, no shadow platform required (soft contact shadow OK if very light).
Negative: text, adult hero, horror, weapon gore, photorealistic, multiple characters, solid backdrop
```

### `sprite-hero-side`

```
Hand-drawn cottagecore RPG sprite of the same friendly kid adventurer, side view facing right, transparent background, battle stance ready, single character. Matching outfit colors to front variant. Clean silhouette for overlay on grass battlefield. No text, no UI.
Negative: text, facing left, adult, gore, solid white backdrop filled opaque scene, multiple characters
```

### `sprite-boar`

```
Hand-drawn cottagecore RPG enemy sprite of a grassland wild boar (草原野豬 vibe), cute adventurous not scary, facing left, transparent background, single animal. Short tusks, bristly mane, earthy browns and warm accents. Roughly 288x224 framing with ground padding. No blood, no text, no UI bars.
Negative: text, gore, horror, realistic taxidermy, rider, solid scenic background, facing right
```

### `sprite-generic-monster` (optional)

```
Hand-drawn cottagecore RPG generic small monster sprite, slime or forest imp style, friendly-scary for kids, facing left, transparent background, single creature, easy to recolor later, about 256x256 framing. No text, no UI, no weapons with logos.
Negative: text, copyrighted character lookalikes, gore, photorealistic, opaque rectangular backdrop
```

---

## Generator settings cheat-sheet

| Asset type | Aspect / size | Background |
|------------|---------------|------------|
| All `bg-*` | 1280×720 (16:9) | Opaque scene |
| UI pieces | As needed; export PNG/SVG | Transparent outside |
| Sprites | 256×256 or 288×224 | Transparent |

After generation: crop to exact size, verify alpha on sprites/UI, confirm zero baked-in text, drop files into `bg/`, `ui/`, `sprites/` using the ids above.
