# Phase 2 parent-approval test status (TDD GREEN)

> Recorded against product implementation on branch `cursor/phase2-approval-green-05f4`.  
> Base: latest `main` (PR #14 red tests merged, commit `57a4c60`).  
> Date: 2026-09-20  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium on Linux.

**GREEN.** Family setting `parents.require_approval` defaults **false**. When on, homework `complete` foreshadows rewards with `pending_approval=true` and does not credit gold/XP/materials until owning parent `POST /api/tasks/<id>/approve`. Reject returns the task to incomplete without deducting ungranted rewards. Short-explore claim and battle drops stay ungated. Unauthenticated approve/reject stay **401**; Parent B / kid get **403**.

Marker: **`phase2`**. Catalog: [`PHASE2_APPROVAL.md`](PHASE2_APPROVAL.md). Spec: `GAMEPLAY_REDESIGN` §6.7.

Synthetic fixtures only: `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

Tiny harness only: `_force_running_battle_monsters_hp` keeps a single 1-HP monster so one attack can win (region battles spawn 1–3). No assertion rewrites.

## Commands (real numbers)

| Suite | Command | Result |
|-------|---------|--------|
| Phase 2 approval | `python3 -m pytest tests/ -m phase2 -v` | **10 passed**, 150 deselected, 13 warnings in 1.90s |
| Phase 1 | `python3 -m pytest tests/ -m phase1 -v` | **39 passed**, 121 deselected, 33 warnings in 7.79s |
| Phase 1.5 onboard | `python3 -m pytest tests/ -m phase1_5 -v` | **6 passed**, 154 deselected, 3 warnings in 1.29s |
| Frontend | `python3 -m pytest tests/test_frontend.py -v` | **26 passed**, 4 warnings in 25.75s |

`P1-TC-CER-03` is `phase2` and **PASS** (not skipped). Frontend stayed 26 green.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| P2-APR-01 | `tests/test_approval.py::test_default_off_complete_credits_immediately` | **PASS** | default off: complete credits immediately; `pending_approval=false` |
| P2-APR-02 | `tests/test_approval.py::test_require_approval_complete_does_not_credit_and_foreshadows` | **PASS** | gate on: no gold/XP/inventory change; JSON still foreshadows |
| P2-APR-03 | `tests/test_approval.py::test_parent_approve_credits_foreshadowed_amounts` | **PASS** | owning parent approve credits exact foreshadowed amounts |
| P2-APR-04 | `tests/test_approval.py::test_parent_reject_returns_task_incomplete_without_credits` | **PASS** | reject + reason → incomplete; economy unchanged |
| P2-APR-05 | `tests/test_approval.py::test_expedition_claim_and_battle_still_award_when_approval_on` | **PASS** | claim + battle win credit while homework stays pending |
| P2-APR-06 | `tests/test_approval.py::test_unauthenticated_approve_and_reject_return_401` | **PASS** | unauthenticated POST still **401** after routes exist |
| P2-APR-07 | `tests/test_approval.py::test_foreign_parent_and_kid_cannot_approve_returns_403` | **PASS** | Parent B / kid → **403** IDOR |
| P1-TC-CER-03 | `tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves` | **PASS** | pending complete then approve credits `points_awarded` |
| P2-APR-FE-01 | `tests/test_approval_ui.py::test_complete_task_shows_waiting_copy_when_pending` | **PASS** | `completeTask` waiting copy |
| P2-APR-FE-02 | `tests/test_approval_ui.py::test_parent_manage_has_pending_approval_list` | **PASS** | manage pending list + `approveTask` / `/approve`. Playwright pending-list E2E = **Manual B** |

## Product code (this PR)

- `backend_v2.py`: `parents.require_approval` (default 0); `POST/GET /api/family/settings`; complete defers rewards when on; `POST /api/tasks/<id>/approve` and `/reject`; ceremony foreshadow stored in `tasks.pending_rewards`.
- `index.html`: parent manage pending-approval list, approve/reject, require-approval toggle; kid waiting copy already present.
