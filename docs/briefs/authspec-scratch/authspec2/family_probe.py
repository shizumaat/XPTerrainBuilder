"""authspec2 probe 1 — THE ANCHOR FAMILY RULE on the real pack (object-placement
spec §18 (5), STOP 1 of lane walls3).

Reads every placement of the OTHH capture through the branch's own intake
(`basin_witness.read_objects`, exactly what the build runs), groups the
LIFTED placements (OBJECT_AGL > 0) into anchor families — same anchor
within `quantum` (the engine's own coordinate quantum), same heading, same
lift — and evaluates, per family, the lift against the family's DEEPEST
genuine solid.  Prints: every family with at least one member deep enough
to found a pit, which members read ground-seated under today's PER-PLACEMENT
rule, which under the FAMILY rule, and the count of placements the family
rule newly captures outside the pit resources.

    cd Ortho4XP && venv/bin/python ../docs/briefs/authspec-scratch/authspec2/family_probe.py CAPTURE.pkl
"""
import math
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "tools")
sys.path.insert(0, "src")

t0 = time.time()
cap = pickle.load(open(sys.argv[1], "rb"))
ap = cap["airport"] if isinstance(cap, dict) else cap[0]
from auto_patch_v2.law import Law                              # noqa: E402
from auto_patch_v2.airport import obj8, frame_entry as fe, basin_witness as bw  # noqa: E402
from auto_patch_v2.airport.authored_seat import lifted_by_own_depth  # noqa: E402

law = Law.for_airport(ap.icao)
bl = law.tables.structures.basin
TOL, ADM = float(bl.authored_rim_tol_m), float(bl.admission_depth_m)
q = fe.quantum(law)
cache = obj8.ResourceCache(bl.min_solid_thickness_m, q)
objs, rep = bw.read_objects(ap, law, cache)
to_ll = ap.frame.transformers()[1]
print(f"read {len(objs)} placements in {time.time() - t0:.0f} s; quantum {q}; tol {TOL}; admission {ADM}")


def deepest_genuine(o):
    if not o.resolved:
        return math.inf
    return min((c.min_y for c in cache.genuine(o.resolved)), default=math.inf)


fam = defaultdict(list)
for o in objs:
    if o.agl_m <= 0.0 or not o.resolved:
        continue
    key = (round(o.xy[0] / max(q, 0.01)), round(o.xy[1] / max(q, 0.01)),
           round(o.heading_deg, 3), round(o.agl_m, 3))
    fam[key].append(o)

newly, per_placement_seated, family_seated = [], [], []
for key, members in sorted(fam.items(), key=lambda kv: -len(kv[1])):
    deeps = {o.id: deepest_genuine(o) for o in members}
    fam_deep = min(deeps.values())
    own = {o.id: lifted_by_own_depth(o.agl_m, deeps[o.id], TOL, ADM) for o in members}
    fam_rule = lifted_by_own_depth(members[0].agl_m, fam_deep, TOL, ADM)
    per_placement_seated += [o.id for o in members if own[o.id]]
    if fam_rule:
        family_seated += [o.id for o in members]
    if not (fam_rule or any(own.values()) or fam_deep <= -ADM):
        continue
    lat, lon = to_ll(*members[0].xy)
    print(f"\nFAMILY {lat:.7f},{lon:.7f} hdg {key[2]} lift {key[3]:+.4f}  "
          f"members {len(members)}  deepest {fam_deep:.3f}  lift-depth {members[0].agl_m + fam_deep:+.3f}  "
          f"FAMILY RULE: {'ground-seated' if fam_rule else 'lifted'}")
    for o in members:
        d = deeps[o.id]
        print(f"   {o.id:14s} {o.path.split('/')[-1]:44s} deepest {d:8.3f}  lift-depth {o.agl_m + d:+.3f}  "
              f"own-rule {'seated' if own[o.id] else 'lifted':7s} build-flag {o.ground_seated}  "
              f"wit {len(o.witnesses)} buried {len(o.buried)}")
        if fam_rule and not own[o.id]:
            newly.append((o.id, o.path.split("/")[-1]))

print(f"\nlifted families {len(fam)} / placements {sum(len(v) for v in fam.values())}")
print(f"ground-seated per-placement (today): {len(per_placement_seated)}")
print(f"ground-seated under the FAMILY rule: {len(family_seated)}")
print(f"NEWLY captured by the family rule ({len(newly)}):")
for oid, nm in newly:
    print("   ", oid, nm)
