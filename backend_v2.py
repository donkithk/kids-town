#!/usr/bin/env python3
"""
Kids Town Backend — SQLite + Flask API
Port 9123
v3.0 — Role-based auth: kids, parents, admins
"""
import os, sqlite3, json, random, re, hashlib, math
from datetime import datetime, timedelta, timezone, date
import bcrypt
from flask import Flask, request, jsonify, g, make_response, Response, session
from flask_cors import CORS

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kids_town.db')
app = Flask(__name__)
app.secret_key = os.environ.get('KIDS_TOWN_SECRET_KEY', 'kids-town-dev-secret-change-me')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'
CORS(app, supports_credentials=True)

# Static files the /kids/ route may serve. Anything else (including .db/.py) is 404.
STATIC_ALLOWED_EXT = {'.html', '.js', '.css', '.png', '.svg', '.ico', '.json', '.woff2', '.webp'}
STATIC_DENIED_MARKERS = ('.db', '.py', '.pyc', '.pyo', '.env', '.pem', '.key', '.sql')
# Write endpoints kids must not call even for themselves (points / debug inventory).
KID_DENIED_WRITE_SUFFIXES = ('/points', '/points/adjust', '/inventory/add')
PUBLIC_API = {
    ('GET', '/api/health'),
    ('POST', '/api/auth/login'),
    ('POST', '/api/auth/parent-register'),
    ('POST', '/api/login'),
    ('POST', '/api/auth/logout'),
}

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
            with open(path, encoding='utf-8') as f:
                html = f.read()
            resp = make_response(html)
            resp.headers['Content-Type'] = 'text/html; charset=utf-8'
            resp.headers['Cache-Control'] = 'no-store'
            return resp
    return jsonify({'error': 'index not found'}), 404

def _denied_static_filename(filename):
    """True if this path must never be served (secrets, source, sqlite, traversal)."""
    name = (filename or '').replace('\\', '/')
    if not name or name.startswith('/') or '..' in name.split('/'):
        return True
    lower = name.lower()
    for marker in STATIC_DENIED_MARKERS:
        if marker in lower:
            return True
    ext = os.path.splitext(lower)[1]
    if ext not in STATIC_ALLOWED_EXT:
        return True
    return False


def _safe_static_path(root, filename):
    base = os.path.abspath(root)
    path = os.path.abspath(os.path.join(base, filename))
    if path != base and not path.startswith(base + os.sep):
        return None
    return path


@app.route('/kids/<path:filename>')
def serve_kids_static(filename):
    if _denied_static_filename(filename):
        return jsonify({'error': 'not found'}), 404
    path = _safe_static_path(HTML_DIR, filename)
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, 'rb') as f:
        head = f.read(16)
        rest = f.read()
    if head.startswith(b'SQLite format 3'):
        return jsonify({'error': 'not found'}), 404
    data = head + rest
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        '.json': 'application/json',
        '.js': 'application/javascript',
        '.svg': 'image/svg+xml',
        '.css': 'text/css',
        '.png': 'image/png',
        '.html': 'text/html',
        '.ico': 'image/x-icon',
        '.woff2': 'font/woff2',
        '.webp': 'image/webp',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
    }
    # Some kit "png" files were JPEG bytes. Sniff so the battle background decodes.
    if data[:3] == b'\xff\xd8\xff':
        mime = 'image/jpeg'
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        mime = 'image/png'
    else:
        mime = mime_map.get(ext, 'application/octet-stream')
    resp = make_response(data)
    resp.headers['Content-Type'] = mime
    if filename.startswith('mocks/ui-direction/kit/'):
        resp.headers['Cache-Control'] = 'no-cache'
    else:
        resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp

@app.route('/assets-c/<path:filename>')
def serve_assets(filename):
    html_dir = os.path.join(os.path.dirname(__file__), '')
    path = os.path.join(html_dir, 'assets-c', filename)
    # Prevent directory traversal
    path = os.path.normpath(path)
    if not path.startswith(os.path.normpath(os.path.join(html_dir, 'assets-c'))):
        return jsonify({'error': 'forbidden'}), 403
    if os.path.isfile(path):
        ext = os.path.splitext(filename)[1]
        mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon'}
        ct = mime_map.get(ext, 'application/octet-stream')
        with open(path, 'rb') as f:
            resp = make_response(f.read())
        resp.headers['Content-Type'] = ct
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
    if 'starter_granted' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN starter_granted INTEGER DEFAULT 0")
    
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
    if 'pending_approval' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN pending_approval INTEGER DEFAULT 0")
    if 'pending_rewards' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN pending_rewards TEXT")
    if 'reject_reason' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN reject_reason TEXT")
    
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
    
    _canonicalize_building_def_materials(db)
    _apply_guild_onboard_recipe(db)
    _migrate_inventory_item_types(db)
    db.execute("""
        CREATE TABLE IF NOT EXISTS farm_claims (
            kid_id     INTEGER PRIMARY KEY,
            claim_date TEXT    NOT NULL,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        )
    """)
    
    # Character stats (experience, level, abilities)
    if 'experience' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN experience INTEGER DEFAULT 0")
    if 'level' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN level INTEGER DEFAULT 1")
    if 'stat_points' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN stat_points INTEGER DEFAULT 0")
    if 'ability_str' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN ability_str INTEGER DEFAULT 0")   # 臂力 💪
    if 'ability_int' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN ability_int INTEGER DEFAULT 0")   # 知識 📖
    if 'ability_spd' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN ability_spd INTEGER DEFAULT 0")   # 速度 💨
    if 'ability_crt' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN ability_crt INTEGER DEFAULT 0")   # 創意 🎨
    if 'ability_brv' not in kid_cols:
        db.execute("ALTER TABLE kids ADD COLUMN ability_brv INTEGER DEFAULT 0")   # 勇氣 ⚔️
    
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
            pending_approval INTEGER DEFAULT 0,
            pending_rewards TEXT,
            reject_reason TEXT,
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

        CREATE TABLE IF NOT EXISTS skill_defs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            icon            TEXT    DEFAULT '💥',
            mp_cost         INTEGER DEFAULT 3,
            bldg_def_id     INTEGER NOT NULL,
            level_required  INTEGER DEFAULT 1,
            target          TEXT    DEFAULT 'enemy',
            description     TEXT    DEFAULT '',
            base_value      REAL    DEFAULT 0,
            per_level       REAL    DEFAULT 0,
            attr_scale      TEXT    DEFAULT 'none',
            effect_type     TEXT    DEFAULT 'damage',
            FOREIGN KEY (bldg_def_id) REFERENCES building_defs(id) ON DELETE CASCADE
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

        CREATE TABLE IF NOT EXISTS monsters (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            icon        TEXT NOT NULL,
            hp          INTEGER NOT NULL,
            atk         INTEGER NOT NULL,
            def         INTEGER NOT NULL,
            region_id   INTEGER NOT NULL,
            gold_reward INTEGER DEFAULT 20,
            mat_reward  TEXT DEFAULT '{}',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS boss_progress (
            kid_id         INTEGER NOT NULL,
            region_id      INTEGER NOT NULL,
            first_kill     INTEGER DEFAULT 0,
            last_summon_at TEXT,
            last_win_at    TEXT,
            PRIMARY KEY (kid_id, region_id)
        );

        CREATE TABLE IF NOT EXISTS daily_battles (
            kid_id      INTEGER NOT NULL,
            region_id   INTEGER NOT NULL,
            battle_date TEXT NOT NULL,
            PRIMARY KEY (kid_id, region_id, battle_date)
        );

        CREATE TABLE IF NOT EXISTS drop_pity (
            kid_id INTEGER PRIMARY KEY,
            count  INTEGER DEFAULT 0
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

        CREATE TABLE IF NOT EXISTS town_tiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            cell_x      INTEGER NOT NULL,
            cell_y      INTEGER NOT NULL,
            tile_type   TEXT    NOT NULL DEFAULT 'road',
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

    # Seed monsters if empty
    db4 = sqlite3.connect(DB_PATH)
    if db4.execute("SELECT COUNT(*) FROM monsters").fetchone()[0] == 0:
        db4.execute("INSERT INTO monsters (id,name,icon,hp,atk,def,region_id,gold_reward,mat_reward) VALUES (1,'野狼','🐺',30,5,0,1,20,'{\"wood\":2}')")
        db4.execute("INSERT INTO monsters (id,name,icon,hp,atk,def,region_id,gold_reward,mat_reward) VALUES (2,'白熊','🐻‍❄️',60,10,2,2,40,'{\"brick\":2,\"fur\":1}')")
        db4.execute("INSERT INTO monsters (id,name,icon,hp,atk,def,region_id,gold_reward,mat_reward) VALUES (3,'巨蠍','🦂',100,15,5,3,80,'{\"gear\":1,\"gem\":1}')")
        db4.commit()
    db4.close()


def _clean_stale_expeditions():
    """Mark running expeditions past their end_time as completed (auto-timeout)."""
    try:
        db = sqlite3.connect(DB_PATH)
        now_iso = datetime.utcnow().isoformat() + 'Z'
        cur = db.execute("UPDATE expeditions SET status='completed' WHERE status='running' AND end_time < ?", (now_iso,))
        if cur.rowcount > 0:
            print(f'   Cleaned {cur.rowcount} stale expedition(s)')
        db.commit()
        db.close()
    except Exception as e:
        print(f'   [warn] _clean_stale_expeditions: {e}')


def _clean_stale_expeditions_db(db):
    """Mark stale running expeditions (past end_time) as completed. Takes a live db connection."""
    now_iso = datetime.utcnow().isoformat() + 'Z'
    db.execute("UPDATE expeditions SET status='completed' WHERE status='running' AND end_time < ?", (now_iso,))
    db.commit()

def seed_building_defs():
    """Insert default building definitions if empty."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    if db.execute("SELECT COUNT(*) FROM building_defs").fetchone()[0] > 0:
        db.close()
        return
    defs = [
        ("📚", "圖書館", 100, '{"wood":5}', "任務 +2⭐", "task_bonus", "[2,4,6,10,15]", 5, None),
        ("🏋️", "健身室", 200, '{"wood":10,"brick":5}', "連續保護", "streak_protect", "[1,1,1,1,1]", 5, None),
        ("🌾", "農場", 300, '{"wood":15,"brick":10}', "每日 +5🪙", "daily_gold", "[5,10,15,25,40]", 5, None),
        ("🏪", "商店", 500, '{"wood":20,"brick":15,"gear":5}', "獎勵 -10%", "discount", "[0.9,0.85,0.8,0.75,0.7]", 5, None),
        ("🏥", "醫院", 400, '{"wood":15,"brick":20}', "探險回復 x2", "expedition_recovery", "[2,3,4,5,6]", 5, None),
        ("🗺️", "探險公會", GUILD_COST_GOLD, DEFAULT_GUILD_MATERIALS, "解鎖探險", "unlock_explore", "[1,1,1,1,1]", 5, None),
        ("🔨", "工坊", 350, '{"wood":20,"gear":5}', "建築速度 x2", "build_speed", "[2,3,4,5,6]", 5, None),
        ("🗼", "燈塔", 800, '{"wood":30,"brick":25,"gear":15,"gem":3}', "探險範圍 +1", "explore_range", "[1,2,2,3,3]", 5, "r3"),
        ("⚔️", "競技場", 1000, '{"wood":40,"brick":30,"gear":20,"gem":5}', "探險金幣 x2", "expedition_gold", "[2,3,4,5,6]", 5, "r4"),
        ("🔭", "天文台", 1500, '{"wood":50,"brick":40,"gear":25,"gem":10,"glass":3}', "新區域發現率", "discovery_rate", "[1.5,2,2.5,3,4]", 5, "r5"),
    ]
    for d in defs:
        db.execute(
            "INSERT INTO building_defs (icon, name, cost_gold, materials, effect, buff_type, buff_vals, max_level, unlock_region) VALUES (?,?,?,?,?,?,?,?,?)",
            (d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8])
        )
    _canonicalize_building_def_materials(db)
    _apply_guild_onboard_recipe(db)
    db.commit()
    db.close()

def seed_skill_defs():
    """Insert default skill definitions if empty."""
    db = sqlite3.connect(DB_PATH)
    if db.execute("SELECT COUNT(*) FROM skill_defs").fetchone()[0] > 0:
        db.close()
        return
    # bldg_def_id: 1=圖書館,2=健身室,3=農場,4=商店,5=醫院,6=探險公會,7=工坊,8=燈塔,9=競技場,10=天文台
    defs = [
        # 健身室 (2)
        ('蓄力', '🔥', 3, 2, 1, 'self', '下次攻擊 1.5 倍', 0, 0, 'none', 'buff'),
        ('重擊', '💪', 5, 2, 2, 'enemy', '強力物理攻擊', 20, 5, 'str', 'damage'),
        ('連擊', '⚡', 7, 2, 4, 'enemy', '連續攻擊 2 次', 16, 4, 'str', 'damage'),
        # 醫院 (5)
        ('繃帶', '🩹', 3, 5, 1, 'ally', '小回復', 12, 4, 'int', 'heal'),
        ('急救', '💚', 8, 5, 3, 'ally', '中回復', 25, 7, 'int', 'heal'),
        ('全體治療', '🌿', 14, 5, 5, 'all_allies', '全體回復', 18, 5, 'int', 'heal'),
        # 競技場 (9)
        ('橫掃', '🗡️', 6, 9, 2, 'all_enemies', '全體物理攻擊', 15, 4, 'str', 'damage'),
        ('挑釁', '🛡️', 4, 9, 4, 'self', '強制敵方攻擊自己', 0, 0, 'none', 'buff'),
        ('必殺', '💥', 10, 9, 5, 'enemy', '對低血量敵人特大傷害', 32, 8, 'str', 'damage'),
        # 圖書館 (1)
        ('火球', '🔥', 6, 1, 2, 'enemy', '魔法攻擊', 20, 5, 'int', 'damage'),
        ('冰凍', '❄️', 8, 1, 4, 'enemy', '魔法攻擊 + 減速', 28, 7, 'int', 'damage'),
        # 探險公會 (6)
        ('偵察', '👁️', 2, 6, 2, 'enemy', '查看怪物弱點', 0, 0, 'none', 'utility'),
        ('迴避', '🏃', 3, 6, 4, 'self', '完全回避下次攻擊', 0, 0, 'none', 'buff'),
        # 工坊 (7)
        ('修復', '🔧', 4, 7, 2, 'ally', '回復 MP', 10, 3, 'int', 'heal'),
        ('強化', '🛡️', 5, 7, 4, 'ally', '提升防禦力', 3, 1, 'none', 'buff'),
    ]
    for d in defs:
        db.execute(
            "INSERT INTO skill_defs (name, icon, mp_cost, bldg_def_id, level_required, target, description, base_value, per_level, attr_scale, effect_type) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            d
        )
    db.commit()
    db.close()


SKILL_BALANCE = {
    '重擊': (20, 5), '連擊': (16, 4), '繃帶': (12, 4), '急救': (25, 7),
    '全體治療': (18, 5), '橫掃': (15, 4), '必殺': (32, 8), '火球': (20, 5),
    '冰凍': (28, 7), '修復': (10, 3),
}


def rebalance_skills(db):
    """Apply skill balance values to skill_defs (base_value + per_level)."""
    for name, (base, per_lv) in SKILL_BALANCE.items():
        db.execute("UPDATE skill_defs SET base_value=?, per_level=? WHERE name=?",
                   (base, per_lv, name))
    db.commit()

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
        require_approval INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    parent_cols = [row[1] for row in db.execute("PRAGMA table_info(parents)").fetchall()]
    if 'require_approval' not in parent_cols:
        db.execute("ALTER TABLE parents ADD COLUMN require_approval INTEGER DEFAULT 0")
    
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
    
    # Do not seed a default admin account. Use KIDS_TOWN_BOOTSTRAP_ADMIN_PASSWORD
    # (and optional KIDS_TOWN_BOOTSTRAP_ADMIN_USERNAME) after migrate if needed.

    db.commit()
    db.close()
    print("✅ migrate_db_v3 done")


def migrate_db_v4():
    """Add task_completions table for per-kid completion of global (kid_id=NULL) tasks."""
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS task_completions (
            task_id      INTEGER NOT NULL,
            kid_id       INTEGER NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pending      INTEGER DEFAULT 0,
            pending_rewards TEXT,
            PRIMARY KEY (task_id, kid_id),
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        )
    """)
    tc_cols = [row[1] for row in db.execute("PRAGMA table_info(task_completions)").fetchall()]
    if 'pending' not in tc_cols:
        db.execute("ALTER TABLE task_completions ADD COLUMN pending INTEGER DEFAULT 0")
    if 'pending_rewards' not in tc_cols:
        db.execute("ALTER TABLE task_completions ADD COLUMN pending_rewards TEXT")
    db.commit()
    db.close()


def _bcrypt_rounds():
    return 4 if app.config.get('TESTING') else 12


def hash_password(password):
    """Salted bcrypt hash for parent/admin passwords and kid PINs."""
    pw = (password or '').encode('utf-8')
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=_bcrypt_rounds())).decode('utf-8')


def _looks_bcrypt(stored):
    return bool(stored) and (stored.startswith('$2') or stored.startswith('$argon2'))


def _looks_sha256_hex(stored):
    return bool(stored) and len(stored) == 64 and all(c in '0123456789abcdef' for c in stored.lower())


def verify_password(password, stored):
    """Check bcrypt, argon2-prefix, legacy SHA-256, or (last) plaintext."""
    if stored is None or password is None:
        return False
    if stored.startswith('$2'):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
        except (ValueError, TypeError):
            return False
    if stored.startswith('$argon2'):
        return False  # stored by an older experiment; not verified here
    if _looks_sha256_hex(stored):
        return hashlib.sha256(password.encode('utf-8')).hexdigest() == stored.lower()
    return stored == password


def _needs_rehash(stored):
    return not _looks_bcrypt(stored)


def public_kid(row):
    d = row_to_dict(row) if not isinstance(row, dict) else dict(row)
    if not d:
        return d
    d.pop('pin', None)
    d.pop('password', None)
    return d


def _norm_api_path():
    p = request.path or ''
    if len(p) > 1 and p.endswith('/'):
        p = p[:-1]
    return p


def current_actor():
    role = session.get('role')
    if not role:
        return None
    return {
        'role': role,
        'user_id': session.get('user_id'),
        'kid_id': session.get('kid_id'),
        'parent_id': session.get('parent_id'),
        'admin_id': session.get('admin_id'),
        'must_change_password': bool(session.get('must_change_password')),
    }


def _set_session(role, user_id, **extra):
    session.clear()
    session['role'] = role
    session['user_id'] = user_id
    for k, v in extra.items():
        session[k] = v
    session.modified = True


def parent_owns_kid(parent_id, kid_id):
    if parent_id is None or kid_id is None:
        return False
    row = get_db().execute(
        "SELECT 1 FROM parent_kid WHERE parent_id=? AND kid_id=?",
        (parent_id, kid_id),
    ).fetchone()
    return row is not None


def _truthy_flag(value):
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)


def _set_parent_require_approval(db, parent_id, flag):
    db.execute(
        "UPDATE parents SET require_approval=? WHERE id=?",
        (1 if _truthy_flag(flag) else 0, parent_id),
    )
    db.commit()


def _kid_requires_approval(db, kid_id):
    """GAMEPLAY_REDESIGN §6.7: any owning parent with require_approval=1."""
    if not kid_id:
        return False
    row = db.execute(
        """SELECT 1 FROM parents p
           JOIN parent_kid pk ON pk.parent_id = p.id
           WHERE pk.kid_id=? AND COALESCE(p.require_approval, 0)=1
           LIMIT 1""",
        (kid_id,),
    ).fetchone()
    return bool(row)


def _unauthorized():
    return jsonify({'error': 'Unauthorized'}), 401


def _forbidden():
    return jsonify({'error': 'Forbidden'}), 403


def bootstrap_admin_if_configured():
    """Create one admin only when a non-default bootstrap password is provided."""
    raw = os.environ.get('KIDS_TOWN_BOOTSTRAP_ADMIN_PASSWORD') or ''
    if not raw or raw in ('admin123', 'password', 'admin'):
        return
    username = (os.environ.get('KIDS_TOWN_BOOTSTRAP_ADMIN_USERNAME') or 'site-admin').strip().lower()
    if username == 'admin' and raw == 'admin123':
        return
    db = sqlite3.connect(DB_PATH)
    try:
        if db.execute("SELECT id FROM admins LIMIT 1").fetchone():
            return
        db.execute(
            "INSERT INTO admins (username, password, name, role) VALUES (?, ?, ?, ?)",
            (username, hash_password(raw), 'Bootstrap Admin', 'super_admin'),
        )
        db.commit()
        print(f'🔐 Bootstrapped admin username={username} (password not printed)')
    finally:
        db.close()


def _is_default_admin_login(username, password):
    return username == 'admin' and password == 'admin123'


@app.before_request
def gate_api_auth():
    """Require a server session on write APIs and sensitive reads. Public: health + login/register."""
    if request.method == 'OPTIONS':
        return None
    path = _norm_api_path()
    if not path.startswith('/api'):
        return None
    if (request.method, path) in PUBLIC_API:
        return None

    actor = current_actor()
    mutating = request.method in ('POST', 'PUT', 'PATCH', 'DELETE')
    sensitive_get = request.method == 'GET' and (
        path == '/api/kids'
        or path == '/api/dev-dashboard'
        or path == '/api/auth/parent-kids'
        or path.startswith('/api/kids/')
        or path.startswith('/api/tasks')
        or path.startswith('/api/family/settings')
        or path.startswith('/api/auth/family-settings')
        or path.startswith('/api/parents/')
        or path.startswith('/api/stats')
        or path.startswith('/api/activity')
        or path.startswith('/api/leaderboard')
        or path.startswith('/api/transactions')
        or path.startswith('/api/savings-goals')
    )
    if mutating or sensitive_get:
        if not actor:
            return _unauthorized()
        if actor.get('must_change_password') and mutating:
            return _forbidden()

    if not actor:
        return None

    # IDOR: /api/kids/<id>/... must match session kid, linked parent, or admin.
    m = re.match(r'^/api/kids/(\d+)(.*)$', path)
    if m:
        kid_id = int(m.group(1))
        rest = m.group(2) or ''
        if actor['role'] == 'admin':
            if actor.get('must_change_password'):
                return _forbidden()
        elif actor['role'] == 'kid':
            if mutating and rest in KID_DENIED_WRITE_SUFFIXES:
                return _forbidden()
            if actor.get('kid_id') != kid_id:
                return _forbidden()
        elif actor['role'] == 'parent':
            if not parent_owns_kid(actor.get('parent_id'), kid_id):
                return _forbidden()
            if mutating and rest == '/inventory/add':
                return _forbidden()
        else:
            return _forbidden()

    if path == '/api/kids' and request.method in ('POST', 'DELETE'):
        if actor['role'] != 'admin':
            return _forbidden()
    if re.match(r'^/api/kids/\d+$', path) and request.method == 'DELETE':
        if actor['role'] != 'admin':
            return _forbidden()
    return None


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
    actor = current_actor()
    if not actor:
        return _unauthorized()
    db = get_db()
    if actor['role'] == 'kid':
        rows = db.execute(
            "SELECT * FROM kids WHERE id=? ORDER BY id ASC", (actor['kid_id'],)
        ).fetchall()
    elif actor['role'] == 'parent':
        rows = db.execute(
            """SELECT k.* FROM kids k
               JOIN parent_kid pk ON k.id = pk.kid_id
               WHERE pk.parent_id=?
               ORDER BY k.points DESC, k.id ASC""",
            (actor['parent_id'],),
        ).fetchall()
    elif actor['role'] == 'admin':
        rows = db.execute("SELECT * FROM kids ORDER BY points DESC, id ASC").fetchall()
    else:
        return _forbidden()
    return jsonify([public_kid(r) for r in rows])

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
    actor = current_actor()
    if not actor:
        return _unauthorized()
    flag = data.get('require_approval')
    nested = data.get('family_settings')
    if flag is None and isinstance(nested, dict):
        flag = nested.get('require_approval')
    if flag is not None:
        if actor['role'] not in ('parent', 'admin'):
            return _forbidden()
        parent_id = actor.get('parent_id')
        if actor['role'] == 'parent' and not parent_id:
            return _forbidden()
        if parent_id:
            _set_parent_require_approval(get_db(), parent_id, flag)
        kid_id = data.get('kid_id')
        theme = data.get('theme')
        if kid_id is not None and theme is not None:
            get_db().execute("UPDATE kids SET theme=? WHERE id=?", (theme, kid_id))
            get_db().commit()
        return jsonify({'ok': True, 'require_approval': _truthy_flag(flag)}), 200
    kid_id = data.get('kid_id')
    theme = data.get('theme', '')
    if not kid_id:
        return jsonify({'error': 'kid_id required'}), 400
    db = get_db()
    db.execute("UPDATE kids SET theme=? WHERE id=?", (theme, kid_id))
    db.commit()
    return jsonify({'ok': True}), 200


@app.route('/api/family/settings', methods=['GET', 'POST'])
@app.route('/api/auth/family-settings', methods=['GET', 'POST'])
def family_settings():
    """GAMEPLAY_REDESIGN §6.7 family require_approval toggle (default off)."""
    actor = current_actor()
    if not actor:
        return _unauthorized()
    if actor['role'] not in ('parent', 'admin'):
        return _forbidden()
    db = get_db()
    parent_id = actor.get('parent_id')
    if request.method == 'GET':
        flag = False
        if parent_id:
            row = db.execute(
                "SELECT require_approval FROM parents WHERE id=?", (parent_id,)
            ).fetchone()
            flag = bool(row['require_approval']) if row else False
        return jsonify({'ok': True, 'require_approval': flag})
    data = request.get_json(silent=True) or {}
    if 'require_approval' not in data:
        return jsonify({'error': 'require_approval required'}), 400
    if actor['role'] == 'parent' and not parent_id:
        return _forbidden()
    if parent_id:
        _set_parent_require_approval(db, parent_id, data.get('require_approval'))
    return jsonify({'ok': True, 'require_approval': _truthy_flag(data.get('require_approval'))}), 200


@app.route('/api/parents/<int:parent_id>/settings', methods=['GET', 'POST'])
def parent_settings(parent_id):
    actor = current_actor()
    if not actor:
        return _unauthorized()
    if actor['role'] == 'kid':
        return _forbidden()
    if actor['role'] == 'parent' and actor.get('parent_id') != parent_id:
        return _forbidden()
    if actor['role'] not in ('parent', 'admin'):
        return _forbidden()
    db = get_db()
    if request.method == 'GET':
        row = db.execute(
            "SELECT require_approval FROM parents WHERE id=?", (parent_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Parent not found'}), 404
        return jsonify({'ok': True, 'require_approval': bool(row['require_approval'])})
    data = request.get_json(silent=True) or {}
    flag = data.get('require_approval')
    if flag is None:
        flag = data.get('approve_rewards')
    if flag is None:
        return jsonify({'error': 'require_approval required'}), 400
    _set_parent_require_approval(db, parent_id, flag)
    return jsonify({'ok': True, 'require_approval': _truthy_flag(flag)}), 200

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

    new_points = max(0, kid['points'] + amount)
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

# -- Experience & Level --

EXP_PER_LEVEL = 25  # base exp needed per level (cap 1000 → gentle curve)

def calc_level(exp):
    """Calculate level from total experience. Lv.1 = 0exp, Lv.2 = 100exp, Lv.3 = 300exp, Lv.4 = 600exp..."""
    level = 1
    while exp >= level * EXP_PER_LEVEL:
        exp -= level * EXP_PER_LEVEL
        level += 1
    return level, exp  # (level, exp_in_current_level)

def exp_for_next_level(level):
    """How much exp needed to go from this level to next."""
    return level * EXP_PER_LEVEL


def exp_reward_for_tier(tier):
    """EXP reward per won battle = 15 + tier*10."""
    return 15 + max(1, tier) * 10


# GAMEPLAY_REDESIGN §6.2 — write-side aliases. mystery_box is Phase 1 stop-issue.
ITEM_TYPE_ALIASES = {
    'iron': 'gear',
    'star_shard': 'glass',
    'star_fragment': 'gem',
    'star_stone': 'gem',
}
STOPPED_ITEM_TYPES = frozenset({'mystery_box'})
PHASE1_LOCKED_REGIONS = frozenset({4, 5})
EXPLORE_FEE_BY_REGION = {1: 10, 2: 20, 3: 30}
EXPLORE_GOLD_REWARD_RANGE = {1: (6, 10), 2: (12, 18), 3: (18, 28)}
HK_TZ = timezone(timedelta(hours=8))
# GAMEPLAY_REDESIGN §6.6 / §7 / §9 Q4 — 入局包 (onboarding pack)
GUILD_COST_GOLD = 150
DEFAULT_GUILD_MATERIALS = '{"wood":10,"brick":5}'
STARTER_POINTS = 120
STARTER_MATERIALS = {'wood': 8, 'brick': 5}
# Preview demo only. Other kids still get the 120-gold starter pack.
PREVIEW_KID_USERNAME = 'preview_kid'
PREVIEW_KID_NAME = 'Preview'
PREVIEW_KID_PIN = '2468'
PREVIEW_MIN_POINTS = 200
PREVIEW_MIN_LEVEL = 2
PREVIEW_MIN_EXPERIENCE = 25  # calc_level(25) is Lv.2, so region 1 can open


def canonicalize_item_type(item_type):
    """Map legacy inventory ids to canonical ones. mystery_box → None (do not issue)."""
    if not item_type:
        return None
    if item_type in STOPPED_ITEM_TYPES:
        return None
    return ITEM_TYPE_ALIASES.get(item_type, item_type)


def add_item(kid_id, item_type, qty, db):
    """Grant inventory, merging onto the canonical item_type. Returns stored id or None."""
    canonical = canonicalize_item_type(item_type)
    if not canonical or not qty:
        return None
    qty = int(qty)
    if qty <= 0:
        return None
    existing = db.execute(
        "SELECT id FROM inventory WHERE kid_id=? AND item_type=?",
        (kid_id, canonical),
    ).fetchone()
    if existing:
        db.execute("UPDATE inventory SET quantity=quantity+? WHERE id=?", (qty, existing['id']))
    else:
        db.execute(
            "INSERT INTO inventory (kid_id, item_type, quantity) VALUES (?,?,?)",
            (kid_id, canonical, qty),
        )
    return canonical


def _canonicalize_material_dict(mats):
    out = {}
    if not isinstance(mats, dict):
        return out
    for key, qty in mats.items():
        canonical = canonicalize_item_type(key)
        if not canonical:
            continue
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        out[canonical] = out.get(canonical, 0) + qty
    return out


def _canonicalize_building_def_materials(db):
    """Normalize seed / migrated recipe keys; repair empty guild materials."""
    bdefs = db.execute("SELECT id, name, materials FROM building_defs").fetchall()
    for bd in bdefs:
        bid = bd['id'] if not isinstance(bd, tuple) else bd[0]
        name = bd['name'] if not isinstance(bd, tuple) else bd[1]
        raw = bd['materials'] if not isinstance(bd, tuple) else bd[2]
        try:
            mats = json.loads(raw or '{}')
        except (json.JSONDecodeError, TypeError):
            mats = {}
        new_mats = _canonicalize_material_dict(mats)
        if name == '探險公會' and not new_mats:
            new_mats = json.loads(DEFAULT_GUILD_MATERIALS)
        if new_mats != mats:
            db.execute(
                "UPDATE building_defs SET materials=? WHERE id=?",
                (json.dumps(new_mats, ensure_ascii=False), bid),
            )
    db.commit()


def _apply_guild_onboard_recipe(db):
    """GAMEPLAY_REDESIGN §6.6 / §9 Q4: 探險公會 is 150 gold + wood×10 + brick×5 (no gear)."""
    try:
        db.execute(
            "UPDATE building_defs SET cost_gold=?, materials=? WHERE name=?",
            (GUILD_COST_GOLD, DEFAULT_GUILD_MATERIALS, '探險公會'),
        )
    except sqlite3.OperationalError:
        return


def grant_starter_pack_once(db, kid_id):
    """GAMEPLAY_REDESIGN §6.6: one-time 120 gold + wood×8 + brick×5 per kid.

    Idempotent: if starter_granted is already truthy, do not add again.
    """
    try:
        row = db.execute(
            "SELECT starter_granted FROM kids WHERE id=?", (kid_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    if row['starter_granted']:
        return False
    db.execute(
        "UPDATE kids SET points = points + ?, starter_granted=1 WHERE id=?",
        (STARTER_POINTS, kid_id),
    )
    for item_type, qty in STARTER_MATERIALS.items():
        add_item(kid_id, item_type, qty, db)
    return True


def _ensure_building_placement_columns(db):
    """buildings.cell_x/cell_y/stored exist on live DBs; add them if a fresh file lacks them."""
    cols = [row[1] for row in db.execute("PRAGMA table_info(buildings)").fetchall()]
    if 'cell_x' not in cols:
        db.execute("ALTER TABLE buildings ADD COLUMN cell_x INTEGER DEFAULT 0")
    if 'cell_y' not in cols:
        db.execute("ALTER TABLE buildings ADD COLUMN cell_y INTEGER DEFAULT 0")
    if 'stored' not in cols:
        db.execute("ALTER TABLE buildings ADD COLUMN stored INTEGER DEFAULT 0")


def _preview_guild_cell(db, kid_id):
    """First free 2×2 plot, preferring the usual guild cell (6, 0)."""
    occupied = set()
    for row in db.execute(
        "SELECT cell_x, cell_y FROM buildings WHERE kid_id=? AND COALESCE(stored, 0)=0",
        (kid_id,),
    ):
        occupied.add((row['cell_x'] or 0, row['cell_y'] or 0))
    candidates = [(6, 0)] + [(x, y) for y in range(0, 13) for x in range(0, 21)]
    for x, y in candidates:
        if all((x + dx, y + dy) not in occupied for dy in range(2) for dx in range(2)):
            return x, y
    return 6, 0


def ensure_preview_kid(db):
    """Give the Preview demo kid enough gold and a placed exploration guild.

    Idempotent. Other kids are untouched. An existing PIN is not replaced.
    Gold is raised to at least PREVIEW_MIN_POINTS and never lowered.
    Level is raised to at least 2 so region 1 wilderness can start.
    """
    _ensure_building_placement_columns(db)
    row = db.execute(
        "SELECT id, points, level, experience FROM kids WHERE username=?",
        (PREVIEW_KID_USERNAME,),
    ).fetchone()
    created = False
    if not row:
        cur = db.execute(
            "INSERT INTO kids (name, username, avatar, color, points, level, experience, starter_granted) "
            "VALUES (?, ?, '👦', '#3b82f6', ?, ?, ?, 1)",
            (
                PREVIEW_KID_NAME,
                PREVIEW_KID_USERNAME,
                PREVIEW_MIN_POINTS,
                PREVIEW_MIN_LEVEL,
                PREVIEW_MIN_EXPERIENCE,
            ),
        )
        kid_id = cur.lastrowid
        db.execute(
            "INSERT INTO kid_auth (kid_id, pin) VALUES (?, ?)",
            (kid_id, hash_password(PREVIEW_KID_PIN)),
        )
        for item_type, qty in STARTER_MATERIALS.items():
            add_item(kid_id, item_type, qty, db)
        created = True
    else:
        kid_id = row['id']
        points = row['points'] or 0
        level = row['level'] or 1
        experience = row['experience'] or 0
        if points < PREVIEW_MIN_POINTS:
            db.execute(
                "UPDATE kids SET points=? WHERE id=?",
                (PREVIEW_MIN_POINTS, kid_id),
            )
        if level < PREVIEW_MIN_LEVEL:
            db.execute(
                "UPDATE kids SET level=?, experience=? WHERE id=?",
                (PREVIEW_MIN_LEVEL, max(experience, PREVIEW_MIN_EXPERIENCE), kid_id),
            )

    guild = db.execute(
        "SELECT id FROM building_defs WHERE name=? OR buff_type='unlock_explore' ORDER BY id LIMIT 1",
        ('探險公會',),
    ).fetchone()
    if guild and not has_active_guild(kid_id, db):
        stored = db.execute(
            "SELECT id FROM buildings WHERE kid_id=? AND def_id=? AND COALESCE(stored, 0)=1 LIMIT 1",
            (kid_id, guild['id']),
        ).fetchone()
        if stored:
            cell_x, cell_y = _preview_guild_cell(db, kid_id)
            db.execute(
                "UPDATE buildings SET stored=0, cell_x=?, cell_y=? WHERE id=?",
                (cell_x, cell_y, stored['id']),
            )
        else:
            cell_x, cell_y = _preview_guild_cell(db, kid_id)
            db.execute(
                "INSERT INTO buildings (kid_id, def_id, plot_idx, level, cell_x, cell_y, stored) "
                "VALUES (?, ?, 0, 1, ?, ?, 0)",
                (kid_id, guild['id'], cell_x, cell_y),
            )
    db.commit()
    return {'kid_id': kid_id, 'created': created}


def _migrate_inventory_item_types(db):
    """Merge legacy inventory rows onto canonical ids. Leave mystery_box in-bag."""
    try:
        rows = db.execute("SELECT id, kid_id, item_type, quantity FROM inventory").fetchall()
    except sqlite3.OperationalError:
        return
    for row in rows:
        canonical = canonicalize_item_type(row['item_type'])
        if not canonical or canonical == row['item_type']:
            continue
        existing = db.execute(
            "SELECT id FROM inventory WHERE kid_id=? AND item_type=?",
            (row['kid_id'], canonical),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE inventory SET quantity=quantity+? WHERE id=?",
                (row['quantity'], existing['id']),
            )
            db.execute("DELETE FROM inventory WHERE id=?", (row['id'],))
        else:
            db.execute("UPDATE inventory SET item_type=? WHERE id=?", (canonical, row['id']))
    db.commit()


def get_building_buff(kid_id, buff_type, db):
    """Return buff_vals[level-1] for an unstored building, or None."""
    row = db.execute(
        """
        SELECT b.level, bd.buff_vals
        FROM buildings b
        JOIN building_defs bd ON b.def_id = bd.id
        WHERE b.kid_id=? AND bd.buff_type=? AND COALESCE(b.stored, 0)=0
        ORDER BY b.level DESC
        LIMIT 1
        """,
        (kid_id, buff_type),
    ).fetchone()
    if not row:
        return None
    try:
        vals = json.loads(row['buff_vals'] or '[]')
    except (json.JSONDecodeError, TypeError):
        return None
    if not vals:
        return None
    idx = max(0, min(int(row['level'] or 1) - 1, len(vals) - 1))
    return vals[idx]


def xp_bar_percent(experience_in_level, experience_for_next):
    """HUD fill: in-level / for-next, capped at 100. for_next==0 → 100."""
    try:
        for_next = float(experience_for_next)
    except (TypeError, ValueError):
        return 100
    if for_next <= 0:
        return 100
    try:
        in_level = float(experience_in_level)
    except (TypeError, ValueError):
        in_level = 0
    return min(100, round(in_level / for_next * 100))


def _row_get(row, key, default=None):
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return default


def _abilities_payload(kid):
    """5-ability HUD dict. Never read dropped ability_atk."""
    return {
        'str': _row_get(kid, 'ability_str', 0) or 0,
        'int': _row_get(kid, 'ability_int', 0) or 0,
        'spd': _row_get(kid, 'ability_spd', 0) or 0,
        'crt': _row_get(kid, 'ability_crt', 0) or 0,
        'brv': _row_get(kid, 'ability_brv', 0) or 0,
    }


def kid_hud(kid):
    """Kid row plus in-level XP fields for ceremony / HUD."""
    data = row_to_dict(kid) or {}
    exp = data.get('experience') or 0
    level = data.get('level') or 1
    _, exp_in = calc_level(exp)
    for_next = exp_for_next_level(level)
    data['experience_in_level'] = exp_in
    data['experience_for_next'] = for_next
    data['xp_bar_percent'] = xp_bar_percent(exp_in, for_next)
    return data


def hk_today_str():
    return datetime.now(HK_TZ).date().isoformat()


def region_content_locked(region_id):
    try:
        return int(region_id) in PHASE1_LOCKED_REGIONS
    except (TypeError, ValueError):
        return False


def parse_unlock_region(value):
    if not value:
        return None
    text = str(value).strip().lower()
    if text.startswith('r') and text[1:].isdigit():
        return int(text[1:])
    if text.isdigit():
        return int(text)
    return None


def has_active_guild(kid_id, db):
    row = db.execute(
        """
        SELECT b.id FROM buildings b
        JOIN building_defs bd ON b.def_id = bd.id
        WHERE b.kid_id=? AND COALESCE(b.stored, 0)=0
          AND (bd.buff_type='unlock_explore' OR bd.name='探險公會')
        LIMIT 1
        """,
        (kid_id,),
    ).fetchone()
    return row is not None


def discounted_gold_cost(kid_id, base_cost, db):
    """Shop discount applies to gold only. Minimum 1. No shop → full price."""
    try:
        cost = int(base_cost or 0)
    except (TypeError, ValueError):
        cost = 0
    discount = get_building_buff(kid_id, 'discount', db)
    if discount is None:
        return cost
    try:
        return max(1, math.floor(cost * float(discount)))
    except (TypeError, ValueError):
        return cost


def building_unlock_error(kid_id, unlock_region, db):
    """Return (error_code, extra) if the building cannot be placed, else (None, None)."""
    region_num = parse_unlock_region(unlock_region)
    if region_num is None:
        return None, None
    if region_content_locked(region_num):
        return 'region_locked', region_num
    explored = db.execute(
        "SELECT 1 FROM explored_regions WHERE kid_id=? AND region_id=?",
        (kid_id, region_num),
    ).fetchone()
    if explored:
        return None, None
    won = db.execute(
        "SELECT 1 FROM daily_battles WHERE kid_id=? AND region_id=?",
        (kid_id, region_num),
    ).fetchone()
    if won:
        return None, None
    try:
        boss = db.execute(
            "SELECT 1 FROM boss_progress WHERE kid_id=? AND region_id=? AND first_kill=1",
            (kid_id, region_num),
        ).fetchone()
        if boss:
            return None, None
    except sqlite3.OperationalError:
        pass
    return 'unlock_region', region_num

@app.route('/api/kids/<int:kid_id>/experience', methods=['GET'])
def get_experience(kid_id):
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    current_level = kid['level']
    current_exp = kid['experience']
    _, exp_in_level = calc_level(current_exp)
    return jsonify({
        'id': kid['id'],
        'name': kid['name'],
        'level': current_level,
        'experience': current_exp,
        'experience_in_level': exp_in_level,
        'experience_for_next': exp_for_next_level(current_level),
        'stat_points': kid['stat_points'],
        'xp_bar_percent': xp_bar_percent(exp_in_level, exp_for_next_level(current_level)),
        'abilities': _abilities_payload(kid),
    })

@app.route('/api/kids/<int:kid_id>/experience', methods=['POST'])
def add_experience(kid_id):
    data = request.get_json(silent=True) or {}
    try:
        amount = int(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'amount must be an integer'}), 400
    if amount <= 0:
        return jsonify({'error': 'amount must be positive'}), 400
    
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    
    new_exp = kid['experience'] + amount
    new_level, _ = calc_level(new_exp)
    stat_gained = 0
    if new_level > kid['level']:
        stat_gained = new_level - kid['level']  # 1 stat point per level
    
    db.execute(
        "UPDATE kids SET experience = ?, level = ?, stat_points = stat_points + ? WHERE id = ?",
        (new_exp, new_level, stat_gained, kid_id)
    )
    db.execute(
        "INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
        (kid_id, amount, 'experience_gained')
    )
    db.commit()
    
    updated = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    _, exp_in_level = calc_level(updated['experience'])
    return jsonify({
        'id': updated['id'],
        'name': updated['name'],
        'level': updated['level'],
        'experience': updated['experience'],
        'experience_in_level': exp_in_level,
        'experience_for_next': exp_for_next_level(updated['level']),
        'stat_points': updated['stat_points'],
        'leveled_up': new_level > kid['level'],
        'levels_gained': new_level - kid['level'],
        'xp_bar_percent': xp_bar_percent(exp_in_level, exp_for_next_level(updated['level'])),
        'abilities': _abilities_payload(updated),
    })

# -- Ability Points Assignment --

ABILITY_FIELDS = {
    'str': 'ability_str',  # 臂力 💪
    'int': 'ability_int',  # 知識 📖
    'spd': 'ability_spd',  # 速度 💨
    'crt': 'ability_crt',  # 創意 🎨
    'brv': 'ability_brv',  # 勇氣 ⚔️
}

@app.route('/api/kids/<int:kid_id>/abilities/assign', methods=['POST'])
def assign_ability(kid_id):
    data = request.get_json(silent=True) or {}
    ability = data.get('ability', '')
    try:
        points = int(data.get('points', 1))
    except (ValueError, TypeError):
        return jsonify({'error': 'points must be an integer'}), 400
    
    if ability not in ABILITY_FIELDS:
        return jsonify({'error': f'Invalid ability. Valid: {",".join(ABILITY_FIELDS.keys())}'}), 400
    if points < 1:
        return jsonify({'error': 'points must be positive'}), 400
    
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    
    if kid['stat_points'] < points:
        return jsonify({'error': f'Not enough stat points. Available: {kid["stat_points"]}, needed: {points}'}), 400
    
    col = ABILITY_FIELDS[ability]
    db.execute(f"UPDATE kids SET stat_points = stat_points - ?, {col} = {col} + ? WHERE id = ?",
               (points, points, kid_id))
    db.commit()
    
    updated = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    return jsonify({
        'id': updated['id'],
        'name': updated['name'],
        'stat_points': updated['stat_points'],
        'abilities': _abilities_payload(updated),
    })

# -- Ability Buffs from Buildings --

BUILDING_ABILITY_MAP = {
    '健身室': 'str',    # Gym → +臂力 💪
    '競技場': 'str',    # Arena → +臂力 💪
    '圖書館': 'int',    # Library → +知識 📖
    '天文台': 'int',    # Observatory → +知識 📖
    '工坊':   'crt',    # Workshop → +創意 🎨
    '探險公會': 'brv',  # Expedition Guild → +勇氣 ⚔️
}

def calc_ability_buffs(db, kid_id):
    """Calculate bonus ability points from owned buildings."""
    buffs = {'str': 0, 'int': 0, 'spd': 0, 'crt': 0, 'brv': 0}
    rows = db.execute("""
        SELECT bd.name, b.level FROM buildings b
        JOIN building_defs bd ON b.def_id = bd.id
        WHERE b.kid_id = ?
    """, (kid_id,)).fetchall()
    for row in rows:
        ability = BUILDING_ABILITY_MAP.get(row['name'])
        if ability:
            buffs[ability] = buffs.get(ability, 0) + row['level'] * 2  # +2 per level
    # Speed buff from Arena also gives +1 per level
    for row in rows:
        if row['name'] == '競技場':
            buffs['spd'] = buffs.get('spd', 0) + row['level']  # +1 speed per level
    return buffs

@app.route('/api/kids/<int:kid_id>/abilities', methods=['GET'])
def get_abilities(kid_id):
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    
    base = {
        'str': kid['ability_str'],
        'int': kid['ability_int'],
        'spd': kid['ability_spd'],
        'crt': kid['ability_crt'],
        'brv': kid['ability_brv'],
    }
    buffs = calc_ability_buffs(db, kid_id)
    total = {k: base[k] + buffs.get(k, 0) for k in base}
    
    return jsonify({
        'id': kid['id'],
        'name': kid['name'],
        'level': kid['level'],
        'base': base,
        'buffs': buffs,
        'total': total,
        'stat_points': kid['stat_points'],
    })

# -- Task Material Drops --

MATERIAL_POOLS = {
    'common': ['wood', 'brick'],
    'uncommon': ['glass'],
    'rare': ['gear'],
}

def award_task_drops(kid_id, task_points, db, source='task', apply=True):
    """Award random materials and experience when completing a task or expedition.

    Base XP is max(5, points//2). Library task_bonus is added on top and
    reported separately (GAMEPLAY_REDESIGN §6.1 / §6.4).
    When apply=False, roll and report amounts without mutating gold/XP/inventory
    (parent-approval foreshadow, GAMEPLAY_REDESIGN §6.7).
    """
    drops = {'materials': [], 'experience': 0, 'experience_bonus': 0, 'experience_total': 0}

    exp_amount = max(5, int(task_points or 0) // 2)
    bonus_raw = get_building_buff(kid_id, 'task_bonus', db)
    try:
        bonus = int(bonus_raw or 0)
    except (TypeError, ValueError):
        bonus = 0
    total = exp_amount + bonus

    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if kid:
        drops['experience'] = exp_amount
        drops['experience_bonus'] = bonus
        drops['experience_total'] = total
        if apply:
            new_exp = (kid['experience'] or 0) + total
            new_level, _ = calc_level(new_exp)
            stat_gained = 0
            if new_level > kid['level']:
                stat_gained = new_level - kid['level']
            db.execute(
                "UPDATE kids SET experience=?, level=?, stat_points=stat_points+? WHERE id=?",
                (new_exp, new_level, stat_gained, kid_id)
            )

    num_drops = 1 if task_points < 20 else random.randint(1, 2)
    for _ in range(num_drops):
        pool = 'common'
        if task_points >= 50:
            pool = random.choices(['common', 'uncommon', 'rare'], weights=[3, 2, 1])[0]
        elif task_points >= 20:
            pool = random.choices(['common', 'uncommon'], weights=[3, 1])[0]
        mat_type = canonicalize_item_type(random.choice(MATERIAL_POOLS[pool]))
        if not mat_type:
            continue
        if apply:
            add_item(kid_id, mat_type, 1, db)
        drops['materials'].append(mat_type)

    return drops

# -- Tasks --

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    actor = current_actor()
    if not actor:
        return _unauthorized()
    db = get_db()
    category = request.args.get('category')
    kid_id = request.args.get('kid_id')
    completed = request.args.get('completed')
    search = request.args.get('search')

    if actor['role'] == 'kid':
        kid_id = str(actor['kid_id'])
    elif actor['role'] == 'parent':
        if kid_id:
            if not parent_owns_kid(actor['parent_id'], int(kid_id)):
                return _forbidden()
        else:
            # Parent dashboard: own kids + unassigned/global tasks
            kid_id = None
    elif actor['role'] != 'admin':
        return _forbidden()

    if kid_id:
        # 小朋友視角: 自己嘅任務 + 全體任務, 全體任務用 per-kid 完成狀態
        kid_id_int = int(kid_id)
        query = """
            SELECT t.id, t.title, t.icon, t.points, t.kid_id,
              t.created_at, t.completed_at, t.category, t.description, t.recurring, t.due_date,
              k.name AS kid_name, k.avatar AS kid_avatar,
              CASE WHEN t.kid_id IS NULL THEN
                (SELECT COUNT(*) FROM task_completions tc WHERE tc.task_id=t.id AND tc.kid_id=?)
              ELSE t.completed END AS completed,
              CASE WHEN t.kid_id IS NULL THEN
                COALESCE((SELECT tc.pending FROM task_completions tc WHERE tc.task_id=t.id AND tc.kid_id=?), 0)
              ELSE COALESCE(t.pending_approval, 0) END AS pending_approval
            FROM tasks t
            LEFT JOIN kids k ON t.kid_id = k.id
            WHERE (t.kid_id IS NULL OR t.kid_id = ?)
        """
        params = [kid_id_int, kid_id_int, kid_id_int]
    elif actor['role'] == 'parent':
        query = """
            SELECT t.*, k.name AS kid_name, k.avatar AS kid_avatar
            FROM tasks t
            LEFT JOIN kids k ON t.kid_id = k.id
            WHERE t.kid_id IS NULL OR t.kid_id IN (
                SELECT kid_id FROM parent_kid WHERE parent_id=?
            )
        """
        params = [actor['parent_id']]
    else:
        # 管理視角: 全部任務 (全體任務 completed 保持 0, 實際完成狀態睇 task_completions)
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
    actor = current_actor()
    if not actor:
        return _unauthorized()
    if actor['role'] not in ('parent', 'admin'):
        return _forbidden()
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or data.get('name') or '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    icon = data.get('icon', '✅')
    points = int(data.get('points', 10))
    kid_id = data.get('kid_id')
    if actor['role'] == 'parent' and kid_id is not None:
        if not parent_owns_kid(actor['parent_id'], int(kid_id)):
            return _forbidden()
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

def _empty_ceremony():
    return {
        'points_awarded': 0,
        'experience_gained': 0,
        'experience_bonus': 0,
        'experience_total': 0,
        'material_drops': [],
        'achievements': [],
        'pending_approval': False,
        'kid': None,
    }


def _ceremony_from_drops(points, drops):
    return {
        'points_awarded': int(points or 0),
        'experience_gained': int(drops.get('experience') or 0),
        'experience_bonus': int(drops.get('experience_bonus') or 0),
        'experience_total': int(drops.get('experience_total') or drops.get('experience') or 0),
        'material_drops': list(drops.get('materials') or []),
    }


def _apply_experience_amount(db, kid_id, total):
    total = int(total or 0)
    if total <= 0:
        return
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return
    new_exp = (kid['experience'] or 0) + total
    new_level, _ = calc_level(new_exp)
    stat_gained = 0
    if new_level > kid['level']:
        stat_gained = new_level - kid['level']
    db.execute(
        "UPDATE kids SET experience=?, level=?, stat_points=stat_points+? WHERE id=?",
        (new_exp, new_level, stat_gained, kid_id),
    )


def _grant_task_reward_payload(db, kid_id, task, payload):
    """Credit previously foreshadowed gold / XP / materials. XP never goes to points_log."""
    result = _empty_ceremony()
    if not kid_id:
        return result
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return result
    points = int(payload.get('points_awarded') if payload.get('points_awarded') is not None else (task['points'] or 0))
    db.execute("UPDATE kids SET points=? WHERE id=?", (kid['points'] + points, kid_id))
    db.execute(
        "INSERT INTO points_log (kid_id, amount, reason) VALUES (?,?,?)",
        (kid_id, points, f"Completed task: {task['title']}"),
    )
    result['points_awarded'] = points
    _apply_experience_amount(db, kid_id, payload.get('experience_total') or payload.get('experience_gained') or 0)
    result['experience_gained'] = int(payload.get('experience_gained') or 0)
    result['experience_bonus'] = int(payload.get('experience_bonus') or 0)
    result['experience_total'] = int(payload.get('experience_total') or result['experience_gained'])
    materials = list(payload.get('material_drops') or [])
    for item in materials:
        name = item if isinstance(item, str) else (item.get('item_type') or item.get('id'))
        if name:
            add_item(kid_id, name, 1, db)
    result['material_drops'] = materials
    update_streak(kid_id, db)
    result['achievements'] = check_achievements(kid_id, db) or []
    result['pending_approval'] = False
    updated = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    result['kid'] = kid_hud(updated)
    return result


def _preview_task_rewards(db, kid_id, task):
    """Roll ceremony amounts without mutating economy (approval foreshadow)."""
    result = _empty_ceremony()
    if not kid_id:
        return result
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return result
    points = task['points'] or 0
    drops = award_task_drops(kid_id, points, db, apply=False)
    result.update(_ceremony_from_drops(points, drops))
    result['pending_approval'] = True
    result['achievements'] = []
    result['kid'] = kid_hud(kid)
    return result


def _apply_task_completion_rewards(db, kid_id, task, result, grant=True):
    """Award gold + XP/materials, or foreshadow them when grant=False. XP is never written to points_log."""
    if grant:
        preview = _preview_task_rewards(db, kid_id, task)
        granted = _grant_task_reward_payload(db, kid_id, task, preview)
        result.update(granted)
        return
    result.update(_preview_task_rewards(db, kid_id, task))


def _store_pending_rewards(db, task_id, kid_id, payload, global_task=False):
    blob = json.dumps({
        'points_awarded': payload.get('points_awarded'),
        'experience_gained': payload.get('experience_gained'),
        'experience_bonus': payload.get('experience_bonus'),
        'experience_total': payload.get('experience_total'),
        'material_drops': payload.get('material_drops') or [],
        'kid_id': kid_id,
    })
    if global_task:
        db.execute(
            "UPDATE task_completions SET pending=1, pending_rewards=? WHERE task_id=? AND kid_id=?",
            (blob, task_id, kid_id),
        )
    else:
        db.execute(
            "UPDATE tasks SET pending_approval=1, pending_rewards=?, reject_reason=NULL WHERE id=?",
            (blob, task_id),
        )


def _load_pending_rewards(task_or_row):
    raw = None
    if task_or_row is not None:
        try:
            raw = task_or_row['pending_rewards']
        except (KeyError, IndexError, TypeError):
            raw = None
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _clear_task_pending(db, task_id, kid_id=None, global_task=False):
    if global_task:
        db.execute(
            "UPDATE task_completions SET pending=0, pending_rewards=NULL WHERE task_id=? AND kid_id=?",
            (task_id, kid_id),
        )
    else:
        db.execute(
            "UPDATE tasks SET pending_approval=0, pending_rewards=NULL WHERE id=?",
            (task_id,),
        )


def _task_row_after(db, task_id):
    return row_to_dict(db.execute(
        "SELECT t.*, k.name AS kid_name, k.avatar AS kid_avatar FROM tasks t LEFT JOIN kids k ON t.kid_id=k.id WHERE t.id=?",
        (task_id,),
    ).fetchone())


@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    actor = current_actor()
    if not actor:
        return _unauthorized()
    data = request.get_json(silent=True) or {}
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    body_kid = data.get('kid_id')
    assigned = task['kid_id']

    if actor['role'] == 'kid':
        if assigned is not None and int(assigned) != actor['kid_id']:
            return _forbidden()
        if body_kid is not None and int(body_kid) != actor['kid_id']:
            return _forbidden()
        data = dict(data)
        data['kid_id'] = actor['kid_id']
    elif actor['role'] == 'parent':
        target = assigned if assigned is not None else body_kid
        if target is not None and not parent_owns_kid(actor['parent_id'], int(target)):
            return _forbidden()
        if assigned is not None and not parent_owns_kid(actor['parent_id'], int(assigned)):
            return _forbidden()
    elif actor['role'] != 'admin':
        return _forbidden()

    now = datetime.utcnow().isoformat()
    
    # Debug log
    print(f"[DEBUG] complete_task(id={task_id}): title={task['title']}, kid_id={task['kid_id']}, points={task['points']}, recurring={task['recurring']}, completed_before={task['completed']}", flush=True)
    
    # ── 全體任務 (kid_id=NULL): 每個小朋友獨立完成 (task_completions) ──
    if task['kid_id'] is None:
        kid_id = data.get('kid_id')
        if not kid_id:
            return jsonify({'error': '全體任務需要指定小朋友 (kid_id)'}), 400
        if db.execute("SELECT 1 FROM task_completions WHERE task_id=? AND kid_id=?", (task_id, kid_id)).fetchone():
            return jsonify({'error': 'Task already completed'}), 400
        db.execute("INSERT INTO task_completions (task_id, kid_id, completed_at) VALUES (?, ?, ?)", (task_id, kid_id, now))
        result = {'task': row_to_dict(task)}
        pending = _kid_requires_approval(db, kid_id)
        _apply_task_completion_rewards(db, kid_id, task, result, grant=not pending)
        if pending:
            _store_pending_rewards(db, task_id, kid_id, result, global_task=True)
        db.commit()
        result['task'] = _task_row_after(db, task_id)
        result['task']['completed'] = 1
        result['task']['pending_approval'] = bool(pending)
        return jsonify(result), 200
    
    # Handle recurring tasks: mark done, award points, set due_date to tomorrow
    if task['recurring']:
        kid_id = task['kid_id']
        pending = _kid_requires_approval(db, kid_id)
        db.execute("UPDATE tasks SET completed=1, completed_at=? WHERE id=?", (now, task_id))
        result = {'task': row_to_dict(task)}
        _apply_task_completion_rewards(db, kid_id, task, result, grant=not pending)
        if pending:
            _store_pending_rewards(db, task_id, kid_id, result, global_task=False)
        else:
            tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
            db.execute("UPDATE tasks SET due_date=? WHERE id=?", (tomorrow, task_id))
        db.commit()
        result['task'] = _task_row_after(db, task_id)
        return jsonify(result), 200
    
    # Regular (non-recurring) task
    if task['completed']:
        return jsonify({'error': 'Task already completed'}), 400

    db.execute("UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?", (now, task_id))

    kid_id = task['kid_id']
    pending = _kid_requires_approval(db, kid_id)
    result = {'task': row_to_dict(task)}
    _apply_task_completion_rewards(db, kid_id, task, result, grant=not pending)
    if pending:
        _store_pending_rewards(db, task_id, kid_id, result, global_task=False)
    if kid_id:
        streak_row = db.execute("SELECT * FROM streaks WHERE kid_id=?", (kid_id,)).fetchone()
        if streak_row:
            result['streak'] = row_to_dict(streak_row)

    db.commit()
    result['task'] = _task_row_after(db, task_id)
    return jsonify(result), 200


def _moderate_task_auth(task_id):
    """Shared auth for approve/reject. Returns (actor, db, task, kid_id, err_response)."""
    actor = current_actor()
    if not actor:
        return None, None, None, None, _unauthorized()
    if actor['role'] == 'kid':
        return None, None, None, None, _forbidden()
    if actor['role'] not in ('parent', 'admin'):
        return None, None, None, None, _forbidden()
    data = request.get_json(silent=True) or {}
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return None, None, None, None, (jsonify({'error': 'Task not found'}), 404)
    kid_id = task['kid_id'] if task['kid_id'] is not None else data.get('kid_id')
    if actor['role'] == 'parent':
        if task['kid_id'] is not None and not parent_owns_kid(actor['parent_id'], int(task['kid_id'])):
            return None, None, None, None, _forbidden()
        if kid_id is not None and not parent_owns_kid(actor['parent_id'], int(kid_id)):
            return None, None, None, None, _forbidden()
        if task['kid_id'] is None and kid_id is None:
            return None, None, None, None, _forbidden()
    return actor, db, task, kid_id, None


@app.route('/api/tasks/<int:task_id>/approve', methods=['POST'])
def approve_task(task_id):
    actor, db, task, kid_id, err = _moderate_task_auth(task_id)
    if err:
        return err
    global_task = task['kid_id'] is None
    pending_row = task
    if global_task:
        if not kid_id:
            return jsonify({'error': 'kid_id required'}), 400
        pending_row = db.execute(
            "SELECT * FROM task_completions WHERE task_id=? AND kid_id=?",
            (task_id, kid_id),
        ).fetchone()
        is_pending = bool(pending_row and pending_row['pending'])
    else:
        is_pending = bool(task['pending_approval'])
    if not is_pending:
        return jsonify({'error': 'not_pending'}), 400
    stored = _load_pending_rewards(pending_row)
    if not stored:
        stored = _preview_task_rewards(db, kid_id, task)
    result = _grant_task_reward_payload(db, kid_id, task, stored)
    _clear_task_pending(db, task_id, kid_id, global_task=global_task)
    if task['recurring'] and not global_task:
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
        db.execute("UPDATE tasks SET due_date=? WHERE id=?", (tomorrow, task_id))
    db.commit()
    result['ok'] = True
    result['task'] = _task_row_after(db, task_id)
    if global_task:
        result['task']['completed'] = 1
        result['task']['pending_approval'] = False
    return jsonify(result), 200


@app.route('/api/tasks/<int:task_id>/reject', methods=['POST'])
def reject_task(task_id):
    actor, db, task, kid_id, err = _moderate_task_auth(task_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or ''
    global_task = task['kid_id'] is None
    if global_task:
        if not kid_id:
            return jsonify({'error': 'kid_id required'}), 400
        pending_row = db.execute(
            "SELECT * FROM task_completions WHERE task_id=? AND kid_id=?",
            (task_id, kid_id),
        ).fetchone()
        if not pending_row:
            return jsonify({'error': 'not_pending'}), 400
        db.execute(
            "DELETE FROM task_completions WHERE task_id=? AND kid_id=?",
            (task_id, kid_id),
        )
    else:
        if not task['pending_approval']:
            return jsonify({'error': 'not_pending'}), 400
        db.execute(
            "UPDATE tasks SET completed=0, completed_at=NULL, pending_approval=0, "
            "pending_rewards=NULL, reject_reason=? WHERE id=?",
            (reason, task_id),
        )
    db.commit()
    result = {'ok': True, 'rejected': True, 'reason': reason, 'task': _task_row_after(db, task_id)}
    if global_task and result['task'] is not None:
        result['task']['completed'] = 0
        result['task']['pending_approval'] = False
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
        return jsonify({'error': 'Wrong PIN'}), 403
    if not verify_password(pin, auth['pin']):
        return jsonify({'error': 'Wrong PIN'}), 403
    if _needs_rehash(auth['pin']):
        db.execute("UPDATE kid_auth SET pin=? WHERE kid_id=?", (hash_password(pin), kid_id))
        db.commit()
    _set_session('kid', kid['id'], kid_id=kid['id'])
    return jsonify({'ok': True, 'kid': public_kid(kid)})

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
    cell_x = data.get('cell_x')
    cell_y = data.get('cell_y')
    if not def_id or cell_x is None or cell_y is None:
        return jsonify({'error': 'def_id, cell_x, cell_y required'}), 400
    if cell_x < 0 or cell_x > 22 or cell_y < 0 or cell_y > 14:
        return jsonify({'error': 'Building position out of range (0-22, 0-14)'}), 400
    db = get_db()
    # Limit: only 1 of each building type per kid
    dup = db.execute("SELECT id FROM buildings WHERE kid_id=? AND def_id=?", (kid_id, def_id)).fetchone()
    if dup:
        return jsonify({'error': '你已經興建咗呢種建築物'}), 400
    
    # Check 2×2 block is free (no building or tile occupies any of the 4 cells)
    for dy in range(2):
        for dx in range(2):
            cx, cy = cell_x + dx, cell_y + dy
            # Check buildings
            existing_bld = db.execute("SELECT id FROM buildings WHERE kid_id=? AND cell_x=? AND cell_y=?", (kid_id, cx, cy)).fetchone()
            if existing_bld:
                return jsonify({'error': '該位置已被建築物佔用'}), 400
            # Check tiles
            existing_tile = db.execute("SELECT id FROM town_tiles WHERE kid_id=? AND cell_x=? AND cell_y=?", (kid_id, cx, cy)).fetchone()
            if existing_tile:
                return jsonify({'error': '該位置已被裝飾佔用'}), 400

    bdef = db.execute("SELECT * FROM building_defs WHERE id=?", (def_id,)).fetchone()
    if not bdef:
        return jsonify({'error': 'Building definition not found'}), 404

    unlock_err, unlock_region = building_unlock_error(kid_id, bdef['unlock_region'], db)
    if unlock_err == 'region_locked':
        return jsonify({'error': 'region_locked', 'region_id': unlock_region}), 400
    if unlock_err:
        return jsonify({'error': 'unlock_region', 'region_id': unlock_region}), 400

    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    gold_cost = discounted_gold_cost(kid_id, bdef['cost_gold'], db)
    if kid['points'] < gold_cost:
        return jsonify({'error': 'Insufficient resources'}), 400

    try:
        required_mats = _canonicalize_material_dict(
            json.loads(bdef['materials']) if bdef['materials'] else {}
        )
    except (json.JSONDecodeError, TypeError):
        required_mats = {}
    for item_type, qty in required_mats.items():
        inv = db.execute("SELECT quantity FROM inventory WHERE kid_id=? AND item_type=?", (kid_id, item_type)).fetchone()
        if not inv or inv['quantity'] < qty:
            return jsonify({'error': 'Insufficient resources'}), 400

    db.execute("UPDATE kids SET points = points - ? WHERE id=?", (gold_cost, kid_id))
    db.execute("INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
               (kid_id, -gold_cost, f"Built {bdef['name']}"))

    for item_type, qty in required_mats.items():
        db.execute("UPDATE inventory SET quantity = quantity - ? WHERE kid_id=? AND item_type=?",
                   (qty, kid_id, item_type))

    cur = db.execute("INSERT INTO buildings (kid_id, def_id, cell_x, cell_y, plot_idx, level) VALUES (?, ?, ?, ?, 0, 1)", (kid_id, def_id, cell_x, cell_y))
    db.commit()
    row = db.execute("SELECT b.*, bd.name, bd.icon, bd.buff_type, bd.buff_vals, bd.effect FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.id=?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201

@app.route('/api/kids/<int:kid_id>/buildings/<int:b_id>/move', methods=['POST'])
def move_building(kid_id, b_id):
    data = request.get_json(silent=True) or {}
    cell_x = data.get('cell_x')
    cell_y = data.get('cell_y')
    if cell_x is None or cell_y is None:
        return jsonify({'error': 'cell_x, cell_y required'}), 400
    if cell_x < 0 or cell_x > 22 or cell_y < 0 or cell_y > 14:
        return jsonify({'error': 'Position out of range (0-22, 0-14)'}), 400
    db = get_db()
    b = db.execute("SELECT id, kid_id, stored FROM buildings WHERE id=? AND kid_id=?", (b_id, kid_id)).fetchone()
    if not b:
        return jsonify({'error': 'Building not found'}), 404
    if b['stored']:
        return jsonify({'error': 'Cannot move a stored building'}), 400
    # Check 2×2 block is free (ignore the building itself)
    for dy in range(2):
        for dx in range(2):
            cx, cy = cell_x + dx, cell_y + dy
            existing = db.execute("SELECT id FROM buildings WHERE kid_id=? AND cell_x=? AND cell_y=? AND id!=?", (kid_id, cx, cy, b_id)).fetchone()
            if existing:
                return jsonify({'error': '該位置已被佔用'}), 400
            tile = db.execute("SELECT id FROM town_tiles WHERE kid_id=? AND cell_x=? AND cell_y=?", (kid_id, cx, cy)).fetchone()
            if tile:
                return jsonify({'error': '該位置已被裝飾佔用'}), 400
    db.execute("UPDATE buildings SET cell_x=?, cell_y=? WHERE id=?", (cell_x, cell_y, b_id))
    db.commit()
    return jsonify({'ok': True, 'cell_x': cell_x, 'cell_y': cell_y}), 200

@app.route('/api/kids/<int:kid_id>/buildings/<int:b_id>/store', methods=['POST'])
def store_building(kid_id, b_id):
    db = get_db()
    b = db.execute("SELECT id, stored FROM buildings WHERE id=? AND kid_id=?", (b_id, kid_id)).fetchone()
    if not b:
        return jsonify({'error': 'Building not found'}), 404
    if b['stored']:
        return jsonify({'error': 'Already stored'}), 400
    db.execute("UPDATE buildings SET stored=1 WHERE id=?", (b_id,))
    db.commit()
    return jsonify({'ok': True}), 200

@app.route('/api/kids/<int:kid_id>/buildings/<int:b_id>/unstored', methods=['POST'])
def unstored_building(kid_id, b_id):
    data = request.get_json(silent=True) or {}
    cell_x = data.get('cell_x')
    cell_y = data.get('cell_y')
    if cell_x is None or cell_y is None:
        return jsonify({'error': 'cell_x, cell_y required'}), 400
    if cell_x < 0 or cell_x > 22 or cell_y < 0 or cell_y > 14:
        return jsonify({'error': 'Position out of range (0-22, 0-14)'}), 400
    db = get_db()
    b = db.execute("SELECT id, stored FROM buildings WHERE id=? AND kid_id=?", (b_id, kid_id)).fetchone()
    if not b:
        return jsonify({'error': 'Building not found'}), 404
    if not b['stored']:
        return jsonify({'error': 'Building is not stored'}), 400
    # Check 2×2 free
    for dy in range(2):
        for dx in range(2):
            cx, cy = cell_x + dx, cell_y + dy
            existing = db.execute("SELECT id FROM buildings WHERE kid_id=? AND cell_x=? AND cell_y=? AND id!=?", (kid_id, cx, cy, b_id)).fetchone()
            if existing:
                return jsonify({'error': '該位置已被佔用'}), 400
            tile = db.execute("SELECT id FROM town_tiles WHERE kid_id=? AND cell_x=? AND cell_y=?", (kid_id, cx, cy)).fetchone()
            if tile:
                return jsonify({'error': '該位置已被裝飾佔用'}), 400
    db.execute("UPDATE buildings SET stored=0, cell_x=?, cell_y=? WHERE id=?", (cell_x, cell_y, b_id))
    db.commit()
    row = db.execute("SELECT b.*, bd.name, bd.icon, bd.buff_type, bd.buff_vals, bd.effect FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.id=?", (b_id,)).fetchone()
    return jsonify(row_to_dict(row)), 200

@app.route('/api/kids/<int:kid_id>/stored-buildings', methods=['GET'])
def get_stored_buildings(kid_id):
    db = get_db()
    rows = db.execute("""
        SELECT b.*, bd.name, bd.icon, bd.buff_type, bd.buff_vals, bd.effect, bd.materials, bd.max_level
        FROM buildings b JOIN building_defs bd ON b.def_id=bd.id
        WHERE b.kid_id=? AND b.stored=1
    """, (kid_id,)).fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/kids/<int:kid_id>/buildings/<int:b_id>/upgrade', methods=['POST'])
def upgrade_building(kid_id, b_id):
    db = get_db()
    b = db.execute("SELECT b.*, bd.max_level, bd.name, bd.buff_vals, bd.materials FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.id=? AND b.kid_id=?", (b_id, kid_id)).fetchone()
    if not b:
        return jsonify({'error': 'Building not found'}), 404
    if b['level'] >= b['max_level']:
        return jsonify({'error': 'Already max level'}), 400

    cost_gold = discounted_gold_cost(kid_id, b['level'] * 100, db)
    try:
        base_mats = _canonicalize_material_dict(
            json.loads(b['materials']) if b['materials'] else {}
        )
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
    add_item(kid_id, item_type, qty, db)
    db.commit()
    updated = db.execute("SELECT * FROM inventory WHERE kid_id=?", (kid_id,)).fetchall()
    return jsonify(rows_to_list(updated))

@app.route('/api/kids/<int:kid_id>/inventory/consume', methods=['POST'])
def consume_materials(kid_id):
    """Deduct materials from inventory. Returns 400 if insufficient."""
    data = request.get_json(silent=True) or {}
    items = data.get('items', {})  # e.g. {"wood":5,"brick":3}
    if not items:
        return jsonify({'error': 'items required'}), 400
    
    db = get_db()
    # Check availability
    for item_type, qty in items.items():
        row = db.execute("SELECT quantity FROM inventory WHERE kid_id=? AND item_type=?", (kid_id, item_type)).fetchone()
        if not row or row['quantity'] < qty:
            return jsonify({'error': f'Insufficient {item_type}: have {row["quantity"] if row else 0}, need {qty}'}), 400
    
    # Deduct
    for item_type, qty in items.items():
        db.execute("UPDATE inventory SET quantity=quantity-? WHERE kid_id=? AND item_type=?", (qty, kid_id, item_type))
    db.commit()
    
    updated = db.execute("SELECT * FROM inventory WHERE kid_id=?", (kid_id,)).fetchall()
    return jsonify(rows_to_list(updated))

@app.route('/api/building-recipes', methods=['GET'])
def get_building_recipes():
    """Return building defs with expanded material info (name + icon)."""
    db = get_db()
    rows = db.execute("SELECT * FROM building_defs ORDER BY cost_gold ASC").fetchall()
    MAT_ICONS = {'wood': '🪵', 'brick': '🧱', 'glass': '🪟', 'gear': '⚙️', 'gem': '💎'}
    MAT_NAMES = {'wood': '木材', 'brick': '磚頭', 'glass': '玻璃', 'gear': '齒輪', 'gem': '寶石'}
    result = []
    for r in rows:
        d = dict(r)
        try:
            mats = json.loads(d.get('materials', '{}'))
        except (json.JSONDecodeError, TypeError):
            mats = {}
        d['materials_detail'] = [
            {'id': k, 'name': MAT_NAMES.get(k, k), 'icon': MAT_ICONS.get(k, '📦'), 'qty': v}
            for k, v in sorted(mats.items())
        ]
        d['materials'] = mats  # keep original dict for compatibility
        result.append(d)
    return jsonify(result)

@app.route('/api/materials/defs', methods=['GET'])
def get_material_defs():
    return jsonify([
        {'id':'wood', 'name':'木材', 'icon':'🪵'},
        {'id':'brick', 'name':'磚頭', 'icon':'🧱'},
        {'id':'glass', 'name':'玻璃', 'icon':'🪟'},
        {'id':'gear', 'name':'齒輪', 'icon':'⚙️'},
        {'id':'gem', 'name':'寶石', 'icon':'💎'},
    ])


@app.route('/api/kids/<int:kid_id>/farm/claim', methods=['POST'])
def farm_claim(kid_id):
    """Daily farm gold. One claim per Asia/Hong_Kong calendar day."""
    db = get_db()
    amount = get_building_buff(kid_id, 'daily_gold', db)
    if amount is None:
        return jsonify({'error': 'farm_required'}), 400
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return jsonify({'error': 'farm_required'}), 400
    today = hk_today_str()
    prev = db.execute("SELECT claim_date FROM farm_claims WHERE kid_id=?", (kid_id,)).fetchone()
    if prev and prev['claim_date'] == today:
        return jsonify({'error': 'already_claimed_today'}), 400
    db.execute("UPDATE kids SET points = points + ? WHERE id=?", (amount, kid_id))
    db.execute(
        "INSERT INTO points_log (kid_id, amount, reason) VALUES (?,?,?)",
        (kid_id, amount, 'daily_gold'),
    )
    if prev:
        db.execute("UPDATE farm_claims SET claim_date=? WHERE kid_id=?", (today, kid_id))
    else:
        db.execute("INSERT INTO farm_claims (kid_id, claim_date) VALUES (?,?)", (kid_id, today))
    db.commit()
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    return jsonify({
        'ok': True,
        'amount': amount,
        'points': kid['points'] if kid else amount,
        'claim_date': today,
    }), 200

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
    expedition_type = data.get('expedition_type', 'explore')
    if expedition_type not in ('explore', 'quiz', 'battle'):
        return jsonify({'error': 'Invalid expedition type'}), 400
    db = get_db()
    running = db.execute("SELECT id FROM expeditions WHERE kid_id=? AND status='running'", (kid_id,)).fetchone()
    if running:
        return jsonify({'error': 'Expedition already running'}), 400

    if expedition_type == 'explore':
        if region_content_locked(region_id):
            return jsonify({'error': 'region_locked', 'region_id': int(region_id)}), 400
        if not has_active_guild(kid_id, db):
            return jsonify({'error': 'guild_required'}), 400
        try:
            fee = EXPLORE_FEE_BY_REGION.get(int(region_id), 0)
        except (TypeError, ValueError):
            fee = 0
        kid = db.execute("SELECT points FROM kids WHERE id=?", (kid_id,)).fetchone()
        have = kid['points'] if kid else 0
        if fee > 0 and have < fee:
            return jsonify({'error': 'insufficient_gold', 'need': fee, 'have': have}), 400
        if fee > 0:
            db.execute("UPDATE kids SET points = points - ? WHERE id=?", (fee, kid_id))
            db.execute(
                "INSERT INTO points_log (kid_id, amount, reason) VALUES (?,?,?)",
                (kid_id, -fee, f"expedition_fee region={region_id}"),
            )

    hours = data.get('duration_hours')
    minutes = data.get('duration_minutes')
    if hours is None and minutes is None:
        delta = timedelta(minutes=5) if expedition_type == 'explore' else timedelta(hours=2)
    else:
        delta = timedelta(hours=int(hours or 0), minutes=int(minutes or 0))
    now = datetime.utcnow()
    end = now + delta
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
    materials = ['wood', 'brick', 'glass', 'gear', 'gem']
    rewards = {}
    events = []
    for m in materials:
        if random.random() < 0.6:
            qty = random.randint(1, 5)
            stored = add_item(kid_id, m, qty, db)
            if stored:
                rewards[stored] = rewards.get(stored, 0) + qty
    if random.random() < 0.1:
        stored = add_item(kid_id, 'dragon_scale', 1, db)
        if stored:
            rewards[stored] = rewards.get(stored, 0) + 1
            events.append('🐉 發現龍鱗！')
    if random.random() < 0.08:
        stored = add_item(kid_id, 'fur', 1, db)
        if stored:
            rewards[stored] = rewards.get(stored, 0) + 1
            events.append('🦊 搵到毛皮！')
    lo, hi = EXPLORE_GOLD_REWARD_RANGE.get(exp['region_id'] or 1, (6, 10))
    gold_reward = random.randint(lo, hi)
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if kid:
        db.execute("UPDATE kids SET points=points+? WHERE id=?", (gold_reward, kid_id))
        # Log expedition gold in points_log so it appears in transaction records
        db.execute("INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)", 
                   (kid_id, gold_reward, f"Expedition claim (Region {exp['region_id']})"))
        # Award experience for expedition
        exp_amount = random.randint(10, 30) * (exp['region_id'] or 1)
        new_exp = kid['experience'] + exp_amount
        new_level, _ = calc_level(new_exp)
        stat_gained = max(0, new_level - kid['level'])
        db.execute(
            "UPDATE kids SET experience=?, level=?, stat_points=stat_points+? WHERE id=?",
            (new_exp, new_level, stat_gained, kid_id)
        )
        events.append(f'⭐ +{exp_amount}EXP')
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


# -- Battle --


def calc_battle_stats(kid):
    """v2: HP from level, ATK from 臂力(str), DEF from 勇氣(brv)."""
    str_v = kid['ability_str'] or 0
    int_v = kid['ability_int'] or 0
    spd_v = kid['ability_spd'] or 0
    crt_v = kid['ability_crt'] or 0
    brv_v = kid['ability_brv'] or 0
    lvl = kid['level'] or 1
    return {
        'hp': 20 + lvl * 8,
        'atk': int(5 + str_v * 1.5),
        'matk': int(5 + int_v * 1.5),
        'def': int(brv_v * 0.6),
        'crt': min(50, crt_v * 2),        # crit %
        'crit_dmg': 1.5 + crt_v * 0.02,   # 爆擊倍率
        'dodge': min(40, spd_v * 1.5),    # dodge %
        'spd': spd_v,
        'int': int_v,
        'brv': brv_v,
        'str': str_v,
    }


def calc_monster_stats(tier):
    """Monster stats from tier (= region number)."""
    t = max(1, tier)
    return {
        'hp': 20 + t * 20,
        'atk': 4 + t * 3,
        'def': t // 2,
        'spd': t,
    }


def calc_boss_stats(base):
    """Boss = 3x HP, 1.5x ATK, 1.5x DEF of the base monster."""
    return {
        'hp': base['hp'] * 3,
        'atk': base['atk'] * 1.5,
        'def': int(base['def'] * 1.5),
    }


def migrate_ability_atk(db):
    """Merge ability_atk into ability_str (臂力), then drop the column."""
    db.execute("UPDATE kids SET ability_str = ability_str + COALESCE(ability_atk, 0)")
    db.execute("ALTER TABLE kids DROP COLUMN ability_atk")
    db.commit()


def region_unlock_level(region_id):
    """Minimum player level to unlock a region (t*2)."""
    return region_id * 2


MILESTONES = [10, 25, 50, 100, 200, 500, 1000]


def check_milestones(old_level, new_level):
    """Return milestone levels crossed between old_level and new_level."""
    return [m for m in MILESTONES if old_level < m <= new_level]


def get_pity_count(db, kid_id):
    row = db.execute("SELECT count FROM drop_pity WHERE kid_id=?", (kid_id,)).fetchone()
    return row['count'] if row else 0


def update_pity(db, kid_id, rarity):
    """Reset pity on epic+; increment on common/rare."""
    if rarity in ('epic', 'legendary'):
        db.execute("INSERT OR REPLACE INTO drop_pity (kid_id, count) VALUES (?,0)", (kid_id,))
    else:
        row = db.execute("SELECT count FROM drop_pity WHERE kid_id=?", (kid_id,)).fetchone()
        new_count = (row['count'] if row else 0) + 1
        db.execute("INSERT OR REPLACE INTO drop_pity (kid_id, count) VALUES (?,?)", (kid_id, new_count))


@app.route('/api/kids/<int:kid_id>/skills', methods=['GET'])
def get_kid_skills(kid_id):
    """Return skills available based on buildings owned and their levels."""
    db = get_db()
    buildings = db.execute(
        "SELECT b.level, bd.id as bldg_def_id, bd.name as bldg_name "
        "FROM buildings b JOIN building_defs bd ON b.def_id=bd.id "
        "WHERE b.kid_id=? AND b.stored=0",
        (kid_id,)
    ).fetchall()
    skills = []
    for bldg in buildings:
        bldg_skills = db.execute(
            "SELECT * FROM skill_defs WHERE bldg_def_id=? AND level_required<=?",
            (bldg['bldg_def_id'], bldg['level'])
        ).fetchall()
        for sk in bldg_skills:
            skills.append({
                'id': sk['id'],
                'name': sk['name'],
                'icon': sk['icon'],
                'mp_cost': sk['mp_cost'],
                'bldg': bldg['bldg_name'],
                'bldg_level': bldg['level'],
                'target': sk['target'],
                'description': sk['description'],
                'base_value': sk['base_value'],
                'per_level': sk['per_level'],
                'attr_scale': sk['attr_scale'],
                'effect_type': sk['effect_type'],
            })
    return jsonify(skills)


BOSS_SUMMON_COST = {'gem': 1}  # 召喚 Boss 材料

# Approved soft-v1 bodies. Anything else stays on the record's icon.
_SPRITE_WOLF = '/kids/mocks/ui-direction/kit/sprites/sprite-wolf.png?v=5'
_SPRITE_BEAR = '/kids/mocks/ui-direction/kit/sprites/sprite-bear.png?v=5'
_SPRITE_SCORPION = '/kids/mocks/ui-direction/kit/sprites/sprite-scorpion.png?v=5'
_SPRITE_BOAR = '/kids/mocks/ui-direction/kit/sprites/sprite-boar.png?v=5'


def enemy_sprite(name, monster_id=None):
    """Sprite bound to this monster definition. None means show its icon."""
    name = name or ''
    if monster_id == 1 or '狼' in name:
        return _SPRITE_WOLF
    if monster_id == 2 or '熊' in name:
        return _SPRITE_BEAR
    if monster_id == 3 or '蠍' in name or '蝎' in name:
        return _SPRITE_SCORPION
    if '豬' in name or '猪' in name:
        return _SPRITE_BOAR
    return None


def boss_is_unlocked(db, kid_id, region_id):
    """Region 1 boss always available; higher regions need previous boss first-kill."""
    if region_id <= 1:
        return True
    prev = db.execute("SELECT first_kill FROM boss_progress WHERE kid_id=? AND region_id=?",
                      (kid_id, region_id - 1)).fetchone()
    return prev is not None and prev['first_kill'] == 1


def _award_boss_rewards(db, kid_id, bd):
    """Boss win: first kill → guaranteed legendary + unlock next region; always set weekly win time."""
    region_id = bd.get('region_id', 1) or 1
    prog = db.execute("SELECT first_kill FROM boss_progress WHERE kid_id=? AND region_id=?",
                      (kid_id, region_id)).fetchone()
    now = datetime.now().isoformat()
    if prog is None or not prog['first_kill']:
        # 首殺: 保底 legendary (dragon_scale)
        add_item(kid_id, 'dragon_scale', 1, db)
        db.execute("INSERT OR REPLACE INTO boss_progress (kid_id, region_id, first_kill, last_win_at) VALUES (?,?,1,?)",
                   (kid_id, region_id, now))
    else:
        # 重戰: 保底 epic (gem)
        add_item(kid_id, 'gem', 1, db)
        db.execute("UPDATE boss_progress SET last_win_at=? WHERE kid_id=? AND region_id=?",
                   (now, kid_id, region_id))
    db.commit()


@app.route('/api/kids/<int:kid_id>/boss/summon', methods=['POST'])
def boss_summon(kid_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    region_id = data.get('region_id', 1)

    if region_content_locked(region_id):
        return jsonify({'error': 'region_locked', 'region_id': int(region_id)}), 400

    # 解鎖檢查 (前一區 Boss 首殺)
    if not boss_is_unlocked(db, kid_id, region_id):
        return jsonify({'error': '尚未解鎖此 Boss 區域'}), 400

    prog = db.execute("SELECT * FROM boss_progress WHERE kid_id=? AND region_id=?",
                      (kid_id, region_id)).fetchone()

    # 一週冷卻 (打贏咗 7 日內唔可以再召喚)
    if prog and prog['last_win_at']:
        try:
            last_win = datetime.fromisoformat(prog['last_win_at'])
            if datetime.now() - last_win < timedelta(days=7):
                return jsonify({'error': '本週已打贏 Boss，下週再挑戰'}), 400
        except ValueError:
            pass

    # 材料
    for item, qty in BOSS_SUMMON_COST.items():
        inv = db.execute("SELECT * FROM inventory WHERE kid_id=? AND item_type=?",
                         (kid_id, item)).fetchone()
        if not inv or inv['quantity'] < qty:
            return jsonify({'error': f'召喚材料不足，需要 {item} ×{qty}'}), 400
        db.execute("UPDATE inventory SET quantity=quantity-? WHERE id=?", (qty, inv['id']))

    # 自動放棄 running 嘅 battle/boss, 再清理 stale, 再檢查其他 running
    db.execute("UPDATE expeditions SET status='completed' WHERE kid_id=? AND status='running' AND expedition_type IN ('battle','boss')", (kid_id,))
    _clean_stale_expeditions_db(db)
    running = db.execute("SELECT id FROM expeditions WHERE kid_id=? AND status='running'",
                         (kid_id,)).fetchone()
    if running:
        return jsonify({'error': 'Expedition already running'}), 400

    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404

    # Boss 怪物 = 3x HP, 1.5x ATK/DEF
    bstats = calc_boss_stats(calc_monster_stats(region_id))
    boss_name = f'第{region_id}區 Boss'
    boss = [{
        'id': 0, 'monster_id': -1,
        'name': boss_name, 'icon': '👑',
        'sprite': enemy_sprite(boss_name, -1),
        'max_hp': bstats['hp'], 'hp': bstats['hp'],
        'atk': bstats['atk'], 'def': bstats['def'],
        'spd': region_id + 3,
    }]

    # 技能
    buildings = db.execute(
        "SELECT b.level, bd.id as bldg_def_id FROM buildings b JOIN building_defs bd ON b.def_id=bd.id "
        "WHERE b.kid_id=? AND b.stored=0", (kid_id,)
    ).fetchall()
    skills = []
    for bldg in buildings:
        bldg_skills = db.execute(
            "SELECT id, name, icon, mp_cost, target, description, base_value, per_level, attr_scale, effect_type, bldg_def_id, level_required "
            "FROM skill_defs WHERE bldg_def_id=? AND level_required<=?",
            (bldg['bldg_def_id'], bldg['level'])
        ).fetchall()
        for s in bldg_skills:
            skills.append(dict(s))

    p_stats = calc_battle_stats(kid)
    p_hp = p_stats['hp']
    p_mp = 10 + kid['level'] * 3

    battle_data = {
        'expedition_id': None,
        'monsters': boss,
        'player_max_hp': p_hp, 'player_hp': p_hp,
        'player_max_mp': p_mp, 'player_mp': p_mp,
        'player_atk': p_stats['atk'],
        'player_def': p_stats.get('def', p_stats['atk'] // 2),
        'player_crt': p_stats['crt'],
        'player_crit_dmg': p_stats.get('crit_dmg', 1.5),
        'player_spd': p_stats['spd'],
        'player_brv': p_stats['brv'],
        'player_int': p_stats.get('int', 0),
        'player_str': p_stats.get('str', 0),
        'player_dodge': p_stats.get('dodge', 0),
        'region_id': region_id,
        'turns': [],
        'status': 'fighting',
        'expedition_type': 'boss',
        'is_boss': True,
        'skills': skills,
        'expedition_data': None,
        'gold_reward': 100,
        'mat_reward': {},
    }

    now = datetime.utcnow()
    cur = db.execute(
        "INSERT INTO expeditions (kid_id, region_id, expedition_type, start_time, end_time, status, expedition_data) VALUES (?,?,'boss',?,?,'running',?)",
        (kid_id, region_id, now.isoformat() + 'Z', (now + timedelta(hours=1)).isoformat() + 'Z', json.dumps(battle_data))
    )
    battle_data['expedition_id'] = cur.lastrowid
    db.execute("UPDATE expeditions SET expedition_data=? WHERE id=?", (json.dumps(battle_data), cur.lastrowid))

    # 更新/插入 boss_progress (保留 first_kill + last_win_at)
    if prog:
        db.execute("UPDATE boss_progress SET last_summon_at=? WHERE kid_id=? AND region_id=?",
                   (now.isoformat() + 'Z', kid_id, region_id))
    else:
        db.execute("INSERT INTO boss_progress (kid_id, region_id, first_kill, last_summon_at) VALUES (?,?,0,?)",
                   (kid_id, region_id, now.isoformat() + 'Z'))
    db.commit()
    return jsonify(battle_data), 201


@app.route('/api/kids/<int:kid_id>/expedition/battle-start', methods=['POST'])
def battle_start(kid_id):
    """Start a battle expedition: player vs monster."""
    data = request.get_json(silent=True) or {}
    region_id = data.get('region_id', 1)
    db = get_db()

    if region_content_locked(region_id):
        return jsonify({'error': 'region_locked', 'region_id': int(region_id)}), 400
    if not has_active_guild(kid_id, db):
        return jsonify({'error': 'guild_required'}), 400

    # 自動放棄 running 嘅 battle/boss (開新戰鬥 = 放棄舊嘅), 再清理 stale, 再檢查其他 running
    db.execute("UPDATE expeditions SET status='completed' WHERE kid_id=? AND status='running' AND expedition_type IN ('battle','boss')", (kid_id,))
    _clean_stale_expeditions_db(db)
    running = db.execute("SELECT id FROM expeditions WHERE kid_id=? AND status='running'", (kid_id,)).fetchone()
    if running:
        return jsonify({'error': 'Expedition already running'}), 400

    # 每區一日一次 (打贏先計)
    today = date.today().isoformat()
    won_today = db.execute("SELECT 1 FROM daily_battles WHERE kid_id=? AND region_id=? AND battle_date=?",
                           (kid_id, region_id, today)).fetchone()
    if won_today:
        return jsonify({'error': '今日已打過此區，聽日再嚟'}), 400

    # Get monster for this region
    monster = db.execute("SELECT * FROM monsters WHERE region_id=?", (region_id,)).fetchone()
    if not monster:
        return jsonify({'error': 'No monster for this region'}), 404

    # Get kid stats
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404

    # 區域解鎖門檻 (level gate, t*2)
    if kid['level'] < region_unlock_level(region_id):
        return jsonify({'error': f'需要 Lv{region_unlock_level(region_id)} 先解鎖此區'}), 400

    # Get available skills
    buildings = db.execute(
        "SELECT b.level, bd.id as bldg_def_id FROM buildings b JOIN building_defs bd ON b.def_id=bd.id "
        "WHERE b.kid_id=? AND b.stored=0", (kid_id,)
    ).fetchall()
    skills = []
    for bldg in buildings:
        bldg_skills = db.execute(
            "SELECT id, name, icon, mp_cost, target, description, base_value, per_level, attr_scale, effect_type, bldg_def_id, level_required "
            "FROM skill_defs WHERE bldg_def_id=? AND level_required<=?",
            (bldg['bldg_def_id'], bldg['level'])
        ).fetchall()
        for s in bldg_skills:
            skills.append(dict(s))

    p_stats = calc_battle_stats(kid)
    p_hp = p_stats['hp']
    p_mp = 10 + kid['level'] * 3  # Base MP: 10 + 3/level
    # Multiple monsters (1-3), stats from tier formula
    num_monsters = random.randint(1, 3)
    mstats = calc_monster_stats(region_id)  # tier = region number
    monsters = []
    for mi in range(num_monsters):
        hp_var = random.randint(-5, 5)
        monsters.append({
            'id': mi,
            'monster_id': monster['id'],
            'name': monster['name'],
            'icon': monster['icon'],
            'sprite': enemy_sprite(monster['name'], monster['id']),
            'max_hp': max(1, mstats['hp'] + hp_var),
            'hp': max(1, mstats['hp'] + hp_var),
            'atk': mstats['atk'],
            'def': mstats['def'],
            'spd': mstats['spd'],
        })
    battle_data = {
        'expedition_id': None,
        'monsters': monsters,
        'player_max_hp': p_hp,
        'player_hp': p_hp,
        'player_max_mp': p_mp,
        'player_mp': p_mp,
        'player_atk': p_stats['atk'],
        'player_def': p_stats.get('def', p_stats['atk'] // 2),
        'player_crt': p_stats['crt'],
        'player_crit_dmg': p_stats.get('crit_dmg', 1.5),
        'player_spd': p_stats['spd'],
        'player_brv': p_stats['brv'],
        'player_int': p_stats.get('int', 0),
        'player_str': p_stats.get('str', 0),
        'player_dodge': p_stats.get('dodge', 0),
        'region_id': region_id,
        'turns': [],
        'status': 'fighting',
        'expedition_type': 'battle',
        'skills': skills,
        'expedition_data': None,
        'gold_reward': monster['gold_reward'],
        'mat_reward': json.loads(monster['mat_reward'] or '{}'),
    }

    now = datetime.utcnow()
    cur = db.execute(
        "INSERT INTO expeditions (kid_id, region_id, expedition_type, start_time, end_time, status, expedition_data) VALUES (?,?,'battle',?,?,'running',?)",
        (kid_id, region_id, now.isoformat() + 'Z', (now + timedelta(hours=1)).isoformat() + 'Z', json.dumps(battle_data))
    )
    db.commit()
    battle_data['expedition_id'] = cur.lastrowid
    return jsonify(battle_data), 201


@app.route('/api/kids/<int:kid_id>/expedition/battle-action', methods=['POST'])
def battle_action(kid_id):
    """Execute one battle turn: player attacks or uses a skill, monster counter-attacks."""
    data = request.get_json(silent=True) or {}
    action = data.get('action', 'attack')
    target_idx = data.get('target_idx', 0)  # which monster to hit
    skill_id = data.get('skill_id')
    db = get_db()

    exp = db.execute("SELECT * FROM expeditions WHERE kid_id=? AND status='running' AND expedition_type IN ('battle','boss') ORDER BY start_time DESC LIMIT 1", (kid_id,)).fetchone()
    if not exp:
        return jsonify({'error': 'No running battle'}), 400

    bd = json.loads(exp['expedition_data'] or '{}')
    if bd.get('status') != 'fighting':
        return jsonify({'error': 'Battle already ended'}), 400

    monsters = bd.get('monsters', [])
    player_atk = bd['player_atk']
    player_crt = bd['player_crt']
    player_def = bd.get('player_def', 5)
    log = []
    defending = False

    # Find a valid target
    alive_targets = [m for m in monsters if m['hp'] > 0]
    if not alive_targets:
        return jsonify({'error': 'No alive targets'}), 400

    target_monster = None
    for m in monsters:
        if m['id'] == target_idx and m['hp'] > 0:
            target_monster = m
            break
    if not target_monster:
        target_monster = alive_targets[0]
        target_idx = target_monster['id']

    # --- Player action ---
    if action == 'attack':
        dmg = max(1, player_atk - target_monster['def'] + random.randint(0, 2))
        # Charge boost: 2x damage
        if bd.get('charge_boost'):
            dmg *= 2
            bd['charge_boost'] = False
            log.append('⚡ 蓄力爆發！')
        crit = False
        if random.randint(1, 100) <= player_crt:
            dmg = int(dmg * bd.get('player_crit_dmg', 2.0))
            crit = True
            log.append('💥 爆擊！')
        target_monster['hp'] = max(0, target_monster['hp'] - dmg)
        log.append(f'⚔️ 對 {target_monster["name"]} 造成 {dmg} 點傷害')

    elif action == 'skill' and skill_id:
        skill = next((s for s in bd.get('skills', []) if s['id'] == skill_id), None)
        if not skill:
            return jsonify({'error': 'Skill not found'}), 400
        # Check MP
        if bd['player_mp'] < skill['mp_cost']:
            log.append(f'❌ MP 不足！需要 {skill["mp_cost"]} MP')
            bd['turns'].append({'action': action, 'skill_id': skill_id, 'log': log, 'target_idx': target_idx, 'mp_used': 0})
            db.execute("UPDATE expeditions SET expedition_data=? WHERE id=?", (json.dumps(bd), exp['id']))
            db.commit()
            bd['battle_result'] = 'fighting'
            return jsonify(bd)
        bd['player_mp'] -= skill['mp_cost']

        target = skill.get('target', 'enemy')
        base = skill.get('base_value', 0)
        per_lv = skill.get('per_level', 0)
        attr_scale = skill.get('attr_scale', 'none')

        # Get building level for this skill
        bldg_level = 1
        bldg_skills = db.execute(
            "SELECT b.level FROM buildings b JOIN building_defs bd ON b.def_id=bd.id "
            "WHERE b.kid_id=? AND bd.id=? AND b.stored=0", (kid_id, skill['bldg_def_id'])
        ).fetchone()
        if bldg_skills:
            bldg_level = bldg_skills['level']

        if target == 'self':
            # Handle buffs
            if skill['name'] == '蓄力' or skill['effect_type'] == 'buff':
                bd['charge_boost'] = True
                log.append(f'🔥 {skill["name"]}！{skill.get("description","")}')
            else:
                log.append(f'🔥 {skill["name"]}！')

        elif target == 'enemy':
            dmg = _calc_skill_damage(skill, base, per_lv, bldg_level, attr_scale, bd)
            if bd.get('charge_boost'):
                dmg *= 2
                bd['charge_boost'] = False
                log.append('⚡ 蓄力爆發！')
            target_monster['hp'] = max(0, target_monster['hp'] - dmg)
            log.append(f'{skill["icon"]} {skill["name"]}！造成 {dmg} 點傷害！')

        elif target == 'all_enemies':
            for m in monsters:
                if m['hp'] <= 0: continue
                dmg = _calc_skill_damage(skill, base, per_lv, bldg_level, attr_scale, bd, 0.7)
                m['hp'] = max(0, m['hp'] - dmg)
            log.append(f'{skill["icon"]} {skill["name"]}！全體 {len([m for m in monsters if m["hp"]>0])} 隻受到傷害！')

        elif target == 'ally' or target == 'all_allies':
            heal = _calc_skill_heal(skill, base, per_lv, bldg_level, attr_scale, bd.get('player_int', 0))
            if target == 'ally':
                # Heal player
                bd['player_hp'] = min(bd['player_max_hp'], bd['player_hp'] + heal)
                log.append(f'{skill["icon"]} {skill["name"]}！回復 {heal} HP')
            else:
                bd['player_hp'] = min(bd['player_max_hp'], bd['player_hp'] + heal)
                log.append(f'{skill["icon"]} {skill["name"]}！回復 {heal} HP')

    elif action == 'defend':
        defending = True
        bd['charge_boost'] = True
        # 防禦時暫減 30% 傷害
        log.append('🛡️ 蓄力！下一擊傷害 x2')

    elif action == 'flee':
        bd['status'] = 'fled'
        log.append('🏃 逃跑成功！')
        bd['turns'].append({'action': action, 'log': log})
        db.execute("UPDATE expeditions SET status='completed', expedition_data=? WHERE id=?", (json.dumps(bd), exp['id']))
        db.commit()
        bd['battle_result'] = 'fled'
        return jsonify(bd)
    # Check all monsters defeated
    if all(m['hp'] <= 0 for m in monsters):
        bd['status'] = 'won'
        log.append('🎉 擊敗所有怪物！')
        bd['turns'].append({'action': action, 'log': log, 'target_idx': target_idx, 'mp_used': 0 if action != 'skill' else (skill['mp_cost'] if skill_id else 0)})
        _award_battle_rewards(db, kid_id, bd, monsters)
        if bd.get('is_boss'):
            _award_boss_rewards(db, kid_id, bd)
        else:
            _record_daily_battle(db, kid_id, bd)
        db.execute("UPDATE expeditions SET status='completed', expedition_data=? WHERE id=?",
                   (json.dumps(bd), exp['id']))
        db.commit()
        bd['battle_result'] = 'won'
        return jsonify(bd)

    # --- Monster counter-attack (recompute alive targets after player action) ---
    alive_after = [m for m in monsters if m['hp'] > 0]
    if not defending and alive_after:
        attacker = alive_after[0]
        log_line, dmg = _monster_counterattack(bd, attacker, player_def)
        log.append(log_line)
        if dmg > 0:
            bd['player_hp'] -= dmg

    # Check player defeated
    if bd['player_hp'] <= 0:
        bd['player_hp'] = 0
        bd['status'] = 'lost'
        log.append('💀 你被打敗了...')
        bd['turns'].append({'action': action, 'log': log, 'target_idx': target_idx, 'mp_used': 0 if action != 'skill' else (skill['mp_cost'] if skill_id else 0)})
        db.execute("UPDATE expeditions SET status='completed', expedition_data=? WHERE id=?", (json.dumps(bd), exp['id']))
        db.commit()
        bd['battle_result'] = 'lost'
        return jsonify(bd)

    bd['turns'].append({'action': action, 'log': log, 'target_idx': target_idx, 'mp_used': 0 if action != 'skill' else (skill['mp_cost'] if skill_id else 0)})
    db.execute("UPDATE expeditions SET expedition_data=? WHERE id=?", (json.dumps(bd), exp['id']))
    db.commit()
    bd['battle_result'] = 'fighting'
    return jsonify(bd)


def _monster_counterattack(bd, attacker, player_def):
    """Monster counter-attack with 先手 (spd) + 回避 (dodge). Returns (log, damage)."""
    if bd.get('player_spd', 0) > attacker.get('spd', 0):
        return (f'💨 先手！{attacker["name"]} 未及反擊', 0)
    if bd.get('player_dodge', 0) > 0 and random.randint(1, 100) <= bd['player_dodge']:
        return (f'💨 回避！{attacker["name"]} 攻擊落空', 0)
    dmg = max(0, attacker['atk'] - player_def + random.randint(0, 2))
    if dmg > 0:
        return (f'🐾 {attacker["name"]} 反擊 {dmg} 點傷害', dmg)
    return ('🛡️ 擋住攻擊！', 0)


def _calc_skill_damage(skill, base, per_lv, bldg_level, attr_scale, bd, mult=1.0):
    """Calculate skill damage. Physical scales from 臂力(str), magic from 知識(int)."""
    attr_bonus = 0
    if attr_scale == 'str':
        attr_bonus = bd.get('player_str', 0)
    elif attr_scale == 'int':
        attr_bonus = bd.get('player_int', 0)
    dmg = int((base + per_lv * bldg_level + attr_bonus) * mult)
    return max(1, dmg + random.randint(0, 3))


def _calc_skill_heal(skill, base, per_lv, bldg_level, attr_scale, player_int=0):
    """Calculate skill heal amount. Scales from 知識(int)."""
    attr_bonus = 0
    if attr_scale == 'int':
        attr_bonus = int(player_int * 0.8)
    heal = int(base + per_lv * bldg_level + attr_bonus)
    return max(1, heal + random.randint(0, 2))


DROP_RARITIES = ['common', 'rare', 'epic', 'legendary']
DROP_BASE_WEIGHTS = {'common': 70.0, 'rare': 22.0, 'epic': 7.0, 'legendary': 1.0}
DROP_TABLE = {
    'common': [('wood', 1), ('wood', 2)],
    'rare': [('brick', 1), ('fur', 1), ('gear', 1)],
    'epic': [('gem', 1), ('gem', 1)],
    'legendary': [('dragon_scale', 1)],
}


def roll_drop(tier=1, pity_count=0):
    """Roll a drop rarity. Higher tier → more epic/legendary; pity>=30 guarantees epic+."""
    t = max(1, tier)
    w = dict(DROP_BASE_WEIGHTS)
    w['epic'] += (t - 1) * 1.5
    w['legendary'] += (t - 1) * 0.3
    if pity_count >= 30:
        w['common'] = 0.0
        w['rare'] = 0.0
    total = sum(w.values())
    r = random.random() * total
    acc = 0.0
    for rarity in DROP_RARITIES:
        acc += w[rarity]
        if r < acc:
            return rarity
    return 'common'


def _record_daily_battle(db, kid_id, bd):
    """Record a daily region win (打贏先計 — only regular battles, not boss)."""
    if bd.get('is_boss'):
        return
    today = date.today().isoformat()
    db.execute("INSERT OR IGNORE INTO daily_battles (kid_id, region_id, battle_date) VALUES (?,?,?)",
               (kid_id, bd.get('region_id', 1), today))


def _award_battle_rewards(db, kid_id, bd, monsters=None):
    """Award gold + materials + EXP for a won battle."""
    gold = bd.get('gold_reward', 20)
    mats = bd.get('mat_reward', {})

    # Gold (scale with number of monsters)
    num_monsters = len(monsters) if monsters else 1
    gold = gold * num_monsters

    # Gold
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if kid:
        db.execute("UPDATE kids SET points=points+? WHERE id=?", (gold, kid_id))
        db.execute("INSERT INTO points_log (kid_id, amount, reason) VALUES (?,?,?)",
                   (kid_id, gold, "Battle win"))

    # Materials (guaranteed base drop)
    for item_type, qty in mats.items():
        add_item(kid_id, item_type, qty, db)

    # Bonus drop (rarity-based, tier-scaled)
    tier = bd.get('region_id', 1) or 1
    pity = get_pity_count(db, kid_id)
    rarity = roll_drop(tier, pity)
    update_pity(db, kid_id, rarity)
    pool = DROP_TABLE.get(rarity, [])
    bd['drop_rarity'] = rarity
    if pool:
        item_type, qty = random.choice(pool)
        bd['drop_item'] = item_type
        bd['drop_qty'] = qty
        add_item(kid_id, item_type, qty, db)

    # EXP (tier-scaled)
    if kid:
        exp_amount = exp_reward_for_tier(tier)
        new_exp = kid['experience'] + exp_amount
        new_level, _ = calc_level(new_exp)
        stat_gained = max(0, new_level - kid['level'])
        db.execute("UPDATE kids SET experience=?, level=?, stat_points=stat_points+? WHERE id=?",
                   (new_exp, new_level, stat_gained, kid_id))

        # 里程碑獎勵 (Lv 10/25/50/100/...)
        crossed = check_milestones(kid['level'], new_level)
        for m in crossed:
            add_item(kid_id, 'gem', 3, db)

    # Mark region explored
    db.execute("INSERT OR IGNORE INTO explored_regions (kid_id, region_id) VALUES (?,?)",
               (kid_id, bd.get('region_id', 1)))


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
    buildings = db.execute('''
        SELECT b.*, bd.name, bd.icon, bd.buff_type, bd.buff_vals, bd.effect, bd.materials, bd.max_level
        FROM buildings b JOIN building_defs bd ON b.def_id=bd.id WHERE b.kid_id=? AND b.stored=0
    ''', (kid_id,)).fetchall()
    inventory = db.execute("SELECT * FROM inventory WHERE kid_id=?", (kid_id,)).fetchall()
    explored = db.execute("SELECT * FROM explored_regions WHERE kid_id=?", (kid_id,)).fetchall()
    # 清理 stale running expedition (避免 frontend 顯示過期嘅 running battle)
    _clean_stale_expeditions_db(db)
    running_exp = db.execute("SELECT * FROM expeditions WHERE kid_id=? AND status='running' ORDER BY start_time DESC LIMIT 1", (kid_id,)).fetchone()
    achievements = db.execute("SELECT * FROM achievements WHERE kid_id=? ORDER BY earned_at DESC", (kid_id,)).fetchall()
    streak = db.execute("SELECT * FROM streaks WHERE kid_id=?", (kid_id,)).fetchone()
    tiles = db.execute("SELECT cell_x, cell_y, tile_type FROM town_tiles WHERE kid_id=?", (kid_id,)).fetchall()
    return jsonify({
        'kid': kid_hud(kid),
        'buildings': rows_to_list(buildings),
        'inventory': rows_to_list(inventory),
        'explored': rows_to_list(explored),
        'expedition': row_to_dict(running_exp) if running_exp else None,
        'achievements': rows_to_list(achievements),
        'streak': row_to_dict(streak) if streak else None,
        'tiles': [dict(t) for t in tiles],
    })

# -- Town Tiles API --

@app.route('/api/kids/<int:kid_id>/tiles', methods=['POST'])
def place_town_tile(kid_id):
    """Place a decoration tile (road, tree, fence) on the town map."""
    data = request.get_json(silent=True) or {}
    cell_x = data.get('cell_x')
    cell_y = data.get('cell_y')
    tile_type = data.get('tile_type', 'road')
    
    if cell_x is None or cell_y is None:
        return jsonify({'error': 'cell_x and cell_y required'}), 400
    if not isinstance(cell_x, int) or not isinstance(cell_y, int):
        return jsonify({'error': 'cell_x and cell_y must be integers'}), 400
    if cell_x < 0 or cell_x > 23 or cell_y < 0 or cell_y > 15:
        return jsonify({'error': 'cell out of range (0-23, 0-15)'}), 400
    if tile_type not in ('road', 'tree', 'fence'):
        return jsonify({'error': 'invalid tile_type'}), 400
    
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404
    
    # Check no building occupies this cell (buildings occupy center 2×2 of 4×4 plot)
    building_plot_x = cell_x // 4
    building_plot_y = cell_y // 4
    # Center 2×2 of 4×4 block = cells [1,2] within the block
    cell_in_block_x = cell_x % 4
    cell_in_block_y = cell_y % 4
    if 1 <= cell_in_block_x <= 2 and 1 <= cell_in_block_y <= 2:
        plot_idx = building_plot_y * 6 + building_plot_x
        existing_bld = db.execute(
            "SELECT id FROM buildings WHERE kid_id=? AND plot_idx=?", (kid_id, plot_idx)
        ).fetchone()
        if existing_bld:
            return jsonify({'error': 'Cell occupied by a building'}), 409
    
    # Check no existing tile at this cell
    existing_tile = db.execute(
        "SELECT id FROM town_tiles WHERE kid_id=? AND cell_x=? AND cell_y=?",
        (kid_id, cell_x, cell_y)
    ).fetchone()
    if existing_tile:
        # Remove tile (free placement)
        db.execute("DELETE FROM town_tiles WHERE id=?", (existing_tile['id'],))
        db.commit()
        return jsonify({'action': 'removed', 'cell_x': cell_x, 'cell_y': cell_y})
    
    # Place tile - cost small gold
    cost = {'road': 10, 'tree': 5, 'fence': 15}.get(tile_type, 10)
    if kid['points'] < cost:
        return jsonify({'error': f'Not enough gold ({cost} needed)'}), 400
    db.execute("UPDATE kids SET points=points-? WHERE id=?", (cost, kid_id))
    db.execute("INSERT INTO town_tiles (kid_id, cell_x, cell_y, tile_type) VALUES (?, ?, ?, ?)",
               (kid_id, cell_x, cell_y, tile_type))
    db.commit()
    return jsonify({'action': 'placed', 'cell_x': cell_x, 'cell_y': cell_y, 'tile_type': tile_type, 'cost': cost})

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
    actor = current_actor()
    if not actor:
        return _unauthorized()
    if actor['role'] != 'admin' or actor.get('must_change_password'):
        return _forbidden()
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

    # Never accept the historical default admin credentials.
    if _is_default_admin_login(username, password):
        return jsonify({'error': 'Invalid credentials'}), 403
    
    db = get_db()
    
    # 1. Try kid login (PIN)
    kid = db.execute("SELECT * FROM kids WHERE username=?", (username,)).fetchone()
    if kid:
        auth = db.execute("SELECT * FROM kid_auth WHERE kid_id=?", (kid['id'],)).fetchone()
        if auth and verify_password(password, auth['pin']):
            if _needs_rehash(auth['pin']):
                db.execute(
                    "UPDATE kid_auth SET pin=? WHERE kid_id=?",
                    (hash_password(password), kid['id']),
                )
                db.commit()
            _set_session('kid', kid['id'], kid_id=kid['id'])
            return jsonify({
                'role': 'kid',
                'user': public_kid(kid),
                'redirect': '/kids/'
            })
        return jsonify({'error': '密碼錯誤'}), 403
    
    # 2. Try parent login
    parent = db.execute("SELECT * FROM parents WHERE username=?", (username,)).fetchone()
    if parent:
        if verify_password(password, parent['password']):
            if _needs_rehash(parent['password']):
                db.execute(
                    "UPDATE parents SET password=? WHERE id=?",
                    (hash_password(password), parent['id']),
                )
                db.commit()
            # Get linked kids
            linked = db.execute("""
                SELECT k.* FROM kids k
                JOIN parent_kid pk ON k.id = pk.kid_id
                WHERE pk.parent_id = ?
            """, (parent['id'],)).fetchall()
            _set_session('parent', parent['id'], parent_id=parent['id'])
            return jsonify({
                'role': 'parent',
                'user': {'id': parent['id'], 'username': parent['username'], 'name': parent['name']},
                'kids': [public_kid(r) for r in linked],
                'redirect': '/kids/manage'
            })
        return jsonify({'error': '密碼錯誤'}), 403
    
    # 3. Try admin login
    admin = db.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
    if admin:
        if verify_password(password, admin['password']):
            _set_session('admin', admin['id'], admin_id=admin['id'], role='admin')
            return jsonify({
                'role': 'admin',
                'user': {'id': admin['id'], 'username': admin['username'], 'name': admin['name'], 'role': admin['role']},
                'redirect': '/kids/admin'
            })
        return jsonify({'error': '密碼錯誤'}), 403
    
    return jsonify({'error': '帳號不存在'}), 404


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """Clear the Flask session so later write APIs return 401.

    Tiny harness-visible logout path used by the UI 登出 button and FE-P0-06.
    Idempotent when already anonymous.
    """
    session.clear()
    session.modified = True
    return jsonify({'ok': True})


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
    if len(password) < 8:
        return jsonify({'error': '密碼至少 8 個字元'}), 400
    
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
    """Link a parent to a kid (by kid_id). Session parent_id wins over body."""
    actor = current_actor()
    if not actor:
        return _unauthorized()
    if actor['role'] not in ('parent', 'admin'):
        return _forbidden()
    data = request.get_json(silent=True) or {}
    body_parent_id = data.get('parent_id')
    kid_username = (data.get('kid_username') or '').strip().lower()

    if actor['role'] == 'parent':
        if body_parent_id is not None and int(body_parent_id) != actor['parent_id']:
            return _forbidden()
        parent_id = actor['parent_id']
    else:
        parent_id = body_parent_id
    
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


@app.route('/api/auth/create-kid', methods=['POST'])
def create_kid():
    """Parent creates a kid account (kids + kid_auth PIN + parent_kid auto-link)."""
    actor = current_actor()
    if not actor:
        return _unauthorized()
    if actor['role'] not in ('parent', 'admin'):
        return _forbidden()
    data = request.get_json(silent=True) or {}
    body_parent_id = data.get('parent_id')
    name = (data.get('name') or '').strip()
    username = (data.get('username') or '').strip().lower()
    pin = (data.get('pin') or '').strip()
    avatar = data.get('avatar', '👦')

    if actor['role'] == 'parent':
        if body_parent_id is not None and int(body_parent_id) != actor['parent_id']:
            return _forbidden()
        parent_id = actor['parent_id']
    else:
        parent_id = body_parent_id

    if not parent_id or not name or not username or not pin:
        return jsonify({'error': 'parent_id、name、username、pin 都需要'}), 400
    if not VALID_USERNAME.match(username):
        return jsonify({'error': '用戶名必須為 2-30 個英文字母、數字或底線'}), 400
    if len(pin) < 4:
        return jsonify({'error': 'PIN 至少 4 個字元'}), 400

    db = get_db()
    parent = db.execute("SELECT * FROM parents WHERE id=?", (parent_id,)).fetchone()
    if not parent:
        return jsonify({'error': 'Parent not found'}), 404

    # username 唯一 (kids / parents / admins)
    if db.execute("SELECT id FROM kids WHERE username=?", (username,)).fetchone():
        return jsonify({'error': '用戶名已被使用'}), 409
    if db.execute("SELECT id FROM parents WHERE username=?", (username,)).fetchone():
        return jsonify({'error': '用戶名已被使用'}), 409
    if db.execute("SELECT id FROM admins WHERE username=?", (username,)).fetchone():
        return jsonify({'error': '用戶名已被使用'}), 409

    # 建立 kid (其他欄位用 DEFAULT)；新手包一次過發放（§6.6 starter_granted）
    cur = db.execute(
        "INSERT INTO kids (name, username, avatar, color) VALUES (?, ?, ?, ?)",
        (name, username, avatar, '#3b82f6')
    )
    kid_id = cur.lastrowid
    db.execute("INSERT INTO kid_auth (kid_id, pin) VALUES (?, ?)", (kid_id, hash_password(pin)))
    # auto-link 到呢個家長
    db.execute("INSERT INTO parent_kid (parent_id, kid_id) VALUES (?, ?)", (parent_id, kid_id))
    grant_starter_pack_once(db, kid_id)
    if username == PREVIEW_KID_USERNAME:
        ensure_preview_kid(db)
    db.commit()

    kid = db.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    return jsonify({'ok': True, 'kid': public_kid(kid)}), 201


@app.route('/api/auth/parent-kids', methods=['GET'])
def parent_kids():
    """Get kids linked to the session parent. Query parent_id is ignored."""
    actor = current_actor()
    if not actor:
        return _unauthorized()
    if actor['role'] == 'parent':
        parent_id = actor['parent_id']
    elif actor['role'] == 'admin':
        parent_id = request.args.get('parent_id')
        if not parent_id:
            return jsonify({'error': 'parent_id required'}), 400
    else:
        return _forbidden()
    
    db = get_db()
    kids = db.execute("""
        SELECT k.* FROM kids k
        JOIN parent_kid pk ON k.id = pk.kid_id
        WHERE pk.parent_id = ?
    """, (parent_id,)).fetchall()
    return jsonify([public_kid(r) for r in kids])


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

@app.route('/mock-horizontal')
@app.route('/mock-horizontal/')
def serve_mock_horizontal():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'mock-horizontal.html')
    if os.path.isfile(path):
        return open(path, encoding='utf-8').read()
    return '<h1>mock page not found</h1>', 404

@app.route('/character-panel')
@app.route('/character-panel/')
def serve_character_panel():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'character-panel.html')
    if os.path.isfile(path):
        return open(path, encoding='utf-8').read()
    return '<h1>character panel not found</h1>', 404

@app.route('/health')
@app.route('/health/')
def redirect_health():
    return '<script>window.location.href="/dashboard/?tab=health"</script><a href="/dashboard/?tab=health">Health Dashboard</a>'

# ── Main ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    migrate_db()
    migrate_db_v3()
    migrate_db_v4()
    seed_building_defs()
    seed_skill_defs()
    bootstrap_admin_if_configured()
    _preview_db = sqlite3.connect(DB_PATH)
    _preview_db.row_factory = sqlite3.Row
    ensure_preview_kid(_preview_db)
    _preview_db.close()

    # Auto‑clean stale expeditions (status='running' but past end_time)
    _clean_stale_expeditions()
    
    print('🎮 Kids Town 3.0 Backend (Role-based Auth) on http://0.0.0.0:9123')
    app.run(host='0.0.0.0', port=9123, debug=False)
