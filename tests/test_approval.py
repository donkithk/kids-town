"""P2-APR-* Phase 2 parent approval of homework rewards (GAMEPLAY_REDESIGN §6.7).

TDD RED against current main: complete always credits immediately and
pending_approval is hardcoded False. No require_approval setting, no
POST /api/tasks/<id>/approve or /reject.

Empty-DB fixtures only. Never copy kids_town.db. Synthetic PIN 1357 only.
"""
from __future__ import annotations

import json

import pytest

from tests.factories import (
    TEST_PARENT_PASSWORD,
    connect_db,
    fetchone,
    force_expedition_claimable,
    get_kid_experience,
    get_kid_points,
    insert_building,
    inventory_map,
    login_as,
    response_text,
    set_kid_level,
    set_kid_points,
)
from tests.phase1_helpers import (
    battle_start,
    create_assigned_task,
    def_id,
    json_or_text,
    login_kid,
    login_parent,
    start_explore,
    try_enable_require_approval,
)

pytestmark = [pytest.mark.phase2]

FORESHADOW_KEYS = (
    "points_awarded",
    "experience_gained",
    "experience_bonus",
    "experience_total",
    "material_drops",
    "pending_approval",
)

ENABLE_FAIL_MSG = (
    "Phase 2 / GAMEPLAY_REDESIGN §6.7: cannot enable require_approval — {detail}. "
    "Implement family_settings.require_approval (default false) or parents.approve_rewards, "
    "then this case must go green. Do not pytest.skip."
)


def _economy(test_db, kid_id):
    return {
        "points": get_kid_points(test_db, kid_id),
        "experience": get_kid_experience(test_db, kid_id) or 0,
        "inventory": inventory_map(test_db, kid_id),
    }


def _enable_require_approval(client, family, test_db):
    ok, detail = try_enable_require_approval(client, family, test_db)
    assert ok, ENABLE_FAIL_MSG.format(detail=detail)
    return detail


def _task_completed_flag(test_db, task_id, client=None, kid_id=None):
    row = fetchone(test_db, "SELECT completed FROM tasks WHERE id=?", (task_id,))
    db_flag = None if row is None else row.get("completed")
    api_flag = None
    if client is not None and kid_id is not None:
        listed = client.get(f"/api/tasks?kid_id={kid_id}").get_json(silent=True) or []
        match = next((t for t in listed if t.get("id") == task_id), None)
        if match is not None:
            api_flag = match.get("completed")
    return db_flag, api_flag


def _is_completed(flag):
    return flag in (1, True, "1", "true", "True")


def _assert_foreshadow_present(data):
    for key in FORESHADOW_KEYS:
        assert key in data, f"missing foreshadow field {key} in {data}"
    assert isinstance(data["points_awarded"], int), data
    assert isinstance(data["experience_gained"], int), data
    assert isinstance(data["experience_bonus"], int), data
    assert isinstance(data["experience_total"], int), data
    assert isinstance(data["material_drops"], list), data


def _apply_foreshadow_to_economy(before, data):
    inv = dict(before["inventory"])
    for item in data.get("material_drops") or []:
        name = item if isinstance(item, str) else (item.get("item_type") or item.get("id"))
        if not name:
            continue
        inv[name] = inv.get(name, 0) + 1
    return {
        "points": before["points"] + int(data.get("points_awarded") or 0),
        "experience": before["experience"] + int(data.get("experience_total") or 0),
        "inventory": inv,
    }


def _force_running_battle_monsters_hp(test_db, kid_id, hp=1):
    """Test-only: leave the battle one hit from a win. Not product code."""
    db = connect_db(test_db)
    try:
        row = db.execute(
            "SELECT id, expedition_data FROM expeditions "
            "WHERE kid_id=? AND status='running' "
            "AND expedition_type IN ('battle','boss') "
            "ORDER BY id DESC LIMIT 1",
            (kid_id,),
        ).fetchone()
        assert row, "expected a running battle expedition"
        payload = json.loads(row["expedition_data"] or "{}")
        monsters = payload.get("monsters") or []
        assert monsters, payload
        # Keep a single 1-HP target so one attack wins (region battles spawn 1–3).
        payload["monsters"] = [monsters[0]]
        payload["monsters"][0]["hp"] = hp
        db.execute(
            "UPDATE expeditions SET expedition_data=? WHERE id=?",
            (json.dumps(payload), row["id"]),
        )
        db.commit()
    finally:
        db.close()


def _give_guild(test_db, kid_id):
    insert_building(test_db, kid_id, def_id(test_db, "guild"), level=1, stored=0, cell_x=6, cell_y=0)


@pytest.mark.case_id("P2-APR-01")
def test_default_off_complete_credits_immediately(client, family, test_db):
    """P2-APR-01 預設 off：complete 即時入帳；pending_approval=false。"""
    kid_id = family.kid_a.id
    before = _economy(test_db, kid_id)
    task_id = create_assigned_task(client, family, "p2-apr-01", points=10)
    r = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    assert data.get("pending_approval") is False, data
    awarded = int(data.get("points_awarded") or 0)
    xp_total = int(data.get("experience_total") or data.get("experience_gained") or 0)
    assert awarded == 10, data
    assert get_kid_points(test_db, kid_id) == before["points"] + awarded
    assert (get_kid_experience(test_db, kid_id) or 0) == before["experience"] + xp_total
    db_flag, api_flag = _task_completed_flag(test_db, task_id, client, kid_id)
    assert _is_completed(db_flag) or _is_completed(api_flag), (db_flag, api_flag)


@pytest.mark.case_id("P2-APR-02")
def test_require_approval_complete_does_not_credit_and_foreshadows(client, family, test_db):
    """P2-APR-02 on：complete 後金幣／XP／背包不變；pending_approval=true；預告欄位齊。"""
    _enable_require_approval(client, family, test_db)
    kid_id = family.kid_a.id
    before = _economy(test_db, kid_id)
    task_id = create_assigned_task(client, family, "p2-apr-02", points=10)
    r = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    _assert_foreshadow_present(data)
    assert data.get("pending_approval") is True, data
    assert int(data["points_awarded"]) == 10, data
    assert _economy(test_db, kid_id) == before


@pytest.mark.case_id("P2-APR-03")
def test_parent_approve_credits_foreshadowed_amounts(client, family, test_db):
    """P2-APR-03 on：parent approve 後入帳數量 = complete 預告。"""
    _enable_require_approval(client, family, test_db)
    kid_id = family.kid_a.id
    before = _economy(test_db, kid_id)
    task_id = create_assigned_task(client, family, "p2-apr-03", points=10)
    complete = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert complete.status_code == 200, response_text(complete)
    data = json_or_text(complete)
    _assert_foreshadow_present(data)
    assert data.get("pending_approval") is True, data
    assert _economy(test_db, kid_id) == before

    login_parent(client, family)
    approve = client.post(f"/api/tasks/{task_id}/approve", json={"kid_id": kid_id})
    assert approve.status_code in (200, 201), response_text(approve)
    expected = _apply_foreshadow_to_economy(before, data)
    after = _economy(test_db, kid_id)
    assert after["points"] == expected["points"], (after, expected, data)
    assert after["experience"] == expected["experience"], (after, expected, data)
    for item, qty in expected["inventory"].items():
        assert after["inventory"].get(item, 0) == qty, (item, after, expected)


@pytest.mark.case_id("P2-APR-04")
def test_parent_reject_returns_task_incomplete_without_credits(client, family, test_db):
    """P2-APR-04 on：reject 後任務 incomplete；仍然無金幣／XP／材料。"""
    _enable_require_approval(client, family, test_db)
    kid_id = family.kid_a.id
    before = _economy(test_db, kid_id)
    task_id = create_assigned_task(client, family, "p2-apr-04", points=10)
    complete = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert complete.status_code == 200, response_text(complete)
    data = json_or_text(complete)
    assert data.get("pending_approval") is True, data
    assert _economy(test_db, kid_id) == before

    login_parent(client, family)
    reject = client.post(
        f"/api/tasks/{task_id}/reject",
        json={"kid_id": kid_id, "reason": "not_done"},
    )
    assert reject.status_code in (200, 201), response_text(reject)
    assert _economy(test_db, kid_id) == before
    db_flag, api_flag = _task_completed_flag(test_db, task_id, client, kid_id)
    assert not _is_completed(db_flag), db_flag
    if api_flag is not None:
        assert not _is_completed(api_flag), api_flag


@pytest.mark.case_id("P2-APR-05")
def test_expedition_claim_and_battle_still_award_when_approval_on(client, family, test_db):
    """P2-APR-05 on：短征 claim／戰鬥仍然發獎；家課 complete 仍然 pending。"""
    _enable_require_approval(client, family, test_db)
    kid_id = family.kid_a.id
    _give_guild(test_db, kid_id)
    set_kid_level(test_db, kid_id, 20, experience=1000)
    set_kid_points(test_db, kid_id, 80)

    homework_before = _economy(test_db, kid_id)
    task_id = create_assigned_task(client, family, "p2-apr-05-hw", points=10)
    hw = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert hw.status_code == 200, response_text(hw)
    hw_data = json_or_text(hw)
    assert hw_data.get("pending_approval") is True, hw_data
    assert _economy(test_db, kid_id) == homework_before

    login_kid(client, family)
    start = start_explore(client, kid_id, 1)
    assert start.status_code == 201, response_text(start)
    after_fee = _economy(test_db, kid_id)
    force_expedition_claimable(test_db, kid_id)
    claimed = client.post(f"/api/kids/{kid_id}/expedition/claim", json={})
    assert claimed.status_code == 200, response_text(claimed)
    after_claim = _economy(test_db, kid_id)
    claim_awarded = (
        after_claim["points"] > after_fee["points"]
        or after_claim["experience"] > after_fee["experience"]
        or after_claim["inventory"] != after_fee["inventory"]
    )
    assert claim_awarded, (
        "expedition/claim must credit gold/XP/materials without parent approve; "
        f"fee={after_fee} claim={after_claim} body={json_or_text(claimed)}"
    )

    battle = battle_start(client, kid_id, 1)
    assert battle.status_code in (200, 201), response_text(battle)
    _force_running_battle_monsters_hp(test_db, kid_id, hp=1)
    before_win = _economy(test_db, kid_id)
    action = client.post(
        f"/api/kids/{kid_id}/expedition/battle-action",
        json={"action": "attack", "target_idx": 0},
    )
    assert action.status_code == 200, response_text(action)
    action_data = json_or_text(action)
    assert action_data.get("battle_result") == "won" or action_data.get("status") == "won", (
        action_data
    )
    after_win = _economy(test_db, kid_id)
    battle_awarded = (
        after_win["points"] > before_win["points"]
        or after_win["experience"] > before_win["experience"]
        or after_win["inventory"] != before_win["inventory"]
    )
    assert battle_awarded, (
        "battle win must credit drops without parent approve; "
        f"before={before_win} after={after_win} body={action_data}"
    )
    assert _economy(test_db, kid_id)["points"] >= homework_before["points"]
    # Homework still must not have been the thing that credited the original 10 gold.
    # Compare homework gold specifically: claim+battle may add gold, so only assert
    # the pending homework foreshadow was not applied at complete-time (already did).
    assert hw_data.get("pending_approval") is True


@pytest.mark.case_id("P2-APR-06")
def test_unauthenticated_approve_and_reject_return_401(client, family, app, test_db):
    """P2-APR-06 無 session 時 POST approve／reject → 401。"""
    kid_id = family.kid_a.id
    with app.test_client() as setup:
        login_as(setup, family.parent_a.username, TEST_PARENT_PASSWORD)
        created = setup.post(
            "/api/tasks",
            json={"title": "p2-apr-06", "points": 10, "kid_id": kid_id},
        )
        assert created.status_code in (200, 201), response_text(created)
        task_id = created.get_json()["id"]

    before = get_kid_points(test_db, kid_id)
    approve = client.post(f"/api/tasks/{task_id}/approve", json={"kid_id": kid_id})
    assert approve.status_code == 401, response_text(approve)
    reject = client.post(
        f"/api/tasks/{task_id}/reject",
        json={"kid_id": kid_id, "reason": "anon"},
    )
    assert reject.status_code == 401, response_text(reject)
    assert get_kid_points(test_db, kid_id) == before


@pytest.mark.case_id("P2-APR-07")
def test_foreign_parent_and_kid_cannot_approve_returns_403(client, family, test_db):
    """P2-APR-07 Parent B 或 Kid A 不能 POST approve → 403。"""
    kid_id = family.kid_a.id
    task_id = create_assigned_task(client, family, "p2-apr-07", points=10)
    before = get_kid_points(test_db, kid_id)

    login_as(client, family.parent_b.username, family.parent_password)
    other_parent = client.post(f"/api/tasks/{task_id}/approve", json={"kid_id": kid_id})
    assert other_parent.status_code == 403, response_text(other_parent)

    login_kid(client, family)
    kid_approve = client.post(f"/api/tasks/{task_id}/approve", json={"kid_id": kid_id})
    assert kid_approve.status_code == 403, response_text(kid_approve)
    assert get_kid_points(test_db, kid_id) == before
