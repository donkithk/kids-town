#!/usr/bin/env python3
"""
Kids Town Backend — SQLite + Flask API
Port 9123
v1.1 — Added Transaction Records API (coin change tracking)
"""
import os, sqlite3, json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g
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

def init_db():
    """Create tables if they don't exist."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
        -- Coin change transaction records
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id          INTEGER NOT NULL,
            amount          INTEGER NOT NULL,
            balance_after   INTEGER NOT NULL DEFAULT 0,
            category        TEXT    DEFAULT 'adjustment',
            description     TEXT    DEFAULT '',
            reference_type  TEXT    DEFAULT NULL,
            reference_id    INTEGER DEFAULT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

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
            icon        TEXT    DEFAULT '✅',
            points      INTEGER DEFAULT 10,
            kid_id      INTEGER,
            completed   INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS buildings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            def_id      INTEGER NOT NULL,
            plot_idx    INTEGER NOT NULL,
            level       INTEGER DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            item_id     TEXT NOT NULL,
            quantity    INTEGER DEFAULT 0,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS explored_regions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            region_id   INTEGER NOT NULL,
            explored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS expeditions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id      INTEGER NOT NULL,
            region_id   INTEGER NOT NULL,
            status      TEXT DEFAULT 'active',
            started_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finishes_at TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );
    """)
    db.commit()

    # Migrate: backfill transactions from points_log if table is empty
    count = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    if count == 0:
        migrate_transactions_from_log(db)

    db.close()

def migrate_transactions_from_log(db):
    """Backfill transactions table from existing points_log data."""
    logs = db.execute("""
        SELECT pl.*, k.points AS kid_points
        FROM points_log pl
        JOIN kids k ON pl.kid_id = k.id
        ORDER BY pl.id ASC
    """).fetchall()

    if not logs:
        return

    # Build running balance per kid
    balances = {}
    insert_sql = """
        INSERT INTO transactions (kid_id, amount, balance_after, category, description, reference_type, reference_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    for row in logs:
        kid_id = row['kid_id']
        amount = row['amount']
        reason = row['reason'] or ''
        created_at = row['created_at']

        if kid_id not in balances:
            # Calculate starting balance from points_log sum before this entry
            prior_total = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM points_log WHERE kid_id=? AND id < ?",
                (kid_id, row['id'])
            ).fetchone()[0]
            balances[kid_id] = prior_total

        balances[kid_id] += amount
        balance_after = balances[kid_id]

        # Classify category from reason
        cat = 'adjustment'
        ref_type = None
        ref_id = None
        r = reason.lower()
        if amount > 0 and 'completed task' in r:
            cat = 'task'
            ref_type = 'task'
        elif amount > 0 and 'expedition' in r:
            cat = 'expedition'
            ref_type = 'expedition'
        elif amount < 0 and any(kw in r for kw in ['build', 'built', 'upgraded', 'upgrade']):
            cat = 'building'
            ref_type = 'building'
        elif amount > 0:
            cat = 'earned'
        elif amount < 0:
            cat = 'spent'

        db.execute(insert_sql, (kid_id, amount, balance_after, cat, reason, ref_type, None, created_at))

    db.commit()

def row_to_dict(row):
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]


# ── Transaction Type Helper ─────────────────────────────────────

def classify_tx_category(reason, amount):
    """Derive transaction category from reason text and amount sign."""
    if not reason:
        return 'earned' if amount > 0 else 'spent'
    r = reason.lower()
    if amount > 0 and 'completed task' in r:
        return 'task'
    if amount > 0 and 'expedition' in r:
        return 'expedition'
    if amount < 0 and any(kw in r for kw in ['build', 'built', 'upgraded', 'upgrade']):
        return 'building'
    if amount > 0:
        return 'earned'
    return 'spent'


# ── Transaction Records (Coin Change Ledger) ────────────────────

@app.route('/api/transactions', methods=['GET'])
def list_transactions():
    """Paginated, filterable transaction history per kid."""
    db = get_db()
    kid_id = request.args.get('kid_id', type=int)
    if not kid_id:
        return jsonify({'error': 'kid_id is required'}), 400

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)
    tx_type = request.args.get('type', 'all')
    days = request.args.get('days', 90, type=int)

    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    wheres = ["t.kid_id = ?", "t.created_at >= ?"]
    params = [kid_id, since]

    if tx_type != 'all':
        allowed_cats = ['task', 'building', 'expedition', 'earned', 'spent', 'adjustment']
        if tx_type in allowed_cats:
            wheres.append("t.category = ?")
            params.append(tx_type)

    where_clause = " AND ".join(wheres)
    total = db.execute(
        f"SELECT COUNT(*) FROM transactions t WHERE {where_clause}", params
    ).fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(f"""
        SELECT t.id, t.kid_id, t.amount, t.balance_after, t.category,
               t.description, t.reference_type, t.reference_id, t.created_at,
               k.name AS kid_name, k.avatar AS kid_avatar
        FROM transactions t
        JOIN kids k ON t.kid_id = k.id
        WHERE {where_clause}
        ORDER BY t.created_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()

    items = []
    for r in rows:
        rdict = dict(r)
        # Add display-friendly icon per category
        cat = rdict.get('category', 'adjustment')
        icon_map = {
            'task': '✅',
            'building': '🏗️',
            'expedition': '🗺️',
            'earned': '💰',
            'spent': '💸',
            'adjustment': '🔧',
        }
        rdict['icon'] = icon_map.get(cat, '🪙')
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


@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    """Record a new coin change transaction (earn/spend/adjust)."""
    data = request.get_json(silent=True) or {}

    kid_id = data.get('kid_id')
    if not kid_id:
        return jsonify({'error': 'kid_id is required'}), 400
    try:
        kid_id = int(kid_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'kid_id must be an integer'}), 400

    amount = data.get('amount', 0)
    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return jsonify({'error': 'amount must be an integer'}), 400

    if amount == 0:
        return jsonify({'error': 'amount must be non-zero'}), 400

    category = data.get('category', 'adjustment')
    description = (data.get('description') or '').strip()
    reference_type = data.get('reference_type')
    reference_id = data.get('reference_id')
    if reference_id is not None:
        try:
            reference_id = int(reference_id)
        except (ValueError, TypeError):
            reference_id = None

    allowed_cats = ['task', 'building', 'expedition', 'earned', 'spent', 'adjustment']
    if category not in allowed_cats:
        return jsonify({'error': f'invalid category. Allowed: {", ".join(allowed_cats)}'}), 400

    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404

    # Update kid's points balance
    new_points = kid['points'] + amount
    if new_points < 0:
        return jsonify({'error': 'Insufficient points'}), 400

    db.execute("UPDATE kids SET points = ? WHERE id = ?", (new_points, kid_id))

    # Record in transactions table with running balance
    db.execute(
        """INSERT INTO transactions (kid_id, amount, balance_after, category, description, reference_type, reference_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (kid_id, amount, new_points, category, description, reference_type, reference_id)
    )
    tx_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Also record in points_log for backward compatibility
    log_reason = description or f"{'Earned' if amount > 0 else 'Spent'} {abs(amount)} coins"
    db.execute(
        "INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
        (kid_id, amount, log_reason)
    )

    db.commit()

    tx = db.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    updated_kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()

    return jsonify({
        'transaction': row_to_dict(tx),
        'kid': row_to_dict(updated_kid),
    }), 201


@app.route('/api/transactions/summary', methods=['GET'])
def transaction_summary():
    """Quick stats for the ledger header (balance, today/week/month)."""
    db = get_db()
    kid_id = request.args.get('kid_id', type=int)
    if not kid_id:
        return jsonify({'error': 'kid_id is required'}), 400

    kid = db.execute("SELECT points, name, avatar FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404

    current_balance = kid['points']

    today = datetime.utcnow().strftime('%Y-%m-%d')
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

    today_earned = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE kid_id=? AND amount>0 AND DATE(created_at)=?",
        (kid_id, today)
    ).fetchone()[0]

    week_stats = db.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS earned,
            COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS spent,
            COUNT(*) AS tx_count
        FROM transactions
        WHERE kid_id=? AND created_at >= ?
    """, (kid_id, week_ago)).fetchone()

    month_stats = db.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS earned,
            COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS spent,
            COUNT(*) AS tx_count
        FROM transactions
        WHERE kid_id=? AND created_at >= ?
    """, (kid_id, month_ago)).fetchone()

    # Category breakdown
    cat_breakdown = db.execute("""
        SELECT category, COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE kid_id=? AND created_at >= ?
        GROUP BY category
        ORDER BY total DESC
    """, (kid_id, week_ago)).fetchall()

    return jsonify({
        'current_balance': current_balance,
        'today_earned': today_earned,
        'week_earned': week_stats['earned'],
        'week_spent': week_stats['spent'],
        'week_transactions': week_stats['tx_count'],
        'month_earned': month_stats['earned'],
        'month_spent': month_stats['spent'],
        'month_transactions': month_stats['tx_count'],
        'category_breakdown': rows_to_list(cat_breakdown),
        'kid_name': kid['name'],
        'kid_avatar': kid['avatar'],
    })


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

@app.route('/api/kids/<int:kid_id>', methods=['DELETE'])
def delete_kid(kid_id):
    db = get_db()
    db.execute("DELETE FROM kids WHERE id = ?", (kid_id,))
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

# -- Town (full state for frontend) --

@app.route('/api/kids/<int:kid_id>/town', methods=['GET'])
def get_town(kid_id):
    db = get_db()
    kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    if not kid:
        return jsonify({'error': 'Kid not found'}), 404

    # Buildings
    buildings = db.execute(
        "SELECT * FROM buildings WHERE kid_id = ? ORDER BY plot_idx", (kid_id,)
    ).fetchall()

    # Inventory
    inventory = db.execute(
        "SELECT * FROM inventory WHERE kid_id = ?", (kid_id,)
    ).fetchall()

    # Explored regions
    explored = db.execute(
        "SELECT region_id FROM explored_regions WHERE kid_id = ?", (kid_id,)
    ).fetchall()

    # Expedition
    expedition = db.execute(
        "SELECT * FROM expeditions WHERE kid_id = ? AND status = 'active'",
        (kid_id,)
    ).fetchone()

    return jsonify({
        'kid': row_to_dict(kid),
        'buildings': rows_to_list(buildings),
        'inventory': rows_to_list(inventory),
        'explored': [r['region_id'] for r in explored],
        'expedition': row_to_dict(expedition) if expedition else None
    })

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
    if new_points < 0:
        return jsonify({'error': 'Insufficient points'}), 400

    db.execute("UPDATE kids SET points = ? WHERE id = ?", (new_points, kid_id))
    db.execute(
        "INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
        (kid_id, amount, reason)
    )
    # Also record in transactions
    category = classify_tx_category(reason, amount)
    db.execute(
        "INSERT INTO transactions (kid_id, amount, balance_after, category, description) VALUES (?, ?, ?, ?, ?)",
        (kid_id, amount, new_points, category, reason or ('Earned' if amount > 0 else 'Spent') + ' coins')
    )
    db.commit()

    updated = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
    return jsonify(row_to_dict(updated)), 200

# -- Tasks --

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    db = get_db()
    rows = db.execute("""
        SELECT t.*, k.name AS kid_name, k.avatar AS kid_avatar
        FROM tasks t
        LEFT JOIN kids k ON t.kid_id = k.id
        ORDER BY t.created_at DESC
    """).fetchall()
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

    db = get_db()
    cur = db.execute(
        "INSERT INTO tasks (title, icon, points, kid_id) VALUES (?, ?, ?, ?)",
        (title, icon, points, kid_id)
    )
    db.commit()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(task)), 201

@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task['completed']:
        return jsonify({'error': 'Task already completed'}), 400

    now = datetime.utcnow().isoformat()
    db.execute(
        "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
        (now, task_id)
    )

    # Award points to the assigned kid (if any)
    kid_id = task['kid_id']
    result = {'task': row_to_dict(task), 'points_awarded': task['points'], 'kid': None}
    if kid_id:
        kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
        if kid:
            new_points = kid['points'] + task['points']
            db.execute("UPDATE kids SET points = ? WHERE id = ?", (new_points, kid_id))
            reason = f"Completed task: {task['title']}"
            db.execute(
                "INSERT INTO points_log (kid_id, amount, reason) VALUES (?, ?, ?)",
                (kid_id, task['points'], reason)
            )
            # Also record in transactions
            db.execute(
                "INSERT INTO transactions (kid_id, amount, balance_after, category, description, reference_type, reference_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (kid_id, task['points'], new_points, 'task', reason, 'task', task_id)
            )
            updated_kid = db.execute("SELECT * FROM kids WHERE id = ?", (kid_id,)).fetchone()
            result['kid'] = row_to_dict(updated_kid)

    db.commit()
    result['task'] = row_to_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
    return jsonify(result), 200

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({'ok': True}), 200

# -- Leaderboard --

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    db = get_db()
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

# -- Health check --

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'kids-town-backend'})

# ── Main ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print(f'🎮 Kids Town Backend on http://0.0.0.0:9123')
    app.run(host='0.0.0.0', port=9123, debug=False)
