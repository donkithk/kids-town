# Venue daily battle cap

Red-test lock. Tests and this note only. No product code change.

Approved contract (user, via Grok). One battle counts against the daily cap only when it is a **successful win that grants the venue reward**. Starting a fight, fleeing, or losing does not use the slot. The same venue can pay that reward once per calendar day. A different venue is a different slot. The next calendar day opens the venue again. Preview accounts are exempt.

Empty temp database and synthetic accounts only. Production `kids_town.db` is not opened by these tests. Its sha256 on this tip must stay `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`.

Run:

```bash
python3 -m pytest tests/test_venue_daily_cap.py -v
```

Result on this tip: [`VENUE_DAILY_CAP_STATUS.md`](VENUE_DAILY_CAP_STATUS.md). Await Grok dispatch.

## Venue

A venue is one battle region. The lobby cards in `index.html` `REGIONS` are the venues. The cap key is `(kid_id, region_id, calendar day)`.

| Spec name | `region_id` | Lobby name | Monster |
| --- | --- | --- | --- |
| Venue A | 1 | 🌲 靜謐森林 | 野狼 |
| Venue B | 2 | ⛰️ 雪山山脈 | 白熊 |

Regions 4 and 5 answer `region_locked` before any daily check. They are not venues in this contract. Boss fights are not this cap: `_record_daily_battle` returns immediately when `is_boss` is set, and boss wins keep the separate 7-day summon cooldown.

## What consumes the slot

The player-facing battle has no second “領取獎勵” step. `POST /api/kids/<id>/expedition/battle-action` grants gold, materials, and EXP inside `_award_battle_rewards` on the same request that sets `battle_result` to `won`, then `_record_daily_battle` inserts `daily_battles`. That winning request **is** the win and the reward claim.

`POST /api/kids/<id>/expedition/claim` is the timed explore/quiz claim. It does not read or write `daily_battles`. Repeat explore stays `P1-TC-EXP-05`. This contract does not move explore claims onto the battle cap.

| Action | Uses the venue slot? |
| --- | --- |
| `POST .../expedition/battle-start` | No |
| `battle-action` `flee` | No |
| `battle-action` that ends `lost` | No |
| Starting again, which marks the previous running battle `completed` | No |
| `battle-action` that ends `won` and grants the reward | Yes, one slot for that venue and that day |
| Boss win | No (out of scope; weekly boss cooldown stays) |
| Explore `expedition/claim` | No (out of scope; still repeatable) |

After the slot is used, another win/claim at that venue on that day is rejected. The rejection is the next `battle-start` for that `region_id`: HTTP 400, no new running expedition, and no further gold or EXP. A loss or an abandoned start leaves `daily_battles` empty for that kid, so a later win the same day still pays.

## Calendar day

Two clocks exist in `backend_v2.py`.

| Clock | Code | Who uses it |
| --- | --- | --- |
| Hong Kong calendar day | `HK_TZ = timezone(timedelta(hours=8))`, `hk_today_str()` → `datetime.now(HK_TZ).date().isoformat()` | Farm. `farm_claim` docstring: one claim per Asia/Hong_Kong calendar day. `farm_claims.claim_date` and `farm_claimed_today_for_placed` use this helper. Hong Kong has no DST, so the fixed +08:00 offset matches the civil date. |
| Process-local date | `date.today().isoformat()` | Battle cap. `battle_start` and `_record_daily_battle`. `ensure_preview_kid` also deletes the preview kid’s `daily_battles` rows for this local date. |

This environment’s local date is UTC (`date.today()` follows UTC). Hong Kong midnight is 16:00 UTC the previous UTC date. From 16:00 UTC until 24:00 UTC the two dates disagree. On a UTC host the battle cap therefore opens at 08:00 Hong Kong time, eight hours before the farm’s day rolls, and a win during 00:00–08:00 Hong Kong time is stored on the previous UTC date so the cap lifts at 08:00 the same Hong Kong morning.

The contract uses the clock the app already uses for daily resets: **`hk_today_str()`**. `battle_date` is that date. The reset is the next Hong Kong midnight, not the next UTC midnight.

| Instant | UTC date | Hong Kong date | Venue A after a win on HK 2026-11-06 |
| --- | --- | --- | --- |
| 2026-11-06 15:00+00:00 | 2026-11-06 | 2026-11-06 | Slot used (the win itself) |
| 2026-11-06 16:30+00:00 | 2026-11-06 | 2026-11-07 | Open again |
| 2026-11-06 20:00+00:00 | 2026-11-06 | 2026-11-07 | A win here is dated 2026-11-07 |
| 2026-11-07 01:00+00:00 | 2026-11-07 | 2026-11-07 | Still closed if the 20:00 UTC win happened |

## Preview exemption

`kid_is_preview` is the request-time check:

```python
def kid_is_preview(db, kid_id):
    row = db.execute("SELECT username FROM kids WHERE id=?", (kid_id,)).fetchone()
    return bool(row) and row['username'] == PREVIEW_KID_USERNAME  # 'preview_kid'
```

There is no preview column. The match is the full username `preview_kid`, case-sensitive on the stored row. Login lowercases the typed username before the lookup, so the stored row is `preview_kid`. `preview_kid_2` is a normal account.

`battle_start` skips the daily `SELECT` when `kid_is_preview` is true. The frontend lobby uses the same username (`isPreviewKid` in `index.html`). `_record_daily_battle` still inserts a row for a preview win; the skip is what lets them start again. `ensure_preview_kid` also deletes that kid’s rows for `date.today()` when the process boots and when a parent creates `preview_kid`. Tests do not call `ensure_preview_kid`. The exemption under test is the username check on the battle request.

## Player-facing copy

The blocked response is HTTP 400. The JSON `error` string is what `startBattle` toasts. The client does `showToast('⚠️ ' + data.error)`, so the warning sign and the following space are not part of `error`.

Current product string, not accepted (colloquial, and it says the player already fought rather than already won):

`今日已打過此區，聽日再嚟`

Proposed. Marked proposed until Grok confirms the wording. Tests assert this exact `error` value.

| Surface | Exact text | Status |
| --- | --- | --- |
| `POST .../battle-start` JSON `error` | `今日已在此區域獲勝，請明日再來。` | proposed |
| Toast in `#toast` | `⚠️ 今日已在此區域獲勝，請明日再來。` | proposed (client prefix `⚠️ ` plus the API `error`) |

No second reward: `kids.points` and `kids.experience` stay at the post-win values, and `expeditions` has no new `status='running'` battle.

## Cases

### TC-API-VENUE-DAILY-CAP-01 — second win at venue A is blocked

| | |
| --- | --- |
| **Priority** | P0 |
| **Module** | `tests/test_venue_daily_cap.py::test_second_win_same_venue_same_day_is_blocked` |
| **Account** | Synthetic normal kid (`test_battle_kid`), guild placed, level 20 |
| **Clock** | Frozen `2026-11-06 12:00+00:00` (Hong Kong 2026-11-06 20:00). Both clocks still say 2026-11-06. The test logs in again inside the freeze so the session is not issued in the future. |
| **Steps** | Win venue A (start, force one hit, attack). Record points and EXP. `battle-start` venue A again. |
| **Expected** | First win HTTP 200 `battle_result=won`, points up by `gold_reward * monster count`, EXP up by `exp_reward_for_tier(1)` (25), one `daily_battles` row `(1, 2026-11-06)`. Second start HTTP 400, `error` exactly `今日已在此區域獲勝，請明日再來。`, points and EXP unchanged, no running battle. |

### TC-API-VENUE-DAILY-CAP-02 — a loss does not use the slot

| | |
| --- | --- |
| **Priority** | P0 |
| **Module** | `tests/test_venue_daily_cap.py::test_loss_does_not_consume_slot_and_win_still_pays` |
| **Steps** | Start venue A, force a loss, then win venue A the same frozen day. |
| **Expected** | Loss HTTP 200 `battle_result=lost`. No `daily_battles` row. Points and EXP unchanged by the loss. The later win pays once and writes `(1, 2026-11-06)`. |

### TC-API-VENUE-DAILY-CAP-03 — flee or a restarted fight does not use the slot

| | |
| --- | --- |
| **Priority** | P0 |
| **Module** | `tests/test_venue_daily_cap.py::test_flee_or_abandoned_start_does_not_consume_slot` |
| **Steps** | Start venue A and `flee`. Start venue A again and start it once more without attacking (the new start completes the previous running battle). Then win venue A. |
| **Expected** | Flee is `battle_result=fled`. No `daily_battles` row after the flee or after the abandoned restart. Points unchanged until the win. The win pays once. |

### TC-API-VENUE-DAILY-CAP-04 — venue B is still open after A is claimed

| | |
| --- | --- |
| **Priority** | P0 |
| **Module** | `tests/test_venue_daily_cap.py::test_other_venue_same_day_still_pays` |
| **Steps** | Set experience to 375 so `calc_level` is Lv.6. A win rewrites `kids.level` from total EXP; the shared battle fixture is level 20 with only 100 EXP and would fall under venue B’s Lv.4 gate. Win venue A. Win venue B. Start venue A again. |
| **Expected** | Both wins pay (`exp_reward_for_tier(1)` is 25, tier 2 is 35). Rows `(1, 2026-11-06)` and `(2, 2026-11-06)`. Another start at A is HTTP 400 and does not pay again. The exact sentence is TC-01. |

### TC-API-VENUE-DAILY-CAP-05 — the next Hong Kong day opens venue A

| | |
| --- | --- |
| **Priority** | P0 |
| **Module** | `tests/test_venue_daily_cap.py::test_next_hk_day_allows_same_venue_again` |
| **Steps** | Win venue A at `2026-11-06 15:00+00:00` (Hong Kong 23:00, still 2026-11-06). Start venue A at `2026-11-06 16:30+00:00` (Hong Kong 2026-11-07 00:30, UTC date still 2026-11-06). |
| **Expected** | The second start is HTTP 201. The UTC date has not changed. The Hong Kong date has. |

### TC-API-VENUE-DAILY-CAP-06 — UTC midnight does not open the venue early

| | |
| --- | --- |
| **Priority** | P0 |
| **Module** | `tests/test_venue_daily_cap.py::test_utc_midnight_does_not_reset_hk_day` |
| **Steps** | Win venue A at `2026-11-06 20:00+00:00` (Hong Kong 2026-11-07 04:00). Start venue A at `2026-11-07 01:00+00:00` (Hong Kong 2026-11-07 09:00). |
| **Expected** | The stored `battle_date` is `2026-11-07`. The later start is HTTP 400 with the proposed `error`. Points and EXP do not increase. The UTC date rolled; the Hong Kong date did not. |

### TC-API-VENUE-DAILY-CAP-07 — preview kid can win venue A twice the same day

| | |
| --- | --- |
| **Priority** | P0 |
| **Module** | `tests/test_venue_daily_cap.py::test_preview_account_can_win_same_venue_twice` |
| **Account** | Synthetic `preview_kid` only. PIN `1357` from `tests/factories.py`. Not `ensure_preview_kid`, so the startup row delete is not the exemption. |
| **Steps** | Win venue A. Win venue A again under the same freeze. |
| **Expected** | Both wins HTTP 200 `battle_result=won`. Points increase by 20 twice (preview forces one monster; region 1 `gold_reward` is 20). EXP increases by 25 twice. |

### TC-API-VENUE-DAILY-CAP-08 — a lookalike username is not preview

| | |
| --- | --- |
| **Priority** | P0 |
| **Module** | `tests/test_venue_daily_cap.py::test_lookalike_username_is_not_preview` |
| **Account** | Synthetic `preview_kid_2` |
| **Steps** | Win venue A. Start venue A again. |
| **Expected** | Second start HTTP 400. Points and EXP unchanged. Exemption is the exact username `preview_kid` only. |

## Open questions for Grok

1. Confirm the day is `hk_today_str()` (the farm’s Hong Kong calendar day), not `date.today()` / UTC.
2. Confirm the proposed sentence `今日已在此區域獲勝，請明日再來。` The product string today is `今日已打過此區，聽日再嚟`.
3. Confirm “claim reward” means the gold/EXP grant inside the winning `battle-action`. Explore `/expedition/claim` stays repeatable and off this cap.
4. Confirm a boss win does not consume the venue slot.
5. Confirm preview means stored `kids.username == preview_kid` only, not a new column and not a username prefix.
