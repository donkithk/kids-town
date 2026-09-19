"""P1-TC-EXP-* — short expedition gold fees (GAMEPLAY_REDESIGN §6.5)."""
import pytest

from tests.factories import (
    force_expedition_claimable,
    get_kid_points,
    insert_building,
    insert_explored_region,
    mark_expeditions_completed,
    points_log_rows,
    response_text,
    set_kid_level,
    set_kid_points,
)
from tests.phase1_helpers import (
    EXPLORE_FEE_BY_REGION,
    battle_start,
    def_id,
    json_or_text,
    login_kid,
    running_expedition_count,
    start_explore,
)

pytestmark = [pytest.mark.phase1]


def _give_guild(test_db, kid_id):
    insert_building(test_db, kid_id, def_id(test_db, "guild"), level=1, stored=0, cell_x=6, cell_y=0)


@pytest.mark.case_id("P1-TC-EXP-01")
def test_region1_short_explore_deducts_10_gold(client, family, test_db):
    """P1-TC-EXP-01 有公會、points=15 時 start 區1 explore → points=5。"""
    kid_id = family.kid_a.id
    _give_guild(test_db, kid_id)
    set_kid_points(test_db, kid_id, 15)
    login_kid(client, family)
    r = start_explore(client, kid_id, 1)
    assert r.status_code == 201, response_text(r)
    assert get_kid_points(test_db, kid_id) == 5
    assert running_expedition_count(test_db, kid_id) == 1
    reasons = [row["reason"] or "" for row in points_log_rows(test_db, kid_id)]
    assert any("expedition_fee" in reason for reason in reasons), reasons


@pytest.mark.case_id("P1-TC-EXP-02")
def test_insufficient_gold_does_not_start_or_charge(client, family, test_db):
    """P1-TC-EXP-02 points=9 start 區1 → 400 insufficient_gold。"""
    kid_id = family.kid_a.id
    _give_guild(test_db, kid_id)
    set_kid_points(test_db, kid_id, 9)
    login_kid(client, family)
    r = start_explore(client, kid_id, 1)
    assert r.status_code == 400, response_text(r)
    data = json_or_text(r)
    assert data.get("error") == "insufficient_gold", data
    assert data.get("need") == 10, data
    assert data.get("have") == 9, data
    assert running_expedition_count(test_db, kid_id) == 0
    assert get_kid_points(test_db, kid_id) == 9


@pytest.mark.case_id("P1-TC-EXP-03")
def test_region_2_and_3_explore_fee_table(client, family, test_db):
    """P1-TC-EXP-03 區2 扣 20、區3 扣 30（factory 插 explored）。"""
    kid_id = family.kid_a.id
    _give_guild(test_db, kid_id)
    insert_explored_region(test_db, kid_id, 1)
    insert_explored_region(test_db, kid_id, 2)
    set_kid_points(test_db, kid_id, 100)
    login_kid(client, family)

    r2 = start_explore(client, kid_id, 2)
    assert r2.status_code == 201, response_text(r2)
    assert get_kid_points(test_db, kid_id) == 100 - EXPLORE_FEE_BY_REGION[2]
    mark_expeditions_completed(test_db, kid_id)

    r3 = start_explore(client, kid_id, 3)
    assert r3.status_code == 201, response_text(r3)
    assert get_kid_points(test_db, kid_id) == 100 - EXPLORE_FEE_BY_REGION[2] - EXPLORE_FEE_BY_REGION[3]


@pytest.mark.case_id("P1-TC-EXP-04")
def test_battle_start_does_not_charge_explore_fee(client, family, test_db):
    """P1-TC-EXP-04 battle-start 金幣不變。"""
    kid_id = family.kid_a.id
    _give_guild(test_db, kid_id)
    set_kid_level(test_db, kid_id, 20, experience=1000)
    set_kid_points(test_db, kid_id, 10)
    login_kid(client, family)
    r = battle_start(client, kid_id, 1)
    assert r.status_code in (200, 201), response_text(r)
    assert get_kid_points(test_db, kid_id) == 10


@pytest.mark.case_id("P1-TC-EXP-05")
def test_explore_can_be_farmed_again_after_claim(client, family, test_db):
    """P1-TC-EXP-05 claim 區1 之後可以再 start 區1。"""
    kid_id = family.kid_a.id
    _give_guild(test_db, kid_id)
    set_kid_points(test_db, kid_id, 40)
    login_kid(client, family)
    first = start_explore(client, kid_id, 1)
    assert first.status_code == 201, response_text(first)
    force_expedition_claimable(test_db, kid_id)
    claimed = client.post(f"/api/kids/{kid_id}/expedition/claim", json={})
    assert claimed.status_code == 200, response_text(claimed)
    set_kid_points(test_db, kid_id, 40)
    second = start_explore(client, kid_id, 1)
    assert second.status_code == 201, response_text(second)
