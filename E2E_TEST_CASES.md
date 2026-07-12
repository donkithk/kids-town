# Kids Town E2E Test Cases

> 每次改 code 之前/之後，用呢份 test cases 驗證
> Run: `cd /home/administrator/projects/hermes-ea/kids-town && python3 /tmp/e2e_verify.py`

---

## TC-01: Task Completion — Gold Award ✅
**Steps:**
```
curl -s http://localhost:9121/api/tasks/{ID}/complete -X POST
```
**Expected:**
- HTTP 200
- `points_awarded > 0`
- `kid.points` increased
- `points_log` has record

---

## TC-02: Task Completion — No Gold for Unassigned ✅
**Steps:**
```
# Create task without kid_id
curl -s -X POST http://localhost:9121/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Test","points":10,"kid_id":null}'
# Complete it
curl -s http://localhost:9121/api/tasks/{ID}/complete -X POST
```
**Expected:**
- HTTP 200
- `points_awarded = 0`
- `kid = null`

---

## TC-03: Recurring Task — No Duplicate on Complete ✅
**Steps:**
```
curl -s http://localhost:9121/api/tasks/{ID}/complete -X POST
python3 -c "import sqlite3; db=sqlite3.connect('/home/administrator/projects/hermes-ea/kids-town/kids_town.db'); print('Count:', db.execute('SELECT COUNT(*) FROM tasks WHERE title=\"做功課\" AND kid_id=1').fetchone()[0])"
```
**Expected:**
- HTTP 200, points_awarded > 0
- task count per (kid_id, title) = 1 (no duplicate spawned)
- task.due_date = tomorrow (completed for today)

---

## TC-04: Recurring Refresh — Daily Reset ✅
**Steps:**
```
curl -s http://localhost:9121/api/tasks/refresh-recurring -X POST
```
**Expected (new day):**
- `count > 0`, tasks reset to `completed=0, due_date=today`

**Expected (same day, already done):**
- `count = 0`

**New logic:** Resets ALL completed recurring tasks UNLESS completed today (checks `DATE(completed_at) < today`)

---

## TC-05: 探險公會 Cost ✅
```
python3 -c "
import sqlite3
db=sqlite3.connect('/home/administrator/projects/hermes-ea/kids-town/kids_town.db')
d=db.execute('SELECT cost_gold, materials FROM building_defs WHERE id=6').fetchone()
print(f'Cost: {d[0]} gold, Materials: {d[1]}')
"
```
**Expected:** cost=600, materials=`{}`

---

## TC-06: Expedition — Start & Claim ✅
**Steps:**
```
# Start (duration 0 = immediate finish)
curl -s -X POST http://localhost:9121/api/kids/1/expedition/start \
  -H 'Content-Type: application/json' \
  -d '{"region_id":1,"duration_hours":0}'

# Claim rewards
curl -s http://localhost:9121/api/kids/1/expedition/claim -X POST \
  -H 'Content-Type: application/json' -d '{}'
```
**Expected:**
- Start: HTTP 201, new expedition with status=running
- Claim: HTTP 200, `gold` >= 10, `materials` dict, possibly `events`

---

## TC-07: Proxy Error Forwarding ✅
**Steps:**
```
# Try claim without running expedition
curl -s http://localhost:9121/api/kids/1/expedition/claim -X POST \
  -H 'Content-Type: application/json' -d '{}'
```
**Expected (no running exp):**
```
{"error": "No running expedition"}
```
**NOT** `{"error": "HTTP Error 400: BAD REQUEST"}` — actual Flask error forwarded

---

## TC-08: Frontend — Only Today's Tasks Visible ✅ (Manual)
**Check:**
- Open `/kids/` in browser
- Should see today's pending tasks (due_date <= today)
- Completed tasks should NOT appear
- Future tasks (due_date > today) should NOT appear
- After completing a task → toast shows gold → task disappears from list

---

## TC-09: Database Consistency ✅
```
python3 -c "
import sqlite3
db=sqlite3.connect('/home/administrator/projects/hermes-ea/kids-town/kids_town.db')
print('FK violations:', db.execute('PRAGMA foreign_key_check').fetchall())
print('Total tasks:', db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0])
print('Recurring per kid:')
for r in db.execute('SELECT kid_id, title, COUNT(*) FROM tasks WHERE recurring!=\"\" GROUP BY kid_id, title').fetchall():
    print(f'  kid {r[0]} | {r[1]:15s} | count={r[2]}')
db.close()
"
```
**Expected:** FK violations = 0, recurring count per (kid,title) = 1

---

## Quick Verification Script
File: `/tmp/e2e_verify.py`

Run with: `python3 /tmp/e2e_verify.py`

Checks:
1. ✅ Complete recurring task → gold awarded
2. ✅ Claim expedition → gold + materials
3. ✅ Refresh recurring → no errors
4. ✅ Backend error log = empty
5. ✅ Tasks state correct (1 per kid+title, due_date=today)
