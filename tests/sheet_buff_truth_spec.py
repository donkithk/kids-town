"""#sheetBuff copy for the locked building effects.

Test harness only. Product code must not import this module.
Shop discount and farm gold still come from buff_vals[level-1].
Passives are +2 per level (arena speed +1). Hospital, lighthouse, and
bank describe their skill. Any other buff_type is 「未開放」 with no number.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO / "backend_v2.py"

# Types whose buff_vals the backend applies. Kept in sync by
# test_sheet_buff_truth_consumed_types_match_get_building_buff.
# get_building_buff callers that must remain. task_bonus is no longer one of them.
CONSUMED_EFFECT_TYPES = frozenset({"discount", "daily_gold"})

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


def passive_points(level: int) -> int:
    """+2 of the building's ability per placed level."""
    return 2 * int(level)


def sheet_effect_label(name: str, level: int, buff_type: str, value) -> str:
    """#sheetBuff text that equals the locked effect.

    Passives use level * 2 (arena speed is level * 1), not the old buff_vals curve.
    Shop and farm still use buff_vals[level-1]. Unknown types stay 「未開放」.
    """
    level = int(level or 1)
    if name == "圖書館":
        return f"知識 +{passive_points(level)}"
    if name == "健身室":
        return f"臂力 +{passive_points(level)}"
    if name == "工坊":
        return f"創意 +{passive_points(level)}"
    if name == "競技場":
        return f"臂力 +{passive_points(level)}、速度 +{level}"
    if name == "探險公會":
        return f"勇氣 +{passive_points(level)}"
    if name == "天文台":
        # 10 percentage points per level. Same numbers as explore_treasure_chance.
        return f"尋寶機率 +{10 * level}%"
    if name == "醫院":
        return "技能：繃帶（小回復）"
    if name == "燈塔":
        return "技能：強光（魔法攻擊，敵人命中率下降 2 回合）"
    if name == "銀行":
        return "技能：金錢砸（每次 10 金幣，傷害約普攻 3 倍）"
    if name == "商店" or buff_type == "discount":
        fold = discount_fold(value)
        if not fold:
            raise AssertionError(
                f"discount buff_vals value {value!r} has no 起屋／升級 fold"
            )
        return f"起屋／升級金幣{fold}"
    if name == "農場" or buff_type == "daily_gold":
        return f"每日金幣 +{format_buff_number(value)}"
    return UNAVAILABLE_LABEL


def honest_buff_label(
    buff_type: str,
    value,
    consumed: set[str] | None = None,
    name: str | None = None,
    level: int | None = None,
) -> str:
    """Panel text for this placed building. `consumed` is ignored; kept for callers."""
    del consumed
    if name:
        return sheet_effect_label(name, level or 1, buff_type, value)
    if buff_type == "discount":
        return sheet_effect_label("商店", level or 1, buff_type, value)
    if buff_type == "daily_gold":
        return sheet_effect_label("農場", level or 1, buff_type, value)
    if buff_type == "task_bonus":
        return sheet_effect_label("圖書館", level or 1, buff_type, value)
    return UNAVAILABLE_LABEL


def effect_line_matches(
    buff_type: str,
    value,
    text: str,
    consumed: set[str] | None = None,
    name: str | None = None,
    level: int | None = None,
) -> bool:
    """True when #sheetBuff equals the honest label.

    Farm gold may keep a trailing 🪙. The coin mark is the real currency.
    The claim control is a separate assert.
    """
    expected = honest_buff_label(buff_type, value, consumed, name=name, level=level)
    raw = (text or "").strip()
    if expected.startswith("每日金幣"):
        return raw in (expected, expected + "🪙")
    return raw == expected


def dishonest_fragments(buff_type: str, name: str | None = None) -> tuple[str, ...]:
    """Copy that describes an effect this building does not have."""
    by_name = {
        "圖書館": ("⭐", "星", "任務多星", "任務多經驗"),
        "商店": ("購物折扣", "獎勵"),
        "健身室": ("漏打卡都唔斷", "連續保護"),
        "工坊": ("建築速度",),
        "醫院": ("探險回復",),
        "燈塔": ("探險範圍",),
        "競技場": ("探險金幣",),
        "天文台": ("發現新區域", "知識"),
        "銀行": ("帳本", "帳簿"),
    }
    if name in by_name:
        return by_name[name]
    if buff_type == "discount":
        return by_name["商店"]
    if buff_type == "daily_gold":
        return ()
    if name in ("農場",):
        return ()
    return FORBIDDEN_UNWIRED_SNIPPETS
