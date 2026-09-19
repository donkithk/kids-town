"""P1-TC-CER-FE-01 — completeTask must read XP / materials / achievements.

This file is a **weak source-contract** (string/AST-ish scan of index.html).
It is NOT full double-verification (A) for ceremony UX. STATUS.md records:
  (A) Playwright mock in tests/test_frontend.py when Chromium is available
  (B) manual checklist still required — grep alone is not ceremony UX.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.phase1]

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "index.html"


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


@pytest.mark.case_id("P1-TC-CER-FE-01")
def test_complete_task_source_reads_xp_materials_achievements():
    """P1-TC-CER-FE-01 completeTask() 必須讀 XP／材料／成就，唔只 toast 金幣。

    WEAK (A): source contract only. Does not prove toast/modal copy.
    Playwright mock (same Case ID in test_frontend.py) is the automatable UI
    assert when Chromium works. (B) manual still required.
    """
    html = INDEX.read_text(encoding="utf-8")
    body = _function_body(html, "completeTask")
    assert "experience_total" in body or "experience_gained" in body, (
        "completeTask must read experience_total or experience_gained "
        "(GAMEPLAY_REDESIGN §6.4). STATUS: this is a weak source assert; "
        "(B) manual ceremony click is still required."
    )
    assert "material_drops" in body, "completeTask must read material_drops"
    assert "achievements" in body, "completeTask must read achievements"
    # Must not be gold-only.
    gold_only = "points_awarded" in body and "experience" not in body
    assert not gold_only, "completeTask currently treats rewards as gold-only toast"
