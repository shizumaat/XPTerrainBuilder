import sys, pickle, collections
sys.path[:0] = ["src", ".", "tools"]
def load(p):
    sv = pickle.load(open(p, "rb"))
    hc = [dict(r) if isinstance(r, dict) else dict(r.__dict__) for r in (sv.get("hard_conflict") or ())]
    to_ll = sv["airport"].frame.transformers()[1]
    return hc, sv["pm"], to_ll
A, pmA, llA = load(sys.argv[1]); B, pmB, llB = load(sys.argv[2])
print("A", len(A), "B", len(B)); print("keys", sorted(A[0].keys())); print("sample", {k: str(v)[:100] for k, v in A[0].items()})
def key(r, pm):
    vs = r.get("vertices") or r.get("verts") or ()
    ks = tuple(sorted(tuple(round(c, 7) for c in v) for v in vs))
    return (r.get("tier"), r.get("stage"), r.get("ruling") or r.get("head"), ks)
ka = collections.Counter(key(r, pmA) for r in A); kb = collections.Counter(key(r, pmB) for r in B)
for nm, only, rs, pm, ll in (("only A", ka - kb, A, pmA, llA), ("only B", kb - ka, B, pmB, llB)):
    print(nm, sum(only.values()))
    for r in rs:
        if key(r, pm) in only:
            print("   ", {k: (str(v)[:140]) for k, v in r.items() if k not in ("vertices",)})
for nm, rs in (("A", A), ("B", B)):
    print(nm, collections.Counter((r.get("tier"), r.get("stage")) for r in rs))
