# SHEET-BUFF-TRUTH — `#sheetBuff` 要等於真實效果

> **狀態**：UI 紅、API 錨點綠（見 [`FRONTEND_E2E_STATUS.md`](FRONTEND_E2E_STATUS.md) 最新一節）。  
> **範圍**：測試同目錄。唔改產品。七個未接線機制唔好喺呢輪實作。  
> **Fixture**：空庫 SQLite、合成帳號（`test_fe_kid`／PIN `1357`，API 用 `test_kid_a`／PIN `1357`）。唔好抄 production DB，唔好用真密碼。  
> **基線**：`main` `8ed2720`（#42–#45 已合併：場景 4 `#sheetBuff` 有繁體標籤、`#sheetFns .fn` 係 0、`#upgradeConfirm` 係 `div.gsw.stage` 最後一個元素子節點）。

`#sheetBuff` 要等於鎖定效果。圖書館唔再係任務經驗。詳細被動同技能見 [`PASSIVE_AND_SKILLS.md`](PASSIVE_AND_SKILLS.md)。

| 建築 | 面板 |
|----|----|
| 圖書館 | `知識 +N（<戰鬥 HUD 嘅 matk 標籤> +M）`。N 係 `calc_ability_buffs` 嘅差，M 係 `calc_battle_stats` 嘅差。唔好「任務多經驗」，亦唔好手寫「+2×等級」。 |
| 商店 | `起屋／升級金幣` + `buff_vals[level-1]` 嘅折。 |
| 農場 | `每日金幣 +N`（尾後 🪙 可以留），另有「領取」／「今日已領」。 |
| 健身室 | `臂力 +N（<戰鬥 HUD 嘅 atk 標籤> +M）` |
| 工坊 | `創意 +N（<戰鬥 HUD 嘅 crt 標籤> +M）` |
| 競技場 | `臂力 +N（<atk 嘅 HUD 標籤> +M）、速度 +N（<dodge 嘅 HUD 標籤> +M）`。兩種能力都要。 |
| 探險公會 | `勇氣 +N（<戰鬥 HUD 嘅 def 標籤> +M）` |
| 天文台 | `技能：流星雨（魔法攻擊全體敵人）`。尋寶機率未定，唔好寫百分比。 |
| 醫院 | `技能：繃帶（小回復）` |
| 燈塔 | 要有「魔法攻擊」同「之後 2 次怪物攻擊打唔中」。唔好「命中率下降」。 |
| 銀行 | `技能：金錢砸（每次 10 金幣，傷害約普攻 3 倍）`（測試庫先插入定義） |
| 未知 `buff_type` | 正好「未開放」，唔好帶 `buff_vals` 數字（`TC-FE-SHEET-UNWIRED-01`） |

仍然要守：

- `#sheetFns .fn` 數量係 0。
- `#upgradeConfirm` 係 `div.gsw.stage` 最後一個元素子節點。
- 商店／農場嘅數字仍然讀 `buff_vals[level-1]`（`TC-FE-SHEET-BUFFVAL-01`）。

舊 ZH 鎖定文案已經改走，原因見下面「改過嘅舊斷言」。

---

## SHEET-BUFF-TRUTH-01 — 圖書館係知識被動，唔係任務經驗

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-01 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_library`）。API：`tests/test_sheet_buff_truth.py::test_sheet_buff_truth_api_library_bonus_is_experience_not_stars` |
| **前置** | 空庫。只種圖書館 `(4,1)` Lv.1、`stored=0`。 |
| **真實效果** | 完成 10 分任務：`experience_gained=5`，`experience_bonus=0`，`experience_total=5`，`points_awarded=10`。知識被動走戰鬥 `player_matk`，見 `TC-API-BLD-PASSIVE-LIB`。 |
| **預期面板** | `#sheetBuff` 文字同 `aria-label` 等於「知識 +N（戰鬥 HUD 標籤 +M）」。N、M 跟 `TC-FE-SHEET-TWO-LAYER`，由函數差計，唔寫死「知識 +2」。唔好讀圖書館 `buff_type`／`buff_vals`。唔好「任務多經驗」、⭐、星、或者「任務多星」。`#sheetFns .fn` 係 0。 |

---

## SHEET-BUFF-TRUTH-02 — 商店只係起屋／升級金幣折扣

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-02 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_shop`）。API：`tests/test_sheet_buff_truth.py::test_sheet_buff_truth_api_discount_is_build_and_upgrade_gold_only` |
| **前置** | 只種商店 `(4,1)` Lv.1。`buff_vals=[0.9,0.85,0.8,0.75,0.7]`，Lv.1 係 **0.9**。 |
| **真實效果** | 有商店再建健身室：金幣 `floor(200×0.9)=180`，木材仍扣 10、磚仍扣 5。升級嗰座 Lv.1 健身室：金幣 `floor(100×0.9)=90`，材料仍係 `base×(level+1)`。區 1 探險費仍然 10，唔係 9。任務金幣仍然係任務 `points`，唔係九折。`discounted_gold_cost(` 只出現喺 helper、起屋、升級。 |
| **預期面板** | `#sheetBuff` 等於「起屋／升級金幣九折」（折數由 `buff_vals[level-1]` 推出：0.9 九折、0.85 八五折、0.8 八折、0.75 七五折、0.7 七折）。唔好寫「購物折扣」或者「獎勵」。`#sheetNote` 如果重述，都要係呢句。 |
| **main 預期** | API **綠**。UI **紅**：而家係「購物折扣 九折」。 |

---

## SHEET-BUFF-TRUTH-03 — 農場面板要有「領取」

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-03 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_farm_claim`） |
| **前置** | 只種農場 `(4,1)` Lv.1。`buff_vals=[5,10,15,25,40]`，而家係 **5**。清 `farm_claims`。金幣 > 0。 |
| **真實效果** | `POST /api/kids/<id>/farm/claim` 會加 5 金幣。前端而家冇入口。 |
| **預期面板** | `#sheetBuff` 係「每日金幣 +5」（尾後一個 🪙 可以留，因為真係金幣）。`#actionSheet` 入面要有一個可見、撳得嘅「領取」掣（按鈕文字或者 `aria-label`）。`#sheetFns .fn` 係 0。 |
| **main 預期** | UI **紅**：`#sheetBuff` 係「每日金幣 +5🪙」，面板冇「領取」。 |

---

## SHEET-BUFF-TRUTH-04 — 領完當日變「今日已領」，唔好加兩次

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-04 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_farm_once`）。API：`tests/test_sheet_buff_truth.py::test_sheet_buff_truth_api_farm_claim_once_per_day` |
| **前置** | 同 TRUTH-03。API 凍結 `2026-09-20 09:00+08:00`，金幣由 0 起。 |
| **真實效果** | 第一次 claim 200，金幣 +5，`points_log` reason `daily_gold` 一行。同日第二次 400 `already_claimed_today`，金幣唔變。 |
| **預期面板** | 撳「領取」之後，HUD 同 DB 金幣只加 5。面板出現「今日已領」，領取掣 disabled（或者個掣本身變成「今日已領」而且 disabled）。再撳一次唔好再加 5。 |
| **main 預期** | API **綠**。UI **紅**：冇「領取」，所以去唔到「今日已領」同「只加一次」。失敗原因係缺掣，唔係種子或登入。 |

---

## SHEET-BUFF-TRUTH-05 — 七座顯示真正被動或技能

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-05 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_unwired`） |
| **前置** | 每次只種一座、`stored=0`、`(4,1)`。工坊 Lv.3。其餘 Lv.1：健身室、醫院、探險公會、燈塔、競技場、天文台。 |
| **預期面板** | 健身室、工坊、探險公會、競技場係兩層數字（能力差同戰鬥屬性差，括號用戰鬥 HUD 嘅字）。醫院「技能：繃帶（小回復）」。燈塔要有「魔法攻擊」同「之後 2 次怪物攻擊打唔中」，唔好「命中率下降」。天文台「技能：流星雨（魔法攻擊全體敵人）」，唔好「尋寶機率」。唔好「未開放」，亦唔好舊句（漏打卡、建築速度 ×、探險回復、探險範圍、探險金幣、發現新區域、手寫「+2×等級」）。`#sheetFns .fn` 係 0。 |

---

## SHEET-BUFF-TRUTH-06 — 每座面板等於鎖定效果

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-06 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_guard`）。API：`tests/test_sheet_buff_truth.py::test_sheet_buff_truth_api_only_three_buff_types_are_consumed` |
| **前置** | 十座種子建築逐座打開。 |
| **真實效果** | `get_building_buff` 只可以留 `discount` 同 `daily_gold`。`task_bonus` 要離開呢個集合。工坊仍然唔改升級金幣。健身室仍然唔加任務 XP。 |
| **預期面板** | 每座等於本檔開頭嗰張表（農場仲要有「領取」）。 |

---

## 改過嘅舊斷言

| 舊 ID | 點改 | 點解 |
|----|----|----|
| `TC-FE-TOWN-UX-SHEET-BUFF-ZH-01` | 工坊 Lv.3 係兩層數字。唔好「建築速度 ×」，亦唔好「未開放」，亦唔好淨係「創意 +6」。 | 被動係創意，再加上轉換後嘅戰鬥數。 |
| `TC-FE-TOWN-UX-SHEET-BUFF-ZH-02` | 健身室 Lv.1 係兩層數字。唔好「漏打卡都唔斷」，亦唔好「未開放」，亦唔好淨係「臂力 +2」。 | 被動係臂力，再加上轉換後嘅戰鬥數。 |
| `TC-FE-TOWN-UX-SHEET-BUFF-01` | 圖書館 Lv.2 係兩層數字。零 `.fn` 仍然要。`buff_vals[level-1]` 搬去 `TC-FE-SHEET-BUFFVAL-01`。 | 「知識 +4」同「任務多經驗 +4」都唔再係成句。 |
| `TC-FE-TOWN-UX-SHEET-BUFF-02` | **冇改斷言**。仍然開工坊查零 `.fn` 同唔好 stub toast。唔再當佢同 01 共用「要見到數字 4」嘅前置。 | 02 從來唔查 buff 數值。 |
| `upgrade_cost`／`upgrade_confirm`／`store_ux` | **冇改**。 | `#upgradeConfirm` 仍然係 `div.gsw.stage` 最後一個元素子節點。 |

`tests/test_frontend.py` 入面舊嘅 `_zh_surface_problems` 唔再係預期文案。兩條 ZH 測試改呼叫未開放面板斷言。

---

## 點跑

```bash
python3 -m pytest tests/test_sheet_buff_truth.py -q --tb=short
python3 -m pytest tests/test_frontend.py -q -k sheet_buff_truth --tb=short
python3 -m pytest tests/test_frontend.py -q -k sheet_buff_zh --tb=short
python3 -m pytest tests/test_frontend.py -q -k 'sheet_buff and not sheet_buff_zh and not sheet_buff_truth' --tb=line
python3 -m pytest tests/test_frontend.py -q -k 'upgrade_cost or upgrade_confirm or scene4_upgrade_feature_and_hud or store_ux' --tb=line
```

`-k sheet_buff` 會一齊跑 01／02、ZH、同 TRUTH。淨係舊數字合約要用第三條。
