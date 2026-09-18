"""Auth tests: 家長建立仔女帳戶 (TDD — RED first)."""
from tests.factories import TEST_KID_PIN, login_as, make_kid, make_parent


def test_parent_create_kid_full_flow(client, test_db):
    """家長可以建立仔女帳戶, 之後仔女可以用 username+PIN 登入."""
    parent = make_parent(client, username="test_auth_parent", name="Auth Parent")
    r = client.post(
        "/api/auth/create-kid",
        json={
            "parent_id": parent["id"],
            "name": "測試小朋友",
            "username": "testkid",
            "pin": TEST_KID_PIN,
        },
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    d = r.get_json()
    assert d["kid"]["name"] == "測試小朋友"
    assert d["kid"]["username"] == "testkid"

    r2 = client.post("/api/auth/login", json={"username": "testkid", "password": TEST_KID_PIN})
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json()["role"] == "kid"

    login_as(client, parent["username"], parent["password"])
    r3 = client.get(f"/api/auth/parent-kids?parent_id={parent['id']}")
    kids = r3.get_json()
    assert any(k["username"] == "testkid" for k in kids), "家長應該關聯到新仔女"


def test_parent_create_kid_duplicate_username(client, test_db):
    """重複 username 應該拒絕 (409)."""
    parent = make_parent(client, username="test_auth_parent2", name="Auth Parent 2")
    make_kid(client, parent["id"], username="testkid_dup", name="First", pin=TEST_KID_PIN)
    r = client.post(
        "/api/auth/create-kid",
        json={
            "parent_id": parent["id"],
            "name": "重複",
            "username": "testkid_dup",
            "pin": TEST_KID_PIN,
        },
    )
    assert r.status_code == 409, r.get_data(as_text=True)


def test_parent_create_kid_short_pin(client, test_db):
    """PIN 太短應該拒絕 (400)."""
    parent = make_parent(client, username="test_auth_parent3", name="Auth Parent 3")
    r = client.post(
        "/api/auth/create-kid",
        json={
            "parent_id": parent["id"],
            "name": "短PIN",
            "username": "testkid_shortpin",
            "pin": "12",
        },
    )
    assert r.status_code == 400, r.get_data(as_text=True)
