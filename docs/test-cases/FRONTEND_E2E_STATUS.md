# Frontend E2E status

> Synthetic fixture users only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`). Production `kids_town.db` is never copied.

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
