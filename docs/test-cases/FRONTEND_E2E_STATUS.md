# Frontend E2E status

> Recorded against branch `cursor/trust-depth-ui-e2e-45bd` (based on PR #5 Playwright harness).  
> Command: `python -m pytest tests/test_frontend.py -v`  
> Date: 2026-09-18  
> Chromium: Playwright bundled browser (`python -m playwright install chromium`).  
> Result: **pending run** (this table is filled after pytest in this PR).

Synthetic fixture users only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`). Production `kids_town.db` is never copied.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| TC-FE-01 | `test_login_shows_town_hud` | pending | Kid PIN login → HUD |
| TC-FE-02 | `test_ability_panel_shows_five_attributes` | pending | `#hudTip` contains 臂力, not 體力 |
| TC-FE-03 | `test_battle_flow_attack` | pending | 野狼 + 攻擊 |
| TC-FE-04 | `test_boss_summon_entry_in_battle_lobby` | pending | |
| TC-FE-05 | `test_battle_win_shows_rarity` | pending | |
| TC-FE-06 | `test_battle_lobby_boss_cost_confirm_not_coming_soon` | pending | Strengthened: no 即將開放 + Boss 💎 + dismiss confirm |
| TC-FE-10 | `test_battle_daily_region_limit_blocks_second_start` | pending | Seeded `daily_battles` → 400 + toast |
| TC-FE-07 | `test_parent_register_flow` | pending | |
| TC-FE-08 | `test_parent_create_kid_ui` | pending | |
| TC-FE-09 | `test_kid_only_sees_own_and_global_tasks` | pending | |
| TC-FE-JOURNEY-01 | `test_parent_assigns_task_kid_completes_hud_gold` | pending | Parent assign → kid complete → HUD gold |
| (harness) | `test_battle_starts_despite_stale_running_expedition` | pending | |
| (harness) | `test_boss_summon_despite_stale_running_expedition` | pending | |
| (harness) | `test_boss_button_shows_cost_and_confirm` | pending | Original cost/confirm harness kept |
| FE-P0-01 | `test_unauthenticated_ui_cannot_complete_task_or_adjust_points` | pending | |
| FE-P0-02 | `test_kid_login_ui_does_not_display_raw_pin` | pending | |
| FE-P0-03 | `test_parent_a_ui_cannot_manage_parent_b_kid` | pending | |
| FE-P0-04 | `test_browser_static_denylist_db_and_python` | pending | |
| FE-P0-05 | `test_default_admin_login_fails_on_fresh_db` | pending | |
| FE-P0-06 | `test_logout_then_write_apis_return_401` | pending | UI 登出 + POST writes 401 |
| FE-XSS-01 | `test_task_title_markup_is_plain_text_not_html` | pending | May **FAIL** (task titles still innerHTML) |
| FE-XSS-02 | `test_kid_display_name_markup_is_plain_text_in_hud` | pending | HUD `#hudNm` uses textContent |

Phase 0 API marker run is tracked separately in [`PHASE0_SECURITY_STATUS.md`](PHASE0_SECURITY_STATUS.md).
