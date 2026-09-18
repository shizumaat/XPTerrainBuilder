"""A BRIDGE STATES THE CROSSING (spec §34 (5); Fable 2026-09-13i;
RULINGS 2026-09-13i item 1, 2026-09-13q item 3) — lane ``v2rampwalk``.

Its own module because ``planar/structures.py`` and
``planar/structure_approach.py`` both stand at their 1,000-line budget.

ARMED at round 2 (RULINGS 2026-09-13ai).  Round 1 measured the seeding
alone as a cockpit REGRESSION — LEMD CRITICAL VISUAL 3 → 10, seven of the
ten rows at 40.46100, −3.54455 (ledger ``f4cf494dab92``) — because the
portal RIM took ``DEM(mouth)`` = 570.0, the road's ground down in the
cutting, against a taxi surface solving ~573.5 above it: a 3.52 m
abutment cliff and four ``strip_seam_tear`` rows that were zero.

THE CURE, ruled 13ai and built here: the rim under a deck takes the taxi
cell's SOLVED surface, never ``DEM(mouth)`` — and the way to say that in
the law this repo already has is GEOMETRIC.  The bore is clipped to the
deck ribbon SHRUNK by the rim stand-off (``wall_gap_m +
wall_band_width_m``) and one identity step, so the mouth stands inside
the taxi cell and the corridor's END CAP — the rim — lands ON the cell,
where the structure's own cut makes it the cell's hole-ring vertex.  One
node, one value (09-01g): the rim IS the taxi surface there, and
``constraints/structures.rim_level``'s one-way ``frontage_level`` row
(RULINGS 2026-09-10an — the rim rises to the pavement it sits in and
never pulls it down) governs the rest.  ``_rim_rows`` skips the DEM pin
on a vertex the governed ground shares, so ``DEM(mouth)`` never reaches
it.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Polygon

from ..classify.roles import TAXI_FAMILY
from ..law import Law
from ..law.tables import zone2_half_width_m
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from ..model.structures import UNDERPASS_NOTE as _UNDERPASS_NOTE
from shapely.geometry import Point
from shapely.strtree import STRtree

from .structure_approach import carriageway_width_m, is_bridge, is_tunnel_way, unit
from .structure_service import airside_cut_roles

_MITRE = dict(join_style="mitre", mitre_limit=2.0)

__all__ = ["underpass_bores", "approach_along", "is_aeroway_bridge",
           "strip_half_width_m", "UNDERPASS_TAG", "UNDERPASS_NOTE"]

#: §34 (5) (b) (Fable 2026-09-15; RULINGS 2026-09-15h): the RUNWAY family
#: for the strip derivation — the same two role names ``planar/zones``
#: keys its own zone regions by, so the covered extent and the graded
#: strip are ONE derivation and cannot drift.
_RUNWAY_FAMILY = ("runway", "runway_crossing")


def strip_half_width_m(law: Law, cell) -> float:
    """§34 (5) (b) THE COVERED EXTENT INCLUDES THE GRADED STRIP (Fable
    2026-09-15; RULINGS 2026-09-15h) — how far beyond ``cell``'s own kerb
    the ground it passes over is GRADED, in metres.

    ONE derivation with ``planar/zones.zone_regions``: the zone-2 half
    width for the cell's class (``zones.toml
    adjacent_ground.{runway,taxi}.half_width_m``, keyed by code NUMBER for
    the runway family and by code LETTER for the taxi family), falling
    back to the zone-1 LIP width where the class declares no strip — the
    ruling's own words, "the zone-1 width where no strip is declared".

    The strip is measured from the PAVEMENT EDGE, which is exactly what
    :func:`_deck_cell`'s per-station offsets are, so it adds to them."""
    lip = float(law.tables.zones.adjacent_ground.lip_width_m)
    if cell.role in _RUNWAY_FAMILY:
        role = "runway"
    elif cell.role in TAXI_FAMILY:
        role = "junction"
    else:
        # no zone band is built around it at all (``planar/zones``
        # groups the RUNWAY and TAXI families and nothing else), so the
        # strip it declares is the LIP the ruling names.
        return lip
    hw = zone2_half_width_m(law, role, cell.code_number, cell.code_letter)
    return float(hw) if hw and hw > 0.0 else lip

#: Re-exported from the RECORD (``model/structures``), where both the
#: planar stage and the constraint generator may read it.
UNDERPASS_NOTE = _UNDERPASS_NOTE


#: §34 (5) NARROWED (Fable 2026-09-13; RULINGS 2026-09-13bm (i)): the only
#: aeroways a TAXIING AIRCRAFT uses.  A ``jet_bridge`` is a passenger
#: walkway on stilts and a ``parking_position`` is a painted point; neither
#: is a structure an aircraft crosses, and neither states a cutting under
#: what it spans.
TAXIED_AEROWAYS: frozenset[str] = frozenset(("taxiway", "runway", "apron"))


def is_aeroway_bridge(tags: _t.Mapping[str, str]) -> bool:
    """AN AEROWAY A TAXIING AIRCRAFT USES, tagged ``bridge`` (not ``no``)
    — spec §34 (5) as NARROWED (Fable 2026-09-13; RULINGS 2026-09-13bm
    item 1).

    ``airport/deck_signature.is_bridge_way`` — the predicate every deck
    pass uses — requires ``highway`` or ``railway``, so an AEROWAY bridge
    is invisible to all of it: LEMD's taxiway F-6 (way −1230,
    ``aeroway=taxiway bridge=yes layer=1``) and KCLT's taxiway U (−1560)
    mint no deck and seed nothing, which is exactly the gap §34 (5)
    closes.  The predicate stays LOCAL: widening the shared one would mint
    a terrain deck at ROAD level from every aeroway bridge across every
    corridor, where the taxi surface over an underpass is the pavement
    cell's own (``pavement_deck_intervals``, 2026-09-06f) under taxi
    law — which is what "level across the cutting under taxi law" means.

    THE NARROWING, measured at SPJC (owner 1.0.327, 13bi): the first
    reading was ANY ``aeroway=*`` with ``bridge``, and SPJC's OSM carries
    63 ways ``{aeroway=jet_bridge, bridge=yes, highway=footway,
    layer=1}`` — the passenger jetways — each of which passed
    ``underpass_min_layer`` and bored every apron service road beneath it:
    19 underpasses, 86 roads bored, 11 of 18 tunnel records.  A jetway
    states nothing about the ground: the apron under it is apron.  So the
    aeroway must be one an aircraft ROLLS ON (``TAXIED_AEROWAYS``), and a
    way tagged ``highway=footway`` is refused whatever its aeroway says —
    a footway is not a crossing an aircraft makes.
    """
    b = tags.get("bridge")
    if not b or b == "no":
        return False
    if str(tags.get("highway", "")).strip() == "footway":
        return False
    return str(tags.get("aeroway", "")).strip() in TAXIED_AEROWAYS

#: The tag a synthesised UNDERPASS bore carries, so the reports and the
#: approach walk can tell it from a mapped ``tunnel=yes`` way.
UNDERPASS_TAG = "o4_underpass"


def aeroway_decks(airport: Airport, law: Law) -> list[OsmWay]:
    """THE DECK READ (§34 (5)) — THE ONE DERIVATION: every taxied aeroway
    tagged ``bridge`` standing at or above ``[tunnel]
    underpass_min_layer``.

    It is a function because §45 (1) (a) asks the SAME question — "does a
    deck state this crossing?" — and asked it with a verbatim copy of
    this loop until the owner's 2026-09-15 addendum (RULINGS 15al/15an/
    15ap).  Two copies of a deck read is how one site gets a rule the
    other never gets: §34 (12) (4)'s below-grade witness (the DEM cut
    under the span, or the way beneath tagged ``tunnel`` / ``layer <=
    -1`` in a schema-current feed) lands HERE when lane ``v2vmmcshore``
    r6 implements it, and the channel pass inherits it by calling this."""
    tn = law.tables.structures.tunnel
    out: list[OsmWay] = []
    for w in airport.osm_ways:
        tags = getattr(w, "tags", None) or {}
        if not is_aeroway_bridge(tags) or len(w.points) < 2:
            continue
        try:
            layer = int(float(str(tags.get("layer", "0")).strip()))
        except ValueError:
            layer = 0
        if layer < tn.underpass_min_layer:
            continue
        out.append(w)
    return out


def underpass_bores(airport: Airport, law: Law, cells, polys
                    ) -> tuple[list[OsmWay], dict[int, LineString], list[str]]:
    """A BRIDGE STATES THE CROSSING (spec §34 (5); Fable 2026-09-13i,
    RULINGS 2026-09-13i item 1 and 2026-09-13q item 3).

    An ``aeroway=*`` way tagged ``bridge=yes`` with ``layer >=
    [tunnel] underpass_min_layer`` is a taxiway ON A STRUCTURE: whatever
    passes under it is in a CUTTING, and OSM says so by the bridge alone —
    the roads beneath carry no ``tunnel`` tag anywhere in either measured
    case (LEMD F-6, way −1230 over service roads −5820/−5821, a 7.5 m DEM
    cutting the taxi surface bathtubs 2.66 m at 5.3 % across; KCLT taxiway
    U, way −1560 over untagged tertiary roads, headroom 2.3–2.5 m).  With
    no bore seeded the terrain simply drapes the cutting and the taxiway
    follows it down.

    So the crossing is stated: the road's own centreline CLIPPED to the
    aeroway's deck ribbon becomes a bore (``tunnel=yes``), and everything
    downstream is the tunnel model already built — the mouths where the
    road leaves the ribbon (§29's on-field gate applies to them like any
    other), the ramps out of them along the road (§34 (1)/(2)), the rims,
    and the aeroway itself as the DECK across the corridor (it is already
    a ``bridge`` way, so ``deck_intervals`` mints it; where a taxi-family
    cell spans the corridor ``pavement_deck_intervals`` keeps that cell's
    own taxi law, 2026-09-06f — "level across the cutting under taxi law").

    The ribbon's half-width is the PAVEMENT the aeroway traces
    (``pavement_half_widths``, 2026-09-06b (2)) — a taxiway bridge carries
    no ``width`` tag and its lanes fallback (7 m) is a third of a real
    taxiway — falling back to the carriageway width where no pavement
    traces it.  Returns the synthetic ways, each one's PARENT road line
    (the ramp's route), and the notes for the structures line."""
    tn = law.tables.structures.tunnel
    out: list[OsmWay] = []
    parents: dict[int, LineString] = {}
    notes: list[str] = []
    decks = aeroway_decks(airport, law)
    if not decks:
        return out, parents, notes
    # §34 (5) (b) AMENDED / §34 (12) (3) AMENDED (owner RULINGS
    # 2026-09-17x (4)): the protected AIRSIDE set the covered extent
    # stops at — §34 (12) (3)'s own derivation, imported, never
    # re-spelled (the census-wrapper precedent).
    cut_roles = airside_cut_roles(law)
    roads = [w for w in airport.osm_ways
             if (getattr(w, "tags", None) or {}).get("highway") and len(w.points) >= 2
             and not is_tunnel_way(w.tags, tn.admitted_values) and not is_bridge(w)]
    for w in decks:
        ln = LineString(w.points)
        half = carriageway_width_m(w.tags, law) / 2.0
        step = max(law.tables.emit.identity.min_distinct_spacing_m, 1.0)
        ss = [min(s, ln.length) for s in _frange(0.0, ln.length, step)]
        axis_fn = (lambda s, _ln=ln: (_ln.interpolate(min(s, _ln.length)).x,
                                      _ln.interpolate(min(s, _ln.length)).y))
        # §34 (5) NARROWED (RULINGS 2026-09-13bm (i)): the cell may only
        # widen the deck up to DECK_CELL_MAX_RATIO × the carriageway.
        # §34 (5) (a) (RULINGS 2026-09-14bp item 1): ONE derivation — the
        # deck CELL's own footprint — read here and by ``_deck_half_width``.
        grid0 = max(law.tables.emit.identity.min_distinct_spacing_m, 0.1)
        stopped: dict[str, int] = {}
        offs, cell_half, n_read, n_refused = _deck_cell(
            axis_fn, ss, cells, polys, half,
            DECK_CELL_MAX_RATIO * 2.0 * half, law=law,
            cut_roles=cut_roles, grid=grid0, stopped=stopped)
        half = max(half, cell_half)
        # THE MOUTH STANDS INSIDE THE DECK (spec §34 (5) as amended,
        # RULINGS 2026-09-13ai): the clip ribbon is the deck's own
        # half-width LESS the rim stand-off and one identity step, so the
        # corridor's end cap — the rim — lands ON the taxi cell and shares
        # its hole-ring vertex instead of standing 1.6 m outside it at
        # ``DEM(mouth)``, the road's ground down in the cutting.
        rim_off = tn.wall_gap_m + tn.wall_band_width_m
        grid = max(law.tables.emit.identity.min_distinct_spacing_m, 0.1)
        half_clip = max(grid, half - rim_off - grid)
        # §34 (5) (a) THE UNDERPASS CLIP IS THE DECK CELL'S (Fable
        # 2026-09-14; RULINGS 2026-09-14bp item 1).  The ribbon was
        # SYMMETRIC about the aeroway's OSM centreline, and a centreline is
        # not a pavement's middle: LEMD F-6's way -1230 runs 0.25 m from
        # ``pav157``'s NORTH kerb and 16.3 m from its south edge, so a
        # 5.6 m half-ribbon put the south mouth 10.0 m INSIDE the 16.6 m
        # taxiway - the trench floor 5.48 m under the pavement with the
        # grade break inside it.  The clip is the deck CELL's own footprint
        # ACROSS THE AXIS - its two kerbs per station - eroded by the rim
        # stand-off and one identity step (the room 13ai's cure needs, so
        # the end cap still lands ON the cell).  The centreline ribbon
        # stands only where no cell states the deck.
        #
        # ACROSS THE AXIS, not the cell's whole plan: measured on the first
        # arm, ``pav157`` is a 200,195 m2 junction BLOB and clipping to it
        # bored 7 roads instead of 2 (bores 70 -> 75, tunnels 50 -> 53).
        # The cell states where the crossing is COVERED, which is the
        # footprint between its kerbs at each station of the way.
        ribbon, from_cell = _cell_ribbon(axis_fn, ss, offs, rim_off + grid, grid)
        if ribbon is None:
            ribbon = ln.buffer(half_clip, **_MITRE)
        n = 0
        for r in roads:
            piece = LineString(r.points).intersection(ribbon)
            for g in getattr(piece, "geoms", [piece]):
                if g.geom_type != "LineString" or g.length < tn.underpass_min_span_m:
                    continue
                pts = tuple((float(x), float(y)) for x, y in g.coords)
                sw = OsmWay(r.id, r.kind, pts, False,
                            {**dict(r.tags), "tunnel": tn.admitted_values[0],
                             UNDERPASS_TAG: str(w.id)})
                out.append(sw)
                parents[id(sw)] = LineString(r.points)
                n += 1
        notes.append(f"underpass {w.tags.get('aeroway')} {w.id} (layer {w.tags.get('layer')}, "
                     f"deck half-width {half:.1f} m, clip "
                     + (f"the deck CELL's footprint across the axis PLUS its graded "
                        f"strip (§34 (5) (b)) eroded by "
                        f"{rim_off + grid:.1f} m ({ribbon.area:.0f} m2 over {n_read} "
                        f"station(s), §34 (5) (a))" if from_cell
                        else f"the centreline ribbon {half_clip:.1f} m (no cell states "
                             f"the deck, §34 (5) (a))")
                     + f", cell {n_read} read / {n_refused} refused over "
                     f"{DECK_CELL_MAX_RATIO:g}x carriageway"
                     + (", the strip STOPPED at a neighbour's pavement "
                        "(§34 (12) (3) as amended, owner 17x (4)): "
                        + ", ".join(f"{r} x{k}" for r, k in
                                    sorted(stopped.items()))
                        if stopped else "")
                     + f"): {n} road(s) bored")
    return out, parents, notes


def _frange(a: float, b: float, step: float) -> list[float]:
    out, s = [], a
    while s < b - 1e-9:
        out.append(s)
        s += step
    out.append(b)
    return out


def approach_along(parent: LineString, mouth: XY, inward: XY,
                   reach_m: float) -> list[XY]:
    """THE RAMP'S ROUTE OUT OF AN UNDERPASS MOUTH (spec §34 (1)/(5)): the
    PARENT road's own centreline, walked outward from the mouth (a mouth
    the bore's clip made stands mid-way along the road, at no mapped node,
    so ``approach``'s node index finds nothing there and falls back to a
    straight extension).  Extended straight past the road's end, exactly
    as ``approach`` does."""
    s0 = parent.project(__import__("shapely").geometry.Point(mouth))
    out_dir = (-inward[0], -inward[1])
    cs = list(parent.coords)
    fwd = None
    if len(cs) >= 2:
        a = parent.interpolate(min(parent.length, s0 + 1.0))
        d = unit(mouth, (a.x, a.y))
        fwd = (d[0] * out_dir[0] + d[1] * out_dir[1]) >= 0.0
    path: list[XY] = [tuple(mouth)]
    if fwd is None:
        return path
    rng = [s for s in _stations(parent, s0, fwd) ]
    for s in rng:
        p = parent.interpolate(s)
        q = (p.x, p.y)
        if math.hypot(q[0] - path[-1][0], q[1] - path[-1][1]) < 1e-6:
            continue
        path.append(q)
        if LineString(path).length >= reach_m:
            return path
    ln = LineString(path) if len(path) >= 2 else None
    if ln is None:
        path.append((mouth[0] + out_dir[0] * (reach_m + 1.0),
                     mouth[1] + out_dir[1] * (reach_m + 1.0)))
        return path
    if ln.length < reach_m:
        a = unit(path[-2], path[-1])
        path.append((path[-1][0] + a[0] * (reach_m - ln.length + 1.0),
                     path[-1][1] + a[1] * (reach_m - ln.length + 1.0)))
    return path


def _stations(parent: LineString, s0: float, fwd: bool) -> list[float]:
    """The parent's own vertex stations beyond ``s0``, in walk order."""
    ss = []
    acc = 0.0
    cs = list(parent.coords)
    for i in range(1, len(cs)):
        acc += math.hypot(cs[i][0] - cs[i - 1][0], cs[i][1] - cs[i - 1][1])
        ss.append(acc)
    ss = [0.0] + ss
    return [s for s in ss if s > s0 + 1e-6] if fwd else \
           [s for s in reversed(ss) if s < s0 - 1e-6]


#: §34 (5) NARROWED (RULINGS 2026-09-13bm (i)): a pavement cell may state
#: the deck only while it is plausibly the way's own pavement.  A cell
#: whose HALF-WIDTH exceeds this multiple of the way's own CARRIAGEWAY
#: WIDTH is a BLOB the axis merely stands in — SPJC's 738,901 m² ``pav40``
#: apron read 49–127 m of "deck" off a 4 m jetway — and is refused; the
#: carriageway is then the deck, which is what the way itself says.
#:
#: THE READING IS THE RULING'S, MEASURED (lane v2spjc, dry
#: ``--stage structures`` arms): half-width vs 4x the carriageway (28 m
#: half off a 7 m lanes fallback) refuses all 19 of SPJC's jetway blobs
#: (29.9-127.1 m) and keeps KCLT taxiway U's real 18.0 m deck.  The
#: tighter paraphrase — cell WIDTH vs 4x the carriageway, a 14 m half —
#: also refuses SPJC but cut taxiway U to 12.1 m and lost one of its two
#: mouths (``tunnel:-13665+-13664@1`` at 35.2015651, -80.9404036), which
#: is a real taxiway bridge read as a blob.
DECK_CELL_MAX_RATIO = 4.0


def _deck_half_width(axis_fn, ss, cells, polys, half_default: float,
                     max_half: float | None = None) -> tuple[float, int, int]:
    """The half-width alone of :func:`_deck_cell` — ONE derivation (spec
    §34 (5) (a)), kept as a name because the twins and the reports read
    it.

    The DECK's width is the PAVEMENT's (§34 (5) (a)); the graded strip
    §34 (5) (b) adds is carried in the per-station offsets alone and
    never widens the deck, so this reader passes no ``law``."""
    _offs, half, n_read, n_refused = _deck_cell(axis_fn, ss, cells, polys,
                                                half_default, max_half)
    return half, n_read, n_refused


def _far_boundary(p, nv, sgn: float, poly, reach: float = 400.0) -> float | None:
    """The distance from ``p`` to the FARTHEST point at which the outward
    normal ray leaves ``poly`` — the far kerb of the cell the ray is
    standing in.  ``None`` where the ray never meets its boundary."""
    ray = LineString([p, (p[0] + nv[0] * sgn * reach, p[1] + nv[1] * sgn * reach)])
    x = ray.intersection(poly.boundary)
    if x.is_empty:
        return None
    ds = [math.hypot(g.x - p[0], g.y - p[1])
          for g in getattr(x, "geoms", [x]) if g.geom_type == "Point"]
    return max(ds) if ds else None


def _edges_at(p, nv, sgn: float, poly, reach: float = 600.0):
    """``(the NEAR boundary distance, the FAR one)`` at which the outward
    normal ray from ``p`` crosses ``poly``'s boundary — the two kerbs of
    the cell the ray is standing in — or ``None``."""
    ray = LineString([p, (p[0] + nv[0] * sgn * reach, p[1] + nv[1] * sgn * reach)])
    x = ray.intersection(poly.boundary)
    if x.is_empty:
        return None
    ds = sorted(math.hypot(g.x - p[0], g.y - p[1])
                for g in getattr(x, "geoms", [x]) if g.geom_type == "Point")
    return (ds[0], ds[-1]) if ds else None


def _covered_offset(p, nv, sgn: float, kerb: float, strip: float, tree, cells,
                    polys, deck_cell, cut_roles, grid: float
                    ) -> tuple[float, str | None]:
    """§34 (5) (b) AMENDED — A COVERED EXTENT NEVER ENDS INSIDE A
    NEIGHBOUR'S PAVEMENT; §34 (12) (3) AMENDED — A RAMP PRIMARILY OFF
    PAVEMENT STOPS AT THE PAVEMENT EDGE (owner RULINGS 2026-09-17x (4);
    owner 17q item 2, 17v).

    ``(the covered extent's offset from the axis on this side, the ref of
    the neighbour pavement that moved it or None)``.

    §34 (5) (b) added the deck cell's own GRADED STRIP to each kerb so the
    trench opens beyond the strip and never inside zone 1 (owner 15e item
    7).  A strip is GROUND.  At LEMD F-6 the deck cell ``junction/pav157``'s
    north kerb stands **0.15 m** from way −1230's OSM centreline, so the
    whole 19.0 m code-E strip was laid on the NEIGHBOUR's pavement
    ``pav188``: the ramp's mouth opened **14.5 m inside** a 30 m apron
    band and the rim notched 324 m² out of it — owner 17q item 2, the
    THIRD read of this one mouth.

    THE AMENDMENT, and it is one sentence: the covered extent may not END
    INSIDE another airside pavement cell.  Where ``kerb + strip`` lands in
    one, it moves to the NEARER of that cell's two kerbs along the normal
    — forward, and the pavement is COVERED and the ramp opens beyond it
    ("stop at the pavement edge"); or back, and the ramp opens before it
    and the pavement is never entered.  The mouth therefore always stands
    on ground or on a pavement's own edge, never in the middle of one.

    THE NEARER EDGE IS WHAT BOUNDS IT, and that was measured: reading
    "always the far kerb" instead (arm r1) ran LEMD F-6 correctly and then
    swallowed whole aprons elsewhere — VMMC's underpass −34 grew its
    ribbon 90,619 → 95,295 m² across ``pav5`` for 1,607 of its 1,614
    stations and BORED A ROAD THAT WAS NOT BORED BEFORE (VMMC tunnels
    2 → 4, at the airport whose owner read is "there should be no tunnels
    cut at VMMC"), and KCLT's ribbons grew the same way.  The nearer-edge
    rule can never move the extent further out than it would move it back,
    so a crossing cannot run under an apron it does not pass through.

    Nothing is added BEYOND the neighbour's pavement: the reading is
    therefore ROLE-BLIND — ``pav188`` as ``apron`` and ``pav188`` re-roled
    to a TAXI-family role (lane ``v2neckarm``, owner 17x (3)) give the
    same offset, which is the twin's own parametrisation.

    ``cut_roles`` is ``structure_service.airside_cut_roles`` — §34 (12)
    (3)'s own protected set, imported and never re-spelled (the
    census-wrapper precedent).  With none (``_deck_half_width``, which
    reads the DECK's width alone) the pre-17x reading stands verbatim."""
    if not cut_roles or strip <= 0.0:
        return kerb + strip, None
    target = kerb + strip
    hit = _airside_at(p, nv, sgn, target, tree, cells, polys,
                      deck_cell, cut_roles)
    if hit is None:
        return target, None                      # the strip stands on ground
    edges = _edges_at(p, nv, sgn, hit[1])
    if edges is None:
        return target, None
    near, far = max(kerb, edges[0]), edges[1]
    if far - target <= target - near:
        return far, hit[0].ref                   # covered: the ramp opens beyond
    return near, hit[0].ref                      # short: the ramp opens before


def _airside_at(p, nv, sgn: float, dist: float, tree, cells, polys,
                deck_cell, cut_roles):
    """``(cell, polygon)`` of the AIRSIDE PAVEMENT cell standing ``dist``
    out along the normal, or ``None`` — the deck cell itself never
    counts (it is the pavement the crossing is already under)."""
    q = Point(p[0] + nv[0] * sgn * dist, p[1] + nv[1] * sgn * dist)
    for j in tree.query(q, predicate="intersects"):
        c = cells[int(j)]
        if c is deck_cell or c.kind == "structure" or c.role not in cut_roles:
            continue
        if not polys[int(j)].contains(q):
            continue
        return c, polys[int(j)]
    return None


def _deck_cell(axis_fn, ss, cells, polys, half_default: float,
               max_half: float | None = None, law: Law | None = None,
               cut_roles: _t.Sequence[str] = (), grid: float = 0.5,
               stopped: dict | None = None):
    """THE DECK CELL AND ITS HALF-WIDTH ACROSS THE ROAD (spec §34 (5),
    §34 (5) (a)): ``(the admitted cells' union or None, the MEDIAN
    half-width, stations read, stations REFUSED)``.

``(the per-station offsets, the MEDIAN half-width,
    stations read, stations REFUSED)``.

    §34 (5) (b) (Fable 2026-09-15; RULINGS 2026-09-15h): with a ``law``
    the two offsets carry the cell's own GRADED STRIP beyond its kerbs
    (:func:`strip_half_width_m`) — the covered extent of an underpass
    beneath a taxiway or runway spans the pavement AND its strip, so the
    mouth opens beyond the strip and the ramp descends outside it.
    Without a ``law`` the offsets are the kerbs alone, which is what the
    DECK's own half-width is read from (``_deck_half_width``).

    Per station the governed pavement cell the aeroway's axis stands in is
    measured perpendicular to the axis: ``(s, left, right)`` are its two
    kerbs' distances from the axis on either side — the DECK CELL's own
    footprint across the crossing, which is what §34 (5) (a) clips the
    bored road to — and the half-width is their median mean.  One
    derivation, two readers (RULINGS 2026-09-14bp item 1: "the
    centreline-symmetric ribbon only where no cell states the deck;
    ``_deck_half_width`` reads the same derivation").

    Returns ``(half, stations read, stations REFUSED)`` — a station whose
    cell half-width exceeds ``max_half`` (§34 (5) as narrowed: 4× the
    way's own carriageway) is refused and the fallback ``half_default``,
    the carriageway, governs where every station is refused.

    A taxiway bridge way carries no ``width`` tag, so the carriageway
    fallback reads 2 lanes × 3.5 m = 7 m — a third of a real taxiway, and
    a 7 m bore puts both its mouths under the deck.  The taxi cell the
    aeroway runs in IS the deck (measured LEMD F-6: ``junction/pav157``),
    and its own edges across the axis are the width the road passes under.
    ``pavement_half_widths`` cannot answer this: its
    ``ramp_pavement_max_offset_m`` test asks whether a pavement TRACES a
    road, and a junction blob's across-axis centre is metres off the
    taxiway centreline it contains."""
    if stopped is None:
        stopped = {}
    if not polys:
        return [], half_default, 0, 0
    tree = STRtree(polys)
    reach = 200.0
    vals: list[float] = []
    offs: list[tuple[float, float, float]] = []
    refused = 0
    for i, s in enumerate(ss):
        p = axis_fn(s)
        a = axis_fn(max(0.0, s - 1.0))
        b = axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        pt = Point(p)
        best = None
        best_cell = None
        for j in tree.query(pt, predicate="intersects"):
            c = cells[int(j)]
            if c.kind == "structure" or not polys[int(j)].contains(pt):
                continue
            poly = polys[int(j)]
            hs = []
            for sgn in (1.0, -1.0):
                ray = LineString([p, (p[0] + nv[0] * sgn * reach,
                                      p[1] + nv[1] * sgn * reach)])
                x = ray.intersection(poly.boundary)
                if x.is_empty:
                    hs = []
                    break
                pts = [g for g in getattr(x, "geoms", [x]) if g.geom_type == "Point"]
                if not pts:
                    hs = []
                    break
                hs.append(min(math.hypot(g.x - p[0], g.y - p[1]) for g in pts))
            if len(hs) == 2:
                h = (hs[0] + hs[1]) / 2.0
                if best is None or h < best[0]:
                    best = (h, hs[0], hs[1])
                    best_cell = c
        if best is None:
            continue
        # §34 (5) NARROWED: the cell the axis stands in states the deck
        # only while it is plausibly the way's own pavement.
        if max_half is not None and best[0] > max_half:
            refused += 1
            continue
        vals.append(best[0])
        # §34 (5) (b): the covered extent is the pavement AND its graded
        # strip.  The DECK's own width (``vals``) is the pavement's alone.
        #
        # THE DECK CELL'S OWN STRIP, and the alternative is DELETED, not
        # parked: a "widest strip standing at this station" reading was
        # built and measured (arm 4, a second full planar replay) and is
        # BYTE-IDENTICAL to this one at LEMD — the classification's cells
        # are a PARTITION, so exactly one cell contains each station, and
        # at F-6 that is ``junction/pav157`` (code E, 19.0 m) for 36 of the
        # way's 48 m with the last station in a 14R/32L ``runway_shoulder``
        # cell the ``DECK_CELL_MAX_RATIO`` gate refuses outright.  The
        # widest reading can therefore never differ from this one.
        strip = strip_half_width_m(law, best_cell) if law is not None else 0.0
        hl, kl = _covered_offset(p, nv, +1.0, best[1], strip, tree, cells,
                                 polys, best_cell, cut_roles, grid)
        hr, kr = _covered_offset(p, nv, -1.0, best[2], strip, tree, cells,
                                 polys, best_cell, cut_roles, grid)
        for ref in (kl, kr):
            if ref:
                stopped[ref] = stopped.get(ref, 0) + 1
        offs.append((s, hl, hr))
    if not vals:
        return offs, half_default, 0, refused
    vals.sort()
    return offs, vals[len(vals) // 2], len(vals), refused


def _cell_ribbon(axis_fn, ss, offs: list[tuple[float, float, float]], erode: float,
                 grid: float):
    """THE DECK CELL'S FOOTPRINT ACROSS THE AXIS, ERODED (§34 (5) (a)),
    WITH ITS GRADED STRIP (§34 (5) (b)): the band between the cell's two
    kerbs at each station read — already carrying the strip where
    :func:`_deck_cell` was given the law — each side brought in by ``erode`` (the rim stand-off and one identity step), as
    one polygon — ``(the ribbon, True)``, or ``(None, False)`` where no
    station's cell states the deck.  Asymmetric by construction: the OSM
    centreline is not the pavement's middle, which is the whole point."""
    if len(offs) < 2:
        return None, False
    left: list[XY] = []
    right: list[XY] = []
    for s, hl, hr in offs:
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        dl, dr = max(grid, hl - erode), max(grid, hr - erode)
        left.append((p[0] + nv[0] * dl, p[1] + nv[1] * dl))
        right.append((p[0] - nv[0] * dr, p[1] - nv[1] * dr))
    ring = left + list(reversed(right))
    poly = Polygon(ring)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        return None, False
    if poly.geom_type != "Polygon":
        parts = [g for g in poly.geoms if g.geom_type == "Polygon"]
        if not parts:
            return None, False
        poly = max(parts, key=lambda g: g.area)
    return poly, True
