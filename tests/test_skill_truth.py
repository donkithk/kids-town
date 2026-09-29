"""Skills must change numbers, not only the battle log.

RNG is monkeypatched. Empty SQLite and synthetic accounts only.
Every case below is red on the current base: the battle endpoint does not
do what the skill text says.
"""
from __future__ import annotations

import re

import pytest

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

# Region 1 weakness locked by TC-API-SKILL-SCOUT. Builder copies this onto the monster.
REGION_WEAKNESS = {1: "火", 2: "冰", 3: "雷"}
# 金幣袋 adds this much gold on top of the normal win payout.
COIN_BAG_BONUS = 20
# 營養餐 restore of HP and of MP, each, is inside this inclusive range.
MEAL_MIN = 1
MEAL_MAX = 15


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
    save_battle(test_db, exp_id, data)
    return data


def _use(client, kid_id, skill):
    return act(client, kid_id, "skill", skill_id=skill["id"])


def _hp_loss(before_hp, body):
    return before_hp - body["player_hp"]


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


@pytest.mark.case_id("TC-API-SKILL-FREEZE")
def test_freeze_slows_enemy_and_skips_counter(client, family, test_db, monkeypatch):
    """冰凍要令敵人慢下來，呢一下反擊係 0，而且 slow_turns >= 1。對照普攻會扣血。"""
    kid_id = family.kid_a.id
    specs = [{"key": "guild", "x": 6}, {"key": "library", "level": 4}]

    control = _open(client, family, test_db, monkeypatch, specs)
    _tune(test_db, kid_id, spd=50, hp=5000)
    control_hp = control["player_hp"]
    punched = act(client, kid_id, "attack")
    assert punched.status_code == 200, response_text(punched)
    control_loss = _hp_loss(control_hp, punched.get_json())
    assert control_loss > 0, punched.get_json()

    frozen_start = _open(client, family, test_db, monkeypatch, specs)
    skill = _require(frozen_start, "冰凍")
    _tune(test_db, kid_id, spd=50, hp=5000)
    before_hp = frozen_start["player_hp"]
    before_enemy = 5000
    done = _use(client, kid_id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    dealt = before_enemy - monster_hp(body)
    assert dealt > 0, body["monsters"]
    assert _hp_loss(before_hp, body) == 0, body
    slow = body["monsters"][0].get("slow_turns", 0)
    assert slow >= 1, body["monsters"][0]


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


@pytest.mark.case_id("TC-API-SKILL-CHARGE")
def test_charge_multiplier_matches_description(client, family, test_db, monkeypatch):
    """蓄力說明入面嘅 1.5 倍就要係下一擊嘅實際倍率（int(普攻 * 1.5)），唔好用 2 倍。"""
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "gym", "level": 1}],
    )
    skill = _require(battle, "蓄力")
    match = re.search(r"(\d+(?:\.\d+)?)", skill.get("description") or "")
    assert match, skill
    assert float(match.group(1)) == 1.5, skill["description"]
    _tune(test_db, kid_id, hp=5000, spd=50)
    cast = _use(client, kid_id, skill)
    assert cast.status_code == 200, response_text(cast)
    charged = cast.get_json()
    assert monster_hp(charged) == 5000, "蓄力本身唔好造成傷害"
    follow = act(client, kid_id, "attack")
    assert follow.status_code == 200, response_text(follow)
    dealt = 5000 - monster_hp(follow.get_json())
    normal = max(1, battle["player_atk"] - 0)
    assert dealt == int(normal * 1.5), f"dealt {dealt}, normal {normal}, want {int(normal * 1.5)}"


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


@pytest.mark.case_id("TC-API-SKILL-MEAL")
def test_farm_meal_restores_a_little_hp_and_mp(client, family, test_db, monkeypatch):
    """農場營養餐回復少量 HP 同 MP（各 1 至 15）。反擊被 999 防禦擋走。"""
    kid_id = family.kid_a.id
    battle = _open(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "x": 6}, {"key": "farm", "level": 1, "x": 2}],
    )
    skill = _require(battle, "營養餐")
    hp_before = battle["player_max_hp"] - 40
    mp_before = battle["player_max_mp"] - 20
    _tune(
        test_db,
        kid_id,
        spd=50,
        player_def=999,
        player_hp=hp_before,
        player_mp=mp_before,
    )
    done = _use(client, kid_id, skill)
    assert done.status_code == 200, response_text(done)
    body = done.get_json()
    hp_gain = body["player_hp"] - hp_before
    mp_gain = body["player_mp"] - mp_before
    assert MEAL_MIN <= hp_gain <= MEAL_MAX, body
    assert MEAL_MIN <= mp_gain <= MEAL_MAX, body


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
def test_lighthouse_flash_drops_enemy_hit_rate_for_two_turns(
    client, family, test_db, monkeypatch
):
    """燈塔強光：魔法傷害，之後兩次玩家行動敵人打唔中（HP 唔跌），第三下先至再扣血。"""
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
