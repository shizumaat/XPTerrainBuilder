"""pads67: for each P run, the nearest declared terrace joint of the sidecar (kind, step, distance). usage: tjoin.py ICAO"""
import json, math, sys, collections
A=sys.argv[1]; W=sys.argv[0].rsplit('/',1)[0]
b=json.load(open(f'/tmp/harness/sw8_{A}.osm.axes.json')); R=json.load(open(f'{W}/pclass_{A}.json'))
def d(p,q): return math.hypot((p[0]-q[0])*110574,(p[1]-q[1])*111320*math.cos(math.radians(p[0])))
out=collections.Counter()
for x in R:
    best=(1e9,None)
    for t in b.get('terrace_joints') or []:
        for p in t['points']:
            dd=d(x['site'],p)
            if dd<best[0]: best=(dd,t)
    x['tj_dist']=round(best[0],1); x['tj']=best[1] and {k:best[1].get(k) for k in('kind','declared_step_m','roles','length_m')}
    out[(x['k'], 'joint<=12m' if best[0]<=12 else 'no joint')]+=1
json.dump(R,open(f'{W}/pclass_{A}.json','w'),indent=1)
print(A, dict(sorted(out.items())))
print(collections.Counter(t['kind'] for t in b.get('terrace_joints') or []))
for x in R:
    if x['k'].startswith('AIR') : print(f"   {x['k']} {x['pad']:12s} off {x['off']:+.2f} tj {x['tj_dist']} {x['tj']}")
