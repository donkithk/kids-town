# 存倉放回 8×8 地圖

紅測。只加測試與本說明，不改產品代碼。`main`（`5bfe76dc5ad31b9fcfe2e273e5f2af3f1f750f7e`）上，建造與取出仍接受舊範圍 0–22 × 0–14；讀取建築時若原點落在 8×8 之外，會把該行改為 `stored=1`，且不退還已扣的金幣與材料。效果只計算 `stored=0` 的行，所以被收進存倉的建築失去加成，公會大廳亦無法使用。

格子原點規則：合法原點是 `cell_x`、`cell_y` 皆在 0 至 7（含）。`(7,7)` 必須接受。`(8,0)`、`(0,8)`、`(8,8)`、負數、以及舊座標如 `(20,12)` 必須拒絕。建築足跡是 2×2。本組案例以原點是否在 8×8 內為準，不把原點收窄到 0–6；同時，兩座已放置建築的 2×2 重疊必須拒絕。燈塔、競技場、天文台解鎖之後使用同一套規則，沒有格外豁免。`P1-TC-UNL-02` 因此改為：解鎖區 3 之後，燈塔放在 `(8,0)` 必須 400 且金幣與材料不變；放在 8×8 內的空格 `(0,0)` 必須 201 且 `stored=0`。舊預期是 `(8,0)` 201。變更原因是 8×8 規則（Grok decision）。

所有案例使用臨時資料庫與測試自行建立的帳號、小朋友。不得讀寫追蹤中的 `kids_town.db`。

## 根因

| 位置 | 現況 |
|------|------|
| `backend_v2.py:1615-1616` | `TOWN_PLACE_COLS = 8`、`TOWN_PLACE_ROWS = 8`。讀取路徑已經是 8×8。 |
| `backend_v2.py:1619-1640` `warehouse_legacy_out_of_grid` | 已放置且原點為空、負數、或 `cell_x >= 8` 或 `cell_y >= 8` 的行，設 `stored=1`。保留 id、等級與（已經不合法的）座標，不退資源。由 `list_buildings`（`backend_v2.py:3247`）、`get_stored_buildings`（`:3400`）、`get_town_state`（`:4987`）呼叫。 |
| `backend_v2.py:3264-3265` `place_building` | 只拒絕 `cell_x` 不在 0–22 或 `cell_y` 不在 0–14。錯誤字串為 `Building position out of range (0-22, 0-14)`。 |
| `backend_v2.py:3313-3321` | 通過上述舊範圍後先扣金幣與材料，再插入 `level=1`、預設 `stored=0` 的新行。下一次 GET 若原點在 8×8 外，該行被收倉，資源已扣。 |
| `backend_v2.py:3267-3270` | 同一 `def_id` 已有任何一行（含 `stored=1`）即回 400「你已經興建咗呢種建築物」，發生在扣費之前。核准行為是放回存倉那一行，不扣費、不新增第二行。 |
| `backend_v2.py:3273-3283` | 佔用檢查只看有沒有另一行的**原點**落在新 2×2 的四格上，且不篩 `stored=0`。真正的足跡重疊（例如已放置原點 `(0,0)` 與新原點 `(1,0)`）會通過。存倉行留下的舊座標仍會擋住建造與取出。 |
| `backend_v2.py:3374-3375` `unstored_building` | 與建造相同的 0–22 × 0–14 閘門。 |
| `backend_v2.py:3383-3391` | 取出的佔用檢查同樣是原點對原點，且包含其他 `stored=1` 的行。成功時（`:3392`）只改 `stored=0` 與座標，不改等級、不扣資源。 |
| `backend_v2.py:3326-3353` `move_building` | `POST /api/kids/<id>/buildings/<id>/move`。`:3333-3334` 同樣只拒絕 0–22 × 0–14 以外。`:3342-3350` 佔用檢查是原點對原點，且包含 `stored=1`。成功時只改座標，不改等級、不扣資源。格外移動若先成功，下一次 GET 會把該行收倉。 |
| `town-four-scene.js:5-6` | 四場景地圖已是 `COLS = 8`、`ROWS = 8`。 |
| `index.html:2931` `renderTownBuildings` | `const COLS = 24, ROWS = 16`，並繪製 `.valid-plot`。 |
| `index.html:3376-3385` `startUnstoreBuilding` | 存倉卡片呼叫它，替 `#placementBar` 加上 `active`。 |
| `index.html:3424-3428` `renderStoredBuildings` | 卡片文字是「按此放置」，沒有「取出」。 |
| `town-four-scene.css:24` | `#placementBar.active ~ #townMap` 隱藏 8×8 地圖。 |

效果只在 `stored=0` 時計算，這部分與案例預期一致，不是本次要改的方向：

- `has_active_guild`（`backend_v2.py:1884-1895`）：`POST /api/kids/<id>/expedition/start` 在公會仍存倉時回 `guild_required`。
- `calc_ability_buffs`（`:2067-2078`）：圖書館每級智力 +2。
- `get_building_buff`（`:1791-1813`）：農場每日金幣、商店折扣。`discounted_gold_cost`（`:1898`）只折金幣，下限 1。
- `get_kid_skills`（`:3877-3884`）：只看 `stored=0`。
- 圖書館的 `task_bonus` 已由 `_drop_library_task_bonus`（`:552`）清掉，`award_task_drops`（`:2128`）把 `experience_bonus` 固定為 0。倉庫修復不得恢復任務經驗加成。已接上的圖書館效果是能力智力與技能。

## 案例

API：`tests/test_warehouse_placement.py`（`pytest -m "not frontend"`）。  
介面：`tests/test_warehouse_e2e.py` 的 `TC-FE-WAREHOUSE-UNSTORE` 與 `TC-FE-WAREHOUSE-CARD`，以及同一 API 檔內讀取已提供頁面的 `TC-FE-WAREHOUSE-GRID`（後者屬 API 套件，因為它只 GET 靜態檔）。

下表「main」是在 `5bfe76d` 加上這些測試後的結果。紅測的斷言訊息寫明預期與實際。綠測是回歸鎖，不是本缺陷。

| ID | 行為 | main | 實際對預期 |
|----|------|------|------------|
| TC-API-WAREHOUSE-UNSTORE-OK | `POST /buildings/<id>/unstored` 到空的 `(7,7)` 或 `(1,1)`：HTTP 200，`stored=0`，Lv.2 保留，金幣與材料不變。 | PASS | 符合。 |
| TC-API-WAREHOUSE-UNSTORE-OOB | `(8,0)`、`(0,8)`、`(8,8)`、`(20,12)` 必須 4xx，行維持 `stored=1`、原座標、資源不變。 | FAIL | 實際 HTTP 200，座標被改成該格外點；其後 GET 再把該行收成 `stored=1` 並留在新的不合法座標。 |
| TC-API-WAREHOUSE-UNSTORE-REJECT | 缺座標、負數、原點已被已放置建築佔用、地磚佔用：4xx，資料不變。 | PASS | 符合。 |
| TC-API-WAREHOUSE-UNSTORE-OVERLAP | 已放置健身室原點 `(0,0)` 時，醫院取出到 `(1,0)` 足跡重疊，必須 4xx；醫院仍 `stored=1` 於 `(20,12)`。 | FAIL | 實際 HTTP 200，醫院變成 `stored=0` 於 `(1,0)`。佔用檢查只比對原點。 |
| TC-API-WAREHOUSE-STORED-OCC | 存倉行的舊座標不佔地圖。另一座建築可取出到該原點；新建造亦可落在存倉行記錄的格子上（新建造仍扣目錄價）。 | FAIL | 取出到存倉圖書館的 `(0,0)` 得 400「該位置已被佔用」。在存倉銀行的 `(4,4)` 建造健身室得 400「該位置已被建築物佔用」。 |
| TC-API-WAREHOUSE-BUILD-OK | 空的 `(7,7)` 新建圖書館：201，扣目錄價（100 金幣、木材 5），GET 之後仍 `stored=0`、等級 1。 | PASS | 符合。 |
| TC-API-WAREHOUSE-BUILD-OOB | `(8,0)`、`(0,8)`、`(8,8)`、`(20,12)` 建造：4xx，不扣資源，不新增行，不收入存倉。 | FAIL | 實際 201 並扣費（圖書館 8000→7900 金幣、木材 80→75）；GET 之後該行 `stored=1`，停在格外座標。 |
| TC-API-WAREHOUSE-BUILD-REJECT | 負數、原點佔用、地磚：4xx，不扣、不新增。省略座標不再當成拒絕。8×8 每個原點都被佔用時，省略座標的新建造必須 400，金幣與材料不變，不得新增該 `def_id` 的行。若回應有訊息，必須正好是「城鎮沒有空位，請先收起或移動其他建築。」原因：有空位時省略座標要自動放置，不能再把缺座標一律判失敗。 | FAIL | 負數、原點佔用、地磚，以及滿圖的 400、不扣、不新增都通過。訊息是 `def_id, cell_x, cell_y required`，不是「城鎮沒有空位，請先收起或移動其他建築。」 |
| TC-API-WAREHOUSE-BUILD-OVERLAP | 圖書館建在 `(1,0)`，與已放置健身室 `(0,0)` 的 2×2 重疊：4xx，不扣、不新增、不入倉。 | FAIL | 實際 201，扣 100 金幣與木材 5，新行 `stored=0` 於 `(1,0)`。 |
| TC-API-WAREHOUSE-BUILD-REUSE | 存倉已有 Lv.2 圖書館時，再 POST 建造該種類並指定格子：放回同一行到要求的格子，等級 2，不扣費，仍然只有一行。 | FAIL | 實際 400「你已經興建咗呢種建築物」；行維持 `stored=1` 於 `(20,12)`。未扣費，但沒有放回。 |
| TC-API-WAREHOUSE-BUILD-REUSE-AUTO | 同一座 `stored=1`、等級大於 1 的建築，POST 只帶 `def_id`、不帶座標。空圖：201，同一行變成 `stored=0` 於第一個合法格（空圖為 `(0,0)`），等級保留，不扣費，該 `def_id` 的行數不增加。滿圖：400，金幣與材料不變，該行仍是 `stored=1`、同一 id、同一等級，不新增。`BUILD-REUSE` 有指定格子，這條沒有。 | FAIL | 空圖省略座標回 400 `def_id, cell_x, cell_y required`。圖書館仍是 `stored=1`、等級 2、座標 `(20,12)`，沒有放到 `(0,0)`。滿圖該半段通過：400、資源不變、同一行維持 `stored=1`、沒有新增。 |
| TC-API-WAREHOUSE-MOVE-OOB | `POST /buildings/<id>/move` 到 `(8,0)`、`(0,8)`、`(8,8)`、`(-1,0)`、`(0,-1)`、`(20,12)`：4xx。行仍是 `stored=0` 且停在原格，資源不變。其後 GET `/buildings` 與 GET `/town` 也不得把它收倉。 | FAIL | 負數已是 4xx 且行不變。`(8,0)`、`(0,8)`、`(8,8)`、`(20,12)` 回 200 並改座標；GET 之後該行 `stored=1`，停在新的格外座標，而不是仍放置在原格。 |
| TC-API-WAREHOUSE-MOVE-OVERLAP | 已放置健身室在 `(0,0)` 時，把醫院從 `(4,0)` 移到 `(1,0)`（2×2 重疊）：4xx，醫院仍在 `(4,0)`、等級 2、資源不變。 | FAIL | 實際 HTTP 200，醫院改到 `(1,0)`。佔用檢查只比對原點。 |
| TC-API-WAREHOUSE-MOVE-STORED-OCC | 地圖上唯一佔用是存倉行留下的座標時，移動必須成功。存倉圖書館停在 `(0,0)` 時，健身室可移到 `(0,0)`，等級保留，不扣資源，圖書館仍 `stored=1`。 | FAIL | 實際 400「該位置已被佔用」，健身室仍在 `(4,4)`。 |
| TC-API-WAREHOUSE-MOVE-OK | 移到空的 `(7,7)`：200，`stored=0`，等級保留，不扣資源。GET `/buildings` 與 GET `/town` 之後仍放置在 `(7,7)`。 | PASS | 符合。 |
| TC-API-WAREHOUSE-EFFECT-GUILD | 存倉的探險公會：`expedition/start` 回 `guild_required`，金幣不變。取出到 `(2,2)` 後出發 201，區域 1 費用 10。 | PASS | 符合。 |
| TC-API-WAREHOUSE-EFFECT-LIBRARY | 存倉時 `buffs.int` 為 0，技能不含「知識的力量」「火球」，且沒有 `task_bonus`。取出 Lv.2 後智力加成為 4，兩項技能出現，`task_bonus` 仍為空。 | PASS | 符合。不要恢復任務經驗加成。 |
| TC-API-WAREHOUSE-EFFECT-FARM | 存倉時領取回 `farm_required`。取出 Lv.2 後領取成功，金幣 +10。 | PASS | 符合。 |
| TC-API-WAREHOUSE-EFFECT-SHOP | 存倉商店不打折。取出 Lv.1 後，下一座建築金幣為 `floor(原價 × 0.9)`（圖書館 100 → 90）。 | PASS | 符合。 |
| TC-API-WAREHOUSE-REPAIR | 格外存倉的探險公會、銀行、圖書館 Lv.2、醫院 Lv.2、農場，以及 GET 後被收倉的工坊 Lv.3，都可取出到 8×8 內互不重疊的原點；等級保留，資源不變，城鎮列表不再有存倉行。 | PASS | 符合。格外舊座標本身不擋住 8×8 內的空格。 |
| TC-FE-WAREHOUSE-GRID | 讀取 `/kids/` 與 `/kids/town-four-scene.js`。四場景與 `renderTownBuildings` 的 `COLS`/`ROWS` 都必須是 8×8。 | FAIL | 四場景已是 `(8, 8)`。`index.html` 的 `renderTownBuildings` 仍是 `(24, 16)`，並含 `.valid-plot`。 |
| TC-API-WAREHOUSE-REGION-GRID | 解鎖後燈塔、競技場、天文台：舊座標（`(8,0)`、`(10,0)`、`(12,0)`）與 2×2 重疊必須 4xx，不扣、不新增。合法空格 `(3,3)` 必須 201、`stored=0`，並扣目錄價。競技場 r4、天文台 r5 若仍回 `region_locked`，只要不扣、不新增即算通過。 | FAIL | 燈塔 `(8,0)` 回 201 並扣費（金幣 20000→19200，木材 200→170，磚 200→175，齒輪 80→65，寶石 40→37）。 |
| TC-API-WAREHOUSE-REGION-AUTO | 省略座標的新建造：空圖自動放到第一個合法空格（行由外、欄由內，空圖為 `(0,0)`），201，`stored=0`，扣目錄價。8×8 每個原點都被佔用時必須 400，金幣與材料不變，不得新增任何一行（含 `stored=1`）。免費入倉只給已經擁有的建築；免費再送一座會變成白拿建築。 | FAIL | 空圖省略座標回 400 `def_id, cell_x, cell_y required`，沒有放到 `(0,0)`。滿圖該半段通過：400、資源不變、沒有新增燈塔行。 |
| TC-API-WAREHOUSE-REGION-NO-AUTOSTORE | 建造之後 GET `/buildings` 與 GET `/town` 不得把該行改成 `stored=1`，也不得再改資源。`(8,0)` 若被拒絕，必須不扣、不新增。 | FAIL | `(8,0)` 被接受（201）並扣費；GET 之後該行 `stored=1`，仍停在 `(8,0)`，沒有退款。 |
| TC-API-WAREHOUSE-REPAIR-PLACED-LEGACY | 已放置的探險公會在 `(13,9)`、`stored=0`。GET 可把它改成 `stored=1`，但不得扣資源。取出到空的 `(0,0)` 免費、等級保留，其後公會大廳可以出發。 | PASS | 符合。GET 把 `(13,9)` 收成 `stored=1` 且不扣資源；取出到 `(0,0)` 免費，等級 2，出發扣區域 1 的 10 金幣。 |
| TC-FE-WAREHOUSE-CARD | 存倉卡片只顯示名稱、等級與「取出」。「按此放置」不得出現。 | FAIL | 清單文字是「圖書館 Lv.2」加「按此放置」，沒有「取出」。 |
| TC-FE-WAREHOUSE-UNSTORE | 見下方介面步驟。取出走與新建造相同的場景 2 → 場景 3，不顯示價錢。同一輪截圖的頁尾 RGB 差為 0，結構與 `tests/fixtures/kt_footer_main.json` 相同。 | FAIL | 存倉清單沒有「取出」。卡片文字是「按此放置」，呼叫 `startUnstoreBuilding`。頁尾結構與 JSON 相同，同一輪兩次截圖的 RGB 差為 0。失敗發生在清單，不是頁尾。 |

拒絕狀態只接受 400、409、422。401 不算成功拒絕。取出成功為 200 或 201。新建（沒有可再用的存倉行）成功為 201。移動成功為 200。

移動端點是 `POST /api/kids/<id>/buildings/<id>/move`，正文為 `cell_x`、`cell_y`。

## 介面步驟（TC-FE-WAREHOUSE-UNSTORE）

合成小朋友：使用者名稱 `test_warehouse_kid`，PIN 為測試用 `1357`，等級 8，金幣 800。存倉一座圖書館，等級 2，舊座標 `(20, 12)`。視窗 1280×720。

對照稿是 PR #27 的 `3b4671d`，目錄 `mocks/town-four-scene-ux/`。取出必須走與新建造相同的程式路徑：場景 2 揀空地 → 場景 3 半透明預覽並確認。不要顯示價錢。落地時沿用新建造的放置特效掛點；特效的外觀只由設計檢視，測試只要求掛點出現。

1. 開啟 `/kids/`，以 `#loginUsername`、`#loginPassword` 與按鈕「🚪 登入」登入。`#app` 可見，`#village .cell-btn` 共 64 格。`#ktFooter`（class `kt-footer`）的結構必須與 `tests/fixtures/kt_footer_main.json` 相同。該檔是 main `5bfe76d` 在 1280×720 下的頁尾：正規化 outerHTML、每個後代的計算樣式，以及頁尾、分頁、圖示的 bounding box（四捨五入到 0.5px）。同一輪再截兩次圖，RGB 差必須為 0。不再使用 PNG 對照，以免不同系統的字型點陣造成假失敗。
2. 打開抽屜「☰」，再按「存倉」，`#tab-store.active` 與 `#storedBuildings` 可見。此時存倉數量為 1。
3. 「取出」按鈕的 bounding box 高度至少 44px。按下之後，以及之後每一步，`#placementBar` 都不得有 class `active`，也不得變成可見（預設 `display: none`）。不得出現 `.valid-plot`。`#townMap` 必須可見，點選發生在這張 8×8 地圖上。
4. 場景 2：點選 `#townMap` 內 aria-label 以「第 2 欄第 2 行」開頭的格子（資料庫座標 `(1, 1)`）。若新建造那一步的 `#btnToScene3`（「去擺位置」）可見且可按，則按下。
5. 場景 3：`#uxPlaceBar` 可見，所選格子上的 `img.ghost` 可見，`#btnUxConfirm`（「確定放置」）可按。`#uxPlaceBar`、`#placeStatus`、`#btnUxConfirm`、`#readyBar` 與預覽格不得出現價錢或費用：不得有 `💰`、`升級要`、`確定先至扣資源`，也不得有帶數字的金幣或材料。頁首資源列不在此限。
6. 按下確定。`POST .../unstored` 回 200 或 201。出現 `[data-town-fx="place"]`（新建造在 `town-four-scene.js` 的 `celebrate("place")` 會寫這個屬性）。`#townMap .cap` 出現「圖書館」。存倉數量變為 0。金幣與材料不變。
7. 重新載入後，等到 `#loginScreen` 可見或 `#app` 已就緒。`main` 沒有工作階段還原，會回到登入畫面；這時用同一個合成小朋友再登入一次。然後 `#loginScreen` 必須隱藏，`#townMap` 與 `#ktFooter` 必須可見。不要求重新載入本身保持登入。同一格仍標示圖書館。資料庫該行 `stored=0`、座標 `(1, 1)`、等級 2。頁尾結構仍與 JSON 相同，且與流程開始前的同一輪截圖 RGB 差為 0。選格中途也再比一次同一輪截圖。價錢檢查只看畫面上的放置條、狀態、確定按鈕、預覽格，以及畫面上可見的 `.pal-cost`；藏起來的建築清單不算。

`main` 上第 3 步失敗：清單文字為「圖書館 Lv.2」加「按此放置」，`[data-testid="warehouse-takeout"]` 與名稱正好為「取出」的按鈕數量都是 0。頁尾結構與同一輪像素比對在按下之前已經通過。

## 存倉卡片（TC-FE-WAREHOUSE-CARD）

同一合成小朋友，打開存倉。`#storedBuildings` 的文字必須含建築名稱與等級（`Lv`），並有「取出」按鈕。文字不得含「按此放置」。`main` 的卡片仍寫「按此放置」，沒有「取出」。

## 選擇器合約

建造者要在存倉取出流程補上這些節點。沿用四場景新建造已有的 id，不要另起一套放置條。既有 id 保留：`#storedBuildings`、`#townMap`、`#village`、`#btnUxConfirm`、`#btnToScene3`、`#uxPlaceBar`、`#placeStatus`、`#readyBar`、`#placementBar`、`#tab-store`、`#tab-town`、`#ktFooter`。

| 節點 | 要求 |
|------|------|
| `[data-testid="warehouse-list"]` | 存倉清單。可與現有 `#storedBuildings` 為同一節點。 |
| `[data-testid="warehouse-count"]` | 文字為存倉建築的整數數量。本案例取出前為 `1`，取出後為 `0`。 |
| `[data-testid="warehouse-takeout"]` | 按鈕。accessible name 正好是「取出」。`data-building-id` 等於 `buildings.id`。bounding box 高度 ≥ 44px。 |
| 取出之後 | 回到 `#tab-town` / `#townMap`，進入場景 2（與 `#btnBuild` 「我要起屋」之後同一條路）。`#placementBar` 在整個流程都不得 `.active` 或可見。不得顯示 `.valid-plot`。 |
| 選格 | `#townMap` 內現有 `.cell-btn`，aria-label 以「第 2 欄第 2 行」開頭。需要進入場景 3 時沿用 `#btnToScene3`，文字「去擺位置」。 |
| 預覽 | `#uxPlaceBar`、`#placeStatus`、`#btnUxConfirm`（「確定放置」）、所選格的 `img.ghost`。此處不顯示價錢。 |
| 落地特效 | `[data-town-fx="place"]`，與新建造的 `celebrate("place")` 相同。粒子的造型與時間只由設計檢視，測試不量顏色或顆數。 |
| 頁尾 | `#ktFooter.kt-footer` 的結構與 `tests/fixtures/kt_footer_main.json` 相同。流程前、選格中、流程後，同一輪截圖的 RGB 差為 0。不要改頁尾的標記或樣式。 |

「取出」是畫面上的書面語。不要再用「按此放置」進入 24×16 的 `#placementBar`。四場景調色盤若已有「放返」，本案例仍以存倉清單上的「取出」為準，以便從清單直接放到 8×8。

## 滿圖提示（人手，不設自動案例）

`main` `5bfe76d` 與建造尖端 `98ea4bf` 都沒有一條介面會送出「只有 `def_id`、沒有 `cell_x`／`cell_y`」的新建造。四場景的確定放置（`town-four-scene.js` 的 `onConfirm`）永遠帶所選格的 `cell_x`、`cell_y`。`index.html` 的 `confirmPlaceBuilding` 同樣帶這兩個欄位。`placeBuilding(defId, plotIdx)` 只送 `def_id` 與 `plot_idx`，後端會把它當成省略座標，但畫面上沒有呼叫 `clickEmptyPlot` 或 `placeBuilding` 的按鈕。後端只在兩個座標都省略、而且 8×8 沒有合法原點時，才回「城鎮沒有空位，請先收起或移動其他建築。」因此這句話在現有畫面上到不了。不設 `TC-FE-WAREHOUSE-FULL-TOAST`，也不另做一條假的按鈕路徑。

`98ea4bf`（`kids-town-v23`）已經放上中性樣式，失敗分支也改為 `showToast(message, 'info')`。`showToast` 在類型為 `info` 時把 class 設成 `info`。若日後有省略座標的建造路徑，自動案例要鎖下面這些值，只認 class，不要另外寫死選擇器：

| 項目 | 要求 |
|------|------|
| 節點 | `#toast`，class 含 `info`，不含 `error` |
| 底色 | `#6b4f2a`，計算值正好 `rgb(107, 79, 42)` |
| 字色 | `#fff8e7`，計算值正好 `rgb(255, 248, 231)` |
| 文字 | 正好「城鎮沒有空位，請先收起或移動其他建築。」 |
| 不得出現 | 價錢、`💰`、`金幣`、「扣」，以及紅色錯誤 modal |
| 其餘 | 字級與圓角與預設 `#toast` 相同。現行為 `font-size:13px`、`border-radius:20px`。 |

不要接受預設綠底（`#15803d`，計算值 `rgb(21, 128, 61)`），也不要接受 `.error` 紅底（`#ef4444`，計算值 `rgb(239, 68, 68)`）。`main` 沒有 `#toast.info`。

儲蓄頁的提取與刪除目標本來就呼叫 `showToast(..., 'info')`（「提取咗…」與「目標已刪除」）。`#toast.info` 落地之後，這兩句由綠底改為棕底。現有測試沒有鎖這兩句的顏色或 class，本輪不改那些測試。

## 對照 `98ea4bf`

同一套測試疊在建造尖端 `98ea4bf`（`kids-town-v23`，`#toast.info` 已落地）的暫用工作樹，沒有推上該分支。`restoreSession` 已在 `0c39ccf` 刪除，這個尖端沒有加回。

| ID | 98ea4bf |
|----|---------|
| 倉庫 API，除下列一條 | PASS。含 `BUILD-REJECT`（滿圖訊息正好是指定那句）、`REGION-AUTO`（空圖 201 於 `(0,0)` 並扣費；滿圖 400、不新增行）、`REGION-GRID`、`REGION-NO-AUTOSTORE`、`REPAIR-PLACED-LEGACY`、`BUILD-REUSE`（指定格子）。 |
| TC-API-WAREHOUSE-BUILD-REUSE-AUTO | FAIL。空圖把同一行放到 `(0,0)`（回應 `id` 1、`cell_x` 0、`cell_y` 0），但 HTTP 是 200，不是 201。滿圖半段沒有另外的失敗。 |
| TC-FE-WAREHOUSE-GRID、CARD、UNSTORE | PASS。取出走到重新載入之後再登入，`#loginScreen` 隱藏，`#townMap` 與 `#ktFooter` 可見，頁尾結構與同一輪像素比對通過。 |
| P1-TC-UNL-01、P1-TC-UNL-02、P1-TC-UNL-03 | PASS |
| TC-FE-WAREHOUSE-FULL-TOAST | 未設自動案例。見上方「滿圖提示」。 |
