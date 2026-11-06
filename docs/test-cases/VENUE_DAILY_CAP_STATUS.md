# Venue daily battle cap — status

> Green. Product now counts one successful venue win per Hong Kong day.
> Cases: [`VENUE_DAILY_CAP.md`](VENUE_DAILY_CAP.md).
> The red suite is the cherry-picked lock from `9dce1eb` (PR #77). Those tests were not rewritten.
> Python 3.12.3 / pytest 9.2.0 on Linux. Process timezone UTC.
> Empty temp DB. Synthetic `test_battle_kid`, `preview_kid`, and `preview_kid_2`. PIN `1357` from `tests/factories.py`. No production password.
> Production `kids_town.db` was not modified. sha256 before and after the run is `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`.

The suite is green. **8 passed** in 0.72s.

Pytest ran on green product commit `58d960f7f1c48db9c730d5d398e9bc516ed32185` (`58d960f`). Green result note: `7c876700ae86f85f1887b631a049d2dd483c68f9` (`7c87670`). The commit that writes this hash into the note does not change product code, tests, or the result table. Product bytes match `58d960f`.

Wait for Grok Preview before 合啦. Red #77 can close after this merges.

### Command

| Suite | Command | Result |
| --- | --- | --- |
| Venue daily cap | `python3 -m pytest tests/test_venue_daily_cap.py -v --tb=short` | **8 passed** in 0.72s |

### What the product does now

| Piece | Change |
| --- | --- |
| `battle_start` daily `SELECT` | `battle_date` is `hk_today_str()` (Asia/Hong_Kong, UTC+8), the same clock as farm claims |
| `_record_daily_battle` | Inserts that same Hong Kong date. Boss wins still return immediately and do not consume the slot |
| Blocked `battle-start` JSON `error` | `今日已在此區域獲勝，請明日再來。` |
| `ensure_preview_kid` | Deletes the preview kid's `daily_battles` rows for `hk_today_str()`, not `date.today()` |
| Boss / explore | Unchanged. Explore `POST .../expedition/claim` still does not read or write `daily_battles` |
| Toast | `startBattle` already toasts `⚠️ ` plus `data.error`. No frontend string change |

Two older fixtures seeded or looked up `daily_battles.battle_date` with `date.today()`. After this clock change they would miss the row from 16:00 UTC until midnight UTC. `tests/test_battle_integration.py` and `tests/test_frontend.py` (TC-FE-10) now use `hk_today_str()`. The red file `tests/test_venue_daily_cap.py` was not edited.

### Case ID → result on `58d960f`

| Case ID | Pytest | Result | What green did |
| --- | --- | --- | --- |
| TC-API-VENUE-DAILY-CAP-01 | `test_second_win_same_venue_same_day_is_blocked` | **PASS** | Second `battle-start` is HTTP 400. `error` is exactly `今日已在此區域獲勝，請明日再來。`. Points and EXP stay at the post-win values. No new running battle. Row stays `(1, 2026-11-06)`. |
| TC-API-VENUE-DAILY-CAP-02 | `test_loss_does_not_consume_slot_and_win_still_pays` | **PASS** | A forced loss leaves `daily_battles` empty and does not change points or EXP. The later win pays once. |
| TC-API-VENUE-DAILY-CAP-03 | `test_flee_or_abandoned_start_does_not_consume_slot` | **PASS** | Flee, and a second start that completes the previous running battle, write no row. The later win pays once. |
| TC-API-VENUE-DAILY-CAP-04 | `test_other_venue_same_day_still_pays` | **PASS** | Venue A and venue B each pay once. Rows `(1, 2026-11-06)` and `(2, 2026-11-06)`. A further start at A is HTTP 400 and does not pay. |
| TC-API-VENUE-DAILY-CAP-05 | `test_next_hk_day_allows_same_venue_again` | **PASS** | Win at 15:00 UTC (Hong Kong 2026-11-06). At 16:30 UTC the Hong Kong date is 2026-11-07 and the UTC date is still 2026-11-06. Start is HTTP 201. |
| TC-API-VENUE-DAILY-CAP-06 | `test_utc_midnight_does_not_reset_hk_day` | **PASS** | Win at 20:00 UTC stores `battle_date` `2026-11-07`. At 01:00 UTC the next UTC date (Hong Kong still 2026-11-07) `battle-start` is HTTP 400 with the locked sentence. Points and EXP do not increase. |
| TC-API-VENUE-DAILY-CAP-07 | `test_preview_account_can_win_same_venue_twice` | **PASS** | `preview_kid` wins venue A twice. Points +20 twice, EXP +25 twice. `ensure_preview_kid` was not called. |
| TC-API-VENUE-DAILY-CAP-08 | `test_lookalike_username_is_not_preview` | **PASS** | `preview_kid_2` is blocked on the second start (HTTP 400). Points and EXP stay put. No new running battle. |

### Compared with main `2e6bdaf`

On main this suite was 3 failed, 5 passed. The three failures were the colloquial error `今日已打過此區，聽日再嚟`, Hong Kong midnight leaving the venue closed, and UTC midnight opening it early because `battle_date` used `date.today()`. Those three now pass. Boss wins still do not write `daily_battles`.

## Independent regress — PASS

Recorded against tip `f200bcec8e14799e5c1c01e06a5b00f5f40b3c44`. `git rev-parse HEAD` was that SHA before the suite and after it. Docs only. The red file was not edited. Do not merge this note ahead of a person reading it.

`git diff 58d960f7f1c48db9c730d5d398e9bc516ed32185 HEAD` is this status file only, so the product bytes under test are `58d960f`. `git diff 9dce1eb9929f67a656f503ee255550f0a4e13558 HEAD -- tests/test_venue_daily_cap.py docs/test-cases/VENUE_DAILY_CAP.md` is empty. The colloquial string `今日已打過此區，聽日再嚟` is not in `backend_v2.py` or `index.html`.

### Command

`TZ=UTC python3 -m pytest tests/test_venue_daily_cap.py -v --tb=short`

**8 passed** in 0.66s. Python 3.12.3, pytest 9.2.0. Wall clock was 2026-11-06 11:52 UTC, still the same calendar day in Hong Kong, so the suite's own freezes are what separate the two clocks.

| Case ID | Result |
| --- | --- |
| TC-API-VENUE-DAILY-CAP-01 | **PASS** |
| TC-API-VENUE-DAILY-CAP-02 | **PASS** |
| TC-API-VENUE-DAILY-CAP-03 | **PASS** |
| TC-API-VENUE-DAILY-CAP-04 | **PASS** |
| TC-API-VENUE-DAILY-CAP-05 | **PASS** |
| TC-API-VENUE-DAILY-CAP-06 | **PASS** |
| TC-API-VENUE-DAILY-CAP-07 | **PASS** |
| TC-API-VENUE-DAILY-CAP-08 | **PASS** |

Same HEAD, same database hash: `tests/test_battle_integration.py`, `tests/test_preview_seed.py`, and `tests/test_expedition_gold.py::test_explore_can_be_farmed_again_after_claim` — **19 passed** in 0.79s (12 + 6 + 1).

### False greens

Extra probes, not added to the suite.

- At 2026-11-06 20:00 UTC (`hk_today_str()` is 2026-11-07, `date.today()` is 2026-11-06) a row dated 2026-11-06 does not block venue A. A row dated 2026-11-07 does, and `error` is exactly `今日已在此區域獲勝，請明日再來。`.
- A boss summon and win writes no `daily_battles` row, pays gold, and venue A still starts (HTTP 201).
- After a venue A win, explore start + claim twice still pays. Each start deducts the region 1 fee of 10. Each claim adds its gold (range 6–10) and does not read or write `daily_battles`. The venue row stays `(1, 2026-11-06)`. The next `battle-start` is HTTP 400 with the locked sentence.
- Regions 4 and 5 return `region_locked` even when a `daily_battles` row exists for that region.
- `preview_kid` writes `(1, 2026-11-06)` on the win and can start again. Renaming that stored username to `Preview_Kid` makes `kid_is_preview` false, and the next start is HTTP 400 with the locked sentence. Typed login `Preview_Kid` still finds stored `preview_kid`, because `/api/auth/login` lowercases the name before the lookup.
- Another kid can start venue A on the same day.
- `battle-action` after the win is HTTP 400 `No running battle`. Points and EXP stay put. The row stays one.
- `ensure_preview_kid` at 20:00 UTC deletes the preview kid's 2026-11-07 row and leaves 2026-11-06. A normal kid keeps both rows.

`index.html` is not in the #78 diff. `startBattle` still toasts `⚠️ ` plus `data.error`. TC-FE-10 was not run. It only asserts that the error and the toast contain `今日`.

Production `kids_town.db` sha256 before and after every run: `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`.
