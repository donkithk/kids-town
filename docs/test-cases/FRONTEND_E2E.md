# Frontend E2E test cases (Playwright)

> **Runner**: `tests/test_frontend.py` (sync Playwright, current venv `sys.executable`).  
> **Fixture**: empty SQLite + factories. **禁止** copy `kids_town.db`.  
> **Credentials**: synthetic only (`test_fe_*`, PIN `1357`, parent `TestParent!pass1`).  
> **Skip rule**: skip **only** if Playwright / Chromium cannot launch; reason must tell the operator to run `python -m playwright install chromium`.  
> **Install**: see [`README.md`](../../README.md) and [`docs/TDD_PROCESS.md`](../TDD_PROCESS.md) § frontend.

Status map after a run: [`FRONTEND_E2E_STATUS.md`](FRONTEND_E2E_STATUS.md).  
Experience C（真機體驗加固）: `TC-FE-CEREMONY-01`、`TC-FE-PLACE-SHOP-01`、`TC-FE-PLACE-BUILD-01`；(B) [`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md).

四場景起屋（設計稿 `3b4671d`／PR #27，**唔好 merge #27**）: `TC-FE-TOWN-UX-01`…`05`、`TC-FE-TOWN-FX-01`／`02`、`TC-FE-TOWN-HIT-01`…`03`、`TC-FE-TOWN-MOTION-01`／`02`。呢個 sheet flow 已經喺 main。舊放置條 `TC-FE-PLACE-SHOP-01`／`TC-FE-PLACE-BUILD-01` 仍然有效，唔係呢個 sheet flow 嘅代替。

8×8 地圖同格外收倉: `TC-FE-TOWN-GRID-01`、`TC-FE-TOWN-STORE-LEGACY-01`、`TC-FE-TOWN-STORE-LEGACY-02`。篩選 `-k 'town_grid or store_legacy'`。可建地圖係欄 0..7 × 行 0..7，場景 1–3 同一個 8×8。載入城鎮時，格外或者無合法格、而且 `stored=0` 嘅屋要一次過收進存倉（`stored=1`），保留同一行、`def_id`、等級。收倉之後場景 1 唔好畫佢哋，建築清單唔好當地圖「已起」鎖住。用現有「存倉」放返空地，唔扣資源。唔好用清單「去擺位置」搬屋來代替。產品喺城鎮載入同建築物讀取時收倉，場景 1–3 係 8×8。

已經 `stored=1` 嘅屋唔好當新建築賣: `TC-FE-TOWN-STORE-LIST-01`、`TC-FE-TOWN-STORE-PLACE-01`、`TC-FE-TOWN-STORE-CONFIRM-01`。篩選 `-k 'store_list or store_place or store_confirm'`。場景 2 建築清單唔好把存倉屋標成「未起」兼顯示價錢，亦唔好帶入「確定先至扣資源」然後 POST `/buildings`。呢個新建查重包埋 `stored=1` 嘅行，所以 API 回 400「你已經興建咗呢種建築物」。正確放返係現有存倉（`#placementBar`，POST `/buildings/<id>/unstored`），唔扣金幣同材料，同一行變 `stored=0`。呢三條喺 main 上留紅。唔改產品。

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

## TC-FE-TOWN-UX-01 — 場景 1 睇地圖 +「我要起屋」

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-UX-01 |
| **優先級** | P0（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **設計** | Mock tip `3b4671d`（PR #27 draft，只係設計參考，**唔好 merge**）。斷言打產品 `/kids/` 城鎮首頁，唔係靜態 mock 路徑。 |
| **前置** | 空庫合成 `test_fe_kid`。測試會種圖書館 `(2,1)`、農場 `(4,0)`、商店 `(0,2)`，健身室未起。HUD 讀畫面，唔硬套 mock 示範籌碼 💰6000。 |
| **步驟** | 1. 登入，停喺城鎮首頁 2. 睇 1280×720 art-stage 3. 等角地圖顯示 DB 入面真正已起嘅圖書館／農場／商店（頁腳「商店」同舊 `.town-building` 唔算） 4. 未起嘅健身室唔好當成已起 5. 空地冇金框 6. 見到「我要起屋」 7. 撳一塊空地 |
| **預期** | 場景 1 顯示小朋友真實資料嘅已起屋，唔係寫死嘅 mock 三座。空地唔發光。撳空地**唔扣** HUD 資源。未有等角格仔／「我要起屋」，本 case **留紅**。唔好用舊 `#placementBar` 當過。 |
| **備註** | `TC-FE-PLACE-SHOP-01`／`TC-FE-PLACE-BUILD-01` 繼續覆蓋舊建造條，唔係本流程嘅代替。 |

---

## TC-FE-TOWN-UX-02 — 場景 2 揀空地／建築清單

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-UX-02 |
| **優先級** | P0（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 撳「我要起屋」 2. 空地出金框 3. 打開「建築清單」 4. 已起嘅圖書館／農場／商店標「已起」 5. 未揀齊之前「去擺位置」disabled 6. 揀一塊空地 + 未起嘅健身室 |
| **預期** | 兩樣都揀好，「去擺位置」先至可撳。清單打得開；已起唔可以再當未起屋來揀。 |

---

## TC-FE-TOWN-UX-03 — 場景 3 取消唔扣資源

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-UX-03 |
| **優先級** | P0（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 去到場景 3 2. 見到半透明 ghost 預覽 3. ghost 搬去另一塊空地 4. 撳已有圖書館嘅格 5. 撳「取消」 6. 讀取消前後 HUD |
| **預期** | Ghost 搬位同撳佔用格都唔改 HUD。佔用格被擋住（toast 似「已經有／唔可以放」）。取消返回，toast 似「已取消，資源未扣除」，HUD 同取消前相等，健身室冇寫入 DB。資源數字跟當時 HUD，唔硬套 mock 嘅 💰6000。確定扣資源係 `TC-FE-TOWN-UX-04`。 |

---

## TC-FE-TOWN-UX-04 — 場景 3 確定扣資源並打開場景 4

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-UX-04 |
| **優先級** | P0（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 去到場景 3 2. 讀 HUD 3. 撳「確定」／「確定放置」 4. 再讀 HUD、地圖、升級面板 |
| **預期** | 至少一項 header 資源變少（其餘唔會變多）。健身室出現喺地圖同 DB。跟住打開場景 4（睇到「升級」）。扣幾多跟產品成本同畫面前後差，唔硬套 mock 示範 💰200 🪵10 🧱5。 |

---

## TC-FE-TOWN-UX-05 — 場景 4 升級、功能、HUD

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-UX-05 |
| **優先級** | P0（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 確定放置進入場景 4 2. 讀 sheet 等級同 HUD 3. 撳升級 4. 再讀等級同 HUD 5. 撳至少一個功能掣 |
| **預期** | 等級上升，HUD 再扣（chips 反映新餘額）。功能掣之後 sheet／toast 有可見結果。功能本身唔好把剛扣完嘅餘額打回升級前。Mock 示範升級 💰50 🪵2 只係設計例子，產品斷言用前後差。 |

---

## TC-FE-TOWN-HIT-01 — 等角背面格唔好被前面建築截走

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-HIT-01 |
| **優先級** | P0（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 場景 2 2. Viewport 1100×800：搵一塊背面空地，畫面被前面建築 sprite 遮住，用滑鼠撳重疊點 3. Viewport 1280×720 再撳一次 |
| **預期** | 兩個 viewport 都選中背面空地（「第 N 欄第 M 行」＋「已揀」），唔係前面嗰座屋。舊 `.valid-plot`／`.town-building` 疊層唔算。種子：商店 `(0,2)`、圖書館 `(2,1)`、農場 `(4,0)`。 |

---

## TC-FE-TOWN-HIT-02 — 信箱縮放後撳格仍然對齊

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-HIT-02 |
| **優先級** | P0（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. Viewport 1100×800，確認舞台 layout 1280×720、視覺縮放 `min(1100/1280, 800/720)` 2. 場景 2 用滑鼠撳一塊空地嘅視覺中心 3. 再將 viewport 設做 1280×720，重覆撳格中心 |
| **預期** | 兩個 viewport 選中嘅都係嗰格（欄／行一致），唔係隔離格。淨係已經有 1280×720 信箱、但未有四場景空地掣，本 case **留紅**。背面格被前面屋遮住係 `TC-FE-TOWN-HIT-01`（同樣兩個 viewport）。 |

---

## TC-FE-TOWN-HIT-03 — 軟橢圓接觸陰影

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-HIT-03 |
| **優先級** | P0（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 場景 1 已起圖書館／農場／商店 2. Viewport 1100×800（1280×720 信箱）睇每座屋嘅接觸陰影 3. 再試 viewport 1280×720 |
| **預期** | 每座真實已起屋有一粒軟橢圓接觸陰影：`radial-gradient` ellipse、有 blur 或者透明邊、比地塊闊所以跨過鄰格縫、`pointer-events: none`、pad `overflow: visible`。舊城鎮 sprite 冇呢個陰影，本 case **留紅**。 |

---

## TC-FE-TOWN-FX-01 — 新起屋金星慶祝

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-FX-01 |
| **優先級** | P1（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 去到場景 3 2. 撳「確定」 3. 等 `.fx-burst.is-place .fx-bit.is-star` 變得睇到 |
| **預期** | 新起屋有可見金星（opacity 升起、有尺寸）。金星喺地圖上嘅新建築，唔好一開始就只喺 action sheet 入面。戰鬥 `.spark-burst` 唔算。未有起屋流程，本 case **留紅**。 |

---

## TC-FE-TOWN-FX-02 — 升級金星喺 action sheet 上

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-FX-02 |
| **優先級** | P1（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 確定放置，打開場景 4 2. 撳升級 3. 等 action sheet 入面 `.fx-burst.is-upgrade .fx-bit.is-star` |
| **預期** | 升級金星係打開緊嘅 action sheet 嘅子節點，而且睇得見（喺面板前面）。地圖上嘅放置金星唔算本 case。 |

---

## TC-FE-TOWN-MOTION-01 — 慶祝層唔截擊

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-MOTION-01 |
| **優先級** | P1（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 確定放置 2. 等城鎮慶祝層（`.fx-burst` 或 `[data-town-fx]`）出現 3. 讀 `pointer-events`，並用 `elementFromPoint` 睇層中心 |
| **預期** | 慶祝層同子節點都係 `pointer-events: none`，中心點嘅 hit target 唔係呢個層。戰鬥 `.spark-burst` 唔算。 |

---

## TC-FE-TOWN-MOTION-02 — 動畫掣：系統減少動態，撳先寫 localStorage

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-MOTION-02 |
| **優先級** | P1（四場景起屋；main 上留紅） |
| **建議模組** | `tests/test_frontend.py`（`-k town_ux`） |
| **步驟** | 1. 清 localStorage，模擬 `prefers-reduced-motion: reduce` 2. 登入城鎮首頁，確認未寫 motion key、掣預設關 3. 撳一次變開 4. 重新載入（系統仍然 reduce） 5. 再撳一次變關 |
| **預期** | 第一次載入唔寫 localStorage，跟系統減少動態所以關。只有明確撳「開」同之後撳「關」先改寫名稱含 `motion` 嘅 key。儲低嘅「開」會覆蓋系統偏好。城鎮首頁未有呢個掣，本 case **留紅**。唔好用音效 mute key 頂替。 |

---

## TC-FE-TOWN-GRID-01 — 四場景地圖係 8×8

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-GRID-01 |
| **優先級** | P0（8×8 可建格） |
| **建議模組** | `tests/test_frontend.py`（`-k town_grid`） |
| **前置** | 空庫合成 `test_fe_kid`。清走佢嘅建築物，等「第 1 欄第 1 行」係空地，清單有「未起」。唔用真 PIN／production DB。 |
| **步驟** | 1. 場景 1 數等角格 2. 「我要起屋」再數一次 3. 揀「第 1 欄第 1 行」+ 第一座可見嘅「未起」，「去擺位置」入場景 3，見到「取消」之後再數一次 |
| **預期** | 場景 1、2、3 都係 **8×8**（64 格，第 1–8 欄 × 第 1–8 行，欄 0..7 × 行 0..7）。 |

---

## TC-FE-TOWN-STORE-LEGACY-01 — 格外或無合法格嘅屋，載入時收進存倉

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-STORE-LEGACY-01 |
| **優先級** | P0（格外收倉） |
| **建議模組** | `tests/test_frontend.py`（`-k store_legacy`） |
| **前置** | 空庫合成 `test_fe_kid`。種子全部 `stored=0`：工坊 `(4,1)` Lv.1（8×8 之內）；圖書館 `(17,1)` Lv.3、健身室 `(15,5)` Lv.1、農場 `(9,5)` Lv.2、醫院 `(17,13)` Lv.1、探險公會 `(9,13)` Lv.1（超出欄 0..7 × 行 0..7）；燈塔 `cell_x`／`cell_y` 都係空（無合法格）Lv.1。銀行唔喺 `seed_building_defs`，唔種。金幣同材料夠多，以免誤當新建築扣到都唔覺。唔用真 PIN／production DB。 |
| **步驟** | 1. 寫低每一行嘅 id、`def_id`、等級 2. 登入並等城鎮 HUD 出現（即係載入城鎮） 3. 再讀同一份 SQLite |
| **預期** | 格外五行同無格嘅燈塔變成 `stored=1`（存倉），**同一行 id**、同一個 `def_id`、同一個等級。工坊留喺 `(4,1)`、`stored=0`、Lv.1。行數唔變。呢個修補要喺城鎮載入時生效（測試伺服器已經行緊，種子係之後先寫入）。只喺程序啟動、未見到呢批行嘅遷移，唔算過。 |

---

## TC-FE-TOWN-STORE-LEGACY-02 — 收倉之後用地圖以外嘅存倉放返，唔扣資源

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-STORE-LEGACY-02 |
| **優先級** | P0（格外收倉） |
| **建議模組** | `tests/test_frontend.py`（`-k store_legacy`） |
| **前置** | 同 `TC-FE-TOWN-STORE-LEGACY-01`。 |
| **步驟** | 1. 載入場景 1，睇等角格 2. 「我要起屋」打開「建築清單」 3. ☰ →「存倉」 4. 如果有圖書館卡：撳「按此放置」，切去城鎮，揀一塊原點喺 0..6 × 0..6 嘅綠色空地（2×2 留喺 8×8 裡面），撳「確認建造」 5. 讀 HUD、金幣、材料、同一行 |
| **預期** | 場景 1 見到工坊喺「第 5 欄第 2 行」。格外屋同燈塔唔好出現喺等角格、sprite 或 caption（舊 `.town-building` 畫布喺場景 1 唔算）。清單入面呢啲屋唔好標地圖「已起」；工坊仍然係「已起」。存倉列出每一座同埋 `Lv.N`。放返用現有存倉流程（`#placementBar`，POST `/buildings/<id>/unstored`），唔好用「去擺位置」。圖書館保持同一行、`def_id`、Lv.3，變成 `stored=0`，格喺 0..7 × 0..7，並且出現喺等角地圖或者城鎮畫布。金幣同材料唔變。工坊仍然係原本嗰行、`stored=0`、`(4,1)`。只做清單搬屋、唔收倉，呢個 case 仍然紅。 |

---

## TC-FE-TOWN-STORE-LIST-01 — 存倉屋唔好喺建築清單當未起兼標價錢

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-STORE-LIST-01 |
| **優先級** | P0（存倉唔好當新建築） |
| **建議模組** | `tests/test_frontend.py`（`-k store_list`） |
| **前置** | 空庫合成 `test_fe_kid`，PIN `1357`。金幣同材料夠多。建築物只得兩行：工坊 `(4,1)` Lv.1 `stored=0`（喺 8×8 地圖）；探險公會 `(9,13)` Lv.1 `stored=1`（已經入倉，舊格喺 8×8 之外）。唔用真 PIN／production DB。 |
| **步驟** | 1. 登入，場景 1 睇等角格 2. 「我要起屋」打開「建築清單」 3. 讀工坊同探險公會嘅清單文案 4. 揀「第 1 欄第 1 行」同探險公會，睇「去擺位置」會唔會打開「確定先至扣資源」 |
| **預期** | 場景 1 見到工坊喺「第 5 欄第 2 行」，唔好畫探險公會。工坊仍然係「已起」。探險公會唔好以「未起」或者 💰 價錢出現。揀佢唔好入新建築確認（「確定先至扣資源」）。正確放返係存倉，唔係清單新建築。main 上留紅。 |

---

## TC-FE-TOWN-STORE-PLACE-01 — 放返存倉屋要走 unstored，地圖見到而且唔扣資源

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-STORE-PLACE-01 |
| **優先級** | P0（存倉唔好當新建築） |
| **建議模組** | `tests/test_frontend.py`（`-k store_place`） |
| **前置** | 同 `TC-FE-TOWN-STORE-LIST-01`。 |
| **步驟** | 1. 場景 1 確認探險公會未喺地圖 2. 「我要起屋」打開「建築清單」，揀空地同探險公會 3. 如果出現「確定先至扣資源」，撳「確定放置」，睇 POST、地圖、同一行、HUD 4. 如果清單冇帶入呢句新建築確認，就改用 ☰ →「存倉」嘅「按此放置」（`#placementBar`，同 `TC-FE-TOWN-STORE-LEGACY-02`），揀 8×8 裡面嘅空地，撳「確認建造」 |
| **預期** | 放返必須係 POST `/buildings/<id>/unstored`，唔好係 POST `/buildings`。地圖見到探險公會。金幣同材料唔變。同一行（同一個 id、`def_id`、Lv.1）變成 `stored=0`，格喺 0..7 × 0..7。工坊留喺 `(4,1)`、`stored=0`。main 上清單會入「確定先至扣資源」，確定打去 POST `/buildings` 得到 400，地圖冇探險公會，行仍然 `stored=1`。留紅。 |

---

## TC-FE-TOWN-STORE-CONFIRM-01 — 唔好同時見到扣資源文案同「你已經興建咗呢種建築物」

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-TOWN-STORE-CONFIRM-01 |
| **優先級** | P0（存倉唔好當新建築） |
| **建議模組** | `tests/test_frontend.py`（`-k store_confirm`） |
| **前置** | 同 `TC-FE-TOWN-STORE-LIST-01`。 |
| **步驟** | 1. 打開建築清單，揀空地同存倉嘅探險公會 2. 如果見到「確定先至扣資源」，撳「確定放置」 3. 讀確認文案、toast、POST 4. 再用存倉／`#placementBar`／unstored 放返（同 `TC-FE-TOWN-STORE-LEGACY-02`） 5. 再讀 HUD、金幣、材料、同一行 |
| **預期** | 唔好同時出現「確定先至扣資源」同「你已經興建咗呢種建築物」（確認文案配埋 400，因為新建查重包埋 `stored=1`）。正確放返之後金幣同材料同放之前一樣，同一行 `stored=0` 喺 8×8 裡面。main 上兩句會一齊出現，所以留紅。 |

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
python -m pytest tests/test_frontend.py -q -k 'town_grid or store_legacy' --tb=line
python -m pytest tests/test_frontend.py -q -k 'store_list or store_place or store_confirm' --tb=line
python -m pytest tests/test_frontend.py -q -k 'not town_grid and not store_legacy' --tb=line
python -m pytest tests/test_frontend.py -q -k town_ux --tb=short
```

`town_grid`／`store_legacy` 係 8×8 地圖同格外收倉（`TC-FE-TOWN-GRID-01`、`TC-FE-TOWN-STORE-LEGACY-01`、`TC-FE-TOWN-STORE-LEGACY-02`）。`store_list`／`store_place`／`store_confirm` 係已經入倉嘅屋唔好當新建築賣（`TC-FE-TOWN-STORE-LIST-01`、`TC-FE-TOWN-STORE-PLACE-01`、`TC-FE-TOWN-STORE-CONFIRM-01`）。`-k 'not town_grid and not store_legacy'` 係其餘前端套件，包括已經落地嘅四場景 `town_ux`，以及呢三條存倉紅測。接受尺寸係 8×8。收倉喺每次城鎮載入同建築物讀取時做。已經 `stored=1` 嘅屋要用存倉 unstored 放返，唔好 POST `/buildings`。

雙重驗證 (B) 人手步驟：[`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md)。跑完結果寫 [`FRONTEND_E2E_STATUS.md`](FRONTEND_E2E_STATUS.md)。
