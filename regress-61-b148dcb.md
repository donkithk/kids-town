# Regression #61 tip b148dcb

**Verdict: FAIL**

Tip `b148dcb9e06ad1f47e7ff76cf6990d124a3d283d` on `cursor/green-warehouse-placement-8555`. Base is #60 `86e5841`. Product code was not modified. `kids_town.db` was not written.

The blocker is a rounded corner of `#palette`. At 1280×720, scroll 300, toast not required: point (294.5, 163.5) is inside the palette border box (left 59, top 163, right 295, bottom 535), 0.5px from the top-right corner, so it is outside the 1px inset `solidUiCovers` uses. `elementFromPoint` is `#palette`. The tap selects cell (0, 5) and selects nothing else. Systematic 3px and 5px insets of the same controls do not select. This path is the map capture listener, not the document toast handler.

Scope change after this tip: only the controls-under-toast census was finished here. Main UI (builder claim 71/63) was not run. The service-worker one-reload follow-up was left inconclusive and was not repeated.

## Identity

| Check | Expected | Actual | Result |
| --- | --- | --- | --- |
| HEAD | b148dcb | b148dcb9e06ad1f47e7ff76cf6990d124a3d283d | PASS |
| `git diff 86e5841 b148dcb -- tests docs/test-cases` | empty | empty | PASS |
| Product diff vs 86e5841 and vs main `5bfe76d` | same, tests-only base | 5 files, +1080/−232: `backend_v2.py` +392, `index.html` +284, `service-worker.js` +17, `town-four-scene.css` +132, `town-four-scene.js` +487 | PASS |
| Special-case grep on added product lines | no viewport or test branch | 3 `data-testid` hits, all warehouse UI in `index.html` (`warehouse-count`, `warehouse-list`, `warehouse-takeout`). No `innerWidth`, `innerHeight`, `bareOverlap`, `1100`, `844`, `390`, `1280`, `720`, `viewport`, `occlusion`, `back-hit`, `dataset.c`, `196px`, `inset(72`, `seed`, `navigator.webdriver`, `playwright`, `isTest` | PASS |
| New-string colloquial 咗/呢/嘅/唔/係 | none on added lines | none (re-checked on the descendant tip; this commit's added lines are a superset) | PASS |
| `kids_town.db` | not in the diff; sha256 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb` | diff empty; hash matched before and after | PASS |

Document click handler in `town-four-scene.js` (removed by the next commit) has no viewport, coordinate, or testid branch.

## Suites

Sequential pytest. API is `-m "not frontend"`. UI is `-m frontend`. Never parallel.

| Tree | Suite | Passed | Failed | Time | Result |
| --- | --- | --- | --- | --- | --- |
| b148dcb | API | 380 | 0 | 49.64s | PASS |
| b148dcb | UI run 1 | 134 | 0 | 352.49s | PASS |
| b148dcb | UI run 2 | 134 | 0 | 349.90s | PASS |
| main `5bfe76d` + #60 test tree | API | 361 | 19 | 59.37s | matches builder 361/19 |
| main + #60 tests | UI | not run | | | skipped by the later scope change |

UI run 1 and run 2 selected the same 134 tests. No green→red. The 19 red API tests that are green on this tip:

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
- `tests.test_warehouse_placement::test_place_owned_explicit_cell_uses_formal_copy`
- `tests.test_warehouse_placement::test_move_outside_8x8_is_rejected_and_stays_placed`
- `tests.test_warehouse_placement::test_move_rejects_footprint_overlap`
- `tests.test_warehouse_placement::test_move_onto_stored_leftover_coords_succeeds`
- `tests.test_warehouse_placement::test_region_buildings_use_8x8_after_unlock`
- `tests.test_warehouse_placement::test_region_building_auto_places_or_rejects_a_full_map`
- `tests.test_warehouse_placement::test_region_build_get_does_not_warehouse_or_lose_the_spend`
- `tests.test_warehouse_placement::test_served_frontend_placement_grid_is_8x8`

## Controls under the toast (baseline)

Temp DB only (`probe_kid_61`). Toast text pinned to `探針`. Every `button` / link whose border box intersects the toast was tapped. Cell buttons were not treated as controls.

Toast box 1280×720: (607, 600.5)–(673, 640). Village content bottom 541, so the toast is entirely below the scrollport. `#ktFooter` top is 632; its tab boxes start at y 643, 3px below the toast, so no footer tab overlaps. `#btnUxBack` ends at y 596, 4.5px above the toast.

Toast box 1100×800: (517, 680.5)–(583, 720). Village content bottom 555.5. The only overlapping control is the `#ktFooter` task tab, overlap height 20.28px, top 643.2.

| Point | What was hit | Action | New cell | Result |
| --- | --- | --- | --- | --- |
| 1280 scene 1 `#btnBuild` (640, 600.8), overlap height 0.5px | `#btnBuild` | scene 1 → scene 2, listener fired | none | PASS |
| 1280 scene 2 closed / open | no button intersects the toast | | | PASS (nothing to steal) |
| 1100 scene 1 / scene 2 closed / scene 2 open task tab (550, 690.6) | `任務板` | `tab-town` → `tab-tasks`, nav `tasks` | none | PASS |
| 1100 scene 1 fixed (550, 691), toast visible | `任務板`, inside the toast | task board open (`tab-tasks`, title 公會任務板) | none | PASS |
| 1280 (632, 601.5) map sample under the toast | scene 1 `#townMap`; scene 2 `#readyBar` (the bar, not a button) | no control action | none | no hittable cell; see below |

Six slab graphics intersect the toast rectangle at each viewport (1280: cells (4,3), (3,4), (4,4), (5,4), (4,5), (5,5)). None is the topmost element. `marginUnderToast` is true for the whole toast because the toast does not meet the village content box, so `cellAt` returns null. There is no map point under the toast that should select a cell.

Shots: `docs/regress-61/shots/controls-b148dcb-1100-before-550-691.png`, `docs/regress-61/shots/controls-b148dcb-1100-after-550-691.png`.

## Other measured checks

| Check | Expected | Actual | Result |
| --- | --- | --- | --- |
| Pointer-events | `#toast` and `.fx-burst` are `none` | toast, burst, and bit all `none` | PASS |
| Rounded corner (294.5, 534.5) scroll 0 | inside palette, no selection | hit `#palette`, not in the 1px inset, chosen `[]` | PASS |
| Rounded corner (294.5, 163.5) scroll 300 | inside palette, no selection | hit `#palette`, not in the 1px inset, chosen `(0, 5)` | FAIL |
| (156.5, 154.5) scroll 366 | not a palette corner: palette top is 163 | hit `#village`, 8.5px above the palette, chosen `[]`, toast `這個位置放不下這座建築物。` | map hit, not a corner leak |
| 3px/5px corner insets, palette / launcher / bar / HUD, scrolls 0, 300, max | no selection | 0 leaks in the systematic pass | PASS |
| Guard: close palette, tap the gold that was underneath | selects that cell | (283.0, 473.3) selects (0, 5) | PASS |
| Focus ring | dashed diamond within 1px of the top face | cell (2, 0), `content` `""`, SVG background, `:focus-visible`, dx 0.185, dy 0.194. Mouse focus is not `:focus-visible` | PASS |
| Chosen mark | `#7c2d12` width 3 solid | interior (2, 1) matches. Edge (6, 0) pixel contrast vs grass 3.60, empty 7.05, gold `#efde9a` 6.95 | PASS |
| Hidden inert | closed drawer out of tab order; `#ktRotate` stays hidden | drawer 13 buttons, 0 tabbable when closed, 13 when open. Rotate `display:none`, inert, 0×0 at 390×844 on tasks | PASS |
| Formal owned copy | `你已經興建了這種建築物。` | explicit and auto POST 400 with that error. Toast `❌ 你已經興建了這種建築物。` class `error`. No colloquial | PASS |
| Full-town vs other failure class | exact full-town string is info; anything else is error | exact → info; owned and extra-dot → error | info, matches the known full-text match |
| Place bar | height 64px, buttons 46px | 64px / 46px, footer 88px | PASS |
| Palette order | stored, then unbuilt, then placed | 圖書館 stored, then unbuilt, then 農場/商店 placed | PASS |
| 1×1 catalog injection | (7, 7) hot for 工坊, quiet for 2×2 健身室 | `is-empty-hot` vs `is-quiet` | PASS |
| Offline scene 1 | `--s` 0.85 and equal side gaps | `--s` 0.85, left 3, right 3 | PASS |
| Page errors during probes | none | `[]` | PASS |

The first automated probe's visible-only, contrast, focus, and toast failures were measurement errors (points above the bar counted as leaks; focus-visible not applied; fade-in counted as an opacity dip). The follow-up measurements above replace them. Toast opacity on this tip was not re-sampled with a clean ≥3s trace; that trace was taken on `3625974`.

## Shots

`docs/regress-61/shots/` also has `a-toast-band-1280x720.png`, `a-toast-band-1100x800.png`, `c-grok-294.png`, `d-palette-closed-gold.png`, `f-selected-interior.png`, `g-focus-ring-retry.png`, `h-drawer-open.png`, `h-drawer-closed.png`, `h-portrait-tasks.png`, `i-formal-toast.png`, `j-offline-scene1.png`.
