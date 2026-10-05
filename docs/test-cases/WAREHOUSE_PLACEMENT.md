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
介面：`tests/test_warehouse_e2e.py` 的 `TC-FE-WAREHOUSE-UNSTORE`、`TC-FE-WAREHOUSE-CARD`、`TC-FE-WAREHOUSE-CARD-BODY`、`TC-FE-WAREHOUSE-SCENE2-LEGAL`、`TC-FE-WAREHOUSE-SCENE3-CANCEL`、`TC-FE-BUILD-SCENE2-NOREGRESS`、`TC-FE-WAREHOUSE-COPY-FORMAL`、`TC-FE-WAREHOUSE-RETURN-MAP`、`TC-FE-WAREHOUSE-TAKEOUT-FULL`、`TC-FE-BUILD-SCENE2-NEWBUILD-LEGAL`、`TC-FE-WAREHOUSE-OFFGRID-TOAST`、`TC-FE-WAREHOUSE-CANCEL-TOAST-INFO`、`TC-FE-WAREHOUSE-BAR-NOOVERFLOW`、`TC-FE-TOWN-MAP-FIT`、`TC-FE-BUILD-UNFIT-PRESELECT`、`TC-FE-BUILD-UNFIT-PRESELECT-MINFP`、`TC-FE-PAL-BTN-NOCLIP`、`TC-FE-BUILD-UNFIT-PRESELECT-OVERLAP`、`TC-FE-CONFIRM-GENERIC-4XX`、`TC-FE-SW-AUTOREG`、`TC-FE-SW-PRECACHE`、`TC-FE-SW-UPGRADE-CLEANUP`、`TC-FE-PAL-ORDER`、`TC-FE-TAP-OFFCENTER`、`TC-FE-CELL-ARIA-MATCH`、`TC-FE-TAP-BAR-NOTHROUGH`、`TC-FE-TAP-VISIBLE-ONLY`、`TC-FE-SELECTED-CONTRAST`、`TC-FE-FOCUS-RING-VISIBLE`、`TC-FE-HIDDEN-INERT`、`TC-FE-TAP-BAR-GAP-BAND`、`TC-FE-TAP-SCENE-GRASS-EDGE`、`TC-FE-SELECTED-OVER-GOLD`、`TC-FE-FOCUS-RING-ABOVE-SPRITE`、`TC-FE-PLACE-SERVER-MSG`、`TC-FE-SELECTED-NO-FILL`、`TC-FE-FOCUS-RING-NO-FILL`、`TC-FE-TAP-VILLAGE-HALFPX`、`TC-FE-MARK-CLEARED`、`TC-FE-MARK-KEPT-READYBAR`、`TC-FE-MARK-RESTORE-AFTER-SHEET`、`TC-FE-RING-CLEARED`、`TC-FE-MARK-FOLLOWS-SCROLL`、`TC-FE-PAINT-UNDER-UI`、`TC-FE-RING-SAMPLER`、`TC-FE-NATIVE-FOCUS`、`TC-FE-RING-EDGE`，以及畫面那一半的 `TC-API-AUTOPLACE-FORMAL` 和 `TC-API-PLACE-OWNED-FORMAL`。API 檔另有 `TC-API-AUTOPLACE-FORMAL`、`TC-API-PLACE-OWNED-FORMAL`、`TC-API-PLACE-DETAIL-FORMAL`，還有只 GET 靜態檔的 `TC-FE-WAREHOUSE-GRID`。


像素打磨不在這條分支。中心 ±1px（`TC-FE-FOCUS-RING-CENTRE`）、外形和 22/24 站（`TC-FE-FOCUS-RING-SHAPE`）、尖角弦（`TC-FE-RING-VERTEX-GAP`）、實線帶的內緣 2.0–4.0 與 1 個裝置像素的洞（`TC-FE-RING-BAND-WALK`），以及同一條案例的嚴格版 `TC-FE-PAINT-UNDER-UI-PX`、`TC-FE-FOCUS-RING-NO-FILL-PX`、`TC-FE-MARK-FOLLOWS-SCROLL-PX`，只寫在後續分支的 `docs/test-cases/RING_PIXEL_POLISH.md`。這條留下的是粗檢：裁切洞離畫出來的外緣約 6 CSS px 以內、露出來的邊看得到環、尖角開口可以空。下面的對照紀錄仍寫著舊的嚴格結果，不是這條現在的斷言。

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
2. 新建造、已選一座 2×2。打開的清單面板會蓋住左側一些格。一個點只要落在打開而且看得見的實心介面外框矩形裡（清單、動作列、頂部 HUD、頁尾、工具列、打開的面板、建築清單按鈕），就不是露出的菱形點，即使圓角讓 `elementFromPoint` 落到地圖上也一樣。這些點從分母拿掉，點下去不得選中格子、不得出提示、不得打開面板。
3. 取出、存倉裡有一座建築。同樣 576 點；若有面板或其他蓋住格子的層，用同一條排除規則。不得跳進場景 3 卻把預覽放在別的格子上。

露出的點還必須落在 `#village`（`.village.is-iso`，`overflow-y: auto`）的外框矩形裡。這一層才把格子裁掉，底緣在地圖下緣上面。外框外面的點，即使 `elementFromPoint` 仍是地圖（底欄和地圖下緣之間的窄條、場景 1 的草地），也不是露出的點：不得選格、不得出提示、不得打開面板。座標從當下的外框算出來，不寫死。

分母規則：打開而且看得見、並且跟 `#townMap` 相交的實心介面，其外框矩形裡的點從分母移除。圓角外面、`elementFromPoint` 落到地圖的角落也算在矩形裡，不得選格。`#village` 外框外面的點同樣從分母移除，而且點下去不得有反應。收起、`display:none`、`visibility:hidden`、opacity 0、inert、移出畫面、或沒有跟 `#townMap` 相交的元素不吃點擊。提示和放置特效不是實心介面。場景 2 裡建築圖不是實心介面：菱形壓在前面建築圖下面時，仍必須作用在後面那一格，而不是前面建築的原點。

精靈：前面有一座高的建築圖、後面有一格沒有自己建築圖的格子時，菱形裡又疊在那張圖上的點必須作用在後面那一格，不是前面建築的原點。後面那一格若是金，就選中它；若是空而非金，提示「這個位置放不下這座建築物。」；若落在別座建築的足跡裡，提示「這個位置已經有建築物。」種子是商店 `(0,0)`、農場 `(4,3)`，至少要有一個這樣的點，而且單獨斷言。

打錯的訊息要寫出格子與點的名字。

既有測試若用 `locator.click()` 點格子按鈕，按鈕不再是指標命中目標之後會壞。格子的指標點改走 `tests/town_tap.py` 的 `tap_cell_centre`。中心若在視窗外面，先把那一格捲進畫面再量菱形；中心若被實心介面蓋住，改點同一菱形裡、產品命中測試仍算這一格、而且不是別的按鈕的點。鍵盤仍點那個按鈕。`TC-FE-WAREHOUSE-COPY-FORMAL` 仍鎖清單與地圖上的「商店，已興建」「空地，點選即可選擇」，那是文案鎖，不是這條的提示用字。`a871b1b` 上連菱形中心也會打到隔壁格，所以原本靠點格的介面測試在這個版本轉紅。`8940905` 上捲進畫面之後，`COPY-FORMAL`、`UNFIT-PRESELECT`、`MINFP` 恢復打中格子；仍紅的是產品行為：已選建築時被蓋住的非原點提示是「這個位置放不下這座建築物。」，以及空但重疊的格會被選中、沒有提示。

## 格子無障礙字與提示一致（TC-FE-CELL-ARIA-MATCH）

新建造（已選 2×2）與取出，每一格都查。無障礙字必須含有提示那一句，逐字相同。前面可以有座標，但那一句本身不能改。

分類跟偏離中心那條一樣，從畫面上的金標和建築圖得出，不用另一套足跡公式。

- 被建築蓋住，原點與非原點都是「這個位置已經有建築物。」。種子裡商店在 `(0,0)`，所以 `(0,0)` 是原點、`(1,0)` 是非原點。不得含「已興建」，也不得含「這個位置放不下這座建築物。」
- 空的，但不是金（足跡重疊或伸出地圖）→「這個位置放不下這座建築物。」。不得含「已興建」，也不得含「這個位置已經有建築物。」
- 金色可選 → 可選的字（「點選即可選擇」「已選此格」「可以放置」），而且不得用上面兩句拒絕句。

每一格仍有一顆可聚焦的按鈕，而且帶 aria-label。Enter 和 Space 各自從清掉的選格開始，效果與第一次點這一格相同（選中、提示，或預覽在這一格）。已選的金格再啟動一次會取消選擇，這是重疊掃格鎖住的第二次點擊；所以兩個鍵不能連在同一格上按。清選格先用指標。指標碰不到被打開的清單蓋住的格時，再在那顆按鈕上按 Enter。若這次按鍵被產品吃掉、選格還在，就改點另一格指標碰得到的金格，把選擇移過去，再用指標清掉。清單蓋住按鈕不另算失敗；測試會印出這些仍能聚焦的格。這條用鍵盤啟動，所以量的是這一格自己的按鈕，不是偏離中心的指標命中。

## 實心介面不穿透（TC-FE-TAP-BAR-NOTHROUGH）

只有打開而且看得見的實心介面可以吃掉點擊。動作列 `#readyBar`、清單面板 `#palette`、頂部 HUD（`.gh`）、`#ktFooter`、打開的 `#actionSheet`，背景格點（避開按鈕）的 `elementFromPoint` 必須落在該介面、不是地圖格子，點下去不得選中格子。

動作列的每一顆按鈕，以及頁尾的每一個分頁，在中心和每條邊往內 8px 的位置，`elementFromPoint` 必須是那顆按鈕（或其子元素），不能是地圖格子。點頁尾的任務、遠征、城鎮分頁，仍要切到對應畫面。

圓角：清單面板、建築清單按鈕 `#listLauncher`、動作列、頂部 HUD、打開的面板，外框矩形的四個角都要測。角往內 3px、5px、7px（大約沿著對角線 4px、7px、10px）的點，包括圓角外面的透明區，都不得打中格子：選中數 0、提示 0，而且 `elementFromPoint` 不得是地圖格子或 `#townMap`。還沒選建築，以及已選 2×2 工坊，都要測。捲動是 `#village.scrollTop` 的 0、300、366 和最大值。視窗是 1280×720、1100×800、390×844。

邊線只量整數像素。瀏覽器把點擊落到整數像素，貼在邊上的 .5 點不再當樣本。一個整數像素只要在實心介面外框裡面，或正好在外框的邊那一列、那一行（含邊），就必須被擋住：不得選格、不得出提示、不得打開面板。離外框至少 1px 的整數像素必須打到地圖。底下有一格看得見的格子（點在 `#village` 外框裡，而且地圖的等距命中會算到那一格）就要作用在那一格：金格選中；放不下或已經有建築，就出那一格的提示。沒有看得見的格子就不得有反應。視窗是 1280×720、1100×800、1100×844，捲動 0、300、366。調色盤、工具列、底欄，以及場景 3 的放置列，每條邊的中點往外 1px 和 2px 都要量，用來擋住外框往外擴 1px。1280×720 捲動 366，工具列下緣是 153：(1135, 153) 必須被擋住，(1135, 154) 必須打中底下那一格。調色盤外面的 (254, 490) 和 (254, 505) 必須選中 (0,5)；捲動用那一格的菱形當場算出來。1280 底欄、調色盤、放置列的上緣整數列仍然逐像素量，那些點在邊框上，必須被擋住。點從畫面矩形算出來。

提示和放置特效不得吃點擊：`#toast`（info 與成功）和 `.fx-burst` 的 `pointer-events` 是 `none`。若有金色格的可見菱形真的落在提示底下，點那一塊要選中那一格。若沒有，點提示範圍（含 1280×720 提示下方、壓在頁尾上的那 8px）不得選格，也不得把狀態改成已選擇空地。不得為了通過而要求選中一格看不見的格子。提示蓋住頁尾時打中藏起來的格子，由 `TC-FE-TAP-VISIBLE-ONLY` 鎖。

Guard（預期在目前產品上通過，不是新的紅測）：收起清單之後（返回地圖再按我要起屋；清單沒有就地關閉的按鈕），點原先清單矩形裡一格看得見的金格，必須選中它。收起的抽屜、關掉或沒打開的面板，以及 inert、`visibility:hidden`、opacity 0、`display:none`、移出畫面、沒跟 `#townMap` 相交的元素，都不得吃掉看得見的金格。提示和特效也不得吃掉看得見的金格。

## 連續提示重新計時（TC-FE-TOAST-TIMER-RESET）

新建造場景 2、還沒選建築。視窗 1100×800。商店在 `(0,0)`。兩下都是 `page.mouse` 的真實點擊，先把兩格捲進畫面並量好菱形點，再點。量測在頁面時鐘上：`requestAnimationFrame` 大約每 16ms 抽 `#toast` 的 inline `display`、計算後的 opacity、文字、以及節點是不是同一個；`animationstart` 聽在 document 上，目標是 `#toast` 或其子節點。同一條裡各跑 3 次。

放不下的格優先用畫面上的非金空格 `(7,0)`、`(5,7)`、`(7,7)`。已經有建築物的格優先用被商店足跡蓋住、而且不是金的 `(0,0)` 或 `(1,0)`。

(a) 同一句，兩段分開測：第二下在第一下之後 1.0 秒，以及 1.6 秒。opacity 第一次升到至少 0.99 之後，必須一直維持到隱藏開始，中間不得掉到 0 再跳回 1。第二下之後至少 1.9 秒仍然是滿透明度。最後一次淡出不超過約 0.35 秒，然後隱藏。第二下不得重播 `animationstart`。`#toast` 節點不變。`display` 為 `block` 直到第二下之後至少 1.9 秒，大約 2.7 秒之後已經消失。

(b) 換句：間隔大約 420ms（容許約 140–700ms）。先點放不下的格，再點已經有建築物的格。文字要在第二下開始後約 150ms 內變成「這個位置已經有建築物。」（允許到 250ms）。顯示時間從第二下算。換句可以重播動畫。

## 只吃看得見的地圖（TC-FE-TAP-VISIBLE-ONLY）

視窗 1100×800、390×844、1280×720。狀態是還沒選建築、已選 2×2 工坊、取出。一個點要算點中格子，必須同時滿足：它在 `#townMap` 的可見矩形裡（視窗、地圖的 overflow、村子捲動區的四邊，再被動作列和 `#ktFooter` 裁掉），而且它落在某一格菱形看得見的那一段。否則不得選格，不得把 `#readyStatus` 改成已選擇空地，也不得新出提示。

掃這些區域裡的可見矩形外面：動作列上緣的窄條、捲到頂之後的上緣、下緣、頁尾後面、左右緣，以及提示還顯示時壓在 `#ktFooter` 上的那一帶。每一段都要有候選點，空掃不算通過。

1280×720 與 1100×800、捲動 0、還沒選建築以及已選 2×2 工坊，先 `showToast` 把提示顯示出來，再用 `page.mouse` 點真實視窗座標。座標來自 `regress-61-003b81f.md`：1280×720 是 (640, 618.4)、(640, 630.2)、(640, 642.1)、(640, 640)；1100×800 是 (550, 697.3)、(550, 709.1)、(550, 721)。另外點這些座標四周 8px、提示和頁尾重疊的 8px，以及地圖可見下緣之下、仍在頁尾裡的點。這些點在地圖外面，不得選中 `(5,5)`、`(6,6)` 或其他格子，也不得把狀態改成已選擇空地，不得把提示改成別的句子。

## 選中格的對比（TC-FE-SELECTED-CONTRAST）

1280×720。選中格的實線是 `#7c2d12`、3px。線的顏色和寬度從選中標記的 SVG 讀。另外從畫面像素量對比：線旁邊實際出現的填色都要至少 3:1，包括地圖外緣的草地 `#7eae52`、空地填色 `#d5e6b4`、金色填色 `#f2df97`，以及出現了的深金 `#ead381`。深金沒有挨到線就不要求。要測一格邊緣格（線挨到外圍草地）和一格內部格（線挨到格子填色）。這條實線的顏色不得等於金色格虛線 `#d4a017`。沒選中的金色格虛線維持 `#d4a017`。

## 隱藏時不可聚焦（TC-FE-HIDDEN-INERT）

收起的抽屜 `#dr`（class `dr`，沒有 `o`）有 13 顆按鈕（✕、小鎮地圖，一直到登出）。1280×720 時它在畫面外（`right:-280px`，左緣大約 1310）。收起時它們不在 Tab 順序裡。用選單按鈕打開之後，這 13 顆都回到 Tab 順序。Tab 順序指沒有被 `display:none`、`visibility:hidden` 或 inert 祖先拿掉的可聚焦控件。移出畫面或 `pointer-events:none` 不算隱藏。

Guard（預期通過，不是新的紅測）：`#ktRotate`（請轉橫向）在橫向 1280×720 和直向 390×844 都量。只有它真的隱藏（`display:none` 或 `visibility:hidden`）時，才要求它不在 Tab 順序裡。桌面橫向本來就是隱藏而且不在 Tab 順序，這不是失敗。直向若把 overlay 顯示出來，隱藏檢查跳過，不算紅。不要用腳本把 `display` 改成 `block` 再要求它可聚焦。兩個視窗都已經符合時，記成通過的 guard。

## 指定格子的書面語（TC-API-PLACE-OWNED-FORMAL）

POST `/api/kids/<id>/buildings` 帶 `def_id`、`cell_x`、`cell_y`，這種建築已經放置時，回 400，`error` 正好是「你已經興建了這種建築物。」。不得是「你已經興建咗呢種建築物」。已放置的那一行不變，不扣費。省略座標的自動放置仍由 `TC-API-AUTOPLACE-FORMAL` 鎖，那條在已經改成書面語的版本上通過。

畫面若把這句放進 `#toast`（`showBuildFailure`），提示裡也要有書面語，不得出現口語那句。

## 底欄和地圖之間的窄條（TC-FE-TAP-BAR-GAP-BAND）

底欄下緣到 `#townMap` 下緣的窄條（1280×720 大約 8px，1100×800 大約 6.9px）不得打中藏起來的格。窄條的 y 用畫面矩形量，不寫死。一個點只有落在那一格看得見的部分（可見像素大於 0）才可以選格。視窗 1280×720 和 1100×800，還沒選建築以及已選工坊，捲動 0，窄條上橫向抽 11 點。1280 捲動 0 另外點 (640, 609)、(930.5, 609)、(404.4, 609)。不得選格，不得出提示，不得打開面板。

## 場景 1 村子下面的草地（TC-FE-TAP-SCENE-GRASS-EDGE）

場景 1、1280×720、捲動 0。真正把格子裁掉的捲動區下緣，到地圖（或頁尾，取較高的那一邊）之間的草地，不得選格、出提示或開面板。不寫死是哪一個元素在裁。草地裡大約 30 個點；落在按鈕上的點跳過，但字面座標仍要點：(349.5, 577)、(155.8, 544)、(219, 544)。少建築（商店、農場、存倉圖書館）和滿鎮（含銀行）各跑一次。種子沒有銀行時，測試在臨時庫補上定義，不改 `kids_town.db`。

## 選中實線蓋過金色虛線（TC-FE-SELECTED-OVER-GOLD）

1280×720，空鎮，選中 `(0,0)` 和 `(3,3)`。四條邊各在中段抽 9 點（避開角），線兩旁 ±1px。那些像素要是選中實線 `#7c2d12`，不能是金色虛線 `#d4a017`。

## 焦點環在建築圖上面（TC-FE-FOCUS-RING-ABOVE-SPRITE）

有建築的格子（商店在 `(0,0)`），焦點環要畫在建築圖上面，跟選中實線一樣在最上層。沿四條邊、和建築圖重疊的位置抽樣，那些像素要是 `#fff8e7` 或 `#6b4f2a`，不能是建築圖的像素。選中線同一格，每條邊中段 5 點至少 3 點是 `#7c2d12`。1280×720。

## 伺服器的放置句子（TC-FE-PLACE-SERVER-MSG）

場景 3 已經為一種建築（工坊）打開確定，另一個請求先把這種建築建好。確定之後，提示必須正好是伺服器那句「你已經興建了這種建築物。」，不得改成「這個位置放不下這座建築物。」。

只有伺服器回來的、給使用者看的中文字串 `detail` 才照字顯示。下面三條是 guard（預期顯示通用句，不是新的紅測），用 `page.route` 換成通用回應：

- 422，`detail` 是陣列（FastAPI：`[{loc, msg:'field required', type:'value_error.missing'}]`）
- 4xx，沒有 `detail`
- 4xx，`detail` 是英文字串

提示要含「這個位置放不下這座建築物。」，而且不得含 `field required`、`[`、`{`、`detail`，也不得是純 ASCII 的句子。

## 選中格不填色（TC-FE-SELECTED-NO-FILL）

選中標記是貼着格子頂面的實線，不是填滿的菱形。線是 `#7c2d12`，約 3px。中線內縮用外緣判斷：外緣在格子外 0–1.5 螢幕 px，線寬 2–4px。外緣是沿邊的法線走出格子、最後仍落在 `#7c2d12` 像素裡的那一點（0.02 螢幕 px 一步），不是整數偏移，也不是只取像素中心。1100×800、`deviceScaleFactor` 1 的 `(0,0)` 也要量；那一格東南外緣超過 1.5px（先前量到約 1.62px）時，這條要紅。格子中心，以及每條邊向內至少 8px 的點，要和同一捲動、同一視窗、提示收起時的未選中未聚焦截圖一致（只容抗鋸齒）；選中時「此格」徽章蓋住的區域除外，徽章本身要有看得見的像素。中心不得是 `#7c2d12`。東南、西南兩條邊，若外側鄰格是金格，邊帶上的像素要是 `#7c2d12`，不能是金色虛線 `#d4a017`。像素從截圖讀，不讀標記自己的 SVG。拍底圖之前，全畫面 `#7c2d12` 必須是 0，焦點環層也必須是 0 像素，避免上一格沒清掉的線污染底圖。視窗 1280×720、1100×800、390×844，各量內部金格和邊緣金格。

## 焦點環不填色（TC-FE-FOCUS-RING-NO-FILL）

焦點環只畫虛線，不填滿格子。未選中、只聚焦時，空地、金格、以及邊緣有建築圖的格子（圖書館），中心和每條邊向內至少 8px 的每一點（不排除徽章位置）都要和未選中未聚焦的底圖一致。選中又聚焦時才排除「此格」徽章區域；其餘內部仍要和底圖一致，中心不得是 `#7c2d12`。每條邊要看得到環色。內緣 2–4px、褐線外緣 0–1px、線寬 2–4px 是像素打磨，不在這條。像素從截圖差讀。拍底圖之前，全畫面 `#7c2d12` 必須是 0，焦點環層也必須是 0 像素。

## 村子下緣半像素（TC-FE-TAP-VILLAGE-HALFPX）

場景 1、捲動 0。`#village` 外框 `bottom + 0.5` 那一列（1280 約 y=541.5，390 約 y=477.6，座標隨畫面矩形）不得選格、出提示或開面板。同一條案例的對照：外框 `bottom - 1.5`、落在一格看得見的金格上的點，仍要選中那一格。實心介面上的點跳過。視窗 1280×720 和 390×844。

## 選中線要清掉（TC-FE-MARK-CLEARED）

取消選擇、回到地圖、以及切到任務板之後，全畫面 `#7c2d12` 像素是 0。畫這條線的元素（`#chosenMarkPaint`，或當時實際在畫的那個）計算樣式必須是 `display: none`，或者沒有盒子。只設 `hidden` 屬性、畫面還看得到，不算清掉。

## 確認欄還在時選中線要留著（TC-FE-MARK-KEPT-READYBAR）

場景 3 先選一格進入，再改選另一格。等確認的底欄要出現（場景 3 是 `#uxPlaceBar`；`#readyBar` 只在場景 2）。新格周圍的 `#7c2d12` 要多於 0 像素。

## 關上面板之後選中線要回來（TC-FE-MARK-RESTORE-AFTER-SHEET）

已經選中一格時打開建築面板，再關上。選中線要回到同一格：每條邊的外緣在該格活矩形外面 0–1.5px。

## 焦點環要清掉（TC-FE-RING-CLEARED）

失焦、換場景、切到別的分頁之後，焦點環那一層在畫面上是 0 像素（相對乾淨底圖沒有差、計算樣式 `display: none`，或 canvas 是空的）。

## 選中線和焦點環跟著捲動（TC-FE-MARK-FOLLOWS-SCROLL）

1280×720，選中 `(3,3)`。捲動 0 和捲動 366 各量一次。選中線的外緣要在該格當時的活矩形外面 0–1.5px，四邊都是。這條看的是露出來的褐線，不因為確認欄把南尖裁掉就放寬。焦點環的 24 站、內緣 2.0–4.0 是像素打磨，不在這條。

## 選中線和焦點環要在介面下面（TC-FE-PAINT-UNDER-UI）

清單、確認欄、抽屜、銀行面板、場景 1 的 `.cta`，向內縮 2px 的內部不得有嚴格環色。嚴格指平方距離 ≤25 的 `#fff8e7`、同樣距離的代替色 `#fffec5`，或選中線 `#7c2d12`。不要求整塊像素差是 0。圓角抗鋸齒（每通道 ≤2）不在這條。近欄兩張的句子仍要相同。

裁切洞離畫出來的外緣不得超過約 6 CSS px。外緣是 border box，加上當時 `::before` 伸出 border box 的距離；沒有生成或沒有伸出就是 0。向外超過 6 是死區：調色盤 border box 外 48 CSS px 的洞要紅。向內超過 6 也紅。環的盒子壓在外緣上、卻沒有對上的洞，算沒裁。大約 4 CSS px 的外擴過得了。

挨著調色盤或確認欄的格子，沒被蓋住的每條邊要看得到環（奶油或環褐）。尖角開口可以空：每邊兩端略過至少 8px 或邊長的 12%。離畫出來的外緣 6 CSS px 以內的站略過，那段不算洞。不量 22/24 站，不量內緣 2.0–4.0，也不量沿邊 1 個裝置像素的缺口。視窗 1280×720、1100×800、390×844。

確認欄、調色盤、`.cta`、動作面板，以及環和選中線那幾層，不得用補色層、`text-shadow`、`filter`，或 `translateZ`／3D transform 把漆蓋掉。查的是這些元素自己的計算樣式，不是面板標題上的裝飾陰影，也不是格子陰影的 blur。欄上句子（`#readyStatus`、`#placeStatus`）的 `text-shadow` 仍必須是 `none`。環和標記在共同堆疊上下文裡的有效 z 必須嚴格低於每一個看得見的欄、調色盤和 `.cta`。`.place-bar`、確認欄、調色盤、`.cta`、動作面板的子樹裡不得掛著環或標記的繪製元素。

## 焦點環在三個視窗都看得到（TC-FE-FOCUS-RING-VISIBLE）

1280×720、1100×800、390×844。點選 `(3,3)` 不得出現 `:focus-visible`，焦點環層是 0 像素。Tab 到同一格必須有 `:focus-visible`，四條邊露出來的部分都要看得到環。尖角開口可以空。不量中心 ±1px，也不量內緣 2–4。

## 產品不得抄測試的取樣幾何（TC-FE-RING-SAMPLER）

`town-four-scene.js` 的 `placeFocusRing` 不得照著測試的取樣走。不得用 `samples = 24` 建 `blocked` 站圖，不得用 `(s + 0.5) / samples` 對上站心，也不得 `hold` 住那些像素不畫。那是 `ring_device_gaps`／`ring_inner_gaps` 的幾何。沒有既有案例把環的內縮鎖成字面 `0.45`，這條不檢查那個數字。

## 不要改掉原生 focus（TC-FE-NATIVE-FOCUS）

`HTMLElement.prototype.focus.toString()` 和 `blur` 的字串都要含 `[native code]`。產品的 `town-four-scene.js`、`audio.js`、`service-worker.js`、`check_js.js` 不得指派 `HTMLElement.prototype.focus`。

## 角落的焦點環不要被村子裁進地圖裡（TC-FE-RING-EDGE）

聚焦四個角。格子是 8×8 時就是 `(0,0)`、`(7,0)`、`(0,7)`、`(7,7)`；若尺寸不同，用真正的角並寫明。環在看得見的地圖裡的那一段不得被村子裁掉。看得見的地圖是 `#village` 外框和視窗的交集，實心介面蓋住的點不算。裁掉的部分必須整段落在這塊外面。樣本在實線奶油帶上，離尖角至少 3px。

## 實心介面的邊用畫面矩形（TC-FE-TAP-BAR-NOTHROUGH）

工具列、調色盤、底欄、放置列的邊都用 `getBoundingClientRect`。含邊的整數像素必須擋住。必須打到地圖的點是離外框至少 1px 的整數：`floor(top) - 1`、`ceil(bottom) + 1`、`floor(left) - 1`、`ceil(right) + 1`（再向外 1px 也測）。外框外 0–1px 的點不判斷：瀏覽器仍會點中控制項（1100×800 底欄 top 555.55 時 y=555 擋住、y=554 才到地圖；工具列 left 1134.55 時 `(1134,148)` 擋住）。那裡有看得見的格就要選中或走到該格；沒有格就不得有反應。不寫死 153、154 或 156。1280 捲動 366 的工具列若 bottom 是 155，`(1135,155)` 擋住，`(1135,156)` 要選到看得見的格。`(254,490)` 和 `(254,505)` 只在離調色盤至少 1px、而且該點下面真的看得見 `(0,5)` 時才要求選中 `(0,5)`；若這兩點落在 0–1px 帶，改用 `ceil(right) + 1` 的同一 y。捲動 366 沒有格，就不得有反應。點落在調色盤裡面則跳過。這條寬限只用於實心控制項外面的「必須打到地圖」，不放寬 `#village` 外面的半像素列。

## 放置接口的書面語（TC-API-PLACE-DETAIL-FORMAL）

只打 `POST /api/kids/<id>/buildings`。每一條 4xx 的字串 `detail`，以及產品而家放句子的字串 `error`，都不得含「咩、呢、唔、嘅、㗎」。英文代號（`region_locked`、`Insufficient resources`）不是中文句子。移動、收倉、取出不在範圍。已知定義、小朋友還沒有，是成功放置，不是 4xx。存倉列放回是 200（`backend_v2.py:3506-3513`），也不是 4xx。

路徑（`3625974` 的 `backend_v2.py`）：

| 路徑 | 位置 | 句子 |
|------|------|------|
| 缺 `def_id` | 3460 | `def_id, cell_x, cell_y required` |
| 省略座標、區域內容鎖定 | 3465 → 1730–1742 | `region_locked` |
| 省略座標、區域未探索 | 3465 → 1744 | `unlock_region` |
| 省略座標、已經放置 | 3473（句在 1770） | 「你已經興建了這種建築物。」 |
| 省略座標、沒有空位 | 3480（句在 1768） | 「城鎮沒有空位，請先收起或移動其他建築。」 |
| 只帶一個座標 | 3483 | 同一句 required |
| 座標是布林、小數或文字 | 3486 → 1684–1696 | 「座標不正確」 |
| 足跡伸出、格外、負數 | 3491 | 「位置超出地圖範圍（0 至 7）」 |
| 格外、但是鎖區建築 | 3488 → 1730 | `region_locked` 或 `unlock_region`，先於上一句 |
| 指定格子、已經放置 | 3499 | 「你已經興建了這種建築物。」 |
| 足跡和建築重疊 | 3505 → 1826 | 「該位置已被建築物佔用」 |
| 裝飾佔用 | 3505 → 1834 | 「該位置已被裝飾佔用」 |
| 沒有這種定義 | 3517 | `Building definition not found` |
| 合法格、區域內容鎖定 | 3521 | `region_locked` |
| 合法格、區域未探索 | 3523 | `unlock_region` |
| 小朋友列已不在 | 3527 | `Kid not found`（閘門只對 session id） |
| 金幣不夠 | 3530 | `Insufficient resources` |
| 材料不夠 | 3541 | `Insufficient resources` |

## 同一格狀態不得有兩套預期

偏離中心、無障礙字、實心介面的提示重疊、未選預選 (a)(b)(c)、重疊掃格、放不下提示、最小足跡、以及倉庫畫面案例，對過同一種格子狀態：

| 狀態 | 預期 | 對過的案例 |
|------|------|------------|
| 畫面上的金格 | 選中這一格，但只有菱形看得見的那一段 | 偏離中心三種狀態、無障礙字、實心介面（提示底下若有可見金格才點它）、只吃看得見的地圖、場景 2 合法原點 |
| 建築足跡蓋住、而且不是金 | 不選，「這個位置已經有建築物。」 | 偏離中心、無障礙字（原點與非原點）、未選預選 (a) 的 `(1,0)`、重疊掃格、放不下提示的已佔用格 |
| 空的但不是金 | 不選，「這個位置放不下這座建築物。」 | 偏離中心（含還沒選建築時的重疊格）、無障礙字、未選預選 (a) 的 `(5,7)`、重疊掃格、放不下提示的 `(7,0)` |
| 最小足跡是 1 的目錄 | `(5,7)` 在未選建築時是金，選了 2×2 之後不再是金 | 最小足跡。目錄不同，不跟 2×2 的重疊格混為一談 |
| 場景 3 確定被伺服器拒絕 | 回到場景 2，提示放不下，清掉選格 | 未選預選 (c)、未知 4xx。這是確定之後，不是預選 |
| 場景 3 點已有商店 | 「這裏已有「商店」，不能放置。」 | 書面語。不是場景 2 的「這個位置已經有建築物。」 |

`TC-FE-TOWN-HIT-01` 用畫出來的地磚菱形（與偏離中心同一套外框）和前面建築圖的外框相交，每一格取幾個點，不是格子按鈕的矩形。只留只落在背面那一格菱形裡的點；同時落在前面那格菱形裡的點不屬於背面格。點下去的反應跟偏離中心相同：菱形贏過建築圖，背面那一格按自己的金／蓋住／空而非金反應。種子是商店 `(0,2)`、圖書館 `(2,1)`、農場 `(4,0)`。一個視窗若完全沒有相交點，這條失敗，不能當成通過。`.cell-btn` 只留給鍵盤，不再用它的外框找重疊。

## 這一輪對過的版本

測試尖端對上建造分支 `cursor/green-warehouse-placement-8555` 的 `cb6fb3d`（`bareOverlapSelectable()` 已刪，`town-four-scene.js` 只少了那段）。沒有在本地把函式改成 `return false`。對照是未改的 `52775b7`（函式還在）。`a871b1b` 與 `8940905` 只跑偏離中心和連續提示。

`cb6fb3d`：API 379 passed、129 deselected。介面 1 failed、128 passed、379 deselected。唯一失敗是 `TC-FE-TOAST-TIMER-RESET` 的同一句：三趟都在第二下重播 `fadeInOut`（opacity 掉到 0）。計時有清掉，所以 1.9 秒仍在、約 2.8 秒前消失，換句三趟都過。偏離中心全過：沒選建築 266/266（兩個視窗），精靈點在非金的 `(3,2)` 上提示放不下；已選 251/251；取出 266/266。重疊掃格在這個種子上不受那段特例影響，這次是過的。

`52775b7` 未改：API 同樣 379 passed、129 deselected。介面 2 failed、127 passed、379 deselected。失敗是偏離中心和同一句的動畫重播。重疊掃格仍過：特例只認商店 `(0,0)` 加農場 `(4,3)` 再加那兩個視窗，掃格的種子是健身室 `(3,0)` 加商店 `(0,6)`，所以碰不到。偏離中心的沒選建築被特例選中空而非金的格：兩個視窗都是 239/266，反應不符 27（`(3,2)` 整格九點，接著 `(4,2)`），精靈點也選中了 `(3,2)`。已選與取出是 0。

`8940905` 偏離中心：沒選建築 239/266，反應不符 27，跟重疊掃格仍會選中空而非金的格同一件事。已選 1100×800 是 220/251、反應不符 31、面板選中 4；390×844 同樣 220/251、反應不符 31、面板選中 4。取出 1100×800 是 235/266、反應不符 31；390×844 是 181/203、反應不符 22。連續提示三趟都在第二下之後約 1.58 秒被第一個計時器關掉，同一句也重播動畫。

`a871b1b` 偏離中心：沒選建築 1100×800 是 198/266、打錯格 68；390×844 是 164/266、打錯格 102。已選 1100×800 是 186/251、打錯格 65、面板選中 4；390×844 是 153/251、打錯格 98、面板選中 4。取出 1100×800 是 197/266、打錯格 68、反應不符 1；390×844 是 131/203、打錯格 72。連續提示同樣約 1.58 秒被舊計時器關掉，三趟都這樣。

## 去掉 196px 按鈕之後（`4d66a57`）

`.cell-btn` 在 `b6dc646` 已改回普通大小，只給鍵盤和螢幕閱讀器。`TC-FE-TOWN-HIT-01` 改量地磚菱形和前面建築圖的相交，並且丟掉同時落在前面那格菱形裡的點。Enter 與 Space 各自從清掉的選格開始。已選金格再啟動一次會取消，這是重疊掃格的第二次點擊；沒有別的案例要求第二次還保持選中。清單蓋住的按鈕仍會聚焦，不因此失敗。新建造時這份清單是 `(0,5)`、`(0,6)`、`(1,6)`、`(0,7)`、`(1,7)`、`(2,7)`。取出沒有。

整套 API 然後整套介面，測試樹是 `4d66a57`，產品樹沒有改：

| 產品 | API | 介面 |
|------|-----|------|
| `b6dc646` | 379 passed、129 deselected | 129 passed、379 deselected |
| `cb6fb3d` | 379 passed、129 deselected | 1 failed、128 passed、379 deselected |
| `52775b7` 未改 | 379 passed、129 deselected | 2 failed、127 passed、379 deselected |
| `8940905` | 1 failed、378 passed、129 deselected | 26 failed、103 passed、379 deselected |
| `a871b1b` | 1 failed、378 passed、129 deselected | 13 failed、116 passed、379 deselected |

`b6dc646` 的遮擋點兩個視窗都是 15 下、0 下打錯，格子是 `(0,1)`、`(1,0)`、`(2,0)`。連續提示同一句與換句都是 3/3。

`cb6fb3d` 只失敗 `test_toast_timer_resets`：同一句三趟都重播 `fadeInOut`。偏離中心全過，遮擋點 0 下打錯，無障礙字鍵盤 0。

`52775b7` 失敗 `test_tap_offcenter` 與 `test_toast_timer_resets`。沒選建築兩個視窗都是 239/266、反應不符 27，精靈點選中了非金的 `(3,2)`。已選與取出是 0。遮擋點 0 下打錯。

`8940905` 的 API 只失敗 `test_autoplace_already_owned_uses_formal_copy`。沒選建築仍是 239/266、反應不符 27。遮擋點 15 下都選中了非金的背面格，沒有提示放不下。無障礙字仍是「已興建」／「放不下」，鍵盤沒有打出提示那一句。

`a871b1b` 的 API 同樣只失敗書面語那條。偏離中心沒選建築 1100×800 是 198/266、打錯格 68；390×844 是 164/266、打錯格 102。已選 1100×800 是 186/251、打錯格 65、面板選中 4；390×844 是 153/251、打錯格 98、面板選中 4。取出 1100×800 是 198/266、打錯格 68；390×844 是 131/203、打錯格 72。遮擋的 15 個獨佔菱形點打中背面格。無障礙字仍不合。連續提示約 1.58 秒被舊計時器關掉。

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

## 對照 `77f320f`（QC6）

測試尖端 `77f320feff22107b4d630ef3f6f9af74d299eb55`。產品工作樹只疊了這套測試，沒有提交。`003b81f` 與 `b6dc646` 的產品檔相同，下面 `b6dc646` 的數字同時代表 `003b81f`。`kids_town.db` 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。

| 產品 | API | 介面 |
|------|-----|------|
| `b6dc646` / `003b81f` | 1 failed、379 passed、134 deselected | 7 failed、127 passed、380 deselected |
| `8940905` | 2 failed、378 passed、134 deselected | 31 failed、103 passed、380 deselected |
| `a871b1b` | 2 failed、378 passed、134 deselected | 18 failed、116 passed、380 deselected |

`b6dc646` 的 API 失敗只有 `test_place_owned_explicit_cell_uses_formal_copy`（`error` 是「你已經興建咗呢種建築物」）。介面 7 條失敗：`test_tap_bar_nothrough`、`test_toast_timer_resets`、`test_tap_visible_only`、`test_selected_contrast`、`test_focus_ring_centre`、`test_hidden_inert`、`test_place_owned_formal_shown`。`test_tap_offcenter`、`TC-FE-TOWN-HIT-01`、`TC-FE-CELL-ARIA-MATCH` 仍然通過。HIT-01 兩個視窗 overlap 15、tapped 15、bad 0，格是 `(0,1)`、`(1,0)`、`(2,0)`。ARIA 鍵不符 0。清單蓋住的焦點仍是 `(0,5)`、`(0,6)`、`(1,6)`、`(0,7)`、`(1,7)`、`(2,7)`；取出沒有。偏離中心兩個視窗都是 266/266、251/251、266/266，`rect-fallthrough` 0。

`8940905` API 失敗是自動放置書面語和指定格子書面語。介面比上一輪多的失敗是這輪新案例；偏離中心仍是 reaction-mis（bare 239/266、27 格），HIT-01 bad 15，ARIA 仍是 28 格、128 個鍵。`a871b1b` API 同樣兩條書面語。介面 18 條失敗含這輪新案例；偏離中心仍是鄰格選錯。

新案例在 `b6dc646` / `003b81f` 上的數字：

- `TC-FE-TAP-VISIBLE-ONLY` 紅。捲動 0 有藏起來的格子候選，但選中數是 0（實心介面吃掉了）。捲到最大之後上緣會選格：1280×720 三種狀態都是 probes 40、leaks 16，含「已選擇空地。」。1100×800 與 390×844 捲到最大是 leaks 9。提示下方那 8px 有 15 個點、leaks 0。提示蓋住頁尾時打中藏起來的 `(5,5)` 仍由這條鎖；這一版的提示落在地圖裡的動作列上，那 15 個點沒有走到頁尾後面的格子。
- `TC-FE-TOAST-TIMER-RESET` 紅。同一句 1.0 秒與 1.6 秒各 3 趟，都在第一下之後約 1720ms 掉到 opacity 0.96，然後回到 1.00。換句沒有失敗。
- `TC-FE-SELECTED-CONTRAST` 紅。計算後的線是 `#d4a017`、寬 4，和金色虛線相同。邊緣格 `(6,0)` 的線像素是 `#d4a017`：對草地 `#7eae52` 1.10（32 點）、對空地 `#d5e6b4` 1.79（14 點）、對挨著線的金色填色 `#efde9a` 1.76（44 點）。內部格 `(4,3)` 對金色填色同樣 1.76（59 點）。深金 `#ead381` 沒有形成夠大的一片（少於 8 個像素），這次不計。
- `TC-FE-FOCUS-RING-CENTRE` 紅。1280×720 的環中心比頂面中心低 8.8px（頂面偏移 8.50）。390×844 低 2.7px（頂面偏移 2.59）。
- `TC-FE-HIDDEN-INERT` 紅，只因為收起的抽屜。class `dr`、沒有 `o`、左緣 x=1310，13/13 顆按鈕仍在 Tab 順序。打開之後會回來，這一半通過。
- `TC-FE-TAP-BAR-NOTHROUGH` 紅，因為圓角外的透明區。1280×720 沒選建築每個捲動 16/48；已選工坊在捲動 0 是 42/48，其後 16/48。1100×800 沒選 14/48，已選捲動 0 是 42/48，其後 15/48。390×844 的 48 個角點都是 0，不能當成這條通過。提示底下沒有看得見的金格，點提示範圍選中數 0。
- `TC-API-PLACE-OWNED-FORMAL` 紅。API 與 `#toast` 都是「你已經興建咗呢種建築物」。

Guard（通過，不是新的紅測）：

- 實心介面的反向點在三個產品上都是 PASS。收起清單後原矩形的金格 `(0,5)` 選中 `(0,5)`。收起抽屜 `(5,0)` 選中 `(5,0)`。關掉的面板 `(2,0)` 選中 `(2,0)`。隱藏元素掃了 10 個、擋住 0。提示和特效都沒有吃掉 `(2,0)`。
- `#ktRotate` 在 1280×720 和 390×844 都是 `display:none`、Tab 停點 0，guard PASS。沒有用腳本把它改成顯示。

## 對照 `37b46b1`（提示蓋住頁尾）

`0343e3b` 的提示條在捲動 0 是 15 點、0 次選中，因為那些點在提示盒子外面，文件上的點擊監聽不會跑。`regress-61-003b81f.md` 的點在提示還顯示時落在頁尾上。`37b46b1` 先 `showToast('探針')`，再用 `page.mouse` 點那些視窗座標，以及四周 8px、提示和頁尾重疊的 8px、地圖可見下緣之下仍在頁尾裡的點。1280×720 與 1100×800，捲動 0，還沒選建築和已選工坊。

`b6dc646`（產品與 `003b81f` 相同）整套仍是 API 1 failed、379 passed，介面 7 failed、127 passed。失敗名單沒有變。新的漏點：

| 畫面 | 點 | 漏 | 回歸座標 |
|------|----|----|----------|
| 1280×720 還沒選、已選工坊 | 43 | 39 | 3/4 |
| 1100×800 還沒選、已選工坊 | 27 | 19 | 2/3 |

1280×720 的 `(640, 642.1)` 選中 `(5,5)`，還沒選建築時狀態是「已選擇空地。」`(640, 618.4)` 和 `(640, 630.2)` 把提示改成「這個位置已經有建築物。」`(640, 640)` 這一次沒有漏。1100×800 的 `(550, 697.3)` 選中 `(5,5)`，`(550, 721)` 選中 `(6,6)`，可見比例都是 0。`(550, 709.1)` 這一次沒有漏。舊的 15 點提示條仍然是 0 次選中。

## 對照 `32d2a52`（窄條、草地、邊線、金線、焦點環、伺服器句子）

測試尖端 `32d2a52`。產品工作樹只疊了這套測試。`kids_town.db` 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。整套只跑在 `3625974`。`b148dcb` 與 `b6dc646` 跑這七條加放置書面語 guard。`86e5841` 本身沒有這七條；下面 `b6dc646` 的新案例是把 `32d2a52` 的測試疊上去的結果。`86e5841` 在 `b6dc646` 上記下的整套仍是 API 1 failed、379 passed、134 deselected，介面 7 failed、127 passed、380 deselected。

| 產品 | API | 介面 |
|------|-----|------|
| `3625974` | 0 failed、381 passed、140 deselected（65.93s） | 7 failed、133 passed、381 deselected（448.62s） |

`3625974` 的 7 條介面失敗就是這一輪：`test_tap_bar_nothrough`、`test_tap_bar_gap_band`、`test_tap_scene_grass_edge`、`test_focus_ring_shape`、`test_selected_over_gold`、`test_focus_ring_above_sprite`、`test_place_server_msg`。上一輪在 `b6dc646` 失敗的對比、焦點中心、隱藏抽屜、提示計時、只吃看得見的地圖、指定格子的畫面書面語，在 `3625974` 通過。`TC-API-PLACE-OWNED-FORMAL` 也通過（句子已是書面語）。

`b148dcb` 這七條的反應與 `3625974` 相同，實心介面 guard 仍是 PASS。

- `TC-FE-TAP-BAR-GAP-BAND` 紅。窄條 1280×720 高 8.00px，1100×800 高 6.88px。1280 還沒選和已選工坊都是 14 點、6 次有反應。字面座標都漏：`(640,609)` 提示「這個位置已經有建築物。」（不是「放不下」），`(930.5,609)` 選中 `(6,2)` 可見像素 0，`(404.4,609)` 選中 `(3,6)` 可見像素 0。1100×800 兩種狀態都是 11 點、3 次有反應。
- `TC-FE-TAP-SCENE-GRASS-EDGE` 紅。草地 y 541–613，少建築和滿鎮（含銀行）各 29 點、11 次有反應。`(349.5,577)`、`(155.8,544)`、`(219,544)` 都提示「想在這裏興建？請先按「我要起屋」。」，這次種子沒有打開銀行或商店面板；仍然是選格或提示，所以算紅。
- `TC-FE-TAP-BAR-NOTHROUGH` 紅，因為邊線。圓角那組在 `3625974` 是 0/48。1280 上緣整數像素：捲動 0 是 1444 點、1097 次漏；捲動 300 是 1445 點、249 次；捲動 366 是 1447 點、200 次。放置列上緣 1159 點、908 次漏。字面座標：`(294.5,163.5)` 在捲動 300 選中 `(0,5)`、捲動 366 選中 `(1,6)`。`(177,163.5)` 選中 `(0,6)`。`(1135,154.5)` 提示「這個位置放不下這座建築物。」。`(976.5,244.3)` 在 1100×844 捲動 366 同樣提示放不下。`(976.5,222.3)` 在 1100×800 捲動 366 提示放不下；捲動 0 和 300 這一次沒有漏。Guard 仍是 PASS：收起清單 `(0,5)`、收起抽屜 `(5,0)`、關掉的面板 `(2,0)`、隱藏元素 10 個擋住 0、提示和特效都沒有吃掉 `(2,0)`。`#ktRotate` 兩個視窗都是 `display:none`、Tab 停點 0，PASS。
- `TC-FE-SELECTED-OVER-GOLD` 紅。`(0,0)` 和 `(3,3)` 的 NE、NW 是 9/9 `#7c2d12`。SE 是 0/9 褐、6/9 金。SW 是 0/9 褐、7/9 金。
- `TC-FE-FOCUS-RING-SHAPE` 紅。1280 的 `(3,3)` 環是 132.5×94.6，格子 142.8×85，寬高比差 16.7%。東、西尖角在格子裡面約 5px，而且壓在選中實線上（約 1249 個環像素）。1100×800 與 390×844、邊緣格和內部格同一件事。
- `TC-FE-FOCUS-RING-ABOVE-SPRITE` 紅。商店圖不透明的地方，NE 0/8、NW 1/8 是環的顏色。
- `TC-FE-PLACE-SERVER-MSG` 紅。背景放置是 201，確定之後提示是「這個位置放不下這座建築物。」，不是「你已經興建了這種建築物。」。三條 guard 都是這句通用句，沒有 `field required`、括號或 JSON：422 的 `detail` 陣列、沒有 `detail` 的 400、英文 `detail`。
- `TC-API-PLACE-DETAIL-FORMAL` 在 `3625974` 全綠，沒有口語路徑。23 條 4xx 的字串都沒有「咩、呢、唔、嘅、㗎」。中文句子在 `error`（產品還沒有 `detail`）：已經放置、城鎮沒有空位、座標不正確、超出地圖、建築物佔用、裝飾佔用，都是書面語。其餘是英文（`region_locked`、`unlock_region`、`Insufficient resources`、`Building definition not found`、`Kid not found`、缺欄位那句）。存倉列放回是 200，不在這條裡。已知定義、還沒有這座建築，是 201，也不是 4xx。

`b6dc646`（`86e5841` 當時的產品）叠上這套測試：七條介面都紅，guard 仍 PASS。指定格子的已經放置是「你已經興建咗呢種建築物」（有「呢」），所以 `TC-API-PLACE-DETAIL-FORMAL` 只有這一路紅；省略座標的已經放置在這一版已是書面語。`(177,163.5)` 在這版捲動 366 沒有漏。放置列上緣 1159 點、0 次漏。選中線四邊都還是金色（NE/NW 也是 0/9 褐）。

## 對照 `f8dc47c`（村外不算出露、整數邊線）

測試尖端 `f8dc47c`（父提交 `bb885ed` 上再讓場景 3 用多格金格打開，捲動不動）。產品工作樹只疊了這套測試。`kids_town.db` 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。整套跑在 `3625974`，測試是 `bb885ed`（場景 3 的開法在 `f8dc47c` 才改，不影響其餘案例的斷言）。`b148dcb` 跑這八條；`test_tap_bar_nothrough` 再用 `f8dc47c` 重跑。`cursor/green-warehouse-placement-8555` 推上去的尖端仍是 `3625974`。`2959131` 沒有推上去，所以沒有另一個綠色尖端可跑。

| 產品 | API | 介面 |
|------|-----|------|
| `3625974` | 0 failed、381 passed、140 deselected（70.85s） | 8 failed、132 passed、381 deselected（484.84s） |

第八條失敗是 `test_tap_offcenter`。上一輪的七條仍然失敗，症狀相同。Guard 仍是 PASS：收起清單 `(0,5)`、收起抽屜 `(5,0)`、關掉的面板 `(2,0)`、隱藏元素 10 個擋住 0、提示和特效都沒有吃掉 `(2,0)`。`#ktRotate` 仍是 `display:none`、Tab 停點 0。

預期改寫（舊 → 新）：

偏離中心 84 點，從「露出、必須作用在該格」改成「在 `#village` 外、不得有反應」。還沒選、已選工坊、取出用同一組座標。村內其餘點仍打中正確的格（打錯格 0、反應不符 0）。

- 1100×800，y=614.6：`(7,1)` `(928.9,614.6)`、`(907.4,614.6)`；`(6,2)` `(806.2,614.6)`、`(784.7,614.6)`；`(5,3)` `(683.5,614.6)`、`(662.0,614.6)`；`(4,4)` `(560.7,614.6)`、`(539.3,614.6)`；`(3,5)` `(438.0,614.6)`、`(416.5,614.6)`；`(2,6)` `(315.3,614.6)`、`(293.8,614.6)`；`(1,7)` `(192.6,614.6)`、`(171.1,614.6)`。
- 390×844，y=498.1：`(7,1)` `(329.3,498.1)`、`(321.7,498.1)`；`(6,2)` `(285.8,498.1)`、`(278.2,498.1)`；`(5,3)` `(242.3,498.1)`、`(234.7,498.1)`；`(4,4)` `(198.8,498.1)`、`(191.2,498.1)`；`(3,5)` `(155.3,498.1)`、`(147.7,498.1)`；`(2,6)` `(111.8,498.1)`、`(104.2,498.1)`；`(1,7)` `(68.3,498.1)`、`(60.7,498.1)`。

`3625974` 上這 84 點仍然有反應（放不下、選格、或「已經有建築物」），所以偏離中心轉紅。裁對村外框之後這些點不該有反應。

邊線只有一處改寫。1280 捲動 366，工具列外框下緣是 153（left 1134.55，right 1217，top 109）。`(1135,154.5)` 從「必須擋住」改成 `(1135,154)` 必須打到底下那一格。等距命中是放不下的 `(7,0)`，新預期是提示「這個位置放不下這座建築物。」，不是選格。這一點通過。含邊的 `(1135,153)` 必須擋住；產品仍提示放不下，邊線仍紅。

不再斷言的貼邊 .5 點（不是改成選格）：`(294.5,163.5)` 在 1280 捲動 300 和 366；`(177,163.5)` 在 1280 捲動 366；`(976.5,244.3)` 在 1100×844 捲動 366；`(976.5,222.3)` 在 1100×800 捲動 0、300、366。

新的反向點，不是舊預期改寫。`(254,490)` 在 1100×800 捲動 1、1100×844 捲動 26 選中 `(0,5)`。`(254,505)` 在 1100×800 捲動 0、1100×844 捲動 9 選中 `(0,5)`。1280 這兩點落在調色盤裡面，不當反向點。

`3625974` 與 `b148dcb` 的反向失敗相同（`f8dc47c` 重跑）：

- 沒有看得見的格，卻提示「這個位置已經有建築物。」：1280 捲動 0 的底欄和放置列 `(640,606)`、`(640,607)`；1100×800 捲動 0 的 `(550,612)`、`(550,613)`；1100×844 捲動 0 的 `(550,634)`、`(550,635)`。點在 `#townMap` 上。這是底欄和地圖下緣之間的窄條，裁對 `#village` 之後不該有反應。
- 調色盤上緣外面 1px、2px，等距命中是金格 `(0,6)`，產品沒有選格也沒有提示，`elementFromPoint` 是 `#village`：1280 捲動 366 的 `(177,162)`、`(177,161)`；1100×800 捲動 366 的 `(152,229)`、`(152,228)`；1100×844 捲動 366 的 `(152,251)`、`(152,250)`。同一列的含邊像素（1280 的 y=163）會選中 `(0,6)`。

其餘 1px、2px 反向點，包括放置列在捲動 300 和 366，是 0 次失手。場景 3 在 1100 捲動 300 要換一格金格才打得開；打開之後那些點打得到地圖。

整數邊線仍然漏。1280 擋住的點：捲動 0 是 1412 點、1097 次漏；捲動 300 是 1412 點、247 次；捲動 366 是 1413 點、195 次。放置列上緣 1159 點、908 次漏。1100 兩個高度的含邊像素也漏（捲動 366 多了工具列下緣）。圓角那組仍是 0/48。

`b148dcb` 這八條與 `3625974` 相同，guard 仍是 PASS。窄條、草地、選中線、焦點環、商店圖蓋住環、伺服器句子的數字與上一節相同。

## 對照 `9acfaf6`（選格要讀 acted）

測試尖端 `9acfaf6`（父提交 `b708905`）。產品工作樹只疊了這套測試，沒有改產品。`kids_town.db` 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。`cursor/green-warehouse-placement-8555` 推上去的尖端仍是 `3625974`，所以沒有第四個產品可跑。`25c91c9` 用 GitHub 分支 `cursor/wip-61-25c91c9` 的完整 SHA `25c91c9e0cfd46687a981ff6639b0161aff87024`，只讀。它的父提交是 `fd4eb4b`，不是 `3625974`。

讀反應的合約：`selection_of` 先讀 `preview`，再讀 `chosen`，再讀 `acted`。`reaction_happened` 是唯一的「有沒有反應」判斷：選了格、出了提示、這一下打開了面板、進了場景 3，或狀態含「已選擇空地」，都算有反應。已經開着的 `#actionSheet` 不算。每一組探測之前先點一格看得見的金格；讀不到那一格，測試自己失敗。

`b708905` 曾把已經開着的面板當成這一下的反應。`#actionSheet` 四角各向內 3、5、7 像素，共 12 點，在 `3625974` 上從 leaked 0 變成 leaked 12。`9acfaf6` 改回「這一下才打開的面板才算」，同一組重新是 leaked 0。下面的數字都是 `9acfaf6`。

| 產品 | API | 介面 |
|------|-----|------|
| `3625974` | 0 failed、387 passed、140 deselected（66.55s） | 8 failed、132 passed、387 deselected（509.78s） |
| `b148dcb` | 0 failed、387 passed、140 deselected（66.31s） | 8 failed、132 passed、387 deselected（512.17s） |
| `25c91c9` | 0 failed、387 passed、140 deselected（65.61s） | 0 failed、140 passed、387 deselected（482.00s） |

`3625974` 與 `b148dcb` 仍是那八條紅：偏離中心、邊線、窄條、草地、選中線蓋金線、焦點環形狀、焦點環在圖上面、伺服器句子。沒有一條從紅變綠。Guard 仍是 PASS。`b148dcb` 的焦點環在圖上面是 NE 1/8、NW 1/8；`3625974` 是 NE 0/8、NW 1/8。兩邊都失敗。

假紅改成通過（讀到 `acted` 之後，真的選中 `(0,6)`）：

- 1280 捲動 366：`(177,162)`、`(177,161)`
- 1100×800 捲動 366：`(152,229)`、`(152,228)`
- 1100×844 捲動 366：`(152,251)`、`(152,250)`

同一列的含邊像素仍然該擋、卻選了格，所以邊線仍紅：1280 捲動 366 的 `(177,163)` 選中 `(0,6)`。捲動 0 和 300 的調色盤上緣外面沒有看得見的格，也沒有反應。

沒有「原本不該有反應、以前誤判通過、現在變紅」的點。核對過的點在 `3625974` 上維持原判：

- 村外 84 點仍然有反應（每個視窗、每種模式 14 點）。這是提示或選格，不是漏讀 `acted`。
- `(1135,153)` 仍提示「這個位置放不下這座建築物。」
- 窄條仍漏。1280 是 14 點、6 次，包括 `(640,609)`、`(930.5,609)`、`(404.4,609)`。底欄外 1px、2px 的 `(640,606)`、`(640,607)` 仍提示「這個位置已經有建築物。」1100×800 是 11 點、3 次。
- 調色盤和工具列的含邊像素仍漏。1280 擋住的點：捲動 0 是 1412 點、1097 次；捲動 300 是 1412 點、247 次；捲動 366 是 1413 點、195 次。放置列上緣 1159 點、908 次。圓角那組是 leaked 0。
- `(254,490)`、`(254,505)` 仍選中 `(0,5)`（1100×800 捲動 1 和 0，1100×844 捲動 26 和 9）。

草地仍是 29 點、11 次，包括 `(349.5,577)`、`(155.8,544)`、`(219,544)`。選中線東南、西南仍被金色蓋住。1280 焦點環仍是 132.5×94.6 對 142.8×85，形狀差 16.7%。伺服器句子仍被改成「這個位置放不下這座建築物。」三條 guard 仍是那句通用句子。

`25c91c9` 這八條都通過，是產品不同，不是讀反應讀漏了。村外 84 點的 outside-reactions 是 0。窄條和草地的 leaks 是 0，上面那幾個座標都安靜。整數邊線 leaks 是 0，反向失手是 0。那 6 個調色盤上緣點選中 `(0,6)`。`(254,490)`、`(254,505)` 選中 `(0,5)`。選中線四個角都是 9/9 褐色。1280 焦點環是 156.4×92.9，形狀差 0.1%。焦點環在圖上面是 NE 3/7、NW 3/7。伺服器提示正好是「你已經興建了這種建築物。」Guard 是 PASS。沒有 helper sanity 失敗。

## 對照 `c628e77`（填色、環、半像素）

測試尖端 `c628e77`。產品工作樹只疊了這套測試。`kids_town.db` 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。`25c91c9` 只讀，完整 SHA `25c91c9e0cfd46687a981ff6639b0161aff87024`。

像素和未選中、未聚焦的同一張截圖比。環色只數格子多邊形外面、離邊大約 8px 以內、而且相對底圖有變化的像素。邊內至少 8px 的點要和底圖一致；「此格」徽章的區域只有選中時才排除。只聚焦時，中心也要和底圖一致。已經是褐色的建築圖像素不算新填上的 `#7c2d12`。褐線中線內縮 0.5–1.5px，用外緣在格子外 0–1px 來判斷。環的內緣大約在格子外 2px。

實心控制項外面「必須打到地圖」的點是 `floor(top)-1`、`ceil(bottom)+1`、`floor(left)-1`、`ceil(right)+1`。外框外 0–1px 不判斷。`#village` 外面半像素列不在這條寬限裡。

| 產品 | API | 介面 |
|------|-----|------|
| `25c91c9` | 0 failed、387 passed、143 deselected（69.46s） | 3 failed、140 passed、387 deselected（498.94s） |
| `3625974` | （本輪沒有重跑 API） | 11 failed、132 passed、387 deselected（528.10s） |
| `b148dcb` | （本輪沒有重跑 API） | 11 failed、132 passed、387 deselected（530.24s） |

`25c91c9` 的三條紅是新案例。上一輪通過的 140 條介面仍然通過。Guard 是 PASS。

`TC-FE-SELECTED-NO-FILL` 在 `25c91c9` 紅。1280 內部格 `(1,1)` 中心 `#efde9a` → `#7c2d12`。邊內的點離開底圖（`#f1df9c` → `#7c2d12`，Δ253）。褐線寬 NE 25、SE 23、SW 24、NW 25，外緣伸出 10–12px（要 2–4px 寬、外緣 0–1px）。「此格」徽章奶油色像素是 0。1100 外緣約 9–10px，390 外緣約 3–4px，中心同樣變成 `#7c2d12`。

`TC-FE-FOCUS-RING-NO-FILL` 在 `25c91c9` 紅。只聚焦、未選中時，中心也算在內：1280 金格 `#efde9a` → `#7c2d12`（Δ251），圖書館 `(6,0)` `#e0cbb1` → `#7c2d12`。格子外有褐像素（1280 金格 NW 11、NE 5、SW 5、SE 2）。選中又聚焦時環的虛線被填色蓋住，1280 四邊環色是 0/5。

`TC-FE-FOCUS-RING-SHAPE` 在 `25c91c9` 仍通過。1280 環 156.4×92.9，格子 142.8×85，形狀差 0.1%，尖角在外面。格子裡的徽章和地面沒有被算成環色。

`TC-FE-TAP-VILLAGE-HALFPX` 在 `25c91c9` 紅。場景 1、捲動 0。1280 的 `#village` bottom 是 541.00，y=541.50，145 點裡 139 點提示「想在這裏興建？請先按「我要起屋」。」390 bottom 是 477.15，y=477.65，44 點裡 42 點同樣提示。對照是綠的：1280 在 `(199.0, 539.5)` 選中 `(0,6)`；390 在 `(80.0, 475.6)` 選中 `(1,6)`。

工具列在三個產品、1280、捲動 366 的 `getBoundingClientRect` 都是 top 109、bottom 153、left 1134.55、right 1217。必須打到地圖的下緣是 `ceil(bottom)+1` = 154，不是寫死的 156。`25c91c9` 這組反向點 miss 0，含邊 leaks 0，整條 `TC-FE-TAP-BAR-NOTHROUGH` 通過。`(254,490)` 和 `(254,505)` 在 1100 離調色盤右緣 253.52 只有約 0.5px，落在 0–1px 帶，不判斷；改點 `(255,490)` 和 `(255,505)`。捲動 0 選中 `(0,5)`。捲動 300 和 366 下面沒有格，沒有反應。1280 這兩個字面點在調色盤裡面，跳過。

`3625974` 和 `b148dcb` 仍是原來那八條紅，再加上三條新的，共 11 條。132 條原來通過的介面仍然通過。Guard 仍是 PASS。

- 偏離中心、窄條（1280 是 14 點、6 次，包括 `(640,609)`、`(930.5,609)`、`(404.4,609)`）、草地（29 點、11 次）、邊線（1280 捲動 0 擋住 1412 點、漏 1097 次；捲動 366 漏 194 次；含邊 `(1135,153)` 仍提示放不下）、焦點環形狀（1280 仍是 132.5×94.6 對 142.8×85，形狀差 16.7%，東、西尖角在格子裡面）、選中線東南西南仍是 0/9 褐、6–7/9 金、焦點環在圖上面（`3625974` 與 `b148dcb` 都是 NE 0/8、NW 1/8）、伺服器句子仍是「這個位置放不下這座建築物。」
- 選中不填色也紅：1280 中心 `#efde9a` → `#fff5cf`，東南、西南褐線寬 0，抽樣是 `#d4a017` 不是 `#7c2d12`。徽章奶油色像素約 644，徽章本身還在。
- 焦點環不填色也紅：只聚焦時中心維持 `#efde9a`，但環的內緣在 0–1px（要 2–4px）。圖書館圖上原本就近褐的像素沒有被當成新填色。選中後中心變成 `#fff5cf`。
- 半像素列同樣紅：1280 是 139/145，390 是 42/44。對照仍選中格子（1280 `(199.0,539.5)` → `(0,6)`；390 `(62.0,475.6)` → `(0,6)`）。

## 對照 `ec5f494`（選中線層、環層、原生 focus）

測試尖端 `ec5f494`。產品工作樹只疊了這套測試。`kids_town.db` 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。綠尖 `ff05ccd` 的完整 SHA 是 `ff05ccd92fe91c93e23044f60a65ebeb759383eb`。`25c91c9` 只讀，完整 SHA `25c91c9e0cfd46687a981ff6639b0161aff87024`。本輪沒有重跑 `3625974` 和 `b148dcb`。

選中線是 `#7c2d12`。環是焦點環那一層。內緣用螢幕像素，不是舞台像素。拍底圖之前，全畫面 `#7c2d12` 必須是 0，環層也必須是 0 像素。

| 產品 | API | 介面 |
|------|-----|------|
| `ff05ccd` | 0 failed、387 passed、151 deselected（65.64s） | 8 failed、143 passed、387 deselected（556.92s） |
| `25c91c9` | 0 failed、387 passed、151 deselected（64.83s） | 9 failed、142 passed、387 deselected（555.69s） |

`ff05ccd` 的八條紅：

- `TC-FE-MARK-CLEARED`。取消、回到場景 1、切到任務板，各剩 888 個 `#7c2d12`。`#chosenMarkPaint` 的 `gone` 是 False（`hidden` 沒有把它收起）。
- `TC-FE-MARK-KEPT-READYBAR`。場景 3 的 `#uxPlaceBar` 看得見，`#readyBar` 沒有。改選 `(4,3)` 之後，那一格周圍的 `#7c2d12` 是 0。線留在進來時那一格。
- `TC-FE-MARK-FOLLOWS-SCROLL`。選中線本身跟著捲動：捲動 0 和 366，`(3,3)` 四邊外緣都是 0.67–0.71px。環的內緣不夠：捲動 0 的西南、西北是 1.90px，捲動 366 的西北是 1.90px（要 2–4）。
- `TC-FE-PAINT-UNDER-UI`。清單裡的差不是 0。捲動 0 聚焦 1255px（褐 0），選中 830px（褐 806）。捲動 366 聚焦 325px（褐 0），選中 257px（褐 234）。鍵盤打開的銀行面板差 1302px，環層 1697px。
- `TC-FE-FOCUS-RING-SHAPE`。幾何外形仍過：1280 環 156.4×93.0，格子 142.8×85，形狀差 0.1%。畫出來的內緣有幾條低於 2.0 螢幕 px。`deviceScaleFactor` 1：1280 的 `(6,0)` 和 `(3,3)` 西北都是 1.90；390 的 `(6,0)` 東北 1.70；390 的 `(3,3)` 西南 1.60、西北 1.50。`deviceScaleFactor` 2：1280 和 1100 的八條邊都在 2.0–2.6；390 的 `(6,0)` 東南 1.80，`(3,3)` 西南 1.70、西北 1.60。每條邊都有 24 個樣本。
- `TC-FE-SELECTED-NO-FILL`。每個視窗的第一格底圖是乾淨的，線本身也在規格裡（寬 3–4px，外緣 0 或 1px，徽章奶油色還在，中心不是 `#7c2d12`）。同一輪後面的格子，底圖之前已經有褐像素：1280 是 972，1100 是 833，390 是 277。取消沒有把線清掉。
- `TC-FE-FOCUS-RING-NO-FILL`。只聚焦的底圖是乾淨的，中心沒有變色，四邊環色是 5/5。選中之後再拍底圖時，同一條沒清掉的線還在：1280 是 972，1100 是 833，390 是 277。
- `TC-FE-NATIVE-FOCUS`。`HTMLElement.prototype.focus` 是包了一層的函式，不是 `[native code]`。`town-four-scene.js:1767` 有指派。`blur` 仍是原生。

`ff05ccd` 上這三條新案例是綠的，沒有改成硬失敗：

- `TC-FE-MARK-RESTORE-AFTER-SHEET`。關上商店面板之後，`(3,3)` 四邊外緣 0.69–0.71px，褐像素 872，格子仍是選中。
- `TC-FE-RING-CLEARED`。失焦、換場景、切到任務板之後，canvas 都是 `display: none`、0 像素。
- `TC-FE-RING-EDGE`。格子是 8×8，角是 `(0,0)`、`(7,0)`、`(0,7)`、`(7,7)`。四個角在看得見的地圖裡都是 144 中、0 缺；地圖外面也是 0 缺。

`TC-FE-TAP-VILLAGE-HALFPX` 在 `ff05ccd` 通過。1280 的 y=541.50 是 0/145，390 的 y=477.65 是 0/44。對照仍選中：1280 `(199.0,539.5)` → `(0,6)`，390 `(80.0,475.6)` → `(1,6)`。上一輪通過的其餘介面仍然通過。`#readyBar` 和抽屜這兩個 guard 是綠的：抽屜在視窗外；確認欄整塊的像素差來自狀態句子（選中時約 4300px），縮進 4px 之後的 `#7c2d12` 和環奶油色是 0，沒有算進失敗。

`25c91c9` 的九條紅，其中新案例五條，舊案例四條：

- `TC-FE-MARK-CLEARED` 通過。取消、回地圖、任務板都是 0 個 `#7c2d12`，標記層 `gone` 是 True。這一版沒有 `#chosenMarkPaint`，格內的圖 `hidden` 會收起。
- `TC-FE-RING-CLEARED` 通過。失焦、換場景、切分頁之後，環是 `DIV`、`display: none`、0 像素。
- `TC-FE-NATIVE-FOCUS` 通過。`focus` 的字串是 `function focus() { [native code] }`。產品腳本沒有指派 `HTMLElement.prototype.focus`。`blur` 也是原生。
- `TC-FE-MARK-KEPT-READYBAR` 紅。`#uxPlaceBar` 看得見，但 `(4,3)` 周圍的 `#7c2d12` 是 0。場景 3 的預覽不是這條褐線。
- `TC-FE-MARK-RESTORE-AFTER-SHEET` 紅。關上面板之後褐像素還在，但四邊外緣約 5.98px，不是 0–1.5px。
- `TC-FE-MARK-FOLLOWS-SCROLL` 紅。捲動 0 和 366，選中線外緣都約 5.98px。環的奶油帶樣本不夠 20：捲動 0 是 16、12、12、15，捲動 366 是 12、16、14、12。量到的間隙本身在 2.6–3.1px。
- `TC-FE-PAINT-UNDER-UI` 紅。聚焦 `(0,6)` 時清單裡出現填色：捲動 0 差 7018px（褐 6423），捲動 366 差 1149px（褐 965）。選中後再打開清單，差 23px（褐 0）。銀行面板差 7372px，環層 15561px。
- `TC-FE-RING-EDGE` 紅。格子仍是 8×8。四個角在看得見的地圖裡缺了奶油帶樣本：`(0,0)` 66 缺、78 中；`(7,0)` 75 缺、69 中；`(0,7)` 63 缺、81 中；`(7,7)` 66 缺、78 中。地圖外面的缺是 0。這一版的環是村子裡的 `DIV`，不是貼在 `body` 上的 canvas。
- `TC-FE-FOCUS-RING-SHAPE` 這次也紅。幾何外形仍過（1280 環 156.4×92.9，形狀差 0.1%）。新的螢幕像素內緣在 `deviceScaleFactor` 1 和 2 都有邊不到 20 個奶油樣本（1280 約 17–20，1100 約 15–20，390 約 16–19）。量到的間隙約 2.0–3.2px。
- `TC-FE-SELECTED-NO-FILL`、`TC-FE-FOCUS-RING-NO-FILL`、`TC-FE-TAP-VILLAGE-HALFPX` 仍紅，原因和上一輪相同。1280 選中中心 `#efde9a` → `#7c2d12`，褐線寬 23–25px，外緣 10–12px，徽章奶油色 0。只聚焦的中心也是 `#efde9a` → `#7c2d12`（Δ251），圖書館 `(6,0)` `#e0cbb1` → `#7c2d12`。半像素列 1280 是 139/145，390 是 42/44；對照仍選中 `(0,6)` 和 `(1,6)`。底圖之前的清潔檢查在這三條沒有另加失敗：第一格底圖是乾淨的，紅的是填色和半像素列本身。

`25c91c9` 的 `#readyBar` 和抽屜 guard 也是綠的。聚焦時確認欄差 0。選中時整塊差約 4303px、褐 0，是狀態句子，沒有算成選中線或環奶油色。抽屜在視窗外。上一輪通過、這次沒有改寫的介面仍然通過。

## 對照 `1449563`（裝置像素內緣、尖角弦、確認欄上的環）

測試尖端 `1449563`。產品工作樹只疊了這套測試。`kids_town.db` 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。綠尖 `bbb23c0` 的完整 SHA 是 `bbb23c0e0505b37f0eb29666471c1cd21ff4f5e3`。`25c91c9` 只讀，完整 SHA `25c91c9e0cfd46687a981ff6639b0161aff87024`。本輪沒有重跑 `ff05ccd`、`3625974`、`b148dcb`。

內緣是裝置像素中心到格子邊的距離。尖角開口是兩條奶油帶內端的直線距離。選中線外緣是沿法線最後仍是 `#7c2d12` 的那一點。拍底圖之前，全畫面 `#7c2d12` 是 0，環層收起。

| 產品 | API | 介面 |
|------|-----|------|
| `bbb23c0` | 0 failed、387 passed、152 deselected（69.92s） | 4 failed、148 passed、387 deselected（600.50s） |
| `25c91c9` | 0 failed、387 passed、152 deselected（66.62s） | 10 failed、142 passed、387 deselected（596.17s） |

`bbb23c0` 的四條紅，都是這一輪改過或新加的。其餘 148 條介面通過，含清單、銀行面板、抽屜，以及 `#readyBar` 縮進之後的 guard。

- `TC-FE-FOCUS-RING-SHAPE`。幾何外形仍過：1280 環 156.4×93.0，格子 142.8×85，形狀差 0.1%。`(3,3)` 的裝置像素內緣（最小／中位／最大，樣本數）在 `deviceScaleFactor` 2 低於 2.0：1280 捲動 0 和 366 的西北都是 1.9／2.5／3.0（24 和 20 個樣本），西南是 2.2。1100 捲動 366 的西北是 1.7／2.3／2.8（21 個樣本）。390 捲動 366 的東南是 1.9／2.3／3.1（24 個樣本）。同一組邊在先前的迴歸裡記成 1.8、1.5、1.6–1.7；這一輪讀到的是那些邊的裝置像素中心，仍在 2.0 下面。另外有幾條邊不到 24 個樣本，1280 捲動 366、`deviceScaleFactor` 1 的東南最大是 4.1。
- `TC-FE-SELECTED-NO-FILL`。1280 三格的外緣都在 1.06–1.42px，線寬 3–4，中心不是 `#7c2d12`。1100 的 `(0,0)` 東南外緣是 1.92px、西南 1.64px。1100 `(1,1)` 東南 1.92、西南 1.64，`(2,1)` 東北 1.58。390 的東南是 1.6、1.6、1.8。最外層褐像素的中心約在 1.40px，沿法線走到像素邊界才是上面這些數。
- `TC-FE-PAINT-UNDER-UI`。清單四次差都是 0。銀行面板差 0，環層 0。底尖靠近確認欄的空地：1280 是 `(3,4)`、`(2,5)`（南尖在欄上緣下面 51.3px）；1100 是 `(4,2)`、`(3,3)`（差 −7.6px）；390 是 `(4,2)`、`(2,4)`（差 −2.7px）。聚焦時 `#readyBar` 裡的墨水是 87、70、79，而且 `#focusRingLift`（z 31）的盒子壓在確認欄（z 30）上。選中之後 lift 收起，墨水仍是 6、9、1。
- `TC-FE-RING-VERTEX-GAP`。開口是帶的內端之間的弦，不是尖角到帶。長邊的實線比例都 ≥0.80。390 的邊長 25.32px，短於 40px，不鎖這個比例。弦本身多半超過 10px。

`bbb23c0` 尖角兩個端點（螢幕 px）：

| 比例 | 視窗 | 邊長 | N | E | S | W |
|------|------|------|---|---|---|---|
| 1 | 1280×720 | 83.09 | 18.0 (631.5,318.5)–(649.5,318.5) | 16.0 (706.5,351.5)–(706.5,367.5) | 19.1 (650.5,402.5)–(631.5,400.5) | 18.0 (573.5,368.5)–(573.5,350.5) |
| 1 | 1100×800 | 71.41 | 17.03 (541.5,362.5)–(558.5,363.5) | 14.0 (607.5,392.5)–(607.5,406.5) | 17.03 (558.5,435.5)–(541.5,436.5) | 14.0 (493.5,406.5)–(493.5,392.5) |
| 1 | 390×844 | 25.32 | 9.06 (190.5,407.5)–(199.5,406.5) | 11.0 (216.5,416.5)–(216.5,427.5) | 9.06 (199.5,437.5)–(190.5,436.5) | 9.0 (173.5,426.5)–(173.5,417.5) |
| 1 | 844×390 | 45.01 | 12.04 (415.5,170.5)–(427.5,171.5) | 13.0 (458.5,188.5)–(458.5,201.5) | 12.04 (427.5,218.5)–(415.5,219.5) | 13.0 (384.5,201.5)–(384.5,188.5) |
| 2 | 1280×720 | 83.09 | 17.5 (631.75,318.25)–(649.25,318.25) | 15.5 (706.75,351.75)–(706.75,367.25) | 18.67 (650.25,402.75)–(631.75,400.25) | 17.5 (573.25,368.25)–(573.25,350.75) |
| 2 | 1100×800 | 71.41 | 16.53 (541.75,362.25)–(558.25,363.25) | 13.5 (607.75,392.75)–(607.75,406.25) | 16.53 (558.25,435.75)–(541.75,436.75) | 13.5 (493.25,406.25)–(493.25,392.75) |
| 2 | 390×844 | 25.32 | 8.56 (190.75,407.25)–(199.25,406.25) | 10.5 (216.75,416.75)–(216.75,427.25) | 8.56 (199.25,437.75)–(190.75,436.75) | 8.5 (173.25,426.25)–(173.25,417.75) |
| 2 | 844×390 | 45.01 | 11.54 (415.75,170.25)–(427.25,171.25) | 12.5 (458.75,188.75)–(458.75,201.25) | 11.54 (427.25,218.75)–(415.75,219.75) | 12.5 (384.25,201.25)–(384.25,188.75) |

`25c91c9` 仍是上一輪那九條紅，再加上新的 `TC-FE-RING-VERTEX-GAP`，共十條。142 條通過，和上一輪的通過數相同。`#readyBar` 縮進 guard 和抽屜仍是綠的。

- `TC-FE-FOCUS-RING-SHAPE` 仍紅。幾何外形過。裝置像素內緣的最小值都在 2.8 以上，但每條邊的奶油樣本多半少於 24（約 10–22），有幾條最大超過 4.0（到 4.5）。
- `TC-FE-SELECTED-NO-FILL` 仍紅。中心 `#efde9a` → `#7c2d12`，線寬 16–25px，四邊外緣都是 3.18px，徽章奶油色 0。1100 的 `(0,0)` 同樣是 3.18px。
- `TC-FE-PAINT-UNDER-UI` 仍紅。清單：捲動 0 聚焦差 7019px（褐 6423），捲動 366 聚焦差 1152px（褐 965），選中後再打開清單差 23px 和 27px（褐 0）。銀行面板差 7373px，環層 15561px。底尖那幾格另外有墨水：聚焦 8、11、19，選中 6、9、1。這一版沒有 `#focusRingLift`；聚焦時是 `#focusRingPaint` 的盒子壓在確認欄上。
- `TC-FE-RING-VERTEX-GAP` 紅。北尖的弦只有 3.0–3.5px，短於 4px。1280 `deviceScaleFactor` 1 的東尖是 8.54、西尖是 6.0，相差 2.54。實線比例在長邊上是 0.96–1.00，這一條過了。端點見下表。
- `TC-FE-MARK-KEPT-READYBAR`、`TC-FE-MARK-RESTORE-AFTER-SHEET`、`TC-FE-MARK-FOLLOWS-SCROLL`、`TC-FE-RING-EDGE`、`TC-FE-FOCUS-RING-NO-FILL`、`TC-FE-TAP-VILLAGE-HALFPX` 仍紅，原因和上一輪相同。`TC-FE-MARK-CLEARED`、`TC-FE-RING-CLEARED`、`TC-FE-NATIVE-FOCUS` 仍通過。

`25c91c9` 尖角兩個端點（螢幕 px）：

| 比例 | 視窗 | 邊長 | N | E | S | W |
|------|------|------|---|---|---|---|
| 1 | 1280×720 | 83.09 | 3.0 (638.5,313.5)–(641.5,313.5) | 8.54 (713.5,356.5)–(710.5,364.5) | 5.0 (642.5,404.5)–(637.5,404.5) | 6.0 (566.5,362.5)–(566.5,356.5) |
| 1 | 1100×800 | 71.41 | 3.0 (548.5,359.5)–(551.5,359.5) | 7.28 (613.5,396.5)–(611.5,403.5) | 5.0 (552.5,438.5)–(547.5,438.5) | 6.0 (486.5,402.5)–(486.5,396.5) |
| 1 | 390×844 | 25.32 | 3.0 (193.5,405.5)–(196.5,405.5) | 6.0 (218.5,418.5)–(218.5,424.5) | 3.0 (196.5,437.5)–(193.5,437.5) | 6.0 (171.5,424.5)–(171.5,418.5) |
| 1 | 844×390 | 45.01 | 3.0 (420.5,168.5)–(423.5,168.5) | 6.0 (462.5,191.5)–(462.5,197.5) | 3.0 (423.5,220.5)–(420.5,220.5) | 6.0 (381.5,197.5)–(381.5,191.5) |
| 2 | 1280×720 | 83.09 | 3.5 (638.25,314.25)–(641.75,314.25) | 8.25 (713.25,356.25)–(711.25,364.25) | 3.5 (641.75,404.75)–(638.25,404.75) | 6.0 (566.75,362.25)–(566.75,356.25) |
| 2 | 1100×800 | 71.41 | 3.5 (548.25,360.25)–(551.75,360.25) | 7.57 (613.25,396.25)–(612.25,403.75) | 3.5 (551.75,438.75)–(548.25,438.75) | 6.5 (486.75,402.75)–(486.75,396.25) |
| 2 | 390×844 | 25.32 | 3.5 (193.25,406.25)–(196.75,406.25) | 5.5 (218.25,418.75)–(218.25,424.25) | 3.5 (196.75,437.25)–(193.25,437.25) | 5.52 (171.75,424.25)–(171.25,418.75) |
| 2 | 844×390 | 45.01 | 3.5 (420.25,169.25)–(423.75,169.25) | 5.5 (462.25,191.75)–(462.25,197.25) | 3.5 (423.75,220.25)–(420.25,220.25) | 5.5 (381.75,197.25)–(381.75,191.75) |

## 對照 `fb298f5`（確認欄裡的 `#fffec5`）

測試尖端 `fb298f5`。產品工作樹只疊了這套測試。資料庫 SHA 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。綠尖 `ef99b6e` 的完整 SHA 是 `ef99b6eb6c0e6ab32d542b2f512a06403b0fa751`。`bbb23c0` 的完整 SHA 是 `bbb23c0e0505b37f0eb29666471c1cd21ff4f5e3`。本輪沒有重跑 `a97f2b4`、`25c91c9`、`ff05ccd`。套件字型是 Noto Sans CJK TC。文泉驛微米黑另跑過確認欄的像素差，聚焦仍是 `#fffec5`，選中仍是欄角那一小塊，字形抗鋸齒沒有被算進墨水。

奶油只認 `#fff8e7`（平方距離 ≤25）。24 站只放在奶油帶也不會進確認欄的那段邊上。確認欄裡的像素差排除句子的文字矩形。環和選中線不再用 `elementsFromPoint`。產品沒有 `clip-path`，SVG 用畫出來的形狀的客戶端盒子。

| 產品 | API | 介面 |
|------|-----|------|
| `ef99b6e` | 0 failed、387 passed、152 deselected（62.32s） | 1 failed、151 passed、387 deselected（590.35s） |
| `bbb23c0` | 0 failed、387 passed、152 deselected（66.81s） | 4 failed、148 passed、387 deselected（585.03s） |

`ef99b6e` 只有 `TC-FE-PAINT-UNDER-UI` 紅。`TC-FE-FOCUS-RING-SHAPE` 通過：露出來的邊上 24/24 打中 `#fff8e7`，間隙在 2.0–4.0。清單四次差都是 0。銀行面板差 0，環層 0。抽屜在視窗外。底尖那幾格和上一輪相同：1280 是 `(3,4)`、`(2,5)`（差 −51.3px）；1100 是 `(4,2)`、`(3,3)`（差 −7.6px）；390 是 `(4,2)`、`(2,4)`（差 −2.7px）。

抓住 `#fffec5` 和 `text-shadow` 的斷言（失敗訊息只列出前 12 條，同一類在其餘視窗和場景掃描裡也有）：

- 確認欄句子 `#readyStatus`、`#placeStatus` 的 computed `text-shadow` 是 `rgb(59, 42, 26) 0px 0px 0px`，要 `none`。
- `svg.ring-under-bar` 是 `#readyBar` 的後代。場景 3 裡 `#uxPlaceBar` 也有一個。場景 1 和銀行面板打開時這兩個 SVG 還在 DOM 裡。
- 環層 `ring-under-bar` 在 `townMap` 這個層疊上下文裡的有效 z 是 30，沒有嚴格低於 `#readyBar` 的 30。調色盤打開時，同一個 30 也沒有低於調色盤的 20。場景 3 對 `#uxPlaceBar` 同樣是 30 對 30。
- 沒有 `clip-path`，所以走盒子規則：`ring-under-bar` 的 `rect` 客戶端盒子和 `#readyBar` 相交（場景 3 和 `#uxPlaceBar` 相交）。
- 聚焦時，文字矩形外面的像素差是 `#8b5e3c` → `#fffec5`。1280 `(3,4)` 299px（520.5,541.5），`(2,5)` 242px（378.5,541.5）。1100 `(4,2)` 100px、`(3,3)` 101px。390 兩格各 54px。

選中底圖當時是沒有選中的欄，句子和選中之後不同。欄左上角因此多了差，不是 `#fffec5`：1280 是 16px（`#867a43` → `#848947`，73.5,541.5），1100 是 10px（`#7fa64f` → `#81964b`，60.9,556.0），390 是 0。`bbb23c0` 同一位置是 17、12、0。這是換句，後來的底圖改成同一句，不再把這幾像素算成墨水。

`(3,3)` 東南、西南的站（`deviceScaleFactor` 1 然後 2；每個比例裡依序是 1280 捲動 0、1280 捲動 366、1100 捲動 0、1100 捲動 366、390 捲動 0、390 捲動 366）。`legacy` 是整條邊清掉尖角之後 24 站裡，邊點本身沒有進確認欄的站數。`vis` 是把邊外 2px 和 3px 的奶油帶也扣掉之後，剩下的長度。

| 比例 | 視窗 | 捲動 | 東南 vis / legacy / 奶油 | 西南 vis / legacy / 奶油 |
|------|------|------|-------------------------|-------------------------|
| 1 | 1280 | 0 | 47.5 / 21 / 24（2.7–3.4） | 47.5 / 21 / 24（2.1–3.4） |
| 1 | 1280 | 366 | 60.47 / 24 / 24（2.7–3.6） | 60.47 / 24 / 24（2.1–3.1） |
| 1 | 1100 | 0 | 39.41 / 21 / 24（2.7–3.5） | 39.41 / 21 / 24（2.0–3.0） |
| 1 | 1100 | 366 | 51.12 / 24 / 24（2.7–3.8） | 51.12 / 24 / 24（2.7–3.5） |
| 1 | 390 | 0 | 7.52 / 21 / 跳過 | 7.52 / 21 / 跳過 |
| 1 | 390 | 366 | 14.25 / 24 / 24（2.1–2.8） | 14.25 / 24 / 24（2.2–3.5） |
| 2 | 1280 | 0 | 47.5 / 21 / 24（2.0–2.4） | 47.5 / 21 / 24（2.0–2.5） |
| 2 | 1280 | 366 | 60.47 / 24 / 24（2.0–2.7） | 60.47 / 24 / 24（2.0–2.7） |
| 2 | 1100 | 0 | 39.41 / 21 / 24（2.4–3.3） | 39.41 / 21 / 24（2.7–3.3） |
| 2 | 1100 | 366 | 51.12 / 24 / 24（2.8–3.3） | 51.12 / 24 / 24（2.8–3.2） |
| 2 | 390 | 0 | 7.52 / 21 / 跳過 | 7.52 / 21 / 跳過 |
| 2 | 390 | 366 | 14.25 / 24 / 24（2.0–2.7） | 14.25 / 24 / 24（2.3–3.1） |

捲動 0 時南尖在確認欄下面，東南和西南的 `legacy` 是 21，不是早先估的 19–20，390 也不是 15–16。奶油帶再扣一層之後，390 捲動 0 只剩 7.52px，短於 12px，跳過。其餘露出來的邊都是 24/24。老老實實裁掉的環過得了這一條。

`bbb23c0` 仍是四條紅：`TC-FE-FOCUS-RING-SHAPE`、`TC-FE-SELECTED-NO-FILL`、`TC-FE-PAINT-UNDER-UI`、`TC-FE-RING-VERTEX-GAP`。其餘 148 條通過。清單四次差都是 0。銀行面板差 0，環層 0。抽屜在視窗外。東南、西南的 `vis` / `legacy` 和上表相同（站的位置跟格子和確認欄走，不跟環的像素走）。紅的是環本身：

- `TC-FE-FOCUS-RING-SHAPE`。幾何外形仍過：1280 環 156.4×93.0，格子 142.8×85，形狀差 0.1%。`deviceScaleFactor` 2、1280 捲動 0 的西北內緣 1.90–3.00。`deviceScaleFactor` 1、1280 捲動 366 的東南 3.00–4.10。捲動 366 有幾條東北、西北奶油站不夠 22：1280 兩個比例都是 20/24（`vis` 60.47，`legacy` 24），1100 比例 1 是 20/24、比例 2 是 21/24（`vis` 51.12），390 比例 1 是 15/24、比例 2 是 18/24 和 17/24（`vis` 14.25）。390 捲動 0 的東南、西南同樣因 7.52px 跳過。
- `TC-FE-SELECTED-NO-FILL`。1100 東南 1.92、西南 1.64，另一格東北 1.58。390 東南 1.6、1.6、1.8。和上一輪同一組數。
- `TC-FE-PAINT-UNDER-UI`。沒有 `text-shadow`，也沒有 `ring-under-bar`。紅的是 `#focusRingLift` 的 z 31 沒有低於 `#readyBar` 的 30，`#focusRingPaint` 和 `#focusRingLift` 的盒子壓在確認欄上。聚焦的像素差是真的環色，不是 `#fffec5`：1280 兩格各 79px（`#8b5e3c` → `#6b4f2a`，樣本裡還有 `#fff8e7`），1100 各 59px，390 各 78px。選中時 `#chosenMarkPaint` 的 polygon 盒子和確認欄相交。欄角那 17 / 12 / 0 px 同上。
- `TC-FE-RING-VERTEX-GAP`。弦仍是 8.5–19.1px，端點和上一輪 `1449563` 的表相同。

相對 `a97f2b4`，diff 只有 `tests/qc6_checks.py`、`tests/test_warehouse_e2e.py`、`docs/test-cases/WAREHOUSE_PLACEMENT.md`。資料庫檔沒有進 diff，SHA 沒有變。沒有加「Tab 到被確認欄蓋住的格子要自動捲動」的測試。

## 對照 `4580fa6`（同一句的欄底圖）

測試尖端 `4580fa6`。產品工作樹只疊了這套測試。資料庫 SHA 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。套件字型是 Noto Sans CJK TC，API 然後介面，兩邊各用新的暫存目錄。

確認欄的像素差改成兩張句子相同。聚焦是該格已選中，失焦對聚焦。選中線是同一格保持選中，標記層在畫對測試把 `#chosenMarkPaint` 設成 `visibility: hidden`（測完還原）。兩張的句子都斷言是「已選擇空地。請打開清單，選擇要興建的建築物。」容差仍是平方距離 25。圓角帶沒有排除。

| 產品 | API | 介面 |
|------|-----|------|
| `ef99b6e` | 0 failed、387 passed、152 deselected（69.88s） | 1 failed、151 passed、387 deselected（589.60s） |
| `bbb23c0` | 0 failed、387 passed、152 deselected（63.08s） | 4 failed、148 passed、387 deselected（587.70s） |

選中的像素差在 1280、1100、390 都是 0。上一輪換句造成的 16px／10px（`#867a43` → `#848947`）和 `bbb23c0` 的 17px／12px 不再出現。

`ef99b6e` 仍只有 `TC-FE-PAINT-UNDER-UI` 紅。抓住 `#fffec5` 和 `text-shadow` 的斷言還在：`#readyStatus`、`#placeStatus` 的 `text-shadow` 是 `rgb(59, 42, 26) 0px 0px 0px`；`svg.ring-under-bar` 是 `#readyBar` 的後代；它在 `townMap` 裡的有效 z 是 30，沒有低於欄的 30；沒有 clip，`rect` 的客戶端盒子和欄相交；聚焦差仍是 `#8b5e3c` → `#fffec5`（1280 是 299px、242px，1100 是 100px、101px，390 兩格各 54px）。

`bbb23c0` 仍是那四條紅，原因沒變。外形、外緣、尖角弦和上一輪同一組數。確認欄沒有 `text-shadow`，也沒有 `ring-under-bar`。紅的是 `#focusRingLift` z 31 沒有低於欄的 30，`#focusRingPaint` 和 lift 的盒子壓在欄上，聚焦差仍是 `#8b5e3c` → `#6b4f2a`（1280 各 79px，1100 各 59px，390 各 78px）。選中時 `#chosenMarkPaint` 的 polygon 盒子仍和欄相交。選中的像素差是 0。

## 對照 `2068c0f`（捲動環只站在沒被蓋住的那段）

測試尖端 `2068c0f`。產品工作樹只疊了這套測試。資料庫 SHA 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。套件字型是 Noto Sans CJK TC。API 然後介面，各用新的暫存目錄。`199fb09` 的介面連跑兩次。`199fb09` 的完整 SHA 是 `199fb099bb87d2c76df075b54369e58f0b001114`。`ff05ccd` 的完整 SHA 是 `ff05ccd92fe91c93e23044f60a65ebeb759383eb`。

這一輪只改了 `TC-FE-MARK-FOLLOWS-SCROLL`。焦點環改用和 `TC-FE-FOCUS-RING-SHAPE` 同一個 `ring_device_gaps`：24 站只放在沒被 `#readyBar`、`#uxPlaceBar`、調色盤蓋住的那段（矩形外擴 1px，邊外 2px 和 3px 的奶油帶進了矩形也不放站）。至少 22 站打中 `#fff8e7`。看得見的長度短於 12px 就跳過。選中線的外緣仍要在 0–1.5px，這條沒有放寬。

查過、沒有改的案例：`TC-FE-FOCUS-RING-SHAPE` 已經用這套站。`TC-FE-RING-EDGE` 的樣本點落在實心介面裡就略過，不要求那裡有奶油。`TC-FE-SELECTED-NO-FILL` 和 `TC-FE-MARK-RESTORE-AFTER-SHEET` 取的是畫出來的外緣，格子先捲進畫面。`TC-FE-RING-VERTEX-GAP` 和 `TC-FE-SELECTED-OVER-GOLD` 也先把格子捲開確認欄。`TC-FE-FOCUS-RING-NO-FILL`、`TC-FE-FOCUS-RING-ABOVE-SPRITE`、`TC-FE-FOCUS-RING-CENTRE` 不沿著整條邊向欄外要奶油配額。`TC-FE-RING-CLEARED`、`TC-FE-MARK-CLEARED`、`TC-FE-MARK-KEPT-READYBAR` 看的是層和像素數。`TC-FE-PAINT-UNDER-UI` 已經接受矩形裁切，底圖也是同一句。`199fb09` 的整套介面兩次都是 152 通過，這些沒改的案例沒有再和矩形裁切衝突。

`199fb09` 上 `TC-FE-MARK-FOLLOWS-SCROLL` 通過。捲動 0，外緣約 0.48–0.54px；環是東北 2.7–4.0、東南 2.7–3.4、西南 2.1–3.4、西北 2.0–3.0，都是 24/24。東南、西南 `vis` 47.5、`legacy` 21。捲動 366，外緣約 0.38–0.54px；環是東北 2.7–4.0、東南 2.7–3.6、西南 2.1–3.1、西北 2.0–3.0，都是 24/24，`vis` 60.47、`legacy` 24。

`ff05ccd` 上這條仍紅，選中線仍跟著捲動：捲動 0 和 366 的外緣都是 0.67–0.71px。舊的 CSS 尺把捲動 0 的西南、西北和捲動 366 的西北量成 1.90px。同一套裝置像素尺把它們讀成 2.0–2.5，不再低於 2。這次紅的是捲動 366 東南內緣 2.80–4.10（要 2–4）。捲動 0 四邊都在 2.0–3.7，24/24。

`bbb23c0` 上這條現在也紅，原因和 `TC-FE-FOCUS-RING-SHAPE` 的環相同，不是選中線。外緣仍在 0–1.5：捲動 0 是 0.60、0.85、0.79、0.52，捲動 366 是 0.65、0.85、0.77、0.54。捲動 0 的環通過。捲動 366 東北和西北各 20/24（`vis` 60.47，`legacy` 24），東南 3.00–4.10。

`ef99b6e` 的 `TC-FE-PAINT-UNDER-UI` 仍紅，原因沒變。`text-shadow` 仍是 `rgb(59, 42, 26) 0px 0px 0px`。`svg.ring-under-bar` 仍是 `#readyBar` 的後代，有效 z 仍是 30 對欄的 30，沒有 clip，盒子仍和欄相交。聚焦差仍是 `#8b5e3c` → `#fffec5`（1280 是 299px、242px，1100 是 100px、101px，390 兩格各 54px）。選中的像素差仍是 0。

| 產品 | API | 介面 |
|------|-----|------|
| `199fb09` | 0 failed、387 passed、152 deselected（64.68s） | 第一次 0 failed、152 passed、387 deselected（588.10s）；第二次 0 failed、152 passed、387 deselected（588.11s） |
| `ef99b6e` | 0 failed、387 passed、152 deselected（61.71s） | 1 failed、151 passed、387 deselected（583.47s） |
| `bbb23c0` | 0 failed、387 passed、152 deselected（67.20s） | 5 failed、147 passed、387 deselected（581.61s） |

`bbb23c0` 的五條紅：上一輪那四條還在，原因同一組數（外形的 1.90 和 4.10、奶油站 15–21、1100 外緣 1.92／1.64／1.58、390 外緣 1.6／1.6／1.8、`#focusRingLift` z 31、聚焦 `#8b5e3c` → `#6b4f2a`、尖角弦 8.5–19.1）。多出來的是 `TC-FE-MARK-FOLLOWS-SCROLL`，就是上面那組環的數。

`199fb09` 的 `.palette` 和 `.place-bar` 各有一行 `transform: translateZ(0)`。這兩行拿掉、其餘不動、不提交，倉庫的 67 條介面仍是 67 passed（475.42s）。和帶著 `translateZ(0)` 的兩次全套介面比，沒有斷言翻轉。這兩個元素本來就有 `isolation: isolate`，拿掉 `translateZ(0)` 沒有拆掉堆疊上下文，z 的守衛還是過。

偶數奇數 `clip-path` 跟得上活矩形。`#paintClipDefs` 的父節點一直是 `#townMap`，不在 `.place-bar`、`#readyBar`、`#uxPlaceBar`、調色盤裡面。捲動 366、場景 2、調色盤打開、`(3,3)` 選中又聚焦：環和選中線的洞和 `#readyBar`、調色盤的外框差是 0。改成 390：環的洞和這兩個外框差 0.005px、0.004px；選中線那一層是收起的，沒有洞可對。場景 3：環和選中線的洞都對上 `#uxPlaceBar`，差是 0。場景 1 和銀行面板打開時，欄和調色盤都沒顯示，環和選中線也收起，沒有 clip；defs 仍在 `#townMap`。

像素差是另一次拍攝，沒有寫進測試。狀態是場景 2、清單打開、沒有選中、焦點在 `body`。句子是「請點選金色空地，或打開清單選擇要興建的建築物。」`#uxPlaceBar` 在這個狀態沒有顯示（它只在場景 3）。比的是元素自己的外框，含文字，任一通道不同就算 1。視窗是 1280×720、1100×800、390×844。

| 拷貝 | 比例 | 視窗 | `#readyBar` | 調色盤 |
|------|------|------|-------------|--------|
| `199fb09` | 1 | 1280 | 8953（1158×64） | 4856（236×372） |
| `199fb09` | 1 | 1100 | 6950（995×55） | 5312（202×319） |
| `199fb09` | 1 | 390 | 2220（352×19） | 1647（71×113） |
| `199fb09` | 2 | 1280 | 22753（2316×128） | 609（472×744） |
| `199fb09` | 2 | 1100 | 19221（1990×110） | 913（404×638） |
| `199fb09` | 2 | 390 | 3585（704×38） | 208（142×226） |
| 拿掉 `translateZ(0)` | 1 | 1280 | 4993（1158×64） | 213（236×372） |
| 拿掉 `translateZ(0)` | 1 | 1100 | 3875（995×55） | 632（202×319） |
| 拿掉 `translateZ(0)` | 1 | 390 | 565（352×19） | 5（71×113） |
| 拿掉 `translateZ(0)` | 2 | 1280 | 11897（2316×128） | 598（472×744） |
| 拿掉 `translateZ(0)` | 2 | 1100 | 280（1990×110） | 913（404×638） |
| 拿掉 `translateZ(0)` | 2 | 390 | 1886（704×38） | 208（142×226） |

目標是對 `bbb23c0` 差 0。兩份拷貝都不是 0。帶著 `translateZ(0)` 時，1280、比例 1 的確認欄左段（句子）有 3757 像素不同，其中 3339 的平方距離大於 25，是字形被重新柵格化。拿掉之後，同一段是 0；剩下的 4993 全在右邊兩個按鈕上，其中 4325 像素正好是紅 −1、綠 0、藍 −1。對比度達標。`199fb09` 的 `#readyStatus` 計算色是 `#3b2a1a`，`text-shadow` 和 `filter` 都是 `none`。欄底 `::before` 是 `rgba(250, 246, 239, 0.98)`，鋪在白色上是 `#faf6ef`，對比 12.724:1。畫面裡句子最常見的墨水是 `#3b2a1a`，欄心最常見的填色是 `#f7f5eb`，對比 12.542:1。兩者都高於 4.5:1。

相對 `a97f2b4`，diff 只有 `tests/qc6_checks.py`、`tests/test_warehouse_e2e.py`、`docs/test-cases/WAREHOUSE_PLACEMENT.md`。資料庫檔沒有進 diff，SHA 沒有變。

## 對照 `f92ea38`（實線帶連續、場景 1 按鈕、角上抗鋸齒）

產品是 `f92ea38`，完整 SHA `f92ea38bcba0ca3605b325f7d4fbb51e3fb55a8d`。測試工作樹只疊了這套測試，沒有改產品。資料庫 SHA 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。只跑了 `TC-FE-RING-BAND-WALK` 和 `TC-FE-PAINT-UNDER-UI`。兩條都紅。`TC-FE-PAINT-UNDER-UI` 裡原有的清單、銀行面板、近欄句子差、場景 2／3 的 z 與幾何沒有再翻成紅；紅的是下面三處新斷言。

尖角開口不算洞。走查只用 `TC-FE-RING-VERTEX-GAP` 的實線內端。內端外面不查。第一個奶油裝置像素的內緣和連續 3 步起算的內緣相同，沒有藏在 3 步規則下面的低於 2.0。

`TC-FE-RING-BAND-WALK` 紅。內緣要 2.0–4.0，沿邊的洞不得長過 1 個裝置像素。

- `deviceScaleFactor` 1，1280 捲動 0 東南 2.7–4.1。捲動 366 東南 2.7–4.1、西南 2.0–4.1。1100 捲動 366 東南 2.7–4.4、西南 2.7–4.3。洞都是 0。390 兩次捲動四邊都在 2.0–3.9，洞是 0。
- `deviceScaleFactor` 2，1280 捲動 0 和 366 四邊都在 2.0–3.9，洞是 0。
- 1100、`deviceScaleFactor` 2、Tab 到 `(3,3)`。捲動 0 四邊 2.3–3.7，洞是 0，內緣沒有低於 2.0。捲動 366 紅：西南 2.3–4.5，西北有一段 2 個裝置像素的奶油洞（內緣 2.4–3.3）。東北 2.8–3.7、東南 2.3–3.0，這兩邊的洞是 0。

`TC-FE-PAINT-UNDER-UI` 的新紅有兩處。

場景 1 的 `.cta`（`#btnBuild`）算進 cover。1280 把 `(3,4)` 的南尖捲到按鈕中線（捲動 17，南尖 575.3，按鈕 549–601）再聚焦。`#focusRingPaint` 的 `rect` 客戶端外框和 `btnBuild` 相交。按鈕矩形裡有 3 個像素變了。

確認欄和調色盤的角：環在畫，對上把 `#focusRingPaint` 設成 `visibility: hidden`。外框外擴 6px，角上 22px 見方，扣掉環色和選中褐。1280、`deviceScaleFactor` 1，確認欄和調色盤的最大通道差都是 0。1100、`deviceScaleFactor` 2，調色盤是 0；確認欄是 35（`#b1937b` → `#c6b19e`，62 個像素超過 2，樣本在裝置像素 1970,100）。要的是 ≤2。

## 對照 `a1ef673` 和 `f92ea38`（畫出來的外緣、貼邊裁切）

測試尖端 `ba26bc6`，疊在 `b6254c2` 上。產品工作樹只疊了這套測試，沒有改產品。資料庫 SHA 仍是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。只跑了 `TC-FE-PAINT-UNDER-UI` 和 `TC-FE-RING-BAND-WALK`。`fc-match sans-serif:lang=zh-tw` 是 Droid Sans Fallback。

蓋住的範圍是 border box，加上當時 `::before` 伸出 border box 的距離。這兩個產品的確認欄和調色盤，`::before` 是 `border-box`，四邊 inset 都是 `-3px`，元素自己的 border 也是 3px，所以伸出是 0。`.cta` 沒有生成 `::before`，外緣就是 border box。4px 和 48px 都不算進 cover。洞的每一邊離這條外緣要在 1 個裝置像素以內。`.cta` 外緣裡的像素差要是 0。

`a1ef673`，完整 SHA `a1ef673a6891e5bfb00e451b78fd2424ab23037e`。1 failed、1 passed、66 deselected（44.09s）。`TC-FE-RING-BAND-WALK` 通過：`(3,3)` 的實線帶沒有走進調色盤外那 48px，所以走查抓不到這個死區。`TC-FE-PAINT-UNDER-UI` 紅。清單、銀行面板、近欄句子差、場景 2／3 的 z 與幾何、角上抗鋸齒沒有再翻成紅。`.cta` 像素差是 0。紅的是貼邊：

- 1280、`deviceScaleFactor` 1。調色盤四邊都是 48.0 裝置像素（48.0 CSS px）的死區。確認欄是 0。
- 1100、`deviceScaleFactor` 2。調色盤最大 97.0 裝置像素（48.5 CSS px）。確認欄四邊是 0.78、0.11、0.75、0.88，不超過 1，這是裝置像素 snap，留下。
- 場景 1 `#btnBuild`。四邊都是 4.0 裝置像素。要的是 ≤1。南尖捲到按鈕中線（捲動 17），像素差是 0。

角：1280 確認欄和調色盤都是 Δ0。1100、`deviceScaleFactor` 2，兩邊也是 Δ0。

`f92ea38`，完整 SHA `f92ea38bcba0ca3605b325f7d4fbb51e3fb55a8d`。2 failed、66 deselected（44.09s）。兩條都紅。

`TC-FE-RING-BAND-WALK` 和上一輪同一組數。內緣要 2.0–4.0，洞不得長過 1 個裝置像素。

- `deviceScaleFactor` 1，1280 捲動 0 東南 2.7–4.1。捲動 366 東南 2.7–4.1、西南 2.0–4.1。1100 捲動 366 東南 2.7–4.4、西南 2.7–4.3。洞都是 0。390 兩次捲動四邊都在 2.0–3.9，洞是 0。
- `deviceScaleFactor` 2，1280 捲動 0 和 366 四邊都在 2.0–3.9，洞是 0。
- 1100、`deviceScaleFactor` 2、Tab 到 `(3,3)`。捲動 0 四邊 2.3–3.7，洞是 0。捲動 366 紅：西南 2.3–4.5，西北有一段 2 個裝置像素的奶油洞（內緣 2.4–3.3）。

`TC-FE-PAINT-UNDER-UI` 的貼邊，確認欄和調色盤是過的。1280、`deviceScaleFactor` 1，兩邊的洞都是 0。1100、`deviceScaleFactor` 2，最大 0.01、最小 −0.09，不超過 1。確認欄的環盒子仍然壓在欄上，洞本身貼著外緣，所以貼邊這條過。紅的是下面三處，加上上一輪的角：

- 1100、`deviceScaleFactor` 2，確認欄角 Δ35（`#b1937b` → `#c6b19e`，62 個像素超過 2，裝置像素 1970,100）。1280 兩邊 Δ0。1100 的調色盤是 Δ0。
- 場景 1 `.cta` 沒有洞。`#focusRingPaint` 的 `rect` 客戶端外框和 `btnBuild` 相交，環的盒子也壓在畫出來的外緣上。
- 同一顆按鈕的像素差是 3。要的是 0。捲動 17，南尖 575.3，按鈕 549–601。

相對 `b6254c2`，diff 只有 `tests/qc6_checks.py`、`tests/test_warehouse_e2e.py`、`docs/test-cases/WAREHOUSE_PLACEMENT.md`。資料庫檔沒有進 diff，SHA 沒有變。
