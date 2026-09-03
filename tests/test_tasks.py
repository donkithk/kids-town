"""Task per-kid completion tests (TDD — RED first)."""
import sys, os, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_global_task(client, title='測試全體任務', points=15):
    r = client.post('/api/tasks', json={'title': title, 'points': points, 'kid_id': None})
    return r.get_json()['id']


def test_global_task_completion_is_per_kid(client, test_db):
    """全體任務嘅完成狀態應該每個小朋友獨立."""
    tid = _make_global_task(client)
    # kid 2 完成
    r = client.post(f'/api/tasks/{tid}/complete', json={'kid_id': 2})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['points_awarded'] == 15, "完成全體任務應該頒獎"
    # kid 2 見到已完成
    t2 = [t for t in client.get('/api/tasks?kid_id=2').get_json() if t['id'] == tid][0]
    assert t2['completed'] == 1, "kid 2 應該見到已完成"
    # kid 3 見到未完成 (獨立狀態)
    t3 = [t for t in client.get('/api/tasks?kid_id=3').get_json() if t['id'] == tid][0]
    assert t3['completed'] == 0, "kid 3 應該見到未完成"


def test_list_tasks_only_own_and_global(client, test_db):
    """list_tasks?kid_id=X 只返回 X 嘅任務 + 全體任務, 唔包其他小朋友."""
    db = sqlite3.connect(test_db)
    db.execute("DELETE FROM tasks WHERE title LIKE '範圍測試%'")
    db.commit()
    db.close()
    client.post('/api/tasks', json={'title': '範圍測試-小華', 'points': 10, 'kid_id': 2})
    client.post('/api/tasks', json={'title': '範圍測試-小美', 'points': 10, 'kid_id': 3})
    client.post('/api/tasks', json={'title': '範圍測試-全體', 'points': 10, 'kid_id': None})
    # kid 2 嘅任務列表
    tasks = client.get('/api/tasks?kid_id=2').get_json()
    titles = {t['title'] for t in tasks}
    assert '範圍測試-小華' in titles, "應該見到自己嘅任務"
    assert '範圍測試-全體' in titles, "應該見到全體任務"
    assert '範圍測試-小美' not in titles, "唔應該見到其他小朋友嘅任務"


def test_complete_global_task_awards_points(client, test_db):
    """完成全體任務應該頒獎俾完成嗰個小朋友."""
    tid = _make_global_task(client, '測試頒獎', 20)
    r = client.post(f'/api/tasks/{tid}/complete', json={'kid_id': 4})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['points_awarded'] == 20, "應該頒 20 分俾 kid 4"
