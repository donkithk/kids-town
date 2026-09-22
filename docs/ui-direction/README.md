# Kids Town 視覺方向 / Visual Direction

**狀態：使用者已核准（2026-09-22）。本資料夾鎖定畫面方向，供之後實作參考。**
**Status: user-approved (2026-09-22). This folder locks the visual direction for later implementation.**

這裡只有概念圖與方向說明，不是已上線的介面，也不改遊戲邏輯。
Concept art and direction notes only. These are not shipped screens, and they do not change gameplay.

## 鎖定的三個畫面 / Locked screens

| 檔案 | 用途 | 感覺 |
| --- | --- | --- |
| [`01-guild-quest-board.png`](01-guild-quest-board.png) | 每日任務／公會任務板 | 溫暖木屋大廳、奶油紙任務列、金色領取鈕 |
| [`02-wilderness-adventure.png`](02-wilderness-adventure.png) | 探索與戰鬥 | 戶外日光草原，明亮、開闊 |
| [`03-honour-reward.png`](03-honour-reward.png) | 獎勵與家長蓋章核准 | 榮譽儀式、獎章與證書的肯定時刻 |

1. **公會每日任務板。** 每日任務用溫暖的公會木質任務板，不要糖果粉彩，也不要深夜 HUD。
   **Guild daily quest board.** Daily tasks use a warm wooden guild board. Not candy pastel. Not a dark night HUD.
2. **戶外日光荒野。** 探索與戰鬥發生在白天的明亮草地，天空、花田、遠山都看得到。
   **Outdoor daylight wilderness.** Exploration and combat stay in bright daytime meadow light.
3. **榮譽儀式。** 領獎與家長蓋章要有典禮感：獎章、證書、金色肯定，而不是冷的後台清單。
   **Honour ceremony.** Rewards and parent stamp approval should feel like a ceremony: medal, certificate, gold recognition.

概念圖裡的數字、文案與按鈕是氣氛參考。產品文案維持現有繁體中文；榮譽圖上的英文是情緒示意。
Numbers, labels, and buttons in the art are mood references. Product copy stays Traditional Chinese; English on the honour image is mood only.

## 色盤提示 / Palette cues

- 暖木色 warm wood（框架、大廳、木牌）
- 奶油紙色 cream paper（任務列、證書）
- 金色點綴 gold accents（標題、領取、獎章）
- 明亮日光 bright daylight（探索與戰鬥；室內任務板則是暖燈，不是夜色）

## 這不是方向 / Explicitly not the direction

以下提早草案**不是**視覺方向，實作時不要沿用：

- **糖果粉彩 mock：[PR #17](https://github.com/donkithk/kids-town/pull/17)**（`cursor/ui-refresh-playful-mocks-0f41`，candy pastel／貼紙卡／confetti）。過早，不採用。
- **暗色 RPG CSS 草稿：** 倉庫內 `mocks/dq_mock.html` 與 `mocks/dq_mock_v2.html` … `mocks/dq_mock_v11.html`。深藍夜色戰鬥 HUD，不採用。

These are superseded and are non-direction:

- Premature candy-pastel mock [PR #17](https://github.com/donkithk/kids-town/pull/17).
- Dark RPG CSS drafts under `mocks/dq_mock*.html` (night-blue combat HUD).

## 實作邊界 / Implementation boundary

合併本 PR 只加入設計資產，可安全合併：不動 `index.html`、`backend_v2.py`，也不動玩法。
This PR is design assets only and is safe to merge. It does not touch `index.html`, `backend_v2.py`, or gameplay.

合併之後，若要照這三張方向做真正的 UI，是下一步的可選工作，不在本次範圍。
After merge, building the real UI from this direction is an optional next step, not part of this change.
