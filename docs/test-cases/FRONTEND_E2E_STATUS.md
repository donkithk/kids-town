# Frontend E2E status

> Recorded against branch `cursor/phase0-playwright-ui-e2e-d6a9` (Phase 0 product from PR #4 + this Playwright harness).  
> Command: `python -m pytest tests/test_frontend.py -v`  
> Date: 2026-09-18  
> Chromium: Playwright bundled browser (`python -m playwright install chromium`).

Synthetic fixture users only. Production `kids_town.db` is never copied.

## Mapping (pending first green run on this PR)

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| TC-FE-01 | `test_login_shows_town_hud` | pending | |
| TC-FE-02 | `test_ability_panel_shows_five_attributes` | pending | |
| TC-FE-03 | `test_battle_flow_attack` | pending | |
| TC-FE-04 | `test_boss_summon_entry_in_battle_lobby` | pending | |
| TC-FE-05 | `test_battle_win_shows_rarity` | pending | |
| TC-FE-06 | `test_battle_not_marked_coming_soon` | pending | |
| TC-FE-07 | `test_parent_register_flow` | pending | |
| TC-FE-08 | `test_parent_create_kid_ui` | pending | |
| TC-FE-09 | `test_kid_only_sees_own_and_global_tasks` | pending | |
| (harness) | `test_battle_starts_despite_stale_running_expedition` | pending | |
| (harness) | `test_boss_summon_despite_stale_running_expedition` | pending | |
| (harness) | `test_boss_button_shows_cost_and_confirm` | pending | |
| FE-P0-01 | `test_unauthenticated_ui_cannot_complete_task_or_adjust_points` | pending | |
| FE-P0-02 | `test_kid_login_ui_does_not_display_raw_pin` | pending | |
| FE-P0-03 | `test_parent_a_ui_cannot_manage_parent_b_kid` | pending | |
| FE-P0-04 | `test_browser_static_denylist_db_and_python` | pending | |
| FE-P0-05 | `test_default_admin_login_fails_on_fresh_db` | pending | |

Phase 0 API marker run is tracked separately in [`PHASE0_SECURITY_STATUS.md`](PHASE0_SECURITY_STATUS.md).
