"""§2 (1)/(2)/(3) THE PLANE-PAD MINT — one pad per BASE PLANE of a unit
whose composed profile reads STEPPED, the object's own riser DECLARED
between them; a SLOPED unit's one pad carries the object's own gradient.

Owner law: RULINGS **2026-10-01f** (the design order, verbatim: *"detect
building's base shape and orientation (e.g. a building that has steps
where part of it is at one level and another part is at a higher level,
and create two pads with a cliff to match them)"*), **10-01k** Q2 (the
riser is the steepest cell on the 0.5 m identity strip, never a 1:3
bank), Q3 (a non-origin plane touching an apron gets its OWN frontage
hold at its level — not a 28b terrace), Q4 (no cap on pads per unit:
every plane ≥ ``min_area_m2`` whose riser survives the weld), Q5 (a
SLOPED pad carries the object's own base gradient with no 1.5 % clamp and
WELDS its airside frontage).  Issues #162 / #163 / #111.

WHERE THIS RUNS, AND WHY EXACTLY HERE (owner RULINGS 2026-10-02m (C) --
THE MEASURED REASON PR #196 WAS REVERTED).  LAST in the pad chain of
``planar/overlay.build_arrangement``: after the 23a apron cut, the 28b
terrace, ``platform.platform_split`` AND ``pad_cut.plateau_cut``.

#196 ran it between the 28b terrace and the platform split, on the
argument that the pad polygon was already final.  It is not: the split
MINTS the held blocks (``model.platform.HELD``) and ``plateau_cut`` then
CUTS THE APRON around them.  So a changed pad changed the held set,
which changed the plateaus, which changed the APRON -- and the apron is
airside.  Measured at HECA: **214 runway movers**, worst 0.200 m at
30.13230718766 / 31.39756435498, stage-1 airside unknowns 19,909 ->
19,726.  Airside is king and a mint that moves a runway vertex is a
STOP, so the mint now runs where nothing downstream of it reads the
airside: every base region is final before it is called, and it takes
and returns pad regions ALONE.

WHAT THAT COSTS, REPORTED NOT DECIDED.  A plane pad no longer passes
through ``platform_split``, so a non-origin plane pad is a §20
CONFORMING pad (``constraints/platform._conforming_records``,
``constraints/pads.pad_flats``) and not a platform inside a collar; and,
being held off the unit's rim by ``geom.base_planes``'s hold (10-02m
(C)), it fronts no apron, so 10-01k Q3's own frontage hold has no case
to arise here.  ``p0`` KEEPS THE UNIT'S OWN PAD REF (not ``<unit>/p0``):
it is the region the split already minted, with its platform, its
collar, its hold and its datum column, which is exactly §2 (1)'s "p0
takes the unit's datum exactly as today".  Only the non-origin planes
take ``<unit>/p<k>``.
WHAT IS NOT MINTED HERE.  No row, no level, no joint record: this module
mints REGIONS and registers them (``model.base_step.PLANE_PADS`` /
``BASE_STEPS``).  The §2 (1) PIN — one hard ``Diff`` row ``z_{D_k} −
z_{D_0} = Δy_k`` per non-origin plane pad — is
``constraints/platform.plane_offset_rows``, and the two must be in the
tree together: a plane pad minted WITHOUT its pin is two independently
frontage-held pads at two free datums, an UNCONTROLLED cliff, which is
worse than today's single pad (PR #174's reported finding 3, and §6
already treats a relaxed plane-offset row as a STOP).

A UNIT READING ROOF / FEET / FLAT MINTS NOTHING, byte-identically: the
composed read publishes no plane pair, this pass returns its input list,
and no registry gains an entry.  That is §1 (3)'s "a unit with no base
plane keeps today's law exactly" and §5 A5's control counts.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon
from shapely.strtree import STRtree

from ..airport.placement_contact import m_per_deg_exact
from ..airport.obj8_grade import FLAT, SLOPED, STEPPED, profile_from_json
from ..geom.base_planes import place, plane_regions
from ..law import Law
from ..model.base_step import (BASE_STEPS, PLANE_PADS, BaseStep, PlanePad)
from ..model.planar import COLLAR_SUFFIX, plane_ref


def _derive_clusters(airport, law: Law):
    """The cluster derivation, asked for ONLY where the airport carries
    none (a twin's fixture) -- never on a build path."""
    from .cluster import clusters as _c
    return _c(airport, law)

__all__ = ["plane_pad_split", "WHY"]

#: WHY a mint came out empty, or which gate dropped a plane — read by the
#: build's own say-line and by the sidecar, so a silent "no plane pads"
#: is never mistaken for "this pack has no stepped building"
#: (``planar/cluster.WHY``'s pattern).
WHY: dict[str, object] = {}

#: The verdicts that mint anything at all (§1 (2)).  ``FLAT`` and ``FEET``
#: keep today's law exactly.
_MINTING = frozenset({STEPPED, SLOPED})


def _strip_width_m(law: Law) -> float:
    """§2 (3) / §4: ``[identity] min_distinct_spacing_m`` — the riser
    strip's width, ONE derivation site.  It is the identity law's own
    number because the strip exists to keep the two rims from sharing an
    XY, and ``emit/osm_adapter.merge_sub_spacing`` sees identity spacing
    by construction (C24).  0 disarms the strip, and the mint then
    refuses the unit (two coincident rims are not emittable)."""
    return float(law.tables.emit.identity.min_distinct_spacing_m)


def _plane_min_area_m2(law: Law) -> float:
    """§1 (1) / §2 (1): ``[building_pad] min_area_m2`` — the smallest pad
    the mint keeps, ONE derivation site (the same floor
    ``platform_split`` applies to a platform piece).  A plane under it is
    furniture, not ground a unit stands on."""
    return float(law.tables.structures.building_pad.min_area_m2)


def _armed(law: Law) -> bool:
    """§1 (1): ``[base_profile] horizontal_ny`` 0 disarms the base read,
    so there is no profile to mint from — ONE gate, the read's own."""
    return float(law.tables.structures.base_profile.horizontal_ny) > 0.0


def _cluster_pieces(airport, law: Law):
    """``[(cluster, its pad polygon in the planar frame)]`` for the
    clusters whose composed profile MINTS — through
    ``geom.cluster_outlines``, the SAME derivation ``classify/evidence``
    minted the pads from and ``constraints/cluster_pad`` censuses against
    (§46 (9) census row 5; a second spelling of "the cluster's footprint"
    is the census-wrapper defect).  ``[]`` where nothing mints.

    THE CLUSTERS ARE READ OFF ``Airport.clusters`` (owner RULINGS
    2026-10-02m (F)).  #196 called ``planar.cluster.clusters(airport,
    law)``, whose ``_MEMO`` is keyed on ``id(airport)`` -- and
    ``pipeline/build.py`` derives the clusters and then STAMPS them with
    ``dataclasses.replace``, so the airport the planar stage holds is a
    DIFFERENT OBJECT from the one the memo was filled for.  Every call
    missed and re-ran ``plan_clusters`` with the composed base read:
    **36 of the mint's 37.7 s at HECA**, against a +1.0 s bar.
    ``Airport.clusters`` is where §1 (4) says the planar stage reads the
    profile from ("as it reads the cluster today") and it is already
    carried on the airport for exactly that reason; the derivation below
    is the fallback for a twin whose fixture stamps none."""
    # ``getattr`` and not ``c.base_profile``: ``Airport.clusters`` is a
    # public channel, and a cluster carrying NO profile at all (a plan
    # before version 12, a twin's fixture) is §1 (3)'s "a unit with no
    # base plane keeps today's law exactly" -- it mints nothing, it does
    # not raise.  (Measured: the full suite's ``test_v2clusterpad`` and
    # ``test_v2jetwaystrip`` fixtures are cluster-shaped stand-ins with
    # no ``base_profile``, and attribute access took 17 of them red.)
    cl = [c for c in (getattr(airport, "clusters", None)
                      or _derive_clusters(airport, law) or ())
          if (getattr(c, "base_profile", None) or {}).get("verdict")
          in _MINTING]
    if not cl:
        return []
    from ..geom import cluster_outlines
    to_xy = airport.frame.entry()
    st = law.tables.structures.placement
    got, _counts = cluster_outlines(
        cl, to_xy, float(st.footprint_touch_m), walled_only=True,
        bridge_m=float(getattr(st, "post_bridge_gap_m", 0.0) or 0.0))
    return [(c, poly) for _pid, c, poly in got]


def _pad_of(poly: Polygon, pads: list, tree: "STRtree | None",
            ) -> "int | None":
    """The index of the pad region ``poly`` belongs to — the one it
    OVERLAPS MOST.  Geometric because the pad REF is minted in
    ``classify`` and carries no cluster id; the overlap is unambiguous
    because ``cluster_outlines`` already made the pieces disjoint (its
    ``taken`` list) and ``classify`` minted one pad per piece."""
    if tree is None or poly is None or poly.is_empty:
        return None
    best, best_a = None, 0.0
    for j in tree.query(poly):
        P = pads[int(j)].polygon
        try:
            a = float(poly.intersection(P).area)
        except Exception:                       # noqa: BLE001
            continue
        if a > best_a:
            best, best_a = int(j), a
    return best


def plane_pad_split(pad_regions, law: Law, grid: float = 0.0, airport=None
                    ) -> tuple[list, dict]:
    """THE MINT (module docstring).  Returns ``(pad_regions, counts)``.

    A no-op — the input list returned unchanged, both registries empty —
    where the base read is disarmed, no pack was read, or no cluster's
    composed profile reads STEPPED or SLOPED.
    """
    PLANE_PADS.clear()
    BASE_STEPS.clear()
    WHY.clear()
    counts: dict[str, _t.Any] = {"plane_pads": 0, "base_steps": 0,
                                 "plane_units": 0, "sloped_units": 0}
    if airport is None or not _armed(law) or not pad_regions:
        WHY["gate"] = ("no airport" if airport is None
                       else "law disarmed ([base_profile] horizontal_ny 0)"
                       if not _armed(law) else "no pad regions")
        return list(pad_regions), counts
    _to_xy, to_ll = airport.frame.transformers()
    strip_m = _strip_width_m(law)
    pmin = _plane_min_area_m2(law)
    frontage = float(law.tables.emit.design.pad_frontage_m)
    pieces = _cluster_pieces(airport, law)
    WHY["candidates"] = len(pieces)
    if not pieces:
        WHY["gate"] = "no cluster reads STEPPED or SLOPED"
        return list(pad_regions), counts
    pads = [r for r in pad_regions
            if isinstance(r.polygon, Polygon) and not r.polygon.is_empty
            and not str(r.ref).endswith(COLLAR_SUFFIX)]
    if not pads:
        WHY["gate"] = "no pad region to mint into"
        return list(pad_regions), counts
    tree = STRtree([r.polygon for r in pads])
    by_ref: dict[str, list] = {}
    replace: dict[str, list] = {}
    drops: list[str] = []
    for c, piece in pieces:
        j = _pad_of(piece, pads, tree)
        if j is None:
            drops.append(f"{c.id}: no pad region")
            continue
        pr = pads[j]
        ref = str(pr.ref)
        if ref in replace:
            # two clusters onto one pad region: the pad is not this unit's
            # alone and §2 (1)'s "the unit footprint union" does not hold
            drops.append(f"{c.id}: pad {ref} already claimed")
            continue
        prof = profile_from_json(c.base_profile)
        anchor = tuple(getattr(c, "profile_anchor", (0.0, 0.0)) or (0.0, 0.0))
        if prof.verdict == SLOPED:
            # §2 (2) / Q5: ONE pad, no new region — the layout is
            # untouched and only the pad's PLANE ROWS change (the carried
            # gradient, ``constraints/platform.platform_plane_rows``).
            # The frontage WELDS as it does today, which is Q5's "the
            # frontage hold wins at the weld line".
            PLANE_PADS[ref] = PlanePad(
                ref=ref, unit=ref, k=0, dy_m=0.0,
                y_m=float(prof.planes[0].y if prof.planes else prof.feet_y),
                area_m2=round(float(pr.polygon.area), 1),
                gradient=(float(prof.slope[0]), float(prof.slope[1])),
                verdict=SLOPED)
            counts["sloped_units"] += 1
            continue
        if anchor == (0.0, 0.0):
            drops.append(f"{c.id}: composed profile carries no anchor")
            continue
        ys = [float(p.y) for p in prof.planes]
        placed = place([p.polygon for p in prof.planes], anchor,
                       airport.frame.entry(), m_per_deg_exact(float(anchor[0])))
        pcounts: dict = {}
        regs, strips = plane_regions(
            placed, ys, [(r.a, r.b, r.dy) for r in prof.risers],
            pr.polygon, strip_m=strip_m, frontage_m=frontage,
            min_area_m2=pmin, counts=pcounts, hold_m=strip_m)
        if not regs or not strips:
            drops.append(f"{c.id}/{ref}: "
                         + (",".join(sorted(pcounts)) or "no plane pair"))
            continue
        out: list = []
        areas: dict[int, float] = {}
        for g in regs:
            out.append(_dc.replace(pr, ref=_ref_of(ref, g.k),
                                   polygon=g.polygon))
            areas[g.k] = areas.get(g.k, 0.0) + float(g.polygon.area)
        for k in sorted(areas):
            dy = next(g.dy for g in regs if g.k == k)
            y = next(g.y for g in regs if g.k == k)
            pref = _ref_of(ref, k)
            PLANE_PADS[pref] = PlanePad(
                ref=pref, unit=ref, k=k, dy_m=round(dy, 4), y_m=round(y, 4),
                area_m2=round(areas[k], 1), verdict=STEPPED)
        for s in strips:
            BASE_STEPS.append(BaseStep(
                unit=ref, lower_ref=_ref_of(ref, s.a),
                upper_ref=_ref_of(ref, s.b), lower_k=s.a, upper_k=s.b,
                declared_step_m=round(float(s.dy), 4),
                strip_m2=round(float(s.strip.area), 2),
                strip_width_m=strip_m,
                line=_line_rings(s.line, to_ll)))
        replace[ref] = out
        by_ref[ref] = [g.k for g in regs]
        counts["plane_units"] += 1
    if drops:
        WHY["dropped"] = "; ".join(sorted(drops)[:12])
        WHY["dropped_n"] = len(drops)
    counts["plane_pads"] = len(PLANE_PADS) - counts["sloped_units"]
    counts["base_steps"] = len(BASE_STEPS)
    WHY["plane_units"] = counts["plane_units"]
    WHY["sloped_units"] = counts["sloped_units"]
    WHY["plane_list"] = "; ".join(
        f"{u} -> {len(ks)} plane pad(s) p{min(ks)}..p{max(ks)}"
        for u, ks in sorted(by_ref.items()))
    if not replace:
        return list(pad_regions), counts
    # ONE REF, ONE UNIT: every OTHER region of a replaced pad's ref (a 23a
    # rim sliver the cut left behind) joins the plane pad it stands
    # NEAREST — the ``platform_split`` ``_to_block`` rule, so no region
    # keeps a ref whose pad no longer exists.
    out: list = []
    for r in pad_regions:
        ref = str(r.ref)
        base = ref[:-len(COLLAR_SUFFIX)] if ref.endswith(COLLAR_SUFFIX) else ref
        if base not in replace:
            out.append(r)
            continue
        if ref == base and _is_the_pad(r, replace[base]):
            out.extend(replace[base])
            continue
        # a sliver (or the collar of a pad that had one): nearest plane pad
        regs = replace[base]
        if r.polygon is None or r.polygon.is_empty:
            out.append(r)
            continue
        k = min(range(len(regs)),
                key=lambda i: regs[i].polygon.distance(r.polygon))
        suffix = COLLAR_SUFFIX if ref.endswith(COLLAR_SUFFIX) else ""
        out.append(_dc.replace(r, ref=str(regs[k].ref) + suffix))
    return out, counts


def _ref_of(unit: str, k: int) -> str:
    """The ref of plane pad ``k`` -- ``<unit>/p<k>`` for a non-origin
    plane and THE UNIT'S OWN REF for ``p0`` (module docstring)."""
    return unit if int(k) == 0 else plane_ref(unit, int(k))


def _is_the_pad(r, regs: list) -> bool:
    """Is ``r`` the region the plane pads REPLACE (the unit's own pad), as
    opposed to another region of the same ref (a 23a rim sliver)?  The
    plane pads were cut OUT of it, so it is the region that contains
    them."""
    # PRECISION-FREE (lane basepads4read, PR #220 item 5): the pad region
    # carries the arrangement's 0.5 m GEOS fixed-precision model, under
    # which ``buffer(1e-6)`` snap-rounds to nothing and ``contains``
    # then answers False for the pad's OWN plane pads -- the mint falls
    # through to the sliver path and replaces nothing.  Found by this
    # PR's own precision twin.
    import shapely
    try:
        P = shapely.set_precision(r.polygon, 0.0)
        return all(P.buffer(1e-6).contains(
            shapely.set_precision(g.polygon, 0.0).representative_point())
            for g in regs)
    except Exception:                           # noqa: BLE001
        return False


def _line_rings(line, to_ll) -> tuple:
    """A riser line as ``(lat, lon)`` tuples for the record — one tuple per
    part of a ``MultiLineString``.

    LAT/LON AND NOT FRAME METRES: the record is read by
    ``pipeline/publication.base_step_joints``, which holds the planar map
    but not the airport frame, and a sidecar record in frame metres would
    be the second spelling of a coordinate nothing else in
    ``terrace_joints`` uses.  The conversion happens here, where the frame
    is in hand."""
    if line is None or to_ll is None:
        return ()
    parts = getattr(line, "geoms", None) or ([line] if hasattr(line, "coords") else [])
    out = []
    for g in parts:
        try:
            out.append(tuple((float(la), float(lo))
                             for la, lo in (to_ll(x, y) for x, y in g.coords)))
        except Exception:                       # noqa: BLE001 — named by the count
            continue
    return tuple(q for q in out if len(q) >= 2)
