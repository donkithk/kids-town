"""P1-TC-CER-* — task complete ceremony JSON (GAMEPLAY_REDESIGN §6.4)."""
from __future__ import annotations

import pytest

from tests.factories import (
    get_kid_points,
    login_as,
    points_log_rows,
    response_text,
)
from tests.phase1_helpers import (
    create_assigned_task,
    json_or_text,
    try_enable_require_approval,
)

# CER-01 / CER-02 stay phase1. P1-TC-CER-03 is Phase 2 leftover (GAMEPLAY_REDESIGN
# §6.7): marker moved to phase2 so `pytest -m phase1` is not carrying this
# intentional red. Do not silent-skip.

CEREMONY_KEYS = (
    "points_awarded",
    "experience_gained",
    "experience_bonus",
    "experience_total",
    "material_drops",
    "achievements",
    "pending_approval",
)
KID_XP_KEYS = ("experience_in_level", "experience_for_next")


@pytest.mark.phase1
@pytest.mark.case_id("P1-TC-CER-01")
def test_complete_json_includes_ceremony_fields(client, family, test_db):
    """P1-TC-CER-01 200 body 含儀式欄位；pending_approval is False；XP 唔入 points_log。"""
    kid_id = family.kid_a.id
    task_id = create_assigned_task(client, family, "p1-cer-01", points=10)
    r = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    for key in CEREMONY_KEYS:
        assert key in data, f"missing {key} in {data}"
    assert isinstance(data["points_awarded"], int)
    assert isinstance(data["experience_gained"], int)
    assert isinstance(data["experience_bonus"], int)
    assert isinstance(data["experience_total"], int)
    assert isinstance(data["material_drops"], list)
    assert isinstance(data["achievements"], list)
    assert data["pending_approval"] is False
    kid = data.get("kid") or {}
    for key in KID_XP_KEYS:
        assert key in kid, f"missing kid.{key} in {kid}"
    xp_reasons = [row["reason"] or "" for row in points_log_rows(test_db, kid_id)]
    assert not any("experience_gained" in reason for reason in xp_reasons), xp_reasons


@pytest.mark.phase1
@pytest.mark.case_id("P1-TC-CER-02")
def test_first_task_achievement_in_complete_response(client, family):
    """P1-TC-CER-02 新號第一次 complete 後 achievements 含 first_task。"""
    kid_id = family.kid_a.id
    task_id = create_assigned_task(client, family, "p1-cer-02", points=10)
    r = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert r.status_code == 200, response_text(r)
    achs = json_or_text(r).get("achievements") or []
    assert achs, achs
    badges = [a.get("badge") for a in achs if isinstance(a, dict)]
    assert "first_task" in badges, achs


@pytest.mark.phase2
@pytest.mark.case_id("P1-TC-CER-03")
def test_require_approval_defers_rewards_until_parent_approves(client, family, test_db):
    """P1-TC-CER-03 批核開啟時唔入帳、pending_approval=true。

    Folded into Phase 2 catalog (P2-APR-02 / P2-APR-03; GAMEPLAY_REDESIGN §6.7).
    Marker is phase2 (not phase1) so `pytest -m phase1` stays green.
    Do not silent-skip: this case must stay visible until Phase 2 ships
    family require_approval (default off) and POST /api/tasks/<id>/approve.
    """
    ok, detail = try_enable_require_approval(client, family, test_db)
    assert ok, (
        "Phase 2 dependency: cannot enable require_approval — "
        f"{detail}. Implement GAMEPLAY_REDESIGN §6.7, then this case must go green. "
        "Do not pytest.skip."
    )
    kid_id = family.kid_a.id
    before = get_kid_points(test_db, kid_id)
    task_id = create_assigned_task(client, family, "p1-cer-03", points=10)
    r = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    assert data.get("pending_approval") is True, data
    assert get_kid_points(test_db, kid_id) == before

    login_as(client, family.parent_a.username, family.parent_password)
    approve = client.post(f"/api/tasks/{task_id}/approve", json={"kid_id": kid_id})
    assert approve.status_code in (200, 201), response_text(approve)
    assert get_kid_points(test_db, kid_id) == before + data.get("points_awarded", 10)
