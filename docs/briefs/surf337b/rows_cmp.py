"""rows >= 0.5 m by family|roles, N arms side by side.  usage: rows_cmp.py name=rows.json ..."""
import json, sys, collections
arms = [a.split("=", 1) for a in sys.argv[1:]]
C = {}
for n, p in arms:
    rows = json.load(open(p))["rows"]
    big = [r for r in rows if (r["magnitude_m"] or 0) >= 0.5]
    C[n] = (len(rows), len(big), collections.Counter(r["family"] for r in big),
            collections.Counter((r["family"], r["roles"]) for r in big))
print("arm", *[n for n, _ in arms]); print("rows", *[C[n][0] for n, _ in arms]); print("rows>=0.5", *[C[n][1] for n, _ in arms])
for fam in sorted(set().union(*[C[n][2] for n, _ in arms])):
    print(f"  {fam:32s}", *[C[n][2][fam] for n, _ in arms])
print("family|roles where the arms differ:")
for k in sorted(set().union(*[C[n][3] for n, _ in arms])):
    v = [C[n][3][k] for n, _ in arms]
    if len(set(v)) > 1: print(f"  {k[0]:24s} {k[1]:44s}", *v)
