"""P2-APR-FE-* — kid waiting copy + parent pending list (GAMEPLAY_REDESIGN §6.7).

Weak source contracts on index.html. Not @pytest.mark.frontend — keep the
Playwright suite (tests/test_frontend.py) at 26 green. Playwright / real-device
pending-list clicks are Manual B (PHASE2_APPROVAL_STATUS.md).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.phase2]

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "index.html"

WAITING_COPY = "✅ 做完喇！等爸爸媽媽確認就入帳"


def _function_body(source: str, name: str) -> str:
    m = re.search(rf"(async\s+)?function\s+{name}\s*\([^)]*\)\s*{{", source)
    assert m, f"function {name}() not found in index.html"
    start = m.end() - 1
    depth = 0
    for i, ch in enumerate(source[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[m.start() : i + 1]
    raise AssertionError(f"unclosed function {name}")


@pytest.mark.case_id("P2-APR-FE-01")
def test_complete_task_shows_waiting_copy_when_pending():
    """P2-APR-FE-01 completeTask() 喺 pending_approval 時顯示等候入帳文案。

    WEAK (A): source contract. Real pending complete is P2-APR-02.
    Playwright mock of pending_approval=true is optional (B) / GREEN follow-up.
    """
    html = INDEX.read_text(encoding="utf-8")
    body = _function_body(html, "completeTask")
    assert "pending_approval" in body, (
        "completeTask must branch on pending_approval (GAMEPLAY_REDESIGN §6.7)"
    )
    assert WAITING_COPY in body, (
        f"completeTask must show {WAITING_COPY!r} when pending_approval is true"
    )


@pytest.mark.case_id("P2-APR-FE-02")
def test_parent_manage_has_pending_approval_list():
    """P2-APR-FE-02 家長管理頁有待批核列表（可 approve）。

    WEAK (A): source contract on renderManage / renderManageTasks.
    Product UI missing → intentional RED. Do not mark frontend.
    (B) manual: parent sees pending homework and can approve/reject.
    """
    html = INDEX.read_text(encoding="utf-8")
    manage = _function_body(html, "renderManage") + _function_body(html, "renderManageTasks")
    has_pending_queue = (
        "pending_approval" in manage
        or "/approve" in manage
        or "approveTask" in manage
        or "一鍵批" in manage
        or "待批" in manage
    )
    assert has_pending_queue, (
        "parent manage UI must list homework waiting for require_approval "
        "(GAMEPLAY_REDESIGN §6.7). STATUS: Playwright pending-list E2E is Manual B."
    )
    calls_approve = "approveTask" in html or (
        "/api/tasks/" in manage and "approve" in manage.lower()
    )
    assert calls_approve, (
        "manage UI must call POST /api/tasks/<id>/approve (or approveTask helper)"
    )
