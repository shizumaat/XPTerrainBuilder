"""pass2 scratch: WHERE two stage-1 answers differ. usage: where.py PROB.pkl A.npz:key B.npz:key [top]"""
import pickle
import sys
from pathlib import Path

import numpy as np

if __name__ == '__main__':
    ROOT = Path.cwd()
    sys.path.insert(0, str(ROOT / 'src'))
    sys.path.insert(0, str(ROOT / 'tools'))
    import replay_null as N
    prob = pickle.load(open(sys.argv[1], 'rb'))
    pm = prob['stage1'].pm
    fa, ka = sys.argv[2].split(':')
    fb, kb = sys.argv[3].split(':')
    a, b = np.load(fa), np.load(fb)
    lv = a['levelled']
    print(N.movers(a[ka], b[kb], lv))
    d = np.abs(a[ka][lv] - b[kb][lv])
    for t in (0.02, 0.05, 0.1, 0.3):
        print(f'  > {t}: {int((d > t).sum())}')
    from collections import Counter
    c = Counter()
    for i in np.flatnonzero(d > 0.02):
        v = int(lv[i])
        roles = tuple(sorted({pm.faces[f].role for f in pm.vertices[v].incident_faces}))
        c[roles] += 1
    print('  by roles:', c.most_common(10))
    for w in N.worst_sites(pm, a[ka], b[kb], lv, top=int(sys.argv[4]) if len(sys.argv) > 4 else 8):
        print('  ', w)
