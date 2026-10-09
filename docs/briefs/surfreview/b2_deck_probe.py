"""B2 intervention, offline: deck_datum_from_surface re-run over the arm's graded
surface with (a) every vertex, (b) gap-piece vertices excluded, (c) main's surface."""
import json, statistics, sys, collections
from shapely.geometry import Polygon
from shapely import contains_xy
import numpy as np
from pyproj import Transformer
MAIN='/tmp/harness/sw6_OTHH.v2'; ARM='/tmp/harness/surf337_OTHH.v2'
def load(d):
    g=json.load(open(f'{d}/OTHH.graded.json')); r=json.load(open(f'{d}/OTHH.rebake.json'))
    return g,r
ga,ra=load(ARM); gm,rm=load(MAIN)
crs=ga['frame']['crs']; tr=Transformer.from_crs('EPSG:4326',crs,always_xy=True)
def surf(g):
    vid=[v[0] for v in g['vertices']]; lat=[v[1] for v in g['vertices']]; lon=[v[2] for v in g['vertices']]; z=np.array([v[3] for v in g['vertices']])
    x,y=tr.transform(lon,lat); x=np.array(x); y=np.array(y)
    owner=collections.defaultdict(set)
    for f in g['faces']:
        for i in f['ring']: owner[i].add(f['ref'])
        for h in f['holes']:
            for i in h: owner[i].add(f['ref'])
    return vid,x,y,z,owner
Sa=surf(ga); Sm=surf(gm)
def datum(S, ring_ll, excl_gap=False):
    vid,x,y,z,owner=S
    rx,ry=tr.transform([q[1] for q in ring_ll],[q[0] for q in ring_ll])
    poly=Polygon(list(zip(rx,ry))).buffer(0.5)
    m=contains_xy(poly,x,y)
    refs=collections.Counter()
    zs=[]
    for i in np.nonzero(m)[0]:
        o=owner.get(vid[i],set())
        for r in o: refs[r.split('#')[0]]+=1
        if excl_gap and o and all(r.startswith('gap') for r in o): continue
        zs.append(z[i])
    return (round(float(statistics.median(zs)),3) if zs else None), len(zs), refs.most_common(6)
for u in ra['units']:
    for m in u['members']:
        if m.get('deck_ring') is None: continue
        um=[mm for uu in rm['units'] if uu['id']==u['id'] for mm in uu['members'] if mm['id']==m['id']]
        mm=um[0] if um else {}
        if mm.get('deck_datum_z')==m.get('deck_datum_z') and mm.get('deck_ends')==m.get('deck_ends'): continue
        print('==',u['id'],m['resource'].split('/')[-1],'plan main',mm.get('deck_datum_z'),'ends' if mm.get('deck_ends') else '', '| plan arm',m.get('deck_datum_z'),'ends' if m.get('deck_ends') else '')
        print('   arm all      :',datum(Sa,m['deck_ring']))
        print('   arm no-gap   :',datum(Sa,m['deck_ring'],True))
        print('   main all     :',datum(Sm,mm['deck_ring'] if mm else m['deck_ring']))
