# 🧪 Kids Town E2E 功能測試案例（中文版）

> 自動化測試腳本：`e2e_functional_test.py`
> 執行方式：`python3 e2e_functional_test.py`

---

## TC-01：家長登入

| 項目 | 內容 |
|------|------|
| **目的** | 驗證小朋友 PIN 登入機制正常運作 |
| **步驟 1** | POST `/api/login` 傳入正確 PIN → 預期回傳 `ok: true` |
| **步驟 2** | POST `/api/login` 傳入錯誤 PIN → 預期回傳 403 + `error` |
| **驗證點** | 正確 PIN 可登入，錯誤 PIN 被拒絕 |

---

## TC-02：小朋友 CRUD

| 項目 | 內容 |
|------|------|
| **目的** | 驗證新增、修改、刪除小朋友功能正常 |
| **步驟 1** | POST `/api/kids` 新增小朋友 → 預期 201 + 有 id |
| **步驟 2** | GET `/api/kids` 檢查新小朋友出現喺列表 |
| **步驟 3** | PATCH `/api/kids/{id}` 修改名稱、頭像 → 預期更新成功 |
| **步驟 4** | DELETE `/api/kids/{id}` 刪除 → 預期 200 |
| **步驟 5** | GET `/api/kids` 確認已刪除 |

---

## TC-03：任務完成 → 金幣發放

| 項目 | 內容 |
|------|------|
| **目的** | 驗證完成任務後金幣正確發放俾小朋友 |
| **步驟 1** | POST `/api/tasks` 建立任務（指定小朋友 + 25 分） |
| **步驟 2** | POST `/api/tasks/{id}/complete` 完成任務 |
| **驗證點** | `points_awarded` = 任務設定分數（25） |
| **驗證點** | points_log 表有記錄該筆交易 |

---

## TC-04：重複任務（Daily / Weekly / Weekdays）

| 項目 | 內容 |
|------|------|
| **目的** | 驗證三種重複模式運作正確 |
| **步驟** | 分別建立 daily / weekly / weekdays 任務並完成 |
| **驗證點** | 每種模式完成後都有金幣獎勵（10分） |
| **驗證點** | 完成後任務仍然存在（唔會刪除），`completed=1` |
| **驗證點** | POST `/api/tasks/refresh-recurring` 回傳 200 |

---

## TC-05：積分手動調整

| 項目 | 內容 |
|------|------|
| **目的** | 驗證家長手動加/扣分功能 |
| **步驟 1** | POST `/api/kids/{id}/points/adjust` 加 50 分（附原因）→ 成功 |
| **步驟 2** | POST 扣 30 分（附原因）→ 成功 |
| **步驟 3** | POST 唔附原因 → 預期 400 + `Reason is required` |
| **驗證點** | 加減分後 balance 正確，冇原因會被拒絕 |

---

## TC-06：建築物 — 建造 + 升級

| 項目 | 內容 |
|------|------|
| **目的** | 驗證建築物建造、升級、刪除功能 |
| **步驟 1** | 確保小朋友有足夠金幣同材料 |
| **步驟 2** | POST `/api/kids/{id}/buildings` 起最平建築（plot 0） |
| **步驟 3** | GET `/api/kids/{id}/buildings` 確認建築出現 |
| **步驟 4** | POST 升級 Lv.2 → 驗證 level=2 |
| **步驟 5** | POST 升級 Lv.3 → 驗證 level=3 |
| **步驟 6** | DELETE 刪除建築 → 確認消失 |

---

## TC-07：探險 — 出發 + 領獎

| 項目 | 內容 |
|------|------|
| **目的** | 驗證探險系統完整流程 |
| **步驟 1** | POST `/api/kids/{id}/expedition/start` (region=1, duration=0) → 201 |
| **步驟 2** | POST `/api/kids/{id}/expedition/claim` 領獎 |
| **驗證點** | 領獎回傳 gold > 0 + materials |
| **驗證點** | 冇 running 探險時 claim → 400 + `No running expedition` |

---

## TC-08：成就系統

| 項目 | 內容 |
|------|------|
| **目的** | 驗證成就相關端點正常 |
| **步驟 1** | GET `/api/achievements/all` → list ✅ |
| **步驟 2** | GET `/api/kids/{id}/achievements` → list ✅ |
| **步驟 3** | GET `/api/leaderboard` → dict/list ✅ |

---

## TC-09：連續記錄（Streak）

| 項目 | 內容 |
|------|------|
| **目的** | 驗證 streak 端點正常 |
| **步驟** | GET `/api/kids/{id}/streak` |
| **驗證點** | 回傳 dict 包含 `current_streak` + `best_streak` |

---

## TC-10：城鎮 + 背包

| 項目 | 內容 |
|------|------|
| **目的** | 驗證 town/inventory/explored 端點正常 |
| **步驟 1** | GET `/api/kids/{id}/town` → 包含 kid, buildings, inventory |
| **步驟 2** | GET `/api/kids/{id}/inventory` → list |
| **步驟 3** | GET `/api/kids/{id}/explored` → list |

---

## TC-11：任務 CRUD（完整）

| 項目 | 內容 |
|------|------|
| **目的** | 驗證建立含全部欄位、編輯、刪除任務 |
| **步驟 1** | POST `/api/tasks` 含 title, points, kid_id, icon, category, description, recurring, due_date |
| **步驟 2** | PUT `/api/tasks/{id}` 修改 title, points, category |
| **步驟 3** | DELETE 刪除任務 |

---

## TC-12：活動紀錄

| 項目 | 內容 |
|------|------|
| **目的** | 驗證 activity log 正確認錄 |
| **步驟** | GET `/api/activity` |
| **驗證點** | 回傳 list，每項有 kid_name, amount, reason, created_at |

---

## TC-13：任務篩選

| 項目 | 內容 |
|------|------|
| **目的** | 驗證任務篩選功能正常 |
| **步驟 1** | GET `/api/tasks?kid_id={id}` → 全部屬於該小朋友 |
| **步驟 2** | GET `/api/tasks?completed=0` → 全部未完成 |
| **步驟 3** | GET `/api/tasks?search=test` → 搜尋結果 |

---

## TC-14：開發者儀表板

| 項目 | 內容 |
|------|------|
| **步驟** | GET `/api/dev-dashboard` |
| **驗證點** | 回傳 dict 且有內容 |

---

## TC-15：任務統計

| 項目 | 內容 |
|------|------|
| **步驟** | GET `/api/tasks/stats` |
| **驗證點** | 回傳 dict 包含 `overall`（total, completed, pending, completion_rate） |
| **驗證點** | 包含 `categories` 列表 |

---

## 已知 Bug 修復記錄

| Bug | 檔案 | 問題 | 修復 |
|-----|------|------|------|
| 🐛 Expedition 500 error | `backend_v2.py` claim_expedition | `datetime.utcnow()` offset-naive vs `fromisoformat('...Z')` offset-aware 無法比較 | 改用 `datetime.utcnow().replace(tzinfo=timezone.utc)` |

---

## 自動化監控

- **Cron job**: 每 30 分鐘自動執行 `e2e_functional_test.py`
- 全部 PASS 時靜默（唔 Send message）
- 有 FAIL 時 Telegram 通知
