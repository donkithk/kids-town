# Frontend E2E status

> Synthetic fixture users only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`). Production `kids_town.db` is never copied.

## Placed-building sheet buff — red on main (tests only)

> Recorded 2026-09-28 against test commit `5350e7ec5608fdc2f33f16f5601891433a869746` (`5350e7e`, branch `cursor/red-sheet-buff-3939`). Base is **main** `1944623328c283325289d0d918aaab8c6e6480cb` (`1944623`). This follow-up only records that run.  
> Cases `TC-FE-TOWN-UX-SHEET-BUFF-01` and `TC-FE-TOWN-UX-SHEET-BUFF-02`. Filter `-k sheet_buff`.  
> Contract: open a placed building's `#actionSheet`. `#sheetFns` has zero `.fn` buttons (no 整道具／修理／接任務／出發, and no `FN` / `onFn` path that only toasts and rewrites `#sheetNote`). A visible `#sheetBuff` shows the current-level buff from API `buff_type` and `buff_vals[level-1]` (same index as `get_building_buff`). Readable text or `aria-label` must include that number and either the buff type or a multiplier mark (`×4` / `x4` / `build_speed` plus `4`). Exact Chinese wording is not required.  
> Fixture: empty DB, synthetic `test_fe_kid` only. Placed 工坊 `(4,1)` Lv.3 `stored=0`. Seed `build_speed` `buff_vals=[2,3,4,5,6]` so index 2 is **4**. Static `effect` 「建築速度 x2」 does not satisfy Lv.3. `#sheetNote`, the toast, and `#sheetCost` are not `#sheetBuff`. No production DB and no real PIN.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux.  
> On this main, tapping 工坊 opens `#actionSheet` at Lv.3, but `#sheetFns` has `.fn` buttons 整道具 and 修理, and `#sheetBuff` does not exist. Clicking 整道具 sets `#sheetNote` and the toast to `工坊：整好一件道具`.  
> Upgrade cost chip, `#btnUpgrade`, and `#upgradeConfirm` (last child of `.stage`; cancel does not spend) stay on the existing `upgrade_cost` / `upgrade_confirm` asserts. `TC-FE-TOWN-UX-05` and `store_ux` asserts were not edited. Those suites passed again.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| Sheet buff (new) | `python3 -m pytest tests/test_frontend.py -q -k sheet_buff --tb=short` | **2 failed**, 48 deselected in 3.69s |
| Upgrade + UX-05 + store_ux | `python3 -m pytest tests/test_frontend.py -q -k 'upgrade_cost or upgrade_confirm or scene4_upgrade_feature_and_hud or store_ux' --tb=line` | **5 passed**, 45 deselected in 10.52s |

The two new cases fail. The upgrade cost, upgrade confirm, scene-4 HUD, and store-place asserts were not weakened.

### Case ID → result on main `1944623` (tests at `5350e7e`)

| Case ID | Pytest | Result | Reason |
|---------|--------|--------|--------|
| TC-FE-TOWN-UX-SHEET-BUFF-01 | `test_town_ux_sheet_buff_shows_level_buff_without_fn` | **FAIL** | `#sheetFns` has 2 `.fn` buttons: 整道具, 修理. `#sheetBuff` is missing, so Lv.3 `build_speed` `buff_vals[2]=4` from `[2,3,4,5,6]` is not shown. |
| TC-FE-TOWN-UX-SHEET-BUFF-02 | `test_town_ux_sheet_buff_no_stub_toast` | **FAIL** | Fake FN click path still present (整道具, 修理). Clicking 整道具 set note and toast to `工坊：整好一件道具`. |

### Regression (unchanged asserts) on the same run

| Case ID | Pytest | Result |
|---------|--------|--------|
| TC-FE-TOWN-UX-UPGRADE-COST-01 | `test_town_ux_upgrade_cost_sheet_shows_gold_and_mats` | **PASS** |
| TC-FE-TOWN-UX-UPGRADE-COST-02 | `test_town_ux_upgrade_cost_insufficient_does_not_post` | **PASS** |
| TC-FE-TOWN-UX-UPGRADE-CONFIRM-01 | `test_town_ux_upgrade_confirm_cancel_then_post` | **PASS** |
| TC-FE-TOWN-UX-05 | `test_town_ux_scene4_upgrade_feature_and_hud` | **PASS** |
| TC-FE-TOWN-STORE-UX-01 | `test_town_store_ux_place_stays_on_four_scene` | **PASS** |

---

## Four-scene upgrade cost + confirm — red on #38 tip (tests only, do not merge)

> Recorded 2026-09-28 against **#38 tip** `46e03920bd893761b71277a16a223bc6cffabf49` (`46e0392`, branch `cursor/four-scene-store-place-eecb`). This is **not main**. When #38 merges, rebase this branch onto main.  
> Aligned to design mock `3b4671d` (PR #27, do not merge). Scene 4 is: tap a placed building → `#actionSheet` shows gold and material need → confirm → then upgrade. Not one click. Mock ids used by the asserts: `#actionSheet`, `#sheetTitle`, `#sheetLevel`, `#sheetNote`, `#btnUpgrade`. The mock demo line 「升級 · 💰50 🪵2」 is only the shape. Product amounts follow the backend: gold `floor(level×100×shop discount)`, materials `base×(level+1)`.  
> This change is tests + catalog only (`tests/test_frontend.py`, `docs/test-cases/FRONTEND_E2E.md`, this file). No product/UI/JS/CSS/backend. No new mock. Do not merge.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux. Empty seeded SQLite only.  
> Fixture: Lv.1 商店 `(0,2)` so discount is 0.9; Lv.2 健身室 `(2,1)`. Quote is gold **180** (`floor(200×0.9)`) and mats wood **30** / brick **15** (`10×3` / `5×3`). COST-02 sets brick to 14. No production DB and no real PIN.  
> On this tip, tapping 健身室 does open `#actionSheet` (`#sheetTitle` is 健身室). `#btnUpgrade` is only 「升級」. `#sheetNote` is 「可以升級，或者試下面嘅功能。」 No gold 180 and no material needs. The first tap POSTs. A short brick pile still enables the button and the API returns 400. A full purse returns 200 and the level goes 2 → 3 with no confirm button inside `#actionSheet`.  
> Existing asserts were not weakened: `TC-FE-TOWN-UX-05` passed again after this alignment. `TC-FE-TOWN-STORE-UX-01` was not edited (it passed on this tip). 整道具／接任務 are out of scope.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| Upgrade cost | `python3 -m pytest tests/test_frontend.py -q -k upgrade_cost --tb=line` | **2 failed**, 46 deselected in 5.25s |
| Upgrade confirm | `python3 -m pytest tests/test_frontend.py -q -k upgrade_confirm --tb=line` | **1 failed**, 47 deselected in 3.00s |
| Both | `python3 -m pytest tests/test_frontend.py -q -k 'upgrade_cost or upgrade_confirm' --tb=line` | **3 failed**, 45 deselected in 7.49s |
| UX-05 (unchanged assert) | `python3 -m pytest tests/test_frontend.py -q -k scene4_upgrade_feature_and_hud --tb=line` | **1 passed**, 47 deselected in 3.58s |
| store_ux (unchanged assert) | `python3 -m pytest tests/test_frontend.py -q -k store_ux --tb=line` | **1 passed**, 47 deselected in 2.38s |

The three new cases fail. UX-05 and store_ux asserts were not weakened.

### Case ID → result on #38 tip `46e0392`

| Case ID | Pytest | Result | Reason |
|---------|--------|--------|--------|
| TC-FE-TOWN-UX-UPGRADE-COST-01 | `test_town_ux_upgrade_cost_sheet_shows_gold_and_mats` | **FAIL** | Tap opens `#actionSheet`, but `#btnUpgrade` is 「升級」 and `#sheetNote` has no gold 180, wood 30, or brick 15. The first tap POSTed `/upgrade` HTTP 200 and the level became 3. No confirm layer showed the cost. |
| TC-FE-TOWN-UX-UPGRADE-COST-02 | `test_town_ux_upgrade_cost_insufficient_does_not_post` | **FAIL** | Brick have 14 / need 15, but `#btnUpgrade` stayed actionable. The tap POSTed `/upgrade` HTTP 400. Level stayed Lv.2. |
| TC-FE-TOWN-UX-UPGRADE-CONFIRM-01 | `test_town_ux_upgrade_confirm_cancel_then_post` | **FAIL** | First `#btnUpgrade` tap POSTed `/upgrade` HTTP 200. Level changed 2 → 3 before any 確定. No confirmation button inside `#actionSheet` (確定／確認, not 確定放置), so 取消 was never reached. |

---

## Store place must stay on four-scene UX — red on main (tests only, do not merge)

> Recorded 2026-09-27 against **main** `66bd1bc2802acd7a04ab3389b9ace1e242dcf302` (`66bd1bc`, Green #35).  
> Acceptance: placing a stored building from the four-scene 建築清單 stays on the visible 8×8 iso pad. `#placementBar` must not gain class `active`. `#townMap` must stay visible (`#placementBar.active ~ #townMap { visibility:hidden }` must not hide it). `#townCanvasWrapper` must not show the legacy 24×16 `.valid-plot` / `↘️` grid or the clipped purple 「確認建造」 bar. Confirm posts `/buildings/<id>/unstored`, gold and materials stay unchanged, and the same row becomes `stored=0` on the map.  
> This change is tests + catalog only. No product code. Do not merge.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux. Empty seeded SQLite only.  
> Fixture: 工坊 `(4,1)` Lv.1 `stored=0`; 探險公會 `stored=1`. No production DB and no real PIN.  
> On this main, `placeFromStore` calls legacy `startUnstoreBuilding`. Preview shows that purple `#placementBar` clipped so only 「確認」 remains, a field of faint `↘️` icons, and a green 「按確認」 cell, instead of the 8×8 iso pad. The test sees the same strip: `#placementBar.active` (`display:flex`, background `rgb(99, 102, 241)`), on-screen copy ending in 「確認」 / 「確認建造」. `#townMap` computed visibility is `hidden` (`pointer-events:none`). `#townCanvasWrapper` shows 335 faint `.valid-plot`, 336 plots total, and 335 `↘️`, plus 1 green cell 「按確認」. Visible iso pads are 0 (the DOM still has 64, aria 「場景 2」). POST `/unstored` was not sent from the four-scene pad.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| Store place UX | `python3 -m pytest tests/test_frontend.py -q -k store_ux --tb=line` | **1 failed**, 44 deselected in 2.03s |

The one new case fails. Asserts were not weakened.

### Case ID → result on main `66bd1bc`

| Case ID | Pytest | Result | Reason |
|---------|--------|--------|--------|
| TC-FE-TOWN-STORE-UX-01 | `test_town_store_ux_place_stays_on_four_scene` | **FAIL** | `#placementBar.active` purple strip (`rgb(99, 102, 241)`); Preview clips it so only 「確認」 shows. `#townMap` visibility is `hidden`. 335 faint `.valid-plot` / 335 `↘️`, plus 1 green 「按確認」 cell. Visible 8×8 iso pads: 0. Four-scene POST `/unstored` was not sent. |

---

## Stored building must not use the new-build spend path — red on main (tests only, do not merge)

> Recorded 2026-09-27 against **main** `0bd8c8729f750ec97019532f8acd60df1c11556b` (`0bd8c87`, Green #32).  
> Acceptance: a `stored=1` building is already owned. Scene 2 建築清單 must not show it as unbuilt with a price, and 確定 must not POST `/buildings`. That create dup-check includes stored rows and returns 400「你已經興建咗呢種建築物」. The correct place is 存倉 / `#placementBar` / `POST /buildings/<id>/unstored`, with no gold or material spend, on the same row (`stored=0`).  
> This change is tests + catalog only. No product code. Do not merge.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux. Empty seeded SQLite only.  
> Fixture: 工坊 `(4,1)` Lv.1 `stored=0`; 探險公會 `(9,13)` Lv.1 `stored=1`. No production DB and no real PIN.  
> On this main the palette still renders the stored guild as 「未起」 with 💰150. Choosing it opens 「確定先至扣資源」 and 確定 posts `/buildings`, which 400s. The row stays `stored=1`, so the map does not show 探險公會. Gold and materials are not deducted because the 400 happens before the spend.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| Stored vs new-build | `python3 -m pytest tests/test_frontend.py -q -k 'store_list or store_place or store_confirm' --tb=line` | **3 failed**, 41 deselected in 5.79s |

All three new cases fail. Asserts were not weakened.

### Case ID → result on main `0bd8c87`

| Case ID | Pytest | Result | Reason |
|---------|--------|--------|--------|
| TC-FE-TOWN-STORE-LIST-01 | `test_town_store_list_does_not_sell_stored_guild` | **FAIL** | Scene 2 建築清單 offers 探險公會 as unbuilt with a price (`探險公會，未起` and 💰150). Choosing it with an empty pad enters 「確定先至扣資源。取消唔會扣。」. On-map 工坊 stayed 「已起」 at 第 5 欄第 2 行. |
| TC-FE-TOWN-STORE-PLACE-01 | `test_town_store_place_from_warehouse_without_spend` | **FAIL** | The list confirm is not 存倉 / `#placementBar` / POST `/buildings/<id>/unstored`. 確定 posts `POST /api/kids/1/buildings` and gets HTTP 400「你已經興建咗呢種建築物」. The map does not show 探險公會. The same row stays id=5, def_id=6, level 1, `stored=1` at `(9,13)`. Gold and materials are unchanged because the 400 is before any deduct. |
| TC-FE-TOWN-STORE-CONFIRM-01 | `test_town_store_confirm_does_not_pair_spend_copy_with_already_built` | **FAIL** | 「確定先至扣資源。取消唔會扣。」 is on screen together with toast「你已經興建咗呢種建築物」 (HTTP 400 from `POST /buildings`). The palette row is still `探險公會，未起` / 💰150. The later 存倉 / `#placementBar` / unstored place kept the same row at `stored=0` and did not change gold or materials; the case stays red because those two strings were shown together. |

---

## 8×8 grid and legacy warehouse — green (product)

> Recorded 2026-09-27 against product commit `75f00b5` on branch `cursor/town-8x8-store-legacy-green-96f2`, based on tester tip `f1f1116` (draft PR #31, not merged).  
> Product: scenes 1–3 are COLS=8 ROWS=8. Each town load and buildings fetch sets `stored=1` on the same row when `stored=0` and the cell is outside 0..7×0..7 or has no legal cell. In-grid rows stay placed. Place-back is the existing 存倉 / `#placementBar` / `POST /buildings/<id>/unstored` path and does not spend resources.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux. Empty seeded SQLite only. Asserts were not weakened.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| Grid + legacy store | `python3 -m pytest tests/test_frontend.py -q -k 'town_grid or store_legacy' --tb=line` | **3 passed**, 38 deselected in 5.34s |
| Existing frontend | `python3 -m pytest tests/test_frontend.py -q -k 'not town_grid and not store_legacy' --tb=line` | **38 passed**, 3 deselected, 4 warnings in 49.13s |

The other frontend suite did not regress.

### Case ID → result

| Case ID | Pytest | Result |
|---------|--------|--------|
| TC-FE-TOWN-GRID-01 | `test_town_grid_map_is_8x8` | **PASS** |
| TC-FE-TOWN-STORE-LEGACY-01 | `test_town_store_legacy_migrates_out_of_grid_to_stored` | **PASS** |
| TC-FE-TOWN-STORE-LEGACY-02 | `test_town_store_legacy_place_from_store_without_spend` | **PASS** |

---

## 8×8 grid and legacy warehouse — red on main (tests only, do not merge)

> Recorded 2026-09-27 against **main** `a443c050805021f245b32eeca25af500d1c83286` (`a443c05`, four-scene UX from #28/#29/#30 already on this tree).  
> Acceptance: the buildable map is **COLS=8 ROWS=8** (64 pads, col 0..7 × row 0..7) in scenes 1–3. On town load, every `stored=0` building whose cell is outside that grid, or which has no legal cell, becomes `stored=1` on the same row (same id, `def_id`, level). Scene 1 must not paint those rows. The build list must not lock them as map-「已起」. Place them back from the existing 存倉 tab onto an empty pad without spending resources. List relocate (「去擺位置」) is not this path.  
> This change is tests + catalog only. No product code. Do not merge.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux. Empty seeded SQLite only.  
> Fixture: 工坊 `(4,1)` Lv.1 stored=0 inside 8×8; 圖書館 `(17,1)` Lv.3, 健身室 `(15,5)` Lv.1, 農場 `(9,5)` Lv.2, 醫院 `(17,13)` Lv.1, 探險公會 `(9,13)` Lv.1 stored=0 outside that grid; 燈塔 with NULL `cell_x`/`cell_y`, Lv.1, stored=0. 銀行 is not in `seed_building_defs`, so it is not seeded. No production DB and no real PIN.  
> The four-scene map is still 6×5. Town load does not warehouse the legacy rows. A NULL cell paints as `(0,0)`. The list locks every legacy name as 「已起」. 存倉 shows 「存倉吉咗，未有建築物」.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| Grid + legacy store | `python3 -m pytest tests/test_frontend.py -q -k 'town_grid or store_legacy' --tb=line` | **3 failed**, 38 deselected in 4.43s |
| Existing frontend | `python3 -m pytest tests/test_frontend.py -q -k 'not town_grid and not store_legacy' --tb=line` | **38 passed**, 3 deselected, 4 warnings in 50.37s |

All three new cases fail. Asserts were not weakened. The exclusion filter stays green. The older `-k 'not relocate'` filter no longer skips these tests.

### Case ID → result on main `a443c05`

| Case ID | Pytest | Result | Reason |
|---------|--------|--------|--------|
| TC-FE-TOWN-GRID-01 | `test_town_grid_map_is_8x8` | **FAIL** | Scenes 1, 2, and 3 each measure 6 columns × 5 rows (30 pads). Acceptance is 8×8 (64 pads, col 0..7 × row 0..7). |
| TC-FE-TOWN-STORE-LEGACY-01 | `test_town_store_legacy_migrates_out_of_grid_to_stored` | **FAIL** | After town load the same rows remain stored=0: 圖書館 `(17,1)`, 健身室 `(15,5)`, 農場 `(9,5)`, 醫院 `(17,13)`, 探險公會 `(9,13)`, 燈塔 `(NULL, NULL)`. def_id and level were kept. In-grid 工坊 was not reported as moved. |
| TC-FE-TOWN-STORE-LEGACY-02 | `test_town_store_legacy_place_from_store_without_spend` | **FAIL** | Scene 1 still paints 燈塔 (NULL cell becomes a map cell). The five out-of-grid names were not on the iso map. All six legacy names are locked 「已起」 (for example `圖書館，已起`). 存倉 is empty: 「存倉吉咗，未有建築物」, so place-from-storage never starts. In-grid 工坊 stayed 「已起」. Coins and materials were unchanged. |

---

## Town four-scene UX — regress PASS (do not merge #27 / #28 / #29)

> Independent regress recorded 2026-09-27.  
> Product tree: PR #29 tip `e6e85abc2000ca6967cf2a4500ad59fc459a90df` (`e6e85ab`, branch `cursor/town-four-scene-product-63d5`).  
> Test overlay only (not product/UI): PR #28 tip `7a92ba8a1a3c2c0ae8d784e687037006843117dc` (`7a92ba8`, branch `cursor/red-town-four-scene-ux-55ae`) — `tests/test_frontend.py`, `docs/test-cases/FRONTEND_E2E.md`, and the prior red STATUS.  
> Design lock: mock tip `3b4671d7d14be2024937213152ac05a008f27372` (PR #27). **Do not merge #27, #28, or #29.**  
> Prior red record on tester PR #28 was against main `ed48d47`. This run is the same assertions on the #29 product tip.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux. Empty seeded SQLite only.  
> `TC-FE-PLACE-SHOP-01` / `TC-FE-PLACE-BUILD-01` stay on the old `#placementBar` flow. They are not this sheet flow.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| New four-scene cases | `python3 -m pytest tests/test_frontend.py -q -k town_ux --tb=line` | **12 passed**, 26 deselected in 19.57s |
| Existing frontend | `python3 -m pytest tests/test_frontend.py -q -k 'not town_ux' --tb=line` | **26 passed**, 12 deselected, 4 warnings in 27.83s |

No town_ux failures. Asserts were not weakened.

### Case ID → PASS on product `e6e85ab` + tests `7a92ba8`

| Case ID | Pytest | Result |
|---------|--------|--------|
| TC-FE-TOWN-UX-01 | `test_town_ux_scene1_map_cta_and_empty_pad_does_not_spend` | **PASS** |
| TC-FE-TOWN-UX-02 | `test_town_ux_scene2_gold_pads_and_building_list` | **PASS** |
| TC-FE-TOWN-UX-03 | `test_town_ux_scene3_cancel_does_not_deduct` | **PASS** |
| TC-FE-TOWN-UX-04 | `test_town_ux_scene3_confirm_deducts_and_opens_sheet` | **PASS** |
| TC-FE-TOWN-UX-05 | `test_town_ux_scene4_upgrade_feature_and_hud` | **PASS** |
| TC-FE-TOWN-HIT-01 | `test_town_ux_hit_back_pad_not_front_sprite` | **PASS** |
| TC-FE-TOWN-HIT-02 | `test_town_ux_letterbox_pad_hit_alignment` | **PASS** |
| TC-FE-TOWN-HIT-03 | `test_town_ux_hit_soft_oval_contact_shadows` | **PASS** |
| TC-FE-TOWN-FX-01 | `test_town_ux_fx_place_shows_gold_stars` | **PASS** |
| TC-FE-TOWN-FX-02 | `test_town_ux_fx_upgrade_shows_gold_stars_on_sheet` | **PASS** |
| TC-FE-TOWN-MOTION-01 | `test_town_ux_motion_burst_pointer_events_none` | **PASS** |
| TC-FE-TOWN-MOTION-02 | `test_town_ux_motion_toggle_follows_reduced_motion_until_click` | **PASS** |

---

## Town four-scene UX — red on main (do not merge)

> Recorded 2026-09-27 against product **main** `ed48d47e27f35ca40adf061aca1f5af0de4028a9` (`ed48d47`, design: town style A compare + building proof pack).  
> This change is tests + catalog only. Design reference is mock tip `3b4671d7d14be2024937213152ac05a008f27372` (PR #27 draft). **Do not merge #27 or this PR.** Builder turns these cases green later.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux.  
> `TC-FE-PLACE-SHOP-01` / `TC-FE-PLACE-BUILD-01` stay. They are the old placement bar, not this sheet flow.  
> Checklist coverage: (1) scene 1 real data `UX-01` (2) scene 2 pad + list `UX-02` (3) ghost confirm/cancel `UX-04` / `UX-03` (4) scene 4 upgrade + feature `UX-05` (5) gold stars `FX-01` place + `FX-02` upgrade on the action sheet (6) soft oval shadows `HIT-03`, letterbox + occluded back-row hit `HIT-01` / `HIT-02` at 1100×800 and 1280×720 (7) animation toggle `MOTION-02`.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| New four-scene cases | `python3 -m pytest tests/test_frontend.py -q -k town_ux --tb=line` | **12 failed**, 26 deselected in 8.47s |
| Existing frontend | `python3 -m pytest tests/test_frontend.py -q -k 'not town_ux' --tb=line` | **26 passed**, 12 deselected, 4 warnings in 26.37s |

Full `tests/test_frontend.py` is now 38 tests: the 12 `town_ux` cases are intentional reds. Filter with `-k 'not town_ux'` to see the previous green set. Do not weaken the new asserts onto `#placementBar`.

### Case ID → FAIL on `ed48d47`

| Case ID | Pytest | Result | Fail message (abridged to the assertion) |
|---------|--------|--------|------------------------------------------|
| TC-FE-TOWN-UX-01 | `test_town_ux_scene1_map_cta_and_empty_pad_does_not_spend` | **FAIL** | Scene 1 must show placed buildings from the kid's real data. Missing: scene-1 iso map missing real placed 商店, 圖書館, 農場, CTA 「我要起屋」, iso empty pads. Footer 「商店」 and legacy `.town-building` do not count. |
| TC-FE-TOWN-UX-02 | `test_town_ux_scene2_gold_pads_and_building_list` | **FAIL** | Scene 2 must open from 「我要起屋」: gold frames, list 「已起」, 「去擺位置」. Entry CTA 「我要起屋」 is not on the town home. |
| TC-FE-TOWN-UX-03 | `test_town_ux_scene3_cancel_does_not_deduct` | **FAIL** | Scene 3 取消 must leave HUD unchanged and toast 「已取消，資源未扣除」 after a semi-transparent preview that can move, while an occupied pad stays blocked. Entry CTA missing. |
| TC-FE-TOWN-UX-04 | `test_town_ux_scene3_confirm_deducts_and_opens_sheet` | **FAIL** | Scene 3 確定 must deduct HUD resources, place the building, and open the scene 4 upgrade sheet. Entry CTA missing. |
| TC-FE-TOWN-UX-05 | `test_town_ux_scene4_upgrade_feature_and_hud` | **FAIL** | Scene 4 must raise the building level, deduct the upgrade from the HUD, and show a visible result from a feature button. Entry CTA missing. |
| TC-FE-TOWN-HIT-01 | `test_town_ux_hit_back_pad_not_front_sprite` | **FAIL** | Iso hit-test needs pad buttons. A tap on a back-row diamond covered by a front building must select that back pad at 1100×800 (stage layout 1280×720, visual 1100.0×618.8) and at 1280×720. |
| TC-FE-TOWN-HIT-02 | `test_town_ux_letterbox_pad_hit_alignment` | **FAIL** | Letterbox pad alignment needs iso pad hit targets at 1100×800 and 1280×720. Stage is already 1280×720 (visual 1100.0×618.8); that alone does not pass. |
| TC-FE-TOWN-HIT-03 | `test_town_ux_hit_soft_oval_contact_shadows` | **FAIL** | Soft oval contact shadow (radial-gradient ellipse, blurred, crosses the seam, pointer-events none) missing under the 1100×800 letterbox; must also hold at 1280×720. |
| TC-FE-TOWN-FX-01 | `test_town_ux_fx_place_shows_gold_stars` | **FAIL** | New-build gold stars `.fx-burst.is-place .fx-bit.is-star` were not visible. Battle `.spark-burst` does not count. Entry CTA missing. |
| TC-FE-TOWN-FX-02 | `test_town_ux_fx_upgrade_shows_gold_stars_on_sheet` | **FAIL** | Upgrade gold stars on the open action sheet `.action-sheet .fx-burst.is-upgrade .fx-bit.is-star` missing. Entry CTA missing. |
| TC-FE-TOWN-MOTION-01 | `test_town_ux_motion_burst_pointer_events_none` | **FAIL** | Place/upgrade celebration bursts (`.fx-burst` or `[data-town-fx]`) must use `pointer-events:none`. Entry CTA missing. Battle `.spark-burst` does not count. |
| TC-FE-TOWN-MOTION-02 | `test_town_ux_motion_toggle_follows_reduced_motion_until_click` | **FAIL** | 動畫 開/關 toggle missing. Reduced-motion emulation was on and the first visit wrote no motion key. Only an explicit on click and an explicit off click may write localStorage. |

Shared tail on every failure: `Missing four-scene town build UX on /kids/ town home (design mock tip 3b4671d / PR #27, do not merge). The old shop／建築 #placementBar flow is a different case and does not pass this one. Builder work: land the sheet flow before turning this green.`

---

## Experience C baseline (historical, 2026-09-19)

> Recorded against branch `cursor/harden-ceremony-place-e2e-17ad` (Experience C — real-device hardening).  
> Base at that time: `main` `4f6cdda`.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux.

## Commands (real numbers, 2026-09-19 historical)

These counts are from before the four-scene red cases. The current file is 38 tests; see the section above.

| Suite | Command | Result |
|-------|---------|--------|
| Frontend E2E | `python3 -m pytest tests/test_frontend.py -v` | **26 passed**, 0 failed, 4 warnings in 26.19s |
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **39 passed, 1 failed**, 105 deselected, 33 warnings in 10.30s |
| Rest of suite | `python3 -m pytest tests/ -m "not phase1" -q` | **105 passed**, 40 deselected, 20 warnings in 38.07s |
| Collection | `python3 -m pytest tests/ --collect-only -q` (implied) | **145 collected** (was 142; +3 Experience C cases) |

Intentional leftover red **P1-TC-CER-03** (Phase 2 `require_approval`) was **not skipped**. 2026-09-20: pytest marker moved to `phase2` and product GREEN — see [`PHASE2_APPROVAL_STATUS.md`](PHASE2_APPROVAL_STATUS.md). New Experience C cases are **not** `@pytest.mark.phase1` and all **PASS**.

## Mapping (pre-existing)

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| TC-FE-01 | `test_login_shows_town_hud` | **PASS** | Kid PIN login → HUD |
| TC-FE-02 | `test_ability_panel_shows_five_attributes` | **PASS** | `#hudTip` contains 臂力, not 體力 |
| TC-FE-03 | `test_battle_flow_attack` | **PASS** | 野狼 + 攻擊 |
| TC-FE-04 | `test_boss_summon_entry_in_battle_lobby` | **PASS** | |
| TC-FE-05 | `test_battle_win_shows_rarity` | **PASS** | |
| TC-FE-06 | `test_battle_lobby_boss_cost_confirm_not_coming_soon` | **PASS** | |
| TC-FE-10 | `test_battle_daily_region_limit_blocks_second_start` | **PASS** | |
| TC-FE-07 | `test_parent_register_flow` | **PASS** | |
| TC-FE-08 | `test_parent_create_kid_ui` | **PASS** | |
| TC-FE-09 | `test_kid_only_sees_own_and_global_tasks` | **PASS** | |
| TC-FE-JOURNEY-01 | `test_parent_assigns_task_kid_completes_hud_gold` | **PASS** | Gold + 「任務完成」 only |
| (harness) | `test_battle_starts_despite_stale_running_expedition` | **PASS** | |
| (harness) | `test_boss_summon_despite_stale_running_expedition` | **PASS** | |
| (harness) | `test_boss_button_shows_cost_and_confirm` | **PASS** | |
| FE-P0-01 | `test_unauthenticated_ui_cannot_complete_task_or_adjust_points` | **PASS** | |
| FE-P0-02 | `test_kid_login_ui_does_not_display_raw_pin` | **PASS** | |
| FE-P0-03 | `test_parent_a_ui_cannot_manage_parent_b_kid` | **PASS** | |
| FE-P0-04 | `test_browser_static_denylist_db_and_python` | **PASS** | |
| FE-P0-05 | `test_default_admin_login_fails_on_fresh_db` | **PASS** | |
| FE-P0-06 | `test_logout_then_write_apis_return_401` | **PASS** | |
| FE-XSS-01 | `test_task_title_markup_is_plain_text_not_html` | **PASS** | |
| FE-XSS-02 | `test_kid_display_name_markup_is_plain_text_in_hud` | **PASS** | |
| P1-TC-CER-FE-01 | `test_complete_task_ceremony_shows_xp_materials_achievements` | **PASS** | Mock route (A); (B) still required |
| P1-TC-CER-FE-01 | `tests/test_frontend_ceremony.py` | **PASS** | Weak source (A) |
| P1-TC-PLC-FE-01 | `tests/test_frontend_placement.py` | **PASS** | Weak source (A) |

## Experience C (this PR)

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| TC-FE-CEREMONY-01 | `test_real_task_complete_ceremony_shows_gold_xp_and_materials` | **PASS** | Real complete (no mock). Toast includes gold + `⭐XP+N` + 🪵/🧱. Product already surfaces all three — **not** gold-only. (B) still required for small-screen toast clipping. |
| TC-FE-PLACE-SHOP-01 | `test_shop_build_enters_placement_and_building_appears_on_map` | **PASS** | 背包商店 → 建造 → `#placementBar` → green `.valid-plot` → 確認 → 圖書館 on map + DB |
| TC-FE-PLACE-BUILD-01 | `test_buildings_tab_build_enters_placement_and_building_appears_on_map` | **PASS** | 建築管理 → 建造 → harness `st('town')` → place 健身室. Overlapping `.valid-plot` layers need DOM `dispatch_event('click')` in automation. |

## Harness notes (not product gameplay)

- **建築 tab does not auto-switch to the map** (`shopBuild` does `st('town')`; `startPlacement` does not). E2E calls `st('town')` after 建造. Call out for KT builder; not fixed in this PR.
- **Overlapping 2×2 `.valid-plot` hit targets** intercept Playwright pointer clicks. Tests dispatch the DOM click. (B) uses a real finger on the topmost green cell.
- Occupancy for picking a free cell is read from **SQLite**, because `let townData` is not on `window`.

## (B)

Remaining manual / real-device steps: [`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md). Do not treat grep/source as full (A).
