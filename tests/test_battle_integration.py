"""Battle system integration tests — verify the new functions are actually WIRED into the flow.

These MUST fail before the wiring is done (RED), then pass after (GREEN).
"""
import sys, os, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backend_v2 as b


def test_battle_start_uses_tier_monster_stats(client):
    """battle_start 應該用 calc_monster_stats(tier) 而唔係 DB 死數值."""
    r = client.post('/api/kids/4/expedition/battle-start', json={'region_id': 1})
    assert r.status_code == 201, r.get_data(as_text=True)
    d = r.get_json()
    m = d['monsters'][0]
    # tier 1 → atk = 4 + 1*3 = 7（舊 DB 死數值係 5）
    assert m['atk'] == 7, f"怪物 ATK 應該 7 (tier 公式), 得到 {m['atk']}"
    # hp = 20 + 1*20 = 40（±5 variance）
    assert 35 <= m['hp'] <= 45, f"怪物 HP 應該 ~40, 得到 {m['hp']}"


def test_award_rewards_uses_tier_exp(test_db):
    """_award_battle_rewards 應該用 exp_reward_for_tier(tier)，唔係 random*monster_id."""
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    before = db.execute('SELECT experience FROM kids WHERE id=4').fetchone()[0]
    bd = {'gold_reward': 20, 'mat_reward': {}, 'region_id': 1, 'monster_id': 1}
    b._award_battle_rewards(db, 4, bd, monsters=[{'id': 0}])
    db.commit()
    after = db.execute('SELECT experience FROM kids WHERE id=4').fetchone()[0]
    db.close()
    # tier 1 → exp_reward_for_tier(1) = 15 + 10 = 25
    assert after - before == b.exp_reward_for_tier(1), \
        f"EXP 增加應該 {b.exp_reward_for_tier(1)}, 得到 {after - before}"


def test_award_rewards_calls_roll_drop(test_db, monkeypatch):
    """_award_battle_rewards 應該呼叫 roll_drop（掉落系統接線）."""
    calls = []
    monkeypatch.setattr(b, 'roll_drop', lambda tier=1, pity_count=0: calls.append(tier) or 'epic')
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    bd = {'gold_reward': 20, 'mat_reward': {}, 'region_id': 1, 'monster_id': 1}
    b._award_battle_rewards(db, 4, bd, monsters=[{'id': 0}])
    db.commit()
    db.close()
    assert calls, "roll_drop 應該被 _award_battle_rewards 呼叫"


def test_ability_atk_migrated_into_str(test_db):
    """ability_atk 應該合併入 ability_str，然後欄位被移除."""
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    # 先模擬一個有臂力點數嘅小朋友
    db.execute("UPDATE kids SET ability_atk = 10 WHERE id = 4")
    db.commit()

    b.migrate_ability_atk(db)
    db.commit()

    # ability_str 應該 +10
    kid = db.execute("SELECT ability_str FROM kids WHERE id=4").fetchone()
    assert kid['ability_str'] >= 10, f"臂力應該合併入 str, 得到 str={kid['ability_str']}"

    # ability_atk 欄位應該被移除
    cols = [r[1] for r in db.execute("PRAGMA table_info(kids)").fetchall()]
    assert 'ability_atk' not in cols, "ability_atk 欄位應該已被 drop"
    db.close()
