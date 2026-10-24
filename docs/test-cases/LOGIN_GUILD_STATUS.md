# Guild-hall login status

> RED on purpose. Tests and docs only. Product JS/CSS/HTML were not changed.  
> Recorded 2026-10-24 against **main** `d5a085fc2dd81ddc6ae744423845e98b92e8f513` (`d5a085f`).  
> Visual contract: PR #67 tip `03f11429881b1ae9636f864fa37e5c60862db901`, `docs/ui-mocks/login.html`.  
> Cases: [`LOGIN_GUILD.md`](LOGIN_GUILD.md). Runner: `tests/test_login_guild_e2e.py`.  
> Python 3.12.3 / pytest 9.1.1 / Playwright Chromium (headless) on Linux.  
> Empty temp DB. Synthetic `test_login_kid` / `test_login_parent` / `test_login_admin` only. PIN and passwords come from `tests/factories.py`. Production `kids_town.db` was not opened. Its sha256 is still `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`.

The product login is still the orange card: `document.title` is `🌈 Kids Town 2.0 開羅小鎮`, visible headings are `Kids Town` and `開羅小鎮`, placeholders are `登入名稱` and `密碼`. There is no slogan 「歡迎回到開心的小鎮」, no hero alt 「木牌寫著 Kids Town」, no cream panel, and no 1280×720 oak stage. Hash `#kid` / `#parent` / `#admin` / `#register` does not switch labelled fields. Auth cases stop before `POST /api/auth/login` because the new controls are absent, so the old `🚪 登入` button is not treated as a pass.

### Command

| Suite | Command | Result |
|-------|---------|--------|
| Guild login | `python3 -m pytest tests/test_login_guild_e2e.py -q --tb=no` | **9 failed** in 5.12s |

### Case ID → result on main `d5a085f`

| Case ID | Pytest | Result | Why it is red |
|---------|--------|--------|----------------|
| TC-FE-LOGIN-STAGE-01 | `test_login_guild_stage_letterboxes` | **FAIL** | Slogan is missing, so neither `1000×800` nor `1600×720` has a visible 1280×720 oak stage to letterbox. |
| TC-FE-LOGIN-HERO-01 | `test_login_guild_hero_cream_overlay_no_competing_title` | **FAIL** | No hero image whose alt contains 「木牌寫著 Kids Town」. `<h1>Kids Town</h1>` is a competing title. No cream panel. |
| TC-FE-LOGIN-COPY-01 | `test_login_guild_copy_slogan_and_no_cairo_name` | **FAIL** | 「開羅小鎮」 is in `document.title` and the visible `<h2>`. Slogan 「歡迎回到開心的小鎮」 is missing. |
| TC-FE-LOGIN-MODE-01 | `test_login_guild_modes_hash_and_plaques` | **FAIL** | Plaques 孩子登入 / 家長登入 / 管理員 / 註冊 are not radio, button, or tab controls. Hash routes do not show the formal headings, leads, or fields. |
| TC-FE-LOGIN-FIELDS-01 | `test_login_guild_fields_pin_password_register` | **FAIL** | No labelled PIN. No labelled 密碼. Register does not show 用戶名稱 / 密碼 / 稱呼 / 電郵（可選）. |
| TC-FE-LOGIN-AUTH-KID-01 | `test_login_guild_auth_kid_pin` | **FAIL** | No 「進入小鎮」 button and no PIN field, so the wrong-PIN and correct-PIN login posts were not sent. |
| TC-FE-LOGIN-AUTH-PARENT-01 | `test_login_guild_auth_parent_password` | **FAIL** | No 「以家長身份登入」 button and no labelled 密碼 field. |
| TC-FE-LOGIN-AUTH-ADMIN-01 | `test_login_guild_auth_admin_password` | **FAIL** | No 「以管理員身份登入」 button and no 管理員名稱 field. |
| TC-FE-LOGIN-AUTH-REGISTER-01 | `test_login_guild_auth_register_then_login` | **FAIL** | Register mode does not show the four labelled fields or 「建立帳戶」, so `POST /api/auth/parent-register` was not sent. |

Buildings and warehouse placement were not part of this run.
