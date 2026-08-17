"""Battle system v2 formula tests — TDD (RED first).

These tests encode the target behavior from .hermes/plans/2026-08-16_211324-battle-system-v2.md
and MUST fail against the current (pre-refactor) backend_v2.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backend_v2 as b


def _kid(**over):
    """Build a kid dict with all ability columns defaulted to 0."""
    kid = {
        'ability_str': 0, 'ability_atk': 0, 'ability_int': 0,
        'ability_spd': 0, 'ability_crt': 0, 'ability_brv': 0,
        'level': 1,
    }
    kid.update(over)
    return kid


# ════════════════════════════════════════════════════════════════
# Phase 2 — 屬性 & 公式 v2
#   HP  = 20 + level*8
#   ATK = int(5 + str*1.5)          (臂力)
#   DEF = int(brv*0.6)              (勇氣)
#   CRT% = min(50, crt*2)           (創意)
#   DODGE% = min(40, spd*1.5)       (速度)
# ════════════════════════════════════════════════════════════════

def test_hp_depends_on_level_not_str():
    s = b.calc_battle_stats(_kid(level=10, ability_str=0))
    assert s['hp'] == 20 + 10 * 8
    # 臂力 50 都唔應該影響 HP
    s2 = b.calc_battle_stats(_kid(level=10, ability_str=50))
    assert s2['hp'] == 20 + 10 * 8


def test_atk_from_str():
    s = b.calc_battle_stats(_kid(ability_str=10, level=1))
    assert s['atk'] == int(5 + 10 * 1.5)


def test_def_from_brv():
    s = b.calc_battle_stats(_kid(ability_brv=10))
    assert s['def'] == int(10 * 0.6)


def test_crit_rate_from_crt_capped_at_50():
    s = b.calc_battle_stats(_kid(ability_crt=10))
    assert s['crt'] == 20
    s2 = b.calc_battle_stats(_kid(ability_crt=100))
    assert s2['crt'] == 50  # capped


def test_dodge_from_spd_capped_at_40():
    s = b.calc_battle_stats(_kid(ability_spd=10))
    assert s.get('dodge') == 15
    s2 = b.calc_battle_stats(_kid(ability_spd=100))
    assert s2.get('dodge') == 40  # capped


# ════════════════════════════════════════════════════════════════
# Phase 1 — 接線 bug 修正
#   INT 技能 scale 用「知識 int」，唔係「勇氣 brv」
#   治療用真 int（唔係硬編碼 +5）
# ════════════════════════════════════════════════════════════════

def test_int_skill_scales_from_int_not_brv():
    bd = {'player_int': 20, 'player_brv': 999, 'player_atk': 999}
    dmg = b._calc_skill_damage({}, base=10, per_lv=0, bldg_level=1,
                               attr_scale='int', bd=bd)
    # 期望：base 10 + int*1.0 (20) + rand(0,3) = 30..33
    # 舊 bug：用 brv//2 = 499 → ~509
    assert 30 <= dmg <= 33, f"int scale 應該 30..33, 得到 {dmg}"


def test_heal_uses_int_not_hardcoded():
    heal = b._calc_skill_heal({}, base=10, per_lv=0, bldg_level=1,
                              attr_scale='int', player_int=20)
    # 期望：base 10 + int*0.8 (16) + rand(0,2) = 26..28
    # 舊 bug：硬編碼 +5 → ~15..17
    assert 26 <= heal <= 28, f"heal 應該 26..28, 得到 {heal}"


# ════════════════════════════════════════════════════════════════
# Phase 7 — EXP 曲線 (cap 1000)
#   exp_for_next_level(level) = level * 25
# ════════════════════════════════════════════════════════════════

def test_exp_for_next_level():
    assert b.exp_for_next_level(1) == 25
    assert b.exp_for_next_level(10) == 250
    assert b.exp_for_next_level(1000) == 25000


def test_calc_level_reaches_1000():
    # 總計 EXP 到 Lv1000 = 25 * 1000*999/2 = 12,487,500
    lvl, _ = b.calc_level(12_487_500)
    assert lvl == 1000


def test_exp_reward_scales_with_tier():
    # exp_reward = 15 + tier*10
    assert b.exp_reward_for_tier(1) == 25
    assert b.exp_reward_for_tier(3) == 45
    assert b.exp_reward_for_tier(10) == 115


# ════════════════════════════════════════════════════════════════
# Phase 4 — 怪物 tier scaling
#   HP = 20 + tier*20, ATK = 4 + tier*3, DEF = tier//2, SPD = tier
# ════════════════════════════════════════════════════════════════

def test_monster_tier_stats():
    m = b.calc_monster_stats(3)
    assert m['hp'] == 20 + 3 * 20
    assert m['atk'] == 4 + 3 * 3
    assert m['def'] == 3 // 2
    assert m['spd'] == 3


def test_monster_tier_grows():
    m1 = b.calc_monster_stats(1)
    m10 = b.calc_monster_stats(10)
    assert m10['hp'] > m1['hp']
    assert m10['atk'] > m1['atk']
    assert m10['def'] > m1['def']


# ════════════════════════════════════════════════════════════════
# Phase 6 — Boss 數值 (HP×3, ATK×1.5, DEF×1.5)
# ════════════════════════════════════════════════════════════════

def test_boss_stats_multipliers():
    base = {'hp': 100, 'atk': 10, 'def': 5}
    boss = b.calc_boss_stats(base)
    assert boss['hp'] == 300
    assert boss['atk'] == 15
    assert boss['def'] == 7  # int(5*1.5)


# ════════════════════════════════════════════════════════════════════
# Phase 2 — 先手 (spd) + 回避 (dodge)
#   先手: player_spd > monster_spd → 怪物唔反擊
#   回避: roll player_dodge% → 成功就零傷害
# ════════════════════════════════════════════════════════════════════

def test_first_strike_prevents_counter():
    bd = {'player_spd': 10, 'player_dodge': 0}
    attacker = {'name': '野狼', 'spd': 5, 'atk': 10}
    log, dmg = b._monster_counterattack(bd, attacker, player_def=0)
    assert dmg == 0
    assert '先手' in log


def test_dodge_avoids_damage(monkeypatch):
    # 強制 dodge roll 成功 (randint→1 <= player_dodge)
    monkeypatch.setattr(b.random, 'randint', lambda a, c: 1)
    bd = {'player_spd': 1, 'player_dodge': 50}
    attacker = {'name': '野狼', 'spd': 5, 'atk': 10}
    log, dmg = b._monster_counterattack(bd, attacker, player_def=0)
    assert dmg == 0
    assert '回避' in log


def test_counter_deals_damage_when_slower_no_dodge():
    bd = {'player_spd': 1, 'player_dodge': 0}
    attacker = {'name': '野狼', 'spd': 5, 'atk': 10}
    log, dmg = b._monster_counterattack(bd, attacker, player_def=0)
    assert dmg > 0
    assert '反擊' in log


# ════════════════════════════════════════════════════════════════════
# 爆擊倍率 scaling — CRTDMG = 1.5 + crt*0.02
# ════════════════════════════════════════════════════════════════════

def test_crit_dmg_multiplier_from_crt():
    s = b.calc_battle_stats(_kid(ability_crt=10))
    assert s.get('crit_dmg') == 1.5 + 10 * 0.02
    s0 = b.calc_battle_stats(_kid(ability_crt=0))
    assert s0.get('crit_dmg') == 1.5


# ════════════════════════════════════════════════════════════════════
# 里程碑獎勵 — check_milestones(old, new)
# ════════════════════════════════════════════════════════════════════

def test_milestones_crossed():
    assert b.check_milestones(9, 11) == [10]
    assert b.check_milestones(5, 30) == [10, 25]
    assert b.check_milestones(50, 60) == []  # 冇跨過里程碑
    assert b.check_milestones(24, 25) == [25]  # 剛好到 25
