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

# Selectors from index.html at ee8a3eb. Assertions are sizes and behavior.
SEL_SKILL_PANEL = "#skillPanel"
SEL_SKILL_GRID = "#skillGrid"
SEL_SKILL_CARD = "#skillGrid .skill-card"
SEL_SKILL_NAME = ".skill-name"
SEL_SKILL_DESC = ".skill-desc"
SEL_SKILL_ICON = ".skill-icon"
SEL_SKILL_TITLE = "#skillTitle"
SEL_PAGE_LABEL = "#pageLabel"
SEL_BTN_BACK = "#btnBack"
SEL_BTN_PREV = "#btnPrev"
SEL_BTN_NEXT = "#btnNext"
SEL_BTN_CLOSE = "#btnClose"
SEL_BTN_SKILL = "#btnSkill"
SEL_MP_NOW = "#mpNow"
SEL_PAGE_DOTS = "#pageDots .dot"
SEL_WILD_TOAST = "#wildToast"
SEL_COMMAND_BAR = ".battle-scene .command-bar"
SEL_MONSTER_CARD = ".battle-scene .monster-card"
SEL_M_NAME = ".m-name"
SEL_M_HP_BAR = ".m-hp-bar"
SEL_M_HP_TEXT = ".m-hp-text"
SEL_PLAYER_VITALS = "#playerVitals"

# Skill card type. ee8a3eb paints name 20px, desc 13px, icon 24px in a 28×24 box,
# padding 3px 4px.
SKILL_NAME_MIN_PX = 22
SKILL_DESC_MIN_PX = 15
SKILL_ICON_FONT_MIN_PX = 28
SKILL_ICON_BOX_MIN_PX = 28
SKILL_CARD_PAD_BLOCK_MIN_PX = 6
SKILL_CARD_PAD_INLINE_MIN_PX = 8
SKILL_CARD_MIN_HEIGHT_PX = 72
SKILL_ICON_INSET_MIN_PX = 4
SKILL_DESC_LINE_RATIO = 1.3

# Title row. ee8a3eb paints the title at 22px and the page label at 16px.
# 返回 is min-width 64px under the global border-box rule.
SKILL_TITLE_MIN_PX = 26
PAGE_LABEL_MIN_PX = 20
BTN_BACK_MIN_WIDTH_PX = 80
BTN_BACK_MIN_HEIGHT_PX = 44
TITLE_CONTROL_MIN_PX = 44

# getBoundingClientRect of #skillPanel at 1280×720 on ee8a3eb.
SKILL_PANEL_RECT = {"left": 332.0, "top": 141.0, "right": 980.0, "bottom": 461.0}
SKILL_PANEL_RECT_TOLERANCE_PX = 2

# Battle message. A long line is probed at this width before the live toast is measured.
TOAST_WRAP_WIDTH_PX = 1100
TOAST_LINE_TOLERANCE_PX = 1
TOAST_SHIFT_TOLERANCE_PX = 1
TOAST_SHORT_MESSAGE = "準備"
# 8 characters × 12 = 96. At the 16px toast font this wraps to 2 lines inside 1100px.
TOAST_LONG_MESSAGE = "野狼從草叢撲過來" * 12

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
