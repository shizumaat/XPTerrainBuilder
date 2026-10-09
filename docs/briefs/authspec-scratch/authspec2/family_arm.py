"""authspec2 probe 2 — THE INTERVENTION: the planar stage replayed off the OTHH
capture with the ANCHOR-FAMILY lift rule in place of the per-placement one
(object-placement spec §18 (5), STOP 1 of lane walls3).  Control = lane walls3's
own planar dump (`<scratchpad>/walls3/pd3.log`: basins 41, Drainage_01 /
Dewatering_01 cut, Drainage_02..05 refused as basements).

Pass 1 reads the placements once and groups the LIFTED ones into anchor
families (same anchor, heading and lift); a family whose deepest genuine
solid is lifted by its own depth (within `[basin] authored_rim_tol_m`, at
least `admission_depth_m` deep) reads ground-seated AS A WHOLE.  Pass 2
replays the planar stage with `obj8._reads_ground_seated` answering for the
family (the pool pinned to budget 1 so the patch is the reader), then prints
every basin, every refusal naming a pit resource, the seat records and
whether each owner site of #451 lies in a basin region.

    cd Ortho4XP && venv/bin/python ../docs/briefs/authspec-scratch/authspec2/family_arm.py CAPTURE.pkl
"""
import math
import os
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "tools")
sys.path.insert(0, "src")

SITES = [("#451 a", 25.2536839, 51.6231506), ("#451 b", 25.2539056, 51.6221564),
         ("#451 c", 25.2963819, 51.6065055)]

import v2_solve_replay as R                                       # noqa: E402
from auto_patch_v2.law import Law                                 # noqa: E402
from auto_patch_v2.airport import obj8, frame_entry as fe, basin_witness as bw, pool as _pool  # noqa: E402
from auto_patch_v2.airport.authored_seat import lifted_by_own_depth  # noqa: E402

_pool.configure(1)
PKL = Path(sys.argv[1])
cap = pickle.load(open(PKL, "rb"))
ap = cap["airport"]
law = Law.for_airport(ap.icao)
bl = law.tables.structures.basin
TOL, ADM = float(bl.authored_rim_tol_m), float(bl.admission_depth_m)
q = fe.quantum(law)
cache = obj8.ResourceCache(bl.min_solid_thickness_m, q)

t0 = time.time()
objs, _rep = bw.read_objects(ap, law, cache)
fam = defaultdict(list)
for o in objs:
    if o.agl_m > 0.0 and o.resolved:
        fam[(round(o.xy[0] / q), round(o.xy[1] / q), round(o.heading_deg, 3), round(o.agl_m, 3))].append(o)
SEATED: set[tuple[str, float]] = set()
for members in fam.values():
    deep = min((min((c.min_y for c in cache.genuine(o.resolved)), default=math.inf) for o in members))
    if lifted_by_own_depth(members[0].agl_m, deep, TOL, ADM):
        SEATED.update((o.resolved, round(o.agl_m, 3)) for o in members)
print(f"pass 1: {len(objs)} placements, {len(fam)} lifted families, family-seated resources {len(SEATED)} "
      f"({time.time() - t0:.0f} s)")
for r, a in sorted(SEATED):
    print("   seated:", os.path.basename(r), a)

_orig = obj8._reads_ground_seated


def _family(cache_, phys, agl, tol_m, admission_depth_m):
    if (phys, round(float(agl), 3)) in SEATED:
        return True
    return _orig(cache_, phys, agl, tol_m, admission_depth_m)


obj8._reads_ground_seated = _family
import auto_patch_v2.planar.build; PB = sys.modules["auto_patch_v2.planar.build"]  # noqa: E402,E702
CAP: dict = {}
_bb = PB.build_basins


def _wrap(*a, **k):
    r = _bb(*a, **k)
    CAP["r"] = r
    return r


PB.build_basins = _wrap

t1 = time.time()
res = R.replay_problem(PKL, "planar", [], pad_read_only=True)
for x in CAP.get("r", ()):
    if hasattr(x, "refused"):
        for ln in x.refused:
            if "Drain" in ln or "Dewater" in ln or "basin:" in ln[:12]:
                print("REFUSED", ln[:420])
pm, ap2 = res["pm"], res["airport"]
print(f"pass 2: planar stage {time.time() - t1:.0f} s; structures {len(pm.structures)} basins {len(pm.basins)}")
from auto_patch_v2.pipeline.authored_seats import seat_records  # noqa: E402
from shapely.geometry import Point, Polygon                       # noqa: E402

to_xy, to_ll = ap2.frame.transformers()
by_res = defaultdict(list)
for b in pm.basins:
    stems = sorted({os.path.basename(p).split("_LOD")[0].rsplit("_", 1)[0] for p in b.objects})
    for s in stems:
        by_res[s].append(b.id)
    print(f"BASIN {b.id:9s} {b.kind:12s} floor {b.floor_z:7.2f} plate_y {b.plate_y_m:7.3f} agl {b.agl_m:6.3f} "
          f"inside {b.anchor_inside_floor!s:5s} rim_cut {('%+.3f' % b.rim_cut_m) if b.rim_cut_m is not None else '  n/a'} "
          f"area {b.area_m2:7.0f} witness {b.witness_id:14s} members {len(b.member_ids)} "
          f"at {b.anchor_ll[0]:.6f},{b.anchor_ll[1]:.6f} :: {', '.join(os.path.basename(p) for p in b.objects)}")
print("basins by resource stem:", {k: v for k, v in sorted(by_res.items()) if "Drain" in k or "Dewater" in k})
print("pit resources cut:", sum(1 for k in by_res if "Drain" in k or "Dewater" in k))
pickle.dump([(b.id, b.kind, b.floor_ref, b.ring, b.region, b.anchor_ll, b.objects) for b in pm.basins],
            open(os.environ.get("AUTHSPEC2_OUT", "/tmp/authspec2_basins.pkl"), "wb"))
for name, lat, lon in SITES:
    p = Point(to_xy(lon, lat))        # the frame's to_xy takes (lon, lat)
    hits = []
    for b in pm.basins:
        poly = b.region if len(b.region) >= 3 else b.ring
        reg = Polygon(poly) if len(poly) >= 3 else None
        if reg is not None and not reg.is_valid:
            reg = reg.buffer(0)
        if reg is not None and reg.contains(p):
            hits.append((b.id, 0.0))
        elif reg is not None:
            d = reg.distance(p)
            if d < 60.0:
                hits.append((b.id, round(d, 1)))
    print(f"SITE {name} {lat},{lon}: " + (", ".join(f"{bid} ({'inside' if d == 0 else f'{d} m away'})" for bid, d in hits) or "NO basin within 60 m")
          + f"   [ring/region sizes: {[(b.id, len(b.ring), len(b.region)) for b in pm.basins if b.agl_m > 0][:3]}]")
recs = seat_records(pm, law)
for k, r in sorted(recs.items()):
    if r["datum"] == "rim":
        print("REC", r)
print(f"total {time.time() - t0:.0f} s")
