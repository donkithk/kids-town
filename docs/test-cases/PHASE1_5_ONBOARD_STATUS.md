# Phase 1.5 onboarding pack test status (TDD GREEN)

> Recorded against product implementation on branch `cursor/onboard-tdd-green-0b05`.  
> Base: latest `main` (PR #12 red tests merged, commit `d94af8a`).  
> Date: 2026-09-19  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux.

**GREEN.** Guild seed is **150 gold + wood×10 + brick×5** (no `gear` key). `POST /api/auth/create-kid` grants **points=120**, **wood×8**, **brick×5**, **`starter_granted=1`** once per kid.

Marker: **`phase1_5`** (not `onboard`). Catalog: [`PHASE1_5_ONBOARD.md`](PHASE1_5_ONBOARD.md).

Synthetic fixtures only: `test_onb_*` / `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Commands (real numbers)

| Suite | Command | Result |
|-------|---------|--------|
| Phase 1.5 onboard | `python3 -m pytest tests/ -m phase1_5 -v` | **6 passed**, 145 deselected, 3 warnings in 2.29s |
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **39 passed, 1 failed**, 111 deselected, 33 warnings in 11.00s |
| Frontend | `python3 -m pytest tests/test_frontend.py -v` | **26 passed**, 4 warnings in 28.83s |
| Not onboard marker | `python3 -m pytest tests/ -m "not phase1_5" -q` | **144 passed, 1 failed**, 6 deselected, 53 warnings in 50.57s |

Phase 1 leftover red is still **only P1-TC-CER-03** (Phase 2 `require_approval`). No new reds from the guild/starter change. Frontend stayed 26 green.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| ONB-GUILD-01 | `tests/test_onboard.py::test_seed_guild_cost_is_150_wood10_brick5_no_gear` | **PASS** | seed + `GET /api/building-defs`: `cost_gold==150`, `{"wood":10,"brick":5}`, no gear key |
| ONB-GUILD-02 | `tests/test_onboard.py::test_place_guild_with_exact_150_gold_and_wood_brick_succeeds` | **PASS** | 150+wood10+brick5 → 201; gold/materials deducted to 0 |
| ONB-GUILD-03 | `tests/test_onboard.py::test_place_guild_with_149_gold_is_insufficient` | **PASS** | 149 gold → 400 insufficient; 1 gold short of 150 |
| ONB-START-01 | `tests/test_onboard.py::test_create_kid_grants_starter_pack_120_wood8_brick5` | **PASS** | create-kid JSON+DB `points==120`; wood=8 brick=5; `starter_granted` |
| ONB-START-02 | `tests/test_onboard.py::test_starter_pack_is_not_double_granted` | **PASS** | login does not re-grant; sibling gets own 120/8/5 |
| ONB-EXP-01 | `tests/test_onboard.py::test_claim_region1_explore_then_start_again_is_unlimited` | **PASS** | no daily explore cap; fee table still 10/20/30 |

## Product code (this PR)

- `backend_v2.py`: `GUILD_COST_GOLD=150`, `DEFAULT_GUILD_MATERIALS={"wood":10,"brick":5}`; seed + migrate `_apply_guild_onboard_recipe`; `kids.starter_granted`; `grant_starter_pack_once` on `POST /api/auth/create-kid`.
- `index.html`: guild-gate copy 600🪙 → 150🪙.
- `tests/test_materials_ids.py`: **P1-TC-MAT-03** no longer requires guild `gear` (wood/brick only).
- `tests/conftest.py`: family fixture still resets gold and clears starter inventory so other suites keep an empty-bag baseline.

Short-explore fees unchanged. No daily explore cap.
