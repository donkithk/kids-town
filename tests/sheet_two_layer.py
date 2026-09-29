"""Two-number building sheet: ability points and the converted battle stat.

Test harness only. Product code must not import this module.

The ability +N is the difference in ``calc_ability_buffs`` with the placed
building versus the same kid without that building. The bracketed +M is the
difference in ``calc_battle_stats`` for the converted field of that ability.
Neither number is a handwritten ``2 * level``. A ``stored=1`` copy must not
change either function.

The words in front of +N are the ability names the HUD tooltip already uses
(``TIP_NAMES`` in ``index.html``). The word inside the brackets has to be the
label the battle HUD shows for that converted stat. This module does not
invent that word.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import backend_v2 as b
from tests.factories import connect_db

REPO = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO / "index.html"

# Placed passives whose sheet is two numbers. Observatory is not one of them.
TWO_LAYER_BUILDINGS = ("圖書館", "健身室", "工坊", "競技場", "探險公會")

_TIP_NAMES_RE = re.compile(r"TIP_NAMES\s*=\s*\{([^}]+)\}")
_TIP_PAIR_RE = re.compile(r"(str|int|spd|crt|brv)\s*:\s*'([^']+)'")
_SEGMENT_RE = re.compile(
    r"(?P<ability>\S+?)\s+\+(?P<n>[0-9]+(?:\.[0-9]+)?)"
    r"（(?P<label>\S+?)\s+\+(?P<m>[0-9]+(?:\.[0-9]+)?)）"
)

_ABILITY_COLUMNS = {
    "str": "ability_str",
    "int": "ability_int",
    "spd": "ability_spd",
    "crt": "ability_crt",
    "brv": "ability_brv",
}
# Stats that copy the ability points. A change equal to the bump is the echo,
# not the converted battle stat. ``crt`` is already a conversion (percent).
_ECHO_KEYS = frozenset({"str", "int", "spd", "brv"})


def ability_labels() -> dict[str, str]:
    """Ability words the HUD tooltip renders. Read from index.html."""
    text = INDEX_HTML.read_text(encoding="utf-8")
    block = _TIP_NAMES_RE.search(text)
    if not block:
        raise AssertionError("index.html has no TIP_NAMES ability labels")
    found = dict(_TIP_PAIR_RE.findall(block.group(1)))
    missing = [key for key in _ABILITY_COLUMNS if key not in found]
    if missing:
        raise AssertionError(f"TIP_NAMES is missing {missing}")
    return found


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
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return format(number, "g")


def _zero_kid():
    return {
        "ability_str": 0,
        "ability_int": 0,
        "ability_spd": 0,
        "ability_crt": 0,
        "ability_brv": 0,
        "level": 1,
    }


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


def converted_field(ability: str) -> str:
    """Which ``calc_battle_stats`` key moves when this ability moves.

    Raw echoes (``str`` / ``int`` / ``spd`` / ``brv`` changing by the same
    amount as the points) are not the bracket. ``crit_dmg`` is the second
    creativity conversion; the percent field ``crt`` is the one the battle
    already publishes as ``player_crt``.
    """
    if ability not in _ABILITY_COLUMNS:
        raise AssertionError(f"unknown ability {ability}")
    bump = 4
    base = battle_stats(_zero_kid(), {})
    bumped_kid = _zero_kid()
    bumped_kid[_ABILITY_COLUMNS[ability]] = bump
    bumped = battle_stats(bumped_kid, {})
    changed = []
    for key in base:
        delta = float(bumped[key]) - float(base[key])
        if abs(delta) < 1e-9:
            continue
        if key in _ECHO_KEYS and abs(delta - bump) < 1e-9:
            continue
        changed.append(key)
    if "crt" in changed:
        changed = [key for key in changed if key != "crit_dmg"]
    if len(changed) != 1:
        raise AssertionError(
            f"ability {ability} should convert to one battle stat, saw {changed}"
        )
    return changed[0]


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

    ``n`` and ``m`` come from the two functions. ``field`` is the converted
    battle stat. ``label`` is filled in by the caller from the battle HUD.
    """
    row = placed_row(db_path, kid_id, name)
    buffs_with, buffs_without, stats_with, stats_without = _diff_maps(
        db_path, kid_id, row["id"]
    )
    labels = ability_labels()
    segments = []
    for key in buffs_with:
        n = float(buffs_with[key]) - float(buffs_without[key])
        if abs(n) < 1e-9:
            continue
        field = converted_field(key)
        m = float(stats_with[field]) - float(stats_without[field])
        segments.append(
            {
                "ability": key,
                "ability_word": labels[key],
                "n": n,
                "field": field,
                "m": m,
            }
        )
    return segments


def format_segments(segments, hud_labels) -> str:
    parts = []
    for seg in segments:
        label = hud_labels[seg["field"]]
        parts.append(
            f"{seg['ability_word']} +{fmt_num(seg['n'])}"
            f"（{label} +{fmt_num(seg['m'])}）"
        )
    return "、".join(parts)


def parse_segments(text: str) -> list[dict] | None:
    """Parse ``能力 +N（標籤 +M）`` pieces joined by ``、``.

    Returns None when the line is not that shape. The bracket word is whatever
    the sheet wrote; it is not checked against the HUD here.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    chunks = raw.split("、")
    parsed = []
    for chunk in chunks:
        match = _SEGMENT_RE.fullmatch(chunk.strip())
        if not match:
            return None
        parsed.append(
            {
                "ability_word": match.group("ability"),
                "n": float(match.group("n")),
                "label": match.group("label"),
                "m": float(match.group("m")),
            }
        )
    return parsed


def _numbers_close(got, want) -> bool:
    return abs(float(got) - float(want)) < 1e-9


def line_problems(text, db_path, kid_id, name, hud_labels=None) -> list[str]:
    """Problems when ``text`` is not the two-layer line for this placed building.

    ``hud_labels`` maps a ``calc_battle_stats`` key to the battle HUD's word.
    When it is omitted, the bracket word only has to be present. When it is
    provided, the bracket word must be that HUD word.
    """
    if name not in TWO_LAYER_BUILDINGS:
        return []
    segments = segments_for(db_path, kid_id, name)
    if not segments:
        return [
            f"{name} did not change calc_ability_buffs, so there is no ability +N."
        ]
    sketch = "、".join(
        f"{seg['ability_word']} +{fmt_num(seg['n'])}"
        f"（<{seg['field']} 嘅戰鬥 HUD 標籤> +{fmt_num(seg['m'])}）"
        for seg in segments
    )
    parsed = parse_segments(text)
    problems = []
    if parsed is None:
        problems.append(
            f"#sheetBuff is {(text or '').strip()!r}, want {sketch}. "
            "兩個數都要由 calc_ability_buffs 同 calc_battle_stats 嘅差計出。"
        )
        return problems
    if len(parsed) != len(segments):
        problems.append(
            f"#sheetBuff has {len(parsed)} segment(s), want {len(segments)}: {sketch}. "
            f"text={(text or '').strip()!r}."
        )
        return problems
    for got, seg in zip(parsed, segments):
        if got["ability_word"] != seg["ability_word"]:
            problems.append(
                f"ability word is {got['ability_word']!r}, "
                f"HUD ability label is {seg['ability_word']!r}."
            )
        if not _numbers_close(got["n"], seg["n"]):
            problems.append(
                f"{seg['ability_word']} +N is {fmt_num(got['n'])}, "
                f"calc_ability_buffs diff is {fmt_num(seg['n'])}."
            )
        if not _numbers_close(got["m"], seg["m"]):
            problems.append(
                f"{seg['ability_word']} bracket +M is {fmt_num(got['m'])}, "
                f"calc_battle_stats {seg['field']} diff is {fmt_num(seg['m'])}."
            )
        if hud_labels is not None:
            label = hud_labels.get(seg["field"])
            if not label:
                problems.append(
                    f"battle HUD has no label for {seg['field']} "
                    f"({seg['ability_word']}). Do not invent one. Sheet bracket is "
                    f"{got['label']!r}."
                )
            elif got["label"] != label:
                problems.append(
                    f"bracket label for {seg['field']} is {got['label']!r}, "
                    f"battle HUD says {label!r}. "
                    f"Use 「{seg['ability_word']} +{fmt_num(seg['n'])}"
                    f"（{label} +{fmt_num(seg['m'])}）」."
                )
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


def bump_delta(ability: str, before_stats, after_stats) -> tuple[str, float]:
    """Primary field and how far it moved between two ``calc_battle_stats``."""
    field = converted_field(ability)
    delta = float(after_stats[field]) - float(before_stats[field])
    return field, delta


def label_tracking(before_text, after_text, old_value, new_value) -> list[str]:
    """Labels in the battle HUD whose number moved from old_value to new_value.

    Only words that are already in the HUD text are returned.
    """
    labeled = re.compile(r"([A-Za-z\u4e00-\u9fff]{1,8})\s*([0-9]+(?:\.[0-9]+)?)")

    def collect(text):
        found = {}
        for match in labeled.finditer(text or ""):
            found.setdefault(match.group(1), []).append(float(match.group(2)))
        return found

    before = collect(before_text)
    after = collect(after_text)
    hits = []
    for label, nums in after.items():
        old_nums = before.get(label, [])
        new_hit = any(abs(num - float(new_value)) < 1e-6 for num in nums)
        if not new_hit:
            continue
        if old_nums:
            old_hit = any(abs(num - float(old_value)) < 1e-6 for num in old_nums)
            if old_hit:
                hits.append(label)
        elif abs(float(new_value) - float(old_value)) >= 1e-9:
            # The HUD started showing the stat once it was non-trivial.
            hits.append(label)
    return hits
