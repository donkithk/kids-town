# Kids Town UI 試作（棉花糖方向）

呢個資料夾係 **視覺 mock only**，用瀏覽器直接打開 HTML 就得，**冇後端、冇資料庫、冇改生產遊戲邏輯**。

唔會改 `index.html` 行為、亦唔會改 `backend_v2.py`。呢度只係俾設計討論同 PR 預覽。

## 點樣睇

用檔案總管雙擊，或者本機起一個靜態伺服器：

```bash
python -m http.server 8765 --directory mocks/ui-refresh
# 打開 http://127.0.0.1:8765/00-index.html
```

手機直開單頁亦可（viewport **准 pinch-zoom**：`width=device-width, initial-scale=1`，冇 `user-scalable=no`）。

| 檔案 | 畫面 |
|------|------|
| [00-index.html](00-index.html) | 圖庫：兩隻手機框 + 對而家 UI 嘅前後對照 |
| [01-kid-tasks-mobile.html](01-kid-tasks-mobile.html) | 小朋友「任務」tab（~390×844） |
| [02-parent-approval-mobile.html](02-parent-approval-mobile.html) | 家長待蓋章／空狀態 |
| [mock.css](mock.css) | 共用 token：色、字、間距、`:focus-visible` |

## 每個畫面展示咩

### 01 小朋友任務

- **底欄**（建議）：任務／城鎮／商店／探險／我的。插畫風 inline SVG，旁邊有清晰中文標籤；點擊區 ≥ 44px。
- 大粒任務卡（圓角 20–24px）。
- 其中一張 **待家長確認**：彈跳徽章、金幣預覽變灰／未入帳、吉祥物「等蓋章」表情。
- 其中一張 **已入帳**：慶祝條 + CSS 彩紙、吉祥物開心跳。
- 一張仍可按「完成」嘅進行中任務。

### 02 家長蓋章站

- 小朋友做完、等批准嘅家課列表。
- 主要動作：**蓋章入帳**（大粒成功色）；次要：**再試一次** 展開原因 chips + 文字欄。
- 右上示範切換可睇 **空狀態**（「全部蓋好章喇」+ 瞓覺吉祥物）。
- 同一套糖果色、圓卡、底欄；感覺係家庭蓋章站，唔係冷冰冰後台。

## 設計決定（好玩、但 UX 優先）

- **更亮、仍然柔**：糖果粉／薄荷／陽光黃做強調；背景粉彩漸層。成功＝綠薄荷、待確認＝陽光黃、危險＝莓紅，對比仍然清楚。
- **圓角 16–24px**、貼紙感描邊同輕微硬陰影。
- **字級**：`--font-display` Fredoka（標題／數字）、`--font-body` Nunito + Noto Sans TC。唔再用 9–11px 雜訊字。
- **微互動（純 CSS）**：掣按下彈跳／縮小；待確認徽章 bounce；已入帳徽章 pop + 彩紙落下。`prefers-reduced-motion` 會停動畫。
- **吉祥物「小城仔」**：簡單 SVG 臉——等確認（緊張）、已入帳（慶祝）、家長畫面（遞印章）、空狀態（瞓覺）。
- **鍵盤**：全域 `:focus-visible { outline: 2px solid; }`。
- **放大**：viewport 只寫 `width=device-width, initial-scale=1`。

Token 一覽（見 `mock.css` `:root`）：`--color-primary`、`--color-success`、`--color-pending`、`--color-danger`、`--font-display`、`--font-body`、間距 `--space-*`。

## 明確唔係咩

- **未接線**：撳掣唔會打 API、唔會改金幣、唔會寫入 SQLite。
- **唔係生產重構**：請唔好把呢套 CSS 直接覆蓋 `index.html`；要落地再另開實作 PR。
