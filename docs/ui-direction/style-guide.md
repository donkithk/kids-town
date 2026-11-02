# Kids Town — Art Style Guide

**遊戲**：Kids Town（donkithk/kids-town）  
**類型**：兒童生活模擬／cottagecore RPG 城鎮建造（探索＋戰鬥）  
**版本**：LOCKED 2026-11-02 · Preview tip `e075646` + asset-kit · user lock (合啦)

---

## 三大支柱（Three pillars）

1. **溫暖木質手繪**：外框、建築與戰鬥背景以手繪木質／石材插畫為主，營造可觸摸的 cottagecore 溫度。  
2. **奶油紙卡 UI**：HUD、內頁卡、footer 以 cream／paper CSS 藥丸與卡片承載書面語文案，不把字烤進圖。  
3. **友善可讀、非糖果**：剪影清楚、晝光柔和、金色點綴；拒絕糖果粉彩與暗黑夜 RPG。

---

## 透視與鏡頭（Perspective and camera）

| 場景 | 透視 | 說明 |
|------|------|------|
| 城鎮地圖 | **等角（isometric）** tile | 草地／泥土可建造格＋外圈鎖定擴張環；建築為等角精靈疊在地圖上 |
| 室內／商店／公會頁 | **平面 UI 卡** 疊於 wood／cream 底 | 非 3D 室內漫遊；大 cream 紙卡＋白藥丸 |
| 戰鬥 | **側視偏手繪背景** + 精靈 | 草原等手繪 BG；英雄／怪物為獨立 sprite 層 |

舞台固定 **1280×720**，全螢幕以均勻縮放／letterbox 適配；不以變形拉伸改比例。

---

## 色票表（Palette）

僅使用下列鎖定色；禁止自創 hex。

| Token | Hex | 角色 |
|-------|-----|------|
| `--wood` | `#8b5e3c` | base · 主木色外框／木紋 |
| `--wood-mid` | `#a67c52` | base／highlight · 室內木底、中亮木 |
| `--wood-deep` | `#5c3d28` | shadow · 深木陰影、木框暗邊 |
| `--wood-plank` | `#c4a06a` | highlight · 木條高光、pinstripe |
| `--cream` | `#faf6ef` | UI base · footer／卡面底 |
| `--paper` | `#fff8e7` | UI highlight · 紙卡亮面 |
| `--paper-aged` | `#f3e6c8` | UI base · 舊紙／EXP chip 底 |
| `--ink` | `#3b2a1a` | UI · 主文字 |
| `--ink-soft` | `#5c4632` | UI · 次級文字 |
| `--muted` | `#7a6550` | UI · 弱提示／禁用偏色 |
| `--gold` | `#d4a017` | accent · 選中框、金點綴 |
| `--gold-bright` | `#f0c14b` | accent／highlight · CTA 黃、亮金 |
| `--sky` | `#87ceeb` | base · 天空、晝光 |
| `--sky-soft` | `#c5e8f7` | highlight · 柔天空、遠景霧 |
| `--grass` | `#7cb342` | base · 草地 tile、草原 BG |
| `--pending` | `#e8a317` | accent · 待確認狀態 |
| `--pending-bg` | `#fff3d6` | UI · 待確認底 |
| `--honour` | `#9b2c2c` | danger／accent · 榮譽紅、警示強調 |
| `--honour-bg` | `#fff5e0` | UI · 榮譽底 |
| `--focus` | `#c45c26` | accent · `:focus-visible` 描邊 |

完整 CSS `:root` 見 `palette.md`（與 asset-kit `ASSETS.md` 一致）。

---

## 線條與描邊（Line and outline）

- 建築／木框／BG：手繪感中等線寬，暖褐墨（近 `--ink`／`--wood-deep`），避免純黑硬邊。  
- 戰鬥英雄：可略粗、清晰 chibi 外輪廓以利 720p 可讀。  
- 怪物（延後）：外輪廓權重須與英雄同級，禁止寫實軟邊對上粗線 chibi。  
- CSS UI：無插畫描邊；用邊框色 `--wood`／`--gold`／`--focus`。  
- 區域標記：扁平圖示，細／無描邊，勿做成微縮寫實建築。

---

## 光線與陰影（Light direction and shadow）

- **主光**：左上柔和日光（soft upper-left daylight）。  
- 建築與 BG：單一光源；陰影偏暖褐（`--wood-deep` 低透明度），禁止冷藍硬影。  
- **禁止**把落地陰影烤進精靈／建築 PNG（no baked drop-shadow platforms）；陰影由場景或 CSS 另加。  
- UI 卡：極淡 soft shadow（`--wood-deep` ~12%），保持紙卡浮在木底上的層次即可。

---

## 細節預算（Detail budget per asset class）

| 資產類 | 預算 | 備註 |
|--------|------|------|
| **BG art** | 中高：材質、遠景層次 | 中央／安全區留空給 DOM；1280×720 全幅 |
| **Building sprite** | 中：石＋木結構可讀剪影 | 等角；透明底；旗／布可為色塊形狀**無字** |
| **Wood chrome texture** | 中低：木紋＋邊角可 9-slice | 無圖示、無文字；供外框／footer 紋理 |
| **CSS UI** | 低繪製：色塊＋圓角＋邊 | cream／paper／pills；書面語由 DOM |
| **Battle sprite** | 中：清晰剪影＋少許材質 | 英雄 chibi 粗線；怪物須匹配同語彙（目前 **defer reskin**） |

---

## 1280×720／小手機 letterbox 可讀性

- 關鍵互動 hit ≥ **44×44px**（對應 stage 座標）。  
- 建築剪影在縮到手機 letterbox 後仍能辨「塔／店／屋」，勿依賴細紋理辨識。  
- Footer 五 tab（城鎮首頁／公會大廳／任務板／商店／背包）：選中為 **金框**（`--gold`／`--gold-bright`）；未選中靠圖示＋書面語，勿過密裝飾。  
- 圖內**零文字**；所有書面語中文由 DOM 承擔。

---

## 越界（Out of bounds）

- ❌ 糖果粉彩／霓虹／高飽和泡泡糖 UI  
- ❌ 暗黑夜 RPG、哥德、血腥寫實  
- ❌ 全概念一張 PNG 內嵌熱點框／假按鈕／假 HUD  
- ❌ 圖內任何文字（中英皆禁）  
- ❌ 自創未鎖定 hex  
- ❌ 英雄 chibi 對寫實軟邊怪物同屏出貨（mismatch → **defer monster reskin**）  
- ❌ 透視混用：等角建築畫成正面正交卡、或把室內做成可走 3D

---

## 圖層規則（Layer rules）

僅允許三層：

1. **BG art** — 手繪背景／城鎮底／戰鬥草原等  
2. **HTML·CSS UI** — 框、卡、footer、藥丸、圖例、CTA  
3. **Sprites** — 建築、角色、（日後）怪物  

禁止「全畫面概念圖 + 熱點盒」單一 PNG 交付。區域標記用扁平 icon，不與手繪建築混為同一資產語彙除非另開批次。

---

## Preview 對齊摘要（encode observations）

- **Town hub**：厚手繪木外框；等角草地 8×8 可建造＋鎖定擴張環；一座石＋木 **探險公會** 塔樓；圖例 cream 卡；CTA 黃；footer cream＋木 pinstripe＋金選中。  
- **Shop／Guild 內頁**：實色 `--wood-mid` 底＋大 cream 紙卡＋白藥丸；店內圖示偏扁平 emoji／vector — 與外觀手繪建築有語彙落差，後續批次對齊。  
- **Battle**：手繪草原 BG 可接受；英雄粗線 chibi vs 狼偏寫實軟邊 — **風格不一致，怪物延後重繪**。

---

## 參考（References）

方向參考 only；**禁止描摹／重繪對方資產**。

- **REF1** — [Pathipelago](https://onebitkid.itch.io/pathipelago)：舒適等角島嶼生活；小地圖尺度下磨損小徑＋小屋剪影重量。  
- **REF2** — [villaggio](https://jvolonte.itch.io/villaggio)：cottagecore 林間聚落；柔可愛房屋而無糖果霓虹。  
- **REF3** — [Clover & Clay UI direction](https://strategicsloth.com/game-ui/clover-and-clay/)：暖木＋奶油陶土面板溫度（僅參考語彙；素材包可能未發行）。  
- **REF4** — [Pixem Forest Valley](https://assetstore.unity.com/packages/2d/gui/pixem-forest-valley-382882)：木紋外框＋奶油舒適農莊 UI 語彙。  
- **REF5** — [Cozy Farming UI Kit](https://nexavisuals.itch.io/cozy-farming-ui-kit-complete-edition)：手繪感暖木／cream 面板；HUD 一致的左上柔光。  
- **REF6** — [Spiritfarer](https://thunderlotusgames.com/games/spiritfarer/)（Thunder Lotus）：手繪暖室內、柔日光、羊皮紙／木 UI 沉靜感。  
- **REF6b** — [Cozy Grove hand-drawn interview](https://www.polygon.com/interviews/22397934/indie-games-hand-drawn-artists-cozy-grove/)：手繪線＋水彩洗的溫暖（方向 only）。  
- **REF6c** — [Stardew Valley](https://www.stardewvalley.net/)（ConcernedApe）：柔和白晝農場景色＋地圖尺度可讀建築剪影（像素媒介不同；只取剪影／可讀性，不取像素點畫法）。

建議 takeaways（對應支柱）：cozy cottage 剪影重量、暖木 UI 溫度、柔和日光、等角城鎮可讀、友善非糖果、柔金點綴。

---

## 版本註記

**LOCKED 2026-11-02** · 來源：Live Preview tip `e075646` + asset-kit · user confirmed 合啦。  
本包收在 `docs/ui-direction/`，作為鎖定美術方向；本變更只加文件，不改產品 CSS 或遊戲程式。
