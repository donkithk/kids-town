"""TC-API-WAREHOUSE-* / TC-FE-WAREHOUSE-GRID — 存倉放回 8×8。

紅測。只鎖行為，唔改產品碼。每個 test 用 conftest 的空臨時庫同合成小朋友，
唔會打開或複製 kids_town.db。

根因（main 5bfe76d）：
- backend_v2.py:3264 place_building、:3374 unstored_building 仍接受 0–22 × 0–14。
- backend_v2.py:1615 TOWN_PLACE_COLS/ROWS 已經係 8，:1619 warehouse_legacy_out_of_grid
  會喺 GET 建築／存倉／城鎮時把格外的 stored=0 列改成 stored=1，而且唔退資源。
- 所以喺 (8,0) 或 (20,12) 起屋會先扣金幣同材料，下一次列表再收進存倉。
- 佔用檢查 :3273 同 :3383 只對原點，唔對 2×2 足跡重疊，亦唔排除 stored=1。
- :3267 已有同種類（包括存倉）就 400，唔會把存倉嗰行放到要求的格。
- index.html renderTownBuildings 仍係 COLS=24, ROWS=16，存倉卡片走 startUnstoreBuilding。
- move_building（backend_v2.py:3333）同樣接受 0–22 × 0–14；格外移動成功後，
  GET 會把該行收倉。佔用檢查 :3342 只對原點，而且包含 stored=1。
"""
from __future__ import annotations

import json
import math
import re

import pytest

import backend_v2 as backend
from tests.factories import (
    connect_db,
    get_kid_experience,
    get_kid_points,
    grant_inventory,
    insert_building,
    inventory_map,
    response_text,
    set_kid_points,
)
from tests.phase1_helpers import def_id, login_kid, start_explore

pytestmark = [pytest.mark.phase1]

REJECT_STATUSES = (400, 409, 422)
# 伺服器而家當合法、8×8 唔接受的舊座標。
LEGACY_OUTSIDE = ((8, 0), (0, 8), (8, 8), (20, 12))
RICH_ITEMS = {"wood": 80, "brick": 80, "glass": 20, "gear": 40, "gem": 10}


def _rich(test_db, kid_id, points=8000):
    set_kid_points(test_db, kid_id, points)
    grant_inventory(test_db, kid_id, dict(RICH_ITEMS))


def _resources(test_db, kid_id):
    return {
        "points": get_kid_points(test_db, kid_id),
        "experience": get_kid_experience(test_db, kid_id),
        "inventory": inventory_map(test_db, kid_id),
    }


def _rows(test_db, kid_id):
    db = connect_db(test_db)
    found = db.execute(
        """
        SELECT b.id, b.def_id, bd.name, b.level, b.cell_x, b.cell_y,
               COALESCE(b.stored, 0) AS stored
          FROM buildings b
          JOIN building_defs bd ON bd.id = b.def_id
         WHERE b.kid_id=?
         ORDER BY b.id
        """,
        (kid_id,),
    ).fetchall()
    db.close()
    return [dict(row) for row in found]


def _row(test_db, building_id):
    db = connect_db(test_db)
    found = db.execute(
        """
        SELECT b.id, b.def_id, bd.name, b.level, b.cell_x, b.cell_y,
               COALESCE(b.stored, 0) AS stored
          FROM buildings b
          JOIN building_defs bd ON bd.id = b.def_id
         WHERE b.id=?
        """,
        (building_id,),
    ).fetchone()
    db.close()
    return dict(found) if found else None


def _cost(test_db, building_def):
    db = connect_db(test_db)
    row = db.execute(
        "SELECT cost_gold, materials FROM building_defs WHERE id=?",
        (building_def,),
    ).fetchone()
    db.close()
    materials = json.loads(row["materials"] or "{}")
    return int(row["cost_gold"] or 0), materials


def _place(client, kid_id, building_def, cell_x=None, cell_y=None, omit=False):
    if omit:
        body = {"def_id": building_def}
    else:
        body = {"def_id": building_def, "cell_x": cell_x, "cell_y": cell_y}
    return client.post(f"/api/kids/{kid_id}/buildings", json=body)


def _unstore(client, kid_id, building_id, cell_x=None, cell_y=None, omit=False):
    if omit:
        body = {}
    else:
        body = {"cell_x": cell_x, "cell_y": cell_y}
    return client.post(
        f"/api/kids/{kid_id}/buildings/{building_id}/unstored",
        json=body,
    )


def _list_buildings(client, kid_id):
    """GET 會跑 warehouse_legacy_out_of_grid。"""
    return client.get(f"/api/kids/{kid_id}/buildings")


def _move(client, kid_id, building_id, cell_x=None, cell_y=None, omit=False):
    if omit:
        body = {}
    else:
        body = {"cell_x": cell_x, "cell_y": cell_y}
    return client.post(
        f"/api/kids/{kid_id}/buildings/{building_id}/move",
        json=body,
    )


def _reload_placement(client, kid_id):
    """GET buildings and town. Both run warehouse_legacy_out_of_grid."""
    listed = _list_buildings(client, kid_id)
    town = client.get(f"/api/kids/{kid_id}/town")
    return listed, town


def _unchanged(before_res, after_res, before_row, after_row):
    problems = []
    if after_res != before_res:
        problems.append(f"resources {before_res} -> {after_res}")
    if after_row != before_row:
        problems.append(f"row {before_row} -> {after_row}")
    return problems


@pytest.mark.case_id("TC-API-WAREHOUSE-UNSTORE-OK")
def test_unstore_inside_8x8_keeps_level_and_does_not_charge(client, family, test_db):
    """TC-API-WAREHOUSE-UNSTORE-OK 8×8 空格取出：stored=0、等級不變、唔扣任何資源。

    (7,7) 係 8×8 最後一格，必須接受。載入城鎮之後唔好再自動收倉。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    hospital = insert_building(
        test_db, kid_id, def_id(test_db, "hospital"), level=2, stored=1, cell_x=20, cell_y=12
    )
    library = insert_building(
        test_db, kid_id, def_id(test_db, "library"), level=2, stored=1, cell_x=0, cell_y=0
    )
    login_kid(client, family)
    before = _resources(test_db, kid_id)

    placed = _unstore(client, kid_id, hospital, 7, 7)
    assert placed.status_code in (200, 201), (
        f"expected unstore 醫院 Lv.2 to (7,7) HTTP 200, got {placed.status_code}: "
        f"{response_text(placed)[:300]}"
    )
    corner = _unstore(client, kid_id, library, 1, 1)
    assert corner.status_code in (200, 201), (
        f"expected unstore 圖書館 Lv.2 to (1,1) HTTP 200, got {corner.status_code}: "
        f"{response_text(corner)[:300]}"
    )
    listed = _list_buildings(client, kid_id)
    assert listed.status_code == 200, response_text(listed)
    after = _resources(test_db, kid_id)
    hospital_row = _row(test_db, hospital)
    library_row = _row(test_db, library)
    assert after == before, f"unstore must not charge, {before} -> {after}"
    assert hospital_row["stored"] == 0 and (hospital_row["cell_x"], hospital_row["cell_y"]) == (7, 7), (
        f"expected 醫院 stored=0 at (7,7), got {hospital_row}"
    )
    assert hospital_row["level"] == 2, hospital_row
    assert library_row["stored"] == 0 and (library_row["cell_x"], library_row["cell_y"]) == (1, 1), (
        f"expected 圖書館 stored=0 at (1,1), got {library_row}"
    )
    assert library_row["level"] == 2, library_row


@pytest.mark.case_id("TC-API-WAREHOUSE-UNSTORE-OOB")
def test_unstore_outside_8x8_is_rejected_without_changes(client, family, test_db):
    """TC-API-WAREHOUSE-UNSTORE-OOB 格外、負數以外的舊座標都要 4xx，行同資源唔變。

    (8,0)、(0,8)、(8,8)、(20,12) 而家會 200，因為閘門係 0–22 × 0–14。
    跟住 GET /buildings 會把格外原點收倉，但座標已經被改走。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    keys = ("library", "gym", "farm", "workshop")
    seeded = []
    for index, key in enumerate(keys):
        seeded.append(
            insert_building(
                test_db,
                kid_id,
                def_id(test_db, key),
                level=2,
                stored=1,
                cell_x=16 + index,
                cell_y=10,
            )
        )
    login_kid(client, family)
    problems = []
    for building_id, (cell_x, cell_y) in zip(seeded, LEGACY_OUTSIDE):
        before_res = _resources(test_db, kid_id)
        before_row = _row(test_db, building_id)
        response = _unstore(client, kid_id, building_id, cell_x, cell_y)
        _list_buildings(client, kid_id)
        after_res = _resources(test_db, kid_id)
        after_row = _row(test_db, building_id)
        if response.status_code not in REJECT_STATUSES:
            problems.append(
                f"({cell_x},{cell_y}) expected 4xx, got {response.status_code} "
                f"{response_text(response)[:180]}"
            )
        drift = _unchanged(before_res, after_res, before_row, after_row)
        if drift:
            problems.append(
                f"({cell_x},{cell_y}) expected no change (still stored=1, same x/y, "
                f"same resources); {'; '.join(drift)}. "
                "place/unstore still use 0-22 x 0-14 "
                "(backend_v2.py:3264 and :3374); GET then runs "
                "warehouse_legacy_out_of_grid (backend_v2.py:1619)."
            )
    assert not problems, "TC-API-WAREHOUSE-UNSTORE-OOB: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-WAREHOUSE-UNSTORE-REJECT")
def test_unstore_rejects_missing_negative_occupied_and_tile(client, family, test_db):
    """TC-API-WAREHOUSE-UNSTORE-REJECT 缺座標、負數、原點佔用、地磚佔用：4xx 而且唔改資料。"""
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    library = insert_building(
        test_db, kid_id, def_id(test_db, "library"), level=2, stored=1, cell_x=18, cell_y=10
    )
    gym = insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=2, stored=1, cell_x=16, cell_y=8
    )
    farm = insert_building(
        test_db, kid_id, def_id(test_db, "farm"), level=2, stored=1, cell_x=14, cell_y=6
    )
    insert_building(
        test_db, kid_id, def_id(test_db, "shop"), level=1, stored=0, cell_x=2, cell_y=2
    )
    bank = insert_building(
        test_db, kid_id, def_id(test_db, "bank"), level=2, stored=1, cell_x=12, cell_y=4
    )
    db = connect_db(test_db)
    db.execute(
        "INSERT INTO town_tiles (kid_id, cell_x, cell_y, tile_type) VALUES (?, ?, ?, ?)",
        (kid_id, 5, 5, "tree"),
    )
    db.commit()
    db.close()
    login_kid(client, family)
    problems = []
    calls = {
        "missing": lambda: _unstore(client, kid_id, library, omit=True),
        "negative-x": lambda: _unstore(client, kid_id, gym, -1, 0),
        "negative-y": lambda: _unstore(client, kid_id, farm, 0, -1),
        "origin-occupied": lambda: _unstore(client, kid_id, library, 2, 2),
        "tile": lambda: _unstore(client, kid_id, bank, 4, 4),
    }
    owners = {
        "missing": library,
        "negative-x": gym,
        "negative-y": farm,
        "origin-occupied": library,
        "tile": bank,
    }
    for name, call in calls.items():
        building_id = owners[name]
        before_res = _resources(test_db, kid_id)
        before_row = _row(test_db, building_id)
        response = call()
        after_res = _resources(test_db, kid_id)
        after_row = _row(test_db, building_id)
        if response.status_code not in REJECT_STATUSES:
            problems.append(
                f"{name} expected 4xx, got {response.status_code} {response_text(response)[:180]}"
            )
        drift = _unchanged(before_res, after_res, before_row, after_row)
        if drift:
            problems.append(f"{name} expected no change; {'; '.join(drift)}")
    assert not problems, "TC-API-WAREHOUSE-UNSTORE-REJECT: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-WAREHOUSE-UNSTORE-OVERLAP")
def test_unstore_rejects_footprint_overlap(client, family, test_db):
    """TC-API-WAREHOUSE-UNSTORE-OVERLAP 2×2 足跡重疊要拒絕。

    已放置原點 (0,0) 佔 (0,0)–(1,1)。取出到 (1,0) 佔 (1,0)–(2,1)，重疊 (1,0) 同 (1,1)。
    而家只檢查有冇另一行的原點落在新 2×2 上，所以會 200。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
    )
    hospital = insert_building(
        test_db,
        kid_id,
        def_id(test_db, "hospital"),
        level=2,
        stored=1,
        cell_x=20,
        cell_y=12,
    )
    login_kid(client, family)
    before_res = _resources(test_db, kid_id)
    before_row = _row(test_db, hospital)
    response = _unstore(client, kid_id, hospital, 1, 0)
    after_res = _resources(test_db, kid_id)
    after_row = _row(test_db, hospital)
    problems = []
    if response.status_code not in REJECT_STATUSES:
        problems.append(
            f"expected 4xx for 2x2 overlap of 健身室 (0,0) and 醫院 (1,0), "
            f"got {response.status_code} {response_text(response)[:180]}"
        )
    problems.extend(_unchanged(before_res, after_res, before_row, after_row))
    assert not problems, (
        "TC-API-WAREHOUSE-UNSTORE-OVERLAP: expected reject and no data change "
        "(row stays stored=1 at (20,12), resources unchanged). "
        + " | ".join(problems)
    )


@pytest.mark.case_id("TC-API-WAREHOUSE-STORED-OCC")
def test_stored_rows_do_not_occupy_map_cells(client, family, test_db):
    """TC-API-WAREHOUSE-STORED-OCC 存倉列的舊座標唔好霸佔地圖。

    只有 stored=0 的屋同地磚先算佔用。另一座 stored=1 的原點唔可以令取出或新建造 400。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    library = insert_building(
        test_db, kid_id, def_id(test_db, "library"), level=2, stored=1, cell_x=0, cell_y=0
    )
    hospital = insert_building(
        test_db, kid_id, def_id(test_db, "hospital"), level=2, stored=1, cell_x=20, cell_y=12
    )
    bank = insert_building(
        test_db, kid_id, def_id(test_db, "bank"), level=1, stored=1, cell_x=4, cell_y=4
    )
    login_kid(client, family)
    before = _resources(test_db, kid_id)
    response = _unstore(client, kid_id, hospital, 0, 0)
    hospital_row = _row(test_db, hospital)
    library_row = _row(test_db, library)
    after_unstore = _resources(test_db, kid_id)
    problems = []
    if response.status_code not in (200, 201):
        problems.append(
            f"unstore 醫院 onto stored 圖書館 origin (0,0) expected HTTP 200, "
            f"got {response.status_code} {response_text(response)[:180]}"
        )
    if hospital_row["stored"] != 0 or (hospital_row["cell_x"], hospital_row["cell_y"]) != (0, 0):
        problems.append(f"expected 醫院 stored=0 at (0,0), got {hospital_row}")
    if hospital_row["level"] != 2:
        problems.append(f"expected 醫院 level 2, got {hospital_row}")
    if library_row["stored"] != 1:
        problems.append(f"stored 圖書館 must stay stored, got {library_row}")
    if after_unstore != before:
        problems.append(f"unstore charged resources {before} -> {after_unstore}")

    gym_before = _resources(test_db, kid_id)
    built = _place(client, kid_id, def_id(test_db, "gym"), 4, 4)
    if built.status_code not in (200, 201):
        problems.append(
            "new 健身室 at (4,4) must ignore stored 銀行 still recorded at (4,4); "
            f"got {built.status_code} {response_text(built)[:180]}"
        )
    else:
        gym_rows = [row for row in _rows(test_db, kid_id) if row["name"] == "健身室"]
        if len(gym_rows) != 1 or gym_rows[0]["stored"] != 0:
            problems.append(f"expected one placed 健身室, got {gym_rows}")
        if _row(test_db, bank)["stored"] != 1:
            problems.append("stored 銀行 must stay stored")
        gold, materials = _cost(test_db, def_id(test_db, "gym"))
        gym_after = _resources(test_db, kid_id)
        if gym_after["points"] != gym_before["points"] - gold:
            problems.append(
                f"健身室 gold expected {gym_before['points'] - gold}, got {gym_after['points']}"
            )
        for item_type, qty in materials.items():
            have = gym_after["inventory"].get(item_type, 0)
            want = gym_before["inventory"].get(item_type, 0) - qty
            if have != want:
                problems.append(f"{item_type} expected {want}, got {have}")
    assert not problems, "TC-API-WAREHOUSE-STORED-OCC: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-WAREHOUSE-BUILD-OK")
def test_new_build_on_7_7_charges_catalog_and_stays_placed(client, family, test_db):
    """TC-API-WAREHOUSE-BUILD-OK (7,7) 新建造成功，扣目錄價，GET 之後仍然 stored=0。"""
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    login_kid(client, family)
    building_def = def_id(test_db, "library")
    gold, materials = _cost(test_db, building_def)
    before = _resources(test_db, kid_id)
    response = _place(client, kid_id, building_def, 7, 7)
    assert response.status_code == 201, response_text(response)
    listed = _list_buildings(client, kid_id)
    assert listed.status_code == 200, response_text(listed)
    rows = _rows(test_db, kid_id)
    after = _resources(test_db, kid_id)
    assert len(rows) == 1, rows
    assert rows[0]["stored"] == 0 and (rows[0]["cell_x"], rows[0]["cell_y"]) == (7, 7), rows
    assert rows[0]["level"] == 1, rows
    assert after["points"] == before["points"] - gold, (before, after, gold)
    for item_type, qty in materials.items():
        assert after["inventory"].get(item_type, 0) == before["inventory"].get(item_type, 0) - qty


@pytest.mark.case_id("TC-API-WAREHOUSE-BUILD-OOB")
def test_new_build_outside_8x8_does_not_charge_or_store(client, family, test_db):
    """TC-API-WAREHOUSE-BUILD-OOB 格外建造要拒絕：唔扣資源、唔新增行、唔好收進存倉。

    而家 (8,0) 等會 201 並扣資源。GET /buildings 再把該行設 stored=1。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    login_kid(client, family)
    targets = (
        ("library", (8, 0)),
        ("gym", (0, 8)),
        ("farm", (8, 8)),
        ("workshop", (20, 12)),
    )
    problems = []
    for key, (cell_x, cell_y) in targets:
        before_res = _resources(test_db, kid_id)
        before_rows = _rows(test_db, kid_id)
        response = _place(client, kid_id, def_id(test_db, key), cell_x, cell_y)
        _list_buildings(client, kid_id)
        after_res = _resources(test_db, kid_id)
        after_rows = _rows(test_db, kid_id)
        if response.status_code not in REJECT_STATUSES:
            problems.append(
                f"{key} ({cell_x},{cell_y}) expected 4xx, got {response.status_code} "
                f"{response_text(response)[:160]}"
            )
        if after_res != before_res:
            problems.append(
                f"{key} ({cell_x},{cell_y}) charged resources {before_res} -> {after_res}"
            )
        if after_rows != before_rows:
            problems.append(
                f"{key} ({cell_x},{cell_y}) expected no new row and nothing put in storage, "
                f"got {after_rows}"
            )
    assert not problems, (
        "TC-API-WAREHOUSE-BUILD-OOB: illegal cells must not deduct resources, "
        "insert a row, or warehouse one. "
        + " | ".join(problems)
    )


@pytest.mark.case_id("TC-API-WAREHOUSE-BUILD-REJECT")
def test_new_build_rejects_missing_negative_occupied_and_tile(client, family, test_db):
    """TC-API-WAREHOUSE-BUILD-REJECT 缺座標、負數、原點佔用、地磚：4xx，唔扣、唔新增。"""
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    insert_building(
        test_db, kid_id, def_id(test_db, "shop"), level=1, stored=0, cell_x=2, cell_y=2
    )
    db = connect_db(test_db)
    db.execute(
        "INSERT INTO town_tiles (kid_id, cell_x, cell_y, tile_type) VALUES (?, ?, ?, ?)",
        (kid_id, 5, 5, "tree"),
    )
    db.commit()
    db.close()
    login_kid(client, family)
    calls = (
        ("missing", "library", lambda: _place(client, kid_id, def_id(test_db, "library"), omit=True)),
        ("negative", "gym", lambda: _place(client, kid_id, def_id(test_db, "gym"), -1, 0)),
        ("origin-occupied", "library", lambda: _place(client, kid_id, def_id(test_db, "library"), 2, 2)),
        ("tile", "farm", lambda: _place(client, kid_id, def_id(test_db, "farm"), 4, 4)),
    )
    problems = []
    for name, _key, call in calls:
        before_res = _resources(test_db, kid_id)
        before_rows = _rows(test_db, kid_id)
        response = call()
        after_res = _resources(test_db, kid_id)
        after_rows = _rows(test_db, kid_id)
        if response.status_code not in REJECT_STATUSES:
            problems.append(
                f"{name} expected 4xx, got {response.status_code} {response_text(response)[:160]}"
            )
        if after_res != before_res or after_rows != before_rows:
            problems.append(
                f"{name} expected no charge and no new row; resources {before_res} -> {after_res}; "
                f"rows {before_rows} -> {after_rows}"
            )
    assert not problems, "TC-API-WAREHOUSE-BUILD-REJECT: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-WAREHOUSE-BUILD-OVERLAP")
def test_new_build_rejects_footprint_overlap_without_charge(client, family, test_db):
    """TC-API-WAREHOUSE-BUILD-OVERLAP 新屋 2×2 撞到已放置足跡：4xx，唔扣、唔新增、唔入倉。"""
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
    )
    login_kid(client, family)
    before_res = _resources(test_db, kid_id)
    before_rows = _rows(test_db, kid_id)
    response = _place(client, kid_id, def_id(test_db, "library"), 1, 0)
    _list_buildings(client, kid_id)
    after_res = _resources(test_db, kid_id)
    after_rows = _rows(test_db, kid_id)
    problems = []
    if response.status_code not in REJECT_STATUSES:
        problems.append(
            f"expected 4xx, got {response.status_code} {response_text(response)[:180]}"
        )
    if after_res != before_res:
        problems.append(f"charged {before_res} -> {after_res}")
    if after_rows != before_rows:
        problems.append(f"rows changed {before_rows} -> {after_rows}")
    assert not problems, (
        "TC-API-WAREHOUSE-BUILD-OVERLAP: 圖書館 at (1,0) overlaps 健身室 2x2 at (0,0). "
        "Expected reject, no resources deducted, no new row, nothing stored. "
        + " | ".join(problems)
    )


@pytest.mark.case_id("TC-API-WAREHOUSE-BUILD-REUSE")
def test_build_reuses_stored_building_without_charge_or_duplicate(client, family, test_db):
    """TC-API-WAREHOUSE-BUILD-REUSE 再起一種已經喺存倉的屋：用返嗰行。

    核准：「要用返存倉嗰間」。呼叫之後剛好一行、stored=0、放在要求的格、
    等級保留、金幣同材料都唔扣。而家係 400「你已經興建咗呢種建築物」，行維持 stored=1。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    library = insert_building(
        test_db, kid_id, def_id(test_db, "library"), level=2, stored=1, cell_x=20, cell_y=12
    )
    login_kid(client, family)
    before = _resources(test_db, kid_id)
    response = _place(client, kid_id, def_id(test_db, "library"), 3, 3)
    rows = [row for row in _rows(test_db, kid_id) if row["name"] == "圖書館"]
    after = _resources(test_db, kid_id)
    problems = []
    if response.status_code not in (200, 201):
        problems.append(
            f"expected HTTP 200 and the stored row placed, got {response.status_code} "
            f"{response_text(response)[:180]}"
        )
    if len(rows) != 1:
        problems.append(f"expected exactly one 圖書館 row, got {rows}")
    elif rows[0]["id"] != library or rows[0]["stored"] != 0:
        problems.append(f"expected the same row stored=0, got {rows[0]}")
    elif (rows[0]["cell_x"], rows[0]["cell_y"]) != (3, 3) or rows[0]["level"] != 2:
        problems.append(f"expected level 2 at (3,3), got {rows[0]}")
    if after != before:
        problems.append(f"must not charge, {before} -> {after}")
    assert not problems, "TC-API-WAREHOUSE-BUILD-REUSE: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-WAREHOUSE-MOVE-OOB")
def test_move_outside_8x8_is_rejected_and_stays_placed(client, family, test_db):
    """TC-API-WAREHOUSE-MOVE-OOB 移去 8×8 外要 4xx，行留在原格而且仍然放置。

    (8,0)、(0,8)、(8,8)、負數、(20,12)。而家除負數外會 200（閘門 0–22 × 0–14，
    backend_v2.py:3333）。跟住 GET /buildings 同 GET /town 會把格外原點收倉。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    targets = (
        ("library", (0, 0), (8, 0)),
        ("gym", (2, 0), (0, 8)),
        ("farm", (4, 0), (8, 8)),
        ("workshop", (6, 0), (-1, 0)),
        ("shop", (0, 2), (0, -1)),
        ("hospital", (2, 2), (20, 12)),
    )
    seeded = []
    for key, (origin_x, origin_y), _dest in targets:
        seeded.append(
            insert_building(
                test_db,
                kid_id,
                def_id(test_db, key),
                level=2,
                stored=0,
                cell_x=origin_x,
                cell_y=origin_y,
            )
        )
    login_kid(client, family)
    problems = []
    for building_id, (key, origin, dest) in zip(seeded, targets):
        cell_x, cell_y = dest
        before_res = _resources(test_db, kid_id)
        before_row = _row(test_db, building_id)
        response = _move(client, kid_id, building_id, cell_x, cell_y)
        listed, town = _reload_placement(client, kid_id)
        after_res = _resources(test_db, kid_id)
        after_row = _row(test_db, building_id)
        if response.status_code not in REJECT_STATUSES:
            problems.append(
                f"{key} ({cell_x},{cell_y}) expected 4xx, got {response.status_code} "
                f"{response_text(response)[:160]}"
            )
        if after_res != before_res or after_row != before_row:
            problems.append(
                f"{key} ({cell_x},{cell_y}) expected no change "
                f"(stored=0 at {origin}, same resources); "
                f"row {before_row} -> {after_row}; resources {before_res} -> {after_res}"
            )
        if after_row["stored"] != 0 or (after_row["cell_x"], after_row["cell_y"]) != origin:
            problems.append(
                f"{key} after buildings/town GET expected still placed at {origin}, "
                f"got stored={after_row['stored']} at "
                f"({after_row['cell_x']},{after_row['cell_y']}). "
                "move_building accepts 0-22 x 0-14 (backend_v2.py:3333); "
                "GET then runs warehouse_legacy_out_of_grid (backend_v2.py:1619)."
            )
        if listed.status_code != 200 or town.status_code != 200:
            problems.append(
                f"{key} reload HTTP buildings={listed.status_code} town={town.status_code}"
            )
    assert not problems, "TC-API-WAREHOUSE-MOVE-OOB: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-WAREHOUSE-MOVE-OVERLAP")
def test_move_rejects_footprint_overlap(client, family, test_db):
    """TC-API-WAREHOUSE-MOVE-OVERLAP 移去另一座已放置屋的 2×2 足跡要 4xx，資料不變。

    健身室原點 (0,0) 佔 (0,0)–(1,1)。醫院由 (4,0) 移到 (1,0) 佔 (1,0)–(2,1)。
    而家只檢查有冇另一行的原點落在新 2×2 上，所以會 200。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
    )
    hospital = insert_building(
        test_db, kid_id, def_id(test_db, "hospital"), level=2, stored=0, cell_x=4, cell_y=0
    )
    login_kid(client, family)
    before_res = _resources(test_db, kid_id)
    before_row = _row(test_db, hospital)
    response = _move(client, kid_id, hospital, 1, 0)
    after_res = _resources(test_db, kid_id)
    after_row = _row(test_db, hospital)
    problems = []
    if response.status_code not in REJECT_STATUSES:
        problems.append(
            f"expected 4xx for 2x2 overlap of 健身室 (0,0) and 醫院 (1,0), "
            f"got {response.status_code} {response_text(response)[:180]}"
        )
    problems.extend(_unchanged(before_res, after_res, before_row, after_row))
    assert not problems, (
        "TC-API-WAREHOUSE-MOVE-OVERLAP: expected reject and no data change "
        "(醫院 stays stored=0 at (4,0), level 2, resources unchanged). "
        + " | ".join(problems)
    )


@pytest.mark.case_id("TC-API-WAREHOUSE-MOVE-STORED-OCC")
def test_move_onto_stored_leftover_coords_succeeds(client, family, test_db):
    """TC-API-WAREHOUSE-MOVE-STORED-OCC 存倉行的舊座標唔霸佔，移動可以落到該格。

    只有 stored=0 的屋同地磚先算佔用。而家 stored=1 的原點都會 400「該位置已被佔用」。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    library = insert_building(
        test_db, kid_id, def_id(test_db, "library"), level=2, stored=1, cell_x=0, cell_y=0
    )
    gym = insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=2, stored=0, cell_x=4, cell_y=4
    )
    login_kid(client, family)
    before = _resources(test_db, kid_id)
    response = _move(client, kid_id, gym, 0, 0)
    gym_row = _row(test_db, gym)
    library_row = _row(test_db, library)
    after = _resources(test_db, kid_id)
    problems = []
    if response.status_code not in (200, 201):
        problems.append(
            f"move 健身室 onto stored 圖書館 origin (0,0) expected HTTP 200, "
            f"got {response.status_code} {response_text(response)[:180]}"
        )
    if gym_row["stored"] != 0 or (gym_row["cell_x"], gym_row["cell_y"]) != (0, 0):
        problems.append(f"expected 健身室 stored=0 at (0,0), got {gym_row}")
    if gym_row["level"] != 2:
        problems.append(f"expected 健身室 level 2, got {gym_row}")
    if library_row["stored"] != 1 or (library_row["cell_x"], library_row["cell_y"]) != (0, 0):
        problems.append(f"stored 圖書館 must stay stored at (0,0), got {library_row}")
    if after != before:
        problems.append(f"move charged resources {before} -> {after}")
    assert not problems, "TC-API-WAREHOUSE-MOVE-STORED-OCC: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-WAREHOUSE-MOVE-OK")
def test_move_inside_8x8_keeps_level_and_does_not_charge(client, family, test_db):
    """TC-API-WAREHOUSE-MOVE-OK 移到 8×8 空格成功，等級不變，唔扣資源，GET 之後仍然放置。"""
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    hospital = insert_building(
        test_db, kid_id, def_id(test_db, "hospital"), level=2, stored=0, cell_x=0, cell_y=0
    )
    login_kid(client, family)
    before = _resources(test_db, kid_id)
    response = _move(client, kid_id, hospital, 7, 7)
    listed, town = _reload_placement(client, kid_id)
    row = _row(test_db, hospital)
    after = _resources(test_db, kid_id)
    assert response.status_code == 200, response_text(response)
    assert listed.status_code == 200, response_text(listed)
    assert town.status_code == 200, response_text(town)
    assert row["stored"] == 0 and (row["cell_x"], row["cell_y"]) == (7, 7), row
    assert row["level"] == 2, row
    assert after == before, (before, after)
    payload = town.get_json()
    placed = [item for item in payload.get("buildings") or [] if item.get("id") == hospital]
    stored = [item for item in payload.get("stored_buildings") or [] if item.get("id") == hospital]
    assert placed and placed[0].get("cell_x") == 7 and placed[0].get("cell_y") == 7, payload
    assert stored == [], stored


@pytest.mark.case_id("TC-API-WAREHOUSE-EFFECT-GUILD")
def test_guild_hall_unlocks_only_after_unstore(client, family, test_db):
    """TC-API-WAREHOUSE-EFFECT-GUILD 存倉公會唔開公會大廳；取出後探險可以出發。

    公會大廳冇獨立旗標。閘門係 has_active_guild：stored=1 時
    POST /expedition/start 回 guild_required；取出到 8×8 之後回 201。
    """
    kid_id = family.kid_a.id
    set_kid_points(test_db, kid_id, 50)
    guild = insert_building(
        test_db, kid_id, def_id(test_db, "guild"), level=1, stored=1, cell_x=6, cell_y=6
    )
    login_kid(client, family)
    blocked = start_explore(client, kid_id, 1)
    assert blocked.status_code in REJECT_STATUSES, response_text(blocked)
    body = blocked.get_json(silent=True) or {}
    assert body.get("error") == "guild_required", body
    assert get_kid_points(test_db, kid_id) == 50
    town_before = client.get(f"/api/kids/{kid_id}/town").get_json()
    stored_names = [row["name"] for row in town_before.get("stored_buildings") or []]
    placed_names = [row["name"] for row in town_before.get("buildings") or []]
    assert "探險公會" in stored_names, stored_names
    assert "探險公會" not in placed_names, placed_names

    response = _unstore(client, kid_id, guild, 2, 2)
    assert response.status_code in (200, 201), response_text(response)
    assert get_kid_points(test_db, kid_id) == 50
    opened = start_explore(client, kid_id, 1)
    assert opened.status_code == 201, (
        f"expected 公會大廳 unlocked via expedition/start 201 after unstore, "
        f"got {opened.status_code} {response_text(opened)[:200]}"
    )
    assert get_kid_points(test_db, kid_id) == 40
    town_after = client.get(f"/api/kids/{kid_id}/town").get_json()
    assert any(row["name"] == "探險公會" and row["stored"] == 0 for row in town_after["buildings"])
    assert not any(row["name"] == "探險公會" for row in town_after["stored_buildings"])


@pytest.mark.case_id("TC-API-WAREHOUSE-EFFECT-LIBRARY")
def test_library_effects_apply_only_after_unstore(client, family, test_db):
    """TC-API-WAREHOUSE-EFFECT-LIBRARY 圖書館取出後先計知識加成同技能。

    task_bonus 已經由 _drop_library_task_bonus 清走，award_task_drops 的
    experience_bonus 固定係 0（P1-TC-BUFF-01）。呢度鎖仍然接住 stored=0 的效果：
    GET /abilities 的 buffs.int（Lv.2 = +4）同 GET /skills 的知識的力量、火球。
    """
    kid_id = family.kid_a.id
    library = insert_building(
        test_db, kid_id, def_id(test_db, "library"), level=2, stored=1, cell_x=18, cell_y=4
    )
    login_kid(client, family)
    before_skills = client.get(f"/api/kids/{kid_id}/skills").get_json()
    before_abilities = client.get(f"/api/kids/{kid_id}/abilities").get_json()
    before_names = {row.get("name") for row in before_skills}
    assert before_abilities["buffs"]["int"] == 0, before_abilities
    assert "知識的力量" not in before_names and "火球" not in before_names, before_names
    db = connect_db(test_db)
    try:
        assert backend.get_building_buff(kid_id, "task_bonus", db) is None
    finally:
        db.close()

    response = _unstore(client, kid_id, library, 4, 4)
    assert response.status_code in (200, 201), response_text(response)
    skills = client.get(f"/api/kids/{kid_id}/skills").get_json()
    abilities = client.get(f"/api/kids/{kid_id}/abilities").get_json()
    names = {row.get("name") for row in skills}
    assert abilities["buffs"]["int"] == 4, (
        f"expected 圖書館 Lv.2 knowledge buff 4 after unstore, got {abilities}"
    )
    assert {"知識的力量", "火球"} <= names, names
    db = connect_db(test_db)
    try:
        assert backend.get_building_buff(kid_id, "task_bonus", db) is None
    finally:
        db.close()


@pytest.mark.case_id("TC-API-WAREHOUSE-EFFECT-FARM")
def test_farm_daily_gold_applies_only_after_unstore(client, family, test_db):
    """TC-API-WAREHOUSE-EFFECT-FARM 存倉農場領唔到；取出 Lv.2 之後每日金幣係 10。"""
    kid_id = family.kid_a.id
    set_kid_points(test_db, kid_id, 100)
    farm = insert_building(
        test_db, kid_id, def_id(test_db, "farm"), level=2, stored=1, cell_x=12, cell_y=6
    )
    login_kid(client, family)
    denied = client.post(f"/api/kids/{kid_id}/farm/claim", json={})
    assert denied.status_code in REJECT_STATUSES, response_text(denied)
    assert (denied.get_json(silent=True) or {}).get("error") == "farm_required"
    assert get_kid_points(test_db, kid_id) == 100
    response = _unstore(client, kid_id, farm, 0, 4)
    assert response.status_code in (200, 201), response_text(response)
    assert get_kid_points(test_db, kid_id) == 100
    claimed = client.post(f"/api/kids/{kid_id}/farm/claim", json={})
    assert claimed.status_code == 200, response_text(claimed)
    assert get_kid_points(test_db, kid_id) == 110, get_kid_points(test_db, kid_id)


@pytest.mark.case_id("TC-API-WAREHOUSE-EFFECT-SHOP")
def test_shop_discount_applies_only_after_unstore(client, family, test_db):
    """TC-API-WAREHOUSE-EFFECT-SHOP 存倉商店唔打折；取出後下一座屋的金幣先用九折。"""
    kid_id = family.kid_a.id
    _rich(test_db, kid_id, points=1000)
    shop = insert_building(
        test_db, kid_id, def_id(test_db, "shop"), level=1, stored=1, cell_x=20, cell_y=10
    )
    login_kid(client, family)
    gym_cost, _gym_mats = _cost(test_db, def_id(test_db, "gym"))
    before = get_kid_points(test_db, kid_id)
    built = _place(client, kid_id, def_id(test_db, "gym"), 0, 0)
    assert built.status_code == 201, response_text(built)
    assert get_kid_points(test_db, kid_id) == before - gym_cost, (
        f"stored shop must not discount; expected {before - gym_cost}, "
        f"got {get_kid_points(test_db, kid_id)}"
    )
    response = _unstore(client, kid_id, shop, 4, 0)
    assert response.status_code in (200, 201), response_text(response)
    library_cost, _library_mats = _cost(test_db, def_id(test_db, "library"))
    discounted = max(1, math.floor(library_cost * 0.9))
    mid = get_kid_points(test_db, kid_id)
    second = _place(client, kid_id, def_id(test_db, "library"), 2, 2)
    assert second.status_code == 201, response_text(second)
    assert get_kid_points(test_db, kid_id) == mid - discounted, (
        f"placed shop Lv.1 should charge {discounted}, points {mid} -> "
        f"{get_kid_points(test_db, kid_id)}"
    )


@pytest.mark.case_id("TC-API-WAREHOUSE-REPAIR")
def test_legacy_out_of_grid_stored_buildings_unstore_into_8x8(client, family, test_db):
    """TC-API-WAREHOUSE-REPAIR 舊圖格外的存倉屋可以放回 8×8，等級保留，唔扣資源。

    另外一座 stored=0 但原點在 (21,13) 的屋，GET 建築之後應先被收倉，然後一樣可以取出。
    """
    kid_id = family.kid_a.id
    _rich(test_db, kid_id)
    plan = (
        ("guild", 1, 20, 12, 0, 0),
        ("bank", 1, 22, 14, 2, 0),
        ("library", 2, 18, 10, 4, 0),
        ("hospital", 2, 16, 8, 6, 0),
        ("farm", 1, 12, 6, 0, 2),
    )
    ids = {}
    for key, level, old_x, old_y, new_x, new_y in plan:
        ids[key] = (
            insert_building(
                test_db,
                kid_id,
                def_id(test_db, key),
                level=level,
                stored=1,
                cell_x=old_x,
                cell_y=old_y,
            ),
            level,
            new_x,
            new_y,
        )
    workshop = insert_building(
        test_db, kid_id, def_id(test_db, "workshop"), level=3, stored=0, cell_x=21, cell_y=13
    )
    login_kid(client, family)
    listed = _list_buildings(client, kid_id)
    assert listed.status_code == 200, response_text(listed)
    warehoused = _row(test_db, workshop)
    assert warehoused["stored"] == 1 and warehoused["level"] == 3, warehoused
    before = _resources(test_db, kid_id)
    response = _unstore(client, kid_id, workshop, 2, 2)
    assert response.status_code in (200, 201), response_text(response)
    for key, (building_id, level, new_x, new_y) in ids.items():
        moved = _unstore(client, kid_id, building_id, new_x, new_y)
        assert moved.status_code in (200, 201), (
            f"{key} unstore to ({new_x},{new_y}) got {moved.status_code} "
            f"{response_text(moved)[:180]}"
        )
        row = _row(test_db, building_id)
        assert row["stored"] == 0 and (row["cell_x"], row["cell_y"]) == (new_x, new_y), row
        assert row["level"] == level, row
    town = client.get(f"/api/kids/{kid_id}/town")
    assert town.status_code == 200, response_text(town)
    payload = town.get_json()
    placed = {(row["name"], row["level"], row["cell_x"], row["cell_y"]) for row in payload["buildings"]}
    assert payload["stored_buildings"] == [], payload["stored_buildings"]
    assert ("工坊", 3, 2, 2) in {(row["name"], row["level"], row["cell_x"], row["cell_y"]) for row in payload["buildings"]}
    assert len(placed) == 6, placed
    assert _resources(test_db, kid_id) == before


@pytest.mark.case_id("TC-FE-WAREHOUSE-GRID")
def test_served_frontend_placement_grid_is_8x8(client):
    """TC-FE-WAREHOUSE-GRID 建造／取出用的前端常數都要係 8×8，唔好再係 24×16。

    四場景 town-four-scene.js 已經係 8。index.html 的 renderTownBuildings
    仍畫 24×16 .valid-plot，存倉取出走呢條路。
    """
    page = client.get("/kids/")
    script = client.get("/kids/town-four-scene.js")
    assert page.status_code == 200, page.status_code
    assert script.status_code == 200, script.status_code
    html = page.get_data(as_text=True)
    js = script.get_data(as_text=True)
    scene = re.search(r"var\s+COLS\s*=\s*(\d+)\s*;\s*var\s+ROWS\s*=\s*(\d+)\s*;", js)
    assert scene, "town-four-scene.js is missing COLS/ROWS"
    scene_grid = (int(scene.group(1)), int(scene.group(2)))
    start = html.find("function renderTownBuildings")
    end = html.find("\nfunction ", start + 10)
    chunk = html[start:end if end != -1 else start + 30000]
    legacy = re.search(r"const\s+COLS\s*=\s*(\d+)\s*,\s*ROWS\s*=\s*(\d+)", chunk)
    assert legacy, "renderTownBuildings is missing COLS/ROWS"
    legacy_grid = (int(legacy.group(1)), int(legacy.group(2)))
    assert "valid-plot" in chunk
    problems = []
    if scene_grid != (8, 8):
        problems.append(f"town-four-scene.js COLS,ROWS={scene_grid}, expected (8, 8)")
    if legacy_grid != (8, 8):
        problems.append(
            f"index.html renderTownBuildings COLS,ROWS={legacy_grid}, expected (8, 8). "
            "That function paints .valid-plot for startPlacement and startUnstoreBuilding. "
            "A 24×16 grid is the legacy limit and must not remain on the build/unstore path."
        )
    assert not problems, "TC-FE-WAREHOUSE-GRID: " + " | ".join(problems)
