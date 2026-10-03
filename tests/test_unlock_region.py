"""P1-TC-UNL-* / P1-TC-PLC-01 — unlock_region enforcement + place API parity."""
import pytest

from tests.factories import (
    connect_db,
    count_rows,
    get_kid_points,
    grant_inventory,
    insert_explored_region,
    inventory_map,
    response_text,
    set_kid_points,
)
from tests.phase1_helpers import (
    def_id,
    error_code,
    json_or_text,
    login_kid,
    place_building,
)

pytestmark = [pytest.mark.phase1]


def _fund_lighthouse(test_db, kid_id):
    set_kid_points(test_db, kid_id, 800)
    grant_inventory(
        test_db,
        kid_id,
        {
            "wood": 30,
            "brick": 25,
            "iron": 15,
            "gear": 15,
            "gem": 3,
            "glass": 3,
            "star_shard": 3,
        },
    )


def _fund_arena(test_db, kid_id):
    set_kid_points(test_db, kid_id, 1000)
    grant_inventory(
        test_db,
        kid_id,
        {
            "wood": 40,
            "brick": 30,
            "iron": 20,
            "gear": 20,
            "gem": 5,
        },
    )


def _fund_library(test_db, kid_id):
    set_kid_points(test_db, kid_id, 100)
    grant_inventory(test_db, kid_id, {"wood": 5})


@pytest.mark.case_id("P1-TC-UNL-01")
def test_lighthouse_requires_explored_region_3(client, family, test_db):
    """P1-TC-UNL-01 unlock_region=r3 嘅燈塔：無區 3 探索／勝利時 place → 400。"""
    kid_id = family.kid_a.id
    _fund_lighthouse(test_db, kid_id)
    login_kid(client, family)
    before = count_rows(test_db, "buildings", "kid_id=?", (kid_id,))
    r = place_building(client, kid_id, def_id(test_db, "lighthouse"), cell_x=8, cell_y=0)
    assert r.status_code == 400, response_text(r)
    err = str(json_or_text(r).get("error") or "")
    assert "region" in err.lower() or "unlock_region" in err.lower(), err
    assert count_rows(test_db, "buildings", "kid_id=?", (kid_id,)) == before


@pytest.mark.case_id("P1-TC-UNL-02")
def test_lighthouse_place_succeeds_after_region_3_explored(client, family, test_db):
    """P1-TC-UNL-02 解鎖區 3 之後，燈塔跟 8×8，沒有格外豁免。

    (8,0) 要 400，金幣同材料不變。合法空格 (0,0) 要 201，而且 stored=0。
    舊預期係 (8,0) 201。改因為 8×8 規則（Grok decision）。
    """
    kid_id = family.kid_a.id
    _fund_lighthouse(test_db, kid_id)
    insert_explored_region(test_db, kid_id, 3)
    login_kid(client, family)
    lighthouse = def_id(test_db, "lighthouse")
    points_before = get_kid_points(test_db, kid_id)
    mats_before = inventory_map(test_db, kid_id)
    rejected = place_building(client, kid_id, lighthouse, cell_x=8, cell_y=0)
    points_after = get_kid_points(test_db, kid_id)
    mats_after = inventory_map(test_db, kid_id)
    problems = []
    if rejected.status_code != 400:
        problems.append(
            f"(8,0) expected 400, got {rejected.status_code} {response_text(rejected)[:180]}"
        )
    if points_after != points_before or mats_after != mats_before:
        problems.append(
            f"(8,0) changed resources: points {points_before} -> {points_after}; "
            f"materials {mats_before} -> {mats_after}"
        )
    db = connect_db(test_db)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    set_kid_points(test_db, kid_id, points_before)
    grant_inventory(test_db, kid_id, mats_before)
    placed = place_building(client, kid_id, lighthouse, cell_x=0, cell_y=0)
    if placed.status_code != 201:
        problems.append(
            f"(0,0) expected 201, got {placed.status_code} {response_text(placed)[:180]}"
        )
    else:
        db = connect_db(test_db)
        row = db.execute(
            """
            SELECT cell_x, cell_y, COALESCE(stored, 0) AS stored
              FROM buildings WHERE kid_id=? AND def_id=?
            """,
            (kid_id, lighthouse),
        ).fetchone()
        db.close()
        if row is None or row["stored"] != 0 or (row["cell_x"], row["cell_y"]) != (0, 0):
            problems.append(f"(0,0) expected stored=0 at (0,0), got {dict(row) if row else None}")
    assert not problems, "P1-TC-UNL-02: " + " | ".join(problems)


@pytest.mark.case_id("P1-TC-UNL-03")
def test_arena_stays_locked_while_region_4_content_locked(client, family, test_db):
    """P1-TC-UNL-03 即使作弊插入 explored 4，競技場仍 400 region_locked。"""
    kid_id = family.kid_a.id
    _fund_arena(test_db, kid_id)
    insert_explored_region(test_db, kid_id, 4)
    login_kid(client, family)
    r = place_building(client, kid_id, def_id(test_db, "arena"), cell_x=10, cell_y=0)
    assert r.status_code == 400, response_text(r)
    assert error_code(r) == "region_locked"


@pytest.mark.case_id("P1-TC-PLC-01")
def test_place_building_api_does_not_depend_on_ui_entry(client, family, test_db):
    """P1-TC-PLC-01 同一 POST buildings body 無論邊個 tab 叫都 201。"""
    kid_id = family.kid_a.id
    _fund_library(test_db, kid_id)
    login_kid(client, family)
    r = place_building(client, kid_id, def_id(test_db, "library"), cell_x=0, cell_y=0)
    assert r.status_code == 201, response_text(r)
