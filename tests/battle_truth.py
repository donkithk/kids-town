"""Shared setup for passive-effect and skill-truth tests.

Test-only. Product code must not import this module.
Empty SQLite and synthetic kids only.
"""
from __future__ import annotations

import json

import backend_v2 as b
from tests.factories import connect_db, fetchone, insert_building
from tests.phase1_helpers import def_id, login_kid


def prepare_kid(
    test_db,
    kid_id,
    *,
    level=20,
    points=200,
    ability_str=0,
    ability_int=0,
    ability_spd=0,
    ability_crt=0,
    ability_brv=0,
):
    """Zero the synthetic kid and clear buildings, daily wins, and running fights."""
    db = connect_db(test_db)
    db.execute(
        """
        UPDATE kids
           SET level=?, points=?, experience=0,
               ability_str=?, ability_int=?, ability_spd=?,
               ability_crt=?, ability_brv=?
         WHERE id=?
        """,
        (
            level,
            points,
            ability_str,
            ability_int,
            ability_spd,
            ability_crt,
            ability_brv,
            kid_id,
        ),
    )
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.execute("DELETE FROM daily_battles WHERE kid_id=?", (kid_id,))
    db.execute(
        "UPDATE expeditions SET status='completed' WHERE kid_id=? AND status='running'",
        (kid_id,),
    )
    db.commit()
    db.close()


def place(test_db, kid_id, key, level=1, stored=0, cell_x=0, cell_y=0):
    return insert_building(
        test_db,
        kid_id,
        def_id(test_db, key),
        level=level,
        stored=stored,
        cell_x=cell_x,
        cell_y=cell_y,
    )


def install_randint(monkeypatch, monsters=1, hit_roll=100):
    """Freeze battle RNG.

    Monster count and HP jitter are fixed. Damage variance rolls return 0.
    A 1..100 roll returns hit_roll so a full hit rate still connects and a
    reduced hit rate (under 100) misses.
    """

    def randint(lo, hi):
        if (lo, hi) == (1, 3):
            return monsters
        if (lo, hi) == (-5, 5):
            return 0
        if (lo, hi) == (1, 100):
            return hit_roll
        return 0

    monkeypatch.setattr(b.random, "randint", randint)


def login_and_start(client, family, kid_id, monkeypatch, region=1, monsters=1):
    login_kid(client, family)
    install_randint(monkeypatch, monsters=monsters)
    response = client.post(
        f"/api/kids/{kid_id}/expedition/battle-start",
        json={"region_id": region},
    )
    return response


def running_battle(test_db, kid_id):
    row = fetchone(
        test_db,
        """
        SELECT id, expedition_data FROM expeditions
         WHERE kid_id=? AND status='running'
           AND expedition_type IN ('battle','boss')
         ORDER BY id DESC LIMIT 1
        """,
        (kid_id,),
    )
    assert row and row["expedition_data"], "no running battle to edit"
    return row["id"], json.loads(row["expedition_data"])


def save_battle(test_db, exp_id, data):
    db = connect_db(test_db)
    db.execute(
        "UPDATE expeditions SET expedition_data=? WHERE id=?",
        (json.dumps(data), exp_id),
    )
    db.commit()
    db.close()


def skill_by_name(battle, name):
    return next((row for row in battle.get("skills") or [] if row.get("name") == name), None)


def act(client, kid_id, action, skill_id=None, target=0):
    body = {"action": action, "target_idx": target}
    if skill_id is not None:
        body["skill_id"] = skill_id
    return client.post(f"/api/kids/{kid_id}/expedition/battle-action", json=body)


def monster_hp(body, index=0):
    return body["monsters"][index]["hp"]


def expected_from_abilities(*, str_v=0, int_v=0, spd_v=0, crt_v=0, brv_v=0):
    """Same formulas as calc_battle_stats, fed by building passives + kid base.

    atk  = int(5 + str * 1.5)
    matk = int(5 + int * 1.5)
    def  = int(brv * 0.6)
    crt  = min(50, crt * 2)
    dodge = min(40, spd * 1.5)
    """
    return {
        "player_atk": int(5 + str_v * 1.5),
        "player_matk": int(5 + int_v * 1.5),
        "player_def": int(brv_v * 0.6),
        "player_crt": min(50, crt_v * 2),
        "player_dodge": min(40, spd_v * 1.5),
    }
