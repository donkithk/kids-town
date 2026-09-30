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

## 書面語

常數 `tests/skill_menu_spec.py` 的 `COLLOQUIAL_CHARS`：

`嘅` `咩` `啲` `唔` `冇` `係` `喺` `佢` `嘢` `畈`

新鮮庫 22 個技能、開戰 `skills[].description`、`GET /api/kids/<id>/skills` 的 `description`、舊庫遷移之後，全部唔好含上面任何一字。每個技能一個 case。

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

說明（種子同舊庫遷移之後，以及上面兩個 API）要含「回復」同「MP」，並且書面語。

`TC-API-SKILL-MEAL` 的 MP 斷言已改成上面公式。回血幅度、Lv5 ≥ Lv1、第 4 回合停止，維持原案。

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
| TC-FE-SKILLMENU-CLOSE | 紅。冇返回／關閉 |
| TC-API-SKILL-FORMAL | 疾風斬、強光紅（含「唔」）；其餘書面語過 |
| TC-API-SKILL-FORMAL-API | 同上，兩個 API |
| TC-API-SKILL-FORMAL-MIGRATE | 遷移後疾風斬、強光仍然含「唔」。金錢砸整行唔見：afbc1a6 冇「銀行」，`seed_building_defs` 見目錄非空就返回，`seed_skill_defs` 就跳過金錢砸 |
| TC-API-SKILL-FORMAL-MIGRATE-KEEP | 綠。小朋友行同已學 id 保留 |
| TC-API-MEAL-MP-BALANCED | 紅。傷害 5、HoT 14 仍在，MP 未加 5 |
| TC-API-MEAL-MP-SKEWED | 紅。傷害 35、HoT 14 仍在，MP 未加 5 |
| TC-API-MEAL-MP-CAP | 紅。MP 停喺 max−cost，未頂到 max |
| TC-API-MEAL-MP-DESC | 紅。說明有「回復」但冇「MP」 |
| TC-API-MEAL-MP-DESC-MIGRATE | 紅。遷移後說明仍冇「MP」 |
| TC-API-SKILL-MEAL | 紅（ intentional 更新）。回血斷言未走到；MP 要加 5 |
