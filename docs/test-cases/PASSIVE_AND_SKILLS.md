# 建築被動同技能真話

> **狀態**：紅燈測試。只加測試同呢份目錄，唔改產品。  
> **基線**：`cursor/green-sheet-buff-truth-6a00` `afbc1a6`。  
> **Fixture**：空庫 SQLite、合成帳號（`test_kid_a`／`test_fe_kid`，PIN `1357`）。唔好抄 production DB，唔好用真密碼。版控嘅 `kids_town.db` 係小朋友遊玩進度：測試唔好改、重新 seed、migrate，或者 commit。舊種子只可以從 git 歷史寫入 pytest `tmp_path`。  
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

舊種子：`git show afbc1a6:backend_v2.py` 嘅 `seed_building_defs`（圖書館 `task_bonus`、`buff_vals=[2,4,6,10,15]`、`effect=任務 +2⭐`）寫入 pytest `tmp_path` 嘅新檔，再跑 `migrate_db()`。之後仍然唔好有 `task_bonus` 行。唔好打開版控嘅 `kids_town.db` 嚟寫。

圖書館擺喺度，完成 40 分任務：`experience_bonus` 係 0，`experience_total` 同小朋友經驗都加 20（`max(5, 40//2)`）。唔好再加舊曲線。

---

## 面板

商店、農場、醫院、燈塔、銀行、天文台嘅句鎖喺 `tests/sheet_buff_truth_spec.py` 嘅 `sheet_effect_label`。圖書館、健身室、工坊、競技場、探險公會唔再寫死「+2×等級」，改由 `tests/sheet_two_layer.py` 用函數差計兩層數字。

| ID | 描述 |
|----|----|
| TC-FE-TOWN-UX-SHEET-BUFF-01 | 圖書館 Lv.2 跟 `STAT_GLOSSARY.md`。M 唔係 0 先至「知識 +N（魔法力 +M）」；M 係 0 就只得「知識 +N」。N、M 由函數差計。零 `.fn`。唔讀 `task_bonus` 種子行。 |
| TC-FE-TOWN-UX-SHEET-BUFF-02 | 工坊零 `.fn`、唔好 stub toast。唔查數字。要綠。 |
| TC-FE-TOWN-UX-SHEET-BUFF-ZH-01 | 工坊 Lv.3 兩層數字，唔好「建築速度 ×」或者「未開放」。 |
| TC-FE-TOWN-UX-SHEET-BUFF-ZH-02 | 健身室 Lv.1 兩層數字，唔好「漏打卡都唔斷」或者「未開放」。 |
| TC-FE-SHEET-BUFFVAL-01 | 商店 Lv.2「起屋／升級金幣八五折」（`buff_vals[1]=0.85`，唔係九折）。要綠。 |
| TC-FE-SHEET-UNWIRED-01 | 自訂 `zzz_unwired`、值 9：正好「未開放」，唔好出現 9。要綠。 |
| TC-FE-SHEET-BANK-01 | 測試庫插入「銀行」：技能句「金錢砸」。而家係「未開放」，所以紅。 |
| SHEET-BUFF-TRUTH-01 | 圖書館兩層數字。唔讀 `task_bonus` 種子行。API bonus 0。 |
| TC-FE-SHEET-TWO-LAYER | 五座被動、Lv.1 同 Lv.3。用字同單位讀 `docs/ui-mocks/STAT_GLOSSARY.md`，唔對戰鬥 HUD。N、M 由函數差計。`stored=1` 唔計。競技場兩種能力都要。唔好「魔力」或者爆擊傷害倍率。 |
| TC-API-SHEET-TWO-LAYER | 同一五座、Lv.1 同 Lv.3：`stored=1` 唔改變 `calc_ability_buffs` 同 `calc_battle_stats`。擺出嚟嘅能力鍵同括號鍵要同詞彙表一致。 |
| TC-DOC-STAT-GLOSSARY | 詞彙表兩張表解析到。單位只係整數或百分比。戰鬥層每個 `calc_battle_stats` 鍵都要係函數輸出，避免 `player_eva`。`player_crit_dmg` 唔入表。 |
| SHEET-BUFF-TRUTH-02 | 商店「起屋／升級金幣九折」。要綠。 |
| SHEET-BUFF-TRUTH-03 | 農場「每日金幣 +5」加可撳「領取」。要綠。 |
| SHEET-BUFF-TRUTH-04 | 領完「今日已領」，同日只加一次。要綠。 |
| SHEET-BUFF-TRUTH-05 | 七座等於上表被動／技能，唔好「未開放」。 |
| SHEET-BUFF-TRUTH-06 | 十座面板都等於鎖定句。API：`get_building_buff` 只剩 `discount`、`daily_gold`。工坊唔改升級金、健身室唔加 XP 呢兩點要先過，然後集合斷言先紅。 |

`#upgradeConfirm` 仍然係 `div.gsw.stage` 最後一個元素子節點。

### TC-FE-SHEET-TWO-LAYER — 被動面板兩個數

圖書館、健身室、工坊、競技場、探險公會。每座至少 Lv.1 同 Lv.3。空庫、合成小朋友。

用字唔好對戰鬥 HUD，亦唔好寫死。測試讀 `docs/ui-mocks/STAT_GLOSSARY.md` 嘅「能力層」同「戰鬥數值層」（欄位、中文、單位、備註），再讀「顯示規則」邊個能力對邊個 `player_*`。

格式係「能力中文 +N（戰鬥數值中文 +M）」。單位係百分比先加 `%`，貼住數字。例子（數字只係例子）：「速度 +1（閃避率 +1.5%）」。競技場兩段用「、」接住。HP、MP 保持英文。唔好寫「魔力」。`player_crit_dmg` 係倍率，唔好出現喺面板或者括號。

- N：`calc_ability_buffs` 有呢座（`stored=0`）減冇呢座。`stored=1` 要同冇座一樣（`TC-API-SHEET-TWO-LAYER`）。
- M：同一個人，`calc_battle_stats` 對住詞彙表備註嗰個短鍵嘅差（例如 `player_atk` 對 `atk`）。
- 最多一個小數位。整數唔寫 `.0`。
- 詞彙表寫明 M 係 0 就唔寫括號，唔好寫「（… +0）」。而家呢條基線 `calc_battle_stats` 唔讀建築，所以 M 係 0，預期句係「知識 +N」呢種，直到函數開始計建築。

面板而家未跟詞彙表，所以紅。#53 預期都係紅。

### TC-DOC-STAT-GLOSSARY — 詞彙表解析

`STAT_GLOSSARY.md` 兩張表要解析到。單位只可以係「整數」或者「百分比」。戰鬥數值層每一列，如果備註話自己係 `calc_battle_stats` 鍵，嗰個鍵同 `player_` 後面嗰截都要出現喺函數輸出。備註話「唔係」嘅列（MP）跳過。`player_crit_dmg` 唔好列喺戰鬥數值層。

### TC-API-SHEET-TWO-LAYER — 存倉唔計

同一五座、Lv.1 同 Lv.3。`stored=1` 呼叫 `calc_ability_buffs` 同 `calc_battle_stats` 要等於冇座。擺出嚟嘅能力鍵要同函數一致，括號用嘅短鍵要係詞彙表嗰個，而且函數真係返回佢。數字唔寫死。

---

## 技能

全部經 `POST .../expedition/battle-start` 同 `.../battle-action`。斷言係 HP、MP、傷害、狀態回合、金幣、命中次數，唔好只睇 log。`random.randint` 固定：`(1,3)` 怪物數、`(-5,5)` 回 0、`(1,100)` 回 100（命中率未跌仍然打中）、其他範圍回 0（傷害方差 0）。怪物速度改成 50，避免先手跳過反擊。

| ID | 技能 | 要見到嘅數字 |
|----|----|----|
| TC-API-SKILL-DOUBLE | 連擊 | 怪物 HP 下降等於兩次單體公式。健身室 Lv4、方差 0：一下 `max(1, int(16+4×4+player_str))`，兩下係兩倍。 |
| TC-API-SKILL-FREEZE | 冰凍 | 魔法傷害 > 0，等於 `max(1, int(base_value + per_level×圖書館等級 + 開戰 player_int))`（方差 0）。有 `player_matk` 就要等於 `int(5 + player_int×1.5)`。唔好寫死 56。對照普攻量到嘅反擊係基線（跟開戰 `player_def`，公會被動計入都得）。施放當回合反擊已經計入兩次：先 `int(怪攻×0.7)` 再代入 `max(0, 攻−player_def)`。下一記玩家行動仍然係呢個削弱值。再下一記（第 3 次怪物攻擊）返基線。 |
| TC-API-SKILL-EXECUTE | 必殺 | 敵人 HP ≤ 25% 上限時，傷害至少係滿血同一擊嘅 1.5 倍。 |
| TC-API-SKILL-REPAIR | 修復 | 回復 MP，HP 唔變。防禦拉到 999，反擊係 0。 |
| TC-API-SKILL-FORTIFY | 強化 | 下一擊受到嘅傷害少過冇開強化嘅對照反擊。 |
| TC-API-SKILL-SCOUT | 偵察 | 怪物 HP 唔變。區 1 弱點係「火」（區 2「冰」、區 3「雷」）。 |
| TC-API-SKILL-CHARGE | 蓄力 | 倍率鎖 ×2。下一擊等於同一場對照普攻嘅 2 倍。對照要等於 `max(1, 開戰 player_atk − 怪防)`，健身室被動令攻擊變 8 都照計，唔好寫死 5 同 10。施放嗰下亦要打中（`TC-API-SKILL-ALL-DAMAGE`）。說明要正好「下次攻擊 2 倍」（開戰 `skills`、`GET /api/kids/<id>/skills`、戰鬥 log）。而家說明係「下次攻擊 1.5 倍」。 |
| TC-API-SKILL-SHIELD | 盾擊 | 舊名「挑釁」唔好再出現。有物理傷害，呢一回合受到嘅傷害係對照反擊嘅整數一半。 |
| TC-API-SKILL-GALE | 疾風斬 | 舊名「迴避」唔好再出現。有物理傷害，呢一回合玩家 HP 唔跌。 |
| TC-API-SKILL-KNOWLEDGE | 知識的力量 | 圖書館。施放之後 3 回合 `player_int` +3×等級（Lv1 +3、Lv5 +15）。火球傷害比對照多正好呢個數。第 4 下同 `player_int` 返原值。施放嗰下亦要打中（`TC-API-SKILL-ALL-DAMAGE`，對魔法普攻）。 |
| TC-API-SKILL-TRAINING | 鍛鍊的成果 | 健身室。施放之後 3 回合臂力 +3×等級。普攻等於 `max(1, int(5+(str+3×等級)×1.5)−敵防)`，`player_str`／`player_atk` 同步。第 4 下返原值。施放嗰下亦要打中（`TC-API-SKILL-ALL-DAMAGE`，對物理普攻）。 |
| TC-API-SKILL-MEAL | 營養餐 | 農場。持續回血，唔係即時治療。施放當下 HP 不變。MP 跟 `docs/test-cases/SKILL_MENU_AND_TEXT.md`：施放後 `min(max_mp, mp_before - cost + NUTRITION_MEAL_MP_REGEN)`，`NUTRITION_MEAL_MP_REGEN = 5`。之後 3 回合每回合回大約最大 HP 嘅 8%（允許大約 6%–14% 嘅取整同少量等級加成）。Lv5 每回合回血 ≥ Lv1。第 4 回合停止。之後回合唔好再加 MP。 |
| TC-API-SKILL-COIN | 金幣袋 | 商店。打贏先至多 20 金幣。逃跑唔加。冇用技能嘅勝場係對照。 |
| TC-API-SKILL-FLASH | 強光 | 燈塔。有魔法傷害。施放當回合反擊係第 1 次打唔中（扣血 0，log 有「攻擊落空」）。下一記怪物攻擊係第 2 次，仍然打唔中。再下一記（第 3 次）按基線 `max(0, 怪攻−player_def)` 扣血。唔係命中率下降。 |
| TC-API-SKILL-METEOR | 流星雨 | 天文台。三隻敵人每一隻 HP 都跌。 |
| TC-API-SKILL-GOLD | 金錢砸 | 要有 `building_defs` 名「銀行」。每次扣 10 金幣，傷害等於 3 倍普攻（方差 0）。金幣少過 10：400 `insufficient_gold`，金幣同怪物 HP 都唔變。 |

新技能假設所屬建築 Lv1 就學到（知識的力量、鍛鍊的成果、營養餐都係）。舊技能嘅等級門檻照種子：蓄力健身室 1、連擊 4、冰凍圖書館 4、火球圖書館 2、偵察公會 2、修復工坊 2、強化 4、必殺競技場 5。`TC-API-SKILL-KNOWLEDGE` 喺測試庫把火球 `level_required` 改成 1，先至能量 Lv1 圖書館嘅魔法傷害；產品種子唔改。

除偵察外，每個技能施放嗰下都要造成傷害，再加上自己嘅額外效果。預期跟該場開戰嘅 `player_atk`／`player_matk`／`player_def`，唔好寫死「冇被動」嘅 5 或 0。

### TC-API-MIGRATE-SKILLS — 舊技能就地改名

測試先把 `skill_defs` 換成 `git show afbc1a6:backend_v2.py` 嘅 `seed_skill_defs`，寫入 pytest 暫存庫：有挑釁、迴避，蓄力說明係「下次攻擊 1.5 倍」，冇七個新技能。合成小朋友用 `kid_skills.skill_id` 學咗呢三個 id，並放好健身室 Lv1、競技場 Lv4、探險公會 Lv4。`migrate_db()` 只可以連呢個暫存檔，唔好打開版控嘅 `kids_town.db`。

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

`TC-API-SKILL-ALL-DAMAGE` 保持原樣，唔好改弱。佢用平衡屬性，魔法技能對住魔法普攻，所以高臂力、低知識嘅魔法施放可以假綠。斜向屬性見 `TC-API-SKILL-DMG-FLOOR-SKEWED`。

### TC-API-SKILL-DMG-FLOOR-SKEWED — 斜向屬性施放唔低過物理普攻

除偵察外，每一個學得到嘅技能，施放嗰下對怪物嘅總傷害要 ≥ **同一個小朋友**嘅物理普攻。普攻係 `max(1, player_atk − 怪防)`，爆擊關掉（`ability_crt` 同戰鬥 `player_crt` 都係 0），方差同其他技能測試一樣固定做 0。

兩套合成屬性，每套都係全新一場對住同一隻怪（同一防禦）：

- 高臂力／低知識：自身臂力 20、知識 0。冇臂力建築時普攻大約 35，要 ≥ 30。
- 低臂力／高知識：自身臂力 0、知識 20。

步驟：先打一記普攻量到傷害，清走嗰場，再用同一個人、同一座建築、同一怪防打技能。怪物 HP 設到 50000，扣血唔好被剩餘 HP 封頂。MP 設到夠一次施放。建築等級用該技能嘅 `level_required`。

- 偵察：傷害 0。
- 其餘：施放**總**傷害 ≥ 嗰下普攻。連擊、流星雨、橫掃呢類多下技能，每一下唔使各自 ≥ 普攻。地板只加喺總數：總數已經夠就唔改每一下；總數唔夠先補到總數夠。
- 目錄入面每一個技能都要有，包括火球、知識的力量、冰凍、強光、流星雨，同所有物理技能。而家 `skill_defs` 有 22 個，醫院三個治療技能都計。繃帶、急救、全體治療唔豁免：施放先打物理傷害（總傷害 ≥ 同一個小朋友嘅物理普攻；全體治療打一隻就得），回復量保持 `414ffce` 嘅數字，見 `TC-API-HEAL-STILL-HEALS`。說明加前綴見 `TC-API-HEAL-DESC-PREFIX`，舊庫見 `TC-API-MIGRATE-HEAL-DESC`。

實現時：單下先用 `max(技能公式, 物理普攻公式)`，倍率最後先乘（蓄力 2 倍、必殺低血 1.5 倍、金錢砸 3 倍，以及其他倍率）。多下就係各下加總之後先同普攻比，差幾多先補總數，唔好逐下抬高。測試只鎖總傷害 ≥ 普攻（偵察係 0），唔改 `TC-API-SKILL-ALL-DAMAGE`。

### TC-API-MULTIHIT-UNCHANGED — 總數已夠時每一下唔變

平衡合成小朋友：能力全 0，同其他技能測試一樣。爆擊關（`player_crt` 0），方差 0。總傷害已經高過同一個人嘅物理普攻，所以補底唔應該改到每一下。呢條喺 `414ffce` 要綠，補底之後都要保持綠。

數字係呢個基線打出來嘅，唔好再計過就改：

- 連擊，健身室 Lv4。臂力只得建築 +8，每一下 40、40（總數 80）。怪物 HP 下降等於 80。
- 流星雨，天文台 Lv1，三隻。知識 0，每一隻 25、25、25（總數 75）。

兩場都要先量到普攻，而且總數 > 普攻。

### TC-API-HEAL-STILL-HEALS — 治療加咗傷害，回復量唔變

繃帶、急救、全體治療要先打物理傷害（斜向地板 `TC-API-SKILL-DMG-FLOOR-SKEWED` 嘅六條保持原樣：總傷害 ≥ 同一個小朋友嘅物理普攻；全體治療打一隻就得），然後仍然回復。回復量係 `414ffce` 打出來嘅數字，而家要綠，加咗傷害之後都要保持綠。爆擊關（`player_crt` 0），方差 0。

能力全 0，醫院等級用該技能嘅 `level_required`。HP 設到低過上限，剩餘空間夠晒呢下回復，唔好被上限封頂。回應冇獨立 heal 欄。怪物反擊用高防變成 0（log 有「擋住攻擊」），所以 HP 上升就係回復本身，log 嘅「回復 N HP」要同呢個上升一樣。

數字唔好再計過就改：

- 繃帶，醫院 Lv1：回復 16。
- 急救，醫院 Lv3：回復 46。
- 全體治療，醫院 Lv5：回復 43。

### TC-API-HEAL-DESC-PREFIX — 治療說明加「物理攻擊，」

種子 `skill_defs` 入面繃帶、急救、全體治療嘅說明唔使逐字。三個條件都要中：

- 以「物理攻擊，」開頭。
- 含「回復」。
- 保留強度字：繃帶含「小回復」，急救含「中回復」，全體治療含「全體回復」。

`物理攻擊，並小回復 HP`、`物理攻擊，並中回復 HP`、`物理攻擊，並全體回復 HP` 要過。`物理攻擊，小回復` 呢類保留舊字嘅寫法都過。前綴只得一次。

而家種子係「小回復」「中回復」「全體回復」，呢條係紅。

### TC-API-MIGRATE-HEAL-DESC — 舊庫治療說明就地加前綴

`git show afbc1a6:backend_v2.py` 嘅 `seed_skill_defs` 已經有醫院嘅繃帶、急救、全體治療，說明係小回復／中回復／全體回復。測試用現成嘅舊目錄助手寫入 pytest 暫存庫，唔使再砌一份 `414ffce` 種子，亦唔好打開版控嘅 `kids_town.db`。合成小朋友用 `kid_skills.skill_id` 學咗呢三個 id。

`migrate_db()` 之後：

- 三行原 id 仍然叫繃帶、急救、全體治療。
- 說明以「物理攻擊，」開頭，含「回復」，並且保留強度字（繃帶「小回復」、急救「中回復」、全體治療「全體回復」）。`物理攻擊，並小回復 HP` 要過，唔使等於「物理攻擊，」加舊字。唔好刪行再插入。前綴只得一次。
- `kids` 每一行不變。已學嘅 `(kid_id, skill_id)` 不變。
- 再跑一次 `migrate_db()`，全表不變，唔好變成「物理攻擊，物理攻擊，」。

### TC-API-FORTIFY-TURNS — 強化三回合

施放當回合計第 1 回合（更新：以前寫施放唔計入）。三次怪物攻擊都用加成防禦，扣血等於 `max(0, 怪攻−(player_def+加成))`（方差 0）。第四次等於同一場基線 `max(0, 怪攻−player_def)`。

加成係 `max(1, int(base_value + per_level×工坊等級))`。怪攻要設到高過加成後防禦，所以加成傷害 > 0，同基線分得開，亦唔好同打唔中（0 血）撈亂。對照跟開戰防禦，唔好寫死 0。

### TC-API-LIGHT-CAST-TURN — 強光施放當回合打唔中

步驟：

1. 燈塔 Lv1，公會可以開戰。`random.randint` 同其他技能測試一樣固定（方差 0）。怪物速度 50。怪物 HP 設到 8000。
2. 施放強光。

預期：同一則 `battle-action` 回應入面，玩家扣血 0，而且呢下反擊係打唔中（呢一回合 log 有「攻擊落空」）。呢下係「之後 2 次怪物攻擊」嘅第 1 次。技能本身仍然對怪物造成魔法傷害，戰鬥未結束。基線反擊 `max(0, 怪攻−player_def)` 要 > 0，先至分得到打唔中同普通扣血。

### TC-API-LIGHT-BOUNDARY — 強光第 2 次打唔中，第 3 次恢復

步驟：

1. 同 `TC-API-LIGHT-CAST-TURN` 施放強光。
2. 再兩次普攻。每次怪物都反擊。怪物要活到第 3 次反擊。

預期：施放之後嗰次反擊（第 2 次，最後一次受影響）扣血 0，log 有「攻擊落空」。再下一次（第 3 次怪物攻擊）扣血等於基線 `max(0, 怪攻−player_def)`，log 唔再係打唔中。

### TC-API-FREEZE-CAST-TURN — 冰凍施放當回合攻擊 ×0.7

步驟：

1. 圖書館 Lv4，公會可以開戰。方差 0，怪物速度 50，怪物 HP 8000。
2. 用該場怪物 `atk` 同 `player_def` 計。削弱先 `int(怪攻×0.7)`，再 `max(0, 攻−player_def)`。基線係未削弱嘅同一條式。兩個數要分得開，而且削弱後仍然 > 0。
3. 施放冰凍。

預期：同一則回應嘅反擊等於削弱值，唔係基線。戰鬥未結束。

### TC-API-FREEZE-BOUNDARY — 冰凍第 2 次仍然削弱，第 3 次恢復

步驟：同 `TC-API-FREEZE-CAST-TURN` 施放冰凍，再兩次普攻。怪物要活到第 3 次反擊。

預期：第 2 次怪物攻擊（施放後第一下，最後一次受影響）仍然係削弱值。第 3 次等於基線。

### TC-API-FORTIFY-CAST-TURN — 強化施放當回合用加成防禦

步驟：

1. 工坊 Lv4。怪物攻擊設到高過「開戰 `player_def` + 強化加成」，加成後反擊仍然 > 0，而且少過基線。加成係 `max(1, int(base_value + per_level×工坊等級))`，加落開戰 `player_def`。反擊係 `max(0, 怪攻−防禦)`（方差 0）。怪物速度 50，HP 8000。
2. 施放強化。

預期：同一則回應嘅反擊等於加成防禦計出嚟嘅傷害，唔係基線。戰鬥未結束。

### TC-API-FORTIFY-BOUNDARY — 強化第 2、3 回合仍然加成，第 4 次恢復

施放當回合計第 1 回合。步驟：同 `TC-API-FORTIFY-CAST-TURN` 施放強化，再三次普攻。怪物要活到第 4 次反擊。

預期：之後兩次怪物攻擊（第 2 回合、第 3 回合；第 3 回合係最後一次）仍然係加成傷害。再下一次（第 4 次怪物攻擊）等於基線。

### TC-API-SHIELD-PERSIST — 盾擊減半留到打中

`player_dodge` 設成 100，`(1,100)` 固定擲 100，施放嗰下反擊係 0，減半唔消耗。下一擊先係對照反擊嘅整數一半。再下一擊恢復全額。

### TC-API-SKILL-DESC-05 — 說明關鍵字

唔好逐字，只係關鍵字：

- 強化含「3 回合」。
- 盾擊含「下一次被打中」或「下次被打中」。
- 強光含「2 次」，以及「打唔中」或「打不中」。
- 冰凍唔好含「減速」。效果係 2 次怪物攻擊（包括施放當回合反擊）攻擊 ×0.7，速度唔變。說明要講到攻擊下降：含「攻擊力下降」「攻擊下降」「攻擊力減」或「傷害減少」其中一句，而且同一段說明有「怪物」或「敵人」。說明文字嘅斷言唔改。而家種子係「魔法攻擊，之後 2 回合怪物攻擊力下降」，冇「減速」。
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
