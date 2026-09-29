"""TC-API-SHEET-TWO-LAYER: stored buildings must not move the two functions.

The sheet text itself is TC-FE-SHEET-TWO-LAYER. Numbers there are the same
diffs these functions return for a placed row. This file only locks the
stored=1 side, which the sheet cannot show.
"""
from __future__ import annotations

import pytest

from tests.factories import building_def_id, connect_db, insert_building
from tests.sheet_two_layer import (
    TWO_LAYER_BUILDINGS,
    abilities_touched,
    segments_for,
    stored_building_counts,
)


@pytest.mark.case_id("TC-API-SHEET-TWO-LAYER")
def test_stored_passive_does_not_change_ability_or_battle_stats(family, test_db):
    """stored=1 圖書館／健身室／工坊／競技場／探險公會唔計入兩個函數。

    擺出嚟嘅同一座要令 calc_ability_buffs 有差。差幾多由函數自己計，唔寫死。
    """
    kid_id = family.kid_a.id
    db = connect_db(test_db)
    db.execute(
        """
        UPDATE kids
           SET ability_str=0, ability_int=0, ability_spd=0,
               ability_crt=0, ability_brv=0
         WHERE id=?
        """,
        (kid_id,),
    )
    db.commit()
    db.close()

    problems = []
    for name in TWO_LAYER_BUILDINGS:
        for level in (1, 3):
            problems.extend(stored_building_counts(test_db, kid_id, name, level))
            insert_building(
                test_db,
                kid_id,
                building_def_id(test_db, name),
                level=level,
                stored=0,
                cell_x=0,
                cell_y=0,
            )
            touched = abilities_touched(name, level)
            segments = segments_for(test_db, kid_id, name)
            got = [seg["ability"] for seg in segments]
            if got != touched:
                problems.append(
                    f"{name} Lv.{level} abilities {got} != calc_ability_buffs {touched}."
                )
            db = connect_db(test_db)
            db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
            db.commit()
            db.close()
    assert not problems, problems
