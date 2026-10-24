# 公會歡迎登入（RED）

> **設計稿**：PR #67 tip `03f11429881b1ae9636f864fa37e5c60862db901`，檔案 `docs/ui-mocks/login.html`（branch `cursor/login-guild-mock-fcde`）。  
> **Runner**：`tests/test_login_guild_e2e.py`（sync Playwright，`sys.executable`，空庫）。  
> **篩選**：`python -m pytest tests/test_login_guild_e2e.py -q --tb=line`  
> **Fixture**：空 SQLite + 合成帳戶。**禁止** copy `kids_town.db`，禁止真實 PIN／密碼。  
> **狀態**：[`LOGIN_GUILD_STATUS.md`](LOGIN_GUILD_STATUS.md)。而家 main 產品仍係橙色 `#loginScreen` 卡，呢組留紅。  
> **唔改**：產品 JS／CSS／HTML、建築、入倉放置。

登入係疊喺歡迎主圖上嘅畫面，唔係另一張空白頁。Builder 要喺 `/kids/` 產品頁做到下面嘅可見行為，並且接上現有 API。設計稿入面嘅 `preventDefault`、「靜態設計稿，不會驗證身份」、`#kid-username` 呢類 id **唔好**原樣抄進產品。id 可以係產品自己嘅；accessible name、欄位種類、hash、外框同埋真正登入必須符合呢度。

共用前置：

1. Session test server，`TESTING=True`，空庫。
2. 小朋友 `test_login_kid` / `LoginKid`，PIN 用 `tests/factories.py` 嘅 `TEST_KID_PIN`。
3. 家長 `test_login_parent` / `Login Parent`，密碼用 `TEST_PARENT_PASSWORD`，已連結上面嗰個小朋友。
4. 管理員 `test_login_admin`，密碼用 `TEST_ADMIN_PASSWORD`。
5. 註冊用一次性 `test_login_new` / `測試家長` / `test_login_new@example.test`，密碼 `TestReg!pass1`。

---

## 可見合約（書面語）

口號同欄位說明跟設計稿原文：

| 模式 | hash | 銘牌 | 標題 | 說明 | 欄位 | 按鈕 |
|------|------|------|------|------|------|------|
| 孩子 | `#kid` | 孩子登入 | 孩子登入 | 請輸入登入名稱與 PIN。不使用密碼。 | 登入名稱（text）、PIN（password，minlength 4） | 進入小鎮 |
| 家長 | `#parent` | 家長登入 | 家長登入 | 請輸入登入名稱與密碼。 | 登入名稱（text）、密碼（password） | 以家長身份登入 |
| 管理員 | `#admin` | 管理員 | 管理員登入 | 請使用已獲授權的帳戶。不設預設密碼。 | 管理員名稱（text）、密碼（password） | 以管理員身份登入 |
| 註冊 | `#register` | 註冊 | 註冊家長帳戶 | 建立後可管理孩子的登入。密碼至少八個字元。 | 用戶名稱、密碼（password，minlength 8）、稱呼、電郵（可選）（email，唔好 required） | 建立帳戶 |

銘牌要同時見到，可以係 radio、button 或 tab，accessible name 要同表上面一字不差（唔好只靠 placeholder，亦唔好靠 emoji 前綴）。開 `#kid` / `#parent` / `#admin` / `#register` 要直接顯示該模式。撳銘牌都要切換。非活躍模式嘅欄位要收起。

口號 **歡迎回到開心的小鎮** 同正在用嘅欄位一齊放喺奶油色面板（接近 `rgba(255, 248, 238, 0.9)`）。面板中心要疊喺歡迎主圖上面。

**Kids Town** 只可以出現喺主圖木牌。可見 `<img>` 嘅 alt 要包含「木牌寫著 Kids Town」。畫面唔好再有一個可見嘅大字標題「Kids Town」（而家嘅 `<h1>Kids Town</h1>` 會失敗）。

**開羅小鎮** 唔好出現喺登入畫面：可見文字、隱藏文案、placeholder、alt、aria-label、`document.title` 都唔好有。

舞台係固定 **1280×720**（border box）橡木外框，暖木底色（設計稿舞台底色 `#a86b38`）加內框。Viewport 改變時用 `scale = min(clientWidth/1280, clientHeight/720)` 等比縮放並置中。多出嚟嘅位置係深色信箱（設計稿頁底 `#140e0b`；亮度夠低嘅深木色亦可）。測試量兩個 viewport：

- `1000×800`：左右貼齊，上下有信箱。
- `1600×720`：上下貼齊，左右有信箱。

---

## 登入行為（唔好削弱現有 auth）

產品提交要打現有 API，唔好打去設計稿嗰句「不會登入」。

| 動作 | API | 成功 | 失敗 |
|------|-----|------|------|
| 孩子「進入小鎮」 | `POST /api/auth/login`，body `username` + `password`（password 欄放 PIN） | 200，`role=kid`；離開登入畫面；`#hudNm` 係 `LoginKid`；`GET /api/auth/session` 200 | 錯 PIN（合成 `9999`）403；口號仍在；`#app` 唔可見；有錯誤文案；session 401 |
| 家長「以家長身份登入」 | 同上，`password` 係家長密碼 | 200，`role=parent`；見到「小朋友管理」；`GET /api/auth/parent-kids` 200 | 錯密碼 403；留喺登入；parent-kids 401 |
| 管理員「以管理員身份登入」 | 同上 | 200，`role=admin`；`#app` 可見；`GET /api/kids` 200 | 錯密碼 403；留喺登入；`/api/kids` 401 |
| 「建立帳戶」 | `POST /api/auth/parent-register`，四個欄位都要入 body（電郵可選但測試會填） | 201；再用 `#parent` 同呢組密碼登入，200 並離開登入 | 唔好顯示「此為靜態設計稿，不會驗證身份，也不會登入。」 |

回應 JSON 唔好帶 `pin` 或 `password`。

---

## TC-FE-LOGIN-STAGE-01 — 橡木 1280×720 信箱

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-STAGE-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | 開 `/kids/#kid`。Viewport 設 `1000×800`，再設 `1600×720`。 |
| **預期** | 口號坐喺可見嘅 1280×720 舞台入面。視覺尺寸等於 `1280*scale` × `720*scale`，置中。舞台底色係暖橡木，並且有內框。第一個 viewport 頂部有深色信箱；第二個 viewport 左側有深色信箱。 |

---

## TC-FE-LOGIN-HERO-01 — 主圖與奶油面板

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-HERO-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | Viewport `1280×720`，開 `/kids/#kid`。 |
| **預期** | 可見主圖 alt 包含「木牌寫著 Kids Town」，而且鋪滿舞台大部分。奶油面板中心疊喺圖上。可見文字節點唔好再有大字「Kids Town」。 |

---

## TC-FE-LOGIN-COPY-01 — 口號，以及禁止「開羅小鎮」

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-COPY-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | 開 `/kids/#kid`。讀 title、正文文字節點、placeholder、alt、aria-label。 |
| **預期** | 任何一處都冇「開羅小鎮」。口號「歡迎回到開心的小鎮」可見，而且同活躍欄位喺同一塊奶油面板。 |

---

## TC-FE-LOGIN-MODE-01 — 四個模式

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-MODE-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | 1. 撳銘牌 家長登入、管理員、註冊、孩子登入 2. 再開 `#kid` `#parent` `#admin` `#register` |
| **預期** | 每次都顯示該模式嘅標題、書面語說明、欄位種類同提交按鈕。另外三個模式嘅欄位收起。四塊銘牌一路都喺畫面。 |

---

## TC-FE-LOGIN-FIELDS-01 — PIN、密碼、註冊四欄

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-FIELDS-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | 順序開 `#kid`、`#parent`、`#admin`、`#register`。 |
| **預期** | 孩子秘密欄位嘅 accessible name 係「PIN」，`type=password`，minlength 4，而且見唔到「密碼」欄。家長同管理員秘密欄位係「密碼」，見唔到 PIN。註冊正好四欄：用戶名稱、密碼、稱呼、電郵（可選）。電郵 `type=email` 而且唔係 required。 |

---

## TC-FE-LOGIN-AUTH-KID-01 — 孩子 PIN

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-AUTH-KID-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | `#kid` 填 `test_login_kid` 同錯 PIN，撳「進入小鎮」。再填正確 PIN。 |
| **預期** | 錯：403，留喺登入，有錯誤，session 401。對：200 `role=kid`，HUD 名 `LoginKid`，登入層收起，session 200。 |

---

## TC-FE-LOGIN-AUTH-PARENT-01 — 家長密碼

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-AUTH-PARENT-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | `#parent` 先錯密碼，再正確密碼。 |
| **預期** | 錯：403，留喺登入，parent-kids 401。對：200 `role=parent`，見到「小朋友管理」，parent-kids 200。 |

---

## TC-FE-LOGIN-AUTH-ADMIN-01 — 管理員密碼

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-AUTH-ADMIN-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | `#admin` 先錯密碼，再正確密碼。 |
| **預期** | 錯：403，留喺登入，`GET /api/kids` 401。對：200 `role=admin`，`#app` 可見，登入層收起，`GET /api/kids` 200。 |

---

## TC-FE-LOGIN-AUTH-REGISTER-01 — 註冊再登入

| 欄 | 內容 |
|----|------|
| **ID** | TC-FE-LOGIN-AUTH-REGISTER-01 |
| **優先級** | P0 |
| **建議模組** | `tests/test_login_guild_e2e.py` |
| **步驟** | `#register` 填四欄，撳「建立帳戶」。再開 `#parent` 用剛註冊嘅密碼登入。 |
| **預期** | `POST /api/auth/parent-register` 201，body 含用戶名稱、密碼、稱呼、電郵。之後家長登入 200，離開登入層，parent-kids 200。 |

---

## 點跑

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m pytest tests/test_login_guild_e2e.py -q --tb=line
```

Skip 只可以係 Chromium 未裝，原因要包含 `python -m playwright install chromium`。

## Builder 點先至綠

1. 喺產品 `/kids/` 登入層做出上表，而唔係把 `docs/ui-mocks/login.html` 整份換入 `index.html`。
2. 孩子 PIN、家長密碼、管理員密碼走 `POST /api/auth/login`。註冊四欄走 `POST /api/auth/parent-register`。
3. 成功就收起登入層（孩子見 HUD，家長見小朋友管理，管理員見 `#app`）。失敗就留喺登入並顯示錯誤。
4. 拿掉登入畫面上嘅「開羅小鎮」同獨立大字「Kids Town」。主圖木牌用 alt 講明寫住 Kids Town。
5. 建築同入倉放置唔好喺呢個 PR 改。
