# Edge-touching footprints — status

> Tests and docs only. Product JS, CSS, HTML, and `backend_v2.py` were not changed.
> Recorded 2026-10-24 against **main** `48bae94747dc37ec1867dc3262a34a794e03200b` (`48bae947`).
> Cases: [`BUILDING_ADJACENT_FOOTPRINT.md`](BUILDING_ADJACENT_FOOTPRINT.md).
> Python 3.12.3 / pytest 9.1.1 / Playwright (headless Chrome) on Linux.
> Empty temp DB. Synthetic `test_kid_a` (API) and `test_adjacent_kid` (scene). PIN from `tests/factories.py` (`1357`). No production password.
> Production `kids_town.db` was not opened. sha256 is still `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`.

`main` already allows edge-touch. Half-open footprints (`<=` on the max edge) accept a shared boundary and reject area overlap. These cases lock that contract. They are green on this tip. FAIL count: **0**.

The “must leave a gap” feeling is not this rule. A 2×2 sprite is drawn only on the origin pad, and the other footprint cells are labeled 「空地」. Detail is in the case note.

### Command

| Suite | Command | Result |
| --- | --- | --- |
| API, domain, map formula, scene | `python3 -m pytest tests/test_building_adjacent_footprint.py tests/test_building_adjacent_e2e.py -q --tb=line` | **8 passed** in 2.74s |

### Case ID → result on main `48bae947`

| Case ID | Pytest | Result | What main did |
| --- | --- | --- | --- |
| TC-API-BUILD-ADJACENT-01 | `test_half_open_overlap_allows_shared_edge` | **PASS** | Shared edge is not an overlap. `(1,0)` against `(0,0)` size 2 returns 「該位置已被建築物佔用」, 400. Catalog footprint is 2, including `GET /api/building-defs`. |
| TC-API-BUILD-ADJACENT-02 | `test_place_edge_adjacent_footprints_succeed` | **PASS** | East pack, south pack, west, north, partial edge, and corner all HTTP 201. Rows stay `stored=0`. Catalog price charged once. |
| TC-API-BUILD-ADJACENT-03 | `test_place_true_area_overlap_is_blocked` | **PASS** | `(1,0)`, `(0,1)`, `(1,1)` are HTTP 400 `{"error": "該位置已被建築物佔用"}`. No charge, no new row. |
| TC-API-BUILD-ADJACENT-04 | `test_move_allows_shared_edge_and_blocks_overlap` | **PASS** | Move to `(2,0)` is HTTP 200 `{"ok": true, "cell_x": 2, "cell_y": 0}`. Move to `(1,0)` is HTTP 400 with the occupied body and the row stays. A lone building may slide to `(1,0)`. |
| TC-API-BUILD-ADJACENT-05 | `test_unstore_allows_shared_edge_and_blocks_overlap` | **PASS** | Unstore to `(2,0)` and `(0,2)` is HTTP 200, level 2 kept, no charge. `(1,0)` is HTTP 400 and stays `stored=1` at `(20,12)`. |
| TC-API-BUILD-ADJACENT-06 | `test_auto_place_picks_touching_origin_not_a_one_cell_gap` | **PASS** | Omitted coordinates place the hospital at `(2,0)`, not `(3,0)`. |
| TC-FE-BUILD-ADJACENT-01 | `test_frontend_overlap_matches_half_open_backend` | **PASS** | `town-four-scene.js` `footprintsOverlap` matches the backend matrix. Toast sentences are in that file. |
| TC-FE-BUILD-ADJACENT-02 | `test_scene2_allows_edge_adjacent_origin_and_blocks_overlap_cell` | **PASS** | Scene 2 gold includes `(2,0)` and excludes `(1,0)`. Overlap toasts are `info`. Confirming `(2,0)` is HTTP 201 and 「起好「醫院」。」 |

No product fix is indicated for the collision rule. Do not dispatch a builder to reject or accept a different overlap test unless the review wants a visual change (sprite / 「空地」 / scene 3 「可以放置」). That visual change is not locked as a failure here.
