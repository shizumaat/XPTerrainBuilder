"""holering scratch: join a pass-1a arm (stage-1 map) to a full replay's FINAL z by vertex key, runway class.
usage: rwjoin.py PROB.pkl ARM.npz SOLVED.pkl"""
import pickle, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import p1a

prob = p1a.load(sys.argv[1]); pm = prob['stage1'].pm; law = prob['law']
a = np.load(sys.argv[2]); za = a['za']
with open(sys.argv[3], 'rb') as fh:
    full = pickle.load(fh)
pmf, zf = full['pm'], np.asarray(full['z'], float)
at = {tuple(pmf.vertices[i].key): i for i in range(len(pmf.vertices))}
cls = p1a.classes(pm, law)
for k in ('runway', 'rim', 'pad_only', 'other'):
    d = []
    for v in sorted(cls[k] & set(a['levelled'].tolist())):
        j = at.get(tuple(pm.vertices[v].key))
        if j is not None:
            d.append(abs(za[v] - zf[j]))
    d = np.asarray(d)
    print(f'{k}: {d.size} joined; |1a - final| > 0.02 {int((d > 0.02).sum())} > 0.1 {int((d > 0.1).sum())} worst {d.max():.3f}')
