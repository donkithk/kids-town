# Regression of #61 tip ff05ccd

**Verdict: FAIL**

Product tip `ff05ccd92fe91c93e23044f60a65ebeb759383eb` on `cursor/green-warehouse-placement-8555`. Base is `c2875a2b55cfb81e41f57081fdc6c1c15cf16bed` (#60 red tip; it is the merge-base). This pass is read-only on product and tests. Suites and probes used empty databases under `/tmp`. `kids_town.db` was not written.

The suites match the builder counts. The map still accepts taps through the tools bar’s left edge, through a transparent palette corner, and misses one gold cell just outside the palette. The focus-ring inner edge is 2.0–3.5px on almost every sample, with one northwest sample at 1280×720 of 1.5px.

## Environment

| Item | Value |
| --- | --- |
| OS | Linux |
| Python | 3.12, pytest 9.1.1 |
| Browser | Playwright Chromium 153.0.8010.12 (Chrome for Testing), `device_scale_factor=1`, sRGB |
| Fonts before | `fc-list :lang=zh` was WenQuanYi Micro Hei and Droid Sans Fallback only. No Noto CJK. |
| Fonts after | `sudo apt-get install -y fonts-noto-cjk`, then a fontconfig rule preferring Noto Sans CJK TC. `fc-list :lang=zh` lists 33 faces, including Noto Sans/Serif CJK. `fc-match sans-serif:lang=zh-tw` is `NotoSansCJK-Regular.ttc: "Noto Sans CJK TC"`. |
| `.tools` at 1280×720, scroll 366 | top 109, bottom **155**, left 1135.36, right 1217, height 46 |

All browser work below ran after Noto was the Chinese font.

## Identity and diff

`git diff c2875a2b55cfb81e41f57081fdc6c1c15cf16bed..ff05ccd92fe91c93e23044f60a65ebeb759383eb --stat`:

| File | Change |
| --- | --- |
| `backend_v2.py` | +392 / − (file total in the five-file diff) |
| `index.html` | included |
| `service-worker.js` | included |
| `town-four-scene.css` | included |
| `town-four-scene.js` | included |

Five files, +1531 / −234. Nothing under `tests/` or `docs/test-cases/` changed. `kids_town.db` is not in the diff.

Special-case tokens on added lines (`innerWidth`, `innerHeight`, `bareOverlap`, `1100`, `844`, `390`, `1280`, `720`, `viewport`, `occlusion`, `back-hit`, `dataset.c`, `196px`, `inset(72`, `seed`, `navigator.webdriver`, `playwright`, `isTest`): **0**.

Fallback scan of the same added lines: **1** line contains `(6, 6)`, a comment in `backend_v2.py` (“A size of 2 ends at (6, 6); (7, 0) sticks out.”). No added line contains `1280`, `390`, `scroll 366`, or `TC-`. Three added `data-testid` attributes name the warehouse count, list, and take-out button.

## Suites

Sequential, one process at a time, under Noto. Marker split is `-m "not frontend"` (API) and `-m frontend` (UI).

| Run | Passed | Failed | Deselected | Duration |
| --- | ---: | ---: | ---: | --- |
| API | 387 | 0 | 143 | 76.83s (0:01:16) |
| UI 1 | 143 | 0 | 387 | 498.29s (0:08:18) |
| UI 2 | 143 | 0 | 387 | 500.69s (0:08:20) |

`kids_town.db` sha256 was `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb` after each run.

## Probes

Independent Playwright scripts. They do not import repository test helpers. Each group started with a centre tap on a visible gold cell, and that cell became the selection. The map renders at 1280×720, 1100×800, 390×844, and 768×1024.

Pixel numbers for the stroke and the ring are from a second pass that compares each pixel with an unselected, unfocused baseline taken after the cell has settled. The first pass scrolled some edge cells and treated sprite wood as brown, so those first-pass pixel failures are not product failures.

### a. Selected stroke — PASS

Interior samples at least 8px inside every edge are unchanged versus the baseline (diff count 0) at every viewport, for an interior gold cell and an edge gold cell. The centre is not `#7c2d12`. The 「此格」 badge is visible.

Stroke width along the outward normal, four samples per edge (t = 0.30, 0.45, 0.60, 0.75). Outer is the furthest brown sample in screen pixels outside the cell edge. Mid-edge samples are 2–4px wide and the outer edge is 0 or 1px.

| Viewport | Cell | Widths outside 2–4 | Outer outside 0–1 |
| --- | --- | --- | --- |
| 1280×720 | (3,3) and (0,6) | none | none |
| 1100×800 | (3,3) | none | none |
| 1100×800 | (0,6) | none | NE t=0.30 outer −1 (width 2). The edge pixel there is still `#d4a017`; brown starts 1px inside. The other three NE samples have outer 0. |
| 390×844 | (3,3) | SW t=0.75 width 8 | none |
| 390×844 | (0,6) | SW t=0.75 width 7 | none |
| 768×1024 | (3,3) and (0,6) | none | none |

The 390 southwest t=0.75 ray runs near the south vertex, so the span from the first brown hit to the last brown hit includes more than the stroke thickness. The other three southwest samples on those cells are 2–4px.

Gold neighbour. At 1280×720 the four cells around (3,3) are gold. On the southeast and southwest edges the sample on the cell edge (distance 0) is exact `#7c2d12` (124, 45, 18), replacing baseline `#d4a017` (212, 160, 23). Southeast is also brown at 0.5px. Gold that remains sits at 1.0px (southeast, northeast) or at 0.5px (southwest, northwest), which is the halo just outside a stroke whose outer edge is 0px. A looser “any gold pixel within 0.5px” flag fired on several edges; the on-edge sample itself is brown.

### b. Focus ring — FAIL

Tab focus (`:focus-visible`) on an empty gold cell, an edge cell, library (6,0), and the same cell selected and focused. Five samples per edge (t = 0.22, 0.38, 0.50, 0.62, 0.78). Distance is the first pixel that both changed versus the baseline and matches the cream `#fff8e7` or ring-brown ink.

Interior at least 8px inside is unchanged on focus-only cells (badge region included). No new solid `#7c2d12` inside those cells. Library sprite pixels inside the diamond: 613 / 453 / 51 / 210 checked at 1280 / 1100 / 390 / 768, and 0 covered.

Inner-edge distance, min–max, screen pixels:

| Viewport | Cell | NE | SE | SW | NW |
| --- | --- | --- | --- | --- | --- |
| 1280×720 | empty (3,3) | 2.5–3.0 | 3.0–3.0 | 3.0–3.0 | **1.5–3.0** |
| 1280×720 | edge (0,6) | 2.5–3.0 | 2.5–3.0 | 3.0–3.0 | 2.5–3.0 |
| 1280×720 | library (6,0) | 2.5–3.0 | 3.0–3.0 | 3.0–3.0 | 2.5–3.0 |
| 1280×720 | selected+focused (3,3) | 2.5–3.0 | 3.0–3.0 | 3.0–3.0 | **1.5–3.0** |
| 1100×800 | empty | 3.0–3.5 | 3.0–3.5 | 2.0–3.0 | 2.0–3.0 |
| 1100×800 | edge | 2.0–2.5 | 2.5–3.0 | 3.0–4.0 | 2.5–3.0 |
| 1100×800 | library | 3.0–3.0 | 3.0–3.5 | 2.5–3.0 | 2.5–3.0 |
| 1100×800 | selected+focused | 3.0–3.5 | 3.0–3.5 | 2.0–3.0 | 2.0–3.0 |
| 390×844 | empty | 2.5–3.0 | 2.5–3.5 | 2.5–3.0 | 2.0–2.5 |
| 390×844 | edge | 3.0–3.5 | 2.0–2.5 | 2.0–2.5 | 3.0–3.5 |
| 390×844 | library | 2.0–3.0 | 2.5–3.5 | 2.5–3.5 | 2.0–3.0 |
| 390×844 | selected+focused | 2.5–3.0 | 2.5–3.5 | 2.5–3.0 | 2.0–2.5 |
| 768×1024 | empty | 2.5–3.5 | 2.0–3.0 | 2.5–3.5 | 2.5–3.5 |
| 768×1024 | edge | 2.5–3.5 | 2.0–3.0 | 2.0–3.0 | 2.5–3.5 |
| 768×1024 | library | 2.5–3.5 | 2.0–3.0 | 2.5–3.5 | 2.5–3.5 |
| 768×1024 | selected+focused | 2.5–3.5 | 2.0–3.0 | 2.5–3.5 | 2.5–3.5 |

The 1280 northwest failure is one of five samples, at 1.5px, on both the empty cell and the selected+focused cell (distances 2.5, 1.5, 2.5, 2.5, 3.0). Southeast and southwest at 1100×800 and 390×844 are inside 2–4px. Southwest at 1100 on the edge cell reaches exactly 4.0.

Interior-cell ring box versus the cell diamond: aspect ratio 0.992–0.996 (within ±2%) and centre within ±1px at every viewport. Example at 1280 empty: cell 142.8×85.0, ring box 169×101, ratio 0.996, centre offset (−0.01, −0.34). Edge-cell boxes from the same “any ring-colored pixel” method are about 6px taller (ratio 0.87–0.94, centre about 3px high). Those boxes count cream-colored pixels that were already in the baseline, so the per-edge distances above are the measurement used for the 2–4px rule.

Selected and focused, the ring sits outside the brown stroke with a gap of other pixels, and the ink sequence contains dashes:

| Viewport | NE gap | SE gap | Notes |
| --- | ---: | ---: | --- |
| 1280 | sequence `bbbbbboooorrrroorrrooo` | (same walk) | brown, then a gap, then dashed ring |
| 1100 | 2.0px | 2.0px | dashes in the ring run |
| 390 | 2.5px | 2.5px | dashes in the ring run |
| 768 | 2.5px | 1.0px | SE sequence `bbbbbboorrrrrrrrrrrroo` still has a gap and a later dash break |

### c. TAP-VILLAGE-HALFPX — PASS

Scene 1, scroll 0. The row at live `#village.bottom + 0.5` does not select, does not toast 「想在這裏興建？」, and does not open a sheet.

| Viewport | Village bottom | Probe y | Points | Leaks | Control |
| --- | ---: | ---: | ---: | ---: | --- |
| 1280×720 | 541 | 541.5 | 145 | 0 | (199, 539.5) selects (0,6) |
| 390×844 | 477.15 | 477.65 | 44 | 0 | (62.0, 475.65) selects (0,6) |

### d. Solid UI edges — FAIL

Inclusive border-box points are blocked. Reverse points are `floor(top)−1`, `ceil(bottom)+1`, `floor(left)−1`, `ceil(right)+1`. The 0–1px band is not asserted.

| Check | Result |
| --- | --- |
| `.tools` at 1280, scroll 366, bottom 155 | Centre column: inclusive bottom blocked, and y=156 has no cell under it. **Left edge x=1135.4, y=155** (the inclusive bottom) reaches the map: cell (7,0), toast 「這個位置已經有建築物。」. First map y on that column is **155**, not 156. Right edge x=1216 has no cell under it. |
| Palette (255, 490), scroll 0 | Outside the palette (right 253.52, gap 1.48px). Selects gold cell **(0,5)**. |
| Palette (255, 505), scroll 0 | Same gap 1.48px, and the point is inside the (0,5) gold diamond. **No selection and no toast.** |
| Both points at scroll 300 and 366 | No reaction. |
| Bar top at 1100×800 | Top 555.55 blocked. Reverse y=554 selects gold (3,3). |
| Palette southeast rounded corner | (255.5, 552.4) is outside the rounded paint and outside the border box. `elementFromPoint` is the cell button. The tap selects **(1,6)**. (253.5, 550.4) is inside the rectangular border box and outside the rounded paint; `elementFromPoint` is still the cell button and the status line changes. (251.5, 548.4) hits the palette element. |

### e. Visible-only — PASS

Taps in the toast/footer band and outside the `#village` clip rect: 12 points, 0 leaks, at 1280 scroll 0, 1280 scroll 366, 390 scroll 0, and 1100 scroll 0.

Control under the toast at 1100: 任務板 at (550, 690.64) opens the tasks tab. No cell is selected.

### f. Toast opacity — PASS

Repeated same-text toast, sampled every 16ms. 157 samples. Opacity stays at 1 until the fade. No dip. `min` before 1900ms is 1. Fade starts at t=2048ms with opacity 0.889 and animation `toastOut`.

### g. Drawer and rotate — PASS

At 390×844 the drawer is `inert`, has no tabbable descendants, and is not in the Tab order. The rotate overlay is `inert`, `display: none`, role `dialog`, aria-label 「請轉橫向」, and has no tabbable descendants. The drawer element itself has no aria-label; its buttons carry visible text.

Store of the library returns HTTP 200. Palette aria-label 「圖書館，放回」. Unstore returns HTTP 200 and the library sprite appears at (0,0).

### h. Server copy and guards — PASS

Placing an owned building on an explicit cell: HTTP 400, `error` is exactly 「你已經興建了這種建築物。」.

The confirm UI, after the server has that sentence, toasts exactly 「你已經興建了這種建築物。」.

Confirm responses that are not a full Chinese sentence toast the generic 「這個位置放不下這座建築物。」. The toast has no ASCII letters and no JSON punctuation.

| Guard | Response | Toast |
| --- | --- | --- |
| 422 array | `[]` | 這個位置放不下這座建築物。 |
| 422 object | `{}` | 這個位置放不下這座建築物。 |
| 422 empty body | empty `text/plain` | 這個位置放不下這座建築物。 |
| English text | 400 `field required` | 這個位置放不下這座建築物。 |
| 409 plain | `Conflict` | 這個位置放不下這座建築物。 |
| Half Chinese | 400 `{"error":"你已經興建了"}` | 這個位置放不下這座建築物。 |

## Screenshots

Noto, 4× nearest-neighbour crops under `docs/regress/assets/`.

- `selected-focused-1100-se.png`, `selected-focused-1100-sw.png` — selected and focused, 1100×800, southeast and southwest edges.
- `selected-focused-390-se.png`, `selected-focused-390-sw.png` — same at 390×844.
- `selected-gold-neighbour.png` plus `-se` / `-sw` — selected cell beside a gold neighbour. The shared edge is brown.
- `focus-library-sprite.png` — focus ring around the library at (6,0).

## Discrepancy versus the builder claims

| Claim | This run |
| --- | --- |
| API 387/0, UI 143/0 twice | Counts match. Durations here are API 76.83s and UI 498.29s / 500.69s (builder API 62.42s, UI 498.31s / 497.08s). |
| Special-case grep 0 | Named tokens: 0. One added comment contains `(6, 6)`. |
| `kids_town.db` unchanged | sha256 still `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`. |
| Ring inner edge 2.5px | Samples cluster from 2.0 to 3.5. One northwest sample at 1280×720 is 1.5px. |
| Noto `.tools` bottom 155 | Measured bottom 155 (top 109, height 46). |

## Database

`sha256sum kids_town.db` at the end of this pass:

`c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`
