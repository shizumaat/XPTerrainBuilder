"""THE ROAD BRIDGE DECK — RULINGS 2026-08-30c §1–§6,
as amended by RULINGS 2026-08-30d (the TERRAIN-BASED bridge).

    A MAPPED ROAD BRIDGE OVER A BELOW-GRADE STRUCTURE IS A DECK, NOT
    CUTTABLE PAVEMENT.

    ...and where the pack provides NO bridge OBJECT for the span, that
    deck is TERRAIN: the mesh is a heightfield, so the deck's terrain
    spans the crossing AT ROAD LEVEL and CUTS THROUGH the ramp's open
    cut.  The ramp CONTINUES ON EITHER SIDE.

One home for the whole law, because its clauses fire in three different
phases and a reader who has to reassemble them from four call sites
cannot check the law against the code:

* **§1 Scope** — :func:`publish_candidates` (phase 4, before the corridor
  course set is built) and :func:`confirm_and_sever` (inside the tunnel
  pass, once the ramps exist).  The tag is the only trigger: a feed way
  carrying ``bridge`` (any value but ``no``).  Geometry NEVER infers a
  bridge.
* **§2 What emits** — the admission hook in ``pipeline`` reads
  :func:`is_candidate_way`, which lets a deck way into the course set on
  BRIDGE EVIDENCE alone, skipping the touching-pavement test.  The
  carriageway width is the way's own stated width, through the ordinary
  ``attach_course_widths`` path — the deck is a piece of the road, not a
  new shape class.
* **§3 What must not touch it** — :func:`is_deck_shape` is honoured by
  ``bridges.cut_pavement_over_footprint`` (so the tunnel-ramp cut and its
  clearance annulus pass the deck by) and by
  ``covered_span.suppress_synthesised_road_pavement``; and
  :func:`abutment_keep_out` removes the free-end DEM tie at either
  abutment, because the road runs THROUGH.
* **§3/§4 AS AMENDED (2026-08-30d)** — :func:`confirm_and_sever` returns
  the footprint of every confirmed TERRAIN deck, and the tunnel pass
  unions it into its PROTECTED-TRANSIT union and its wall gate.  That is
  the covered-stretch machinery the pass already owns, REUSED and not
  forked: over protected pavement a mostly-covered ramp piece drops and
  a graze is clipped back to the edge, so the open cut is severed inside
  the deck footprint, no walls stand there, and the ramp resumes at both
  deck edges with its authored profile untouched.  The old float-above
  model (deck pinned at ramp + clearance, over an OPEN ramp) is
  SUPERSEDED and its pin machinery is deleted.
* **§4's clearance clause, as amended** — it now applies to the ramp's
  CONTINUED profile, which passes under the deck "by construction of the
  authored ramp datum, NOT by moving the deck up".  So it is an
  INSTRUMENT here: :func:`confirm_and_sever` records the cover the
  emitted ramp actually leaves under the deck and says whether the
  premise holds.  Nothing in this module moves a deck or a ramp.
* **§5 The approaches** — unchanged, and now the only thing that sets the
  deck's height: the deck sits at the ROAD SOLVE's own level, so the
  chain simply solves through it at ``SERVICE_ROAD_MAX_GRADE``.  There
  is no deck pin.
* **§6 Refusal, loudly** — retained for a deck that carries an
  INDEPENDENT value to reach.  A terrain deck carries none (it IS the
  road solve), so §6 cannot fire in the no-object case; see the round
  report's deviation delta.

WHY CANDIDACY IS PREDICTED AND THEN CONFIRMED.  §1 asks whether the span
crosses a structure THIS BUILD EMITTED, and the tunnel pass emits long
after the course set is minted in phase 4.  Admitting every bridge-tagged
way and sorting it out later is NOT equivalent: a way minted in phase 4
is a solver variable by phase 5, so a way over nothing would perturb a
surface §1 says it must leave alone.  So candidacy is decided in phase 4
against the extent the tunnel pass CAN reach — the mapped bore corridor
extended along its own tangents by the portal walk's own arm cap, and
narrowed by §2's own continuity clause — and §1 proper is decided inside
the tunnel pass against what was actually emitted.
"""
from __future__ import annotations

import math

import O4_UI_Utils as UI

_CANDIDATES = "_road_bridge_deck_candidates"
_PINS = "_road_bridge_deck_pins"
_RECORDS = "_road_bridge_deck_records"

#: Tag values that are NOT a bridge.  §1: "``bridge`` (any value but
#: ``no``)".
_NOT_A_BRIDGE = {"", "no"}

#: How far past a mapped bore's own ends the phase-4 PREDICTION reaches,
#: along the bore's end tangents.  This is ``_emit_tunnel_portals``'s own
#: ``arm_max_length_m`` default — the furthest a ramp arm can walk — so
#: the prediction cannot fall short of what the emitter may produce.
#: It is a CANDIDACY bound only; §1 is decided in :func:`confirm_and_pin`
#: against emitted geometry.
PREDICTION_ARM_M = 500.0

#: Lateral margin (m) added to the predicted bore corridor's half width.
PREDICTION_MARGIN_M = 8.0

#: Minimum share of a minted road piece that must lie inside a deck
#: corridor before the piece IS that deck (the "mostly over" test the
#: covered-span mask uses for the same kind of question).
DECK_PIECE_MIN_FRACTION = 0.5

#: Roles whose emitted shapes are the BELOW-GRADE STRUCTURE of §1.
_BELOW_GRADE_REFS = ("tunnel_ramp", "tunnel_corridor", "tunnel_trench",
                     "object_basin_trench")


def _way_is_bridge(tags) -> bool:
    """§1's ONLY trigger."""
    return str((tags or {}).get("bridge", "") or "").lower() \
        not in _NOT_A_BRIDGE


def _extended(points, arm_m: float):
    """``points`` with a straight arm of ``arm_m`` added at each end
    along that end's own tangent — the reach a portal walk can add."""
    if len(points) < 2:
        return list(points)
    out = list(points)

    def _arm(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        if n <= 0.0:
            return None
        return (b[0] + dx / n * arm_m, b[1] + dy / n * arm_m)

    tail = _arm(out[1], out[0])
    head = _arm(out[-2], out[-1])
    if tail is not None:
        out.insert(0, tail)
    if head is not None:
        out.append(head)
    return out


def _predicted_extent(layout):
    """Union of where the tunnel pass CAN put a below-grade structure.

    Reads the memoised tunnel road network (``bridges._load_tunnel_road_
    network``) — the same ONE load the covered-span mask uses, so
    publishing this costs no second parse."""
    try:
        from shapely.geometry import LineString
        from shapely.ops import unary_union

        from .bridges import (
            TUNNEL_DEFAULT_CARRIAGEWAY_WIDTH_M,
            _carriageway_width_from_tags, _has_tunnel_tag_evidence,
            _load_tunnel_road_network, _local_meter_projections,
            _tunnelable,
        )
        nodes_r, ways_r, _big, _ntags = _load_tunnel_road_network(layout)
        to_m, _ = _local_meter_projections(layout.anchor)
        bodies = []
        for _wid, nrefs, tags in ways_r:
            # A BELOW-GRADE WAY, not merely a tunnelABLE one.
            # ``_tunnelable`` is a highway/railway CLASS test — at LEMD
            # it is true of 4,654 of the feed's 5,025 ways, and a
            # prediction built from those covers 40 km² and makes every
            # bridge in the region a candidate.  The admission test for
            # a below-grade way is R4's ``_has_tunnel_tag_evidence``
            # (``tunnel`` in TUNNEL_VALUES, or ``layer`` < 0), which is
            # what the tunnel pass itself requires before it emits
            # anything below grade.
            if not (_tunnelable(tags) and _has_tunnel_tag_evidence(tags)):
                continue
            pts = []
            for n in nrefs:
                ll = nodes_r.get(n)
                if ll is not None:
                    pts.append(to_m(ll[1], ll[0]))
            if len(pts) < 2:
                continue
            half = 0.5 * float(_carriageway_width_from_tags(
                tags.get("highway"), tags,
                TUNNEL_DEFAULT_CARRIAGEWAY_WIDTH_M)) + PREDICTION_MARGIN_M
            try:
                bodies.append(LineString(
                    _extended(pts, PREDICTION_ARM_M)).buffer(
                        half, cap_style=2, join_style=2))
            except Exception:                            # pragma: no cover
                continue
        if not bodies:
            return None
        extent = unary_union(bodies)
        return None if extent.is_empty else extent
    except Exception as exc:                             # pragma: no cover
        UI.vprint(1, f"  [bridge-deck] prediction NOT derived ({exc!r}) — "
                     f"§1 candidacy is INACTIVE this build.")
        return None


def publish_candidates(layout, touches_pavement=None) -> list:
    """§1, phase 4: the bridge-tagged feed ways whose span can cross a
    below-grade structure this build will emit AND which complete an
    admitted road chain.  Idempotent.

    ``touches_pavement(way_id, line) -> bool`` is the caller's ORDINARY
    admission test — the same one §2 lets a deck skip.  It is needed
    here, not merely later, because §2's own sentence scopes the
    admission: *"so the chain it belongs to is continuous end to end
    across the span"*.  A bridge that completes no admitted chain is
    bridging nothing this build paves, and admitting it would mint road
    pavement where today there is none — which is exactly what §1's
    "drapes exactly as today" forbids.  MEASURED at LEMD: the predicted
    extent alone makes 51 of the feed's 196 bridge ways candidates;
    requiring the chain join leaves 3, the owner's two among them.

    The join is by CANONICAL IDENTITY — the feed's own node ids, shared
    between ways — never proximity.
    """
    existing = getattr(layout, _CANDIDATES, None)
    if existing is not None:
        return existing
    records: list = []
    try:
        from shapely.geometry import LineString

        from .bridges import _local_meter_projections
        net = getattr(layout, "airport_road_network", None)
        extent = _predicted_extent(layout) if net is not None else None
        if net is not None and extent is not None:
            to_m, _ = _local_meter_projections(layout.anchor)
            lines: dict = {}
            for wid, nrefs, tags in net.ways:
                if not tags.get("highway"):
                    continue
                pts, ends = [], []
                for n in nrefs:
                    ll = net.nodes.get(n)
                    if ll is None:
                        continue
                    pts.append(to_m(ll[1], ll[0]))
                    ends.append((n, ll))
                if len(pts) < 2:
                    continue
                try:
                    line = LineString(pts)
                except Exception:                        # pragma: no cover
                    continue
                if line.is_empty or line.length < 1.0:
                    continue
                lines[wid] = (line, ends, tags, list(nrefs))
            # The nodes of every way TODAY's course set already admits.
            admitted_nodes: set = set()
            if touches_pavement is not None:
                for wid, (line, _e, tags, nrefs) in lines.items():
                    if _way_is_bridge(tags):
                        continue
                    try:
                        if touches_pavement(wid, line):
                            admitted_nodes.update(nrefs)
                    except Exception:                    # pragma: no cover
                        continue
            for wid, (line, ends, tags, nrefs) in lines.items():
                if not _way_is_bridge(tags):
                    continue
                if not line.intersects(extent):
                    continue          # §1: no structure can be beneath
                if touches_pavement is not None and not (
                        set(nrefs) & admitted_nodes):
                    continue          # §2: it completes no admitted chain
                width = float((getattr(net, "widths", None) or {}).get(
                    wid, 0.0)) or None
                records.append({
                    "way_id": str(wid),
                    "line": line,
                    "width_m": width,
                    "abutments": [ends[0], ends[-1]],
                    "bridge": str(tags.get("bridge")),
                    "layer": str(tags.get("layer", "") or ""),
                    "highway": str(tags.get("highway", "") or ""),
                    "bridge_evidence_only": False,
                    "verdict": "candidate",
                })
    except Exception as exc:                             # pragma: no cover
        UI.vprint(1, f"  [bridge-deck] candidates NOT published "
                     f"({exc!r}) — the law is INACTIVE this build.")
        records = []
    setattr(layout, _CANDIDATES, records)
    if records:
        UI.vprint(1,
            f"  [bridge-deck] §1: {len(records)} mapped road bridge(s) "
            f"span ground a below-grade structure can reach "
            f"({', '.join(r['way_id'] for r in records[:6])}"
            f"{' …' if len(records) > 6 else ''}) — admitted to the "
            f"corridor course set on BRIDGE EVIDENCE (§2); §1 is "
            f"confirmed against emitted geometry after the tunnel pass.")
    return records


def candidates_of(layout) -> list:
    return list(getattr(layout, _CANDIDATES, None) or ())


def is_candidate_way(layout, way_id) -> bool:
    """§2: does this feed way skip the touching-pavement test?"""
    wid = str(way_id)
    return any(r["way_id"] == wid for r in candidates_of(layout))


def note_bridge_evidence_only(layout, way_id, touched_pavement: bool):
    """Record whether the way would have been admitted anyway.  A deck
    that stands down must leave TODAY's surface, and today's surface
    keeps a bridge way that touches pavement."""
    wid = str(way_id)
    for r in candidates_of(layout):
        if r["way_id"] == wid:
            r["bridge_evidence_only"] = not bool(touched_pavement)


def _corridor(record):
    width = record.get("width_m") or 0.0
    if width <= 0.0:
        from .config import SERVICE_ROAD_WIDTH_M
        width = float(SERVICE_ROAD_WIDTH_M)
    return record["line"].buffer(0.5 * float(width), cap_style=2,
                                 join_style=2)


def stamp_shapes(layout) -> int:
    """§2/§3: mark the minted road pieces that ARE a deck, so the cut
    passes can pass them by.  The flag rides the shape through every
    clip and re-role, exactly like ``synthesised_road_corridor``."""
    records = candidates_of(layout)
    if not records:
        return 0
    corridors = [(r, _corridor(r)) for r in records]
    n = 0
    for s in getattr(layout, "shapes", None) or ():
        poly = getattr(s, "polygon", None)
        if (poly is None or poly.is_empty
                or not getattr(s, "synthesised_road_corridor", False)):
            continue
        try:
            area = float(poly.area)
        except Exception:                                # pragma: no cover
            continue
        if area <= 0.0:
            continue
        for r, corr in corridors:
            try:
                if poly.intersection(corr).area \
                        >= DECK_PIECE_MIN_FRACTION * area:
                    s.road_bridge_deck = r["way_id"]
                    n += 1
                    break
            except Exception:                            # pragma: no cover
                continue
    return n


_DECK_UNION = "_road_bridge_deck_union"


def deck_union(layout):
    """Union of every live deck corridor — the ground §3 protects.

    Cached on the layout: the corridors come from the phase-4 candidate
    records and never move."""
    got = getattr(layout, _DECK_UNION, "unset")
    if got != "unset":
        return got
    records = [r for r in candidates_of(layout)
               if r.get("verdict") in ("candidate", "confirmed_terrain")]
    u = None
    if records:
        try:
            from shapely.ops import unary_union
            u = unary_union([_corridor(r) for r in records])
            if u.is_empty:
                u = None
        except Exception:                                # pragma: no cover
            u = None
    try:
        setattr(layout, _DECK_UNION, u)
    except (AttributeError, TypeError):                  # pragma: no cover
        pass
    return u


def terrain_deck_union(layout):
    """The union the RAMP-DATUM rule reads (RULINGS 2026-08-30f) — the
    decks whose cut must hold bore datum beneath them.

    Narrower than :func:`deck_union` by exactly one clause: a span with a
    classified hard-deck OBJECT bridge over it is governed by the object
    law and "the terrain stays open", so its walk must NOT be flattened.
    Not cached: the portal walk runs after the classification is
    attached, while :func:`deck_union` (protection) is asked much
    earlier, and freezing one answer for both would let a pre-
    classification call decide the ramp datum.
    """
    records = [r for r in candidates_of(layout)
               if r.get("verdict") in ("candidate", "confirmed_terrain")]
    if not records:
        return None
    keep = []
    for r in records:
        corr = _corridor(r)
        if _hard_deck_object_over(layout, corr):
            continue
        keep.append(corr)
    if not keep:
        return None
    try:
        from shapely.ops import unary_union
        u = unary_union(keep)
        return None if u.is_empty else u
    except Exception:                                    # pragma: no cover
        return None


def is_deck_shape(shape, layout=None) -> bool:
    """§3: this piece is a ROAD BRIDGE DECK — no tunnel-ramp cut, no
    clearance annulus and no covered-span suppression may remove it.

    GEOMETRY, not only the flag.  The flag is stamped on the minted
    ``service_road`` rect in phase 4, but the GROUNDSIDE PASS runs before
    the tunnel pass and rebuilds pieces as fresh ``BuiltShape``s (several
    sites in ``groundside`` merge and re-role rather than
    ``dataclasses.replace``), so by the time the ramp cut asks, the flag
    is gone and the exemption lapses.  MEASURED at LEMD 2026-08-30
    (build ``lemddeck3``): both decks were demoted to
    ``groundside_pavement`` before the tunnel pass and the ramp cut then
    carved the span into four fragments with three gaps — 12-22, 30-50
    and 57-69 m along an 84.2 m span.

    The corridor is published once in phase 4 and never moves, so asking
    "is this piece mostly INSIDE a deck corridor?" is stable across every
    re-role and merge, which a per-shape flag is not.
    """
    if bool(getattr(shape, "road_bridge_deck", "") or ""):
        return True
    if layout is None:
        return False
    u = deck_union(layout)
    if u is None:
        return False
    poly = getattr(shape, "polygon", None)
    if poly is None or poly.is_empty:
        return False
    try:
        area = float(poly.area)
        if area <= 0.0:
            return False
        return poly.intersection(u).area >= DECK_PIECE_MIN_FRACTION * area
    except Exception:                                    # pragma: no cover
        return False


def abutment_keep_out(layout):
    """§3: the corridors inside which no free-end DEM tie is minted — the
    road runs THROUGH a deck, so neither abutment is a terminus.
    ``None`` when the law found nothing."""
    records = [r for r in candidates_of(layout)
               if r.get("verdict") in ("candidate", "confirmed")]
    if not records:
        return None
    try:
        from shapely.ops import unary_union
        u = unary_union([_corridor(r) for r in records])
        return None if u.is_empty else u
    except Exception:                                    # pragma: no cover
        return None


def _shape_top(shape):
    """The HIGHEST elevation a built shape carries, whichever of the
    three encodings it uses — ``None`` when it carries none.

    ALL THREE, and this is load-bearing: a tunnel RAMP is a SLOPED rect,
    so ``bridges`` builds it with ``altitude_high`` / ``altitude_low``
    and NEITHER ``node_altitudes`` NOR ``altitude``.  Reading only the
    latter two skips every sloped ramp, which is the whole population
    §1 exists to find (measured at LEMD 2026-08-30: 4 ramps beneath the
    owner's span, all four invisible, both decks wrongly UNCONFIRMED).
    """
    vals = [float(a) for a in
            (getattr(shape, "node_altitudes", None) or ())
            if a is not None]
    for attr in ("altitude_high", "altitude", "altitude_low"):
        a = getattr(shape, attr, None)
        if a is not None:
            vals.append(float(a))
    return max(vals) if vals else None


def _below_grade_shapes(layout):
    out = []
    for s in getattr(layout, "shapes", None) or ():
        if str(getattr(s, "ref", "") or "") not in _BELOW_GRADE_REFS:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        top = _shape_top(s)
        if top is None:
            continue
        out.append((poly, top, s))
    return out


def _receiving_value(layout, point, deck_ids, reach_m: float = 25.0):
    """§5's "the receiving surface's own value" AT an abutment.

    THE NEAREST VERTEX, not the nearest shape's mean.  A receiving
    surface is often a single large ring — an apron, or a 42-node
    taxiway junction spanning hundreds of metres — whose mean elevation
    says nothing about the metre of ground the deck actually lands on.
    Measured at LEMD 2026-08-30: the shape-mean reader returned 612.08 m
    for the west abutment of ``-2192``, where the road it lands on is at
    ~601 m, and priced §6 against a number that exists nowhere near the
    bridge.  The vertex carries its own solved value, which is what
    "the receiving surface's own value" means.
    """
    best = None
    px, py = float(point.x), float(point.y)
    for s in getattr(layout, "shapes", None) or ():
        if id(s) in deck_ids or is_deck_shape(s, layout):
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        if getattr(s, "role", None) not in _RECEIVING_ROLES:
            continue
        try:
            if float(poly.distance(point)) > reach_m:
                continue
            ring = list(poly.exterior.coords)
        except Exception:                                # pragma: no cover
            continue
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        alts = [a for a in (getattr(s, "node_altitudes", None) or ())
                if a is not None]
        flat = _shape_top(s) if not alts else None
        for i, (vx, vy) in enumerate(ring):
            d = math.hypot(float(vx) - px, float(vy) - py)
            if d > reach_m or (best is not None and d >= best[0]):
                continue
            if alts and len(alts) == len(ring):
                v = float(alts[i])
            elif flat is not None:
                v = float(flat)
            else:
                continue
            best = (d, v, s)
    return best


_RECEIVING_ROLES = frozenset()


def _init_receiving_roles():
    global _RECEIVING_ROLES
    if _RECEIVING_ROLES:
        return
    from .layout import (ROLE_APRON, ROLE_GROUNDSIDE_PAVEMENT,
                         ROLE_JUNCTION, ROLE_SERVICE_JUNCTION,
                         ROLE_SERVICE_ROAD)
    _RECEIVING_ROLES = frozenset({
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
        ROLE_GROUNDSIDE_PAVEMENT, ROLE_APRON, ROLE_JUNCTION,
    })


def _hard_deck_object_over(layout, corridor) -> bool:
    """Does a CLASSIFIED HARD-DECK OBJECT BRIDGE stand over this span?

    RULINGS 2026-08-30d: *"Where a classified hard-deck OBJECT bridge
    exists, the object law (R14-2/A-3 first exception) continues to
    govern and the terrain stays open."*  So the terrain-based treatment
    is the NO-OBJECT case, and this is the discriminator.

    The classifier's own ``hard_deck`` verdict is the test — which is
    exactly why "surface cones and edge barriers do not count": they
    never reach it.  The deck footprint is projected through the SAME
    helper the object-bridge emitter uses, so the two can never disagree
    about where an object bridge is.
    """
    try:
        from .bridges import (_bridge_footprint_meters,
                              _local_meter_projections,
                              _object_bridge_classification)
        classification = _object_bridge_classification(layout)
        records = list(getattr(classification, "bridges", None) or ())
        if not records:
            return False
        to_m, _ = _local_meter_projections(layout.anchor)
        for b in records:
            if not bool(getattr(b, "hard_deck", False)):
                continue
            poly = _bridge_footprint_meters(b, to_m)
            if poly is None or poly.is_empty:
                continue
            if poly.intersects(corridor):
                return True
    except Exception:                                    # pragma: no cover
        return False
    return False


def confirm_and_sever(layout, icao: str = ""):
    """§1 confirmation and the TERRAIN-BASED deck (RULINGS 2026-08-30d),
    in the one slot where both can mean something: inside the tunnel
    pass, after the ramps are emitted and BEFORE the covered-stretch
    clip reads its protected union.

    Returns ``(report, sever_union)``.  ``sever_union`` is the footprint
    of every CONFIRMED TERRAIN deck; the caller unions it into the
    protected-transit union and the wall gate, which is what makes the
    stretch under the deck a COVERED STRETCH — the ramp's open cut is
    severed there, no walls stand inside the footprint, and the ramp
    RESUMES at both deck edges with its authored profile untouched.
    That is the tunnel pass's own covered-stretch machinery, reused
    rather than forked: over protected pavement a mostly-covered ramp
    piece drops and a graze is clipped back to the edge, exactly as it
    already does under a taxiway.

    WHY THE SLOT MOVED.  Under 2026-08-30c the deck floated ABOVE an
    open ramp, so §1 could be confirmed after the whole tunnel pass and
    §4 could pin the deck.  Under 2026-08-30d the deck CUTS the ramp,
    so confirmation has to happen while the ramp pieces are still
    there — confirm afterwards and §1 would find the very geometry the
    deck had just severed, call the deck unconfirmed, stand it down, and
    leave the ramp cut with nothing spanning it.
    """
    _init_receiving_roles()
    report = {"candidates": 0, "confirmed_terrain": 0,
              "object_governed": 0, "unconfirmed": 0, "refused": 0}
    records = candidates_of(layout)
    if not records:
        setattr(layout, _RECORDS, [])
        return report, None
    from .config import BRIDGE_ROAD_CLEARANCE_M

    beneath_all = _below_grade_shapes(layout)
    stand_down: list = []
    sever: list = []
    report["candidates"] = len(records)

    for r in records:
        corr = _corridor(r)
        # ── §1: what did this build ACTUALLY emit beneath the span? ──
        beneath = []
        for poly, top, s in beneath_all:
            try:
                if poly.intersection(corr).area >= 0.5:
                    beneath.append((top, s))
            except Exception:                            # pragma: no cover
                continue
        if not beneath:
            r["verdict"] = "unconfirmed"
            r["reason"] = ("no below-grade structure was emitted beneath "
                           "the span — §1 does not reach this way")
            report["unconfirmed"] += 1
            stand_down.append(r)
            continue
        top = max(t for t, _s in beneath)
        r["structures_beneath"] = len(beneath)
        r["highest_beneath_m"] = round(float(top), 3)

        # ── 2026-08-30d: OBJECT OR TERRAIN? ─────────────────────────
        if _hard_deck_object_over(layout, corr):
            r["verdict"] = "object_governed"
            r["reason"] = ("a classified hard-deck OBJECT bridge stands "
                           "over this span — the object law (R14-2/A-3's "
                           "first exception) governs and the terrain "
                           "stays open")
            report["object_governed"] += 1
            # Not a terrain deck: the pieces stay (the road is real) but
            # they sever nothing and claim no protection of their own.
            continue

        # ── TERRAIN-BASED DECK ──────────────────────────────────────
        # "the mesh is a heightfield, so the deck's terrain spans the
        # crossing AT ROAD LEVEL and CUTS THROUGH the tunnel ramp's open
        # cut."  There is NO deck value to pin: the deck sits at the
        # road solve's own level (§5 approaches unchanged), so §6 has no
        # independent value to price and cannot fire here.
        r["verdict"] = "confirmed_terrain"
        report["confirmed_terrain"] += 1
        # §4 as amended is an INSTRUMENT here, not a lever: the ramp's
        # continued profile passes under the deck "by construction of
        # the authored ramp datum, not by moving the deck up".  Record
        # what the emitted ramp actually left, so the owner can see
        # whether that premise holds at this site — we never move the
        # deck to satisfy it, and we never move the ramp at all.
        deck_level = _deck_level(layout, r)
        r["deck_level_m"] = (round(deck_level, 3)
                             if deck_level is not None else None)
        r["clearance_required_m"] = float(BRIDGE_ROAD_CLEARANCE_M)
        r["clearance_measured_m"] = (
            round(deck_level - float(top), 3)
            if deck_level is not None else None)
        r["clearance_premise_holds"] = (
            bool(r["clearance_measured_m"] is not None
                 and r["clearance_measured_m"]
                 >= float(BRIDGE_ROAD_CLEARANCE_M)))
        sever.append(corr)
        UI.vprint(1,
            f"  [bridge-deck] {r['way_id']} CONFIRMED TERRAIN (§1 + "
            f"2026-08-30d): {len(beneath)} emitted below-grade shape(s) "
            f"beneath the span, highest {top:.2f} m, no hard-deck object "
            f"over it — the deck's terrain spans at ROAD LEVEL and the "
            f"stretch beneath becomes a COVERED STRETCH: the open cut is "
            f"severed inside the footprint and the ramp resumes at both "
            f"deck edges with its authored profile untouched.")
        if not r["clearance_premise_holds"] \
                and r["clearance_measured_m"] is not None:
            UI.vprint(1,
                f"  [bridge-deck] {r['way_id']} §4 CLEARANCE PREMISE "
                f"DOES NOT HOLD (instrument, no lever): the emitted ramp "
                f"reaches {top:.2f} m against a deck at "
                f"{deck_level:.2f} m — {r['clearance_measured_m']:.2f} m "
                f"of cover where the law's continued-profile clause "
                f"expects {float(BRIDGE_ROAD_CLEARANCE_M)} m.  Nothing "
                f"here moves the deck or the ramp; the ramp's own "
                f"surfacing profile under the span is what the number "
                f"reports.")

    if stand_down:
        _stand_down(layout, stand_down, icao)
    setattr(layout, _RECORDS, [
        {k: v for k, v in r.items() if k not in ("line", "abutments")}
        for r in records])
    setattr(layout, _PINS, {})
    sever_union = None
    if sever:
        try:
            from shapely.ops import unary_union
            sever_union = unary_union(sever)
            if sever_union.is_empty:
                sever_union = None
        except Exception:                                # pragma: no cover
            sever_union = None
    return report, sever_union


def _deck_level(layout, record):
    """The ROAD SOLVE's own level along the deck — the mean of the deck
    pieces' solved altitudes.  ``None`` before the solve has run or when
    no piece carries a value.

    2026-08-30d: the deck "sits at the road solve's own level", so this
    READS the solve; it never writes it.
    """
    _init_receiving_roles()
    vals = []
    wid = record["way_id"]
    corr = _corridor(record)
    for s in getattr(layout, "shapes", None) or ():
        # The FLAG names the piece the minter stamped; the GEOMETRY finds
        # it again after the groundside pass has re-roled it (round 1
        # measured a null deck level for exactly that reason).
        if str(getattr(s, "road_bridge_deck", "") or "") != wid:
            # The deck's own GROUND only: never the structure beneath it
            # and never a wall, or the "road level" would average the
            # very things the deck spans over.
            if (str(getattr(s, "ref", "") or "") in _BELOW_GRADE_REFS
                    or getattr(s, "role", None) not in _RECEIVING_ROLES):
                continue
            poly = getattr(s, "polygon", None)
            if poly is None or poly.is_empty:
                continue
            try:
                if poly.area <= 0.0 or poly.intersection(corr).area \
                        < DECK_PIECE_MIN_FRACTION * poly.area:
                    continue
            except Exception:                            # pragma: no cover
                continue
        vals.extend(float(a) for a in
                    (getattr(s, "node_altitudes", None) or ())
                    if a is not None)
        for attr in ("altitude", "altitude_high", "altitude_low"):
            a = getattr(s, attr, None)
            if a is not None:
                vals.append(float(a))
    if vals:
        return sum(vals) / len(vals)
    # FALLBACK, a READ not a law: with the deck's ground fragmented, no
    # single piece may reach DECK_PIECE_MIN_FRACTION of its own area
    # inside the corridor, and the level then reads null (measured at
    # LEMD rounds 3-4 for ``-2192``).  Take the deck's own ground
    # AREA-WEIGHTED over whatever lies in the corridor instead, so a
    # fragmented deck still reports the level it actually has.
    num = den = 0.0
    for s in getattr(layout, "shapes", None) or ():
        if (str(getattr(s, "ref", "") or "") in _BELOW_GRADE_REFS
                or getattr(s, "role", None) not in _RECEIVING_ROLES):
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        try:
            share = float(poly.intersection(corr).area)
        except Exception:                                # pragma: no cover
            continue
        if share <= 1.0:
            continue
        own = [float(a) for a in
               (getattr(s, "node_altitudes", None) or ()) if a is not None]
        for attr in ("altitude", "altitude_high", "altitude_low"):
            a = getattr(s, attr, None)
            if a is not None:
                own.append(float(a))
        if not own:
            continue
        num += share * (sum(own) / len(own))
        den += share
    return (num / den) if den > 0.0 else None


def _stand_down(layout, records, icao: str = "") -> None:
    """§1/§6 stand-down: the pre-law surface returns.  A deck admitted on
    BRIDGE EVIDENCE ALONE loses its pieces (today's course set never had
    them); one that would have been admitted anyway merely loses the
    flag, because today's surface keeps it."""
    ids = {r["way_id"] for r in records}
    drop = {r["way_id"] for r in records if r.get("bridge_evidence_only")}
    kept, removed = [], 0
    for s in getattr(layout, "shapes", None) or ():
        wid = str(getattr(s, "road_bridge_deck", "") or "")
        if wid and wid in ids:
            s.road_bridge_deck = ""
            if wid in drop:
                removed += 1
                continue
        kept.append(s)
    if removed:
        layout.shapes = kept
        from .road_piece_ledger import log_removal
        for _r in ():                                    # pragma: no cover
            log_removal(layout, _r, "bridge-deck stand-down")
        UI.vprint(1,
            f"  [bridge-deck] stand-down: {removed} piece(s) minted on "
            f"bridge evidence alone removed for "
            f"{sorted(drop)} — the pre-law surface stands.")


def pins_of(layout) -> dict:
    """§5: the deck values, keyed by rounded layout-metre coordinate, for
    the free-road profile pass to pin like any other end."""
    return dict(getattr(layout, _PINS, None) or {})


def records_of(layout) -> list:
    """Sidecar evidence — every candidate with its verdict, the §4
    numbers and the §6 abutment arithmetic."""
    return list(getattr(layout, _RECORDS, None) or ())


#: Smallest piece either side of a deck split worth keeping (m²).  Below
#: this the split would mint a sliver instead of a surface, so the shape
#: is left whole — the same "do not cut here" instinct
#: ``bridges._split_host_at_corridor`` encodes with its own two floors.
DECK_SPLIT_MIN_PART_M2 = 4.0

#: The families a deck split may cut.  Road and landside pavement only:
#: an AIRSIDE surface is never cut for a deck (airside is king), and a
#: deck that overlapped one would be a classification defect to report,
#: not ground to carve.
_SPLITTABLE_ROLES = ("service_road", "service_junction",
                     "groundside_pavement")


def split_shapes_at_deck(layout, icao: str = "") -> int:
    """Split every straddling road/landside surface at the deck
    footprint, so the deck's own strip arrives at the scorer as ITS OWN
    candidate (RULINGS 2026-08-30c §2/§5, round-8 instruction: "the lot
    resumes at the deck edges").

    WHY A SPLIT AND NOT A LOWER THRESHOLD.  The scorer votes per SHAPE,
    and the ground carrying a deck is normally a lot that merely
    CONTAINS the deck strip — measured at LEMD (build ``lemdr7``):
    ``shapeID 1853``, 5,134 m² total with 1,133 m² inside the deck, a
    fraction of 0.2206 against the 0.50 predicate.  Lowering the
    predicate to catch it would demote real lots; splitting the lot
    gives the strip its own vote and leaves the remainder exactly the
    lot it was.  This is the same footprint discipline the claim
    (round 4) and the ramp cut (round 6) already use — the fourth member
    of one family.

    THE SEAM.  Both parts are cut from the SAME ring and take
    nearest-neighbour resampled altitudes from it, so at the moment of
    the split the two new edges carry identical values — the split
    itself mints no step.  Any step across a deck edge afterwards is the
    §5 solve moving the strip, which is what the law asks for and what
    the census then judges.

    Returns the number of shapes split.  Idempotent in effect: a shape
    already wholly inside or outside the deck is never cut.
    """
    u = terrain_deck_union(layout)
    if u is None:
        UI.vprint(1,
            "  [bridge-deck] split: NO terrain-deck union at this pass — "
            "either no candidate survived §1/§2 or every span is "
            "object-governed; nothing to split.")
        return 0
    from .elevation import _resample_node_altitudes_nn
    from .groundside import _ring_and_altitudes
    from .layout import BuiltShape

    out: list = []
    n_split = 0
    for s in (getattr(layout, "shapes", None) or ()):
        poly = getattr(s, "polygon", None)
        role = str(getattr(s, "role", "") or "")
        if (poly is None or poly.is_empty or poly.geom_type != "Polygon"
                or role not in _SPLITTABLE_ROLES):
            out.append(s)
            continue
        try:
            inside = poly.intersection(u)
            outside = poly.difference(u)
        except Exception:                                # pragma: no cover
            out.append(s)
            continue
        in_parts = [g for g in getattr(inside, "geoms", [inside])
                    if g is not None and not g.is_empty
                    and g.geom_type == "Polygon"
                    and g.area >= DECK_SPLIT_MIN_PART_M2]
        out_parts = [g for g in getattr(outside, "geoms", [outside])
                     if g is not None and not g.is_empty
                     and g.geom_type == "Polygon"
                     and g.area >= DECK_SPLIT_MIN_PART_M2]
        if not in_parts or not out_parts:
            out.append(s)                # wholly in, wholly out, or slivers
            continue
        # A VALUELESS SHAPE STILL SPLITS.  At the mint a service_junction
        # fill carries NO ``node_altitudes`` at all — it is pure geometry
        # until the solve — so requiring values here refused every split
        # at the one moment §2 says the deck is already road.  MEASURED
        # (round 9, build ``lemdr9``): the split census saw the straddler
        # at BOTH call sites (``service_junction`` 1,179 of 5,257 m²,
        # 0.22) and split nothing, because of this gate and nothing else.
        # With no values there is nothing to resample and the parts carry
        # ``None``, exactly as the shape did.
        ring, alts = _ring_and_altitudes(s)
        has_values = bool(ring is not None and alts)
        open_ring = (ring[:-1] if (ring and ring[0] == ring[-1]) else ring) \
            if has_values else None
        made = []
        for part in in_parts + out_parts:
            na = None
            if has_values:
                na = _resample_node_altitudes_nn(
                    part, open_ring, list(alts),
                    interior_edge_project=True)
                if na is None:
                    made = []
                    break
            made.append(BuiltShape(
                polygon=part, role=s.role, ref=s.ref, node_altitudes=na,
                synthesised_road_corridor=getattr(
                    s, "synthesised_road_corridor", False),
                road_bridge_deck=getattr(s, "road_bridge_deck", "")))
        if not made:
            out.append(s)
            continue
        out.extend(made)
        n_split += 1
    # ALWAYS SAY WHAT WAS THERE.  Round 8 returned 0 in silence and cost
    # a whole round to explain; the census law (RULINGS 2026-08-30l) is
    # about knowing every consumer, and a pass that finds nothing must
    # say what it looked at.
    _touch = []
    for s2 in (getattr(layout, "shapes", None) or ()):
        p2 = getattr(s2, "polygon", None)
        if p2 is None or p2.is_empty:
            continue
        try:
            share = float(p2.intersection(u).area)
        except Exception:                                # pragma: no cover
            continue
        if share < 1.0:
            continue
        _touch.append((share, float(p2.area),
                       str(getattr(s2, "role", "") or ""),
                       str(getattr(s2, "ref", "") or "")))
    _touch.sort(reverse=True)
    UI.vprint(1,
        f"  [bridge-deck] split census: {len(_touch)} shape(s) meet the "
        f"deck union; {n_split} split.  " + "; ".join(
            f"{r or '-'}/{f or '-'} {sh:,.0f} of {a:,.0f} m² "
            f"({sh / a:.2f})" for sh, a, r, f in _touch[:6]))
    # §3/30m INVARIANT REPORT: the deck's ground must never wear an
    # AIRSIDE role (owner 2026-08-30m).  Airside is king, so this pass
    # never carves one — it NAMES it, so the upstream pass that minted
    # the role is fixed there and not worked around here.
    _AIRSIDE = ("apron", "junction", "runway", "runway_crossing",
                "primary_parallel", "secondary_parallel", "stub",
                "cross_connector")
    _bad = [(sh, a, r, f) for sh, a, r, f in _touch
            if r in _AIRSIDE and sh >= DECK_PIECE_MIN_FRACTION * a]
    for sh, a, r, f in _bad:
        UI.vprint(1,
            f"  [bridge-deck] 30m VIOLATION: a shape {sh / a:.0%} inside "
            f"the deck carries the AIRSIDE role {r!r} (ref {f or '-'}, "
            f"{a:,.0f} m²).  The deck's ground is road by §2 from mint; "
            f"the upstream pass that re-roled it is the defect.  Airside "
            f"is king: nothing here carves or re-roles it.")
    if n_split:
        layout.shapes = out
        UI.vprint(1,
            f"  [bridge-deck] §2/§5: {n_split} surface(s) split at the "
            f"road bridge deck before the scorer votes — the deck's strip "
            f"is its own candidate and the lot resumes at both deck "
            f"edges.  Both sides take resampled values from the same "
            f"ring, so the split mints no step of its own.")
    return n_split
