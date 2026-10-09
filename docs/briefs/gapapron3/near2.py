import sys, pickle, collections, math
sys.path[:0] = ["src", ".", "tools"]
A=pickle.load(open(sys.argv[1],"rb")); B=pickle.load(open(sys.argv[2],"rb"))
lat0,lon0=[float(x) for x in sys.argv[3].split(",")]; R=float(sys.argv[4])
pa,za,pb,zb=A["pm"],A["z"],B["pm"],B["z"]
vf=collections.defaultdict(set)
for fid,f in pb.faces.items():
    for ring in (f.ring,*f.holes):
        for v in pb.ring_vertices(ring): vf[v].add((f.role,str(f.ref)))
ka={tuple(v.key):i for i,v in (pa.vertices.items() if isinstance(pa.vertices,dict) else enumerate(pa.vertices))}
by=collections.defaultdict(list)
it = pb.vertices.items() if isinstance(pb.vertices,dict) else enumerate(pb.vertices)
for i,v in it:
    k=tuple(v.key); d=math.hypot((k[0]-lat0)*110900,(k[1]-lon0)*96300)
    if d<R and k in ka:
        try: dz=float(zb[i])-float(za[ka[k]])
        except Exception: continue
        for r in vf[i]: by[r].append((dz,d))
rows=[(max(abs(x) for x,_ in v), sum(x for x,_ in v)/len(v), len(v), min(d for _,d in v), k) for k,v in by.items()]
for mx,mean,n,dmin,k in sorted(rows,reverse=True)[:28]:
    print("%-55s n %4d max|dz| %.4f mean %+.4f nearest %4.0f m"%(str(k),n,mx,mean,dmin))
