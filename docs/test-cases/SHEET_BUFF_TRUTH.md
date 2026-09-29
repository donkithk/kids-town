# SHEET-BUFF-TRUTH — `#sheetBuff` 要等於真實效果

> **狀態**：UI 紅、API 錨點綠（見 [`FRONTEND_E2E_STATUS.md`](FRONTEND_E2E_STATUS.md) 最新一節）。  
> **範圍**：測試同目錄。唔改產品。七個未接線機制唔好喺呢輪實作。  
> **Fixture**：空庫 SQLite、合成帳號（`test_fe_kid`／PIN `1357`，API 用 `test_kid_a`／PIN `1357`）。唔好抄 production DB，唔好用真密碼。  
> **基線**：`main` `8ed2720`（#42–#45 已合併：場景 4 `#sheetBuff` 有繁體標籤、`#sheetFns .fn` 係 0、`#upgradeConfirm` 係 `div.gsw.stage` 最後一個元素子節點）。

`#sheetBuff` 而家講大話：寫咗後端冇做、或者做得唔同嘅效果。面板文字要等於真實效果。

後端核對（`backend_v2.py`，唔好只信假設）：

| `buff_type` | 建築 | 真實效果 |
|----|----|----|
| `task_bonus` | 圖書館 | `award_task_drops` 用 `get_building_buff(..., 'task_bonus')` 加 `experience_bonus`。基礎 XP 係 `max(5, points//2)`。金幣／`points_awarded` 唔加呢個數。唔係星星。 |
| `discount` | 商店 | `discounted_gold_cost` 只俾 `place_building` 同 `upgrade_building` 嘅金幣。`floor(cost * buff_vals[level-1])`，材料數量唔打折。探險入場費、任務金幣獎勵都唔用呢個折扣。 |
| `daily_gold` | 農場 | `POST /api/kids/<id>/farm/claim` 每個 `Asia/Hong_Kong` 日一次，金額係 `buff_vals[level-1]`。同日第二次 `400 already_claimed_today`，金幣唔再加。 |
| `streak_protect`、`build_speed`、`expedition_recovery`、`unlock_explore`、`explore_range`、`expedition_gold`、`discovery_rate` | 其餘七座 | `get_building_buff` 冇人傳呢七個 type。`unlock_explore` 只喺 `has_active_guild` 當「有冇座公會」嘅閘，唔讀 `buff_vals`。面板唔好顯示效果數值，要寫「未開放」。 |

`buff_vals[level-1]` 同 `get_building_buff` 同一個 index。

仍然要守、呢輪唔改斷言：

- `#sheetFns .fn` 數量係 0（`TC-FE-TOWN-UX-SHEET-BUFF-01`／`02`）。
- `#upgradeConfirm` 係 `div.gsw.stage` 最後一個元素子節點（`TC-FE-TOWN-UX-UPGRADE-CONFIRM-01`）。
- `SHEET-BUFF-01` 喺圖書館 `task_bonus` Lv.2 要求「任務多經驗 +4」（`buff_vals[1]`，唔係 Lv.1 嘅 2）。工坊唔再做數字合約。

舊 ZH 鎖定文案已經改走，原因見下面「改過嘅舊斷言」。

---

## SHEET-BUFF-TRUTH-01 — 圖書館係任務多經驗，唔係星

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-01 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_library`）。API：`tests/test_sheet_buff_truth.py::test_sheet_buff_truth_api_library_bonus_is_experience_not_stars` |
| **前置** | 空庫。只種圖書館 `(4,1)` Lv.1、`stored=0`。`buff_type=task_bonus`，`buff_vals=[2,4,6,10,15]`，所以而家係 **2**。 |
| **真實效果** | 完成 10 分任務：`experience_gained=5`，`experience_bonus=2`，`experience_total=7`，`points_awarded=10`。金幣只加 10，唔加 2。 |
| **預期面板** | `#sheetBuff` 文字同 `aria-label` 等於「任務多經驗 +2」。唔好有 ⭐、星、或者「任務多星」。撳 `#sheetBuff` 之後，如果 `#sheetNote` 重述加成，都要係呢句，唔好抄星。`#sheetFns .fn` 係 0。 |
| **main 預期** | API **綠**（效果已經係經驗）。UI **紅**：而家係「任務多星 +2⭐」。 |

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

## SHEET-BUFF-TRUTH-05 — 未接線嘅七種要寫「未開放」

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-05 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_unwired`） |
| **前置** | 每次只種一座、`stored=0`、`(4,1)`。工坊 Lv.3（`build_speed`，`buff_vals[2]=4`）。健身室 Lv.1（`streak_protect`，值 1）。其餘 Lv.1：醫院、探險公會、燈塔、競技場、天文台。 |
| **真實效果** | 呢七個 type 冇 `get_building_buff` 呼叫。工坊唔改變升級金幣（冇商店時仍然係 `level×100`）。健身室唔加任務 XP。公會閘唔讀 `buff_vals`。 |
| **預期面板** | 每座 `#sheetBuff` 文字同 `aria-label` 等於「未開放」，唔好帶 `buff_vals` 嘅效果數值（唔好 `×N`、`+N`、折、⭐）。`#sheetBuff` 同 `#sheetNote` 都唔好再出現「漏打卡都唔斷」或者「建築速度 ×」（`×`／`x`／`X`）。撳 `#sheetBuff` 之後，note 如果重述加成，都要係「未開放」。`#sheetFns .fn` 係 0。 |
| **main 預期** | UI **紅**。健身室而家係「連續保護 ×1 漏打卡都唔斷」。工坊 Lv.3 而家係「建築速度 ×4」。其他座顯示各自嘅效果句（例如「解鎖探險」「探險回復 ×2」），唔係「未開放」。 |

---

## SHEET-BUFF-TRUTH-06 — 未消費嘅 buff 唔好宣稱效果

| 欄 | 內容 |
|----|------|
| **ID** | SHEET-BUFF-TRUTH-06 |
| **優先級** | P0 |
| **建議模組** | UI：`tests/test_frontend.py`（`-k sheet_buff_truth_guard`）。API：`tests/test_sheet_buff_truth.py::test_sheet_buff_truth_api_only_three_buff_types_are_consumed` |
| **前置** | 十座建築逐座打開（同一張表，見本檔開頭）。消費集合由 `backend_v2.py` 入面 `get_building_buff(..., 'type')` 嘅字面量算出，唔好手寫死之後同後端脫節。 |
| **真實效果** | 消費集合係 `task_bonus`、`discount`、`daily_gold`。其餘 type 唔傳入 `get_building_buff`。 |
| **預期面板** | 消費集合入面：`#sheetBuff` 等於上面 01／02／03 嘅誠實句（農場仲要有「領取」）。集合外面：等於「未開放」，而且唔好出現效果數值、「漏打卡都唔斷」、「建築速度 ×」。 |
| **main 預期** | API **綠**（集合的確係三個；工坊唔改升級金幣；健身室 `experience_bonus=0`）。UI **紅**：未消費嘅座仍然顯示效果句。 |

---

## 改過嘅舊斷言

| 舊 ID | 點改 | 點解 |
|----|----|----|
| `TC-FE-TOWN-UX-SHEET-BUFF-ZH-01` | 唔再要求「建築速度 ×4」。改為「未開放」，並且 `#sheetBuff`／`#sheetNote` 唔好有「建築速度 ×」。 | `build_speed` 冇後端消費。舊斷言鎖死咗假效果。 |
| `TC-FE-TOWN-UX-SHEET-BUFF-ZH-02` | 唔再要求「連續保護 ×1」加「漏打卡都唔斷」。改為「未開放」，並且唔好再出現「漏打卡都唔斷」。 | `streak_protect` 冇後端消費。舊旁白描述咗一個未實作嘅保護。 |
| `TC-FE-TOWN-UX-SHEET-BUFF-01` | 數字合約由工坊 `build_speed` Lv.3（要見到 4／`×4`）搬去圖書館 `task_bonus` Lv.2。`#sheetBuff` 文字同 `aria-label` 要等於「任務多經驗 +4」（`buff_vals[1]`，唔係 `buff_vals[0]=2`，亦唔係種子「任務 +2⭐」）。零 `.fn` 仍然要。 | 工坊未接線，要求「建築速度 ×4」同 ZH-01／TRUTH-05 嘅「未開放」打架。#48 只係因為呢條舊斷言紅。 |
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
