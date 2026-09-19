# Frontend E2E status

> Recorded against branch `cursor/phase0-playwright-ui-e2e-d6a9` (Phase 0 product from PR #4 + this Playwright harness).  
> Command: `python -m pytest tests/test_frontend.py -v`  
> Date: 2026-09-18  
> Chromium: Playwright bundled browser (`python -m playwright install chromium`).  
> Result: **17 passed**.

Also: `python -m pytest tests/ -m phase0 -v` → **32 passed**.  
Full suite: `python -m pytest tests/ -q` → **96 passed**, 0 skipped.

Synthetic fixture users only. Production `kids_town.db` is never copied.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| TC-FE-01 | `test_login_shows_town_hud` | **PASS** | Kid PIN login → HUD |
| TC-FE-02 | `test_ability_panel_shows_five_attributes` | **PASS** | `#hudTip` contains 臂力, not 體力 |
| TC-FE-03 | `test_battle_flow_attack` | **PASS** | 野狼 + 攻擊 |
| TC-FE-04 | `test_boss_summon_entry_in_battle_lobby` | **PASS** | |
| TC-FE-05 | `test_battle_win_shows_rarity` | **PASS** | |
| TC-FE-06 | `test_battle_not_marked_coming_soon` | **PASS** | |
| TC-FE-07 | `test_parent_register_flow` | **PASS** | |
| TC-FE-08 | `test_parent_create_kid_ui` | **PASS** | |
| TC-FE-09 | `test_kid_only_sees_own_and_global_tasks` | **PASS** | |
| (harness) | `test_battle_starts_despite_stale_running_expedition` | **PASS** | |
| (harness) | `test_boss_summon_despite_stale_running_expedition` | **PASS** | |
| (harness) | `test_boss_button_shows_cost_and_confirm` | **PASS** | |
| FE-P0-01 | `test_unauthenticated_ui_cannot_complete_task_or_adjust_points` | **PASS** | UI login wall + API 401 from browser fetch |
| FE-P0-02 | `test_kid_login_ui_does_not_display_raw_pin` | **PASS** | Login JSON + visible text |
| FE-P0-03 | `test_parent_a_ui_cannot_manage_parent_b_kid` | **PASS** | Manage list + adjust 403 |
| FE-P0-04 | `test_browser_static_denylist_db_and_python` | **PASS** | Both URLs 404 |
| FE-P0-05 | `test_default_admin_login_fails_on_fresh_db` | **PASS** | `admin`/`admin123` stays on login |

Phase 0 API marker run is tracked separately in [`PHASE0_SECURITY_STATUS.md`](PHASE0_SECURITY_STATUS.md).
