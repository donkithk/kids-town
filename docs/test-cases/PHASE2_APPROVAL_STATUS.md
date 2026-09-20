# Phase 2 parent-approval test status (TDD RED)

> Recorded against **current `main` product** (no `backend_v2.py` / `index.html` gameplay change in this PR).  
> Branch: `cursor/phase2-approval-tdd-red-9a30`  
> Date: 2026-09-20  
> Python / pytest / Playwright: fill after the recorded run in this PR.

**Intentional RED.** Product still credits homework on `complete` and hardcodes `pending_approval=False`. There is no `require_approval` setting and no `POST /api/tasks/<id>/approve` or `/reject`. Do **not** implement the product change in this PR.

Marker: **`phase2`**. Catalog: [`PHASE2_APPROVAL.md`](PHASE2_APPROVAL.md). Spec: `GAMEPLAY_REDESIGN` §6.7.

**P1-TC-CER-03 marker move:** `tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves` is now `@pytest.mark.phase2` only (was collected by `phase1`). Not skipped. Folded into this catalog (overlaps P2-APR-02 / P2-APR-03).

Synthetic fixtures only: `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Commands (real numbers)

*Placeholder — this file is updated with honest pytest counts after the recorded run.*

| Suite | Command | Result |
|-------|---------|--------|
| Phase 2 approval | `python3 -m pytest tests/ -m phase2 -v` | **pending run** |
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **pending run** (expect 39 passed / 0 failed if CER-03 moved) |
| Phase 1.5 onboard | `python3 -m pytest tests/ -m phase1_5 -v` | **pending run** (expect 6 passed) |
| Frontend | `python3 -m pytest tests/test_frontend.py -v` | **pending run** (expect 26 passed) |
| Not phase2 | `python3 -m pytest tests/ -m "not phase2" -q` | **pending run** |

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| P2-APR-01 | `tests/test_approval.py::test_default_off_complete_credits_immediately` | pending | default off; Phase 1 path |
| P2-APR-02 | `tests/test_approval.py::test_require_approval_complete_does_not_credit_and_foreshadows` | pending | enable gate + no credit |
| P2-APR-03 | `tests/test_approval.py::test_parent_approve_credits_foreshadowed_amounts` | pending | `/approve` |
| P2-APR-04 | `tests/test_approval.py::test_parent_reject_returns_task_incomplete_without_credits` | pending | `/reject` |
| P2-APR-05 | `tests/test_approval.py::test_expedition_claim_and_battle_still_award_when_approval_on` | pending | gate must not block explore/battle |
| P2-APR-06 | `tests/test_approval.py::test_unauthenticated_approve_and_reject_return_401` | pending | session gate |
| P2-APR-07 | `tests/test_approval.py::test_foreign_parent_and_kid_cannot_approve_returns_403` | pending | IDOR |
| P1-TC-CER-03 | `tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves` | pending | marker moved to phase2 |
| P2-APR-FE-01 | `tests/test_approval_ui.py::test_complete_task_shows_waiting_copy_when_pending` | pending | source contract |
| P2-APR-FE-02 | `tests/test_approval_ui.py::test_parent_manage_has_pending_approval_list` | pending | source contract; Playwright = Manual B |

## Product code (this PR)

None in `backend_v2.py` / `index.html`. Test harness + catalogs only.

## Handoff for KT builder (GREEN PR)

See catalog closing section and the PR body. Do not silent-skip these cases.
