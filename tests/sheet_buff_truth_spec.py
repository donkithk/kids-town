"""Honest #sheetBuff copy, anchored to backend_v2 consumers.

Test harness only. Product code must not import this module.
The consumed set is whatever backend_v2.py actually passes to
get_building_buff. Labels for every other buff_type are 「未開放」.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO / "backend_v2.py"

# Types whose buff_vals the backend applies. Kept in sync by
# test_sheet_buff_truth_consumed_types_match_get_building_buff.
CONSUMED_EFFECT_TYPES = frozenset({"task_bonus", "discount", "daily_gold"})

UNWIRED_BUFF_TYPES = frozenset(
    {
        "streak_protect",
        "build_speed",
        "expedition_recovery",
        "unlock_explore",
        "explore_range",
        "expedition_gold",
        "discovery_rate",
    }
)

# name, level, buff_type. Level picks the value the lying panel currently shows.
PANEL_BUILDINGS = (
    {"name": "圖書館", "level": 1, "buff_type": "task_bonus"},
    {"name": "商店", "level": 1, "buff_type": "discount"},
    {"name": "農場", "level": 1, "buff_type": "daily_gold"},
    {"name": "健身室", "level": 1, "buff_type": "streak_protect"},
    {"name": "醫院", "level": 1, "buff_type": "expedition_recovery"},
    {"name": "探險公會", "level": 1, "buff_type": "unlock_explore"},
    {"name": "工坊", "level": 3, "buff_type": "build_speed"},
    {"name": "燈塔", "level": 1, "buff_type": "explore_range"},
    {"name": "競技場", "level": 1, "buff_type": "expedition_gold"},
    {"name": "天文台", "level": 1, "buff_type": "discovery_rate"},
)

DISCOUNT_FOLDS = (
    (0.9, "九折"),
    (0.85, "八五折"),
    (0.8, "八折"),
    (0.75, "七五折"),
    (0.7, "七折"),
)

UNAVAILABLE_LABEL = "未開放"
FARM_CLAIM_LABEL = "領取"
FARM_CLAIMED_LABEL = "今日已領"

# Strings the old ZH lock required, which describe effects the backend does not apply.
FORBIDDEN_UNWIRED_SNIPPETS = ("漏打卡都唔斷",)
BUILD_SPEED_LIE_RE = re.compile(r"建築速度\s*[×xX✕＊*]")
_GET_BUFF_RE = re.compile(
    r"get_building_buff\(\s*[^,\n]+,\s*['\"]([a-z_]+)['\"]"
)


def backend_source() -> str:
    return BACKEND_PATH.read_text(encoding="utf-8")


def consumed_buff_types_in_backend(source: str | None = None) -> set[str]:
    """buff_type string literals passed to get_building_buff (not the def)."""
    text = backend_source() if source is None else source
    return set(_GET_BUFF_RE.findall(text))


def format_buff_number(value) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return format(value, "g")


def discount_fold(value) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    for factor, fold in DISCOUNT_FOLDS:
        if abs(number - factor) < 1e-9:
            return fold
    return None


def honest_buff_label(buff_type: str, value, consumed: set[str] | None = None) -> str:
    """Panel text that matches the real effect of this buff_type.

    Unconsumed types (no get_building_buff caller) are 「未開放」 with no magnitude.
    """
    applied = CONSUMED_EFFECT_TYPES if consumed is None else consumed
    if buff_type not in applied:
        return UNAVAILABLE_LABEL
    if buff_type == "task_bonus":
        return f"任務多經驗 +{format_buff_number(value)}"
    if buff_type == "daily_gold":
        return f"每日金幣 +{format_buff_number(value)}"
    if buff_type == "discount":
        fold = discount_fold(value)
        if not fold:
            raise AssertionError(
                f"discount buff_vals value {value!r} has no 起屋／升級 fold"
            )
        return f"起屋／升級金幣{fold}"
    raise AssertionError(f"no honest label for consumed buff_type {buff_type!r}")


def effect_line_matches(buff_type: str, value, text: str, consumed: set[str] | None = None) -> bool:
    """True when #sheetBuff equals the honest label.

    Farm gold may keep a trailing 🪙. The coin mark is the real currency.
    The claim control is a separate assert.
    """
    expected = honest_buff_label(buff_type, value, consumed)
    raw = (text or "").strip()
    if buff_type == "daily_gold" and buff_type in (consumed or CONSUMED_EFFECT_TYPES):
        return raw in (expected, expected + "🪙")
    return raw == expected


def dishonest_fragments(buff_type: str) -> tuple[str, ...]:
    """Copy that describes an effect the backend does not implement."""
    if buff_type == "task_bonus":
        return ("⭐", "星", "任務多星")
    if buff_type == "discount":
        # 「購物折扣」 sounds like reward shopping. Seed effect is 「獎勵 -10%」.
        return ("購物折扣", "獎勵")
    if buff_type not in CONSUMED_EFFECT_TYPES:
        return FORBIDDEN_UNWIRED_SNIPPETS
    return ()
