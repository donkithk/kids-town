# Kids Town 工程流程：測試先行（TDD）+ 雙重驗證

> **適用**：本 repo 所有功能／安全 PR（跟 [`GAMEPLAY_REDESIGN.md`](GAMEPLAY_REDESIGN.md) 嘅 Phase 0→1→2）。  
> **語言**：說明用香港繁體；測試函數名、模組、斷言訊息入面嘅識別名用英文。  
> **原則**：未有失敗測試，唔寫產品碼；未雙重驗證，唔當完成。

---

## 0. 點解要呢份文件

評估（[`EVALUATION.md`](EVALUATION.md) §3.3、P2-6）指出：而家 `tests/conftest.py` **複製生產 `kids_town.db`**、auth 無 IDOR 負例、Playwright 綁 Windows Python、幾乎無授權測試。用戶決定：**之後所有工作必須 TDD**，而且要 **雙重驗證**（自動化 + 第二輪手動／E2E 清單）。

本流程對齊現有已用過嘅習慣（`tests/test_auth.py`、`tests/test_tasks.py` 註解寫「TDD — RED first」），但把「空庫 fixture、負例、PR 閘」寫死。

---

## 1. 五步循環（每個最小行為都走一次）

```
1. Spec     企劃／test-case 寫清行為同 Expected
2. RED      寫會失敗嘅測試（pytest；前端能測就測）
3. GREEN    寫最少產品碼令測試過
4. REFACTOR 清理重複；測試保持綠
5. DOUBLE   (A) 相關 pytest 全綠  (B) 手動／E2E checklist 簽收
```

### Step 1 — Spec in plan

- 行為必須能指到：`GAMEPLAY_REDESIGN.md` 某節，或 `docs/test-cases/PHASE0_SECURITY.md` / `PHASE1_GAMEPLAY.md` 某個 **Case ID**。
- 若行為唔喺企劃裏：先改企劃（短 PR），**唔好**一邊發明玩法一邊寫碼。
- Spec 最少有：誰（角色）、前置、動作（HTTP／UI）、預期狀態碼同 JSON 鍵、優先級 P0/P1。

### Step 2 — 寫失敗測試

| 層 | 工具 | 何時必須有 |
|----|------|------------|
| API／domain | **pytest** + Flask `test_client` | 所有後端行為、授權、buff、掉落、金幣 |
| 純函數 | pytest 直接 import `backend_v2` helper | `calc_level`、`get_building_buff`、材料正規化 |
| 前端（可行就寫） | Playwright 或對 JS 契約嘅輕量測試 | 登入後 HUD、任務儀式文案、放置模式、區 4 鎖定字 |
| 前端（暫不可行） | 喺 test-case 標「手動／E2E」+ 雙重驗證 B | 例如複雜 Canvas 動畫；**唔可以**因此跳過後端測試 |

**RED 先通過關：** 新測試必須先紅（失敗原因係「產品未做」或「而家行為錯」），先至開始 GREEN。若測試一寫就綠，代表無斷到新行為——改測試，唔好當完成。

### Step 3 — 最少實作

- 只改令呢個 Case ID 變綠嘅碼。
- 唔順手做 Phase 2 家庭寶箱、唔順手重構 3800 行 `backend_v2.py`（重構另 PR，要有表徵測試保護）。
- 安全：deny-by-default。新路由一加就要有「無 session → 401」測試。

### Step 4 — Refactor

- 抽 helper、去重複、改名。
- 每次重構後跑 **相關檔案** pytest；準備 push 前跑 **成個 `tests/`**（見 §5）。
- 禁止重構時改行為而「順便修」無測試覆蓋嘅分支。

### Step 5 — 雙重驗證（硬閘）

**(A) 自動化**

```bash
# 開發中：相關模組
python -m pytest tests/test_authz_idor.py tests/test_building_buffs.py -v

# PR 前：成個測試目錄必須綠
python -m pytest tests/ -v
```

- 失敗 = 唔准合併。
- 暫時 skip 必須喺 PR 寫明 ticket／原因；**P0 安全 case 禁止 skip**。
- `tests/test_frontend.py` 而家綁 Windows `Python312\python.exe`（評估 P2-6）：未修路徑之前，**唔好**當 (A) 嘅必綠項；修路徑本身係一個 TDD 任務。修完之後前端 E2E 納入 (A)。

**(B) 第二輪：手動／E2E checklist 簽收**

- 每個功能 PR 喺描述貼上 **已打勾** 清單（可從 test-case 檔嘅 Manual 節複製）。
- 簽收格式：

```
DOUBLE-CHECK (B)
- 跑手：<名>
- 日期：YYYY-MM-DD
- 環境：本機 Flask :9123 / 空庫 seed / 瀏覽器 <名+版>
- 清單：PHASE0 或 PHASE1 或本 PR 自訂（連結）
- 結果：PASS / FAIL（失敗列 case id）
```

- (A) 綠但 (B) 未勾 → **唔當完成**。Cloud agent 無瀏覽器時：(B) 寫明「未能人手點 UI，已用契約測試覆蓋 X；請用戶補跑第 Y 項」。

---

## 2. 規則（違反即 PR 退回）

### 2.1 無測試，無功能 PR

- 新增／改變行為嘅 PR 必須包含：**新測試或更新測試**，對應 Case ID。
- 純文件 PR（好似本企劃）例外。
- 「只改文案」若影響玩家規則（例如費用數字）→ 要測試。
- 刪測試去令 CI 綠 = 禁止。

### 2.2 安全測試必須包含 IDOR 負例

每個寫入資源嘅 API，最少兩條：

1. **正向**：正確 session + 擁有者 → 2xx 同狀態改變。
2. **負向 IDOR**：正確 session 但目標 `kid_id`／`task_id` 屬於別人 → **403**（或 404，選定一種就要全 repo 一致；**建議 403** 以免洩漏存在性，列表類用 404 亦可，但要喺測試寫死）。
3. **負向未登入**：無 session → **401**。

例：`POST /api/kids/<id>/inventory/add`、`/points`、`/points/adjust`、`/tasks/<id>/complete`、`/auth/create-kid`（偽造 `parent_id`）。

### 2.3 Fixture：空庫 seed，永不複製生產 DB

**禁止：**

```python
shutil.copy2(os.path.join(REPO, 'kids_town.db'), dst)  # 評估 P2-6，停用
```

**必須：**

- `tmp_path` 新 SQLite 檔。
- 呼叫而家嘅 `init_db` / `migrate_db*` / `seed_building_defs` / `seed_skill_defs` / monster seed（視乎測試需要）。
- Factory：`make_parent(client, ...)`、`make_kid(...)`、`login(client, username, password)` → 之後 request 帶 session cookie（Phase 0 實作 session 之後）。
- 測試資料 username 用前綴 `t_` 或 `test_`，teardown 可刪但空庫其實唔使。
- **唔好** 寫死 `parent_id=7`、`kid_id=4`（小強生產角色）。

`pytest.ini` 保持 `testpaths = tests`。新 conftest 可以分 `tests/conftest.py`（空庫）同必要時 `tests/factories.py`。

舊 `conftest.py` 複製 DB 嘅行為：Phase 0 第一個測試 PR **一併改掉**，否則戰鬥測試繼續綁 PII。

### 2.4 唔用生產資料、唔把 DB 提交返 git

- 測試唔讀真實名、PIN、email。
- 新 `.gitignore` 必須有 `*.db`（Phase 0 範圍）。
- CI artifact 若有 sqlite，只限 tmp 測試庫。

### 2.5 其他

- 新功能預設 **香港時區** 斷言用固定 `freezegun` 或可注入 clock，避免 `utcnow` 喺夜晚 8 點後先綠。
- 隨機掉落：測試要 `random.seed` 或 mock `random.random`，唔好 flaky。
- 測試內唔 `print` 機密；唔 assert 完整密碼 hash 字串到 log。

---

## 3. 測試點名

### 3.1 檔案（模組）

```
tests/test_<area>.py
```

| 範圍 | 建議檔名 |
|------|----------|
| Session／未登入 | `tests/test_authz_session.py` |
| IDOR | `tests/test_authz_idor.py` |
| Admin bootstrap | `tests/test_admin_bootstrap.py` |
| PIN hash | `tests/test_pin_hash.py` |
| 靜態洩漏 | `tests/test_static_denylist.py` |
| 家長密碼 | `tests/test_parent_password.py` |
| 背包授權 | `tests/test_inventory_authz.py` |
| 金幣下限 | `tests/test_points_floor.py` |
| 兒童列表私隱 | `tests/test_list_kids_privacy.py` |
| XSS 編碼 | `tests/test_xss_encoding.py` |
| 建築 buff | `tests/test_building_buffs.py` |
| 材料 id | `tests/test_materials_ids.py` |
| 區域鎖／怪物 | `tests/test_region_lock.py` |
| unlock_region | `tests/test_unlock_region.py` |
| 任務儀式 API | `tests/test_task_ceremony.py` |
| XP helper | `tests/test_xp_bar.py` |
| 探險費用 | `tests/test_expedition_gold.py` |
| 公會閘 | `tests/test_guild_gate.py` |
| 放置模式（前端） | `tests/test_frontend_placement.py` |

一個 Case ID 對一個 `def test_...`。相關 helper 可同檔。

### 3.2 函數名

```
test_<actor>_<action>_<expected>
```

例子：

- `test_unauthenticated_post_points_returns_401`
- `test_kid_cannot_add_points_to_sibling_returns_403`
- `test_library_level1_adds_task_bonus_xp`
- `test_battle_start_region_4_returns_region_locked`

**Docstring 第一行：** Case ID + 中文短題。

```python
def test_library_level1_adds_task_bonus_xp(client, family):
    """P1-TC-BUFF-01 圖書館 Lv.1 完成任務額外 +2 XP。"""
```

### 3.3 斷言風格

- 先 `assert r.status_code == ...`，失敗時附 `r.get_data(as_text=True)`。
- JSON 鍵用英文：`points_awarded`、`error`。
- 錯誤碼優先 assert 穩定機碼 `error == 'region_locked'`，其次先至係中文訊息。

---

## 4. 由 test-case 目錄去到 pytest

`docs/test-cases/*.md` 係 **人類同 agent 嘅目錄**，唔係執行器。

轉換清單：

1. 開對應 `tests/test_*.py`（見每案「建議模組」）。
2. 用空庫 fixture + factory 重現「前置」。
3. 用 `client.get/post/...` 重現「步驟」。
4. Assert 「預期」。
5. Commit 訊息：`test(phase0): add P0-TC-IDOR-02 kid cannot adjust sibling points`（仍然紅）→ 下一 commit `fix(authz): deny cross-kid points adjust`。

Phase 0 全目錄變綠先至公開示範。Phase 1 遊戲碼 **唔好** 混進未綠嘅 Phase 0 PR。

---

## 5. PR checklist 模板（複製到每個實作 PR）

```markdown
## Spec
- [ ] 行為已寫喺 docs/GAMEPLAY_REDESIGN.md 或 docs/test-cases/…
- [ ] Case IDs：…

## TDD
- [ ] 測試 commit 先於或同於產品碼（至少本地經歷過 RED）
- [ ] 新測試用空庫 seed，無 copy kids_town.db
- [ ] 寫入 API 有 401（未登入）同 403（IDOR）負例（若適用）
- [ ] 無 skip P0

## Double verification
- [ ] (A) `python -m pytest tests/ -v` 綠（或列出豁免嘅 Windows-only 前端檔 + 原因）
- [ ] (B) 手動／E2E 清單已勾，簽收見上

## Safety
- [ ] 無提交 .db、無新預設密碼、無把生產資料當 fixture
- [ ] 本 PR 唔做未批核嘅玩法發明

## Out of scope
- （寫明故意唔做咩）
```

標題建議：`feat(phase0): session gate on write APIs` / `feat(phase1): apply library task_bonus`。

---

## 6. 同現有測試債共存

| 現況 | 本流程點處理 |
|------|----------------|
| `tests/conftest.py` copy 真 DB | Phase 0 改空庫；戰鬥測試用 factory 建 Lv 足夠嘅假 kid |
| `test_auth.py` 寫死 parent_id=7 | 一併改 factory；舊測試可暫留但唔再加硬編碼 id |
| `test_frontend.py` Windows Python | 獨立 PR 改 `sys.executable`；之前 (A) 豁免呢個檔 |
| 根目錄 `e2e_functional_test.py` | 當手動腳本；新 case 優先入 `tests/` |
| 無 CI workflow | Later；未有 CI 都要本地 (A) |

---

## 7. 角色同「完成」定義

| 角色 | 責任 |
|------|------|
| 作者 | RED→GREEN→REFACTOR；(A) 全綠；填 checklist |
| 第二驗證 | 可以係同一人隔一段時間、另一 agent、或用戶；必須真嘅 (B) 勾，唔好複製 (A) |
| 用戶 | 批企劃；公開示範前確認 Phase 0；(B) 若 agent 無瀏覽器 |

**完成 ≠ merge。** 完成 = checklist 全勾 + 用戶接受該 Phase 可進下一 Phase。

---

*流程完。實作碼仍然等企劃批准同獨立 PR。*
