# 能力同戰鬥數值用字

`#sheetBuff` 同之後任何戰鬥 HUD 嘅用字，以呢份表做唯一來源。測試 `TC-FE-SHEET-TWO-LAYER` 會對住下面兩張表嘅中文同單位斷言。戰鬥畫面而家冇攻擊力、魔法力、爆擊率、閃避率、防禦力（只得 `HP`、`MP`，同「攻擊」「逃走」），所以括號入面對呢份表，唔好對 HUD。

能力層中文同 `index.html` 嘅 `TIP_NAMES` 一樣。而家 `town-four-scene.js` 嘅 `levelBuff` 仍然印 `buff_vals` 句子，未印兩層句。

戰鬥數值層嘅 `欄位` 用開戰 JSON 鍵（例如 `player_atk`）。`calc_battle_stats` 返回嘅短鍵寫喺備註。

## 能力層

| 欄位 | 中文 | 單位 | 備註 |
| --- | --- | --- | --- |
| str | 臂力 | 整數 | 健身室每級 +2；競技場每級 +2 |
| int | 知識 | 整數 | 圖書館每級 +2。天文台而家喺 BUILDING_ABILITY_MAP 映射去 int，但 TC-API-BLD-PASSIVE-OBS 要求唔加知識，所以唔計天文台。 |
| spd | 速度 | 整數 | 競技場每級 +1 |
| crt | 創意 | 整數 | 工坊每級 +2 |
| brv | 勇氣 | 整數 | 探險公會每級 +2 |

`calc_ability_buffs` 返回嘅鍵就係上表 `欄位`：`str`、`int`、`spd`、`crt`、`brv`。五座面板係圖書館知識、健身室臂力、工坊創意、競技場臂力同速度、探險公會勇氣。

## 戰鬥數值層

| 欄位 | 中文 | 單位 | 備註 |
| --- | --- | --- | --- |
| player_atk | 攻擊力 | 整數 | calc_battle_stats 鍵 atk。int(5 + str×1.5)。餵 str 臂力。健身室、競技場。 |
| player_matk | 魔法力 | 整數 | calc_battle_stats 鍵 matk。int(5 + int×1.5)。餵 int 知識。圖書館。而家開戰 JSON 未輸出呢鍵。 |
| player_crt | 爆擊率 | 百分比 | calc_battle_stats 鍵 crt。min(50, crt×2)，同 1 到 100 嘅骰比較。餵 crt 創意。工坊。 |
| player_dodge | 閃避率 | 百分比 | calc_battle_stats 鍵 dodge。代碼冇 evasion。min(40, spd×1.5)，同 1 到 100 嘅骰比較。餵 spd 速度。競技場。 |
| player_def | 防禦力 | 整數 | calc_battle_stats 鍵 def。int(brv×0.6)。餵 brv 勇氣。探險公會。 |
| player_spd | 速度 | 整數 | calc_battle_stats 鍵 spd，等於速度能力點，用嚟先手。面板括號唔用呢鍵；速度能力嘅括號係 player_dodge。 |
| player_hp | HP | 整數 | calc_battle_stats 鍵 hp。跟等級 20 + level×8。被動建築唔改。HUD 字面 HP。亦有 player_max_hp。 |
| player_mp | MP | 整數 | 唔係 calc_battle_stats 鍵。跟等級 10 + level×3。被動建築唔改。HUD 字面 MP。唔好叫魔力。亦有 player_max_mp。 |

`player_crit_dmg`（爆擊傷害倍率，1.5 + crt×0.02）唔入面板、唔入括號；將來 HUD 如果要顯示，中文用「爆擊傷害」，格式待定。

`calc_battle_stats` 亦返回 `str`、`int`、`brv`。佢哋係能力點原值，唔另起中文，亦唔入括號。

## 顯示規則

格式：`{能力} +{N}（{戰鬥數值} +{M}）`。

競技場兩個能力用「、」連接，每個能力自己一對括號。例子（數字只係例子，唔好寫死）：`臂力 +2（攻擊力 +3）、速度 +1（閃避率 +1.5%）`。

括號用轉換之後嘅戰鬥數值，同 `tests/sheet_two_layer.py` 嘅 `converted_field` 一樣。能力點原值（`str`／`int`／`spd`／`brv`）同 `player_crit_dmg` 唔入括號。

| 能力 | 括號 | 例子（只係例子） |
| --- | --- | --- |
| 臂力 str | 攻擊力 player_atk | 臂力 +2（攻擊力 +3） |
| 知識 int | 魔法力 player_matk | 知識 +2（魔法力 +3） |
| 創意 crt | 爆擊率 player_crt | 創意 +2（爆擊率 +4%） |
| 速度 spd | 閃避率 player_dodge | 速度 +1（閃避率 +1.5%） |
| 勇氣 brv | 防禦力 player_def | 勇氣 +2（防禦力 +1） |

- N 係同一個小朋友 `calc_ability_buffs` 有呢座同冇呢座嘅差。M 係同一個小朋友 `calc_battle_stats` 對應短鍵嘅差。存倉（`stored=1`）唔計。兩個數都由函數計，唔好手寫公式。
- 正數一定帶前導 `+`。
- 最多一個小數位。整數唔寫 `.0`：`+3`，`+1.5` 先至保留小數。
- 單位係百分比先加 `%`，貼住數字，否則冇後綴：`+4%`、`+1.5%`、`+3`。
- M 係 0 就唔寫括號，唔好寫 `（… +0）`。
- 面板禁止：英文鍵（`player_atk`、`matk`、`int` 等）、`.0` 結尾、用魔力稱呼 MP。

而家 `calc_ability_buffs` 嘅 SQL 未排除 `stored=1`，`calc_battle_stats` 亦未讀建築加成。上面係顯示合約。呢份表唔改程式。

## 單位核對

爆擊同閃避都係百分比（百分點）。1.5 閃避即係 1.5 個百分點，面板寫 `+1.5%`。

- 爆擊。`backend_v2.py` 第 3574 行：`'crt': min(50, crt_v * 2)`，同行註解 `# crit %`。判定喺第 4038 行：`random.randint(1, 100) <= player_crt`。`tests/test_battle_formulas.py` 第 27 行寫 `CRT% = min(50, crt*2)`。上限 50 即係 50%。創意 +2 令呢個數由 0 變 4，面板寫 `+4%`。
- 閃避。`backend_v2.py` 第 3576 行：`'dodge': min(40, spd_v * 1.5)`，同行註解 `# dodge %`。判定喺第 4168 行：`random.randint(1, 100) <= bd['player_dodge']`。`tests/test_battle_formulas.py` 第 28 行寫 `DODGE% = min(40, spd*1.5)`，第 146 行註解「回避: roll player_dodge%」。上限 40 即係 40%。競技場每級速度 +1 時，差係 1.5，即 1.5 個百分點。
- `randint(1, 100)` 只出整數，所以存咗 1.5 嘅時候只有骰出 1 先算閃到。單位仍然係百分比。面板跟函數嘅 1.5，寫 `+1.5%`。

`player_spd` 唔係百分比：第 3577 行 `'spd': spd_v`，第 4166 行用 `player_spd > 怪物 spd` 決定先手。`player_crit_dmg` 亦唔係百分比：第 3575 行 `1.5 + crt_v * 0.02`，第 4039 行爆擊時 `dmg * player_crit_dmg`。

「未排除 stored=1／未讀建築加成／未輸出 player_matk」呢幾句描述基線分支 #49 `d2850d5`（紅燈，被動數值轉綠嘅 #50 之前），唔係最終產品。
