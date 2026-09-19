# Frontend E2E status

> Recorded against branch `cursor/green-fe-xss-01-task-title-encoding-b390` (based on latest `main` / PR #7).  
> Command: `python3 -m pytest tests/test_frontend.py -v`  
> Date: 2026-09-19  
> Chromium: Playwright bundled browser (`python3 -m playwright install chromium`).  
> Result: **22 passed, 0 failed** (`FE-XSS-01` green — task titles encoded as plain text).

Also: `python3 -m pytest tests/ -m phase0 -v` → **33 passed**.  
Full suite: `python3 -m pytest tests/ -q` → **102 passed, 0 failed**.

Synthetic fixture users only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`). Production `kids_town.db` is never copied.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| TC-FE-01 | `test_login_shows_town_hud` | **PASS** | Kid PIN login → HUD |
| TC-FE-02 | `test_ability_panel_shows_five_attributes` | **PASS** | `#hudTip` contains 臂力, not 體力 |
| TC-FE-03 | `test_battle_flow_attack` | **PASS** | 野狼 + 攻擊 |
| TC-FE-04 | `test_boss_summon_entry_in_battle_lobby` | **PASS** | |
| TC-FE-05 | `test_battle_win_shows_rarity` | **PASS** | |
| TC-FE-06 | `test_battle_lobby_boss_cost_confirm_not_coming_soon` | **PASS** | No 即將開放 + Boss 💎 + dismiss confirm |
| TC-FE-10 | `test_battle_daily_region_limit_blocks_second_start` | **PASS** | Seeded `daily_battles` → 400 + 「今日」toast |
| TC-FE-07 | `test_parent_register_flow` | **PASS** | |
| TC-FE-08 | `test_parent_create_kid_ui` | **PASS** | |
| TC-FE-09 | `test_kid_only_sees_own_and_global_tasks` | **PASS** | |
| TC-FE-JOURNEY-01 | `test_parent_assigns_task_kid_completes_hud_gold` | **PASS** | Parent assign → kid complete → HUD gold + toast |
| (harness) | `test_battle_starts_despite_stale_running_expedition` | **PASS** | |
| (harness) | `test_boss_summon_despite_stale_running_expedition` | **PASS** | |
| (harness) | `test_boss_button_shows_cost_and_confirm` | **PASS** | Original cost/confirm harness kept |
| FE-P0-01 | `test_unauthenticated_ui_cannot_complete_task_or_adjust_points` | **PASS** | |
| FE-P0-02 | `test_kid_login_ui_does_not_display_raw_pin` | **PASS** | |
| FE-P0-03 | `test_parent_a_ui_cannot_manage_parent_b_kid` | **PASS** | |
| FE-P0-04 | `test_browser_static_denylist_db_and_python` | **PASS** | |
| FE-P0-05 | `test_default_admin_login_fails_on_fresh_db` | **PASS** | |
| FE-P0-06 | `test_logout_then_write_apis_return_401` | **PASS** | Kid + parent UI 登出 → writes 401 |
| FE-XSS-01 | `test_task_title_markup_is_plain_text_not_html` | **PASS** | `escapeHtml()` — `<b>粗體</b>` shows as text, no real `<b>` / `<img>` |
| FE-XSS-02 | `test_kid_display_name_markup_is_plain_text_in_hud` | **PASS** | `#hudNm` `textContent` shows tags as text; no alert |

Phase 0 API marker run is tracked separately in [`PHASE0_SECURITY_STATUS.md`](PHASE0_SECURITY_STATUS.md).
