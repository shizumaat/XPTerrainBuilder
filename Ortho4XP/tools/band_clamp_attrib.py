#!/usr/bin/env python3
"""BAND-CLAMP + ROAD↔AIRSIDE CONTACT attribution for an emitted patch.

Two read-only questions no other indexed tool answers, over ONE patch and
its ``.axes.json`` sidecar:

``--clamps`` (default)
    For every band-clamp record in the sidecar: its role, its side
    (floor/ceiling), its |dz|, and — the attribution — how far the clamped
    node lies from the AIRSIDE PAVEMENT DOMAIN the band of record is
    actually defined over.  The domain role set is IMPORTED from the band
    engine itself (``raster_reach_band.band_domain_roles``), never
    re-typed here: a second hand-written role list is the census-wrapper
    defect the project CLAUDE.md names.  This is how the 2026-08-25 HECA
    roads round attributed 92 road-family clamps to a band that states no
    road law (spec ``docs/specs/road-band-seal-scope-spec.md`` §1).

``--contact-rings``
    RULINGS 2026-08-25b: *a road sharing an EDGE with an apron conforms to
    the strictest grade — it becomes part of the apron*.  Contact is
    CANONICAL IDENTITY, never proximity: ``layout.to_osm`` deduplicates
    emitted nodes by their 11-decimal lat/lon spelling, so two rings share
    an edge exactly when they share an ordered-pair of consecutive node
    IDS (either orientation).  Reports the contact rings, the airside
    partners, and the worst ring-edge step inside each, and — separately,
    NEVER folded in — the NEAR-MISS rings: road rings within
    ``--near-miss-m`` of airside pavement that share no edge.  The ruling's
    boundary is edge-sharing; near-misses are for the owner to rule on.

It measures no law and counts no defects: the census
(``tools/harness/census.py``) is the law instrument.  Read-only — opens
the patch and the sidecar and writes nothing.

    venv/bin/python tools/band_clamp_attrib.py PATCH.osm
    venv/bin/python tools/band_clamp_attrib.py PATCH.osm --contact-rings
    venv/bin/python tools/band_clamp_attrib.py PATCH.osm --site LAT,LON
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent                                   # Ortho4XP/
sys.path[:0] = [str(_TOOLS), str(_ROOT / "src"), str(_ROOT)]

import check_grade as cg                                        # noqa: E402
from shapely.geometry import Point, Polygon                     # noqa: E402
from shapely.ops import unary_union                             # noqa: E402

from auto_patch.config import (                                 # noqa: E402
    APRON_MAX_GRADE, RASTER_REACH_BAND_OFFNET_RADIUS_M,
    SERVICE_ROAD_MAX_GRADE, TAXI_MAX_GRADE)
from auto_patch.elevation_per_surface.building_feasibility import (  # noqa: E402
    _VIS_BUFFER_M)
# THE DOMAIN, imported from the band engine itself — one source.
from auto_patch.elevation_per_surface.raster_reach_band import (  # noqa: E402
    band_domain_roles)

DOMAIN_ROLES = band_domain_roles()
ROAD_ROLES = cg._ROAD_FAMILY_ROLES


# ──────────────────────────────────────────────────────────────────
# Shared reading
# ──────────────────────────────────────────────────────────────────
class _Patch:
    """The patch, read once through the harness library's own reader."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.side = json.loads(
            Path(str(self.path) + ".axes.json").read_text())
        self.nodes, self.ways = cg._parse_osm(self.path)
        self.anchor = self.side.get("anchor")
        self.to_m = cg._ll_to_m_factory(self.nodes, self.anchor)
        self.rings = []          # (way, open nids, pts, elevs, polygon)
        for w in self.ways:
            nids = (w.nids[:-1]
                    if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
                    else w.nids)
            pts = [self.to_m(*self.nodes[n]) for n in nids
                   if n in self.nodes]
            if len(pts) < 3 or len(pts) != len(nids):
                continue
            try:
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
            except Exception:
                continue
            if poly.is_empty:
                continue
            self.rings.append((w, nids, pts, list(w.elevs[:len(nids)]), poly))

    def domain(self):
        polys = [r[4] for r in self.rings if r[0].role in DOMAIN_ROLES]
        if not polys:
            return None
        return unary_union(polys).buffer(_VIS_BUFFER_M)


def _edge_keys(nids):
    """The ring's undirected consecutive-node-id pairs — canonical identity.

    Emitted node ids ARE the canonical 11-dp point keys (``to_osm``
    deduplicates by them), so a shared key is a shared VERTEX and a shared
    pair is a shared EDGE.  No proximity anywhere in this function.
    """
    n = len(nids)
    return {frozenset((nids[k], nids[(k + 1) % n])) for k in range(n)
            if nids[k] != nids[(k + 1) % n]}


# ──────────────────────────────────────────────────────────────────
# Mode 1 — the clamp records
# ──────────────────────────────────────────────────────────────────
def report_clamps(p: _Patch, site=None):
    domain = p.domain()
    print(f"patch          : {p.path}")
    print(f"anchor         : {p.anchor}")
    n_dom = sum(1 for r in p.rings if r[0].role in DOMAIN_ROLES)
    print(f"airside domain : {n_dom} shapes, area "
          f"{(domain.area if domain else 0.0):,.0f} m2 "
          f"(roles {sorted(DOMAIN_ROLES)})")
    print(f"off-net radius : {RASTER_REACH_BAND_OFFNET_RADIUS_M} m  "
          f"off-mask leg cap {APRON_MAX_GRADE:.3f}  road cap "
          f"{SERVICE_ROAD_MAX_GRADE:.3f}  taxi cap {TAXI_MAX_GRADE:.3f}")

    recs = p.side.get("band_clamp_nodes") or []
    print(f"\nband_clamp_nodes: {len(recs)} record(s)")
    rows, by_role, by_side = [], {}, {}
    for r in recs:
        lat, lon, dz, s, role = r[0], r[1], float(r[2]), r[3], r[4]
        x, y = p.to_m(lat, lon)
        d = Point(x, y).distance(domain) if domain is not None else float("nan")
        rows.append((role, s, dz, d, lat, lon, x, y))
        by_role[role] = by_role.get(role, 0) + 1
        by_side[s] = by_side.get(s, 0) + 1
    print("  by role :", dict(sorted(by_role.items(), key=lambda kv: -kv[1])))
    print("  by side :", by_side)

    road = [r for r in rows if r[0] in ROAD_ROLES]
    print(f"\nROAD-FAMILY clamp records: {len(road)} of {len(rows)}")
    if road:
        ds = sorted(r[3] for r in road)
        n = len(ds)
        print(f"  distance to AIRSIDE domain (m): min {ds[0]:.2f} "
              f"p50 {ds[n // 2]:.2f} p95 {ds[int(0.95 * n)]:.2f} "
              f"max {ds[-1]:.2f}")
        within = sum(1 for d in ds
                     if d <= RASTER_REACH_BAND_OFFNET_RADIUS_M)
        print(f"  ON the domain (d=0): {sum(1 for d in ds if d <= 1e-9)}   "
              f"within {RASTER_REACH_BAND_OFFNET_RADIUS_M} m: {within}  "
              f"BEYOND it: {n - within}")
        dz = sorted(abs(r[2]) for r in road)
        print(f"  |dz| (m): min {dz[0]:.2f} p50 {dz[n // 2]:.2f} "
              f"max {dz[-1]:.2f}")
        print("  worst 12 road clamps:")
        for (role, s, d_z, d, lat, lon, _x, _y) in sorted(
                road, key=lambda r: -abs(r[2]))[:12]:
            print(f"    {role:<17} {s:<5} dz {d_z:+7.2f} m  "
                  f"d_airside {d:7.2f} m  {lat:.7f},{lon:.7f}")
    other = [r for r in rows if r[0] not in ROAD_ROLES]
    if other:
        ds = sorted(r[3] for r in other)
        n = len(ds)
        print(f"\nNON-ROAD clamp records: {n}; d_airside "
              f"p50 {ds[n // 2]:.2f} max {ds[-1]:.2f}")
    if site:
        report_site(p, site, rows, domain)
    return rows


def report_site(p: _Patch, site, rows, domain):
    """The ring profile at one owner-named lat/lon — before/after evidence."""
    sx, sy = p.to_m(*site)
    print(f"\nOWNER SITE {site[0]}, {site[1]} -> local m ({sx:.2f}, {sy:.2f})")
    near = sorted(rows, key=lambda r: math.hypot(r[6] - sx, r[7] - sy))[:8]
    for (role, s, d_z, d, lat, lon, x, y) in near:
        print(f"  clamp {role:<17} {s:<5} dz {d_z:+7.2f}  d_airside "
              f"{d:7.2f} m  {math.hypot(x - sx, y - sy):6.1f} m from site  "
              f"{lat:.7f},{lon:.7f}")
    if not near:
        print("  (no band-clamp record anywhere in the patch)")
    clamped = [(r[6], r[7], r[2]) for r in rows]
    print("  ROAD ring vertices within 60 m of the site "
          "(alt, dist-to-airside, clamped?):")
    seen = set()
    for (w, nids, pts, elevs, _poly) in p.rings:
        if w.role not in ROAD_ROLES:
            continue
        for (x, y), nid, alt in zip(pts, nids, elevs):
            if math.hypot(x - sx, y - sy) > 60.0 or nid in seen:
                continue
            seen.add(nid)
            d = (Point(x, y).distance(domain)
                 if domain is not None else float("nan"))
            best = min(((math.hypot(cx - x, cy - y), dzc)
                        for (cx, cy, dzc) in clamped), default=(9e9, 0.0))
            tag = ("CLAMPED %+.2f" % best[1]) if best[0] <= 0.30 else "-"
            print(f"    way {w.wid:<8} {w.role:<17} alt {str(alt):>8}  "
                  f"d_airside {d:7.2f} m  {tag:<16} "
                  f"{math.hypot(x - sx, y - sy):5.1f} m")
    # The RING PROFILE: the worst step on every road ring touching the site.
    print("  ring PROFILE (worst edge per road ring within 60 m):")
    for (w, nids, pts, elevs, _poly) in p.rings:
        if w.role not in ROAD_ROLES:
            continue
        if min((math.hypot(x - sx, y - sy) for (x, y) in pts),
               default=9e9) > 60.0:
            continue
        worst = _worst_ring_edge(pts, elevs)
        if worst is None:
            continue
        dz, L, g = worst
        print(f"    way {w.wid:<8} {w.role:<17} n={len(pts):<3} "
              f"alt {min(v for v in elevs if v is not None):.2f}"
              f"..{max(v for v in elevs if v is not None):.2f} m  "
              f"worst edge {dz:.2f} m over {L:.2f} m = {100 * g:.1f} %")


def _worst_ring_edge(pts, elevs, only_keys=None, nids=None):
    """``(|dz|, length, grade)`` of the ring's worst consecutive edge.

    ``only_keys`` (with ``nids``) restricts the walk to the given
    canonical edge keys — used for the CONTACT edges a road ring holds in
    common with an airside ring.
    """
    best = None
    n = len(pts)
    for k in range(n):
        if only_keys is not None:
            key = frozenset((nids[k], nids[(k + 1) % n]))
            if key not in only_keys:
                continue
        a, b = elevs[k], elevs[(k + 1) % n]
        if a is None or b is None:
            continue
        (x1, y1), (x2, y2) = pts[k], pts[(k + 1) % n]
        L = math.hypot(x2 - x1, y2 - y1)
        if L <= 1e-9:
            continue
        dz = abs(float(b) - float(a))
        if best is None or dz / L > best[2]:
            best = (dz, L, dz / L)
    return best


# ──────────────────────────────────────────────────────────────────
# Mode 2 — the contact rings (RULINGS 2026-08-25b)
# ──────────────────────────────────────────────────────────────────
def report_contact_rings(p: _Patch, near_miss_m: float = 1.0):
    airside = [(w, nids, pts, elevs, poly) for (w, nids, pts, elevs, poly)
               in p.rings if w.role in DOMAIN_ROLES]
    roads = [(w, nids, pts, elevs, poly) for (w, nids, pts, elevs, poly)
             in p.rings if w.role in ROAD_ROLES]
    print(f"patch          : {p.path}")
    print(f"airside rings  : {len(airside)}   road rings: {len(roads)}")
    print(f"contact rule   : EDGE-SHARING by canonical node identity "
          f"(RULINGS 2026-08-25b); near-miss horizon {near_miss_m} m")

    # Index every airside edge key -> the airside ways carrying it.
    edge_owner = collections.defaultdict(list)
    for (w, nids, _pts, _e, _poly) in airside:
        for key in _edge_keys(nids):
            edge_owner[key].append(w)

    contact, near = [], []
    airside_union = unary_union([r[4] for r in airside]) if airside else None
    for (w, nids, pts, elevs, poly) in roads:
        shared = []
        for key in _edge_keys(nids):
            for aw in edge_owner.get(key, ()):
                shared.append((key, aw))
        if shared:
            partners = sorted({aw.role for (_k, aw) in shared})
            pids = sorted({aw.wid for (_k, aw) in shared})
            worst = _worst_ring_edge(pts, elevs)
            # The CONTACT EDGE itself — the edge the ruling is about: the
            # one the road and the apron hold in common.  A step here is
            # a step ACROSS the shared boundary of two surfaces that the
            # ruling says are one surface under one law.
            keys = {k for (k, _aw) in shared}
            cworst = _worst_ring_edge(pts, elevs, only_keys=keys, nids=nids)
            contact.append((w, len(shared), partners, pids, worst, poly,
                            cworst))
            continue
        if airside_union is None:
            continue
        d = poly.distance(airside_union)
        if d <= near_miss_m:
            near.append((w, d, _worst_ring_edge(pts, elevs)))

    print(f"\nCONTACT RINGS (share >=1 edge with airside): {len(contact)}")
    over = [c for c in contact
            if c[6] and c[6][2] > APRON_MAX_GRADE + 1e-9]
    print(f"  of which the SHARED EDGE itself steps over the apron cap "
          f"({100 * APRON_MAX_GRADE:.1f} %): {len(over)}")
    contact.sort(key=lambda c: -(c[6][2] if c[6] else 0.0))
    for (w, n_edges, partners, pids, worst, poly, cworst) in contact:
        if cworst is None or cworst[2] <= APRON_MAX_GRADE + 1e-9:
            continue
        c = poly.representative_point()
        ll = _to_ll(p, c.x, c.y)
        wt = (f"worst RING edge {worst[0]:.2f} m over {worst[1]:.2f} m "
              f"= {100 * worst[2]:.1f} %" if worst else "no elevations")
        print(f"  way {w.wid:<8} {w.role:<17} area {poly.area:8.0f} m2  "
              f"{n_edges:2d} shared edge(s) with {','.join(partners)} "
              f"(ways {','.join(pids[:4])}{'…' if len(pids) > 4 else ''})  "
              f"CONTACT edge {cworst[0]:.2f} m over {cworst[1]:.2f} m = "
              f"{100 * cworst[2]:.1f} %  |  {wt}  at {ll}")
    if over:
        w0 = max((c[6] for c in over), key=lambda t: t[2])
        print(f"  WORST contact EDGE: {w0[0]:.2f} m over "
              f"{w0[1]:.2f} m ({100 * w0[2]:.1f} %)")

    print(f"\nNEAR-MISS rings (<= {near_miss_m} m from airside, NO shared "
          f"edge — reported, NEVER absorbed): {len(near)}")
    for (w, d, worst) in sorted(near, key=lambda t: t[1]):
        wt = (f"worst edge {worst[0]:.2f} m over {worst[1]:.2f} m "
              f"= {100 * worst[2]:.1f} %" if worst else "no elevations")
        print(f"  way {w.wid:<8} {w.role:<17} gap {d:6.3f} m  {wt}")
    return contact, near


def _to_ll(p: _Patch, x, y):
    """Best-effort local-metres -> 'lat,lon' for a site line (report only)."""
    best, bestd = None, 9e9
    for (_w, nids, pts, _e, _poly) in p.rings:
        for nid, (px, py) in zip(nids, pts):
            d = math.hypot(px - x, py - y)
            if d < bestd:
                best, bestd = nid, d
    if best is None:
        return f"({x:.0f},{y:.0f}) m"
    lat, lon = p.nodes[best]
    return f"{lat:.7f},{lon:.7f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patch", help="the emitted .osm patch (its "
                                  ".axes.json sidecar must sit beside it)")
    ap.add_argument("--contact-rings", action="store_true",
                    help="road<->airside EDGE-SHARING contact rings + "
                         "near-miss list (RULINGS 2026-08-25b)")
    ap.add_argument("--near-miss-m", type=float, default=1.0,
                    help="near-miss horizon in metres (default 1.0)")
    ap.add_argument("--site", default=None,
                    help="LAT,LON — the ring profile at one named site")
    args = ap.parse_args(argv)
    p = _Patch(Path(args.patch))
    site = None
    if args.site:
        site = tuple(float(v) for v in args.site.split(","))
    if args.contact_rings:
        report_contact_rings(p, args.near_miss_m)
        if site:
            report_site(p, site, [], p.domain())
        return 0
    report_clamps(p, site)
    return 0


if __name__ == "__main__":
    sys.exit(main())
