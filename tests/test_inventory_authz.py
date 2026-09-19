"""P0-TC-INV-* — inventory/add is not a public or kid self-service endpoint."""
import pytest

from tests.factories import TEST_KID_PIN, inventory_qty, login_as, response_text

pytestmark = [pytest.mark.phase0]


@pytest.mark.case_id("P0-TC-INV-01")
def test_unauthenticated_inventory_add_returns_401(client, family, test_db):
    """P0-TC-INV-01 匿名 POST /api/kids/<id>/inventory/add 拒絕且數量不變。"""
    before = inventory_qty(test_db, family.kid_a.id, "wood")
    r = client.post(
        f"/api/kids/{family.kid_a.id}/inventory/add",
        json={"item_type": "wood", "quantity": 99},
    )
    assert r.status_code == 401, response_text(r)
    assert inventory_qty(test_db, family.kid_a.id, "wood") == before == 0


@pytest.mark.case_id("P0-TC-INV-02")
def test_kid_cannot_self_grant_inventory_returns_403(client, family, test_db):
    """P0-TC-INV-02 Kid A session 呼叫 inventory/add → 403（材料只經任務／探險／戰鬥）。"""
    before = inventory_qty(test_db, family.kid_a.id, "wood")
    login_as(client, family.kid_a.username, TEST_KID_PIN)
    r = client.post(
        f"/api/kids/{family.kid_a.id}/inventory/add",
        json={"item_type": "wood", "quantity": 50},
    )
    assert r.status_code == 403, response_text(r)
    assert inventory_qty(test_db, family.kid_a.id, "wood") == before
