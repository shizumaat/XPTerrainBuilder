import os, sys, pickle, collections
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); pm = cap["pm"]
rp = pickle.load(open(f"{SP}/HECA_t3_replay.pkl", "rb")); lab = rp["label"]; edges = rp["edges"]; z = rp["z"]
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_family
law = Law.for_airport("HECA")
def face_report(fid):
    f = pm.faces[fid]; vs = [v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)]
    ls = collections.Counter(lab.get(v, -1) for v in vs)
    je = [e for e in edges if e[0] in set(vs) and e[1] in set(vs)]
    print(f"face #{fid} {f.role} {f.ref}: verts {len(vs)} labels {dict(ls.most_common(6))}{' ...' if len(ls)>6 else ''} unlabelled {ls.get(-1,0)} joint edges on it {len(je)} max step {max((abs(z[a]-z[b]) for a,b,*_ in je), default=0):.2f}")
for fid in (364, 365, 393, 396, 381, 403):
    if fid in pm.faces: face_report(fid)
# roads: every road-family face touching a labelled complex — label coverage and steps
roads = [fid for fid, f in pm.faces.items() if role_family(law, f.role) == "road"]
cov = collections.Counter()
for fid in roads:
    f = pm.faces[fid]; vs = [v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)]
    n_l = sum(1 for v in vs if lab.get(v, -1) != -1)
    cov["all labelled" if n_l == len(vs) else ("none" if n_l == 0 else "PARTIAL")] += 1
    if 0 < n_l < len(vs):
        print(f"  road face #{fid} {f.role} {f.ref}: {n_l}/{len(vs)} labelled")
print("road faces", len(roads), dict(cov))
# junction faces partial?
jn = [fid for fid, f in pm.faces.items() if f.role == "junction"]
part = []
for fid in jn:
    f = pm.faces[fid]; vs = [v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)]
    n_l = sum(1 for v in vs if lab.get(v, -1) != -1)
    if 0 < n_l < len(vs): part.append((fid, n_l, len(vs)))
print("junction faces", len(jn), "partially labelled", len(part), part[:12])
