"""Drop system tests — TDD (RED first).

Target behavior from the plan:
  稀有度: common 70% / rare 22% / epic 7% / legendary 1%
  tier scaling: 每 +1 tier, epic +1.5%, legendary +0.3%
  保底 pity: 連續 30 次無 epic → 第 31 次保底 epic 或以上
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backend_v2 as b


def test_roll_drop_returns_valid_rarity():
    for _ in range(100):
        r = b.roll_drop(tier=1, pity_count=0)
        assert r in ('common', 'rare', 'epic', 'legendary')


def test_drop_distribution_matches_weights():
    random.seed(42)
    results = [b.roll_drop(tier=1, pity_count=0) for _ in range(10000)]
    common_ratio = results.count('common') / 10000
    # 基礎 common 70%，容許 ±15%
    assert 0.55 <= common_ratio <= 0.85, f"common ratio = {common_ratio}"


def test_higher_tier_drops_more_rare_plus():
    random.seed(7)
    low = [b.roll_drop(tier=1, pity_count=0) for _ in range(20000)]
    high = [b.roll_drop(tier=30, pity_count=0) for _ in range(20000)]
    def epic_plus(lst):
        return lst.count('epic') + lst.count('legendary')
    # 高 tier 嘅 epic+ 機率應該明顯高過低 tier
    assert epic_plus(high) > epic_plus(low)


def test_pity_at_30_guarantees_epic_or_above():
    for _ in range(50):
        r = b.roll_drop(tier=1, pity_count=30)
        assert r in ('epic', 'legendary'), f"pity=30 應該保底, 得到 {r}"
