# 雙重驗證 (B) — 真機／人手清單

> 自動化 (A) 綠 **唔等於** 體驗完成。Cloud agent Linux Chromium 可以跑 Playwright；**真機手機／家長平板** 仍要人手簽收。  
> **禁止** 用 `index.html` grep／AST 當齊儀式 UX 或放置 UX。  
> Fixture：空庫 + 合成帳戶（`test_fe_*`／PIN `1357`／家長 `TestParent!pass1`）。**禁止** copy `kids_town.db`、禁止用真實 PIN。

簽收格式見 [`docs/TDD_PROCESS.md`](../TDD_PROCESS.md) §5。

```
DOUBLE-CHECK (B)
- 跑手：<名>
- 日期：YYYY-MM-DD
- 環境：本機 Flask / 空庫 seed / 裝置 <型號+瀏覽器>
- 清單：本檔 + PHASE1 人手項
- 結果：PASS / FAIL（失敗列 Case ID）
```

---

## 體驗 C — 任務完成儀式（金幣 + XP + 材料）

對應：**TC-FE-CEREMONY-01**（真實 E2E）、**P1-TC-CER-FE-01**（mock／弱 source）。

前置：家長指派一條 ≥10 分任務俾合成小朋友；小朋友 PIN 登入。

| # | 步驟 | 預期 | (A) 已覆蓋？ |
|---|------|------|----------------|
| B-CER-01 | 任務 tab 撳「✅ 完成」 | 見到「任務完成」 | 部分（JOURNEY-01 / CEREMONY-01） |
| B-CER-02 | 望 toast **同** 頂欄 HUD | **金幣**（🪙 或 `#hudCo` 上升） | CEREMONY-01 |
| B-CER-03 | 同一下完成 | **XP 數字**可見（例如 `⭐XP+5`），唔可以淨係 XP 條、亦唔可以金幣-only | CEREMONY-01 讀 toast text；**真機要睇有冇被 `nowrap` 裁走** |
| B-CER-04 | 同一下完成 | **材料提示**：🪵／木材／wood 或 🧱／磚 等；或 HUD 四格對應數字 +1 | CEREMONY-01；真機確認 emoji／字未被裁 |
| B-CER-05 | （可選）已起圖書館 | toast 有「圖書館 +N」 | **未**自動化；PHASE1 人手項 |
| B-CER-06 | 細屏（≤390px 寬）望 toast | 金幣、XP、材料三樣都睇得清，唔好只見「獲得 🪙10…」 | **必須人手** — Playwright 讀 `textContent` 睇唔到視覺裁切 |

若 B-CER-03／04 失敗：當產品缺口交 KT builder，**唔好**放寬 `TC-FE-CEREMONY-01` 斷言去假綠。

---

## 體驗 C — 商店／建築 tab 雙路徑放置

對應：**TC-FE-PLACE-SHOP-01**、**TC-FE-PLACE-BUILD-01**、弱 source **P1-TC-PLC-FE-01**。

前置：金幣／材料夠起圖書館同健身室（或任何未擁有、無區鎖嘅建築）。

| # | 步驟 | 預期 | (A) 已覆蓋？ |
|---|------|------|----------------|
| B-PLC-01 | 背包 → 建築商店 → 圖書館「建造」 | 進入放置態（紫／藍 bar「點擊地圖上綠色區域」）；地圖有綠色 2×2 高亮 | PLACE-SHOP-01 |
| B-PLC-02 | 撳一塊綠色空地 → 「確認建造」 | 地圖出現該建築（圖／名）；金幣扣咗 | PLACE-SHOP-01 |
| B-PLC-03 | ☰ → 建築管理 → 另一座（例如健身室）「建造」 | **同樣**進入 `startPlacement`（唔只 toast「點擊下方空地」） | PLACE-BUILD-01 |
| B-PLC-04 | 若畫面仲喺建築列表 | 小朋友要返到小鎮地圖先見到綠格。確認呢步係咪直觀（產品而家 **唔**自動切地圖；商店會） | E2E 會跟住開「小鎮地圖」；**真機 UX 必須人手** |
| B-PLC-05 | 綠格 → 確認 | 第二座建築出現喺另一格 | PLACE-BUILD-01 |
| B-PLC-06 | 真機手指（唔係 mouse）點綠格 | 選中高亮 + 確認掣出嚟；無點唔中／點到裝飾 modal | **必須人手** |

`.empty-cell`（1×1 裝飾格）喺放置態 **唔會**起屋；要點 `.valid-plot` 綠色 2×2。人手清單請寫「撳綠色範圍」而唔係「撳任意空格」。自動化要用 `force` click，因為產品疊咗好多層 2×2 熱區（Playwright 會話 intercepts pointer events）；真機手指會點到最上層。

---

## Phase 1 其餘人手項（本 PR 無加強自動化）

抄錄自 [`PHASE1_GAMEPLAY.md`](PHASE1_GAMEPLAY.md)，方便一次簽收：

- [ ] 起圖書館 → 再做任務，儀式見到「圖書館 +2」（或當前等級值）
- [ ] 農場領金幣 → 再撳被拒 → 改日先至再領
- [ ] 起商店後下一座建築金幣較平，材料數不變
- [ ] 探險回來 HUD 四格係木頭／磚／玻璃／齒輪，背包無孤立「鐵」
- [ ] 區 4 掣顯示尚未開放，戰鬥唔彈技術 404
- [ ] 無公會時探險／戰鬥有人話
- [ ] 短征費用標「費用 🪙10」
- [ ] 同一區探索可第二次出發
- [ ] XP 條：升 1 級過程由空→滿
- [ ] 15 分鐘劇本（企劃 §8）至少內部走一次

---

## 本 PR 唔當完成嘅事

| 項目 | 點解 |
|------|------|
| P1-TC-CER-03 | Phase 2 `require_approval`；**保持紅**，禁止 skip |
| grep `completeTask` / `startPlacement` | 弱契約；唔可以標「(A) 完成」 |
| 產品修正 toast 裁字、建築 tab 自動切地圖 | 體驗 C 呢單係 **測試／文件**；產品修另 PR |
