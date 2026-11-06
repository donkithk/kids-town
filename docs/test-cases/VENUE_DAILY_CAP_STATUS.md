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
