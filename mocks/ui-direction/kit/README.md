# Kids Town Asset Kit v1 — 可拆層資源盤點

> **方法變更**：已否決「整張概念圖 + hotspot 覆蓋」。改採 **可拆層資源（decomposable layered assets）**：背景、UI 元件、戰鬥精靈分開產出，執行期再疊加。
>
> **風格**：溫暖木質 / cottagecore RPG UI + 手繪場景畫。  
> **舞台**：橫向 1280×720。  
> **產品 UI 文案**：繁體中文；**檔名 id**：英文 kebab-case OK。

本套件僅為設計／產圖規格，**不**改動 production `index.html`，**不**開 PR。產生的圖可之後複製進 repo 的 `mocks/asset-kit/`（見下方目錄提案）。

---

## 快速目錄

| 路徑 | 內容 |
|------|------|
| [`ASSETS.md`](./ASSETS.md) | 背景／UI／精靈完整規格（尺寸、安全區、tokens） |
| [`GENERATE_PROMPTS.md`](./GENERATE_PROMPTS.md) | 可直接貼上的英文產圖 prompt |
| `bg/` | 背景層佔位（1280×720，無角色／無文字） |
| `ui/` | UI 元件佔位（PNG/SVG 友善） |
| `sprites/` | 戰鬥精靈佔位（透明底） |

---

## 1. 背景層（Background layers）

**共通規則**

- 尺寸：**1280×720**（16:9 landscape）
- **禁止**：角色剪影、畫死的 UI chrome、假名字、任務標題、按鈕、徽章文字
- **保留**：暖光、木紋／草地／天空氛圍；中央與底部留給 live UI

| File id | 繁中說明 | 必須留空 | Live UI 安全區 |
|---------|----------|----------|----------------|
| `bg-guild-quest-room` | 溫暖木質公會任務室／任務板牆面 | 任務卡位置、角色站位、文字牌 | 中央 70% 任務卡區；底部 ~96px tab bar；右上 HUD |
| `bg-honour-ceremony` | 頒獎亭／村莊典禮背板 | 證書面板中央、角色、假名 | 中央證書區；左右裝飾可濃；底部 tab；頂部標題條 |
| `bg-wilderness-grass` | 晴朗草地／小徑／天空（戰鬥用） | 角色／怪物站位、血條、技能 UI | 左下英雄站位、右下敵方；中下行動列；頂部 HP／狀態 |

詳見 [`ASSETS.md` §背景](./ASSETS.md#1-背景層-background-layers)。

---

## 2. UI 元件規格（CSS-friendly）

**Design tokens（與 guild mock 對齊）**

| Token | Hex | 用途 |
|-------|-----|------|
| `--wood` | `#8b5e3c` | 主木色 |
| `--wood-mid` | `#a67c52` | 中木／tab |
| `--wood-deep` | `#5c3d28` | 深陰影／文字強調 |
| `--wood-plank` | `#c4a06a` | 淺木紋 |
| `--cream` | `#faf6ef` | 卡片底 |
| `--paper` | `#fff8e7` | 羊皮紙高光 |
| `--paper-aged` | `#f3e6c8` | 舊紙 |
| `--ink` | `#3b2a1a` | 正文 |
| `--gold` | `#d4a017` | 領取／金幣 |
| `--gold-bright` | `#f0c14b` | 金幣高光 |
| `--pending` | `#e8a317` | 待確認 |
| `--honour` | `#9b2c2c` | 已頒獎印 |
| `--focus` | `#c45c26` | `:focus-visible` outline |
| 點擊最小 | **44×44px** | 觸控 hit area |

**元件清單**

| id | 說明 | 約略尺寸（landscape） | radius |
|----|------|----------------------|--------|
| `ui-quest-card` | 圓角任務卡（奶油羊皮紙貼木板） | 寬 ~560–640；高依內容 ~120–160 | 12–16px 卡；外木框 8–10px |
| `ui-tab-bar` | 木紋底 tab bar（5 項） | 全寬 × ~72–88px | 頂 16–20px |
| `ui-btn-claim` | 金色「領取」按鈕 | min 120×48（hit ≥44） | 999px 或 12px |
| `ui-badge-pending` | 「待確認」徽章 | ~88×28 | 999px |
| `ui-badge-awarded` | 「已頒獎」徽章 | ~88×28 | 999px |
| `ui-hud-chip-gold` | HUD 金幣 chip | ~96×36 | 999px |
| `ui-hud-chip-exp` | HUD EXP chip | ~96×36 | 999px |
| `ui-honour-panel` | 榮譽印章／證書面板 | ~480×360 | 16–24px |

詳見 [`ASSETS.md` §UI](./ASSETS.md#2-ui-元件規格)。

---

## 3. 戰鬥精靈（Battle sprites）

透明 PNG、物件分離、可疊在 `bg-wilderness-grass` 上。

| File id | 說明 | 建議像素 | 朝向 |
|---------|------|----------|------|
| `sprite-hero` | 小孩冒險者（需 front + side 變體） | 約 256×256（裁切後可縮） | front：面向鏡頭；side：面向右（敵方在右） |
| `sprite-boar` | 草原野豬 | 約 288×224 | 面向左（朝向英雄） |
| `sprite-generic-monster` | 未來通用怪物槽（可選） | 約 256×256 | 面向左 |

詳見 [`ASSETS.md` §精靈](./ASSETS.md#3-戰鬥精靈-battle-sprites)。

---

## 4. 產圖 Prompt

每個藝術資產的英文 ready-to-paste prompt 見 [`GENERATE_PROMPTS.md`](./GENERATE_PROMPTS.md)。  
共通約束：cottagecore / warm wood / hand-drawn illustration；**畫面內無文字**；背景 1280×720；精靈透明底。

---

## 5. Repo 目錄提案

建議落入 Kids Town repo：

```text
mocks/asset-kit/          # 或 mocks/ui-assets/
  README.md               # 可自本套件同步
  ASSETS.md
  GENERATE_PROMPTS.md
  bg/
    bg-guild-quest-room.png
    bg-honour-ceremony.png
    bg-wilderness-grass.png
  ui/
    ui-quest-card.png|svg
    ui-tab-bar.png|svg
    ui-btn-claim.png|svg
    ui-badge-pending.png|svg
    ui-badge-awarded.png|svg
    ui-hud-chip-gold.png|svg
    ui-hud-chip-exp.png|svg
    ui-honour-panel.png|svg
  sprites/
    sprite-hero-front.png
    sprite-hero-side.png
    sprite-boar.png
    sprite-generic-monster.png   # optional
```

本工作區鏡像結構：

```text
/workspace/kids-town-asset-kit-v1/
  README.md
  ASSETS.md
  GENERATE_PROMPTS.md
  bg/  ui/  sprites/
```

---

## 資產計數（規格層）

| 類別 | 數量 | 備註 |
|------|------|------|
| 背景 | **3** | 皆 1280×720 |
| UI 元件 | **8** | CSS/SVG 優先，PNG 可作紋理 |
| 戰鬥精靈 | **3–4** | hero 建議 2 朝向變體 → 檔案可到 5 |
| **合計產圖目標** | **約 14–16 檔** | 含 hero front/side；generic-monster 可選 |

---

## 不做／不做的事

- ❌ 不開 GitHub PR  
- ❌ 不修改 production `index.html`  
- ❌ 不把任務名、小孩名、按鈕字畫進背景  
- ✅ 只寫規格與 prompt；實際位圖可後續依 prompt 產出放入 `bg/` `ui/` `sprites/`
