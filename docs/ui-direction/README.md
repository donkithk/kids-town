# Kids Town 視覺方向 / Visual Direction

**狀態：畫面方向使用者已核准（2026-09-22）。美術風格指南、色票與城鎮鎖定首批提示詞另於 2026-11-02 鎖定（合啦）。**
**Status: screen direction user-approved (2026-09-22). Art style guide, palette, and town-lock first-batch prompts locked 2026-11-02 (合啦).**

這裡有已核准的概念圖，以及 2026-11-02 鎖定的美術方向。都不是已上線的介面，也不改遊戲邏輯。
Approved concept art lives here, plus the art direction locked on 2026-11-02. These are not shipped screens, and they do not change gameplay.

## 鎖定的三個畫面 / Locked screens（2026-09-22）

2026-09-22 的畫面方向仍然有效。下面三張核准概念圖保留，不因 2026-11-02 的風格鎖定而取代。

The 2026-09-22 visual direction remains. These three approved concept images stay; the 2026-11-02 art lock does not replace them.

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

## 美術風格鎖定 / Art style lock（2026-11-02）

使用者於 2026-11-02 確認（合啦）：風格指南、色票，以及城鎮鎖定首批提示詞 **A–C**。怪物重繪**延後**——英雄是粗線 chibi，狼偏寫實軟邊，風格不一致，先不出貨，本批提示詞不含怪物。

Locked 2026-11-02 (合啦): style guide, palette, and town-lock first-batch prompts **A–C**. **Monsters are deferred** — the hero is bold-outline chibi and the wolf is softer and more realist, so the mismatch does not ship. This batch has no monster prompts.

| 檔案 | 用途 |
| --- | --- |
| [`style-guide.md`](style-guide.md) | 風格指南（LOCKED 2026-11-02）：手繪暖木、奶油紙卡、等角城鎮 |
| [`palette.md`](palette.md) | 鎖定色票與 CSS `:root`；禁止自創 hex |
| [`palette-swatch.png`](palette-swatch.png) | 色票色卡 |
| [`prompt-sheets/2026-11-02-first-batch.md`](prompt-sheets/2026-11-02-first-batch.md) | 首批提示詞 A 木框、B 空廣場／草地、C 探險公會精靈 |
| [`shot-list.md`](shot-list.md) | 城鎮鎖定鏡頭清單；標出延後的怪物與不在本批的項目 |

提示詞只寫用詞，像素由圖像工具產出。圖內零文字；書面語中文由 DOM 承擔。
The prompt sheet is wording only. Pixels come from the image tool. No text in images; Traditional Chinese copy stays in the DOM.

## 色盤提示 / Palette cues

口語色感仍是下面四點。精確用色以 [`palette.md`](palette.md) 的鎖定 token 為準，不要另造 hex。

The spoken color feel is still the four cues below. Exact colors follow the locked tokens in [`palette.md`](palette.md).

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

2026-09-22 的畫面方向與 2026-11-02 的美術鎖定都只放在本資料夾。合併只加入設計文件與概念圖，可安全合併：不動 `index.html`、`backend_v2.py`，也不動玩法。
The 2026-09-22 screen direction and the 2026-11-02 art lock both live in this folder. Merge adds design docs and concept art only. It does not touch `index.html`, `backend_v2.py`, or gameplay.

合併之後，若要照方向做真正的 UI 或產出 A–C 像素，是下一步的可選工作，不在本次範圍。怪物重繪仍延後。
After merge, building the real UI from this direction, or generating A–C pixels, is an optional next step, not part of this change. Monster reskin stays deferred.
