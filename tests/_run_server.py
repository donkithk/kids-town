"""Test server launcher — runs backend_v2 on a dedicated port with a temp DB.

Usage: python _run_server.py <db_path> <port>

Does not copy production kids_town.db. If the given SQLite file already has
schema/rows (seeded by the pytest fixture), only DB_PATH is set.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backend_v2 as b
from tests.factories import init_empty_db

db_path = os.path.abspath(sys.argv[1])
port = int(sys.argv[2])
b.app.config["TESTING"] = True
# Keep fixture-seeded rows. Only bootstrap a brand-new empty file.
if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
    init_empty_db(b, db_path)
else:
    b.DB_PATH = db_path
b._clean_stale_expeditions()
print(f"Kids Town test server DB={db_path} port={port}", flush=True)
b.app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
