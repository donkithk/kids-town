"""P1-TC-XP-* — XP bar helpers / GET experience (GAMEPLAY_REDESIGN §6.4)."""
import pytest

import backend_v2 as b
from tests.factories import response_text
from tests.phase1_helpers import json_or_text, login_kid

pytestmark = [pytest.mark.phase1]


@pytest.mark.case_id("P1-TC-XP-01")
def test_calc_level_uses_exp_per_level_25():
    """P1-TC-XP-01 總經驗 0/24/25/75 對齊 EXP_PER_LEVEL=25 三角。"""
    assert b.EXP_PER_LEVEL == 25
    assert b.calc_level(0) == (1, 0)
    assert b.calc_level(24) == (1, 24)
    assert b.calc_level(25) == (2, 0)
    assert b.calc_level(75) == (3, 0)
    assert b.exp_for_next_level(1) == 25
    assert b.exp_for_next_level(2) == 50


@pytest.mark.case_id("P1-TC-XP-02")
def test_xp_bar_percent_uses_in_level_not_total():
    """P1-TC-XP-02 xp_bar_percent(in_level, for_next) = min(100, round(in/for_next*100))。"""
    assert hasattr(b, "xp_bar_percent"), (
        "backend_v2.xp_bar_percent(experience_in_level, experience_for_next) "
        "is required (GAMEPLAY_REDESIGN §6.4 / P1-TC-XP-02). "
        "Do not use total experience / (level*100)."
    )
    fn = b.xp_bar_percent
    assert fn(0, 25) == 0
    assert fn(25, 25) == 100
    assert fn(12, 25) == min(100, round(12 / 25 * 100))
    # for_next==0: catalog allows 100 or 0 — lock to 100 (full / no next bar).
    assert fn(0, 0) == 100
    assert fn(99, 0) == 100
    assert fn(40, 25) == 100


@pytest.mark.case_id("P1-TC-XP-03")
def test_get_experience_returns_hud_fields_not_500(client, family):
    """P1-TC-XP-03 GET /experience 有 in-level 欄位；唔 500（ability_atk KeyError）。"""
    login_kid(client, family)
    try:
        r = client.get(f"/api/kids/{family.kid_a.id}/experience")
    except Exception as exc:
        pytest.fail(
            f"GET /experience must not 500 / KeyError (ability_atk); got {type(exc).__name__}: {exc}"
        )
    assert r.status_code == 200, response_text(r)
    data = json_or_text(r)
    assert "experience_in_level" in data, data
    assert "experience_for_next" in data, data
    assert isinstance(data["experience_in_level"], int)
    assert isinstance(data["experience_for_next"], int)
    abilities = data.get("abilities") or {}
    assert "atk" not in abilities or abilities.get("str") is not None
