# Kids Town Economy Analysis
## Source files: `backend_v2.py` (v2.1) and `backend.py` (v1)
## Extracted: 2026-06-06

---

## 1. CURRENCY TYPES

| Currency | Type | Table/Field | Detail |
|----------|------|-------------|--------|
| **Points/Coins 🪙** | Primary currency | `kids.points` | Used for building purchase/upgrade; earned via tasks & expeditions. Also called "gold" in UI context. Default 0 at creation. |
| **Wood 🪵** | Crafting material | `inventory.quantity` WHERE `item_type='wood'` | Basic building material |
| **Brick 🧱** | Crafting material | `inventory.quantity` WHERE `item_type='brick'` | Common building material |
| **Iron 🔩** | Crafting material | `inventory.quantity` WHERE `item_type='iron'` | Mid-tier building material |
| **Gem 💎** | Rare material | `inventory.quantity` WHERE `item_type='gem'` | Used in high-tier buildings (lighthouse, arena, observatory) |
| **Star Shard ⭐** | Rare material | `inventory.quantity` WHERE `item_type='star_shard'` | Used only in observatory (top-tier building) |
| **Dragon Scale 🐉** | Special event item | `inventory.quantity` WHERE `item_type='dragon_scale'` | Expedition rare drop (10% chance) |
| **Star Stone ⭐** | Special event item | `inventory.quantity` WHERE `item_type='star_stone'` | Expedition rare drop (8% chance) |
| **Mystery Box 🎁** | Special event item | `inventory.quantity` WHERE `item_type='mystery_box'` | Expedition rare drop (15% chance) |

**Key finding:** There is NO separate XP/leveling system for kids (no `level` or `xp` column on `kids` table). Points serve as both currency and score. Building leveling exists separately (max_level=5).

---

## 2. FAUCETS (How currency is earned)

### 2A. Task Completion
| Parameter | Value | Source |
|-----------|-------|--------|
| Default points per task | **10** | `tasks.points DEFAULT 10` (configurable per task) |
| Configurable range | Any integer | Set by parent when creating/editing task |
| Points from task awarded | Task's `points` value added to `kids.points` | `complete_task()` |

### 2B. Expeditions
| Parameter | Value | Source |
|-----------|-------|--------|
| Default duration | **2 hours** | `duration_hours = int(data.get('duration_hours', 2))` |
| Gold reward range | **10-30 × region_id** | `random.randint(10, 30) * (exp['region_id'] or 1)` |
| Material drop rate | **60%** per material type | `if random.random() < 0.6` |
| Material quantity | **1-5** per rolled material | `random.randint(1, 5)` |
| Dragon Scale chance | **10%** | `if random.random() < 0.1` |
| Star Stone chance | **8%** | `if random.random() < 0.08` |
| Mystery Box chance | **15%** | `if random.random() < 0.15` |

### 2C. Building Passive Income (Farm)
| Building Level | Daily Gold 🪙 |
|---------------|---------------|
| Lv.1 | +5 |
| Lv.2 | +10 |
| Lv.3 | +15 |
| Lv.4 | +25 |
| Lv.5 | +40 |

*Buff type: `daily_gold`, buff_vals: `[5,10,15,25,40]`*

### 2D. Parent Manual Adjustment
Parents can add or subtract any amount with a reason via the `/api/kids/<id>/points/adjust` endpoint. Points floor is 0 (cannot go negative).

---

## 3. SINKS (How currency is spent)

### 3A. Building Construction Costs
| Building | Icon | Cost (Points) | Materials | Effect | Unlock |
|----------|------|--------------|-----------|--------|--------|
| 📚 Library | 📚 | **100** | 5 wood | Tasks +2⭐ bonus | None |
| 🏋️ Gym | 🏋️ | **200** | 10 wood, 5 brick | Streak protect | None |
| 🌾 Farm | 🌾 | **300** | 15 wood, 10 brick | Daily +5🪙 | None |
| 🔨 Workshop | 🔨 | **350** | 20 wood, 5 iron | Build speed x2 | None |
| 🏥 Hospital | 🏥 | **400** | 15 wood, 20 brick | Expedition recovery x2 | None |
| 🏪 Shop | 🏪 | **500** | 20 wood, 15 brick, 5 iron | -10% discount | None |
| 🗺️ Guild | 🗺️ | **600** | 25 wood, 20 brick, 10 iron | Unlock exploration | None |
| 🗼 Lighthouse | 🗼 | **800** | 30 wood, 25 brick, 15 iron, 3 gem | Expedition range +1 | Region r3 |
| ⚔️ Arena | ⚔️ | **1,000** | 40 wood, 30 brick, 20 iron, 5 gem | Expedition gold x2 | Region r4 |
| 🔭 Observatory | 🔭 | **1,500** | 50 wood, 40 brick, 25 iron, 10 gem, 3 star_shard | Discovery rate 1.5x | Region r5 |

### 3B. Building Upgrade Costs
| Parameter | Formula | Notes |
|-----------|---------|-------|
| Gold cost | `level × 100` | Lv.1→2 costs 100, Lv.2→3 costs 200, etc. |
| Material cost | `base_mats × (level + 1)` | Multiplied per material type |
| Max level | **5** (all buildings) | `max_level INTEGER DEFAULT 5` |
| Upgrade endpoint | `/api/kids/<id>/buildings/<b_id>/upgrade` | POST |

### 3C. Building Buff Values (Per Level)
| Building | Buff Type | Lv.1 | Lv.2 | Lv.3 | Lv.4 | Lv.5 |
|----------|-----------|------|------|------|------|------|
| Library | task_bonus | +2 | +4 | +6 | +10 | +15 |
| Gym | streak_protect | 1 | 1 | 1 | 1 | 1 |
| Farm | daily_gold | +5 | +10 | +15 | +25 | +40 |
| Shop | discount | 0.9x | 0.85x | 0.8x | 0.75x | 0.7x |
| Hospital | expedition_recovery | x2 | x3 | x4 | x5 | x6 |
| Guild | unlock_explore | 1 | 1 | 1 | 1 | 1 |
| Workshop | build_speed | x2 | x3 | x4 | x5 | x6 |
| Lighthouse | explore_range | +1 | +2 | +2 | +3 | +3 |
| Arena | expedition_gold | x2 | x3 | x4 | x5 | x6 |
| Observatory | discovery_rate | 1.5x | 2x | 2.5x | 3x | 4x |

---

## 4. STREAK SYSTEM

| Parameter | Value | Source |
|-----------|-------|--------|
| Streak definition | Consecutive calendar days with ≥1 task completion | `update_streak()` |
| Streak reset | Miss a day (not yesterday → today) → resets to 1 | `if last_active_date != yesterday: new_streak = 1` |
| Streak tracking | `streaks` table: current_streak, best_streak, last_active_date | SQL schema |
| Same-day repeat | Already active today → returns current streak | `if last_active_date == today: return current_streak` |

---

## 5. ACHIEVEMENT SYSTEM (Milestone Rewards)

| Milestone | Badge ID | Icon | Title | Threshold |
|-----------|----------|------|-------|-----------|
| 1st task | first_task | 🌟 | First Task | ≥1 completed |
| 10 tasks | ten_tasks | ⭐ | Task Ace (10) | ≥10 completed |
| 50 tasks | fifty_tasks | 🏆 | Task Master (50) | ≥50 completed |
| 100 tasks | hundred_tasks | 👑 | Task King (100) | ≥100 completed |
| 3-day streak | three_streak | 🔥 | Streak Star | ≥3 days |
| 7-day streak | seven_streak | 🔥 | Streak Pro | ≥7 days |
| 30-day streak | thirty_streak | 💪 | Unbreakable | ≥30 days |
| 1,000 points earned | thousand_points | 💰 | Little Vault | ≥1000 total earned |
| 5,000 points earned | five_k_points | 💎 | Millionaire | ≥5000 total earned |
| 10,000 points earned | ten_k_points | 👑 | Billionaire | ≥10000 total earned |
| All buildings | all_buildings | 🏗️ | Great Architect | All building defs built |
| All regions | all_regions | 🗺️ | Great Explorer | All 5 regions explored |

**Note:** Achievements are checked automatically on task completion via `check_achievements()`. Points achievements look at cumulative *positive* points_log amounts (not current balance).

---

## 6. XP / LEVELING SYSTEM

| Query | Result |
|-------|--------|
| Is there a kid level/XP system? | **NO.** The `kids` table has no `level` or `xp` column. |
| What serves as progression? | **Points total** acts as both score and currency. |
| Building leveling? | **YES.** All buildings level 1-5, upgrade cost = current_level × 100 gold. |
| Is there XP per level table? | **NO.** No XP curves or level thresholds exist anywhere in the codebase. |

---

## 7. ADDITIONAL ECONOMY PARAMETERS

| Parameter | Value | Details |
|-----------|-------|---------|
| Leaderboard cap | Top **50** | `LIMIT 50` on all leaderboard queries |
| Leaderboard periods | all / weekly (7d) / monthly (30d) | `period` query param |
| Activity log limit | **50** entries default | `limit=50` for activity endpoint |
| Stats history max | **365 days** | Calendar heatmap endpoint |
| Points floor | **0** | `new_points = max(0, kid['points'] + amount)` |
| Recurring task reset | Midnight (based on UTC date) | `DATE(completed_at) < today` check |
| Building upgrade cost scaling | Gold: `level × 100` | Linear scaling |
| Building upgrade material scaling | Materials: `base × (level + 1)` | Linear scaling |
| Auth PIN default | `0000` | `kid_auth.pin DEFAULT '0000'` |

---

## 8. DATABASE SCHEMA SUMMARY (Economy-relevant tables)

```sql
-- Primary currency
kids (id, name, avatar, color, points INTEGER DEFAULT 0, created_at)

-- Transaction log
points_log (id, kid_id, amount INTEGER, reason TEXT, created_at)

-- Tasks (configurable reward)
tasks (id, title, icon, points INTEGER DEFAULT 10, kid_id, completed, 
       category, description, recurring, due_date, created_at, completed_at)

-- Buildings (cost + materials)
building_defs (id, name, icon, cost_gold INTEGER DEFAULT 100, materials TEXT DEFAULT '{}',
               effect, buff_type, buff_vals, max_level INTEGER DEFAULT 5, unlock_region)
buildings (id, kid_id, def_id, plot_idx, level INTEGER DEFAULT 1, built_at)

-- Materials inventory
inventory (id, kid_id, item_type TEXT NOT NULL, quantity INTEGER DEFAULT 0)

-- Streaks
streaks (id, kid_id, current_streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0,
         last_active_date TEXT)

-- Achievements
achievements (id, kid_id, badge TEXT, title TEXT, description, earned_at)

-- Expeditions
expeditions (id, kid_id, region_id, start_time, end_time, status DEFAULT 'pending', rewards TEXT)

-- Explored regions
explored_regions (id, kid_id, region_id, completed_at)

-- Auth
kid_auth (id, kid_id, pin TEXT DEFAULT '0000')
```
