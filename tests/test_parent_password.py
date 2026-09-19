"""P0-TC-PWD-* — parent passwords must be salted (not raw SHA-256)."""
import hashlib

import pytest

import backend_v2 as b
from tests.factories import connect_db, fetchone, login_as, response_text

pytestmark = [pytest.mark.phase0]


def _looks_salted(stored: str) -> bool:
    return stored.startswith("$2") or stored.startswith("$argon2")


@pytest.mark.case_id("P0-TC-PWD-01")
def test_parent_register_password_is_salted_not_sha256(client, test_db):
    """P0-TC-PWD-01 新家長 parents.password 唔等於 sha256(plaintext)。"""
    password = "CorrectHorse1"
    r = client.post(
        "/api/auth/parent-register",
        json={"username": "t_pa", "password": password, "name": "Salt Parent", "email": ""},
    )
    assert r.status_code == 201, response_text(r)
    row = fetchone(test_db, "SELECT password FROM parents WHERE username=?", ("t_pa",))
    stored = row["password"]
    sha = hashlib.sha256(password.encode()).hexdigest()
    assert stored != sha
    assert stored != password
    assert _looks_salted(stored), "hash must be bcrypt ($2) or argon2"
    hashed = b.hash_password(password)
    assert hashed != sha
    if hasattr(b, "verify_password"):
        assert b.verify_password(password, stored) is True
    login = login_as(client, "t_pa", password)
    assert login.status_code == 200, response_text(login)


@pytest.mark.case_id("P0-TC-PWD-02")
def test_parent_password_min_length_8_and_not_returned(client, test_db):
    """P0-TC-PWD-02 少過 8 字拒絕；成功回應無 password 欄。"""
    short = client.post(
        "/api/auth/parent-register",
        json={"username": "t_shortpw", "password": "abcd", "name": "Short"},
    )
    assert short.status_code == 400, response_text(short)

    ok = client.post(
        "/api/auth/parent-register",
        json={"username": "t_okpw", "password": "abcdefgh", "name": "Ok"},
    )
    assert ok.status_code == 201, response_text(ok)
    data = ok.get_json()
    body = response_text(ok)
    assert "password" not in data
    parent = data.get("parent") or {}
    assert "password" not in parent
    stored = fetchone(test_db, "SELECT password FROM parents WHERE username=?", ("t_okpw",))
    assert stored["password"] not in body


@pytest.mark.case_id("P0-TC-PWD-03")
def test_legacy_sha256_parent_rehashes_or_is_rejected(client, test_db):
    """P0-TC-PWD-03 舊 SHA-256 列 login 成功並 rehash 成 salted hash（企劃建議）。

    Locked strategy: successful login + one-time rehash. Plain SHA-256 must
    not remain the stored value after a successful login.
    """
    password = "oldpass12"
    sha = hashlib.sha256(password.encode()).hexdigest()
    db = connect_db(test_db)
    db.execute(
        "INSERT INTO parents (username, password, name, email) VALUES (?, ?, ?, ?)",
        ("t_legacy_pw", sha, "Legacy Parent", ""),
    )
    db.commit()
    db.close()

    r = login_as(client, "t_legacy_pw", password)
    assert r.status_code == 200, response_text(r)
    stored = fetchone(test_db, "SELECT password FROM parents WHERE username=?", ("t_legacy_pw",))["password"]
    assert stored != sha
    assert _looks_salted(stored)
