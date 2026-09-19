"""P0-TC-ADM-* — default admin/admin123 must not work after install."""
import hashlib
import os
import re

import pytest

from tests.factories import connect_db, insert_kid, response_text

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

pytestmark = [pytest.mark.phase0]


@pytest.mark.case_id("P0-TC-ADM-01")
def test_fresh_db_has_no_default_admin_admin123(client, test_db):
    """P0-TC-ADM-01 migrate／seed 之後無預設 admin／admin123（或 login 必定失敗）。

    Choice (GAMEPLAY_REDESIGN / user-approved): a fresh install must not seed
    a usable admin/admin123. Login with those default creds must fail (401/403).
    """
    db = connect_db(test_db)
    rows = [dict(r) for r in db.execute("SELECT id, username, role FROM admins").fetchall()]
    db.close()
    default = [r for r in rows if r["username"] == "admin"]
    assert default == [], f"fresh DB must not seed username=admin, got {default}"

    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code in (401, 403, 404), response_text(r)
    data = r.get_json(silent=True) or {}
    assert data.get("role") != "admin"
    assert data.get("must_change_password") is not True or r.status_code != 200


@pytest.mark.case_id("P0-TC-ADM-02")
def test_legacy_default_admin_must_change_password_has_no_write(client, test_db):
    """P0-TC-ADM-02 若插入舊 hash／明文 admin123，login 只允許改密，唔發寫入權 session。"""
    digest = hashlib.sha256(b"admin123").hexdigest()
    db = connect_db(test_db)
    db.execute("DELETE FROM admins WHERE username='admin'")
    db.execute(
        "INSERT INTO admins (username, password, name, role) VALUES (?, ?, ?, ?)",
        ("admin", digest, "legacy-admin", "super_admin"),
    )
    db.commit()
    db.close()
    kid = insert_kid(test_db, username="test_adm02_kid", name="ADM02 Kid")

    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    data = r.get_json(silent=True) or {}
    # Allowed: reject, or 200 with must_change_password and no write session.
    if r.status_code == 200:
        assert data.get("must_change_password") is True, response_text(r)
        assert data.get("role") != "admin" or data.get("must_change_password") is True
    else:
        assert r.status_code in (401, 403), response_text(r)

    r2 = client.delete(f"/api/kids/{kid['id']}")
    assert r2.status_code in (401, 403), response_text(r2)
    still = connect_db(test_db).execute(
        "SELECT id FROM kids WHERE id=?", (kid["id"],)
    ).fetchone()
    assert still is not None, "legacy default admin must not delete kids"


@pytest.mark.case_id("P0-TC-ADM-03")
def test_login_forms_do_not_prefill_admin123():
    """P0-TC-ADM-03 前端 showAdminLogin／login 表單無 value=admin123；開機訊息唔印 Default admin。"""
    for rel in ("index.html", "index-legacy.html"):
        path = os.path.join(REPO, rel)
        text = open(path, encoding="utf-8").read()
        assert not re.search(
            r"loginPassword['\"]?\)\.value\s*=\s*['\"]admin123['\"]", text
        ), f"{rel} prefills admin123"
        assert 'value="admin123"' not in text, f"{rel} has password value=admin123"

    backend = open(os.path.join(REPO, "backend_v2.py"), encoding="utf-8").read()
    assert "Default admin:" not in backend
    assert "admin / admin123" not in backend
