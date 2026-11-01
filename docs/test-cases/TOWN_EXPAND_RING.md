# 城鎮可擴建外圈（紅測）

只加測試與本說明。不改遊戲畫面、不改後端、不改 `kids_town.db`。

設計稿是 PR #72，tip `52a5bb06297725045774378427184204d8054823`，檔案 `docs/ui-mocks/town-expandable.html`（說明在同一次提交的 `docs/ui-mocks/town-expandable.md`）。稿仍是靜態頁。本輪要鎖的是**登入後的產品城鎮** `#townMap`，不是把那張靜態稿打開來測。

篩選：

```bash
python -m pytest tests/test_town_expand_ring_e2e.py -q --tb=line
```

臨時資料庫，合成小朋友 `test_expand_kid` / `Expand Kid`，PIN 用 `tests/factories.py` 的 `TEST_KID_PIN`。沒有預放建築。視窗 1280×720。登入走產品表單「進入小鎮」（`#loginUsername`、`#loginPassword`）。禁止讀寫追蹤中的 `kids_town.db`。

結果見 [`TOWN_EXPAND_RING_STATUS.md`](TOWN_EXPAND_RING_STATUS.md)。

## 本輪鎖什麼

1. 可建造的地圖仍是正中 **8×8**（欄 0..7 × 行 0..7）。不把可玩範圍放大。
2. 外圍剛好 **一圈** 鎖住的「可擴建」格子：看得到，樣式是鎖住的，但不能選、不能放建築。
3. 點鎖住的格子，`#toast` 的文字正好是「此格尚未解鎖，暫時不能建造。」而且該格沒有被選中。
4. 沒有解鎖、沒有擴建經濟、沒有更大的可建造格子。本輪不測解鎖流程。
5. 建築足跡與邊緣相鄰（#71）不在本輪。不要為了這四條去改重疊或 `(7,*)` 的斷言。

畫面上的句子用書面語。案例 ID 用英文。

## 格子

跟設計稿同一套座標，畫在產品已有的 `#townMap .village.is-iso` 上。

| | 數量 | `data-col` / `data-row` | 標記 |
|--|------|-------------------------|------|
| 可建 | 64 | 0..7 × 0..7，每格一次 | `data-zone="buildable"`，class 含 `is-buildable` |
| 鎖住的外圈 | 36 | −1..8 之中、不在 0..7 的每一格 | `data-zone="locked"`，class 含 `is-locked` |
| 合計 | 100 | 沒有 −1 以外，也沒有 8 以外 | 沒有第二圈 |

`--c` / `--r` 必須等於 `data-col` / `data-row`，沿用現在的等角公式，外圈才會包住中間，而不是疊在同一點。四邊都要比內圈更外：北、南看 `offsetTop`，東、西看 `offsetLeft`。

可建格保留現在的場景 class（`is-quiet`、`is-empty`、`is-empty-hot`、`is-chosen`、`is-preview`、`is-valid`、`is-illegal`），在其上再加 `is-buildable`。`renderCell` 現在會整段換掉 `className`，實作時要把這兩個 zone class 留住。

可建格的 aria-label **維持四場景現有句子**（「第 N 欄第 M 行…」）。不要改成設計稿靜態頁的「可建空地（欄 N，行 M）」或「已選取可建空地…」。那兩句只屬於靜態稿的點選示範。

鎖住的格子：

- aria-label 正好是「未解鎖格子（欄 N，行 M）」。N、M 是 `data-col + 1`、`data-row + 1`，所以外圈會讀成 0 或 9。括號是全形，數字兩側有空格，與稿的 `labelFor` 相同。
- `aria-disabled="true"`，`tabIndex` 為 −1，滑鼠指標是 `not-allowed`。
- 沒有 `aria-pressed="true"`。
- 沒有可建場景 class，也沒有看得見的金色 `.mark`。
- 地塊圖是 `ground-tile.svg`（可建格仍是 `ground-plot.svg`）。
- `.slab` 的 filter 同時含 `grayscale`、`brightness`、`saturate`（稿是 `grayscale(0.78) brightness(0.74) saturate(0.28)`）。
- 看得見 `.shade`（斜線）和 `svg.lock-icon`。
- 格子有實際寬高，不是 `display:none`。

`#townMap` 裡要看得見這兩句，一字不差：

- 可建區域（8×8）
- 可擴建（未解鎖）

不要把稿上的「靜態設計稿」做進產品。圖例可以沿用稿的 `#legend`，測試只要求這兩句在 `#townMap` 裡可見。

## 點選

`#townMap` 的 click 監聽在捕獲階段呼叫 `cellAt`。`town-four-scene.js` 的 `cellAt` 在座標超出 0..7 時回傳 null，然後直接 return，按鈕自己沒有監聽。所以只把格子畫出來、不改這條命中路徑，滑鼠點外圈不會出提示。鍵盤啟動（`detail === 0`）會讀 `--c` / `--r` 再進 `onCell`；負座標現在會走到場景 1 的「想在這裏興建？請先按「我要起屋」。」那不是本輪要的句子。

鎖住的格子被點到（滑鼠點在按鈕中心，以及聚焦後按 Enter）時：

- `#toast` 可見，文字正好是「此格尚未解鎖，暫時不能建造。」前後沒有別的字。
- 該格沒有 `is-chosen`。
- 場景 1：本來沒有選中；點完仍然沒有。`#actionSheet` 不開。
- 場景 2：若已經選了可建格（本案例先選欄 1 行 1，資料座標 `(0,0)`），點外圈之後選中仍是那一格，不改成鎖住的格子，也不進入場景 3（`#uxPlaceBar` 保持收起）。
- 不為這一下 POST `/buildings`，不新增 `buildings` 列，金幣與材料不變。
- `#placementBar` 不加 `active`。

場景 1 點可建空地，提示仍是現有的「想在這裏興建？請先按「我要起屋」。」不要改成鎖住那句。

場景 2 的金色格（`is-empty-hot` / `is-chosen`）不得落在外圈或 0..7 之外。哪些內圈原點算合法，本輪不重新斷言（足跡相鄰是 #71）。

## 不做的事

- 不測解鎖條件、價錢、按鈕把 10×10 變成可建造。
- 不新增擴建 API 的案例。產品目前沒有 expand-lock 這個領域概念；`TOWN_PLACE_COLS` / `ROWS` 維持 8。
- 不改焦點環（`#focusRingPaint`、`ringBtn` 是另一件事）。
- 不要求產品照抄稿的 `--s: 0.48`。外圈可以縮小或放在現有的直向捲動裡，但每一格都要畫出來，而且點得到。

## 案例

| ID | 行為 |
|----|------|
| TC-FE-EXPAND-RING-01 | 場景 1。64 格可建在正中，36 格外圈鎖住，座標與 class / `data-zone` 如上。外圈在四邊都伸出可建區。沒有第二圈。 |
| TC-FE-EXPAND-RING-02 | 36 格都是鎖住的外觀與「未解鎖格子」名稱。圖例兩句可見。可建格不被刷成鎖住的地塊。 |
| TC-FE-EXPAND-RING-03 | 場景 1。可建 `(0,0)` 仍是舊提示。外圈六點（四角與四邊的樣本）滑鼠點擊，以及其中一格的 Enter，都是鎖住那句，而且不選中、不開面板、不扣資源、不 POST。 |
| TC-FE-EXPAND-RING-04 | 場景 2。金色格不落在外圈。先選可建 `(0,0)`，再點 `(-1,0)` 與 `(8,7)`：提示是鎖住那句，選中不變，不進場景 3，不 POST，資源與行數不變。 |

樣本座標：`(-1,-1)`、`(-1,3)`、`(3,-1)`、`(8,4)`、`(4,8)`、`(8,8)`。04 另點緊貼西、東南的 `(-1,0)` 與 `(8,7)`。

## 給建造者

要綠，改的是登入後的四場景城鎮，不是靜態稿。

- 在現有 `buildGrid` / `renderCell` 加上這一圈，不要把 `COLS` / `ROWS` 改成 10。
- 滑鼠與鍵盤兩條都要認 `data-zone="locked"`，並且在呼叫一般 `onCell` 之前停下。
- 可建 8×8 的放置、金色格、場景 1 的空地提示維持現狀。
- 不要做解鎖。外圈這一輪一直鎖著。
