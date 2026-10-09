"""lane flatvalley scratch: per-stage diff of two nullarm runs (z by stage call, demote sets, qp exits)."""
import json, sys
from pathlib import Path
import numpy as np
a, b = Path(sys.argv[1]), Path(sys.argv[2])
A = json.load(open(a / "stages.json"))["stages"]; B = json.load(open(b / "stages.json"))["stages"]
print(f"stage calls {len(A)} vs {len(B)}")
for sa, sb in zip(A, B):
    k = sa["k"]
    za, zb = np.load(a / f"z_{k}.npy"), np.load(b / f"z_{sb['k']}.npy")
    da = {json.dumps(i[:2]) for i in sa.get("demote", [])}; db = {json.dumps(i[:2]) for i in sb.get("demote", [])}
    pa = {json.dumps(i[:2]) for i in sa.get("promote", [])}; pb = {json.dumps(i[:2]) for i in sb.get("promote", [])}
    line = (f"call {k}: unk {sa['unknowns']}/{sb['unknowns']} drop {sa['drop']} fixed {sa['fixed']}/{sb['fixed']} "
            f"demote {len(da)}/{len(db)} (only-A {len(da-db)} only-B {len(db-da)}) "
            f"promote {len(pa)}/{len(pb)} (only-A {len(pa-pb)} only-B {len(pb-pa)}) "
            f"qp rounds {[q[1] for q in sa.get('qp',[])]} / {[q[1] for q in sb.get('qp',[])]}")
    if za.size == zb.size:
        d = np.abs(za - zb)
        line += f" | dz>0.02 {int((d>0.02).sum())} >0.3 {int((d>0.3).sum())} max {d.max():.4f} >1e-6 {int((d>1e-6).sum())}"
    else:
        line += f" | n {za.size}/{zb.size}"
    print(line)
    qa, qb = sa.get("qp", []), sb.get("qp", [])
    for i, (x, y) in enumerate(zip(qa, qb)):
        print(f"     qp{i}: {x[0]} F {x[3]:.9g} |g| {x[4]:.3g}  ||  {y[0]} F {y[3]:.9g} |g| {y[4]:.3g}   dF {y[3]-x[3]:+.3e}")
