"""Shared constants for the skill-menu, formal-copy, and 營養餐 MP tests.

Product code must not import this module. The selector contract lives in
docs/test-cases/SKILL_MENU_AND_TEXT.md (mock 63b81c8).
"""
from __future__ import annotations

# Cast-turn MP restored by 營養餐, after the skill's MP cost is paid.
# Tests must use this name. The number may change later; do not hard-code 5
# at the assertion site.
NUTRITION_MEAL_MP_REGEN = 5

# One list. A description is colloquial if it contains any of these characters.
COLLOQUIAL_CHARS = ("嘅", "咩", "啲", "唔", "冇", "係", "喺", "佢", "嘢", "畈")

# Fresh seed at main 3b0a48a. Order matches skill_defs insert order.
SEEDED_SKILL_NAMES = (
    "蓄力",
    "重擊",
    "連擊",
    "繃帶",
    "急救",
    "全體治療",
    "橫掃",
    "盾擊",
    "必殺",
    "火球",
    "冰凍",
    "偵察",
    "疾風斬",
    "修復",
    "強化",
    "知識的力量",
    "鍛鍊的成果",
    "營養餐",
    "金幣袋",
    "強光",
    "流星雨",
    "金錢砸",
)

# Mock page size. 2 columns × 3 rows.
SKILL_MENU_PAGE_SIZE = 6

# Pinned on main 3b0a48a with crit off and damage variance frozen at 0.
# Level 20, region 1 (monster def 0), 農場 Lv1 + 探險公會 Lv1.
# Balanced: every ability 0, player_atk 5. Skewed: ability_str 20, player_atk 35.
# 營養餐 damage is that physical hit. HoT is 14 HP on each of the next 3 turns.
MEAL_CAST_DAMAGE = {"balanced": 5, "skewed": 35}
MEAL_HOT_PER_TURN = 14
MEAL_HOT_TURNS = 3


def colloquial_hits(text):
    """Characters from COLLOQUIAL_CHARS that appear in text, in list order."""
    raw = text or ""
    return [char for char in COLLOQUIAL_CHARS if char in raw]


def mp_after_nutrition_meal(mp_before, cost, max_mp, regen=NUTRITION_MEAL_MP_REGEN):
    """MP after casting 營養餐: pay the cost, restore regen, never above max."""
    return min(int(max_mp), int(mp_before) - int(cost) + int(regen))
