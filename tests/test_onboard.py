"""ONB-* Phase 1.5 onboarding pack (GAMEPLAY_REDESIGN §6.6 / §7 / §9 Q3–Q4).

TDD RED against current main: guild seed is still ~600 gold + gear, and
create-kid does not grant the 120 / wood×8 / brick×5 starter pack.

Empty-DB fixtures only. Never copy kids_town.db. Synthetic PIN 1357 only.
"""
from __future__ import annotations

import json

import pytest

from tests.factories import (
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    count_rows,
    force_expedition_claimable,
    get_kid_points,
    get_kid_row,
    grant_inventory,
    insert_building,
    inventory_qty,
    login_as,
    make_parent,
    response_text,
    set_kid_points,
)
from tests.phase1_helpers import (
    GUILD_COST_GOLD,
    GUILD_COST_MATERIALS,
    STARTER_MATERIALS,
    STARTER_POINTS,
    def_id,
    json_or_text,
    login_kid,
    place_building,
    start_explore,
)

pytestmark = [pytest.mark.phase1_5]

STARTER_WOOD = STARTER_MATERIALS["wood"]
STARTER_BRICK = STARTER_MATERIALS["brick"]
GUILD_WOOD = GUILD_COST_MATERIALS["wood"]
GUILD_BRICK = GUILD_COST_MATERIALS["brick"]


def _parse_materials(raw):
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _guild_seed_row(test_db):
    from tests.factories import fetchone

    row = fetchone(test_db, "SELECT * FROM building_defs WHERE name=?", ("探險公會",))
    assert row, "building_defs missing 探險公會"
    return row


def _truthy_flag(value):
    return value in (1, True, "1", "true", "True") and value not in (0, False, "0", "")


def _starter_granted_sources(kid_json, test_db, kid_id):
    """Collect starter_granted from create-kid JSON and/or kids row."""
    sources = {}
    if isinstance(kid_json, dict) and "starter_granted" in kid_json:
        sources["json"] = kid_json.get("starter_granted")
    row = get_kid_row(test_db, kid_id) or {}
    if "starter_granted" in row:
        sources["db"] = row.get("starter_granted")
    return sources


def assert_starter_granted(kid_json, test_db, kid_id):
    sources = _starter_granted_sources(kid_json, test_db, kid_id)
    assert sources, (
        "starter_granted missing from create-kid JSON and kids row "
        "(GAMEPLAY_REDESIGN §6.6 flag starter_granted)"
    )
    assert any(_truthy_flag(v) for v in sources.values()), sources


def _create_kid_as_parent(client, parent, username, name):
    r = client.post(
        "/api/auth/create-kid",
        json={
            "parent_id": parent["id"],
            "name": name,
            "username": username,
            "pin": TEST_KID_PIN,
            "avatar": "👦",
        },
    )
    return r


@pytest.mark.case_id("ONB-GUILD-01")
def test_seed_guild_cost_is_150_wood10_brick5_no_gear(client, test_db):
    """ONB-GUILD-01 seed/defs 公會成本 150 + wood×10 + brick×5，無 gear 需求。"""
    row = _guild_seed_row(test_db)
    mats = _parse_materials(row.get("materials"))
    assert row.get("cost_gold") == GUILD_COST_GOLD, row
    assert mats.get("wood") == GUILD_WOOD, mats
    assert mats.get("brick") == GUILD_BRICK, mats
    assert mats.get("gear", 0) == 0, f"guild materials must not require gear: {mats}"
    assert "gear" not in mats, f"materials JSON has no gear requirement: {mats}"

    r = client.get("/api/building-defs")
    assert r.status_code == 200, response_text(r)
    defs = r.get_json() or []
    api = next((d for d in defs if d.get("name") == "探險公會"), None)
    assert api, defs
    api_mats = _parse_materials(api.get("materials"))
    assert api.get("cost_gold") == GUILD_COST_GOLD, api
    assert api_mats.get("wood") == GUILD_WOOD, api_mats
    assert api_mats.get("brick") == GUILD_BRICK, api_mats
    assert api_mats.get("gear", 0) == 0, api_mats
    assert "gear" not in api_mats, api_mats


@pytest.mark.case_id("ONB-GUILD-02")
def test_place_guild_with_exact_150_gold_and_wood_brick_succeeds(client, family, test_db):
    """ONB-GUILD-02 恰好 150 金 + wood10 brick5（無 gear）place 公會 → 201。"""
    kid_id = family.kid_a.id
    guild_id = def_id(test_db, "guild")
    set_kid_points(test_db, kid_id, GUILD_COST_GOLD)
    grant_inventory(test_db, kid_id, {"wood": GUILD_WOOD, "brick": GUILD_BRICK})
    login_kid(client, family)

    before = count_rows(test_db, "buildings", "kid_id=? AND def_id=?", (kid_id, guild_id))
    r = place_building(client, kid_id, guild_id, cell_x=6, cell_y=0)
    assert r.status_code == 201, response_text(r)
    assert count_rows(test_db, "buildings", "kid_id=? AND def_id=?", (kid_id, guild_id)) == before + 1
    assert get_kid_points(test_db, kid_id) == 0
    assert inventory_qty(test_db, kid_id, "wood") == 0
    assert inventory_qty(test_db, kid_id, "brick") == 0


@pytest.mark.case_id("ONB-GUILD-03")
def test_place_guild_with_149_gold_is_insufficient(client, family, test_db):
    """ONB-GUILD-03 149 金（木磚足夠）→ insufficient 400，無 building 行。"""
    kid_id = family.kid_a.id
    guild_id = def_id(test_db, "guild")
    set_kid_points(test_db, kid_id, GUILD_COST_GOLD - 1)
    grant_inventory(test_db, kid_id, {"wood": GUILD_WOOD, "brick": GUILD_BRICK})
    login_kid(client, family)

    r = place_building(client, kid_id, guild_id, cell_x=6, cell_y=0)
    assert r.status_code == 400, response_text(r)
    err = str(json_or_text(r).get("error") or "")
    assert "insufficient" in err.lower(), err
    need = json_or_text(r).get("need")
    if need is not None:
        assert need == GUILD_COST_GOLD, json_or_text(r)
    assert count_rows(test_db, "buildings", "kid_id=? AND def_id=?", (kid_id, guild_id)) == 0
    assert get_kid_points(test_db, kid_id) == GUILD_COST_GOLD - 1
    assert inventory_qty(test_db, kid_id, "wood") == GUILD_WOOD
    assert inventory_qty(test_db, kid_id, "brick") == GUILD_BRICK


@pytest.mark.case_id("ONB-START-01")
def test_create_kid_grants_starter_pack_120_wood8_brick5(client, test_db):
    """ONB-START-01 create-kid（家長 session）points=120；wood×8 brick×5；starter_granted。"""
    parent = make_parent(
        client,
        username="test_onb_parent_start01",
        password=TEST_PARENT_PASSWORD,
        name="Onboard Parent Start01",
        email="test_onb_parent_start01@example.test",
    )
    r = _create_kid_as_parent(
        client, parent, username="test_onb_kid_start01", name="Onboard Kid Start01"
    )
    assert r.status_code == 201, response_text(r)
    data = json_or_text(r)
    kid = data.get("kid") or {}
    kid_id = kid.get("id")
    assert kid_id, data

    json_points = kid.get("points")
    db_points = get_kid_points(test_db, kid_id)
    assert json_points == STARTER_POINTS, kid
    assert db_points == STARTER_POINTS, db_points
    wood = inventory_qty(test_db, kid_id, "wood")
    brick = inventory_qty(test_db, kid_id, "brick")
    assert wood >= STARTER_WOOD, wood
    assert brick >= STARTER_BRICK, brick
    assert wood == STARTER_WOOD, f"fresh kid wood must be exactly {STARTER_WOOD}, got {wood}"
    assert brick == STARTER_BRICK, f"fresh kid brick must be exactly {STARTER_BRICK}, got {brick}"
    assert_starter_granted(kid, test_db, kid_id)


@pytest.mark.case_id("ONB-START-02")
def test_starter_pack_is_not_double_granted(client, test_db):
    """ONB-START-02 第二個 create／已發放 kid 唔雙重發放；sibling 各自一份。"""
    parent = make_parent(
        client,
        username="test_onb_parent_start02",
        password=TEST_PARENT_PASSWORD,
        name="Onboard Parent Start02",
        email="test_onb_parent_start02@example.test",
    )
    first = _create_kid_as_parent(
        client, parent, username="test_onb_kid_start02a", name="Onboard Kid Start02A"
    )
    assert first.status_code == 201, response_text(first)
    kid_a = json_or_text(first).get("kid") or {}
    kid_a_id = kid_a["id"]
    assert_starter_granted(kid_a, test_db, kid_a_id)
    assert get_kid_points(test_db, kid_a_id) == STARTER_POINTS
    assert inventory_qty(test_db, kid_a_id, "wood") == STARTER_WOOD
    assert inventory_qty(test_db, kid_a_id, "brick") == STARTER_BRICK

    login = login_as(client, "test_onb_kid_start02a", TEST_KID_PIN)
    assert login.status_code == 200, response_text(login)
    assert get_kid_points(test_db, kid_a_id) == STARTER_POINTS
    assert inventory_qty(test_db, kid_a_id, "wood") == STARTER_WOOD
    assert inventory_qty(test_db, kid_a_id, "brick") == STARTER_BRICK

    login_as(client, parent["username"], TEST_PARENT_PASSWORD)
    second = _create_kid_as_parent(
        client, parent, username="test_onb_kid_start02b", name="Onboard Kid Start02B"
    )
    assert second.status_code == 201, response_text(second)
    kid_b = json_or_text(second).get("kid") or {}
    kid_b_id = kid_b["id"]
    assert_starter_granted(kid_b, test_db, kid_b_id)
    assert get_kid_points(test_db, kid_b_id) == STARTER_POINTS
    assert inventory_qty(test_db, kid_b_id, "wood") == STARTER_WOOD
    assert inventory_qty(test_db, kid_b_id, "brick") == STARTER_BRICK

    assert get_kid_points(test_db, kid_a_id) == STARTER_POINTS
    assert inventory_qty(test_db, kid_a_id, "wood") == STARTER_WOOD
    assert inventory_qty(test_db, kid_a_id, "brick") == STARTER_BRICK


@pytest.mark.case_id("ONB-EXP-01")
def test_claim_region1_explore_then_start_again_is_unlimited(client, family, test_db):
    """ONB-EXP-01 claim 區1 後再 start 區1 → 201（unlimited farm；無 daily cap）。"""
    kid_id = family.kid_a.id
    insert_building(test_db, kid_id, def_id(test_db, "guild"), level=1, stored=0, cell_x=6, cell_y=0)
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
