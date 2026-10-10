"""pads67: one cell's own grades in two graded.json (base, arm) and how far the arm moved it. usage: cellgrade.py BASE ARM REF [REF...]"""
import json, sys, math
A, B = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
def idx(g): return {v[0]: v for v in g['vertices']}, {(f"{v[1]:.11f}", f"{v[2]:.11f}"): v[3] for v in g['vertices']}
VA, KA = idx(A); VB, KB = idx(B)
def m(a, b): return math.hypot((a[1]-b[1])*110574, (a[2]-b[2])*111320*math.cos(math.radians(a[1])))
for ref in sys.argv[3:]:
    for name, g, V in (('base', A, VA), ('arm', B, VB)):
        gr = []; n = 0
        for f in g['faces']:
            if str(f['ref']).split('#')[0] != ref: continue
            n += 1; r = f['ring']
            for a, b in zip(r, r[1:] + r[:1]):
                d = m(V[a], V[b])
                if d > 1.0: gr.append((abs(V[a][3]-V[b][3])/d, d, V[a][1], V[a][2]))
        gr.sort()
        if gr: print(f"{ref:16s} {name:5s} faces {n} ring edges {len(gr)}: max grade {100*gr[-1][0]:.1f} % over {gr[-1][1]:.1f} m at {gr[-1][2]:.11f}, {gr[-1][3]:.11f}; p90 {100*gr[int(.9*len(gr))][0]:.1f} %; edges > 5 % {sum(1 for x in gr if x[0] > .05)}, > 10 % {sum(1 for x in gr if x[0] > .10)}")
    dz = []
    for f in B['faces']:
        if str(f['ref']).split('#')[0] != ref: continue
        for i in f['ring']:
            k = (f"{VB[i][1]:.11f}", f"{VB[i][2]:.11f}")
            if k in KA: dz.append(VB[i][3] - KA[k])
    if dz: print(f"{ref:16s} arm - base over {len(dz)} vertices: min {min(dz):+.2f} max {max(dz):+.2f}; moved > 0.3 m {sum(1 for d in dz if abs(d) > .3)}, > 1 m {sum(1 for d in dz if abs(d) > 1)}")
