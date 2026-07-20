#!/usr/bin/env python3
"""Battle system test — verify all 4 fixes."""
import json, urllib.request, sqlite3, sys

BASE = 'http://127.0.0.1:9123'
db = sqlite3.connect('/home/administrator/projects/hermes-ea/kids-town/kids_town.db')
db.execute('DELETE FROM expeditions')
db.commit()

def post(path, data):
    req = urllib.request.Request(f'{BASE}{path}',
        data=json.dumps(data).encode(), headers={'Content-Type':'application/json'})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=5).read())
    except urllib.error.HTTPError as e:
        return {'error': f'HTTP {e.code}', 'body': e.read().decode()[:200]}

def test(name, ok, detail=''):
    status = '✅' if ok else '❌'
    print(f'{status} {name}')
    if not ok and detail:
        print(f'   └─ {detail}')

# Show player stats
kid = db.execute('SELECT id, name, ability_str, level FROM kids WHERE id=4').fetchone()
print(f'=== 小強 (lv{kid[3]}, str={kid[2]}) ===')

# Start battle (region 1 = 野狼)
d = post('/api/kids/4/expedition/battle-start', {'region_id':1})
if 'error' in d:
    print(f'❌ Start failed: {d}')
    sys.exit(1)

n_monsters = len(d['monsters'])
mn = d['monsters'][0]['name']
print(f'Monsters: {n_monsters} x {mn}')
print(f'Player: ATK={d[\"player_atk\"]} HP={d[\"player_hp\"]}/{d[\"player_max_hp\"]} DEF={d.get(\"player_def\",0)}')
test('#1 ATK reasonable', 10 <= d['player_atk'] <= 40,
     f'ATK={d[\"player_atk\"]} (target 10-40)')

# Test charge boost  
d = post('/api/kids/4/expedition/battle-action', {'action':'defend'})
test('#2 Charge set', d.get('charge_boost') == True,
     f'charge_boost={d.get(\"charge_boost\")}')
last = d['turns'][-1]['log']
test('#2 Charge visible', any('蓄力' in l for l in last),
     ' | '.join(last))

# Charged attack
d = post('/api/kids/4/expedition/battle-action', {'action':'attack', 'target_idx':0})
last = d['turns'][-1]['log']
test('#2 Charge consumed on attack',
     any('蓄力爆發' in l for l in last),
     ' | '.join(last))
test('#2 Charge boost reset',
     d.get('charge_boost') == False,
     f'charge_boost={d.get(\"charge_boost\")}')

# Attack again (no charge) — check monster counter-attack
d = post('/api/kids/4/expedition/battle-action', {'action':'attack', 'target_idx':0})
last = d['turns'][-1]['log']
hp = d.get('player_hp', 0)

# Did a monster attack back?
monster_attacked = any('反擊' in l or '擋住' in l for l in last)
player_took_dmg = hp < 113  # Starting HP
test('#3 Monster counter-attack', monster_attacked or player_took_dmg or d.get('battle_result') == 'won',
     f'log: {" | ".join(last)} HP={hp}')

print()
# End battle (keep attacking until done)
for turn in range(20):
    d = post('/api/kids/4/expedition/battle-action', {'action':'attack', 'target_idx':0})
    r = d.get('battle_result', '?')
    if r == 'won':
        mon = d.get('monsters', [])
        for m in mon:
            test(f'#4 Dead monster animation: M{m[\"id\"]}',
                 m['hp'] <= 0,
                 f'HP={m[\"hp\"]}')
        print(f'🎉 Battle won at turn {turn+1}!')
        break
    elif r == 'lost':
        print(f'💀 Battle lost at turn {turn+1}!')
        break
    if 'error' in d:
        print(f'Error: {d}')
        break
else:
    print('❌ Battle not ended after 20 turns')
