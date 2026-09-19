"""P1-TC-REG-* — regions 4–5 locked with region_locked (GAMEPLAY_REDESIGN §6.3)."""
import pytest

import backend_v2 as b
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
    json_or_text,
    login_kid,
    running_expedition_count,
    start_explore,
)

pytestmark = [pytest.mark.phase1]


def _ready_explorer(test_db, family, points=50):
    kid_id = family.kid_a.id
    insert_building(test_db, kid_id, def_id(test_db, "guild"), level=1, stored=0, cell_x=6, cell_y=0)
    set_kid_level(test_db, kid_id, 20, experience=1000)
    set_kid_points(test_db, kid_id, points)
    return kid_id


@pytest.mark.case_id("P1-TC-REG-01")
def test_regions_1_2_3_battle_start_has_monsters_not_404(client, family, test_db):
    """P1-TC-REG-01 足夠等級時 region 1/2/3 battle-start 唔係 404 No monster。"""
    kid_id = _ready_explorer(test_db, family)
    login_kid(client, family)
    min_level = b.region_unlock_level(3)
    set_kid_level(test_db, kid_id, max(20, min_level), experience=1000)
    for region_id in (1, 2, 3):
        r = battle_start(client, kid_id, region_id)
        body = response_text(r)
        assert r.status_code != 404, body
        assert "No monster" not in body
        if r.status_code in (200, 201):
            data = json_or_text(r)
            assert data.get("monsters"), data
        else:
            assert r.status_code == 400, body


@pytest.mark.case_id("P1-TC-REG-02")
def test_region_4_battle_start_returns_region_locked(client, family, test_db):
    """P1-TC-REG-02 region 4 battle-start → 400 error=region_locked，唔係 404。"""
    kid_id = _ready_explorer(test_db, family)
    login_kid(client, family)
    before = running_expedition_count(test_db, kid_id)
    r = battle_start(client, kid_id, 4)
    assert r.status_code == 400, response_text(r)
    data = json_or_text(r)
    assert data.get("error") == "region_locked", data
    assert data.get("region_id") == 4, data
    assert running_expedition_count(test_db, kid_id) == before


@pytest.mark.case_id("P1-TC-REG-03")
def test_region_5_battle_start_returns_region_locked(client, family, test_db):
    """P1-TC-REG-03 region 5 同 REG-02。"""
    kid_id = _ready_explorer(test_db, family)
    login_kid(client, family)
    r = battle_start(client, kid_id, 5)
    assert r.status_code == 400, response_text(r)
    data = json_or_text(r)
    assert data.get("error") == "region_locked", data
    assert data.get("region_id") == 5, data


@pytest.mark.case_id("P1-TC-REG-04")
def test_region_4_explore_start_returns_region_locked(client, family, test_db):
    """P1-TC-REG-04 expedition/start region 4 explore → region_locked。"""
    kid_id = _ready_explorer(test_db, family, points=80)
    login_kid(client, family)
    gold_before = get_kid_points(test_db, kid_id)
    r = start_explore(client, kid_id, 4)
    assert r.status_code == 400, response_text(r)
    assert error_code(r) == "region_locked"
    assert get_kid_points(test_db, kid_id) == gold_before
    assert running_expedition_count(test_db, kid_id) == 0
