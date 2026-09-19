"""Task per-kid completion tests (TDD — RED first)."""
from tests.factories import TEST_KID_PIN, make_kid, make_parent


def _two_kids(client):
    parent = make_parent(client, username="test_task_parent", name="Task Parent")
    kid_a = make_kid(
        client, parent["id"], username="test_task_kid_a", name="Task Kid A", pin=TEST_KID_PIN
    )
    kid_b = make_kid(
        client, parent["id"], username="test_task_kid_b", name="Task Kid B", pin=TEST_KID_PIN
    )
    return kid_a, kid_b


def _make_global_task(client, title="測試全體任務", points=15):
    r = client.post("/api/tasks", json={"title": title, "points": points, "kid_id": None})
    return r.get_json()["id"]


def test_global_task_completion_is_per_kid(client, test_db):
    """全體任務嘅完成狀態應該每個小朋友獨立."""
    kid_a, kid_b = _two_kids(client)
    tid = _make_global_task(client)
    r = client.post(f"/api/tasks/{tid}/complete", json={"kid_id": kid_a["id"]})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["points_awarded"] == 15, "完成全體任務應該頒獎"
    t2 = [t for t in client.get(f"/api/tasks?kid_id={kid_a['id']}").get_json() if t["id"] == tid][0]
    assert t2["completed"] == 1, "kid A 應該見到已完成"
    t3 = [t for t in client.get(f"/api/tasks?kid_id={kid_b['id']}").get_json() if t["id"] == tid][0]
    assert t3["completed"] == 0, "kid B 應該見到未完成"


def test_list_tasks_only_own_and_global(client, test_db):
    """list_tasks?kid_id=X 只返回 X 嘅任務 + 全體任務, 唔包其他小朋友."""
    kid_a, kid_b = _two_kids(client)
    client.post("/api/tasks", json={"title": "範圍測試-小華", "points": 10, "kid_id": kid_a["id"]})
    client.post("/api/tasks", json={"title": "範圍測試-小美", "points": 10, "kid_id": kid_b["id"]})
    client.post("/api/tasks", json={"title": "範圍測試-全體", "points": 10, "kid_id": None})
    tasks = client.get(f"/api/tasks?kid_id={kid_a['id']}").get_json()
    titles = {t["title"] for t in tasks}
    assert "範圍測試-小華" in titles, "應該見到自己嘅任務"
    assert "範圍測試-全體" in titles, "應該見到全體任務"
    assert "範圍測試-小美" not in titles, "唔應該見到其他小朋友嘅任務"


def test_complete_global_task_awards_points(client, test_db):
    """完成全體任務應該頒獎俾完成嗰個小朋友."""
    kid_a, _kid_b = _two_kids(client)
    tid = _make_global_task(client, "測試頒獎", 20)
    r = client.post(f"/api/tasks/{tid}/complete", json={"kid_id": kid_a["id"]})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["points_awarded"] == 20, "應該頒 20 分俾 kid A"
