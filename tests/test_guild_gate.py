"""P1-TC-GLD-* — server-side expedition guild gate (GAMEPLAY_REDESIGN §6.9)."""
import pytest

from tests.factories import (
    get_kid_points,
    insert_building,
    response_text,
    set_kid_level,
    set_kid_points,
)
from tests.phase1_helpers import (
    battle_start,
    def_id,
    error_code,
    login_kid,
    running_expedition_count,
    start_explore,
)

pytestmark = [pytest.mark.phase1]


@pytest.mark.case_id("P1-TC-GLD-01")
def test_explore_start_without_guild_returns_guild_required(client, family, test_db):
    """P1-TC-GLD-01 無探險公會時 expedition/start 400／403 guild_required。"""
    kid_id = family.kid_a.id
    set_kid_points(test_db, kid_id, 999)
    login_kid(client, family)
    r = start_explore(client, kid_id, 1)
    assert r.status_code in (400, 403), response_text(r)
    assert error_code(r) == "guild_required"
    assert running_expedition_count(test_db, kid_id) == 0
    assert get_kid_points(test_db, kid_id) == 999


@pytest.mark.case_id("P1-TC-GLD-02")
def test_battle_start_without_guild_returns_guild_required(client, family, test_db):
    """P1-TC-GLD-02 battle-start 同樣要公會（而家只靠前端 def_id===6）。"""
    kid_id = family.kid_a.id
    set_kid_level(test_db, kid_id, 20, experience=1000)
    set_kid_points(test_db, kid_id, 50)
    login_kid(client, family)
    r = battle_start(client, kid_id, 1)
    assert r.status_code in (400, 403), response_text(r)
    assert error_code(r) == "guild_required"
    assert running_expedition_count(test_db, kid_id) == 0


@pytest.mark.case_id("P1-TC-GLD-03")
def test_stored_guild_counts_as_no_guild(client, family, test_db):
    """P1-TC-GLD-03 stored=1 公會不能探險。"""
    kid_id = family.kid_a.id
    insert_building(
        test_db, kid_id, def_id(test_db, "guild"), level=1, stored=1, cell_x=6, cell_y=0
    )
    set_kid_points(test_db, kid_id, 50)
    login_kid(client, family)
    r = start_explore(client, kid_id, 1)
    assert r.status_code in (400, 403), response_text(r)
    assert error_code(r) == "guild_required"


@pytest.mark.case_id("P1-TC-GLD-04")
def test_unstored_guild_allows_explore_start(client, family, test_db):
    """P1-TC-GLD-04 有未存倉公會可以 start。"""
    kid_id = family.kid_a.id
    insert_building(
        test_db, kid_id, def_id(test_db, "guild"), level=1, stored=0, cell_x=6, cell_y=0
    )
    set_kid_points(test_db, kid_id, 15)
    login_kid(client, family)
    r = start_explore(client, kid_id, 1)
    assert r.status_code == 201, response_text(r)
