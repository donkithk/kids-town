"""TC-API-VENUE-DAILY-CAP — one successful venue win per Hong Kong day.

Red lock for docs/test-cases/VENUE_DAILY_CAP.md. Empty temp DB only.
Does not open production kids_town.db and does not change product code.
"""
import json

import pytest
from freezegun import freeze_time

import backend_v2 as b
from tests.factories import (
    TEST_KID_PIN,
    building_def_id,
    connect_db,
    get_kid_experience,
    get_kid_points,
    insert_building,
    insert_kid,
    login_as,
)

pytestmark = [pytest.mark.case_id("TC-API-VENUE-DAILY-CAP")]

# Proposed player-facing API error. Toast is "⚠️ " + this string.
# See VENUE_DAILY_CAP.md. Not the colloquial product string.
PROPOSED_ERROR = "今日已在此區域獲勝，請明日再來。"

VENUE_A = 1
VENUE_B = 2
# 2026-11-06 04:00 UTC = 2026-11-06 12:00 Hong Kong. Both clocks agree.
# Noon UTC is still 2026-11-06 in Hong Kong (20:00). Login is repeated
# inside each freeze so the session cookie is not issued "in the future".
SAME_DAY = "2026-11-06 12:00:00+00:00"
HK_DATE = "2026-11-06"


def _place_guild(db_path, kid_id):
    insert_building(
        db_path,
        kid_id,
        building_def_id(db_path, "探險公會"),
        level=1,
        stored=0,
        cell_x=0,
        cell_y=0,
    )


def _running_battle(db_path, kid_id):
    db = connect_db(db_path)
    row = db.execute(
        "SELECT id, expedition_data FROM expeditions "
        "WHERE kid_id=? AND status='running' AND expedition_type='battle' "
        "ORDER BY id DESC LIMIT 1",
        (kid_id,),
    ).fetchone()
    db.close()
    assert row, "expected a running battle"
    return row["id"], json.loads(row["expedition_data"])


def _save_battle(db_path, expedition_id, battle):
    db = connect_db(db_path)
    db.execute(
        "UPDATE expeditions SET expedition_data=? WHERE id=?",
        (json.dumps(battle), expedition_id),
    )
    db.commit()
    db.close()


def _start(client, kid_id, region_id):
    return client.post(
        f"/api/kids/{kid_id}/expedition/battle-start",
        json={"region_id": region_id},
    )


def _attack(client, kid_id):
    return client.post(
        f"/api/kids/{kid_id}/expedition/battle-action",
        json={"action": "attack", "target_idx": 0},
    )


def _prime_win(db_path, kid_id):
    """One attack defeats the pack. Other bodies are already at 0 HP."""
    expedition_id, battle = _running_battle(db_path, kid_id)
    for index, monster in enumerate(battle["monsters"]):
        monster["hp"] = 1 if index == 0 else 0
        monster["def"] = 0
        monster["atk"] = 0
        monster["spd"] = 0
    battle["player_atk"] = 99
    battle["player_hp"] = battle.get("player_max_hp") or 100
    battle["player_spd"] = 99
    battle["player_def"] = 99
    _save_battle(db_path, expedition_id, battle)


def _prime_loss(db_path, kid_id):
    """The counterattack defeats the player. The pack stays alive."""
    expedition_id, battle = _running_battle(db_path, kid_id)
    for monster in battle["monsters"]:
        monster["hp"] = 500
        monster["def"] = 999
        monster["atk"] = 80
        monster["spd"] = 99
    battle["player_hp"] = 1
    battle["player_atk"] = 1
    battle["player_def"] = 0
    battle["player_spd"] = 0
    battle["player_dodge"] = 0
    _save_battle(db_path, expedition_id, battle)


def _daily_rows(db_path, kid_id):
    db = connect_db(db_path)
    rows = db.execute(
        "SELECT region_id, battle_date FROM daily_battles WHERE kid_id=? "
        "ORDER BY region_id, battle_date",
        (kid_id,),
    ).fetchall()
    db.close()
    return [(row["region_id"], row["battle_date"]) for row in rows]


def _running_count(db_path, kid_id):
    db = connect_db(db_path)
    count = db.execute(
        "SELECT COUNT(*) AS n FROM expeditions "
        "WHERE kid_id=? AND status='running' AND expedition_type='battle'",
        (kid_id,),
    ).fetchone()["n"]
    db.close()
    return count


def _gold_of(start_payload):
    return int(start_payload["gold_reward"]) * len(start_payload["monsters"])


def _win(client, db_path, kid_id, region_id):
    started = _start(client, kid_id, region_id)
    assert started.status_code == 201, started.get_data(as_text=True)
    payload = started.get_json()
    _prime_win(db_path, kid_id)
    finished = _attack(client, kid_id)
    assert finished.status_code == 200, finished.get_data(as_text=True)
    body = finished.get_json()
    assert body.get("battle_result") == "won", body
    return payload, body


def _assert_blocked(response, db_path, kid_id, points, experience, rows):
    problems = []
    body = response.get_json(silent=True) or {}
    if response.status_code != 400:
        problems.append(f"status {response.status_code} body={body}")
    elif body.get("error") != PROPOSED_ERROR:
        problems.append(f"error {body.get('error')!r} != {PROPOSED_ERROR!r}")
    if get_kid_points(db_path, kid_id) != points:
        problems.append(
            f"points {get_kid_points(db_path, kid_id)} != {points}"
        )
    if get_kid_experience(db_path, kid_id) != experience:
        problems.append(
            f"experience {get_kid_experience(db_path, kid_id)} != {experience}"
        )
    if _daily_rows(db_path, kid_id) != rows:
        problems.append(f"daily rows {_daily_rows(db_path, kid_id)} != {rows}")
    if _running_count(db_path, kid_id) != 0:
        problems.append("a running battle was opened")
    assert not problems, " | ".join(problems)


def _resume(client, username):
    """Log in again under the active freeze. A cookie minted at wall time is rejected once the clock moves backward."""
    logged_in = login_as(client, username, TEST_KID_PIN)
    assert logged_in.status_code == 200, logged_in.get_data(as_text=True)


def _insert_cap_kid(db_path, username):
    kid = insert_kid(
        db_path,
        name="Cap Kid",
        username=username,
        pin=TEST_KID_PIN,
        level=20,
        points=100,
        experience=100,
    )
    _place_guild(db_path, kid["id"])
    return kid


@pytest.mark.case_id("TC-API-VENUE-DAILY-CAP-01")
def test_second_win_same_venue_same_day_is_blocked(battle_client, test_db, battle_kid):
    """TC-API-VENUE-DAILY-CAP-01 second win at venue A the same HK day is blocked."""
    kid_id = battle_kid["id"]
    with freeze_time(SAME_DAY):
        _resume(battle_client, battle_kid["username"])
        assert b.hk_today_str() == HK_DATE
        before_points = get_kid_points(test_db, kid_id)
        before_exp = get_kid_experience(test_db, kid_id)
        started, _won = _win(battle_client, test_db, kid_id, VENUE_A)
        points = before_points + _gold_of(started)
        experience = before_exp + b.exp_reward_for_tier(VENUE_A)
        assert get_kid_points(test_db, kid_id) == points
        assert get_kid_experience(test_db, kid_id) == experience
        assert _daily_rows(test_db, kid_id) == [(VENUE_A, HK_DATE)]

        blocked = _start(battle_client, kid_id, VENUE_A)
        _assert_blocked(
            blocked,
            test_db,
            kid_id,
            points,
            experience,
            [(VENUE_A, HK_DATE)],
        )


@pytest.mark.case_id("TC-API-VENUE-DAILY-CAP-02")
def test_loss_does_not_consume_slot_and_win_still_pays(battle_client, test_db, battle_kid):
    """TC-API-VENUE-DAILY-CAP-02 a loss does not consume the slot."""
    kid_id = battle_kid["id"]
    with freeze_time(SAME_DAY):
        _resume(battle_client, battle_kid["username"])
        points = get_kid_points(test_db, kid_id)
        experience = get_kid_experience(test_db, kid_id)
        started = _start(battle_client, kid_id, VENUE_A)
        assert started.status_code == 201, started.get_data(as_text=True)
        _prime_loss(test_db, kid_id)
        lost = _attack(battle_client, kid_id)
        assert lost.status_code == 200, lost.get_data(as_text=True)
        assert lost.get_json().get("battle_result") == "lost"
        assert get_kid_points(test_db, kid_id) == points
        assert get_kid_experience(test_db, kid_id) == experience
        assert _daily_rows(test_db, kid_id) == []

        won_start, _body = _win(battle_client, test_db, kid_id, VENUE_A)
        assert get_kid_points(test_db, kid_id) == points + _gold_of(won_start)
        assert get_kid_experience(test_db, kid_id) == (
            experience + b.exp_reward_for_tier(VENUE_A)
        )
        assert _daily_rows(test_db, kid_id) == [(VENUE_A, HK_DATE)]


@pytest.mark.case_id("TC-API-VENUE-DAILY-CAP-03")
def test_flee_or_abandoned_start_does_not_consume_slot(battle_client, test_db, battle_kid):
    """TC-API-VENUE-DAILY-CAP-03 flee and an abandoned start do not consume the slot."""
    kid_id = battle_kid["id"]
    with freeze_time(SAME_DAY):
        _resume(battle_client, battle_kid["username"])
        points = get_kid_points(test_db, kid_id)
        experience = get_kid_experience(test_db, kid_id)
        first = _start(battle_client, kid_id, VENUE_A)
        assert first.status_code == 201, first.get_data(as_text=True)
        fled = battle_client.post(
            f"/api/kids/{kid_id}/expedition/battle-action",
            json={"action": "flee"},
        )
        assert fled.status_code == 200, fled.get_data(as_text=True)
        assert fled.get_json().get("battle_result") == "fled"
        assert _daily_rows(test_db, kid_id) == []
        assert get_kid_points(test_db, kid_id) == points

        restarted = _start(battle_client, kid_id, VENUE_A)
        assert restarted.status_code == 201, restarted.get_data(as_text=True)
        abandoned = _start(battle_client, kid_id, VENUE_A)
        assert abandoned.status_code == 201, abandoned.get_data(as_text=True)
        assert _daily_rows(test_db, kid_id) == []
        assert get_kid_points(test_db, kid_id) == points
        assert _running_count(test_db, kid_id) == 1

        won_start, _body = _win(battle_client, test_db, kid_id, VENUE_A)
        assert get_kid_points(test_db, kid_id) == points + _gold_of(won_start)
        assert get_kid_experience(test_db, kid_id) == (
            experience + b.exp_reward_for_tier(VENUE_A)
        )
        assert _daily_rows(test_db, kid_id) == [(VENUE_A, HK_DATE)]


@pytest.mark.case_id("TC-API-VENUE-DAILY-CAP-04")
def test_other_venue_same_day_still_pays(battle_client, test_db, battle_kid):
    """TC-API-VENUE-DAILY-CAP-04 venue B still pays after venue A was claimed."""
    kid_id = battle_kid["id"]
    with freeze_time(SAME_DAY):
        _resume(battle_client, battle_kid["username"])
        # A win rewrites kids.level from total EXP. The shared battle fixture
        # is level 20 with only 100 EXP, so the first win would drop the kid
        # under venue B's Lv4 gate. 375 EXP is Lv.6 and stays there.
        db = connect_db(test_db)
        db.execute(
            "UPDATE kids SET level=6, experience=375 WHERE id=?",
            (kid_id,),
        )
        db.commit()
        db.close()
        assert b.calc_level(375)[0] >= 4
        points = get_kid_points(test_db, kid_id)
        experience = get_kid_experience(test_db, kid_id)
        won_a, _body_a = _win(battle_client, test_db, kid_id, VENUE_A)
        won_b, _body_b = _win(battle_client, test_db, kid_id, VENUE_B)
        assert get_kid_points(test_db, kid_id) == (
            points + _gold_of(won_a) + _gold_of(won_b)
        )
        assert get_kid_experience(test_db, kid_id) == (
            experience
            + b.exp_reward_for_tier(VENUE_A)
            + b.exp_reward_for_tier(VENUE_B)
        )
        assert _daily_rows(test_db, kid_id) == [
            (VENUE_A, HK_DATE),
            (VENUE_B, HK_DATE),
        ]
        paid = get_kid_points(test_db, kid_id)
        gained = get_kid_experience(test_db, kid_id)
        blocked = _start(battle_client, kid_id, VENUE_A)
        assert blocked.status_code == 400, blocked.get_data(as_text=True)
        assert get_kid_points(test_db, kid_id) == paid
        assert get_kid_experience(test_db, kid_id) == gained
        assert _running_count(test_db, kid_id) == 0
        assert _daily_rows(test_db, kid_id) == [
            (VENUE_A, HK_DATE),
            (VENUE_B, HK_DATE),
        ]


@pytest.mark.case_id("TC-API-VENUE-DAILY-CAP-05")
def test_next_hk_day_allows_same_venue_again(battle_client, test_db, battle_kid):
    """TC-API-VENUE-DAILY-CAP-05 Hong Kong midnight opens the venue; UTC date does not."""
    kid_id = battle_kid["id"]
    with freeze_time("2026-11-06 15:00:00+00:00"):
        _resume(battle_client, battle_kid["username"])
        assert b.hk_today_str() == "2026-11-06"
        assert b.date.today().isoformat() == "2026-11-06"
        _win(battle_client, test_db, kid_id, VENUE_A)
        assert _daily_rows(test_db, kid_id) == [(VENUE_A, "2026-11-06")]

    with freeze_time("2026-11-06 16:30:00+00:00"):
        _resume(battle_client, battle_kid["username"])
        assert b.hk_today_str() == "2026-11-07"
        assert b.date.today().isoformat() == "2026-11-06"
        opened = _start(battle_client, kid_id, VENUE_A)
        assert opened.status_code == 201, opened.get_data(as_text=True)


@pytest.mark.case_id("TC-API-VENUE-DAILY-CAP-06")
def test_utc_midnight_does_not_reset_hk_day(battle_client, test_db, battle_kid):
    """TC-API-VENUE-DAILY-CAP-06 a new UTC date does not open the same Hong Kong day."""
    kid_id = battle_kid["id"]
    with freeze_time("2026-11-06 20:00:00+00:00"):
        _resume(battle_client, battle_kid["username"])
        assert b.hk_today_str() == "2026-11-07"
        assert b.date.today().isoformat() == "2026-11-06"
        _win(battle_client, test_db, kid_id, VENUE_A)
        points = get_kid_points(test_db, kid_id)
        experience = get_kid_experience(test_db, kid_id)

    with freeze_time("2026-11-07 01:00:00+00:00"):
        _resume(battle_client, battle_kid["username"])
        assert b.hk_today_str() == "2026-11-07"
        assert b.date.today().isoformat() == "2026-11-07"
        problems = []
        rows = _daily_rows(test_db, kid_id)
        if rows != [(VENUE_A, "2026-11-07")]:
            problems.append(f"stored rows {rows}, expected [(1, '2026-11-07')]")
        blocked = _start(battle_client, kid_id, VENUE_A)
        body = blocked.get_json(silent=True) or {}
        if blocked.status_code != 400:
            problems.append(f"second start {blocked.status_code} body={body}")
        elif body.get("error") != PROPOSED_ERROR:
            problems.append(f"error {body.get('error')!r} != {PROPOSED_ERROR!r}")
        if get_kid_points(test_db, kid_id) != points:
            problems.append("points changed after the UTC date rolled")
        if get_kid_experience(test_db, kid_id) != experience:
            problems.append("experience changed after the UTC date rolled")
        assert not problems, "TC-API-VENUE-DAILY-CAP-06: " + " | ".join(problems)


@pytest.mark.case_id("TC-API-VENUE-DAILY-CAP-07")
def test_preview_account_can_win_same_venue_twice(client, test_db):
    """TC-API-VENUE-DAILY-CAP-07 preview_kid is exempt from the venue cap."""
    kid = _insert_cap_kid(test_db, b.PREVIEW_KID_USERNAME)
    kid_id = kid["id"]
    with freeze_time(SAME_DAY):
        _resume(client, b.PREVIEW_KID_USERNAME)
        points = get_kid_points(test_db, kid_id)
        experience = get_kid_experience(test_db, kid_id)
        first, _body1 = _win(client, test_db, kid_id, VENUE_A)
        second, _body2 = _win(client, test_db, kid_id, VENUE_A)
        assert get_kid_points(test_db, kid_id) == (
            points + _gold_of(first) + _gold_of(second)
        )
        assert get_kid_experience(test_db, kid_id) == (
            experience + 2 * b.exp_reward_for_tier(VENUE_A)
        )
        assert _gold_of(first) == 20
        assert _gold_of(second) == 20


@pytest.mark.case_id("TC-API-VENUE-DAILY-CAP-08")
def test_lookalike_username_is_not_preview(client, test_db):
    """TC-API-VENUE-DAILY-CAP-08 preview_kid_2 is a normal account."""
    kid = _insert_cap_kid(test_db, "preview_kid_2")
    kid_id = kid["id"]
    with freeze_time(SAME_DAY):
        _resume(client, "preview_kid_2")
        _win(client, test_db, kid_id, VENUE_A)
        points = get_kid_points(test_db, kid_id)
        experience = get_kid_experience(test_db, kid_id)
        blocked = _start(client, kid_id, VENUE_A)
        assert blocked.status_code == 400, blocked.get_data(as_text=True)
        assert get_kid_points(test_db, kid_id) == points
        assert get_kid_experience(test_db, kid_id) == experience
        assert _running_count(test_db, kid_id) == 0
