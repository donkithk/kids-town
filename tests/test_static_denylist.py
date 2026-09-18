"""P0-TC-STAT-* — static routes must not serve .db / .py / traversal."""
import pytest

import backend_v2 as b
from tests.factories import response_text

pytestmark = [pytest.mark.phase0]


def _is_sqlite_header(data: bytes) -> bool:
    return data.startswith(b"SQLite format 3")


@pytest.mark.case_id("P0-TC-STAT-01")
def test_static_route_does_not_serve_db_files(client, tmp_path, monkeypatch):
    """P0-TC-STAT-01 GET /kids/kids_town.db → 404（即使檔存在都唔 serve）。"""
    fake = tmp_path / "staticroot"
    fake.mkdir()
    (fake / "kids_town.db").write_bytes(b"SQLite format 3\x00phase0-fake")
    (fake / "foo.db").write_bytes(b"SQLite format 3\x00phase0-foo")
    monkeypatch.setattr(b, "HTML_DIR", str(fake))

    for url in ("/kids/kids_town.db", "/kids/foo.db"):
        r = client.get(url)
        assert r.status_code == 404, f"{url} -> {r.status_code}"
        assert not _is_sqlite_header(r.get_data()), f"{url} leaked sqlite header"


@pytest.mark.case_id("P0-TC-STAT-02")
def test_static_route_does_not_serve_python_source(client):
    """P0-TC-STAT-02 GET /kids/backend_v2.py → 404。"""
    r = client.get("/kids/backend_v2.py")
    assert r.status_code == 404, response_text(r)[:200]
    body = response_text(r)
    assert "def serve_kids_static" not in body

    r2 = client.get("/kids/tests/conftest.py")
    assert r2.status_code == 404, response_text(r2)[:200]
    assert "init_empty_db" not in response_text(r2)


@pytest.mark.case_id("P0-TC-STAT-03")
def test_static_path_traversal_and_double_extension_denied(client, tmp_path, monkeypatch):
    """P0-TC-STAT-03 .. 同雙副檔名不能讀源碼／DB。"""
    fake = tmp_path / "staticroot"
    fake.mkdir()
    (fake / "secret.db.png").write_bytes(b"SQLite format 3\x00disguised")
    monkeypatch.setattr(b, "HTML_DIR", str(fake))

    urls = (
        "/kids/%2e%2e/backend_v2.py",
        "/kids/backend_v2.py.txt",
        "/kids/secret.db.png",
        "/kids/../backend_v2.py",
    )
    for url in urls:
        r = client.get(url)
        assert r.status_code in (400, 404), f"{url} -> {r.status_code}"
        data = r.get_data()
        assert not _is_sqlite_header(data)
        assert b"def serve_kids_static" not in data


@pytest.mark.case_id("P0-TC-STAT-04")
def test_legitimate_static_assets_still_served(client):
    """P0-TC-STAT-04 GET /kids/ 或 index、/assets-c/ 圖仍可匿名讀。"""
    r = client.get("/kids/")
    if r.status_code != 200:
        r = client.get("/kids/index.html")
    assert r.status_code == 200, response_text(r)[:200]
    body = response_text(r)
    assert "1357" not in body
    assert "pin 清單" not in body.lower()

    img = client.get("/assets-c/house.png")
    assert img.status_code == 200
    assert img.headers.get("Content-Type", "").startswith("image/")
