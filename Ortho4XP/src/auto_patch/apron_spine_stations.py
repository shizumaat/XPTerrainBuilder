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


# ── §A: THE HOST FAMILIES (spec lemd-rim-and-stations §A.1) ──────────
#
# A station whose foot lands on a ring EDGE is never a free node.  What
# happens instead is decided by the HOST EDGE'S ROLE, max-tier over
# every host of that (shared) boundary:
#
#   TAXIWAY family — the station STANDS DOWN.  That ground already
#   carries the anchored surface the station would re-state, and
#   round-3 Amendment 2's gate 2a (taxiway-family byte-identity against
#   the stations-OFF arm) is then preserved BY CONSTRUCTION.
#   APRON family — the station WELDS: one node, inserted into every
#   host ring at the edge lerp, and the STATION VALUE WINS.
#
# ``_STATION_STANDDOWN_ROLES`` is the taxi family verbatim (crown's
# ``_TAXI_FAMILY``: junction / primary_parallel / secondary_parallel /
# stub / cross_connector).  Any OTHER role — runway, service, boundary,
# a plate — is neither: the station stands down there too, because §A.1's
# first sentence is unconditional ("never minted as a free node") and
# welding into a family this round has not measured would be a law
# invented at a call site.  Counted separately, never silently.
def _station_host_families():
    """``(standdown, weld, pad)`` — the taxiway family, the apron family,
    and the PAD family.

    A PAD RING IS A STAND-DOWN HOST FOR EVERY WELD (spec Amendment 1 §1,
    2026-08-28): a building pad is ONE FLAT VALUE by definition — the
    pads-as-band-variables §1.1 invariant — so the inserter never puts a
    foreign-valued node into one.  It was already covered by the
    unconditional "never minted as a free node" rule; naming it makes
    the count legible and pins the ruling where a reader looks for it.
    """
    from .crown import _TAXI_FAMILY
    from .layout import ROLE_APRON, PAD_WELD_STANDDOWN_ROLES
    return (frozenset(_TAXI_FAMILY), frozenset({ROLE_APRON}),
            PAD_WELD_STANDDOWN_ROLES)


def _ring_edge_host(poly, x, y, tol):
    """``(i, t, perp)`` for the CURRENT exterior ring edge of ``poly``
    that hosts ``(x, y)`` strictly inside and endpoint-clear, else
    ``None``.

    Re-derived from the LIVE polygon on every call, never cached: a weld
    into one host splits the very edge a later station may land on, and
    an index taken before that split would insert at the wrong place.
    """
    try:
        ring = list(poly.exterior.coords)
    except _GEOM_EXC:                                     # pragma: no cover
        return None
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    n = len(ring)
    if n < 3:
        return None
    best = None
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        L = math.sqrt(L2)
        t = ((x - ax) * dx + (y - ay) * dy) / L2
        if t <= 0.0 or t >= 1.0:
            continue
        if t * L < tol or (1.0 - t) * L < tol:
            continue                    # coincident with an endpoint
        perp = abs((x - ax) * dy - (y - ay) * dx) / L
        if perp > tol:
            continue
        if best is None or perp < best[2]:
            best = (i, t, perp)
    return best


def _weld_station_into_ring(shape, x, y, tol):
    """Insert ``(x, y)`` into ``shape``'s exterior ring at the hosting
    edge — the ``crown._weld_terminus_into_rings`` case-(b) transplant:
    an index-aligned ring + ``node_altitudes`` rebuild that keeps the
    interior rings (an exterior-only rebuild fills the shape's holes).

    Returns True when a vertex was inserted.  The VALUE is not decided
    here: a welded station and the ring vertex are ONE canonical node, so
    the station's phase-A constant is what the solve carries there
    (round-3 Amendment 1) — the ring's own lerp is only what the inserted
    vertex inherits until then.
    """
    from shapely.geometry import Polygon as _Poly
    from .conformance import _vertex_alts
    poly = getattr(shape, "polygon", None)
    if poly is None or getattr(poly, "is_empty", True):   # pragma: no cover
        return False
    hit = _ring_edge_host(poly, x, y, tol)
    if hit is None:                                       # pragma: no cover
        return False
    i, t, _perp = hit
    ring = list(poly.exterior.coords)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    n = len(ring)
    # ONE reading of "this shape's per-vertex altitudes": the
    # conformance weld's own, which normalises the closing repeat and
    # the sloped-quad model.  A second spelling here is the
    # census-wrapper defect in miniature.
    alts = _vertex_alts(shape, n)
    lerp = None
    if alts is not None:
        try:
            lerp = (float(alts[i])
                    + t * (float(alts[(i + 1) % n]) - float(alts[i])))
        except (TypeError, ValueError):                   # pragma: no cover
            lerp = None
    new_ring = list(ring[:i + 1]) + [(float(x), float(y))] \
        + list(ring[i + 1:])
    try:
        new_poly = _Poly(new_ring, [list(r.coords)
                                    for r in poly.interiors])
        if new_poly.is_empty or not new_poly.is_valid:
            return False
    except _GEOM_EXC:                                     # pragma: no cover
        return False
    shape.polygon = new_poly
    # A shape emitted with a single ``altitude`` is FLAT: the inserted
    # vertex inherits it and the shape stays flat (crown's own rule).
    _flat_single = (getattr(shape, "node_altitudes", None) is None
                    and getattr(shape, "altitude_high", None) is None
                    and getattr(shape, "altitude_low", None) is None
                    and getattr(shape, "altitude", None) is not None)
    if lerp is not None and not _flat_single:
        new_alts = list(alts[:i + 1]) + [lerp] + list(alts[i + 1:])
        shape.node_altitudes = new_alts + [new_alts[0]]
        shape.altitude_high = None
        shape.altitude_low = None
    return True


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

    # ── §A: THE EDGE TEST ``_free`` NEVER HAD ────────────────────────
    # ``_free`` guards against plan VERTICES only, and an aircraft axis
    # is routinely COLLINEAR with the apron slice boundaries it crosses:
    # 144 stations across LEMD/HECA/SPJC/CYXY landed ON a shared ring
    # edge as unwelded T-vertices, worst value tear 0.907 m.  A
    # value-only patch cannot fix that — two near-collinear constrained
    # segments ~2 cm apart are the documented mm-jitter segment-recovery
    # killer — so the geometry is what must become ONE.
    #
    # The tree is a CANDIDATE FILTER over shape exteriors, nothing more:
    # the hosting edge itself is re-derived from the LIVE ring on every
    # query (``_ring_edge_host``), because a weld splits the very edge a
    # later station may land on.
    _edge_on = bool(getattr(_cfg, "STATION_EDGE_WELD", False))
    _standdown_roles, _weld_roles, _pad_roles = _station_host_families()
    _host_shapes: list = []
    _host_tree = None
    if _edge_on:
        try:
            from shapely.geometry import LineString as _LS
            from shapely.strtree import STRtree as _T2
            for s in (getattr(layout, "shapes", None) or ()):
                poly = getattr(s, "polygon", None)
                if poly is None or getattr(poly, "is_empty", True):
                    continue
                if poly.geom_type != "Polygon":
                    continue
                _host_shapes.append(s)
            _host_tree = (_T2([_LS(sh.polygon.exterior.coords)
                               for sh in _host_shapes])
                          if _host_shapes else None)
        except Exception:                                 # pragma: no cover
            _host_tree = None
    _edge_report = {"welded": 0, "weld_rings": 0,
                    "stood_down_taxi": 0, "stood_down_pad": 0,
                    "stood_down_other": 0, "other_roles": {}}
    # THE WELD IS AN INVISIBLE ANCHOR, and both decimators must be told
    # (crown's own precedent, ``_crown_spine_weld_xy``).  A welded
    # station sits ON its host edge, so it is exactly the 3D-redundant
    # vertex ``emit_decimate.decimate_emit_nodes`` and ``to_osm``'s own
    # sweep remove — and their unanimity vote is taken over SHAPES, while
    # the thing that needs the vertex is an emitted FEATURE way.  Nothing
    # in either vote can see that dropping it re-opens the unwelded
    # T-vertex the weld exists to close (the SPLP -13/-77 precedent,
    # reproduced here at CYXY: the insert landed, both decimators dropped
    # it, and the sweep still read 6 of 6 on-edge).
    _weld_xy: list = []

    def _edge_hosts(x, y):
        """Every shape whose CURRENT exterior ring hosts ``(x, y)`` on an
        edge, strictly interior and endpoint-clear."""
        if _host_tree is None:
            return []
        from shapely.geometry import Point as _P3
        out = []
        try:
            cand = _host_tree.query(
                _P3(x, y).buffer(SHARED_VERTEX_TOL_M * 4.0))
        except Exception:                                 # pragma: no cover
            return []
        for j in cand:
            sh = _host_shapes[int(j)]
            if _ring_edge_host(sh.polygon, x, y,
                               SHARED_VERTEX_TOL_M) is not None:
                out.append(sh)
        return out

    def _admit(x, y):
        """Is this candidate minted?  ``_free`` decides vertex
        coincidence exactly as before; §A decides the EDGE case, and
        performs the weld as its side effect."""
        if not _free(x, y):
            return False
        if not _edge_on:
            return True
        hosts = _edge_hosts(x, y)
        if not hosts:
            return True                 # a genuinely free interior node
        roles = {(getattr(h, "role", None) or "") for h in hosts}
        if roles & _pad_roles:
            # Amendment 1 §1: a pad is one flat value; never a weld host.
            _edge_report["stood_down_pad"] += 1
            return False
        if roles & _standdown_roles:
            _edge_report["stood_down_taxi"] += 1
            return False
        if not roles <= _weld_roles:
            _edge_report["stood_down_other"] += 1
            for r in sorted(roles - _weld_roles):
                _edge_report["other_roles"][r] = (
                    _edge_report["other_roles"].get(r, 0) + 1)
            return False
        n_welded = 0
        for h in hosts:
            if _weld_station_into_ring(h, x, y, SHARED_VERTEX_TOL_M):
                n_welded += 1
        if not n_welded:                                  # pragma: no cover
            _edge_report["stood_down_other"] += 1
            return False
        _edge_report["welded"] += 1
        _edge_report["weld_rings"] += n_welded
        _weld_xy.append((float(x), float(y)))
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
                       if _admit(x, y)]
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
    layout.apron_spine_edge_report = dict(_edge_report)
    layout._apron_station_weld_xy = list(_weld_xy)
    if _edge_on and any(_edge_report[k] for k in
                        ("welded", "stood_down_taxi", "stood_down_pad",
                         "stood_down_other")):
        _other = ("" if not _edge_report["other_roles"] else
                  " (" + ", ".join(f"{k}×{v}" for k, v in
                                   sorted(_edge_report["other_roles"].items()))
                  + ")")
        UI.vprint(1,
            f"  [apron-spine] ON-EDGE candidates: "
            f"{_edge_report['welded']} WELDED as T-vertices into "
            f"{_edge_report['weld_rings']} apron-family ring(s) (one node, "
            f"the station value wins); "
            f"{_edge_report['stood_down_taxi']} STOOD DOWN on a "
            f"taxiway-family host (that ground already carries the anchored "
            f"surface); {_edge_report['stood_down_pad']} on a building-PAD "
            f"host (one flat value by definition, Amendment 1 §1); "
            f"{_edge_report['stood_down_other']} stood down on "
            f"another family{_other} — spec lemd-rim-and-stations §A")
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
              "worst_move_m": 0.0, "axes": 0, "from_endpoints": 0,
              "unstrung_axes": 0}
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
        if cl is None:                                    # pragma: no cover
            arc_cache[ci] = ()
            return ()
        chain = chains.get(ci) or []
        if len(chain) < 2:
            return _unstrung(ci, cl)
        out = []
        for i in chain:
            p = G.pos.get(i)
            if p is None or not (0 <= i < n):             # pragma: no cover
                continue
            a, _d, _f = _project(cl, float(p[0]), float(p[1]))
            out.append((float(a), int(i)))
        out.sort()
        if len(out) >= 2:
            arc_cache[ci] = tuple(out)
            return arc_cache[ci]
        return _unstrung(ci, cl)                          # pragma: no cover

    def _unstrung(ci, cl):
        # ── THE UNSTRUNG AXIS (spec Amendment 3 ruling 1) ─────────────
        # Fewer than two on-line nodes means this axis contributed NO
        # string, and that is not a rare corner: it is exactly the empty
        # apron this round exists for.  Measured at HECA (A5): 20 of 62
        # stations sat on such an axis and got no value at all, the
        # crossing over dip apron -10659 among them, so the coupling was
        # inert at the very site the owner named.
        #
        # The value source is then the ROUTE'S OWN ENDPOINT VALUES: the
        # solved pavement/junction nodes the piece runs between, with the
        # station on the straight plane between them.  That is the
        # DEM-LAST ruling's own construction for an unanchored span
        # (RULINGS 2026-08-25: "the pavement surface between anchors is
        # the straight-plane/taut interpolation") — no new authority, and
        # emphatically not a DEM read.
        #
        # "The node at this end" is asked with the engine's own
        # centerline-contact radius, ``grade_law.RUNWAY_JOIN_NEAR_M`` —
        # the same question ``_runway_anchors`` asks of a join contact,
        # the same constant, no second proximity notion.
        report["unstrung_axes"] += 1
        ends = _axis_endpoint_values(cl)
        arc_cache[ci] = ends
        return ends

    _node_tree = [None]           # built once, and only if an axis needs it

    def _nearest_valued(x, y, radius):
        """The nearest graph node to ``(x, y)`` carrying a solved value,
        within ``radius``; ``None`` if the end anchors nothing."""
        import math as _m
        if _node_tree[0] is None:
            items = [(i, p) for (i, p) in G.pos.items() if 0 <= i < n]
            try:
                from shapely.geometry import Point as _P
                from shapely.strtree import STRtree as _T
                _node_tree[0] = (items,
                                 _T([_P(p[0], p[1]) for (_i, p) in items]))
            except Exception:                             # pragma: no cover
                _node_tree[0] = (items, None)
        items, tree = _node_tree[0]
        best = None
        if tree is not None:
            from shapely.geometry import Point as _P2
            cand = tree.query(_P2(x, y).buffer(float(radius)))
            it = (items[int(k)] for k in cand)
        else:                                             # pragma: no cover
            it = iter(items)
        for (i, p) in it:
            d = _m.hypot(p[0] - x, p[1] - y)
            if d > float(radius):
                continue
            v = float(elev[i])
            if v != v:                                    # pragma: no cover
                continue
            if best is None or d < best[0]:
                best = (d, i)
        return None if best is None else best[1]

    def _axis_endpoint_values(cl):
        """``((arc, node), ...)`` for the ends of ``cl`` that anchor a
        solved node — 2, 1 or 0 of them."""
        from .grade_law import RUNWAY_JOIN_NEAR_M as _NEAR_M
        pts = list(cl.pts)
        if len(pts) < 2:                                  # pragma: no cover
            return ()
        arcs = cl.arc()
        out = []
        for (px, py), a in ((pts[0], arcs[0]), (pts[-1], arcs[-1])):
            i = _nearest_valued(float(px), float(py), _NEAR_M)
            if i is not None:
                out.append((float(a), int(i)))
        if len(out) == 2 and out[0][1] == out[1][1]:
            out = out[:1]          # both ends found the same node
        return tuple(out)

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
            if len(chains.get(int(ci)) or ()) < 2:
                report["from_endpoints"] += 1
            # Bracketing profile points by arc.  Outside the range the
            # profile simply has no data further along, so the nearest
            # END value is the honest read — recorded as a clamp, not
            # dressed up as an interpolation.  A profile of ONE point is
            # the Amendment 3 single-valued-endpoint case and clamps for
            # exactly the same reason.
            if len(prof) == 1:
                v = float(elev[prof[0][1]])
                report["clamped"] += 1
            elif a_st <= prof[0][0]:
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
            f"{report['worst_move_m']:.2f} m; {report['clamped']} clamped to "
            f"an end value); {report['from_endpoints']} of them on "
            f"{report['unstrung_axes']} UNSTRUNG axis(es), valued from the "
            f"route's own endpoint anchors (the DEM-last straight plane, "
            f"spec Amendment 3); {report['no_chain']} left FREE where no "
            f"end anchors a solved node.  The chain is NOT densified — "
            f"spec Amendment 2")


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
