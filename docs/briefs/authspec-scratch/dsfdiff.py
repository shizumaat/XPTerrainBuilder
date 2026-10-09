import sys, collections
sys.path.insert(0, sys.argv[0].rsplit('/',1)[0])
from dsfobjs import objs
A,B=sys.argv[1],sys.argv[2]
def key(o): return (o[1], round(o[2],5), round(o[3],5))
a={}; b={}
for o in objs(A, lambda n: True): a.setdefault(key(o),[]).append(o)
for o in objs(B, lambda n: True): b.setdefault(key(o),[]).append(o)
na=sum(len(v) for v in a.values()); nb=sum(len(v) for v in b.values())
print("objects A",na,"B",nb,"keys A",len(a),"B",len(b))
only_a=[k for k in a if k not in b]; only_b=[k for k in b if k not in a]
print("placements only in A",sum(len(a[k]) for k in only_a),"only in B",sum(len(b[k]) for k in only_b))
ca=collections.Counter(k[0].rsplit('_',1)[0][:40] for k in only_a); cb=collections.Counter(k[0].rsplit('_',1)[0][:40] for k in only_b)
print(" only-A top:",ca.most_common(12)); print(" only-B top:",cb.most_common(12))
changed=collections.defaultdict(list)
for k in a:
    if k in b:
        oa=a[k][0]; ob=b[k][0]
        if oa[0]!=ob[0] or (oa[4] or 0)!=(ob[4] or 0):
            changed[k[0]].append((oa[0],oa[4],ob[0],ob[4]))
print("resources with elevation/kind change:",len(changed),"placements:",sum(len(v) for v in changed.values()))
for r,v in sorted(changed.items()):
    deltas=set((x[0],x[1],x[2],x[3]) for x in v)
    print("  %-45s n=%d %s"%(r,len(v),sorted(deltas)[:3]))
