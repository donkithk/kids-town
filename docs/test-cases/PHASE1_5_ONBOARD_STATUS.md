# Phase 1.5 onboarding pack test status (TDD RED)

> Recorded against **current `main` product** (no `backend_v2.py` / `index.html` gameplay change).  
> Branch: `cursor/onboard-tdd-red-7ff1`  
> Date: 2026-09-19  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux.

**Intentional RED.** Tests fail because guild seed is still **600 gold + wood×25 + brick×20 + gear×10**, and `create-kid` still starts at **points=0** with no `starter_granted`. Do **not** implement the product change in this PR.

Marker: **`phase1_5`** (not `onboard`). Catalog: [`PHASE1_5_ONBOARD.md`](PHASE1_5_ONBOARD.md).

Synthetic fixtures only: `test_onb_*` / `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Commands (real numbers)

| Suite | Command | Result |
|-------|---------|--------|
| Phase 1.5 onboard | `python3 -m pytest tests/ -m phase1_5 -v` | **4 failed, 2 passed**, 145 deselected, 3 warnings in 1.79s |
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **39 passed, 1 failed**, 111 deselected, 33 warnings in 9.34s |
| Frontend | `python3 -m pytest tests/test_frontend.py -v` | **26 passed**, 4 warnings in 29.58s |
| Not onboard marker | `python3 -m pytest tests/ -m "not phase1_5" -q` | **144 passed, 1 failed**, 6 deselected, 53 warnings in 45.11s |
| Collection | `python3 -m pytest tests/ -m phase1_5 --collect-only -q` | **6 selected** / 151 collected (was 145; +6 ONB) |

Phase 1 leftover red is still **only P1-TC-CER-03**. Frontend stayed 26 green. `not phase1_5` is pre-PR main (144 pass + CER-03).

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| ONB-GUILD-01 | `tests/test_onboard.py::test_seed_guild_cost_is_150_wood10_brick5_no_gear` | **FAIL** | seed `cost_gold==600`, materials `{"wood":25,"brick":20,"gear":10}` |
| ONB-GUILD-02 | `tests/test_onboard.py::test_place_guild_with_exact_150_gold_and_wood_brick_succeeds` | **FAIL** | 150+wood10+brick5 → 400 `Insufficient resources` (old 600+gear recipe) |
| ONB-GUILD-03 | `tests/test_onboard.py::test_place_guild_with_149_gold_is_insufficient` | **PASS** | 149 gold already 400 vs old 600; still required after GREEN (1 gold short of 150) |
| ONB-START-01 | `tests/test_onboard.py::test_create_kid_grants_starter_pack_120_wood8_brick5` | **FAIL** | create-kid JSON `points==0` (need 120); no pack |
| ONB-START-02 | `tests/test_onboard.py::test_starter_pack_is_not_double_granted` | **FAIL** | `starter_granted` missing from JSON and `kids` row |
| ONB-EXP-01 | `tests/test_onboard.py::test_claim_region1_explore_then_start_again_is_unlimited` | **PASS** | same as P1-TC-EXP-05; no daily explore cap; fee table untouched |

## Product code (this PR)

None in `backend_v2.py` / `index.html`. Test harness only: `tests/test_onboard.py`, `tests/phase1_helpers.py` constants (`GUILD_COST_GOLD=150`, `STARTER_POINTS=120`, `STARTER_MATERIALS`), `pytest.ini` marker `phase1_5`.

## Handoff for KT builder (GREEN PR)

1. `seed_building_defs` 探險公會：`cost_gold=150`, `materials={"wood":10,"brick":5}` — **delete gear key**.
2. `POST /api/auth/create-kid`: set `points=120`, inventory wood×8 brick×5, `starter_granted=1` (JSON + DB). Idempotent per kid.
3. Second sibling gets their **own** pack; login / already-granted kid does not add another 120/8/5.
4. Do **not** add a daily explore cap. Keep EXP fees 10/20/30. Keep `P1-TC-EXP-05`.
5. Update **`P1-TC-MAT-03`** (`assert "gear" in guild_mats`) in the GREEN PR — this RED PR left it alone so `pytest -m phase1` stays 39/1.
