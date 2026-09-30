"""Old catalogs from git history, written only into a pytest temp database.

The tracked ``kids_town.db`` is a child's play progress. These helpers never
open it. They read ``backend_v2.py`` at ``afbc1a6`` through ``git show`` and
insert that seed into a path the caller already created under ``tmp_path``.
"""
from __future__ import annotations

import ast
import hashlib
import os
import subprocess
from contextlib import contextmanager

import backend_v2 as b

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKED_DB = os.path.realpath(os.path.join(REPO, "kids_town.db"))
OLD_SEED_REV = "afbc1a6"

_SOURCE = None


def tracked_sha256():
    """Read-only digest of the play database. Used to prove a test left it alone."""
    digest = hashlib.sha256()
    with open(TRACKED_DB, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refuse_tracked(path):
    real = os.path.realpath(path)
    if real == TRACKED_DB:
        raise RuntimeError(f"refusing to open tracked play database {real}")
    return real


def historical_source(rev=OLD_SEED_REV):
    global _SOURCE
    if _SOURCE is None or _SOURCE[0] != rev:
        raw = subprocess.check_output(
            ["git", "show", f"{rev}:backend_v2.py"],
            cwd=REPO,
        )
        _SOURCE = (rev, raw.decode("utf-8"))
    return _SOURCE[1]


def _module_constants(tree):
    constants = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            constants[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return constants


def _assigned_list(tree, func_name, assign_name="defs"):
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != func_name:
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == assign_name:
                    return stmt.value
    raise AssertionError(f"{func_name} has no {assign_name} list in {OLD_SEED_REV}")


def _eval_expr(node, constants):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "None":
            return None
        if node.id in constants:
            return constants[node.id]
        raise AssertionError(f"unresolved seed name {node.id}")
    if isinstance(node, (ast.List, ast.Tuple)):
        values = tuple(_eval_expr(item, constants) for item in node.elts)
        return values
    return ast.literal_eval(node)


def historical_catalogs(rev=OLD_SEED_REV):
    """Return (building_rows, skill_rows_with_building_name) from the old seed.

    Building rows are the ``seed_building_defs`` tuples. Skill rows replace the
    historical ``bldg_def_id`` with that seed's building name so the caller can
    look the id up in whatever temp database it built.
    """
    tree = ast.parse(historical_source(rev))
    constants = _module_constants(tree)
    buildings = _eval_expr(_assigned_list(tree, "seed_building_defs"), constants)
    skills = _eval_expr(_assigned_list(tree, "seed_skill_defs"), constants)
    if not isinstance(buildings, tuple) or not isinstance(skills, tuple):
        raise AssertionError("historical seed lists did not parse")
    id_to_name = {}
    for index, row in enumerate(buildings, start=1):
        if len(row) != 9:
            raise AssertionError(f"building seed row {index} has length {len(row)}")
        id_to_name[index] = row[1]
    named_skills = []
    for row in skills:
        if len(row) != 11:
            raise AssertionError(f"skill seed row has length {len(row)}: {row!r}")
        name, icon, mp_cost, bldg_id, level_required, target, description, base_value, per_level, attr_scale, effect_type = row
        if bldg_id not in id_to_name:
            raise AssertionError(f"skill {name} points at missing building id {bldg_id}")
        named_skills.append(
            (
                name,
                icon,
                mp_cost,
                id_to_name[bldg_id],
                level_required,
                target,
                description,
                base_value,
                per_level,
                attr_scale,
                effect_type,
            )
        )
    return buildings, tuple(named_skills)


def build_historical_building_db(path):
    """Schema plus the afbc1a6 ``seed_building_defs`` rows, then ``migrate_db()``.

    ``path`` must be a new file under pytest's temp directory. The library row
    in that revision is ``task_bonus``. This never opens ``kids_town.db``.
    """
    from tests.factories import connect_db

    buildings, _skills = historical_catalogs()
    library = next((row for row in buildings if row[1] == "圖書館"), None)
    if library is None or library[5] != "task_bonus":
        raise AssertionError(f"{OLD_SEED_REV} library seed is not task_bonus: {library!r}")
    with use_temp_database(path):
        b.init_db()
        b.migrate_db()
        b.migrate_db_v3()
        b.migrate_db_v4()
    db = connect_db(refuse_tracked(path))
    db.execute("DELETE FROM building_defs")
    db.executemany(
        """
        INSERT INTO building_defs (
            icon, name, cost_gold, materials, effect, buff_type, buff_vals,
            max_level, unlock_region
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        list(buildings),
    )
    db.commit()
    planted = db.execute(
        "SELECT name, buff_type, effect FROM building_defs WHERE buff_type='task_bonus'"
    ).fetchall()
    db.close()
    if not planted:
        raise AssertionError("historical building seed did not insert task_bonus")
    with use_temp_database(path):
        b.migrate_db()
    return refuse_tracked(path)


@contextmanager
def use_temp_database(path):
    """Point ``migrate_db`` / ``init_db`` at ``path`` and reject any other file.

    ``sqlite3.connect`` inside ``backend_v2`` may only open this temp path.
    The tracked play database is refused even if ``DB_PATH`` is wrong.
    """
    real = refuse_tracked(path)
    old_path = b.DB_PATH
    old_connect = b.sqlite3.connect

    def guarded(target, *args, **kwargs):
        opened = refuse_tracked(target)
        if opened != real:
            raise RuntimeError(f"sqlite opened {opened}, expected temp database {real}")
        return old_connect(target, *args, **kwargs)

    b.DB_PATH = real
    b.sqlite3.connect = guarded
    try:
        yield real
    finally:
        b.sqlite3.connect = old_connect
        b.DB_PATH = old_path
