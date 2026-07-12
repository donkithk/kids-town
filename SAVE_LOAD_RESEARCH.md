# Kids-Town Save/Load System Research

> Task: P3 [Kids-Town] Research: HTML5 game save load system design
> Date: 2026-06-21
> Author: System Dev Team

---

## 1. Current Architecture Assessment

### Data Flow (As-Is)

```
Browser                         Backend (Flask)              Database
┌─────────────────────┐         ┌──────────────────┐        ┌──────────┐
│ index.html          │  fetch  │ backend_v2.py    │  SQL   │ SQLite   │
│ (no framework)      │◄───────►│ port 9123        │◄──────►│ kids_town│
│                     │  REST   │                  │        │ .db      │
│ localStorage:       │         │                  │        └──────────┘
│   kids_town_muted   │         │ /api/kids         │
│ Service Worker:     │         │ /api/tasks        │
│   cache-first       │         │ /api/transactions │
│   network-first API │         │ /api/buildings    │
└─────────────────────┘         └──────────────────┘
```

**Key gap:** 100% online-dependent. When offline:
- API reads fall back to cached responses (stale cache, no writes)
- No queued writes — data loss on offline operations
- Audio mute persists (localStorage) but nothing else

### Game State Data Categories

| Category | Size | Update Freq | Criticality | Current Persistence |
|---|---|---|---|---|
| 🔐 Auth (kid profiles, PIN) | ~1KB/kid | Low | High | Server-only |
| 🪙 Points, gold, XP | ~100B/kid | High (task complete) | High | Server-only |
| 🏗️ Buildings (defs + placed) | ~2KB/kid | Low (build/upgrade) | Medium | Server-only |
| 📦 Inventory (materials) | ~500B/kid | Medium (expedition) | Medium | Server-only |
| 🗺️ Expeditions + regions | ~1KB/kid | Medium | Low-Med | Server-only |
| 📋 Tasks | ~3KB/family | Medium | Medium | Server-only |
| 📜 Transaction logs | ~5KB+/kid | High | Low | Server-only |
| 🏆 Achievements + streaks | ~500B/kid | Low | Low | Server-only |
| 🔊 Audio mute | 5B | Very Low | Very Low | localStorage |
| 🎨 UI preferences (theme, etc.) | ~200B | Very Low | Very Low | None |

---

## 2. Technology Comparison: localStorage vs IndexedDB

### localStorage

| Aspect | Detail |
|--------|--------|
| **Max Size** | 5-10 MB per origin (varies by browser) |
| **Data Model** | Key-value (strings only) |
| **Query** | None — load whole key, parse JSON |
| **Async** | Synchronous (blocks main thread) |
| **Transaction** | None — one atomic write per key |
| **Indexing** | None |
| **Structured data** | JSON-serialized only |
| **Browser support** | All modern + IE8+ |
| **Worker access** | No (not available in Service Worker) |
| **Pros** | Dead simple, synchronous = easy to read/write |
| **Cons** | 5MB cap, sync = blocks UI, no query, no SW access |

**Good for:** Small configs, preferences, mute state, last-selected kid ID

### IndexedDB

| Aspect | Detail |
|--------|--------|
| **Max Size** | Effectively unlimited (browser-dependent, typically >50% of disk) |
| **Data Model** | Object store (structured JS objects) |
| **Query** | Index-based range queries, cursors |
| **Async** | Asynchronous (Promise/request-based) |
| **Transaction** | Full ACID per transaction |
| **Indexing** | Multiple indexes per store |
| **Structured data** | Native — stores any structured-cloneable object (Array, Map, Date, Blob) |
| **Browser support** | All modern + IE10+ |
| **Worker access** | Yes — accessible from Service Worker |
| **Pros** | Large capacity, async = non-blocking, SW-accessible, indexes, transactions |
| **Cons** | Complex API (need wrapper), async means more code |

**Good for:** Full game state, offline cache, sync queue, binary assets

### Recommendation for Kids-Town

**Use both — each for its niche:**

| Storage | Use Case |
|---------|----------|
| localStorage | UI preferences: audio mute, last-selected kid, theme, language |
| IndexedDB | Game state: kids, points, buildings, inventory, tasks, pending write queue |

**Why IndexedDB wins for game state:**
1. Capacity — 5MB localStorage is too tight for full game state with multiple kids
2. Service Worker access — critical for background sync
3. Transaction safety — prevents partial writes during crash
4. Query support — can search "buildings for kid X" without loading everything

---

## 3. Recommended Architecture: Offline-First Save/Load

### Three-Layer Storage Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    React/UI Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Kids View│  │ Town View│  │ Task View│  │ Shop View│   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │        │
│  ┌────▼──────────────▼──────────────▼──────────────▼────┐   │
│  │              Data Access Layer (DAL)                 │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  OfflineManager class                          │  │   │
│  │  │  - read(key) → IndexedDB                       │  │   │
│  │  │  - write(key, data) → IndexedDB + SyncQueue    │  │   │
│  │  │  - sync() → flush queue to API                 │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ localStorage  │  │  IndexedDB   │  │  SyncQueue (IDB) │  │
│  │ (Preferences) │  │ (Game State) │  │ (Pending writes) │  │
│  └──────────────┘  └──────┬───────┘  └────────┬─────────┘  │
│                           │                    │            │
│                    ┌──────▼────────────────────▼─────────┐  │
│                    │      Service Worker (sync)         │  │
│                    │  - on online: flush SyncQueue      │  │
│                    │  - on install: precache state      │  │
│                    └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  Flask API Server    │
                    │  /api/sync/...       │
                    │  backend_v2.py       │
                    └─────────────────────┘
```

### Key Component: OfflineManager Class

```javascript
class OfflineManager {
  constructor(dbName = 'kids-town-db', version = 1) {
    this.dbName = dbName;
    this.version = version;
    this.db = null;
  }

  // ── Open / migrate IndexedDB ──────────────────────────
  async open() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(this.dbName, this.version);
      req.onupgradeneeded = (ev) => this.migrate(ev);
      req.onsuccess = (ev) => { this.db = ev.target.result; resolve(); };
      req.onerror = () => reject(req.error);
    });
  }

  // ── Schema migration ──────────────────────────────────
  migrate(event) {
    const db = event.target.result;
    const oldVersion = event.oldVersion;

    if (oldVersion < 1) {
      // Game state stores
      db.createObjectStore('kids', { keyPath: 'id' });
      db.createObjectStore('buildings', { keyPath: 'id' });
      db.createObjectStore('inventory', { keyPath: 'id' });
      db.createObjectStore('tasks', { keyPath: 'id' });
      db.createObjectStore('achievements', { keyPath: 'id' });
      db.createObjectStore('expeditions', { keyPath: 'id' });

      // Sync queue — pending writes that haven't reached server
      const syncStore = db.createObjectStore('sync_queue', { keyPath: 'id', autoIncrement: true });
      syncStore.createIndex('status', 'status', { unique: false });
      syncStore.createIndex('created_at', 'created_at', { unique: false });
    }

    if (oldVersion < 2) {
      // Added in v2: regions store
      db.createObjectStore('regions', { keyPath: 'id' });
    }

    // Future: add more stores for new features
  }

  // ── Read (cache-first) ────────────────────────────────
  async read(storeName, key) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readonly');
      const req = tx.objectStore(storeName).get(key);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  }

  async readAll(storeName) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readonly');
      const req = tx.objectStore(storeName).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  // ── Write (write-through to IDB, enqueue for server sync) ──
  async write(storeName, data) {
    // 1. Write to local IndexedDB immediately
    await this._writeLocal(storeName, data);

    // 2. Enqueue for server sync
    await this._enqueueSync('write', storeName, data);
  }

  async delete(storeName, key) {
    await this._deleteLocal(storeName, key);
    await this._enqueueSync('delete', storeName, { id: key });
  }

  // ── Internal: direct IDB operations ───────────────────
  async _writeLocal(storeName, data) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readwrite');
      tx.objectStore(storeName).put(data);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async _deleteLocal(storeName, key) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(storeName, 'readwrite');
      tx.objectStore(storeName).delete(key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async _enqueueSync(action, store, data) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_queue', 'readwrite');
      tx.objectStore('sync_queue').add({
        action,      // 'write' | 'delete'
        store,       // 'kids' | 'buildings' | ...
        data,        // the payload
        status: 'pending',
        created_at: Date.now(),
        retries: 0,
      });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  // ── Sync: flush pending writes to server ──────────────
  async sync() {
    const pending = await this._getPendingSyncs();
    if (pending.length === 0) return;

    for (const item of pending) {
      try {
        const resp = await this._sendToServer(item);
        if (resp.ok) {
          await this._removeSyncItem(item.id);
          // Update local IDB with server-assigned ID (for new items)
          if (resp.data && resp.data.id && !item.data.id) {
            item.data.id = resp.data.id;
            await this._writeLocal(item.store, item.data);
          }
        }
      } catch (err) {
        // Increment retry, skip for now
        await this._incrementRetry(item.id);
        if (item.retries >= 5) {
          await this._markFailed(item.id);
        }
      }
    }
  }

  async _getPendingSyncs() {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_queue', 'readonly');
      const index = tx.objectStore('sync_queue').index('status');
      const req = index.getAll('pending');
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  async _removeSyncItem(id) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_queue', 'readwrite');
      tx.objectStore('sync_queue').delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async _incrementRetry(id) {
    // Read current, increment retries
    // (simplified — actual impl needs a read-before-write)
  }

  async _sendToServer(item) {
    let url, method, body;
    if (item.action === 'delete') {
      method = 'DELETE';
      url = `/api/${item.store}/${item.data.id}`;
    } else {
      method = item.data.id ? 'PUT' : 'POST';
      url = `/api/${item.store}${item.data.id ? '/' + item.data.id : ''}`;
      body = item.data;
    }
    const resp = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await resp.json();
    return { ok: resp.ok, data };
  }
}
```

### Initial Load Strategy

```javascript
async function initGame(kidId) {
  const mgr = await getOfflineManager();

  // 1. Try server first (network-first)
  try {
    const data = await fetchAPI(`/api/kids/${kidId}/full-state`);
    // Write response to IndexedDB
    await mgr.write('kids', data.kid);
    await mgr.writeAll('buildings', data.buildings);
    await mgr.writeAll('inventory', data.inventory);
    // ... etc
    return data; // Use server data
  } catch (err) {
    // 2. Offline — load from IndexedDB
    const kid = await mgr.read('kids', kidId);
    const buildings = await mgr.readAll('buildings');
    const inventory = await mgr.readAll('inventory');
    // Show "Offline mode" indicator
    return { kid, buildings, inventory, offline: true };
  }
}
```

---

## 4. Cross-Device Sync Strategies

### Strategy Comparison

| Strategy | Complexity | Offline Support | Conflict Resolution | Kids-Town Fit |
|----------|-----------|-----------------|---------------------|---------------|
| **1. Server-authoritative** (current) | Low | None | Trivial (server wins) | ❌ No offline |
| **2. Last-write-wins** | Low | ✅ Yes | Timestamp-based | ⭐ Best fit for Kids-Town |
| **3. CRDT (Conflict-free Replicated Data Types)** | High | ✅ Yes | Automatic merge | ❌ Overkill |
| **4. Operational Transform** | Very High | ✅ Yes | Operation-based | ❌ Overkill |
| **5. Hybrid (LWW + sync queue)** | Medium | ✅ Yes | Declared per-table | ⭐ Recommended |

### Recommended: Hybrid LWW + Sync Queue

**Principle:** Each data entity has a `updated_at` timestamp. When syncing:
- Server compares `updated_at` from client vs server
- If client timestamp > server timestamp: client data wins (client was offline and made changes)
- If server timestamp > client timestamp: server data wins (another device already updated)
- Return the winning dataset back to client

**Conflict table for Kids-Town entities:**

| Entity | Conflict Rule | Rationale |
|--------|---------------|-----------|
| Points, gold, XP | Server-authoritative (additive) | Points only accumulate, never conflict |
| Buildings | Last-write-wins per building | Only one user per device edits builds |
| Tasks | Parent device wins | Tasks are created/managed on parent's device |
| Kids profile | Last-write-wins per field | Name/avatar changes infrequently |
| Inventory (materials) | Server-authoritative (additive) | Similar to points — only accumulate |
| Expeditions | Server-authoritative | Expedition state managed server-side |
| Transactions | Append-only (no conflict) | Each transaction is a new row |

**For Kids-Town**, the sync is simple because:
- Each family uses 1 device at a time (not real-time multi-device)
- "Conflicts" are rare — kids use tablet, parents use phone
- The game is single-player-per-session

### Sync Flow

```
Offline writes happen
        │
        ▼
Writes queued in IndexedDB sync_queue
        │
        ▼
Browser comes online
  OR Service Worker detects connectivity
        │
        ▼
Sync queue flushed in order:
  for each pending item:
    POST/PUT/DELETE /api/sync/...
         │
         ▼
  Server processes:
    1. Check updated_at on entity
    2. If client newer → apply + return updated
    3. If server newer → return server version
    4. Client updates IndexedDB with server version
         │
         ▼
  Remove item from sync_queue
        │
        ▼
UI refreshes with latest data
```

---

## 5. Data Migration Strategy

### Migration Challenge

As Kids-Town evolves, the schema changes:
- New tables added (expeditions v1→v2, regions v2→v3)
- New fields added to existing objects (task.description, task.recurring)
- Old fields deprecated

### Migration Pattern: Versioned Migration

```javascript
// IndexedDB version = 1, 2, 3, ...
const DB_VERSION = 3;

// Migration table in localStorage (survives IDB reset)
const MIGRATION_KEY = 'kids_town_db_migration';

function getAppliedMigrations() {
  try {
    return JSON.parse(localStorage.getItem(MIGRATION_KEY) || '[]');
  } catch { return []; }
}

function markMigrationApplied(version) {
  const applied = getAppliedMigrations();
  if (!applied.includes(version)) {
    applied.push(version);
    localStorage.setItem(MIGRATION_KEY, JSON.stringify(applied));
  }
}

// Each migration is a pure function
const MIGRATIONS = {
  // v1→v2: Add 'regions' store + add region_id index to expeditions
  2: async (db) => {
    const regionsStore = db.createObjectStore('regions', { keyPath: 'id' });
    // Expeditions store already exists — add index
    const expStore = db.transaction('expeditions', 'versionchange')
                       .objectStore('expeditions');
    expStore.createIndex('region_id', 'region_id', { unique: false });
  },

  // v2→v3: Add 'deleted' flag for soft-delete
  3: async (db) => {
    // Add deleted_at field via schema change
    // (IndexedDB schema changes happen in onupgradeneeded)
  },
};
```

### Server-side Migration (Backend)

The existing Flask backend already uses safe migration:

```python
# Current pattern in backend_v2.py — extend for save/load:
def migrate_db():
    db = sqlite3.connect(DB_PATH)
    cols = [row[1] for row in db.execute("PRAGMA table_info(tasks)").fetchall()]
    if 'game_version' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN game_version TEXT DEFAULT '1.0'")
    if 'updated_at' not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN updated_at TIMESTAMP")
    # Add game_state table for full-state snapshots
    db.execute("""
        CREATE TABLE IF NOT EXISTS game_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id     INTEGER NOT NULL,
            snapshot   TEXT    NOT NULL,  -- JSON blob of full game state
            version    TEXT    NOT NULL,  -- schema version for migration
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        )
    """)
    db.commit()
```

### Game Save/Load API Endpoints

```
POST   /api/save          — Save full game state (bulk)
GET    /api/load?kid_id=N  — Load full game state (bulk)
POST   /api/sync          — Sync queue: process batch of operations
GET    /api/snapshot?kid_id=N — Load last known snapshot (for conflict resolution)
```

### Snapshot Strategy

For quick save/load (e.g., "Save & Exit"), serialize the full game state:

```javascript
// Save snapshot
async function saveGameSnapshot(kidId) {
  const mgr = await getOfflineManager();
  const snapshot = {
    kid:          await mgr.read('kids', kidId),
    buildings:    await mgr.readAll('buildings'),
    inventory:    await mgr.readAll('inventory'),
    expeditions:  await mgr.readAll('expeditions'),
    achievements: await mgr.readAll('achievements'),
    meta: {
      saved_at: Date.now(),
      version: DB_VERSION,
    }
  };

  // Save to IndexedDB
  await mgr.write('game_snapshot', snapshot);

  // If online, save to server too
  if (navigator.onLine) {
    try {
      await fetchAPI('/api/save', {
        method: 'POST',
        body: JSON.stringify({ kid_id: kidId, snapshot }),
      });
    } catch (err) {
      // Will sync later
      await mgr._enqueueSync('write', 'game_snapshot', { kid_id: kidId, snapshot });
    }
  }
}

// Load snapshot
async function loadGameSnapshot(kidId) {
  const mgr = await getOfflineManager();

  // 1. Try server first
  if (navigator.onLine) {
    try {
      const serverData = await fetchAPI(`/api/snapshot?kid_id=${kidId}`);
      if (serverData && serverData.snapshot) {
        // Populate IndexedDB from server data
        await restoreFromSnapshot(serverData.snapshot);
        return serverData.snapshot;
      }
    } catch (err) { /* fall through */ }
  }

  // 2. Fallback to IndexedDB
  const localSnapshot = await mgr.read('game_snapshot', kidId);
  if (localSnapshot) {
    return localSnapshot;
  }

  // 3. No snapshot — load individual stores
  return {
    kid: await mgr.read('kids', kidId),
    buildings: await mgr.readAll('buildings'),
    // ...
  };
}
```

---

## 6. Service Worker Integration

The current Service Worker (`service-worker.js`) caches API responses but has no write-back. **Recommended additions:**

### Background Sync (when offline writes get flushed)

```javascript
// In service-worker.js

// ── Listen for online event → trigger sync ──
self.addEventListener('message', (event) => {
  if (event.data === 'trigger-sync') {
    // Notify all Kids-Town clients to sync
    self.clients.matchAll().then(clients => {
      clients.forEach(client => {
        client.postMessage({ type: 'SYNC_NOW' });
      });
    });
  }
});

// ── Extend fetch handler for sync API ──
// The sync_queue endpoints get special treatment:
// - If online: pass through to server
// - If offline: return a "queued" acknowledgment
```

### Cache Strategy Update

| Endpoint | Strategy | TTL |
|----------|----------|-----|
| `/api/kids` | Network-first, cache fallback | 5 min |
| `/api/tasks` | Network-first, cache fallback | 1 min |
| `/api/buildings` | Network-first, cache fallback | 5 min |
| `/api/save` | Network-only (with offline queue) | N/A |
| `/api/sync` | Network-only (with offline queue) | N/A |
| `/api/snapshot` | Network-first, cache fallback | 10 min |
| Static assets (`.html`, `.js`, `.png`) | Cache-first | Immutable |
| Static assets (`.json`, `.svg`) | Cache-first | 1 day |

---

## 7. Implementation Recommendations for Kids-Town

### Phase 1: Core Offline (Priority: P2)
**Effort:** 2-3 days

1. Create `offline_manager.js` with the OfflineManager class
2. Add IndexedDB schema (v1): all stores + sync_queue
3. Wrap existing API calls with OfflineManager (read/update functions)
4. Add offline indicator banner (already exists in index.html!)
5. Save mute state in both localStorage + IndexedDB

### Phase 2: Sync Queue (Priority: P3)
**Effort:** 1-2 days

1. Wire sync_queue flush on `navigator.onLine` change
2. Add `POST /api/sync` endpoint to backend
3. Add `updated_at` column to all SQLite tables (for conflict detection)
4. Add retry logic with exponential backoff (max 5 retries)

### Phase 3: Full-State Snapshots (Priority: P3)
**Effort:** 1 day

1. Add `game_snapshots` table to backend
2. Implement saveSnapshot/loadSnapshot
3. Add "Save & Exit" button in game UI
4. Auto-save every 5 minutes (when online)

### Phase 4: Cross-Device Sync (Priority: P4)
**Effort:** 2-3 days

1. Implement last-write-wins conflict resolution on server
2. Add device ID tracking to distinguish clients
3. Test sync between phone↔tablet↔desktop
4. Add sync status indicator in UI

### Phase 5: Future-Proofing (Priority: P4)
**Effort:** 3 days

1. Schema migration framework (versioned migrations table)
2. Automated migration tests
3. Snapshot compatibility checks (warn if trying to restore older-format save)

---

## 8. Edge Cases & Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| IndexedDB quota exceeded | Low (game <50MB) | Medium | Implement quota monitor, warn user |
| Sync queue grows unbounded offline | Medium | Low | Cap at 1000 items, oldest-first flush |
| localStorage wiped (iOS Safari) | Medium | High | Don't store critical data in localStorage |
| Two devices conflict on same task | Low | Low | Last-write-wins, inform via UI |
| Browser storage cleared on update | Medium | High | Always sync before update |
| Service Worker cache stale | Medium | Medium | Add version-based cache busting |
| IndexedDB API differences (FireFox vs Safari) | Low | Medium | Use wrapper, test on all 3 |
| Slow sync on reconnect (100+ items) | Low | Low | Process sync in batches of 20 |

---

## 9. Key Decision Matrix

| Decision | Option A | Option B | Winner | Reason |
|----------|----------|----------|--------|--------|
| Primary local storage | localStorage | **IndexedDB** | **IndexedDB** | Capacity, SW access, async |
| Preferences storage | **localStorage** | IndexedDB | **localStorage** | Simplicity, sync = fine for prefs |
| Sync trigger | **onOnline event** | Periodic poll | **onOnline event** | Immediate, no wasted polls |
| Conflict resolution | **Last-write-wins** | CRDT | **Last-write-wins** | Simple, sufficient for Kids-Town |
| Sync queue storage | localStorage | **IndexedDB** | **IndexedDB** | Size, transaction safety |
| Full-state save format | **Single JSON blob** | Per-entity | **Single JSON blob** | Simpler save/load, <50KB total |
| Migration tracking | localStorage meta | IndexedDB schema | **Both** | Schema for structure, localStorage for applied versions |

---

## 10. Appendix: Reference Implementations

### Popular HTML5 Games' Save Strategies

| Game | Storage | Sync | Notes |
|------|---------|------|-------|
| **Cookie Clicker** | localStorage | Manual export | Uses <5MB even after years of play |
| **Stardew Valley** (web) | IndexedDB | Server upload | Per-save snapshots, ~2MB each |
| **Wordle** | localStorage | Server (daily) | Simple, text-only state |
| **GeoGuessr** | IndexedDB | Real-time | Heavier data (maps, images) |
| **Slay the Spire** (web) | IndexedDB | Steam Cloud | Per-run saves, diff-based sync |

**Relevant to Kids-Town:** Cookie Clicker-size data (~500KB) with Stardew Valley-style snapshots.

### Existing Code That Needs Changes

| File | Change |
|------|--------|
| `index.html` | Load `offline_manager.js`, wrap API calls with OfflineManager |
| `service-worker.js` | Add sync message handler, updated cache strategies |
| `backend_v2.py` | Add `updated_at` columns, `/api/sync`, `/api/save`, `/api/snapshot` |
| `kids_town.db` | Migration: add `updated_at` to all tables, create `game_snapshots` table |

---

> **Next Step:** Review with KK to decide Phase 1 implementation priority vs other P2/P3 tasks.
