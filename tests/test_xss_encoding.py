"""P0-TC-XSS-* — API round-trip for untrusted strings; frontend is manual."""
import pytest

import backend_v2 as b
from tests.factories import TEST_KID_PIN, TEST_PARENT_PASSWORD, login_as, response_text

pytestmark = [pytest.mark.phase0]

XSS_TITLE = "<script>alert(1)</script>"
XSS_NAME = "<img src=x onerror=alert(1)>"


def _escape_helper():
    for name in ("escape_html", "html_escape", "sanitize_html"):
        fn = getattr(b, name, None)
        if callable(fn):
            return name, fn
    return None, None


@pytest.mark.case_id("P0-TC-XSS-01")
def test_task_title_roundtrip_and_escape_helper_if_present(client, family, app):
    """P0-TC-XSS-01 標題含 script 時 JSON 係字串；前端渲染標手動（見 STATUS）。"""
    name, fn = _escape_helper()
    if fn is not None:
        escaped = fn(XSS_TITLE)
        assert "<script>" not in escaped
        assert "alert" in escaped or "&lt;script&gt;" in escaped

    with app.test_client() as setup:
        login_as(setup, family.parent_a.username, TEST_PARENT_PASSWORD)
        created = setup.post(
            "/api/tasks",
            json={"title": XSS_TITLE, "points": 5, "kid_id": family.kid_a.id},
        )
        assert created.status_code in (200, 201), response_text(created)

    login_as(client, family.kid_a.username, TEST_KID_PIN)
    listed = client.get(f"/api/tasks?kid_id={family.kid_a.id}")
    assert listed.status_code == 200, response_text(listed)
    titles = [t.get("title") for t in listed.get_json()]
    assert XSS_TITLE in titles or any("&lt;script&gt;" in (t or "") for t in titles)


@pytest.mark.case_id("P0-TC-XSS-02")
def test_kid_display_name_api_roundtrip(client, family, app):
    """P0-TC-XSS-02 kid.name 含 img onerror 時 API 一致；HUD 前端為手動。

    If create-kid rejects the special characters, 400 is also acceptable.
    """
    with app.test_client() as setup:
        login_as(setup, family.parent_a.username, TEST_PARENT_PASSWORD)
        r = setup.post(
            "/api/auth/create-kid",
            json={
                "parent_id": family.parent_a.id,
                "name": XSS_NAME,
                "username": "test_kid_xss",
                "pin": TEST_KID_PIN,
            },
        )
    if r.status_code == 400:
        return
    assert r.status_code == 201, response_text(r)
    kid = r.get_json()["kid"]
    assert kid["name"] == XSS_NAME or "&lt;img" in kid["name"]

    login_as(client, family.parent_a.username, TEST_PARENT_PASSWORD)
    listed = client.get("/api/kids")
    if listed.status_code in (401, 403):
        listed = client.get(f"/api/auth/parent-kids?parent_id={family.parent_a.id}")
    body = response_text(listed)
    assert "onerror=" in body or "&lt;img" in body or XSS_NAME in body
