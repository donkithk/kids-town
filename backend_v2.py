#!/usr/bin/env python3
"""
Kids Town Backend — SQLite + Flask API
Port 9123
v3.0 — Role-based auth: kids, parents, admins
"""
import os, sqlite3, json, random, re, hashlib
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, g, make_response
from flask_cors import CORS

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kids_town.db')
app = Flask(__name__)
CORS(app)

# ── Database helpers ─────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

app.teardown_appcontext(close_db)

HTML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

@app.route('/kids')
@app.route('/kids/')
def serve_kids_index():
    # Serve main index (check both names, fallback to index.html)
    for fname in ['index_v2.html', 'index.html']:
        path = os.path.join(HTML_DIR, fname)
        if os.path.isfile(path):
            return open(path, encoding='utf-8').read()
    return jsonify({'error': 'index not found'}), 404

@app.route('/kids/<path:filename>')
def serve_kids_static(filename):
    path = os.path.join(HTML_DIR, filename)
    if os.path.isfile(path):
        ext = os.path.splitext(filename)[1]
        mime_map = {
            '.json': 'application/json',
            '.js': 'application/javascript',
            '.svg': 'image/svg+xml',
            '.css': 'text/css',
            '.png': 'image/png',
            '.html': 'text/html',
            '.ico': 'image/x-icon',
        }
        content_type = mime_map.get(ext, 'text/plain')
        
        if ext in ('.png', '.ico'):
            with open(path, 'rb') as f:
                resp = make_response(f.read())
        else:
            with open(path, encoding='utf-8') as f:
                resp = make_response(f.read())
        
        resp.headers['Content-Type'] = content_type
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp
    return jsonify({'error': 'not found'}), 404

@app.route('/')
def serve_root():
    # Root serves dashboard index
    path = os.path.join(DASHBOARD_DIR, 'index.html')
    if os.path.isfile(path):
        return open(path, encoding='utf-8').read()
    return jsonify({'error': 'index not found'}), 404


def migrate_db():
    """Add new columns/tables if they don't exist (safe migration)."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    
    # Add theme column to kids table
    kid_cols = [row[1] for row in db.execute("PRAGMA table_info(kids)").fetchall()]
    if 'theme' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN theme TEXT DEFAULT ''")
    
    # Check tasks table columns
    cols = [row[1] for row in db.execute("PRAGMA table_info(tasks)").fetchall()]
    if 'category' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT ''")
    if 'description' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN description TEXT DEFAULT ''")
    if 'recurring' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN recurring TEXT DEFAULT ''")  # daily/weekly/weekdays
    if 'due_date' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
    
    # Achievements table
    db.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            badge       TEXT    NOT NULL,
            title       TEXT    NOT NULL,
            description TEXT,
            earned_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        )
    """)
    
    # Streak tracking
    db.execute("""
        CREATE TABLE IF NOT EXISTS streaks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL UNIQUE,
            current_streak INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            last_active_date TEXT,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        )
    """)
    
    db.commit()
    db.close()


def init_db():
    """Create tables if they don't exist."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS kids (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            avatar      TEXT    DEFAULT '👦',
            color       TEXT    DEFAULT '#3b82f6',
            points      INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS points_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            amount      INTEGER NOT NULL,
            reason      TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            icon        TEXT    DEFAULT 'star',
            points      INTEGER DEFAULT 10,
            kid_id      INTEGER,
            completed   INTEGER DEFAULT 0,
            category    TEXT    DEFAULT '',
            description TEXT    DEFAULT '',
            recurring   TEXT    DEFAULT '',
            due_date    TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS kid_auth (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL UNIQUE,
            pin         TEXT    DEFAULT '0000',
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS building_defs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            icon        TEXT    DEFAULT '📚',
            cost_gold   INTEGER DEFAULT 100,
            materials   TEXT    DEFAULT '{}',
            effect      TEXT    DEFAULT '',
            buff_type   TEXT,
            buff_vals   TEXT    DEFAULT '[]',
            max_level   INTEGER DEFAULT 5,
            unlock_region TEXT
        );

        CREATE TABLE IF NOT EXISTS buildings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            def_id      INTEGER NOT NULL,
            plot_idx    INTEGER NOT NULL,
            level       INTEGER DEFAULT 1,
            built_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE,
            FOREIGN KEY (def_id) REFERENCES building_defs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            item_type   TEXT    NOT NULL,
            quantity    INTEGER DEFAULT 0,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS expeditions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            region_id   INTEGER NOT NULL,
            expedition_type TEXT DEFAULT 'explore',
            expedition_data TEXT,
            start_time  TIMESTAMP,
            end_time    TIMESTAMP,
            status      TEXT    DEFAULT 'pending',
            rewards     TEXT,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quiz_questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subject     TEXT    NOT NULL,
            question    TEXT    NOT NULL,
            options     TEXT    NOT NULL,
            correct_idx INTEGER NOT NULL,
            points      INTEGER DEFAULT 10
        );

        CREATE TABLE IF NOT EXISTS explored_regions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            region_id   INTEGER NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS achievements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            badge       TEXT    NOT NULL,
            title       TEXT    NOT NULL,
            description TEXT,
            earned_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS streaks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL UNIQUE,
            current_streak INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            last_active_date TEXT,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS savings_goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            title       TEXT    NOT NULL,
            target_coins INTEGER NOT NULL DEFAULT 100,
            saved_coins INTEGER DEFAULT 0,
            icon        TEXT    DEFAULT '🎯',
            color       TEXT    DEFAULT '#f97316',
            completed   INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );
    """)
    db.commit()
    db.close()

    # Migration: add expedition_type column to existing DBs
    try:
        db2 = sqlite3.connect(DB_PATH)
        db2.execute("ALTER TABLE expeditions ADD COLUMN expedition_type TEXT DEFAULT 'explore'")
        db2.commit()
    except sqlite3.OperationalError:
        pass
    try:
        db2.execute("ALTER TABLE expeditions ADD COLUMN expedition_data TEXT")
        db2.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        db2.close()

    # Seed quiz questions if empty
    db3 = sqlite3.connect(DB_PATH)
    if db3.execute("SELECT COUNT(*) FROM quiz_questions").fetchone()[0] == 0:
        questions = [
            ('math', '1 + 1 = ?', '["1","2","3","4"]', 1, 10),
            ('math', '5 x 5 = ?', '["10","15","20","25"]', 3, 10),
            ('math', '100 ÷ 4 = ?', '["15","20","25","30"]', 1, 15),
            ('math', '8 + 12 - 5 = ?', '["10","15","20","25"]', 1, 15),
            ('math', '3 x 7 = ?', '["18","20","21","24"]', 2, 10),
            ('chi', '「學而時習之」下一句係？', '["不亦說乎","不亦樂乎","不亦君子乎","不亦悅乎"]', 0, 15),
            ('chi', '「舉頭望明月」下一句係？', '["低頭思故鄉","低頭思故人","疑是地上霜","靜夜思"]', 0, 15),
            ('chi', '以下邊個係動物？', '["鉛筆","老虎","書包","電腦"]', 1, 10),
            ('eng', 'What colour is the sky?', '["Red","Blue","Green","Yellow"]', 1, 10),
            ('eng', '"Apple" 係咩意思？', '["香蕉","蘋果","橙","提子"]', 1, 10),
            ('eng', 'I ___ a student.', '["am","is","are","be"]', 0, 10),
            ('eng', '反義詞：Hot ≠ ?', '["Warm","Cold","Cool","Mild"]', 1, 15),
            ('science', '地球圍繞邊個轉？', '["月球","太陽","火星","金星"]', 1, 10),
            ('science', '水嘅化學式係？', '["CO2","H2O","NaCl","O2"]', 1, 15),
            ('science', '植物用咩過程製造食物？', '["呼吸作用","光合作用","蒸騰作用","消化作用"]', 1, 15),
        ]
        for q in questions:
            db3.execute("INSERT INTO quiz_questions (subject, question, options, correct_idx, points) VALUES (?,?,?,?,?)", q)
        db3.commit()
    db3.close()


def seed_building_defs():
    """Insert default building definitions if empty."""
    db = sqlite3.connect(DB_PATH)
    if db.execute("SELECT COUNT(*) FROM building_defs").fetchone()[0] > 0:
        db.close()
        return
    defs = [
        ("📚", "圖書館", 100, '{"wood":5}', "任務 +2⭐", "task_bonus", "[2,4,6,10,15]", 5, None),
        ("🏋️", "健身室", 200, '{"wood":10,"brick":5}', "連續保護", "streak_protect", "[1,1,1,1,1]", 5, None),
        ("🌾", "農場", 300, '{"wood":15,"brick":10}', "每日 +5🪙", "daily_gold", "[5,10,15,25,40]", 5, None),
        ("🏪", "商店", 500, '{"wood":20,"brick":15,"iron":5}', "獎勵 -10%", "discount", "[0.9,0.85,0.8,0.75,0.7]", 5, None),
        ("🏥", "醫院", 400, '{"wood":15,"brick":20}', "探險回復 x2", "expedition_recovery", "[2,3,4,5,6]", 5, None),
        ("🗺️", "探險公會", 600, '{"wood":25,"brick":20,"iron":10}', "解鎖探險", "unlock_explore", "[1,1,1,1,1]", 5, None),
        ("🔨", "工坊", 350, '{"wood":20,"iron":5}', "建築速度 x2", "build_speed", "[2,3,4,5,6]", 5, None),
        ("🗼", "燈塔", 800, '{"wood":30,"brick":25,"iron":15,"gem":3}', "探險範圍 +1", "explore_range", "[1,2,2,3,3]", 5, "r3"),
        ("⚔️", "競技場", 1000, '{"wood":40,"brick":30,"iron":20,"gem":5}', "探險金幣 x2", "expedition_gold", "[2,3,4,5,6]", 5, "r4"),
        ("🔭", "天文台", 1500, '{"wood":50,"brick":40,"iron":25,"gem":10,"star_shard":3}', "新區域發現率", "discovery_rate", "[1.5,2,2.5,3,4]", 5, "r5"),
    ]
    for d in defs:
        db.execute(
            "INSERT INTO building_defs (icon, name, cost_gold, materials, effect, buff_type, buff_vals, max_level, unlock_region) VALUES (?,?,?,?,?,?,?,?,?)",
            (d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8])
        )
    db.commit()
    db.close()

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]

# ── Achievements helpers ─────────────────────────────────────────

ACHIEVEMENT_DEFS = {
    'first_task':       ('🌟', '第一次任務', '完成第一個任務！'),
    'ten_tasks':        ('⭐', '任務達人 (10)', '累積完成10個任務'),
    'fifty_tasks':      ('🏆', '任務大師 (50)', '累積完成50個任務'),
    'hundred_tasks':    ('👑', '任務王者 (100)', '累積完成100個任務'),
    'three_streak':     ('🔥', '連擊新星', '連續3天完成任務'),
    'seven_streak':     ('🔥', '連擊高手', '連續7天完成任務'),
    'thirty_streak':    ('💪', '不滅意志', '連續30天完成任務'),
    'thousand_points':  ('💰', '小金庫', '累積獲得1000分'),
    'five_k_points':    ('💎', '大富翁', '累積獲得5000分'),
    'ten_k_points':     ('👑', '億萬富翁', '累積獲得10000分'),
    'all_buildings':    ('🏗️', '偉大建築師', '建造所有建築物'),
    'all_regions':      ('🗺️', '偉大探險家', '探索全部5個區域'),
}

def check_achievements(kid_id, db):
    """Check and award achievements for a kid."""
    if not kid_id:
        return []
    
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return []
    
    existing = set(row['badge'] for row in db.execute("SELECT badge FROM achievements WHERE kid_id=?", (kid_id,)).fetchall())
    new_achievements = []
    
    # Task count achievements
    completed_count = db.execute("SELECT COUNT(*) FROM tasks WHERE kid_id=? AND completed=1", (kid_id,)).fetchone()[0]
    
    checks = {
        'first_task': completed_count >= 1,
        'ten_tasks': completed_count >= 10,
        'fifty_tasks': completed_count >= 50,
        'hundred_tasks': completed_count >= 100,
    }
    
    # Points achievements
    total_earned = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM points_log WHERE kid_id=? AND amount>0", (kid_id,)
    ).fetchone()[0]
    
    point_checks = {
        'thousand_points': total_earned >= 1000,
        'five_k_points': total_earned >= 5000,
        'ten_k_points': total_earned >= 10000,
    }
    checks.update(point_checks)
    
    # Streak achievements
    streak = db.execute("SELECT * FROM streaks WHERE kid_id=?", (kid_id,)).fetchone()
    if streak:
        streak_checks = {
            'three_streak': streak['current_streak'] >= 3,
            'seven_streak': streak['current_streak'] >= 7,
            'thirty_streak': streak['current_streak'] >= 30,
        }
        checks.update(streak_checks)
    
    # Building achievements
    building_count = db.execute("SELECT COUNT(*) FROM buildings WHERE kid_id=?", (kid_id,)).fetchone()[0]
    total_defs = db.execute("SELECT COUNT(*) FROM building_defs").fetchone()[0]
    checks['all_buildings'] = building_count >= total_defs
    
    # Region achievements
    explored = set(row['region_id'] for row in db.execute("SELECT region_id FROM explored_regions WHERE kid_id=?", (kid_id,)).fetchall())
    checks['all_regions'] = len(explored) >= 5
    
    for badge_id, earned in checks.items():
        if earned and badge_id not in existing:
            icon, title, desc = ACHIEVEMENT_DEFS[badge_id]
            db.execute(
                "INSERT INTO achievements (kid_id, badge, title, description) VALUES (?,?,?,?)",
                (kid_id, badge_id, title, desc)  # Store badge_id (not icon) so dedup check works
            )
            new_achievements.append({'badge': badge_id, 'icon': icon, 'title': title, 'description': desc})
    
    if new_achievements:
        db.commit()
    
    return new_achievements


def migrate_db_v3():
    """Add role-based auth tables (parents, admins, parent_kid, etc)."""
    db = sqlite3.connect(DB_PATH)
    
    # Add username to kids table
    cols = [row[1] for row in db.execute("PRAGMA table_info(kids)").fetchall()]
    if 'username' not in cols:
        db.execute("ALTER TABLE kids ADD COLUMN username TEXT")
        # Add unique index (can't use UNIQUE in ALTER TABLE in SQLite)
        try:
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_kids_username ON kids(username)")
        except:
            pass
        kids = db.execute("SELECT id, name FROM kids").fetchall()
        for k in kids:
            # Generate username from name: use first 2 chars + id suffix for Chinese names
            raw = k[1].lower().strip()
            # Try to extract ASCII chars, fallback to 'kid'
            ascii_part = re.sub(r'[^a-zA-Z0-9]', '', raw)[:10]
            if not ascii_part:
                ascii_part = "kid"
            username = ascii_part
            counter = 1
            while db.execute("SELECT id FROM kids WHERE username=? AND id!=?", (username, k[0])).fetchone():
                username = f"{ascii_part}{counter}"
                counter += 1
            db.execute("UPDATE kids SET username=? WHERE id=?", (username, k[0]))
        print(f"✅ Auto-generated usernames for {len(kids)} kids")
    
    # Parents table
    db.execute("""CREATE TABLE IF NOT EXISTS parents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL, email TEXT, name TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    # Parent-Kid many-to-many
    db.execute("""CREATE TABLE IF NOT EXISTS parent_kid (
        id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER NOT NULL,
        kid_id INTEGER NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES parents(id) ON DELETE CASCADE,
        FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE,
        UNIQUE(parent_id, kid_id))""")
    
    # Admins table
    db.execute("""CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL, email TEXT, name TEXT DEFAULT '',
        role TEXT DEFAULT 'super_admin', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    # System config
    db.execute("""CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    # Admin audit log
    db.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER,
        action TEXT NOT NULL, target_type TEXT, target_id INTEGER,
        details TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE SET NULL)""")
    
    # Seed default admin
    if not db.execute("SELECT id FROM admins WHERE username='admin'").fetchone():
        db.execute("INSERT INTO admins (username, password, name, role) VALUES (?, ?, ?, ?)",
                   ("admin", hash_password("admin123"), "系統管理員", "super_admin"))
    
    # Ensure all kids have auth records
    for k in db.execute("SELECT id FROM kids").fetchall():
        if not db.execute("SELECT id FROM kid_auth WHERE kid_id=?", (k[0],)).fetchone():
            db.execute("INSERT INTO kid_auth (kid_id, pin) VALUES (?, '0000')", (k[0],))
    
    db.commit()
    db.close()
    print("✅ migrate_db_v3 done")


def hash_password(password):
    """Simple SHA-256 hash for passwords (upgrade to bcrypt later)."""
    return hashlib.sha256(password.encode()).hexdigest()


def update_streak(kid_id, db):
    """Update daily streak for a kid when a task is completed."""
    if not kid_id:
        return None
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    streak = db.execute("SELECT * FROM streaks WHERE kid_id=?", (kid_id,)).fetchone()
    
    if not streak:
        db.execute(
            "INSERT INTO streaks (kid_id, current_streak, best_streak, last_active_date) VALUES (?,1,1,?)",
            (kid_id, today)
        )
        db.commit()
        return 1
    
    if streak['last_active_date'] == today:
        return streak['current_streak']  # Already marked today
    
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    if streak['last_active_date'] == yesterday:
        new_streak = streak['current_streak'] + 1
        best = max(new_streak, streak['best_streak'])
    else:
        new_streak = 1
        best = streak['best_streak']
    
    db.execute(
        "UPDATE streaks SET current_streak=?, best_streak=?, last_active_date=? WHERE kid_id=?",
        (new_streak, best, today, kid_id)
    )
    db.commit()
    return new_streak


# ── API Endpoints ────────────────────────────────────────────────

# -- Kids --

@app.route('/api/kids', methods=['GET'])
def list_kids():
    db = get_db()
    rows = db.execute("SELECT * FROM kids ORDER BY points DESC, id ASC").fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/kids', methods=['POST'])
def add_kid():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    avatar = data.get('avatar', '👦')
    color = data.get('color', '#3b82f6')
    db = get_db()
    cur = db.execute(
        "INSERT INTO kids (name, avatar, color) VALUES (?, ?, ?)",
        (name, avatar, color)
    )
    db.commit()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(kid)), 201

@app.route('/api/kids/<int:kid_id>', methods=['PATCH'])
def update_kid(kid_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    
    updates = []
    params = []
    for field in ['name', 'avatar', 'color', 'theme']:
        if field in data:
            updates.append(f"{field}=?")
            params.append(data[field])
    
    if updates:
        db.execute(f"UPDATE kids SET {', '.join(updates)} WHERE id=?", params + [kid_id])
        db.commit()
    
    updated = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    return jsonify(row_to_dict(updated))

@app.route('/api/kids/<int:kid_id>', methods=['DELETE'])
def delete_kid(kid_id):
    db = get_db()
    db.execute("DELETE FROM kids WHERE id = ?", (kid_id,))
    db.commit()
    return jsonify({'ok': True}), 200

@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.get_json(silent=True) or {}
    kid_id = data.get('kid_id')
    theme = data.get('theme', '')
    if not kid_id:
        return jsonify({'error': 'kid_id required'}), 400
    db = get_db()
    db.execute("UPDATE kids SET theme=? WHERE id=?", (theme, kid_id))
    db.commit()
    return jsonify({'ok': True}), 200

# -- Points --

@app.route('/api/kids/<int:kid_id>/points', methods=['GET'])
def get_points(kid_id):
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    return jsonify(row_to_dict(kid))

@app.route('/api/kids/<int:kid_id>/points', methods=['POST'])
def add_points(kid_id):
    data = request.get_json(silent=True) or {}
    amount = data.get('amount', 0)
    reason = (data.get('reason') or '').strip()

    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return jsonify({'error': 'amount must be an integer'}), 400

    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404

    new_points = kid['points'] + amount
    db.execute("UPDATE kids SET points = ? WHERE id = ?", (new_points, kid_id))
    db.execute(
        "INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
        (kid_id, amount, reason)
    )
    db.commit()

    updated = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    return jsonify(row_to_dict(updated)), 200

@app.route('/api/kids/<int:kid_id>/points/adjust', methods=['POST'])
def adjust_points(kid_id):
    """Parent adjustment with reason (positive or negative)."""
    data = request.get_json(silent=True) or {}
    amount = data.get('amount', 0)
    reason = (data.get('reason') or '').strip()
    if not reason:
        return jsonify({'error': 'Reason is required'}), 400
    
    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return jsonify({'error': 'amount must be an integer'}), 400

    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404

    new_points = max(0, kid['points'] + amount)
    db.execute("UPDATE kids SET points = ? WHERE id = ?", (new_points, kid_id))
    db.execute(
        "INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
        (kid_id, amount, reason)
    )
    db.commit()

    updated = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    return jsonify(row_to_dict(updated)), 200

# -- Tasks --

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    db = get_db()
    category = request.args.get('category')
    kid_id = request.args.get('kid_id')
    completed = request.args.get('completed')
    search = request.args.get('search')
    
    query = """
        SELECT t.*, k.name AS kid_name, k.avatar AS kid_avatar
        FROM tasks t
        LEFT JOIN kids k ON t.kid_id = k.id
        WHERE 1=1
    """
    params = []
    
    if category:
        query += " AND t.category=?"
        params.append(category)
    if kid_id:
        query += " AND t.kid_id=?"
        params.append(int(kid_id))
    if completed is not None:
        query += " AND t.completed=?"
        params.append(1 if completed in ('1', 'true', 'yes') else 0)
    if search:
        query += " AND t.title LIKE ?"
        params.append(f'%{search}%')
    
    query += " ORDER BY t.created_at DESC"
    
    rows = db.execute(query, params).fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or data.get('name') or '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    icon = data.get('icon', '✅')
    points = int(data.get('points', 10))
    kid_id = data.get('kid_id')
    category = data.get('category', '')
    description = data.get('description', '')
    recurring = data.get('recurring', '')
    due_date = data.get('due_date')

    db = get_db()
    cur = db.execute(
        "INSERT INTO tasks (title, icon, points, kid_id, category, description, recurring, due_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, icon, points, kid_id, category, description, recurring, due_date)
    )
    db.commit()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(task)), 201

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """Edit a task: modify title, icon, points, kid_id, category, description, recurring, due_date."""
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    data = request.get_json(silent=True) or {}
    updates = []
    params = []
    
    for field in ['title', 'icon', 'points', 'kid_id', 'category', 'description', 'recurring', 'due_date']:
        if field in data:
            updates.append(f"{field}=?")
            params.append(data[field])
    
    if updates:
        db.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id=?", params + [task_id])
        db.commit()
    
    updated = db.execute("SELECT t.*, k.name AS kid_name, k.avatar AS kid_avatar FROM tasks t LEFT JOIN kids k ON t.kid_id=k.id WHERE t.id=?", (task_id,)).fetchone()
    return jsonify(row_to_dict(updated))

@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    now = datetime.utcnow().isoformat()
    
    # Debug log
    print(f"[DEBUG] complete_task(id={task_id}): title={task['title']}, kid_id={task['kid_id']}, points={task['points']}, recurring={task['recurring']}, completed_before={task['completed']}", flush=True)
    
    # Handle recurring tasks: mark done, award points, set due_date to tomorrow
    if task['recurring']:
        # Mark as completed
        db.execute("UPDATE tasks SET completed=1, completed_at=? WHERE id=?", (now, task_id))
        
        # Award points
        kid_id = task['kid_id']
        result = {'task': row_to_dict(task), 'points_awarded': 0, 'kid': None}
        if kid_id:
            kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
            if kid:
                new_points = kid['points'] + task['points']
                db.execute("UPDATE kids SET points = ? WHERE id = ?", (new_points, kid_id))
                db.execute(
                    "INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
                    (kid_id, task['points'], f"Completed task: {task['title']}")
                )
                result['points_awarded'] = task['points']
                updated_kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
                result['kid'] = row_to_dict(updated_kid)
        
        # Set due_date to tomorrow so it reappears tomorrow
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
        db.execute("UPDATE tasks SET due_date=? WHERE id=?", (tomorrow, task_id))
        
        # Check streak + achievements
        if kid_id:
            update_streak(kid_id, db)
            new_achs = check_achievements(kid_id, db)
            if new_achs:
                result['achievements'] = new_achs
        
        db.commit()
        result['task'] = row_to_dict(db.execute("SELECT t.*, k.name AS kid_name, k.avatar AS kid_avatar FROM tasks t LEFT JOIN kids k ON t.kid_id=k.id WHERE t.id=?", (task_id,)).fetchone())
        return jsonify(result), 200
    
    # Regular (non-recurring) task
    if task['completed']:
        return jsonify({'error': 'Task already completed'}), 400

    db.execute("UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?", (now, task_id))

    kid_id = task['kid_id']
    result = {'task': row_to_dict(task), 'points_awarded': 0, 'kid': None}
    if kid_id:
        kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
        if kid:
            new_points = kid['points'] + task['points']
            db.execute("UPDATE kids SET points = ? WHERE id = ?", (new_points, kid_id))
            db.execute(
                "INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
                (kid_id, task['points'], f"Completed task: {task['title']}")
            )
            result['points_awarded'] = task['points']
            updated_kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
            result['kid'] = row_to_dict(updated_kid)
            
            # Update streak + check achievements
            new_streak = update_streak(kid_id, db)
            result['streak'] = new_streak
            new_achs = check_achievements(kid_id, db)
            if new_achs:
                result['achievements'] = new_achs

    db.commit()
    result['task'] = row_to_dict(db.execute("SELECT t.*, k.name AS kid_name, k.avatar AS kid_avatar FROM tasks t LEFT JOIN kids k ON t.kid_id=k.id WHERE t.id=?", (task_id,)).fetchone())
    return jsonify(result), 200

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({'ok': True}), 200

@app.route('/api/tasks/refresh-recurring', methods=['POST'])
def refresh_recurring_tasks():
    """Refresh recurring tasks based on recurrence type.
    
    - daily: reset every day
    - weekdays: reset Mon-Fri only
    - weekly: reset on Monday only
    """
    db = get_db()
    now = datetime.utcnow()
    today = now.strftime('%Y-%m-%d')
    weekday = now.weekday()  # 0=Mon, 6=Sun
    refreshed = []

    # Determine which recurring types should refresh today
    active_types = ['daily']
    if weekday < 5:  # Mon-Fri
        active_types.append('weekdays')
    if weekday == 0:  # Monday
        active_types.append('weekly')

    if not active_types:
        return jsonify({'refreshed': [], 'count': 0, 'note': 'no refresh today'}), 200

    placeholders = ','.join('?' for _ in active_types)

    # Reset completed recurring tasks back to pending
    rows = db.execute(
        f"""SELECT * FROM tasks WHERE recurring IN ({placeholders}) AND completed=1 
           AND (completed_at IS NULL OR DATE(completed_at) < ?)""",
        (*active_types, today)
    ).fetchall()

    for task in rows:
        db.execute("UPDATE tasks SET completed=0, due_date=?, completed_at=NULL WHERE id=?", (today, task['id']))
        refreshed.append(task['id'])

    # Handle overdue tasks
    overdue = db.execute(
        f"SELECT * FROM tasks WHERE recurring IN ({placeholders}) AND completed=0 AND due_date IS NOT NULL AND due_date < ?",
        (*active_types, today)
    ).fetchall()
    for task in overdue:
        db.execute("UPDATE tasks SET due_date=? WHERE id=?", (today, task['id']))
        if task['id'] not in refreshed:
            refreshed.append(task['id'])

    db.commit()
    return jsonify({'refreshed': refreshed, 'count': len(refreshed)}), 200

# -- Task Stats --

@app.route('/api/tasks/stats', methods=['GET'])
def task_stats():
    """Return task and activity statistics."""
    db = get_db()
    
    # Overall stats
    total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE completed=1").fetchone()[0]
    pending_tasks = total_tasks - completed_tasks
    completion_rate = round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0
    
    # Per kid stats
    per_kid = db.execute("""
        SELECT 
            k.id, k.name, k.avatar, k.points,
            COUNT(t.id) AS total_tasks,
            SUM(CASE WHEN t.completed=1 THEN 1 ELSE 0 END) AS completed_tasks,
            COALESCE(SUM(CASE WHEN t.completed=1 THEN t.points ELSE 0 END), 0) AS points_from_tasks
        FROM kids k
        LEFT JOIN tasks t ON k.id = t.kid_id
        GROUP BY k.id
        ORDER BY k.points DESC
    """).fetchall()
    
    # Weekly activity (last 7 days)
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    weekly = db.execute("""
        SELECT 
            k.id, k.name, k.avatar,
            COUNT(pl.id) AS actions,
            COALESCE(SUM(pl.amount), 0) AS points_change
        FROM kids k
        LEFT JOIN points_log pl ON k.id = pl.kid_id AND pl.created_at >= ?
        GROUP BY k.id
        ORDER BY points_change DESC
    """, (week_ago,)).fetchall()
    
    # Daily completion for last 14 days
    daily_raw = db.execute("""
        SELECT DATE(completed_at) AS day, COUNT(*) AS cnt
        FROM tasks
        WHERE completed=1 AND completed_at IS NOT NULL
          AND completed_at >= ?
        GROUP BY DATE(completed_at)
        ORDER BY day
    """, ((datetime.utcnow() - timedelta(days=14)).isoformat(),)).fetchall()
    
    daily_chart = []
    for d in daily_raw:
        daily_chart.append({'date': d['day'], 'count': d['cnt']})
    
    # Categories
    categories = db.execute("""
        SELECT category, COUNT(*) AS count,
               SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END) AS completed
        FROM tasks
        WHERE category != ''
        GROUP BY category
        ORDER BY count DESC
    """).fetchall()
    
    # Task templates (most used icons/points combos)
    templates = db.execute("""
        SELECT icon, points, COUNT(*) AS usage_count
        FROM tasks
        GROUP BY icon, points
        ORDER BY usage_count DESC
        LIMIT 10
    """).fetchall()
    
    return jsonify({
        'overall': {
            'total': total_tasks,
            'completed': completed_tasks,
            'pending': pending_tasks,
            'completion_rate': completion_rate,
        },
        'per_kid': rows_to_list(per_kid),
        'weekly_activity': rows_to_list(weekly),
        'daily_chart': daily_chart,
        'categories': rows_to_list(categories),
        'templates': rows_to_list(templates),
    })

# -- Achievements --

@app.route('/api/kids/<int:kid_id>/achievements', methods=['GET'])
def list_achievements(kid_id):
    db = get_db()
    rows = db.execute("SELECT * FROM achievements WHERE kid_id=? ORDER BY earned_at DESC", (kid_id,)).fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/kids/<int:kid_id>/streak', methods=['GET'])
def get_streak(kid_id):
    db = get_db()
    streak = db.execute("SELECT * FROM streaks WHERE kid_id=?", (kid_id,)).fetchone()
    return jsonify(row_to_dict(streak) if streak else {'current_streak': 0, 'best_streak': 0})

@app.route('/api/achievements/all', methods=['GET'])
def all_achievement_defs():
    """Return all possible achievements and their defs."""
    defs_list = []
    for badge_id, (icon, title, desc) in ACHIEVEMENT_DEFS.items():
        defs_list.append({'id': badge_id, 'icon': icon, 'title': title, 'description': desc})
    return jsonify(defs_list)

# -- Leaderboard --

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    db = get_db()
    period = request.args.get('period', 'all')  # all, weekly, monthly
    
    if period == 'weekly':
        since = (datetime.utcnow() - timedelta(days=7)).isoformat()
        rows = db.execute("""
            SELECT k.id, k.name, k.avatar, k.color,
                   COALESCE(SUM(pl.amount), 0) AS points_earned
            FROM kids k
            LEFT JOIN points_log pl ON k.id = pl.kid_id AND pl.created_at >= ? AND pl.amount > 0
            GROUP BY k.id
            ORDER BY points_earned DESC
            LIMIT 50
        """, (since,)).fetchall()
    elif period == 'monthly':
        since = (datetime.utcnow() - timedelta(days=30)).isoformat()
        rows = db.execute("""
            SELECT k.id, k.name, k.avatar, k.color,
                   COALESCE(SUM(pl.amount), 0) AS points_earned
            FROM kids k
            LEFT JOIN points_log pl ON k.id = pl.kid_id AND pl.created_at >= ? AND pl.amount > 0
            GROUP BY k.id
            ORDER BY points_earned DESC
            LIMIT 50
        """, (since,)).fetchall()
    else:
        rows = db.execute("""
            SELECT id, name, avatar, color, points
            FROM kids
            ORDER BY points DESC
            LIMIT 50
        """).fetchall()
    
    return jsonify(rows_to_list(rows))

# -- Activity Log --

@app.route('/api/activity', methods=['GET'])
def list_activity():
    db = get_db()
    kid_id = request.args.get('kid_id')
    limit = request.args.get('limit', 50, type=int)
    if kid_id:
        rows = db.execute("""
            SELECT pl.*, k.name AS kid_name, k.avatar AS kid_avatar
            FROM points_log pl
            JOIN kids k ON pl.kid_id = k.id
            WHERE pl.kid_id = ?
            ORDER BY pl.created_at DESC
            LIMIT ?
        """, (kid_id, limit)).fetchall()
    else:
        rows = db.execute("""
            SELECT pl.*, k.name AS kid_name, k.avatar AS kid_avatar
            FROM points_log pl
            JOIN kids k ON pl.kid_id = k.id
            ORDER BY pl.created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return jsonify(rows_to_list(rows))


# ── Transaction Type Helper ────────────────────────────────────

def classify_tx_type(reason, amount):
    """Derive transaction type from reason and amount.
    
    Returns one of: 'task', 'building', 'expedition', 'adjustment', 'spent'
    """
    if not reason:
        return 'earned' if amount > 0 else 'spent'
    r = reason.lower()
    if amount > 0 and 'completed task' in r:
        return 'task'
    if amount > 0 and 'expedition' in r:
        return 'expedition'
    if amount < 0 and ('built ' in r or 'upgraded' in r):
        return 'building'
    if amount > 0:
        return 'adjustment'
    return 'spent'


# ── Savings Goals ──────────────────────────────────────────

@app.route('/api/savings-goals', methods=['GET'])
def list_savings_goals():
    """List all savings goals for a kid. Active ones first, then completed."""
    kid_id = request.args.get('kid_id', type=int)
    if not kid_id:
        return jsonify({'error': 'kid_id required'}), 400
    db = get_db()
    goals = db.execute(
        "SELECT * FROM savings_goals WHERE kid_id = ? ORDER BY completed ASC, created_at DESC",
        (kid_id,)
    ).fetchall()
    return jsonify(rows_to_list(goals))


@app.route('/api/savings-goals', methods=['POST'])
def create_savings_goal():
    """Create a new savings goal."""
    data = request.get_json()
    kid_id = data.get('kid_id')
    title = data.get('title', '').strip()
    target_coins = data.get('target_coins', 100)
    icon = data.get('icon', '🎯')
    color = data.get('color', '#f97316')

    if not kid_id or not title:
        return jsonify({'error': 'kid_id and title required'}), 400
    if target_coins < 1:
        return jsonify({'error': 'target_coins must be at least 1'}), 400

    db = get_db()
    db.execute(
        "INSERT INTO savings_goals (kid_id, title, target_coins, icon, color) VALUES (?, ?, ?, ?, ?)",
        (kid_id, title, target_coins, icon, color)
    )
    db.commit()
    goal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    return jsonify(row_to_dict(goal)), 201


@app.route('/api/savings-goals/<int:goal_id>', methods=['PUT'])
def update_savings_goal(goal_id):
    """Update goal title, target, icon, or color."""
    db = get_db()
    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404

    data = request.get_json()
    title = data.get('title', goal['title']).strip()
    target_coins = data.get('target_coins', goal['target_coins'])
    icon = data.get('icon', goal['icon'])
    color = data.get('color', goal['color'])

    db.execute(
        "UPDATE savings_goals SET title = ?, target_coins = ?, icon = ?, color = ? WHERE id = ?",
        (title, target_coins, icon, color, goal_id)
    )
    db.commit()
    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    return jsonify(row_to_dict(goal))


@app.route('/api/savings-goals/<int:goal_id>/contribute', methods=['POST'])
def contribute_savings_goal(goal_id):
    """Move coins from kid's points into a savings goal."""
    db = get_db()
    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    if goal['completed']:
        return jsonify({'error': 'Goal already completed'}), 400

    data = request.get_json()
    kid_id = data.get('kid_id', goal['kid_id'])
    amount = data.get('amount', 0)

    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400

    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    if kid['points'] < amount:
        return jsonify({'error': f'Not enough coins (have {kid["points"]}, need {amount})'}), 400

    # Deduct from kid points, add to goal savings
    db.execute("UPDATE kids SET points = points - ? WHERE id = ?", (amount, kid_id))
    db.execute("UPDATE savings_goals SET saved_coins = saved_coins + ? WHERE id = ?", (amount, goal_id))
    db.execute("INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
               (kid_id, -amount, f'儲蓄目標: {goal["title"]}'))

    # Check if goal is now complete
    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    auto_completed = False
    if goal['saved_coins'] >= goal['target_coins']:
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        db.execute("UPDATE savings_goals SET completed = 1, completed_at = ? WHERE id = ?",
                   (now, goal_id))
        db.commit()
        auto_completed = True
        # Award achievement
        db.execute("INSERT INTO achievements (kid_id, badge, title, description) VALUES (?, ?, ?, ?)",
                   (kid_id, '🏆', f'達成目標: {goal["title"]}', f'成功儲蓄 {goal["target_coins"]} 🪙！'))
    else:
        db.commit()

    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    return jsonify({
        'goal': row_to_dict(goal),
        'auto_completed': auto_completed,
        'remaining_points': db.execute("SELECT points FROM kids WHERE id = ?", (kid_id,)).fetchone()['points'],
    })


@app.route('/api/savings-goals/<int:goal_id>/withdraw', methods=['POST'])
def withdraw_savings_goal(goal_id):
    """Move saved coins back to kid's points (with penalty)."""
    db = get_db()
    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    if goal['completed']:
        return jsonify({'error': 'Cannot withdraw from completed goal'}), 400

    data = request.get_json()
    kid_id = data.get('kid_id', goal['kid_id'])
    amount = data.get('amount', 0)

    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    if goal['saved_coins'] < amount:
        return jsonify({'error': f'Not enough saved (have {goal["saved_coins"]}, want {amount})'}), 400

    # 10% penalty on withdrawal (minimum 1 coin)
    penalty = max(1, int(amount * 0.1))
    actual_return = amount - penalty

    db.execute("UPDATE kids SET points = points + ? WHERE id = ?", (actual_return, kid_id))
    db.execute("UPDATE savings_goals SET saved_coins = saved_coins - ? WHERE id = ?", (amount, goal_id))
    db.execute("INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
               (kid_id, actual_return, f'提取儲蓄 (-{penalty}🔒 罰金): {goal["title"]}'))
    db.commit()

    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    return jsonify({
        'goal': row_to_dict(goal),
        'returned': actual_return,
        'penalty': penalty,
        'remaining_points': db.execute("SELECT points FROM kids WHERE id = ?", (kid_id,)).fetchone()['points'],
    })


@app.route('/api/savings-goals/<int:goal_id>', methods=['DELETE'])
def delete_savings_goal(goal_id):
    """Delete a savings goal (saved coins are lost)."""
    db = get_db()
    goal = db.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404

    saved = goal['saved_coins']
    db.execute("DELETE FROM savings_goals WHERE id = ?", (goal_id,))
    db.commit()
    return jsonify({'deleted': True, 'saved_coins_lost': saved})


# ── Transaction Records (Ledger) ──────────────────────────────

@app.route('/api/transactions', methods=['GET'])
def list_transactions():
    """Paginated, filterable transaction history for kids."""
    db = get_db()
    kid_id = request.args.get('kid_id', type=int)
    if not kid_id:
        return jsonify({'error': 'kid_id is required'}), 400
    
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)
    tx_type = request.args.get('type', 'all')
    days = request.args.get('days', 30, type=int)
    amount_min = request.args.get('amount_min', type=int)
    amount_max = request.args.get('amount_max', type=int)
    
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    wheres = ["pl.kid_id = ?", "pl.created_at >= ?"]
    params = [kid_id, since]
    
    if tx_type != 'all':
        if tx_type == 'task':
            wheres.append("(pl.amount > 0 AND pl.reason LIKE 'Completed task:%')")
        elif tx_type == 'building':
            wheres.append("(pl.amount < 0 AND (pl.reason LIKE 'Built%' OR pl.reason LIKE 'Upgraded%'))")
        elif tx_type == 'expedition':
            wheres.append("(pl.amount > 0 AND pl.reason LIKE 'Expedition%')")
        elif tx_type == 'earned':
            wheres.append("pl.amount > 0")
        elif tx_type == 'spent':
            wheres.append("pl.amount < 0")
    
    if amount_min is not None:
        wheres.append("pl.amount >= ?")
        params.append(amount_min)
    if amount_max is not None:
        wheres.append("pl.amount <= ?")
        params.append(amount_max)
    
    where_clause = " AND ".join(wheres)
    count_sql = f"SELECT COUNT(*) FROM points_log pl WHERE {where_clause}"
    total = db.execute(count_sql, params).fetchone()[0]
    
    offset = (page - 1) * per_page
    rows = db.execute(f"""
        SELECT pl.id, pl.amount, pl.reason, pl.created_at,
               k.name AS kid_name, k.avatar AS kid_avatar
        FROM points_log pl
        JOIN kids k ON pl.kid_id = k.id
        WHERE {where_clause}
        ORDER BY pl.created_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()
    
    items = []
    for r in rows:
        rdict = dict(r)
        rdict['type'] = classify_tx_type(rdict['reason'], rdict['amount'])
        reason = rdict['reason'] or ''
        if rdict['type'] == 'task':
            rdict['icon'] = '✅'
            rdict['category'] = '任務'
        elif rdict['type'] == 'building':
            rdict['icon'] = '🏗️'
            rdict['category'] = '建築'
        elif rdict['type'] == 'expedition':
            rdict['icon'] = '🗺️'
            rdict['category'] = '探險'
        elif rdict['amount'] > 0:
            rdict['icon'] = '💰'
            rdict['category'] = '收入'
        else:
            rdict['icon'] = '💸'
            rdict['category'] = '支出'
        items.append(rdict)
    
    return jsonify({
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': max(1, (total + per_page - 1) // per_page),
        },
    })


@app.route('/api/transactions/summary', methods=['GET'])
def transaction_summary():
    """Quick stats for the ledger header."""
    db = get_db()
    kid_id = request.args.get('kid_id', type=int)
    if not kid_id:
        return jsonify({'error': 'kid_id is required'}), 400
    
    kid = db.execute("SELECT points FROM kids WHERE id=?", (kid_id,)).fetchone()
    current_balance = kid['points'] if kid else 0
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
    
    today_earned = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM points_log WHERE kid_id=? AND amount>0 AND DATE(created_at)=?",
        (kid_id, today)
    ).fetchone()[0]
    
    week_stats = db.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS earned,
            COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS spent,
            COUNT(*) AS transactions
        FROM points_log
        WHERE kid_id=? AND created_at >= ?
    """, (kid_id, week_ago)).fetchone()
    
    month_stats = db.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS earned,
            COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS spent
        FROM points_log
        WHERE kid_id=? AND created_at >= ?
    """, (kid_id, month_ago)).fetchone()
    
    best_day = db.execute("""
        SELECT DATE(created_at) AS day, SUM(amount) AS total
        FROM points_log
        WHERE kid_id=? AND amount>0
        GROUP BY DATE(created_at)
        ORDER BY total DESC
        LIMIT 1
    """, (kid_id,)).fetchone()
    
    return jsonify({
        'current_balance': current_balance,
        'today_earned': today_earned,
        'week_earned': week_stats['earned'] if week_stats else 0,
        'week_spent': week_stats['spent'] if week_stats else 0,
        'week_transactions': week_stats['transactions'] if week_stats else 0,
        'month_earned': month_stats['earned'] if month_stats else 0,
        'month_spent': month_stats['spent'] if month_stats else 0,
        'best_day': best_day['day'] if best_day else None,
        'best_day_amount': best_day['total'] if best_day else 0,
    })


# -- Login/Auth --
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    kid_id = data.get('kid_id')
    pin = data.get('pin', '')
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    auth = db.execute("SELECT * FROM kid_auth WHERE kid_id = ?", (kid_id,)).fetchone()
    if not auth:
        db.execute("INSERT INTO kid_auth (kid_id, pin) VALUES (?, '0000')", (kid_id,))
        db.commit()
        return jsonify({'ok': True, 'kid': row_to_dict(kid), 'pin': '0000'})
    if auth['pin'] != pin:
        return jsonify({'error': 'Wrong PIN'}), 403
    return jsonify({'ok': True, 'kid': row_to_dict(kid)})

# -- Buildings (unchanged from v2) --

@app.route('/api/building-defs', methods=['GET'])
def list_building_defs():
    db = get_db()
    rows = db.execute("SELECT * FROM building_defs ORDER BY cost_gold ASC").fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/kids/<int:kid_id>/buildings', methods=['GET'])
def list_buildings(kid_id):
    db = get_db()
    rows = db.execute("""
        SELECT b.*, bd.name, bd.icon, bd.buff_type, bd.buff_vals, bd.effect
        FROM buildings b
        JOIN building_defs bd ON b.def_id = bd.id
        WHERE b.kid_id = ?
    """, (kid_id,)).fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/kids/<int:kid_id>/buildings', methods=['POST'])
def place_building(kid_id):
    data = request.get_json(silent=True) or {}
    def_id = data.get('def_id')
    plot_idx = data.get('plot_idx')
    if not def_id:
        return jsonify({'error': 'def_id is required'}), 400
    db = get_db()
    existing = db.execute("SELECT id FROM buildings WHERE kid_id=? AND plot_idx=?", (kid_id, plot_idx)).fetchone()
    if existing:
        return jsonify({'error': 'Plot already occupied'}), 400

    bdef = db.execute("SELECT * FROM building_defs WHERE id=?", (def_id,)).fetchone()
    if not bdef:
        return jsonify({'error': 'Building definition not found'}), 404

    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    if kid['points'] < bdef['cost_gold']:
        return jsonify({'error': 'Insufficient resources'}), 400

    try:
        required_mats = json.loads(bdef['materials']) if bdef['materials'] else {}
    except (json.JSONDecodeError, TypeError):
        required_mats = {}
    for item_type, qty in required_mats.items():
        inv = db.execute("SELECT quantity FROM inventory WHERE kid_id=? AND item_type=?", (kid_id, item_type)).fetchone()
        if not inv or inv['quantity'] < qty:
            return jsonify({'error': 'Insufficient resources'}), 400

    db.execute("UPDATE kids SET points = points - ? WHERE id=?", (bdef['cost_gold'], kid_id))
    db.execute("INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
               (kid_id, -bdef['cost_gold'], f"Built {bdef['name']}"))

    for item_type, qty in required_mats.items():
        db.execute("UPDATE inventory SET quantity = quantity - ? WHERE kid_id=? AND item_type=?",
                   (qty, kid_id, item_type))

    cur = db.execute("INSERT INTO buildings (kid_id, def_id, plot_idx, level) VALUES (?, ?, ?, 1)", (kid_id, def_id, plot_idx))
    db.commit()
    row = db.execute("SELECT b.*, bd.name, bd.icon, bd.buff_type, bd.buff_vals, bd.effect FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.id=?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201

@app.route('/api/kids/<int:kid_id>/buildings/<int:b_id>/upgrade', methods=['POST'])
def upgrade_building(kid_id, b_id):
    db = get_db()
    b = db.execute("SELECT b.*, bd.max_level, bd.name, bd.buff_vals, bd.materials FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.id=? AND b.kid_id=?", (b_id, kid_id)).fetchone()
    if not b:
        return jsonify({'error': 'Building not found'}), 404
    if b['level'] >= b['max_level']:
        return jsonify({'error': 'Already max level'}), 400

    cost_gold = b['level'] * 100
    try:
        base_mats = json.loads(b['materials']) if b['materials'] else {}
    except (json.JSONDecodeError, TypeError):
        base_mats = {}
    required_mats = {k: v * (b['level'] + 1) for k, v in base_mats.items()}

    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    if kid['points'] < cost_gold:
        return jsonify({'error': 'Insufficient resources'}), 400

    for item_type, qty in required_mats.items():
        inv = db.execute("SELECT quantity FROM inventory WHERE kid_id=? AND item_type=?", (kid_id, item_type)).fetchone()
        if not inv or inv['quantity'] < qty:
            return jsonify({'error': 'Insufficient resources'}), 400

    db.execute("UPDATE kids SET points = points - ? WHERE id=?", (cost_gold, kid_id))
    db.execute("INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
               (kid_id, -cost_gold, f"Upgraded {b['name']} to Lv.{b['level']+1}"))

    for item_type, qty in required_mats.items():
        db.execute("UPDATE inventory SET quantity = quantity - ? WHERE kid_id=? AND item_type=?",
                   (qty, kid_id, item_type))

    new_level = b['level'] + 1
    db.execute("UPDATE buildings SET level=? WHERE id=?", (new_level, b_id))
    db.commit()
    updated = db.execute("SELECT b.*, bd.name, bd.icon, bd.buff_type, bd.buff_vals, bd.effect FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.id=?", (b_id,)).fetchone()
    return jsonify(row_to_dict(updated))

@app.route('/api/kids/<int:kid_id>/buildings/<int:b_id>', methods=['DELETE'])
def remove_building(kid_id, b_id):
    db = get_db()
    db.execute("DELETE FROM buildings WHERE id=? AND kid_id=?", (b_id, kid_id))
    db.commit()
    return jsonify({'ok': True})

# -- Inventory --

@app.route('/api/kids/<int:kid_id>/inventory', methods=['GET'])
def get_inventory(kid_id):
    db = get_db()
    rows = db.execute("SELECT * FROM inventory WHERE kid_id=?", (kid_id,)).fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/kids/<int:kid_id>/inventory/add', methods=['POST'])
def add_to_inventory(kid_id):
    data = request.get_json(silent=True) or {}
    item_type = data.get('item_type')
    qty = int(data.get('quantity', 1))
    db = get_db()
    existing = db.execute("SELECT * FROM inventory WHERE kid_id=? AND item_type=?", (kid_id, item_type)).fetchone()
    if existing:
        db.execute("UPDATE inventory SET quantity=quantity+? WHERE id=?", (qty, existing['id']))
    else:
        db.execute("INSERT INTO inventory (kid_id, item_type, quantity) VALUES (?, ?, ?)", (kid_id, item_type, qty))
    db.commit()
    updated = db.execute("SELECT * FROM inventory WHERE kid_id=?", (kid_id,)).fetchall()
    return jsonify(rows_to_list(updated))

# -- Expeditions --

@app.route('/api/kids/<int:kid_id>/expedition', methods=['GET'])
def get_expedition(kid_id):
    db = get_db()
    exp = db.execute("SELECT * FROM expeditions WHERE kid_id=? AND status='running' ORDER BY start_time DESC LIMIT 1", (kid_id,)).fetchone()
    return jsonify(row_to_dict(exp) if exp else {})

@app.route('/api/kids/<int:kid_id>/expedition/start', methods=['POST'])
def start_expedition(kid_id):
    data = request.get_json(silent=True) or {}
    region_id = data.get('region_id')
    duration = int(data.get('duration_hours', 2))
    expedition_type = data.get('expedition_type', 'explore')
    if expedition_type not in ('explore', 'quiz', 'battle'):
        return jsonify({'error': 'Invalid expedition type'}), 400
    db = get_db()
    running = db.execute("SELECT id FROM expeditions WHERE kid_id=? AND status='running'", (kid_id,)).fetchone()
    if running:
        return jsonify({'error': 'Expedition already running'}), 400
    now = datetime.utcnow()
    end = now + timedelta(hours=duration)
    cur = db.execute("INSERT INTO expeditions (kid_id, region_id, expedition_type, start_time, end_time, status) VALUES (?,?,?,?,?,'running')",
                     (kid_id, region_id, expedition_type, now.isoformat() + 'Z', end.isoformat() + 'Z'))
    db.commit()
    exp = db.execute("SELECT * FROM expeditions WHERE id=?",
                     (cur.lastrowid,)).fetchone()

    # For quiz mode, assign random questions
    extra = {}
    if expedition_type == 'quiz':
        questions = db.execute("SELECT * FROM quiz_questions ORDER BY RANDOM() LIMIT 5").fetchall()
        extra['questions'] = [dict(q) for q in questions]
        db.execute("UPDATE expeditions SET expedition_data=? WHERE id=?",
                   (json.dumps({'questions': [q['id'] for q in questions], 'answers': [], 'score': 0}), cur.lastrowid))
        db.commit()
        exp = db.execute("SELECT * FROM expeditions WHERE id=?", (cur.lastrowid,)).fetchone()

    result = row_to_dict(exp)
    result['extra'] = extra
    return jsonify(result), 201

@app.route('/api/kids/<int:kid_id>/expedition/claim', methods=['POST'])
def claim_expedition(kid_id):
    db = get_db()
    exp = db.execute("SELECT * FROM expeditions WHERE kid_id=? AND status='running' ORDER BY start_time DESC LIMIT 1", (kid_id,)).fetchone()
    if not exp:
        return jsonify({'error': 'No running expedition'}), 400
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(exp['end_time'])
    if now < end:
        return jsonify({'error': 'Expedition not finished'}), 400
    materials = ['wood', 'brick', 'iron', 'gem', 'star_shard']
    rewards = {}
    for m in materials:
        if random.random() < 0.6:
            rewards[m] = random.randint(1, 5)
    events = []
    if random.random() < 0.1:
        rewards['dragon_scale'] = rewards.get('dragon_scale', 0) + 1
        events.append('🐉 發現龍鱗！')
    if random.random() < 0.08:
        rewards['star_stone'] = rewards.get('star_stone', 0) + 1
        events.append('⭐ 搵到星石！')
    if random.random() < 0.15:
        rewards['mystery_box'] = rewards.get('mystery_box', 0) + 1
        events.append('🎁 獲得神秘寶箱')
    gold_reward = random.randint(10, 30) * (exp['region_id'] or 1)
    for item_type, qty in rewards.items():
        existing = db.execute("SELECT * FROM inventory WHERE kid_id=? AND item_type=?", (kid_id, item_type)).fetchone()
        if existing:
            db.execute("UPDATE inventory SET quantity=quantity+? WHERE id=?", (qty, existing['id']))
        else:
            db.execute("INSERT INTO inventory (kid_id, item_type, quantity) VALUES (?, ?, ?)", (kid_id, item_type, qty))
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if kid:
        db.execute("UPDATE kids SET points=points+? WHERE id=?", (gold_reward, kid_id))
        # Log expedition gold in points_log so it appears in transaction records
        db.execute("INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)", 
                   (kid_id, gold_reward, f"Expedition claim (Region {exp['region_id']})"))
    db.execute("INSERT OR IGNORE INTO explored_regions (kid_id, region_id) VALUES (?, ?)", (kid_id, exp['region_id']))
    result_json = json.dumps({'gold': gold_reward, 'materials': rewards, 'events': events})
    db.execute("UPDATE expeditions SET status='completed', rewards=? WHERE id=?", (result_json, exp['id']))
    db.commit()
    return jsonify({'gold': gold_reward, 'materials': rewards, 'events': events})


@app.route('/api/kids/<int:kid_id>/expedition/answer', methods=['POST'])
def answer_quiz(kid_id):
    """Submit an answer for quiz-mode expedition."""
    data = request.get_json(silent=True) or {}
    question_id = data.get('question_id')
    answer_idx = data.get('answer_idx')
    if question_id is None or answer_idx is None:
        return jsonify({'error': 'question_id and answer_idx required'}), 400
    db = get_db()
    exp = db.execute("SELECT * FROM expeditions WHERE kid_id=? AND status='running' AND expedition_type='quiz' ORDER BY start_time DESC LIMIT 1", (kid_id,)).fetchone()
    if not exp:
        return jsonify({'error': 'No running quiz expedition'}), 400
    exp_data = json.loads(exp['expedition_data'] or '{}')
    if question_id not in exp_data.get('questions', []):
        return jsonify({'error': 'Question not in this expedition'}), 400
    if question_id in [a.get('id') for a in exp_data.get('answers', [])]:
        return jsonify({'error': 'Already answered'}), 400
    q = db.execute("SELECT * FROM quiz_questions WHERE id=?", (question_id,)).fetchone()
    if not q:
        return jsonify({'error': 'Question not found'}), 404
    correct = answer_idx == q['correct_idx']
    if correct:
        exp_data['score'] = exp_data.get('score', 0) + q['points']
    answers = exp_data.get('answers', [])
    answers.append({'id': question_id, 'selected': answer_idx, 'correct': correct})
    exp_data['answers'] = answers
    db.execute("UPDATE expeditions SET expedition_data=? WHERE id=?", (json.dumps(exp_data), exp['id']))
    db.commit()
    return jsonify({'correct': correct, 'correct_idx': q['correct_idx'], 'points': q['points'] if correct else 0, 'score': exp_data['score'], 'total': len(exp_data.get('questions', []))})


@app.route('/api/quiz-questions/<int:qid>', methods=['GET'])
def get_quiz_question(qid):
    """Return a single quiz question (without exposing correct answer)."""
    db = get_db()
    q = db.execute("SELECT * FROM quiz_questions WHERE id=?", (qid,)).fetchone()
    if not q:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'id': q['id'],
        'subject': q['subject'],
        'question': q['question'],
        'options': q['options'],
        'points': q['points'],
    })


@app.route('/api/kids/<int:kid_id>/explored', methods=['GET'])
def get_explored(kid_id):
    db = get_db()
    rows = db.execute("SELECT * FROM explored_regions WHERE kid_id=?", (kid_id,)).fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/kids/<int:kid_id>/town', methods=['GET'])
def get_town_state(kid_id):
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    buildings = db.execute("""
        SELECT b.*, bd.name, bd.icon, bd.buff_type, bd.buff_vals, bd.effect, bd.materials, bd.max_level
        FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.kid_id=?
    """, (kid_id,)).fetchall()
    inventory = db.execute("SELECT * FROM inventory WHERE kid_id=?", (kid_id,)).fetchall()
    explored = db.execute("SELECT * FROM explored_regions WHERE kid_id=?", (kid_id,)).fetchall()
    running_exp = db.execute("SELECT * FROM expeditions WHERE kid_id=? AND status='running' ORDER BY start_time DESC LIMIT 1", (kid_id,)).fetchone()
    achievements = db.execute("SELECT * FROM achievements WHERE kid_id=? ORDER BY earned_at DESC", (kid_id,)).fetchall()
    streak = db.execute("SELECT * FROM streaks WHERE kid_id=?", (kid_id,)).fetchone()
    return jsonify({
        'kid': row_to_dict(kid),
        'buildings': rows_to_list(buildings),
        'inventory': rows_to_list(inventory),
        'explored': rows_to_list(explored),
        'expedition': row_to_dict(running_exp) if running_exp else None,
        'achievements': rows_to_list(achievements),
        'streak': row_to_dict(streak) if streak else {'current_streak': 0, 'best_streak': 0},
    })

# -- Stats Enhancements (v2.2) --

@app.route('/api/stats/completion-history', methods=['GET'])
def stats_completion_history():
    """Paginated completion timeline with filters."""
    db = get_db()
    kid_id = request.args.get('kid_id')
    days = request.args.get('days', 30, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    where = "AND t.completed_at >= ?"
    params = [since]
    if kid_id:
        where += " AND t.kid_id=?"
        params.append(int(kid_id))

    # Total count
    count_sql = f"SELECT COUNT(*) FROM tasks t WHERE t.completed=1 AND t.completed_at IS NOT NULL {where}"
    total = db.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(f"""
        SELECT t.id, t.title, t.icon, t.points, t.category, t.completed_at,
               t.kid_id, k.name AS kid_name, k.avatar AS kid_avatar
        FROM tasks t
        LEFT JOIN kids k ON t.kid_id = k.id
        WHERE t.completed=1 AND t.completed_at IS NOT NULL {where}
        ORDER BY t.completed_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()

    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': max(1, (total + per_page - 1) // per_page),
        'items': rows_to_list(rows),
    })


@app.route('/api/stats/monthly', methods=['GET'])
def stats_monthly():
    """Monthly aggregation: tasks completed + gold earned by month."""
    db = get_db()
    kid_id = request.args.get('kid_id')
    months = request.args.get('months', 12, type=int)

    # Completed tasks per month
    task_params = []
    task_where = ""
    if kid_id:
        task_where = "AND t.kid_id=?"
        task_params = [int(kid_id)]

    monthly_tasks = db.execute(f"""
        SELECT strftime('%Y-%m', t.completed_at) AS ym,
               COUNT(*) AS tasks_completed,
               SUM(t.points) AS points_awarded
        FROM tasks t
        WHERE t.completed=1 AND t.completed_at IS NOT NULL {task_where}
        GROUP BY ym ORDER BY ym DESC LIMIT ?
    """, task_params + [months]).fetchall()

    # Gold earned per month (from points_log, positive amounts)
    gold_params = []
    gold_where = ""
    if kid_id:
        gold_where = "AND pl.kid_id=?"
        gold_params = [int(kid_id)]

    monthly_gold = db.execute(f"""
        SELECT strftime('%Y-%m', pl.created_at) AS ym,
               COUNT(*) AS transactions,
               SUM(pl.amount) AS gold_earned
        FROM points_log pl
        WHERE pl.amount > 0 {gold_where}
        GROUP BY ym ORDER BY ym DESC LIMIT ?
    """, gold_params + [months]).fetchall()

    # Merge into unified timeline
    merged = {}
    for row in monthly_tasks:
        merged[row['ym']] = {'tasks_completed': row['tasks_completed'], 'points_awarded': row['points_awarded'], 'gold_earned': 0, 'transactions': 0}
    for row in monthly_gold:
        if row['ym'] in merged:
            merged[row['ym']]['gold_earned'] = row['gold_earned']
            merged[row['ym']]['transactions'] = row['transactions']
        else:
            merged[row['ym']] = {'tasks_completed': 0, 'points_awarded': 0, 'gold_earned': row['gold_earned'], 'transactions': row['transactions']}

    result = []
    for ym in sorted(merged.keys(), reverse=True):
        result.append({'month': ym, **merged[ym]})
    return jsonify(result)


@app.route('/api/stats/calendar', methods=['GET'])
def stats_calendar():
    """Daily task completion + gold earned for last 365 days (heatmap data)."""
    db = get_db()
    kid_id = request.args.get('kid_id')
    days = request.args.get('days', 365, type=int)

    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')

    task_params = [since]
    gold_params = [since]
    task_where = ""
    gold_where = ""
    if kid_id:
        task_where = "AND t.kid_id=?"
        gold_where = "AND pl.kid_id=?"
        task_params.append(int(kid_id))
        gold_params.append(int(kid_id))

    daily_tasks = db.execute(f"""
        SELECT DATE(t.completed_at) AS day,
               COUNT(*) AS tasks_completed,
               SUM(t.points) AS points_awarded
        FROM tasks t
        WHERE t.completed=1 AND t.completed_at IS NOT NULL AND DATE(t.completed_at) >= ? {task_where}
        GROUP BY DATE(t.completed_at) ORDER BY day
    """, task_params).fetchall()

    daily_gold = db.execute(f"""
        SELECT DATE(pl.created_at) AS day,
               COUNT(*) AS transactions,
               SUM(pl.amount) AS gold_earned
        FROM points_log pl
        WHERE pl.amount > 0 AND DATE(pl.created_at) >= ? {gold_where}
        GROUP BY DATE(pl.created_at) ORDER BY day
    """, gold_params).fetchall()

    # Build sparse dict
    daily = {}
    for row in daily_tasks:
        daily[row['day']] = {'tasks_completed': row['tasks_completed'], 'points_awarded': row['points_awarded'], 'gold_earned': 0}
    for row in daily_gold:
        key = row['day']
        if key in daily:
            daily[key]['gold_earned'] = row['gold_earned']
        else:
            daily[key] = {'tasks_completed': 0, 'points_awarded': 0, 'gold_earned': row['gold_earned']}

    # Fill in missing days with zeros
    result = []
    current = datetime.strptime(since, '%Y-%m-%d')
    end = datetime.utcnow()
    while current <= end:
        key = current.strftime('%Y-%m-%d')
        if key in daily:
            result.append({'date': key, **daily[key]})
        else:
            result.append({'date': key, 'tasks_completed': 0, 'points_awarded': 0, 'gold_earned': 0})
        current += timedelta(days=1)

    return jsonify(result)


@app.route('/api/stats/by-category', methods=['GET'])
def stats_by_category():
    """Completion rate by task category."""
    db = get_db()
    kid_id = request.args.get('kid_id')

    where = ""
    params = []
    if kid_id:
        where = "WHERE t.kid_id=?"
        params.append(int(kid_id))

    rows = db.execute(f"""
        SELECT
            COALESCE(NULLIF(t.category, ''), '(未分類)') AS category,
            COUNT(*) AS total,
            SUM(CASE WHEN t.completed=1 THEN 1 ELSE 0 END) AS completed,
            ROUND(CAST(SUM(CASE WHEN t.completed=1 THEN 1 ELSE 0 END) AS REAL) / MAX(COUNT(*), 1) * 100, 1) AS rate,
            COALESCE(SUM(CASE WHEN t.completed=1 THEN t.points ELSE 0 END), 0) AS points_awarded
        FROM tasks t
        {where}
        GROUP BY category
        ORDER BY total DESC
    """, params).fetchall()

    return jsonify(rows_to_list(rows))


@app.route('/api/stats/export', methods=['GET'])
def stats_export():
    """Export completed task report as CSV."""
    db = get_db()
    kid_id = request.args.get('kid_id')
    days = request.args.get('days', 365, type=int)
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    where = "AND t.completed_at >= ?"
    params = [since]
    if kid_id:
        where += " AND t.kid_id=?"
        params.append(int(kid_id))

    rows = db.execute(f"""
        SELECT t.id, t.title, t.icon, t.points, t.category,
               t.completed_at, t.created_at,
               COALESCE(k.name, '') AS kid_name, COALESCE(k.avatar, '') AS kid_avatar
        FROM tasks t
        LEFT JOIN kids k ON t.kid_id = k.id
        WHERE t.completed=1 AND t.completed_at IS NOT NULL {where}
        ORDER BY t.completed_at DESC
    """, params).fetchall()

    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Title', 'Icon', 'Points', 'Category', 'Completed At', 'Created At', 'Kid Name', 'Kid Avatar'])
    for row in rows:
        writer.writerow([row['id'], row['title'], row['icon'], row['points'],
                        row['category'], row['completed_at'], row['created_at'],
                        row['kid_name'], row['kid_avatar']])

    csv_content = output.getvalue()
    from flask import Response
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=kids_town_report_{datetime.utcnow().strftime("%Y%m%d")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig',
        }
    )


# -- Health check --

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'service': 'kids-town-backend', 'version': '2.1'})


# -- Dev Dashboard API --

DEV_FEATURES = [
    # Phase 1
    {'id': 'p1-login', 'phase': 1, 'name': '🔐 小朋友登入', 'status': 'completed', 'detail': 'Create/select child profile'},
    {'id': 'p1-db', 'phase': 1, 'name': '🗄️ 後端 DB 模型', 'status': 'completed', 'detail': 'kids, buildings, inventory, expeditions, events'},
    {'id': 'p1-resources', 'phase': 1, 'name': '🪙 資源系統', 'status': 'completed', 'detail': '金幣、經驗值、材料'},
    # Phase 2
    {'id': 'p2-town', 'phase': 2, 'name': '🎨 Canvas 城鎮', 'status': 'completed', 'detail': 'Kairosoft pixel town'},
    {'id': 'p2-buildings', 'phase': 2, 'name': '🏗️ 放置建築物', 'status': 'completed', 'detail': '商店買建築物放落 grid'},
    {'id': 'p2-shop', 'phase': 2, 'name': '🏪 商店 v2', 'status': 'completed', 'detail': '材料需求顯示'},
    # Phase 3
    {'id': 'p3-explore', 'phase': 3, 'name': '🗺️ 探險地圖', 'status': 'completed', 'detail': '5 個區域，逐層解鎖'},
    {'id': 'p3-events', 'phase': 3, 'name': '🎲 特殊事件', 'status': 'completed', 'detail': '隨機事件 → 關鍵材料'},
    {'id': 'p3-inventory', 'phase': 3, 'name': '📦 材料庫存', 'status': 'completed', 'detail': '獨立材料背包'},
    # Phase 4
    {'id': 'p4-tasks', 'phase': 4, 'name': '📋 家長任務管理', 'status': 'completed', 'detail': '創建/編輯/刪除、搜尋/篩選'},
    {'id': 'p4-task-edit', 'phase': 4, 'name': '✏️ 任務編輯', 'status': 'completed', 'detail': '描述+截止日期+重複週期'},
    {'id': 'p4-desc', 'phase': 4, 'name': '📝 任務描述', 'status': 'completed', 'detail': '200字描述+摘要顯示'},
    {'id': 'p4-due', 'phase': 4, 'name': '📅 截止日期', 'status': 'completed', 'detail': '到期日+逾期紅提示'},
    {'id': 'p4-overdue', 'phase': 4, 'name': '🔍 逾期篩選', 'status': 'completed', 'detail': '狀態過濾器「已逾期」'},
    {'id': 'p4-points', 'phase': 4, 'name': '🪙 積分手動調整', 'status': 'completed', 'detail': '加/扣分+原因記錄'},
    {'id': 'p4-log', 'phase': 4, 'name': '📜 活動紀錄', 'status': 'completed', 'detail': 'points_log 時間排序顯示'},
    {'id': 'p4-recurring', 'phase': 4, 'name': '🔄 重複任務', 'status': 'completed', 'detail': 'daily/weekly/weekdays'},
    {'id': 'p4-streak', 'phase': 4, 'name': '🔥 連續記錄', 'status': 'completed', 'detail': '每日任務完成 streak'},
    {'id': 'p4-achievements', 'phase': 4, 'name': '🏆 成就系統', 'status': 'completed', 'detail': '12種成就自動解鎖'},
    {'id': 'p4-leaderboard', 'phase': 4, 'name': '🏅 排行榜', 'status': 'completed', 'detail': '總分/本週/本月排名'},
    {'id': 'p4-dashboard', 'phase': 4, 'name': '📊 統計儀表板', 'status': 'completed', 'detail': '完成率/趨勢圖/分類統計'},
    # Phase 5
    {'id': 'p5-rank', 'phase': 5, 'name': '🏆 排行榜', 'status': 'completed', 'detail': '三種排名+獎牌顯示'},
    {'id': 'p5-achievements', 'phase': 5, 'name': '🎖️ 成就系統', 'status': 'completed', 'detail': '12種成就自動解鎖'},
    {'id': 'p5-badges', 'phase': 5, 'name': '🏅 成就徽章展示', 'status': 'completed', 'detail': '已獲得/未解鎖 grid layout'},
    {'id': 'p5-stats', 'phase': 5, 'name': '📊 統計儀表板', 'status': 'completed', 'detail': '14日趨勢圖'},
    {'id': 'p5-streak2', 'phase': 5, 'name': '🔥 連續記錄', 'status': 'completed', 'detail': 'current+best streak 展示'},
    {'id': 'p5-reset', 'phase': 5, 'name': '📅 每週/每月重置', 'status': 'completed', 'detail': 'Leaderboard period 切換'},
    {'id': 'p5-bugfix', 'phase': 5, 'name': '🔧 Bug fix', 'status': 'completed', 'detail': 'check_achievements() 重複成就 bug'},
    {'id': 'p5-clean', 'phase': 5, 'name': '🧹 資料清理', 'status': 'completed', 'detail': '移除 duplicate kids + achievements'},
    # Phase 6 (Next)
    {'id': 'p6-pwa', 'phase': 6, 'name': '📱 PWA offline mode 測試', 'status': 'planned', 'detail': '需要真實裝置測試', 'priority': 'P2'},
    {'id': 'p6-notify', 'phase': 6, 'name': '🏆 推送通知', 'status': 'planned', 'detail': '任務完成推送、成就解鎖通知', 'priority': 'P3'},
    {'id': 'p6-more-stats', 'phase': 6, 'name': '📈 更多統計', 'status': 'planned', 'detail': '每月報告、圖表化趨勢', 'priority': 'P3'},
    {'id': 'p6-avatar', 'phase': 6, 'name': '🎨 自訂頭像', 'status': 'planned', 'detail': '頭像選擇器', 'priority': 'P4'},
]


@app.route('/api/dev-dashboard')
def dev_dashboard():
    """Return comprehensive development dashboard data."""
    db = get_db()

    # ── Kid stats ──
    kids = db.execute("SELECT * FROM kids ORDER BY points DESC, id ASC").fetchall()
    total_kids = len(kids)
    total_points = sum(k['points'] for k in kids)
    total_buildings = db.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
    total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE completed=1").fetchone()[0]
    completion_rate = round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0

    # Kid detail with buildings + streaks
    kid_details = []
    for k in kids:
        bld = db.execute("""
            SELECT b.*, bd.name, bd.icon, bd.effect
            FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.kid_id=?
        """, (k['id'],)).fetchall()
        streak = db.execute("SELECT * FROM streaks WHERE kid_id=?", (k['id'],)).fetchone()
        achs = db.execute("SELECT COUNT(*) FROM achievements WHERE kid_id=?", (k['id'],)).fetchone()[0]
        kid_details.append({
            'id': k['id'],
            'name': k['name'],
            'avatar': k['avatar'],
            'color': k['color'],
            'points': k['points'],
            'buildings': len(bld),
            'buildings_detail': rows_to_list(bld),
            'streak': row_to_dict(streak) if streak else {'current_streak': 0, 'best_streak': 0},
            'achievements_unlocked': achs,
            'created_at': k['created_at'],
        })

    # ── Achievement heatmap ──
    achievement_defs = [{'id': k, 'icon': v[0], 'title': v[1], 'description': v[2]}
                        for k, v in ACHIEVEMENT_DEFS.items()]
    all_earned = db.execute("""
        SELECT a.*, k.name AS kid_name, k.avatar AS kid_avatar
        FROM achievements a
        JOIN kids k ON a.kid_id = k.id
        ORDER BY a.earned_at DESC
    """).fetchall()

    # Per-kid heatmap data
    heatmap = {}
    for k in kids:
        heatmap[k['id']] = {
            'kid_name': k['name'],
            'achievements': {}
        }
    for a in all_earned:
        if a['kid_id'] not in heatmap:
            continue
        heatmap[a['kid_id']]['achievements'][a['badge']] = {
            'earned_at': a['earned_at'],
            'title': a['title'],
        }

    # ── Recent activity (last 30 entries) ──
    recent_activity = db.execute("""
        SELECT pl.*, k.name AS kid_name, k.avatar AS kid_avatar
        FROM points_log pl
        JOIN kids k ON pl.kid_id = k.id
        ORDER BY pl.created_at DESC
        LIMIT 30
    """).fetchall()

    # Also recent task completions
    recent_tasks = db.execute("""
        SELECT t.id, t.title, t.icon, t.points, t.completed_at,
               k.name AS kid_name, k.avatar AS kid_avatar
        FROM tasks t
        LEFT JOIN kids k ON t.kid_id = k.id
        WHERE t.completed=1 AND t.completed_at IS NOT NULL
        ORDER BY t.completed_at DESC
        LIMIT 20
    """).fetchall()

    # ── Building stats ──
    building_defs_count = db.execute("SELECT COUNT(*) FROM building_defs").fetchone()[0]
    building_types_used = db.execute("SELECT COUNT(DISTINCT def_id) FROM buildings").fetchone()[0]

    # Count features by status
    feature_counts = {'completed': 0, 'planned': 0}
    for f in DEV_FEATURES:
        feature_counts[f['status']] = feature_counts.get(f['status'], 0) + 1

    return jsonify({
        'summary': {
            'total_kids': total_kids,
            'total_points': total_points,
            'total_buildings': total_buildings,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': completion_rate,
            'building_defs': building_defs_count,
            'building_types_used': building_types_used,
        },
        'kid_details': kid_details,
        'features': DEV_FEATURES,
        'feature_counts': feature_counts,
        'achievement_defs': achievement_defs,
        'achievements_earned': rows_to_list(all_earned),
        'achievement_heatmap': heatmap,
        'recent_activity': rows_to_list(recent_activity),
        'recent_task_completions': rows_to_list(recent_tasks),
        'version': '3.0',
    })


# ── Auth API ──────────────────────────────────────────────────────

VALID_USERNAME = re.compile(r'^[a-zA-Z0-9_]{2,30}$')

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Unified login: detects role from username prefix/table."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip().lower()
    password = (data.get('password') or '').strip()
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    db = get_db()
    
    # 1. Try kid login (PIN)
    kid = db.execute("SELECT * FROM kids WHERE username=?", (username,)).fetchone()
    if kid:
        auth = db.execute("SELECT * FROM kid_auth WHERE kid_id=?", (kid['id'],)).fetchone()
        if auth and auth['pin'] == password:
            return jsonify({
                'role': 'kid',
                'user': row_to_dict(kid),
                'redirect': '/kids/'
            })
        return jsonify({'error': '密碼錯誤'}), 403
    
    # 2. Try parent login
    parent = db.execute("SELECT * FROM parents WHERE username=?", (username,)).fetchone()
    if parent:
        if parent['password'] == hash_password(password):
            # Get linked kids
            linked = db.execute("""
                SELECT k.* FROM kids k
                JOIN parent_kid pk ON k.id = pk.kid_id
                WHERE pk.parent_id = ?
            """, (parent['id'],)).fetchall()
            return jsonify({
                'role': 'parent',
                'user': {'id': parent['id'], 'username': parent['username'], 'name': parent['name']},
                'kids': rows_to_list(linked),
                'redirect': '/kids/manage'
            })
        return jsonify({'error': '密碼錯誤'}), 403
    
    # 3. Try admin login
    admin = db.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
    if admin:
        if admin['password'] == password or admin['password'] == hash_password(password):
            return jsonify({
                'role': 'admin',
                'user': {'id': admin['id'], 'username': admin['username'], 'name': admin['name'], 'role': admin['role']},
                'redirect': '/kids/admin'
            })
        return jsonify({'error': '密碼錯誤'}), 403
    
    return jsonify({'error': '帳號不存在'}), 404


@app.route('/api/auth/parent-register', methods=['POST'])
def parent_register():
    """Register a new parent (callable from frontend or by admin)."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip().lower()
    password = (data.get('password') or '').strip()
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    
    if not VALID_USERNAME.match(username):
        return jsonify({'error': '用戶名必須為 2-30 個英文字母、數字或底線'}), 400
    if len(password) < 4:
        return jsonify({'error': '密碼至少 4 個字元'}), 400
    
    db = get_db()
    
    # Check unique
    if db.execute("SELECT id FROM parents WHERE username=?", (username,)).fetchone():
        return jsonify({'error': '用戶名已被使用'}), 409
    if db.execute("SELECT id FROM kids WHERE username=?", (username,)).fetchone():
        return jsonify({'error': '用戶名已被使用'}), 409
    if db.execute("SELECT id FROM admins WHERE username=?", (username,)).fetchone():
        return jsonify({'error': '用戶名已被使用'}), 409
    
    cur = db.execute(
        "INSERT INTO parents (username, password, email, name) VALUES (?, ?, ?, ?)",
        (username, hash_password(password), email, name)
    )
    db.commit()
    parent = db.execute("SELECT * FROM parents WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({'ok': True, 'parent': {'id': parent['id'], 'username': parent['username'], 'name': parent['name']}}), 201


@app.route('/api/auth/link-kid', methods=['POST'])
def link_kid():
    """Link a parent to a kid (by kid_id)."""
    data = request.get_json(silent=True) or {}
    parent_id = data.get('parent_id')
    kid_username = (data.get('kid_username') or '').strip().lower()
    
    if not parent_id or not kid_username:
        return jsonify({'error': 'parent_id and kid_username required'}), 400
    
    db = get_db()
    parent = db.execute("SELECT * FROM parents WHERE id=?", (parent_id,)).fetchone()
    if not parent:
        return jsonify({'error': 'Parent not found'}), 404
    
    kid = db.execute("SELECT * FROM kids WHERE username=?", (kid_username,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    
    try:
        db.execute("INSERT INTO parent_kid (parent_id, kid_id) VALUES (?, ?)", (parent_id, kid['id']))
        db.commit()
        return jsonify({'ok': True, 'kid': {'id': kid['id'], 'name': kid['name'], 'avatar': kid['avatar']}}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Already linked'}), 409


@app.route('/api/auth/parent-kids', methods=['GET'])
def parent_kids():
    """Get kids linked to a parent."""
    parent_id = request.args.get('parent_id')
    if not parent_id:
        return jsonify({'error': 'parent_id required'}), 400
    
    db = get_db()
    kids = db.execute("""
        SELECT k.* FROM kids k
        JOIN parent_kid pk ON k.id = pk.kid_id
        WHERE pk.parent_id = ?
    """, (parent_id,)).fetchall()
    return jsonify(rows_to_list(kids))


# ── Dashboard proxy ──────────────────────────────────────────────
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dashboard')

@app.route('/dashboard')
@app.route('/dashboard/')
def serve_dashboard_index():
    path = os.path.join(DASHBOARD_DIR, 'index.html')
    if os.path.isfile(path):
        return open(path, encoding='utf-8').read()
    return jsonify({'error': 'dashboard index not found'}), 404

@app.route('/dashboard/<path:filename>')
def serve_dashboard_static(filename):
    path = os.path.join(DASHBOARD_DIR, filename)
    if os.path.isfile(path):
        ext = os.path.splitext(filename)[1]
        with open(path, 'rb') if ext in ('.png', '.ico', '.jpg', '.gif', '.svg') else open(path, encoding='utf-8') as f:
            content = f.read()
        mime_map = {'.json': 'application/json', '.js': 'application/javascript',
                    '.svg': 'image/svg+xml', '.css': 'text/css', '.png': 'image/png',
                    '.html': 'text/html', '.ico': 'image/x-icon', '.jpg': 'image/jpeg', '.gif': 'image/gif'}
        resp = make_response(content)
        resp.headers['Content-Type'] = mime_map.get(ext, 'text/plain')
        return resp
    return jsonify({'error': 'not found'}), 404

@app.route('/kanban')
@app.route('/kanban/')
def redirect_kanban():
    return '<script>window.location.href="/dashboard/?tab=kanban"</script><a href="/dashboard/?tab=kanban">Kanban Board</a>'

@app.route('/health')
@app.route('/health/')
def redirect_health():
    return '<script>window.location.href="/dashboard/?tab=health"</script><a href="/dashboard/?tab=health">Health Dashboard</a>'

# ── Main ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    migrate_db()
    migrate_db_v3()
    seed_building_defs()
    print(f'🎮 Kids Town 3.0 Backend (Role-based Auth) on http://0.0.0.0:9123')
    print(f'   Default admin: admin / admin123')
    app.run(host='0.0.0.0', port=9123, debug=False)
