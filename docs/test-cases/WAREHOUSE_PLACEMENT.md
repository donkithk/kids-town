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
介面：`tests/test_warehouse_e2e.py` 的 `TC-FE-WAREHOUSE-UNSTORE`、`TC-FE-WAREHOUSE-CARD`、`TC-FE-WAREHOUSE-CARD-BODY`、`TC-FE-WAREHOUSE-SCENE2-LEGAL`、`TC-FE-WAREHOUSE-SCENE3-CANCEL`、`TC-FE-BUILD-SCENE2-NOREGRESS`、`TC-FE-WAREHOUSE-COPY-FORMAL`、`TC-FE-WAREHOUSE-RETURN-MAP`、`TC-FE-WAREHOUSE-TAKEOUT-FULL`、`TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL`、`TC-FE-WAREHOUSE-OFFGRID-TOAST`、`TC-FE-WAREHOUSE-CANCEL-TOAST-INFO`、`TC-FE-WAREHOUSE-BAR-NOOVERFLOW`、`TC-FE-TOWN-MAP-FIT`、`TC-FE-BUILD-UNFIT-PRESELECT`、`TC-FE-BUILD-UNFIT-PRESELECT-MINFP`、`TC-FE-PAL-BTN-NOCLIP`、`TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP`、`TC-FE-CONFIRM-GENERIC-4XX`、`TC-FE-SW-AUTOREG`、`TC-FE-SW-PRECACHE`、`TC-FE-SW-UPGRADE-CLEANUP`、`TC-FE-PAL-ORDER`、`TC-FE-TAP-OFFCENTER`、`TC-FE-CELL-ARIA-MATCH`、`TC-FE-TAP-BAR-NOTHROUGH`，以及畫面那一半的 `TC-API-AUTOPLACE-FORMAL`。API 檔另有 `TC-API-AUTOPLACE-FORMAL`，還有只 GET 靜態檔的 `TC-FE-WAREHOUSE-GRID`。

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
| TC-FE-WAREHOUSE-BAR-NOOVERFLOW | 1280×720、1100×800、390×720：四個底欄按鈕的邊框盒高 46±1，底欄本身 64±1。1280 與 1100 另查 `nowrap`、左右 padding ≥13、寬度、提示一行。三個視窗都查文字不溢出。 | FAIL | 見下方。按鈕邊框盒是 44，底欄更高，不是 46 / 64。 |
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

點放不下的空格，`#toast.info` 的文字必須正好是「這個位置放不下這座建築物。」第 8 欄第 1 行（索引 7，足跡伸出地圖）是這種空格。`(1,0)` 落在健身室 `(0,0)` 的 2×2 裡面，是被蓋住的格，不是「空但會重疊」。它的提示必須正好是「這個位置已經有建築物。」原點 `(0,0)` 也是這句。空而會重疊的例子（健身室在 `(3,0)`、點 `(2,0)`）由 `TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP` 鎖。金幣、材料與行都不變。

8×8 的格子都可以點。若第 8 欄不存在，測試改點 `(1,0)`，並且不會只因為改點而失敗。這一輪兩端都有第 8 欄，沒有改點。

`25b959a` 的取出場景 2：只要 `footprintFree` 為假（索引 7 與足跡重疊都算），提示都是「這個位置已經有建築物。」所以放不下的兩格失敗，已佔用的 `(0,0)` 通過（文字、`info`、棕底都對）。新建造場景 2 點空格只是選中，沒有提示；點已佔用格打開升級面板，也沒有「這個位置已經有建築物。」`SCENE2-LEGAL` 仍要求已佔用格顯示後一句，那條在 `25b959a` 上通過。

## 取消提示的底色（TC-FE-WAREHOUSE-CANCEL-TOAST-INFO）

新建造與取出都進到場景 3，按「取消」。文字必須正好是「已取消，資源未扣除」。class 含 `info`、不含 `error`。底色 `rgb(107, 79, 42)`，字色 `rgb(255, 248, 231)`。不要預設綠底 `rgb(21, 128, 61)`。

`25b959a` 的 `cancelPreview` 呼叫 `showToast("已取消，資源未扣除")`，沒有傳 `info`。文字正確，class 是空的，底色是綠的。`showToast` 已經認得 `info`，`#toast.info` 也在。`main` 的 `showToast` 只分錯誤與空白 class，而且沒有 `#toast.info`。取出在 `main` 上進不去。

`UX-03` 仍只查取消文字含「已取消」「未扣除」，不鎖底色。

## 底欄不溢出（TC-FE-WAREHOUSE-BAR-NOOVERFLOW）

新建造場景 2 量 `#btnUxBack`、`#btnToScene3`、`#readyStatus`、`#readyBar`。進入場景 3 之後量 `#btnUxCancel`、`#btnUxConfirm`、`#placeStatus`、`#uxPlaceBar`。按 id 量，不按按鈕上的舊字。

三個視窗都量：1280×720、1100×800、390×720。

- 「返回地圖」「選擇位置」「確定放置」「取消」的邊框盒高是 46±1。
- `#readyBar` 與 `#uxPlaceBar` 的邊框盒高是 64±1。
- 高度用 `getBoundingClientRect().height`（含 border），不用 `getComputedStyle().height`。`content-box` 高 48 再加上下各 3px border 是 54，必須失敗。舞台 `.gsw` 有 `transform: scale(...)`。1280×720 的縮放是 1，矩形高度就是邊框盒。1100 與 390 先把矩形高度除以舞台縮放（`stage.getBoundingClientRect().width / stage.offsetWidth`），再跟 46 / 64 比。這樣 54px 的按鈕在 1100 上畫成約 46px 時仍然失敗。
- 三個視窗都查 `scrollWidth` 不大於 `clientWidth`。
- 1280×720 與 1100×800 另查：`white-space` 是 `nowrap`，左右 padding 至少 13px，四字按鈕寬至少 90px，「取消」至少 58px，中間提示 `Range.getClientRects()` 是一行。寬度仍用畫面上的矩形，不除縮放。390 不查寬、padding、`nowrap`、提示行數。

倉庫測試裡沒有別的案例用計算樣式去鎖這四個按鈕或底欄的高度。`tests/test_frontend.py` 的 `offsetHeight` 只量舞台，不量底欄。

`ba93ca9` 在 1280×720：四個按鈕 `getBoundingClientRect().height` 是 54，計算樣式 `height` 是 48（`box-sizing: content-box` 再加上下各 3px border）。`#readyBar` 與 `#uxPlaceBar` 都是 72。1100×800 的矩形高度是 46.4（按鈕）與 61.9（底欄），除以舞台縮放 0.859 之後仍是 54 與 72。390×720 的矩形是 16.5 與 21.9，除以 0.305 之後同樣是 54 與 72。`nowrap`、padding、寬度、不溢出、提示一行在 `ba93ca9` 通過。`main` 的按鈕邊框盒是 44（1100 的矩形約 37.8），底欄是 62，而且 `white-space` 是 `normal`、padding 是 0、寬度低於下限。390 沒有溢出。

## 未選建築時不能預選放不下的格（TC-FE-BUILD-UNFIT-PRESELECT）

新建造場景 2，商店已放在 `(0,0)`，還沒選建築物。

(a) 點空的、非金的 `(5,7)`：不得選中（沒有「已選此格」、沒有「此格」徽章）。`#toast.info` 正好是「這個位置放不下這座建築物。」然後選工坊，「選擇位置」不得把這個原點帶進場景 3，也不得出現紅色 `.error`「位置超出地圖範圍（0 至 7）」。

再重新進入場景 2，點已放置商店足跡裡的 `(1,0)`：同樣不得選中。`#toast.info` 正好是「這個位置已經有建築物。」然後選工坊並按「選擇位置」，不得進入以 `(1,0)` 為原點的場景 3，也不得出現紅色 `.error`「該位置已被建築物佔用」。

(b) `TC-FE-BUILD-UNFIT-PRESELECT-MINFP`：攔截 `GET /api/building-defs`，既有列加 `footprint: 2`，並加一座 `footprint: 1` 的郵箱。未選建築時 `(5,7)` 必須是金格而且可以選。再選 2×2 的工坊：清掉這格、`#toast.info`「這個位置放不下這座建築物。」、工坊仍選中、提示以「請點選金色空地」開頭（或含工坊與「金色空地」）、`#btnToScene3` 保持停用，直到再點一個 2×2 金格。選完工坊之後 `(5,7)` 不再是金。`ba93ca9` 的目錄物件沒有 `footprint` / `width` / `height`，`town-four-scene.js` 寫死 `FOOTPRINT = 2`。

(c) 新建造與取出都進到場景 3 的合法格，再用 `page.route` 把確定的 POST 回 400，正文 `{"error":"位置超出地圖範圍（0 至 7）"}`。畫面必須 `#toast.info`「這個位置放不下這座建築物。」回到場景 2，不出現紅色 `.error`，也不顯示伺服器原文或 `Request failed`。被拒的那一格要清掉（沒有「已選此格」、沒有「此格」徽章）。「選擇位置」停用。新建造的提示以「請點選金色空地」開頭，而且健身室仍選中。取出的提示回到「請點選空地，放回「圖書館」。不扣除金幣和材料。」金幣、材料與行不變。未知正文的 4xx 由 `TC-FE-CONFIRM-GENERIC-4XX` 鎖，規則相同。

## 建築清單按鈕不裁切（TC-FE-PAL-BTN-NOCLIP）

合成小朋友有已放置的商店、存倉的圖書館，以及目錄裡還沒蓋的建築（例如健身室）。新建造場景 2 打開 `#palette`。每一個 `.pal-btn`：

- `scrollHeight` 不得大於 `clientHeight`。
- 第二行（`.pal-cost`：存倉、已興建或已起、💰 價錢）的 `getBoundingClientRect().bottom` 必須比按鈕內底邊至少高 4px。內底邊是按鈕矩形的 `bottom` 減去 `border-bottom-width`。

1280×720。三種列都要出現，否則案例失敗。

## 空但重疊的格不能預選（TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP）

新建造場景 2，還沒選建築物。健身室放在 `(3,0)`（足跡蓋住 `(3,0)`、`(4,0)`、`(3,1)`、`(4,1)`），商店放在 `(0,6)`。`(2,0)` 本身是空的，但一座最小足跡從這裡放下會壓到健身室。它不是金格。點下去不得選中，`#toast.info` 正好是「這個位置放不下這座建築物。」提示維持點之前那句，不得變成「已選擇空地…」或「已揀空地…」。「選擇位置」停用。

然後重新進入場景 2，再掃全部 64 格。測試用當下的 `GET /api/building-defs` 算最小足跡（缺了或不是正整數就當 2），再跟已放置的足跡算：

- 金格：最小足跡放得下、在地圖內、不與已放置建築重疊。點下去必須選中，再點一次清掉。可選格的集合必須等於畫面上的金格，也等於算出來的金格。
- 空而非金：不得選中，`#toast.info`「這個位置放不下這座建築物。」
- 落在某座已放置足跡裡（含原點）：不得選中，`#toast.info`「這個位置已經有建築物。」

不查半張卡片露出，也不查底部漸層。

`TC-FE-WAREHOUSE-OFFGRID-TOAST` 的 `(1,0)` 是健身室 `(0,0)` 蓋住的格，提示是「這個位置已經有建築物。」那條是已經選了建築之後。這一條是還沒選建築。

## 確認時的未知 4xx（TC-FE-CONFIRM-GENERIC-4XX）

新建造與取出各進場景 3，在按下確定之前用 `page.route` 攔截那個 POST。四種正文都要測：

| 標籤 | 狀態 | 正文 |
|------|------|------|
| plain | 400 | `text/plain` 的 `Bad Request` |
| detail | 400 | `{"detail":"x"}` |
| occupied | 409 | `{"error":"該位置已被建築物佔用"}` |
| empty | 422 | 空正文 |

每一種都要：`#toast.info`「這個位置放不下這座建築物。」、沒有紅色 `.error`、畫面上不出現原始正文或 `Request failed`、回到場景 2、選格清掉、「選擇位置」停用。新建造的提示以「請點選金色空地」開頭且建築仍選中。取出的提示是「請點選空地，放回「圖書館」。不扣除金幣和材料。」金幣、材料與行不變。不在整頁裡搜尋單一個 `x`。

## 服務工作自行註冊（TC-FE-SW-AUTOREG）

新的瀏覽器上下文，測試不呼叫 `navigator.serviceWorker.register`。打開 `/kids/`，必要時登入，最多等 10 秒：`getRegistration()` 要有 active worker，`caches.keys()` 含 `service-worker.js` 裡的 `CACHE_NAME`（不寫死版號）。`pageerror` 不得含 `buildingImage`，而且整個流程都不得有任何 pageerror。流程再走場景 1、建築清單、任務板、儲蓄目標，以及一座名稱含「農」的已放置建築。`tests/test_skill_menu_e2e.py` 只記錄 pageerror，不把它當成允許，也不自己註冊 service worker。

## 預快取四場景檔（TC-FE-SW-PRECACHE）

`PRECACHE_URLS` 必須含 `town-four-scene.css` 與 `town-four-scene.js`（版號從 `service-worker.js` 讀）。新上下文裡 worker 變成 active 之後、進入城鎮之前，名為 `CACHE_NAME` 的 cache 要含這兩個檔和 `index.html`。名字不在 `caches.keys()` 裡時不得 `caches.open`。然後在線上登入，`context.setOffline(true)` 再重新載入：場景 1 用四場景版面，`#townMap .village.is-iso` 的 `--s` 是 0.85，`#townMap` 相對 `.mp` 左右留白相差不超過 1px，`#ktFooter .kt-footer-tab` 的 `white-space` 是 `nowrap`。

## 升級時清掉舊 cache（TC-FE-SW-UPGRADE-CLEANUP）

先用 `page.route` 把 `service-worker.js` 的 `CACHE_NAME` 與 `STATIC_CACHE` 改成原名加 `-test`，文件回應的 `<body` 加上 `data-sw-stale="1"`。等這個舊 worker 安裝並寫入那個 cache，再種一個 `other-app-cache`。然後拿掉 route，最多重新載入兩次。新的 worker 要變成 controller（`scriptURL` 含 `service-worker.js`、state 為 activated）。`caches.keys()` 裡符合 `kids-town-v` 前綴的只剩現在的 `CACHE_NAME`。`-test` 的 cache 要消失。`other-app-cache` 要留下。頁面不得再帶 `data-sw-stale`。`#townMap` 的 aria 是「場景 1 · 查看地圖」，`--s` 是 0.85。

## 建築清單分組順序（TC-FE-PAL-ORDER）

新建造場景 2 的 `#paletteGrid`。`.pal-btn` 的 DOM 順序，以及由上到下的視覺順序（`getBoundingClientRect().top`，同一高度再比 left），都必須是：存倉（第二行「存倉」）→ 未建（第二行有 💰）→ 已興建（「已興建」或仍寫「已起」）。每一組裡面保持 `GET /api/building-defs` 回傳的順序，不按價錢或名稱重排。空的組整組不出現：沒有標題、沒有佔位元素，`#paletteGrid` 的子節點全部是 `.pal-btn`。同一種建築若又放置又存倉，放置贏，算已興建。

三個合成小朋友，建築從目錄的位置挑，不斷言寫死名稱：

1. `mixed`：目錄第 2、5 項存倉，第 1、3 項已放置，其餘未建。三組都在。
2. `no-stored`：沒有存倉。清單從第一個未建開始，然後才是已興建。
3. `none-built`：沒有已放置。清單是存倉然後未建，沒有已興建那一組。

預期順序在測試裡用當下的目錄陣列和這個小朋友的行算出來。只鎖順序，不鎖半張卡片露出，也不鎖底部漸層。

## 偏離中心的點格（TC-FE-TAP-OFFCENTER）

視窗 1100×800 與 390×844。菱形來自畫面上的地磚（`#townMap .pad > .slab` 的外框）：四個頂點是四邊的中點。不是格子按鈕的外框。每一格點九下，都用 `page.mouse`：中心、朝四個頂點、朝四條邊的中點。後八點在中心到該目標的 35%，所以嚴格在菱形裡面。

點下去必須作用在含有這個點的那一格。三種狀態（還沒選建築、已選 2×2、取出）用同一條規則，跟 `TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP` 的掃格相同。預期只看含有這個點的那一格在畫面上的狀態，不寫死座標清單：

- 金色：畫面上 `.mark` 的金色 filter（與重疊掃格同一套）。選中這一格。取出時是場景 3 的預覽落在這一格。
- 被建築蓋住：畫面上有建築圖的原點，再用目錄足跡（沒有足跡欄時是 2）展開到足跡裡的每一格。不選格，提示「這個位置已經有建築物。」
- 空的但不是金（足跡會重疊，或伸出地圖）：不選格，提示「這個位置放不下這座建築物。」

還沒選建築時，空但重疊的格不是金，不得選中。選中隔壁格是打錯格。提示句子不對，或這格不該選卻被選中，是反應不符。

1. 新建造、還沒選建築。64×9 = 576 點都算。
2. 新建造、已選一座 2×2。打開的清單面板會蓋住左側一些格。一個點算在面板裡，只當 `elementFromPoint` 落在 `#palette`（圓角已經裁掉點擊）。只在外框矩形裡、視覺上在圓角外面的點仍是露出的菱形點，打中自己那一格不算穿透。面板上的點從分母拿掉，而且不得選中格子。
3. 取出、存倉裡有一座建築。同樣 576 點；若有面板或其他蓋住格子的層，用同一條排除規則。不得跳進場景 3 卻把預覽放在別的格子上。

分母規則：`elementFromPoint` 落在實心介面（動作列、清單、頂部 HUD、頁尾、工具列、打開的面板）才從分母移除。外框矩形的角落如果點不中那塊介面，不算被蓋住。提示和放置特效不是實心介面。場景 2 裡建築圖不是實心介面：菱形壓在前面建築圖下面時，仍必須作用在後面那一格，而不是前面建築的原點。

精靈：前面有一座高的建築圖、後面有一格沒有自己建築圖的格子時，菱形裡又疊在那張圖上的點必須作用在後面那一格，不是前面建築的原點。後面那一格若是金，就選中它；若是空而非金，提示「這個位置放不下這座建築物。」；若落在別座建築的足跡裡，提示「這個位置已經有建築物。」種子是商店 `(0,0)`、農場 `(4,3)`，至少要有一個這樣的點，而且單獨斷言。

打錯的訊息要寫出格子與點的名字。

既有測試若用 `locator.click()` 點格子按鈕，按鈕不再是指標命中目標之後會壞。格子的指標點改走 `tests/town_tap.py` 的 `tap_cell_centre`。中心若在視窗外面，先把那一格捲進畫面再量菱形；中心若被實心介面蓋住，改點同一菱形裡、產品命中測試仍算這一格、而且不是別的按鈕的點。鍵盤仍點那個按鈕。`TC-FE-WAREHOUSE-COPY-FORMAL` 仍鎖清單與地圖上的「商店，已興建」「空地，點選即可選擇」，那是文案鎖，不是這條的提示用字。`a871b1b` 上連菱形中心也會打到隔壁格，所以原本靠點格的介面測試在這個版本轉紅。`8940905` 上捲進畫面之後，`COPY-FORMAL`、`UNFIT-PRESELECT`、`MINFP` 恢復打中格子；仍紅的是產品行為：已選建築時被蓋住的非原點提示是「這個位置放不下這座建築物。」，以及空但重疊的格會被選中、沒有提示。

## 格子無障礙字與提示一致（TC-FE-CELL-ARIA-MATCH）

新建造（已選 2×2）與取出，每一格都查。無障礙字必須含有提示那一句，逐字相同。前面可以有座標，但那一句本身不能改。

分類跟偏離中心那條一樣，從畫面上的金標和建築圖得出，不用另一套足跡公式。

- 被建築蓋住，原點與非原點都是「這個位置已經有建築物。」。種子裡商店在 `(0,0)`，所以 `(0,0)` 是原點、`(1,0)` 是非原點。不得含「已興建」，也不得含「這個位置放不下這座建築物。」
- 空的，但不是金（足跡重疊或伸出地圖）→「這個位置放不下這座建築物。」。不得含「已興建」，也不得含「這個位置已經有建築物。」
- 金色可選 → 可選的字（「點選即可選擇」「已選此格」「可以放置」），而且不得用上面兩句拒絕句。

每一格仍有一顆可聚焦的按鈕，而且帶 aria-label。在那顆按鈕上按 Enter 和 Space，效果與點這一格相同（選中、提示，或預覽在這一格）。這條用鍵盤啟動，所以量的是這一格自己的按鈕，不是偏離中心的指標命中。

## 實心介面不穿透（TC-FE-TAP-BAR-NOTHROUGH）

實心介面要吃掉點擊，底下的格子選中數是 0，而且 `document.elementFromPoint` 落在那塊介面、不是地圖格子。背景格點（避開按鈕）蓋住：動作列 `#readyBar`、清單面板 `#palette`、頂部 HUD（`.gh`）、`#ktFooter`、以及打開的 `#actionSheet`。

動作列的每一顆按鈕，以及頁尾的每一個分頁，在中心和每條邊往內 8px 的位置，`elementFromPoint` 必須是那顆按鈕（或其子元素），不能是地圖格子。點頁尾的任務、遠征、城鎮分頁，仍要切到對應畫面。

相反，提示和放置特效不得吃點擊：`#toast`（info 與成功）和 `.fx-burst` 的 `pointer-events` 是 `none`。提示還顯示時，菱形中心落在提示矩形裡的金色格，用 `tap_cell_centre` 同一套中心點下去，必須選中那一格。測試會先挑一個提示真的壓到金色格中心的版面（1280×720），並斷言有這個重疊。那一格必須在當下畫出來的金色集合裡（這條用 `(4,5)`）；不是金的格不拿來當「壓住仍要選中」的目標。

## 連續提示重新計時（TC-FE-TOAST-TIMER-RESET）

新建造場景 2、還沒選建築。視窗 1100×800。商店在 `(0,0)`。兩下都是 `page.mouse` 的真實點擊，先把兩格捲進畫面並量好菱形點，再點，間隔大約 420ms（容許約 280–700ms）。量測在頁面時鐘上：`requestAnimationFrame` 抽 `#toast` 的 inline `display`、計算後的 opacity、文字、以及節點是不是同一個；`animationstart` 聽在 document 上，目標是 `#toast` 或其子節點。同一條裡「同一句」和「換句」各跑 3 次。

放不下的格優先用畫面上的非金空格 `(7,0)`、`(5,7)`、`(7,7)`。已經有建築物的格優先用被商店足跡蓋住、而且不是金的 `(0,0)` 或 `(1,0)`。

(a) 同一句：點同一個放不下的格兩次。提示一直顯示（`display` 為 `block`），直到第二下之後至少 1.9 秒仍在，大約 2.7 秒之後已經消失（2.8 秒前）。第二下不得重播進場動畫：第二下前後沒有新的 `animationstart`，而且第一下淡入到 opacity ≥ 0.9 之後、直到第二下，opacity 不得再低於 0.9；第二下之後的 350ms 也不得掉下去。`#toast` 節點不變。

(b) 換句：先點放不下的格，再點已經有建築物的格。文字要在第二下開始後約 150ms 內變成「這個位置已經有建築物。」（允許到 250ms）。顯示時間與 (a) 相同，從第二下算。換句可以重播動畫。

## 同一格狀態不得有兩套預期

偏離中心、無障礙字、實心介面的提示重疊、未選預選 (a)(b)(c)、重疊掃格、放不下提示、最小足跡、以及倉庫畫面案例，對過同一種格子狀態：

| 狀態 | 預期 | 對過的案例 |
|------|------|------------|
| 畫面上的金格 | 選中這一格 | 偏離中心三種狀態、無障礙字、實心介面壓住 `(4,5)` 的那一下（先確認它在金色集合裡）、場景 2 合法原點 |
| 建築足跡蓋住、而且不是金 | 不選，「這個位置已經有建築物。」 | 偏離中心、無障礙字（原點與非原點）、未選預選 (a) 的 `(1,0)`、重疊掃格、放不下提示的已佔用格 |
| 空的但不是金 | 不選，「這個位置放不下這座建築物。」 | 偏離中心（含還沒選建築時的重疊格）、無障礙字、未選預選 (a) 的 `(5,7)`、重疊掃格、放不下提示的 `(7,0)` |
| 最小足跡是 1 的目錄 | `(5,7)` 在未選建築時是金，選了 2×2 之後不再是金 | 最小足跡。目錄不同，不跟 2×2 的重疊格混為一談 |
| 場景 3 確定被伺服器拒絕 | 回到場景 2，提示放不下，清掉選格 | 未選預選 (c)、未知 4xx。這是確定之後，不是預選 |
| 場景 3 點已有商店 | 「這裏已有「商店」，不能放置。」 | 書面語。不是場景 2 的「這個位置已經有建築物。」 |

`TC-FE-TOWN-HIT-01` 要求被前面建築圖蓋住的背面格選中自己。那一格必須是金格才跟上面第一列相同；它鎖的是菱形贏過建築圖，不是空而非金的格可以選。

## 自動放置的書面語（TC-API-AUTOPLACE-FORMAL）

省略座標的 POST `/api/kids/<id>/buildings`（只帶 `def_id`），當這種建築已經放置，回 400，`error` 正好是「你已經興建了這種建築物。」。不得是「你已經興建咗呢種建築物」。已放置的那一行不變，不扣費。

畫面若顯示這句（`showBuildFailure` 把伺服器錯誤放進 `#toast`），提示裡也要有這一句書面語，不得出現口語那句。其他後端口語句子不在這條範圍。

## 這一輪在三個版本上的結果

分母會先拿掉頁尾、頂部 HUD、動作列、工具列蓋住的菱形點，所以露出的點比「348」少。打錯格只算選中或預覽到另一格。

`a871b1b`：

- `TC-FE-TAP-OFFCENTER` 紅。1100×800 已選 2×2：露出 193，打錯格 65，清單矩形裡 15 點有 4 下選中了格子。390×844 已選 2×2：打錯格 98。空地 `(3,2)` 疊在農場圖上的那一點沒有選中 `(3,2)`。
- `TC-FE-CELL-ARIA-MATCH` 紅。新建造與取出都是無障礙字 28 格不合（原點 2、非原點 6），鍵盤 0。原點寫「已興建」，非原點只寫「放不下」，都沒有提示那一整句。
- `TC-FE-TAP-BAR-NOTHROUGH` 紅。動作列背景 162 點有 71 下選中格子（`elementFromPoint` 仍在動作列）。清單背景 40 點有 6 下選中。頂部 HUD 272 點、頁尾 150 點、打開的面板 896 點都是 0。動作列按鈕 10 個探測點、頁尾分頁 25 個探測點都沒有被格子蓋住，三個分頁點下去仍會切畫面。提示 `pointer-events` 是 `auto`。1280×720 下金色格 `(4,5)` 的菱形中心落在提示裡，點下去沒有選中。`.fx-burst` 是 `none`。
- `TC-API-AUTOPLACE-FORMAL` 紅。省略座標回 400，`error` 是「你已經興建咗呢種建築物」。畫面提示是「❌ 你已經興建咗呢種建築物」。

`8940905`：沒選建築的 1100×800 與 390×844，打錯格 0、沒反應 0（266/266）。先前那 5 下打錯、12 下沒反應，重測之後不是菱形算錯。地磚外框的四個頂點就是菱形頂點（與 `getBoundingClientRect` 的四邊中點一致）。16 點不在實心介面下，也不在前面建築圖的不透明像素上，清掉選格之後都打中自己那一格。`(4,3)` 的 `vertex-top` 的 `elementFromPoint` 是 `#readyBar`，從分母剔除（實心介面）。已選 2×2 與取出的打錯格是 0。被蓋住的非原點仍提示「這個位置放不下這座建築物。」，所以有反應不符。清單上 `elementFromPoint` 落在面板的 15 點裡有 4 下選中格子，是穿透，不是圓角外面的點。動作列背景 162 點有 71 下選中格子。清單背景 84 點有 11 下選中（點真的在面板上）。頂部 HUD 與頁尾是 0。1280×720 的提示矩形蓋住金色格 `(4,5)` 的菱形中心，但提示 `pointer-events` 是 `auto`，點下去沒有選中。無障礙字同樣不合，Enter／Space 沒有點到該格。自動放置仍是口語那句。

`main` `5bfe76d`：取出進不去。新建造無障礙字 64 格都不含那兩句提示。動作列背景 170 點有 141 下選中格子，另有 24 下 `elementFromPoint` 落到地圖格子。省略座標回 `def_id, cell_x, cell_y required`，不是書面語那句。

這一輪整套（測試樹是這次的菱形與實心介面修正，產品樹分別是三個提交）：

| 產品 | API `pytest -m "not frontend"` | 介面 `pytest -m frontend` |
|------|--------------------------------|---------------------------|
| `8940905` | 1 failed、378 passed、128 deselected | 24 failed、104 passed、379 deselected |
| `a871b1b` | 1 failed、378 passed、128 deselected | 12 failed、116 passed、379 deselected |
| `main` `5bfe76d` | 18 failed、361 passed、128 deselected | 57 failed、71 passed、379 deselected |

API 在 `8940905` 與 `a871b1b` 只失敗 `test_autoplace_already_owned_uses_formal_copy`（口語那句）。`main` 的 18 條是原本的倉庫 API 17 條，加上同一條書面語。介面在 `8940905` 多出來的失敗是放不下／400／未知 4xx、重疊預選、三條 service worker、清單順序、偏離中心（反應不符與清單穿透）、無障礙字、實心介面、自動放置畫面。`COPY-FORMAL`、`UNFIT-PRESELECT`、`MINFP` 在 `8940905` 通過。

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

## 對照 `ba93ca9`（收緊的三條）

產品是 `ba93ca9fd9620a4c4bd6db7147a88379c8fd2934` 的暫用工作樹，測試是本紅測分支。沒有推上建造分支。目錄物件沒有 `footprint`、`width`、`height`；`town-four-scene.js` 的 `FOOTPRINT` 仍是常數 2。`occAt` 只比對原點，所以商店在 `(0,0)` 時 `(1,0)` 不算已佔用。

| ID | main `5bfe76d` | `ba93ca9` |
|----|----------------|-----------|
| TC-FE-BUILD-UNFIT-PRESELECT | FAIL。`(5,7)` 與 `(1,0)` 在未選建築時都是金格，點下去選中（aria「已揀呢格」、徽章「呢格」），沒有 info 提示。選建築後「去擺位置」進入場景 3。確定時的 `.error` 是英文 `Insufficient resources`，不是「該位置已被建築物佔用」。 | FAIL。`(5,7)` 與 `(1,0)` 都不是金格，但點下去仍選中（aria「已選此格」）。選工坊後提示是「已選擇「工坊」和這個位置。」，「選擇位置」進入場景 3。`(5,7)` 確定時紅色 `.error`「位置超出地圖範圍（0 至 7）」。`(1,0)` 確定時紅色 `.error`「該位置已被建築物佔用」。兩次點格都沒有 info 提示。 |
| TC-FE-WAREHOUSE-BAR-NOOVERFLOW | FAIL。按鈕邊框盒 44，底欄 62。另有 `nowrap`、padding、寬度。390 無溢出。 | FAIL。只剩高度：按鈕邊框盒 54（計算樣式 48），底欄 72。1100 的矩形是 46.4，除以縮放後仍是 54。`nowrap`、padding、寬度、不溢出、提示一行通過。 |
| TC-FE-PAL-BTN-NOCLIP | FAIL。三種列都有（存倉、已起、💰）。每個 `.pal-btn` 的 `scrollHeight` 41 大於 `clientHeight` 38。存倉與已起的第二行在內底邊之下 1px，價錢行只高出 0.5px。 | FAIL。同一組數字。已放置列的第二行是「已興建」。 |
| TC-FE-BUILD-UNFIT-PRESELECT-MINFP | FAIL。`(5,7)` 在未選建築時已是金格。選工坊後仍選中，提示是「已揀「工坊」同呢格空地。」，「去擺位置」可按，`(5,7)` 仍是金。沒有 info 提示。 | FAIL。目錄鍵是 `buff_type`、`buff_vals`、`cost_gold`、`effect`、`icon`、`id`、`materials`、`max_level`、`name`、`unlock_region`，沒有足跡欄。注入 `footprint: 1` 之後 `(5,7)` 仍不是金。選工坊後格子仍選中，提示是「已選擇「工坊」和這個位置。」，沒有 info 提示。 |
| TC-FE-BUILD-UNFIT-PRESELECT (c) | FAIL。新建造停在場景 3，紅色提示是伺服器原文「位置超出地圖範圍（0 至 7）」。取出沒有「取出」，進不了場景 3。 | FAIL。新建造與取出都停在場景 3，`#toast.error` 顯示伺服器原文「位置超出地圖範圍（0 至 7）」，底色 `rgb(239, 68, 68)`。 |
| TC-FE-WAREHOUSE-COPY-FORMAL | FAIL。畫面與原始碼仍是舊口語，含「睇地圖」「確定收起呢棟建築物」。 | FAIL。只剩這兩句：`#townMap` aria 是「場景 1」，不是「場景 1 · 查看地圖」。`index.html` 仍有「睇地圖」與「確定收起呢棟」。收起對話框是「📦 確定收起呢棟建築物？」。 |

整套：`pytest -m "not frontend"` main 17 failed、361 passed、108 deselected；`ba93ca9` 378 passed、108 deselected。`pytest -m frontend` main 37 failed、71 passed、378 deselected（比上一輪多 5 條失敗，就是未預選、400 回場景 2 的兩條、最小足跡、清單裁切；通過數仍是 71）。`ba93ca9` 7 failed、101 passed、378 deselected。這 7 條是：書面語剩下的「睇地圖／確定收起呢棟」、底欄高度、未預選、400 回場景 2 的兩條、最小足跡、清單裁切。上一輪在 `25b959a` 失敗的返回地圖、滿圖、金色格、放不下、取消底色、地圖橫向、`UX-02`、`NOREGRESS` 在 `ba93ca9` 通過。

## 對照 `8940905`

產品是 `89409051b1b85181fac5731f2cd4f8e964db9ba6` 的暫用工作樹 `/tmp/kt-green-8940905`，測試是本紅測分支。沒有提交、沒有推上建造分支。`renderPalette` 仍按 `defs()`（`/api/building-defs` 的陣列順序）逐個加 `.pal-btn`，沒有把存倉、未建、已興建分成三組。`showUnfit` 回到場景 2 並顯示放不下的 info 提示，但不清 `state.pad`。`onCell` 在還沒選建築時，被足跡蓋住的格與放不下最小足跡的格會擋下；空但與已放置建築重疊的原點仍會選中。`index.html` 裡 `window.buildingImage = buildingImage` 在 `buildingImage` 還沒宣告時就丟出 `ReferenceError`，同一個 script 後面的 `serviceWorker.register` 不會跑。`PRECACHE_URLS` 沒有 `town-four-scene.css` / `town-four-scene.js`。

`TC-FE-WAREHOUSE-OFFGRID-TOAST` 的 `(1,0)` 改為已選建築之後的「被蓋住」格，預期「這個位置已經有建築物。」`(c)` 加上清掉選格、「選擇位置」停用、提示回到該場景的原句。`tests/test_skill_menu_e2e.py` 不呼叫 `serviceWorker.register`，也不再把 `buildingImage is not defined` 當成允許的 pageerror。沒有別的測試把選格留在 4xx 之後、或把紅色原始錯誤當成成功。

| ID | main `5bfe76d` | `8940905` |
|----|----------------|-----------|
| TC-FE-WAREHOUSE-OFFGRID-TOAST | FAIL。取出沒有「取出」。新建造點 `(7,0)`、`(1,0)`、`(0,0)` 都沒有提示。 | FAIL。只剩 `(1,0)`：建築已選時，被蓋住的非原點提示是「這個位置放不下這座建築物。」，預期「這個位置已經有建築物。」`(7,0)` 與原點 `(0,0)` 通過。新建造與取出相同。 |
| TC-FE-BUILD-UNFIT-PRESELECT (c) | FAIL。新建造停在場景 3，紅色 `.error` 是「位置超出地圖範圍（0 至 7）」。取出沒有「取出」。 | FAIL。info 提示與回到場景 2 已通過。`(0,0)` 仍是「第 1 欄第 1 行，已選此格」，「選擇位置」仍可按。新建造提示停在「已選擇「健身室」和這個位置。」取出提示已是放回那句，失敗在選格與按鈕。 |
| TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP | FAIL。`(2,0)` 是金格，點下去選中（「已揀呢格」、徽章「呢格」），提示變成「已揀空地…」，沒有 info。掃格時被蓋住的格也沒有「這個位置已經有建築物。」 | FAIL。算出來的金格與畫面上的金格一致，被蓋住的格有「這個位置已經有建築物。」空但重疊的 `(2,0)`、`(2,1)`、`(0,5)`、`(1,5)` 被選中（aria「已選此格」），沒有提示，提示變成「已選擇空地。請打開清單，選擇要興建的建築物。」第一次點 `(2,0)` 時「選擇位置」仍是停用。 |
| TC-FE-CONFIRM-GENERIC-4XX | FAIL。取出沒有「取出」。新建造的 plain、detail、empty 都停在場景 3，紅色 `.error` 是 `Request failed`。occupied 的紅色 `.error` 是「該位置已被建築物佔用」。 | FAIL。plain、detail、empty：兩種場景都停在場景 3，紅色 `.error`「Request failed」。occupied：回到場景 2 且 info 提示通過，但格子仍選中、「選擇位置」仍可按；新建造提示仍是「已選擇「健身室」和這個位置。」 |
| TC-FE-SW-AUTOREG | FAIL。`getRegistration()` 沒有 registration。`caches.keys()` 是 `[]`，沒有 `kids-town-v18`。唯一的 pageerror 是 `buildingImage is not defined`。場景 1、清單、任務板、儲蓄、農場都走完，沒有第二種 pageerror。 | FAIL。同一件事，cache 名是 `kids-town-v27`。pageerror 同樣只有 `buildingImage is not defined`。 |
| TC-FE-SW-PRECACHE | FAIL。`PRECACHE_URLS` 沒有這兩個四場景檔。worker 沒有 active，cache 不存在。離線重新載入是 `net::ERR_INTERNET_DISCONNECTED`。 | FAIL。同一組：預快取清單沒有這兩個檔，worker 沒有 active，`caches.keys()` 是 `[]`，離線重新載入斷線。 |
| TC-FE-SW-UPGRADE-CLEANUP | FAIL。`kids-town-v18-test` 沒有安裝。重新載入後沒有 controller。`caches.keys()` 只有種下去的 `other-app-cache`。aria 是「場景 1」，`--s` 是 `1`。 | FAIL。`kids-town-v27-test` 沒有安裝，沒有 controller，keys 只有 `other-app-cache`。aria「場景 1 · 查看地圖」與 `--s` 0.85 在頁面自己的 script 跑起來之後已經對，這兩項沒有失敗。 |
| TC-FE-PAL-ORDER | FAIL。三種佈局的 DOM 與由上到下都是目錄順序：圖書館、探險公會、健身室、農場、工坊、醫院、商店、銀行、燈塔、競技場、天文台。`mixed` 預期探險公會、工坊在最前，圖書館與健身室在最後。`no-stored` 實際從已建的圖書館開始。`none-built` 的存倉列夾在未建列中間。沒有多出來的標題或佔位節點。 | FAIL。同一組順序。第二行的存倉／💰／已興建分得出來，但沒有依組排。 |

整套：`pytest -m "not frontend"` main 17 failed、361 passed、123 deselected；`8940905` 378 passed、123 deselected。`pytest -m frontend` main 52 failed、71 passed、378 deselected（比上一輪多 15 條，就是這輪新案例；通過數仍是 71，因為收緊的放不下與 400 在 main 本來就失敗）。`8940905` 19 failed、104 passed、378 deselected。這 19 條就是上表：收緊的放不下兩條、收緊的 400 兩條、未知 4xx 八條、重疊預選、三條 service worker、清單順序三條。上一輪在 `8940905` 通過的 108 條裡，除了這四條被收緊的，其餘仍然通過。
