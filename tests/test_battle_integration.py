"""Battle system integration tests — verify the new functions are actually WIRED into the flow.

These MUST fail before the wiring is done (RED), then pass after (GREEN).
"""
import sqlite3
from datetime import date

import backend_v2 as b


def test_battle_start_uses_tier_monster_stats(battle_client, battle_kid):
    """battle_start 應該用 calc_monster_stats(tier) 而唔係 DB 死數值."""
    r = battle_client.post(
        f"/api/kids/{battle_kid['id']}/expedition/battle-start", json={"region_id": 1}
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    d = r.get_json()
    m = d["monsters"][0]
    assert m["atk"] == 7, f"怪物 ATK 應該 7 (tier 公式), 得到 {m['atk']}"
    assert 35 <= m["hp"] <= 45, f"怪物 HP 應該 ~40, 得到 {m['hp']}"


def test_award_rewards_uses_tier_exp(test_db, battle_kid):
    """_award_battle_rewards 應該用 exp_reward_for_tier(tier)，唔係 random*monster_id."""
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    before = db.execute("SELECT experience FROM kids WHERE id=?", (kid_id,)).fetchone()[0]
    bd = {"gold_reward": 20, "mat_reward": {}, "region_id": 1, "monster_id": 1}
    b._award_battle_rewards(db, kid_id, bd, monsters=[{"id": 0}])
    db.commit()
    after = db.execute("SELECT experience FROM kids WHERE id=?", (kid_id,)).fetchone()[0]
    db.close()
    assert after - before == b.exp_reward_for_tier(1), (
        f"EXP 增加應該 {b.exp_reward_for_tier(1)}, 得到 {after - before}"
    )


def test_award_rewards_calls_roll_drop(test_db, battle_kid, monkeypatch):
    """_award_battle_rewards 應該呼叫 roll_drop（掉落系統接線）."""
    calls = []
    monkeypatch.setattr(b, "roll_drop", lambda tier=1, pity_count=0: calls.append(tier) or "epic")
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    bd = {"gold_reward": 20, "mat_reward": {}, "region_id": 1, "monster_id": 1}
    b._award_battle_rewards(db, battle_kid["id"], bd, monsters=[{"id": 0}])
    db.commit()
    db.close()
    assert calls, "roll_drop 應該被 _award_battle_rewards 呼叫"


def test_ability_atk_migrated_into_str(test_db, battle_kid):
    """ability_atk 應該合併入 ability_str，然後欄位被移除."""
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    db.execute("ALTER TABLE kids ADD COLUMN ability_atk INTEGER DEFAULT 0")
    db.execute("UPDATE kids SET ability_atk = 10 WHERE id = ?", (kid_id,))
    db.commit()
    before_str = db.execute("SELECT ability_str FROM kids WHERE id=?", (kid_id,)).fetchone()[0]

    b.migrate_ability_atk(db)
    db.commit()

    after_str = db.execute("SELECT ability_str FROM kids WHERE id=?", (kid_id,)).fetchone()[0]
    assert after_str == before_str + 10, f"臂力應該合併入 str ({before_str}+10), 得到 {after_str}"

    cols = [r[1] for r in db.execute("PRAGMA table_info(kids)").fetchall()]
    assert "ability_atk" not in cols, "ability_atk 欄位應該已被 drop"
    db.close()


def _ref_kid():
    return {
        "ability_str": 20,
        "ability_int": 20,
        "ability_spd": 0,
        "ability_crt": 0,
        "ability_brv": 0,
        "level": 20,
    }


def test_damage_skills_stronger_than_basic_attack(test_db):
    """每個單體 damage 技能嘅傷害應該 > 普攻."""
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    b.rebalance_skills(db)
    db.commit()

    basic = b.calc_battle_stats(_ref_kid())["atk"]  # 5 + 20*1.5 = 35
    bd = {"player_str": 20, "player_int": 20}
    rows = db.execute(
        "SELECT name, base_value, per_level, attr_scale FROM skill_defs "
        "WHERE effect_type='damage' AND target='enemy'"
    ).fetchall()
    db.close()

    assert len(rows) >= 4, "應該有至少 4 個單體傷害技能"
    for r in rows:
        dmg = b._calc_skill_damage({}, r["base_value"], r["per_level"], 1, r["attr_scale"], bd)
        assert dmg > basic, f"{r['name']} 傷害 {dmg} 應該 > 普攻 {basic}"


def test_region_once_per_day_blocks_second_battle(battle_client, test_db, battle_kid):
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.execute("DELETE FROM daily_battles WHERE kid_id=?", (kid_id,))
    db.execute(
        "INSERT INTO daily_battles (kid_id, region_id, battle_date) VALUES (?,1,?)",
        (kid_id, date.today().isoformat()),
    )
    db.commit()
    db.close()
    r = battle_client.post(f"/api/kids/{kid_id}/expedition/battle-start", json={"region_id": 1})
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "今日" in r.get_json()["error"]


def test_region_once_per_day_allows_different_region(battle_client, test_db, battle_kid):
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.execute("DELETE FROM daily_battles WHERE kid_id=?", (kid_id,))
    db.execute(
        "INSERT INTO daily_battles (kid_id, region_id, battle_date) VALUES (?,1,?)",
        (kid_id, date.today().isoformat()),
    )
    db.commit()
    db.close()
    r = battle_client.post(f"/api/kids/{kid_id}/expedition/battle-start", json={"region_id": 2})
    assert r.status_code == 201, r.get_data(as_text=True)


def test_win_records_daily_battle(test_db, battle_kid):
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    db.execute("DELETE FROM daily_battles WHERE kid_id=?", (kid_id,))
    db.commit()
    b._record_daily_battle(db, kid_id, {"region_id": 1, "is_boss": False})
    db.commit()
    row = db.execute(
        "SELECT * FROM daily_battles WHERE kid_id=? AND region_id=1 AND battle_date=?",
        (kid_id, date.today().isoformat()),
    ).fetchone()
    assert row is not None, "打贏應該記錄今日戰鬥"
    db.close()


def test_boss_does_not_record_daily_battle(test_db, battle_kid):
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    db.execute("DELETE FROM daily_battles WHERE kid_id=?", (kid_id,))
    db.commit()
    b._record_daily_battle(db, kid_id, {"region_id": 1, "is_boss": True})
    db.commit()
    row = db.execute("SELECT * FROM daily_battles WHERE kid_id=?", (kid_id,)).fetchone()
    assert row is None, "Boss 戰鬥唔應該記錄每日"
    db.close()


def test_region_requires_level(battle_client, test_db, battle_kid):
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.execute("UPDATE kids SET level=1 WHERE id=?", (kid_id,))
    db.execute("DELETE FROM daily_battles WHERE kid_id=?", (kid_id,))
    db.commit()
    db.close()
    r = battle_client.post(f"/api/kids/{kid_id}/expedition/battle-start", json={"region_id": 3})
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "Lv" in r.get_json()["error"]


def test_pity_increments_and_resets(test_db, battle_kid):
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    db.execute("DELETE FROM drop_pity WHERE kid_id=?", (kid_id,))
    db.commit()
    b.update_pity(db, kid_id, "common")
    b.update_pity(db, kid_id, "rare")
    db.commit()
    assert b.get_pity_count(db, kid_id) == 2
    b.update_pity(db, kid_id, "epic")
    db.commit()
    assert b.get_pity_count(db, kid_id) == 0, "epic 應該重置 pity"
    db.close()


def test_boss_repeat_win_awards_epic(test_db, battle_kid):
    kid_id = battle_kid["id"]
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    db.execute("DELETE FROM boss_progress WHERE kid_id=? AND region_id=1", (kid_id,))
    db.execute("DELETE FROM inventory WHERE kid_id=? AND item_type='gem'", (kid_id,))
    db.execute(
        "INSERT INTO boss_progress (kid_id, region_id, first_kill) VALUES (?,1,1)", (kid_id,)
    )
    db.commit()
    b._award_boss_rewards(db, kid_id, {"region_id": 1, "is_boss": True})
    db.commit()
    inv = db.execute(
        "SELECT quantity FROM inventory WHERE kid_id=? AND item_type='gem'", (kid_id,)
    ).fetchone()
    assert inv and inv["quantity"] >= 1, "重戰應該保底 epic (gem)"
    db.close()
