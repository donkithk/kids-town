# Frontend E2E test cases (Playwright)

> **Runner**: `tests/test_frontend.py` (sync Playwright, current venv `sys.executable`).  
> **Fixture**: empty SQLite + factories. **禁止** copy `kids_town.db`.  
> **Credentials**: synthetic only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`).  
> **Skip rule**: skip **only** if Playwright / Chromium cannot launch; reason must tell the operator to run `python -m playwright install chromium`.  
> **Install**: see [`README.md`](../../README.md) and [`docs/TDD_PROCESS.md`](../TDD_PROCESS.md) § frontend.

Status map after a run: [`FRONTEND_E2E_STATUS.md`](FRONTEND_E2E_STATUS.md).

共用前置（除另註）：

1. Session-scoped test server on a free port, `TESTING=True`, empty DB + seed.
2. Family A: parent `test_fe_parent` + kid `test_fe_kid` (`TestKid`, Lv.20, 探險公會).
3. Family B: parent `test_fe_parent_b` + kid `test_fe_other` (`OtherKid`).
4. Global task `做功課`. No default `admin` row.

---

## TC-FE-01 — 小朋友 PIN 登入見到城鎮 HUD

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_frontend.py` |
| **前置** | 合成 kid `test_fe_kid` / PIN fixture |
| **步驟** | 開 `/kids/` → 填登入名+PIN → 撳「🚪 登入」 |
| **預期** | 見到 HUD 名 `TestKid` 同 `Lv.`；登入畫面收埋；無預填 admin 密碼 |

---

## TC-FE-02 — 能力面板五屬性

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-02 |
| **步驟** | 登入後 hover 頭像 |
| **預期** | Tooltip 有「臂力」；冇「體力」 |

---

## TC-FE-03 — 戰鬥開戰見到怪物

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-03 |
| **步驟** | ☰ → 探索 → 戰鬥 → ⚔️ 戰鬥 |
| **預期** | 見到「野狼」；可以撳「攻擊」 |

---

## TC-FE-04 — Boss 召喚入口

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-04 |
| **步驟** | 進入戰鬥挑戰頁 |
| **預期** | 見到 Boss 按鈕 |

---

## TC-FE-05 — 戰鬥勝利顯示稀有度

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-05 |
| **步驟** | 打贏區域 1 |
| **預期** | 勝利畫面含 普通／稀有／珍貴／傳說 其中一個 |

---

## TC-FE-06 — 唔再標「即將開放」

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-06 |
| **步驟** | 打開主目錄 |
| **預期** | 冇「即將開放」 |

---

## TC-FE-07 — 家長註冊

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-07 |
| **步驟** | 登入頁 → 註冊 → 用戶名／≥8 字密碼／稱呼 → 建立帳戶 |
| **預期** | 見到成功訊息 |

---

## TC-FE-08 — 家長建立仔女

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-08 |
| **步驟** | 家長 A 登入管理頁 → 填名／登入名／PIN → 建立仔女 |
| **預期** | 新名出現喺小朋友管理列表 |

---

## TC-FE-09 — 任務列表隔離

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-09 |
| **步驟** | 插入「小美專屬任務」給 OtherKid；TestKid 登入開任務 tab |
| **預期** | 見到全體「做功課」；見唔到「小美專屬任務」 |

---

## FE-P0-01 — 未登入不能完成任務／改金幣

| 欄 | 內容 |
|----|------|
| **ID** | FE-P0-01 |
| **優先級** | P0 |
| **對應 API** | P0-TC-SESS-01、P0-TC-SESS-02 |
| **前置** | 未登入瀏覽器 context（無 session cookie） |
| **步驟** | 1. 開 `/kids/` 2. 確認登入頁、冇「完成」任務掣 3. 用同一 context `POST /api/kids/<id>/points`、`.../points/adjust`、`POST /api/tasks/<id>/complete` |
| **預期** | UI 停留登入頁；三個 API **401**；金幣不變 |

---

## FE-P0-02 — 登入成功唔展示明文 PIN

| 欄 | 內容 |
|----|------|
| **ID** | FE-P0-02 |
| **優先級** | P0 |
| **對應 API** | P0-TC-PIN-02 |
| **步驟** | 小朋友登入；讀 `/api/auth/login` JSON；讀可見頁面文字 |
| **預期** | HUD 出現；JSON 無 `pin`／`password` 鍵；body 同可見文字不含 fixture PIN；密碼欄 `type=password` |

---

## FE-P0-03 — 家長 A 不能管理家長 B 仔女

| 欄 | 內容 |
|----|------|
| **ID** | FE-P0-03 |
| **優先級** | P0 |
| **對應 API** | P0-TC-IDOR-05、P0-TC-LIST-01 |
| **前置** | 兩家庭已 seed |
| **步驟** | 家長 A 登入管理頁；檢查小朋友列表、積分調整／篩選下拉；再用 session cookie `POST .../kid_b/points/adjust` |
| **預期** | UI 只見 TestKid，不見 OtherKid；API **403**；B 金幣不變 |

---

## FE-P0-04 — 瀏覽器不能下載 DB／源碼

| 欄 | 內容 |
|----|------|
| **ID** | FE-P0-04 |
| **優先級** | P0 |
| **對應 API** | P0-TC-STAT-01、P0-TC-STAT-02 |
| **步驟** | `page.goto /kids/kids_town.db` 同 `/kids/backend_v2.py` |
| **預期** | HTTP **404**；body `not found`；無 SQLite header、無 `serve_kids_static` |

---

## FE-P0-05 — 預設 admin/admin123 失敗

| 欄 | 內容 |
|----|------|
| **ID** | FE-P0-05 |
| **優先級** | P0 |
| **對應 API** | P0-TC-ADM-01、P0-TC-ADM-03 |
| **前置** | 空庫（無 admin 行） |
| **步驟** | 開登入頁（密碼欄空白）→ 填 `admin` / `admin123` → 登入 |
| **預期** | 錯誤訊息；停留登入頁；`#app` 仍 `display:none`；錯誤文字不含密碼 |

---

## 點跑

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m pytest tests/test_frontend.py -v
```
