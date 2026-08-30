"""THE ROAD BRIDGE DECK — RULINGS 2026-08-30c §1–§6.

    A MAPPED ROAD BRIDGE OVER A BELOW-GRADE STRUCTURE IS A DECK, NOT
    CUTTABLE PAVEMENT.

One home for the whole law, because its six clauses fire in four
different phases and a reader who has to reassemble them from four call
sites cannot check the law against the code:

* **§1 Scope** — :func:`publish_candidates` (phase 4, before the corridor
  course set is built) and :func:`confirm_and_pin` (phase 6, after the
  tunnel pass has emitted).  The tag is the only trigger: a feed way
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
* **§4 Where it sits** — :func:`confirm_and_pin` values the deck at the
  highest EMITTED surface beneath the span plus
  ``config.BRIDGE_ROAD_CLEARANCE_M``.  AIRSIDE IS KING is the DIRECTION
  of the constraint: nothing here ever writes the structure beneath.
* **§5 The approaches** — :func:`pins_of` hands the deck value to
  ``free_road_profile.solve_free_road_profiles`` as an ordinary pin, so
  the chain reaches it at ``SERVICE_ROAD_MAX_GRADE`` like any other
  pinned end.
* **§6 Refusal, loudly** — a deck whose two abutment values cannot both
  be reached at the road cap is refused at candidate time with a named
  line and sidecar evidence, and :func:`_stand_down` leaves the pre-law
  surface.  The gap-spine-bridge stand-down precedent (owner
  2026-08-27): the misplaced object is the bridge.

WHY CANDIDACY IS PREDICTED AND THEN CONFIRMED.  §1 asks whether the span
crosses a structure THIS BUILD EMITTED, and the tunnel pass emits in
phase 6 — long after the course set is minted in phase 4.  Admitting
every bridge-tagged way and sorting it out later is NOT equivalent: a
way minted in phase 4 is a solver variable by phase 5, so a way over
nothing would perturb a surface §1 says it must leave alone.  So
candidacy is decided in phase 4 against the extent the tunnel pass CAN
reach — the mapped bore corridor extended along its own tangents by the
portal walk's own arm cap — and §1 proper is decided in phase 6 against
what was actually emitted.  Over-prediction is safe (the candidate
stands down and today's surface returns); under-prediction would silently
lose a deck, so the prediction is deliberately generous.
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


def is_deck_shape(shape) -> bool:
    """§3: this piece is a ROAD BRIDGE DECK — no tunnel-ramp cut, no
    clearance annulus and no covered-span suppression may remove it."""
    return bool(getattr(shape, "road_bridge_deck", "") or "")


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


def _below_grade_shapes(layout):
    out = []
    for s in getattr(layout, "shapes", None) or ():
        if str(getattr(s, "ref", "") or "") not in _BELOW_GRADE_REFS:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        alts = [a for a in (getattr(s, "node_altitudes", None) or ())
                if a is not None]
        if not alts:
            a = getattr(s, "altitude", None)
            if a is None:
                continue
            alts = [float(a)]
        out.append((poly, max(float(a) for a in alts), s))
    return out


def _receiving_value(layout, point, deck_ids, reach_m: float = 25.0):
    """§5's "the receiving surface's own value" at an abutment: the
    nearest emitted pavement that is NOT part of this deck."""
    best = None
    for s in getattr(layout, "shapes", None) or ():
        if id(s) in deck_ids or is_deck_shape(s):
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        if getattr(s, "role", None) not in _RECEIVING_ROLES:
            continue
        try:
            d = float(poly.distance(point))
        except Exception:                                # pragma: no cover
            continue
        if d > reach_m or (best is not None and d >= best[0]):
            continue
        alts = [a for a in (getattr(s, "node_altitudes", None) or ())
                if a is not None]
        if not alts:
            a = getattr(s, "altitude", None)
            if a is None:
                continue
            alts = [float(a)]
        best = (d, sum(float(a) for a in alts) / len(alts), s)
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


def confirm_and_pin(layout, icao: str = "") -> dict:
    """§1 confirmation, §4 valuation and §6 refusal, in the one slot
    where all three can mean something: after the tunnel pass has
    emitted and before the free-road profile solves.

    Returns a report dict; the per-deck records are published on the
    layout for the sidecar."""
    _init_receiving_roles()
    report = {"candidates": 0, "confirmed": 0, "unconfirmed": 0,
              "refused": 0, "pins": 0}
    records = candidates_of(layout)
    if not records:
        setattr(layout, _RECORDS, [])
        return report
    from .config import BRIDGE_ROAD_CLEARANCE_M, SERVICE_ROAD_MAX_GRADE
    from shapely.geometry import Point

    beneath_all = _below_grade_shapes(layout)
    deck_ids = {id(s) for s in (getattr(layout, "shapes", None) or ())
                if is_deck_shape(s)}
    pins: dict = {}
    stand_down: list = []
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
        deck_value = float(top) + float(BRIDGE_ROAD_CLEARANCE_M)
        r["structures_beneath"] = len(beneath)
        r["highest_beneath_m"] = round(float(top), 3)
        r["deck_value_m"] = round(deck_value, 3)

        # ── §6: can BOTH abutment values be reached at the road cap? ──
        line = r["line"]
        try:
            span_end = float(line.length)
            stations = []
            for _t, s in beneath:
                inter = s.polygon.intersection(corr)
                coords = (list(inter.exterior.coords)
                          if getattr(inter, "exterior", None) is not None
                          else [c for g in getattr(inter, "geoms", ())
                                for c in g.exterior.coords])
                for c in coords:
                    stations.append(line.project(Point(c)))
            lo_station = min(stations) if stations else 0.0
            hi_station = max(stations) if stations else span_end
        except Exception:                                # pragma: no cover
            lo_station, hi_station, span_end = 0.0, 0.0, 0.0

        cap = float(SERVICE_ROAD_MAX_GRADE)
        checks = []
        for label, (_nid, ll), run in (
                ("west", r["abutments"][0], max(lo_station, 0.0)),
                ("east", r["abutments"][1],
                 max(span_end - hi_station, 0.0))):
            try:
                from .bridges import _local_meter_projections
                to_m, _ = _local_meter_projections(layout.anchor)
                p = Point(*to_m(ll[1], ll[0]))
            except Exception:                            # pragma: no cover
                continue
            hit = _receiving_value(layout, p, deck_ids)
            if hit is None:
                continue
            need = abs(deck_value - hit[1])
            allowed = cap * run
            checks.append({
                "side": label, "receive_m": round(hit[1], 3),
                "run_m": round(run, 2),
                "required_m": round(need, 3),
                "allowed_m": round(allowed, 3),
                "grade_needed": (round(need / run, 5) if run > 0 else None),
            })
        r["abutment_checks"] = checks
        infeasible = [c for c in checks
                      if c["required_m"] > c["allowed_m"] + 1e-9]
        if infeasible:
            r["verdict"] = "refused"
            r["reason"] = "§6: abutment unreachable at the road cap"
            report["refused"] += 1
            stand_down.append(r)
            for c in infeasible:
                UI.vprint(1,
                    f"  [bridge-deck] REFUSED {r['way_id']} (§6): its "
                    f"{c['side']} abutment receives {c['receive_m']:.2f} m "
                    f"and the §4 deck value is {deck_value:.2f} m "
                    f"(highest emitted surface beneath the span "
                    f"{top:.2f} m + {float(BRIDGE_ROAD_CLEARANCE_M)} m) — "
                    f"{c['required_m']:.2f} m over {c['run_m']:.1f} m is "
                    f"{100.0 * (c['grade_needed'] or 0):.1f} %, past the "
                    f"{100.0 * cap:.0f} % road cap "
                    f"({c['allowed_m']:.2f} m allowed).  The misplaced "
                    f"object is the bridge: it is NOT built and the "
                    f"pre-law surface stands.")
            continue

        r["verdict"] = "confirmed"
        report["confirmed"] += 1
        UI.vprint(1,
            f"  [bridge-deck] {r['way_id']} CONFIRMED (§1): "
            f"{len(beneath)} emitted below-grade shape(s) beneath the "
            f"span, highest {top:.2f} m — deck pinned at "
            f"{deck_value:.2f} m (§4 = that surface + "
            f"{float(BRIDGE_ROAD_CLEARANCE_M)} m); the structure beneath "
            f"is untouched.")
        for s in (getattr(layout, "shapes", None) or ()):
            if str(getattr(s, "road_bridge_deck", "") or "") != r["way_id"]:
                continue
            poly = getattr(s, "polygon", None)
            if poly is None or poly.is_empty:
                continue
            try:
                for x, y in poly.exterior.coords:
                    pins[(round(float(x), 3), round(float(y), 3))] = \
                        deck_value
            except Exception:                            # pragma: no cover
                continue

    if stand_down:
        _stand_down(layout, stand_down, icao)
    setattr(layout, _PINS, pins)
    setattr(layout, _RECORDS, [
        {k: v for k, v in r.items() if k not in ("line", "abutments")}
        for r in records])
    report["pins"] = len(pins)
    return report


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
