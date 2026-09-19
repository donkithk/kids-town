"""Test server launcher — runs backend_v2 on a dedicated port with a temp DB.

Usage: python _run_server.py <db_path> <port>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backend_v2 as b
from tests.factories import init_empty_db

init_empty_db(b, sys.argv[1])
port = int(sys.argv[2])
b._clean_stale_expeditions()
b.app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
