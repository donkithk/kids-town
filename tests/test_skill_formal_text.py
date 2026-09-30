"""Formal skill copy and 營養餐 MP regen. Red where the current catalog disagrees.

Empty SQLite and synthetic kids only. Never opens the tracked kids_town.db.
Old rows come from a git worktree of afbc1a6 under /tmp.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

import backend_v2 as b
from tests.battle_truth import act, login_and_start, monster_hp, place, prepare_kid
from tests.factories import connect_db, response_text
from tests.historical_seed import tracked_sha256, use_temp_database
from tests.skill_menu_spec import (
    COLLOQUIAL_CHARS,
    MEAL_CAST_DAMAGE,
    MEAL_HOT_PER_TURN,
    MEAL_HOT_TURNS,
    NUTRITION_MEAL_MP_REGEN,
    SEEDED_SKILL_NAMES,
    colloquial_hits,
    mp_after_nutrition_meal,
)
from tests.test_skill_truth import _require, _tune

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_REV = "afbc1a6"
_RENAME = {"挑釁": "盾擊", "迴避": "疾風斬"}


def _formal_problem(name, description):
    hits = colloquial_hits(description)
    if not hits:
        return None
    return f"{name} description {description!r} contains colloquial {''.join(hits)}"


def _assert_formal(name, description):
    problem = _formal_problem(name, description)
    assert problem is None, problem


@pytest.fixture(scope="module")
def fresh_catalog(tmp_path_factory):
    """One fresh database: seed rows plus the battle UI's two description APIs."""
    dst = str(tmp_path_factory.mktemp("formal") / "fresh.db")
    old = b.DB_PATH
    b.app.config["TESTING"] = True
    b.app.config["SECRET_KEY"] = "formal-skill-text"
    from tests.factories import init_empty_db, insert_building, insert_kid, TEST_KID_PIN

    init_empty_db(b, dst)
    try:
        kid = insert_kid(dst, name="Formal Kid", username="test_formal_kid", pin=TEST_KID_PIN, level=20, points=50)
        db = connect_db(dst)
        buildings = db.execute("SELECT id, name FROM building_defs").fetchall()
        db.close()
        for index, row in enumerate(buildings):
            insert_building(dst, kid["id"], row["id"], level=5, cell_x=index % 8, cell_y=index // 8)
        with b.app.test_client() as client:
            login = client.post(
                "/api/auth/login",
                json={"username": kid["username"], "password": TEST_KID_PIN},
            )
            assert login.status_code == 200, response_text(login)
            listed = client.get(f"/api/kids/{kid['id']}/skills")
            assert listed.status_code == 200, response_text(listed)
            started = client.post(
                f"/api/kids/{kid['id']}/expedition/battle-start",
                json={"region_id": 1},
            )
            assert started.status_code == 201, response_text(started)
        db = connect_db(dst)
        seeded = {
            row["name"]: row["description"] or ""
            for row in db.execute("SELECT name, description FROM skill_defs").fetchall()
        }
        db.close()
        yield {
            "seed": seeded,
            "skills_api": {row["name"]: row.get("description") or "" for row in listed.get_json()},
            "battle_api": {
                row["name"]: row.get("description") or ""
                for row in (started.get_json().get("skills") or [])
            },
        }
    finally:
        b.DB_PATH = old


def _build_old_database(dest):
    """afbc1a6 schema, seeds, and one synthetic kid, via a /tmp worktree.

    Returns the pre-migration snapshot. Does not open the tracked play database
    or write the worktree's kids_town.db.
    """
    from tests.historical_seed import TRACKED_DB, refuse_tracked

    dest = refuse_tracked(dest)
    work = "/tmp/kt-afbc1a6-skill-menu"
    if os.path.exists(work):
        subprocess.check_call(["git", "worktree", "remove", "--force", work], cwd=REPO)
    subprocess.check_call(
        ["git", "worktree", "add", "--detach", work, OLD_REV],
        cwd=REPO,
    )
    work_db = os.path.join(work, "kids_town.db")
    work_digest = _sha256(work_db)
    play_digest = _sha256(TRACKED_DB)
    snapshot_path = dest + ".before.json"
    script = r"""
import json, os, sqlite3, sys
root, dest, snapshot_path = sys.argv[1], sys.argv[2], sys.argv[3]
root_real = os.path.realpath(root)
sys.path = [root] + [
    p for p in sys.path
    if p and os.path.realpath(p) != os.path.realpath("/workspace")
]
os.chdir(root)
import backend_v2 as old
if not os.path.realpath(old.__file__).startswith(root_real):
    raise SystemExit("imported " + old.__file__ + " instead of the worktree")
tracked = os.path.realpath(os.path.join(root, "kids_town.db"))
dest_real = os.path.realpath(dest)
if dest_real == tracked or dest_real.endswith("/kids_town.db"):
    raise SystemExit("refusing to write " + dest_real)
old.DB_PATH = dest_real
old.init_db()
old.migrate_db()
old.migrate_db_v3()
old.migrate_db_v4()
old.seed_building_defs()
old.seed_skill_defs()
db = sqlite3.connect(dest_real)
db.row_factory = sqlite3.Row
kid_cols = [row[1] for row in db.execute("PRAGMA table_info(kids)")]
values = {
    "name": "Formal Migrate Kid",
    "username": "test_formal_migrate_kid",
    "avatar": "boy",
    "color": "#3b82f6",
    "points": 40,
    "level": 12,
    "experience": 80,
}
row = {col: values[col] for col in kid_cols if col in values}
columns = list(row)
db.execute(
    "INSERT INTO kids (" + ", ".join(columns) + ") VALUES (" + ",".join("?" for _ in columns) + ")",
    [row[col] for col in columns],
)
kid_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
pin = old.hash_password("1357")
db.execute("INSERT INTO kid_auth (kid_id, pin) VALUES (?, ?)", (kid_id, pin))
wanted = {"健身室": 1, "競技場": 4, "探險公會": 4}
for name, level in wanted.items():
    bldg = db.execute("SELECT id FROM building_defs WHERE name=?", (name,)).fetchone()
    if not bldg:
        raise SystemExit("missing building " + name)
    db.execute(
        "INSERT INTO buildings (kid_id, def_id, plot_idx, level) VALUES (?, ?, 0, ?)",
        (kid_id, bldg["id"], level),
    )
learned = db.execute(
    "SELECT s.id, s.name FROM buildings b "
    "JOIN skill_defs s ON s.bldg_def_id = b.def_id AND s.level_required <= b.level "
    "WHERE b.kid_id = ? ORDER BY s.id",
    (kid_id,),
).fetchall()
db.execute(
    "CREATE TABLE IF NOT EXISTS kid_skills (kid_id INTEGER NOT NULL, skill_id INTEGER NOT NULL)"
)
for skill in learned:
    db.execute(
        "INSERT INTO kid_skills (kid_id, skill_id) VALUES (?, ?)",
        (kid_id, skill["id"]),
    )
db.commit()
kid_row = dict(db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone())
auth = dict(db.execute("SELECT kid_id, pin FROM kid_auth WHERE kid_id=?", (kid_id,)).fetchone())
pairs = [
    [row["kid_id"], row["skill_id"]]
    for row in db.execute(
        "SELECT kid_id, skill_id FROM kid_skills WHERE kid_id=? ORDER BY skill_id",
        (kid_id,),
    )
]
skills = [
    {"id": row["id"], "name": row["name"], "description": row["description"] or ""}
    for row in db.execute("SELECT id, name, description FROM skill_defs ORDER BY id")
]
db.close()
db = sqlite3.connect(dest_real)
db.execute("PRAGMA wal_checkpoint(FULL)")
db.close()
payload = {
    "kid_id": kid_id,
    "kid": {key: kid_row[key] for key in kid_row},
    "auth": auth,
    "learned": [{"id": row["id"], "name": row["name"]} for row in learned],
    "kid_skills": pairs,
    "skills": skills,
}
# sqlite rows may contain non-JSON types; stringify leftover objects.
def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).decode("utf-8", "replace")
    return value
with open(snapshot_path, "w", encoding="utf-8") as handle:
    json.dump(_clean(payload), handle, ensure_ascii=False)
"""
    try:
        proc = subprocess.run(
            [sys_executable(), "-c", script, work, dest, snapshot_path],
            cwd=work,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"old worktree seed failed ({proc.returncode})\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        if _sha256(work_db) != work_digest:
            raise AssertionError("worktree kids_town.db was written")
        if _sha256(TRACKED_DB) != play_digest:
            raise AssertionError("tracked kids_town.db changed while building the old db")
        with open(snapshot_path, encoding="utf-8") as handle:
            return json.load(handle)
    finally:
        subprocess.call(["git", "worktree", "remove", "--force", work], cwd=REPO)


def sys_executable():
    import sys

    return sys.executable


def _sha256(path):
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _apply_current_migrations(path):
    with use_temp_database(path):
        b.init_db()
        b.migrate_db()
        b.migrate_db_v3()
        b.migrate_db_v4()
        b.seed_building_defs()
        b.seed_skill_defs()


@pytest.fixture(scope="module")
def migrated_catalog(tmp_path_factory):
    """Old afbc1a6 database copied, then current init/migrations applied."""
    folder = tmp_path_factory.mktemp("migrated")
    original = str(folder / "old.db")
    play_before = tracked_sha256()
    snapshot = _build_old_database(original)
    assert tracked_sha256() == play_before
    copied = str(folder / "migrated.db")
    shutil.copy2(original, copied)
    _apply_current_migrations(copied)
    assert tracked_sha256() == play_before
    db = connect_db(copied)
    descriptions = {
        row["name"]: row["description"] or ""
        for row in db.execute("SELECT name, description FROM skill_defs").fetchall()
    }
    by_id = {
        row["id"]: dict(row)
        for row in db.execute("SELECT id, name, description FROM skill_defs").fetchall()
    }
    kid = dict(db.execute("SELECT * FROM kids WHERE id=?", (snapshot["kid_id"],)).fetchone())
    auth = dict(
        db.execute(
            "SELECT kid_id, pin FROM kid_auth WHERE kid_id=?",
            (snapshot["kid_id"],),
        ).fetchone()
    )
    pairs = [
        [row["kid_id"], row["skill_id"]]
        for row in db.execute(
            "SELECT kid_id, skill_id FROM kid_skills WHERE kid_id=? ORDER BY skill_id",
            (snapshot["kid_id"],),
        )
    ]
    db.close()
    return {
        "descriptions": descriptions,
        "by_id": by_id,
        "snapshot": snapshot,
        "kid": kid,
        "auth": auth,
        "kid_skills": pairs,
    }


@pytest.mark.case_id("TC-API-SKILL-FORMAL-COUNT")
def test_fresh_catalog_is_the_22_seeded_skills(fresh_catalog):
    """The fresh seed is exactly these 22 names, so each name is its own case."""
    assert len(SEEDED_SKILL_NAMES) == 22
    assert len(COLLOQUIAL_CHARS) == 10
    assert set(fresh_catalog["seed"]) == set(SEEDED_SKILL_NAMES), sorted(fresh_catalog["seed"])


@pytest.mark.case_id("TC-API-SKILL-FORMAL")
@pytest.mark.parametrize("skill_name", SEEDED_SKILL_NAMES, ids=list(SEEDED_SKILL_NAMES))
def test_seed_description_is_formal_written_chinese(fresh_catalog, skill_name):
    """Fresh skill_defs.description has none of the colloquial characters."""
    description = fresh_catalog["seed"].get(skill_name)
    assert description is not None, skill_name
    _assert_formal(skill_name, description)


@pytest.mark.case_id("TC-API-SKILL-FORMAL-API")
@pytest.mark.parametrize("skill_name", SEEDED_SKILL_NAMES, ids=list(SEEDED_SKILL_NAMES))
def test_battle_ui_api_description_is_formal(fresh_catalog, skill_name):
    """GET /skills and battle-start skills[].description stay formal.

    Those are the payloads the battle UI reads. Card text in the menu is
    checked by TC-FE-SKILLMENU-CARDS when the menu exists.
    """
    for source, rows in (
        ("GET /api/kids/<id>/skills", fresh_catalog["skills_api"]),
        ("battle-start skills", fresh_catalog["battle_api"]),
    ):
        assert skill_name in rows, f"{skill_name} missing from {source}"
        problem = _formal_problem(skill_name, rows[skill_name])
        assert problem is None, f"{source}: {problem}"
        assert rows[skill_name] == fresh_catalog["seed"][skill_name], (
            skill_name,
            source,
            rows[skill_name],
            fresh_catalog["seed"][skill_name],
        )


@pytest.mark.case_id("TC-API-SKILL-FORMAL-MIGRATE")
@pytest.mark.parametrize("skill_name", SEEDED_SKILL_NAMES, ids=list(SEEDED_SKILL_NAMES))
def test_migrated_description_is_formal(migrated_catalog, skill_name):
    """After current migrations of an afbc1a6 database, every description is formal."""
    description = migrated_catalog["descriptions"].get(skill_name)
    assert description is not None, (
        f"{skill_name} missing after migrating {OLD_REV}. "
        "seed_building_defs leaves a non-empty catalog untouched, so a building "
        "that old seed did not have (銀行) never appears, and seed_skill_defs "
        "then skips the skill that needs it."
    )
    _assert_formal(skill_name, description)


@pytest.mark.case_id("TC-API-SKILL-FORMAL-MIGRATE-KEEP")
def test_migrate_preserves_kid_row_and_learned_skill_ids(migrated_catalog):
    """The synthetic kid row and learned skill ids survive current migrations."""
    snapshot = migrated_catalog["snapshot"]
    kid = migrated_catalog["kid"]
    before = snapshot["kid"]
    for column, value in before.items():
        assert column in kid, column
        assert kid[column] == value, (column, kid[column], value)
    assert migrated_catalog["auth"]["pin"] == snapshot["auth"]["pin"]
    assert migrated_catalog["kid_skills"] == snapshot["kid_skills"]
    for learned in snapshot["learned"]:
        row = migrated_catalog["by_id"].get(learned["id"])
        assert row, learned
        assert row["name"] == _RENAME.get(learned["name"], learned["name"]), row
    assert "挑釁" not in migrated_catalog["descriptions"]
    assert "迴避" not in migrated_catalog["descriptions"]


def _open_meal(client, family, test_db, monkeypatch, *, ability_str=0):
    kid_id = family.kid_a.id
    prepare_kid(
        test_db,
        kid_id,
        level=20,
        points=200,
        ability_str=ability_str,
        ability_int=0,
        ability_crt=0,
    )
    place(test_db, kid_id, "guild", level=1, cell_x=6)
    place(test_db, kid_id, "farm", level=1, cell_x=2)
    started = login_and_start(client, family, kid_id, monkeypatch)
    assert started.status_code == 201, response_text(started)
    battle = started.get_json()
    assert int(battle.get("player_crt") or 0) == 0, battle.get("player_crt")
    assert int(battle["monsters"][0].get("def") or 0) == 0, battle["monsters"]
    return kid_id, battle


def _cast_meal(client, test_db, kid_id, battle, *, mp_before, hp_before=None):
    skill = _require(battle, "營養餐")
    max_hp = battle["player_max_hp"]
    if hp_before is None:
        hp_before = max_hp // 2
    _tune(
        test_db,
        kid_id,
        hp=5000,
        spd=50,
        player_def=999,
        player_crt=0,
        player_hp=hp_before,
        player_mp=mp_before,
    )
    cast = act(client, kid_id, "skill", skill_id=skill["id"])
    assert cast.status_code == 200, response_text(cast)
    body = cast.get_json()
    dealt = 5000 - monster_hp(body)
    return skill, body, dealt, hp_before


def _hot_ticks(client, kid_id, body):
    hp = body["player_hp"]
    ticks = []
    for _ in range(MEAL_HOT_TURNS + 1):
        step = act(client, kid_id, "attack")
        assert step.status_code == 200, response_text(step)
        payload = step.get_json()
        ticks.append(payload["player_hp"] - hp)
        assert payload["player_mp"] == body["player_mp"], payload["player_mp"]
        hp = payload["player_hp"]
    return ticks


@pytest.mark.case_id("TC-API-MEAL-MP-BALANCED")
def test_nutrition_meal_mp_regen_for_a_balanced_kid(client, family, test_db, monkeypatch):
    """Balanced kid: damage and HoT stay at the pinned main numbers, then MP regens.

    Captured on 3b0a48a, crit off, variance 0, abilities 0: damage 5, HoT 14.
    """
    kid_id, battle = _open_meal(client, family, test_db, monkeypatch, ability_str=0)
    assert battle["player_atk"] == 5, battle.get("player_atk")
    mp_before = 20
    skill, body, dealt, hp_before = _cast_meal(
        client, test_db, kid_id, battle, mp_before=mp_before
    )
    assert dealt == MEAL_CAST_DAMAGE["balanced"], (dealt, battle.get("player_atk"))
    assert body["player_hp"] == hp_before, body
    ticks = _hot_ticks(client, kid_id, body)
    assert ticks[:MEAL_HOT_TURNS] == [MEAL_HOT_PER_TURN] * MEAL_HOT_TURNS, ticks
    assert ticks[-1] == 0, ticks
    expected = mp_after_nutrition_meal(mp_before, skill["mp_cost"], battle["player_max_mp"])
    assert body["player_mp"] == expected, (
        f"actual {body['player_mp']}, want {expected} "
        f"(min(max_mp={battle['player_max_mp']}, {mp_before} - {skill['mp_cost']} "
        f"+ {NUTRITION_MEAL_MP_REGEN}))"
    )


@pytest.mark.case_id("TC-API-MEAL-MP-SKEWED")
def test_nutrition_meal_mp_regen_for_a_skewed_kid(client, family, test_db, monkeypatch):
    """Skewed kid (臂力 20): damage stays 35, HoT stays 14, MP uses the same formula."""
    kid_id, battle = _open_meal(client, family, test_db, monkeypatch, ability_str=20)
    assert battle["player_atk"] == 35, battle.get("player_atk")
    assert battle.get("player_str") == 20, battle.get("player_str")
    mp_before = 20
    skill, body, dealt, hp_before = _cast_meal(
        client, test_db, kid_id, battle, mp_before=mp_before
    )
    assert dealt == MEAL_CAST_DAMAGE["skewed"], (dealt, battle.get("player_atk"))
    assert body["player_hp"] == hp_before, body
    ticks = _hot_ticks(client, kid_id, body)
    assert ticks[:MEAL_HOT_TURNS] == [MEAL_HOT_PER_TURN] * MEAL_HOT_TURNS, ticks
    assert ticks[-1] == 0, ticks
    expected = mp_after_nutrition_meal(mp_before, skill["mp_cost"], battle["player_max_mp"])
    assert body["player_mp"] == expected, (
        f"actual {body['player_mp']}, want {expected} "
        f"(+ {NUTRITION_MEAL_MP_REGEN} after cost)"
    )


@pytest.mark.case_id("TC-API-MEAL-MP-CAP")
def test_nutrition_meal_mp_regen_caps_at_max_mp(client, family, test_db, monkeypatch):
    """When mp_before - cost + 5 exceeds max MP, MP ends exactly at max MP."""
    kid_id, battle = _open_meal(client, family, test_db, monkeypatch, ability_str=0)
    mp_before = battle["player_max_mp"]
    skill, body, dealt, _hp_before = _cast_meal(
        client, test_db, kid_id, battle, mp_before=mp_before
    )
    assert dealt == MEAL_CAST_DAMAGE["balanced"], dealt
    overflow = mp_before - int(skill["mp_cost"]) + NUTRITION_MEAL_MP_REGEN
    assert overflow > battle["player_max_mp"], (overflow, battle["player_max_mp"])
    expected = mp_after_nutrition_meal(mp_before, skill["mp_cost"], battle["player_max_mp"])
    assert expected == battle["player_max_mp"]
    assert body["player_mp"] == expected, (
        f"actual {body['player_mp']}, want max_mp {battle['player_max_mp']} "
        f"(uncapped would be {overflow})"
    )


def _meal_copy_problem(description):
    text = description or ""
    problems = []
    if "回復" not in text or "MP" not in text:
        problems.append(f"營養餐 description {text!r} must mention 回復 and MP")
    hit = _formal_problem("營養餐", text)
    if hit:
        problems.append(hit)
    return problems


@pytest.mark.case_id("TC-API-MEAL-MP-DESC")
def test_nutrition_meal_seed_description_mentions_mp_restore(fresh_catalog):
    """Seed and both battle-UI payloads say 營養餐 restores MP, in formal Chinese."""
    problems = []
    for source, text in (
        ("skill_defs", fresh_catalog["seed"].get("營養餐")),
        ("GET /skills", fresh_catalog["skills_api"].get("營養餐")),
        ("battle-start", fresh_catalog["battle_api"].get("營養餐")),
    ):
        problems.extend(f"{source}: {item}" for item in _meal_copy_problem(text))
    assert not problems, "; ".join(problems)


@pytest.mark.case_id("TC-API-MEAL-MP-DESC-MIGRATE")
def test_nutrition_meal_description_mentions_mp_after_migrate(migrated_catalog):
    """An old database, after current migrations, also describes the MP restore."""
    text = migrated_catalog["descriptions"].get("營養餐")
    problems = _meal_copy_problem(text)
    assert not problems, "; ".join(problems)


def test_colloquial_constant_is_the_locked_list():
    """The banned characters live in one constant."""
    assert COLLOQUIAL_CHARS == ("嘅", "咩", "啲", "唔", "冇", "係", "喺", "佢", "嘢", "畈")
    assert NUTRITION_MEAL_MP_REGEN == 5
