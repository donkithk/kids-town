# 能力同戰鬥數值用字

`#sheetBuff` 同之後任何戰鬥 HUD 嘅用字，以呢份表做唯一來源。測試 `TC-FE-SHEET-TWO-LAYER` 會對住表入面嘅中文斷言。戰鬥畫面而家冇攻擊力、魔法力、爆擊率、閃避率、防禦力呢啲字（只得 `HP`、`MP`，同「攻擊」「逃走」兩個指令），所以括號入面唔好再去對 HUD，要對第二表。

能力層中文同 `index.html` 嘅 `TIP_NAMES` 一樣。而家 `town-four-scene.js` 嘅 `levelBuff` 仍然印 `buff_vals` 句子（例如任務多經驗、未開放），未印下面嘅兩層句。兩層句要用呢度嘅字。

## 1. 能力層

`calc_ability_buffs`（`backend_v2.py`）返回嘅鍵係 `str`、`int`、`spd`、`crt`、`brv`。中文係 `+N` 前面嗰個字。

| 能力鍵 | 中文 | 邊座建築加 |
| --- | --- | --- |
| `str` | 臂力 | 健身室（每級 +2）、競技場（每級 +2） |
| `int` | 知識 | 圖書館（每級 +2） |
| `crt` | 創意 | 工坊（每級 +2） |
| `spd` | 速度 | 競技場（每級 +1） |
| `brv` | 勇氣 | 探險公會（每級 +2） |

五座面板因此係：圖書館知識、健身室臂力、工坊創意、競技場臂力同速度、探險公會勇氣。

`BUILDING_ABILITY_MAP` 而家仲將天文台映射去 `int`。鎖定測試 `TC-API-BLD-PASSIVE-OBS` 要求天文台唔加知識，所以呢度唔當天文台係知識來源。

## 2. 戰鬥數值層

`calc_battle_stats` 返回嘅鍵（括號同測試對嘅係呢啲鍵，唔係開戰 JSON 嘅 `player_` 名）。攻擊力、魔法力、爆擊率、閃避率、防禦力、速度係設計師定嘅字。百分比（百分點）先至喺面板加 `%`；整數冇後綴。

| 戰鬥鍵 | 中文 | 單位 | 邊個能力餵佢 |
| --- | --- | --- | --- |
| `atk` | 攻擊力 | 整數 | `str` 臂力 |
| `matk` | 魔法力 | 整數 | `int` 知識 |
| `crt` | 爆擊率 | 百分比 | `crt` 創意 |
| `dodge` | 閃避率 | 百分比 | `spd` 速度 |
| `def` | 防禦力 | 整數 | `brv` 勇氣 |
| `spd` | 速度 | 整數 | `spd` 速度（先手用；面板括號唔用呢鍵，見顯示規則） |
| `crit_dmg` | 爆傷 | 倍率（小數，唔係百分比，亦唔係整數） | `crt` 創意 |
| `hp` | HP | 整數 | 無。跟等級，被動建築唔改 |
| （函數冇呢鍵） | MP | 整數 | 無。跟等級，被動建築唔改 |

開戰 JSON 對照（方便同 `player_atk` 呢類名對上，面板唔好印英文鍵）：

| `calc_battle_stats` | 開戰 JSON |
| --- | --- |
| `atk` | `player_atk` |
| `matk` | 而家 JSON 冇 `player_matk` |
| `crt` | `player_crt` |
| `dodge` | `player_dodge` |
| `def` | `player_def` |
| `spd` | `player_spd` |
| `crit_dmg` | `player_crit_dmg` |
| `hp` | `player_hp`、`player_max_hp` |
| （MP 唔係函數鍵） | `player_mp`、`player_max_mp` |

代碼冇 `evasion` 呢個鍵。閃避鍵係 `dodge`。

`calc_battle_stats` 亦返回 `str`、`int`、`brv`。佢哋係能力點原值（回聲），唔係另一個戰鬥數值，唔另起中文，亦唔入括號。`spd` 同樣係能力點原值，另外用 `player_spd > 怪物 spd` 決定先手；速度能力嘅括號仍然係閃避率。

`crit_dmg` 係創意會一併郁嘅第二個數（函數註解寫「爆擊倍率」）。面板括號只用爆擊率。**爆傷**係暫定嘅兩個字，設計師要確認。

HP、MP 保持戰鬥 HUD 嘅字面 `HP`、`MP`（`index.html`：`HP ${血}/${上限} · MP ${mp}`）。MP 唔好叫魔力，同魔法力太近。

## 顯示規則

格式：`{能力} +{N}（{戰鬥數值} +{M}）`。

競技場兩個能力用「、」連接，每個能力自己一對括號。例子（數字只係例子，唔好寫死）：`臂力 +2（攻擊力 +3）、速度 +1（閃避率 +1.5%）`。

括號用轉換之後嘅戰鬥鍵，同 `tests/sheet_two_layer.py` 嘅 `converted_field` 一樣。能力點原值（`str`／`int`／`spd`／`brv`）同 `crit_dmg` 唔入括號。

| 能力 | 括號 | 例子（只係例子） |
| --- | --- | --- |
| 臂力 `str` | 攻擊力 `atk` | `臂力 +2（攻擊力 +3）` |
| 知識 `int` | 魔法力 `matk` | `知識 +2（魔法力 +3）` |
| 創意 `crt` | 爆擊率 `crt` | `創意 +2（爆擊率 +4%）` |
| 速度 `spd` | 閃避率 `dodge` | `速度 +1（閃避率 +1.5%）` |
| 勇氣 `brv` | 防禦力 `def` | `勇氣 +2（防禦力 +1）` |

- N 係同一個小朋友 `calc_ability_buffs` 有呢座同冇呢座嘅差。M 係同一個小朋友 `calc_battle_stats` 對應戰鬥鍵嘅差。存倉（`stored=1`）唔計。兩個數都由函數計，唔好手寫公式。
- 正數一定帶前導 `+`。
- 最多一個小數位。整數唔寫 `.0`：`+3`，`+1.5` 先至保留小數。
- 單位係百分比先加 `%`，貼住數字，否則冇後綴：`+4%`、`+1.5%`、`+3`。
- M 係 0 就唔寫括號，唔好寫 `（… +0）`。
- 面板禁止：英文鍵（`player_atk`、`matk`、`int` 等）、`.0` 結尾、用魔力稱呼 MP。

而家 `calc_ability_buffs` 嘅 SQL 未排除 `stored=1`，`calc_battle_stats` 亦未讀建築加成。上面係顯示合約：存倉唔計，N、M 用兩個函數嘅差。呢份表唔改程式。

## 單位核對

爆擊同閃避都係百分比（百分點）。1.5 閃避即係 1.5 個百分點，面板寫 `+1.5%`，唔係一個冇單位嘅小數。

- 爆擊。`backend_v2.py` 第 3574 行：`'crt': min(50, crt_v * 2)`，同行註解 `# crit %`。判定喺第 4038 行：`random.randint(1, 100) <= player_crt`。`tests/test_battle_formulas.py` 第 27 行寫 `CRT% = min(50, crt*2)`。上限 50 即係 50%。創意 +2 令 `crt` 由 0 變 4，就係 `+4%`。
- 閃避。`backend_v2.py` 第 3576 行：`'dodge': min(40, spd_v * 1.5)`，同行註解 `# dodge %`。判定喺第 4168 行：`random.randint(1, 100) <= bd['player_dodge']`。`tests/test_battle_formulas.py` 第 28 行寫 `DODGE% = min(40, spd*1.5)`，第 146 行註解「回避: roll player_dodge%」。上限 40 即係 40%。競技場每級速度 +1 時，`dodge` 差係 1.5，即 1.5 個百分點。
- `randint(1, 100)` 只出整數，所以存咗 1.5 嘅時候只有骰出 1 先算閃到，實際次數同 1% 一樣。單位仍然係百分比。面板跟函數嘅 1.5，寫 `+1.5%`，唔好改成 `+1%` 或者 `+2%`。

速度戰鬥鍵 `spd` 唔係百分比：第 3577 行 `'spd': spd_v`，第 4166 行用 `player_spd > 怪物 spd` 決定先手。`crit_dmg` 亦唔係百分比：第 3575 行 `1.5 + crt_v * 0.02`，第 4039 行爆擊時 `dmg * player_crit_dmg`。
