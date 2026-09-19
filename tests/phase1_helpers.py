"""Shared helpers for Phase 1 gameplay RED tests.

Test-only: empty-DB SQL seeds, synthetic logins, catalog constants.
Does not implement product buffs / fees / locks.
"""
from __future__ import annotations

from tests.factories import (
    TEST_KID_PIN,
    TEST_PARENT_PASSWORD,
    building_def_id,
    connect_db,
    login_as,
    logout,
    response_text,
)

# GAMEPLAY_REDESIGN §6.2
CANONICAL_MATERIALS = frozenset({"wood", "brick", "glass", "gear", "gem"})
OPTIONAL_FLAVOR_MATERIALS = frozenset({"fur", "dragon_scale"})
ALLOWED_DROP_MATERIALS = CANONICAL_MATERIALS | OPTIONAL_FLAVOR_MATERIALS
FORBIDDEN_DROP_MATERIALS = frozenset(
    {"iron", "star_shard", "star_fragment", "star_stone", "mystery_box"}
)

# GAMEPLAY_REDESIGN §6.5 short-explore gold fees (do not change in Phase 1.5)
EXPLORE_FEE_BY_REGION = {1: 10, 2: 20, 3: 30}

# GAMEPLAY_REDESIGN §6.6 / §7 / user-locked §9 Q4 — 入局包 (onboarding pack)
# Guild: 150 gold + wood×10 + brick×5, gear×0 (no gear key in materials JSON).
GUILD_COST_GOLD = 150
GUILD_COST_MATERIALS = {"wood": 10, "brick": 5}
# Starter pack on create-kid / new account: exact grant; flag starter_granted.
STARTER_POINTS = 120
STARTER_MATERIALS = {"wood": 8, "brick": 5}

BUILDING_NAMES = {
    "library": "圖書館",
    "gym": "健身室",
    "farm": "農場",
    "shop": "商店",
    "hospital": "醫院",
    "guild": "探險公會",
    "workshop": "工坊",
    "lighthouse": "燈塔",
    "arena": "競技場",
    "observatory": "天文台",
}


def def_id(test_db, key):
    return building_def_id(test_db, BUILDING_NAMES[key])


def login_kid(client, family):
    r = login_as(client, family.kid_a.username, TEST_KID_PIN)
    assert r.status_code == 200, response_text(r)
    return r


def login_parent(client, family):
    r = login_as(client, family.parent_a.username, TEST_PARENT_PASSWORD)
    assert r.status_code == 200, response_text(r)
    return r


def create_assigned_task(client, family, title, points=10, kid=None):
    """Parent creates a per-kid task, then switches session to that kid."""
    kid = kid or family.kid_a
    login_parent(client, family)
    r = client.post(
        "/api/tasks",
        json={"title": title, "points": points, "kid_id": kid.id, "icon": "✅"},
    )
    assert r.status_code in (200, 201), response_text(r)
    data = r.get_json()
    task_id = data.get("id") or (data.get("task") or {}).get("id")
    assert task_id, data
    login_as(client, kid.username, TEST_KID_PIN)
    return task_id


def json_or_text(r):
    data = r.get_json(silent=True)
    if data is None:
        return {"_raw": response_text(r)}
    return data


def error_code(r):
    data = json_or_text(r)
    return data.get("error")


def start_explore(client, kid_id, region_id, **extra):
    body = {
        "region_id": region_id,
        "expedition_type": "explore",
        "duration_hours": 0,
        "duration_minutes": 0,
    }
    body.update(extra)
    return client.post(f"/api/kids/{kid_id}/expedition/start", json=body)


def battle_start(client, kid_id, region_id):
    return client.post(
        f"/api/kids/{kid_id}/expedition/battle-start",
        json={"region_id": region_id},
    )


def place_building(client, kid_id, def_id_value, cell_x=0, cell_y=0):
    return client.post(
        f"/api/kids/{kid_id}/buildings",
        json={"def_id": def_id_value, "cell_x": cell_x, "cell_y": cell_y},
    )


def farm_claim(client, kid_id):
    return client.post(f"/api/kids/{kid_id}/farm/claim", json={})


def running_expedition_count(db_path, kid_id):
    db = connect_db(db_path)
    n = db.execute(
        "SELECT COUNT(*) AS n FROM expeditions WHERE kid_id=? AND status='running'",
        (kid_id,),
    ).fetchone()["n"]
    db.close()
    return n


def try_enable_require_approval(client, family, test_db):
    """Best-effort enable of GAMEPLAY_REDESIGN §6.7. Returns (ok, detail).

    Phase 2 dependency: product may not expose this yet. Callers must FAIL
    visibly rather than pytest.skip.
    """
    login_parent(client, family)
    payloads = [
        ("/api/settings", {"require_approval": True, "kid_id": family.kid_a.id}),
        ("/api/settings", {"family_settings": {"require_approval": True}}),
        ("/api/family/settings", {"require_approval": True}),
        ("/api/auth/family-settings", {"require_approval": True}),
        (
            f"/api/parents/{family.parent_a.id}/settings",
            {"approve_rewards": True, "require_approval": True},
        ),
    ]
    for path, body in payloads:
        r = client.post(path, json=body)
        if r.status_code in (200, 201, 204):
            data = r.get_json(silent=True) or {}
            if data.get("ok") or data.get("require_approval") or r.status_code in (201, 204):
                if path == "/api/settings" and body.get("kid_id") and "theme" in (
                    response_text(r).lower()
                ):
                    continue
                # Theme-only settings route is not approval. Detect via DB/columns below.
                pass

    db = connect_db(test_db)
    try:
        parent_cols = [row[1] for row in db.execute("PRAGMA table_info(parents)")]
        for col in ("approve_rewards", "require_approval"):
            if col in parent_cols:
                db.execute(
                    f"UPDATE parents SET {col}=1 WHERE id=?",
                    (family.parent_a.id,),
                )
                db.commit()
                return True, f"parents.{col}=1"
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        if "family_settings" in tables:
            cols = [row[1] for row in db.execute("PRAGMA table_info(family_settings)")]
            if "require_approval" in cols:
                existing = db.execute("SELECT 1 FROM family_settings LIMIT 1").fetchone()
                if existing:
                    db.execute("UPDATE family_settings SET require_approval=1")
                else:
                    db.execute(
                        "INSERT INTO family_settings (require_approval) VALUES (1)"
                    )
                db.commit()
                return True, "family_settings.require_approval=1"
    finally:
        db.close()
    return False, "no require_approval setting API or column (Phase 2 / GAMEPLAY_REDESIGN §6.7)"


def logout_client(client):
    client.post("/api/auth/logout")
    logout(client)
