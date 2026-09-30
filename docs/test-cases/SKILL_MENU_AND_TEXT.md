# 戰鬥技能選單、書面語說明、營養餐回 MP

紅測。產品代碼未改之前，選單同書面語同營養餐回 MP 會失敗。選擇器跟設計稿 `63b81c8` 的 `docs/ui-mocks/battle-skill-menu.html`。唔好用設計稿卡片上嘅說明文字做預期（嗰度抄咗舊口語／公式，例如「+3×等級」）。說明文字只跟下面「書面語」。設計稿嘅 MP 3/20 同 14 個技能係示範數據。

只測 1280×720。直向 390×844 維持現有 `#ktRotate`「請轉橫向」，唔好測直向技能選單。

## 保留現有 id

唔好改走而家 Playwright 套件用緊嘅 id／class。戰鬥畫面要繼續有 `.battle-scene`、`.m-name`、`.monster-card`、`#dbt`、`.result-overlay`。舞台係 `body.kt-artstage .gsw.stage`（layout 1280×720）。底部分頁係 `#ktFooter`（`aria-label="主要導覽"`：城鎮首頁、公會大廳、任務板、商店、背包）。攻擊掣嘅 accessible name 要含「攻擊」，所以現有「打贏」流程仍然撳到。

設計稿舞台 id 係 `#stage`。可以加喺同一個 `.gsw.stage` 節點上面，唔好另起一個舞台。

## 選擇器合約（mock 63b81c8）

### 指令列

戰鬥底部指令列係 `.command-bar`（可以放喺現有 `.kt-command-bar` 裡面，取代而家嘅 `.kt-skill` 熱點）。

正好三個掣，由左至右：

| id | 文字 | 類 | 其他 |
|----|------|----|------|
| `#btnAttack` | 攻擊 | `cmd cmd-primary` | |
| `#btnSkill` | 技能 | `cmd` | `aria-expanded`，`aria-controls="skillPanel"` |
| `#btnFlee` | 逃走 | `cmd` | |

指令列唔好再有個別技能掣，亦唔好有「未解鎖」佔位。

### 技能選單

`#skillPanel.skill-panel`：木框（有可見粗邊）。收起時有 `hidden`。打開之後：

- 選單底邊 ≤ `#ktFooter` 頂邊（唔好疊住底部分頁）。
- 選單底邊 ≤ `.command-bar` 頂邊（坐喺指令列上面）。
- 選單 bounding box 完全喺 1280×720 舞台裡面，唔好被 overflow 裁走。

頂部：

| 節點 | 要求 |
|------|------|
| `#skillTitle` | 文字「技能」 |
| `#mpNow` | 而家 MP |
| `#btnBack` | 文字「返回」，關閉選單，唔施放 |
| `#btnClose` | `aria-label="關閉技能"`，關閉選單，唔施放 |

`Escape` 同樣關閉，唔施放。

### 卡片同翻頁

`#skillGrid.skill-grid` 係 2 欄 × 3 行，每頁 6 格。

每張真正技能係 `button.skill-card`：

| 節點 | 要求 |
|------|------|
| `.skill-name` | 技能名 |
| `.mp-pill` | 文字正好 `MP {消耗}`（整數，例如 `MP 4`） |
| `.skill-desc` | 非空說明。用技能自己嘅書面語，唔好抄設計稿 |
| `.broke` | 只喺 MP 唔夠時出現，文字正好「MP 不夠」 |

MP 消耗 > 而家 MP：`aria-disabled="true"`（可以同時 `disabled`）。灰色可以做，但測試唔會單憑顏色失敗。MP 標籤可以轉紅，同樣唔係硬斷言。撳呢張卡唔好施放：MP 不變，`turns` 長度不變。

MP 夠嘅卡：一撳就施放（自身目標技能唔使再揀怪），MP 減少該技能消耗，選單關閉（`hidden`）。施放斷言用「蓄力」，唔用「營養餐」或「修復」（呢兩個會另加 MP）。

翻頁：

| 節點 | 要求 |
|------|------|
| `#btnPrev` | `aria-label="上一頁"`，文字「◀」 |
| `#btnNext` | `aria-label="下一頁"`，文字「▶」 |
| `#pageLabel` | 正好 `N / M`（左右有空格），例如 `1 / 1`、`1 / 2`、`2 / 2` |
| `#pageDots .dot` | 每頁一點。而家頁 `aria-current="page"`，`aria-label` 例如「第 1 頁」 |

禁用用 `aria-disabled="true"`，掣仍然喺畫面。第一頁 ◀ 禁用。最後一頁 ▶ 禁用。

- 6 個已學技能：一頁。標籤 `1 / 1`。6 張卡，全部可揀（MP 夠嘅話）。◀ ▶ 都睇到，而且兩個都 `aria-disabled="true"`。一點。
- 8 個已學技能：兩頁。第一頁標籤 `1 / 2`、6 張卡、◀ 禁用、▶ 可用。▶ 之後標籤 `2 / 2`，**正好 2 張** `.skill-card`，其餘格留空，唔好有佔位／假卡／「未解鎖」。▶ 禁用，◀ 可用。◀ 返第一頁。
- 次序跟開戰 `skills` 陣列：第 1 頁係頭 6 個，第 2 頁係其餘。每個已學技能都要搵到。已學 = 已放置（`stored=0`）建築等級 ≥ `skill_defs.level_required`。

### HP／MP

`#playerVitals` 裡面有 `#hpNums` 同 `#mpNums`。選單打開時，呢三個 bounding box 要完全喺舞台內、唔好被 overflow 裁、唔好疊 `#ktFooter`。

### 敵人名牌唔好被選單遮住

區 1 真正開戰跟 `battle_start`：非 preview 小朋友 `random.randint(1, 3)` 隻同一區怪物。區 1 係野狼。測試用同一個 API 重開，直到隻數係 3；另一條直到係 1。唔好自己砌一排假卡。

名牌、血條、血量數字用而家 `index.html` 已有嘅節點。main 同 #59 `f37f6fc` 都有，唔使加新 class：

| 節點 | 意思 |
|------|------|
| `.monster-card .m-name` | 敵人名字 |
| `.monster-card .m-hp-bar` | HP 條 |
| `.monster-card .m-hp-text` | HP 數字 |

`.m-img` 同入面嘅精靈圖可以俾選單遮住。測試唔量精靈。

1280×720。打開 `#btnSkill` → `#skillPanel` 之後，每一隻敵人：

- `.m-name`、`.m-hp-bar`、`.m-hp-text` 都要看得見（唔好 `display:none`、`visibility:hidden`，亦唔好 `hidden`），而且同 `#skillPanel` 的 bounding box 交集係 0 px²。
- `#skillPanel` 底邊要高過最高嗰塊名牌或血條至少 8px。
- 選單仍然要完全喺 1280×720 舞台入面，唔好被 overflow 裁，底邊唔好低過 `.command-bar` 同 `#ktFooter`（同 `TC-FE-SKILLMENU-LAYOUT`）。

## 書面語

常數 `tests/skill_menu_spec.py` 的 `COLLOQUIAL_CHARS`：

`嘅` `咩` `啲` `唔` `冇` `係` `喺` `佢` `嘢` `畈`

新鮮庫 22 個技能、開戰 `skills[].description`、`GET /api/kids/<id>/skills` 的 `description`、舊庫遷移之後，全部唔好含上面任何一字。每個技能一個 case。

盾擊要正好「物理攻擊，下一次受到的傷害減半」。呢句同書面語 case 一齊參數化：`TC-API-SKILL-FORMAL`（種子）、`TC-API-SKILL-FORMAL-API`（兩個 API）、`TC-API-SKILL-FORMAL-MIGRATE`。疾風斬、強光仍然只鎖口語字。營養餐仍然只鎖「回復」同「MP」，唔逐字。

`TC-API-SKILL-DESC-05` 的盾擊關鍵字改為「減半」加上「下一次」或「下次」，唔再要求「被打中」。強光「2 次」加「落空」／「打不中」、拒絕「打唔中」，以及其他 DESC-05 鎖，維持原案。

遷移有兩個來源：

- `afbc1a6`：冇銀行。挑釁 id 8 改名做盾擊之後，說明要變上面嗰句。
- main `3b0a48a`：盾擊已經係「物理攻擊，怪物攻擊傷害減半，直到下一次被打中」。遷移後要變新句，id 8 唔好變。

戰鬥 UI 讀嘅係 `POST /api/kids/<id>/expedition/battle-start` 回報入面 `skills[].description`，同 `GET /api/kids/<id>/skills`。選單 `.skill-desc` 要同呢段文字一致。

舊庫：`afbc1a6` 的 `backend_v2.py` 用 `/tmp` git worktree 建成暫存庫，放入合成小朋友同已學 skill id，再抄一份，用而家代碼的 `init_db`／`migrate_db`／`migrate_db_v3`／`migrate_db_v4`／`seed_building_defs`／`seed_skill_defs`。小朋友行同已學 skill id 要保留（挑釁→盾擊、迴避→疾風斬可以改名，id 唔好變）。唔好打開版控嘅 `kids_town.db`。

## 營養餐回 MP

`NUTRITION_MEAL_MP_REGEN = 5`（之後可以改數，斷言要用呢個常數）。

施放「營養餐」：

- 傷害同而家 main 一樣。爆擊關、`random.randint` 方差固定 0（同 `tests/test_skill_truth.py`／`tests/battle_truth.py`）。Lv20、區 1（怪防 0）、農場 Lv1、探險公會 Lv1。
  - 平衡（能力全 0，`player_atk` 5）：傷害 **5**。
  - 偏科（`ability_str` 20，其餘 0，`player_atk` 35）：傷害 **35**。
- 原效果不變：施放當下 HP 不變；之後 3 回合各回 **14** HP；第 4 回合停止。之後回合唔好再加 MP。
- 施放後 MP = `min(max_mp, mp_before - cost + NUTRITION_MEAL_MP_REGEN)`。
- 若 `mp_before - cost + 5 > max_mp`，MP 正好等於 `max_mp`。

說明（種子同舊庫遷移之後，以及上面兩個 API）要含「回復」同「MP」，並且書面語。唔使含數字 5，亦唔好逐字。「物理攻擊，回復 MP，並持續回復 HP」含「回復」同「MP」，又冇口語字，所以過。

`TC-API-SKILL-MEAL` 的 MP 斷言已改成上面公式。回血幅度、Lv5 ≥ Lv1、第 4 回合停止，維持原案。

## 字級、標題列、戰鬥訊息

選擇器跟 `ee8a3eb` 的 `index.html`，常數喺 `tests/skill_menu_spec.py`。斷言係尺寸同行為。`#ktFooter` 唔另加新斷言，沿用現有套件。`TC-FE-SKILLMENU-ENEMY-VISIBLE` 唔改。

`#wildToast` 由 `renderBattleMode` 用上一回合 `log` 砌出嚟，冇一個可以傳字串就寫入嘅函式。`townData` 係頂層 `let`，Playwright 改唔到。測試喺戰鬥畫面直接設 `#wildToast` 的 `textContent`。撳返回／✕ 會 `renderExpedition()`，節點換咗，所以關閉之後再設同一次長句，先量收起選單之後嘅版面。

長句係 `野狼從草叢撲過來` 重複 12 次（96 字）。先用 1100px 寬、`white-space:normal`、抄 `#wildToast` 字級嘅探針確認會摺成 2 行或以上。短句係「準備」，用來量單行高度。

### TC-FE-SKILLMENU-TYPE

6 個技能的小朋友、8 個技能的小朋友第 2 頁，以及一個學齊 22 個技能的合成小朋友（逐頁）。選單打開：

- `.skill-name` 字級 ≥ 22px
- `.skill-desc` 字級 ≥ 15px
- `.skill-icon` 字級 ≥ 28px，而且盒子 ≥ 28×28
- `.skill-card` 的 padding-top／bottom ≥ 6px，padding-left／right ≥ 8px
- 說明仍然單行：`white-space:nowrap`，高度 ≤ 1.3×字級，`scrollWidth` ≤ `clientWidth`（22 個技能都係）
- 卡高度 ≥ 72px，成張卡喺 `#skillPanel` 裡面
- 圖示離卡 border box 每邊 ≥ 4px

`ee8a3eb` 量到：卡名 20px、說明 13px、圖示字 24px、盒子 28×24、padding 3px 4px。所以紅。

### TC-FE-SKILLMENU-NOSQUEEZE

假綠。`#59` `7e00b66` 用 `.skill-desc { letter-spacing: -0.14em }` 把 15px 說明擠到 `scrollWidth` 入到卡裡面，所以 `TC-FE-SKILLMENU-TYPE` 過。中文擠埋一齊，睇唔清。呢條封住負字距，同埋縮放、字寬、省略號呢類同類漏洞。

同一套畫面：1280×720。6 個技能的一頁、8 個技能的第 2 頁、學齊 22 個技能逐頁。每一頁再量 `#skillTitle`「技能」同 `#pageLabel`。字級下限仍然由 `TC-FE-SKILLMENU-TYPE` 負責（說明 ≥ 15、卡名 ≥ 22），呢條唔再寫一次，只係量同一批元素。

每一個 `.skill-desc`、`.skill-name`、`#skillTitle`、`#pageLabel`：

1. computed `letter-spacing` ≥ 0（`normal` 當 0）。computed `word-spacing` ≥ 0。
2. 元素自己，以及上至 `#skillPanel`（包括面板）的每個祖先，computed `transform` 係 `none`，或者純位移矩陣（`a=1,b=0,c=0,d=1`，容差 0.001）。元素 `getBoundingClientRect().width / offsetWidth` 喺 0.99 到 1.01。
3. computed `font-stretch` 係 `100%` 或 `normal`。
4. 只限 `.skill-desc`：`text-overflow` 唔好係 `ellipsis`，`scrollWidth` ≤ `clientWidth`（同 TYPE 一樣容許 1px），而且仍然單行（`white-space:nowrap`，高度 ≤ 1.3×字級）。
5. CJK 字寬：對每個文字節點用 DOM Range，量每個漢字或全形標點（U+3000–U+303F、U+4E00–U+9FFF、U+FF00–U+FFEF）的 client rect 寬。每個都要 ≥ 0.95 × computed font-size。失敗訊息列出每個技能的最小比例。

main 未有選單，所以紅。`7e00b66` 的說明係 -0.14em，字寬低過 0.95，而且 `text-overflow:ellipsis`，所以都紅。

### TC-FE-SKILLMENU-TITLE

選單打開（6 技能的 `1 / 1`，同 8 技能第 2 頁的 `2 / 2`）：

- `#skillTitle`「技能」字級 ≥ 26px
- `#pageLabel`「N / M」字級 ≥ 20px
- `#btnBack`「返回」寬 ≥ 80px、高 ≥ 44px
- `#btnPrev` ◀、`#btnNext` ▶、`#btnClose` ✕ 都 ≥ 44×44
- 標題列控件（標題、頁碼、返回、◀ ▶ ✕、`#mpNow`、頁點）全部喺面板內，兩兩交集 0 px²

`ee8a3eb`：標題 22px、頁碼 16px、返回 `min-width` 64px（全域 `border-box`）。所以紅。

### TC-FE-TOAST-MENU-ONELINE

區 1 真正開戰，重開到 3 隻野狼，再重開到 1 隻。選單打開時，長句：

- `#wildToast` 高度 ≤ 短句單行高度 + 1px
- `text-overflow` 係 `ellipsis` 而且 `white-space` 係 `nowrap`（或者等同截斷：`scrollWidth` > `clientWidth`）
- 同 `#skillPanel` 交集 0 px²

收起選單（返回，冇返回就 ✕）之後：全文可見（`scrollWidth` ≤ `clientWidth` 而且 `scrollHeight` ≤ `clientHeight`），同每隻 `.m-name`、`.m-hp-bar`、`.m-hp-text` 交集 0 px²。

`ee8a3eb`：選單打開時，兩行訊息同 `#skillPanel` 交集 9963 px²。訊息唔係單行省略。所以紅。

### TC-FE-TOAST-NO-SHIFT

3 隻同 1 隻野狼，選單收住。先記短句時每張 `.monster-card` 的 top／left，再換成長句：

- 每張卡 top／left 移動 ≤ 1px
- 短句同長句兩種狀態，每隻 `.m-hp-text` 同戰鬥指令列交集都係 0 px²。指令列係 `.battle-scene .kt-command-bar`（木條）同入面嘅 `.command-bar`（三個掣）。`ee8a3eb` 嘅血量數字疊住木條，未疊到裡面嗰行掣。
- `#playerVitals` 的位置同尺寸唔變

`ee8a3eb`：長句將怪物卡推低 14.375px，每張卡的 `.m-hp-text` 同 `.kt-command-bar` 交集 711.984 px²（約 712）。main 係推低 24px、交集 2127 px²。所以紅。

### TC-FE-SKILLMENU-PANEL-RECT

守衛。選單打開時 `#skillPanel` 維持 `ee8a3eb` 的盒子：left 332±2、top 141±2、right 980±2、bottom 461±2。呢條喺 `ee8a3eb` 應該過。`TC-FE-SKILLMENU-ENEMY-VISIBLE` 維持原案。

## 木框內線、圖示、頁點

`8ac7b0d` 的 `#skillPanel`（`.battle-scene.kt-wild .skill-panel`）冇 `::before`／`::after`（computed `content: none`）。木框唔係背景圖，係元素自己畫的：

- `border: 8px solid #3b2416`（外圈深木）
- `box-shadow: inset 0 0 0 3px #e7c48a, inset 0 0 0 6px #6b4428, 0 10px 0 rgba(28,16,8,.28)`
- `background-color` 加三層 `background-image`（徑向高光、橫向木紋、直向漸層）只填面板裡面

**內線**：border box 向內收「該邊 `border-width` + inset box-shadow 喺嗰一邊的最大內伸」。內伸 = `max(0, spread + 向內 offset)`：左 `spread + offsetX`、右 `spread - offsetX`、上 `spread + offsetY`、下 `spread - offsetY`。模糊唔計入內線。冇 `inset` 的外陰影唔計。如果 `::before`／`::after` 真係生成一個 absolute 盒，而且四邊 inset 都係長度，內線再收緊到該偽元素的邊框加 inset 陰影。

`8ac7b0d` 兩層 inset 的 offset 都係 0、blur 都係 0，最大 spread 係 6px，所以內線離 border box 14px。面板 `332 / 141 / 980 / 461` 時，內線係 left **346**、top **155**、right **966**、bottom **447**。

### TC-FE-SKILLMENU-INSET

原因：左右 padding 由 12px 跌到 4px，卡由大約 300 闊到 309。「技能」、卡的左右邊同 ✕ 踩入木框深色內線大約 2px。第三行卡底離內線只剩 2px。

步驟：1280×720。6 個技能的一頁、8 個技能的第 1 同第 2 頁、學齊 22 個技能的每一頁。打開 `#btnSkill`。

預期：

- `#skillPanel` computed `padding-left` 同 `padding-right` ≥ 12px
- 每張 `.skill-card`、`#skillTitle`、`#mpNow`、`#btnPrev`、每一粒 `#pageDots .dot`、`#pageLabel`、`#btnBack`、`#btnClose` 的 bounding rect，離內線每一邊 ≥ 4px
- `#skillGrid` 仍然係 2 欄 × 3 行（最後一頁可以有空格）。卡兩兩交集 ≤ 0.5 px²。卡高 ≥ 72px
- 卡闊 ≤ 304px。12px 側 padding 喺鎖定的 648px 面板上，扣 6px 欄距，自然係 301px。唔鎖死 300

`8ac7b0d` 量到：padding `4px 8px`（左右 4、上下 8）。卡闊 **309**、高 72。網格 `309px 309px` / `72px 72px 72px`。「技能」左 **-2px**。✕ 右 **-2px**。左欄卡左 -2px，右欄卡右 -2px。第三行卡底 **2px**（內線 bottom 447，卡底 445）。◀ ▶ 同頁點的頂部剛好 4px。所以紅。

### TC-FE-SKILLMENU-ICON

原因：emoji 墨水大約 35×38，溢出 28px 圖示盒。盒到技能名的 flex gap 係 6px，但字形右緣越過個盒 7px，所以字形到名的間距係 **-1px**。繃帶、急救、盾擊、必殺都係咁，其餘技能一樣。

步驟：1280×720。學齊 22 個技能，逐頁量每一個 `.skill-icon`。字形用 DOM Range 包住圖示文字節點的 client rect。

預期：

- 盒闊 ≥ 36px。computed `font-size` ≥ 28px（維持 28，唔放大字）
- 字形橫向喺盒裡面，容差 0.5px
- 字形四邊都喺卡裡面，容差 0.5px
- 字形同 `.skill-name`、`.skill-desc` 唔重疊（相交寬同高都要 ≤ 0.5px）
- 圖示盒右緣到 `.skill-name` 左緣 ≥ 6px，而且字形右緣到 `.skill-name` 左緣都 ≥ 6px
- 字形因為字體度量高過個盒（38 > 28）唔要求垂直收進個盒。只要仍然喺卡裡面、又唔撞到名同說明

`8ac7b0d` 量到（22/22）：盒 **28×28**，字級 28px，字形 **35×38**。盒內橫向 inset 左 0、右 **-7**。盒到名 **6px**，字形到名 **-1px**。字形同名重疊 x **1px**、y 24.188px；同說明重疊 x 35px、y **3px**。字形仍然喺卡內（上 7.375、下 26.625、左 10）。所以紅。

### TC-FE-SKILLMENU-DOTS

原因：3 頁或以上（`:has(.dot:nth-child(3))`）每點闊 26px。決定：點只做指示，`pointer-events: none`。翻頁只靠 ◀ ▶（≥ 44×44）。唔要求點變大。

13 個技能的合成小朋友：探險公會 Lv1、健身室 Lv4、農場 Lv1、商店 Lv1、圖書館 Lv2、醫院 Lv5、燈塔 Lv1、天文台 Lv1。學到 13 招，`ceil(13/6) = 3` 頁。22 招係 4 頁。

步驟：1280×720。兩個小朋友都打開選單。

預期：

- 點數 = 頁數。`aria-current="page"` 的點對應 `#pageLabel` 的頁碼
- 每一粒 `.dot`，以及唔包含 `#btnPrev`／`#btnNext` 的容器（`#pageDots`），computed `pointer-events` 係 `none`。`.skill-pager` 含 ◀ ▶，唔要求 `none`
- `document.elementFromPoint` 打中點中心時，目標唔係 `.dot`
- 用真實滑鼠撳點中心（唔好用 locator click，嗰個會無視 `pointer-events`），`#pageLabel` 唔變。第 1 頁同最後一頁都試
- ◀ ▶ 仍然 ≥ 44×44，而且可以由 1 去到 N 再返到 1

`8ac7b0d` 量到：13 技能 3 點、22 技能 4 點，3 頁或以上每點 **26×44**。點同 `#pageDots` 都係 `pointer-events: auto`。`elementFromPoint` 打中 `BUTTON.dot`。第 1 頁撳第 2 點：13 技能 `1 / 3` → `2 / 3`，22 技能 `1 / 4` → `2 / 4`。◀ ▶ 仍然 44×44，而且 1→N→1 仍然得。所以紅。

## Case id

| id | 期望（未改產品時） |
|----|-------------------|
| TC-FE-SKILLMENU-BAR | 紅。指令列仍係攻擊／逃走加個別技能掣 |
| TC-FE-SKILLMENU-OPEN | 紅。冇 `#btnSkill`／`#skillPanel` |
| TC-FE-SKILLMENU-PAGE6 | 紅。6 個技能只露出一部分，冇 `1 / 1` |
| TC-FE-SKILLMENU-PAGE8 | 紅。8 個技能去唔到第 2 頁的 2 張卡 |
| TC-FE-SKILLMENU-CARDS | 紅。冇卡顯示名、MP、說明 |
| TC-FE-SKILLMENU-BROKE | 紅。冇「MP 不夠」的禁用卡 |
| TC-FE-SKILLMENU-CAST | 紅。唔能夠由選單施放蓄力 |
| TC-FE-SKILLMENU-VITALS | 紅。冇 `#playerVitals` |
| TC-FE-SKILLMENU-LAYOUT | 紅。冇選單可以量度 |
| TC-FE-SKILLMENU-ENEMY-VISIBLE | 紅。未有 `#skillPanel` 可以同敵人名牌比。3 隻同 1 隻野狼各一條。選單出現之後，每隻 `.m-name`／`.m-hp-bar`／`.m-hp-text` 同選單交集要係 0 px²，選單底邊高過最高名牌或血條至少 8px。精靈可以遮。 |
| TC-FE-SKILLMENU-CLOSE | 紅。冇返回／關閉 |
| TC-FE-SKILLMENU-TYPE | 紅。卡名 20px（要 ≥ 22）、說明 13px（要 ≥ 15）、圖示 24px 喺 28×24（要字級 ≥ 28 同盒子 ≥ 28×28）、padding 3px 4px（要上下 ≥ 6、左右 ≥ 8）。6 技能、8 技能第 2 頁、22 技能逐頁。 |
| TC-FE-SKILLMENU-NOSQUEEZE | 紅。main 冇選單。假綠：負 `letter-spacing`（`7e00b66` 說明 -0.14em）唔准用來塞 15px。字距、字詞距 ≥ 0；唔好縮放；`font-stretch` 100%；說明唔好 `ellipsis` 或被裁；每個 CJK 字寬 ≥ 0.95×字級。 |
| TC-FE-SKILLMENU-TITLE | 紅。標題 22px（要 ≥ 26）、頁碼 16px（要 ≥ 20）、返回寬度未到 80px。◀ ▶ ✕ 已係 44×44。 |
| TC-FE-TOAST-MENU-ONELINE | 紅。3 隻同 1 隻野狼。選單打開時兩行訊息同 `#skillPanel` 交集 9963 px²，而且唔係單行省略。 |
| TC-FE-TOAST-NO-SHIFT | 紅。選單收住時長句將卡推低 14.375px（main 24px），`.m-hp-text` 同 `.kt-command-bar` 交集 711.984 px²（main 2127 px²）。 |
| TC-FE-SKILLMENU-PANEL-RECT | 守衛。`ee8a3eb` 應過：面板 left 332、top 141、right 980、bottom 461，各 ±2。main 未有面板，所以紅。 |
| TC-FE-SKILLMENU-INSET | 紅。`8ac7b0d` 左右 padding 4px（要 ≥ 12）。內線 = border 8px + inset spread 6px（冇偽元素），離邊 14px。技能左 -2、✕ 右 -2、卡左右 -2、第三行卡底 2px（要每邊 ≥ 4）。卡闊 309（要 ≤ 304） |
| TC-FE-SKILLMENU-ICON | 紅。`8ac7b0d` 盒 28×28、字形 35×38、字形到名 -1px（盒到名 6px）。要盒闊 ≥ 36、字級 ≥ 28、字形橫向喺盒內、到名 ≥ 6px、唔撞名同說明。垂直溢出個盒可以，但要喺卡內 |
| TC-FE-SKILLMENU-DOTS | 紅。13 技能 3 頁、22 技能 4 頁。點同 `#pageDots` 係 `pointer-events: auto`，撳點會翻頁。要 `none`，而且 `elementFromPoint` 唔打中點。◀ ▶ 維持 ≥ 44×44。唔要求點變大 |
| TC-API-SKILL-FORMAL | 疾風斬、強光紅（含「唔」）。盾擊紅：要正好「物理攻擊，下一次受到的傷害減半」。其餘書面語過 |
| TC-API-SKILL-FORMAL-API | 同上，兩個 API。盾擊兩個 payload 都要正好嗰句 |
| TC-API-SKILL-FORMAL-MIGRATE | afbc1a6：疾風斬、強光仍然含「唔」；金錢砸整行唔見（冇「銀行」）；挑釁 id 8 改名盾擊後說明仍係舊句。main `3b0a48a`：舊盾擊句遷移後未變新句；疾風斬、強光仍然含「唔」 |
| TC-API-SKILL-FORMAL-MIGRATE-KEEP | 綠。小朋友行同已學 id 保留 |
| TC-API-MEAL-MP-BALANCED | 紅。傷害 5、HoT 14 仍在，MP 未加 5 |
| TC-API-MEAL-MP-SKEWED | 紅。傷害 35、HoT 14 仍在，MP 未加 5 |
| TC-API-MEAL-MP-CAP | 紅。MP 停喺 max−cost，未頂到 max |
| TC-API-MEAL-MP-DESC | 紅。說明有「回復」但冇「MP」。唔要求數字 5 |
| TC-API-MEAL-MP-DESC-MIGRATE | 紅。遷移後說明仍冇「MP」。唔要求數字 5 |
| TC-API-SKILL-MEAL | 紅（ intentional 更新）。回血斷言未走到；MP 要加 5 |
