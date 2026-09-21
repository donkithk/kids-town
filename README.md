# Kids Town

Family town / chore-reward game. Flask (`backend_v2.py`) + `index.html`.

視覺 UI 試作（未接線，唔改遊戲邏輯）：[`mocks/ui-refresh/`](mocks/ui-refresh/)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

On Linux CI or a fresh desktop, Chromium also needs OS libraries. If `playwright install` warns about missing deps:

```bash
python -m playwright install-deps chromium   # may require sudo
```

## Run the app

```bash
python backend_v2.py
# then open http://127.0.0.1:9123/kids/
```

Or `./scripts/start-app.sh` (see below). Use a **fresh / empty** SQLite file for local security checks. Tests never copy `kids_town.db`.

## 本機、公網、更新 main / Local run, public ngrok, update main

三步方便本機示範與公網預覽。**不要**把 `NGROK_AUTHTOKEN`、`.env`、或本機／示範用的 `kids_town.db` 提交進 git。
Three steps for a local demo and an optional public preview. **Never** commit tokens, `.env`, or a machine-local `kids_town.db`.

公網／ngrok 示範前，**Phase 0 及以上**已鎖定測試必須保持全綠（至少 `python -m pytest tests/ -m phase0 -v`）。未綠不要轉發 `0.0.0.0` 或 ngrok。
Keep **Phase 0+** green before any public demo. Do not expose the app until that gate passes.

### 1. 本機跑 / Run locally

```bash
./scripts/start-app.sh
# http://127.0.0.1:9123/kids/
# http://127.0.0.1:9123/api/health
```

有 `.venv` 會自動啟用；埠 9123 已被占用則拒絕啟動並印出原因。背景跑：`./scripts/start-app.sh --background`（日誌在 `logs/`）。
Activates `.venv` when present. Refuses to start if port 9123 is busy. Use `--background` to daemonize (logs under `logs/`).

### 2. 公網 ngrok / Public tunnel

```bash
export NGROK_AUTHTOKEN=...          # required; never commit
# optional reserved domain (example hostname only — not a token):
export NGROK_DOMAIN=moody-faction-spoken.ngrok-free.dev
./scripts/start-ngrok.sh
```

有設 `NGROK_DOMAIN` 時用 `ngrok http 9123 --domain=$NGROK_DOMAIN`，否則拿隨機免費 URL，並印出公開網址。
Uses a reserved domain when `NGROK_DOMAIN` is set; otherwise a random free URL. Prints the public https URL.

一次做完兩步：`./scripts/dev-up.sh`（先確保本機 9123，再開 ngrok）。
Or run both: `./scripts/dev-up.sh`.

### 3. 更新 main / Update to latest main

```bash
./scripts/update-main.sh
```

`git fetch` + `git reset --hard origin/main`，**備份／還原 `kids_town.db`**（示範進度不會被 repo 內的樣本庫蓋掉），`requirements.txt` 有變才重裝，然後殺掉舊的 9123 行程並重啟。
Fetches and hard-resets to `origin/main`, **preserves** `kids_town.db`, reinstalls requirements only if they changed, then restarts the app on 9123.

腳本說明：[`scripts/start-app.sh`](scripts/start-app.sh)、[`scripts/start-ngrok.sh`](scripts/start-ngrok.sh)、[`scripts/update-main.sh`](scripts/update-main.sh)、[`scripts/dev-up.sh`](scripts/dev-up.sh)（各支援 `--help`）。

## Tests

API (Phase 0 security, no browser):

```bash
python -m pytest tests/ -m phase0 -v
```

Phase 1.5 onboarding pack (TDD; currently RED until the guild-cost / starter-pack product PR):

```bash
python -m pytest tests/ -m phase1_5 -v
```

Frontend E2E (Playwright + Chromium, empty seeded DB):

```bash
python -m playwright install chromium   # once per machine
python -m pytest tests/test_frontend.py -v
```

If Chromium is not installed, those tests **skip** with a message that includes `python -m playwright install chromium`. They no longer require a Windows-only Python path.

Full suite:

```bash
python -m pytest tests/ -v
```

Case catalogs: [`docs/test-cases/PHASE0_SECURITY.md`](docs/test-cases/PHASE0_SECURITY.md), [`docs/test-cases/PHASE1_GAMEPLAY.md`](docs/test-cases/PHASE1_GAMEPLAY.md), [`docs/test-cases/PHASE1_5_ONBOARD.md`](docs/test-cases/PHASE1_5_ONBOARD.md), [`docs/test-cases/FRONTEND_E2E.md`](docs/test-cases/FRONTEND_E2E.md). Engineering process: [`docs/TDD_PROCESS.md`](docs/TDD_PROCESS.md).
