"""Skills must change numbers, not only the battle log.

RNG is monkeypatched. Empty SQLite and synthetic accounts only.
Every case below is red on the current base: the battle endpoint does not
do what the skill text says.
"""
from __future__ import annotations

import sqlite3
import threading

import pytest

import backend_v2 as b
from tests.battle_truth import (
    act,
    login_and_start,
    monster_hp,
    place,
    prepare_kid,
    running_battle,
    save_battle,
    skill_by_name,
)
from tests.factories import connect_db, get_kid_points, response_text
from tests.phase1_helpers import login_kid

# Region 1 weakness locked by TC-API-SKILL-SCOUT. Builder copies this onto the monster.
REGION_WEAKNESS = {1: "火", 2: "冰", 3: "雷"}
# 金幣袋 adds this much gold on top of the normal win payout.
COIN_BAG_BONUS = 20


def _open(client, family, test_db, monkeypatch, specs, monsters=1, points=200):
    kid_id = family.kid_a.id
    prepare_kid(test_db, kid_id, points=points)
    for spec in specs:
        place(
            test_db,
            kid_id,
            spec["key"],
            level=spec.get("level", 1),
            stored=spec.get("stored", 0),
            cell_x=spec.get("x", 0),
            cell_y=spec.get("y", 0),
        )
    response = login_and_start(
        client, family, kid_id, monkeypatch, monsters=monsters
    )
    assert response.status_code == 201, response_text(response)
    return response.get_json()


def _require(battle, name, absent=()):
    names = [row.get("name") for row in battle.get("skills") or []]
    found = skill_by_name(battle, name)
    assert found, f"battle skills {names} do not include {name}"
    for old in absent:
        assert old not in names, f"{old} is still listed: {names}"
    return found


def _tune(test_db, kid_id, **flags):
    exp_id, data = running_battle(test_db, kid_id)
    hp = flags.get("hp")
    spd = flags.get("spd")
    for monster in data["monsters"]:
        if hp is not None:
            monster["hp"] = hp
            monster["max_hp"] = max(monster.get("max_hp") or 0, hp)
        if flags.get("max_hp") is not None:
            monster["max_hp"] = flags["max_hp"]
        if spd is not None:
            monster["spd"] = spd
    if "player_def" in flags:
        data["player_def"] = flags["player_def"]
    if "player_hp" in flags:
        data["player_hp"] = flags["player_hp"]
    if "player_mp" in flags:
        data["player_mp"] = flags["player_mp"]
    if "player_dodge" in flags:
        data["player_dodge"] = flags["player_dodge"]
    save_battle(test_db, exp_id, data)
    return data


def _use(client, kid_id, skill):
    return act(client, kid_id, "skill", skill_id=skill["id"])


def _hp_loss(before_hp, body):
    return before_hp - body["player_hp"]


def _set_level_required(test_db, name, level_required):
    """Test DB only. Lets a seeded skill be cast at a lower building level."""
    db = connect_db(test_db)
    cur = db.execute(
        "UPDATE skill_defs SET level_required=? WHERE name=?",
        (level_required, name),
    )
    db.commit()
    changed = cur.rowcount
    db.close()
    assert changed == 1, name


def _ok(response):
    assert response.status_code == 200, response_text(response)
    return response.get_json()


def _physical_damage(str_v, monster_def):
    """Basic attack with variance 0. atk = int(5 + str * 1.5)."""
    return max(1, int(5 + str_v * 1.5) - monster_def)


@pytest.mark.case_id("TC-API-SKILL-DOUBLE")
def test_combo_hits_twice(client, family, test_db, monkeypatch):
    """連擊要打兩下。HP 下降等於兩次單體公式（randint 固定 0），唔好只得一下。"""
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "gym", "level": 4}],
    )
    skill = _require(battle, "連擊")
    _tune(test_db, family.kid_a.id, hp=5000, spd=50)
    before = 5000
    done = _use(client, family.kid_a.id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    one = max(1, int(16 + 4 * 4 + body.get("player_str", 0)) + 0)
    dealt = before - monster_hp(body)
    assert body["monsters"][0]["hp"] > 0, body["monsters"]
    assert dealt == 2 * one, f"dealt {dealt}, one hit {one}, want {2 * one}"


def _magic_hit(skill, bldg_level, player_int):
    """Magic skill damage, variance 0. int is added 1:1; matk = int(5 + int×1.5)."""
    return max(1, int(skill["base_value"] + skill["per_level"] * bldg_level + player_int))


def _counter_from_atk(monster_atk, player_def):
    """Monster counter, variance 0: max(0, atk − player_def)."""
    return max(0, int(monster_atk) - int(player_def))


@pytest.mark.case_id("TC-API-SKILL-FREEZE")
def test_freeze_magic_hit_weakens_attack_for_two_turns(
    client, family, test_db, monkeypatch
):
    """冰凍係魔法攻擊，之後兩回合怪攻 ×0.7，第三回合恢復。

    預期跟開戰回報，唔好寫死「防 0／傷害 56」。
    魔法傷害 > 0，等於技能公式加開戰 `player_int`（方差 0）。
    若 JSON 有 `player_matk`，佢要等於 `int(5 + player_int×1.5)`，同一知識。
    對照普攻量到嘅反擊係基線。削弱先 `int(怪攻×0.7)` 再代入
    `max(0, 攻−player_def)`。施放嗰下唔計入兩回合，反擊仍係基線。
    """
    kid_id = family.kid_a.id
    library_level = 4
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "library", "level": library_level}],
    )
    skill = _require(battle, "冰凍")
    monster_atk = battle["monsters"][0]["atk"]
    player_def = battle["player_def"]
    player_int = battle.get("player_int", 0) or 0
    derived_matk = int(5 + player_int * 1.5)
    if "player_matk" in battle:
        assert battle["player_matk"] == derived_matk, battle.get("player_matk")
    formula_normal = _counter_from_atk(monster_atk, player_def)
    formula_reduced = _counter_from_atk(int(monster_atk * 0.7), player_def)
    magic = _magic_hit(skill, library_level, player_int)
    assert formula_reduced < formula_normal, (monster_atk, player_def, formula_reduced, formula_normal)
    assert magic > 0

    _tune(test_db, kid_id, hp=8000, spd=50)
    control = _ok(act(client, kid_id, "attack"))
    baseline = _hp_loss(battle["player_hp"], control)
    assert baseline == formula_normal, (baseline, formula_normal, battle.get("player_def"))
    assert baseline > 0, control
    enemy_hp = monster_hp(control)

    cast = _ok(_use(client, kid_id, skill))
    dealt = enemy_hp - monster_hp(cast)
    assert dealt > 0, cast["monsters"]
    assert dealt == magic, (dealt, magic, player_int, derived_matk)
    assert _hp_loss(control["player_hp"], cast) == baseline, cast

    hp = cast["player_hp"]
    for turn in (1, 2):
        step = _ok(act(client, kid_id, "attack"))
        loss = hp - step["player_hp"]
        assert loss == formula_reduced, (turn, loss, formula_reduced, baseline)
        hp = step["player_hp"]
    expired = _ok(act(client, kid_id, "attack"))
    assert hp - expired["player_hp"] == baseline, expired


@pytest.mark.case_id("TC-API-SKILL-EXECUTE")
def test_execute_hits_harder_when_enemy_hp_is_low(client, family, test_db, monkeypatch):
    """必殺對低血（唔超過 25% 上限）嘅傷害至少係滿血同一擊嘅 1.5 倍。"""
    kid_id = family.kid_a.id
    specs = [{"key": "guild", "x": 6}, {"key": "arena", "level": 5}]

    def _strike(current_hp):
        battle = _open(client, family, test_db, monkeypatch, specs)
        skill = _require(battle, "必殺")
        _tune(test_db, kid_id, hp=current_hp, max_hp=10000, spd=50)
        done = _use(client, kid_id, skill)
        assert done.status_code == 200, response_text(done)
        body = done.get_json()
        return current_hp - monster_hp(body)

    high = _strike(10000)
    low = _strike(1000)
    assert high > 0 and low > 0, (high, low)
    assert low > high, (high, low)
    assert low >= int(high * 1.5), (high, low)


@pytest.mark.case_id("TC-API-SKILL-REPAIR")
def test_repair_restores_mp_not_hp(client, family, test_db, monkeypatch):
    """修復回復 MP，唔好回復 HP。防禦拉到 999，所以反擊係 0，HP 變化只可以來自技能。"""
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "workshop", "level": 2}],
    )
    skill = _require(battle, "修復")
    hp_before = battle["player_max_hp"] - 40
    mp_before = battle["player_max_mp"] - 20
    _tune(
        test_db,
        kid_id,
        hp=5000,
        spd=50,
        player_def=999,
        player_hp=hp_before,
        player_mp=mp_before,
    )
    done = _use(client, kid_id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    restored = body["player_mp"] - (mp_before - skill["mp_cost"])
    assert body["player_hp"] == hp_before, body
    assert restored >= 1, body


@pytest.mark.case_id("TC-API-SKILL-FORTIFY")
def test_fortify_lowers_damage_taken(client, family, test_db, monkeypatch):
    """強化之後，下一擊受到嘅傷害要少過冇開強化嘅對照反擊。"""
    kid_id = family.kid_a.id
    specs = [{"key": "guild", "x": 6}, {"key": "workshop", "level": 4}]

    control = _open(client, family, test_db, monkeypatch, specs)
    _tune(test_db, kid_id, hp=5000, spd=50)
    control_hp = control["player_hp"]
    punched = act(client, kid_id, "attack")
    assert punched.status_code == 200, response_text(punched)
    control_loss = _hp_loss(control_hp, punched.get_json())
    assert control_loss > 0, punched.get_json()

    buffed = _open(client, family, test_db, monkeypatch, specs)
    skill = _require(buffed, "強化")
    _tune(test_db, kid_id, hp=5000, spd=50)
    cast = _use(client, kid_id, skill)
    assert cast.status_code == 200, response_text(cast)
    mid_hp = cast.get_json()["player_hp"]
    follow = act(client, kid_id, "attack")
    assert follow.status_code == 200, response_text(follow)
    buff_loss = _hp_loss(mid_hp, follow.get_json())
    assert buff_loss < control_loss, (buff_loss, control_loss)


@pytest.mark.case_id("TC-API-SKILL-SCOUT")
def test_scout_reveals_weakness_and_deals_no_damage(client, family, test_db, monkeypatch):
    """偵察揭示區 1 弱點「火」，而且怪物 HP 唔變。"""
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "level": 2, "x": 6}],
    )
    skill = _require(battle, "偵察")
    _tune(test_db, kid_id, hp=500, spd=50)
    done = _use(client, kid_id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    assert monster_hp(body) == 500, body["monsters"]
    assert body["monsters"][0].get("weakness") == REGION_WEAKNESS[1], body["monsters"][0]


CHARGE_TEXT = "下次攻擊 2 倍"


@pytest.mark.case_id("TC-API-SKILL-CHARGE")
def test_charge_doubles_next_attack_and_says_so(client, family, test_db, monkeypatch):
    """蓄力下一擊係同一場對照普攻嘅 2 倍。說明要係「下次攻擊 2 倍」。

    對照傷害跟開戰 `player_atk` 同怪物防，唔好寫死 5 同 10。
    施放嗰下亦要造成傷害，由 TC-API-SKILL-ALL-DAMAGE 量。
    """
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "gym", "level": 1}],
    )
    skill = _require(battle, "蓄力")
    monster_def = battle["monsters"][0]["def"]
    from_atk = max(1, battle["player_atk"] - monster_def)
    _tune(test_db, kid_id, hp=5000, spd=50)

    control = _ok(act(client, kid_id, "attack"))
    normal = 5000 - monster_hp(control)
    assert normal == from_atk, (normal, from_atk, battle.get("player_atk"))
    assert normal > 0, control
    enemy_hp = monster_hp(control)

    cast = _ok(_use(client, kid_id, skill))
    enemy_hp = monster_hp(cast)
    follow = _ok(act(client, kid_id, "attack"))
    dealt = enemy_hp - monster_hp(follow)
    assert dealt == normal * 2, f"dealt {dealt}, normal {normal}, want {normal * 2}"

    listed = client.get(f"/api/kids/{kid_id}/skills")
    assert listed.status_code == 200, response_text(listed)
    listed_skill = next(
        (row for row in listed.get_json() if row.get("name") == "蓄力"),
        None,
    )
    action_skill = skill_by_name(cast, "蓄力") or {}
    log_text = " ".join((cast.get("turns") or [{}])[-1].get("log") or [])
    exposed = {
        "battle-start": skill.get("description"),
        "GET /skills": None if listed_skill is None else listed_skill.get("description"),
        "battle-action": action_skill.get("description"),
    }
    bad = {where: text for where, text in exposed.items() if text != CHARGE_TEXT}
    if CHARGE_TEXT not in log_text:
        bad["battle log"] = log_text
    assert not bad, bad


@pytest.mark.case_id("TC-API-SKILL-SHIELD")
def test_shield_bash_hits_and_halves_next_damage(client, family, test_db, monkeypatch):
    """挑釁改名盾擊：物理傷害，而且呢一下受到嘅傷害係對照反擊嘅一半（整數除法）。"""
    kid_id = family.kid_a.id
    specs = [{"key": "guild", "x": 6}, {"key": "arena", "level": 4}]

    control = _open(client, family, test_db, monkeypatch, specs)
    _tune(test_db, kid_id, hp=5000, spd=50)
    control_hp = control["player_hp"]
    punched = act(client, kid_id, "attack")
    assert punched.status_code == 200, response_text(punched)
    control_loss = _hp_loss(control_hp, punched.get_json())
    assert control_loss > 1, punched.get_json()

    battle = _open(client, family, test_db, monkeypatch, specs)
    skill = _require(battle, "盾擊", absent=("挑釁",))
    _tune(test_db, kid_id, hp=5000, spd=50)
    before_hp = battle["player_hp"]
    done = _use(client, kid_id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    assert 5000 - monster_hp(body) > 0, body["monsters"]
    assert _hp_loss(before_hp, body) == control_loss // 2, (
        _hp_loss(before_hp, body),
        control_loss,
    )


@pytest.mark.case_id("TC-API-SKILL-GALE")
def test_gale_slash_hits_and_prevents_counter(client, family, test_db, monkeypatch):
    """迴避改名疾風斬：物理傷害，而且呢一回合冇有反擊（玩家 HP 唔跌）。"""
    kid_id = family.kid_a.id
    specs = [{"key": "guild", "level": 4, "x": 6}]

    control = _open(client, family, test_db, monkeypatch, specs)
    _tune(test_db, kid_id, hp=5000, spd=50)
    control_hp = control["player_hp"]
    punched = act(client, kid_id, "attack")
    assert punched.status_code == 200, response_text(punched)
    assert _hp_loss(control_hp, punched.get_json()) > 0, punched.get_json()

    battle = _open(client, family, test_db, monkeypatch, specs)
    skill = _require(battle, "疾風斬", absent=("迴避",))
    _tune(test_db, kid_id, hp=5000, spd=50)
    before_hp = battle["player_hp"]
    done = _use(client, kid_id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    assert 5000 - monster_hp(body) > 0, body["monsters"]
    assert body["player_hp"] == before_hp, body


def _meal_band(max_hp):
    """About 8% of max HP, with room for rounding and a small level bump."""
    low = max(1, int(max_hp * 0.06))
    high = int(max_hp * 0.14) + 1
    return low, high


@pytest.mark.case_id("TC-API-SKILL-KNOWLEDGE")
def test_library_knowledge_power_boosts_magic_for_three_turns(
    client, family, test_db, monkeypatch
):
    """圖書館「知識的力量」：施放之後三回合知識 +3×建築等級，第 4 下返原值。

    施放嗰下唔計入三回合。施放本身亦要打中（見 TC-API-SKILL-ALL-DAMAGE）。
    魔法傷害用火球量：
    而家公式把 player_int 一比一加落去，所以加成期間每下比對照多正好 3×等級
    （方差 0）。Lv1 多 3，Lv5 多 15。戰鬥 JSON 嘅 player_int 同步升降。
    測試庫先把火球 level_required 改成 1，Lv1 圖書館先能量到魔法傷害。
    """
    kid_id = family.kid_a.id
    seen = {}
    for level in (1, 5):
        _set_level_required(test_db, "火球", 1)
        battle = _open(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "x": 6}, {"key": "library", "level": level}],
        )
        power = _require(battle, "知識的力量")
        bolt = skill_by_name(battle, "火球")
        assert bolt, battle.get("skills")
        _tune(test_db, kid_id, hp=8000, spd=50, player_def=999)
        base_int = battle["player_int"]
        bonus = 3 * level

        opened = _ok(_use(client, kid_id, bolt))
        plain = 8000 - monster_hp(opened)
        assert plain > 0, opened
        enemy_hp = monster_hp(opened)

        cast = _ok(_use(client, kid_id, power))
        enemy_hp = monster_hp(cast)

        for turn in (1, 2, 3):
            hit = _ok(_use(client, kid_id, bolt))
            dealt = enemy_hp - monster_hp(hit)
            assert dealt == plain + bonus, (level, turn, dealt, plain, bonus)
            assert hit["player_int"] == base_int + bonus, (level, turn, hit["player_int"])
            enemy_hp = monster_hp(hit)

        expired = _ok(_use(client, kid_id, bolt))
        assert enemy_hp - monster_hp(expired) == plain, (level, expired)
        assert expired["player_int"] == base_int, (level, expired["player_int"])
        seen[level] = plain + bonus

    assert seen[5] - seen[1] != 0
    assert seen[1] > 0 and seen[5] > seen[1]


@pytest.mark.case_id("TC-API-SKILL-TRAINING")
def test_gym_training_result_boosts_physical_for_three_turns(
    client, family, test_db, monkeypatch
):
    """健身室「鍛鍊的成果」：施放之後三回合臂力 +3×等級，普攻上升，第 4 下返原值。

    普攻傷害係 max(1, int(5 + str×1.5) − 敵防)，方差 0。
    施放本身亦要打中（見 TC-API-SKILL-ALL-DAMAGE）。
    player_str 同 player_atk 喺三回合入面要係加成後嘅值。
    Lv1 臂力 +3，Lv5 臂力 +15。
    """
    kid_id = family.kid_a.id
    boosted_hits = {}
    for level in (1, 5):
        battle = _open(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "x": 6}, {"key": "gym", "level": level}],
        )
        skill = _require(battle, "鍛鍊的成果")
        monster_def = battle["monsters"][0]["def"]
        base_str = battle["player_str"]
        bonus = 3 * level
        _tune(test_db, kid_id, hp=8000, spd=50)
        plain = _physical_damage(base_str, monster_def)
        boosted = _physical_damage(base_str + bonus, monster_def)
        assert boosted > plain, (level, plain, boosted)

        control = _ok(act(client, kid_id, "attack"))
        assert 8000 - monster_hp(control) == plain, control
        enemy_hp = monster_hp(control)

        cast = _ok(_use(client, kid_id, skill))
        enemy_hp = monster_hp(cast)

        for turn in (1, 2, 3):
            hit = _ok(act(client, kid_id, "attack"))
            dealt = enemy_hp - monster_hp(hit)
            assert dealt == boosted, (level, turn, dealt, boosted)
            assert hit["player_str"] == base_str + bonus, (level, turn, hit.get("player_str"))
            assert hit["player_atk"] == int(5 + (base_str + bonus) * 1.5), hit.get("player_atk")
            enemy_hp = monster_hp(hit)

        expired = _ok(act(client, kid_id, "attack"))
        assert enemy_hp - monster_hp(expired) == plain, (level, expired)
        assert expired["player_str"] == base_str, expired.get("player_str")
        assert expired["player_atk"] == int(5 + base_str * 1.5), expired.get("player_atk")
        boosted_hits[level] = boosted

    assert boosted_hits[5] > boosted_hits[1]


@pytest.mark.case_id("TC-API-SKILL-MEAL")
def test_farm_meal_heals_over_three_turns(client, family, test_db, monkeypatch):
    """農場「營養餐」係三回合持續回血，大約最大 HP 嘅 8%，等級高唔少過等級低。

    施放當下 HP、MP 都唔好即時回復（MP 只可以扣技能消耗）。
    之後三個玩家回合每回合 HP 上升，第四回合停止。反擊被 999 防禦擋走。
    """
    kid_id = family.kid_a.id
    per_level = {}
    for level in (1, 5):
        battle = _open(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "x": 6}, {"key": "farm", "level": level, "x": 2}],
        )
        skill = _require(battle, "營養餐")
        max_hp = battle["player_max_hp"]
        hp_before = max(1, max_hp // 2)
        mp_before = max(0, battle["player_max_mp"] - 15)
        _tune(
            test_db,
            kid_id,
            hp=5000,
            spd=50,
            player_def=999,
            player_hp=hp_before,
            player_mp=mp_before,
        )
        cast = _ok(_use(client, kid_id, skill))
        assert cast["player_hp"] == hp_before, cast
        assert cast["player_mp"] == mp_before - int(skill.get("mp_cost") or 0), cast
        low, high = _meal_band(max_hp)
        hp = cast["player_hp"]
        mp = cast["player_mp"]
        ticks = []
        for turn in (1, 2, 3):
            step = _ok(act(client, kid_id, "attack"))
            gain = step["player_hp"] - hp
            assert low <= gain <= high, (level, turn, gain, low, high, max_hp)
            assert step["player_mp"] == mp, (level, turn, step["player_mp"], mp)
            ticks.append(gain)
            hp = step["player_hp"]
        stopped = _ok(act(client, kid_id, "attack"))
        assert stopped["player_hp"] == hp, (level, stopped["player_hp"], hp)
        assert stopped["player_mp"] == mp, stopped["player_mp"]
        per_level[level] = ticks

    for fast, slow in zip(per_level[5], per_level[1]):
        assert fast >= slow, (per_level[5], per_level[1])


def _clear_win(test_db, kid_id):
    db = connect_db(test_db)
    db.execute("DELETE FROM daily_battles WHERE kid_id=?", (kid_id,))
    db.execute(
        "UPDATE expeditions SET status='completed' WHERE kid_id=? AND status='running'",
        (kid_id,),
    )
    db.commit()
    db.close()


@pytest.mark.case_id("TC-API-SKILL-COIN")
def test_shop_coin_bag_adds_gold_only_when_the_battle_is_won(
    client, family, test_db, monkeypatch
):
    """商店金幣袋：打贏先至多 20 金幣。逃跑唔加。冇用技能嘅勝場係對照。"""
    kid_id = family.kid_a.id
    specs = [{"key": "guild", "x": 6}, {"key": "shop", "level": 1, "x": 2}]

    fled = _open(client, family, test_db, monkeypatch, specs, points=300)
    skill = _require(fled, "金幣袋")
    points_before_flee = get_kid_points(test_db, kid_id)
    cast = _use(client, kid_id, skill)
    assert cast.status_code == 200, response_text(cast)
    ran = act(client, kid_id, "flee")
    assert ran.status_code == 200, response_text(ran)
    assert ran.get_json().get("battle_result") == "fled", ran.get_json()
    assert get_kid_points(test_db, kid_id) == points_before_flee

    _clear_win(test_db, kid_id)
    plain = login_and_start(client, family, kid_id, monkeypatch)
    assert plain.status_code == 201, response_text(plain)
    _tune(test_db, kid_id, hp=1)
    before_plain = get_kid_points(test_db, kid_id)
    win_plain = act(client, kid_id, "attack")
    assert win_plain.status_code == 200, response_text(win_plain)
    assert win_plain.get_json().get("battle_result") == "won", win_plain.get_json()
    plain_delta = get_kid_points(test_db, kid_id) - before_plain

    _clear_win(test_db, kid_id)
    bag = login_and_start(client, family, kid_id, monkeypatch)
    assert bag.status_code == 201, response_text(bag)
    again = _require(bag.get_json(), "金幣袋")
    held = _use(client, kid_id, again)
    assert held.status_code == 200, response_text(held)
    _tune(test_db, kid_id, hp=1)
    before_bag = get_kid_points(test_db, kid_id)
    win_bag = act(client, kid_id, "attack")
    assert win_bag.status_code == 200, response_text(win_bag)
    assert win_bag.get_json().get("battle_result") == "won", win_bag.get_json()
    bag_delta = get_kid_points(test_db, kid_id) - before_bag
    assert plain_delta > 0, plain_delta
    assert bag_delta == plain_delta + COIN_BAG_BONUS, (bag_delta, plain_delta)


@pytest.mark.case_id("TC-API-SKILL-FLASH")
def test_lighthouse_flash_makes_the_next_two_monster_attacks_miss(
    client, family, test_db, monkeypatch
):
    """燈塔強光：魔法傷害。之後 2 次怪物攻擊打唔中，第三次先至再扣血。

    怪物攻擊喺每次玩家行動之後先至發生，所以用連續三個玩家行動量反擊。
    """
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "lighthouse", "level": 1}],
    )
    skill = _require(battle, "強光")
    _tune(test_db, kid_id, hp=8000, spd=50)
    cast = _use(client, kid_id, skill)
    assert cast.status_code == 200, response_text(cast)
    opened = cast.get_json()
    assert 8000 - monster_hp(opened) > 0, opened["monsters"]
    hp = opened["player_hp"]
    for turn in (1, 2):
        step = act(client, kid_id, "attack")
        assert step.status_code == 200, response_text(step)
        body = step.get_json()
        assert body.get("battle_result") == "fighting", body
        assert body["player_hp"] == hp, f"turn {turn} still hurt the player: {body['player_hp']}"
        hp = body["player_hp"]
    third = act(client, kid_id, "attack")
    assert third.status_code == 200, response_text(third)
    assert third.get_json()["player_hp"] < hp, third.get_json()


@pytest.mark.case_id("TC-API-SKILL-METEOR")
def test_observatory_meteor_hits_every_enemy(client, family, test_db, monkeypatch):
    """天文台流星雨要對每一隻敵人造成魔法傷害。"""
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "observatory", "level": 1}],
        monsters=3,
    )
    skill = _require(battle, "流星雨")
    assert len(battle["monsters"]) == 3, battle["monsters"]
    before = [monster["hp"] for monster in battle["monsters"]]
    done = _use(client, kid_id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    after = [monster["hp"] for monster in body["monsters"]]
    assert len(after) == 3, body["monsters"]
    drops = [old - new for old, new in zip(before, after)]
    assert all(drop > 0 for drop in drops), drops


@pytest.mark.case_id("TC-API-SKILL-GOLD")
def test_bank_gold_smash_costs_ten_and_deals_triple(client, family, test_db, monkeypatch):
    """銀行金錢砸：扣 10 金幣，傷害等於 3 倍普攻（方差 0）。金幣少過 10 就拒絕，金幣同 HP 都唔變。"""
    kid_id = family.kid_a.id
    db = connect_db(test_db)
    row = db.execute("SELECT id FROM building_defs WHERE name='銀行'").fetchone()
    db.close()
    assert row, "building_defs has no 銀行, so 金錢砸 cannot be learned"

    rich = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "bank", "level": 1}],
        points=25,
    )
    skill = _require(rich, "金錢砸")
    _tune(test_db, kid_id, hp=5000, spd=50)
    before_points = get_kid_points(test_db, kid_id)
    done = _use(client, kid_id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    dealt = 5000 - monster_hp(body)
    normal = max(1, rich["player_atk"] - 0)
    assert dealt == 3 * normal, (dealt, normal)
    assert get_kid_points(test_db, kid_id) == before_points - 10

    poor = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "bank", "level": 1}],
        points=9,
    )
    poor_skill = _require(poor, "金錢砸")
    _tune(test_db, kid_id, hp=4000, spd=50)
    broke = get_kid_points(test_db, kid_id)
    assert broke == 9
    rejected = _use(client, kid_id, poor_skill)
    assert rejected.status_code == 400, response_text(rejected)
    payload = rejected.get_json() or {}
    assert payload.get("error") == "insufficient_gold", payload
    assert get_kid_points(test_db, kid_id) == 9
    _exp, still = running_battle(test_db, kid_id)
    assert still["monsters"][0]["hp"] == 4000, still["monsters"]


# Historical skill_defs from the base seed (afbc1a6). Building names, not raw ids.
_OLD_SKILL_SEED = (
    ("蓄力", "🔥", 3, "健身室", 1, "self", "下次攻擊 1.5 倍", 0, 0, "none", "buff"),
    ("重擊", "💪", 5, "健身室", 2, "enemy", "強力物理攻擊", 20, 5, "str", "damage"),
    ("連擊", "⚡", 7, "健身室", 4, "enemy", "連續攻擊 2 次", 16, 4, "str", "damage"),
    ("繃帶", "🩹", 3, "醫院", 1, "ally", "小回復", 12, 4, "int", "heal"),
    ("急救", "💚", 8, "醫院", 3, "ally", "中回復", 25, 7, "int", "heal"),
    ("全體治療", "🌿", 14, "醫院", 5, "all_allies", "全體回復", 18, 5, "int", "heal"),
    ("橫掃", "🗡️", 6, "競技場", 2, "all_enemies", "全體物理攻擊", 15, 4, "str", "damage"),
    ("挑釁", "🛡️", 4, "競技場", 4, "self", "強制敵方攻擊自己", 0, 0, "none", "buff"),
    ("必殺", "💥", 10, "競技場", 5, "enemy", "對低血量敵人特大傷害", 32, 8, "str", "damage"),
    ("火球", "🔥", 6, "圖書館", 2, "enemy", "魔法攻擊", 20, 5, "int", "damage"),
    ("冰凍", "❄️", 8, "圖書館", 4, "enemy", "魔法攻擊 + 減速", 28, 7, "int", "damage"),
    ("偵察", "👁️", 2, "探險公會", 2, "enemy", "查看怪物弱點", 0, 0, "none", "utility"),
    ("迴避", "🏃", 3, "探險公會", 4, "self", "完全回避下次攻擊", 0, 0, "none", "buff"),
    ("修復", "🔧", 4, "工坊", 2, "ally", "回復 MP", 10, 3, "int", "heal"),
    ("強化", "🛡️", 5, "工坊", 4, "ally", "提升防禦力", 3, 1, "none", "buff"),
)
_NEW_SKILL_NAMES = (
    "知識的力量",
    "鍛鍊的成果",
    "營養餐",
    "金幣袋",
    "強光",
    "流星雨",
    "金錢砸",
)
_RENAMES = {"挑釁": "盾擊", "迴避": "疾風斬"}


def _reported_matk(battle):
    """Magic attack from the battle payload, or from the reported knowledge."""
    knowledge = battle.get("player_int") or 0
    derived = int(5 + knowledge * 1.5)
    if "player_matk" in battle:
        assert battle["player_matk"] == derived, (battle.get("player_matk"), derived)
        return battle["player_matk"]
    return derived


def _basic_physical(battle, monster_def):
    return max(1, int(battle["player_atk"]) - int(monster_def))


def _basic_magic(battle, monster_def):
    return max(1, int(_reported_matk(battle)) - int(monster_def))


def _ensure_bank(test_db):
    """Test DB only. 金錢砸 needs a 銀行 row before it can be placed."""
    db = connect_db(test_db)
    row = db.execute("SELECT id FROM building_defs WHERE name='銀行'").fetchone()
    if not row:
        db.execute(
            """
            INSERT INTO building_defs
                (name, icon, cost_gold, materials, effect, buff_type, buff_vals, max_level)
            VALUES ('銀行', '🏦', 600, '{}', '', 'skill', '[0]', 5)
            """
        )
        db.commit()
    db.close()


def _install_old_skill_seed(test_db):
    """Replace skill_defs with the historical catalog. Returns rows by name."""
    db = connect_db(test_db)
    db.execute("DELETE FROM skill_defs")
    for name, icon, mp_cost, bldg_name, level_required, target, description, base_value, per_level, attr_scale, effect_type in _OLD_SKILL_SEED:
        bldg = db.execute(
            "SELECT id FROM building_defs WHERE name=?",
            (bldg_name,),
        ).fetchone()
        assert bldg, bldg_name
        db.execute(
            """
            INSERT INTO skill_defs (
                name, icon, mp_cost, bldg_def_id, level_required, target,
                description, base_value, per_level, attr_scale, effect_type
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                name,
                icon,
                mp_cost,
                bldg["id"],
                level_required,
                target,
                description,
                base_value,
                per_level,
                attr_scale,
                effect_type,
            ),
        )
    db.commit()
    rows = {
        row["name"]: dict(row)
        for row in db.execute("SELECT * FROM skill_defs").fetchall()
    }
    db.close()
    return rows


def _skill_snapshot(test_db):
    db = connect_db(test_db)
    rows = [
        tuple(row)
        for row in db.execute("SELECT * FROM skill_defs ORDER BY id").fetchall()
    ]
    db.close()
    return rows


@pytest.mark.case_id("TC-API-MIGRATE-SKILLS")
def test_migrate_renames_skills_in_place_and_keeps_learned_ids(
    client, family, test_db, monkeypatch
):
    """舊 skill_defs 就地改名，唔好刪行再插入。學咗嘅 id 仍然打得到。

    舊目錄係基礎分支種子：挑釁、迴避、蓄力說明「1.5 倍」，冇七個新技能。
    小朋友用 skill id 學咗呢三個。migrate_db() 之後原 id 叫盾擊／疾風斬，
    蓄力說明有「2 倍」或「2倍」，七個新技能都在，舊 id 全部仲在，行數只增唔減。
    用原 id 開戰打得到。再跑一次 migrate_db() 唔改變、唔重複。
    """
    kid_id = family.kid_a.id
    prepare_kid(test_db, kid_id, points=200)
    place(test_db, kid_id, "gym", level=1, cell_x=0)
    place(test_db, kid_id, "arena", level=4, cell_x=2)
    place(test_db, kid_id, "guild", level=4, cell_x=6)

    before = _install_old_skill_seed(test_db)
    assert "挑釁" in before and "迴避" in before
    assert "1.5" in (before["蓄力"]["description"] or "")
    for name in _NEW_SKILL_NAMES:
        assert name not in before
    old_ids = [row["id"] for row in before.values()]
    learned = {
        before["挑釁"]["id"]: "盾擊",
        before["迴避"]["id"]: "疾風斬",
        before["蓄力"]["id"]: "蓄力",
    }
    db = connect_db(test_db)
    db.execute(
        "CREATE TABLE IF NOT EXISTS kid_skills (kid_id INTEGER NOT NULL, skill_id INTEGER NOT NULL)"
    )
    db.execute("DELETE FROM kid_skills WHERE kid_id=?", (kid_id,))
    for skill_id in learned:
        db.execute(
            "INSERT INTO kid_skills (kid_id, skill_id) VALUES (?, ?)",
            (kid_id, skill_id),
        )
    db.commit()
    db.close()

    b.migrate_db()

    db = connect_db(test_db)
    by_id = {
        row["id"]: dict(row)
        for row in db.execute("SELECT * FROM skill_defs").fetchall()
    }
    names = {row["name"] for row in by_id.values()}
    db.close()
    assert len(by_id) >= len(old_ids)
    for skill_id in old_ids:
        assert skill_id in by_id, skill_id
    for skill_id, new_name in learned.items():
        assert by_id[skill_id]["name"] == new_name, (skill_id, by_id.get(skill_id))
    charge_desc = by_id[before["蓄力"]["id"]]["description"] or ""
    assert ("2 倍" in charge_desc) or ("2倍" in charge_desc), charge_desc
    for name in _NEW_SKILL_NAMES:
        assert name in names, names
    assert "挑釁" not in names and "迴避" not in names

    started = login_and_start(client, family, kid_id, monkeypatch)
    assert started.status_code == 201, response_text(started)
    battle = started.get_json()
    _tune(test_db, kid_id, hp=8000, spd=50)
    for skill_id, new_name in learned.items():
        found = next(
            (row for row in battle.get("skills") or [] if row.get("id") == skill_id),
            None,
        )
        assert found and found.get("name") == new_name, battle.get("skills")
        cast = act(client, kid_id, "skill", skill_id=skill_id)
        assert cast.status_code == 200, response_text(cast)
        body = cast.get_json() or {}
        assert body.get("error") != "Skill not found", body

    snapshot = _skill_snapshot(test_db)
    b.migrate_db()
    assert _skill_snapshot(test_db) == snapshot
    db = connect_db(test_db)
    counts = dict(
        db.execute(
            "SELECT name, COUNT(*) FROM skill_defs GROUP BY name"
        ).fetchall()
    )
    db.close()
    assert all(count == 1 for count in counts.values()), counts


_DAMAGE_CASES = (
    {"name": "連擊", "building": "gym", "level": 4, "kind": "physical"},
    {"name": "冰凍", "building": "library", "level": 4, "kind": "magic"},
    {"name": "必殺", "building": "arena", "level": 5, "kind": "physical"},
    {"name": "修復", "building": "workshop", "level": 2, "kind": "physical"},
    {"name": "強化", "building": "workshop", "level": 4, "kind": "physical"},
    {"name": "偵察", "building": "guild", "level": 2, "kind": "zero"},
    {"name": "蓄力", "building": "gym", "level": 1, "kind": "physical"},
    {"name": "盾擊", "building": "arena", "level": 4, "kind": "physical", "exact": True},
    {"name": "疾風斬", "building": "guild", "level": 4, "kind": "physical", "exact": True},
    {"name": "知識的力量", "building": "library", "level": 1, "kind": "magic"},
    {"name": "鍛鍊的成果", "building": "gym", "level": 1, "kind": "physical"},
    {"name": "營養餐", "building": "farm", "level": 1, "kind": "physical"},
    {"name": "金幣袋", "building": "shop", "level": 1, "kind": "physical"},
    {"name": "強光", "building": "lighthouse", "level": 1, "kind": "magic"},
    {"name": "流星雨", "building": "observatory", "level": 1, "kind": "magic", "monsters": 3},
    {"name": "金錢砸", "building": "bank", "level": 1, "kind": "physical", "points": 40},
)


@pytest.mark.case_id("TC-API-SKILL-ALL-DAMAGE")
@pytest.mark.parametrize("spec", _DAMAGE_CASES, ids=[row["name"] for row in _DAMAGE_CASES])
def test_skill_cast_damage_against_basic_attack(
    client, family, test_db, monkeypatch, spec
):
    """除偵察外，施放嗰下怪物 HP 要跌，而且唔少過同一狀態嘅普攻。

    知識的力量、冰凍、強光、流星雨對魔法普攻 max(1, matk − 怪防)。
    matk 用開戰 player_matk；冇呢個欄就用 int(5 + player_int×1.5)。
    其餘（偵察除外）對物理普攻 max(1, player_atk − 怪防)。
    盾擊同疾風斬要剛好等於物理普攻。偵察要 0。流星雨每一隻都要達標。
    """
    if spec["building"] == "bank":
        _ensure_bank(test_db)
    specs = [{"key": "guild", "x": 6, "level": 1}]
    if spec["building"] == "guild":
        specs = [{"key": "guild", "x": 6, "level": spec["level"]}]
    else:
        specs.append({"key": spec["building"], "level": spec["level"], "x": 2})
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        specs,
        monsters=spec.get("monsters", 1),
        points=spec.get("points", 200),
    )
    skill = _require(battle, spec["name"])
    _tune(test_db, family.kid_a.id, hp=8000, spd=50)
    before = [8000 for _ in battle["monsters"]]
    cast = _ok(_use(client, family.kid_a.id, skill))
    drops = [old - monster_hp(cast, index) for index, old in enumerate(before)]
    if spec["kind"] == "zero":
        assert drops == [0] * len(drops), drops
        return
    floors = []
    for monster in battle["monsters"]:
        monster_def = monster.get("def") or 0
        if spec["kind"] == "magic":
            floors.append(_basic_magic(battle, monster_def))
        else:
            floors.append(_basic_physical(battle, monster_def))
    assert all(drop > 0 for drop in drops), (spec["name"], drops)
    if spec.get("exact"):
        assert drops[0] == floors[0], (spec["name"], drops, floors)
    else:
        assert all(drop >= floor for drop, floor in zip(drops, floors)), (
            spec["name"],
            drops,
            floors,
        )


@pytest.mark.case_id("TC-API-FORTIFY-TURNS")
def test_fortify_defence_lasts_three_monster_turns(
    client, family, test_db, monkeypatch
):
    """強化嘅防禦加乘維持三次怪物行動，第四次返對照。施放唔計入三次。"""
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "workshop", "level": 4, "x": 2}],
    )
    skill = _require(battle, "強化")
    _tune(test_db, kid_id, hp=8000, spd=50)
    control = _ok(act(client, kid_id, "attack"))
    baseline = _hp_loss(battle["player_hp"], control)
    assert baseline > 0, control
    cast = _ok(_use(client, kid_id, skill))
    hp = cast["player_hp"]
    for turn in (1, 2, 3):
        step = _ok(act(client, kid_id, "attack"))
        loss = hp - step["player_hp"]
        assert loss < baseline, (turn, loss, baseline)
        hp = step["player_hp"]
    expired = _ok(act(client, kid_id, "attack"))
    assert hp - expired["player_hp"] == baseline, (hp - expired["player_hp"], baseline)


@pytest.mark.case_id("TC-API-SHIELD-PERSIST")
def test_shield_halves_the_first_real_hit_not_a_miss(
    client, family, test_db, monkeypatch
):
    """盾擊減半留到怪物真正打中。打唔中唔消耗。再下一擊恢復全額。

    閃避用開戰 RNG：player_dodge 100 而且 (1,100) 擲 100 就打唔中。
    減半係對照反擊嘅整數除法。對照同全額都跟呢一場嘅 player_def。
    """
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "arena", "level": 4, "x": 2}],
    )
    skill = _require(battle, "盾擊", absent=("挑釁",))
    _tune(test_db, kid_id, hp=8000, spd=50, player_dodge=0)
    control = _ok(act(client, kid_id, "attack"))
    baseline = _hp_loss(battle["player_hp"], control)
    assert baseline > 1, (baseline, battle.get("player_def"))
    _tune(test_db, kid_id, player_dodge=100)
    cast = _ok(_use(client, kid_id, skill))
    assert _hp_loss(control["player_hp"], cast) == 0, cast
    _tune(test_db, kid_id, player_dodge=0)
    first = _ok(act(client, kid_id, "attack"))
    first_loss = cast["player_hp"] - first["player_hp"]
    assert first_loss == baseline // 2, (first_loss, baseline)
    second = _ok(act(client, kid_id, "attack"))
    assert first["player_hp"] - second["player_hp"] == baseline, second


_DESC_FORBIDDEN = ("唔會打傷害", "不造成傷害", "無傷害", "0 傷害")
# 冰凍 slows nothing. The copy must say the monster's attack drops.
_FREEZE_ATTACK_DROP = ("攻擊力下降", "攻擊下降", "攻擊力減", "傷害減少")
_FREEZE_TARGET = ("怪物", "敵人")


@pytest.mark.case_id("TC-API-SKILL-DESC-05")
def test_skill_descriptions_use_the_locked_keywords(test_db):
    """說明只鎖關鍵字，唔好逐字。

    冰凍唔好寫減速。要講怪物或者敵人嘅攻擊下降。
    """
    db = connect_db(test_db)
    rows = {
        row["name"]: row["description"] or ""
        for row in db.execute("SELECT name, description FROM skill_defs").fetchall()
    }
    db.close()
    problems = []
    fortify = rows.get("強化")
    if fortify is None:
        problems.append("強化 missing")
    elif "3 回合" not in fortify:
        problems.append(f"強化 description {fortify!r} missing 3 回合")
    shield = rows.get("盾擊")
    if shield is None:
        problems.append("盾擊 missing")
    elif "下一次被打中" not in shield and "下次被打中" not in shield:
        problems.append(f"盾擊 description {shield!r} missing 下一次被打中/下次被打中")
    flash = rows.get("強光")
    if flash is None:
        problems.append("強光 missing")
    elif "2 次" not in flash or ("打唔中" not in flash and "打不中" not in flash):
        problems.append(f"強光 description {flash!r} missing 2 次 and 打唔中/打不中")
    freeze = rows.get("冰凍")
    if freeze is None:
        problems.append("冰凍 missing")
    else:
        if "減速" in freeze:
            problems.append(f"冰凍 description contains 減速: {freeze!r}")
        drop = next((word for word in _FREEZE_ATTACK_DROP if word in freeze), None)
        target = next((word for word in _FREEZE_TARGET if word in freeze), None)
        if drop is None or target is None:
            problems.append(
                "冰凍 description must mention the monster attack drop "
                f"(one of {_FREEZE_ATTACK_DROP} together with 怪物 or 敵人): {freeze!r}"
            )
    for name in ("知識的力量", "鍛鍊的成果", "營養餐", "金幣袋", "修復", "強化"):
        text = rows.get(name)
        if text is None:
            problems.append(f"{name} missing")
            continue
        for banned in _DESC_FORBIDDEN:
            if banned in text:
                problems.append(f"{name} description contains {banned!r}: {text!r}")
    assert not problems, problems


@pytest.mark.case_id("TC-API-SEED-NO-DEAD-CURVE")
def test_shield_and_gale_have_no_unused_damage_curve(test_db):
    """盾擊、疾風斬傷害等於普攻，種子唔好再留傷害曲線。

    skill_defs 嘅曲線欄係 base_value、per_level（REAL，預設 0）。
    兩者要係 NULL 或 0。冇呢兩欄先至跳過。
    """
    db = connect_db(test_db)
    columns = [row[1] for row in db.execute("PRAGMA table_info(skill_defs)").fetchall()]
    curve_fields = [name for name in ("base_value", "per_level") if name in columns]
    if not curve_fields:
        db.close()
        pytest.skip("skill_defs has no base_value/per_level damage curve")
    problems = []
    for name in ("盾擊", "疾風斬"):
        row = db.execute("SELECT * FROM skill_defs WHERE name=?", (name,)).fetchone()
        if row is None:
            problems.append(f"{name} missing")
            continue
        for field in curve_fields:
            value = row[field]
            if value not in (None, 0, 0.0):
                problems.append(f"{name}.{field}={value!r}")
    db.close()
    assert not problems, problems


_RECAST_CASES = (
    {
        "name": "知識的力量",
        "building": "library",
        "stat": "player_int",
        "meter": "fireball",
    },
    {
        "name": "鍛鍊的成果",
        "building": "gym",
        "stat": "player_str",
        "also": "player_atk",
        "meter": "attack",
    },
)


def _meter_action(client, kid_id, spec, meter_skill):
    if spec["meter"] == "fireball":
        return _ok(_use(client, kid_id, meter_skill))
    return _ok(act(client, kid_id, "attack"))


def _single_cast_expect(spec, original, bonus, monster_def, baseline):
    """One cast adds 3×level. A second cast must not add it again."""
    stat_name = spec["stat"]
    stat = original[stat_name] + bonus
    expect = {stat_name: stat}
    if spec["meter"] == "fireball":
        expect["damage"] = baseline + bonus
    else:
        atk = int(5 + stat * 1.5)
        expect["player_atk"] = atk
        expect["damage"] = max(1, atk - monster_def)
    return expect


def _assert_profile(body, dealt, expect, label):
    for key, value in expect.items():
        if key == "damage":
            assert dealt == value, (label, dealt, expect)
        else:
            assert body.get(key) == value, (label, key, body.get(key), expect)


@pytest.mark.case_id("TC-API-SKILL-RECAST-REVERT")
@pytest.mark.parametrize("spec", _RECAST_CASES, ids=[row["name"] for row in _RECAST_CASES])
def test_recast_refreshes_three_turns_without_stacking(
    client, family, test_db, monkeypatch, spec
):
    """再施放只刷新 3 回合，唔疊加，亦唔改底。

    加成係一次 +3×等級。Lv1 圖書館如果開戰知識係 2，加成後係 5，唔好變 8。
    第二次施放唔計入三回合。之後三下維持一次加成，第四下返第一次之前嘅原值。
    原值同傷害跟呢一場開戰數，唔寫死。
    """
    kid_id = family.kid_a.id
    level = 1
    bonus = 3 * level
    if spec["meter"] == "fireball":
        _set_level_required(test_db, "火球", 1)
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": spec["building"], "level": level, "x": 2}],
    )
    skill = _require(battle, spec["name"])
    meter_skill = None
    if spec["meter"] == "fireball":
        meter_skill = skill_by_name(battle, "火球")
        assert meter_skill, battle.get("skills")
    original = {spec["stat"]: battle[spec["stat"]]}
    if spec.get("also"):
        original[spec["also"]] = battle[spec["also"]]
    monster_def = battle["monsters"][0]["def"]
    _tune(test_db, kid_id, hp=8000, spd=50, player_def=999)
    enemy_hp = 8000

    opened = _meter_action(client, kid_id, spec, meter_skill)
    baseline = enemy_hp - monster_hp(opened)
    assert baseline > 0, opened
    _assert_profile(opened, baseline, {**original, "damage": baseline}, "before cast")
    enemy_hp = monster_hp(opened)
    single = _single_cast_expect(spec, original, bonus, monster_def, baseline)
    assert single[spec["stat"]] != original[spec["stat"]]

    first = _ok(_use(client, kid_id, skill))
    enemy_hp = monster_hp(first)
    if first.get(spec["stat"]) == original[spec["stat"]]:
        probed = _meter_action(client, kid_id, spec, meter_skill)
        dealt = enemy_hp - monster_hp(probed)
        enemy_hp = monster_hp(probed)
        _assert_profile(probed, dealt, single, "buff must be active before the recast")
    else:
        stats_only = {key: value for key, value in single.items() if key != "damage"}
        _assert_profile(first, None, stats_only, "first cast")

    second = _ok(_use(client, kid_id, skill))
    enemy_hp = monster_hp(second)
    for turn in (1, 2, 3):
        step = _meter_action(client, kid_id, spec, meter_skill)
        dealt = enemy_hp - monster_hp(step)
        enemy_hp = monster_hp(step)
        _assert_profile(step, dealt, single, f"turn {turn} after recast")
    expired = _meter_action(client, kid_id, spec, meter_skill)
    dealt = enemy_hp - monster_hp(expired)
    _assert_profile(expired, dealt, {**original, "damage": baseline}, "after expiry")


def _race_two_gold_smashes(app, family, kid_id, skill_id):
    """Both gold reads observe 10 before either debit, when the code reads points.

    sqlite3.Connection.execute is read-only, so the barrier sits on a proxy
    returned from sqlite3.connect. Login happens first, on the real connect.
    """
    clients = [app.test_client(), app.test_client()]
    for racer in clients:
        login_kid(racer, family)

    gate = threading.Barrier(2)
    armed = {"on": True}
    waits = {"n": 0}
    lock = threading.Lock()
    original_connect = sqlite3.connect

    class _GoldConn:
        def __init__(self, conn):
            object.__setattr__(self, "_conn", conn)

        def execute(self, sql, *params, **kw):
            cursor = self._conn.execute(sql, *params, **kw)
            text = sql.lower() if isinstance(sql, str) else ""
            if armed["on"] and "select points from kids" in text:
                with lock:
                    waits["n"] += 1
                    ordinal = waits["n"]
                if ordinal <= 2:
                    gate.wait(timeout=5)
            return cursor

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def __setattr__(self, name, value):
            setattr(self._conn, name, value)

    def connect(*args, **kwargs):
        return _GoldConn(original_connect(*args, **kwargs))

    sqlite3.connect = connect
    errors = []
    responses = [None, None]
    try:

        def run(index):
            try:
                responses[index] = clients[index].post(
                    f"/api/kids/{kid_id}/expedition/battle-action",
                    json={"action": "skill", "skill_id": skill_id, "target_idx": 0},
                )
            except Exception as exc:  # noqa: BLE001 — surface the racer error in the assert
                errors.append(repr(exc))

        threads = [threading.Thread(target=run, args=(index,)) for index in (0, 1)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
    finally:
        armed["on"] = False
        sqlite3.connect = original_connect
    return responses, errors


@pytest.mark.case_id("TC-API-GOLD-SMASH-ATOMIC")
def test_two_gold_smashes_cannot_both_spend_the_last_ten_gold(
    app, client, family, test_db, monkeypatch
):
    """剛好 10 金幣。兩個金錢砸同時過金檢，只可以成功一次。

    兩邊讀到 10 之後先一齊扣。最後金幣 0，帳本只有一行 −10。
    """
    kid_id = family.kid_a.id
    _ensure_bank(test_db)
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "bank", "level": 1, "x": 2}],
        points=10,
    )
    skill = _require(battle, "金錢砸")
    _tune(test_db, kid_id, hp=8000, spd=50)
    assert get_kid_points(test_db, kid_id) == 10

    responses, errors = _race_two_gold_smashes(app, family, kid_id, skill["id"])
    assert not errors, errors
    assert all(response is not None for response in responses), responses
    codes = sorted(response.status_code for response in responses)
    rejected = [response for response in responses if response.status_code == 400]
    if len(rejected) == 1:
        assert (rejected[0].get_json(silent=True) or {}).get("error") == "insufficient_gold"
    gold = get_kid_points(test_db, kid_id)
    db = connect_db(test_db)
    debits = [
        dict(row)
        for row in db.execute(
            """
            SELECT amount, reason FROM points_log
             WHERE kid_id=? AND amount=-10 AND reason LIKE '%金錢砸%'
            """,
            (kid_id,),
        ).fetchall()
    ]
    db.close()
    assert codes == [200, 400] and gold == 0 and len(debits) == 1, {
        "codes": [
            (response.status_code, (response.get_json(silent=True) or {}).get("error"))
            for response in responses
        ],
        "gold": gold,
        "debits": debits,
    }
