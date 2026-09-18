"""P0-TC-LIST-* — kid list APIs are not a public roster."""
import pytest

from tests.factories import TEST_KID_PIN, TEST_PARENT_PASSWORD, login_as, response_text

pytestmark = [pytest.mark.phase0]


def _ids(payload):
    if isinstance(payload, dict):
        payload = payload.get("kids") or payload.get("data") or payload.get("items") or []
    return {item.get("id") for item in payload if isinstance(item, dict)}


def _assert_no_pin(payload, body):
    blob = str(payload).lower() + body.lower()
    assert "pin" not in blob or '"pin"' not in body.lower()
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                assert "pin" not in item
                assert "password" not in item


@pytest.mark.case_id("P0-TC-LIST-01")
def test_get_api_kids_is_not_a_public_full_list(client, family, app):
    """P0-TC-LIST-01 未登入 GET /api/kids 401；kid session 只見自己；家長只見 linked。"""
    anon = client.get("/api/kids")
    assert anon.status_code in (401, 403), response_text(anon)
    anon_data = anon.get_json(silent=True)
    assert not isinstance(anon_data, list)

    login_as(client, family.kid_a.username, TEST_KID_PIN)
    kid_r = client.get("/api/kids")
    assert kid_r.status_code == 200, response_text(kid_r)
    kid_body = response_text(kid_r)
    kid_data = kid_r.get_json()
    ids = _ids(kid_data)
    assert ids == {family.kid_a.id}
    assert family.kid_b.id not in ids
    _assert_no_pin(kid_data, kid_body)

    with app.test_client() as parent_client:
        login_as(parent_client, family.parent_a.username, TEST_PARENT_PASSWORD)
        parent_r = parent_client.get("/api/kids")
        assert parent_r.status_code == 200, response_text(parent_r)
        parent_ids = _ids(parent_r.get_json())
        assert parent_ids == {family.kid_a.id}
        assert family.kid_b.id not in parent_ids
        _assert_no_pin(parent_r.get_json(), response_text(parent_r))


@pytest.mark.case_id("P0-TC-LIST-02")
def test_parent_kids_ignores_forged_parent_id_query(client, family):
    """P0-TC-LIST-02 GET /api/auth/parent-kids?parent_id= 忽略 query，只用 session。"""
    login_as(client, family.parent_a.username, TEST_PARENT_PASSWORD)
    r = client.get(f"/api/auth/parent-kids?parent_id={family.parent_b.id}")
    if r.status_code == 403:
        return
    assert r.status_code == 200, response_text(r)
    ids = _ids(r.get_json())
    assert family.kid_b.id not in ids
    assert ids == {family.kid_a.id}
    _assert_no_pin(r.get_json(), response_text(r))
