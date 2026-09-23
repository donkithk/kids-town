# 城鎮建築證明（柔和等角剪影）

十座種子建築嘅 **Style A** 手繪等角剪影，加一頁靜態互動：空白城鎮 → 揀屋 → 金色格高亮 → 半透明預覽 → 確定放置／取消。取消**唔扣**畫面上嘅金幣同材料。

**只係設計建議。** 未改遊戲、API、經濟數字、測試。未得用戶 Preview 之前 **唔好 merge**。之後先至由 builder 接到產品。

風格來源係 PR #25（`mocks/town-style-compare/`）嘅 A：柔和約 45° 等角、暖木田園、厚線手繪。唔係像素，亦唔係真 3D。

種子順序跟 `backend_v2.py` 嘅 `seed_building_defs()`。註釋寫明：1 圖書館、2 健身室、3 農場、4 商店、5 醫院、6 探險公會、7 工坊、8 燈塔、9 競技場、10 天文台。銀行（id 11）唔喺呢包。

## 點樣打開

頁面**冇** `user-scalable=no`，可以放大。焦點環係 `#c45c26`。可撳目標喺 1280 舞台入面至少 44px。手機想要真實尺寸就加 `?native=1`（舞台唔縮細，自己捲）。

### 電腦

```bash
cd mocks/town-building-proof
python -m http.server 8767
```

- 放置／搬移演示：http://127.0.0.1:8767/index.html （`demo.html` 會跳去同一頁）
- 十座剪影一覽：http://127.0.0.1:8767/catalog.html
- 全尺寸自己捲：網址加 `?native=1`

### 手機

1. 電腦跑上面個 server，手機同一 Wi-Fi，開 `http://<電腦區域 IP>:8767/index.html?native=1`。
2. 或者呢條分支上 GitHub 之後用 raw.githack：

   `https://raw.githack.com/donkithk/kids-town/cursor/town-building-proof-ec78/mocks/town-building-proof/index.html`

   剪影紙：`https://raw.githack.com/donkithk/kids-town/cursor/town-building-proof-ec78/mocks/town-building-proof/catalog.html`

3. 建議橫放。可以捏合放大。演示狀態只喺呢頁瀏覽器入面，冇後端。

## 資產清單

剪影係透明 SVG，分層（牆、頂、門窗、物件分開畫），字喺 DOM，圖入面冇字。圖書館、農場、商店沿用 #25 A 嘅等角檔，其餘七座用同一套暖木、奶油牆、厚線。

| 種子 id | 中文 | 英文檔名 | 種子花費（參考，未改遊戲） |
| --- | --- | --- | --- |
| 1 | 圖書館 | `assets/bldg-library-iso.svg` | 💰100 🪵5 |
| 2 | 健身室 | `assets/bldg-gym-iso.svg` | 💰200 🪵10 🧱5 |
| 3 | 農場 | `assets/bldg-farm-iso.svg` | 💰300 🪵15 🧱10 |
| 4 | 商店 | `assets/bldg-shop-iso.svg` | 💰500 🪵20 🧱15 ⚙️5 |
| 5 | 醫院 | `assets/bldg-hospital-iso.svg` | 💰400 🪵15 🧱20 |
| 6 | 探險公會 | `assets/bldg-expedition-guild-iso.svg` | 💰150 🪵10 🧱5 |
| 7 | 工坊 | `assets/bldg-workshop-iso.svg` | 💰350 🪵20 ⚙️5 |
| 8 | 燈塔 | `assets/bldg-lighthouse-iso.svg` | 💰800 🪵30 🧱25 ⚙️15 💎3 |
| 9 | 競技場 | `assets/bldg-arena-iso.svg` | 💰1000 🪵40 🧱30 ⚙️20 💎5 |
| 10 | 天文台 | `assets/bldg-observatory-iso.svg` | 💰1500 🪵50 🧱40 ⚙️25 💎10 🪟3 |

Header／Footer 樣式係 #22／#25 嘅 `chrome.css` 快照，圖示喺 `assets/ui/`，所以喺呢個資料夾開 server 都載到，唔使靠上一層路徑。

共用格仔（由 #25 A 再改）：

| 檔 | 用途 |
| --- | --- |
| `assets/meadow.svg` | 草地背景 |
| `assets/cell-iso.svg` | #25 可建造虛線格（原樣） |
| `assets/cell-valid.svg` | 而家可以放：金虛線 |
| `assets/cell-illegal.svg` | 碰撞／出界：紅虛線同交叉 |
| `assets/plot-iso.svg` | 搬屋嗰陣嘅原位空地 |
| `assets/avatar.svg` | Header 頭像 |

Header／Footer 係 1280×720 信箱，城鎮首頁金色選中，同 #22／#25 一樣。演示籌碼開始係 💰6000 🪵240 🧱180 🪟12 ⚙️90，夠放晒十座畫面上有嘅材料。燈塔、競技場、天文台種子仲有寶石；共用 header 冇寶石格，所以演示**唔扣寶石**，亦冇改遊戲經濟。

## 演示點玩

1. 打開係空白草地，未有屋。
2. 左邊揀一座 → 空格變金框「可放」，已有屋嘅格變紅框「唔得」。
3. 指住或者點一格 → 半透明屋影。點「確定放置」先扣畫面籌碼。
4. 點「取消」（或者再撳一次同一座、或者 Esc）→ 籌碼唔變，toast：**已取消，資源未扣除**。
5. 點已起嘅屋（地圖或者清單）→ 提起，搬去另一格空格，或者取消。搬屋唔扣資源。
6. 點已佔格：紅框加「唔得」，確定掣停用。點草地空白：紅格「出界」。
7. 「重置地圖」清走示範同還原籌碼。每種建築只起一座。

全部狀態喺瀏覽器入面，冇呼叫 API。

## Preview 請對

- [ ] 十座都認到：圓窗書、啞鈴、麥田、黃簷、紅十字、旗同指南針、煙囪齒輪、燈塔光、沙地旗、圓頂望遠鏡
- [ ] 可以單獨擺、前後遮擋合理（等角分層）
- [ ] 空白開場；放置、半透明預覽、確定、取消
- [ ] 取消之後金幣／材料同取消之前一樣
- [ ] 提起再搬；取消搬屋都唔扣資源
- [ ] 已佔格同出界都係清楚嘅紅色非法狀態
- [ ] 可以放大；鍵盤焦點係 `#c45c26`；城鎮首頁係金色選中
- [ ] 未當正式功能，未接產品 `index.html`

## 唔好 merge

等用戶話 OK 先至算數。產品接線（真資源、真格仔、建造 API）係之後嘅 builder，唔係呢個 PR。
