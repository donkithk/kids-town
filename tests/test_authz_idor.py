"""P0-TC-IDOR-* — authenticated actor cannot mutate another family's kid."""
import pytest

from tests.factories import (
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    count_rows,
    fetchone,
    get_kid_points,
    inventory_qty,
    login_as,
    response_text,
)

pytestmark = [pytest.mark.phase0]


@pytest.mark.case_id("P0-TC-IDOR-01")
def test_kid_cannot_add_points_to_other_kid_returns_403(client, family, test_db):
    """P0-TC-IDOR-01 Kid A session 對 kid B POST .../points → 403，B 金幣不變。"""
    login_as(client, family.kid_a.username, TEST_KID_PIN)
    r = client.post(
        f"/api/kids/{family.kid_b.id}/points",
        json={"amount": 999, "reason": "x"},
    )
    assert r.status_code == 403, response_text(r)
    assert get_kid_points(test_db, family.kid_b.id) == 5


@pytest.mark.case_id("P0-TC-IDOR-02")
def test_kid_cannot_adjust_sibling_points_returns_403(client, family, test_db):
    """P0-TC-IDOR-02 Kid A 呼叫 POST /api/kids/{kid_b}/points/adjust 拒絕。"""
    before = get_kid_points(test_db, family.kid_b.id)
    login_as(client, family.kid_a.username, TEST_KID_PIN)
    r = client.post(
        f"/api/kids/{family.kid_b.id}/points/adjust",
        json={"amount": -5, "reason": "punish"},
    )
    assert r.status_code == 403, response_text(r)
    assert get_kid_points(test_db, family.kid_b.id) == before


@pytest.mark.case_id("P0-TC-IDOR-03")
def test_parent_cannot_forge_parent_id_on_create_kid(client, family, test_db):
    """P0-TC-IDOR-03 Parent A 帶 parent_id=parent_b 去 create-kid／link-kid 失敗。"""
    login_as(client, family.parent_a.username, TEST_PARENT_PASSWORD)
    before_kids = count_rows(test_db, "kids")
    before_links = count_rows(
        test_db, "parent_kid", "parent_id=? AND kid_id=?", (family.parent_a.id, family.kid_b.id)
    )
    r = client.post(
        "/api/auth/create-kid",
        json={
            "parent_id": family.parent_b.id,
            "name": "Stolen",
            "username": "t_stolen",
            "pin": "2468",
        },
    )
    assert r.status_code == 403, response_text(r)
    assert count_rows(test_db, "kids") == before_kids

    r2 = client.post(
        "/api/auth/link-kid",
        json={"parent_id": family.parent_b.id, "kid_username": family.kid_b.username},
    )
    assert r2.status_code == 403, response_text(r2)
    assert (
        count_rows(
            test_db,
            "parent_kid",
            "parent_id=? AND kid_id=?",
            (family.parent_a.id, family.kid_b.id),
        )
        == before_links
    )


@pytest.mark.case_id("P0-TC-IDOR-04")
def test_kid_cannot_complete_other_kids_task_returns_403(client, family, app, test_db):
    """P0-TC-IDOR-04 Kid A complete 指定 kid_id=kid_b 嘅任務 → 403。"""
    with app.test_client() as setup:
        login_as(setup, family.parent_b.username, TEST_PARENT_PASSWORD)
        created = setup.post(
            "/api/tasks",
            json={"title": "phase0-idor-04", "points": 10, "kid_id": family.kid_b.id},
        )
        task_id = created.get_json()["id"]
    before_points = get_kid_points(test_db, family.kid_b.id)
    login_as(client, family.kid_a.username, TEST_KID_PIN)
    r1 = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": family.kid_b.id})
    assert r1.status_code == 403, response_text(r1)
    r2 = client.post(f"/api/tasks/{task_id}/complete", json={"kid_id": family.kid_a.id})
    assert r2.status_code == 403, response_text(r2)
    row = fetchone(test_db, "SELECT completed FROM tasks WHERE id=?", (task_id,))
    assert row["completed"] == 0
    assert get_kid_points(test_db, family.kid_b.id) == before_points


@pytest.mark.case_id("P0-TC-IDOR-05")
def test_parent_cannot_adjust_unlinked_kid_points_returns_403(client, family, test_db):
    """P0-TC-IDOR-05 Parent A 對 kid_b points/adjust → 403。"""
    before = get_kid_points(test_db, family.kid_b.id)
    login_as(client, family.parent_a.username, TEST_PARENT_PASSWORD)
    r = client.post(
        f"/api/kids/{family.kid_b.id}/points/adjust",
        json={"amount": 10, "reason": "gift"},
    )
    assert r.status_code == 403, response_text(r)
    assert get_kid_points(test_db, family.kid_b.id) == before


@pytest.mark.case_id("P0-TC-INV-03")
def test_kid_cannot_add_inventory_to_other_kid_returns_403(client, family, test_db):
    """P0-TC-INV-03 Kid A 對 kid_b inventory/add → 403。"""
    before = inventory_qty(test_db, family.kid_b.id, "wood")
    login_as(client, family.kid_a.username, TEST_KID_PIN)
    r = client.post(
        f"/api/kids/{family.kid_b.id}/inventory/add",
        json={"item_type": "wood", "quantity": 50},
    )
    assert r.status_code == 403, response_text(r)
    assert inventory_qty(test_db, family.kid_b.id, "wood") == before
