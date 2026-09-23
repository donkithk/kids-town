#!/usr/bin/env python3
"""Ensure the Preview demo kid can fight soft-v1 wilderness monsters.

Unlocks regions 1–3 (Lv.6 + explored 1–2) and clears today's daily battle locks.
Safe to run more than once. Does not change other kids or an existing PIN.
See README "Preview demo kid".
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import backend_v2 as b


def main():
    b.init_db()
    b.migrate_db()
    b.migrate_db_v3()
    b.migrate_db_v4()
    b.seed_building_defs()
    b.seed_skill_defs()
    db = sqlite3.connect(b.DB_PATH)
    db.row_factory = sqlite3.Row
    info = b.ensure_preview_kid(db)
    db.close()
    print(
        f"preview_kid id={info['kid_id']} created={info['created']} "
        f"points>={b.PREVIEW_MIN_POINTS} guild=placed level>={b.PREVIEW_MIN_LEVEL} "
        f"explored=1,2 soft-v1=野豬/野狼/白熊/巨蠍"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
