"""Edge-touching building footprints. Tests and docs only.

Product contract: two footprints may share an edge. There is no required
empty cell between them. A real area overlap stays blocked.

Catalog buildings are 2×2 (`backend_v2._BUILDING_FOOTPRINT`). Touching means
the next origin is exactly one footprint side away — (0,0) beside (2,0) —
not (1,0), which is area overlap. Empty temp DB and synthetic kids only.
Does not open kids_town.db.
"""
from __future__ import annotations

import json
import shutil
import subprocess

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
from tests.phase1_helpers import def_id, login_kid

pytestmark = [pytest.mark.phase1]

OCCUPIED_ERROR = "該位置已被建築物佔用"
RICH_ITEMS = {"wood": 80, "brick": 80, "glass": 20, "gear": 40, "gem": 10}
# (ax, ay, a_size, bx, by, b_size, overlaps, why)
OVERLAP_MATRIX = (
    (0, 0, 2, 2, 0, 2, False, "east edge"),
    (0, 0, 2, 0, 2, 2, False, "south edge"),
    (2, 0, 2, 0, 0, 2, False, "west edge"),
    (0, 2, 2, 0, 0, 2, False, "north edge"),
    (0, 0, 2, 2, 2, 2, False, "corner only"),
    (0, 0, 2, 2, 1, 2, False, "partial east edge"),
    (0, 0, 2, 1, 2, 2, False, "partial south edge"),
    (0, 0, 2, 3, 0, 2, False, "one empty column is allowed, not required"),
    (0, 0, 1, 1, 0, 1, False, "1x1 east edge"),
    (0, 0, 3, 3, 0, 2, False, "mixed-size shared edge"),
    (0, 0, 2, 1, 0, 2, True, "east shift by 1 overlaps a column"),
    (0, 0, 2, 0, 1, 2, True, "south shift by 1 overlaps a row"),
    (0, 0, 2, 1, 1, 2, True, "diagonal shift still overlaps the corner cell"),
    (0, 0, 2, 0, 0, 2, True, "same origin"),
    (0, 0, 1, 0, 0, 1, True, "1x1 same cell"),
    (0, 0, 3, 2, 0, 2, True, "mixed-size area overlap"),
)


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


def _clear_buildings(test_db, kid_id):
    db = connect_db(test_db)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()


def _cost(test_db, name):
    db = connect_db(test_db)
    row = db.execute(
        "SELECT id, cost_gold, materials FROM building_defs WHERE name=?",
        (name,),
    ).fetchone()
    db.close()
    assert row, name
    return int(row["id"]), int(row["cost_gold"] or 0), json.loads(row["materials"] or "{}")


def _place(client, kid_id, building_def, cell_x=None, cell_y=None, omit=False):
    if omit:
        body = {"def_id": building_def}
    else:
        body = {"def_id": building_def, "cell_x": cell_x, "cell_y": cell_y}
    return client.post(f"/api/kids/{kid_id}/buildings", json=body)


def _move(client, kid_id, building_id, cell_x, cell_y):
    return client.post(
        f"/api/kids/{kid_id}/buildings/{building_id}/move",
        json={"cell_x": cell_x, "cell_y": cell_y},
    )


def _unstore(client, kid_id, building_id, cell_x, cell_y):
    return client.post(
        f"/api/kids/{kid_id}/buildings/{building_id}/unstored",
        json={"cell_x": cell_x, "cell_y": cell_y},
    )


def _cells(origin_x, origin_y, size):
    return {
        (origin_x + dx, origin_y + dy)
        for dy in range(size)
        for dx in range(size)
    }


def _shares_edge(left, right):
    for x, y in left:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) in right:
                return True
    return False


def _charge_problems(label, before, after, gold, materials):
    problems = []
    if after["points"] != before["points"] - gold:
        problems.append(
            f"{label} gold {before['points']} -> {after['points']}, expected -{gold}"
        )
    if after["experience"] != before["experience"]:
        problems.append(f"{label} experience changed")
    for item_type, qty in materials.items():
        have = after["inventory"].get(item_type, 0)
        want = before["inventory"].get(item_type, 0) - qty
        if have != want:
            problems.append(f"{label} {item_type} {have}, expected {want}")
    return problems


def _body(response):
    parsed = response.get_json(silent=True)
    if parsed is None:
        return response_text(response)[:300]
    return parsed


@pytest.mark.case_id("TC-API-BUILD-ADJACENT-01")
def test_half_open_overlap_allows_shared_edge(client, family, test_db):
    """TC-API-BUILD-ADJACENT-01 Shared edges are not overlaps. Area overlaps are.

    Half-open squares: [x, x+size) × [y, y+size). `ax + a_size <= bx` means
    the two squares may touch. A strict `<` would reject that touch and force
    a one-cell gap. Catalog names are all size 2, and `/api/building-defs`
    reports that same size.
    """
    problems = []
    for name, size in backend._BUILDING_FOOTPRINT.items():
        if backend._footprint(name) != 2 or size != 2:
            problems.append(f"catalog {name} footprint {backend._footprint(name)} / table {size}")
    if backend._footprint(None) != 2 or backend._footprint("not-a-building") != 2:
        problems.append("unknown footprint must stay 2")

    login_kid(client, family)
    listed = client.get("/api/building-defs")
    if listed.status_code != 200:
        problems.append(f"GET /api/building-defs {listed.status_code} {_body(listed)}")
    else:
        by_name = {row.get("name"): row for row in (listed.get_json(silent=True) or [])}
        for name in backend._BUILDING_FOOTPRINT:
            row = by_name.get(name)
            if not row:
                problems.append(f"building-defs missing {name}")
                continue
            if row.get("footprint") != 2:
                problems.append(f"{name} API footprint {row.get('footprint')!r}, expected 2")

    for ax, ay, a_size, bx, by, b_size, overlaps, why in OVERLAP_MATRIX:
        got = backend._footprints_overlap(ax, ay, a_size, bx, by, b_size)
        if got is not overlaps:
            problems.append(
                f"_footprints_overlap {why}: got {got}, expected {overlaps} "
                f"for ({ax},{ay}) size {a_size} vs ({bx},{by}) size {b_size}"
            )

    kid_id = family.kid_a.id
    _clear_buildings(test_db, kid_id)
    insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
    )
    db = connect_db(test_db)
    allowed, allowed_status = backend._placement_blocked(db, kid_id, 2, 0, None, 2)
    blocked, blocked_status = backend._placement_blocked(db, kid_id, 1, 0, None, 2)
    south, south_status = backend._placement_blocked(db, kid_id, 0, 2, None, 2)
    db.close()
    if (allowed, allowed_status) != (None, None):
        problems.append(f"_placement_blocked (2,0) {allowed!r} {allowed_status}")
    if (south, south_status) != (None, None):
        problems.append(f"_placement_blocked (0,2) {south!r} {south_status}")
    if (blocked, blocked_status) != (OCCUPIED_ERROR, 400):
        problems.append(f"_placement_blocked (1,0) {blocked!r} {blocked_status}")
    assert not problems, "TC-API-BUILD-ADJACENT-01: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-BUILD-ADJACENT-02")
def test_place_edge_adjacent_footprints_succeed(client, family, test_db):
    """TC-API-BUILD-ADJACENT-02 New builds may share an edge. No empty cell required.

    East pack origins (0,0), (2,0), (4,0), (6,0) and the south pack
    (0,0), (0,2), (0,4), (0,6) put 2×2 footprints against each other and
    against the map edge. Also: approach from the west and the north, a
    partial edge, and a corner-only touch. Each success is HTTP 201, the
    row stays stored=0 on that origin, and the catalog price is charged once.
    """
    kid_id = family.kid_a.id
    login_kid(client, family)
    problems = []
    packs = (
        ("east", ((0, 0), (2, 0), (4, 0), (6, 0))),
        ("south", ((0, 0), (0, 2), (0, 4), (0, 6))),
    )
    names = ("健身室", "醫院", "農場", "圖書館")
    for label, origins in packs:
        _clear_buildings(test_db, kid_id)
        _rich(test_db, kid_id)
        placed = []
        for (cell_x, cell_y), name in zip(origins, names):
            building_def, gold, materials = _cost(test_db, name)
            before = _resources(test_db, kid_id)
            response = _place(client, kid_id, building_def, cell_x, cell_y)
            after = _resources(test_db, kid_id)
            body = response.get_json(silent=True) or {}
            if response.status_code != 201:
                problems.append(
                    f"{label} {name} ({cell_x},{cell_y}) expected 201, "
                    f"got {response.status_code} {_body(response)}"
                )
                continue
            if body.get("cell_x") != cell_x or body.get("cell_y") != cell_y:
                problems.append(f"{label} {name} body cell {body.get('cell_x'), body.get('cell_y')}")
            if "error" in body:
                problems.append(f"{label} {name} success body has error {body.get('error')!r}")
            problems.extend(_charge_problems(f"{label} {name}", before, after, gold, materials))
            placed.append((cell_x, cell_y))
        listed = client.get(f"/api/kids/{kid_id}/buildings")
        rows = _rows(test_db, kid_id)
        if listed.status_code != 200:
            problems.append(f"{label} GET buildings {listed.status_code}")
        if len(rows) != len(origins):
            problems.append(f"{label} row count {len(rows)} {rows}")
        for row, origin in zip(rows, origins):
            if row["stored"] != 0 or (row["cell_x"], row["cell_y"]) != origin:
                problems.append(f"{label} row {row} expected stored=0 at {origin}")
        for index, origin in enumerate(placed):
            mine = _cells(*origin, 2)
            for other in placed[index + 1:]:
                theirs = _cells(*other, 2)
                if not mine.isdisjoint(theirs):
                    problems.append(f"{label} {origin} overlaps {other}")
                if abs(origin[0] - other[0]) + abs(origin[1] - other[1]) == 2:
                    if not _shares_edge(mine, theirs):
                        problems.append(f"{label} {origin} does not share an edge with {other}")

    singles = (
        ("west", "健身室", 2, 0, "醫院", 0, 0),
        ("north", "健身室", 0, 2, "醫院", 0, 0),
        ("partial-east", "健身室", 0, 0, "醫院", 2, 1),
        ("corner", "健身室", 0, 0, "醫院", 2, 2),
    )
    for label, anchor_name, ax, ay, new_name, nx, ny in singles:
        _clear_buildings(test_db, kid_id)
        _rich(test_db, kid_id)
        insert_building(
            test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=ax, cell_y=ay
        )
        building_def, gold, materials = _cost(test_db, new_name)
        before = _resources(test_db, kid_id)
        before_rows = _rows(test_db, kid_id)
        response = _place(client, kid_id, building_def, nx, ny)
        after = _resources(test_db, kid_id)
        body = response.get_json(silent=True) or {}
        if response.status_code != 201:
            problems.append(
                f"{label} {new_name} ({nx},{ny}) next to {anchor_name} ({ax},{ay}) "
                f"expected 201, got {response.status_code} {_body(response)}"
            )
            continue
        if (body.get("cell_x"), body.get("cell_y")) != (nx, ny):
            problems.append(f"{label} body cell {(body.get('cell_x'), body.get('cell_y'))}")
        problems.extend(_charge_problems(label, before, after, gold, materials))
        rows = _rows(test_db, kid_id)
        if len(rows) != len(before_rows) + 1:
            problems.append(f"{label} expected one new row, {before_rows} -> {rows}")
        anchor_cells = _cells(ax, ay, 2)
        new_cells = _cells(nx, ny, 2)
        if not anchor_cells.isdisjoint(new_cells):
            problems.append(f"{label} footprints overlap")
        if label != "corner" and not _shares_edge(anchor_cells, new_cells):
            problems.append(f"{label} footprints do not share an edge")
        if label == "corner" and _shares_edge(anchor_cells, new_cells):
            problems.append("corner setup unexpectedly shares an edge")
    assert not problems, "TC-API-BUILD-ADJACENT-02: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-BUILD-ADJACENT-03")
def test_place_true_area_overlap_is_blocked(client, family, test_db):
    """TC-API-BUILD-ADJACENT-03 Area overlap stays HTTP 400 with the occupied error.

    健身室 at (0,0) covers (0,0), (1,0), (0,1), (1,1). A new 2×2 at (1,0),
    (0,1), or (1,1) overlaps that area. The body is exactly
    {"error": "該位置已被建築物佔用"}. Gold, materials, and rows stay put.
    """
    kid_id = family.kid_a.id
    login_kid(client, family)
    problems = []
    targets = ((1, 0), (0, 1), (1, 1))
    for cell_x, cell_y in targets:
        _clear_buildings(test_db, kid_id)
        _rich(test_db, kid_id)
        insert_building(
            test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
        )
        building_def, _gold, _materials = _cost(test_db, "醫院")
        before = _resources(test_db, kid_id)
        before_rows = _rows(test_db, kid_id)
        response = _place(client, kid_id, building_def, cell_x, cell_y)
        after = _resources(test_db, kid_id)
        after_rows = _rows(test_db, kid_id)
        body = response.get_json(silent=True)
        if response.status_code != 400:
            problems.append(
                f"({cell_x},{cell_y}) expected 400, got {response.status_code} {_body(response)}"
            )
        if body != {"error": OCCUPIED_ERROR}:
            problems.append(f"({cell_x},{cell_y}) body {body!r}")
        if after != before:
            problems.append(f"({cell_x},{cell_y}) resources {before} -> {after}")
        if after_rows != before_rows:
            problems.append(f"({cell_x},{cell_y}) rows changed {before_rows} -> {after_rows}")
    assert not problems, "TC-API-BUILD-ADJACENT-03: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-BUILD-ADJACENT-04")
def test_move_allows_shared_edge_and_blocks_overlap(client, family, test_db):
    """TC-API-BUILD-ADJACENT-04 Move may land on a shared edge. Overlap does not.

    Success body is {"ok": true, "cell_x": ..., "cell_y": ...} and HTTP 200.
    Overlap is HTTP 400 {"error": "該位置已被建築物佔用"}; the row stays.
    Moving the only building onto its own old cells is allowed (the row is
    excluded from the check), so a one-cell slide is not a self-gap.
    """
    kid_id = family.kid_a.id
    login_kid(client, family)
    problems = []

    _clear_buildings(test_db, kid_id)
    _rich(test_db, kid_id)
    insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
    )
    hospital = insert_building(
        test_db, kid_id, def_id(test_db, "hospital"), level=2, stored=0, cell_x=4, cell_y=4
    )
    before = _resources(test_db, kid_id)
    moved = _move(client, kid_id, hospital, 2, 0)
    moved_body = moved.get_json(silent=True)
    if moved.status_code != 200 or moved_body != {"ok": True, "cell_x": 2, "cell_y": 0}:
        problems.append(f"move to (2,0) {moved.status_code} {moved_body!r}")
    rows = {row["id"]: row for row in _rows(test_db, kid_id)}
    hospital_row = rows.get(hospital)
    if not hospital_row or hospital_row["stored"] != 0 or hospital_row["level"] != 2:
        problems.append(f"hospital after edge move {hospital_row}")
    if hospital_row and (hospital_row["cell_x"], hospital_row["cell_y"]) != (2, 0):
        problems.append(f"hospital cell {hospital_row}")
    if _resources(test_db, kid_id) != before:
        problems.append("edge move charged resources")
    gym = next(row for row in rows.values() if row["name"] == "健身室")
    if (gym["cell_x"], gym["cell_y"]) != (0, 0) or gym["stored"] != 0:
        problems.append(f"gym moved unexpectedly {gym}")

    before = _resources(test_db, kid_id)
    before_row = _rows(test_db, kid_id)
    blocked = _move(client, kid_id, hospital, 1, 0)
    blocked_body = blocked.get_json(silent=True)
    if blocked.status_code != 400 or blocked_body != {"error": OCCUPIED_ERROR}:
        problems.append(f"move to (1,0) {blocked.status_code} {blocked_body!r}")
    if _rows(test_db, kid_id) != before_row:
        problems.append(f"overlap move changed rows {before_row} -> {_rows(test_db, kid_id)}")
    if _resources(test_db, kid_id) != before:
        problems.append("overlap move charged resources")

    _clear_buildings(test_db, kid_id)
    _rich(test_db, kid_id)
    alone = insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=3, stored=0, cell_x=0, cell_y=0
    )
    before = _resources(test_db, kid_id)
    slid = _move(client, kid_id, alone, 1, 0)
    slid_body = slid.get_json(silent=True)
    if slid.status_code != 200 or slid_body != {"ok": True, "cell_x": 1, "cell_y": 0}:
        problems.append(f"solo slide to (1,0) {slid.status_code} {slid_body!r}")
    alone_row = next(row for row in _rows(test_db, kid_id) if row["id"] == alone)
    if (alone_row["cell_x"], alone_row["cell_y"], alone_row["level"], alone_row["stored"]) != (1, 0, 3, 0):
        problems.append(f"solo slide row {alone_row}")
    if _resources(test_db, kid_id) != before:
        problems.append("solo slide charged resources")
    assert not problems, "TC-API-BUILD-ADJACENT-04: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-BUILD-ADJACENT-05")
def test_unstore_allows_shared_edge_and_blocks_overlap(client, family, test_db):
    """TC-API-BUILD-ADJACENT-05 Unstore may share an edge. Overlap stays stored.

    Success is HTTP 200, stored=0, level kept, no charge. Overlap is HTTP 400
    {"error": "該位置已被建築物佔用"} and the row stays stored=1 at (20,12).
    """
    kid_id = family.kid_a.id
    login_kid(client, family)
    problems = []

    def seed(stored_at):
        _clear_buildings(test_db, kid_id)
        _rich(test_db, kid_id)
        insert_building(
            test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
        )
        return insert_building(
            test_db,
            kid_id,
            def_id(test_db, "hospital"),
            level=2,
            stored=1,
            cell_x=stored_at[0],
            cell_y=stored_at[1],
        )

    for cell_x, cell_y in ((2, 0), (0, 2)):
        hospital = seed((20, 12))
        before = _resources(test_db, kid_id)
        response = _unstore(client, kid_id, hospital, cell_x, cell_y)
        body = response.get_json(silent=True) or {}
        if response.status_code != 200:
            problems.append(
                f"unstore ({cell_x},{cell_y}) expected 200, got {response.status_code} {_body(response)}"
            )
            continue
        if (body.get("cell_x"), body.get("cell_y")) != (cell_x, cell_y):
            problems.append(f"unstore ({cell_x},{cell_y}) body cell {body}")
        if body.get("level") != 2:
            problems.append(f"unstore ({cell_x},{cell_y}) level {body.get('level')}")
        if "error" in body:
            problems.append(f"unstore ({cell_x},{cell_y}) body error {body.get('error')!r}")
        row = next(item for item in _rows(test_db, kid_id) if item["id"] == hospital)
        if row["stored"] != 0 or (row["cell_x"], row["cell_y"]) != (cell_x, cell_y) or row["level"] != 2:
            problems.append(f"unstore ({cell_x},{cell_y}) row {row}")
        if _resources(test_db, kid_id) != before:
            problems.append(f"unstore ({cell_x},{cell_y}) charged resources")

    hospital = seed((20, 12))
    before = _resources(test_db, kid_id)
    before_rows = _rows(test_db, kid_id)
    response = _unstore(client, kid_id, hospital, 1, 0)
    body = response.get_json(silent=True)
    if response.status_code != 400 or body != {"error": OCCUPIED_ERROR}:
        problems.append(f"unstore overlap {response.status_code} {body!r}")
    if _rows(test_db, kid_id) != before_rows:
        problems.append("unstore overlap changed rows")
    if _resources(test_db, kid_id) != before:
        problems.append("unstore overlap charged resources")
    assert not problems, "TC-API-BUILD-ADJACENT-05: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-BUILD-ADJACENT-06")
def test_auto_place_picks_touching_origin_not_a_one_cell_gap(client, family, test_db):
    """TC-API-BUILD-ADJACENT-06 Omitting coordinates picks the touching origin.

    With 健身室 at (0,0), the first free 2×2 origin in row-major order is
    (2,0), which shares the east edge. (3,0) would leave column x=2 empty.
    The new row is stored=0 at (2,0) and the catalog price is charged once.
    """
    kid_id = family.kid_a.id
    _clear_buildings(test_db, kid_id)
    _rich(test_db, kid_id)
    insert_building(
        test_db, kid_id, def_id(test_db, "gym"), level=1, stored=0, cell_x=0, cell_y=0
    )
    login_kid(client, family)
    building_def, gold, materials = _cost(test_db, "醫院")
    before = _resources(test_db, kid_id)
    response = _place(client, kid_id, building_def, omit=True)
    body = response.get_json(silent=True) or {}
    after = _resources(test_db, kid_id)
    rows = [row for row in _rows(test_db, kid_id) if row["name"] == "醫院"]
    problems = []
    if response.status_code != 201:
        problems.append(f"expected 201, got {response.status_code} {_body(response)}")
    if (body.get("cell_x"), body.get("cell_y")) != (2, 0):
        problems.append(
            f"auto origin {body.get('cell_x'), body.get('cell_y')}, expected (2,0) "
            "which shares an edge. (3,0) would be a one-cell gap."
        )
    if len(rows) != 1 or rows[0]["stored"] != 0 or (rows[0]["cell_x"], rows[0]["cell_y"]) != (2, 0):
        problems.append(f"hospital row {rows}")
    problems.extend(_charge_problems("auto", before, after, gold, materials))
    gym = [row for row in _rows(test_db, kid_id) if row["name"] == "健身室"]
    if len(gym) != 1 or (gym[0]["cell_x"], gym[0]["cell_y"], gym[0]["stored"]) != (0, 0, 0):
        problems.append(f"gym changed {gym}")
    assert not problems, "TC-API-BUILD-ADJACENT-06: " + " | ".join(problems)


def _frontend_overlap_results(cases):
    node = shutil.which("node")
    if not node:
        pytest.fail("TC-FE-BUILD-ADJACENT-01: node is not on PATH")
    script = r"""
const fs = require("fs");
const src = fs.readFileSync("town-four-scene.js", "utf8");
const match = src.match(/function footprintsOverlap\(ax, ay, aSize, bx, by, bSize\) \{[\s\S]*?\n  \}/);
if (!match) {
  console.error("footprintsOverlap not found");
  process.exit(2);
}
const footprintsOverlap = new Function(match[0] + "\nreturn footprintsOverlap;")();
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
const out = cases.map((row) => {
  const overlap = footprintsOverlap(row.ax, row.ay, row.a, row.bx, row.by, row.b);
  return Object.assign({}, row, { overlap: !!overlap });
});
process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(
        [node, "-e", script],
        input=json.dumps(cases),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(
            "TC-FE-BUILD-ADJACENT-01: node failed "
            f"{proc.returncode} {proc.stderr[:400]}"
        )
    return json.loads(proc.stdout)


@pytest.mark.case_id("TC-FE-BUILD-ADJACENT-01")
def test_frontend_overlap_matches_half_open_backend():
    """TC-FE-BUILD-ADJACENT-01 The map's footprintsOverlap matches the API.

    Runs the function in town-four-scene.js. A change from `<=` to `<` makes
    a shared edge count as overlap and fails this case. Toast copy used when
    that rejection reaches the player is locked beside the formula.
    """
    cases = [
        {
            "ax": ax,
            "ay": ay,
            "a": a_size,
            "bx": bx,
            "by": by,
            "b": b_size,
            "expect": overlaps,
            "why": why,
        }
        for ax, ay, a_size, bx, by, b_size, overlaps, why in OVERLAP_MATRIX
    ]
    got = _frontend_overlap_results(cases)
    problems = []
    for row in got:
        backend_overlap = backend._footprints_overlap(
            row["ax"], row["ay"], row["a"], row["bx"], row["by"], row["b"]
        )
        if row["overlap"] is not row["expect"] or row["overlap"] is not backend_overlap:
            problems.append(
                f"{row['why']}: js {row['overlap']} expected {row['expect']} "
                f"backend {backend_overlap}"
            )
    source = open("town-four-scene.js", encoding="utf-8").read()
    # showUnfit matches the API phrase 「已被建築物佔用」 inside
    # 「該位置已被建築物佔用」 and then shows the unfit toast. The full
    # API sentence lives in backend_v2.py, not in this file.
    required = (
        "這個位置放不下這座建築物。",
        "這個位置已經有建築物。",
        "這裏已有「",
        "起好「",
        "已放好「",
        "城鎮沒有空位，請先收起或移動其他建築。",
        "已被建築物佔用",
    )
    for text in required:
        if text not in source:
            problems.append(f"town-four-scene.js missing {text!r}")
    if "ax + aSize <= bx" not in source:
        problems.append("frontend separation no longer uses ax + aSize <= bx")
    assert not problems, "TC-FE-BUILD-ADJACENT-01: " + " | ".join(problems)
