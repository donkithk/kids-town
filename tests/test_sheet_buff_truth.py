"""SHEET-BUFF-TRUTH API anchors.

These lock the real effects that #sheetBuff must describe. They use an empty
SQLite file and synthetic accounts only. Several pass on main because
library XP, shop gold discount, and farm claim already exist. The matching
Playwright cases in tests/test_frontend.py are the red panel asserts.

Filter: python3 -m pytest tests/test_sheet_buff_truth.py -q --tb=short
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from tests.factories import (
    get_kid_experience,
    get_kid_points,
    grant_inventory,
    insert_building,
    inventory_qty,
    points_log_rows,
    response_text,
    set_kid_points,
)
from tests.phase1_helpers import (
    EXPLORE_FEE_BY_REGION,
    create_assigned_task,
    def_id,
    farm_claim,
    json_or_text,
    login_kid,
    place_building,
    start_explore,
)
from tests.sheet_buff_truth_spec import (
    CONSUMED_EFFECT_TYPES,
    UNWIRED_BUFF_TYPES,
    backend_source,
    consumed_buff_types_in_backend,
)

HK = timezone(timedelta(hours=8))


def _complete(client, task_id, kid_id):
    return client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})


@pytest.mark.case_id("SHEET-BUFF-TRUTH-01")
def test_sheet_buff_truth_api_library_bonus_is_experience_not_stars(client, family, test_db):
    """Library task_bonus adds experience_bonus, not stars or extra gold.

    Lv.1 buff_vals[0] is 2. Base XP for a 10-point task is max(5, 10//2)=5.
    Points move by the task reward only (10), never by the buff.
    """
    kid_id = family.kid_a.id
    insert_building(
        test_db, kid_id, def_id(test_db, "library"), level=1, stored=0, cell_x=0, cell_y=0
    )
    set_kid_points(test_db, kid_id, 20)
    before_xp = get_kid_experience(test_db, kid_id) or 0
    task_id = create_assigned_task(client, family, "truth-library-xp", points=10)

    r = _complete(client, task_id, kid_id)
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    assert data.get("experience_gained") == 5, data
    assert data.get("experience_bonus") == 2, data
    assert data.get("experience_total") == 7, data
    assert data.get("points_awarded") == 10, data
    assert get_kid_experience(test_db, kid_id) == before_xp + 7
    assert get_kid_points(test_db, kid_id) == 30, "buff must not add stars/gold"
    reasons = [row["reason"] or "" for row in points_log_rows(test_db, kid_id)]
    assert not any("star" in reason.lower() or "⭐" in reason for reason in reasons), reasons


@pytest.mark.case_id("SHEET-BUFF-TRUTH-02")
def test_sheet_buff_truth_api_discount_is_build_and_upgrade_gold_only(client, family, test_db):
    """Shop discount scales build and upgrade gold only.

    Lv.1 factor 0.9. Gym seed cost 200 → 180 gold, wood 10 and brick 5 unchanged.
    Upgrading that gym (level*100) → 90 gold, materials still ×(level+1).
    Explore fee and task gold are not reward-shop discounts.
    """
    kid_id = family.kid_a.id
    insert_building(
        test_db, kid_id, def_id(test_db, "shop"), level=1, stored=0, cell_x=4, cell_y=0
    )
    set_kid_points(test_db, kid_id, 500)
    grant_inventory(test_db, kid_id, {"wood": 50, "brick": 30, "gear": 5})
    login_kid(client, family)

    placed = place_building(client, kid_id, def_id(test_db, "gym"), cell_x=0, cell_y=0)
    assert placed.status_code == 201, response_text(placed)
    gym = json_or_text(placed)
    gym_id = gym.get("id")
    assert gym_id, gym
    assert get_kid_points(test_db, kid_id) == 500 - math.floor(200 * 0.9)
    assert inventory_qty(test_db, kid_id, "wood") == 40
    assert inventory_qty(test_db, kid_id, "brick") == 25

    upgraded = client.post(f"/api/kids/{kid_id}/buildings/{gym_id}/upgrade", json={})
    assert upgraded.status_code == 200, response_text(upgraded)
    assert get_kid_points(test_db, kid_id) == 500 - 180 - math.floor(100 * 0.9)
    assert inventory_qty(test_db, kid_id, "wood") == 20, "upgrade mats are not discounted"
    assert inventory_qty(test_db, kid_id, "brick") == 15

    insert_building(
        test_db, kid_id, def_id(test_db, "guild"), level=1, stored=0, cell_x=6, cell_y=0
    )
    set_kid_points(test_db, kid_id, 25)
    explore = start_explore(client, kid_id, 1)
    assert explore.status_code == 201, response_text(explore)
    assert get_kid_points(test_db, kid_id) == 25 - EXPLORE_FEE_BY_REGION[1]

    before_task_gold = get_kid_points(test_db, kid_id)
    task_id = create_assigned_task(client, family, "truth-shop-not-reward", points=10)
    done = _complete(client, task_id, kid_id)
    assert done.status_code == 200, response_text(done)
    body = json_or_text(done)
    assert body.get("points_awarded") == 10, body
    assert get_kid_points(test_db, kid_id) == before_task_gold + 10

    source = backend_source()
    assert source.count("discounted_gold_cost(") == 3, (
        "discounted_gold_cost should be the helper plus place_building and "
        "upgrade_building only, not a reward-purchase route"
    )


@pytest.mark.case_id("SHEET-BUFF-TRUTH-04")
def test_sheet_buff_truth_api_farm_claim_once_per_day(client, family, test_db):
    """Farm daily_gold pays buff_vals once per Hong Kong day.

    Lv.1 pays 5. The second claim the same day is 400 already_claimed_today
    and does not add gold again.
    """
    kid_id = family.kid_a.id
    insert_building(
        test_db, kid_id, def_id(test_db, "farm"), level=1, stored=0, cell_x=2, cell_y=0
    )
    set_kid_points(test_db, kid_id, 0)

    with freeze_time(datetime(2026, 9, 20, 9, 0, tzinfo=HK)):
        login_kid(client, family)
        first = farm_claim(client, kid_id)
        assert first.status_code == 200, response_text(first)
        assert json_or_text(first).get("amount") == 5
        assert get_kid_points(test_db, kid_id) == 5
        reasons = [row["reason"] or "" for row in points_log_rows(test_db, kid_id)]
        assert reasons.count("daily_gold") == 1, reasons

        second = farm_claim(client, kid_id)
        assert second.status_code == 400, response_text(second)
        assert json_or_text(second).get("error") == "already_claimed_today"
        assert get_kid_points(test_db, kid_id) == 5
        reasons = [row["reason"] or "" for row in points_log_rows(test_db, kid_id)]
        assert reasons.count("daily_gold") == 1, reasons


@pytest.mark.case_id("SHEET-BUFF-TRUTH-06")
def test_sheet_buff_truth_api_only_three_buff_types_are_consumed(client, family, test_db):
    """get_building_buff is only applied for task_bonus, discount, and daily_gold.

    The other seven types are not passed to that helper. A placed workshop
    does not change upgrade gold, and a placed gym does not add task XP.
    unlock_explore is a presence check in has_active_guild, not a buff_vals
    effect, so it stays in the unwired set for the panel.
    """
    found = consumed_buff_types_in_backend()
    assert found == set(CONSUMED_EFFECT_TYPES), found
    assert UNWIRED_BUFF_TYPES.isdisjoint(found)

    kid_id = family.kid_a.id
    insert_building(
        test_db, kid_id, def_id(test_db, "workshop"), level=3, stored=0, cell_x=4, cell_y=1
    )
    insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
    )
    set_kid_points(test_db, kid_id, 300)
    grant_inventory(test_db, kid_id, {"wood": 40, "brick": 20})
    login_kid(client, family)
    before = get_kid_points(test_db, kid_id)
    db_buildings = client.get(f"/api/kids/{kid_id}/buildings")
    assert db_buildings.status_code == 200, response_text(db_buildings)
    gym = next(row for row in db_buildings.get_json() if row.get("name") == "健身室")
    upgraded = client.post(
        f"/api/kids/{kid_id}/buildings/{gym['id']}/upgrade", json={}
    )
    assert upgraded.status_code == 200, response_text(upgraded)
    assert get_kid_points(test_db, kid_id) == before - 100, (
        "build_speed must not change upgrade gold"
    )

    task_id = create_assigned_task(client, family, "truth-gym-no-xp", points=10)
    done = _complete(client, task_id, kid_id)
    assert done.status_code == 200, response_text(done)
    body = json_or_text(done)
    assert body.get("experience_bonus") == 0, body
    assert body.get("points_awarded") == 10, body
