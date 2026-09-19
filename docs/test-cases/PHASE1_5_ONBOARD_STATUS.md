# Phase 1.5 onboarding pack test status (TDD RED)

> Recorded against **current `main` product** (no `backend_v2.py` / `index.html` gameplay change).  
> Branch: `cursor/onboard-tdd-red-7ff1`  
> Date: 2026-09-19  
> Python / pytest: fill after the verification run in this PR.

**Intentional RED.** Tests fail because guild seed is still ~600 gold + gear, and `create-kid` does not grant the 120 / wood×8 / brick×5 starter pack. Do **not** implement the product change in this PR.

Marker: **`phase1_5`** (not `onboard`). Catalog: [`PHASE1_5_ONBOARD.md`](PHASE1_5_ONBOARD.md).

Synthetic fixtures only: `test_onb_*` / `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Commands (placeholder — replace with real numbers after pytest)

| Suite | Command | Result |
|-------|---------|--------|
| Phase 1.5 onboard | `python3 -m pytest tests/ -m phase1_5 -v` | **TBD — expect RED** (guild cost + starter pack) |
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **must stay 39 passed, 1 failed (P1-TC-CER-03)** |
| Frontend | `python3 -m pytest tests/test_frontend.py -v` | **must stay 26 passed** |
| Not onboard marker | `python3 -m pytest tests/ -m "not phase1_5" -q` | **must match pre-PR main** (phase1 39/1 CER-03 + rest green) |

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| ONB-GUILD-01 | `tests/test_onboard.py::test_seed_guild_cost_is_150_wood10_brick5_no_gear` | **FAIL (expected)** | seed still 600 + wood/brick/gear |
| ONB-GUILD-02 | `tests/test_onboard.py::test_place_guild_with_exact_150_gold_and_wood_brick_succeeds` | **FAIL (expected)** | 150+wood10+brick5 insufficient vs old recipe |
| ONB-GUILD-03 | `tests/test_onboard.py::test_place_guild_with_149_gold_is_insufficient` | **PASS or FAIL** | 149 gold already 400 vs old 600; still required after GREEN |
| ONB-START-01 | `tests/test_onboard.py::test_create_kid_grants_starter_pack_120_wood8_brick5` | **FAIL (expected)** | points DEFAULT 0; no starter_granted |
| ONB-START-02 | `tests/test_onboard.py::test_starter_pack_is_not_double_granted` | **FAIL (expected)** | no pack to grant or double |
| ONB-EXP-01 | `tests/test_onboard.py::test_claim_region1_explore_then_start_again_is_unlimited` | **PASS (expected)** | same as P1-TC-EXP-05; no daily cap |

## Product code (this PR)

None in `backend_v2.py` / `index.html`. Test harness only: `tests/test_onboard.py`, `tests/phase1_helpers.py` constants, `pytest.ini` marker `phase1_5`.

## Handoff for KT builder (GREEN PR)

1. `seed_building_defs` 探險公會：`cost_gold=150`, `materials={"wood":10,"brick":5}` — **delete gear key**.
2. `POST /api/auth/create-kid`: set `points=120`, inventory wood×8 brick×5, `starter_granted=1` (JSON + DB). Idempotent per kid.
3. Second sibling gets their **own** pack; login / already-granted kid does not add another 120/8/5.
4. Do **not** add a daily explore cap. Keep EXP fees 10/20/30. Keep `P1-TC-EXP-05`.
5. Update **`P1-TC-MAT-03`** (`assert "gear" in guild_mats`) in the GREEN PR — this RED PR left it alone so `pytest -m phase1` stays 39/1.
