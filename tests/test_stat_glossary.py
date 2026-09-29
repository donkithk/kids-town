"""TC-DOC-STAT-GLOSSARY: the stat glossary parses and names real battle keys."""
from __future__ import annotations

import pytest

import backend_v2 as b
from tests.sheet_two_layer import battle_stat_key, load_glossary


@pytest.mark.case_id("TC-DOC-STAT-GLOSSARY")
def test_stat_glossary_parses_and_battle_keys_exist():
    """詞彙表兩張表要解析到，戰鬥層每個鍵都要係 calc_battle_stats 嘅輸出。

    單位只可以係整數或者百分比。備註寫明「唔係 calc_battle_stats 鍵」嘅列
    （而家係 MP）唔使出現喺函數輸出。其餘列嘅「calc_battle_stats 鍵 …」
    同 ``player_`` 後面嗰截都要係函數鍵，避免 ``player_eva`` 呢類錯字。
    ``player_crit_dmg`` 唔好出現喺戰鬥數值層嘅表。
    """
    glossary = load_glossary()
    sample = b.calc_battle_stats(
        {
            "ability_str": 0,
            "ability_int": 0,
            "ability_spd": 0,
            "ability_crt": 0,
            "ability_brv": 0,
            "level": 1,
        }
    )
    problems = []
    if "player_crit_dmg" in glossary["battles"]:
        problems.append("戰鬥數值層 still lists player_crit_dmg")
    for row in list(glossary["abilities"].values()) + list(glossary["battles"].values()):
        if row["unit"] not in ("整數", "百分比"):
            problems.append(f"{row['field']} unit {row['unit']!r}")
    for row in glossary["battles"].values():
        if "唔係" in row["note"] and "calc_battle_stats" in row["note"]:
            continue
        key = battle_stat_key(row)
        if key is None:
            problems.append(f"{row['field']} does not name a calc_battle_stats key")
            continue
        if key not in sample:
            problems.append(
                f"{row['field']} names calc_battle_stats {key!r}, "
                f"which is not in the output {sorted(sample)}"
            )
        if row["field"].startswith("player_"):
            suffix = row["field"][len("player_") :]
            if suffix not in sample:
                problems.append(
                    f"battle-layer key {row['field']} is not in calc_battle_stats "
                    f"(suffix {suffix!r} missing; typo such as player_eva)"
                )
    for binding in glossary["bindings"]:
        if binding["stat_key"] not in sample:
            problems.append(
                f"{binding['ability']} bracket {binding['player_field']} "
                f"maps to missing {binding['stat_key']}"
            )
    assert not problems, problems
