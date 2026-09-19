# Frontend E2E test cases (Playwright)

> **Runner**: `tests/test_frontend.py` (sync Playwright, current venv `sys.executable`).  
> **Fixture**: empty SQLite + factories. **禁止** copy `kids_town.db`.  
> **Credentials**: synthetic only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`).  
> **Skip rule**: skip **only** if Playwright / Chromium cannot launch; reason must tell the operator to run `python -m playwright install chromium`.  
> **Install**: see [`README.md`](../../README.md) and [`docs/TDD_PROCESS.md`](../TDD_PROCESS.md) § frontend.

Status map after a run: [`FRONTEND_E2E_STATUS.md`](FRONTEND_E2E_STATUS.md).  
Experience C（真機體驗加固）: `TC-FE-CEREMONY-01`、`TC-FE-PLACE-SHOP-01`、`TC-FE-PLACE-BUILD-01`；(B) [`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md).

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

## TC-FE-06 — 戰鬥已上線：Boss 成本／confirm（唔再得「即將開放」）

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-06 |
| **優先級** | P0 |
| **建議模組** | `tests/test_frontend.py` |
| **步驟** | 1. 登入後打開主目錄，確認冇「即將開放」 2. 進入戰鬥挑戰頁 3. 見到 Boss 按鈕含 💎 成本 4. 撳 Boss 之後 **取消** confirm |
| **預期** | 選單／戰鬥頁冇「即將開放」；Boss 按鈕可見且含 💎；取消 confirm 之後唔會出現怪物名 |
| **備註** | 取代舊「只 assert 冇即將開放」淺 case。稀有度仍由 TC-FE-05 覆蓋。Harness `test_boss_button_shows_cost_and_confirm` 保留作回歸。 |

---

## TC-FE-10 — 區域每日戰鬥上限

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-10 |
| **優先級** | P1 |
| **建議模組** | `tests/test_frontend.py` |
| **前置** | 合成 kid；fixture 寫入今日 `daily_battles`（區域 1） |
| **步驟** | 戰鬥挑戰頁撳「⚔️ 戰鬥」 |
| **預期** | `POST .../battle-start` **400**；錯誤含「今日」；toast 提示今日已打過；唔進入戰鬥（冇 `.m-name`） |
| **備註** | 測而家已有嘅每日一區上限，**唔**發明 Phase 1 buff。 |

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

## FE-P0-06 — 登出後寫入 API → 401

| 欄 | 內容 |
|----|------|
| **ID** | FE-P0-06 |
| **優先級** | P0 |
| **對應 API** | P0-TC-SESS-05 |
| **前置** | 合成 kid／家長已 seed |
| **步驟** | 1. 小朋友登入 2. 主目錄撳「🚪 登出」 3. 同一 browser context `POST /api/kids/<id>/points`、`.../points/adjust`、`POST /api/tasks/<id>/complete` 4. 再用家長帳戶重做一次 |
| **預期** | UI 返登入牆（`#loginScreen` 可見、`#app` `display:none`）；三個 API **401**；金幣不變 |
| **產品 hook** | `POST /api/auth/logout`（清 Flask session）+ 主目錄「登出」掣。JS `logout()` 會 call 呢條 API，唔只清前端變數。 |

---

## TC-FE-JOURNEY-01 — 家長指派任務 → 小朋友完成

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-JOURNEY-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_frontend.py` |
| **前置** | 家長 A + 已 link 嘅 `test_fe_kid`；合成 PIN `1357`、家長密碼 `TestParent!pass1` |
| **步驟** | 1. 家長登入管理頁 2. 填任務名 `JOURNEY-洗碗`、分數 12、指定 TestKid → ＋ 新增 3. 小朋友登入 → 任務 tab 見到該任務 4. 撳「✅ 完成」 |
| **預期** | 家長列表見到新任務；小朋友見到同一標題；toast／文案有「任務完成」；`#hudCo` 金幣上升（至少 +12）；DB `completed=1` |
| **備註** | 呢 case 只保證金幣／「任務完成」。**金幣 + XP 數字 + 材料** 由 `TC-FE-CEREMONY-01` 覆蓋。 |

---

## TC-FE-CEREMONY-01 — 真實完成任務：金幣 + XP + 材料（唔 mock）

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-CEREMONY-01 |
| **優先級** | P0（體驗 C） |
| **建議模組** | `tests/test_frontend.py` |
| **對應** | P1-TC-CER-01（API）、P1-TC-CER-FE-01（mock／source） |
| **前置** | 空庫合成 `test_fe_kid`；插入專屬任務 `TC-FE-CEREMONY-洗碗` points=10。**唔** mock `/api/tasks/<id>/complete`。 |
| **步驟** | 1. 小朋友 PIN 登入 2. 任務 tab 撳「✅ 完成」 3. 截真實 complete JSON（`points_awarded`／`experience_total`／`material_drops`） 4. 讀 `#toast` 同 HUD（`#hudCo`、`#hdrRes .mat`） |
| **預期** | API 有 XP 同至少一項材料。可見回饋必須同時有：**金幣**（toast 🪙 或 HUD 上升）、**XP 數字**（toast／面板含 `XP+N`／經驗，唔可以淨係 XP 條）、**材料提示**（🪵／木材／wood／🧱… 或 HUD 對應格數量 +1）。**禁止**金幣-only 當綠。若產品只 toast 金幣，本 case **故意留紅**，唔好放寬斷言。 |
| **(A)/(B)** | Playwright 真實旅程 = 可自動化 (A)。真機細屏 toast `nowrap` 可能裁字 → **(B) 必須**（見 [`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md)）。唔好當 grep／mock 做齊 (A)。 |

---

## TC-FE-PLACE-SHOP-01 — 商店建造 → 放置 → 地圖出現建築

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-PLACE-SHOP-01 |
| **優先級** | P0（體驗 C） |
| **建議模組** | `tests/test_frontend.py` |
| **對應** | P1-TC-PLC-01（API）、P1-TC-PLC-FE-01（建築 tab source） |
| **前置** | 合成 kid；fixture 發夠金幣／材料；清走已有「圖書館」（保留探險公會） |
| **步驟** | 1. 登入 2. 底欄「背包」→ 🏪 建築商店 3. 圖書館「🏗️ 建造」（`shopBuild` → `startPlacement`） 4. 見到 `#placementBar.active` 5. 撳綠色 `.valid-plot` 空地 6. 「✅ 確認建造」 |
| **預期** | 進入放置態；確認後 `.town-building img[alt=圖書館]` 出現；DB 有該建築。產品空地係 2×2 `.valid-plot`（`.empty-cell` 喺放置態會被忽略）。 |
| **(A)/(B)** | Linux Chromium E2E = (A)。真機手指點格／確認仍要 (B)。 |

---

## TC-FE-PLACE-BUILD-01 — 建築 tab 建造 → 放置 → 地圖出現建築

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-PLACE-BUILD-01 |
| **優先級** | P0（體驗 C） |
| **建議模組** | `tests/test_frontend.py` |
| **對應** | P1-TC-PLC-FE-01（弱 source twin；本 case 係較強 E2E） |
| **前置** | 合成 kid；金幣／材料夠；清走已有「健身室」 |
| **步驟** | 1. 登入 2. ☰ → 建築管理 3. 可建造列表「健身室」撳「🏗️ 建造」（onclick `startPlacement`） 4. 若未喺地圖：☰ → 小鎮地圖 5. `#placementBar.active` → `.valid-plot` → 「✅ 確認建造」 |
| **預期** | 同商店一樣進入放置態；地圖出現健身室；DB persist。**產品觀察（非本 PR 修復）：** 建築 tab `startPlacement` **唔**自動 `st('town')`（商店 `shopBuild` 會）。E2E 會跟住開小鎮地圖——呢步亦要 (B) 喺真機確認小朋友知去邊。 |
| **(A)/(B)** | 取代「只 grep `startPlacement`」當齊 (A)。source 檔 `tests/test_frontend_placement.py` 仍保留作弱契約。 |

---

## FE-XSS-01 — 任務標題 DOM 唔執行 markup

| 欄 | 內容 |
|----|------|
| **ID** | FE-XSS-01 |
| **優先級** | P1 |
| **對應 API** | P0-TC-XSS-01 |
| **前置** | 合成任務標題 `<b>粗體</b>` 同 `<img src="https://xss.example.test/probe.png" onerror="window.__xssHit=1">` |
| **步驟** | 小朋友登入 → 任務 tab；用 Playwright 讀 `.task-title` 嘅 `textContent`／`innerHTML`；監聽 `xss.example.test` 網絡 |
| **預期** | 見到括號字／escape 後嘅 tags；**無** 真正 `<b>` 節點；**無** 任務標題入面嘅 `<img>`；`window.__xssHit` 唔係 1；無 probe 網絡 |
| **備註** | 產品 `renderTasks()` 用 `escapeHtml()` 編碼 title／描述等用戶字串，再拼進 innerHTML。標籤以純文字顯示，唔執行 markup。 |

---

## FE-XSS-02 — 小朋友顯示名 HUD 編碼

| 欄 | 內容 |
|----|------|
| **ID** | FE-XSS-02 |
| **優先級** | P1 |
| **對應 API** | P0-TC-XSS-02 |
| **前置** | 合成 kid `test_fe_xss`，name=`<img src=x onerror=alert(1)>` |
| **步驟** | 用該帳戶登入；讀 `#hudNm` |
| **預期** | HUD 名係文字（含 `<img` tags 字面）；`#hudNm` 入面無 attacker `img`；無 `alert` dialog；`#hudAv img[src]` 唔係 `x` |
| **備註** | `#hudNm` 已用 `textContent`（部分支援）。呢 case 預期可以綠。 |

---

## 點跑

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m pytest tests/test_frontend.py -v
```

雙重驗證 (B) 人手步驟：[`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md)。跑完結果寫 [`FRONTEND_E2E_STATUS.md`](FRONTEND_E2E_STATUS.md)。
