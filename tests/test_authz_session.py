"""P0-TC-SESS-* and P0-TC-DEV-01 — write APIs require an authenticated session."""
import pytest

from tests.factories import (
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    count_rows,
    fetchone,
    get_kid_points,
    login_as,
    response_text,
)

pytestmark = [pytest.mark.phase0]


@pytest.mark.case_id("P0-TC-SESS-01")
def test_unauthenticated_post_points_returns_401(client, family, test_db):
    """P0-TC-SESS-01 無 session 時 POST /api/kids/<id>/points 拒絕。"""
    kid_id = family.kid_a.id
    before_log = count_rows(test_db, "points_log", "kid_id=?", (kid_id,))
    r = client.post(
        f"/api/kids/{kid_id}/points",
        json={"amount": 100, "reason": "hack"},
    )
    assert r.status_code == 401, response_text(r)
    assert get_kid_points(test_db, kid_id) == 0
    assert count_rows(test_db, "points_log", "kid_id=?", (kid_id,)) == before_log


@pytest.mark.case_id("P0-TC-SESS-02")
def test_unauthenticated_complete_task_returns_401(client, family, app, test_db):
    """P0-TC-SESS-02 無 session 時 POST /api/tasks/<id>/complete 拒絕。"""
    with app.test_client() as setup:
        login_as(setup, family.parent_a.username, TEST_PARENT_PASSWORD)
        created = setup.post(
            "/api/tasks",
            json={"title": "phase0-sess-02", "points": 10, "kid_id": family.kid_a.id},
        )
        assert created.status_code in (200, 201), response_text(created)
        task_id = created.get_json()["id"]
    r = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": family.kid_a.id})
    assert r.status_code == 401, response_text(r)
    row = fetchone(test_db, "SELECT completed FROM tasks WHERE id=?", (task_id,))
    assert row["completed"] == 0
    assert get_kid_points(test_db, family.kid_a.id) == 0


@pytest.mark.case_id("P0-TC-SESS-03")
def test_unauthenticated_create_kid_returns_401(client, family, test_db):
    """P0-TC-SESS-03 無 session 時 POST /api/auth/create-kid 拒絕（即使 body 有 parent_id）。"""
    before = count_rows(test_db, "kids")
    r = client.post(
        "/api/auth/create-kid",
        json={
            "parent_id": family.parent_a.id,
            "name": "X",
            "username": "t_x",
            "pin": "1234",
        },
    )
    assert r.status_code == 401, response_text(r)
    assert count_rows(test_db, "kids") == before


@pytest.mark.case_id("P0-TC-SESS-04")
def test_health_allows_anonymous_without_pii(client):
    """P0-TC-SESS-04 GET /api/health 無 session 仍 200，body 不含兒童名單／PIN／email。"""
    r = client.get("/api/health")
    assert r.status_code == 200, response_text(r)
    body = response_text(r).lower()
    data = r.get_json(silent=True) or {}
    assert "pin" not in body
    assert "email" not in body
    blob = str(data)
    assert "kids" not in blob.lower() or data.get("status") == "ok"
    assert data.get("status") == "ok"


@pytest.mark.case_id("P0-TC-DEV-01")
def test_dev_dashboard_denied_for_non_admin(client, family, app):
    """P0-TC-DEV-01 匿名同 kid／家長 session GET /api/dev-dashboard 401／403。"""
    anon = client.get("/api/dev-dashboard")
    assert anon.status_code in (401, 403), response_text(anon)
    anon_body = response_text(anon)
    assert "kid_details" not in anon_body

    login_as(client, family.kid_a.username, TEST_KID_PIN)
    kid_r = client.get("/api/dev-dashboard")
    assert kid_r.status_code in (401, 403), response_text(kid_r)
    assert "kid_details" not in response_text(kid_r)

    with app.test_client() as parent_client:
        login_as(parent_client, family.parent_a.username, TEST_PARENT_PASSWORD)
        parent_r = parent_client.get("/api/dev-dashboard")
        assert parent_r.status_code in (401, 403), response_text(parent_r)
        assert "kid_details" not in response_text(parent_r)
