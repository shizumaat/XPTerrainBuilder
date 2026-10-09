"""which nodes of ways with a given role moved between two patches (canonical 11-dp join)."""
import sys, collections
from pathlib import Path
sys.path[:0] = ["tools", "src", "."]
import check_grade as cg
a, b, role = sys.argv[1], sys.argv[2], sys.argv[3]
tol = float(sys.argv[4]) if len(sys.argv) > 4 else 0.005
def read(p):
    nodes, ways = cg._parse_osm(Path(p))
    out = {}
    for w in ways:
        if w.role != role: continue
        for n, e in zip(w.nids, w.elevs):
            if e is not None:
                out[(nodes[n], w.ref)] = e
    return out
A = read(a); B = read(b)
mv = [(B[k] - A[k], k) for k in A if k in B and abs(B[k] - A[k]) > tol]
print(len(A), len(B), "moved", len(mv))
for d, (ll, ref) in sorted(mv, key=lambda t: (t[1][1], t[1][0])):
    print(f"{ref:10s} {ll[0]:.11f},{ll[1]:.11f} dz {d:+.4f}  {A[(ll,ref)]:.3f}->{B[(ll,ref)]:.3f}")
