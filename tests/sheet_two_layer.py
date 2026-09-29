"""Two-number building sheet: ability points and the converted battle stat.

Test harness only. Product code must not import this module.

The words and the percent sign come from ``docs/ui-mocks/STAT_GLOSSARY.md``.
Nothing here hard-codes 攻擊力, 魔法力, 爆擊率, 閃避率, or 防禦力. The ability
+N is the ``calc_ability_buffs`` difference with the placed building versus
without it. The bracketed +M is the ``calc_battle_stats`` difference on the
glossary-mapped key. A ``stored=1`` copy must not change either function.

When the glossary says a zero battle diff omits the bracket, the line is only
``能力 +N``.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import backend_v2 as b
from tests.factories import connect_db

REPO = Path(__file__).resolve().parents[1]
GLOSSARY_PATH = REPO / "docs" / "ui-mocks" / "STAT_GLOSSARY.md"

# Placed passives whose sheet is two numbers. Observatory is not one of them.
TWO_LAYER_BUILDINGS = ("圖書館", "健身室", "工坊", "競技場", "探險公會")

_UNITS = ("整數", "百分比")
_ABILITY_KEYS = ("str", "int", "spd", "crt", "brv")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
_STATS_KEY_RE = re.compile(r"calc_battle_stats\s*鍵\s*([A-Za-z_][A-Za-z0-9_]*)")
_NOT_STATS_RE = re.compile(r"唔係\s*calc_battle_stats\s*鍵")
_MAP_RE = re.compile(
    r"^\|\s*(\S+)\s+(str|int|spd|crt|brv)\s*"
    r"\|\s*(\S+)\s+(player_[A-Za-z0-9_]+)\s*\|",
    re.M,
)
_CHUNK_RE = re.compile(
    r"(?P<ability>\S+?)\s+\+(?P<n>[0-9]+(?:\.[0-9])?)"
    r"(?:（(?P<label>\S+?)\s+\+(?P<m>[0-9]+(?:\.[0-9])?)(?P<pct>%)?）)?"
)
_BANNED_SHEET = ("魔力", "爆擊傷害", "player_crit_dmg", "crit_dmg", "倍率")


def glossary_text() -> str:
    if not GLOSSARY_PATH.is_file():
        raise AssertionError(f"missing stat glossary {GLOSSARY_PATH}")
    return GLOSSARY_PATH.read_text(encoding="utf-8")


def _section(text: str, title: str) -> str:
    marks = list(_HEADING_RE.finditer(text))
    for index, mark in enumerate(marks):
        if mark.group(1).strip() != title:
            continue
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        return text[mark.end() : end]
    raise AssertionError(f"STAT_GLOSSARY.md has no ## {title}")


def _is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _table_rows(section: str) -> list[dict]:
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0] == "欄位" or _is_separator(cells):
            continue
        unit = cells[2]
        if unit not in _UNITS:
            raise AssertionError(
                f"glossary unit {unit!r} for {cells[0]!r} is not 整數 or 百分比"
            )
        rows.append(
            {
                "field": cells[0],
                "zh": cells[1],
                "unit": unit,
                "note": cells[3],
            }
        )
    if not rows:
        raise AssertionError("glossary table has no data rows")
    return rows


def battle_stat_key(row: dict) -> str | None:
    """Short ``calc_battle_stats`` key named in the note, if this row has one."""
    if _NOT_STATS_RE.search(row["note"]):
        return None
    match = _STATS_KEY_RE.search(row["note"])
    if not match:
        return None
    return match.group(1)


def load_glossary() -> dict:
    """Parse the two glossary tables and the ability-to-battle mapping."""
    text = glossary_text()
    abilities = {row["field"]: row for row in _table_rows(_section(text, "能力層"))}
    battles = {row["field"]: row for row in _table_rows(_section(text, "戰鬥數值層"))}
    missing = [key for key in _ABILITY_KEYS if key not in abilities]
    if missing:
        raise AssertionError(f"能力層 is missing {missing}")
    bindings = []
    seen = set()
    for match in _MAP_RE.finditer(_section(text, "顯示規則")):
        ability_zh, ability, battle_zh, player_field = match.groups()
        if ability in seen:
            raise AssertionError(f"顯示規則 lists {ability} twice")
        seen.add(ability)
        if abilities[ability]["zh"] != ability_zh:
            raise AssertionError(
                f"顯示規則 calls {ability} {ability_zh!r}, "
                f"能力層 says {abilities[ability]['zh']!r}"
            )
        battle = battles.get(player_field)
        if battle is None:
            raise AssertionError(f"顯示規則 uses {player_field}, missing from 戰鬥數值層")
        if battle["zh"] != battle_zh:
            raise AssertionError(
                f"顯示規則 calls {player_field} {battle_zh!r}, "
                f"戰鬥數值層 says {battle['zh']!r}"
            )
        stat_key = battle_stat_key(battle)
        if not stat_key:
            raise AssertionError(f"{player_field} has no calc_battle_stats key")
        bindings.append(
            {
                "ability": ability,
                "ability_word": abilities[ability]["zh"],
                "player_field": player_field,
                "label": battle["zh"],
                "unit": battle["unit"],
                "stat_key": stat_key,
            }
        )
    if set(seen) != set(_ABILITY_KEYS):
        raise AssertionError(f"顯示規則 maps {sorted(seen)}, want {list(_ABILITY_KEYS)}")
    return {
        "abilities": abilities,
        "battles": battles,
        "bindings": bindings,
        "omit_zero_bracket": "M 係 0 就唔寫括號" in text,
    }


def sheet_bindings() -> list[dict]:
    return load_glossary()["bindings"]


def battle_stats(kid, buffs):
    """Call ``calc_battle_stats`` the way this build accepts the building.

    When the function takes ``buffs``, pass ``calc_ability_buffs``. When it
    does not, call it with the kid only. The diff then follows the function
    that is actually on this branch.
    """
    if "buffs" in inspect.signature(b.calc_battle_stats).parameters:
        return b.calc_battle_stats(kid, buffs)
    return b.calc_battle_stats(kid)


def fmt_num(value) -> str:
    """At most one decimal place. Integers have no ``.0``."""
    number = float(value)
    nearest = round(number * 10) / 10
    if abs(nearest - round(nearest)) < 1e-9:
        return str(int(round(nearest)))
    return f"{nearest:.1f}"


def abilities_touched(name: str, level: int = 1) -> list[str]:
    """Ability keys ``calc_ability_buffs`` changes for one placed building.

    The fake cursor returns that one row, so this follows the Python in the
    function (including the arena speed add). It does not apply the SQL
    ``stored`` filter; ``stored_building_counts`` covers that on a real DB.
    """

    class _Cursor:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, *_args, **_kwargs):
            return self

        def fetchall(self):
            return self._rows

    with_rows = b.calc_ability_buffs(
        _Cursor([{"name": name, "level": int(level)}]), 1
    )
    without = b.calc_ability_buffs(_Cursor([]), 1)
    return [key for key in with_rows if with_rows[key] != without[key]]


def _diff_maps(db_path, kid_id, building_id):
    """Function output with that placed row, then with the row removed.

    The delete is rolled back. Other buildings stay, so the diff is this
    building only.
    """
    db = connect_db(db_path)
    try:
        db.execute("BEGIN IMMEDIATE")
        kid = dict(db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone())
        buffs_with = dict(b.calc_ability_buffs(db, kid_id))
        stats_with = dict(battle_stats(kid, buffs_with))
        db.execute("DELETE FROM buildings WHERE id=?", (building_id,))
        buffs_without = dict(b.calc_ability_buffs(db, kid_id))
        stats_without = dict(battle_stats(kid, buffs_without))
        db.rollback()
    finally:
        db.close()
    return buffs_with, buffs_without, stats_with, stats_without


def placed_row(db_path, kid_id, name):
    db = connect_db(db_path)
    row = db.execute(
        """
        SELECT b.id AS id, b.level AS level, bd.name AS name
        FROM buildings b
        JOIN building_defs bd ON bd.id = b.def_id
        WHERE b.kid_id=? AND bd.name=? AND COALESCE(b.stored, 0)=0
        ORDER BY b.id DESC LIMIT 1
        """,
        (kid_id, name),
    ).fetchone()
    db.close()
    if not row:
        raise AssertionError(f"placed {name} missing for kid {kid_id}")
    return {"id": row["id"], "level": int(row["level"]), "name": row["name"]}


def segments_for(db_path, kid_id, name) -> list[dict]:
    """One segment per ability this placed building changes.

    ``n`` and ``m`` come from the two functions. ``label`` and ``unit`` come
    from the glossary, not from a handwritten word list.
    """
    glossary = load_glossary()
    row = placed_row(db_path, kid_id, name)
    buffs_with, buffs_without, stats_with, stats_without = _diff_maps(
        db_path, kid_id, row["id"]
    )
    by_ability = {item["ability"]: item for item in glossary["bindings"]}
    segments = []
    for key in buffs_with:
        n = float(buffs_with[key]) - float(buffs_without[key])
        if abs(n) < 1e-9:
            continue
        binding = by_ability.get(key)
        if binding is None:
            raise AssertionError(f"glossary has no sheet binding for {key}")
        field = binding["stat_key"]
        if field not in stats_with:
            raise AssertionError(
                f"glossary maps {key} to calc_battle_stats {field}, "
                f"which this build does not return"
            )
        m = float(stats_with[field]) - float(stats_without[field])
        omit = glossary["omit_zero_bracket"] and abs(m) < 1e-9
        segments.append(
            {
                "ability": key,
                "ability_word": binding["ability_word"],
                "n": n,
                "field": field,
                "stat_key": field,
                "player_field": binding["player_field"],
                "label": binding["label"],
                "unit": binding["unit"],
                "m": m,
                "omit_bracket": omit,
            }
        )
    return segments


def _token(value, unit: str) -> str:
    body = fmt_num(value)
    if unit == "百分比":
        return body + "%"
    return body


def format_segments(segments) -> str:
    parts = []
    for seg in segments:
        ability = f"{seg['ability_word']} +{_token(seg['n'], '整數')}"
        if seg["omit_bracket"]:
            parts.append(ability)
            continue
        parts.append(f"{ability}（{seg['label']} +{_token(seg['m'], seg['unit'])}）")
    return "、".join(parts)


def _bad_decimal(token: str) -> bool:
    if "." not in token:
        return False
    frac = token.split(".", 1)[1]
    return frac == "0" or len(frac) != 1


def parse_segments(text: str) -> list[dict] | None:
    """Parse ``能力 +N`` pieces, with an optional ``（標籤 +M[%]）``."""
    raw = (text or "").strip()
    if not raw:
        return None
    parsed = []
    for chunk in raw.split("、"):
        match = _CHUNK_RE.fullmatch(chunk.strip())
        if not match or _bad_decimal(match.group("n")):
            return None
        if match.group("m") is not None and _bad_decimal(match.group("m")):
            return None
        parsed.append(
            {
                "ability_word": match.group("ability"),
                "n_token": match.group("n"),
                "n": float(match.group("n")),
                "label": match.group("label"),
                "m_token": match.group("m"),
                "m": None if match.group("m") is None else float(match.group("m")),
                "pct": match.group("pct") == "%",
            }
        )
    return parsed


def _numbers_close(got, want) -> bool:
    return abs(float(got) - float(want)) < 1e-9


def line_problems(text, db_path, kid_id, name) -> list[str]:
    """Problems when ``text`` is not the glossary line for this placed building."""
    if name not in TWO_LAYER_BUILDINGS:
        return []
    raw = (text or "").strip()
    problems = [
        f"#sheetBuff contains {banned!r}."
        for banned in _BANNED_SHEET
        if banned in raw
    ]
    segments = segments_for(db_path, kid_id, name)
    if not segments:
        problems.append(
            f"{name} did not change calc_ability_buffs, so there is no ability +N."
        )
        return problems
    sketch = format_segments(segments)
    parsed = parse_segments(raw)
    if parsed is None:
        problems.append(
            f"#sheetBuff is {raw!r}, want {sketch}. "
            "用詞跟 STAT_GLOSSARY.md。兩個數都係函數差。"
        )
        return problems
    if len(parsed) != len(segments):
        problems.append(
            f"#sheetBuff has {len(parsed)} segment(s), want {len(segments)}: {sketch}. "
            f"text={raw!r}."
        )
        return problems
    for got, seg in zip(parsed, segments):
        if got["ability_word"] != seg["ability_word"]:
            problems.append(
                f"ability word is {got['ability_word']!r}, "
                f"glossary says {seg['ability_word']!r}."
            )
        if got["n_token"] != _token(seg["n"], "整數") or not _numbers_close(
            got["n"], seg["n"]
        ):
            problems.append(
                f"{seg['ability_word']} +N is {got['n_token']}, "
                f"calc_ability_buffs diff is {_token(seg['n'], '整數')}."
            )
        if seg["omit_bracket"]:
            if got["label"] is not None:
                problems.append(
                    f"{seg['ability_word']} battle diff is 0, "
                    f"so the glossary omits the bracket. Sheet has "
                    f"（{got['label']} +{got['m_token']}）."
                )
            continue
        want_m = _token(seg["m"], seg["unit"])
        if got["label"] != seg["label"]:
            problems.append(
                f"bracket label is {got['label']!r}, "
                f"glossary {seg['player_field']} says {seg['label']!r}."
            )
        got_m = f"{got['m_token']}{'%' if got['pct'] else ''}"
        if got["m"] is None or got_m != want_m or not _numbers_close(got["m"], seg["m"]):
            problems.append(
                f"{seg['ability_word']} bracket +M is {got_m}, "
                f"calc_battle_stats {seg['stat_key']} diff is {want_m}."
            )
        wants_pct = seg["unit"] == "百分比"
        if got["pct"] != wants_pct:
            problems.append(
                f"{seg['label']} unit is {seg['unit']}, "
                f"{'%' if wants_pct else 'no %'} is required."
            )
    if problems and sketch not in " ".join(problems):
        problems.append(f"want {sketch}.")
    return problems


def stored_building_counts(db_path, kid_id, name, level) -> list[str]:
    """A stored=1 copy must match having no building, for both functions."""
    from tests.factories import building_def_id, insert_building

    db = connect_db(db_path)
    db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
    db.commit()
    kid = dict(db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone())
    absent_buffs = dict(b.calc_ability_buffs(db, kid_id))
    absent_stats = dict(battle_stats(kid, absent_buffs))
    db.close()
    insert_building(
        db_path,
        kid_id,
        building_def_id(db_path, name),
        level=level,
        stored=1,
        cell_x=4,
        cell_y=1,
    )
    db = connect_db(db_path)
    try:
        stored_buffs = dict(b.calc_ability_buffs(db, kid_id))
        stored_stats = dict(battle_stats(kid, stored_buffs))
    finally:
        db.execute("DELETE FROM buildings WHERE kid_id=?", (kid_id,))
        db.commit()
        db.close()
    problems = []
    for key in absent_buffs:
        if stored_buffs.get(key) != absent_buffs.get(key):
            problems.append(
                f"stored=1 {name} Lv.{level} changes calc_ability_buffs {key}: "
                f"{absent_buffs.get(key)} -> {stored_buffs.get(key)}."
            )
    for key, absent in absent_stats.items():
        got = stored_stats.get(key)
        if isinstance(absent, float) or isinstance(got, float):
            same = abs(float(got) - float(absent)) < 1e-9
        else:
            same = got == absent
        if not same:
            problems.append(
                f"stored=1 {name} Lv.{level} changes calc_battle_stats {key}: "
                f"{absent} -> {got}."
            )
    return problems
