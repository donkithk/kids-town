# Edge-touching building footprints

Red-test lock. Tests and this note only. No product code change.

Recorded against **main** `48bae94747dc37ec1867dc3262a34a794e03200b` (`48bae947`, static guild-hall login mock, #67). The parent of that tip is `14ffd862` (`14ffd86`, guild-hall login wired to auth, #69).

Approved contract for this round: two footprints may share an edge. Placement must not require an empty cell between them. A true area overlap stays blocked.

`main` already implements that contract. The new cases passed (8/8). They stay so a later change cannot turn a shared edge into a one-cell gap. The player-facing “I have to leave a gap” report is not a collision bug. The hypothesis is below, for review before any builder is sent.

Empty temp database and synthetic accounts only. Production `kids_town.db` was not opened. Its sha256 is still `c046fc41e1cf0eb8c5be5ae5a100fd62dfc6390e8c2277a6a84f93002fe3ecfb`.

## What the code does

Footprints are half-open squares `[x, x + size) × [y, y + size)`. Touching at the max edge is not an overlap.

```text
separated when ax + a_size <= bx
          or bx + b_size <= ax
          or ay + a_size <= by
          or by + b_size <= ay
```

A strict `<` in those four comparisons would reject a shared edge and force one empty cell. Both the API and the town map use `<=`.

| Place | Behavior on `48bae947` |
| --- | --- |
| `backend_v2.py` `_BUILDING_FOOTPRINT` (about line 1645) and `_footprint` (1660) | Every catalog name is size 2. Unknown names are 2. There is no per-row size column on `building_defs`. |
| `GET /api/building-defs` (`list_building_defs`, 3429) | Each def includes `footprint: 2`. The map reads that (`footprintOf` in `town-four-scene.js`). A missing key would also fall back to 2. |
| `_footprints_overlap` (1793) | Half-open. `(0,0)` size 2 and `(2,0)` size 2 do not overlap. `(1,0)` does. |
| `_placement_blocked` (1799) | Place, move, unstore, and auto-pick all use it. `stored=1` rows do not occupy. The moving/unstore row is excluded, so a building can slide onto its own old cells. |
| `place_building` (3452), `move_building` (3555), `unstored_building` (3601) | Same blocked result. Omitting `cell_x` and `cell_y` on a new build uses `_first_legal_cell`, which scans row-major and accepts the touching origin. |
| `town-four-scene.js` `footprintsOverlap` (472) and `footprintFree` (496) | Same half-open test. Scene 2 gold (`is-empty-hot`) is exactly the origins where `footprintFree` is true. |
| `occAt` (380) | Sprite and “this cell has a building” match the origin cell only. |
| `coveredAt` (481) | The whole footprint. Used when scene 2 has not chosen a building yet. |

A 2×2 at `(0,0)` occupies `(0,0)`, `(1,0)`, `(0,1)`, `(1,1)`. The next building at `(2,0)` occupies `(2,0)`, `(3,0)`, `(2,1)`, `(3,1)`. Those squares share the boundary between column 1 and column 2. There is no empty cell between the footprints. `(1,0)` is area overlap, not “adjacent”.

East pack `(0,0) (2,0) (4,0) (6,0)` and south pack `(0,0) (0,2) (0,4) (0,6)` both place. West, north, a partial edge `(2,1)`, and a corner-only touch `(2,2)` also place. With a gym already at `(0,0)`, a hospital posted with no coordinates lands on `(2,0)`, not `(3,0)`.

## Why it can still look like a forced gap

The collision rule does not insert a gap. The picture and the labels do.

Measured on the live map at 1280×720 (`--s: 0.85`) with 健身室 at `(0,0)`, `TC-FE-BUILD-ADJACENT-02`:

| Piece | Box |
| --- | --- |
| Origin pad `(0,0)` | x 572–708, y 149.5–283.8 (136×134.3) |
| Sprite on that pad only | x 572–708, y 164.8–283.8 (136×119). Art is `viewBox="0 0 240 210"`, CSS `width: 100%` of the one pad, `aspect-ratio: 240 / 210`. |
| Cell `(1,0)`, the second column of the 2×2 | pad x 643.4–779.4. The sprite covers about 65×92 px of that pad. |
| Cell `(2,0)`, the legal touching origin | pad starts at x 714.8. The sprite ends at x 708, so it misses this pad by about 7 px. |
| Contact shadow | x 502.3–723.3 (221×95). It overlaps the legal neighbor’s pad by about 9 px. `z-index` 2, under the gold mark (`z-index` 3), so it does not hide the gold filter. |

Scene 1 accessible names:

- `(0,0)` 「第 1 欄第 1 行，健身室」
- `(1,0)` 「第 2 欄第 1 行，空地」 — this cell is inside the footprint
- `(2,0)` 「第 3 欄第 1 行，空地」

After 醫院 is placed on `(2,0)`, `(1,0)` is still 「空地」. The two names have a blank cell between them. That blank cell is the second column of the first 2×2, not an empty cell the rules demanded.

Scene 2, before and after 醫院 is chosen: `(2,0)` is gold (`is-empty-hot` plus the gold `drop-shadow`). `(0,0)` and `(1,0)` are not. The click target is the iso cell (`cellAt`), not a footprint-sized hitbox. The 44×44 `.cell-btn` is the focus control; the test’s click on 「第 3 欄第 1 行」 placed the hospital. The hotzone is not inflated.

Scene 3 contradicts itself on the overlap cell. With the preview on `(2,0)`, `(1,0)` is labeled 「第 2 欄第 1 行，可以放置，點選即可移到此格」 because `occAt` is origin-only and every other cell becomes kind `valid`. The click still rejects it. The gold mark is not drawn for kind `valid` (`showMark` is only empty, chosen, and preview).

The dormant legacy canvas (`index.html` `renderTownBuildings`) marks an exact 2×2 and then draws the image at `scale = 1.5` (“slightly larger than 2×2”), which is a 3-cell picture. `#townCanvas` is `display: none`. Players on `#townMap` do not see that overlay.

Hypothesis, not a requested code change: players try to put the next origin on the blank-looking cell beside the picture (`+1`). That cell is area overlap, so the game refuses it. The next gold cell is `+2`, one picture-width further. It feels like a required gap. The footprints are already touching. A collision change that accepted `+1` would allow real overlap. A visual change, if one is wanted later, would paint or label the whole 2×2 and would stop calling those cells empty or placeable. This round does not do that.

## Toasts and API bodies

Blocked area overlap, API (`place`, `move`, `unstore`):

- HTTP 400
- body exactly `{"error": "該位置已被建築物佔用"}`
- no gold or material change
- move and unstore leave the row as it was

Shared edge, API:

- new build HTTP 201, building row JSON includes `cell_x` and `cell_y`, no `error`. `stored=0`. Catalog price charged once.
- move HTTP 200, body exactly `{"ok": true, "cell_x": <x>, "cell_y": <y>}`. Level kept. No charge.
- unstore HTTP 200, building row includes the new cell and `level`. `stored=0`. No charge.
- omitted coordinates HTTP 201 at the touching origin `(2,0)` when `(0,0)` is taken.

Map toasts. Info toasts use class `info` (not `error`), background `rgb(107, 79, 42)`, text `rgb(255, 248, 231)` (`#toast.info` is `#6b4f2a` / `#fff8e7`).

| When | Toast |
| --- | --- |
| Scene 2, no building chosen, click a cell inside an existing footprint (`coveredAt`), including the non-origin cell `(1,0)` | 「這個位置已經有建築物。」 `info` |
| Scene 2, building chosen, click the origin | 「這個位置已經有建築物。」 `info` |
| Scene 2, building chosen, click a non-origin overlap such as `(1,0)` (`occAt` misses it, `footprintFree` is false) | 「這個位置放不下這座建築物。」 `info` |
| Scene 3, click the origin | 「這裏已有「健身室」，不能放置。」 `info` |
| Scene 3, click a non-origin overlap | 「這個位置放不下這座建築物。」 `info` |
| API returns 「該位置已被建築物佔用」 or 「已被裝飾佔用」 or 「位置超出…」 during confirm (`showUnfit`) | 「這個位置放不下這座建築物。」 `info`. The API sentence is not shown. |
| New build confirm on a touching cell | 「起好「醫院」。」 No `info` or `error` class. Background `rgb(21, 128, 61)` (`#15803d`). |
| Unstore confirm | 「已放好「…」。」 Same default toast, not `info`. |
| No legal origin | 「城鎮沒有空位，請先收起或移動其他建築。」 `info` |

「放不下」 on a cell the map just called 「空地」 or 「可以放置」 is the sentence players hear when they try to close the visual gap.

## Cases

API and the map formula: `tests/test_building_adjacent_footprint.py`.

Scene 2 / scene 3: `tests/test_building_adjacent_e2e.py` (`TC-FE-BUILD-ADJACENT-02`). It logs in through the guild-hall control 「進入小鎮」 (`#form-kid`), not the old 「🚪 登入」 button.

Results: [`BUILDING_ADJACENT_FOOTPRINT_STATUS.md`](BUILDING_ADJACENT_FOOTPRINT_STATUS.md).

| ID | Lock |
| --- | --- |
| TC-API-BUILD-ADJACENT-01 | `_footprints_overlap` and `_placement_blocked` allow a shared edge (including 1×1 and mixed sizes) and reject area overlap. Catalog and `GET /api/building-defs` footprint is 2. Overlap message is 「該位置已被建築物佔用」, status 400. |
| TC-API-BUILD-ADJACENT-02 | `POST /buildings` east pack, south pack, west, north, partial edge, and corner. HTTP 201, `stored=0`, catalog price once. Neighbors in the pack share an edge and do not overlap. |
| TC-API-BUILD-ADJACENT-03 | `POST /buildings` at `(1,0)`, `(0,1)`, `(1,1)` against a 2×2 at `(0,0)`. HTTP 400, body exactly `{"error": "該位置已被建築物佔用"}`, no charge, no new row. |
| TC-API-BUILD-ADJACENT-04 | `POST .../move` to a shared edge is HTTP 200 `{"ok": true, "cell_x", "cell_y"}`. Overlap is HTTP 400 with that same body and the row stays. A lone building may slide to `(1,0)` (it is excluded from its own check). |
| TC-API-BUILD-ADJACENT-05 | `POST .../unstored` to `(2,0)` or `(0,2)` is HTTP 200, level kept, no charge. `(1,0)` is HTTP 400 with the occupied body; the row stays `stored=1` at `(20,12)`. |
| TC-API-BUILD-ADJACENT-06 | `POST /buildings` with only `def_id` picks `(2,0)` next to a building at `(0,0)`, not `(3,0)`. |
| TC-FE-BUILD-ADJACENT-01 | The `footprintsOverlap` function in `town-four-scene.js` matches the backend matrix (`<=`, not `<`). The toast sentences above are present in that file. `showUnfit` matches the substring 「已被建築物佔用」. |
| TC-FE-BUILD-ADJACENT-02 | On `#townMap`, `(2,0)` is gold and `(1,0)` is not. Toasts match the table. Confirming `(2,0)` is HTTP 201, 「起好「醫院」。」, and both rows stay `stored=0` on a shared edge. |
