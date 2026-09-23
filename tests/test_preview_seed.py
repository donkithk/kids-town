"""Preview demo kid: enough gold and a placed exploration guild."""
import sqlite3

import backend_v2 as b
from tests.factories import connect_db, init_empty_db


def test_preview_seed_creates_kid_with_gold_and_guild(tmp_path):
    db_path = str(tmp_path / "preview.db")
    init_empty_db(b, db_path)
    db = connect_db(db_path)
    info = b.ensure_preview_kid(db)
    row = db.execute(
        "SELECT points, level FROM kids WHERE username=?",
        (b.PREVIEW_KID_USERNAME,),
    ).fetchone()
    assert info["created"] is True
    assert row["points"] >= 200
    assert row["level"] >= 2
    assert b.has_active_guild(info["kid_id"], db)
    pin = db.execute(
        "SELECT pin FROM kid_auth WHERE kid_id=?", (info["kid_id"],)
    ).fetchone()["pin"]
    assert b.verify_password(b.PREVIEW_KID_PIN, pin)
    again = b.ensure_preview_kid(db)
    assert again["created"] is False
    points = db.execute(
        "SELECT points FROM kids WHERE id=?", (info["kid_id"],)
    ).fetchone()["points"]
    guilds = db.execute(
        "SELECT COUNT(*) AS n FROM buildings WHERE kid_id=? AND COALESCE(stored,0)=0",
        (info["kid_id"],),
    ).fetchone()["n"]
    assert points == row["points"]
    assert guilds == 1
    db.close()


def test_preview_seed_tops_up_existing_120_gold_without_changing_pin(tmp_path):
    db_path = str(tmp_path / "preview.db")
    init_empty_db(b, db_path)
    db = connect_db(db_path)
    cur = db.execute(
        "INSERT INTO kids (name, username, points, level, experience, starter_granted) "
        "VALUES ('Preview', ?, 120, 1, 0, 1)",
        (b.PREVIEW_KID_USERNAME,),
    )
    kid_id = cur.lastrowid
    db.execute(
        "INSERT INTO kid_auth (kid_id, pin) VALUES (?, ?)",
        (kid_id, b.hash_password("existing-pin")),
    )
    db.commit()
    info = b.ensure_preview_kid(db)
    assert info["created"] is False
    row = db.execute(
        "SELECT points, level, experience FROM kids WHERE id=?", (kid_id,)
    ).fetchone()
    assert row["points"] >= 200
    assert row["points"] == 200
    assert row["level"] >= 2
    assert b.has_active_guild(kid_id, db)
    pin = db.execute(
        "SELECT pin FROM kid_auth WHERE kid_id=?", (kid_id,)
    ).fetchone()["pin"]
    assert b.verify_password("existing-pin", pin)
    assert not b.verify_password(b.PREVIEW_KID_PIN, pin)
    db.close()


def test_create_kid_preview_username_is_topped_up(client, test_db):
    from tests.factories import TEST_PARENT_PASSWORD, get_kid_points, make_parent
    from tests.test_onboard import _create_kid_as_parent

    parent = make_parent(
        client,
        username="test_preview_parent",
        password=TEST_PARENT_PASSWORD,
        name="Preview Parent",
        email="test_preview_parent@example.test",
    )
    r = _create_kid_as_parent(
        client, parent, username=b.PREVIEW_KID_USERNAME, name="Preview"
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    kid_id = (r.get_json() or {}).get("kid", {}).get("id")
    assert get_kid_points(test_db, kid_id) >= 200
    db = sqlite3.connect(test_db)
    db.row_factory = sqlite3.Row
    assert b.has_active_guild(kid_id, db)
    level = db.execute("SELECT level FROM kids WHERE id=?", (kid_id,)).fetchone()["level"]
    assert level >= 2
    db.close()


def test_preview_seed_unlocks_regions_1_to_3(tmp_path):
    db_path = str(tmp_path / "preview.db")
    init_empty_db(b, db_path)
    db = connect_db(db_path)
    info = b.ensure_preview_kid(db)
    row = db.execute(
        "SELECT points, level, experience FROM kids WHERE id=?",
        (info["kid_id"],),
    ).fetchone()
    assert row["level"] >= 6
    assert row["experience"] >= 375
    explored = {
        r["region_id"]
        for r in db.execute(
            "SELECT region_id FROM explored_regions WHERE kid_id=?",
            (info["kid_id"],),
        )
    }
    assert {1, 2}.issubset(explored)
    db.close()


def test_preview_battle_start_soft_v1_bodies(client, test_db):
    """preview_kid can start fixed soft-v1 fights including art-only 野豬."""
    db = connect_db(test_db)
    info = b.ensure_preview_kid(db)
    kid_id = info["kid_id"]
    db.close()

    login = client.post(
        "/api/auth/login",
        json={"username": b.PREVIEW_KID_USERNAME, "password": b.PREVIEW_KID_PIN},
    )
    assert login.status_code == 200, login.get_data(as_text=True)

    expected = {
        "boar": "野豬",
        "wolf": "野狼",
        "bear": "白熊",
        "scorpion": "巨蠍",
    }
    for key, name in expected.items():
        r = client.post(
            f"/api/kids/{kid_id}/expedition/battle-start",
            json={"region_id": 1, "preview_monster": key},
        )
        assert r.status_code == 201, (key, r.get_data(as_text=True))
        data = r.get_json()
        assert len(data["monsters"]) == 1
        m = data["monsters"][0]
        assert m["name"] == name
        assert m["sprite"]
        # battle-start auto-abandons a prior running battle for this kid


def test_preview_monster_ignored_for_normal_kid(battle_client, battle_kid):
    """Real kids ignore preview_monster and still fight the region monster."""
    r = battle_client.post(
        f"/api/kids/{battle_kid['id']}/expedition/battle-start",
        json={"region_id": 1, "preview_monster": "boar"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    assert r.get_json()["monsters"][0]["name"] == "野狼"
