"""P0-TC-PIN-* — kid PIN must be hashed and never echoed."""
import pytest

from tests.factories import (
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    connect_db,
    fetchone,
    login_as,
    response_text,
)

pytestmark = [pytest.mark.phase0]


@pytest.mark.case_id("P0-TC-PIN-01")
def test_create_kid_stores_hashed_pin_not_plaintext(client, family, test_db):
    """P0-TC-PIN-01 create-kid 之後 kid_auth.pin ≠ 明文 PIN。"""
    pin = "2468"
    login_as(client, family.parent_a.username, TEST_PARENT_PASSWORD)
    r = client.post(
        "/api/auth/create-kid",
        json={
            "parent_id": family.parent_a.id,
            "name": "Hashed Pin Kid",
            "username": "test_kid_pin01",
            "pin": pin,
        },
    )
    assert r.status_code == 201, response_text(r)
    kid_id = r.get_json()["kid"]["id"]
    row = fetchone(test_db, "SELECT pin FROM kid_auth WHERE kid_id=?", (kid_id,))
    assert row is not None
    stored = row["pin"]
    assert stored != pin
    assert stored != "0000"
    assert stored.startswith("$2") or stored.startswith("$argon2"), "PIN must use a salted hash"
    login = client.post("/api/auth/login", json={"username": "test_kid_pin01", "password": pin})
    assert login.status_code == 200, response_text(login)
    assert login.get_json().get("role") == "kid"


@pytest.mark.case_id("P0-TC-PIN-02")
def test_login_response_does_not_echo_pin(client, family):
    """P0-TC-PIN-02 Kid／legacy login JSON 唔包含 pin／password。"""
    r = client.post(
        "/api/auth/login",
        json={"username": family.kid_a.username, "password": TEST_KID_PIN},
    )
    assert r.status_code == 200, response_text(r)
    data = r.get_json()
    body = response_text(r)
    assert "pin" not in data
    assert "password" not in data
    user = data.get("user") or {}
    assert "pin" not in user
    assert "password" not in user
    assert TEST_KID_PIN not in body

    legacy = client.post(
        "/api/login", json={"kid_id": family.kid_a.id, "pin": TEST_KID_PIN}
    )
    if legacy.status_code != 404:
        assert legacy.status_code == 200, response_text(legacy)
        legacy_data = legacy.get_json() or {}
        legacy_body = response_text(legacy)
        assert "pin" not in legacy_data
        assert "password" not in legacy_data
        assert TEST_KID_PIN not in legacy_body
        assert "0000" not in legacy_body


@pytest.mark.case_id("P0-TC-PIN-03")
def test_missing_kid_auth_does_not_insert_plaintext_0000(client, test_db):
    """P0-TC-PIN-03 只有 kids 行、無 kid_auth 時，login 失敗且 DB 唔新插入明文 0000。"""
    db = connect_db(test_db)
    cur = db.execute(
        "INSERT INTO kids (name, username, avatar, color) VALUES (?, ?, '👦', '#3b82f6')",
        ("No Auth Kid", "test_kid_noauth"),
    )
    kid_id = cur.lastrowid
    db.commit()
    db.close()

    r = client.post("/api/auth/login", json={"username": "test_kid_noauth", "password": "0000"})
    assert r.status_code in (401, 403), response_text(r)

    legacy = client.post("/api/login", json={"kid_id": kid_id, "pin": "0000"})
    assert legacy.status_code in (401, 403, 404), response_text(legacy)

    row = fetchone(test_db, "SELECT pin FROM kid_auth WHERE kid_id=?", (kid_id,))
    if row is not None:
        assert row["pin"] != "0000"
        assert row["pin"].startswith("$2") or row["pin"].startswith("$argon2")
    else:
        assert row is None
