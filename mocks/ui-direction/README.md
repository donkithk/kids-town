# 視覺方向熱點稿

這三頁是對住已核准概念圖的互動熱點稿，不是另一套重畫的介面。

畫面本體是 `docs/ui-direction/` 的三張圖。HTML 只在圖上的按鈕位置放透明熱點：領取、查看任務、底部導覽、攻擊、技能、蓋章領獎。點下去會改狀態、出提示，或把按鈕停用。

從專案根目錄：

```bash
python -m http.server 8765
```

打開 http://127.0.0.1:8765/mocks/ui-direction/00-index.html

Hotspot mock keyed to the approved art in `docs/ui-direction/`. The PNGs are the visuals. Buttons are transparent hit targets on the designed controls.
