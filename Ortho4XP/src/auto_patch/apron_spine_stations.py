"""APRON SPINE STATIONS — §1/§3 of
docs/specs/heca-apron-round3-spec.md (2026-08-26).

OWNER RULING RULINGS 2026-08-26b item 4: *"it should probably join
seamlessly with taxiway centerline spines, since the whole apron must be
perfectly smooth for aircraft movement"* — the apron lattice is not a
private membrane; where a taxi centerline crosses a latticed apron the
two must solve as ONE surface.

THE DEFECT THIS CLOSES (items 3 and 5, one mechanism).  The owner's
84.2 m line T at HECA carried ZERO interior emitted stations: vertices
only at arc 0.00 (74.02) and 84.22 (74.55).  The taxi ROUTE was never
cut — the sidecar axes 656→663→662→212→210/215 chain straight across the
apron at cap 1.5 % — what was cut is the ANCHORED SURFACE along the
crossing.  With no emitted vertex between the two ends, the junction
pieces the centerline profile DOES anchor (73.87–74.34) stand 0.7–1.2 m
proud of the membrane beside them (73.12–73.61), and the same membrane,
coupled only to its own ring (which spans 61–74 on apron -10659), sags
to 70.11 at the owner's dip site.  Proud ridge and bowl are the two
sides of ONE missing coupling.

WHAT A STATION IS, AND WHAT IT IS NOT.  A station is a CENTERLINE node:
it lies exactly on an aircraft taxi axis, it joins the phase-A scaffold
anchor set, and it takes the route profile's solved value exactly as a
junction-ring centerline node does.  It mints NO new authority — the
axis's own profile is the authority, and the station is simply a place
where that profile becomes an emitted, priced vertex.  It is NOT a
lattice point (those are free interior apron variables) and NOT a new
route (the route already exists, whole).

THE ONE ENUMERATION.  The axis population is
``grade_graph.centerline_specs`` — the same list the sidecar's
``axes_exact`` publishes (``verification.taxi_axes_exact_ll`` walks that
function).  A second private notion of "which axes are taxi axes" is the
census-wrapper defect in miniature.  Service (road) axes are excluded:
a truck route is not an aircraft spine.

HOW A STATION BECOMES A SPINE NODE.  ``_build_global_spine`` strings
every node of ``G.pos`` that lies within ``SPINE_PERP_TOL_M`` of a
centerline, in ARC ORDER, at the centerline's own cap.  A station lies
ON its axis, so registering its position in ``G.pos`` (see
``grade_graph.build_unified_graph``) is the whole mechanism — no second
profile solver, no new edge kind.  Route METRIC is untouched by
construction: the stations are COLLINEAR interior points of an existing
axis, so a chain that used to be one budget ``cap·d`` becomes two whose
arc gaps sum to ``d``.  That is exactly what distinguishes this from the
R-a lateral-foot defect ``_build_global_spine`` documents, where OFF-axis
feet interleaved into cross edges and shortened routes until the final
band inverted.

SPACING.  ``layout.PAVEMENT_NODE_MAX_CHORD_M`` (60 m) — the standing
pavement-node rule ("a pavement edge keeps a node every ~60 m so the
solver holds the edge at its solved grade; a longer chord lets the
pavement sag visibly between distant nodes"), which is the very sag the
owner saw.  Reused, never re-spelled.  A crossing at or under the
spacing needs no interior node and gets none.  A crossing longer than it
is subdivided EVENLY into at least three sub-chords, so every crossing
that gets a station gets at least two: an emitted breakline needs two
nodes to exist at all (``to_osm`` writes only nodes a way references),
and a lone station would be a solver variable that never reaches the
patch — a lost measurement, not an anchor.
"""
from __future__ import annotations

import math

import O4_UI_Utils as UI

_GEOM_EXC = Exception

#: Lattice points closer than this multiple of ``APRON_LATTICE_SPACING_M``
#: to a station are joined to it by a law edge (spec §3.1).  Beyond it the
#: lattice keeps its own ring/lattice adjacency: a far pair would be a
#: chord across ground neither node controls.
LATTICE_JOIN_SPACING_MULT = 1.5

#: Sub-chords per crossing, FLOOR.  Not a spacing: the spacing is
#: ``layout.PAVEMENT_NODE_MAX_CHORD_M`` and this only ever makes a
#: crossing DENSER than that rule requires, never sparser.  It exists
#: because of the emit/parse contract, measured on this round's first
#: HECA arm: 13 of 18 crossings subdivided into two sub-chords carried
#: ONE emitted station each side, i.e. a TWO-node way — and
#: ``check_grade._parse_osm`` drops a way with fewer than three nodes
#: before its open-feature route, so 761 of 853 published station pairs
#: came back as LOST MEASUREMENTS and every site instrument reported the
#: owner's line T as stationless while the patch in fact carried two
#: stations on it.  Four sub-chords ⇒ three stations ⇒ the crossing is
#: always visible to the census that must price it.
_MIN_SUBDIVISION = 4


def _clip(*, lines_in, poly):
    """ONE implementation of the per-segment clip: the lattice's
    (``apron_lattice.clip_lines_to_apron``), at the ring itself.  A
    second copy here would be the census-wrapper defect in miniature."""
    from .apron_lattice import clip_lines_to_apron
    return clip_lines_to_apron(lines_in, poly, margin_m=0.0)


def _pieces_inside(axis_pts, poly):
    """The parts of one axis polyline that run INSIDE ``poly``, as lists
    of ``(x, y)`` in local metres.  Holes are respected by the geometry
    itself — a polygon's interior excludes its holes."""
    from shapely.geometry import LineString
    try:
        line = LineString([(float(x), float(y)) for (x, y) in axis_pts])
        if line.is_empty or line.length <= 0.0:
            return []
        inter = line.intersection(poly)
    except _GEOM_EXC:                                     # pragma: no cover
        return []
    if inter.is_empty:
        return []
    geoms = (list(inter.geoms) if inter.geom_type.startswith("Multi")
             or inter.geom_type == "GeometryCollection" else [inter])
    out: list = []
    for g in geoms:
        if getattr(g, "geom_type", "") != "LineString":
            continue
        pts = [(float(x), float(y)) for (x, y) in g.coords]
        if len(pts) >= 2:
            out.append(pts)
    return out


def stations_on_piece(pts, spacing_m):
    """The interior stations of ONE inside-the-apron axis piece.

    Even subdivision, so no sub-chord exceeds ``spacing_m``; a piece at
    or under the spacing gets none.  At least two stations whenever any
    are minted — see the module docstring (the emit contract).
    """
    if len(pts) < 2 or spacing_m <= 0.0:
        return []
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(seg)
    if total <= float(spacing_m):
        return []
    n_sub = max(_MIN_SUBDIVISION, int(math.ceil(total / float(spacing_m))))
    out: list = []
    for k in range(1, n_sub):
        s = total * k / n_sub
        acc = 0.0
        for (a, b), d in zip(zip(pts, pts[1:]), seg):
            if d <= 0.0:
                continue
            if acc + d >= s:
                t = (s - acc) / d
                out.append((a[0] + t * (b[0] - a[0]),
                            a[1] + t * (b[1] - a[1])))
                break
            acc += d
    return out


def construct_apron_spine_stations_presolve(layout, *, spacing_m=None,
                                            roles=("apron",)):
    """Build ``layout.apron_spine_presolve`` — one entry per apron an
    AIRCRAFT taxi axis crosses.

    Entry: ``{"shape", "shapeID", "points" [(x, y)], "lines" [[(x, y),
    ...]]}`` — ``lines`` is one polyline per crossing, in arc order, and
    is what the emitter writes as an ``apron_spine_station`` way.

    Called in the pipeline's FREEZE WINDOW slot, beside the gap spines
    and the apron lattice and BEFORE ``geometry_freeze.freeze``: a
    station is plan geometry, so it must exist before the plan is frozen
    and the ONE node list is built.

    Flag OFF: no store, and every downstream leg is vacuous —
    byte-identical.
    """
    from . import config as _cfg
    from .grade_graph import centerline_specs
    from .layout import PAVEMENT_NODE_MAX_CHORD_M, SHARED_VERTEX_TOL_M
    if not getattr(_cfg, "APRON_SPINE_STATIONS", False):
        layout.apron_spine_presolve = []
        return []
    if spacing_m is None:
        spacing_m = float(PAVEMENT_NODE_MAX_CHORD_M)
    try:
        specs = centerline_specs(layout)
    except _GEOM_EXC:                                     # pragma: no cover
        layout.apron_spine_presolve = []
        return []
    # AIRCRAFT axes only: a service centerline is a truck route, never an
    # aircraft spine (``grade_graph._reads_service_spines``).
    #
    # THE INDEX TRAVELS WITH THE AXIS.  ``ci`` is the axis's position in
    # ``centerline_specs`` — the SAME ordinal ``grade_graph.build_context``
    # gives ``ctx.centerlines`` and ``_build_global_spine`` keys
    # ``G.centerline_chains`` by, because all three walk that one
    # enumeration in that one order.  It is what lets a station read its
    # own axis's solved profile later (Amendment 2) instead of guessing
    # which axis it belongs to by proximity.
    axes = [(ci, pts)
            for ci, (pts, _caps, is_svc, _rkey, _rpts) in enumerate(specs)
            if not is_svc and len(pts or ()) >= 2]
    entries: list = []
    if not axes:
        layout.apron_spine_presolve = []
        return []
    # A station that would intern into an EXISTING plan vertex is not a
    # new variable — it would adopt that node and then be emitted a
    # second time at the same coordinate.  Skipped at construction, where
    # the whole plan is visible.  Same registry tolerance the canonical
    # points use.
    taken: list = []
    try:
        from shapely.geometry import Point as _Pt
        from shapely.strtree import STRtree as _Tree
        for s in (getattr(layout, "shapes", None) or ()):
            poly = getattr(s, "polygon", None)
            if poly is None or getattr(poly, "is_empty", True):
                continue
            if poly.geom_type != "Polygon":
                continue
            taken.extend((float(x), float(y))
                         for x, y in poly.exterior.coords)
        vtree = _Tree([_Pt(x, y) for (x, y) in taken]) if taken else None
    except Exception:                                     # pragma: no cover
        vtree = None
    seen: set = set()

    def _free(x, y):
        """Is ``(x, y)`` clear of every existing plan vertex AND of every
        station already minted?  Keyed on the registry's own bucket."""
        k = (int(round(x / SHARED_VERTEX_TOL_M)),
             int(round(y / SHARED_VERTEX_TOL_M)))
        if k in seen:
            return False
        if vtree is not None:
            try:
                from shapely.geometry import Point as _P
                for j in vtree.query(_P(x, y).buffer(SHARED_VERTEX_TOL_M)):
                    px, py = taken[int(j)]
                    if math.hypot(px - x, py - y) <= SHARED_VERTEX_TOL_M:
                        return False
            except Exception:                             # pragma: no cover
                pass
        seen.add(k)
        return True

    for idx, s in enumerate(getattr(layout, "shapes", None) or ()):
        if (getattr(s, "role", None) or "") not in roles:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        try:
            if poly.geom_type != "Polygon":
                continue
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        lines: list = []
        pts_all: list = []
        stations: list = []
        for (ci, axis) in axes:
            for piece in _pieces_inside(axis, poly):
                run = [(x, y) for (x, y) in stations_on_piece(piece,
                                                              spacing_m)
                       if _free(x, y)]
                if len(run) < 2:
                    continue
                # THE §2 DISCIPLINE, APPLIED TO THE SPINE'S OWN RUN.
                # Stations sit at ARC positions on a POLYLINE axis, so
                # the straight chord between two consecutive stations
                # chords off any bend — and where the axis curves around
                # a carved junction the chord cuts straight through it.
                # Measured on this round's second HECA arm: 2 of 40
                # station segments left the apron footprint, 23.7 m,
                # 22.6 m of it through junction -10165.  Same law as the
                # lattice's (owner item 1): a SEGMENT lies inside its
                # apron or it is dropped and the run splits.  The
                # stations themselves are on the axis inside the apron;
                # only the chord between them can offend, so the margin
                # here is the ring itself, not the lattice's stand-off.
                kept = _clip(lines_in=[run], poly=poly)
                for sub in kept:
                    if len(sub) >= 2:
                        lines.append(sub)
                        pts_all.extend(sub)
                        stations.extend((x, y, ci) for (x, y) in sub)
        if not pts_all:
            continue
        entries.append({"shape": s, "shapeID": idx,
                        "points": pts_all, "lines": lines,
                        "stations": stations})
    layout.apron_spine_presolve = entries
    if entries:
        n_pts = sum(len(e["points"]) for e in entries)
        n_lines = sum(len(e["lines"]) for e in entries)
        UI.vprint(1, f"  [apron-spine] {len(entries)} apron(s) crossed by an "
                     f"aircraft taxi axis gained {n_pts} interior centerline "
                     f"station(s) in {n_lines} crossing(s) at "
                     f"{spacing_m:g} m — the spine the apron never cut "
                     f"(RULINGS 2026-08-26b items 3/5)")
    return entries


def station_node_indices(layout, bucket_to_idx):
    """The solver node indices of every station, resolved through the
    canonical registry."""
    cps = layout.canonical_points
    out: set = set()
    for entry in (getattr(layout, "apron_spine_presolve", None) or ()):
        for (x, y) in entry.get("points", ()):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None:
                out.add(i)
    return out


def interpolate_station_values(layout, G, ctx, bucket_to_idx, elev,
                               base_hard):
    """VALUE EVERY STATION FROM THE PHASE-A PROFILE — spec Amendment 2
    ruling 1 (2026-08-27), the law that replaces §1.2's chain membership.

    A station is NOT a chain variable.  Its value is the solved profile
    of its OWN AXIS, interpolated at its arc position: still "the
    profile's own value", but with the chain — and therefore every
    junction, ring and centerline value — byte-identical to the
    stations-OFF arm by construction.

    ONE SOURCE FOR THE PROFILE, and it is the graph's own.
    ``G.centerline_chains[ci]`` is the ARC-ORDERED on-line node list
    ``_build_global_spine`` authored while it strung that centerline —
    the same walk, the same tolerance, the same order.  Re-deriving "the
    nodes on this axis" here would be the census-wrapper defect in
    miniature, and it would drift the moment the walk's eligibility
    rules changed.  Arc positions come from ``grade_graph._project``,
    the projection the walk itself used.

    Called ONCE, in the slot Amendment 1 named: after the phase-A pass
    has solved and frozen the spine, before the membrane/POCS pass — so
    the value is a phase-A OUTPUT and a CONSTANT downstream, never a
    post-hoc rewrite of a solved surface.  ``base_hard`` is stamped here
    because that constancy is the whole ruling.

    A station whose axis contributed NO string (fewer than two on-line
    nodes — the very void this round exists for) has no profile to read.
    It is left FREE at whatever the seeder gave it and COUNTED, never
    silently stamped with a DEM value dressed as a spine value.

    Returns a report dict; nothing is printed here.
    """
    from .grade_graph import _project
    report = {"valued": 0, "no_chain": 0, "clamped": 0,
              "worst_move_m": 0.0, "axes": 0}
    entries = getattr(layout, "apron_spine_presolve", None) or []
    if not entries:
        return report
    cps = getattr(layout, "canonical_points", None)
    cls_list = list(getattr(ctx, "centerlines", None) or ())
    chains = getattr(G, "centerline_chains", None) or {}
    if cps is None or not cls_list:                       # pragma: no cover
        return report
    n = len(elev)
    # Arc position of every chain node, per axis, computed ONCE for the
    # axes that actually carry a station.
    arc_cache: dict = {}

    def _profile(ci):
        prof = arc_cache.get(ci)
        if prof is not None:
            return prof
        cl = cls_list[ci] if 0 <= ci < len(cls_list) else None
        chain = chains.get(ci) or []
        if cl is None or len(chain) < 2:
            arc_cache[ci] = ()
            return ()
        out = []
        for i in chain:
            p = G.pos.get(i)
            if p is None or not (0 <= i < n):             # pragma: no cover
                continue
            a, _d, _f = _project(cl, float(p[0]), float(p[1]))
            out.append((float(a), int(i)))
        out.sort()
        arc_cache[ci] = tuple(out) if len(out) >= 2 else ()
        return arc_cache[ci]

    for entry in entries:
        for (x, y, ci) in entry.get("stations", ()):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is None or not (0 <= i < n):             # pragma: no cover
                continue
            prof = _profile(int(ci))
            if not prof:
                report["no_chain"] += 1
                continue
            cl = cls_list[int(ci)]
            a_st, _d, _f = _project(cl, float(x), float(y))
            # Bracketing chain nodes by arc.  Outside the strung range the
            # profile simply has no data further along, so the axis's own
            # END value is the honest read — recorded as a clamp, not
            # dressed up as an interpolation.
            if a_st <= prof[0][0]:
                v = float(elev[prof[0][1]])
                report["clamped"] += 1
            elif a_st >= prof[-1][0]:
                v = float(elev[prof[-1][1]])
                report["clamped"] += 1
            else:
                v = None
                for (a0, i0), (a1, i1) in zip(prof, prof[1:]):
                    if a0 <= a_st <= a1:
                        span = a1 - a0
                        t = 0.0 if span <= 1e-9 else (a_st - a0) / span
                        v = ((1.0 - t) * float(elev[i0])
                             + t * float(elev[i1]))
                        break
                if v is None:                             # pragma: no cover
                    report["no_chain"] += 1
                    continue
            move = abs(v - float(elev[i]))
            elev[i] = v
            base_hard[i] = True
            report["valued"] += 1
            if move > report["worst_move_m"]:
                report["worst_move_m"] = move
    report["axes"] = len([k for k, v in arc_cache.items() if v])
    return report


def format_station_report(icao: str, report: dict) -> str:
    """The build log's one line — named so a reader can tell an
    interpolated station from a re-solved chain without opening the
    patch."""
    return (f"  [apron-spine] {icao}: {report['valued']} station(s) valued "
            f"by INTERPOLATING the phase-A profile of {report['axes']} "
            f"axis(es) at their arc position (worst move from the seed "
            f"{report['worst_move_m']:.2f} m; {report['clamped']} past the "
            f"strung range took the axis's end value); "
            f"{report['no_chain']} left FREE on an axis that contributed no "
            f"string.  The chain is NOT densified — spec Amendment 2")


def build_apron_spine_station_constraints(layout, bucket_to_idx, ctx):
    """The within-shape law edges a station gains to its apron
    neighbours (spec §1.3) and to the lattice (spec §3.1).

    THE LAW IS THE APRON'S OWN, exactly as the lattice's is: edges come
    out of ``_grade_graph_edges``/``classify_pair`` on a ring that is the
    apron's exterior WITH its lattice points AND its stations appended,
    so every pair is priced by the apron's caps.  This is what makes the
    membrane CONFORM UP to the spine instead of sagging beside it.

    ONLY STATION-TOUCHING PAIRS ARE KEPT.  The apron's ring pairs are
    already stated by its ordinary within-shape entry and the
    lattice/ring pairs by ``apron_lattice.build_apron_lattice_
    constraints``; restating either would hand the POCS sweep two copies
    of one law.  STATION↔STATION pairs are also dropped: consecutive
    stations lie on the axis and are governed by the SPINE's own cap
    through ``G.spine_adj`` — an apron-cap copy of that pair would be a
    second authority on the taxiway profile, which is the one thing this
    round exists to remove.

    Returns ``(sc_entries, station_idx, edge_records)``; ``edge_records``
    extends the sidecar's ``apron_lattice_edges`` publication (one
    family, ``apron_lattice_membrane``) with
    ``{"a", "b", "budget_m", "shapeID", "provenance"}``.
    """
    from .elevation_per_surface.solver_primitives import (
        _grade_graph_edges, _open_ring, _stage_of_shape, _STAGE_KEY)
    from . import config as _cfg
    entries = getattr(layout, "apron_spine_presolve", None) or []
    if not entries or not getattr(_cfg, "APRON_SPINE_STATIONS", False):
        return [], set(), []
    lat_by_shape: dict = {}
    for _e in (getattr(layout, "apron_lattice_presolve", None) or ()):
        lat_by_shape[_e.get("shapeID")] = [
            (float(x), float(y)) for (x, y) in _e.get("points", ())]
    join_r = (LATTICE_JOIN_SPACING_MULT
              * float(getattr(_cfg, "APRON_LATTICE_SPACING_M", 50.0)))
    cps = layout.canonical_points
    sc_out: list = []
    station_idx: set = set()
    edge_records: list = []
    for entry in entries:
        s = entry.get("shape")
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        try:
            ring = _open_ring(list(poly.exterior.coords))
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        lat_pts = lat_by_shape.get(entry.get("shapeID"), [])
        st_pts = [(float(x), float(y)) for (x, y) in entry["points"]]
        coords = list(ring) + list(lat_pts) + st_pts
        idx = [bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
               for (x, y) in coords]
        first_lat = len(ring)
        first_st = first_lat + len(lat_pts)
        ring_set = {i for i in idx[:first_lat] if i is not None}
        lat_set = {i for i in idx[first_lat:first_st]
                   if i is not None} - ring_set
        st_set = ({i for i in idx[first_st:] if i is not None}
                  - ring_set - lat_set)
        if not st_set:
            continue
        station_idx |= st_set
        try:
            edges = _grade_graph_edges(s, coords, idx, ctx)
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        pos = {i: coords[p] for p, i in enumerate(idx) if i is not None}
        keep: list = []
        for (a, b, bud) in edges:
            a_st, b_st = a in st_set, b in st_set
            if a_st == b_st:
                continue            # ring/ring, lattice/x, station/station
            other = b if a_st else a
            if other not in ring_set and other not in lat_set:
                continue
            if other in lat_set:
                pa, pb = pos.get(a), pos.get(b)
                if pa is None or pb is None:              # pragma: no cover
                    continue
                if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) > join_r:
                    continue                              # §3.1 join radius
            keep.append((a, b, bud))
        if not keep:
            continue
        node_list = sorted({a for (a, _b, _c) in keep}
                           | {b for (_a, b, _c) in keep})
        sc_out.append({"nodes": node_list, "edges": keep, "flat": False,
                       "flat_pairs": (), "area": 0.0,
                       "role": getattr(s, "role", "") or "apron",
                       _STAGE_KEY: _stage_of_shape(s),
                       "ref": "apron_spine_station"})
        for (a, b, bud) in keep:
            pa, pb = pos.get(a), pos.get(b)
            if pa is None or pb is None:                  # pragma: no cover
                continue
            try:
                la = layout.m_to_ll(pa[0], pa[1])
                lb = layout.m_to_ll(pb[0], pb[1])
            except _GEOM_EXC:                             # pragma: no cover
                continue
            edge_records.append({
                "a": [round(float(la[0]), 11), round(float(la[1]), 11)],
                "b": [round(float(lb[0]), 11), round(float(lb[1]), 11)],
                "budget_m": round(float(bud), 6),
                "shapeID": entry.get("shapeID"),
                "provenance": "apron_spine_station"})
    return sc_out, station_idx, edge_records
