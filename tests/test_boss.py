"""Boss 集料召喚系統 tests (TDD — RED first)."""
import sqlite3
from datetime import datetime, timedelta

import backend_v2 as b


def _kid_id(battle_kid):
    return battle_kid["id"]


def _clear(db, kid_id):
    db.execute("DELETE FROM expeditions WHERE status='running'")
    db.execute(
        "DELETE FROM inventory WHERE kid_id=? AND item_type IN ('gem','dragon_scale')",
        (kid_id,),
    )
    db.execute("DELETE FROM boss_progress WHERE kid_id=?", (kid_id,))
    db.commit()


def _give_gem(db, kid_id, qty=5):
    db.execute(
        "INSERT INTO inventory (kid_id, item_type, quantity) VALUES (?, 'gem', ?)",
        (kid_id, qty),
    )
    db.commit()


def test_boss_summon_requires_material(client, test_db, battle_kid):
    kid_id = _kid_id(battle_kid)
    db = sqlite3.connect(test_db)
    _clear(db, kid_id)
    db.close()
    r = client.post(f"/api/kids/{kid_id}/boss/summon", json={"region_id": 1})
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "材料" in r.get_json()["error"]


def test_boss_summon_creates_boss_battle(client, test_db, battle_kid):
    kid_id = _kid_id(battle_kid)
    db = sqlite3.connect(test_db)
    _clear(db, kid_id)
    _give_gem(db, kid_id)
    db.close()
    r = client.post(f"/api/kids/{kid_id}/boss/summon", json={"region_id": 1})
    assert r.status_code == 201, r.get_data(as_text=True)
    d = r.get_json()
    m = d["monsters"][0]
    assert m["hp"] == 120, f"boss HP 應該 120, 得到 {m['hp']}"
    assert d.get("is_boss") is True


def test_boss_requires_previous_region_kill(client, test_db, battle_kid):
    kid_id = _kid_id(battle_kid)
    db = sqlite3.connect(test_db)
    _clear(db, kid_id)
    _give_gem(db, kid_id)
    db.close()
    r = client.post(f"/api/kids/{kid_id}/boss/summon", json={"region_id": 2})
    assert r.status_code == 400
    assert "解鎖" in r.get_json()["error"]


def test_boss_first_kill_awards_legendary_and_unlocks(test_db, battle_kid):
    kid_id = _kid_id(battle_kid)
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    _clear(db, kid_id)
    bd = {"region_id": 1, "is_boss": True}
    b._award_boss_rewards(db, kid_id, bd)
    db.commit()
    inv = db.execute(
        "SELECT quantity FROM inventory WHERE kid_id=? AND item_type='dragon_scale'",
        (kid_id,),
    ).fetchone()
    assert inv and inv["quantity"] >= 1, "首殺應該有 legendary 掉落"
    prog = db.execute(
        "SELECT first_kill FROM boss_progress WHERE kid_id=? AND region_id=1", (kid_id,)
    ).fetchone()
    assert prog and prog["first_kill"] == 1, "首殺 flag 應該 set"
    db.close()


def test_boss_weekly_cooldown_blocks_resummon(client, test_db, battle_kid):
    kid_id = _kid_id(battle_kid)
    db = sqlite3.connect(test_db)
    _clear(db, kid_id)
    _give_gem(db, kid_id)
    db.execute(
        "INSERT INTO boss_progress (kid_id, region_id, first_kill, last_win_at) VALUES (?,1,1,?)",
        (kid_id, datetime.now().isoformat()),
    )
    db.commit()
    db.close()
    r = client.post(f"/api/kids/{kid_id}/boss/summon", json={"region_id": 1})
    assert r.status_code == 400
    assert "本週" in r.get_json()["error"]


def test_boss_cooldown_expires_after_week(client, test_db, battle_kid):
    kid_id = _kid_id(battle_kid)
    db = sqlite3.connect(test_db)
    _clear(db, kid_id)
    _give_gem(db, kid_id)
    old_win = (datetime.now() - timedelta(days=8)).isoformat()
    db.execute(
        "INSERT INTO boss_progress (kid_id, region_id, first_kill, last_win_at) VALUES (?,1,1,?)",
        (kid_id, old_win),
    )
    db.commit()
    db.close()
    r = client.post(f"/api/kids/{kid_id}/boss/summon", json={"region_id": 1})
    assert r.status_code == 201, f"過咗一週應該可以再召喚, 得到 {r.get_data(as_text=True)}"


def test_boss_battle_action_works(client, test_db, battle_kid):
    """召喚 Boss 後應該可以攻擊/用技能 (唔會 no running battle)."""
    kid_id = _kid_id(battle_kid)
    db = sqlite3.connect(test_db)
    _clear(db, kid_id)
    _give_gem(db, kid_id)
    db.close()
    r = client.post(f"/api/kids/{kid_id}/boss/summon", json={"region_id": 1})
    assert r.status_code == 201, r.get_data(as_text=True)
    r2 = client.post(
        f"/api/kids/{kid_id}/expedition/battle-action",
        json={"action": "attack", "target_idx": 0},
    )
    assert r2.status_code == 200, f"攻擊 Boss 應該成功, 得到 {r2.get_data(as_text=True)}"
    d = r2.get_json()
    assert "error" not in d, f"唔應該有 error: {d}"
