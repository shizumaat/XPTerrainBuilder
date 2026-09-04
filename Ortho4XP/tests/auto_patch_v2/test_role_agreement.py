"""M1 role-agreement twin against v1's roles (M0 §4 acceptance; plan §3
M1 bar: roles match v1's on >= 95 % of pavement AREA, differences
listed).

v1's roles are the ``role`` tags of the 09-02 CYXY arm's patch in the
artifact ledger (Appendix B; tag ``CYXY_20260901T235159``); v2's are the
classifier's cells on the same inputs (the ``CYXY Whitehorse`` custom
pack the arm was built from).  Agreement is measured by intersecting
every v2 pavement cell with the v1 rings and summing the area where the
role (or the law family) is the same.

The twin records the MEASURED agreement as a regression floor and
requires every disagreeing role pair to carry a reason (``REASONS``) —
a new class of disagreement fails until it is explained.  The M1 bar
itself (95 %) is NOT met at M1 (see ``docs/specs/auto-patch-v2/
m1-report.md``): the floor here is the measured value, not the bar.
Skipped when the shared corpus or the ledger blob is absent.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from auto_patch_v2.airport.load import Inputs, load
from auto_patch_v2.classify import classify
from auto_patch_v2.law import Law

LEDGER = Path(os.path.expanduser("~/.ortho4xp/artifact_ledger"))
TAG = "CYXY_20260901T235159"
DATA = Path("/Users/noah/XPTerrainBuilderData")
XPLANE = Path("/Users/noah/X-Plane 12")

VALUE_ROLES = frozenset(("runway", "runway_crossing", "primary_parallel",
                         "secondary_parallel", "stub", "cross_connector",
                         "junction", "apron", "service_road",
                         "service_junction", "groundside_pavement",
                         "parking_lot"))
TAXI = frozenset(("primary_parallel", "secondary_parallel", "stub",
                  "cross_connector", "junction"))

#: Every (v2 role, v1 role) pair that disagrees needs a reason here.
REASONS: dict[tuple[str, str], str] = {
    # owner 2026-09-04j (lane v2class): lots and road strips are classes of their own
    ("parking_lot", "groundside_pavement"): "owner 2026-09-04j: a landside source polygon carrying an OSM road (not a strip) is a PARKING LOT (5 %); v1 has no such role",
    ("parking_lot", "service_junction"): "owner 2026-09-04j: v1's road-feed junction territory inside a lot page is the lot (the road inside the lot IS the lot, cut at the mouth)",
    ("parking_lot", "service_road"): "owner 2026-09-04j: v1's road-feed corridor inside a lot page is the lot",
    ("parking_lot", "apron"): "owner 2026-09-04j item 3: a lot page (OSM road, no taxi centreline, no startup, not apron-named) that v1 dissolved into the apron blob (CYXY dsf:pol130)",
    ("parking_lot", "junction"): "as parking_lot vs apron (v1 route-proximity junction band over a lot page)",
    ("parking_lot", "building"): "v1 pad footprint inside a lot v2 keeps as pavement (pad folded)",
    ("service_road", "apron"): "owner 2026-09-04j item 3: a road STRIP (pav29/pav30, the 1206 ring road drawn as its own 110 polygon) is cut from the apron at its own boundary",
    ("service_road", "junction"): "as service_road vs apron (v1's route-proximity band over a road strip)",
    ("service_road", "groundside_pavement"): "as service_road vs apron: a landside strip page carrying the road (v1 groundside_pavement)",
    ("service_road", "service_junction"): "a strip page carrying the route: one road face where v1 read a service junction",
    ("service_road", "building"): "as service_road vs apron",
    ("groundside_pavement", "service_junction"): "as groundside_pavement vs apron",
    ("cross_connector", "groundside_pavement"): "owner 2026-09-04j item 4: a NETWORK taxiway runs onto the page (CYXY dsf:pol19): airside without a pavement touch-chain; v1 demoted it",
    ("junction", "groundside_pavement"): "runway touch-chain difference (item 4: network taxiway seeds the chain)",
    ("apron", "groundside_pavement"): "runway touch-chain: v1's road carve severed these lots; v2 keeps roads inside wide pavement uncut (free-road ruling) so the chain reaches the runway; item 4 network seeding",
    ("primary_parallel", "junction"): "v1 emits every slice face as junction; v2 names corridors by sub-role (same taxi-family caps; plane_gradient family differs)",
    ("secondary_parallel", "junction"): "same as primary_parallel vs junction",
    ("stub", "junction"): "same as primary_parallel vs junction",
    ("cross_connector", "junction"): "same as primary_parallel vs junction",
    ("stub", "apron"): "Apron 1 lanes: v2 cuts the apron by every through lane (corridor width test); v1's junction_repair re-roles interior faces back to apron",
    ("primary_parallel", "apron"): "as stub vs apron (Apron 1 lanes)",
    ("cross_connector", "apron"): "as stub vs apron (Apron 1 lanes)",
    ("secondary_parallel", "apron"): "as stub vs apron (Apron 1 lanes)",
    ("junction", "apron"): "route-proximity band (user 2026-07-06) vs v1's junction_repair apron re-role",
    ("apron", "junction"): "pavement with no route (pav28 remainder, pav29): v1 junction via gap-spine synthesis; v2 apron per the proximity ruling",
    ("service_junction", "groundside_pavement"): "DSF page dsf:pol117 touched only by a FREE ground-route part; v1 severed it from the runway chain (road carve) and demoted it",
    ("service_junction", "apron"): "free ground-route parts cutting pavement v1 left uncut (free-road width test differs at the station)",
    ("service_junction", "service_road"): "v1 road corridors inside pavement vs v2 service_junction cells",
    ("apron", "groundside_pavement"): "runway touch-chain: v1's road carve severed these lots; v2 keeps roads inside wide pavement uncut (free-road ruling) so the chain reaches the runway",
    ("groundside_pavement", "apron"): "runway touch-chain: v2 severs at DSF page boundaries / pads where v1 chained through",
    ("groundside_pavement", "junction"): "as groundside_pavement vs apron",
    ("groundside_pavement", "service_junction"): "as groundside_pavement vs apron",
    ("groundside_pavement", "service_road"): "as groundside_pavement vs apron",
    ("groundside_pavement", "building"): "v1 pad footprint inside a lot v2 keeps as pavement (pad folded: < 250 m2 or outside boundary gate)",
    ("apron", "service_road"): "v1 OSM road-feed corridors inside apron; v2 M1 carries 1206 routes only (M3 roads)",
    ("apron", "service_junction"): "v1 road-feed service junctions; v2 M1 carries 1206 routes only",
    ("apron", "building"): "v1 pad v2 folded (tiny or outside the boundary gate)",
    ("junction", "building"): "v1 pad v2 folded",
    ("cross_connector", "building"): "v1 pad v2 folded",
    ("runway", "runway_crossing"): "v1 crossing rings extend beyond the slab overlap (junction-snap stations)",
    ("junction", "groundside_pavement"): "runway touch-chain difference",
    ("junction", "service_junction"): "v1 road-feed service junctions",
    ("apron", "apron"): "", ("junction", "junction"): "", ("runway", "runway"): "",
    ("runway_crossing", "runway_crossing"): "",
    ("groundside_pavement", "groundside_pavement"): "",
    ("service_junction", "service_junction"): "",
    ("service_road", "service_road"): "",
    ("service_road", "apron"): "v2 1206 corridor outside apt.dat pavement over v1 apron (DSF page)",
    ("service_road", "junction"): "as service_road vs apron",
    ("service_road", "groundside_pavement"): "as service_road vs apron",
    ("service_road", "service_junction"): "as service_road vs apron",
    ("service_road", "building"): "as service_road vs apron",
    ("stub", "building"): "v1 pad v2 folded",
    ("primary_parallel", "building"): "v1 pad v2 folded",
}

#: Measured 2026-09-03 (this branch): the regression floors.
FLOOR_EXACT = 0.40
FLOOR_FAMILY = 0.65


def _blob() -> Path | None:
    entries = LEDGER / "entries"
    if not entries.is_dir():
        return None
    for p in entries.glob("*.json"):
        try:
            d = json.loads(p.read_text())
        except ValueError:
            continue
        if d.get("tag") == TAG:
            sha = d["files"]["patch"]["sha256"]
            b = LEDGER / "blobs" / sha
            return b if b.is_file() else None
    return None


def _family(role: str) -> str:
    return "taxi" if role in TAXI else role


@pytest.mark.skipif(not DATA.is_dir() or not XPLANE.is_dir() or _blob() is None,
                    reason="shared corpus / ledger blob not on this machine")
def test_role_agreement_with_v1_cyxy():
    blob = _blob()
    inputs = Inputs(xplane_root=str(XPLANE), cifp_dir=str(XPLANE / "Custom Data" / "CIFP"),
                    osm_root=str(DATA / "OSM_data"), elevation_root="",
                    mod_cache_root=str(DATA / "Airport_mod_cache"))
    law = Law.for_airport("CYXY")
    a = load("CYXY", inputs, law)
    assert a.pack.name == "CYXY Whitehorse"          # the pack the v1 arm was built from
    cl = classify(a, law)

    from pyproj import Transformer
    fwd = Transformer.from_crs("EPSG:4326", a.frame.crs, always_xy=True)
    root = ET.parse(blob).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon")))
             for n in root.findall("node")}
    v1: list[tuple[str, Polygon]] = []
    for w in root.findall("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        nds = [nd.get("ref") for nd in w.findall("nd")]
        role = tags.get("role")
        if role not in VALUE_ROLES | {"building"} or nds[0] != nds[-1]:
            continue
        p = Polygon([fwd.transform(nodes[i][1], nodes[i][0]) for i in nds])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            v1.append((role, p))
    tree = STRtree([p for _r, p in v1])

    total = agree = fam = covered = 0.0
    pairs: dict[tuple[str, str], float] = {}
    for c in cl.cells:
        if c.role not in VALUE_ROLES:
            continue
        p = Polygon(c.ring, c.holes)
        total += p.area
        for j in tree.query(p, predicate="intersects"):
            r1, q = v1[int(j)]
            ia = p.intersection(q).area
            if ia <= 0:
                continue
            covered += ia
            pairs[(c.role, r1)] = pairs.get((c.role, r1), 0.0) + ia
            if r1 == c.role:
                agree += ia
            if _family(r1) == _family(c.role):
                fam += ia
    exact, family = agree / total, fam / total
    print(f"\nCYXY role agreement: exact {exact:.1%}  family {family:.1%}  "
          f"v1-covered {covered / total:.1%}  (pavement cells {total:,.0f} m2)")
    for (r2, r1), area in sorted(pairs.items(), key=lambda x: -x[1]):
        print(f"  v2 {r2:20s} v1 {r1:20s} {area:9,.0f}  {REASONS.get((r2, r1), '?')}")
    assert covered / total >= 0.95                    # same pavement population
    unexplained = [k for k, v in pairs.items() if v > 200.0 and k not in REASONS]
    assert not unexplained, unexplained
    assert exact >= FLOOR_EXACT and family >= FLOOR_FAMILY, (exact, family)
