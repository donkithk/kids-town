# 建築被動同技能真話

> **狀態**：紅燈測試。只加測試同呢份目錄，唔改產品。  
> **基線**：`cursor/green-sheet-buff-truth-6a00` `afbc1a6`。  
> **Fixture**：空庫 SQLite、合成帳號（`test_kid_a`／`test_fe_kid`，PIN `1357`）。唔好抄 production DB，唔好用真密碼。  
> **模組**：`tests/test_building_passives.py`、`tests/test_skill_truth.py`、`tests/test_frontend.py`、`tests/sheet_buff_truth_spec.py`。

戰鬥公式（`calc_battle_stats`，小朋友自身屬性係 0）：

| 屬性 | 戰鬥欄 | 公式 |
|----|----|----|
| 臂力 str | `player_atk` | `int(5 + str × 1.5)` |
| 知識 int | `player_matk` | `int(5 + int × 1.5)` |
| 勇氣 brv | `player_def` | `int(brv × 0.6)` |
| 創意 crt | `player_crt` | `min(50, crt × 2)` |
| 速度 spd | `player_dodge` | `min(40, spd × 1.5)` |

而家 `calc_battle_stats` 只讀小朋友自己嘅點，唔讀 `calc_ability_buffs`。開戰 JSON 亦冇 `player_matk`。所以被動測試喺呢條基線係紅。`stored=1` 唔計。

---

## 被動（API）

### TC-API-BLD-PASSIVE-LIB — 圖書館知識

每級 +2 知識。`POST /api/kids/<id>/expedition/battle-start` 嘅 `player_matk`：Lv0（只有公會）= 5，Lv1 = 8，Lv2 = 11，Lv4 = 17。Lv4 唔好用舊 `buff_vals` 嘅 10 知識計成 20。存倉圖書館仍然係 5。

### TC-API-BLD-PASSIVE-GYM — 健身室臂力

每級 +2 臂力。`player_atk`：Lv0 = 5，Lv1 = 8，Lv2 = 11。存倉唔計。

### TC-API-BLD-PASSIVE-WRK — 工坊創意

每級 +2 創意。`player_crt`：Lv0 = 0，Lv1 = 4，Lv2 = 8。存倉唔計。

### TC-API-BLD-PASSIVE-ARN — 競技場臂力同速度

每級 +2 臂力、+1 速度。Lv1：`player_atk` 8、`player_dodge` 1.5。Lv2：11 同 3.0。存倉唔計。

### TC-API-BLD-PASSIVE-GLD — 探險公會勇氣

每級 +2 勇氣。`player_def`：Lv1 = 1，Lv2 = 2。再開一座 stored Lv5 仍然係 1，唔好變成 `int((2+10)×0.6)=7`。冇公會開唔到戰（`guild_required`）係原有閘。

### TC-API-BLD-PASSIVE-OBS — 天文台唔再加知識

`GET /api/kids/<id>/abilities` 嘅 `buffs.int` 要係 0，`total.int` 等於 `base.int`。開戰 `player_matk` 要係 5。而家 `calc_ability_buffs` 天文台每級 +2 知識，所以呢條紅。

天文台尋寶機率**暫緩**。數值未定，會用戰鬥之後嘅 `roll_drop` 稀有度權重。呢份目錄同測試都唔鎖定 `explore_treasure_chance` 或者百分比。面板改為描述已確定嘅技能「流星雨」，唔好寫「尋寶機率」。`TC-API-SKILL-METEOR` 同 `TC-API-BLD-PASSIVE-OBS` 仍然要。

---

## 取消咗嘅舊效果

### TC-API-BLD-REMOVED-XP — 圖書館任務經驗

10 分任務：`experience_bonus==0`，`experience_total==5`。同 `P1-TC-BUFF-01`、`P1-TC-BUFF-03`、`SHEET-BUFF-TRUTH-01` API 同一件事。而家仲加 2／4，所以紅。

### TC-API-BLD-REMOVED-STREAK — 健身室唔保護連續

漏咗 3 日，`current_streak` 由 5 變 1，即使健身室 Lv5。`update_streak` 本來就唔睇健身室，呢條要綠。

### TC-API-BLD-REMOVED-HOSP — 醫院唔乘探險獎勵

同一 RNG（`random` 0.99、`randint` 取下界）：有醫院 Lv5 同冇醫院都係回報金幣 6、淨金幣 −4（入場費 10）、經驗 +10。要綠。

### TC-API-BLD-REMOVED-RANGE — 燈塔唔加探險範圍

燈塔 Lv5 開區 4 仍然 400 `region_locked`。區 1 有公會仍然 201。要綠。

### TC-API-BLD-REMOVED-LEDGER — 銀行唔係帳本

`building_defs` 嘅名、`buff_type`、`effect` 都唔好有 `ledger`。如果有一行叫「銀行」，`effect` 唔好有「帳本」。家長 `GET /api/transactions?kid_id=` 冇銀行都要 200，而且 `items` 係陣列。家長帳本 API 唔係建築效果，要留低。要綠。

### TC-API-MIGRATE-FARM — 舊庫 migrate 之後城鎮 200

由一個已經 init、但 `DROP TABLE farm_claims` 嘅庫開始，呼叫 `migrate_db()`。之後表要存在，`SELECT claim_date` 要行得。`GET /api/kids/<id>/town` 係 200，`farm_claimed_today` 係 false。唔好靠「表唔存在就當 false」。呢條基線 `migrate_db` 已經 `CREATE TABLE IF NOT EXISTS farm_claims`，所以要綠；如果 builder 改成吞錯誤，`SELECT claim_date` 會紅。

要繼續綠、呢輪唔改預期：商店建造／升級金幣折扣（`P1-TC-BUFF-07`／`08`、`SHEET-BUFF-TRUTH-02`）、農場每日領取（`P1-TC-BUFF-05`、`POST /api/kids/<id>/farm/claim`、`farm_claimed_today`）。

### TC-API-SEED-NO-TASK-BONUS — 種子唔好再有任務經驗

新種子：`building_defs` 冇任何 `buff_type='task_bonus'`（圖書館都唔好）。

舊種子：把圖書館改返 `task_bonus`、`buff_vals=[2,4,6,10,15]`、`effect=任務 +2⭐`，再跑 `migrate_db()`。之後仍然唔好有 `task_bonus` 行。

圖書館擺喺度，完成 40 分任務：`experience_bonus` 係 0，`experience_total` 同小朋友經驗都加 20（`max(5, 40//2)`）。唔好再加舊曲線。

---

## 面板

文案鎖喺 `tests/sheet_buff_truth_spec.py` 嘅 `sheet_effect_label`。

| ID | 描述 |
|----|----|
| TC-FE-TOWN-UX-SHEET-BUFF-01 | 圖書館 Lv.2「知識 +4」（+2×等級）。零 `.fn`。唔讀 `task_bonus` 種子行。 |
| TC-FE-TOWN-UX-SHEET-BUFF-02 | 工坊零 `.fn`、唔好 stub toast。唔查數字。要綠。 |
| TC-FE-TOWN-UX-SHEET-BUFF-ZH-01 | 工坊 Lv.3「創意 +6」。 |
| TC-FE-TOWN-UX-SHEET-BUFF-ZH-02 | 健身室 Lv.1「臂力 +2」。 |
| TC-FE-SHEET-BUFFVAL-01 | 商店 Lv.2「起屋／升級金幣八五折」（`buff_vals[1]=0.85`，唔係九折）。要綠。 |
| TC-FE-SHEET-UNWIRED-01 | 自訂 `zzz_unwired`、值 9：正好「未開放」，唔好出現 9。要綠。 |
| TC-FE-SHEET-BANK-01 | 測試庫插入「銀行」：技能句「金錢砸」。而家係「未開放」，所以紅。 |
| SHEET-BUFF-TRUTH-01 | 圖書館「知識 +2」。唔讀 `task_bonus` 種子行。API bonus 0。 |
| SHEET-BUFF-TRUTH-02 | 商店「起屋／升級金幣九折」。要綠。 |
| SHEET-BUFF-TRUTH-03 | 農場「每日金幣 +5」加可撳「領取」。要綠。 |
| SHEET-BUFF-TRUTH-04 | 領完「今日已領」，同日只加一次。要綠。 |
| SHEET-BUFF-TRUTH-05 | 七座等於上表被動／技能，唔好「未開放」。 |
| SHEET-BUFF-TRUTH-06 | 十座面板都等於鎖定句。API：`get_building_buff` 只剩 `discount`、`daily_gold`。工坊唔改升級金、健身室唔加 XP 呢兩點要先過，然後集合斷言先紅。 |

`#upgradeConfirm` 仍然係 `div.gsw.stage` 最後一個元素子節點。

---

## 技能

全部經 `POST .../expedition/battle-start` 同 `.../battle-action`。斷言係 HP、MP、傷害、狀態回合、金幣、命中次數，唔好只睇 log。`random.randint` 固定：`(1,3)` 怪物數、`(-5,5)` 回 0、`(1,100)` 回 100（命中率未跌仍然打中）、其他範圍回 0（傷害方差 0）。怪物速度改成 50，避免先手跳過反擊。

| ID | 技能 | 要見到嘅數字 |
|----|----|----|
| TC-API-SKILL-DOUBLE | 連擊 | 怪物 HP 下降等於兩次單體公式。健身室 Lv4、方差 0：一下 `max(1, int(16+4×4+player_str))`，兩下係兩倍。 |
| TC-API-SKILL-FREEZE | 冰凍 | 魔法傷害 > 0，等於 `max(1, int(base_value + per_level×圖書館等級 + 開戰 player_int))`（方差 0）。有 `player_matk` 就要等於 `int(5 + player_int×1.5)`。唔好寫死 56。對照普攻量到嘅反擊係基線（跟開戰 `player_def`，公會被動計入都得）。施放唔計入兩回合，嗰下反擊仍係基線。之後兩次玩家行動先 `int(怪攻×0.7)` 再代入 `max(0, 攻−player_def)`。第三次返基線。 |
| TC-API-SKILL-EXECUTE | 必殺 | 敵人 HP ≤ 25% 上限時，傷害至少係滿血同一擊嘅 1.5 倍。 |
| TC-API-SKILL-REPAIR | 修復 | 回復 MP，HP 唔變。防禦拉到 999，反擊係 0。 |
| TC-API-SKILL-FORTIFY | 強化 | 下一擊受到嘅傷害少過冇開強化嘅對照反擊。 |
| TC-API-SKILL-SCOUT | 偵察 | 怪物 HP 唔變。區 1 弱點係「火」（區 2「冰」、區 3「雷」）。 |
| TC-API-SKILL-CHARGE | 蓄力 | 倍率鎖 ×2。下一擊等於同一場對照普攻嘅 2 倍。對照要等於 `max(1, 開戰 player_atk − 怪防)`，健身室被動令攻擊變 8 都照計，唔好寫死 5 同 10。施放嗰下亦要打中（`TC-API-SKILL-ALL-DAMAGE`）。說明要正好「下次攻擊 2 倍」（開戰 `skills`、`GET /api/kids/<id>/skills`、戰鬥 log）。而家說明係「下次攻擊 1.5 倍」。 |
| TC-API-SKILL-SHIELD | 盾擊 | 舊名「挑釁」唔好再出現。有物理傷害，呢一回合受到嘅傷害係對照反擊嘅整數一半。 |
| TC-API-SKILL-GALE | 疾風斬 | 舊名「迴避」唔好再出現。有物理傷害，呢一回合玩家 HP 唔跌。 |
| TC-API-SKILL-KNOWLEDGE | 知識的力量 | 圖書館。施放之後 3 回合 `player_int` +3×等級（Lv1 +3、Lv5 +15）。火球傷害比對照多正好呢個數。第 4 下同 `player_int` 返原值。施放嗰下亦要打中（`TC-API-SKILL-ALL-DAMAGE`，對魔法普攻）。 |
| TC-API-SKILL-TRAINING | 鍛鍊的成果 | 健身室。施放之後 3 回合臂力 +3×等級。普攻等於 `max(1, int(5+(str+3×等級)×1.5)−敵防)`，`player_str`／`player_atk` 同步。第 4 下返原值。施放嗰下亦要打中（`TC-API-SKILL-ALL-DAMAGE`，對物理普攻）。 |
| TC-API-SKILL-MEAL | 營養餐 | 農場。持續回血，唔係即時治療。施放當下 HP 不變，MP 只扣消耗。之後 3 回合每回合回大約最大 HP 嘅 8%（允許大約 6%–14% 嘅取整同少量等級加成）。Lv5 每回合回血 ≥ Lv1。第 4 回合停止。唔好順便回 MP。 |
| TC-API-SKILL-COIN | 金幣袋 | 商店。打贏先至多 20 金幣。逃跑唔加。冇用技能嘅勝場係對照。 |
| TC-API-SKILL-FLASH | 強光 | 燈塔。有魔法傷害。之後 2 次怪物攻擊打唔中（唔係命中率下降），第三次先至再扣血。測試用之後三次玩家行動嘅反擊量到。 |
| TC-API-SKILL-METEOR | 流星雨 | 天文台。三隻敵人每一隻 HP 都跌。 |
| TC-API-SKILL-GOLD | 金錢砸 | 要有 `building_defs` 名「銀行」。每次扣 10 金幣，傷害等於 3 倍普攻（方差 0）。金幣少過 10：400 `insufficient_gold`，金幣同怪物 HP 都唔變。 |

新技能假設所屬建築 Lv1 就學到（知識的力量、鍛鍊的成果、營養餐都係）。舊技能嘅等級門檻照種子：蓄力健身室 1、連擊 4、冰凍圖書館 4、火球圖書館 2、偵察公會 2、修復工坊 2、強化 4、必殺競技場 5。`TC-API-SKILL-KNOWLEDGE` 喺測試庫把火球 `level_required` 改成 1，先至能量 Lv1 圖書館嘅魔法傷害；產品種子唔改。

除偵察外，每個技能施放嗰下都要造成傷害，再加上自己嘅額外效果。預期跟該場開戰嘅 `player_atk`／`player_matk`／`player_def`，唔好寫死「冇被動」嘅 5 或 0。

### TC-API-MIGRATE-SKILLS — 舊技能就地改名

測試先把 `skill_defs` 換成基礎分支種子（`afbc1a6`）：有挑釁、迴避，蓄力說明係「下次攻擊 1.5 倍」，冇七個新技能。合成小朋友用 `kid_skills.skill_id` 學咗呢三個 id，並放好健身室 Lv1、競技場 Lv4、探險公會 Lv4。

`migrate_db()` 之後：

- 挑釁、迴避嗰兩行原 id 改名做盾擊、疾風斬，舊名唔留。
- 蓄力原 id 嘅說明含「2 倍」或「2倍」。
- 知識的力量、鍛鍊的成果、營養餐、金幣袋、強光、流星雨、金錢砸都存在。
- 每一個舊 id 仲在，行數 ≥ 舊行數。
- 用原 id 開戰，三個技能都打得到（200，唔好 `Skill not found`）。
- 再跑一次 `migrate_db()`，全表不變，每個名只得一行。

### TC-API-SKILL-ALL-DAMAGE — 施放都要打中

每個技能一條。偵察：怪物 HP 下降 0。其餘：施放嗰下傷害 > 0，而且 ≥ 同一狀態嘅普攻。

- 魔法普攻（知識的力量、冰凍、強光、流星雨）：`max(1, matk − 怪防)`。有 `player_matk` 就用佢，而且要等於 `int(5 + player_int×1.5)`；冇就用呢條式。流星雨三隻每一隻都要達標。
- 物理普攻（鍛鍊的成果、營養餐、金幣袋、修復、強化，以及連擊、必殺、蓄力、盾擊、疾風斬、金錢砸）：`max(1, player_atk − 怪防)`。
- 盾擊、疾風斬要剛好等於物理普攻，唔好再用種子傷害曲線。

### TC-API-FORTIFY-TURNS — 強化三回合

施放唔計入三回合。之後三次怪物行動，玩家扣血少過同一場對照反擊。第四次等於對照。對照跟開戰防禦，唔好寫死 0。

### TC-API-SHIELD-PERSIST — 盾擊減半留到打中

`player_dodge` 設成 100，`(1,100)` 固定擲 100，施放嗰下反擊係 0，減半唔消耗。下一擊先係對照反擊嘅整數一半。再下一擊恢復全額。

### TC-API-SKILL-DESC-05 — 說明關鍵字

唔好逐字，只係關鍵字：

- 強化含「3 回合」。
- 盾擊含「下一次被打中」或「下次被打中」。
- 強光含「2 次」，以及「打唔中」或「打不中」。
- 知識的力量、鍛鍊的成果、營養餐、金幣袋、修復、強化嘅說明唔好含「唔會打傷害」「不造成傷害」「無傷害」「0 傷害」。

### TC-API-SEED-NO-DEAD-CURVE — 盾擊／疾風斬冇傷害曲線

`skill_defs` 有 `base_value`、`per_level`（`REAL`，預設 0）。呢兩欄就係傷害曲線，所以唔跳過。盾擊同疾風斬嘅呢兩欄要係 `NULL` 或 0。如果表冇呢兩欄，測試先至 skip。

### TC-API-SKILL-RECAST-REVERT — 再施放只刷新三回合

同一場戰鬥。知識的力量同鍛鍊的成果各一條（建築 Lv1）。再施放只刷新 3 回合計時，唔疊加，亦唔改底。

先量未加成嘅數：知識用火球傷害同開戰 `player_int`（測試庫先把火球 `level_required` 改成 1）；臂力用一記普攻傷害、開戰 `player_str` 同 `player_atk`。一次加成係 +3×等級。Lv1 如果開戰知識係 2，加成後係 5，唔好變 8（2+3+3）。數字跟該場開戰值計，唔寫死。

施放一次。如果嗰下回應未見到加成，下一記火球或普攻要已經係一次加成，先至再施放。第二次施放唔計入三回合。

- 之後連續三下：能力同傷害等於一次加成（知識係 `player_int` 同火球；臂力係 `player_str`、`player_atk` 同普攻）。
- 第四下：能力同傷害返到第一次施放之前量到嘅原值。

### TC-API-GOLD-SMASH-ATOMIC — 金錢砸扣金要原子

小朋友剛好 10 金幣。兩個 `battle-action` 金錢砸同時過金檢：兩條 thread，`SELECT points FROM kids` 讀完之後先一齊放行，所以兩邊都見到 10，先至有機會扣。

預期剛好一個 200、一個 400 `insufficient_gold`。最後金幣係 0，唔好負數。`points_log` 剛好一行金額 −10、原因有「金錢砸」。

如果實現唔用呢句 SELECT，而係用 `UPDATE ... WHERE points >= 10` 並且 0 行就當失敗，barrier 唔會觸發；兩個請求仍然並行，條件更新只可以成功一次。
