import sys, pickle, collections, json
sys.path[:0] = ["src", ".", "tools"]
out={}
for name in sys.argv[2:]:
    sv=pickle.load(open(f"{sys.argv[1]}/{name}/solved.pkl","rb"))
    hc=list(sv.get("hard_conflict") or ())
    pm=sv["pm"]
    recs=[]
    for r in hc:
        d=dict(r) if isinstance(r,dict) else r.__dict__
        recs.append(d)
    out[name]=recs
    print(name,"hard_conflict",len(recs), "keys", sorted(recs[0].keys()) if recs else None)
    if recs: print("  sample", {k:(str(v)[:120]) for k,v in recs[0].items()})
    del sv
pickle.dump(out, open(f"{sys.argv[1]}/hc.pkl","wb"))
