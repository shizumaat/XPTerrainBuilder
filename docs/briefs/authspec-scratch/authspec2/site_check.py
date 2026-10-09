"""authspec2 probe 3 — the three #451 owner sites against the basins the
family-rule arm produced (`family_arm.py`'s pickle; the arm's own site line
read `to_xy(lat, lon)` — the frame's transformer takes (lon, lat), which is
why it printed "no basin within 60 m"; this is the corrected read).

    cd Ortho4XP && venv/bin/python ../docs/briefs/authspec-scratch/authspec2/site_check.py BASINS.pkl
"""
import pickle
import sys

sys.path.insert(0, "src")
from shapely.geometry import Point, Polygon  # noqa: E402

cap = pickle.load(open("/Users/noah/XPTerrainBuilderData/.harness/frames/perfB362/OTHH.pkl", "rb"))
to_xy, _to_ll = cap["airport"].frame.transformers()
SITES = [("#451 a", 25.2536839, 51.6231506), ("#451 b", 25.2539056, 51.6221564),
         ("#451 c", 25.2963819, 51.6065055)]
for bid, kind, fref, ring, region, anchor_ll, objs in pickle.load(open(sys.argv[1], "rb")):
    if not any("Drain" in o or "Dewater" in o for o in objs):
        continue
    reg = Polygon(region if len(region) >= 3 else ring).buffer(0)
    print(f"{bid} {kind} {fref} area {reg.area:.0f} m2 anchor inside {reg.contains(Point(to_xy(anchor_ll[1], anchor_ll[0])))}")
    for name, lat, lon in SITES:
        d = reg.distance(Point(to_xy(lon, lat)))
        if d < 60:
            print(f"    SITE {name} {lat},{lon}: {'INSIDE' if d == 0 else f'{d:.1f} m away'}")
