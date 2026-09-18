"""P0-TC-PTS-* — points cannot go negative; unauth/kid writes denied."""
import pytest

from tests.factories import (
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    count_rows,
    get_kid_points,
    login_as,
    response_text,
    set_kid_points,
)

pytestmark = [pytest.mark.phase0]


@pytest.mark.case_id("P0-TC-PTS-01")
def test_points_cannot_go_negative_without_auth_and_floor_at_zero(client, family, app, test_db):
    """P0-TC-PTS-01 匿名或 kid 對 POST .../points 負數被拒；家長合法扣分結餘 ≥ 0。"""
    set_kid_points(test_db, family.kid_a.id, 3)
    before_log = count_rows(test_db, "points_log", "kid_id=?", (family.kid_a.id,))

    anon = client.post(
        f"/api/kids/{family.kid_a.id}/points",
        json={"amount": -100, "reason": "hack"},
    )
    assert anon.status_code == 401, response_text(anon)
    assert get_kid_points(test_db, family.kid_a.id) == 3

    login_as(client, family.kid_a.username, TEST_KID_PIN)
    kid_r = client.post(
        f"/api/kids/{family.kid_a.id}/points",
        json={"amount": -100, "reason": "self"},
    )
    assert kid_r.status_code == 403, response_text(kid_r)
    assert get_kid_points(test_db, family.kid_a.id) == 3

    with app.test_client() as parent_client:
        login_as(parent_client, family.parent_a.username, TEST_PARENT_PASSWORD)
        adj = parent_client.post(
            f"/api/kids/{family.kid_a.id}/points/adjust",
            json={"amount": -100, "reason": "test"},
        )
        assert adj.status_code == 200, response_text(adj)
        assert get_kid_points(test_db, family.kid_a.id) == 0
        after_log = count_rows(test_db, "points_log", "kid_id=?", (family.kid_a.id,))
        assert after_log == before_log + 1


@pytest.mark.case_id("P0-TC-PTS-02")
def test_add_points_parent_negative_floors_at_zero(client, family, test_db):
    """P0-TC-PTS-02 若仍保留 POST .../points 給家長，負數結果 floor 0。"""
    set_kid_points(test_db, family.kid_a.id, 1)
    login_as(client, family.parent_a.username, TEST_PARENT_PASSWORD)
    r = client.post(
        f"/api/kids/{family.kid_a.id}/points",
        json={"amount": -50, "reason": "parent"},
    )
    if r.status_code in (404, 405):
        return
    assert r.status_code == 200, response_text(r)
    pts = get_kid_points(test_db, family.kid_a.id)
    assert pts == 0, f"points must floor at 0, got {pts}"
