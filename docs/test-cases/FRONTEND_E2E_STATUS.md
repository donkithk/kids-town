# Frontend E2E status

> Recorded against branch `cursor/harden-ceremony-place-e2e-17ad` (Experience C — real-device hardening).  
> Base: latest `main` (`4f6cdda`, Phase 1 merged).  
> Date: 2026-09-19  
> Chromium: Playwright bundled browser.  
> Synthetic fixture users only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`). Production `kids_town.db` is never copied.

Pytest numbers are filled after the verification run (see PR body). **P1-TC-CER-03** stays red / Phase 2 — not skipped.

## Mapping (pre-existing)

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| TC-FE-01 … FE-XSS-02 | see prior STATUS | pending re-run | Must stay green |
| P1-TC-CER-FE-01 | `test_complete_task_ceremony_shows_xp_materials_achievements` | pending | Mock route; **not** full UX (B) |
| P1-TC-CER-FE-01 | `tests/test_frontend_ceremony.py` | pending | Weak source (A) |
| P1-TC-PLC-FE-01 | `tests/test_frontend_placement.py` | pending | Weak source (A) |

## Experience C (this PR)

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| TC-FE-CEREMONY-01 | `test_real_task_complete_ceremony_shows_gold_xp_and_materials` | pending | Real complete; gold+XP+materials; may stay RED if gold-only toast |
| TC-FE-PLACE-SHOP-01 | `test_shop_build_enters_placement_and_building_appears_on_map` | pending | Shop → startPlacement → valid-plot → confirm |
| TC-FE-PLACE-BUILD-01 | `test_buildings_tab_build_enters_placement_and_building_appears_on_map` | pending | 建築 tab → startPlacement → 小鎮地圖 → place |

(B) remaining steps: [`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md). Do not treat grep as full (A).
