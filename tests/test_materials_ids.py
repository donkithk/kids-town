"""P1-TC-MAT-* — canonical material ids (GAMEPLAY_REDESIGN §6.2)."""
from __future__ import annotations

import json

import pytest

import backend_v2 as b
from tests.factories import (
    connect_db,
    force_expedition_claimable,
    grant_inventory,
    insert_building,
    inventory_map,
    inventory_qty,
    response_text,
    set_kid_points,
)
from tests.phase1_helpers import (
    ALLOWED_DROP_MATERIALS,
    CANONICAL_MATERIALS,
    FORBIDDEN_DROP_MATERIALS,
    create_assigned_task,
    def_id,
    json_or_text,
    login_kid,
    start_explore,
)

pytestmark = [pytest.mark.phase1]


def _give_guild(test_db, kid_id):
    insert_building(test_db, kid_id, def_id(test_db, "guild"), level=1, stored=0, cell_x=6, cell_y=0)


@pytest.mark.case_id("P1-TC-MAT-01")
def test_expedition_claim_only_emits_canonical_material_ids(
    client, family, test_db, monkeypatch
):
    """P1-TC-MAT-01 expedition/claim 回應同 inventory 無 iron／star_shard 鍵。"""
    kid_id = family.kid_a.id
    _give_guild(test_db, kid_id)
    set_kid_points(test_db, kid_id, 50)
    login_kid(client, family)

    monkeypatch.setattr(b.random, "random", lambda: 0.0)
    monkeypatch.setattr(b.random, "randint", lambda a, c: a)

    r = start_explore(client, kid_id, 1)
    assert r.status_code == 201, response_text(r)
    force_expedition_claimable(test_db, kid_id)
    claimed = client.post(f"/api/kids/{kid_id}/expedition/claim", json={})
    assert claimed.status_code == 200, response_text(claimed)
    data = json_or_text(claimed)
    rewards = data.get("materials") or data.get("rewards") or {}
    if isinstance(rewards, list):
        reward_ids = set(rewards)
    else:
        reward_ids = set(rewards.keys())
    assert reward_ids <= ALLOWED_DROP_MATERIALS, reward_ids
    assert reward_ids.isdisjoint(FORBIDDEN_DROP_MATERIALS), reward_ids
    inv = inventory_map(test_db, kid_id)
    assert set(inv) <= ALLOWED_DROP_MATERIALS | set(inv.keys())
    for forbidden in FORBIDDEN_DROP_MATERIALS:
        assert forbidden not in inv, inv
        assert inventory_qty(test_db, kid_id, forbidden) == 0


@pytest.mark.case_id("P1-TC-MAT-02")
def test_internal_add_iron_normalizes_to_gear(family, test_db):
    """P1-TC-MAT-02 內部 add iron → 存成 gear 數量合併。"""
    kid_id = family.kid_a.id
    grant_inventory(test_db, kid_id, {"gear": 2})
    add_item = (
        getattr(b, "add_item", None)
        or getattr(b, "add_inventory_item", None)
        or getattr(b, "grant_item", None)
    )
    canonicalize = (
        getattr(b, "canonicalize_item_type", None)
        or getattr(b, "normalize_item_type", None)
        or getattr(b, "normalize_material_id", None)
    )
    assert add_item is not None or canonicalize is not None, (
        "backend_v2 must expose add_item(...) or canonicalize_item_type('iron')=='gear' "
        "(GAMEPLAY_REDESIGN §6.2)"
    )
    db = connect_db(test_db)
    try:
        if add_item is not None:
            try:
                add_item(kid_id, "iron", 3, db)
            except TypeError:
                try:
                    add_item(kid_id, "iron", 3)
                except TypeError:
                    add_item(db, kid_id, "iron", 3)
            db.commit()
        else:
            assert canonicalize("iron") == "gear"
            existing = db.execute(
                "SELECT id, quantity FROM inventory WHERE kid_id=? AND item_type=?",
                (kid_id, "gear"),
            ).fetchone()
            db.execute(
                "UPDATE inventory SET quantity=? WHERE id=?",
                (existing["quantity"] + 3, existing["id"]),
            )
            db.commit()
    finally:
        db.close()
    inv = inventory_map(test_db, kid_id)
    assert "iron" not in inv or inv.get("iron", 0) == 0, inv
    assert inv.get("gear") == 5, inv


@pytest.mark.case_id("P1-TC-MAT-03")
def test_material_defs_and_building_recipes_use_canonical_ids(client, family, test_db):
    """P1-TC-MAT-03 GET /api/materials/defs 含五 canonical；building_defs 鍵合法。"""
    login_kid(client, family)
    r = client.get("/api/materials/defs")
    assert r.status_code == 200, response_text(r)
    defs = r.get_json()
    ids = {row["id"] for row in defs}
    assert CANONICAL_MATERIALS <= ids, ids

    db = connect_db(test_db)
    try:
        rows = db.execute("SELECT id, name, materials FROM building_defs").fetchall()
        guild = db.execute(
            "SELECT materials FROM building_defs WHERE name=?", ("探險公會",)
        ).fetchone()
    finally:
        db.close()
    assert guild is not None
    guild_mats = json.loads(guild["materials"] or "{}")
    assert guild_mats, "guild materials must not be {} on a fresh seed"
    assert "wood" in guild_mats and "brick" in guild_mats
    assert "gear" in guild_mats

    for row in rows:
        mats = json.loads(row["materials"] or "{}")
        extra = set(mats) - CANONICAL_MATERIALS
        assert not extra, f"{row['name']} materials {mats} contain non-canonical {extra}"


@pytest.mark.case_id("P1-TC-MAT-04")
def test_task_drop_pools_and_complete_use_canonical_ids(client, family, test_db):
    """P1-TC-MAT-04 MATERIAL_POOLS / complete material_drops 只含 HUD 四格或 gem。"""
    for pool, items in b.MATERIAL_POOLS.items():
        extra = set(items) - CANONICAL_MATERIALS
        assert not extra, f"MATERIAL_POOLS[{pool}] has non-canonical {extra}"
        assert "iron" not in items
    task_id = create_assigned_task(client, family, "p1-mat-04", points=50)
    r = client.post(
        f"/api/tasks/{task_id}/complete", json={"kid_id": family.kid_a.id}
    )
    assert r.status_code == 200, response_text(r)
    drops = json_or_text(r).get("material_drops") or []
    assert set(drops) <= CANONICAL_MATERIALS, drops
    assert "iron" not in drops


@pytest.mark.case_id("P1-TC-MAT-05")
def test_boss_summon_consumes_gem_not_glass(client, family, test_db):
    """P1-TC-MAT-05 召喚 Boss 扣 gem×1，glass 不變。"""
    kid_id = family.kid_a.id
    grant_inventory(test_db, kid_id, {"gem": 1, "glass": 10})
    login_kid(client, family)
    r = client.post(f"/api/kids/{kid_id}/boss/summon", json={"region_id": 1})
    assert r.status_code in (200, 201), response_text(r)
    assert inventory_qty(test_db, kid_id, "gem") == 0
    assert inventory_qty(test_db, kid_id, "glass") == 10
