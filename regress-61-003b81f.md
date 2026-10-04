# Regression of green PR #61 at 003b81f

**Verdict: FAIL**

HEAD `003b81f7893db1c4acea05c932cb11b73a897006` on `cursor/green-warehouse-placement-8555`. Red tip `45d4bff`. Main `5bfe76d`. Read-only against the tracked `kids_town.db`. Every probe used a temporary SQLite file. Five designer checks fail on the running tip: off-screen taps select cells, a same-text toast fades out and snaps back to full opacity, the selected stroke is below 3:1, the focus ring sits 8.5px below the cell diamond, and the collapsed drawer stays in the Tab order.

## Identity

| Check | Expected | Actual | Result |
| --- | --- | --- | --- |
| Tip SHA | `003b81f` | `003b81f7893db1c4acea05c932cb11b73a897006` | PASS |
| `tests/` and `docs/test-cases/` vs `45d4bff` | empty diff | empty diff | PASS |
| Product diff vs `45d4bff` | the green commits | 5 files, +817 / −218: `backend_v2.py` +313/−75, `index.html` +157/−72, `service-worker.js` +9/−8, `town-four-scene.css` +48/−4, `town-four-scene.js` +290/−59 | PASS |
| Tracked `kids_town.db` sha256, start and end | `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb` | same hash at the end | PASS |
| `git diff main...HEAD -- kids_town.db` | empty | empty | PASS |

## Suites

pytest was one process at a time. Main ran at `5bfe76d` with the `45d4bff` test tree copied over. The tip is `003b81f`. UI on the tip ran twice.

| Suite | Expected | Actual | Result |
| --- | --- | --- | --- |
| Main API `pytest -m "not frontend"` | 361 pass / 18 fail | 361 passed, 18 failed, 129 deselected, 70.31s | PASS |
| Main UI `pytest -m frontend` | 71 pass / 58 fail | 71 passed, 58 failed, 379 deselected, 264.79s | PASS |
| Tip API | 379 / 0 | 379 passed, 129 deselected, 72.44s | PASS |
| Tip UI run 1 | 129 / 0 | 129 passed, 379 deselected, 262.72s | PASS |
| Tip UI run 2 | 129 / 0 | 129 passed, 379 deselected, 261.55s | PASS |
| Red → green | the 18 + 58 names below | 76 names, all failed on main and passed on the tip | PASS |
| Green → red | empty | empty | PASS |
| Flaky between the two tip UI runs | empty | 129 names, identical pass/fail | PASS |

### Red → green (76)

API:

- `tests.test_unlock_region::test_lighthouse_place_succeeds_after_region_3_explored`
- `tests.test_warehouse_placement::test_unstore_outside_8x8_is_rejected_without_changes`
- `tests.test_warehouse_placement::test_unstore_rejects_footprint_overlap`
- `tests.test_warehouse_placement::test_stored_rows_do_not_occupy_map_cells`
- `tests.test_warehouse_placement::test_origin_7_sticks_out_of_2x2`
- `tests.test_warehouse_placement::test_new_build_outside_8x8_does_not_charge_or_store`
- `tests.test_warehouse_placement::test_new_build_rejects_missing_negative_occupied_and_tile`
- `tests.test_warehouse_placement::test_new_build_rejects_footprint_overlap_without_charge`
- `tests.test_warehouse_placement::test_build_reuses_stored_building_without_charge_or_duplicate`
- `tests.test_warehouse_placement::test_stored_building_auto_places_without_coordinates`
- `tests.test_warehouse_placement::test_autoplace_already_owned_uses_formal_copy`
- `tests.test_warehouse_placement::test_move_outside_8x8_is_rejected_and_stays_placed`
- `tests.test_warehouse_placement::test_move_rejects_footprint_overlap`
- `tests.test_warehouse_placement::test_move_onto_stored_leftover_coords_succeeds`
- `tests.test_warehouse_placement::test_region_buildings_use_8x8_after_unlock`
- `tests.test_warehouse_placement::test_region_building_auto_places_or_rejects_a_full_map`
- `tests.test_warehouse_placement::test_region_build_get_does_not_warehouse_or_lose_the_spend`
- `tests.test_warehouse_placement::test_served_frontend_placement_grid_is_8x8`

UI:

- `tests.test_frontend::test_town_ux_scene2_gold_pads_and_building_list`
- `tests.test_frontend::test_town_ux_scene3_cancel_does_not_deduct`
- `tests.test_frontend::test_town_ux_scene3_confirm_deducts_and_opens_sheet`
- `tests.test_frontend::test_town_ux_scene4_upgrade_feature_and_hud`
- `tests.test_frontend::test_town_ux_hit_back_pad_not_front_sprite`
- `tests.test_frontend::test_town_ux_letterbox_pad_hit_alignment`
- `tests.test_frontend::test_town_ux_fx_place_shows_gold_stars`
- `tests.test_frontend::test_town_ux_fx_upgrade_shows_gold_stars_on_sheet`
- `tests.test_frontend::test_town_ux_motion_burst_pointer_events_none`
- `tests.test_frontend::test_town_grid_map_is_8x8`
- `tests.test_frontend::test_town_store_legacy_place_from_store_without_spend`
- `tests.test_frontend::test_town_store_place_from_warehouse_without_spend`
- `tests.test_frontend::test_town_store_confirm_does_not_pair_spend_copy_with_already_built`
- `tests.test_frontend::test_town_store_ux_place_stays_on_four_scene`
- `tests.test_warehouse_e2e::test_storage_takeout_places_on_8x8_and_persists`
- `tests.test_warehouse_e2e::test_storage_card_shows_name_level_and_takeout_only`
- `tests.test_warehouse_e2e::test_storage_card_body_does_not_start_unstore`
- `tests.test_warehouse_e2e::test_unstore_scene2_gold_matches_legal_origins`
- `tests.test_warehouse_e2e::test_unstore_cancel_returns_to_unstore_scene2`
- `tests.test_warehouse_e2e::test_new_build_scene2_still_places_and_charges_once`
- `tests.test_warehouse_e2e::test_formal_placement_copy`
- `tests.test_warehouse_e2e::test_return_map_leaves_scene2[new-build]`
- `tests.test_warehouse_e2e::test_return_map_leaves_scene2[unstore]`
- `tests.test_warehouse_e2e::test_takeout_full_town_stays_put[takeout]`
- `tests.test_warehouse_e2e::test_takeout_full_town_stays_put[list]`
- `tests.test_warehouse_e2e::test_new_build_scene2_gold_matches_legal_origins`
- `tests.test_warehouse_e2e::test_offgrid_cell_uses_cannot_fit_toast[unstore]`
- `tests.test_warehouse_e2e::test_offgrid_cell_uses_cannot_fit_toast[new-build]`
- `tests.test_warehouse_e2e::test_cancel_toast_uses_info_style[new-build]`
- `tests.test_warehouse_e2e::test_cancel_toast_uses_info_style[unstore]`
- `tests.test_warehouse_e2e::test_place_bar_buttons_do_not_overflow`
- `tests.test_warehouse_e2e::test_town_map_fits_horizontally`
- `tests.test_warehouse_e2e::test_unfit_cell_is_not_preselected`
- `tests.test_warehouse_e2e::test_confirm_400_returns_to_scene2[new-build]`
- `tests.test_warehouse_e2e::test_confirm_400_returns_to_scene2[unstore]`
- `tests.test_warehouse_e2e::test_smallest_catalog_footprint_golds_index_7`
- `tests.test_warehouse_e2e::test_palette_buttons_do_not_clip`
- `tests.test_warehouse_e2e::test_confirm_generic_4xx[plain-new-build]`
- `tests.test_warehouse_e2e::test_confirm_generic_4xx[plain-unstore]`
- `tests.test_warehouse_e2e::test_confirm_generic_4xx[detail-new-build]`
- `tests.test_warehouse_e2e::test_confirm_generic_4xx[detail-unstore]`
- `tests.test_warehouse_e2e::test_confirm_generic_4xx[occupied-new-build]`
- `tests.test_warehouse_e2e::test_confirm_generic_4xx[occupied-unstore]`
- `tests.test_warehouse_e2e::test_confirm_generic_4xx[empty-new-build]`
- `tests.test_warehouse_e2e::test_confirm_generic_4xx[empty-unstore]`
- `tests.test_warehouse_e2e::test_unfit_preselect_overlap`
- `tests.test_warehouse_e2e::test_sw_autoregisters_without_pageerror`
- `tests.test_warehouse_e2e::test_sw_precache_includes_four_scene`
- `tests.test_warehouse_e2e::test_sw_upgrade_drops_old_kids_town_cache`
- `tests.test_warehouse_e2e::test_palette_group_order[mixed]`
- `tests.test_warehouse_e2e::test_palette_group_order[no-stored]`
- `tests.test_warehouse_e2e::test_palette_group_order[none-built]`
- `tests.test_warehouse_e2e::test_tap_offcenter`
- `tests.test_warehouse_e2e::test_cell_aria_matches_tap[picked]`
- `tests.test_warehouse_e2e::test_cell_aria_matches_tap[unstore]`
- `tests.test_warehouse_e2e::test_tap_bar_nothrough`
- `tests.test_warehouse_e2e::test_toast_timer_resets`
- `tests.test_warehouse_e2e::test_autoplace_formal_shown`

Green → red: none.

## Probes

Temporary accounts only. Screenshots are under `screenshots/`.

| Check | Expected | Actual | Result |
| --- | --- | --- | --- |
| TAP-OFFCENTER 1100×800 bare | 576/576, palette and bar select 0 | 576/576, panel 0/0, bar 0/0 | PASS |
| TAP-OFFCENTER 1100×800 picked | exposed points correct, palette/bar select 0 | 531/531, panel 45/0, bar 0/0 | PASS |
| TAP-OFFCENTER 1100×800 unstore | 576/576, palette and bar select 0 | 576/576, panel 0/0, bar 0/0 | PASS |
| TAP-OFFCENTER 390×844 bare | 576/576 | 576/576, panel 0/0, bar 0/0 | PASS |
| TAP-OFFCENTER 390×844 picked | exposed points correct, palette/bar select 0 | 531/531, panel 45/0, bar 0/0 | PASS |
| TAP-OFFCENTER 390×844 unstore | 576/576 | 576/576, panel 0/0, bar 0/0 | PASS |
| Sprite over a back diamond | diamond wins | No 35% interior point of a back cell sat inside another building's sprite box, so this probe did not sample that overlap. Suite test `test_town_ux_hit_back_pad_not_front_sprite` passed on the tip. | INFO |
| TAP-BAR | bar, palette, HUD, footer, sheet, toast, burst select 0 cells; pointer-events none | 0 selections. `#toast`, `.fx-burst`, and the star bit all compute to `pointer-events: none`. | PASS |
| CELL-ARIA picked | 64/64, Enter 64/64, Space 64/64, no「已興建」on scene-2 reject labels | 64/64, Enter 64/64, Space 64/64 | PASS |
| CELL-ARIA unstore | same | 64/64, Enter 64/64, Space 64/64 | PASS |
| FOCUS pointer | mouse and touch leave no ring | Cell (2,2): `focus-visible` false, `::after` content `none`, outline `none`. Brown ring pixels 0. `screenshots/focus-mouse-diamond.png`, `focus-mouse-button.png`, `focus-touch.png` | PASS |
| FOCUS Tab | dashed diamond, outer `#6b4f2a` 2px, inner `#fff8e7` 3px, no rectangular outline | Cell (1,0): `focus-visible` true, outline `none`, clip diamond, 44 brown + 5 cream samples. `screenshots/focus-tab.png` | PASS |
| FOCUS selected and focused | solid gold line and dashed ring together | Cell (2,2): `focus-visible` true and the chosen mark is up. `screenshots/focus-selected-and-focused.png` | PASS |
| Palette cells that still take focus | known backlog (0,5) (0,6) (1,6) (0,7) (1,7) (2,7) | exactly that list | INFO |
| 4xx confirm 400 / 409 / 422, new-build and unstore | back to scene 2, toast「這個位置放不下這座建築物。」, raw body absent, resources unchanged | all 6 cases passed | PASS |
| Service worker fresh | only v28 caches within 10s | 0.12s, keys `kids-town-v28`, pageerrors 0 | PASS |
| Service worker upgrade | v27 and v20 gone, v28 remains, other app cache kept | deleted `kids-town-v27`, `kids-town-static-v27`, `kids-town-v20`; keys left `kids-town-v28`, `other-app-cache` | PASS |
| Offline town | scene 1, `--s` 0.85, left/right gaps equal ±1px, footer nowrap | aria「場景 1 · 查看地圖」, `--s` 0.85, left 3px / right 3px, `white-space: nowrap`. Precache holds `/kids/`, `index.html`, `town-four-scene.css`, `town-four-scene.js`. `screenshots/sw-offline.png` | PASS |
| Footprint single source | copy `"商店": 2` → `1`; API 商店 1, 農場 2; 商店 at (7,7) places; 農場 at (7,0) is 4xx; UI (7,7) is selectable; workspace file stays `"商店": 2` | API footprints 1 and 2. Funded 商店 at (7,7) returns **201** with `cell_x: 7, cell_y: 7` (the success status is 201). 農場 at (7,0) returns 400「位置超出地圖範圍（0 至 7）」. UI label「第 8 欄第 8 行，空地，點選即可選擇」. Workspace line remains `"商店": 2`. `screenshots/footprint-shop-1x1.png` | PASS |
| PAL-ORDER | stored, then unbuilt, then built, each group in catalog order | 圖書館 (stored), 探險公會 健身室 工坊 醫院 銀行 燈塔 競技場 天文台 (unbuilt), 農場 商店 (built). `screenshots/pal-order.png` | PASS |
| Place bars | height 64, buttons 46 | ready bar 64/46, scene-3 bar 64/46. `screenshots/bar-sizes.png` | PASS |
| Footer vs main `5bfe76d` | `#ktFooter` markup unchanged | source blocks equal, 1325 characters both. Live outerHTML is 1652 after icon render. `screenshots/footer.png` | PASS |
| Page errors across town, scene 2, palette, scene 3, sheet, 任務板, 儲蓄目標, 存倉 | 0 | 0. `screenshots/scene-quests.png`, `scene-savings.png`, `scene-store.png`, `scene-sheet.png` | PASS |
| New strings in the product diff | formal written Chinese | Added lines contain no 咗 呢 嘅 唔 係 撳 而家 喺. The visible「唔」is the pre-existing sheet sentence「木材唔夠、磚頭唔夠、齒輪唔夠。」, absent from the diff. | PASS |
| Auto-place already owned | formal「你已經興建了這種建築物。」 | 400, that exact string | PASS |
| Explicit-coordinate already owned | — | 400「你已經興建咗呢種建築物」. Present on main and on `45d4bff`. Not an added line in this diff. | INFO |
| Hard-coded viewport / test special cases in the product diff | no hits | no code hits for innerWidth, innerHeight, bareOverlap, 1100, 844, 390, 1280, 720, viewport, occlusion, back-hit, dataset.c, 196px, inset(72, webdriver, playwright, isTest. The only nearby strings are the git index line `175094f..5844df3` and the hunk header `@@ -616 +720,7 @@`. | PASS |

`cellAt` still rejects only a clientX outside the village width. The same function is on `45d4bff`. The document click listener that calls `cellAt` for a toast tap whose target is outside `#townMap` was added on this branch (commit `45427a7`).

## QC6

| Check | Expected | Actual | Result |
| --- | --- | --- | --- |
| Visible-only taps | A point outside `#townMap`, or off a visible part of a cell diamond, selects nothing and shows no toast. Off-screen cells such as (6,6) do not become「已選擇空地」. | See the case list. Off-screen (5,5) and (6,6) are selected from points outside the map. (4,5) is 0% visible at 1280×720 with scroll 0. | **FAIL** |
| Same-text toast opacity | Second identical tap at 1.0s and at 1.6s. Opacity stays smooth. Report any dip to 0 and the final fade. | Both gaps dip to 0 and jump back to 1 at about 2.02s. The later hide is `display: none` in one frame while opacity is still 1. | **FAIL** |
| Selected solid line | Colour, width, contrast ≥ 3:1 against grass and against the gold fill. Compare with the dashed gold outline. | Solid and dashed both sample `#d4a017`. Contrast 1.10 vs grass, 2.17 vs the fill. | **FAIL** |
| Focus ring centre | Ring centre on the cell diamond centre. | Ring centre is 8.50px below the diamond centre. The lowest brown pixel also lies in cell (3,1). | **FAIL** |
| Hidden drawer and rotate overlay in Tab order | Hidden controls are skipped. | All 13 collapsed drawer buttons take Tab. The rotate overlay does not. | **FAIL** (drawer) / PASS (rotate) |

### 1. Visible-only taps

`cellAt` returns a cell when clientX is inside the village and the iso rounding hits the grid. It does not test clientY against the village top or bottom. Scene 2, bare, temporary kid, scroll measured.

Gold cell **(4,5) at 1280×720, scrollTop 0: visible fraction 0.000**, centre outside the village, still marked hot. It is fully off-screen at the default scroll. The same is true at 1100×800 and 390×844. After scrolling to the bottom at 1280×720 and 1100×800, (4,5) and (6,6) are fraction 1.000. At 390×844, setting `scrollTop = scrollHeight` left `scrollTop` at 0.

Shots: `screenshots/qc6-visible-1280x720-top.png`, `qc6-visible-1280x720-bottom.png`, `qc6-visible-1100x800-top.png`, `qc6-visible-1100x800-bottom.png`, `qc6-visible-390x844-top.png`, `qc6-visible-390x844-bottom.png`.

Points on the strip above the bar, the village top edge, the four sides outside the map, the 8px footer band, and the centres of (4,5) and (6,6) produced no selection while the toast listener was idle. The failures are the toast-box taps and one point just above the village after scrolling to the bottom.

**1280×720, scrollTop 0.** (4,5) fraction 0.000. (6,6) fraction 0.000. (0,0) and (2,2) fraction 1.000. 34 points checked, 4 violations, all outside the map and off any visible diamond:

| Where | x, y | Chosen | Toast | Status |
| --- | --- | --- | --- | --- |
| toast / footer | 640.0, 618.4 | none | 這個位置已經有建築物。 | 請點選金色空地，或打開清單選擇要興建的建築物。 |
| toast / footer | 640.0, 630.2 | none | 這個位置已經有建築物。 | same |
| toast / footer | 640.0, 642.1 | **(5,5)** | stayed the probe sentinel | **已選擇空地。請打開清單，選擇要興建的建築物。** |
| toast / footer | 640.0, 640.0 | **(5,5)** | stayed the probe sentinel | **已選擇空地。請打開清單，選擇要興建的建築物。** |

(5,5) sits between (4,5) and (6,6), both at fraction 0, so (5,5) is off-screen at this scroll.

**1280×720, scrollTop 366.** (4,5) and (6,6) fraction 1.000. (0,0) fraction 0. 35 points, 1 violation: (640.0, 104.0), inside the map, above the village, not on a visible diamond. Chosen none. Toast「這個位置放不下這座建築物。」

**1100×800, scrollTop 0.** (4,5) and (6,6) fraction 0.000. 34 points, 3 violations, all outside the map:

| x, y | Chosen | Status |
| --- | --- | --- |
| 550.0, 697.3 | **(5,5)** | 已選擇空地。請打開清單，選擇要興建的建築物。 |
| 550.0, 709.1 | **(5,5)** | same |
| 550.0, 721.0 | **(6,6)** | same |

**(6,6) is selected while its visible fraction is 0.**

**1100×800, scrollTop 366.** 1 violation: (550.0, 179.6), inside the map, above the village. Toast「這個位置放不下這座建築物。」 No cell selected.

**390×844, scrollTop 0.** (4,5) and (6,6) fraction 0.000. 32 points, 0 violations. The bottom-scroll pass also stayed at scrollTop 0; that second fraction table is the same scroll and is not a separate layout.

### 2. Same-text toast

`#toast` computed opacity, `requestAnimationFrame`, median gap 16.66ms. First tap on the occupied shop cell (0,0). Second tap the same sentence, 1003.5ms later and, in a separate run, 1612.9ms later. `showToast` does not restart `fadeInOut` when the text is already showing. It only resets the 2000ms hide timer. The stylesheet animation is 2s: opacity 0 at 0%, 1 at 15% (0.30s), 1 at 85% (1.70s), 0 at 100% (2.00s), fill-mode `none`.

| Gap | Samples | Opacity 1500–2200ms | Dip to ≤0.05 | Jump back to 1 | Hide |
| --- | --- | --- | --- | --- | --- |
| 1003.5ms | 277 | min 0.000, max 1.000 | 1917.3ms | 2017.4ms | `display: none` at 3017.8ms, opacity still 1.000, one frame (17.0ms) |
| 1612.9ms | 313 | min 0.000, max 1.000 | 1927.1ms | 2027.3ms | `display: none` at 3627.2ms, opacity still 1.000, one frame (17.1ms) |

On the 1000ms run the fade is already 0.334 at 1817ms, 0.075 at 1901ms, 0.031 at 1934ms, then 1.000 at 2017ms. That is the designer window 1.74–2.02s: the first animation's fade-out, then a snap back to 1 while the element stays `display: block` until the timer from the second tap. The final disappearance is not a fade. Shots `screenshots/qc6-toast-delay-1000.png`, `qc6-toast-delay-1600.png`.

A separate 423ms same-text pair (the suite's gap) fired `animationstart` once. Opacity is below 0.9 during the opening fade-in, which is the animation starting at 0. After the second tap, opacity is 0.89 at 1322ms (about 1.74s after the first tap), the same fade. A different sentence restarts the animation (two `animationstart` events) and that run stayed within its checks.

### 3. Selected-cell solid line

Cell (2,0) at 1280×720. Source: `MARK_CHOSEN` is a solid polygon, stroke `#d4a017`, stroke-width 4. `mocks/town-building-proof/assets/cell-valid.svg` is the same polygon, dashed `8 6`, same stroke and width.

| Sample | RGB | Hex |
| --- | --- | --- |
| Solid stroke | 212, 160, 23 | `#d4a017` |
| Dashed stroke | 212, 160, 23 | `#d4a017` |
| Diamond centre fill | 255, 245, 207 | `#fff5cf` |
| Grass and map background | 126, 174, 82 | `#7eae52` |

RGB distance between solid and dashed is 0. They are the same colour. A vertical run of pure `#d4a017` pixels at the top tip is 3px; the SVG stroke-width is 4. WCAG contrast of the sampled stroke:

- against grass `#7eae52`: **1.10** (below 3:1)
- against the sampled fill `#fff5cf`: **2.17** (below 3:1)
- against the map background, same grass pixel: **1.10**

Shots: `screenshots/qc6-gold-dashed.png`, `qc6-selected-solid.png`.

### 4. Focus ring centre

Keyboard Tab onto the selected gold cell (2,0), `focus-visible` true. The ring box matches the slab box (dx −0.01px, dy −0.00px). The cell diamond centre is the mark image at viewBox y=50 of 120, which is also the hit-test origin. The ring SVG diamond is centred in its box (viewBox y=60).

| Comparison | dx | dy |
| --- | --- | --- |
| Ring centre vs cell diamond centre | −0.01px | **+8.50px** |
| Ring centre vs hit-test origin | −0.21px | +7.99px |
| Brown-pixel centroid vs cell diamond | +1.15px | **+8.06px** |

237 brown pixels (`#6b4f2a` ±28). Lowest brown pixel (782, 392) lies in cell **(2,0) and cell (3,1)**. The lower tip enters the next cell. Shot: `screenshots/qc6-focus-ring.png`. The ring rule was added in `003b81f`.

### 5. Tab order while hidden

Scene 2, drawer class `dr` (no `o`), `pointer-events: none`, `display: block`, `visibility: visible`, `aria-hidden` unset, `inert` false. The 13 buttons (✕, 小鎮地圖, 建築管理, 存倉, 探索, 任務, 榮譽, 背包, 成就, 儲蓄目標, 帳本, 設定, 登出) have `tabIndex` 0 and are not CSS-hidden. Their boxes start at x=1313 and x=1525, past the 1280px viewport (`right: -280px`).

Tab from the last footer button lands on ✕, then walks all 13 drawer buttons, with the drawer still closed. `#61` added `pointer-events: none` to `.dr` (the red tip does not have it) and left the buttons in the Tab order.

`#ktRotate` (請轉橫向) computes to `display: none`, 0×0, no focusable descendants, `tabIndex` −1. The Tab walk never entered it. At 390×844 it is still `display: none`, 0×0. Shots: `screenshots/qc6-tab-hidden.png`, `qc6-rotate-portrait.png`.

## Blockers

1. Toast and footer taps outside `#townMap` select off-screen cells, including (6,6) at visible fraction 0, and set the status to「已選擇空地」。A point above the village, inside the map and off every visible diamond, toasts「這個位置放不下這座建築物。」 (4,5) is 0% visible at 1280×720, scroll 0.
2. A second identical toast lets the original 2s animation fade to opacity 0 around 1.92–2.03s and then jumps back to 1. The eventual hide is one frame of `display: none` at opacity 1, 2.0s after the second tap.
3. The selected solid stroke is `#d4a017`, the same colour as the dashed gold outline. Contrast is 1.10 against grass and 2.17 against the gold fill, both under 3:1.
4. The focus ring centre is 8.50px below the cell diamond centre. Its lowest brown pixel lies in the next cell (3,1).
5. All 13 buttons in the collapsed, off-screen drawer are in the Tab order.

## Info

- Cells under the open palette that still take focus are the known list (0,5) (0,6) (1,6) (0,7) (1,7) (2,7).
- Explicit placement of a building the child already owns still returns「你已經興建咗呢種建築物」. That line is on main and on `45d4bff`. The new auto-place path returns the formal sentence.
- The upgrade sheet still shows「木材唔夠、磚頭唔夠、齒輪唔夠。」 That sentence is not in the `#61` diff.
- The 9-point tap sample never landed inside both a back-cell diamond and a front sprite. The suite test for that hit passed on the tip.
- `#ktRotate` is `display: none` and is not in the Tab order.
- Fresh service-worker caches were only `kids-town-v28` at 0.12s. By the offline check, `kids-town-static-v28` was also present. Upgrade kept `other-app-cache`.
