"""pads64 scratch: the rows two --solved-out pickles' stage-1 sets do NOT share (by type, head, vertex keys, bounds).
usage: csdiff.py A.solved.pkl B.solved.pkl [cs_s1|cs]"""
import pickle, sys, collections
sys.path.insert(0, "src")
from auto_patch_v2.model.constraints import Diff, Linear, Band, Pin, Flat, Offset
which = sys.argv[3] if len(sys.argv) > 3 else "cs_s1"
def sig(p):
    sv = pickle.load(open(p, "rb")); cs = sv[which]; pm = sv["pm_s1" if which == "cs_s1" else "pm"]
    k = lambda v: tuple(round(float(x), 9) for x in pm.vertices[int(v)].key)
    h = lambda r: r.source.ruling.split(" (")[0].strip()
    out = collections.Counter()
    for r in cs.rows():
        if isinstance(r, Diff): s = ("Diff", h(r), k(r.a), k(r.b), round(r.cap, 9), round(r.d, 4), r.soft)
        elif isinstance(r, Linear): s = ("Linear", h(r), tuple((k(v), round(float(c), 6)) for v, c in r.terms), None if r.lo is None else round(r.lo, 6), None if r.hi is None else round(r.hi, 6))
        elif isinstance(r, Band): s = ("Band", h(r), k(r.v), None if r.lo is None else round(r.lo, 4), None if r.hi is None else round(r.hi, 4))
        elif isinstance(r, Pin): s = ("Pin", h(r), k(r.v), round(r.z, 4))
        elif isinstance(r, Flat): s = ("Flat", h(r), tuple(sorted(k(v) for v in r.group)))
        else: s = (type(r).__name__, h(r), str(r)[:80])
        out[s] += 1
    return out
A, B = sig(sys.argv[1]), sig(sys.argv[2])
print("rows", sum(A.values()), sum(B.values()))
for name, X, Y in (("A only", A, B), ("B only", B, A)):
    d = X - Y; byh = collections.Counter()
    for s, n in d.items(): byh[(s[0], s[1])] += n
    print(name, sum(d.values())); [print("    ", n, t, hd[:90]) for (t, hd), n in byh.most_common(12)]
    for s in list(d)[:4]: print("      e.g.", str(s)[:300])
