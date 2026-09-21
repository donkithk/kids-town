# Frontend E2E status

> Recorded against branch `cursor/harden-ceremony-place-e2e-17ad` (Experience C — real-device hardening).  
> Base: latest `main` (`4f6cdda`, Phase 1 merged).  
> Date: 2026-09-19  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux.  
> Synthetic fixture users only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`). Production `kids_town.db` is never copied.

## Commands (real numbers)

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
