"""Auth tests: 家長建立仔女帳戶 (TDD — RED first)."""
import sys, os, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cleanup(db):
    db.execute("DELETE FROM kid_auth WHERE kid_id IN (SELECT id FROM kids WHERE username LIKE 'testkid%')")
    db.execute("DELETE FROM parent_kid WHERE kid_id IN (SELECT id FROM kids WHERE username LIKE 'testkid%')")
    db.execute("DELETE FROM kids WHERE username LIKE 'testkid%'")
    db.commit()


def test_parent_create_kid_full_flow(client, test_db):
    """家長可以建立仔女帳戶, 之後仔女可以用 username+PIN 登入."""
    db = sqlite3.connect(test_db)
    _cleanup(db)
    db.close()

    # 家長 (爸爸 id=7) 建立仔女
    r = client.post('/api/auth/create-kid', json={
        'parent_id': 7, 'name': '測試小朋友', 'username': 'testkid', 'pin': '1234'
    })
    assert r.status_code == 201, r.get_data(as_text=True)
    d = r.get_json()
    assert d['kid']['name'] == '測試小朋友'
    assert d['kid']['username'] == 'testkid'

    # 仔女可以用 username+PIN 登入
    r2 = client.post('/api/auth/login', json={'username': 'testkid', 'password': '1234'})
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json()['role'] == 'kid'

    # 家長關聯到呢個仔女
    r3 = client.get('/api/auth/parent-kids?parent_id=7')
    kids = r3.get_json()
    assert any(k['username'] == 'testkid' for k in kids), "家長應該關聯到新仔女"


def test_parent_create_kid_duplicate_username(client, test_db):
    """重複 username 應該拒絕 (409)."""
    db = sqlite3.connect(test_db)
    _cleanup(db)
    db.close()
    r = client.post('/api/auth/create-kid', json={
        'parent_id': 7, 'name': '重複', 'username': 'kid', 'pin': '1234'
    })
    assert r.status_code == 409, r.get_data(as_text=True)


def test_parent_create_kid_short_pin(client, test_db):
    """PIN 太短應該拒絕 (400)."""
    db = sqlite3.connect(test_db)
    _cleanup(db)
    db.close()
    r = client.post('/api/auth/create-kid', json={
        'parent_id': 7, 'name': '短PIN', 'username': 'testkid2', 'pin': '12'
    })
    assert r.status_code == 400, r.get_data(as_text=True)
