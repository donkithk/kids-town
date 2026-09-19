# Phase 1 gameplay test status (TDD RED)

> Recorded against **latest `main`** (no Phase 1 product code).  
> Commands:
> - `python -m pytest tests/ -m phase1 -v`
> - `python -m pytest tests/ -m "not phase1" -q`  
> Date: 2026-09-19  
> Results: **pending first run on this PR** — this file will be updated with honest PASS/FAIL after pytest.

Synthetic fixtures only (`test_parent_*` / `TestParent!pass1`, kid PIN `1357`). Production `kids_town.db` is never copied.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| P1-TC-BUFF-01 | `tests/test_building_buffs.py::test_library_level1_adds_task_bonus_xp` | TBD | |
| P1-TC-BUFF-02 | `tests/test_building_buffs.py::test_no_library_task_bonus_is_zero` | TBD | |
| P1-TC-BUFF-03 | `tests/test_building_buffs.py::test_library_level2_uses_updated_buff_table` | TBD | |
| P1-TC-BUFF-04 | `tests/test_building_buffs.py::test_stored_library_does_not_grant_bonus` | TBD | P1 |
| P1-TC-BUFF-05 | `tests/test_building_buffs.py::test_farm_daily_gold_claim_once_per_hk_day` | TBD | |
| P1-TC-BUFF-06 | `tests/test_building_buffs.py::test_farm_claim_without_farm_returns_farm_required` | TBD | |
| P1-TC-BUFF-07 | `tests/test_building_buffs.py::test_shop_level1_discounts_gold_not_materials` | TBD | |
| P1-TC-BUFF-08 | `tests/test_building_buffs.py::test_placing_first_shop_pays_full_seed_price` | TBD | P1 |
| P1-TC-BUFF-09 | `tests/test_building_buffs.py::test_get_building_buff_helper_farm_and_missing_types` | TBD | |
| P1-TC-MAT-01 | `tests/test_materials_ids.py::test_expedition_claim_only_emits_canonical_material_ids` | TBD | |
| P1-TC-MAT-02 | `tests/test_materials_ids.py::test_internal_add_iron_normalizes_to_gear` | TBD | |
| P1-TC-MAT-03 | `tests/test_materials_ids.py::test_material_defs_and_building_recipes_use_canonical_ids` | TBD | |
| P1-TC-MAT-04 | `tests/test_materials_ids.py::test_task_drop_pools_and_complete_use_canonical_ids` | TBD | |
| P1-TC-MAT-05 | `tests/test_materials_ids.py::test_boss_summon_consumes_gem_not_glass` | TBD | P1 |
| P1-TC-REG-01 | `tests/test_region_lock.py::test_regions_1_2_3_battle_start_has_monsters_not_404` | TBD | |
| P1-TC-REG-02 | `tests/test_region_lock.py::test_region_4_battle_start_returns_region_locked` | TBD | |
| P1-TC-REG-03 | `tests/test_region_lock.py::test_region_5_battle_start_returns_region_locked` | TBD | |
| P1-TC-REG-04 | `tests/test_region_lock.py::test_region_4_explore_start_returns_region_locked` | TBD | |
| P1-TC-UNL-01 | `tests/test_unlock_region.py::test_lighthouse_requires_explored_region_3` | TBD | |
| P1-TC-UNL-02 | `tests/test_unlock_region.py::test_lighthouse_place_succeeds_after_region_3_explored` | TBD | |
| P1-TC-UNL-03 | `tests/test_unlock_region.py::test_arena_stays_locked_while_region_4_content_locked` | TBD | P1 |
| P1-TC-CER-01 | `tests/test_task_ceremony.py::test_complete_json_includes_ceremony_fields` | TBD | |
| P1-TC-CER-02 | `tests/test_task_ceremony.py::test_first_task_achievement_in_complete_response` | TBD | |
| P1-TC-CER-03 | `tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves` | TBD | **Phase 2 dependency** — do not silent-skip |
| P1-TC-CER-FE-01 | `tests/test_frontend_ceremony.py::test_complete_task_source_reads_xp_materials_achievements` | TBD | Weak source (A); (B) manual required |
| P1-TC-CER-FE-01 | `tests/test_frontend.py::test_complete_task_ceremony_shows_xp_materials_achievements` | TBD | Playwright mock (A) if Chromium |
| P1-TC-XP-01 | `tests/test_xp_bar.py::test_calc_level_uses_exp_per_level_25` | TBD | |
| P1-TC-XP-02 | `tests/test_xp_bar.py::test_xp_bar_percent_uses_in_level_not_total` | TBD | |
| P1-TC-XP-03 | `tests/test_xp_bar.py::test_get_experience_returns_hud_fields_not_500` | TBD | |
| P1-TC-EXP-01 | `tests/test_expedition_gold.py::test_region1_short_explore_deducts_10_gold` | TBD | |
| P1-TC-EXP-02 | `tests/test_expedition_gold.py::test_insufficient_gold_does_not_start_or_charge` | TBD | |
| P1-TC-EXP-03 | `tests/test_expedition_gold.py::test_region_2_and_3_explore_fee_table` | TBD | |
| P1-TC-EXP-04 | `tests/test_expedition_gold.py::test_battle_start_does_not_charge_explore_fee` | TBD | |
| P1-TC-EXP-05 | `tests/test_expedition_gold.py::test_explore_can_be_farmed_again_after_claim` | TBD | |
| P1-TC-GLD-01 | `tests/test_guild_gate.py::test_explore_start_without_guild_returns_guild_required` | TBD | |
| P1-TC-GLD-02 | `tests/test_guild_gate.py::test_battle_start_without_guild_returns_guild_required` | TBD | |
| P1-TC-GLD-03 | `tests/test_guild_gate.py::test_stored_guild_counts_as_no_guild` | TBD | P1 |
| P1-TC-GLD-04 | `tests/test_guild_gate.py::test_unstored_guild_allows_explore_start` | TBD | |
| P1-TC-PLC-01 | `tests/test_unlock_region.py::test_place_building_api_does_not_depend_on_ui_entry` | TBD | P1 |
| P1-TC-PLC-FE-01 | `tests/test_frontend_placement.py::test_buildings_tab_build_button_calls_start_placement` | TBD | Weak source (A); (B) manual required |
