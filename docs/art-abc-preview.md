# A–C 美術預覽（不合併）

只把 2026-11-04 鎖定的 A 木框和 C 探險公會放進城鎮畫面。預設關閉。廣場 B 沒有鋪上地圖。不改 8×8、擴建環、足跡相接、點擊格、`--s` 陰影縮放、導覽，也不改每日戰鬥獲勝上限。

## 本機怎麼看

不要用倉庫裡的 `kids_town.db`，也不要開隧道。

不解壓 git、也不要打開倉庫裡的 `kids_town.db` 或隧道。審查包在 Agent Store：`/cursor/stores/self/art-abc-review.tar.gz`。裡面沒有資料庫。

```bash
mkdir -p /tmp/art-abc-review
tar -xzf /cursor/stores/self/art-abc-review.tar.gz -C /tmp/art-abc-review
cd /tmp/art-abc-review/kids-town
python3 -m pip install -r requirements.txt
ART_PREVIEW_PORT=9124 ART_PREVIEW_DB=/tmp/kids-town-art-preview.db python3 scripts/art_abc_preview_server.py
```

`--port 9124` 跟 `ART_PREVIEW_PORT` 一樣，只聽 `127.0.0.1`。兩個都沒給時仍是 **9123**。`--port` 蓋過環境變數。路徑若是倉庫的 `kids_town.db`，腳本會拒絕。

瀏覽器開 `http://127.0.0.1:9124/kids/?art=abc`。登入走現有登入流程，不另開免登入截圖。地圖上有相接的健身室 `(0,0)` 和探險公會 `(2,0)`。選單「關閉美術預覽」可關掉。`?art=off` 強制關閉。

對照測試：

```bash
python3 -m pytest tests/test_art_abc_preview.py -v
```

## 畫面上有什麼

- **A** `derived/ui-town-wood-frame-cutout.png`：1280×720，奶油中心挖空。預覽打開時整張圖以 1.08 倍置中放大，舞台把外圈木條裁掉，所以看得見的框變薄、中間開口變大。不是九宮格，也沒有重畫原圖。只在城鎮分頁蓋上。8×8 加外圈鎖格會縮進這個開口，不再靠地圖內的捲軸。離開城鎮或進入戰鬥時，木框和這段位移會收回。
- **主目錄**：抽屜改放在 1280×720 舞台裡，跟信箱一起縮放，奶油紙面、木色邊。預覽開或關都可以完整看到關閉鈕。底欄在遮罩之上，點「公會大廳」等分頁會先收起目錄。
- **C** `derived/building-adventure-guild-cutout.png`：641×833，四角透明，沒有奶油方塊。寬度仍是原點那一格，底邊對齊石台。名字是 DOM。接觸陰影仍是原來的橢圓，跟 `--s` 一起縮。
- **B** 原圖留在 `originals/bg-town-plaza.jpg`，沒有派生圖，也沒有設成地圖背景。

切圖算法在 `assets/art-locked-2026-11-04/DERIVE.md`。原 JPEG 沒有改過。

## 不足（如實）

- 廣場是 6×6 菱形加木板十字和石板環，而且伸出地圖矩形，碰到頂欄、底欄和左右邊。鋪在 8×8 後面會多出一套格子。用顏色把格子抹掉，不是留下可讀的殘影，就是連樹一起吃掉。所以這次預覽不顯示 B。
- 木框是整張 1280×720，沒有核准過的九宮格。開口是透明的，裡面看到的是現有綠色地圖，不是廣場。
- 公會比舊 SVG 高。名字依切圖高度抬到屋頂上方，避免壓在旗上。陰影沒有改位置，橢圓可能比新石台寬一點。石台和草叢是原圖裡的，QC 已接受。窗戶是藍灰，偏出色票，同樣接受、不重畫。
- 其他建築仍是舊 SVG，和這座公會不是同一套。
- 煙囪頂的洞是奶油被挖掉後的透明，不是另外畫的內壁。

## 還沒有鎖定圖的清單

這批鎖定只有 A、B、C。下面都還沒有對應的鎖定繪圖，這次沒有補畫。

| 缺什麼 | 現況 |
| --- | --- |
| 圖書館、健身室、農場、商店、醫院、工坊、燈塔、競技場、天文台 | 地圖上仍是 `mocks/town-building-proof` 的 SVG |
| 廣場可對上 8×8 的草地 | B 不能直接用，見上 |
| 物品圖 | `generated/` 裡沒有鎖定的物品組 |
| 商店／公會內頁圖示 | 仍是扁平 emoji／向量；shot list 標成非本批 |
| 任務卡、領取鈕、徽章、HUD chip、榮譽面板、分頁木紋 | asset kit 的 `ASSETS.md` 有規格，`ui/` 沒有那些匯出檔 |
| 英雄 | asset kit 有 `sprite-hero.png`，不在這次鎖定，沒有接上 |
| 怪物 | 2026-11-04 鎖定寫明延後。這次沒有接狼、豬、熊、蠍 |

Footer 五個 SVG（城鎮首頁、公會大廳、任務板、商店、背包）是另一套，不是這次 A–C。
