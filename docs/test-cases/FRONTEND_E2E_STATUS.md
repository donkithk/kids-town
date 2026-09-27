# Frontend E2E status

> Synthetic fixture users only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`). Production `kids_town.db` is never copied.

## Out-of-grid relocate — red on main (tests only, do not merge)

> Recorded 2026-09-27 against **main** `a443c050805021f245b32eeca25af500d1c83286` (`a443c05`, four-scene UX from #28/#29/#30 already on this tree).  
> This change is tests + catalog only. No product code. Do not merge. Do not implement the relocate UX in this PR.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux. Empty seeded SQLite only.  
> Fixture mimics the verified kid pattern without a production DB or a real PIN: 工坊 `(4,1)` stored=0 inside the 6×5 grid; 圖書館 `(17,1)`, 健身室 `(15,5)`, 農場 `(9,5)`, 醫院 `(17,13)`, 探險公會 `(9,13)` stored=0 outside col 0..5 × row 0..4; 商店 `(3,3)` stored=1. 銀行 is not in `seed_building_defs`, so it is not seeded.  
> Bug: the list marks those off-grid rows 「已起」 and the hint asks for 「未起」, so 「去擺位置」 cannot put them back. Stored rows are offered as a new build (💰). Confirm POSTs create, which the API rejects as 「你已經興建咗呢種建築物」 and does not move or unstored the row. `POST /buildings/<id>/move` and store/unstored already exist.

### Commands

| Suite | Command | Result |
|-------|---------|--------|
| Relocate cases | `python3 -m pytest tests/test_frontend.py -q -k relocate --tb=line` | **2 failed, 2 passed**, 38 deselected in 8.45s |
| Existing frontend | `python3 -m pytest tests/test_frontend.py -q -k 'not relocate' --tb=line` | **38 passed**, 4 deselected, 4 warnings in 48.03s |

`01` and `04` pass because scene 1 already hides out-of-grid and stored buildings, and an in-grid 「已起」 still cannot start a second build. `02` and `03` fail on the missing place-back. Asserts were not weakened. `-k 'not relocate'` stays green (the 12 `town_ux` cases plus the previous 26).

### Case ID → result on main `a443c05`

| Case ID | Pytest | Result | Reason |
|---------|--------|--------|--------|
| TC-FE-TOWN-RELOCATE-01 | `test_town_relocate_scene1_hides_out_of_grid_buildings` | **PASS** | Scene 1 shows 工坊 at 第 5 欄第 2 行. Out-of-grid 圖書館／健身室／農場／醫院／探險公會 are not on the iso map. Stored 商店 does not paint on 第 4 欄第 4 行 (that pad stays 空地). |
| TC-FE-TOWN-RELOCATE-02 | `test_town_relocate_scene2_offgrid_and_stored_selectable` | **FAIL** | Every out-of-grid row is locked 「已起」 (for example `圖書館，已起`) and is not offered as relocate. Clicking 圖書館 opens the upgrade sheet and leaves 「去擺位置」 disabled. Hint: 「已揀空地。打開清單，揀一座未起嘅屋。」 Stored 商店 is offered as a new build (`商店，未起` / 💰500) and that selection enables 「去擺位置」 for create, not place-back. |
| TC-FE-TOWN-RELOCATE-03 | `test_town_relocate_confirm_moves_without_deduct` | **FAIL** | Empty pad 第 1 欄第 1 行 + 圖書館 `(17,1)` never enables 「去擺位置」, so confirm does not run and the row stays at `(17,1)`. Stored 商店 does reach confirm, but that POSTs a new build and toasts 「你已經興建咗呢種建築物」; the row stays stored=1 at `(3,3)` and does not appear on 第 1 欄第 4 行. Coins and materials were unchanged, which is necessary but not sufficient: the existing row was not moved. |
| TC-FE-TOWN-RELOCATE-04 | `test_town_relocate_in_grid_cannot_duplicate_build` | **PASS** | In-grid 工坊 stays 「已起」. 「去擺位置」 stays disabled. Still one 工坊 at `(4,1)`. HUD and inventory unchanged. |

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
