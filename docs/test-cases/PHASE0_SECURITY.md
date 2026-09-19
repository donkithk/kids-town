# Phase 0 安全測試目錄（先寫 pytest，後寫產品碼）

> **狀態**：目錄 + GREEN 實作（見 [`PHASE0_SECURITY_STATUS.md`](PHASE0_SECURITY_STATUS.md)）。  
> **流程**：[`docs/TDD_PROCESS.md`](../TDD_PROCESS.md)  
> **產品背景**：[`docs/EVALUATION.md`](../EVALUATION.md) P0-1～P0-8、P1-14～P1-16；[`GAMEPLAY_REDESIGN.md`](../GAMEPLAY_REDESIGN.md) Phase 0。  
> **Fixture**：空庫 + seed，**禁止** `shutil.copy2(kids_town.db)`。  
> **優先級**：P0 = 公開示範前必須綠；P1 = 同 Phase 0 PR 能做就做，最遲隨即 follow-up。

每個案例轉 pytest 時：函數 docstring 第一行放 **ID**；模組見「建議模組」。

共用前置（除另註）：

1. Flask `TESTING=True`，`DB_PATH` 指向 tmp 空庫，已跑 init／migrate／seed。
2. Factory 建立 `parent_a` + `kid_a`（A 家庭）、`parent_b` + `kid_b`（B 家庭）。
3. Session 方案未定實作（cookie 或 token）；測試用 helper `login_as(client, user)`，斷言後續 request 帶憑證。未登入 client 另開。

建議統一狀態碼：**401 unauthenticated**、**403 forbidden (IDOR／角色錯)**。若實作揀 404 藏存在性，改呢份目錄再改測試，唔好混用。

---

## P0-TC-SESS-01 — 未登入不能寫入金幣

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-SESS-01 |
| **標題** | 無 session 時 `POST /api/kids/<id>/points` 拒絕 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_session.py` |
| **前置** | 空庫；存在 `kid_a`，`points=0`；client 未 login |
| **步驟** | 1. `POST /api/kids/{kid_a}/points` JSON `{"amount":100,"reason":"hack"}` |
| **預期** | 狀態碼 401；`kid_a.points` 仍為 0；`points_log` 無新行 |

---

## P0-TC-SESS-02 — 未登入不能完成任務

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-SESS-02 |
| **標題** | 無 session 時 `POST /api/tasks/<id>/complete` 拒絕 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_session.py` |
| **前置** | 家長 session 建咗任務 `task_1` 指定 `kid_a`；測試用**未登入** client 打 complete |
| **步驟** | 1. `POST /api/tasks/{task_1}/complete` JSON `{"kid_id": kid_a}` |
| **預期** | 401；任務 `completed` 仍 0；金幣不變 |

---

## P0-TC-SESS-03 — 未登入不能 create-kid

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-SESS-03 |
| **標題** | 無 session 時 `POST /api/auth/create-kid` 拒絕（即使 body 有 `parent_id`） |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_session.py` |
| **前置** | `parent_a` 已存在；未登入 |
| **步驟** | 1. `POST /api/auth/create-kid` `{"parent_id": parent_a, "name":"X","username":"t_x","pin":"1234"}` |
| **預期** | 401；無新 `kids` 行 |

---

## P0-TC-SESS-04 — 讀寫分離：健康檢查仍可匿名

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-SESS-04 |
| **標題** | `GET /api/health`（或等價）無 session 仍 200（避免把公開示範完全打悶） |
| **優先級** | P1 |
| **建議模組** | `tests/test_authz_session.py` |
| **前置** | 未登入 |
| **步驟** | 1. `GET /api/health` 或而家實際 health 路徑 |
| **預期** | 200；**body 不含** 兒童名單、PIN、email |

---

## P0-TC-IDOR-01 — 小朋友不能改另一個小朋友金幣

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-IDOR-01 |
| **標題** | Kid A session 對 kid B `POST .../points` → 403，B 金幣不變 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_idor.py` |
| **前置** | 已 login 為 `kid_a`；`kid_b.points=5` |
| **步驟** | 1. `POST /api/kids/{kid_b}/points` `{"amount":999,"reason":"x"}` |
| **預期** | 403；`kid_b.points==5` |

---

## P0-TC-IDOR-02 — 小朋友不能調整兄弟積分

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-IDOR-02 |
| **標題** | Kid A 呼叫 `POST /api/kids/{kid_b}/points/adjust` 拒絕 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_idor.py` |
| **前置** | login `kid_a`；`kid_b` 存在 |
| **步驟** | 1. `POST /api/kids/{kid_b}/points/adjust` `{"amount":-5,"reason":"punish"}` |
| **預期** | 403；B 金幣不變 |

---

## P0-TC-IDOR-03 — 家長不能用 body 偽造 parent_id 綁別人仔女

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-IDOR-03 |
| **標題** | Parent A session 帶 `parent_id=parent_b` 去 `create-kid`／`link-kid` 失敗 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_idor.py` |
| **前置** | login `parent_a`；`parent_b` 存在 |
| **步驟** | 1. `POST /api/auth/create-kid` 用 `parent_id=parent_b` 2. 或 `POST /api/auth/link-kid` 指向 B 嘅 kid |
| **預期** | 403；`parent_kid` 無 A 偷綁 B 嘅行；session 內 `parent_id` **以伺服器為準**，忽略 body |

---

## P0-TC-IDOR-04 — 小朋友不能完成指定給另一人嘅任務

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-IDOR-04 |
| **標題** | Kid A complete 指定 `kid_id=kid_b` 嘅任務 → 403 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_idor.py` |
| **前置** | 任務只屬於 B；login A |
| **步驟** | 1. `POST /api/tasks/{id}/complete` `{"kid_id": kid_b}` 2. 再試 `{"kid_id": kid_a}` |
| **預期** | 兩次都 403 或第二次仍 403；B 未完成、未加分 |

---

## P0-TC-IDOR-05 — 家長只能調整自己 linked kids

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-IDOR-05 |
| **標題** | Parent A 對 kid_b `points/adjust` → 403 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_idor.py` |
| **前置** | login `parent_a`；kid_b 只 link B |
| **步驟** | 1. `POST /api/kids/{kid_b}/points/adjust` `{"amount":10,"reason":"gift"}` |
| **預期** | 403；金幣不變 |

---

## P0-TC-ADM-01 — 空庫不再有預設 admin／admin123

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-ADM-01 |
| **標題** | migrate／seed 之後 `admins` 表無 username=`admin` 配預設口令 |
| **優先級** | P0 |
| **建議模組** | `tests/test_admin_bootstrap.py` |
| **前置** | 全新空庫跑完所有 migrate＋seed |
| **步驟** | 1. `SELECT * FROM admins` 2. `POST /api/auth/login` `{"username":"admin","password":"admin123"}` |
| **預期** | 無預設 super_admin 行 **或** 該行 `must_change_password=1` 且 login 被拒直到改密；login 用 `admin123` **必定失敗**（401／403） |

---

## P0-TC-ADM-02 — 舊預設管理員強制改密

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-ADM-02 |
| **標題** | 若測試插入舊 hash／明文 `admin123`，login 只允許進入改密，唔發完整能力 session |
| **優先級** | P0 |
| **建議模組** | `tests/test_admin_bootstrap.py` |
| **前置** | 空庫人手 INSERT 模擬舊 `admin` 列（明文或 SHA-256 of admin123） |
| **步驟** | 1. login admin／admin123 2. 用該 session `DELETE /api/kids/{any}` |
| **預期** | 步驟 1：403 或 200 但 `must_change_password=true` 且無寫入權；步驟 2：401／403 |

---

## P0-TC-ADM-03 — 登入頁唔預填管理員口令

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-ADM-03 |
| **標題** | 前端 `showAdminLogin`／login 表單無 `value="admin123"` |
| **優先級** | P0 |
| **建議模組** | `tests/test_admin_bootstrap.py`（讀 `index.html` 字串即可，唔使開瀏覽器） |
| **前置** | repo 內 `index.html`、`index-legacy.html` |
| **步驟** | 1. 讀檔搜尋 `admin123` 作為表單預填 |
| **預期** | 生產 HTML **無** password input 預填 `admin123`；開機 print 亦唔好再印 Default admin（可 grep `backend_v2.py` 啟動訊息） |

---

## P0-TC-PIN-01 — PIN 以 hash 存庫

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-PIN-01 |
| **標題** | `create-kid` 之後 `kid_auth.pin` ≠ 明文 PIN |
| **優先級** | P0 |
| **建議模組** | `tests/test_pin_hash.py` |
| **前置** | login `parent_a` |
| **步驟** | 1. create-kid PIN=`2468` 2. SQL 讀 `kid_auth.pin` |
| **預期** | 存庫值唔等於 `'2468'`；長度／前綴符合所用 hash（例如 bcrypt `$2`）；用正確 PIN 仍可 `POST /api/auth/login` 200 |

---

## P0-TC-PIN-02 — 登入回應不含 PIN

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-PIN-02 |
| **標題** | Kid／legacy login JSON 唔包含 pin／password |
| **優先級** | P0 |
| **建議模組** | `tests/test_pin_hash.py` |
| **前置** | 已知 kid 帳戶 |
| **步驟** | 1. `POST /api/auth/login` 成功 2. 若仍存在 `POST /api/login` legacy，一併打 |
| **預期** | 200；`user`／頂層鍵 **無** `pin`、`password`；JSON 字串唔包含明文 PIN |

---

## P0-TC-PIN-03 — 缺 kid_auth 行唔好插入 0000

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-PIN-03 |
| **標題** | 只有 `kids` 行、無 `kid_auth` 時，login 失敗且 DB 唔新插入明文 `0000` |
| **優先級** | P0 |
| **建議模組** | `tests/test_pin_hash.py` |
| **前置** | INSERT kid 無 auth 行 |
| **步驟** | 1. login username + `0000` 2. 再查 `kid_auth` |
| **預期** | 403；`kid_auth` 仍空（或只有 hash，絕非明文 `0000`） |

---

## P0-TC-STAT-01 — 靜態路由不提供 .db

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-STAT-01 |
| **標題** | `GET /kids/kids_town.db` → 404 |
| **優先級** | P0 |
| **建議模組** | `tests/test_static_denylist.py` |
| **前置** | 測試庫旁或 HTML_DIR 放一個假 `kids_town.db` 檔（內容 `SQLite format 3`）以證明即使檔存在都唔會 serve |
| **步驟** | 1. `GET /kids/kids_town.db` 2. `GET /kids/foo.db` |
| **預期** | 404；body 唔係 sqlite 檔頭 |

---

## P0-TC-STAT-02 — 靜態路由不提供 .py

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-STAT-02 |
| **標題** | `GET /kids/backend_v2.py` → 404 |
| **優先級** | P0 |
| **建議模組** | `tests/test_static_denylist.py` |
| **前置** | `backend_v2.py` 喺 HTML_DIR 同層（而家係） |
| **步驟** | 1. `GET /kids/backend_v2.py` 2. `GET /kids/tests/conftest.py` |
| **預期** | 404；body 不含 `def serve_kids_static` |

---

## P0-TC-STAT-03 — 路徑遍歷同副檔名偽裝

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-STAT-03 |
| **標題** | `..` 同雙副檔名不能讀源碼／DB |
| **優先級** | P0 |
| **建議模組** | `tests/test_static_denylist.py` |
| **前置** | 同 STAT-01 |
| **步驟** | 1. `GET /kids/%2e%2e/backend_v2.py` 2. `GET /kids/backend_v2.py.txt` 若會 map 到 py 則 404 3. `GET /kids/secret.db.png` 若實際檔係 db 亦 404（白名單以真實副檔名／內容策略為準，測試鎖你哋揀嘅實作） |
| **預期** | 全部 404 或 400；**200 只允許** 白名單：`.html .js .css .png .svg .ico .json .woff2 .webp` |

---

## P0-TC-STAT-04 — 合法靜態仍然 200

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-STAT-04 |
| **標題** | `GET /kids/` 或 index、`/assets-c/` 圖仍可匿名讀（遊戲要載入） |
| **優先級** | P1 |
| **建議模組** | `tests/test_static_denylist.py` |
| **前置** | 有 `index.html`、至少一張 `assets-c` png |
| **步驟** | 1. `GET /kids/` 或 `/kids/index.html` 2. `GET /assets-c/` 下一張已知圖 |
| **預期** | 200；HTML 唔包含伺服器 PIN 清單 |

---

## P0-TC-PWD-01 — 家長註冊密碼有 salt、唔再純 SHA-256

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-PWD-01 |
| **標題** | 新家長 `parents.password` 唔等於 `sha256(plaintext)` |
| **優先級** | P0 |
| **建議模組** | `tests/test_parent_password.py` |
| **前置** | 空庫未登入（註冊本身可公開，但要 rate-limit Later） |
| **步驟** | 1. `POST /api/auth/parent-register` username=`t_pa` password=`CorrectHorse1` email 可空 2. SQL 讀 hash 3. 計算 `hashlib.sha256(b'CorrectHorse1').hexdigest()` |
| **預期** | 201；存庫 ≠ sha256 hex；login 用同一明文 200；hash 有 salt（bcrypt 前綴 `$2` 或 argon2 `$argon2`） |

---

## P0-TC-PWD-02 — 家長密碼最短 8 同唔回傳 hash

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-PWD-02 |
| **標題** | 少過 8 字拒絕；成功回應無 password 欄 |
| **優先級** | P0 |
| **建議模組** | `tests/test_parent_password.py` |
| **前置** | 無 |
| **步驟** | 1. register password=`abcd` 2. register password=`abcdefgh` 3. 檢查步驟 2 JSON |
| **預期** | 步驟 1：400；步驟 2：201；JSON 無 `password`、無 hash 字串 |

---

## P0-TC-PWD-03 — 舊 SHA-256 家長可遷移或拒絕策略有測試

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-PWD-03 |
| **標題** | 舊 SHA-256 列 login 行為有明確斷言（升級 rehash 或強制重設，二揀一） |
| **優先級** | P1 |
| **建議模組** | `tests/test_parent_password.py` |
| **前置** | INSERT parent，password=`sha256(b'oldpass12')` hex |
| **步驟** | 1. login `oldpass12` |
| **預期** | **本企劃建議**：成功並 **rehash** 成 bcrypt（一次過），第二次 SQL ≠ sha256；**或** 拒絕並要求重設。測試必須鎖死其中一種，唔好明文仍可比對成功又唔升級。 |

---

## P0-TC-INV-01 — 未登入 inventory/add 403／401

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-INV-01 |
| **標題** | 匿名 `POST /api/kids/<id>/inventory/add` 拒絕且數量不變 |
| **優先級** | P0 |
| **建議模組** | `tests/test_inventory_authz.py` |
| **前置** | `kid_a` wood=0；未登入 |
| **步驟** | 1. `POST /api/kids/{kid_a}/inventory/add` `{"item_type":"wood","quantity":99}` |
| **預期** | 401；wood 仍 0 |

---

## P0-TC-INV-02 — 小朋友不能對自己任意 add（生產路徑）

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-INV-02 |
| **標題** | Kid A session 呼叫 `inventory/add` → 403（材料只經任務／探險／戰鬥） |
| **優先級** | P0 |
| **建議模組** | `tests/test_inventory_authz.py` |
| **前置** | login `kid_a` |
| **步驟** | 1. `POST .../inventory/add` wood×50 |
| **預期** | 403；數量不變。Debug 後門若保留，必須 admin session + 非 production flag；另開 P1 測。 |

---

## P0-TC-INV-03 — 小朋友不能加材料給別人

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-INV-03 |
| **標題** | Kid A 對 kid_b `inventory/add` → 403 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_idor.py` 或 `test_inventory_authz.py` |
| **前置** | login `kid_a` |
| **步驟** | 1. POST add 到 kid_b |
| **預期** | 403；B 背包不變 |

---

## P0-TC-PTS-01 — 未授權路徑不能把金幣扣到負

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-PTS-01 |
| **標題** | 匿名或 kid 對 `POST .../points` 負數被拒；即使家長合法扣分，結餘 ≥ 0 |
| **優先級** | P0 |
| **建議模組** | `tests/test_points_floor.py` |
| **前置** | `kid_a.points=3` |
| **步驟** | 1. 未登入 POST amount=-100 2. login kid_a POST amount=-100 3. login parent_a（已 link）`points/adjust` amount=-100 reason=`test` |
| **預期** | 1→401；2→403；3→200 且 `points==0`（唔係 -97）；`points_log` 家長嗰行存在 |

---

## P0-TC-PTS-02 — add_points 同 adjust 下限一致

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-PTS-02 |
| **標題** | 若仍保留 `POST .../points` 給家長，負數結果 floor 0（修評估 P1-16） |
| **優先級** | P0 |
| **建議模組** | `tests/test_points_floor.py` |
| **前置** | login `parent_a`；kid_a points=1 |
| **步驟** | 1. `POST /api/kids/{kid_a}/points` `{"amount":-50,"reason":"parent"}`（若 endpoint 改為只准 adjust，則呢步應 404／405，改 assert） |
| **預期** | 200 且 points=0 **或** 明確廢除呢條路由（測試鎖廢除）。禁止 200 且 points 為負。 |

---

## P0-TC-LIST-01 — GET /api/kids 不再公開全站兒童

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-LIST-01 |
| **標題** | 未登入 `GET /api/kids` 401；kid session 只見自己；家長只見 linked |
| **優先級** | P0 |
| **建議模組** | `tests/test_list_kids_privacy.py` |
| **前置** | kid_a、kid_b 兩個家庭 |
| **步驟** | 1. 未登入 GET `/api/kids` 2. login kid_a GET 3. login parent_a GET |
| **預期** | 1：401（或 403，但**唔好** 200+陣列）。2：200 陣列長度 1 且 id=kid_a，**無** kid_b。3：只有 A 家庭小孩。Body 無 PIN。 |

---

## P0-TC-LIST-02 — parent-kids 唔好洩漏未授權 query

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-LIST-02 |
| **標題** | `GET /api/auth/parent-kids?parent_id=` 忽略 query，只用 session |
| **優先級** | P0 |
| **建議模組** | `tests/test_list_kids_privacy.py` |
| **前置** | login parent_a |
| **步驟** | 1. GET `parent-kids?parent_id={parent_b}` |
| **預期** | 200 只返回 A 嘅仔女，**或** 403；絕唔返回 B 嘅小孩 |

---

## P0-TC-XSS-01 — 任務標題儲存後 API 保持原文、前端策略有文件化斷言

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-XSS-01 |
| **標題** | 標題含 `<script>alert(1)</script>` 時 JSON 係字串；渲染唔用未編碼 innerHTML（前端） |
| **優先級** | P1 |
| **建議模組** | `tests/test_xss_encoding.py` |
| **前置** | login parent_a 建任務 title=`<script>alert(1)</script>` 指定 kid_a |
| **步驟** | 1. GET `/api/tasks?kid_id=kid_a`（kid session）2. 前端：Playwright 或靜態檢查 `completeTask`／任務卡唔把 title 拼進 innerHTML；**若前端測試未修路徑，本 case 後端部分仍要綠，前端部分標手動** |
| **預期** | API JSON `title` 等於原字串（或已 escape，二揀一寫死）。DOM：`document.querySelector` 任務名 `textContent` 含 `<script>` 文字，`page.evaluate` 確認 **無** 執行 script、無額外套咗真正 `script` 節點。 |

---

## P0-TC-XSS-02 — 小朋友顯示名同樣編碼

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-XSS-02 |
| **標題** | kid.name=`<img src=x onerror=alert(1)>` 唔在 HUD 變成真 img onerror |
| **優先級** | P1 |
| **建議模組** | `tests/test_xss_encoding.py` |
| **前置** | 建 kid 時用上述 name（若 create 拒絕特殊字元：改預期為 400，亦算過） |
| **步驟** | 1. GET 該 kid 嘅 town／kids API 2. 手動／Playwright 開 HUD |
| **預期** | API 一致；HUD 名係文字；`#hudAv` 唔因 name 執行 onerror。 |

---

## P0-TC-DEV-01 — /api/dev-dashboard 非管理員不可讀

| 欄 | 內容 |
|----|------|
| **ID** | P0-TC-DEV-01 |
| **標題** | 匿名同 kid／家長 session GET `/api/dev-dashboard` 401／403 |
| **優先級** | P0 |
| **建議模組** | `tests/test_authz_session.py` |
| **前置** | 三個 client：匿名、kid_a、parent_a |
| **步驟** | 各 GET 一次 |
| **預期** | 全部非 admin 失敗；body 無全站 kids 列表 |

---

## 手動／E2E 清單（雙重驗證 B）

瀏覽器對應已自動化（Playwright）：[`FRONTEND_E2E.md`](FRONTEND_E2E.md) `FE-P0-01`…`FE-P0-05`。

喺 pytest 綠之後勾：

- [ ] 無登入用 curl 加分失敗，DB 不變
- [ ] 兩個家庭互打 API，改唔到對方
- [ ] 瀏覽器開 `/kids/kids_town.db`、`/kids/backend_v2.py` 見到 404
- [ ] 登入頁無預填 admin123
- [ ] 家長註冊短密碼有紅字
- [ ] 任務標題打 `<b>粗體</b>` 只見到括號字，頁面樣式唔變粗（若用 textContent）

簽收欄見 `TDD_PROCESS.md` §5。
