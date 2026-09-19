# Phase 1 gameplay test status (TDD RED)

> Recorded against **latest `main`** (commit `9c4da41`, no Phase 1 product code) on branch `cursor/phase1-gameplay-tdd-red-e548`.  
> Date: 2026-09-19  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium available on Linux.

## Commands (real numbers)

| Suite | Command | Result |
|-------|---------|--------|
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **29 failed, 11 passed**, 102 deselected, 40 warnings in 10.37s |
| Rest of suite | `python3 -m pytest tests/ -m "not phase1" -q` | **102 passed**, 40 deselected, 20 warnings in 33.11s |
| Collection | `python3 -m pytest tests/ -m phase1 --collect-only -q` | **40 selected** / 142 collected |

Intentional: `pytest -m phase1` is **RED**. Existing green suite (`not phase1`, including Phase 0 + frontend E2E) stayed green. No new skips.

Synthetic fixtures only: `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| P1-TC-BUFF-01 | `tests/test_building_buffs.py::test_library_level1_adds_task_bonus_xp` | **FAIL** | no `experience_bonus` (got `None`; base XP 5 still awarded) |
| P1-TC-BUFF-02 | `tests/test_building_buffs.py::test_no_library_task_bonus_is_zero` | **FAIL** | missing `experience_bonus` key |
| P1-TC-BUFF-03 | `tests/test_building_buffs.py::test_library_level2_uses_updated_buff_table` | **FAIL** | missing `experience_bonus==4` |
| P1-TC-BUFF-04 | `tests/test_building_buffs.py::test_stored_library_does_not_grant_bonus` | **FAIL** | P1; missing `experience_bonus` key |
| P1-TC-BUFF-05 | `tests/test_building_buffs.py::test_farm_daily_gold_claim_once_per_hk_day` | **FAIL** | `POST /farm/claim` → **404** (route missing) |
| P1-TC-BUFF-06 | `tests/test_building_buffs.py::test_farm_claim_without_farm_returns_farm_required` | **FAIL** | 404 HTML, not 400 `farm_required` |
| P1-TC-BUFF-07 | `tests/test_building_buffs.py::test_shop_level1_discounts_gold_not_materials` | **FAIL** | deducted 100, expect 90 (`points==100` not 110) |
| P1-TC-BUFF-08 | `tests/test_building_buffs.py::test_placing_first_shop_pays_full_seed_price` | **PASS** | guard: first shop still full 500 |
| P1-TC-BUFF-09 | `tests/test_building_buffs.py::test_get_building_buff_helper_farm_and_missing_types` | **FAIL** | `get_building_buff` missing |
| P1-TC-MAT-01 | `tests/test_materials_ids.py::test_expedition_claim_only_emits_canonical_material_ids` | **FAIL** | claim still drops `iron`, `star_shard`, `star_stone`, `mystery_box` |
| P1-TC-MAT-02 | `tests/test_materials_ids.py::test_internal_add_iron_normalizes_to_gear` | **FAIL** | no `add_item` / `canonicalize_item_type` |
| P1-TC-MAT-03 | `tests/test_materials_ids.py::test_material_defs_and_building_recipes_use_canonical_ids` | **FAIL** | `GET /materials/defs` missing `gem`; seed recipes still have `iron`/`star_shard` |
| P1-TC-MAT-04 | `tests/test_materials_ids.py::test_task_drop_pools_and_complete_use_canonical_ids` | **PASS** | guard: `MATERIAL_POOLS` already canonical (no `iron`) |
| P1-TC-MAT-05 | `tests/test_materials_ids.py::test_boss_summon_consumes_gem_not_glass` | **PASS** | P1 guard: Boss already costs `gem`×1 |
| P1-TC-REG-01 | `tests/test_region_lock.py::test_regions_1_2_3_battle_start_has_monsters_not_404` | **PASS** | guard: regions 1–3 have monsters |
| P1-TC-REG-02 | `tests/test_region_lock.py::test_region_4_battle_start_returns_region_locked` | **FAIL** | 404 `No monster for this region` (not 400 `region_locked`) |
| P1-TC-REG-03 | `tests/test_region_lock.py::test_region_5_battle_start_returns_region_locked` | **FAIL** | same as REG-02 for region 5 |
| P1-TC-REG-04 | `tests/test_region_lock.py::test_region_4_explore_start_returns_region_locked` | **FAIL** | explore start region 4 currently **201** |
| P1-TC-UNL-01 | `tests/test_unlock_region.py::test_lighthouse_requires_explored_region_3` | **FAIL** | lighthouse place **201** with no r3 explore |
| P1-TC-UNL-02 | `tests/test_unlock_region.py::test_lighthouse_place_succeeds_after_region_3_explored` | **PASS** | guard: place already 201 when resources + explored 3 (unlock not wired, so this is a happy-path guard) |
| P1-TC-UNL-03 | `tests/test_unlock_region.py::test_arena_stays_locked_while_region_4_content_locked` | **FAIL** | P1; arena place **201** even with explored 4 |
| P1-TC-CER-01 | `tests/test_task_ceremony.py::test_complete_json_includes_ceremony_fields` | **FAIL** | missing `experience_bonus`, `experience_total`, `pending_approval`, `kid.experience_in_level` |
| P1-TC-CER-02 | `tests/test_task_ceremony.py::test_first_task_achievement_in_complete_response` | **PASS** | guard: `first_task` already in complete JSON |
| P1-TC-CER-03 | `tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves` | **FAIL** | **Phase 2 dependency** — no `require_approval` API/column; **not skipped** |
| P1-TC-CER-FE-01 | `tests/test_frontend_ceremony.py::test_complete_task_source_reads_xp_materials_achievements` | **FAIL** | Weak source (A): `completeTask` does not read XP/materials. **(B) manual required** — grep is not full UX (A) |
| P1-TC-CER-FE-01 | `tests/test_frontend.py::test_complete_task_ceremony_shows_xp_materials_achievements` | **FAIL** | Playwright mock (A) on Linux Chromium: toast is gold-only `獲得 🪙10` |
| P1-TC-XP-01 | `tests/test_xp_bar.py::test_calc_level_uses_exp_per_level_25` | **PASS** | guard: `EXP_PER_LEVEL=25` already matches spec; **do not raise to 100** |
| P1-TC-XP-02 | `tests/test_xp_bar.py::test_xp_bar_percent_uses_in_level_not_total` | **FAIL** | `xp_bar_percent` missing |
| P1-TC-XP-03 | `tests/test_xp_bar.py::test_get_experience_returns_hud_fields_not_500` | **FAIL** | `IndexError` on `ability_atk` (TESTING re-raises; would be 500) |
| P1-TC-EXP-01 | `tests/test_expedition_gold.py::test_region1_short_explore_deducts_10_gold` | **FAIL** | points stay 15 (no fee) |
| P1-TC-EXP-02 | `tests/test_expedition_gold.py::test_insufficient_gold_does_not_start_or_charge` | **FAIL** | start **201** with 9 gold (no `insufficient_gold`) |
| P1-TC-EXP-03 | `tests/test_expedition_gold.py::test_region_2_and_3_explore_fee_table` | **FAIL** | no 20/30 deduction |
| P1-TC-EXP-04 | `tests/test_expedition_gold.py::test_battle_start_does_not_charge_explore_fee` | **PASS** | guard: battle already free |
| P1-TC-EXP-05 | `tests/test_expedition_gold.py::test_explore_can_be_farmed_again_after_claim` | **PASS** | guard: backend already allows second start (frontend still blocks) |
| P1-TC-GLD-01 | `tests/test_guild_gate.py::test_explore_start_without_guild_returns_guild_required` | **FAIL** | start **201** without guild |
| P1-TC-GLD-02 | `tests/test_guild_gate.py::test_battle_start_without_guild_returns_guild_required` | **FAIL** | battle-start **201** without guild |
| P1-TC-GLD-03 | `tests/test_guild_gate.py::test_stored_guild_counts_as_no_guild` | **FAIL** | P1; stored guild still 201 |
| P1-TC-GLD-04 | `tests/test_guild_gate.py::test_unstored_guild_allows_explore_start` | **PASS** | guard: start already 201 with guild |
| P1-TC-PLC-01 | `tests/test_unlock_region.py::test_place_building_api_does_not_depend_on_ui_entry` | **PASS** | P1 guard: one POST buildings API already 201 |
| P1-TC-PLC-FE-01 | `tests/test_frontend_placement.py::test_buildings_tab_build_button_calls_start_placement` | **FAIL** | Weak source (A): 建築 tab 建造 is `showToast('點擊下方空地…')` not `startPlacement`. **(B) manual required** |

## Accidentally passing guards (keep)

These are **not** evidence that Phase 1 gameplay is done. Leave them as regression guards:

1. **BUFF-08** — first shop still costs seed 500.
2. **MAT-04** — task `MATERIAL_POOLS` already wood/brick/glass/gear.
3. **MAT-05** — Boss summon already consumes `gem` not glass.
4. **REG-01** — regions 1–3 `battle-start` returns monsters (not 404).
5. **UNL-02** — lighthouse 201 when resources exist (unlock_region still not enforced; UNL-01 is the red counterpart).
6. **CER-02** — `first_task` already appears on first complete.
7. **XP-01** — `calc_level` / `EXP_PER_LEVEL=25` already match spec.
8. **EXP-04** — battle-start does not charge explore fee.
9. **EXP-05** — backend allows re-farm after claim (UI still shows 已完成).
10. **GLD-04** — with an unstored guild, explore start is 201.
11. **PLC-01** — POST `/buildings` with `cell_x/cell_y` already 201.

## Frontend (A) vs (B)

| Case | Automatable (A) | Honest limit |
|------|-----------------|--------------|
| P1-TC-CER-FE-01 | Playwright mock **FAIL** (Linux Chromium) + weak `completeTask` source **FAIL** | **(B) still required** — do not treat grep/source as full ceremony UX |
| P1-TC-PLC-FE-01 | Weak source **FAIL** (`startPlacement` missing on 建築 tab) | **(B) still required** — click 商店 and 建築 建造 once |

## Test-only harness (not product)

- `tests/factories.py`: `insert_building`, `grant_inventory`, `force_expedition_claimable`, `mark_expeditions_completed` (SQL / `end_time` backdate).
- `tests/phase1_helpers.py`: catalog constants + login/task helpers.
- `freezegun` in `requirements.txt` for farm HK-day (BUFF-05).
- `pytest.ini` marker `phase1`.

No `backend_v2.py` / `index.html` gameplay implementation in this PR.
