-- Monster definitions for Battle MVP
CREATE TABLE IF NOT EXISTS monsters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    icon        TEXT NOT NULL,
    hp          INTEGER NOT NULL,
    atk         INTEGER NOT NULL,
    def         INTEGER NOT NULL,
    region_id   INTEGER NOT NULL,
    gold_reward INTEGER DEFAULT 20,
    mat_reward  TEXT DEFAULT '{}',  -- JSON: {"wood":2,"brick":1}
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Seed 3 region bosses
INSERT OR IGNORE INTO monsters (id, name, icon, hp, atk, def, region_id, gold_reward, mat_reward) VALUES
(1, '野狼', '🐺', 30, 5, 0, 1, 20, '{"wood":2,"leather":1}'),
(2, '白熊', '🐻‍❄️', 60, 10, 2, 2, 40, '{"fur":1,"brick":2}'),
(3, '巨蠍', '🦂', 100, 15, 5, 3, 80, '{"gear":1,"gem":1}');
