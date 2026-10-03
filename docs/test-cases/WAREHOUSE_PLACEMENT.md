# 存倉放回 8×8 地圖

紅測。只加測試與本說明，不改產品代碼。`main`（`5bfe76dc5ad31b9fcfe2e273e5f2af3f1f750f7e`）上，建造與取出仍接受舊範圍 0–22 × 0–14；讀取建築時若原點落在 8×8 之外，會把該行改為 `stored=1`，且不退還已扣的金幣與材料。效果只計算 `stored=0` 的行，所以被收進存倉的建築失去加成，公會大廳亦無法使用。

格子原點規則：目錄裡每一座建築都是 2×2。`building_defs` 沒有每座自己的寬高或足跡欄，所以不另設 1×1 成功案例。合法條件是原點加足跡之後兩邊都不超出 8，而且不與 `stored=0` 的 2×2 重疊。`stored=1` 不佔格子。因此 `cell_x`、`cell_y` 都必須在 0 至 6（含），最遠合法原點是 `(6,6)`。`(7,0)`、`(0,7)`、`(7,7)` 足跡伸出地圖，必須拒絕，見 `TC-API-WAREHOUSE-PLACE-EDGE-7`。`(8,0)`、`(0,8)`、`(8,8)`、負數、以及舊座標如 `(20,12)` 仍然必須拒絕。燈塔、競技場、天文台解鎖之後使用同一套規則，沒有格外豁免。`P1-TC-UNL-02` 因此改為：解鎖區 3 之後，燈塔放在 `(8,0)` 必須 400 且金幣與材料不變；放在 8×8 內的空格 `(0,0)` 必須 201 且 `stored=0`。舊預期是 `(8,0)` 201。變更原因是 8×8 規則（Grok decision）。`(7,7)` 曾經被 `BUILD-OK`、`UNSTORE-OK`、`MOVE-OK` 當成合法原點，現已改到 `(6,6)`。

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
介面：`tests/test_warehouse_e2e.py` 的 `TC-FE-WAREHOUSE-UNSTORE`、`TC-FE-WAREHOUSE-CARD`、`TC-FE-WAREHOUSE-CARD-BODY`、`TC-FE-WAREHOUSE-SCENE2-LEGAL`、`TC-FE-WAREHOUSE-SCENE3-CANCEL`、`TC-FE-BUILD-SCENE2-NOREGRESS`、`TC-FE-WAREHOUSE-COPY-FORMAL`、`TC-FE-WAREHOUSE-RETURN-MAP`、`TC-FE-WAREHOUSE-TAKEOUT-FULL`、`TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL`、`TC-FE-WAREHOUSE-OFFGRID-TOAST`、`TC-FE-WAREHOUSE-CANCEL-TOAST-INFO`、`TC-FE-WAREHOUSE-BAR-NOOVERFLOW`、`TC-FE-TOWN-MAP-FIT`，以及同一 API 檔內讀取已提供頁面的 `TC-FE-WAREHOUSE-GRID`（後者屬 API 套件，因為它只 GET 靜態檔）。

下表「main」是在 `5bfe76d` 加上這些測試後的結果。紅測的斷言訊息寫明預期與實際。綠測是回歸鎖，不是本缺陷。

| ID | 行為 | main | 實際對預期 |
|----|------|------|------------|
| TC-API-WAREHOUSE-UNSTORE-OK | `POST /buildings/<id>/unstored` 到空的 `(6,6)` 或 `(1,1)`：HTTP 200，`stored=0`，Lv.2 保留，金幣與材料不變。`(7,7)` 改由 `PLACE-EDGE-7` 拒絕。 | PASS | 符合。2×2 最遠合法原點是 `(6,6)`。 |
| TC-API-WAREHOUSE-UNSTORE-OOB | `(8,0)`、`(0,8)`、`(8,8)`、`(20,12)` 必須 4xx，行維持 `stored=1`、原座標、資源不變。 | FAIL | 實際 HTTP 200，座標被改成該格外點；其後 GET 再把該行收成 `stored=1` 並留在新的不合法座標。 |
| TC-API-WAREHOUSE-UNSTORE-REJECT | 缺座標、負數、原點已被已放置建築佔用、地磚佔用：4xx，資料不變。 | PASS | 符合。 |
| TC-API-WAREHOUSE-UNSTORE-OVERLAP | 已放置健身室原點 `(0,0)` 時，醫院取出到 `(1,0)` 足跡重疊，必須 4xx；醫院仍 `stored=1` 於 `(20,12)`。 | FAIL | 實際 HTTP 200，醫院變成 `stored=0` 於 `(1,0)`。佔用檢查只比對原點。 |
| TC-API-WAREHOUSE-STORED-OCC | 存倉行的舊座標不佔地圖。另一座建築可取出到該原點；新建造亦可落在存倉行記錄的格子上（新建造仍扣目錄價）。 | FAIL | 取出到存倉圖書館的 `(0,0)` 得 400「該位置已被佔用」。在存倉銀行的 `(4,4)` 建造健身室得 400「該位置已被建築物佔用」。 |
| TC-API-WAREHOUSE-BUILD-OK | 空的 `(6,6)` 新建圖書館：201，扣目錄價（100 金幣、木材 5），GET 之後仍 `stored=0`、等級 1。`(7,7)` 不合法，見 `PLACE-EDGE-7`。 | PASS | 符合。 |
| TC-API-WAREHOUSE-PLACE-EDGE-7 | 目錄沒有每座建築的尺寸欄，全部 2×2，不設 1×1。`(7,0)`、`(0,7)`、`(7,7)` 的新建、移動、取出都必須 400，金幣與材料不變；新建不新增行，移動與取出的那一行不變。每個 `x<=6` 且 `y<=6` 的原點都被 2×2 擋住、只剩 `x=7` 或 `y=7` 空著時，省略座標的新建造與存倉放回都必須 400，不扣費、不新增、不改行。 | FAIL | 指定座標的新建回 201 並扣費（圖書館 8000→7900 金幣、木材 80→75），移動回 200，取出回 200，行被放到該格。省略座標的兩半在 main 已是 400（仍要求 `cell_x`、`cell_y`），金幣與行不變，所以這兩半沒有另外失敗。 |
| TC-API-WAREHOUSE-BUILD-OOB | `(8,0)`、`(0,8)`、`(8,8)`、`(20,12)` 建造：4xx，不扣資源，不新增行，不收入存倉。 | FAIL | 實際 201 並扣費（圖書館 8000→7900 金幣、木材 80→75）；GET 之後該行 `stored=1`，停在格外座標。 |
| TC-API-WAREHOUSE-BUILD-REJECT | 負數、原點佔用、地磚：4xx，不扣、不新增。省略座標不再當成拒絕。8×8 每個原點都被佔用時，省略座標的新建造必須 400，金幣與材料不變，不得新增該 `def_id` 的行。若回應有訊息，必須正好是「城鎮沒有空位，請先收起或移動其他建築。」原因：有空位時省略座標要自動放置，不能再把缺座標一律判失敗。 | FAIL | 負數、原點佔用、地磚，以及滿圖的 400、不扣、不新增都通過。訊息是 `def_id, cell_x, cell_y required`，不是「城鎮沒有空位，請先收起或移動其他建築。」 |
| TC-API-WAREHOUSE-BUILD-OVERLAP | 圖書館建在 `(1,0)`，與已放置健身室 `(0,0)` 的 2×2 重疊：4xx，不扣、不新增、不入倉。 | FAIL | 實際 201，扣 100 金幣與木材 5，新行 `stored=0` 於 `(1,0)`。 |
| TC-API-WAREHOUSE-BUILD-REUSE | 存倉已有 Lv.2 圖書館時，再 POST 建造該種類並指定格子：放回同一行到要求的格子，等級 2，不扣費，仍然只有一行。 | FAIL | 實際 400「你已經興建咗呢種建築物」；行維持 `stored=1` 於 `(20,12)`。未扣費，但沒有放回。 |
| TC-API-WAREHOUSE-BUILD-REUSE-AUTO | 同一座 `stored=1`、等級大於 1 的建築，POST 只帶 `def_id`、不帶座標。空圖：200 或 201，與 `BUILD-REUSE` 相同。放回的是已有那一行，不是新建，所以不要求 201。同一行變成 `stored=0` 於第一個合法格（空圖為 `(0,0)`），等級保留，不扣費，該 `def_id` 的行數不增加。滿圖：400，金幣與材料不變，該行仍是 `stored=1`、同一 id、同一等級，不新增。`BUILD-REUSE` 有指定格子，這條沒有。 | FAIL | 空圖省略座標回 400 `def_id, cell_x, cell_y required`。圖書館仍是 `stored=1`、等級 2、座標 `(20,12)`，沒有放到 `(0,0)`。滿圖該半段通過：400、資源不變、同一行維持 `stored=1`、沒有新增。 |
| TC-API-WAREHOUSE-MOVE-OOB | `POST /buildings/<id>/move` 到 `(8,0)`、`(0,8)`、`(8,8)`、`(-1,0)`、`(0,-1)`、`(20,12)`：4xx。行仍是 `stored=0` 且停在原格，資源不變。其後 GET `/buildings` 與 GET `/town` 也不得把它收倉。 | FAIL | 負數已是 4xx 且行不變。`(8,0)`、`(0,8)`、`(8,8)`、`(20,12)` 回 200 並改座標；GET 之後該行 `stored=1`，停在新的格外座標，而不是仍放置在原格。 |
| TC-API-WAREHOUSE-MOVE-OVERLAP | 已放置健身室在 `(0,0)` 時，把醫院從 `(4,0)` 移到 `(1,0)`（2×2 重疊）：4xx，醫院仍在 `(4,0)`、等級 2、資源不變。 | FAIL | 實際 HTTP 200，醫院改到 `(1,0)`。佔用檢查只比對原點。 |
| TC-API-WAREHOUSE-MOVE-STORED-OCC | 地圖上唯一佔用是存倉行留下的座標時，移動必須成功。存倉圖書館停在 `(0,0)` 時，健身室可移到 `(0,0)`，等級保留，不扣資源，圖書館仍 `stored=1`。 | FAIL | 實際 400「該位置已被佔用」，健身室仍在 `(4,4)`。 |
| TC-API-WAREHOUSE-MOVE-OK | 移到空的 `(6,6)`：200，`stored=0`，等級保留，不扣資源。GET `/buildings` 與 GET `/town` 之後仍放置在 `(6,6)`。`(7,7)` 不合法，見 `PLACE-EDGE-7`。 | PASS | 符合。 |
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
| TC-FE-WAREHOUSE-CARD-BODY | 點存倉卡片的圖示或名稱（不是「取出」）不得呼叫 `startUnstoreBuilding`，不得進入取出。`#placementBar` 不得 `.active`，維持 `display:none`、0×0。不得出現 `.valid-plot`，也不得出現「📍 選擇位置放置倉庫建築」。卡片沒有 `onclick`，計算游標不是 `pointer`。只有「取出」進入 `#townMap` 場景 2。 | FAIL | 點名稱呼叫了 `startUnstoreBuilding`。卡片有 `onclick="startUnstoreBuilding(...)"`，`cursor` 為 `pointer`。`#placementBar` 變成 `.active`、`display:flex`、底色 `rgb(99, 102, 241)`，文字是「📍 選擇位置放置倉庫建築」。出現 `.valid-plot`。清單沒有「取出」，所以沒有再測按鈕進入場景 2。 |
| TC-FE-WAREHOUSE-SCENE2-LEGAL | 取出後的場景 2，金色可選格的集合必須正好等於合法原點（順序不論，且不得有重複格）。點非法、非金色的已佔用格，提示正好是「這個位置已經有建築物。」，class 為 `info` 而不是 `error`，底色 `rgb(107, 79, 42)`。金幣與材料不變。 | FAIL | 清單沒有「取出」（文字是「📚 / 圖書館 Lv.2 / 按此放置」），進不了取出場景 2。 |
| TC-FE-WAREHOUSE-SCENE3-CANCEL | 取出、選合法格、進入場景 3 之後按「取消」，回到取出場景 2。`#readyStatus` 正好是「請點選空地，放回「圖書館」。不扣除金幣和材料。」不得回到普通建造場景 2，不得出現「喺存倉」「用存倉放返」「唔使再扣資源」。`#placementBar` 維持不啟動。資源不變。 | FAIL | 同樣沒有「取出」，進不了場景 3。 |
| TC-FE-BUILD-SCENE2-NOREGRESS | 普通新建造場景 2 仍在 `#townMap`。點索引不大於 6 的合法金色格，選未興建的健身室，確認後放置並只扣目錄價一次（200 金幣、木材 10、磚 5）。三句提示改為書面語（見下方）。金色格是否正好等於合法原點，改由 `TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL` 鎖。 | FAIL | 放置本身通過：一次 201，只扣目錄價。三句提示仍是舊口語。 |
| TC-FE-WAREHOUSE-COPY-FORMAL | 放置流程的口語改為書面語。舊字串在五個產品檔裡必須是 0 次（跳過升級、儲蓄等後備行）。新句子必須出現在對應畫面。清單徽章「已起」改「已興建」，「未起」改「未興建」。見下方對照。 | FAIL | 原始碼與畫面仍是舊字。詳見下方。 |
| TC-FE-WAREHOUSE-RETURN-MAP | 新建造場景 2 與取出場景 2，按 `#btnUxBack`「返回地圖」回到場景 1。不扣資源。取出時那一行維持 `stored=1`。 | FAIL | 新建造：按鈕仍是「返去睇地圖」，按下去停在場景 2。取出：沒有「取出」，進不了場景 2。 |
| TC-FE-WAREHOUSE-TAKEOUT-FULL | 九座健身室佔滿每個合法原點、圖書館存倉時，按「取出」或在場景 2 建築清單點圖書館，都不得進入取出場景 2，並以 `#toast.info` 顯示「城鎮沒有空位，請先收起或移動其他建築。」行與資源不變。 | FAIL | 沒有「取出」。清單點擊後調色盤關上，畫面變成場景 3，提示仍是普通建造那句，沒有滿圖提示。 |
| TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL | 新建造場景 2 的金色格集合必須正好等於合法原點。進入場景 3 之後，金色格不得多過合法原點，而且每一格要麼是合法原點，要麼落在所選預覽的 2×2 裡。 | FAIL | 場景 2 把空格（含第 8 欄、第 8 行）都塗金，多於合法原點。場景 3 亦然。 |
| TC-FE-WAREHOUSE-OFFGRID-TOAST | 取出場景 2 與新建造場景 2，點放不下的空格（第 8 欄第 1 行，以及與已放置 2×2 重疊的空格）提示正好是「這個位置放不下這座建築物。」已佔用格仍是「這個位置已經有建築物。」兩者都是 `#toast.info`。 | FAIL | 取出進不去。新建造點空格只是選格，沒有提示；點已佔用格打開升級面板，也沒有這句。 |
| TC-FE-WAREHOUSE-CANCEL-TOAST-INFO | 場景 3 按「取消」，文字維持「已取消，資源未扣除」，但必須是 `#toast.info`（底 `rgb(107, 79, 42)`、字 `rgb(255, 248, 231)`），不是預設綠底。新建造與取出各測一次。 | FAIL | 新建造文字正確，class 是空的，底色 `rgb(21, 128, 61)`。取出進不去。 |
| TC-FE-WAREHOUSE-BAR-NOOVERFLOW | 1280×720 與 1100×800：底欄「返回地圖」「選擇位置」「確定放置」「取消」為 `white-space:nowrap`，高至少 45px，左右 padding 至少 13px，文字不溢出，四字按鈕寬至少 90px，「取消」至少 58px。中間提示一行。390×720 只查按鈕文字不溢出。 | FAIL | 1280×720 與 1100×800：`white-space` 是 `normal`，高 44（1100 縮到 37.8），padding 0，寬度低於下限。390 沒有溢出。 |
| TC-FE-TOWN-MAP-FIT | 1280×720。場景 1（商店在 `(0,6)`、農場在 `(6,0)`）、新建造場景 2、取出場景 2：`#townMap` 的 `scrollWidth` 不得大於 `clientWidth`。每一格金色的外框，以及每一座已放置建築的 `img.sprite`，橫向必須落在 `#townMap` 可見範圍內（左 ≥ 框左 −1px，右 ≤ 框右 +1px）。不查直向。 | FAIL | 場景 1 與新建造場景 2：`scrollWidth` 等於 `clientWidth`（1178/1178），但 `(0,6)` 的商店圖 `x=14–174`，框左是 51，左側伸出 37px。新建造金色格伸到 `x=-70` 與 `x=1266`（框是 51–1229）。取出進不去。農場 `(6,0)` 的圖 `x=1022–1182` 在框內。 |

拒絕狀態只接受 400、409、422。401 不算成功拒絕。取出成功為 200 或 201。放回已有存倉行（指定格子或省略座標）成功為 200 或 201。新建（沒有可再用的存倉行）成功為 201。移動成功為 200。

移動端點是 `POST /api/kids/<id>/buildings/<id>/move`，正文為 `cell_x`、`cell_y`。

## 介面步驟（TC-FE-WAREHOUSE-UNSTORE）

合成小朋友：使用者名稱 `test_warehouse_kid`，PIN 為測試用 `1357`，等級 8，金幣 800。存倉一座圖書館，等級 2，舊座標 `(20, 12)`。視窗 1280×720。

對照稿是 PR #27 的 `3b4671d`，目錄 `mocks/town-four-scene-ux/`。取出必須走與新建造相同的程式路徑：場景 2 揀空地 → 場景 3 半透明預覽並確認。不要顯示價錢。落地時沿用新建造的放置特效掛點；特效的外觀只由設計檢視，測試只要求掛點出現。

1. 開啟 `/kids/`，以 `#loginUsername`、`#loginPassword` 與按鈕「🚪 登入」登入。`#app` 可見，`#village .cell-btn` 共 64 格。`#ktFooter`（class `kt-footer`）的結構必須與 `tests/fixtures/kt_footer_main.json` 相同。該檔是 main `5bfe76d` 在 1280×720 下的頁尾：正規化 outerHTML、每個後代的計算樣式，以及頁尾、分頁、圖示的 bounding box（四捨五入到 0.5px）。同一輪再截兩次圖，RGB 差必須為 0。不再使用 PNG 對照，以免不同系統的字型點陣造成假失敗。
2. 打開抽屜「☰」，再按「存倉」，`#tab-store.active` 與 `#storedBuildings` 可見。此時存倉數量為 1。
3. 「取出」按鈕的 bounding box 高度至少 44px。按下之後，以及之後每一步，`#placementBar` 都不得有 class `active`，也不得變成可見（預設 `display: none`）。不得出現 `.valid-plot`。`#townMap` 必須可見，點選發生在這張 8×8 地圖上。
4. 場景 2：點選 `#townMap` 內 aria-label 以「第 2 欄第 2 行」開頭的格子（資料庫座標 `(1, 1)`）。若 `#btnToScene3` 可見且可按，則按下。按鈕文字由 `TC-FE-WAREHOUSE-COPY-FORMAL` 鎖定為「選擇位置」。
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
| 選格 | `#townMap` 內現有 `.cell-btn`，aria-label 以「第 2 欄第 2 行」開頭。需要進入場景 3 時沿用 `#btnToScene3`。文字必須是「選擇位置」，見 `TC-FE-WAREHOUSE-COPY-FORMAL`。已選格的 aria-label 是「第 N 欄第 M 行，已選此格」。 |
| 預覽 | `#uxPlaceBar`、`#placeStatus`、`#btnUxConfirm`（「確定放置」）、所選格的 `img.ghost`。此處不顯示價錢。 |
| 落地特效 | `[data-town-fx="place"]`，與新建造的 `celebrate("place")` 相同。粒子的造型與時間只由設計檢視，測試不量顏色或顆數。 |
| 頁尾 | `#ktFooter.kt-footer` 的結構與 `tests/fixtures/kt_footer_main.json` 相同。流程前、選格中、流程後，同一輪截圖的 RGB 差為 0。不要改頁尾的標記或樣式。 |

「取出」是畫面上的書面語。不要再用「按此放置」進入 24×16 的 `#placementBar`。四場景調色盤若已有「放返」，本案例仍以存倉清單上的「取出」為準，以便從清單直接放到 8×8。

## 原點 7（TC-API-WAREHOUSE-PLACE-EDGE-7）

先讀 `building_defs`。沒有寬、高、足跡這類欄位，目錄裡每一行都按 2×2，不測 1×1。地圖是 8×8，最遠合法原點是 `8 - 2 = 6`，測試不把 6 寫死成與足跡無關的常數。

`(7,0)`、`(0,7)`、`(7,7)` 各做三次：`POST /buildings` 新建圖書館、把已放置的醫院從 `(0,0)` 移過去、把存倉醫院取出到該格。三次都必須是 400、409 或 422。金幣與材料不變。新建不得新增行。移動與取出之後該行與呼叫前相同。

自動選格：用九座健身室佔住 `(0,0)`、`(2,0)`、`(5,0)`、`(0,2)`、`(2,2)`、`(5,2)`、`(0,5)`、`(2,5)`、`(5,5)`。這些 2×2 互不重疊，而且每一個 `x<=6`、`y<=6` 的原點都與其中一座重疊。`(7,0)`、`(0,7)`、`(7,7)` 與它們不重疊，但足跡伸出地圖。此時省略座標、只送圖書館的 `def_id`：新建造必須 400，不扣費、不新增。存倉裡已有等級 2 的圖書館時，同樣省略座標必須 400，該行維持 `stored=1`、同一 id、同一等級，不新增。

## 卡片本體（TC-FE-WAREHOUSE-CARD-BODY）

同一合成小朋友，打開存倉。點卡片裡的名稱或圖示，不點「取出」。`startUnstoreBuilding` 不得被呼叫。`#placementBar` 不得加上 `.active`，維持 `display:none`，bounding box 為 0×0（啟動後才是 `display:flex`，底色 `#6366f1`）。不得出現 `.valid-plot`，畫面上不得出現「📍 選擇位置放置倉庫建築」。`.build-card` 不得有 `onclick`，計算樣式的 `cursor` 不得是 `pointer`。只有「取出」（`[data-testid="warehouse-takeout"]` 或 accessible name「取出」）進入 `#townMap` 場景 2，而且 `#placementBar` 仍然不啟動。

## 取出場景 2 的合法格（TC-FE-WAREHOUSE-SCENE2-LEGAL）

存倉圖書館之外，另放健身室於 `(0,0)`、農場於 `(4,4)`，兩座都是 `stored=0`。測試在頁面之外計算合法原點：`x`、`y` 都在 0 至 6，且 2×2 不與這兩座重疊。存倉行不算佔用。

按下「取出」之後，`#townMap` 為場景 2。金色可選格收集自 `#townMap .pad`：class 含 `is-empty-hot` 或 `is-chosen`，而且可見的 `.mark` 帶金色 `drop-shadow`（`rgba(212, 160, 23, 0.95)`）。格子座標由 aria-label「第 N 欄第 M 行」換算，資料庫格是 `(N-1, M-1)`。比較時把它們當成集合，順序不論（畫面可以先欄後行，合法原點可以先行後欄）。集合必須與合法原點相等，不多也不少。同一格不得出現兩次。

再點已佔用、不該是金色的「第 1 欄第 1 行」。`#toast` 文字正好是「這個位置已經有建築物。」，class 含 `info`、不含 `error`，計算底色正好 `rgb(107, 79, 42)`。金幣與材料不變。

## 取消預覽（TC-FE-WAREHOUSE-SCENE3-CANCEL）

只留存倉圖書館。取出後點 `(0,0)`（索引 0，不大於 6）。若 `#btnToScene3` 可見且可按，則按下，進入場景 3。按 `#btnUxCancel`「取消」。

必須回到取出的場景 2，`#readyStatus` 正好是「請點選空地，放回「圖書館」。不扣除金幣和材料。」不得變成普通建造。舊句「點金色空地，或者打開清單揀一座未起嘅屋。」「已揀「圖書館」同呢格空地。」「已揀空地。打開清單，揀一座未起嘅屋。」和新句「請點選金色空地，或打開清單選擇要興建的建築物。」「已選擇「圖書館」和這個位置。」「已選擇空地。請打開清單，選擇要興建的建築物。」都不得出現。可見文字不得含「喺存倉」「用存倉放返」「唔使再扣資源」。`#placementBar` 不得 `.active`。金幣與材料不變。

## 新建造不回歸（TC-FE-BUILD-SCENE2-NOREGRESS）

清掉這個小朋友的建築，金幣 800，木材 10、磚 5。目錄裡健身室是 200 金幣、木材 10、磚 5。登入後按「我要起屋」。場景 2 在 `#townMap`。點第一格兩邊索引都不大於 6 的金色格（不用第 8 欄）。打開「建築清單」，選健身室：aria-label 含「未興建」或「未起」，而且不是已放置的鎖（「已興建」，或只有「已起」而沒有「未起」「未興建」）。按 `#btnToScene3`，再按「確定放置」。正好一次 `POST /buildings`，狀態 201。資料庫只扣目錄價一次，新行是等級 1 的健身室、`stored=0`、座標就是剛點的那一格。

三句提示改在放置成功之後才斷言，句子是新的書面語：

- 一進場景 2，`#readyStatus` 正好是「請點選金色空地，或打開清單選擇要興建的建築物。」
- 選了健身室之後，`#readyStatus` 正好是「已選擇「健身室」和這個位置。」
- 場景 3 的 `#placeStatus` 正好是「按「確定放置」後才扣除資源；取消不會扣除。」

金色格是否正好等於合法原點，本案例不再要求。那件事由 `TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL` 鎖。`main` 與 `25b959a` 上放置都通過，三句提示仍是舊口語，所以這條現在失敗。

## 新建造場景 2 的合法格（TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL）

商店放在 `(4,4)`、`stored=0`。測試在頁面之外計算合法原點：`x`、`y` 都在 0 至 6，2×2 不與商店重疊。存倉行不算佔用。

按「我要起屋」之後，金色格的集合必須正好等於這些合法原點，不得有重複格。這裡的金色不看 `is-empty-hot`：任何可見的 `.mark`，只要 `filter` 同時含 212、160、23（`rgba(212, 160, 23, 0.95)`），就算金色。場景 3 用的是 `is-valid`、`is-preview`、`is-illegal`，樣式一樣會把前兩種塗金。

再點 `(0,0)`，選健身室，進入場景 3。金色格的數量不得多過場景 2 的合法原點數。每一格要麼是合法原點，要麼落在所選預覽的四格 `(0,0)`、`(1,0)`、`(0,1)`、`(1,1)`。

`25b959a` 的新建造場景 2 把每一個沒有原點佔用的格子都塗金（含第 8 欄、第 8 行，以及與商店 2×2 重疊的空格）。量到 63 格，合法原點 40 格，沒有缺格，多出來的含 `(0,7)`、`(3,3)`、`(4,3)`。場景 3 仍是 63 格，超出合法原點，也超出預覽的四格。

## 返回地圖（TC-FE-WAREHOUSE-RETURN-MAP）

新建造場景 2，以及取出場景 2，各測一次。`#btnUxBack` 的文字必須是「返回地圖」。按下之後 `#townMap` 的 aria-label 含「場景 1」。金幣與材料不變。取出那一次，圖書館那一行與按下之前相同（仍是 `stored=1`）。

`25b959a` 的按鈕文字已經是「返回地圖」，但 `wire()` 沒有綁 `#btnUxBack`。兩種場景按下之後都停在場景 2。`main` 的新建造按鈕仍是「返去睇地圖」，按下也停在場景 2；取出則沒有「取出」按鈕。

## 滿圖時取出（TC-FE-WAREHOUSE-TAKEOUT-FULL）

佈局與 `PLACE-EDGE-7` 的滿圖相同：九座健身室在 `(0,0)`、`(2,0)`、`(5,0)`、`(0,2)`、`(2,2)`、`(5,2)`、`(0,5)`、`(2,5)`、`(5,5)`，圖書館 `stored=1` 於 `(20,12)`。這時沒有合法原點。兩個入口都要測：存倉卡片上的「取出」，以及新建造場景 2 的「建築清單」裡點圖書館（產品的調色盤，不是升級面板）。

正確行為：留在原來的畫面，不得進入取出場景 2。`#toast` 的文字正好是「城鎮沒有空位，請先收起或移動其他建築。」class 含 `info`、不含 `error`，底色 `rgb(107, 79, 42)`，字色 `rgb(255, 248, 231)`。圖書館那一行不變，金幣與材料不變。

`25b959a` 的 `beginWarehousePlace` 不論地圖滿不滿都把場景設成 2。按「取出」之後存倉頁關掉、場景是 2，沒有這句提示。點清單裡的圖書館也進入取出場景 2，提示變成「請點選空地，放回「圖書館」。不扣除金幣和材料。」`main` 沒有「取出」。清單點擊後調色盤關上，畫面是場景 3，提示仍是普通建造那句。

省略座標的新建造仍然沒有畫面上的按鈕會送出。後端那條路徑仍由 API 案例鎖，這裡不另做假按鈕。

## 放不下與已經有建築物（TC-FE-WAREHOUSE-OFFGRID-TOAST）

健身室放在 `(0,0)`，圖書館存倉。取出場景 2 與新建造場景 2 都測。新建造先在清單選醫院，讓場景知道要放哪一座。

點放不下的空格，`#toast.info` 的文字必須正好是「這個位置放不下這座建築物。」不是「這個位置已經有建築物。」兩種放不下都要點：第 8 欄第 1 行（索引 7，足跡伸出地圖），以及與健身室 2×2 重疊的空格 `(1,0)`。再點真正被健身室佔住的 `(0,0)`，提示必須正好是「這個位置已經有建築物。」，同樣是 `info`。金幣、材料與行都不變。

8×8 的格子都可以點。若第 8 欄不存在，測試改點 `(1,0)`，並且不會只因為改點而失敗。這一輪兩端都有第 8 欄，沒有改點。

`25b959a` 的取出場景 2：只要 `footprintFree` 為假（索引 7 與足跡重疊都算），提示都是「這個位置已經有建築物。」所以放不下的兩格失敗，已佔用的 `(0,0)` 通過（文字、`info`、棕底都對）。新建造場景 2 點空格只是選中，沒有提示；點已佔用格打開升級面板，也沒有「這個位置已經有建築物。」`SCENE2-LEGAL` 仍要求已佔用格顯示後一句，那條在 `25b959a` 上通過。

## 取消提示的底色（TC-FE-WAREHOUSE-CANCEL-TOAST-INFO）

新建造與取出都進到場景 3，按「取消」。文字必須正好是「已取消，資源未扣除」。class 含 `info`、不含 `error`。底色 `rgb(107, 79, 42)`，字色 `rgb(255, 248, 231)`。不要預設綠底 `rgb(21, 128, 61)`。

`25b959a` 的 `cancelPreview` 呼叫 `showToast("已取消，資源未扣除")`，沒有傳 `info`。文字正確，class 是空的，底色是綠的。`showToast` 已經認得 `info`，`#toast.info` 也在。`main` 的 `showToast` 只分錯誤與空白 class，而且沒有 `#toast.info`。取出在 `main` 上進不去。

`UX-03` 仍只查取消文字含「已取消」「未扣除」，不鎖底色。

## 底欄不溢出（TC-FE-WAREHOUSE-BAR-NOOVERFLOW）

新建造場景 2 量 `#btnUxBack`、`#btnToScene3`、`#readyStatus`。進入場景 3 之後量 `#btnUxCancel`、`#btnUxConfirm`、`#placeStatus`。按 id 量，不按按鈕上的舊字。

1280×720 與 1100×800：

- 按鈕的計算 `white-space` 是 `nowrap`。
- 高度至少 45px（規格 46，允許少 1）。
- 左右 padding 至少 13px（規格 14，允許少 1）。
- `scrollWidth` 不得大於 `clientWidth`。
- 畫出來的寬度：四個字的按鈕至少 90px，「取消」至少 58px。不讀 CSS 的 `min-width`。
- 中間提示用 `Range.getClientRects()` 數行，必須是 1。區塊元素自己的 `getClientRects()` 包行時仍是 1，所以改數文字行。

390×720 只查按鈕的 `scrollWidth` 不大於 `clientWidth`。不查寬、高、padding、提示行數。

`25b959a` 與 `main` 的底欄按鈕共用 `min-height:44px`，沒有水平 padding。1280×720：`white-space` 是 `normal`，高 44，padding 0/0。「返回地圖」與「選擇位置」「確定放置」寬 70，「取消」寬 44。1100×800 因畫面縮放，高約 37.8，四字按鈕寬約 60.2，「取消」約 37.8。390 沒有量到溢出。提示在 1280 與 1100 是一行，這部分通過。

## 地圖橫向不裁切（TC-FE-TOWN-MAP-FIT）

視窗 1280×720。商店放在左緣合法原點 `(0,6)`，農場放在右緣合法原點 `(6,0)`，圖書館存倉以便進入取出場景 2。三個畫面都量：場景 1、新建造場景 2（有金色格）、取出場景 2（有金色格）。

`#townMap` 的 `scrollWidth` 不得大於 `clientWidth`。每一格金色（與上一節相同的 `.mark` filter）的格子外框，以及每一座已放置建築的 `img.sprite`，橫向必須落在 `#townMap` 的可見矩形裡：左 ≥ 框左 −1px，右 ≤ 框右 +1px。不查直向，也不要求直向不捲動。

在無頭 Chromium、視窗正好 1280×720 下量到的數字，`main` `5bfe76d` 與 `25b959a` 相同（取出場景 2 在 `main` 進不去）：

| 畫面 | scrollWidth / clientWidth | 框（左..右） | 金色格橫向 | 建築圖 |
|------|---------------------------|--------------|------------|--------|
| 場景 1 | 1178 / 1178 | 51..1229 | 沒有金色格 | 商店 `(0,6)`：14–174，左側伸出框 37px。農場 `(6,0)`：1022–1182，在框內。 |
| 新建造場景 2 | 1178 / 1178 | 51..1229 | −70..1266，左右都伸出框 | 同上，商店仍伸出。 |
| 取出場景 2（只 `25b959a`） | 1178 / 1178 | 51..1229 | 182..1014，在框內 | 商店仍是 14–174，伸出框。 |

`scrollWidth` 並沒有大於 `clientWidth`。裁切發生在絕對定位的格子與建築圖伸出 `#townMap` 的可見矩形，村子本身 `overflow-x:hidden`，所以捲動寬度沒有變大。設計稿在 `25b959a` 上記的是框左 59、商店約 10–178（伸出約 49px）、`scrollWidth` 1211 大於 `clientWidth` 1162。這一輪的無頭測量沒有重現那組捲動數字；兩端都是 1178 等於 1178，商店圖是 14–174、框左 51（伸出 37px）。失敗原因仍是左緣建築（以及新建造的金色格）沒有整段落在 `#townMap` 裡面。`main` 有同樣的左緣裁切。

## 書面語（TC-FE-WAREHOUSE-COPY-FORMAL）

只掃這五個檔：`index.html`、`town-four-scene.js`、`town-four-scene.css`、`backend_v2.py`、`service-worker.js`。不掃 `tests/`、`docs/`、`mocks/`。一行裡若含後備標記，就整行跳過，避免升級、儲蓄、非倉庫畫面把這條打紅。後備標記對上這些行（`25b959a`）：`town-four-scene.js` 的「打唔中」「金幣唔夠」「確定先至扣，取消只關呢個視窗。」「領唔到」「再點一塊金色空地」「撳「升級」會彈出確認窗」「升級唔到」；`index.html` 的「先揀位置，再按「確認」建造」「確定收起呢棟建築物」「㩒此放置」「選擇要起嘅建築」。材料不夠那行只寫「唔夠」，不含下面的舊字，所以不用標記。「我要起屋」這個按鈕名稱不改。其他畫面的口語不在這條裡。

協調紀錄寫的是「㨒」（U+3A12）。`25b959a` 的 `index.html` 實際是「㩒」（U+3A52）。掃描用共同的尾巴「要放返出嚟」與「入去揀建築物放返」，兩個字都會失敗。

舊字必須是 0 次：未起嘅屋、同呢格空地、確定先至扣資源、撳一下就揀、已經有屋，唔可以放、撳一下就搬去呢格、，放返、想喺呢度起屋、唔可以放、放唔返、起唔到、存倉吉咗、要放返出嚟、入去揀建築物放返、呢格、已起、未起。「確定先至扣資源」對不上後備那句「確定先至扣，」。

畫面上要出現的新字，對照如下。

| 舊 | 新 |
|----|----|
| 點金色空地，或者打開清單揀一座未起嘅屋。 | 請點選金色空地，或打開清單選擇要興建的建築物。 |
| 已揀「X」同呢格空地。 | 已選擇「X」和這個位置。 |
| 已揀空地。打開清單，揀一座未起嘅屋。 | 已選擇空地。請打開清單，選擇要興建的建築物。 |
| 確定先至扣資源。取消唔會扣。 | 按「確定放置」後才扣除資源；取消不會扣除。 |
| 空地，撳一下就揀 | 空地，點選即可選擇 |
| 呢格（已選徽章與 aria） | 此格／已選此格 |
| X，已起 | X，已興建 |
| X，未起 | X，未興建 |
| 已起 N | 已興建 N |
| 已經有屋，唔可以放 | 已有建築物，不能放置 |
| 可以放，撳一下就搬去呢格 | 可以放置，點選即可移到此格 |
| X，放返 | X，放回 |
| 想喺呢度起屋？先撳「我要起屋」。 | 想在這裏興建？請先按「我要起屋」。 |
| 呢度已經有X，唔可以放。 | 這裏已有「X」，不能放置。 |
| 放唔返 | 未能放回 |
| 起唔到 | 未能興建 |
| 📦 存倉吉咗，未有建築物 | 📦 存倉是空的，暫時沒有建築物。 |
| 📦 存倉吉咗 | 📦 存倉是空的 |
| 㩒要放返出嚟嘅建築物 | 請點選要放回地圖的建築物 |
| 㩒入去揀建築物放返出嚟 | 點選進入，選擇要放回的建築物 |

清單徽章文字「存倉」維持不變。`fetchAPI` 丟出的錯誤總是有訊息，所以「未能放回」「未能興建」這兩個後備字不會自己出現。測試在其他畫面查完之後，把 `window.fetchAPI` 換成丟出空訊息的函式，再按確定。原始碼裡也必須看得到這兩個新字。空訊息會弄壞後續請求，所以接著重新載入再查存倉 modal。

種子是存倉圖書館 `(20,12)` 加上已放置商店 `(4,4)`，這樣才能同時看到「已興建」和「這裏已有「商店」，不能放置。」

`25b959a` 上「返回地圖」「選擇位置」「已選此格」已經落地，這三項沒有再失敗。其餘舊字仍在。畫面例子：場景 2 閒置提示仍是「點金色空地…」，徽章是「呢格」，清單是「商店，已起」「健身室，未起」「圖書館，放返」，計數是「已起 1」，空存倉是「📦 存倉吉咗，未有建築物」，空訊息時的失敗提示是「起唔到」與「放唔返」。註解「Not a map 「已起」」也含「已起」，算一次命中。

## 舊介面案例對齊

行為案例同時接受舊字與新字，避免文案還沒改完時把回歸打紅。文案案例才要求新字。

- `TC-FE-TOWN-UX-02`：金色框改為「每一個合法原點都有框」，不再要求金色格等於全部空格。索引 7 多出來的金由 `NEWBUILD-LEGAL` 鎖。清單必須出現「已興建」（不再接受只有「已起」）。
- `TC-FE-TOWN-UX-03`：已佔用提示接受「不能放置」「已有」或舊的「唔可以」「已經有」。取消仍只查文字含「已取消」「未扣除」。
- `TC-FE-TOWN-UX-05`：跳過按鈕的正則加上「已興建」「已起」。
- `TC-FE-TOWN-GRID-01`、清單裡的未建列：接受「未興建」或「未起」。
- `TC-FE-TOWN-STORE-LEGACY-02`、`STORE-LIST`：已放置的鎖接受「已興建」或「已起」。空存倉接受「存倉吉咗」或「存倉是空的」。
- 扣費確認句接受「確定先至扣資源」或「按「確定放置」後才扣除資源」，這樣取出案例仍能抓住不該出現的扣費句。
- `SCENE3-CANCEL` 同時排除舊的與新的普通建造提示。
- `UX-03`、`UX-04`、`UX-05`、`HIT`、`FX`、`MOTION` 進入場景 3 時，只要求合法原點有金框，不要求索引 7 也是金的。

`TC-FE-TOWN-STORE-LEGACY-02`、`STORE-PLACE-01`、`STORE-CONFIRM-01` 仍從卡片上的「取出」開始，不點卡片本體。

## 建築清單直接取出（TC-FE-TOWN-STORE-UX-01）

在場景 2 打開「建築清單」，點一座已經在存倉的建築（本案例是探險公會；圖書館同理）。必須直接進入取出場景 2，與按下「取出」同一條路。`#readyStatus` 正好是「請點選空地，放回「探險公會」。不扣除金幣和材料。」`#placementBar` 不得 `.active`。這一步不顯示價錢，也不扣金幣或材料。其後在 8×8 上確定，仍是 `POST /unstored`，同一行變成 `stored=0`，等級保留。

`25b959a` 的 `onPalette` 在存倉列上呼叫 `beginWarehousePlace`，這條通過。滿圖時不該走這條路，由 `TAKEOUT-FULL` 鎖。

## 對照 `25b959a`

同一套測試疊在建造尖端 `25b959af792b15502a3ebf4ad6bf24e75cbec6e6` 的暫用工作樹 `/tmp/kt-green-25b959a`，沒有提交、沒有推上該分支。產品檔是該提交，測試檔是本紅測分支。

| ID | main `5bfe76d` | `25b959a` |
|----|----------------|-----------|
| TC-API-WAREHOUSE-PLACE-EDGE-7 | FAIL。`(7,0)`、`(0,7)`、`(7,7)` 的新建 201 並扣費，移動 200，取出 200。省略座標的兩半已是 400。 | PASS |
| TC-FE-WAREHOUSE-CARD-BODY | FAIL。點名稱呼叫 `startUnstoreBuilding`，`#placementBar` `.active`。 | PASS |
| TC-FE-WAREHOUSE-SCENE2-LEGAL | FAIL。沒有「取出」。 | PASS。金色格與合法原點集合相等。已佔用格的提示是「這個位置已經有建築物。」且為 `info`。 |
| TC-FE-WAREHOUSE-SCENE3-CANCEL | FAIL。沒有「取出」。 | PASS |
| TC-FE-BUILD-SCENE2-NOREGRESS | FAIL。放置 201 且只扣一次。三句提示仍是舊口語。 | FAIL。同樣是放置通過、提示仍是舊口語。 |
| TC-FE-WAREHOUSE-COPY-FORMAL | FAIL。按鈕仍是「返去睇地圖」「去擺位置」，其餘舊字也在。沒有「取出」，所以取不出「未能放回」。 | FAIL。見上方。「返回地圖」「選擇位置」「已選此格」已通過，其餘舊字仍在，含「放唔返」「起唔到」。 |
| TC-FE-WAREHOUSE-RETURN-MAP | FAIL。新建造按鈕是「返去睇地圖」，按下停在場景 2。取出沒有「取出」。 | FAIL。按鈕已是「返回地圖」，兩種場景按下都停在場景 2。 |
| TC-FE-WAREHOUSE-TAKEOUT-FULL | FAIL。沒有「取出」。清單點擊進入場景 3，沒有滿圖提示。 | FAIL。兩個入口都進入取出場景 2，沒有「城鎮沒有空位…」。 |
| TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL | FAIL。金色 63，合法 40。場景 3 同樣 63。 | FAIL。同一組數字。 |
| TC-FE-WAREHOUSE-OFFGRID-TOAST | FAIL。取出進不去。新建造點空格與已佔用格都沒有提示。 | FAIL。取出：放不下的兩格都顯示「這個位置已經有建築物。」已佔用格那句通過。新建造：空格只是選中，已佔用格打開升級面板，都沒有對應提示。 |
| TC-FE-WAREHOUSE-CANCEL-TOAST-INFO | FAIL。新建造文字正確、綠底。取出進不去。 | FAIL。兩種場景文字都是「已取消，資源未扣除」，class 空白，底色 `rgb(21, 128, 61)`。 |
| TC-FE-WAREHOUSE-BAR-NOOVERFLOW | FAIL。見上方尺寸。390 無溢出。 | FAIL。同一組尺寸（「返回地圖」在 1280 寬 70，`main` 上舊字「返去睇地圖」寬 86）。390 無溢出。 |
| TC-FE-TOWN-MAP-FIT | FAIL。見上方數字。取出場景 2 沒有量到。 | FAIL。`scrollWidth` 1178 等於 `clientWidth` 1178。商店圖 14–174，框左 51。三個畫面都裁到這張圖。取出場景 2 的金色格在框內。 |
| TC-FE-TOWN-UX-02 | FAIL。斷言停在「選擇位置」（按鈕仍是「去擺位置」），還沒查到清單。 | FAIL。合法原點有金框，「選擇位置」已在。清單仍是「已起」，`get_by_text("已興建")` 是 0。 |
| TC-FE-TOWN-UX-03、UX-04、UX-05、FX-01、FX-02、MOTION-01 | FAIL。場景 2 沒有「選擇位置」。 | PASS |
| TC-FE-TOWN-HIT-01、HIT-02 | FAIL。已選格仍是「已揀呢格」。 | PASS |
| TC-FE-TOWN-GRID-01 | FAIL。「選擇位置」沒有變成可按。 | PASS |
| TC-FE-TOWN-STORE-LEGACY-02、STORE-PLACE-01、STORE-CONFIRM-01 | FAIL。沒有「取出」。 | PASS |
| TC-FE-TOWN-STORE-UX-01 | FAIL。點清單裡的探險公會之後是場景 3。 | PASS。點存倉列進入取出場景 2，提示是「請點選空地，放回「探險公會」。不扣除金幣和材料。」 |

整套 API（`pytest -m "not frontend"`）：main 17 failed、361 passed、103 deselected。`25b959a` 378 passed、103 deselected。多出來的 deselected 是本輪新增的 11 條介面案例。API 失敗名單與上一輪相同。整套介面（`pytest -m frontend`）：main 32 failed、71 passed、378 deselected。`25b959a` 14 failed、89 passed、378 deselected。上一輪對 `f785d04` 的測試是介面 92 passed、0 failed。本輪 14 條失敗就是上表裡 `25b959a` 的 FAIL：兩條返回地圖、兩條滿圖取出、新建造金色格、兩條放不下、書面語、兩條取消底色、底欄、地圖橫向、`UX-02` 的「已興建」、`NOREGRESS` 的三句新提示。其餘原本通過的行為案例仍然通過，包括 `STORE-UX-01`、`SCENE2-LEGAL`、`SCENE3-CANCEL`。
