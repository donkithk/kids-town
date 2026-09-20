# Phase 2 家長批核家課獎勵測試目錄（TDD GREEN）

> **狀態**：GREEN（產品碼已實作 `require_approval` 閘，預設 off）。`pytest -m phase2` = **10 passed**。對照表見 [`PHASE2_APPROVAL_STATUS.md`](PHASE2_APPROVAL_STATUS.md)。  
> **Marker**：`phase2`（`python -m pytest tests/ -m phase2 -v`）。  
> **企劃**：[`GAMEPLAY_REDESIGN.md`](../GAMEPLAY_REDESIGN.md) **§6.7**（可選家長批核先發獎；family setting，**預設 off**）。  
> **Fixture**：空庫 seed；factory 合成帳戶。**禁止** copy `kids_town.db`。**禁止**真實 PIN。  
> **產品碼**：GREEN PR 實作 `parents.require_approval`、`/approve`、`/reject`、管理頁待批列表。  
> **Phase 1 leftover**：`P1-TC-CER-03` 由 `phase1` **改標 `phase2`**（唔 silent-skip），而家同 APR-02／03 一齊綠。

Pytest 模組：`tests/test_approval.py`（API）、`tests/test_approval_ui.py`（可選 FE 契約）、`tests/test_task_ceremony.py::test_require_approval_defers_rewards_until_parent_approves`（CER-03）。Helper：`tests/phase1_helpers.py` 嘅 `try_enable_require_approval`。

---

## 用戶已拍板（對齊 §6.7）

| 項 | 決定 |
|----|------|
| 開關 | `family_settings.require_approval`（或 `parents.approve_rewards`），**預設 false** |
| 預設 **off** | homework/task `complete` **即時入帳**（維持 Phase 1 綠路徑） |
| 開啟 **on** | `complete` → pending；**唔**加金幣／XP／材料；JSON **預告** `points_awarded`／XP／`material_drops` 等 + `pending_approval=true` |
| 家長批准 | `POST /api/tasks/<id>/approve` → 先至按預告數量入帳 |
| 家長拒絕 | `reject` + 原因；任務回到**未完成**；仍然無獎勵 |
| **Out of scope** | 短征 `expedition/claim`、戰鬥掉落 **唔**受 `require_approval` 擋住 |

小朋友 UI：「✅ 做完喇！等爸爸媽媽確認就入帳」（仍有完成感）。家長：管理頁待辦列表；可一鍵批今日全部（FE；見下）。

---

## 同 Phase 1 leftover 嘅關係

| Case ID | 本目錄點處理 |
|---------|----------------|
| `P1-TC-CER-03` | **摺入** Phase 2：pytest marker `phase1` → `phase2`。行為 ≈ `P2-APR-02` + 批准入帳（`P2-APR-03`）。**禁止** `pytest.skip`。 |
| `P1-TC-CER-01` | 預設 `pending_approval is False`；**保持** `phase1` 綠 |

`pytest -m phase1` 唔再攜帶呢條故意紅。`pytest -m phase2` 先至見 CER-03／APR-*。

---

## A. 預設關閉（回歸 Phase 1）

### P2-APR-01 — 預設 off：complete 即時入帳

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-01 |
| **標題** | 家庭未開批核（預設 off）→ complete 即時入金幣／XP；`pending_approval=false` |
| **優先級** | P0 |
| **建議模組** | `tests/test_approval.py` |
| **前置** | 空庫；`family` fixture；**唔**呼叫 enable 批核；任務 points=10 指派 `kid_a` |
| **步驟** | `POST /api/tasks/{id}/complete`（kid session） |
| **預期** | 200；`pending_approval is False`；`kids.points` += `points_awarded`（=10）；`kids.experience` += `experience_total`（無圖書館時基礎 `max(5,10//2)=5`）；任務 `completed` 為真。現況（main）：**應綠**（Phase 1 行為）。 |

---

## B. 開啟後 complete 只 pending、唔入帳

### P2-APR-02 — on：complete 後經濟不變；JSON 預告 + pending

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-02 |
| **標題** | `require_approval=true` 時 complete 後金幣／XP／背包不變；`pending_approval=true`；預告欄位齊 |
| **優先級** | P0 |
| **建議模組** | `tests/test_approval.py` |
| **前置** | 家長 session 開批核（API 名以實作為準：`family_settings.require_approval` 或 `parents.approve_rewards`）。若 setting API／欄未做：**斷言失敗**，**唔好** `pytest.skip`。 |
| **步驟** | 1. 記錄 points／experience／inventory 2. kid `POST .../complete` |
| **預期** | 200；`pending_approval is True`；`points_awarded`、`experience_gained`、`experience_bonus`、`experience_total`、`material_drops` **仍然出現**（預告，方便 UI「等家長確認」）；DB 金幣／XP／inventory **同 complete 前一樣**。 |

現況（故意紅）：無 `require_approval` 欄／設定 API；complete 仍即時 `_apply_task_completion_rewards` 且 hardcode `pending_approval=False`。

---

### P2-APR-03 — on：approve 後入帳數量 = 預告

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-03 |
| **標題** | 批核開啟時 parent `POST /api/tasks/<id>/approve` → 金幣／XP／材料按 complete 預告入帳 |
| **優先級** | P0 |
| **建議模組** | `tests/test_approval.py` |
| **前置** | 同 APR-02；complete 已 pending |
| **步驟** | 家長 session `POST /api/tasks/{id}/approve`（body 可含 `kid_id`） |
| **預期** | 200 或 201；`kids.points` = complete 前 + `points_awarded`；`kids.experience` = complete 前 + `experience_total`；每個 `material_drops` 項 inventory +1。 |

現況（故意紅）：開唔到 `require_approval`；亦無 `POST /api/tasks/<id>/approve`。

---

### P2-APR-04 — on：reject → 任務未完成；仍然無獎勵

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-04 |
| **標題** | 家長 reject（可帶原因）後任務回到 incomplete；金幣／XP／背包仍係 complete 前 |
| **優先級** | P0 |
| **建議模組** | `tests/test_approval.py` |
| **前置** | 同 APR-02；complete 已 pending；**未** approve |
| **步驟** | 家長 `POST /api/tasks/{id}/reject` JSON 含 `reason`（例如 `not_done`） |
| **預期** | 2xx；`GET /api/tasks?kid_id=` 該任務 `completed` 為假／0；points／experience／inventory 仍 = complete 前。唔扣「從未發過」嘅獎。 |

現況（故意紅）：無 reject 路由。

---

## C. 批核閘唔綁探險／戰鬥

### P2-APR-05 — on：短征 claim／戰鬥仍然即時發獎

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-05 |
| **標題** | `require_approval` 開住：expedition claim 同 battle win **唔使**家長 approve 都入帳；家課 complete 仍然 pending |
| **優先級** | P0 |
| **建議模組** | `tests/test_approval.py` |
| **前置** | 批核已開；有未存倉公會；區 1 |
| **步驟** | 1. 家課 complete（對照：唔入帳）2. 短征 start → 強制可 claim → `expedition/claim` 3. battle-start → 打贏（測試可把怪 HP 設低） |
| **預期** | 家課：`pending_approval=true`、經濟不變。claim：金幣或材料或 XP **有增加**（相對 claim 前）。battle win：金幣／XP／掉落 **有入帳**。**禁止**把短征／戰鬥掉落納入家長批核隊列。 |

---

## D. 寫入 API 負例（TDD_PROCESS §2.2）

### P2-APR-06 — 未登入不能批准／拒絕

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-06 |
| **標題** | 無 session 時 `POST .../approve` 同 `.../reject` → 401 |
| **優先級** | P0 |
| **建議模組** | `tests/test_approval.py` |
| **前置** | 已有指派任務；client **未** login |
| **步驟** | 匿名 POST approve、reject |
| **預期** | 兩個都 **401**。現況：**已綠**（Phase 0 session 閘喺路由未存在時都 401）。GREEN 加路由時**必須保持** 401。 |

---

### P2-APR-07 — IDOR：外人／小朋友不能批准

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-07 |
| **標題** | Parent B 或 Kid A session `POST .../approve` 自己家課 → **403** |
| **優先級** | P0 |
| **建議模組** | `tests/test_approval.py` |
| **前置** | 任務屬於 `kid_a`／家庭 A |
| **步驟** | 1. login `parent_b` → approve 2. login `kid_a` → approve |
| **預期** | 兩次 **403**；任務經濟不變。只有擁有該 kid 嘅家長（或 admin）可批。 |

---

## E. 可選前端

> 產品 UI 未做齊時，本 RED PR 用 **source 契約**；Playwright 真機待辦列 **STATUS 標手動 B**。故意紅 OK。**唔**加 `@pytest.mark.frontend`，以免 `pytest tests/test_frontend.py` 由 26 綠變紅。

### P2-APR-FE-01 — 小朋友見到等候文案

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-FE-01 |
| **標題** | `completeTask()` 喺 `pending_approval` 時顯示「✅ 做完喇！等爸爸媽媽確認就入帳」 |
| **優先級** | P1 |
| **建議模組** | `tests/test_approval_ui.py`（弱 source）；Playwright mock 可 GREEN 後補，標 `phase2` 而非 `frontend` |
| **前置** | `index.html` `completeTask` |
| **步驟** | 讀函數體 |
| **預期** | 含 `pending_approval` 分支同企劃原文案。現況：Phase 1 儀式已寫呢句 → **可能已綠**（契約）；真 API pending 仍靠 APR-02。 |

---

### P2-APR-FE-02 — 家長管理頁待批列表

| 欄 | 內容 |
|----|------|
| **ID** | P2-APR-FE-02 |
| **標題** | 家長 `renderManage`／管理頁有 pending 批核列表（可一鍵批今日） |
| **優先級** | P1 |
| **建議模組** | `tests/test_approval_ui.py` |
| **前置** | `index.html` 管理頁 |
| **步驟** | 掃 `renderManage`／`renderManageTasks` 同相關 HTML |
| **預期** | 有待批核隊列（`pending_approval`／`/approve`／「待批」等）；可呼叫 approve。現況（故意紅）：管理頁只有完成／未完成 filter，無批核待辦。**(B)** 真機：細路完成後家長見到待批、可批／拒。 |

---

## 手動／E2E 清單（雙重驗證 B — GREEN PR 先簽）

- [ ] 預設家庭：細路完成家課即時入金幣／XP／材料（同而家）
- [ ] 開啟批核：細路完成後 toast「等爸爸媽媽確認」；HUD 金幣／XP **唔即加**
- [ ] 家長管理頁見到待批；批准後 HUD 先加，數量同預告
- [ ] 拒絕後任務返未完成，金幣不變
- [ ] 批核開住：短征 claim、打贏戰鬥仍然即時入帳
- [ ] 一鍵批今日全部（若 GREEN 有做）

簽收格式見 `TDD_PROCESS.md`。本 RED PR 唔做 (B)。
