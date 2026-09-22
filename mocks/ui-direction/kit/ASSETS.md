# ASSETS.md — Kids Town 可拆層資產規格

產品 UI 標籤用**繁體中文**；檔名／id 用**英文**。風格：warm wood cozy / cottagecore RPG UI + hand-drawn scene art。舞台：**1280×720** landscape。

---

## 0. 全域約束

| 項目 | 規格 |
|------|------|
| Stage | 1280×720，CSS `object-fit: cover` 於 stage 容器 |
| 文字 | 圖像內 **零文字**（含英文）；文案由 DOM／CSS 疊加 |
| 角色 | 背景層 **無角色**；角色僅在 `sprites/` |
| 觸控 | 可點元件 hit area ≥ **44×44px** |
| Focus | `:focus-visible { outline: 3px solid #c45c26; outline-offset: 2px; }` |
| 匯出 | 背景 JPEG/PNG OK；UI 優先 SVG／9-slice PNG；精靈 **PNG + alpha** |

### Color tokens

```css
:root {
  --wood: #8b5e3c;
  --wood-mid: #a67c52;
  --wood-deep: #5c3d28;
  --wood-plank: #c4a06a;
  --cream: #faf6ef;
  --paper: #fff8e7;
  --paper-aged: #f3e6c8;
  --ink: #3b2a1a;
  --ink-soft: #5c4632;
  --muted: #7a6550;
  --gold: #d4a017;
  --gold-bright: #f0c14b;
  --sky: #87ceeb;
  --sky-soft: #c5e8f7;
  --grass: #7cb342;
  --pending: #e8a317;
  --pending-bg: #fff3d6;
  --honour: #9b2c2c;
  --honour-bg: #fff5e0;
  --focus: #c45c26;
}
```

---

## 1. 背景層（Background layers）

### `bg-guild-quest-room`

| 欄位 | 內容 |
|------|------|
| 檔名 | `bg/bg-guild-quest-room.png` |
| 尺寸 | **1280×720** |
| 繁中用途 | 孩子任務板／公會任務室底圖 |
| 畫面內容 | 溫暖木質公會廳：木地板、橫梁、牆上空白任務板／軟木板區、窗光、柔和燭光或午后陽光；cottagecore 手繪 |
| **必須留空** | 任務卡剪影、釘書針上的假任務標題、角色、NPC、「Quest」等任何文字、畫死的按鈕／tab／HUD |
| **安全區（建議）** | **中央卡片帶**：約 x=200–1080、y=120–560（放 2–4 張 live quest cards）；**底部**：y=624–720（wood tab bar ~72–96px）；**右上**：約 200×80（金幣／EXP chips）；**頂部**：y=0–72 可放標題條但勿畫字 |
| 色調 | wood `#8b5e3c` 家族 + cream 牆面高光；避免高對比霓虹 |

### `bg-honour-ceremony`

| 欄位 | 內容 |
|------|------|
| 檔名 | `bg/bg-honour-ceremony.png` |
| 尺寸 | **1280×720** |
| 繁中用途 | 家長頒獎／榮譽典禮背板 |
| 畫面內容 | 村莊頒獎亭或戶外典禮：木亭、花環、布幔、柔和旗幟（無字）、金光粒子可極淡；遠景小屋／樹 |
| **必須留空** | 中央證書／印章面板位置、假姓名、獎狀正文、角色、家長／孩子剪影、畫死的「已頒獎」章 |
| **安全區** | **中央面板**：約 480×360 置中（x≈400–880、y≈140–500）；左右可濃裝飾；**底部** tab 預留；**頂部** 標題條空白 |
| 色調 | 暖木 + 柔金 `#d4a017` 點綴 + cream 布幔 |

### `bg-wilderness-grass`

| 欄位 | 內容 |
|------|------|
| 檔名 | `bg/bg-wilderness-grass.png` |
| 尺寸 | **1280×720** |
| 繁中用途 | 戰鬥場景底圖（草原） |
| 畫面內容 | 晴朗草地、小徑、遠山或矮樹、藍天白雲；手繪 RPG 戰場；地面有清楚的左右站位暗示（草紋／土徑）但**不畫腳印角色** |
| **必須留空** | 英雄／野豬／怪物、血條、技能按鈕、傷害數字、任何 UI chrome |
| **安全區** | **左下英雄**：約 x=80–360、y=280–580；**右下敵方**：約 x=820–1180、y=260–560；**中下行動列**：y=600–700、全寬可點區；**頂部狀態**：y=16–80 |
| 色調 | grass `#7cb342`、sky `#87ceeb`、暖土徑 |

---

## 2. UI 元件規格

實作可純 CSS；下列規格供 PNG／SVG 紋理與對齊。所有可點元件 **min tap 44px**；`:focus-visible` 用 `--focus` `#c45c26`。

### `ui-quest-card` — 圓角任務卡

| 欄位 | 規格 |
|------|------|
| 外觀 | 奶油羊皮紙貼在淺木板／軟木上；細縫線或膠帶角可選 |
| 約略尺寸 | 寬 **560–640px**；高 **120–160px**（內容可變） |
| Corner radius | 內紙 **12–16px**；外木框 **8–10px** |
| 填色 | 面 `--cream` / `--paper`；邊 `--wood-plank`；陰影 soft `--wood-deep` 12% |
| 預留 | 左上狀態徽章槽 ~100×32；右下 CTA 槽 ~140×48；標題／描述由 DOM |
| 檔名建議 | `ui/ui-quest-card.svg` 或 9-slice PNG |

### `ui-tab-bar` — 木紋底 5-tab

| 欄位 | 規格 |
|------|------|
| 項目數 | **5**（圖示 + 繁中 label 由 DOM：例如 任務／冒險／城鎮／背包／我的 — 實際文案產品定） |
| 尺寸 | 寬 **1280**（或 100%）；高 **72–88px** |
| Radius | 頂邊 **16–20px**；底貼齊舞台 |
| 填色 | wood-grain 漸層 `--wood-mid` → `--wood`；頂緣細亮線 `--wood-plank` |
| 單 tab hit | 寬 ≥ 最小 20% 寬、高 ≥ **44px** |
| Active | 略亮木色 + 頂部小金點或下劃線 `--gold` |
| 檔名 | `ui/ui-tab-bar.png`（紋理）+ CSS icons |

### `ui-btn-claim` — 金色「領取」

| 欄位 | 規格 |
|------|------|
| Label（產品） | **領取**（圖內無字；字用 DOM） |
| 尺寸 | 視覺 ≥ **120×48**；hit ≥ **44×44**（建議整鈕 48 高） |
| Radius | **12px** 或 pill **999px** |
| 填色 | 漸層 `--gold-bright` → `--gold`；文字 `--ink` 或近白 cream |
| 狀態 | hover 略亮；disabled 降飽和 40%；focus-visible `--focus` |
| 檔名 | `ui/ui-btn-claim.svg` |

### `ui-badge-pending` — 待確認

| 欄位 | 規格 |
|------|------|
| Label | **待確認** |
| 尺寸 | ~**88×28**（文字區）；外包 hit 若可點則撐到 44 高） |
| Radius | **999px** |
| 色 | 底 `--pending-bg`；字／邊 `--pending` |
| 檔名 | `ui/ui-badge-pending.svg` |

### `ui-badge-awarded` — 已頒獎

| 欄位 | 規格 |
|------|------|
| Label | **已頒獎** |
| 尺寸 | ~**88×28** |
| Radius | **999px** |
| 色 | 底 `--honour-bg`；字／邊 `--honour`；可選小印章紋理 |
| 檔名 | `ui/ui-badge-awarded.svg` |

### `ui-hud-chip-gold` / `ui-hud-chip-exp`

| 欄位 | 規格 |
|------|------|
| 尺寸 | ~**96×36**；hit 高 ≥ 44 時可加大 padding |
| Radius | **999px** |
| Gold chip | 左金幣圖示（無字圖）+ DOM 數字；邊 `--gold`；底 cream |
| EXP chip | 左星／葉圖示 + DOM 數字；邊 `--wood`；底 `--paper-aged` |
| 檔名 | `ui/ui-hud-chip-gold.svg`、`ui/ui-hud-chip-exp.svg` |

### `ui-honour-panel` — 榮譽印章／證書面板

| 欄位 | 規格 |
|------|------|
| 尺寸 | ~**480×360**（置於 `bg-honour-ceremony` 中央安全區） |
| Radius | **16–24px** |
| 外觀 | 厚紙證書 + 木框；中央大圓印章區（圖內無「已頒獎」字，印章可用抽象花紋；文字 DOM） |
| 填色 | `--honour-bg` / `--paper`；框 `--wood`；印章強調 `--honour` + 淡金 |
| 預留 | 標題列、姓名列、日期列、底部按鈕列皆空白帶 |
| 檔名 | `ui/ui-honour-panel.svg` 或 PNG |

---

## 3. 戰鬥精靈（Battle sprites）

共通：透明背景、單一物件、手繪／cottagecore RPG、**無文字**、無底座 UI。

### `sprite-hero`

| 欄位 | 內容 |
|------|------|
| 檔名 | `sprites/sprite-hero-front.png`、`sprites/sprite-hero-side.png` |
| 建議畫布 | **256×256**（角色約佔 70–85% 高度，腳底留 padding） |
| 角色 | 小孩冒險者：溫暖服色、小披風或背囊、友善表情；非寫實、非恐怖 |
| 變體 | **front**：面向鏡頭（選角／勝利）；**side**：面向右（戰鬥，敵在右） |
| 可選後續 | `sprite-hero-hurt`、`sprite-hero-attack`（本 v1 不強制） |

### `sprite-boar`（草原野豬）

| 欄位 | 內容 |
|------|------|
| 檔名 | `sprites/sprite-boar.png` |
| 建議畫布 | **288×224** |
| 朝向 | **面向左**（朝向英雄） |
| 外觀 | 卡通野豬、短牙、草地色鬃毛；可愛偏冒險、非血腥 |

### `sprite-generic-monster`（可選）

| 欄位 | 內容 |
|------|------|
| 檔名 | `sprites/sprite-generic-monster.png` |
| 建議畫布 | **256×256** |
| 朝向 | 面向左 |
| 外觀 | 中性史萊姆／森林小妖等通用剪影，方便換色換皮 |

---

## 4. 疊加示意（實作參考）

```text
任務頁 z-order:
  bg-guild-quest-room
  → ui-quest-card ×N + badges + ui-btn-claim（DOM）
  → ui-hud-chip-*（右上）
  → ui-tab-bar（底）

頒獎頁:
  bg-honour-ceremony
  → ui-honour-panel + DOM 文案／印章狀態
  → ui-tab-bar

戰鬥頁:
  bg-wilderness-grass
  → sprite-hero-side（左） + sprite-boar（右）
  → HUD／技能列（純 DOM/CSS）
```

---

## 5. 驗收清單（產圖後）

- [ ] 三張 BG 皆 1280×720，無字、無角色、無假 UI
- [ ] 安全區肉眼可放卡片／證書／雙人站位
- [ ] UI 對得上 tokens；按鈕／tab hit ≥ 44px
- [ ] 精靈透明底、朝向正確、可疊在草地 BG
- [ ] 檔名符合上表 id
