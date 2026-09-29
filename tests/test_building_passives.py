"""Locked building passives, removed old effects, and the observatory treasure contract.

New behaviour is red on the current base. Shop discount and farm daily gold
stay covered by P1-TC-BUFF-05..08 and SHEET-BUFF-TRUTH-02..04.

Empty SQLite, synthetic accounts only.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import backend_v2 as b
from tests.battle_truth import (
    expected_from_abilities,
    login_and_start,
    place,
    prepare_kid,
)
from tests.factories import (
    connect_db,
    force_expedition_claimable,
    get_kid_experience,
    get_kid_points,
    response_text,
)
from tests.phase1_helpers import (
    create_assigned_task,
    json_or_text,
    login_kid,
    start_explore,
)

# explore_treasure_chance(level): 0 at 0, else min(0.50, 0.10 * level).
# Claim JSON must include treasure_chance and treasure.
# roll_explore_treasure(chance) is the single RNG hook (random.random() < chance).


def _problems_for(body, expected, fields, label):
    problems = []
    for field in fields:
        got = body.get(field, "MISSING")
        want = expected[field]
        if isinstance(want, float):
            if got == "MISSING" or abs(float(got) - want) > 1e-9:
                problems.append(f"{label} {field}={got} want {want}")
        elif got != want:
            problems.append(f"{label} {field}={got} want {want}")
    return problems


def _start_clean(client, family, test_db, monkeypatch, specs, points=200):
    kid_id = family.kid_a.id
    prepare_kid(test_db, kid_id, points=points)
    for spec in specs:
        place(
            test_db,
            kid_id,
            spec["key"],
            level=spec.get("level", 1),
            stored=spec.get("stored", 0),
            cell_x=spec.get("cell_x", 0),
            cell_y=spec.get("cell_y", 0),
        )
    response = login_and_start(client, family, kid_id, monkeypatch)
    assert response.status_code == 201, response_text(response)
    return response.get_json()


@pytest.mark.case_id("TC-API-BLD-PASSIVE-LIB")
def test_library_knowledge_raises_battle_matk(client, family, test_db, monkeypatch):
    """圖書館每級 +2 知識，經 matk=int(5+int*1.5) 進入開戰。

    Lv0 → 5，Lv1 → 8（+3），Lv2 → 11（+6），Lv4 → 17（+12，唔係舊 buff_vals 10 知識嘅 20）。
    stored=1 唔計。calc_battle_stats 而家唔讀 calc_ability_buffs，所以 matk 唔會升。
    """
    kid_id = family.kid_a.id
    fields = ("player_matk",)
    problems = []

    baseline = _start_clean(
        client, family, test_db, monkeypatch, [{"key": "guild", "cell_x": 6}]
    )
    problems += _problems_for(
        baseline, expected_from_abilities(), fields, "library Lv0"
    )

    lv1 = _start_clean(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "cell_x": 6}, {"key": "library", "level": 1, "cell_x": 0}],
    )
    problems += _problems_for(
        lv1, expected_from_abilities(int_v=2), fields, "library Lv1"
    )

    lv2 = _start_clean(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "cell_x": 6}, {"key": "library", "level": 2, "cell_x": 0}],
    )
    problems += _problems_for(
        lv2, expected_from_abilities(int_v=4), fields, "library Lv2"
    )

    lv4 = _start_clean(
        client,
        family,
        test_db,
        monkeypatch,
        [{"key": "guild", "cell_x": 6}, {"key": "library", "level": 4, "cell_x": 0}],
    )
    problems += _problems_for(
        lv4, expected_from_abilities(int_v=8), fields, "library Lv4"
    )

    stored = _start_clean(
        client,
        family,
        test_db,
        monkeypatch,
        [
            {"key": "guild", "cell_x": 6},
            {"key": "library", "level": 4, "stored": 1, "cell_x": 2},
        ],
    )
    problems += _problems_for(
        stored, expected_from_abilities(), fields, "stored library"
    )
    assert not problems, problems


@pytest.mark.case_id("TC-API-BLD-PASSIVE-GYM")
def test_gym_strength_raises_battle_atk(client, family, test_db, monkeypatch):
    """健身室每級 +2 臂力。atk=int(5+str*1.5)：Lv0=5，Lv1=8，Lv2=11。存倉唔計。"""
    fields = ("player_atk",)
    problems = []
    problems += _problems_for(
        _start_clean(client, family, test_db, monkeypatch, [{"key": "guild", "cell_x": 6}]),
        expected_from_abilities(),
        fields,
        "gym Lv0",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "cell_x": 6}, {"key": "gym", "level": 1}],
        ),
        expected_from_abilities(str_v=2),
        fields,
        "gym Lv1",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "cell_x": 6}, {"key": "gym", "level": 2}],
        ),
        expected_from_abilities(str_v=4),
        fields,
        "gym Lv2",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [
                {"key": "guild", "cell_x": 6},
                {"key": "gym", "level": 2, "stored": 1, "cell_x": 2},
            ],
        ),
        expected_from_abilities(),
        fields,
        "stored gym",
    )
    assert not problems, problems


@pytest.mark.case_id("TC-API-BLD-PASSIVE-WRK")
def test_workshop_creativity_raises_battle_crt(client, family, test_db, monkeypatch):
    """工坊每級 +2 創意。crt%=min(50, crt*2)：Lv0=0，Lv1=4，Lv2=8。存倉唔計。"""
    fields = ("player_crt",)
    problems = []
    problems += _problems_for(
        _start_clean(client, family, test_db, monkeypatch, [{"key": "guild", "cell_x": 6}]),
        expected_from_abilities(),
        fields,
        "workshop Lv0",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "cell_x": 6}, {"key": "workshop", "level": 1}],
        ),
        expected_from_abilities(crt_v=2),
        fields,
        "workshop Lv1",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "cell_x": 6}, {"key": "workshop", "level": 2}],
        ),
        expected_from_abilities(crt_v=4),
        fields,
        "workshop Lv2",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [
                {"key": "guild", "cell_x": 6},
                {"key": "workshop", "level": 2, "stored": 1},
            ],
        ),
        expected_from_abilities(),
        fields,
        "stored workshop",
    )
    assert not problems, problems


@pytest.mark.case_id("TC-API-BLD-PASSIVE-ARN")
def test_arena_raises_atk_and_dodge(client, family, test_db, monkeypatch):
    """競技場每級 +2 臂力、+1 速度。

    Lv1：atk 8、dodge 1.5。Lv2：atk 11、dodge 3.0。存倉唔計。
    """
    fields = ("player_atk", "player_dodge")
    problems = []
    problems += _problems_for(
        _start_clean(client, family, test_db, monkeypatch, [{"key": "guild", "cell_x": 6}]),
        expected_from_abilities(),
        fields,
        "arena Lv0",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "cell_x": 6}, {"key": "arena", "level": 1}],
        ),
        expected_from_abilities(str_v=2, spd_v=1),
        fields,
        "arena Lv1",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [{"key": "guild", "cell_x": 6}, {"key": "arena", "level": 2}],
        ),
        expected_from_abilities(str_v=4, spd_v=2),
        fields,
        "arena Lv2",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [
                {"key": "guild", "cell_x": 6},
                {"key": "arena", "level": 2, "stored": 1},
            ],
        ),
        expected_from_abilities(),
        fields,
        "stored arena",
    )
    assert not problems, problems


@pytest.mark.case_id("TC-API-BLD-PASSIVE-GLD")
def test_guild_courage_raises_battle_def(client, family, test_db, monkeypatch):
    """探險公會每級 +2 勇氣。def=int(brv*0.6)：Lv1=1，Lv2=2。

    再開一座 stored Lv5 公會唔好再加。冇公會開唔到戰（guild_required）係原有閘。
    """
    fields = ("player_def",)
    problems = []
    problems += _problems_for(
        _start_clean(
            client, family, test_db, monkeypatch, [{"key": "guild", "level": 1, "cell_x": 6}]
        ),
        expected_from_abilities(brv_v=2),
        fields,
        "guild Lv1",
    )
    problems += _problems_for(
        _start_clean(
            client, family, test_db, monkeypatch, [{"key": "guild", "level": 2, "cell_x": 6}]
        ),
        expected_from_abilities(brv_v=4),
        fields,
        "guild Lv2",
    )
    problems += _problems_for(
        _start_clean(
            client,
            family,
            test_db,
            monkeypatch,
            [
                {"key": "guild", "level": 1, "cell_x": 6},
                {"key": "guild", "level": 5, "stored": 1, "cell_x": 2},
            ],
        ),
        expected_from_abilities(brv_v=2),
        fields,
        "stored guild ignored",
    )
    assert not problems, problems


@pytest.mark.case_id("TC-API-BLD-PASSIVE-OBS")
def test_observatory_does_not_grant_knowledge(client, family, test_db, monkeypatch):
    """天文台唔再加知識。

    GET /abilities 嘅 buffs.int 要係 0（而家 calc_ability_buffs 每級 +2）。
    開戰 player_matk 要等於冇天文台嘅 5。
    """
    kid_id = family.kid_a.id
    body = _start_clean(
        client,
        family,
        test_db,
        monkeypatch,
        [
            {"key": "guild", "cell_x": 6},
            {"key": "observatory", "level": 2, "cell_x": 0},
        ],
    )
    abilities = client.get(f"/api/kids/{kid_id}/abilities")
    assert abilities.status_code == 200, response_text(abilities)
    payload = abilities.get_json()
    problems = []
    if payload["buffs"]["int"] != 0:
        problems.append(
            f"observatory still adds knowledge buffs.int={payload['buffs']['int']} want 0"
        )
    if payload["total"]["int"] != payload["base"]["int"]:
        problems.append(
            f"total int {payload['total']['int']} != base {payload['base']['int']}"
        )
    matk = body.get("player_matk", "MISSING")
    if matk != 5:
        problems.append(f"player_matk={matk} want 5 (no knowledge from observatory)")
    assert not problems, problems


def _claim_explore(client, test_db, kid_id, region=1):
    started = start_explore(client, kid_id, region)
    assert started.status_code == 201, response_text(started)
    force_expedition_claimable(test_db, kid_id)
    claimed = client.post(f"/api/kids/{kid_id}/expedition/claim", json={})
    assert claimed.status_code == 200, response_text(claimed)
    return json_or_text(claimed)


@pytest.mark.case_id("TC-API-BLD-TREASURE")
def test_observatory_treasure_chance_rises_on_explore(client, family, test_db, monkeypatch):
    """探險而家冇寶物欄位。鎖定最小合約：

    backend_v2.explore_treasure_chance(level) = 0（level<=0）否則 min(0.50, 0.10*level)。
    backend_v2.roll_explore_treasure(chance) 用 random.random() < chance，claim 要呼叫佢。
    claim JSON 有 treasure_chance 同 treasure。Lv1 機會 0.10 唔中；Lv2 機會 0.20 中。
    存倉天文台機會係 0。
    """
    assert hasattr(b, "explore_treasure_chance"), (
        "explore claim has no treasure mechanic. "
        "Add explore_treasure_chance(level): 0 if level<=0 else min(0.50, 0.10*level)."
    )
    assert b.explore_treasure_chance(0) == 0.0
    assert b.explore_treasure_chance(1) == pytest.approx(0.10)
    assert b.explore_treasure_chance(2) == pytest.approx(0.20)
    assert b.explore_treasure_chance(6) == pytest.approx(0.50)
    assert hasattr(b, "roll_explore_treasure"), (
        "claim must call roll_explore_treasure(chance), implemented as random.random() < chance"
    )

    def _roll(chance):
        return float(chance) >= 0.20

    monkeypatch.setattr(b, "roll_explore_treasure", _roll)

    kid_id = family.kid_a.id
    prepare_kid(test_db, kid_id, points=80)
    place(test_db, kid_id, "guild", cell_x=6)
    place(test_db, kid_id, "observatory", level=1, cell_x=0)
    login_kid(client, family)

    low = _claim_explore(client, test_db, kid_id)
    assert low.get("treasure_chance") == pytest.approx(0.10), low
    assert low.get("treasure") is False, low

    db = connect_db(test_db)
    db.execute(
        """
        UPDATE buildings SET level=2
         WHERE kid_id=? AND def_id=(SELECT id FROM building_defs WHERE name='天文台')
        """,
        (kid_id,),
    )
    db.commit()
    db.close()
    high = _claim_explore(client, test_db, kid_id)
    assert high.get("treasure_chance") == pytest.approx(0.20), high
    assert high.get("treasure") is True, high

    db = connect_db(test_db)
    db.execute(
        """
        UPDATE buildings SET stored=1
         WHERE kid_id=? AND def_id=(SELECT id FROM building_defs WHERE name='天文台')
        """,
        (kid_id,),
    )
    db.commit()
    db.close()
    parked = _claim_explore(client, test_db, kid_id)
    assert parked.get("treasure_chance") == pytest.approx(0.0), parked
    assert parked.get("treasure") is False, parked


@pytest.mark.case_id("TC-API-BLD-REMOVED-XP")
def test_library_no_longer_adds_task_xp(client, family, test_db):
    """圖書館任務經驗加成要消失。10 分任務 experience_bonus==0，總 XP 得 5。"""
    kid_id = family.kid_a.id
    prepare_kid(test_db, kid_id, level=1, points=20)
    place(test_db, kid_id, "library", level=2)
    before = get_kid_experience(test_db, kid_id) or 0
    task_id = create_assigned_task(client, family, "passive-no-lib-xp", points=10)
    done = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert done.status_code == 200, response_text(done)
    data = json_or_text(done)
    assert data.get("experience_gained") == 5, data
    assert data.get("experience_bonus") == 0, data
    assert data.get("experience_total") == 5, data
    assert data.get("points_awarded") == 10, data
    assert get_kid_experience(test_db, kid_id) == before + 5


@pytest.mark.case_id("TC-API-BLD-REMOVED-STREAK")
def test_gym_does_not_protect_streak(client, family, test_db):
    """健身室連續保護要消失。漏咗幾日，連續日數重置為 1，唔好留喺 5。"""
    kid_id = family.kid_a.id
    prepare_kid(test_db, kid_id, level=1, points=10)
    place(test_db, kid_id, "gym", level=5)
    stale = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    db = connect_db(test_db)
    db.execute("DELETE FROM streaks WHERE kid_id=?", (kid_id,))
    db.execute(
        """
        INSERT INTO streaks (kid_id, current_streak, best_streak, last_active_date)
        VALUES (?, 5, 5, ?)
        """,
        (kid_id, stale),
    )
    db.commit()
    db.close()
    task_id = create_assigned_task(client, family, "passive-no-streak", points=10)
    done = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": kid_id})
    assert done.status_code == 200, response_text(done)
    row = fetch_streak(test_db, kid_id)
    assert row["current_streak"] == 1, row


def fetch_streak(test_db, kid_id):
    db = connect_db(test_db)
    row = db.execute("SELECT * FROM streaks WHERE kid_id=?", (kid_id,)).fetchone()
    db.close()
    assert row, "streak row missing"
    return dict(row)


@pytest.mark.case_id("TC-API-BLD-REMOVED-HOSP")
def test_hospital_does_not_multiply_explore_rewards(client, family, test_db, monkeypatch):
    """醫院探險回復要消失。同一 RNG 之下，有醫院同冇醫院嘅探險金幣、經驗一樣，唔好乘 buff。"""
    monkeypatch.setattr(b.random, "random", lambda: 0.99)
    monkeypatch.setattr(b.random, "randint", lambda lo, hi: lo)

    def _once(with_hospital):
        kid_id = family.kid_a.id
        prepare_kid(test_db, kid_id, points=40)
        place(test_db, kid_id, "guild", cell_x=6)
        if with_hospital:
            place(test_db, kid_id, "hospital", level=5, cell_x=0)
        login_kid(client, family)
        before_points = get_kid_points(test_db, kid_id)
        before_xp = get_kid_experience(test_db, kid_id) or 0
        body = _claim_explore(client, test_db, kid_id)
        return {
            "gold": get_kid_points(test_db, kid_id) - before_points,
            "xp": (get_kid_experience(test_db, kid_id) or 0) - before_xp,
            "reported_gold": body.get("gold"),
        }

    plain = _once(False)
    hospital = _once(True)
    # Region 1 fee is 10 and the low gold roll is 6, so the net is -4. Recovery xN would change the reward.
    assert hospital["reported_gold"] == plain["reported_gold"] == 6, (plain, hospital)
    assert hospital["gold"] == plain["gold"] == -4, (plain, hospital)
    assert hospital["xp"] == plain["xp"] == 10, (plain, hospital)


@pytest.mark.case_id("TC-API-BLD-REMOVED-RANGE")
def test_lighthouse_does_not_extend_explore_range(client, family, test_db):
    """燈塔探險範圍要消失。Lv5 燈塔都唔可以打開區 4（仍然 region_locked）。區 1 照舊要公會先至開到。"""
    kid_id = family.kid_a.id
    prepare_kid(test_db, kid_id, level=2, points=40)
    place(test_db, kid_id, "guild", cell_x=6)
    place(test_db, kid_id, "lighthouse", level=5, cell_x=0)
    login_kid(client, family)
    locked = start_explore(client, kid_id, 4)
    assert locked.status_code == 400, response_text(locked)
    assert json_or_text(locked).get("error") == "region_locked"
    opened = start_explore(client, kid_id, 1)
    assert opened.status_code == 201, response_text(opened)


@pytest.mark.case_id("TC-API-BLD-REMOVED-LEDGER")
def test_bank_ledger_is_not_a_building_effect(client, family, test_db):
    """銀行帳本被動要消失。

    建築定義唔好有 ledger／帳本 buff。家長帳本 API 唔使有銀行都回得 200，
    而且唔因為有冇銀行而改變筆數。金錢砸係技能，唔係帳本。
    """
    kid_id = family.kid_a.id
    db = connect_db(test_db)
    defs = db.execute("SELECT name, buff_type, effect FROM building_defs").fetchall()
    db.close()
    for row in defs:
        blob = f"{row['name']} {row['buff_type'] or ''} {row['effect'] or ''}"
        assert "ledger" not in blob.lower(), blob
        if row["name"] == "銀行":
            assert "帳本" not in (row["effect"] or ""), row["effect"]

    from tests.phase1_helpers import login_parent

    login_parent(client, family)
    ledger = client.get(f"/api/transactions?kid_id={kid_id}")
    assert ledger.status_code == 200, response_text(ledger)
    body = ledger.get_json()
    assert isinstance(body.get("items"), list), body


@pytest.mark.case_id("TC-API-MIGRATE-FARM")
def test_migrate_old_schema_without_farm_claims_then_town(client, family, test_db):
    """舊庫冇 farm_claims。migrate_db() 要自己建表。

    之後 GET /api/kids/<id>/town 係 200，farm_claimed_today 係 false。
    唔好靠「表唔存在就當 false」吞掉錯誤。
    """
    db = connect_db(test_db)
    db.execute("DROP TABLE farm_claims")
    db.commit()
    names = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "farm_claims" not in names
    db.close()

    b.migrate_db()

    db = connect_db(test_db)
    names = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "farm_claims" in names, "migrate_db() must create farm_claims"
    db.execute("SELECT claim_date FROM farm_claims").fetchall()
    db.close()

    login_kid(client, family)
    town = client.get(f"/api/kids/{family.kid_a.id}/town")
    assert town.status_code == 200, response_text(town)
    assert town.get_json().get("farm_claimed_today") is False

