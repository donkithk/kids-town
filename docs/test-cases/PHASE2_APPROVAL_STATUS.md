# Phase 2 parent-approval test status (TDD RED)

> Recorded against **current `main` product** (no `backend_v2.py` / `index.html` gameplay change in this PR).  
> Branch: `cursor/phase2-approval-tdd-red-9a30`  
> Date: 2026-09-20  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux.

**Intentional RED.** Product still credits homework on `complete` and hardcodes `pending_approval=False`. There is no `require_approval` setting and no `POST /api/tasks/<id>/approve` or `/reject`. Do **not** implement the product change in this PR.

Marker: **`phase2`**. Catalog: [`PHASE2_APPROVAL.md`](PHASE2_APPROVAL.md). Spec: `GAMEPLAY_REDESIGN` §6.7.

**P1-TC-CER-03 marker move:** `tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves` is now `@pytest.mark.phase2` only (was collected by `phase1`). Not skipped. Folded into this catalog (overlaps P2-APR-02 / P2-APR-03). After the move, `pytest -m phase1` is **39 passed / 0 failed**.

Synthetic fixtures only: `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Commands (real numbers)

| Suite | Command | Result |
|-------|---------|--------|
| Phase 2 approval | `python3 -m pytest tests/ -m phase2 -v` | **7 failed, 3 passed**, 150 deselected, 2 warnings in 2.31s |
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **39 passed**, 121 deselected, 33 warnings in 9.56s |
| Phase 1.5 onboard | `python3 -m pytest tests/ -m phase1_5 -v` | **6 passed**, 154 deselected, 3 warnings in 1.73s |
| Frontend | `python3 -m pytest tests/test_frontend.py -v` | **26 passed**, 4 warnings in 27.15s |
| Not phase2 | `python3 -m pytest tests/ -m "not phase2" -q` | **150 passed**, 10 deselected, 56 warnings in 50.54s |
| Collection | `python3 -m pytest tests/ -m phase2 --collect-only -q` | **10 selected** / 160 collected (was 151; +9 APR + CER-03 still present) |

`not phase2` is fully green (CER-03 no longer in that set). Frontend stayed 26 green because FE contracts are **not** `@pytest.mark.frontend`.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| P2-APR-01 | `tests/test_approval.py::test_default_off_complete_credits_immediately` | **PASS** | default off: complete credits immediately; `pending_approval=false` |
| P2-APR-02 | `tests/test_approval.py::test_require_approval_complete_does_not_credit_and_foreshadows` | **FAIL** | cannot enable `require_approval` (no API/column); not skipped |
| P2-APR-03 | `tests/test_approval.py::test_parent_approve_credits_foreshadowed_amounts` | **FAIL** | same enable failure (route `/approve` also missing) |
| P2-APR-04 | `tests/test_approval.py::test_parent_reject_returns_task_incomplete_without_credits` | **FAIL** | same enable failure (route `/reject` also missing) |
| P2-APR-05 | `tests/test_approval.py::test_expedition_claim_and_battle_still_award_when_approval_on` | **FAIL** | cannot enable gate, so cannot prove explore/battle stay ungated |
| P2-APR-06 | `tests/test_approval.py::test_unauthenticated_approve_and_reject_return_401` | **PASS** | Phase 0 session gate already 401s unauthenticated POST even before the route exists; GREEN must **keep** 401 when adding `/approve` `/reject` |
| P2-APR-07 | `tests/test_approval.py::test_foreign_parent_and_kid_cannot_approve_returns_403` | **FAIL** | authenticated Parent B → **404** (no route); need **403** IDOR |
| P1-TC-CER-03 | `tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves` | **FAIL** | marker moved to `phase2`; still cannot enable `require_approval`; not skipped |
| P2-APR-FE-01 | `tests/test_approval_ui.py::test_complete_task_shows_waiting_copy_when_pending` | **PASS** | `completeTask` already shows 「✅ 做完喇！等爸爸媽媽確認就入帳」 |
| P2-APR-FE-02 | `tests/test_approval_ui.py::test_parent_manage_has_pending_approval_list` | **FAIL** | `renderManage` has no pending-approval queue / `/approve`. Playwright pending-list E2E = **Manual B** |

## Product code (this PR)

None in `backend_v2.py` / `index.html`. Test harness + catalogs only: `tests/test_approval.py`, `tests/test_approval_ui.py`, `pytest.ini` marker `phase2`, CER-03 marker move.

## Handoff for KT builder (GREEN PR)

1. `family_settings.require_approval` (or `parents.approve_rewards`), **default false**. Parent-facing toggle API. Tests probe several paths via `try_enable_require_approval` — do not skip if missing.
2. `POST /api/tasks/<id>/complete` when on: **do not** credit gold/XP/materials; `pending_approval=true`; JSON still foreshadows `points_awarded` / XP / `material_drops`.
3. `POST /api/tasks/<id>/approve` (owning parent only): then credit **exactly** the foreshadowed amounts.
4. `POST /api/tasks/<id>/reject` + `reason`: task back to incomplete; economy unchanged.
5. Short-explore `expedition/claim` and battle drops must **not** enter the approval queue (P2-APR-05).
6. Unauthenticated approve/reject stay **401** (already true). Parent B / kid approve → **403** (today 404).
7. Parent manage UI: pending list + approve (P2-APR-FE-02). Kid waiting copy already in `completeTask` (P2-APR-FE-01).
8. Turn **P1-TC-CER-03** green together with APR-02/03. **Do not skip.**
