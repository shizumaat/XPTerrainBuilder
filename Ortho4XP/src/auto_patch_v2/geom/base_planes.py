"""§2 (1)/(3) THE PLANE PADS OF ONE UNIT, AS GEOMETRY — the composed base
planes placed in the planar frame, clipped to the unit's pad, and the
RISER STRIPS cut between adjacent planes.

It lives in ``geom`` for the reason ``geom/cluster_outline`` does (owner
RULINGS 2026-09-11x (4), the layering twin): the pad polygon the planes
are clipped to is minted in ``planar`` and read in ``constraints``, and
those two layers may not import each other.  A second spelling of "where
does plane k's pad go" is the census-wrapper defect in geometry
(RULINGS 2026-08-30l), so the shape is derived here, ONCE, and both
readers ask it.

ONLY SHAPE HERE.  The polygons, a transformer and the tolerances in, the
regions out; no law value is read — the caller passes the law's own
(``planar/plane_pads`` holds the ``Law``).

THE FRAMES.  ``PlanCluster.base_profile``'s polygons are metres
EAST/NORTH of ``PlanCluster.profile_anchor`` (``placement_family.
cluster_base_profile`` composes about the unit anchor).  The planar map's
frame is the airport's own.  :func:`place` is the ONE conversion between
them: east/north -> ``(lat, lon)`` at the anchor's own metres-per-degree,
then through the airport frame's entry — the same two steps the
composition took in reverse, so the round trip is the identity to the
frame's own precision and the twin asserts it.

THE REGIONS PARTITION THE PAD (owner RULINGS 2026-10-02m (C)/(D), the
two measured STOPs that reverted PR #196).

(D) THEY ARE DISJOINT.  #196 clipped every plane to the pad
INDEPENDENTLY, so two planes whose face unions overlapped in plan came
out as the SAME polygon at two levels -- SPJC ``building21`` p0 and p1,
one 11,549 m2 polygon 5.0 m apart, of which one pad vanished in the
patch while the registry went on listing it.  A terrain surface is
single-valued in plan: the regions are resolved LOWEST PLANE FIRST and
each later plane keeps only what no lower plane claimed, because a
higher plane overlapping a lower one stands ON it (the storey reading
``obj8_grade._storeys`` makes at the base read; this is the same law
spelled in geometry, for the slivers a clip leaves behind).  The
resolved area is COUNTED, never silent.

(C) THEIR UNION IS THE PAD, LESS THE STRIPS, AND NO AIRSIDE VERTEX MOVES.
``p0`` is not its own face union: it is THE PAD LESS the other planes
less the strips.  Two things follow, and both are the (C) fix.  First
nothing is left unclaimed -- #196 replaced the unit's pad region with
the planes' own unions and whatever the planes did not cover became a
HOLE where a building pad had been.  Second ``p0``'s OUTER RING IS THE
PAD'S, coordinate for coordinate, so the rim the apron is welded along
is untouched.  The non-origin planes are additionally held
``strip_m`` back from the pad's boundary (:func:`plane_regions`'s
``hold_m``), so no minted ring reaches the rim and no new vertex can
appear on it: 214 RUNWAY vertices moved at HECA under #196 (worst 0.200
m, stage-1 airside unknowns 19,909 -> 19,726) and airside is king.  The
cost is a ``min_distinct_spacing_m`` lip of ``p0`` wherever an upper
plane would otherwise reach the unit's edge; it also means a non-origin
plane never touches an apron, so 10-01k Q3's own frontage hold has no
case to arise here -- REPORTED, not decided.

THE STRIP IS A GAP, NOT A FACE (§2 (3), §4; the wall-gap precedent
RULINGS 2026-09-01c, ``structures.toml`` ``wall_gap_m``).  A heightfield
cannot carry a vertical face, so the riser is TWO VERTEX ROWS
``min_distinct_spacing_m`` apart in XY at two levels: plane ``a``'s rim
and plane ``b``'s rim, pulled back half the spacing each from the riser
line, with NOTHING claiming what is between them.  The mesher's
triangles across that gap are the steep triangles — exactly as the OSM
bore's ramp edge stands ``wall_gap_m`` off its at-grade rim — and the
object's own riser faces stand on them.  The step is forgiven and priced
through the DECLARED ``base_step`` joint (``pipeline/publication``), the
way 28b's pad|apron terrace is; nothing here prices anything.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import MultiLineString, Polygon
from shapely.ops import unary_union

__all__ = ["place", "plane_regions", "PlaneRegion", "RiserStrip"]

import dataclasses as _dc


@_dc.dataclass(frozen=True)
class PlaneRegion:
    """One base plane's pad REGION in the planar frame: its index ``k``
    into ``BaseProfile.planes`` (0 is the origin plane ``p0``, §1 (3)),
    its authored offset ``dy = y_k - y_0``, and the polygon — the plane's
    own face union, clipped to the unit's pad and less every riser strip
    it touches."""

    k: int
    dy: float
    polygon: Polygon
    #: the plane's authored height, carried for the report line
    y: float = 0.0


@_dc.dataclass(frozen=True)
class RiserStrip:
    """One riser between two plane regions: the pair's plane indices, the
    DECLARED height difference ``dy = y_b - y_a`` (the object's own
    authored riser — never a measured step), the strip polygon cut out of
    both, and the riser LINE the strip is centred on (the joint the
    census is declared against)."""

    a: int
    b: int
    dy: float
    strip: Polygon
    line: _t.Any


def place(polys: "_t.Sequence", anchor: tuple[float, float],
          to_xy: _t.Callable[[float, float], tuple[float, float]],
          m_per_deg: tuple[float, float]) -> list:
    """The composed polygons (metres east/north of ``anchor``) in the
    planar frame — the module docstring's ONE conversion.

    ``m_per_deg`` is ``(metres per degree of latitude, of longitude)`` at
    the anchor, as ``airport.contact.m_per_deg_exact`` gives it; the
    caller passes it rather than this module re-deriving it, so the
    placement and the composition read ONE ellipsoid.  A ``None`` or
    empty polygon comes back ``None`` and the caller names the drop."""
    from shapely.ops import transform
    la0, lo0 = float(anchor[0]), float(anchor[1])
    ml, mo = float(m_per_deg[0]), float(m_per_deg[1])
    if ml <= 0.0 or mo <= 0.0:
        return [None for _ in polys]

    def _fwd(xs, ys):
        out_x, out_y = [], []
        for e, n in zip(xs, ys):
            x, y = to_xy(lo0 + float(e) / mo, la0 + float(n) / ml)
            out_x.append(x)
            out_y.append(y)
        return out_x, out_y

    out: list = []
    for p in polys:
        if p is None or p.is_empty:
            out.append(None)
            continue
        try:
            q = transform(_fwd, p)
        except Exception:                       # noqa: BLE001 — named, not silent
            out.append(None)
            continue
        if q.is_empty:
            out.append(None)
            continue
        if not q.is_valid:
            q = q.buffer(0.0)
        out.append(q if not q.is_empty else None)
    return out


def _parts(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [q for q in getattr(g, "geoms", [])
            if isinstance(q, Polygon) and not q.is_empty]


def _riser_line(a: Polygon, b: Polygon, frontage_m: float):
    """The part of ``a``'s rim FACING ``b`` — ``a``'s boundary within
    ``frontage_m`` of ``b`` (§1 (1): two planes are adjacent when their
    polygons are within ``[seam] pad_frontage_m``).  ``None`` where they
    face each other nowhere."""
    try:
        line = a.boundary.intersection(b.buffer(max(frontage_m, 1e-9),
                                               join_style=2))
    except Exception:                           # noqa: BLE001
        return None
    if line.is_empty:
        return None
    if getattr(line, "length", 0.0) <= 0.0:
        # a corner touch faces nothing (``platform._MIN_WELDED``'s reason)
        return None
    return line


def plane_regions(polys: "_t.Sequence", ys: "_t.Sequence[float]",
                  risers: "_t.Sequence[tuple[int, int, float]]",
                  pad: Polygon, *, strip_m: float, frontage_m: float,
                  min_area_m2: float, counts: "dict | None" = None,
                  hold_m: "float | None" = None,
                  ) -> "tuple[list[PlaneRegion], list[RiserStrip]]":
    """§2 (1)/(3): the plane pads of one unit and the riser strips between
    them.

    ``polys`` are the composed planes ALREADY IN THE PLANAR FRAME
    (:func:`place`), ordered as ``BaseProfile.planes`` — index 0 is the
    origin plane ``p0``.  ``ys`` are their authored heights, ``risers``
    the adjacent pairs ``(a, b, dy)`` the base read welded and kept.

    Each plane is clipped to ``pad`` (§2 (1) "clipped to the unit
    footprint union": the pad polygon is the unit's own footprint after
    the 23a apron cut and the 28b terrace, so a plane reaching past the
    footprint — a lot the pack authored wider than the bodies standing on
    it — never widens the unit's claim).  Then every riser strip is cut
    out of BOTH its planes, half the spacing from each, so no two rims
    share an XY (the identity law, §4).

    A plane left under ``min_area_m2`` (the pad mint's own floor) is
    DROPPED and counted — its ground belongs to whatever encloses it, and
    a 40 m² pad with its own datum column and hold set is a solver
    liability, not a terrace.  THE ORIGIN PLANE IS NEVER DROPPED: it
    carries today's datum law (§2 (1)), so a unit whose ``p0`` falls under
    the floor mints NOTHING and keeps today's single pad — reported
    through ``counts["origin_under_min"]``, never a silent half-mint.

    Returns ``([] , [])`` for anything that leaves fewer than two planes:
    one plane is today's pad exactly and must stay byte-identical (§5 A1's
    FLAT fixture).
    """
    c = counts if counts is not None else {}
    if pad is None or pad.is_empty:
        c["no_pad"] = c.get("no_pad", 0) + 1
        return [], []
    if len(polys) < 2:
        # one plane IS today's pad (§1 (3)): the caller must get nothing
        # back, not one pad renamed ``/p0`` — a rename is not
        # byte-identical.  NAMED, so "no plane pads" is never silent.
        c["one_plane"] = c.get("one_plane", 0) + 1
        return [], []
    half = 0.5 * max(float(strip_m), 0.0)
    hold = max(float(strip_m), 0.0) if hold_m is None else max(float(hold_m), 0.0)
    inner_pad = pad
    if hold > 0.0:
        inner_pad = pad.buffer(-hold, join_style=2, mitre_limit=2.0)
        if inner_pad.is_empty:
            c["pad_eroded_away"] = c.get("pad_eroded_away", 0) + 1
            return [], []
    clipped: dict[int, Polygon] = {}
    for k, p in enumerate(polys):
        if p is None or p.is_empty:
            c["plane_unplaced"] = c.get("plane_unplaced", 0) + 1
            continue
        try:
            q = p.intersection(pad)
        except Exception:                       # noqa: BLE001
            c["plane_clip_failed"] = c.get("plane_clip_failed", 0) + 1
            continue
        if k != 0 and hold > 0.0:
            # (C) HELD OFF THE UNIT'S RIM: clipped to the pad SHRUNK by
            # ``hold``, so a minted ring never shares a coordinate with
            # the pad's outer boundary and the airside welded along it
            # keeps its own vertex set exactly (10-02m (C))
            try:
                q = q.intersection(inner_pad)
            except Exception:                   # noqa: BLE001
                c["plane_hold_failed"] = c.get("plane_hold_failed", 0) + 1
                continue
        keep = [g for g in _parts(q)]
        if not keep:
            c["plane_outside_pad"] = c.get("plane_outside_pad", 0) + 1
            continue
        g = keep[0] if len(keep) == 1 else unary_union(keep)
        clipped[k] = g
    if 0 not in clipped or len(clipped) < 2:
        c["no_pair"] = c.get("no_pair", 0) + 1
        return [], []
    # THE STRIPS, cut from both sides (§2 (3)).  Every kept riser whose
    # two planes both survived the clip; the line is read on the LOWER
    # plane's rim so the strip sits the same way whichever order the
    # pair arrived in.
    strips: list[RiserStrip] = []
    cut: dict[int, list] = {}
    for a, b, dy in risers:
        if a not in clipped or b not in clipped:
            continue
        lo, hi = (a, b) if float(ys[a]) <= float(ys[b]) else (b, a)
        line = _riser_line(clipped[lo], clipped[hi], frontage_m)
        if line is None:
            c["riser_no_facing_rim"] = c.get("riser_no_facing_rim", 0) + 1
            continue
        if half > 0.0:
            band = line.buffer(half, cap_style=2, join_style=2)
            try:
                band = band.intersection(pad)
            except Exception:                   # noqa: BLE001
                pass
        else:
            band = line.buffer(0.0)
        parts = _parts(band)
        if not parts:
            c["riser_strip_empty"] = c.get("riser_strip_empty", 0) + 1
            continue
        strip = parts[0] if len(parts) == 1 else unary_union(parts)
        cut.setdefault(lo, []).append(strip)
        cut.setdefault(hi, []).append(strip)
        strips.append(RiserStrip(
            a=lo, b=hi, dy=float(ys[hi]) - float(ys[lo]), strip=strip,
            line=(line if isinstance(line, MultiLineString)
                  else MultiLineString([line]) if hasattr(line, "coords")
                  else line)))
    if not strips:
        # two planes with no riser between them are two independent floors
        # the base read did not pair: not this law's case (§1 (1) — a riser
        # exists only between planes within ``pad_frontage_m``)
        c["no_riser"] = c.get("no_riser", 0) + 1
        return [], []
    out: list[PlaneRegion] = []
    y0 = float(ys[0])
    strip_all = unary_union([s.strip for s in strips]) if strips else None
    # (D) LOWEST PLANE FIRST, each keeping only what no lower plane took
    order = sorted((k for k in clipped if k != 0), key=lambda k: float(ys[k]))
    taken: list = []
    kept_poly: dict[int, _t.Any] = {}
    for k in order:
        g = clipped[k]
        if taken:
            try:
                g2 = g.difference(unary_union(taken))
            except Exception:                   # noqa: BLE001
                c["plane_overlap_cut_failed"] = \
                    c.get("plane_overlap_cut_failed", 0) + 1
                continue
            lost = float(g.area) - float(g2.area)
            if lost > 0.0:
                c["overlap_resolved_m2"] = round(
                    c.get("overlap_resolved_m2", 0.0) + lost, 2)
            g = g2
        if strip_all is not None:
            try:
                g = g.difference(strip_all)
            except Exception:                   # noqa: BLE001
                c["plane_cut_failed"] = c.get("plane_cut_failed", 0) + 1
                continue
        keep = [q for q in _parts(g) if q.area >= float(min_area_m2)]
        if not keep:
            c["plane_under_min"] = c.get("plane_under_min", 0) + 1
            continue
        g = keep[0] if len(keep) == 1 else unary_union(keep)
        kept_poly[k] = g
        taken.append(g)
        for q in keep:
            out.append(PlaneRegion(k=k, dy=float(ys[k]) - y0, polygon=q,
                                   y=float(ys[k])))
    # (C) ``p0`` IS THE PAD LESS EVERYTHING ELSE -- its outer ring is the
    # pad's own, so the rim the apron is welded along cannot move, and no
    # cell of the pad is left unclaimed
    g0 = pad
    if taken:
        try:
            g0 = g0.difference(unary_union(taken))
        except Exception:                       # noqa: BLE001
            c["origin_cut_failed"] = c.get("origin_cut_failed", 0) + 1
            return [], []
    if strip_all is not None:
        try:
            g0 = g0.difference(strip_all)
        except Exception:                       # noqa: BLE001
            c["origin_cut_failed"] = c.get("origin_cut_failed", 0) + 1
            return [], []
    keep0 = [q for q in _parts(g0) if q.area >= float(min_area_m2)]
    if not keep0:
        c["origin_under_min"] = c.get("origin_under_min", 0) + 1
        return [], []
    for q in keep0:
        out.append(PlaneRegion(k=0, dy=0.0, polygon=q, y=y0))
    out.sort(key=lambda r: (r.k, -r.polygon.area))
    planes_kept = {r.k for r in out}
    if len(planes_kept) < 2:
        c["one_plane_after_cut"] = c.get("one_plane_after_cut", 0) + 1
        return [], []
    strips = [s for s in strips if s.a in planes_kept and s.b in planes_kept]
    if not strips:
        c["no_riser_after_cut"] = c.get("no_riser_after_cut", 0) + 1
        return [], []
    return out, strips
