"""Shared fixtures: empty seeded SQLite, never a copy of production kids_town.db."""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.factories import (  # noqa: E402
    TEST_ADMIN_PASSWORD,
    TEST_ADMIN_USERNAME,
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    init_empty_db,
    insert_kid,
    login_as,
    make_admin,
    make_kid,
    make_parent,
    set_kid_points,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def test_db(tmp_path):
    """Brand-new SQLite file: schema init + building/monster seed only."""
    import backend_v2 as b

    dst = str(tmp_path / "test_kids_town.db")
    old = b.DB_PATH
    init_empty_db(b, dst)
    yield dst
    b.DB_PATH = old


@pytest.fixture()
def app(test_db):
    import backend_v2 as b

    b.app.config["TESTING"] = True
    b.app.config["SECRET_KEY"] = "phase0-test-secret-not-for-production"
    return b.app


@pytest.fixture()
def client(app):
    """Unauthenticated Flask test client bound to the empty temp DB."""
    with app.test_client() as c:
        yield c


@pytest.fixture()
def family(app, test_db):
    """Two synthetic households: parent_a/kid_a and parent_b/kid_b."""
    with app.test_client() as setup:
        parent_a = make_parent(
            setup,
            username="test_parent_a",
            password=TEST_PARENT_PASSWORD,
            name="Test Parent A",
            email="test_parent_a@example.test",
        )
        kid_a = make_kid(
            setup,
            parent_a["id"],
            username="test_kid_a",
            pin=TEST_KID_PIN,
            name="Test Kid A",
        )
        parent_b = make_parent(
            setup,
            username="test_parent_b",
            password=TEST_PARENT_PASSWORD,
            name="Test Parent B",
            email="test_parent_b@example.test",
        )
        kid_b = make_kid(
            setup,
            parent_b["id"],
            username="test_kid_b",
            pin=TEST_KID_PIN,
            name="Test Kid B",
        )
    set_kid_points(test_db, kid_a["id"], 0)
    set_kid_points(test_db, kid_b["id"], 5)
    kid_a["points"] = 0
    kid_b["points"] = 5
    return SimpleNamespace(
        parent_a=SimpleNamespace(**parent_a),
        kid_a=SimpleNamespace(**kid_a),
        parent_b=SimpleNamespace(**parent_b),
        kid_b=SimpleNamespace(**kid_b),
        parent_password=TEST_PARENT_PASSWORD,
        kid_pin=TEST_KID_PIN,
    )


@pytest.fixture()
def battle_kid(test_db):
    """High-level synthetic kid for existing battle tests (no production id=4)."""
    return insert_kid(
        test_db,
        name="Battle Kid",
        username="test_battle_kid",
        pin=TEST_KID_PIN,
        level=20,
        points=100,
        experience=100,
    )


@pytest.fixture()
def test_admin(test_db):
    return make_admin(test_db)


# Re-export helpers so older tests can `from tests.conftest import login_as` if needed.
__all__ = [
    "TEST_ADMIN_PASSWORD",
    "TEST_ADMIN_USERNAME",
    "TEST_KID_PIN",
    "TEST_PARENT_PASSWORD",
    "login_as",
    "make_admin",
    "make_kid",
    "make_parent",
]
