# Phase 1 gameplay test status (TDD GREEN)

> Recorded against product implementation on branch `cursor/phase1-gameplay-tdd-green-9aed`.  
> Base: latest `main` (PR #9 red tests merged, commit `72b873e`).  
> Date: 2026-09-19  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium available on Linux.

## Commands (real numbers)

| Suite | Command | Result |
|-------|---------|--------|
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **39 passed, 1 failed**, 102 deselected, 33 warnings in 9.05s（GREEN 當時；**P1-TC-CER-03** 其後改標 `phase2`，見 Phase 2 目錄） |
| Rest of suite | `python3 -m pytest tests/ -m "not phase1" -q` | **102 passed**, 40 deselected, 20 warnings in 36.56s |
| Collection | `python3 -m pytest tests/ -m phase1 --collect-only -q` | **40 selected** / 142 collected |

Historical leftover red was **P1-TC-CER-03** only (Phase 2 `require_approval` / `GAMEPLAY_REDESIGN` §6.7). **Not skipped.** On 2026-09-20 the pytest marker moved `phase1` → `phase2` so `pytest -m phase1` no longer carries this intentional red. Executable coverage: [`PHASE2_APPROVAL.md`](PHASE2_APPROVAL.md) / [`PHASE2_APPROVAL_STATUS.md`](PHASE2_APPROVAL_STATUS.md).

Experience C re-verify (branch `cursor/harden-ceremony-place-e2e-17ad`, 2026-09-19): `pytest -m phase1` still **39 passed / 1 failed (CER-03)**; `not phase1` **105 passed** (was 102; +3 TC-FE-CEREMONY/PLACE cases). Collection 145. Details: [`FRONTEND_E2E_STATUS.md`](FRONTEND_E2E_STATUS.md).

Phase 1.5 GREEN re-verify (branch `cursor/onboard-tdd-green-0b05`, 2026-09-19): `pytest -m phase1` still **39 passed / 1 failed (CER-03)**; P1-TC-MAT-03 now asserts guild **wood/brick, no gear**. Details: [`PHASE1_5_ONBOARD_STATUS.md`](PHASE1_5_ONBOARD_STATUS.md).

Synthetic fixtures only: `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| P1-TC-BUFF-01 | `tests/test_building_buffs.py::test_library_level1_adds_task_bonus_xp` | **PASS** | library Lv.1: base 5 + bonus 2 = 7 XP; gold unchanged |
| P1-TC-BUFF-02 | `tests/test_building_buffs.py::test_no_library_task_bonus_is_zero` | **PASS** | `experience_bonus==0` without library |
| P1-TC-BUFF-03 | `tests/test_building_buffs.py::test_library_level2_uses_updated_buff_table` | **PASS** | Lv.2 `buff_vals[1]==4` |
| P1-TC-BUFF-04 | `tests/test_building_buffs.py::test_stored_library_does_not_grant_bonus` | **PASS** | stored library does not buff |
| P1-TC-BUFF-05 | `tests/test_building_buffs.py::test_farm_daily_gold_claim_once_per_hk_day` | **PASS** | HK-day claim +5; second 400 `already_claimed_today`; next day +5; anon 401 |
| P1-TC-BUFF-06 | `tests/test_building_buffs.py::test_farm_claim_without_farm_returns_farm_required` | **PASS** | 400 `farm_required` |
| P1-TC-BUFF-07 | `tests/test_building_buffs.py::test_shop_level1_discounts_gold_not_materials` | **PASS** | library gold 90, wood still 5 |
| P1-TC-BUFF-08 | `tests/test_building_buffs.py::test_placing_first_shop_pays_full_seed_price` | **PASS** | first shop still full 500 |
| P1-TC-BUFF-09 | `tests/test_building_buffs.py::test_get_building_buff_helper_farm_and_missing_types` | **PASS** | farm Lv.3 `daily_gold=15`; missing `task_bonus` → None |
| P1-TC-MAT-01 | `tests/test_materials_ids.py::test_expedition_claim_only_emits_canonical_material_ids` | **PASS** | claim pool wood/brick/glass/gear/gem + optional fur/dragon_scale |
| P1-TC-MAT-02 | `tests/test_materials_ids.py::test_internal_add_iron_normalizes_to_gear` | **PASS** | `add_item` + `canonicalize_item_type('iron')=='gear'` |
| P1-TC-MAT-03 | `tests/test_materials_ids.py::test_material_defs_and_building_recipes_use_canonical_ids` | **PASS** | defs include gem; seed recipes canonical; guild wood/brick **no gear** (Phase 1.5 §9 Q4) |
| P1-TC-MAT-04 | `tests/test_materials_ids.py::test_task_drop_pools_and_complete_use_canonical_ids` | **PASS** | `MATERIAL_POOLS` already canonical |
| P1-TC-MAT-05 | `tests/test_materials_ids.py::test_boss_summon_consumes_gem_not_glass` | **PASS** | Boss still costs `gem`×1 |
| P1-TC-REG-01 | `tests/test_region_lock.py::test_regions_1_2_3_battle_start_has_monsters_not_404` | **PASS** | regions 1–3 still have monsters |
| P1-TC-REG-02 | `tests/test_region_lock.py::test_region_4_battle_start_returns_region_locked` | **PASS** | 400 `region_locked` (not 404 No monster) |
| P1-TC-REG-03 | `tests/test_region_lock.py::test_region_5_battle_start_returns_region_locked` | **PASS** | same for region 5 |
| P1-TC-REG-04 | `tests/test_region_lock.py::test_region_4_explore_start_returns_region_locked` | **PASS** | explore start locked; gold not deducted |
| P1-TC-UNL-01 | `tests/test_unlock_region.py::test_lighthouse_requires_explored_region_3` | **PASS** | lighthouse place 400 `unlock_region` without r3 |
| P1-TC-UNL-02 | `tests/test_unlock_region.py::test_lighthouse_place_succeeds_after_region_3_explored` | **PASS** | explored 3 → lighthouse 201 |
| P1-TC-UNL-03 | `tests/test_unlock_region.py::test_arena_stays_locked_while_region_4_content_locked` | **PASS** | arena 400 `region_locked` even with explored 4 |
| P1-TC-CER-01 | `tests/test_task_ceremony.py::test_complete_json_includes_ceremony_fields` | **PASS** | bonus/total/pending_approval + HUD XP fields; XP not in points_log |
| P1-TC-CER-02 | `tests/test_task_ceremony.py::test_first_task_achievement_in_complete_response` | **PASS** | `first_task` still awarded |
| P1-TC-CER-03 | `tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves` | **PASS** (now `phase2`) | Marker moved 2026-09-20; GREEN in Phase 2. See [`PHASE2_APPROVAL_STATUS.md`](PHASE2_APPROVAL_STATUS.md) |
| P1-TC-CER-FE-01 | `tests/test_frontend_ceremony.py::test_complete_task_source_reads_xp_materials_achievements` | **PASS** | Weak source (A): `completeTask` reads XP/materials/achievements |
| P1-TC-CER-FE-01 | `tests/test_frontend.py::test_complete_task_ceremony_shows_xp_materials_achievements` | **PASS** | Playwright mock (A): toast shows XP + 🪵木材 + 🌟第一次任務 |
| P1-TC-XP-01 | `tests/test_xp_bar.py::test_calc_level_uses_exp_per_level_25` | **PASS** | `EXP_PER_LEVEL=25` unchanged |
| P1-TC-XP-02 | `tests/test_xp_bar.py::test_xp_bar_percent_uses_in_level_not_total` | **PASS** | helper uses in-level / for-next; `for_next==0` → 100 |
| P1-TC-XP-03 | `tests/test_xp_bar.py::test_get_experience_returns_hud_fields_not_500` | **PASS** | no `ability_atk` IndexError; HUD fields present |
| P1-TC-EXP-01 | `tests/test_expedition_gold.py::test_region1_short_explore_deducts_10_gold` | **PASS** | 15→5; `expedition_fee` log |
| P1-TC-EXP-02 | `tests/test_expedition_gold.py::test_insufficient_gold_does_not_start_or_charge` | **PASS** | 400 `insufficient_gold` need=10 have=9 |
| P1-TC-EXP-03 | `tests/test_expedition_gold.py::test_region_2_and_3_explore_fee_table` | **PASS** | region 2 −20, region 3 −30 |
| P1-TC-EXP-04 | `tests/test_expedition_gold.py::test_battle_start_does_not_charge_explore_fee` | **PASS** | battle still free |
| P1-TC-EXP-05 | `tests/test_expedition_gold.py::test_explore_can_be_farmed_again_after_claim` | **PASS** | second start after claim 201 |
| P1-TC-GLD-01 | `tests/test_guild_gate.py::test_explore_start_without_guild_returns_guild_required` | **PASS** | 400 `guild_required`; gold not deducted |
| P1-TC-GLD-02 | `tests/test_guild_gate.py::test_battle_start_without_guild_returns_guild_required` | **PASS** | battle-start also gated |
| P1-TC-GLD-03 | `tests/test_guild_gate.py::test_stored_guild_counts_as_no_guild` | **PASS** | stored guild = no guild |
| P1-TC-GLD-04 | `tests/test_guild_gate.py::test_unstored_guild_allows_explore_start` | **PASS** | unstored guild 201 |
| P1-TC-PLC-01 | `tests/test_unlock_region.py::test_place_building_api_does_not_depend_on_ui_entry` | **PASS** | POST `/buildings` 201 |
| P1-TC-PLC-FE-01 | `tests/test_frontend_placement.py::test_buildings_tab_build_button_calls_start_placement` | **PASS** | Weak source (A): 建築 tab calls `startPlacement` |

## Intentionally still red

| Case ID | Why |
|---------|-----|
| P1-TC-CER-03 | Folded into Phase 2 (`@pytest.mark.phase2`). GREEN: `require_approval` + `POST /api/tasks/<id>/approve`. |

## Frontend (A) vs (B)

| Case | Automatable (A) | Honest limit |
|------|-----------------|--------------|
| P1-TC-CER-FE-01 | Playwright mock **PASS** + weak `completeTask` source **PASS** | **(B) still required** — do not treat grep/source as full ceremony UX |
| TC-FE-CEREMONY-01 | Real complete Playwright **PASS** (gold + XP number + materials, no mock) | **(B) still required** — small-screen toast `nowrap` clipping; library +N copy |
| P1-TC-PLC-FE-01 | Weak source **PASS** (`startPlacement` on 建築 tab) | **(B) still required** |
| TC-FE-PLACE-SHOP-01 / TC-FE-PLACE-BUILD-01 | Playwright full path **PASS** (shop and 建築 tab → place → building on map) | **(B) still required** — overlapping green cells; 建築 tab does not auto-switch to map |

## Product code (this PR)

- `backend_v2.py`: `get_building_buff`, `canonicalize_item_type` / `add_item`, farm claim, shop discount, `region_locked`, `unlock_region`, ceremony fields, `xp_bar_percent`, explore fee, guild gate.
- `index.html`: ceremony toast (XP / materials / achievements); 建築 tab `startPlacement`; short-explore fee copy; regions 4–5 locked UI.
- `tests/conftest.py`: existing `battle_kid` fixture now seeds an unstored guild so pre-Phase-1 battle tests still 201 under the new server gate. Phase 1 GLD cases still use family kids without a guild.

No production `kids_town.db` copy.
