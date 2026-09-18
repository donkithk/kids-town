# Kids Town

Family town / chore-reward game. Flask (`backend_v2.py`) + `index.html`.

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

Use a **fresh / empty** SQLite file for local security checks. Tests never copy `kids_town.db`.

## Tests

API (Phase 0 security, no browser):

```bash
python -m pytest tests/ -m phase0 -v
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

Case catalogs: [`docs/test-cases/PHASE0_SECURITY.md`](docs/test-cases/PHASE0_SECURITY.md), [`docs/test-cases/FRONTEND_E2E.md`](docs/test-cases/FRONTEND_E2E.md). Engineering process: [`docs/TDD_PROCESS.md`](docs/TDD_PROCESS.md).
