#!/usr/bin/env python3
"""Local town server for the A–C art review.

Uses a temporary SQLite file. Refuses the repo's kids_town.db.
Listens on 127.0.0.1 only. Does not open a tunnel.

    python3 scripts/art_abc_preview_server.py
    python3 scripts/art_abc_preview_server.py --port 9124
    ART_PREVIEW_PORT=9124 python3 scripts/art_abc_preview_server.py

Default port stays 9123. --port wins over ART_PREVIEW_PORT.
Then open http://127.0.0.1:<port>/kids/?art=abc
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import backend_v2 as backend
from tests.factories import init_empty_db, insert_kid

DEFAULT_PORT = 9123
DB_PATH = os.environ.get("ART_PREVIEW_DB", "/tmp/kids-town-art-preview.db")
PROD_DB = os.path.join(ROOT, "kids_town.db")


def resolve_port(argv=None) -> int:
    """9123 unless --port or ART_PREVIEW_PORT is set. --port wins."""
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    raw = args.port
    if raw is None:
        env = os.environ.get("ART_PREVIEW_PORT", "").strip()
        if env:
            try:
                raw = int(env)
            except ValueError:
                raise SystemExit("ART_PREVIEW_PORT must be an integer from 1 to 65535")
        else:
            raw = DEFAULT_PORT
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1 or raw > 65535:
        raise SystemExit("port must be an integer from 1 to 65535")
    return raw


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
    port = resolve_port()
    print(f"art preview DB={DB_PATH} port={port}", flush=True)
    print("open http://127.0.0.1:%s/kids/?art=abc" % port, flush=True)
    backend.app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
