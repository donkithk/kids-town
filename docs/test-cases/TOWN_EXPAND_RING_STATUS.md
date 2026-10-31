# 可擴建外圈 — 狀態

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
