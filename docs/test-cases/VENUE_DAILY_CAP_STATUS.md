# Venue daily battle cap — status

> Tests and docs only. `backend_v2.py`, `index.html`, and every other product file were not changed.
> Recorded against product **main** `2e6bdafeb9b67eb420f059a01c9c550c3e4c869f` (`2e6bdaf`).
> Cases: [`VENUE_DAILY_CAP.md`](VENUE_DAILY_CAP.md).
> Python 3.12.3 / pytest 9.2.0 on Linux. Process timezone UTC.
> Empty temp DB. Synthetic `test_battle_kid`, `preview_kid`, and `preview_kid_2`. PIN `1357` from `tests/factories.py`. No production password.
> Production `kids_town.db` was not modified. sha256 before and after the run is `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`.

The suite is red. **3 failed, 5 passed** in 0.54s. The five passes are behavior main already has (a loss, a flee, and an abandoned start do not write `daily_battles`; venue B still pays; `preview_kid` can win twice; `preview_kid_2` cannot). The three failures are the contract main does not meet: the formal sentence, and the Hong Kong calendar day.

Await Grok dispatch.

### Command

| Suite | Command | Result |
| --- | --- | --- |
| Venue daily cap | `python3 -m pytest tests/test_venue_daily_cap.py -v --tb=line` | **3 failed, 5 passed** in 0.54s |

### Case ID → result on main `2e6bdaf`

| Case ID | Pytest | Result | What main did |
| --- | --- | --- | --- |
| TC-API-VENUE-DAILY-CAP-01 | `test_second_win_same_venue_same_day_is_blocked` | **FAIL** | The second `battle-start` is HTTP 400 and does not pay again or open a fight. `error` is `今日已打過此區，聽日再嚟`, not the proposed `今日已在此區域獲勝，請明日再來。` |
| TC-API-VENUE-DAILY-CAP-02 | `test_loss_does_not_consume_slot_and_win_still_pays` | **PASS** | A forced loss leaves `daily_battles` empty and does not change points or EXP. The later win pays once and writes `(region 1, 2026-11-06)`. |
| TC-API-VENUE-DAILY-CAP-03 | `test_flee_or_abandoned_start_does_not_consume_slot` | **PASS** | Flee, and a second start that completes the previous running battle, write no row and do not change points. The later win pays once. |
| TC-API-VENUE-DAILY-CAP-04 | `test_other_venue_same_day_still_pays` | **PASS** | After venue A pays, venue B (region 2) still pays. A further start at A is HTTP 400 and does not pay. The sentence is asserted in TC-01, not here. |
| TC-API-VENUE-DAILY-CAP-05 | `test_next_hk_day_allows_same_venue_again` | **FAIL** | Win at 15:00 UTC (Hong Kong still 2026-11-06). At 16:30 UTC the Hong Kong date is 2026-11-07 and the UTC date is still 2026-11-06. Start is HTTP 400 `今日已打過此區，聽日再嚟`. The venue stays closed across Hong Kong midnight. |
| TC-API-VENUE-DAILY-CAP-06 | `test_utc_midnight_does_not_reset_hk_day` | **FAIL** | Win at 20:00 UTC (Hong Kong 2026-11-07 04:00) stores `battle_date` `2026-11-06`. At 01:00 UTC on 2026-11-07 (Hong Kong still 2026-11-07 09:00) `battle-start` is HTTP 201 and opens a new fight. UTC midnight lifts the cap eight hours early. |
| TC-API-VENUE-DAILY-CAP-07 | `test_preview_account_can_win_same_venue_twice` | **PASS** | `preview_kid` wins venue A twice on the same frozen day. Points +20 twice, EXP +25 twice. `ensure_preview_kid` was not called. |
| TC-API-VENUE-DAILY-CAP-08 | `test_lookalike_username_is_not_preview` | **PASS** | `preview_kid_2` is blocked on the second start (HTTP 400). Points and EXP stay put. No new running battle. |

### Preview detection on this tip

`kid_is_preview` (`backend_v2.py`) is true only when `kids.username == 'preview_kid'` (`PREVIEW_KID_USERNAME`). There is no preview column. `battle_start` skips the daily `SELECT` for that username. `_record_daily_battle` still inserts a row; the skip is what allows the second start. The lobby uses the same username in `isPreviewKid`. `ensure_preview_kid` also deletes that kid’s `daily_battles` rows for `date.today()` at process boot and when a parent creates `preview_kid`. That delete uses the process-local date, not `hk_today_str()`.
