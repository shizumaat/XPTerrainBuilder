"""pads67: one airport's table row. usage: row.py ICAO"""
import json, sys, collections
A = sys.argv[1]; W = sys.argv[0].rsplit('/', 1)[0]; H = '/tmp/harness'; R = 'surf337b' if A == 'OTHH' else 'sw7'
def L(p): return json.load(open(p))
ra, rb = L(f'{H}/{R}_{A}.result.json'), L(f'{H}/sw8_{A}.result.json')
print(f"{A}: body {ra['body_sha256'][:12]} -> {rb['body_sha256'][:12]}  build {ra.get('build_seconds')} -> {rb.get('build_seconds')} s")
j = L(f'{W}/avd_{A}.json')
for fr, f in j['frames'].items():
    mv = f['moved']
    rw = [m for m in mv if m.get('family') == 'runway' or any(r in ('runway', 'runway_crossing') for r in m.get('roles', []))]
    print(f"   frame {fr}: moved>0.02 {len(mv)} worst {max([abs(m['dz_m']) for m in mv] or [0]):.2f} | runway-role {len(rw)}" + (f" worst {max(abs(m['dz_m']) for m in rw):.2f}" if rw else ''))
sa, sb = L(f'{H}/{R}_{A}.osm.axes.json'), L(f'{H}/sw8_{A}.osm.axes.json')
for n, sc in (('ref', sa), ('sw8', sb)):
    hc = collections.Counter(q.get('tier') for q in sc.get('hard_conflict') or [])
    pl = sc.get('platforms') or []
    w = [int(p.get('welded') or 0) for p in pl]
    print(f"   {n}: hard_conflict {dict(sorted(hc.items(), key=str))} | platforms {len(pl)} welded total {sum(w)} pads with welded>0 {sum(1 for x in w if x)} released {sum(int(p.get('released') or 0) for p in pl)} warned {sum(1 for p in pl if p.get('warned'))} widened {[p['ref'] for p in pl if p.get('weld_widened')]}")
print('   per-pad welded (sw8):', ' '.join(f"{p['ref']}:{int(p.get('welded') or 0)}" for p in sorted(sb.get('platforms') or [], key=lambda p: -int(p.get('welded') or 0))))
def rd(p):
    d = L(p); d = d[0] if isinstance(d, list) else d
    return d.get('reports', [d])[0] if 'reports' in d else d
ca, cb = rd(f'{W}/census_{R}_{A}.json'), rd(f'{W}/census_sw8_{A}.json')
for n, c in (('ref', ca), ('sw8', cb)):
    ck = c.get('cockpit') or {}
    cm, cv = ck.get('critical_motion') or {}, ck.get('critical_visual') or {}
    print(f"   {n}: adjudicated airside {c.get('adjudicated_airside_for_acceptance')} | CRITICAL motion {cm.get('n')} {cm.get('by_family')} | CRITICAL visual {cv.get('n')} {cv.get('by_family')}")
