# Phase 1.5 入局包測試目錄（TDD RED — 先寫失敗測試）

> **狀態**：RED（產品碼**未**實作）。對照表見 [`PHASE1_5_ONBOARD_STATUS.md`](PHASE1_5_ONBOARD_STATUS.md)。  
> **Marker**：`phase1_5`（`python -m pytest tests/ -m phase1_5 -v`）。未用別名 `onboard`，避免兩套跑法。  
> **企劃**：[`GAMEPLAY_REDESIGN.md`](../GAMEPLAY_REDESIGN.md) §6.6 15 分鐘劇本、§7 新手包／公會成本、§9 Q3／Q4（用戶已拍板，見下）。  
> **Fixture**：空庫 seed；factory 合成帳戶。**禁止** copy `kids_town.db`。**禁止**真實 PIN。  
> **產品碼**：本目錄 PR **唔改** `backend_v2.py`／`index.html`。GREEN 另 PR。  
> **短征費用表**：維持 Phase 1 **10 / 20 / 30**（`P1-TC-EXP-01`–`04`）。本目錄**唔**改費用。

Pytest 模組：`tests/test_onboard.py`。常數：`tests/phase1_helpers.py`（`GUILD_COST_*`、`STARTER_*`）。

---

## 用戶已拍板（對齊 §6.6／§7／§9）

| Open Q | 決定 | Exact amounts |
|--------|------|----------------|
| **Q4 公會成本** | 降至 **150 金 + wood×10 + brick×5**，**NO gear**（`gear×0`；materials JSON **無** gear 需求鍵） | gold=`150`；`{"wood":10,"brick":5}` |
| **新手包** | 新 kid／新帳戶：`points=120` + `wood×8` + `brick×5`；flag `starter_granted` | 新鮮 `create-kid`：**恰好** 120／8／5（START-01 亦接受 wood≥8、brick≥5 若之後有額外掉落路徑；空庫新號必須剛好呢組） |
| **Q3 短征重複農** | **無限次**（費用剎車 only）。**唔**加每日探索上限 | 費用仍 10/20/30；claim 後同一區可再 start |

---

## A. 公會成本

### ONB-GUILD-01 — seed／defs 公會成本

| 欄 | 內容 |
|----|------|
| **ID** | ONB-GUILD-01 |
| **標題** | `building_defs` 探險公會 `cost_gold==150`；materials 為 wood×10 + brick×5；**無 gear 需求** |
| **優先級** | P0 |
| **建議模組** | `tests/test_onboard.py` |
| **前置** | 空庫 seed |
| **步驟** | 1. SQL `building_defs` WHERE name=探險公會 2. `GET /api/building-defs` 對同一座 |
| **預期** | `cost_gold==150`；JSON materials `wood==10`、`brick==5`；`gear` **不存在**或數量為 0（無 gear requirement）。API 列表與 seed 一致。 |

---

### ONB-GUILD-02 — 恰好 150 金 + 足夠木磚可放置

| 欄 | 內容 |
|----|------|
| **ID** | ONB-GUILD-02 |
| **標題** | 恰好 150 金 + wood≥10 + brick≥5（**唔使 gear**）place 公會 → 201；金幣／材料正確扣除 |
| **優先級** | P0 |
| **建議模組** | `tests/test_onboard.py` |
| **前置** | login `kid_a`；points=150；inventory wood=10、brick=5；無公會；無商店折扣 |
| **步驟** | `POST /api/kids/{id}/buildings` `def_id`=探險公會 |
| **預期** | 201；DB 有 1 行公會；points=0；wood=0；brick=0；**唔**要求扣 gear（測試唔發 gear） |

現況（故意紅）：seed 仍係 **600 金 + wood×25 + brick×20 + gear×10**，150/10/5 會 400。

---

### ONB-GUILD-03 — 149 金不足

| 欄 | 內容 |
|----|------|
| **ID** | ONB-GUILD-03 |
| **標題** | 149 金（木磚足夠新配方）→ insufficient 400；無 buildings 行；資源不變 |
| **優先級** | P0 |
| **建議模組** | `tests/test_onboard.py` |
| **前置** | points=149；wood=10；brick=5；無公會 |
| **步驟** | 同上 place |
| **預期** | 400；`error` 含 insufficient（`Insufficient resources`／`insufficient_gold`／`insufficient_resources` 皆可）；buildings 仍 0；points 仍 149；wood/brick 未扣 |

註：現況 149 金對舊成本 600 亦會 400，所以本 case **喺 main 可能已綠**。GREEN 之後仍必須因 **差 1 金（need 150）** 而失敗，唔可以因為誤把成本改成 ≤149 而 201。

---

## B. 新手包

### ONB-START-01 — create-kid 發新手包

| 欄 | 內容 |
|----|------|
| **ID** | ONB-START-01 |
| **標題** | 家長 session `POST /api/auth/create-kid` → points=120；wood≥8；brick≥5；`starter_granted` 已設 |
| **優先級** | P0 |
| **建議模組** | `tests/test_onboard.py` |
| **前置** | 空庫；家長已註冊並 login；**唔**用 `family` fixture 預先建好、再被 `set_kid_points` 蓋掉嘅 kid |
| **步驟** | create-kid（合成 username + PIN `1357`，非生產 PIN） |
| **預期** | 201；`kid.points==120`（DB 同 JSON）；inventory **恰好** wood=8、brick=5（空庫新號）；`starter_granted` 喺 create-kid JSON **或** `kids.starter_granted`（truthy / 1） |

現況（故意紅）：`INSERT INTO kids` 用 DEFAULT points=0；無材料；無 `starter_granted`。

---

### ONB-START-02 — 唔雙重發放

| 欄 | 內容 |
|----|------|
| **ID** | ONB-START-02 |
| **標題** | 已發放過嘅 kid 唔再加一次；第二個 create-kid（另一個仔女）各自拿一份 |
| **優先級** | P0 |
| **建議模組** | `tests/test_onboard.py` |
| **前置** | 家長 session；第一個 kid 已 create（應已有 starter） |
| **步驟** | 1. 第一個 kid PIN login（唔應再發）2. 同一家長再 create 第二個 kid 3. 讀兩個 kid 嘅 points／材料／flag |
| **預期** | Kid A 仍係 **120 / wood 8 / brick 5**（唔係 240／16／10）；Kid B **自己** 120／8／5 且 `starter_granted`；兩個 kid 獨立，唔共用一份、亦唔把 A 嘅包再加一次 |

---

## C. 短征可重複農（回歸；唔加每日上限）

### ONB-EXP-01 — claim 後同一區可再 start

| 欄 | 內容 |
|----|------|
| **ID** | ONB-EXP-01 |
| **標題** | claim 區 1 探索之後再 start 區 1 → 201（unlimited farm；無 daily explore cap） |
| **優先級** | P0 |
| **建議模組** | `tests/test_onboard.py`（風格同 `P1-TC-EXP-05`） |
| **前置** | 有未存倉公會；points 足夠兩次區 1 費用（10+10）；即時 duration 可 claim |
| **步驟** | start 區1 → 強制可 claim → `expedition/claim` → 補金幣 → 再 start 區1 |
| **預期** | 第二次 start **201**。**唔**引入每日探索次數上限。費用表仍 10/20/30（本 case 只跑區 1）。 |

現況：Phase 1 已綠（`P1-TC-EXP-05`）。本 case 係 Phase 1.5 **回歸**，預期喺 main **仍然綠**。

---

## 同 Phase 1 嘅關係

| Phase 1 case | 入局包之後 |
|--------------|------------|
| `P1-TC-MAT-03` 斷言公會 materials 含 **gear** | GREEN PR **必須一併改**呢條（新配方無 gear）。本 RED PR **唔改**，以免 `pytest -m phase1` 多一條紅。 |
| `P1-TC-EXP-01`–`04` 費用 10/20/30 | **保持** |
| `P1-TC-EXP-05` 可再農 | **保持**；ONB-EXP-01 重複斷言 |

---

## 手動／E2E 清單（雙重驗證 B — GREEN PR 先簽）

- [ ] 空庫家長建仔女，HUD 金幣 120、木頭 8、磚 5
- [ ] 用新手包金幣+木起圖書館（100+wood5）之後仍夠起公會（150+wood10+brick5）
- [ ] 起公會**唔使**齒輪
- [ ] 149 金不能起公會
- [ ] 區 1 短征 claim 後可再出發（無「今日已達上限」）

簽收格式見 `TDD_PROCESS.md`。本 RED PR 唔做 (B)。
