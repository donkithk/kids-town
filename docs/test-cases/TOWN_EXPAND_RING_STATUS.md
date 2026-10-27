# 可擴建外圈 — 狀態

獨立回歸（本檔更新）。這次只認 PR #74 的新 tip。先前 `c1aa5a96` 的 PASS 不沿用。測試檔沒有改，也沒有改弱。紅測基線留在文末。

## 獨立回歸 #74 tip 9c1b648e — PASS，先不要合併

對新 tip 重跑紅測四條兩次，並另外抽查縮放與平移。沒有要退回建造者的契約失敗。合併仍等人眼 Preview。

| 項目 | 值 |
|------|----|
| 受測 tip | `9c1b648e2b2e6b42819e904e067f29a6c073fa1d`（`9c1b648e`，分支 `cursor/town-expand-ring-product-1016`，PR #74 head） |
| 上一 tip | `c1aa5a96f94ce800514b7df1d5d77fe20f87c750`。那次 PASS 不當作這次的結果。 |
| 紅測契約 | PR #73 tip `ef7be1573b9448055765192bb714eaad0ba66527` |
| 設計稿 | PR #72 tip `52a5bb06297725045774378427184204d8054823` |
| 命令 | `python3 -m pytest tests/test_town_expand_ring_e2e.py -q --tb=short` |
| 環境 | Python 3.12.3，pytest 9.2.0，Playwright 1.64.1（Chromium 156.0.8078.4），視窗 1280×720，Linux |
| 結果 | **4 passed，0 failed**，5.23s。接著 `-v` 再跑一次仍是 4 passed（4.38s），節點名帶 `[chromium]` |
| 產品差異（相對 #73） | 只有 `town-four-scene.js`（+190 / −3）、`town-four-scene.css`（+148 / −7）。測試與 `docs/test-cases` 相對紅測 tip 沒有 diff |
| 資料庫 | 追蹤中的 `kids_town.db` sha256 跑前、兩次官方測試後、抽查後都是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。只用臨時庫與 `test_expand_kid`。 |

| ID | Pytest | 結果 | 獨立核對 |
|----|--------|------|----------|
| TC-FE-EXPAND-RING-01 | `test_expand_ring_buildable_8x8_stays_centered` | **PASS** | 100 格。可建 64 格在 `data-col`／`data-row` 0..7，`data-zone="buildable"`，class 含 `is-buildable`。鎖住 36 格在 −1..8 的外圈，沒有第二圈，也沒有框外格。每一格 `--c`／`--r` 等於 data 座標。`COLS`／`ROWS` 仍是 8。後端 `TOWN_PLACE_COLS`／`ROWS` 仍是 8。 |
| TC-FE-EXPAND-RING-02 | `test_expand_ring_locked_styling_and_labels` | **PASS** | `#townMap` 看得到「可建區域（8×8）」和「可擴建（未解鎖）」。沒有稿上的「靜態設計稿」。 |
| TC-FE-EXPAND-RING-03 | `test_expand_ring_locked_click_toast_does_not_select` | **PASS** | 官方測試的六個樣本與 Enter 通過。抽查再點全部 36 格按鈕中心：`#toast` 可見且正好是「此格尚未解鎖，暫時不能建造。」（全形逗號 U+FF0C、句號 U+3002）。場景 1 結束時沒有 `is-chosen`。可建 `(0,0)` 仍是「想在這裏興建？請先按「我要起屋」。」 |
| TC-FE-EXPAND-RING-04 | `test_expand_ring_locked_not_placeable_keeps_selection` | **PASS** | 官方測試先選可建 `(0,0)`，再點 `(-1,0)` 與 `(8,7)` 通過。抽查在場景 2 對全部 36 格再點一次：選中仍是那一格，`aria-label` 維持「場景 2」，`#uxPlaceBar` 收起。沒有 `POST /buildings`，也沒有 expand／unlock 請求。 |

### 縮放與平移

這次新 tip 拿掉 `fitExpandRing`。`#townMap .village.is-iso` 的 `--s` 計算值是 `0.85`，沒有 inline 覆寫。可建格 `offsetWidth` 是 136（160×0.85），外框寬也是 136，村莊沒有再被父層縮小（scale 1）。

板面比視窗大，所以改為捲動：內容 1452×897，村莊視窗 1162×434，`overflow` 為 `auto`，`scrollLeft` 0..290、`scrollTop` 0..463。游標是 `grab`。開場 `scrollLeft` 145、`scrollTop` 0。水平方向這 145px 把可建地塊的外框中心對到村莊中心。垂直方向沒有對中：`centerLiveVillage` 不改 `scrollTop`，可建地塊中心比村莊中心低約 234px。北面鎖住的格子在開場畫面裡（36 格裡有 17 格的按鈕中心已經在視窗內，含整條北緣）。南緣要往下捲，最多約 463px。

36 格鎖住按鈕都能用捲動放進村莊。捲到定點後，`elementFromPoint` 打中的是該格 `.cell-btn`。在草地上拖曳會加上 `is-panning`，並把 `scrollLeft` 從 145 拉到 290；拖曳那一下沒有選中格子。鬆手後再點當時看得到的鎖住格 `(-1,-1)`，toast 仍是那句，沒有 `is-chosen`，`--s` 仍是 0.85。滑鼠滾輪實測 `scrollTop` +80。

場景 2 在捲動之後點可建 `(7,7)`：打中 `data-zone="buildable"`，toast 文字是「這個位置放不下這座建築物。」，不是鎖住那句。選中留在 `(0,0)`，沒有進場景 3。鎖住地塊上、按鈕以外的一點打中村莊本身，沒有 toast，也沒有把選中改到可建格。`cellAt` 仍拒絕 0..7 以外。契約點的是按鈕中心；按鈕約 37×37（44×0.85）。

接觸陰影跟著 `--s`。實測 `--s: 0.85`：盒子 221×95.1875、`blur(1.5px)`、徑向漸層 120px×40px，`--contact` 為 `calc(0.85 / 0.85)`。把 `--s` 暫時設成 0.39 再量（量完已還原 0.85）：盒子 101.391×43.6719、`blur(0.688235px)`、漸層 55.0588px×18.3529px。空鎮上陰影仍是 `hidden`；這是打開元素讀計算樣式，不是放了一座建築。

Toast 碼位：`此格尚未解鎖，暫時不能建造。` = U+6B64 U+683C U+5C1A U+672A U+89E3 U+9396 U+FF0C U+66AB U+6642 U+4E0D U+80FD U+5EFA U+9020 U+3002。

### Preview

水平已對中，北圈在開場畫面裡。南圈與 8×8 的南半要捲才看得到。人眼要看這個開場是不是要的。鎖住的按鈕被點到時會成為焦點，既有的 `#focusRingLift` 會畫出來（實測 180×109）；該格不是 `is-chosen`，`aria-pressed` 也不是 true。不要把焦點環看成選中。

建議：四條可以當真。不要為了這份報告合併。等 Preview 和使用者看過 0.85 與捲動後的開場再決定 #74。

## 先前 tip c1aa5a96（不沿用）

`c1aa5a96f94ce800514b7df1d5d77fe20f87c750` 上一次獨立回歸是 4 passed。那個 tip 的 `fitExpandRing` 會把 `--s` 收到約 0.3868。這次換了縮放與平移，所以那次 PASS 不算這次。

## 紅測基線（#73，保留）

紅測。只加 `tests/test_town_expand_ring_e2e.py` 與說明。產品代碼未改。對 main 的城鎮跑，四條都失敗，直到建造者把外圈做進登入後的 `#townMap`。

案例說明：[`TOWN_EXPAND_RING.md`](TOWN_EXPAND_RING.md)。

| 項目 | 值 |
|------|----|
| 產品 | main `48bae94747dc37ec1867dc3262a34a794e03200b`（本分支只加測試） |
| 設計稿 | PR #72 tip `52a5bb06297725045774378427184204d8054823` |
| 命令 | `python3 -m pytest tests/test_town_expand_ring_e2e.py -q --tb=short` |
| 環境 | Python 3.12.3，pytest 9.1.1，Playwright Chromium，Linux |
| 結果 | **4 failed，0 passed**，4.98s |
| 資料庫 | 追蹤中的 `kids_town.db` sha256 跑前與跑後都是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。測試用臨時庫與 `test_expand_kid`。 |

登入與場景 1 的 8×8 已經進得去。失敗不是登入、也不是地圖沒畫。內圈 64 格是 `pad is-quiet`，`--c`／`--r` 為 0..7。沒有 `data-col`、`data-zone`、`is-buildable`，也沒有任何外圈。

| ID | Pytest | 結果 | 實際對預期 |
|----|--------|------|------------|
| TC-FE-EXPAND-RING-01 | `test_expand_ring_buildable_8x8_stays_centered` | **FAIL** | 格子數 64，要 100。外圈 36 格全缺（例：`(-1,-1)`、`(0,-1)`）。64 格內圈沒有 `data-col`／`data-row`（例：class `pad is-quiet`，`--c=0`，`--r=0`），沒有 `data-zone="buildable"`，沒有 class `is-buildable`。沒有「內圈缺格」這一行，所以正中 8×8 已經畫了。 |
| TC-FE-EXPAND-RING-02 | `test_expand_ring_locked_styling_and_labels` | **FAIL** | `#townMap` 看不到「可建區域（8×8）」和「可擴建（未解鎖）」。沒有鎖住的格子可查樣式（0/36）。 |
| TC-FE-EXPAND-RING-03 | `test_expand_ring_locked_click_toast_does_not_select` | **FAIL** | 場景 1 點可建「第 1 欄第 1 行」已經通過：提示是「想在這裏興建？請先按「我要起屋」。」，而且沒有選中。接著要點 `data-col=-1`、`data-row=-1` 的鎖住按鈕，找到 0 個。鎖住那句提示與 Enter 的斷言還沒跑到，因為按鈕不存在。 |
| TC-FE-EXPAND-RING-04 | `test_expand_ring_locked_not_placeable_keeps_selection` | **FAIL** | 已經進入場景 2（有金色 `is-empty-hot`）。外圈 `data-zone="locked"` 仍是 0/36。選中保留、不進場景 3、不 POST 的斷言還沒跑到。 |

沒有 API 案例。產品沒有擴建解鎖這個概念；本輪不測解鎖，也不重測足跡相鄰。
