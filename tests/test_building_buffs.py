"""P1-TC-BUFF-* — library / farm / shop buffs (GAMEPLAY_REDESIGN §6.1)."""
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

import backend_v2 as b
from tests.factories import (
    connect_db,
    get_kid_experience,
    get_kid_points,
    grant_inventory,
    insert_building,
    inventory_qty,
    logout,
    points_log_rows,
    response_text,
    set_kid_points,
)
from tests.phase1_helpers import (
    create_assigned_task,
    def_id,
    farm_claim,
    json_or_text,
    login_kid,
    place_building,
)

pytestmark = [pytest.mark.phase1]

HK = timezone(timedelta(hours=8))


def _complete(client, task_id, kid_id):
    return client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})


@pytest.mark.case_id("P1-TC-BUFF-01")
def test_library_level1_adds_task_bonus_xp(client, family, test_db):
    """P1-TC-BUFF-01 圖書館 Lv.1 完成任務 XP = 基礎 + 2。"""
    kid_id = family.kid_a.id
    insert_building(test_db, kid_id, def_id(test_db, "library"), level=1, stored=0, cell_x=0, cell_y=0)
    task_id = create_assigned_task(client, family, "p1-buff-01", points=10)
    before_xp = get_kid_experience(test_db, kid_id) or 0
    before_gold = get_kid_points(test_db, kid_id)

    r = _complete(client, task_id, kid_id)
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    assert data.get("experience_gained") == 5, data
    assert data.get("experience_bonus") == 2, data
    assert data.get("experience_total") == 7, data
    assert data.get("points_awarded") == 10, data
    assert get_kid_experience(test_db, kid_id) == before_xp + 7
    assert get_kid_points(test_db, kid_id) == before_gold + 10


@pytest.mark.case_id("P1-TC-BUFF-02")
def test_no_library_task_bonus_is_zero(client, family, test_db):
    """P1-TC-BUFF-02 未起圖書館：experience_bonus==0，XP 只有基礎。"""
    kid_id = family.kid_a.id
    task_id = create_assigned_task(client, family, "p1-buff-02", points=10)
    r = _complete(client, task_id, kid_id)
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    assert data.get("experience_bonus") == 0, data
    assert data.get("experience_gained") == 5, data
    assert data.get("experience_total") == 5, data
    assert data.get("points_awarded") == 10, data


@pytest.mark.case_id("P1-TC-BUFF-03")
def test_library_level2_uses_updated_buff_table(client, family, test_db):
    """P1-TC-BUFF-03 Lv.2 buff_vals[1]==4。"""
    kid_id = family.kid_a.id
    insert_building(test_db, kid_id, def_id(test_db, "library"), level=2, stored=0, cell_x=0, cell_y=0)
    task_id = create_assigned_task(client, family, "p1-buff-03", points=10)
    r = _complete(client, task_id, kid_id)
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    assert data.get("experience_bonus") == 4, data


@pytest.mark.case_id("P1-TC-BUFF-04")
def test_stored_library_does_not_grant_bonus(client, family, test_db):
    """P1-TC-BUFF-04 stored=1 嘅圖書館唔加 XP。"""
    kid_id = family.kid_a.id
    insert_building(test_db, kid_id, def_id(test_db, "library"), level=1, stored=1, cell_x=0, cell_y=0)
    task_id = create_assigned_task(client, family, "p1-buff-04", points=10)
    r = _complete(client, task_id, kid_id)
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    assert data.get("experience_bonus") == 0, data


@pytest.mark.case_id("P1-TC-BUFF-05")
def test_farm_daily_gold_claim_once_per_hk_day(client, family, test_db):
    """P1-TC-BUFF-05 Lv.1 農場每日 +5，同日第二次 already_claimed_today。"""
    kid_id = family.kid_a.id
    insert_building(test_db, kid_id, def_id(test_db, "farm"), level=1, stored=0, cell_x=2, cell_y=0)
    set_kid_points(test_db, kid_id, 0)
    login_kid(client, family)

    with freeze_time(datetime(2026, 9, 18, 10, 0, tzinfo=HK)):
        r1 = farm_claim(client, kid_id)
        assert r1.status_code == 200, response_text(r1)
        assert get_kid_points(test_db, kid_id) == 5
        reasons = [row["reason"] or "" for row in points_log_rows(test_db, kid_id)]
        assert any("daily_gold" in reason for reason in reasons), reasons

        r2 = farm_claim(client, kid_id)
        assert r2.status_code == 400, response_text(r2)
        assert json_or_text(r2).get("error") == "already_claimed_today"
        assert get_kid_points(test_db, kid_id) == 5

    with freeze_time(datetime(2026, 9, 19, 0, 1, tzinfo=HK)):
        r3 = farm_claim(client, kid_id)
        assert r3.status_code == 200, response_text(r3)
        assert get_kid_points(test_db, kid_id) == 10

    logout(client)
    client.post("/api/auth/logout")
    r_anon = farm_claim(client, kid_id)
    assert r_anon.status_code == 401, response_text(r_anon)


@pytest.mark.case_id("P1-TC-BUFF-06")
def test_farm_claim_without_farm_returns_farm_required(client, family, test_db):
    """P1-TC-BUFF-06 無農場 → 400 farm_required。"""
    kid_id = family.kid_a.id
    set_kid_points(test_db, kid_id, 3)
    login_kid(client, family)
    r = farm_claim(client, kid_id)
    assert r.status_code == 400, response_text(r)
    assert json_or_text(r).get("error") == "farm_required"
    assert get_kid_points(test_db, kid_id) == 3


@pytest.mark.case_id("P1-TC-BUFF-07")
def test_shop_level1_discounts_gold_not_materials(client, family, test_db):
    """P1-TC-BUFF-07 已有商店 Lv.1 時再建圖書館扣 90 金而非 100；木頭仍扣 5。"""
    kid_id = family.kid_a.id
    insert_building(test_db, kid_id, def_id(test_db, "shop"), level=1, stored=0, cell_x=4, cell_y=0)
    set_kid_points(test_db, kid_id, 200)
    grant_inventory(test_db, kid_id, {"wood": 10, "gear": 5, "iron": 5})
    login_kid(client, family)

    r = place_building(client, kid_id, def_id(test_db, "library"), cell_x=0, cell_y=0)
    assert r.status_code == 201, response_text(r)
    assert get_kid_points(test_db, kid_id) == 110
    assert inventory_qty(test_db, kid_id, "wood") == 5
    gold_logs = [row for row in points_log_rows(test_db, kid_id) if row["amount"] < 0]
    assert any(row["amount"] == -90 for row in gold_logs), gold_logs


@pytest.mark.case_id("P1-TC-BUFF-08")
def test_placing_first_shop_pays_full_seed_price(client, family, test_db):
    """P1-TC-BUFF-08 第一座商店仍付全價 500（自己未享折扣）。"""
    kid_id = family.kid_a.id
    set_kid_points(test_db, kid_id, 500)
    grant_inventory(
        test_db,
        kid_id,
        {"wood": 20, "brick": 15, "iron": 5, "gear": 5},
    )
    login_kid(client, family)
    r = place_building(client, kid_id, def_id(test_db, "shop"), cell_x=4, cell_y=0)
    assert r.status_code == 201, response_text(r)
    assert get_kid_points(test_db, kid_id) == 0, "first shop must cost full 500, not 450"


@pytest.mark.case_id("P1-TC-BUFF-09")
def test_get_building_buff_helper_farm_and_missing_types(family, test_db):
    """P1-TC-BUFF-09 無建築 None；Lv.3 農場 daily_gold=15。"""
    assert hasattr(b, "get_building_buff"), (
        "backend_v2.get_building_buff(kid_id, buff_type, db) is required "
        "(GAMEPLAY_REDESIGN §6.1)"
    )
    kid_id = family.kid_a.id
    insert_building(test_db, kid_id, def_id(test_db, "farm"), level=3, stored=0, cell_x=2, cell_y=0)
    db = connect_db(test_db)
    try:
        daily = b.get_building_buff(kid_id, "daily_gold", db)
        bonus = b.get_building_buff(kid_id, "task_bonus", db)
    finally:
        db.close()
    assert daily == 15, daily
    assert bonus is None, bonus
