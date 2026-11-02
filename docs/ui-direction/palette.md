# Kids Town — Palette tokens

鎖定色票。**禁止**新增未列於下表的 hex。與 `mocks/asset-kit/ASSETS.md` 的 `:root` 一致。  
Swatch 圖：`palette-swatch.png`。

## Token list

| Token | Hex | Role |
|-------|-----|------|
| `--wood` | `#8b5e3c` | base — 主木色（外框、木紋） |
| `--wood-mid` | `#a67c52` | base / highlight — 室內木底、中亮木 |
| `--wood-deep` | `#5c3d28` | shadow — 深木陰影、暗邊 |
| `--wood-plank` | `#c4a06a` | highlight — 木條高光、pinstripe |
| `--cream` | `#faf6ef` | UI base — footer／卡面 |
| `--paper` | `#fff8e7` | UI highlight — 亮紙卡 |
| `--paper-aged` | `#f3e6c8` | UI base — 舊紙、EXP chip 底 |
| `--ink` | `#3b2a1a` | UI — 主文字 |
| `--ink-soft` | `#5c4632` | UI — 次級文字 |
| `--muted` | `#7a6550` | UI — 弱提示／禁用 |
| `--gold` | `#d4a017` | accent — 選中金框、點綴 |
| `--gold-bright` | `#f0c14b` | accent / highlight — CTA 黃、亮金 |
| `--sky` | `#87ceeb` | base — 天空 |
| `--sky-soft` | `#c5e8f7` | highlight — 柔天空／遠景 |
| `--grass` | `#7cb342` | base — 草地、草原 BG |
| `--pending` | `#e8a317` | accent — 待確認 |
| `--pending-bg` | `#fff3d6` | UI — 待確認底 |
| `--honour` | `#9b2c2c` | danger / accent — 榮譽紅 |
| `--honour-bg` | `#fff5e0` | UI — 榮譽底 |
| `--focus` | `#c45c26` | accent — focus-visible 描邊 |

## CSS `:root`（matching ASSETS.md）

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

## Usage notes

- 木 chrome／外框：`--wood` · `--wood-mid` · `--wood-deep` · `--wood-plank`
- 紙卡／footer：`--cream` · `--paper` · `--paper-aged`；字色 `--ink` / `--ink-soft` / `--muted`
- 選中 tab／柔金點綴：`--gold` · `--gold-bright`
- 晝空／草：`--sky` · `--sky-soft` · `--grass`
- 狀態：pending / honour / focus 各對一組字色＋底色（或描邊）

LOCKED 2026-11-02 · tip e075646
