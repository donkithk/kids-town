"""Shared fixtures for battle integration tests.

Copies the real DB to a temp file so tests never mutate live data.
"""
import os, shutil, sys, sqlite3
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def test_db(tmp_path):
    """Copy real DB to temp, point backend_v2.DB_PATH at it."""
    import backend_v2 as b
    src = os.path.join(REPO, 'kids_town.db')
    dst = str(tmp_path / 'test_kids_town.db')
    shutil.copy2(src, dst)

    # clean any running expeditions + daily/boss/pity so tests start clean
    db = sqlite3.connect(dst)
    db.execute('DELETE FROM expeditions WHERE status="running"')
    db.execute('DELETE FROM daily_battles')
    db.execute('DELETE FROM boss_progress')
    db.execute('DELETE FROM drop_pity')
    db.commit()
    db.close()

    old = b.DB_PATH
    b.DB_PATH = dst
    yield dst
    b.DB_PATH = old


@pytest.fixture()
def client(test_db):
    """Flask test client bound to the temp DB."""
    import backend_v2 as b
    b.app.config['TESTING'] = True
    with b.app.test_client() as c:
        yield c
