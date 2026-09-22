# 視覺方向熱點稿

畫面就是已核准的概念圖。圖檔放在這個資料夾的 `art/`，HTML 用 `./art/...png` 引用，所以只打開 `mocks/ui-direction/` 都睇到圖。按鈕是透明熱點，疊在領取、攻擊、蓋章同導覽上面。沒有另一套重畫的介面。

## 點樣打開

在 `mocks/ui-direction/` 裡面：

```bash
cd mocks/ui-direction
python -m http.server 8765
```

然後打開：

- http://127.0.0.1:8765/00-index.html
- http://127.0.0.1:8765/01-guild-quest-board.html
- http://127.0.0.1:8765/02-wilderness-adventure.html
- http://127.0.0.1:8765/03-honour-reward.html

也可以直接用瀏覽器打開 `01-guild-quest-board.html`（`file://` 可以，圖在旁邊的 `art/`）。

Art files live in `art/` next to these pages (`./art/01-guild-quest-board.png`, `02-wilderness-adventure.png`, `03-honour-reward.png`). They are copies of the approved concept art. Hotspots only; no separate painted UI.
