"""Summarise results.jsonl: per n, per arm: median t_solve, max RSS, max viol, rel-obj gap
vs the best feasible QP objective (viol <= 1e-3) at that n, plus diagnosis columns."""
import json, sys, os
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
recs = [json.loads(l) for l in open(os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "results.jsonl"))]
by = defaultdict(list)
for r in recs:
    by[(r["n"], r["kind"], r["arm"])].append(r)

for n in sorted({r["n"] for r in recs}):
    feas_objs = [r["obj"] for r in recs if r["n"] == n and r["kind"] == "f" and r.get("viol", {}).get("max", 9) <= 1e-3
                 and "lp" not in r["arm"] and "raw" not in r["arm"]]
    ref = min(feas_objs) if feas_objs else float("nan")
    m = next((r["m"] for r in recs if r["n"] == n and "m" in r), "?")
    print(f"\n### n={n}  rows m={m}  ref QP obj (best feasible, viol<=1e-3) = {ref:.4f}")
    print(f"{'arm':22s} | {'kind':4s} | {'t_med s':>9s} | {'t_min..max':>16s} | {'RSS MB':>7s} | {'max viol m':>10s} | {'rel obj gap':>11s} | status / diagnosis")
    print("-" * 130)
    for (nn, kind, arm), rs in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][2])):
        if nn != n:
            continue
        ts = [r["t_solve"] for r in rs if "t_solve" in r]
        tm = np.median(ts) if ts else float("nan")
        rss = max(r.get("rss_peak_mb", float("nan")) for r in rs)
        viol = max((r.get("viol", {}).get("max", float("nan")) for r in rs), default=float("nan"))
        objs = [r["obj"] for r in rs if "obj" in r]
        gap = (np.median(objs) - ref) / abs(ref) if objs and ref == ref else float("nan")
        r0 = rs[0]
        extra = str(r0.get("status"))
        if arm.startswith("osqp"):
            extra += f" it={r0.get('iters')} polish={r0.get('status_polish')}"
        if arm.startswith("admm"):
            extra += f" it={r0.get('iters')} refac={r0.get('refactors')}"
        if kind == "i":
            if "dual_ray_rows" in r0:
                extra += f" | ray nnz={r0['dual_ray_nnz']} {r0['dual_ray_rows'][:3]} t={r0.get('t_dual_ray', 0):.3f}s"
            if "iis_rows" in r0:
                extra += f" | IIS n={r0.get('iis_nrows', len(r0['iis_rows']))} {r0['iis_rows'][:3]} t={r0.get('t_iis', r0.get('t_filter', 0)):.3f}s probes={r0.get('probes', '')}"
            if "cert_rows" in r0:
                extra += f" | cert nnz={r0['cert_nnz']} top={r0['cert_rows'][:3]}"
        gap_s = f"{gap:11.2e}" if gap == gap else f"{'-':>11s}"
        print(f"{arm:22s} | {kind:4s} | {tm:9.3f} | {min(ts) if ts else float('nan'):7.3f}..{max(ts) if ts else float('nan'):7.3f} | {rss:7.0f} | {viol:10.2e} | {gap_s} | {extra}")
