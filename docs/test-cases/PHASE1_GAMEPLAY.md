# Phase 1 遊戲循環測試目錄（先寫 pytest，後寫產品碼）

> **狀態**：GREEN（產品碼已實作）。`pytest -m phase1` = 39 passed / 1 failed（**P1-TC-CER-03** Phase 2 批核，故意留紅）。對照表見 [`PHASE1_GAMEPLAY_STATUS.md`](PHASE1_GAMEPLAY_STATUS.md)。  
> **Phase 1.5 入局包**（公會 150 金＋新手包 120／wood×8／brick×5）：另見 [`PHASE1_5_ONBOARD.md`](PHASE1_5_ONBOARD.md)，marker `phase1_5`。本目錄 **唔** 改短征費用表 10/20/30；可重複農仍由 **P1-TC-EXP-05** 覆蓋。  
> **依賴**：Phase 0 session／角色模型已存在；呢啲 case 全部用 **已登入** 嘅正確擁有者，另加註明嘅 401／403。  
> **企劃**：[`GAMEPLAY_REDESIGN.md`](../GAMEPLAY_REDESIGN.md) §6。  
> **Fixture**：空庫 seed 10 座建築；factory 發足夠金幣／材料；`freezegun` 測每日農場。  
> **P0** = Phase 1 合併前必須綠（循環誠實）；**P1** = 同批能做就做。

Session helper 同 Phase 0。金幣／建築操作一律 kid 或該家長。

---

## A. 建築 buff

### P1-TC-BUFF-01 — 圖書館 task_bonus 加 XP

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-01 |
| **標題** | 有 Lv.1 圖書館時，完成任務 XP = 基礎 + 2 |
| **優先級** | P0 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | login `kid_a`；起咗圖書館 level=1 `stored=0`；任務 points=10（基礎 XP=`max(5,10//2)=5`）；無其他 buff 建築 |
| **步驟** | 1. `POST /api/tasks/{id}/complete` 2. 讀 JSON 同 `kids.experience` |
| **預期** | `experience_gained==5`；`experience_bonus==2`；`experience_total==7`；DB experience +7；`points_awarded==10`（金幣**唔**加 2） |

---

### P1-TC-BUFF-02 — 無圖書館就無 bonus

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-02 |
| **標題** | 未起圖書館：`experience_bonus==0`，XP 只有基礎 |
| **優先級** | P0 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | kid 無圖書館；任務 points=10 |
| **步驟** | complete |
| **預期** | bonus=0；total=5；金幣 10 |

---

### P1-TC-BUFF-03 — 圖書館升級後用新表

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-03 |
| **標題** | Lv.2 `buff_vals[1]==4` |
| **優先級** | P0 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | 圖書館 level=2；任務 points=10 |
| **步驟** | complete |
| **預期** | `experience_bonus==4` |

---

### P1-TC-BUFF-04 — 存倉圖書館唔生效

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-04 |
| **標題** | `stored=1` 嘅圖書館唔加 XP |
| **優先級** | P1 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | 圖書館 stored=1 |
| **步驟** | complete |
| **預期** | bonus=0 |

---

### P1-TC-BUFF-05 — 農場每日金幣可領一次

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-05 |
| **標題** | Lv.1 農場 `POST /api/kids/<id>/farm/claim` +5，寫 points_log `daily_gold` |
| **優先級** | P0 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | 農場 Lv.1；points=0；凍結時間 `2026-09-18 10:00+08:00` |
| **步驟** | 1. claim 2. 再 claim 3. 時間調到 `2026-09-19 00:01+08:00` 再 claim |
| **預期** | 1：200，points=5。2：400 `already_claimed_today`，points 仍 5。3：200，points=10。未登入 claim → 401（可放 session 檔）。 |

---

### P1-TC-BUFF-06 — 無農場不能 claim

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-06 |
| **標題** | 無農場 → 400 `farm_required` |
| **優先級** | P0 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | 無 def_id 農場 |
| **步驟** | claim |
| **預期** | 400；金幣不變 |

---

### P1-TC-BUFF-07 — 商店折扣只減金幣

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-07 |
| **標題** | 已有商店 Lv.1 時，再建圖書館扣 90 金而非 100；木頭仍扣 5 |
| **優先級** | P0 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | 已有商店 Lv.1；points=200；wood=10；未有圖書館 |
| **步驟** | `POST .../buildings` def 圖書館 |
| **預期** | 201；points=110；wood=5；`points_log` amount=-90 |

---

### P1-TC-BUFF-08 — 起商店當下自己未享折扣

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-08 |
| **標題** | 第一座商店仍付全價 500（seed） |
| **優先級** | P1 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | 無商店；points 同材料足夠 seed 成本（注意材料正規化後 iron→gear） |
| **步驟** | place 商店 |
| **預期** | 扣 500 金，唔係 450 |

---

### P1-TC-BUFF-09 — get_building_buff helper 單測

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-BUFF-09 |
| **標題** | 純函數／DB helper：無建築 None；Lv.3 農場 daily_gold=15 |
| **優先級** | P0 |
| **建議模組** | `tests/test_building_buffs.py` |
| **前置** | 可直接打 DB 起農場 level=3 |
| **步驟** | 呼叫 `get_building_buff(kid_id,'daily_gold', db)` 及 `'task_bonus'` |
| **預期** | 15 同 None |

---

## B. 材料 id 一致性

### P1-TC-MAT-01 — 探險 claim 只產出 canonical id

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-MAT-01 |
| **標題** | `expedition/claim` 回應同 inventory **無** `iron`／`star_shard` 鍵 |
| **優先級** | P0 |
| **建議模組** | `tests/test_materials_ids.py` |
| **前置** | 有公會；start 區 1 短征 `duration` 即時可 claim；mock `random` 令所有材料都掉 |
| **步驟** | claim |
| **預期** | rewards 鍵 ⊆ `{wood,brick,glass,gear,gem,dragon_scale,fur}`（fur／dragon_scale 可選）；**禁止** `iron`、`star_shard`、`star_fragment`、`star_stone`、`mystery_box`（Phase 1 停發） |

---

### P1-TC-MAT-02 — 舊 id 寫入被正規化

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-MAT-02 |
| **標題** | 內部 add `iron` → 存成 `gear` 數量合併 |
| **優先級** | P0 |
| **建議模組** | `tests/test_materials_ids.py` |
| **前置** | 已有 gear×2；呼叫正規化 helper 或任何仍接受舊 id 嘅內部函數 `add_item(kid,'iron',3)` |
| **步驟** | add iron×3 |
| **預期** | 無 iron 行；gear×5 |

---

### P1-TC-MAT-03 — 商店配方鍵 ⊆ canonical

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-MAT-03 |
| **標題** | `GET /api/materials/defs` 含 wood/brick/glass/gear/gem；所有 `building_defs.materials` JSON 鍵合法 |
| **優先級** | P0 |
| **建議模組** | `tests/test_materials_ids.py` |
| **前置** | 空庫 seed |
| **步驟** | 1. GET materials/defs 2. SELECT building_defs |
| **預期** | defs 至少五 canonical；每座建築 materials 鍵屬於 canonical；公會 **唔係** `{}`（Phase 1.5：seed 新庫 wood×10 + brick×5，**無 gear 鍵**） |

---

### P1-TC-MAT-04 — 任務掉落同 HUD 集合一致

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-MAT-04 |
| **標題** | `award_task_drops`／complete 嘅 `material_drops` 只含 HUD 四格或 gem |
| **優先級** | P0 |
| **建議模組** | `tests/test_materials_ids.py` |
| **前置** | seed `random`；complete 高分任務多次（或直接測 `MATERIAL_POOLS` 常數） |
| **步驟** | 斷言 `MATERIAL_POOLS` 所有 id canonical；complete 回應 drops ⊆ canonical |
| **預期** | 無 `iron` |

---

### P1-TC-MAT-05 — Boss 仍耗 gem 唔係 glass

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-MAT-05 |
| **標題** | 召喚 Boss 扣 `gem`×1 |
| **優先級** | P1 |
| **建議模組** | `tests/test_materials_ids.py`（或現有 `test_boss.py` 改空庫後加） |
| **前置** | gem×1、glass×10；符合現有召喚條件嘅 kid |
| **步驟** | 召喚成功 |
| **預期** | gem=0；glass 仍 10 |

---

## C. 區域 4–5 戰鬥行為

### P1-TC-REG-01 — 區 1–3 有怪物可開戰

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-REG-01 |
| **標題** | 足夠等級時 region 1/2/3 `battle-start` 唔係 404 `No monster` |
| **優先級** | P0 |
| **建議模組** | `tests/test_region_lock.py` |
| **前置** | 有公會；kid level ≥ `region_unlock_level(3)`；每日未打 |
| **步驟** | 對 region_id=1,2,3 POST battle-start |
| **預期** | 200／201；body 有 monsters 陣列。允許因其他業務 400（已打過），但 **禁止** 404 No monster |

---

### P1-TC-REG-02 — 區 4 明確鎖定（本企劃揀 locked，唔 seed 假怪）

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-REG-02 |
| **標題** | region 4 battle-start → 400 `error=region_locked`，唔係 404 |
| **優先級** | P0 |
| **建議模組** | `tests/test_region_lock.py` |
| **前置** | 有公會；level 很高（排除 level gate 誤報） |
| **步驟** | POST battle-start `region_id=4` |
| **預期** | 400；JSON `error=='region_locked'` 且 `region_id==4`；**唔**建立 running expedition |

---

### P1-TC-REG-03 — 區 5 同樣 locked

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-REG-03 |
| **標題** | region 5 同 REG-02 |
| **優先級** | P0 |
| **建議模組** | `tests/test_region_lock.py` |
| **前置** | 同上 |
| **步驟** | region_id=5 |
| **預期** | 400 `region_locked` |

---

### P1-TC-REG-04 — 探索區 4 start 亦鎖定

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-REG-04 |
| **標題** | `expedition/start` region 4 explore → `region_locked` |
| **優先級** | P0 |
| **建議模組** | `tests/test_region_lock.py` |
| **前置** | 有公會、有金幣 |
| **步驟** | start explore region 4 |
| **預期** | 400 locked；金幣未扣 |

---

## D. unlock_region 強制

### P1-TC-UNL-01 — 未探區 3 不能起燈塔

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-UNL-01 |
| **標題** | `unlock_region=r3` 嘅燈塔：無區 3 探索／勝利時 place → 400 |
| **優先級** | P0 |
| **建議模組** | `tests/test_unlock_region.py` |
| **前置** | 金幣材料夠燈塔；`explored_regions` 無 3；無區 3 戰鬥勝 |
| **步驟** | POST buildings 燈塔 |
| **預期** | 400 `error` 含 region 或 `unlock_region`；無新 buildings 行 |

---

### P1-TC-UNL-02 — 滿足 r3 後可以起燈塔

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-UNL-02 |
| **標題** | 插入 explored region_id=3 之後燈塔 201 |
| **優先級** | P0 |
| **建議模組** | `tests/test_unlock_region.py` |
| **前置** | 資源夠；explored 3 |
| **步驟** | place 燈塔 |
| **預期** | 201 |

---

### P1-TC-UNL-03 — 競技場／天文台喺區 4–5 locked 期間買唔到

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-UNL-03 |
| **標題** | 即使作弊插入 explored 4，若產品仍 `region_locked` 內容未上，place 競技場仍 400 |
| **優先級** | P1 |
| **建議模組** | `tests/test_unlock_region.py` |
| **前置** | 資源夠競技場 |
| **步驟** | place 競技場 |
| **預期** | 400 `region_locked`（企劃：未開放區嘅建築一併鎖） |

---

## E. 任務完成回應欄位 + 前端斷言策略

### P1-TC-CER-01 — complete JSON 契約

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-CER-01 |
| **標題** | 200 body 含 `points_awarded`、`experience_gained`、`experience_bonus`、`experience_total`、`material_drops`、`achievements`、`pending_approval`、`kid.experience_in_level`、`kid.experience_for_next` |
| **優先級** | P0 |
| **建議模組** | `tests/test_task_ceremony.py` |
| **前置** | 普通任務；無批核 |
| **步驟** | complete |
| **預期** | 以上鍵存在；型別：int／list／bool；`pending_approval is False`；XP **無**寫入 `points_log`（reason 唔含 `experience_gained`） |

---

### P1-TC-CER-02 — 第一個任務成就出現喺回應

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-CER-02 |
| **標題** | 新號第一次 complete 後 `achievements` 含 `first_task` |
| **優先級** | P0 |
| **建議模組** | `tests/test_task_ceremony.py` |
| **前置** | 新 kid 零成就 |
| **步驟** | complete |
| **預期** | list 非空；有 badge `first_task` |

---

### P1-TC-CER-03 — 批核開啟時唔入帳（若 setting API 尚未做，skip 直到 Phase 2——**唔好 silent skip**；未做則本 case 標 Phase 2 依賴）

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-CER-03 |
| **標題** | `require_approval=true` 時 complete 後金幣／XP 不變、`pending_approval=true` |
| **優先級** | P1 |
| **建議模組** | `tests/test_task_ceremony.py` |
| **前置** | 家庭開啟批核（API 名以實作為準） |
| **步驟** | complete；再 approve |
| **預期** | complete 後 points 不變；approve 後先至加上 `points_awarded` |

---

### P1-TC-CER-FE-01 — 前端儀式策略（文件化；能自動化就自動化）

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-CER-FE-01 |
| **標題** | `completeTask()` 必須讀 XP／材料／成就，唔只 toast 金幣 |
| **優先級** | P0（行為）；自動化 **P1** 直到 Playwright 唔綁 Windows |
| **建議模組** | `tests/test_frontend.py` 或 `tests/test_frontend_ceremony.py` |
| **前置** | mock `/api/tasks/1/complete` 返回 CER-01 形狀，含 `experience_total=7`、`material_drops:["wood"]`、成就 |
| **步驟** | 觸發完成 |
| **預期** | 可見字包含 XP 數字同材料（木材／wood／🪵 任一）；金幣；成就標題或 icon。**策略**：1) Playwright mock route 最穩（本 case）；2) 若未有瀏覽器，用正則／AST 測 `index.html` 嘅 `completeTask` **引用** `experience_total` 或 `experience_gained` 同 `material_drops`——呢個係弱斷言；3) **較強 (A)**：`TC-FE-CEREMONY-01` 真實 complete、唔 mock。禁止只 grep 過關當 (A) 完成儀式 UX。(B) 見 [`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md)。 |

---

## F. XP 條公式 helper

### P1-TC-XP-01 — calc_level 同 EXP_PER_LEVEL=25

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-XP-01 |
| **標題** | 總經驗 0→Lv1 remainder 0；25→Lv2 rem 0；24→Lv1 rem 24；75→Lv3 rem 0 |
| **優先級** | P0 |
| **建議模組** | `tests/test_xp_bar.py` |
| **前置** | import `calc_level`, `EXP_PER_LEVEL`, `exp_for_next_level` |
| **步驟** | 直接呼叫（三角：升 Lv 扣 `level*25`） |
| **預期** | 同現有後端行為；`exp_for_next_level(1)==25`；`exp_for_next_level(2)==50`。**唔好**改成 100 去遷就舊 HUD。 |

---

### P1-TC-XP-02 — HUD 百分比 helper

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-XP-02 |
| **標題** | `xp_bar_percent(experience_in_level, experience_for_next)` 用 in-level 唔用總經驗／(level*100) |
| **優先級** | P0 |
| **建議模組** | `tests/test_xp_bar.py` |
| **前置** | 新增 helper（後端或共用純函數，前端應呼叫 GET `/experience` 欄位） |
| **步驟** | percent(0,25)==0；percent(25,25)==100（或 100 封頂）；percent(12,25) 約 48 |
| **預期** | 永遠 `min(100, round(in_level/for_next*100))`；`for_next==0` 時定義為 100 或 0（寫死一種） |

---

### P1-TC-XP-03 — GET /experience 欄位夠 HUD 用

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-XP-03 |
| **標題** | 已有 `experience_in_level`、`experience_for_next`；修復 `ability_atk` KeyError（評估 P1-6） |
| **優先級** | P0 |
| **建議模組** | `tests/test_xp_bar.py` |
| **前置** | 空庫 kid；login |
| **步驟** | GET `/api/kids/{id}/experience` |
| **預期** | 200；有上述欄位；**唔** 500 |

---

## G. 探險金幣費用（跟 GAMEPLAY_REDESIGN §6.5）

政策摘要：**短征區1 費用 10、區2 20、區3 30**；獎勵期望 ≤ 費用（材料為主）；扣費發生在 **start**；錢唔夠唔建行。

### P1-TC-EXP-01 — 區 1 短征扣 10 金

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-EXP-01 |
| **標題** | 有公會、points=15 時 start 區1 explore → points=5，log reason 含 `expedition_fee` |
| **優先級** | P0 |
| **建議模組** | `tests/test_expedition_gold.py` |
| **前置** | 公會；points=15 |
| **步驟** | POST `expedition/start` region_id=1, type=explore |
| **預期** | 201；points=5；有 running expedition |

---

### P1-TC-EXP-02 — 金幣不足唔扣唔建

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-EXP-02 |
| **標題** | points=9 start 區1 → 400 `insufficient_gold` |
| **優先級** | P0 |
| **建議模組** | `tests/test_expedition_gold.py` |
| **前置** | 公會；points=9 |
| **步驟** | start |
| **預期** | 400；`need==10` `have==9`；無 running；points 仍 9 |

---

### P1-TC-EXP-03 — 區 2／3 費用表

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-EXP-03 |
| **標題** | 區2 扣 20、區3 扣 30（解鎖條件用 factory 插 explored） |
| **優先級** | P0 |
| **建議模組** | `tests/test_expedition_gold.py` |
| **前置** | 足夠金幣；區域已解鎖 |
| **步驟** | 各 start 一次（可用兩個 kid 或 claim 後再 start） |
| **預期** | 扣 20／30 |

---

### P1-TC-EXP-04 — 戰鬥 start 唔扣探險費

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-EXP-04 |
| **標題** | battle-start 金幣不變 |
| **優先級** | P0 |
| **建議模組** | `tests/test_expedition_gold.py` |
| **前置** | 公會；points=10；區1 可打 |
| **步驟** | battle-start region 1 |
| **預期** | 成功；points 仍 10 |

---

### P1-TC-EXP-05 — 探索可重複農

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-EXP-05 |
| **標題** | claim 區1 之後可以再 start 區1 |
| **優先級** | P0 |
| **建議模組** | `tests/test_expedition_gold.py` |
| **前置** | 即時 duration claim 一次；再加金幣 |
| **步驟** | 第二次 start 區1 |
| **預期** | 201（而家產品「已完成就不能再農」必須被呢條打紅） |

---

## H. 公會閘（伺服器）

### P1-TC-GLD-01 — 無公會不能探險

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-GLD-01 |
| **標題** | 無探險公會時 `expedition/start` 400／403 `guild_required` |
| **優先級** | P0 |
| **建議模組** | `tests/test_guild_gate.py` |
| **前置** | 無 def 公會；points 很多 |
| **步驟** | start 區1 |
| **預期** | 失敗；無 expedition 行；金幣唔扣 |

---

### P1-TC-GLD-02 — 無公會不能戰鬥

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-GLD-02 |
| **標題** | `battle-start` 同樣要公會 |
| **優先級** | P0 |
| **建議模組** | `tests/test_guild_gate.py` |
| **前置** | 無公會 |
| **步驟** | battle-start |
| **預期** | `guild_required`；而家只靠前端 `def_id===6` 必須被呢條打紅 |

---

### P1-TC-GLD-03 — 存倉公會當無公會

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-GLD-03 |
| **標題** | `stored=1` 公會不能探險 |
| **優先級** | P1 |
| **建議模組** | `tests/test_guild_gate.py` |
| **前置** | 公會 stored |
| **步驟** | start |
| **預期** | `guild_required` |

---

### P1-TC-GLD-04 — 有未存倉公會可以 start

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-GLD-04 |
| **標題** | 正向 |
| **優先級** | P0 |
| **建議模組** | `tests/test_guild_gate.py` |
| **前置** | 公會 stored=0；points≥10 |
| **步驟** | start 區1 |
| **預期** | 201 |

---

## I. 放置模式對等（前端為主）

> **註**：評估：商店會 `startPlacement`；建築分頁「建造」只 toast「點擊下方空地」，**唔**進放置模式。呢個可以純前端修。後端 place API 已收 `cell_x/cell_y`。pytest 測後端對等**唔需要**；前端測試或手動必做。

### P1-TC-PLC-01 — 後端 place 不依賴入口來源

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-PLC-01 |
| **標題** | 同一 POST buildings body 無論邊個 tab 叫都 201 |
| **優先級** | P1 |
| **建議模組** | `tests/test_unlock_region.py` 或現有建築測試（空庫版） |
| **前置** | 資源夠最平建築（圖書館） |
| **步驟** | POST def_id=圖書館, cell_x=0, cell_y=0 |
| **預期** | 201；證明「對等」唔係兩套 API |

---

### P1-TC-PLC-FE-01 — 建築分頁亦進入放置模式

| 欄 | 內容 |
|----|------|
| **ID** | P1-TC-PLC-FE-01 |
| **標題** | 建築 tab 撳建造後，地圖進入同商店一樣嘅放置態（可點空地） |
| **優先級** | P0（UX）；自動化視 Playwright |
| **建議模組** | `tests/test_frontend_placement.py` |
| **前置** | 已登入；金幣夠；開建築分頁 |
| **步驟** | 撳圖書館建造（唔經商店）→ 點空地 |
| **預期** | 見到放置高亮／2×2 預覽；成功後格上有建築。**弱 (A)：** 字串斷言 `index.html` 建築分頁 onclick 含 `startPlacement` 而非只 `showToast`（`tests/test_frontend_placement.py`）。**較強 (A)：** `TC-FE-PLACE-SHOP-01`／`TC-FE-PLACE-BUILD-01` Playwright 全路徑。**(B) 必須人手走一次兩個入口**（真機；見 [`MANUAL_B_CHECKLIST.md`](MANUAL_B_CHECKLIST.md)）。 |

---

## 手動／E2E 清單（雙重驗證 B）

- [ ] 起圖書館 → 再做任務，儀式見到「圖書館 +2」（或當前等級值）
- [ ] 農場領金幣 → 再撳被拒 → 改系統日期（或等）先至再領（開發可用 freeze 端點 **唔好** 留生產）
- [ ] 起商店後下一座建築金幣較平，材料數不變
- [ ] 探險回來 HUD 四格加嘅係木頭／磚／玻璃／齒輪，背包無「鐵」孤立堆
- [ ] 區 4 掣顯示尚未開放，戰鬥唔彈技術 404
- [ ] 無公會時探險／戰鬥有人話，唔係靜默失敗
- [ ] 短征費用標「費用 🪙10」，唔再把 🪙30 當費用
- [ ] 同一區探索可第二次出發
- [ ] 建築分頁同商店都能放置（對應 `TC-FE-PLACE-SHOP-01` / `TC-FE-PLACE-BUILD-01`；(B) 真機仍要）
- [ ] 完成任務儀式同時見到金幣 + XP 數字 + 材料（對應 `TC-FE-CEREMONY-01`；真機確認 toast 冇裁走 XP／🪵）
- [ ] XP 條：升 1 級過程中條由空→滿，唔係一開始滿格（對住 GET `/experience`）
- [ ] 15 分鐘劇本（企劃 §8）至少內部走一次

簽收格式見 `TDD_PROCESS.md`。
