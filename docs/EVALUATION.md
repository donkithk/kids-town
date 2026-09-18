# Kids Town 產品／工程評估報告

> **性質**：唯讀調查，唔改遊戲玩法。  
> **範圍**：`backend_v2.py`、`backend.py`、`index.html`、PWA、測試、設計文件、已提交嘅 `kids_town.db`。  
> **日期**：2026-09-18  
> **程式識別名**（函數、路由、欄位）保留英文。

---

## 0. 總結（先讀呢段）

Kids Town 係一個**家庭用、已可玩**嘅任務積分 + 開羅風城鎮 PWA。核心 enticement 清楚：小朋友做家課換金幣，再起屋、探險、打怪。家長側有任務 CRUD、加減分、統計雛形。戰鬥系統（屬性、技能、Boss、pity）比文件寫嘅「Phase 5 完成」更深。

但產品同工程狀態係 **prototype 當 production save 用**：

| 層面 | 判斷 |
|------|------|
| 遊戲循環 | 骨架齊，但多個設計承諾未接線（建築 buff、探險扣金幣、5 區戰鬥、材料統一） |
| 可玩性 | 家庭內部用得；對外會覺得關卡斷、獎勵唔對、等待長 |
| 架構 | Flask 單體 + SQLite + 單檔 SPA；可以撐小規模，唔適合多家庭 |
| 安全／私隱 | **未達兒童產品最低線**：API 無 session、PIN 明文、預設管理員、資料庫入 git |
| 變現 | `MONETIZATION_STRATEGY.md` 全未實作；而家無訂閱、無 feature gate |

**建議主軌道：B（漸進重構），以 A 做第 0 階段。** 理由：遊戲內容同戰鬥公式有價值，唔值得全盤重寫；但安全同資料模型必須先修，否則唔可以再加功能或對外示範。唔建議即刻 C（綠地重建），除非明確要上 App Store + COPPA 合規產品（屆時 auth／私隱層幾乎一定要換，但玩法同美術仍應搬過去）。

**最嚴重 10 項**（PR 摘要同源）：

1. **P0** 全部 `/api/*` 無伺服器端授權（IDOR、任意加減分、`inventory/add`）
2. **P0** 預設管理員 `admin` / `admin123`，登入頁預填、開機 print
3. **P0** 小朋友 PIN 明文；`kids_town.db` 已 commit，靜態路由可直接下載
4. **P0** 家長密碼 SHA-256（有 bcrypt TODO）；管理員更接受明文比對
5. **P1** 設計 10 座建築／5 區探險 vs DB 11 座建築／3 隻怪物
6. **P1** `building_defs.buff_type`（`task_bonus`、`daily_gold` 等）從未套用
7. **P1** 材料經濟分裂：探險掉 `iron`/`gem`，商店要 `gear`/`glass`
8. **P1** `ability_atk` 遷移殘留 → `/experience`、`/abilities/assign` 會 `KeyError`
9. **P1** 根路徑 `/` 期望 `../dashboard/index.html`，本 repo 404
10. **P1** 測試複製真實 DB、硬編碼 Windows Python；覆蓋偏戰鬥、幾乎無 auth 強制

---

## 1. 遊戲循環／UX 流程

設計文件（`DEV_PLAN.md`）寫嘅主循環：

```
做任務／家課 → 金幣 + 經驗
       ↓
探險（消耗金幣）→ 木頭／磚頭／鐵
       ↓
收集材料 → 起建築物／升級
       ↓
建築物 buff → 更有效率做任務 + 探險
       ↓
特殊事件 → 關鍵材料 → Lv.5
       ↓
解鎖新區域 → 新建築設計圖
```

實作係一條**分叉、部分斷線**嘅循環。以下按玩家路徑對照。

### 1.1 家長任務 → 獎勵

| 步驟 | 實作 | 對齊程度 |
|------|------|----------|
| 家長開任務 | `POST /api/tasks`（`backend_v2.py`）；可指定 `kid_id` 或 `NULL`（全體） | 有 |
| 小朋友見到自己嘅任務 | `GET /api/tasks?kid_id=` 過濾自己 + 全體；全體完成寫入 `task_completions` | 有（近期 TDD） |
| 完成頒金幣 | `complete_task()` 加 `kids.points` + `points_log` | 有 |
| 完成頒經驗／材料 | `award_task_drops()`：XP `max(5, points//2)` + 1–2 材料 | **後端有、前端幾乎唔顯示** |
| 連續日 | `update_streak()` 用 UTC 日曆日 | 有；時區可能錯（香港 UTC+8） |
| 成就 | `check_achievements()` 12 種 | 後端有；前端 `completeTask()` 只 toast 金幣，忽略 `achievements` / `experience_gained` / `material_drops` |

前端 `index.html` 嘅 `completeTask()`：

- 成功只顯示 `🎉 任務完成！獲得 🪙{points_awarded}`
- **唔讀** 經驗、材料、成就彈窗（`DEV_PLAN.md` Phase 5 寫「Kairosoft 風格成就解鎖彈窗」）

**家長入口斷裂：**

- 正式家長登入：`doLogin()` → `st('manage')`，但 `st()` **冇呼叫** `renderManage()`，管理頁可能空白直到其他事件觸發。
- 小朋友若知前端常數 `PARENT_PASSWORD = '1234'`，`prompt` 即可進管理頁（同伺服器家長帳號無關）。
- 管理 API（建任務、刪小朋友、加減分）**完全無證明你係家長**。

**重複任務：** 完成後 `completed=1`，要等 `POST /api/tasks/refresh-recurring`（前端載入時打一次）。當日小朋友會見到「已完成」而唔係「每日任務仲可以做」——對兒童 UX 易混淆。`weekdays`／`weekly` 用 UTC `datetime.utcnow()`，香港夜晚 8 點後可能提早換日。

### 1.2 金幣 → 城鎮／建築

設計：10 座建築、材料成本、`unlock_region`（燈塔 r3、競技場 r4、天文台 r5）、buff 影響任務／探險。

**Seed（空庫）有 10 座**（`seed_building_defs()`）：圖書館、健身室、農場、商店、醫院、探險公會、工坊、燈塔、競技場、天文台。

**已提交 DB 有 11 座**：額外 `id=11 🏦 銀行`（cost 150），**唔喺 seed**。`all_buildings` 成就用 `COUNT(building_defs)`，所以呢個 save 要起 11 座先當「全部」。

更嚴重嘅資料漂移：

- 探險公會（id=6）seed 材料係 wood/brick/iron；**DB 變成 `materials='{}'`** → 只需 600 金幣、零材料。
- `migrate_db()` 把 defs 裏 `iron→gear`、`gem→glass`、`star_shard→glass`；天文台 DB 變成 glass×13（seed 係 gem 10 + star_shard 3 合併）。

**放置 UX：**

- 生產前端**唔再係 Canvas**（`initCanvas()` 空函數）；城鎮係 DOM 絕對定位、24×16 格、`assets-c/` PNG。
- `DEV_PLAN.md` 仍寫「Canvas 城鎮（開羅風格）」——文件過時。
- 商店／建築分頁雙路徑：商店會進入 `startPlacement`；建築分頁「建造」只 toast「點擊下方空地」，**唔啟動放置模式**。
- 每種建築每小朋友限 1 座（合理）；`unlock_region` **前後端都唔檢查**。
- HUD 材料只顯示 wood / brick / glass / gear；探險掉落嘅 iron / gem / star_shard 只喺背包頁先見到。

**建築 buff：設計核心，實作幾乎冇。**  
`buff_type` / `buff_vals` 只被 SELECT 返回，**從來冇**用嚟：

- 任務額外經驗（圖書館 `task_bonus`）
- 農場每日金幣（`daily_gold`）
- 商店折扣（`discount`）
- 連續保護（`streak_protect`）
- 探險回復／範圍／金幣倍率／發現率

唯一接線嘅「建築好處」係戰鬥：`BUILDING_ABILITY_MAP` + `skill_defs`（建築等級解鎖技能）。對「做家課更有效率」呢條主循環，建築而家只係裝飾 + 戰鬥 RPG。

探險門檻：前端要求 `def_id === 6`（公會）先開探險頁。後端 `expedition/start` **唔檢查公會**——改 API 可跳過。

### 1.3 探險／戰鬥／Boss

前端 `REGIONS` 寫死 5 區（森林→雪山→沙漠→火山→星輝），時長 2–12 小時。解鎖靠 `explored_regions` 鏈式（探索過上一區）。

三種模式（`expedition-v2-plan.md`）：

| 模式 | 行為 | 問題 |
|------|------|------|
| `explore` | 等 `duration_hours` 再 `claim` | **唔扣金幣**（`DEV_PLAN` 寫「探險消耗金幣」）；UI 嘅 🪙30/60/… 睇落似費用，其實係預計獎勵。Claim 之後該區按鈕變「已完成」，**好難再農材料**。長時間真等（火山 8h、高原 12h）對兒童偏 grind。 |
| `quiz` | 前端 `hours=0` 即時可 claim；另有答題 API | 學科同「探險」心智模型重疊；題庫只 15 題 |
| `battle` | 即時戰鬥 | 見下 |

**戰鬥 vs 5 區：**

- `monsters` 表／seed 只有 region 1–3（野狼、白熊、巨蠍）。
- `battle_start` 無 row → **404 `No monster for this region`**。區 4–5 戰鬥係死路。
- 戰鬥用 `calc_monster_stats(region_id)`，**唔用** DB 嘅 hp/atk；DB 主要提供名／圖示／金幣／材料模板。
- 等級門檻 `region_id * 2`（後端有、前端大廳唔預先標 Lv）。
- 每區每日勝場 1 次（`daily_battles`）。

**Boss：** 程序化（`calc_boss_stats`），耗 gem×1，贏後每週冷却，要上一區 first_kill。區 4–5 Boss  theoretically 可打（唔依賴 monsters 表），但 gem 來源混亂（見材料節）。前端 `MONSTER_ART` 只有 1–3。

**成長：**

- 而家**有** `kids.level` / `experience` / `stat_points` / 五維能力（`economy_analysis.md` 寫「無 XP」——文件過時，抽取日期 2026-06-06）。
- `EXP_PER_LEVEL = 25`；註解寫「Lv.2 = 100exp」，公式實際 Lv.1→2 要 **25**。
- HUD 經驗條：`(kid.level||1) * 100` 去除總經驗——**同後端三角曲線完全唔同**，高等級條會長期滿或長期空。
- `kid.stars` HUD 欄位後端 `kids` 表**無 stars 欄**，多數時候顯示 0。
- `characterImage()` 永遠返回 `assets-c/boy.png`。

### 1.4 循環哪裏「唔清／肝／壞／唔對齊」

1. **主循環承諾嘅建築 buff 未接線** → 起屋唔改變做任務效率；小朋友唔理解點解要起圖書館。
2. **探險唔消耗金幣、探索又係一次性** → 材料主要靠任務隨機掉落同戰鬥；同 `DEV_PLAN` 箭頭圖相反。
3. **5 區地圖、3 隻怪** → 後期探險頁有按鈕但戰鬥 404。
4. **材料兩套語言**（iron vs gear）→ 背包有鐵，商店要齒輪，感覺「農咗無用」。
5. **公會 600 金幣門檻** + 探索 2–12 小時 → 新號要先狂做任務先入得主循環；DB 裏公會材料被清空反而令呢個門檻畸形地低（只要金幣）。
6. **任務完成反饋只顯示金幣** → 經驗／材料／成就係隱藏獎勵，兒童動機弱。
7. **家長登入唔 hydrate 管理頁**；小朋友用 `1234` 可進管理。
8. **變現文件**寫「核心循環 100% 免費、Premium 額外 3 區」——而家 5 區已喺免費前端，且後 2 區戰鬥壞咗；無任何 subscription flag。
9. **Wireframe**（8 個固定 plot、探險解鎖新建築設計圖）同生產（自由格子、每類型 1 座、`unlock_region` 閒置）係兩個產品。
10. **Admin 登入 fallback `currentKidId = 4`**（小強，Lv.36、8478 分）——開發用角色洩進正式流程。

---

## 2. 缺陷同不一致（按嚴重性）

### P0 — 安全／資料（必須先停，先修）

| ID | 問題 | 證據 |
|----|------|------|
| P0-1 | **API 無認證／無 session**。無 `SECRET_KEY`、無 cookie、無 `@before_request`。任何客戶端可呼叫任意 `kid_id`。 | `backend_v2.py` Flask app 初始化；路由一覽見 §3。例：`POST /api/kids/<id>/points`、`POST .../inventory/add`、`POST /api/auth/create-kid` 只信 body 裏嘅 `parent_id`。 |
| P0-2 | **預設管理員** `admin` / `admin123`；開機 print；`showAdminLogin()` 預填表單。 | `migrate_db_v3()` seed；`index.html` `showAdminLogin`；`index-legacy.html` 同樣。 |
| P0-3 | **管理員登入接受明文或 hash**。 | `auth_login()`：`admin['password'] == password or ... hash_password(password)`。 |
| P0-4 | **小朋友 PIN 明文**存 `kid_auth.pin`；缺 record 時插入 `'0000'`；legacy `/api/login` 成功時把 PIN `'0000'` 送返客戶端。 | schema DEFAULT；`migrate_db_v3`；`login()`。已提交 DB：多數 `0000`，另有一條似 YYYYMMDD 嘅 PIN（兒童 DOB 風險）。 |
| P0-5 | **`kids_town.db` 入 git**（`.gitignore` 無 `*.db`）。近期 commit message：「更新遊戲數據 (小朋友遊玩進度)」。含真實名、username、email、PIN。 | `git ls-files`；`git log -- kids_town.db`。 |
| P0-6 | **靜態伺服器可洩漏 DB 同原始碼**。`GET /kids/<path:filename>` 以 repo 根為目錄、**無** path normalize（對比 `/assets-c/` 有 traversal 檢查）。`/kids/kids_town.db`、`/kids/backend_v2.py` 極可能直接下載。 | `serve_kids_static()` vs `serve_assets()`。 |
| P0-7 | **CORS(app) 全開放** + 無 CSRF（反正無 cookie，但配合 P0-1 等於公開寫入 API）。 | `CORS(app)`。 |
| P0-8 | **家長密碼 SHA-256、無 salt**；註解「upgrade to bcrypt later」。最短 4 字。 | `hash_password()`；`parent_register` `len(password) < 4`。 |

### P1 — 會令循環壞／崩潰／嚴重誤導

| ID | 問題 | 證據 |
|----|------|------|
| P1-1 | Seed 10 座建築 vs **DB 11 座（銀行）**；公會材料被改成 `{}`。 | `seed_building_defs` vs `SELECT * FROM building_defs`。 |
| P1-2 | 前端 5 區 vs **3 隻怪物**；區 4–5 `battle-start` 404。 | `REGIONS`；`seed` monsters；`battle_start`。 |
| P1-3 | **建築 `buff_type` 未套用**（任務加成、每日金幣、折扣、streak 保護、探險倍率）。 | grep：`buff_type` 只出現喺 schema／seed／SELECT。 |
| P1-4 | **`unlock_region` 未執行**。 | `place_building()` 無讀該欄。 |
| P1-5 | **材料 ID 分裂**：claim 掉 `wood/brick/iron/gem/star_shard`；`/api/materials/defs` 只有 wood/brick/glass/gear；戰鬥掉 `fur`/`gem`。商店升級要 gear/glass。 | `claim_expedition`；`get_material_defs`；`MATERIAL_POOLS`。 |
| P1-6 | **`ability_atk` 殘留**。`migrate_ability_atk()` 存在、測試覆蓋、**startup 唔呼叫**。`get_experience` / `add_experience` / `assign_ability` 讀 `kid['ability_atk']`。已提交 schema **已無此欄** → sqlite3.Row **KeyError / 500**。 | 欄位列表無 `ability_atk`；三處 abilities dict。 |
| P1-7 | **`/` 同 `/dashboard` 404**（期望 `../dashboard/index.html`，本 repo 無此目錄）。遊戲在 `/kids/`。 | `serve_root`；`DASHBOARD_DIR`。 |
| P1-8 | **XP 條公式錯**：前端 `experience / (level * 100)` vs 後端 `EXP_PER_LEVEL=25` 三角累積。註解同公式矛盾。 | `updateHeader()`；`calc_level()`。 |
| P1-9 | **經驗寫入 `points_log`**（reason `experience_gained`）污染金幣帳本、成就「累積 1000 分」可能被 XP 灌水。 | `add_experience()`。 |
| P1-10 | **時區／`datetime.utcnow` 棄用**：`backend_v2.py` 大量 `utcnow()`；claim 用 aware UTC，stale cleaner 用 naive `isoformat()+'Z'` 字串比較。E2E 文件已記過一次 500。 | `E2E_TEST_CASES_zh.md`；`_clean_stale_expeditions` vs `claim_expedition`。 |
| P1-11 | **競態**：完成任務、扣金幣、inventory 皆 read-modify-write，無 `BEGIN IMMEDIATE`。全體任務有 `task_completions` UNIQUE，普通任務靠 `completed` flag，雙擊仍可能。`inventory/add` 無數量上限、無類型白名單。 | `complete_task`；`add_to_inventory`。 |
| P1-12 | **家長登入唔 render 管理頁**；`st('manage')` 無 `renderManage()`。 | `doLogin`；`st()`。 |
| P1-13 | **`/api/dev-dashboard` 無保護**，回傳所有小朋友同功能狀態。 | `dev_dashboard()`。 |
| P1-14 | **`GET /api/kids` 列出全部兒童**（成就頁 `renderStreaks()` 每個小朋友 session 都會打）。 | `list_kids`；`renderStreaks`。 |
| P1-15 | 前端 **innerHTML 插入任務標題／小朋友名**（stored XSS：惡意任務名）。 | `index.html` 任務卡、streak 名。 |
| P1-16 | `add_points` **可以扣到負數**（`adjust_points` 先有 floor 0）。 | 兩 endpoint 行為不一致。 |

### P2 — 品質、測試、營運、文件債

| ID | 問題 | 證據 |
|----|------|------|
| P2-1 | 雙後端：`backend.py` v1.1 同 `backend_v2.py` v3.0 **共用 port 9123 同 `kids_town.db`**，schema 分叉。 | 兩個檔案 header。 |
| P2-2 | 雙前端：`index.html`（DOM 城）vs `index-legacy.html`（真 Canvas）vs `kids-dev.html`（dev dashboard）；`index_v2.html` 已唔存在但仍喺 serve 優先名單。 | `serve_kids_index`。 |
| P2-3 | Health `version: '2.1'` vs docstring v3.0 vs SW header 2.1.0 vs install log **v2.0.1** vs cache `kids-town-v8`。 | `health()`；`service-worker.js`。 |
| P2-4 | PWA：`checkSyncQueue()` 空；offline API 超時當 **HTTP 200** 回 `{error:'offline'}`，前端可能當成功。 | `networkFirstWithTimeout`。 |
| P2-5 | 靜態資源 `Cache-Control: max-age=86400` 含 JS/HTML（`/kids/<file>`）。 | `serve_kids_static`。 |
| P2-6 | 測試 `conftest.py` **複製真實 `kids_town.db`**；`test_auth.py` 寫死 `parent_id: 7`；`test_frontend.py` 寫死 Windows `Python312\python.exe`。`_run_server.py` 唔跑 `migrate_db_v4`。 | `tests/`。 |
| P2-7 | 無 `requirements.txt` / Dockerfile / README；部署靠本機 `0.0.0.0:9123` + ngrok header hack。 | repo 根；`index.html` fetch wrapper。 |
| P2-8 | `complete_task` 留 `[DEBUG] print`。 | `complete_task`。 |
| P2-9 | 大量 `gen-*.png`（51 張實驗圖）同 `assets/`、`assets-b/`、`assets-c/` 三套美術；`.gitignore` 想 ignore `gen_*.png` 但檔已 tracked。 | 工作區 listing。 |
| P2-10 | 文件互相矛盾：`economy_analysis.md` 無 XP；`DEV_PLAN` 有 XP；`MONETIZATION` 「免費 3 區」vs 前端 5 區；Phase 全部標 COMPLETED 但 buff／PWA／變現未做。 | 各 md。 |
| P2-11 | `admin_logs` 表存在、**從未寫入**。 | schema vs grep。 |
| P2-12 | 圖塊碰撞用 `plot_idx`，建築用 `cell_x/cell_y`——裝飾同建築佔格模型不一致。 | `tiles` vs `place_building`。 |
| P2-13 | 成就 `all_regions` 要求 5；探索一次性 + 區 4–5 戰鬥壞 → 難達成。`all_buildings` 跟 DB 定義數而唔係設計 10。 | `check_achievements`。 |
| P2-14 | Quiz 15 題、無科目／難度／家長自訂（同「家課遊戲化」主題錯位）。 | `quiz_questions` count。 |
| P2-15 | Monetization、推送、COPPA 年齡閘、資料保留：**零程式**。 | `MONETIZATION_STRATEGY.md` checkbox 全空。 |

---

## 3. 架構

### 3.1 而家嘅形狀

```
瀏覽器 SPA (index.html ~5112 行，inline CSS/JS)
    │  fetch /api/*   （相對路徑，API=''）
    │  PWA scope /kids/
    ▼
Flask 單體 backend_v2.py (~3830 行，~87 條 route)
    │  sqlite3 直連，每 request 一 connection，WAL + FK
    ▼
kids_town.db（單一檔、已入版控、亦係 live save）
```

| 元件 | 現況 |
|------|------|
| 應用 | 單模組：schema、migration、seed、戰鬥模擬、靜態檔、CSV export 全喺一檔 |
| DB | SQLite；`init_db` + `migrate_db` + `migrate_db_v3` + `migrate_db_v4`（增量 ALTER，無版本表） |
| 前端 | 無 bundler、無 router；tab = `st(name)` 顯示 panel |
| 音效 | 獨立 `audio.js` 程序化 Web Audio（品質相對高） |
| PWA | `manifest.json` start_url `/kids/`；SW network-first HTML、cache-first 靜態、API 10s timeout |
| 舊碼 | `backend.py` 仍可跑；`index-legacy.html` Canvas 時代；`wireframe/`、`mocks/dq_mock_v*.html` 戰鬥 UI 實驗 |

**`backend.py` vs `backend_v2.py`：** 前者約 670 行、交易紀錄 API、簡單建築／探險；後者先係真正入口。兩者同 DB 路徑、同 port。誤跑 v1 會寫入過時 schema。

### 3.2 路由分組（全部無伺服器授權）

**靜態：** `/`（壞）、`/kids`、`/kids/*`、`/assets-c/*`、`/dashboard/*`（壞）、`/kanban`、`/health`（跳去 dashboard）、`/mock-horizontal`、`/character-panel`

**Auth（只係核對密碼，唔發 session）：**  
`POST /api/auth/login`、`parent-register`、`link-kid`、`create-kid`、`GET parent-kids`、legacy `POST /api/login`

**遊戲寫入（公開）：** kids CRUD、points、experience、abilities、tasks CRUD/complete、buildings、inventory add/consume、expedition start/claim/answer/battle、boss summon、tiles、savings、settings

**讀取／統計：** town、leaderboard、achievements、stats、export CSV、`/api/health`、`/api/dev-dashboard`

### 3.3 測試質素

`tests/` 約 1000 行；另有根目錄 `e2e_functional_test.py`、`fe_full_test.py`（`.gitignore` 列 `e2e_*.py` 但檔仍 tracked）。

| 套件 | 質素 |
|------|------|
| `test_battle_formulas.py` / `test_battle_integration.py` / `test_boss.py` / `test_drop_system.py` | 相對好：公式、pity、Boss 獎勵；但綁死 `kid_id=4`（生產角色小強） |
| `test_tasks.py` / `test_auth.py` | 窄、有用；auth **唔測**「無 parent session 都能 create-kid」呢類負例 |
| `test_frontend.py` | Playwright 黑盒；**Windows 絕對路徑**，呢個 Linux 環境唔會綠 |
| `conftest` | 複製 live DB → 測試唔可重現、會洩漏 PII 到 CI artifact |
| 缺口 | 無建築 buff、無材料一致性、無 IDOR、無 `/` 健康、無 PWA、無時區 |

`pytest.ini` 只有 `pythonpath` + `-v`。無 CI workflow 檔。

### 3.4 部署故事

- `app.run(host='0.0.0.0', port=9123, debug=False)` — 內建 Werkzeug，單 process。
- 前端為 ngrok 免費層加 `ngrok-skip-browser-warning`。
- `fe_full_test.py` 提到 ngrok URL + `127.0.0.1:9123`。
- **無** process manager、HTTPS、備份、migration 命令、環境變數（DB 路徑寫死）。
- SQLite + 公開 `0.0.0.0` + 已 commit 嘅憑證 = 只適合作家用 LAN；端口一轉發就變成公開資料庫。

### 3.5 優點（應保留嘅）

- 遊戲 fantasy 清楚：家課 → 城鎮 → 探險 RPG，喺 chores app 市場仍少見（`MONETIZATION_STRATEGY.md` 競爭分析呢點成立）。
- 戰鬥 v2 公式有測試、有技能同建築掛鈎，係而家最「完整」嘅系統。
- 家長任務模型（每人／全體、重複、到期）近期先用 TDD 修過，方向正確。
- 美術／音效／開羅風 HUD 已有可玩原型，wireframe 同 mocks 係設計資產。
- 單檔 Flask 對**單一家庭**迭代速度快——問題係誤把呢個形態當成多租戶產品。

---

## 4. 安全／私隱

對象係**兒童 + 家長**。文件聲稱 COPPA / GDPR-K「Built-in（家長帳號）」——**程式上唔成立**。

### 4.1 收集咗咩

| 資料 | 位置 | 風險 |
|------|------|------|
| 兒童顯示名、username、頭像 emoji | `kids` | 已入 git |
| PIN | `kid_auth.pin` 明文 | 可被靜態下載；部分似出生日期 |
| 家長 username、email、SHA-256 密碼 | `parents` | 弱 hash、email 可空 |
| 任務標題、積分、成就、戰鬥紀錄 | 多表 | 行為側寫 |
| 管理員帳號 | `admins` 預設 super_admin | 全庫權限 |

無：年齡、家長同意紀錄、資料保留期、刪除權流程（有 `DELETE /api/kids/<id>` 但無 auth）、私隱政策、cookie 同意。

### 4.2 認證模型（而家）

```
登入成功 → JSON {role, user} → 前端變數 currentKidId / isParentSession
之後所有 API：信任 URL 同 body 入面嘅 id
```

後果：

- 知（或猜）`kid_id` 就可以完成任務、加無限金幣、加材料、改名、刪號。
- `parent_id` 偽造即可 `create-kid` / `link-kid`。
- 排行榜／`GET /api/kids` 暴露全站兒童。
- 前端 `PARENT_PASSWORD='1234'` 係裝飾。

### 4.3 密碼學

- 家長：SHA-256(password) 無 salt → 彩虹表即破。
- 管理員：更差（明文 OR hash）。
- 兒童：明文 PIN，預設 0000。
- 無 lockout、無 rate limit、無 2FA（家長閘理應要有）。

### 4.4 保密同 repo

Secrets 唔喺環境變數，而係：

- 源碼常數 `admin123`、`1234`
- 已追蹤 DB
- 開機 stdout

即使之後改密碼，git history 仍有舊 PIN 同 hash。對外開源或分享 zip 即洩漏家庭資料。

### 4.5 合規對照（文件 vs 現實）

| 宣稱（`MONETIZATION_STRATEGY.md`） | 現實 |
|-----------------------------------|------|
| 兒童零付費、零廣告 | 成立（因為根本無付費系統） |
| COPPA：無家長同意唔收集兒童資料 | 失敗：註冊家長無驗證；API 公開；DB 入 git |
| GDPR-K parental gate | 失敗：gate 只喺 `prompt()` |
| 無 loot box | 部分：探險 mystery_box、戰鬥 pity／稀有掉落偏 gacha 味道；未收費所以未違法賭博，但同「無 loot box」文案緊張 |

**結論：** 而家只適合作**開發者自家 LAN、唔暴露端口、唔把 repo 當公開**。任何 ngrok／公網示範都係事故。

---

## 5. 建議：三條軌道

Effort 用**工程範圍**描述，唔用日曆時間。

### Track A — 穩定同打磨現有 stack

**目標：** 繼續家庭自用；堵住洩漏；令主循環同 `DEV_PLAN` 一致到「唔覺得騙細路」。

**保留：** `backend_v2.py` + SQLite + `index.html` DOM 城鎮 + 戰鬥系統 + 家長任務。

**丟掉／停用：** `backend.py` 當入口；`index-legacy.html` 當生產；ngrok 當正式部署；`showAdminLogin` 預填；`inventory/add` 對外；`/api/dev-dashboard` 對外。

**必做順序：**

1. **安全止血：** `.gitignore` `*.db`；從 git 移除 `kids_town.db`（history 另計）；靜態白名單，禁止 `/kids/*.py`、`*.db`；刪預設 admin 或強制首次改密；PIN hash；所有寫入 API 要 session；關閉預設 CORS。
2. **崩潰修復：** 呼叫或刪除 `ability_atk` 殘留；`/` 改 redirect `/kids/`；XP HUD 用 `experience_in_level`；材料 ID 統一（全程 gear/glass 或全程 iron/gem，選一套）。
3. **循環接線（最小）：** 5 區怪物 seed；探索是否可重複農；任務完成 toast 顯示 XP／材料／成就；至少實作 1–2 個建築 buff（圖書館任務加成、農場每日金幣），否則改文案唔好再寫「buff」。
4. **測試：** 用 fixture seed 空庫，唔再 copy 生產 DB；修 Playwright 解釋器路徑；加 IDOR 負例。

**唔做：** 訂閱、新區 DLC、推送、微服務。

**Rough effort：** 中等——集中改 auth 中間層、seed 資料、前端反饋；唔切架構。風險低，收益係「可以再畀自己屋企用、示範前唔驚」。

### Track B — 漸進重構（**建議**）

**目標：** 同一產品幻想，變成可給少量家庭用、可合規起步嘅服務。A 係第 0 階段。

**保留：** 玩法（任務、城鎮格子、三種探險、戰鬥公式、技能、成就概念）；`assets-c` 美術；程序化音效；Cantonese UX。

**逐步丟掉：** 單檔 3800 行 route 神；inline 5000 行 `index.html`；SQLite 當多租戶；文件同程式分家嘅「全部 COMPLETED」。

**建議模組切法（仍可以 Flask，唔使一開始換語言）：**

```
auth/          session、角色、家長閘、PIN hash、rate limit
family/        parent–kid、任務、points_log
town/          building_defs、placement、inventory（統一物料表）
expedition/    regions 設定檔、explore/quiz/battle/boss
progress/      level 曲線、achievements、streaks（時區=家庭時區）
static/        明確白名單
```

前端：先拆 `index.html` 做 `js/api.js`、`town.js`、`battle.js`、`parent.js`（仍可無框架）；再決定要唔要上小型 view 層。

資料：家庭（tenant）ID；**禁止**把 live save commit 進 git；migration 用版本號；備份。

測試：空庫 fixtures；authz matrix；契約測試「5 區每區有怪」；buff 有單位測試。

變現：僅在 auth + tenant 穩後先做；且必須家長 session + Store 收據。依而家倫理文件，**唔好**用戰鬥 pity 做付費。

**順序：** A 止血 → 物料／區域設定檔化 → 拆 backend 模組（行為不變）→ 拆前端 JS → tenant + 真 session → 先至考慮 Premium flag。

**Rough effort：** 高——要碰幾乎所有寫入路徑，但可按模組 PR，遊戲可一直玩。風險係「邊切邊加功能」會再堆債；要用功能凍結窗口。

### Track C — 綠地重建

**目標：** 上架兒童產品（App Store／Play）、多地區、COPPA 審計可過。

**保留（搬過去，唔係重畫）：** 循環設計、10 建築 fantasy、5 區敘事、戰鬥公式同技能名、美術風格、音效思路、家長任務語義。

**丟掉：** Flask 單體、SQLite 單檔、明文 PIN、單頁 5k 行、ngrok 部署、把 DB 當 save 檔 commit、自製 SHA-256、無框架 XSS innerHTML。

**綠地形態（示例，非唯一）：** 托管 Postgres；真 session 或 cookie + CSRF；家長 OAuth／magic link；兒童裝置 PIN 只存 hash 且唔入 log；前端 Vite + 明確元件；伺服器權威戰鬥；物件儲存放美術；正式 backup／刪除權。

**Rough effort：** 非常高——auth／私隱／多租戶幾乎重寫；玩法要重新接線同回歸。只有喺「要賣錢、要過審」先值得。若只係屋企用，C 係過度投資。

### 點解揀 B（A 做 Phase 0）

| 準則 | A only | **B** | C |
|------|--------|-------|---|
| 家庭繼續玩 | 最好 | 中（有凍結窗） | 最差（長期無得玩） |
| 安全最低線 | 做完 A 就達 | 達 + 可擴 | 達但最慢 |
| 主循環誠信 | 部分（buff 擇要） | 可系統性修 | 可，但重接線成本高 |
| 戰鬥／美術沉沒成本 | 全留 | 全留 | 要搬、易失 |
| 變現／多家庭 | 唔支援 | 之後可加 | 為呢個而存在 |
| 文件同程式再對齊 | 手動改 md | 設定檔即文件 | 重寫文件 |

產品而家嘅價值喺**已調過嘅戰鬥**同**可玩嘅城鎮原型**，唔喺 Flask 檔案結構。C 會扔掉接線知識（pity、Boss 週冷却、全體任務 TDD）。A-only 會令下一輪功能（第五區怪、銀行、訂閱）繼續堆上 3800 行檔。B 承認「呢個 fantasy 值得留」，同時拒絕「再 commit 一次小朋友進度進 GitHub」。

**若決策者只想週末同仔女玩：** 做完 A 就可以停。  
**若想變成產品：** 唔好跳過 A 去畫 Premium 區；亦唔好未止血就開 C。

---

## 6. 附錄：設計文件 vs 程式（速查）

| 來源 | 宣稱 | 程式 |
|------|------|------|
| `DEV_PLAN.md` | 10 建築、5 區、探險耗金幣、建築 buff、Canvas 城、成就彈窗 | 11 建築（此 DB）、3 怪、探險唔扣金幣、buff 未套用、DOM 城、無成就彈窗 |
| `economy_analysis.md` | 無 kid XP；PIN 預設 0000；10 建築成本表 | 有 XP/level；PIN 確實 0000；銀行第 11 座；材料鍵已 migrate |
| `MONETIZATION_STRATEGY.md` | 免費 2 個兒童、免費 3 區、家長訂閱 $3.99 | 無 tier、無支付、前端 5 區 |
| `index.html` REGIONS | 5 區獎勵／時長 | 後端隨機 `10–30 * region_id`，唔用前端表 |
| `wireframe/index.html` | 8 plot、探險掉設計圖 | 自由格、每類型 1 座、設計圖系統不存在 |
| `/api/health` | version 2.1 | 檔頭 v3.0 |
| SW | v2.1.0 | console v2.0.1，cache v8 |

---

## 7. 調查方法同限制

- 唯讀：源碼、已提交 SQLite、設計 md、測試。無改遊戲邏輯。
- 未做：真實裝置 PWA 安裝、公網滲透、瀏覽器 E2E（Playwright 綁 Windows 路徑）。
- 已提交 DB 含可能真實兒童資料；本報告避免複製完整 PIN／email 清單，但工程上必須當 **PII 事故** 處理（rotate PIN、停用預設 admin、考慮 git history purge）。

---

*報告完。*
