#!/usr/bin/env python3
"""Local town server for the A–C art review.

Uses a temporary SQLite file. Refuses the repo's kids_town.db.
Does not open a tunnel and does not change game rewards.

    python3 scripts/art_abc_preview_server.py

Then open http://127.0.0.1:9123/kids/?art=abc
Kid login: art_preview / 1357
Menu: 開啟美術預覽 / 關閉美術預覽
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import backend_v2 as backend
from tests.factories import init_empty_db, insert_kid

PORT = 9123
DB_PATH = os.environ.get("ART_PREVIEW_DB", "/tmp/kids-town-art-preview.db")
PROD_DB = os.path.join(ROOT, "kids_town.db")


def _refuse_prod(path: str) -> None:
    if os.path.abspath(path) == os.path.abspath(PROD_DB):
        raise SystemExit("refusing to open kids_town.db; set ART_PREVIEW_DB to another file")


def _place(db_path: str, kid_id: int, name: str, cell_x: int, cell_y: int) -> None:
    db = backend.sqlite3.connect(db_path)
    row = db.execute("SELECT id FROM building_defs WHERE name=?", (name,)).fetchone()
    if row is None:
        db.close()
        raise SystemExit(f"missing building def {name}")
    db.execute(
        "INSERT INTO buildings (kid_id, def_id, plot_idx, level, cell_x, cell_y, stored) "
        "VALUES (?, ?, 0, 1, ?, ?, 0)",
        (kid_id, row[0], cell_x, cell_y),
    )
    db.commit()
    db.close()


def main() -> int:
    _refuse_prod(DB_PATH)
    for suffix in ("", "-wal", "-shm"):
        extra = DB_PATH + suffix
        if os.path.exists(extra):
            os.remove(extra)
    init_empty_db(backend, DB_PATH)
    kid = insert_kid(
        DB_PATH,
        name="預覽",
        username="art_preview",
        pin="1357",
        level=8,
        points=800,
    )
    # Touching 2×2 footprints: gym at (0,0), guild at (2,0). No charge.
    _place(DB_PATH, kid["id"], "健身室", 0, 0)
    _place(DB_PATH, kid["id"], "探險公會", 2, 0)
    backend.DB_PATH = DB_PATH
    backend.app.config["TESTING"] = True
    print(f"art preview DB={DB_PATH} port={PORT}", flush=True)
    print("open http://127.0.0.1:%s/kids/?art=abc  login art_preview / 1357" % PORT, flush=True)
    backend.app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
