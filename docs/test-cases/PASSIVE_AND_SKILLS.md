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

---

## 面板

文案鎖喺 `tests/sheet_buff_truth_spec.py` 嘅 `sheet_effect_label`。

| ID | 描述 |
|----|----|
| TC-FE-TOWN-UX-SHEET-BUFF-01 | 圖書館 Lv.2「知識 +4」。零 `.fn`。唔好「任務多經驗」。 |
| TC-FE-TOWN-UX-SHEET-BUFF-02 | 工坊零 `.fn`、唔好 stub toast。唔查數字。要綠。 |
| TC-FE-TOWN-UX-SHEET-BUFF-ZH-01 | 工坊 Lv.3「創意 +6」。 |
| TC-FE-TOWN-UX-SHEET-BUFF-ZH-02 | 健身室 Lv.1「臂力 +2」。 |
| TC-FE-SHEET-BUFFVAL-01 | 商店 Lv.2「起屋／升級金幣八五折」（`buff_vals[1]=0.85`，唔係九折）。要綠。 |
| TC-FE-SHEET-UNWIRED-01 | 自訂 `zzz_unwired`、值 9：正好「未開放」，唔好出現 9。要綠。 |
| TC-FE-SHEET-BANK-01 | 測試庫插入「銀行」：技能句「金錢砸」。而家係「未開放」，所以紅。 |
| SHEET-BUFF-TRUTH-01 | 圖書館「知識 +2」。API bonus 0。 |
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
| TC-API-SKILL-FREEZE | 冰凍 | 魔法攻擊，怪物 HP 跌 `max(1, int(base_value + per_level×圖書館等級 + player_int))`（方差 0）。圖書館 Lv4、知識 0 係 56。`matk = int(5 + player_int×1.5)`，公式加嘅係 `player_int`。施放唔計入兩回合，嗰下反擊仍然係原本攻擊力，唔好變 0。之後兩次玩家行動先 `int(原攻×0.7)` 再代入 `max(0, 攻−玩家防)`。區 1 攻 7、防 0：原本 7，削弱後 4。第三次恢復 7。 |
| TC-API-SKILL-EXECUTE | 必殺 | 敵人 HP ≤ 25% 上限時，傷害至少係滿血同一擊嘅 1.5 倍。 |
| TC-API-SKILL-REPAIR | 修復 | 回復 MP，HP 唔變。防禦拉到 999，反擊係 0。 |
| TC-API-SKILL-FORTIFY | 強化 | 下一擊受到嘅傷害少過冇開強化嘅對照反擊。 |
| TC-API-SKILL-SCOUT | 偵察 | 怪物 HP 唔變。區 1 弱點係「火」（區 2「冰」、區 3「雷」）。 |
| TC-API-SKILL-CHARGE | 蓄力 | 倍率鎖 ×2。下一擊等於 2×普攻（臂力 0、區 1：普攻 5，蓄力後 10）。蓄力本身唔造成傷害。說明要正好「下次攻擊 2 倍」（開戰 `skills`、`GET /api/kids/<id>/skills`、戰鬥 log）。而家說明係「下次攻擊 1.5 倍」。 |
| TC-API-SKILL-SHIELD | 盾擊 | 舊名「挑釁」唔好再出現。有物理傷害，呢一回合受到嘅傷害係對照反擊嘅整數一半。 |
| TC-API-SKILL-GALE | 疾風斬 | 舊名「迴避」唔好再出現。有物理傷害，呢一回合玩家 HP 唔跌。 |
| TC-API-SKILL-KNOWLEDGE | 知識的力量 | 圖書館。施放之後 3 回合 `player_int` +3×等級（Lv1 +3、Lv5 +15）。火球傷害比對照多正好呢個數。第 4 下同 `player_int` 返原值。施放本身唔造成傷害。 |
| TC-API-SKILL-TRAINING | 鍛鍊的成果 | 健身室。施放之後 3 回合臂力 +3×等級。普攻等於 `max(1, int(5+(str+3×等級)×1.5)−敵防)`，`player_str`／`player_atk` 同步。第 4 下返原值。施放本身唔造成傷害。 |
| TC-API-SKILL-MEAL | 營養餐 | 農場。持續回血，唔係即時治療。施放當下 HP 不變，MP 只扣消耗。之後 3 回合每回合回大約最大 HP 嘅 8%（允許大約 6%–14% 嘅取整同少量等級加成）。Lv5 每回合回血 ≥ Lv1。第 4 回合停止。唔好順便回 MP。 |
| TC-API-SKILL-COIN | 金幣袋 | 商店。打贏先至多 20 金幣。逃跑唔加。冇用技能嘅勝場係對照。 |
| TC-API-SKILL-FLASH | 強光 | 燈塔。有魔法傷害。之後兩次玩家行動敵人打唔中，第三次先至再扣血。 |
| TC-API-SKILL-METEOR | 流星雨 | 天文台。三隻敵人每一隻 HP 都跌。 |
| TC-API-SKILL-GOLD | 金錢砸 | 要有 `building_defs` 名「銀行」。每次扣 10 金幣，傷害等於 3 倍普攻（方差 0）。金幣少過 10：400 `insufficient_gold`，金幣同怪物 HP 都唔變。 |

新技能假設所屬建築 Lv1 就學到（知識的力量、鍛鍊的成果、營養餐都係）。舊技能嘅等級門檻照種子：蓄力健身室 1、連擊 4、冰凍圖書館 4、火球圖書館 2、偵察公會 2、修復工坊 2、強化 4、必殺競技場 5。`TC-API-SKILL-KNOWLEDGE` 喺測試庫把火球 `level_required` 改成 1，先至能量 Lv1 圖書館嘅魔法傷害；產品種子唔改。
