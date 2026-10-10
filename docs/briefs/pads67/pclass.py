"""pads67: class every P run of pad_edge_read by WHAT the engine says of the pad|cell pair.
usage: pclass.py ICAO [--list N]   (reads edge_ICAO.json, pairs_ICAO.json, /tmp/harness/sw8_ICAO.{osm.axes.json,v2/ICAO.graded.json})
T28      the pair is in pad_frontage_gs's population and HELD AS A TERRACE (DEM step > frontage_step_max_m; RULINGS 13o/13p/18c (1))
ARMED    the pair is in the population and ARMED (the cell's frontage should take the pad's level) — and it still stands > 1 m off
GAP      the cell is a gap piece (late stage), not a §28 pair
GS-NEAR  groundside cell across a sliver, not in the §28 population
GS-TOUCH groundside cell sharing a vertex with the pad, leaving it by > 1 m inside 10 m
AIR-NEAR / AIR-TOUCH  the same for an airside cell"""
import json, sys, collections
A = sys.argv[1]; W = sys.argv[0].rsplit('/', 1)[0]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 0
E = json.load(open(f'{W}/edge_{A}.json')); S = json.load(open(f'/tmp/harness/sw8_{A}.osm.axes.json'))
G = json.load(open(f'/tmp/harness/sw8_{A}.v2/{A}.graded.json'))
try: PR = json.load(open(f'{W}/pairs_{A}.json'))['pairs']
except FileNotFoundError: PR = None
side = {f"{f['role']}:{f['ref']}": f.get('side') for f in G['faces']}
pair = {(p['pad_ref'], p['gs_ref']): p for p in PR or []}
plat = collections.defaultdict(list)
for p in S.get('platforms') or []: plat[p['ref']].append(p)
STEPMAX = 2.4
rows = []
for r in E['runs']:
    if r['cls'] != 'P': continue
    cs = [c for c in r['cells'] if c['kind'] == 'pavement' and c['dist_m'] <= E['standoff_m'] and abs(c['off_m'] if c['touching'] else c['step_m']) > E['off_m']]
    c = max(cs, key=lambda c: abs(c['off_m'] if c['touching'] else c['step_m']))
    ref = c['cell'].split(':', 1)[1]; pr = pair.get((r['pad'], ref)) or pair.get((r['pad'], ref.split('#')[0])) or pair.get((r['pad'].split('/')[0], ref.split('/')[0]))
    air = side.get(c['cell']) == 'airside'
    if ref.startswith('gap:'): k = 'GAP'
    elif pr: k = 'T28' if abs(pr['step']) > STEPMAX else 'ARMED'
    elif air: k = 'AIR-TOUCH' if c['touching'] else 'AIR-NEAR'
    else: k = 'GS-TOUCH' if c['touching'] else 'GS-NEAR'
    pl = plat.get(r['pad']) or plat.get(r['pad'].split('/')[0]) or [{}]
    p = pl[0]
    rows.append(dict(k=k, pad=r['pad'], site=r['site'], n=r['vertices'], L=r['length_m'], cell=c['cell'], dist=c['dist_m'], step=c['step_m'], off=c['off_m'], grade=c['grade_pct'],
                     welded=p.get('welded'), datum=p.get('datum', p.get('level')), band=p.get('reach_band'), dem_step=pr and round(pr['step'], 2), rim=r['rim_z'][0], ground=r['ground_off_m']))
json.dump(rows, open(f'{W}/pclass_{A}.json', 'w'), indent=1)
by = collections.defaultdict(list)
for x in rows: by[x['k']].append(x)
print(f"{A}: P runs {len(rows)}" + ('' if PR is not None else '  (NO §28 pairs file: T28/ARMED not separated)'))
for k in ('T28', 'ARMED', 'GAP', 'GS-NEAR', 'GS-TOUCH', 'AIR-NEAR', 'AIR-TOUCH'):
    v = sorted(by.get(k, []), key=lambda x: -abs(x['off']))
    if not v: continue
    print(f"  {k:9s} runs {len(v):3d}  vertices {sum(x['n'] for x in v):4d}  {sum(x['L'] for x in v):6.0f} m  pads {len({x['pad'] for x in v})}  worst {max(abs(x['off']) for x in v):.2f}  median dist {sorted(x['dist'] for x in v)[len(v)//2]:.2f}")
    for x in v[:N]:
        inband = None if not x['band'] or None in x['band'] or x['datum'] is None else (x['band'][0] <= x['rim'] + x['step'] <= x['band'][1])
        print(f"      {x['pad']:22s} {x['site'][0]:.11f}, {x['site'][1]:.11f} rim {x['rim']:.2f} {x['cell'][:40]:40s} d {x['dist']:.2f} step {x['step']:+.2f} off {x['off']:+.2f} grade {x['grade']:.0f}% | welded {x['welded']} band {x['band']} target-in-band {inband} dem_step {x['dem_step']} n {x['n']} L {x['L']}")
