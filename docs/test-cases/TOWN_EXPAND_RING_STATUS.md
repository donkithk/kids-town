# 可擴建外圈 — 狀態

獨立回歸（本檔更新）。產品仍是 PR #74，測試檔沒有改弱。下面先記這次對綠 tip 的結果，紅測基線留在文末。

## 獨立回歸 #74 — PASS，先不要合併

對 PR #74 tip 重跑紅測四條，並另外抽查契約裡測試只抽樣的格子。沒有退回建造者的失敗清單。合併仍等人眼 Preview：村莊為了放進外圈，縮放比以前小。

| 項目 | 值 |
|------|----|
| 受測 tip | `c1aa5a96f94ce800514b7df1d5d77fe20f87c750`（`c1aa5a96`，分支 `cursor/town-expand-ring-product-1016`，PR #74 head，本次未再移動） |
| 紅測契約 | PR #73 tip `ef7be1573b9448055765192bb714eaad0ba66527` |
| 設計稿 | PR #72 tip `52a5bb06297725045774378427184204d8054823` |
| 命令 | `python3 -m pytest tests/test_town_expand_ring_e2e.py -q --tb=short` |
| 環境 | Python 3.12.3，pytest 9.1.1，Playwright Chromium，Linux |
| 結果 | **4 passed，0 failed**，4.82s。接著 `-v` 再跑一次仍是 4 passed（4.12s），節點名帶 `[chromium]` |
| 產品差異（相對 #73） | 只有 `town-four-scene.js`、`town-four-scene.css`（+256 / −5）。測試、後端、`index.html`、`kids_town.db` 都沒有進這次 diff |
| 資料庫 | 追蹤中的 `kids_town.db` sha256 跑前、官方測試後、抽查後都是 `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`。只用臨時庫與 `test_expand_kid`。 |

| ID | Pytest | 結果 | 獨立核對 |
|----|--------|------|----------|
| TC-FE-EXPAND-RING-01 | `test_expand_ring_buildable_8x8_stays_centered` | **PASS** | 100 格。可建 64 格在 `data-col`／`data-row` 0..7，`data-zone="buildable"`，class 含 `is-buildable`。鎖住 36 格在 −1..8 的外圈，沒有第二圈，也沒有框外格。每一格 `--c`／`--r` 等於 data 座標。`COLS`／`ROWS` 仍是 8。 |
| TC-FE-EXPAND-RING-02 | `test_expand_ring_locked_styling_and_labels` | **PASS** | `#townMap` 看得到「可建區域（8×8）」和「可擴建（未解鎖）」。沒有稿上的「靜態設計稿」。36 格 aria-label 都是「未解鎖格子（欄 N，行 M）」。 |
| TC-FE-EXPAND-RING-03 | `test_expand_ring_locked_click_toast_does_not_select` | **PASS** | 官方測試的六個樣本與 Enter 通過。抽查再點全部 36 格按鈕中心：`#toast` 可見且正好是「此格尚未解鎖，暫時不能建造。」（全形逗號 U+FF0C、句號 U+3002）。場景 1 結束時沒有 `is-chosen`。可建 `(0,0)` 仍是「想在這裏興建？請先按「我要起屋」。」 |
| TC-FE-EXPAND-RING-04 | `test_expand_ring_locked_not_placeable_keeps_selection` | **PASS** | 官方測試先選可建 `(0,0)`，再點 `(-1,0)` 與 `(8,7)` 通過。抽查在場景 2 對全部 36 格再點一次：選中仍是那一格，`aria-label` 維持「場景 2」，`#uxPlaceBar` 收起。沒有 `POST /buildings`。 |

假綠檢查：沒有抓到契約失敗。官方 03／04 只抽樣外圈，所以另外把 36 格都點過（場景 1 與場景 2）。鎖頭圖示中心在 `(-1,-1)` 疊在 `.cell-btn` 上，點下去也是同一句。`cellAt` 仍拒絕 0..7 以外，後端 `TOWN_PLACE_COLS` 仍是 8，這次 diff 沒有解鎖 API，抽查期間沒有 expand／unlock 請求。點可建 `(7,7)` 打中的是 `data-zone="buildable"`，走出的是原有「這個位置放不下這座建築物。」，不是鎖住那句；選中留在 `(0,0)`。足跡相鄰的函式沒有改。

給 Preview 的畫面：`fitExpandRing` 把 `#townMap .village.is-iso` 的 `--s` 從固定 `0.85` 收到約 `0.3868`（`--origin-y` 約 `23.34px`）。紅測允許外圈縮小。可建區仍是 8×8，不是可玩的 10×10。人眼要看縮小後的小鎮還能不能用。

建議：四條可以當真。不要為了這份報告合併。等 Preview 和使用者看過縮小後的城鎮再決定 #74。

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
