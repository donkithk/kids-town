"""Empty-DB factories and test-only credentials for Kids Town.

Synthetic users only. Never copy production kids_town.db. Never use live
family usernames (donkit, matthew, kid, kid1, kid2) or live PINs.
"""
from __future__ import annotations

import sqlite3

# Test-only credentials (not production). Used by Phase 0 fixtures.
TEST_ADMIN_USERNAME = "test-admin"
TEST_ADMIN_PASSWORD = "TestAdmin!pass1"
TEST_PARENT_PASSWORD = "TestParent!pass1"
TEST_KID_PIN = "1357"


def connect_db(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def ensure_app_schema(db_path):
    """Add columns the live schema has but init_db() does not create.

    This is a test-only schema helper so Flask routes can boot on an empty DB.
    It is not a product security fix.
    """
    db = connect_db(db_path)
    bcols = [r[1] for r in db.execute("PRAGMA table_info(buildings)")]
    if "cell_x" not in bcols:
        db.execute("ALTER TABLE buildings ADD COLUMN cell_x INTEGER DEFAULT 0")
    if "cell_y" not in bcols:
        db.execute("ALTER TABLE buildings ADD COLUMN cell_y INTEGER DEFAULT 0")
    if "stored" not in bcols:
        db.execute("ALTER TABLE buildings ADD COLUMN stored INTEGER DEFAULT 0")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER DEFAULT 0,
            category TEXT DEFAULT 'adjustment',
            description TEXT DEFAULT '',
            reference_type TEXT,
            reference_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.commit()
    db.close()


def init_empty_db(backend_module, db_path):
    """Point backend_v2 at db_path and run init/migrate/seed (no production copy)."""
    backend_module.DB_PATH = db_path
    backend_module.init_db()
    backend_module.migrate_db()
    backend_module.migrate_db_v3()
    backend_module.migrate_db_v4()
    backend_module.seed_building_defs()
    backend_module.seed_skill_defs()
    ensure_app_schema(db_path)
    return db_path


def login_as(client, username, password):
    """Log in through the unified auth API.

    After Phase 0 session work, Flask test_client keeps Set-Cookie. If a token
    is returned instead, attach it as Bearer. Tests assert desired 401/403 even
    when today's code has no session at all.
    """
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    data = r.get_json(silent=True) or {}
    token = data.get("token") or data.get("access_token") or data.get("session_token")
    if token:
        client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return r


def logout(client):
    jar = getattr(client, "_cookies", None) or getattr(client, "cookie_jar", None)
    if jar is not None and hasattr(jar, "clear"):
        jar.clear()
    if hasattr(client, "environ_base"):
        client.environ_base.pop("HTTP_AUTHORIZATION", None)


def make_parent(
    client,
    username="test_parent_a",
    password=TEST_PARENT_PASSWORD,
    name="Test Parent A",
    email="test_parent_a@example.test",
):
    r = client.post(
        "/api/auth/parent-register",
        json={"username": username, "password": password, "name": name, "email": email},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    parent = r.get_json()["parent"]
    parent["password"] = password
    login_as(client, username, password)
    return parent


def make_kid(
    client,
    parent_id,
    username="test_kid_a",
    pin=TEST_KID_PIN,
    name="Test Kid A",
    avatar="👦",
):
    r = client.post(
        "/api/auth/create-kid",
        json={
            "parent_id": parent_id,
            "name": name,
            "username": username,
            "pin": pin,
            "avatar": avatar,
        },
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    kid = r.get_json()["kid"]
    kid["pin"] = pin
    return kid


def make_admin(
    db_path,
    username=TEST_ADMIN_USERNAME,
    password=TEST_ADMIN_PASSWORD,
    name="Test Admin",
    role="super_admin",
):
    import backend_v2 as b

    db = connect_db(db_path)
    db.execute(
        "INSERT INTO admins (username, password, name, role) VALUES (?, ?, ?, ?)",
        (username, b.hash_password(password), name, role),
    )
    db.commit()
    row = db.execute(
        "SELECT id, username, name, role FROM admins WHERE username=?", (username,)
    ).fetchone()
    db.close()
    return {"id": row["id"], "username": row["username"], "name": row["name"], "role": row["role"]}


def insert_kid(
    db_path,
    name="Battle Kid",
    username="test_battle_kid",
    pin=TEST_KID_PIN,
    level=20,
    points=0,
    experience=0,
):
    """Direct SQL kid for battle tests that do not go through create-kid."""
    import backend_v2 as b

    db = connect_db(db_path)
    cur = db.execute(
        "INSERT INTO kids (name, username, avatar, color, points, level, experience) "
        "VALUES (?, ?, '👦', '#3b82f6', ?, ?, ?)",
        (name, username, points, level, experience),
    )
    kid_id = cur.lastrowid
    db.execute("INSERT INTO kid_auth (kid_id, pin) VALUES (?, ?)", (kid_id, b.hash_password(pin)))
    db.commit()
    db.close()
    return {"id": kid_id, "username": username, "name": name, "level": level, "points": points}


def set_kid_points(db_path, kid_id, points):
    db = connect_db(db_path)
    db.execute("UPDATE kids SET points=? WHERE id=?", (points, kid_id))
    db.commit()
    db.close()


def get_kid_points(db_path, kid_id):
    db = connect_db(db_path)
    row = db.execute("SELECT points FROM kids WHERE id=?", (kid_id,)).fetchone()
    db.close()
    return row["points"] if row else None


def inventory_qty(db_path, kid_id, item_type):
    db = connect_db(db_path)
    row = db.execute(
        "SELECT quantity FROM inventory WHERE kid_id=? AND item_type=?",
        (kid_id, item_type),
    ).fetchone()
    db.close()
    return row["quantity"] if row else 0


def count_rows(db_path, table, where="1=1", params=()):
    db = connect_db(db_path)
    n = db.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", params).fetchone()["n"]
    db.close()
    return n


def fetchone(db_path, sql, params=()):
    db = connect_db(db_path)
    row = db.execute(sql, params).fetchone()
    db.close()
    return dict(row) if row else None


def response_text(r):
    return r.get_data(as_text=True)
