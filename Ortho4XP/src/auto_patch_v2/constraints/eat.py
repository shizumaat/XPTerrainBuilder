"""THE END-AROUND TAXIWAY CEILING — the anchor rect as a v2 HARD PIN
family (owner RULINGS 2026-09-13j item 2, ruled 2026-09-13q item 2; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §36).

THE LAW.  An end-around taxiway loops BEYOND a runway end and crosses the
extended centreline, so the aircraft standing on it stands directly under
the departure (FAA 40:1 from the DER) / take-off-climb (EASA 2 % from a
60 m inner edge) surface — and it is the TAIL, not the wingtip, that
penetrates.  The pavement must therefore sit a whole tail height below the
surface::

    ceiling(D) = end_z + max(0, D − setback) · slope − tail_height

which is NORMALLY BELOW the runway end (KATL taxiway Victor ≈ −9 m; KCLT's
18C crossing at D ≈ 378-399 m ⇒ 216.6-217.1 m against a runway end of
227.25).  v1 carried this whole law (``grade_law.eat_pavement_ceiling``,
``elevation_per_surface/solver_primitives._build_eat_anchor_rect_pins``,
``docs/specs/eat-anchor-rect-spec.md`` + ``eat-recognition-scoping-spec.md``);
``auto_patch_v2`` had NONE of it, and read KCLT's crossing at the runway
end +0.9 m — the "pre-law, FLAT" state the v1 spec named as the defect.

THE ENCODING IS A HARD ANCHOR, NOT A LAW EDGE (v1's own lesson).  v1's
first implementation hung one-sided pavement↔pavement interval edges on
the governed nodes; their negative slab weights blew the reach-envelope
Dijkstra up (KCLT killed at 15 min / 20.3 GB).  The RECT — the corridor
about the extended centreline at the runway's DECLARED half width,
intersected with taxi-family / apron pavement beyond ``min_crossing_m`` —
is instead PINNED FLAT at the regulation value, and the surrounding taxi
law grades the ramps to it.  In v2 that is literally a ``Pin``: the
reduction (``solve/rows._reduce``) takes a pinned vertex OUT of the free
columns, so the rect holds EXACTLY and the taxi-family ``Diff`` rows either
side ARE the ramp (targets at the taxi caps, under the hard 5 % pavement
ceiling).  No new solver machinery, no negative edge anywhere.

RECOGNITION (v1's scoping v2, owner ruling 2026-08-25c/25d — ported whole,
because recognition that silently narrows is indistinguishable from
recognition that broke; every refusal is NAMED in :data:`RECTS`):

* the runway is transport-category (``min_runway_code_number``);
* ``s ≥ min_crossing_m`` (300 m) and ``|q| ≤`` the runway's declared half
  width — closer in, the pavement is an ordinary runway-end connector and
  the ceiling would be violently infeasible (−18.6 m at 60 m, code E);
* ONE crossing per cluster by along-corridor gap (``segment_gap_m``); a
  rect — or a whole FACE — longer than ``rect_max_along_m`` along ``s``
  RUNS ALONG the corridor and is another facility, refused whole;
* clause 2, THE FAR BOUND: a rect starting beyond ``min(D_clear,
  max_crossing_m)`` is not recognised.  ``D_clear = setback + tail/slope``
  is the regulation's OWN geometry (past it the surface has cleared the
  tallest tail and binds nothing), not a tunable;
* clause 1, THE ROUTED WRAP: a TAXI ROUTE (apt.dat row 1202, the aircraft
  network — ground-vehicle routes carry no tail and are row 1206, a
  different input) must cross the extended centreline within the rect's own
  extent widened by ``segment_gap_m``.  An apron lying under a projected
  centreline is not an end-around taxiway (LEMD's 149 false pins);
* clause 3, CUT-ONLY: the rect is stamped at ONE value, so "does it cut?"
  is a question about the RECT.  Where that value sits ABOVE the
  pavement's unconstrained reference (its DEM sample) EVERYWHERE it would
  stamp, it would LIFT pavement into the air and pins nothing.

Where two ends' corridors cover one node the LOWER value wins (the most
restrictive surface governs, deterministically).  A node another family
has already PINNED — a CIFP threshold, a crossing anchor, a seam, a water
datum, a structure datum — or one welded into a rigid ``Flat`` group is
never overridden: :func:`withdraw_against_senior` is the post-pass
``constraints/__init__`` runs for it, the same shape as the water and
structure-datum withdrawals beside it.

THE CONSTANTS ARE THE LAW TABLES' (``law/rulesets.toml``): the authority's
``slope`` / ``setback_m`` in ``[faa.eat]`` / ``[icao.eat]``, everything
region-invariant in ``[common.eat]``.  ``tests/auto_patch_v2/test_law_tables.py``
asserts them equal to v1's ``config.py`` values, the ramp-cap precedent
(RULINGS 2026-09-12p).
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Flat, Pin, Row, Source
from ..model.planar import PlanarMap
from .precedence import view
from .runway_chord import _chords, _with_knots, runway_crossings

__all__ = ["eat_pins", "eat_rects", "withdraw_against_senior", "eat_ceiling_offset",
           "eat_clear_distance", "eat_reach_plan", "withdraw_trend_over_reach",
           "GEN", "RULING", "RECTS", "STATS"]

GEN = "eat_anchor_rect"
RULING = ("rulesets.eat ceiling (owner RULINGS 2026-09-13j item 2; "
          "spec §36: the end-around taxiway sits a tail height below the "
          "departure surface)")

#: The generator's own statistics, published beside its row count by
#: ``constraints/__init__.generate`` as ``eat_anchor_rect.<key>``.
STATS: dict[str, dict] = {}

#: EVERY candidate rect this run judged — accepted AND refused, each with
#: the end it belongs to, its ``D`` extent, its value and (when refused)
#: the clause that refused it.  Recognition that narrows silently is
#: indistinguishable from recognition that broke, so the verdicts are
#: published rather than counted away.  Rebuilt on every call.
RECTS: list[dict[str, _t.Any]] = []

#: The APRON joins the taxi family here exactly as in v1
#: (``solver_primitives.EAT_CEILING_ROLES``): an end-around taxiway is
#: built from taxi-family pavement, and the apron it widens into carries
#: the same tail.  Runway, structure and groundside roles are excluded —
#: the runway profile is senior (an EAT ceiling must never bend it) and a
#: service road carries no aircraft.
EXTRA_ROLES = ("apron",)


def eat_clear_distance(slope: float, setback_m: float,
                       tail_height_m: float) -> float:
    """``D_clear`` — the distance beyond the end at which the surface has
    risen a WHOLE TAIL above the runway end, i.e. the root of the ceiling
    (v1 ``grade_law.eat_ceiling_clear_distance``)::

        ceiling(D_clear) = 0   ⇔   D_clear = setback + tail / slope

    NOT a tuning constant: it is the inverse of the law function, from the
    very same slope / setback / tail.  Worked: FAA code E ⇒ 0 + 20.1/0.025
    = 804 m; EASA code F ⇒ 60 + 24.4/0.02 = 1280 m.  A non-positive slope
    (no surface at all) yields ``inf`` — a missing bound is honest, never a
    silent refusal."""
    s = float(slope)
    if s <= 0.0:
        return float("inf")
    return float(setback_m) + float(tail_height_m) / s


def eat_ceiling_offset(distance_beyond_end_m: float, slope: float,
                       setback_m: float, tail_height_m: float) -> float:
    """THE LAW, as an offset (m) relative to the runway-END elevation (v1
    ``grade_law.eat_pavement_ceiling``).

    Deliberately NOT clamped at 0: the depression is the entire point.
    Only the SURFACE's own rise is floored, so a point inside the setback
    reads the inner-edge height rather than a fictitious below-DER
    surface."""
    rise = max(0.0, float(distance_beyond_end_m) - float(setback_m)) * float(slope)
    return rise - float(tail_height_m)


def _ends(airport: Airport, law: Law, chords, rec, planar: PlanarMap, vw,
          rwy_vertices: _t.AbstractSet[int]
          ) -> tuple[list[dict], tuple[int, int, int]]:
    """One EAT frame per DEPARTURE end of every recognised runway: the
    row-100 endpoint, the outward unit vector, the runway's declared half
    width, the tail height its code letter carries and the RUNWAY-END
    ELEVATION the ceiling is referenced to.

    THE ANCHOR (v1's own discipline — the end's SOLVED profile value, read
    off the frozen-nearest pavement ring vertex, never the published
    threshold elevation).  v2 states that value BEFORE the solve as the
    runway's own TARGET PROFILE: the trend / chord through its two CIFP
    thresholds where it has them (``runway_chord``), and otherwise — a
    runway with fewer than two pins "keeps the DEM as its target", never
    an invented value (plan §2) — the DEM at the runway-family vertex
    nearest the end.  KCLT's 18C/36C is the second case: CIFP carries no
    threshold for either end, and v1's anchor there was the solved runway
    ring, which IS the DEM-fitted profile.  ``anchor`` records which."""
    out: list[dict] = []
    n_small = n_no_anchor = n_no_letter = 0
    for rw in airport.runways:
        code = rw.code_number
        if code is None or int(code) < int(rec.min_runway_code_number):
            n_small += 1
            continue
        tail = rec.tail_height_m.value(code_letter=rw.code_letter)
        if tail is None:
            n_no_letter += 1
            continue
        chord = chords.get(rw.id)
        for k in (0, 1):
            p0 = rw.ends[k].xy
            q0 = rw.ends[1 - k].xy
            dx, dy = p0[0] - q0[0], p0[1] - q0[1]
            n = math.hypot(dx, dy)
            if n <= 0.0:
                continue
            if chord is not None:
                end_z, anchor = float(chord.z(chord.station(*p0))), "chord"
            else:
                near = _nearest(vw, rwy_vertices, p0)
                z = None if near is None else planar.vertices[near].dem_z
                if z is None:
                    # unreadable: a pin at a guessed datum would
                    # masquerade as regulation
                    n_no_anchor += 1
                    continue
                end_z, anchor = float(z), "dem"
            out.append({
                "runway": rw.id,
                "end": rw.ends[k].name,
                "p0": (float(p0[0]), float(p0[1])),
                "outward": (dx / n, dy / n),
                "half_width_m": float(rw.width_m) / 2.0,
                "tail_height_m": float(tail),
                "end_z": end_z,
                "anchor": anchor,
            })
    return out, (n_small, n_no_anchor, n_no_letter)


def _nearest(vw, vertices: _t.AbstractSet[int],
             xy: tuple[float, float]) -> int | None:
    """The vertex of ``vertices`` nearest ``xy`` (the runway ring vertex
    v1 read its end elevation off)."""
    best = None
    best_d = float("inf")
    for v in vertices:
        (x, y) = vw.xy[v]
        d = (x - xy[0]) ** 2 + (y - xy[1]) ** 2
        if d < best_d:
            best, best_d = v, d
    return best


def _project(spec: dict, x: float, y: float) -> tuple[float, float]:
    """``(s, q)`` in one end's EAT frame: ``s`` along the extended
    centreline beyond the row-100 endpoint (negative = still inside the
    runway), ``q`` the signed lateral offset from it."""
    p0 = spec["p0"]
    nx, ny = spec["outward"]
    dx, dy = float(x) - p0[0], float(y) - p0[1]
    return (dx * nx + dy * ny, -dx * ny + dy * nx)


def _crossing_stations(airport: Airport, spec: dict) -> list[float]:
    """The stations at which a TAXI ROUTE crosses this end's extended
    centreline — clause 1's geometry half.  A crossing is a SIGN CHANGE of
    ``q`` between the two ends of one row-1202 edge; a route that merely
    touches ``q == 0`` is not a crossing and is not reported (recognition
    must under-claim)."""
    nodes = airport.taxi_nodes
    out: list[float] = []
    for e in airport.taxi_edges:
        a, b = nodes.get(e.a), nodes.get(e.b)
        if a is None or b is None:
            continue
        sa, qa = _project(spec, *a.xy)
        sb, qb = _project(spec, *b.xy)
        if (qa < 0.0 <= qb) or (qb < 0.0 <= qa):
            denom = qb - qa
            t = (-qa / denom) if denom else 0.0
            out.append(sa + t * (sb - sa))
    out.sort()
    return out


def eat_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One hard ``Pin`` per governed EAT vertex, at the regulation value of
    the rect it belongs to (module docstring)."""
    RECTS.clear()
    STATS["eat_pins"] = stats = {
        "ends": 0, "runways_below_code": 0, "ends_without_anchor": 0,
        "runways_without_letter": 0, "rects_accepted": 0,
        "refused_far_bound": 0, "refused_no_wrap": 0, "refused_no_cut": 0,
        "refused_along_corridor": 0, "pins": 0,
    }
    surface = getattr(law.ruleset, "eat", None)
    if surface is None:                    # the authority states no surface
        return []
    rec = law.tables.common.eat
    vw = view(planar, law)
    roles = set(law.tables.precedence.taxi_family.members) | set(EXTRA_ROLES)
    faces = [f for f in vw.faces_of_role(roles)]
    if not faces:
        return []
    # the runway's OWN target profile, re-fit through any crossing knot —
    # the same chord ``runway_chord`` hands every runway-family vertex, so
    # the anchor the ceiling is referenced to is the surface the patch will
    # actually render (v1's anchor discipline, one derivation)
    straight, _ = _chords(planar, law, airport)
    chords = _with_knots(
        straight, runway_crossings(planar, law, airport, straight))
    rwy = set(law.tables.precedence.runway_family.members)
    rwy_vertices: set[int] = set()
    for f in planar.faces.values():
        if f.role in rwy:
            for ring in (f.ring, *f.holes):
                rwy_vertices.update(planar.ring_vertices(ring))
    specs, (n_small, n_no_anchor, n_no_letter) = _ends(
        airport, law, chords, rec, planar, vw, rwy_vertices)
    stats["ends"] = len(specs)
    stats["runways_below_code"] = n_small
    stats["ends_without_anchor"] = n_no_anchor
    stats["runways_without_letter"] = n_no_letter
    if not specs:
        return []

    min_s = float(rec.min_crossing_m)
    gap = float(rec.segment_gap_m)
    max_along = float(rec.rect_max_along_m)
    cut_tol = 0.01                 # the anchor envelope's own materiality

    pins: dict[int, float] = {}
    rect_of: dict[int, tuple[int, str, str]] = {}
    for spec in specs:
        half = spec["half_width_m"]
        d_clear = eat_clear_distance(surface.slope, surface.setback_m,
                                     spec["tail_height_m"])
        cap = float(rec.max_crossing_m)
        d_far, far_rule = ((d_clear, "D_clear") if d_clear <= cap
                           else (cap, "max_crossing_m"))
        cross_s = _crossing_stations(airport, spec)
        members: list[tuple[float, int]] = []
        seen: set[int] = set()
        for f in faces:
            got: list[tuple[float, int]] = []
            for ring in [vw.rings[f.id], *vw.holes[f.id]]:
                for v in ring:
                    s, q = _project(spec, *vw.xy[v])
                    if s < min_s or abs(q) > half:
                        continue
                    if v not in seen:
                        got.append((s, v))
            if not got:
                continue
            # a FACE whose governed vertices span more than the crossing
            # cap RUNS ALONG the corridor (a decimated long rect carries
            # vertices only at its far-apart ends, so the cluster check
            # below alone would read it as two short crossings)
            if max(s for s, _v in got) - min(s for s, _v in got) > max_along:
                stats["refused_along_corridor"] += 1
                RECTS.append({"end": spec["end"], "runway": spec["runway"],
                              "face": f.id, "accepted": False,
                              "reason": "the FACE runs along the corridor "
                                        f"({max(s for s, _v in got) - min(s for s, _v in got):.0f} m "
                                        f"> rect_max_along_m {max_along:.0f})"})
                continue
            seen.update(v for _s, v in got)
            members.extend(got)
        if not members:
            continue
        members.sort()
        start = 0
        for k in range(1, len(members) + 1):
            if k < len(members) and members[k][0] - members[k - 1][0] <= gap:
                continue
            seg, start = members[start:k], k
            s_lo, s_hi = seg[0][0], seg[-1][0]
            d_mid = 0.5 * (s_lo + s_hi)
            value = spec["end_z"] + eat_ceiling_offset(
                d_mid, surface.slope, surface.setback_m, spec["tail_height_m"])
            row = {"end": spec["end"], "runway": spec["runway"],
                   "anchor": spec["anchor"],
                   "d_lo": round(s_lo, 1), "d_hi": round(s_hi, 1),
                   "d_mid": round(d_mid, 1), "vertices": len(seg),
                   "value_m": round(value, 3), "end_z_m": round(spec["end_z"], 3),
                   "accepted": True, "reason": ""}
            if s_hi - s_lo > max_along:
                stats["refused_along_corridor"] += 1
                row.update(accepted=False,
                           reason=f"runs along the corridor ({s_hi - s_lo:.0f} m "
                                  f"> rect_max_along_m {max_along:.0f})")
                RECTS.append(row)
                continue
            if s_lo > d_far:
                stats["refused_far_bound"] += 1
                row.update(accepted=False,
                           reason=(f"beyond {far_rule} = {d_far:.0f} m "
                                   f"(rect starts at {s_lo:.0f} m)"))
                RECTS.append(row)
                continue
            if not any(s_lo - gap <= c <= s_hi + gap for c in cross_s):
                stats["refused_no_wrap"] += 1
                row.update(accepted=False,
                           reason=("no routed wrap: "
                                   f"{len(cross_s)} taxi-route crossing(s) at "
                                   f"this end, none within "
                                   f"[{s_lo - gap:.0f},{s_hi + gap:.0f}] m"))
                RECTS.append(row)
                continue
            refs = [planar.vertices[v].dem_z for _s, v in seg
                    if planar.vertices[v].dem_z is not None]
            if refs and value >= max(refs) - cut_tol:
                stats["refused_no_cut"] += 1
                row.update(accepted=False,
                           reason=("the regulation is ABOVE the reference "
                                   f"everywhere (+{value - max(refs):.1f} m: "
                                   f"value {value:.2f} vs highest DEM "
                                   f"{max(refs):.2f} over {len(refs)} node(s))"))
                RECTS.append(row)
                continue
            stats["rects_accepted"] += 1
            RECTS.append(row)
            rid = stats["rects_accepted"]
            for _s, v in seg:
                prev = pins.get(v)
                if prev is None or value < prev:
                    pins[v] = float(value)
                    rect_of[v] = (rid, spec["end"], spec["runway"])
    stats["pins"] = len(pins)
    return [Pin(v, z, Source(GEN, RULING,
                             (f"vertex:{v}", f"rect:{rect_of[v][0]}",
                              f"end:{rect_of[v][1]}",
                              f"runway:{rect_of[v][2]}",
                              f"value:{z:.3f}")))
            for v, z in sorted(pins.items())]


def eat_rects(planar: PlanarMap, cs) -> list[dict[str, _t.Any]]:
    """THE ACCEPTED RECTS, FOR THE CENSUS (the sidecar key ``eat_rects``).

    Read off the FINAL pin rows — after :func:`withdraw_against_senior` —
    so the instrument prices exactly the vertices the solve pinned and a
    lawfully withdrawn vertex is never reported as a violation (the
    lockstep discipline: a reader exempt for the reason the emitter
    skipped).  One record per rect: its end, its runway, its regulation
    value and the ``[lat, lon]`` of every vertex it governs."""
    by_rect: dict[int, dict[str, _t.Any]] = {}
    for p in cs.pins:
        if p.source.generator != GEN:
            continue
        tags = dict(t.split(":", 1) for t in p.source.inputs)
        rid = int(tags.get("rect", 0))
        rec = by_rect.setdefault(rid, {
            "rect": rid, "end": tags.get("end", ""),
            "runway": tags.get("runway", ""),
            "value_m": round(float(p.z), 4), "vertices": []})
        key = planar.vertices[p.v].key
        rec["vertices"].append([key[0], key[1]])
    return [by_rect[k] for k in sorted(by_rect)]


def withdraw_against_senior(rows: list[Row]) -> tuple[list[Row], int]:
    """A NODE THAT IS ALREADY HARD IS NEVER OVERRIDDEN (v1
    ``_build_eat_anchor_rect_pins``: "the runway profile and the seam law
    outrank the rect").

    v2's reduction fixes a vertex from the LAST ``Pin`` it reads, so two
    pins on one vertex would resolve by generator ORDER — silently, and the
    EAT would win wherever it ran last.  This post-pass states the
    precedence instead: an EAT pin is withdrawn where ANY other generator
    pins the same vertex, or where the vertex is welded into a rigid
    ``Flat`` group (a pad / deck plate is ONE value its whole group carries,
    so pinning one member would stamp the regulation across the group).

    Returns the rows and the number withdrawn.  The same shape as
    :func:`constraints.water_exempt` / ``structures.reconcile_datums``."""
    senior = {r.v for r in rows
              if isinstance(r, Pin) and r.source.generator != GEN}
    for r in rows:
        if isinstance(r, Flat):
            senior.update(r.group)
    if not senior:
        return rows, 0
    out: list[Row] = []
    n = 0
    for r in rows:
        if (isinstance(r, Pin) and r.source.generator == GEN
                and r.v in senior):
            n += 1
            continue
        out.append(r)
    return out, n


# ── §36 (5) THE RAMP REACH IS DERIVED; THE TREND YIELDS ────────────────
# (Fable 2026-09-13, owner RULINGS 2026-09-13aa)
#
# Lane ``v2eat`` measured the six ring edges off the pinned feet at
# 2.37-3.87 % over 28.6-59.1 m against the 1.5 % taxi cap.  The mechanism
# was named in that lane's own consumer census, not guessed: the ramp's
# free neighbours keep a ``taxi_trend`` DEM target (``[design] taxi_trend``
# 30) against the taxi cap (``law`` 300), so the least-squares solve buys
# ~1 % of grade with trend residual rather than running the ramp OUT along
# the loop.  §31 settles which of the two is law — a 3.9 % taxiway is a
# slope a pilot feels; the DEM is the unreliable witness — so the trend
# YIELDS, and it yields by being WITHDRAWN rather than outweighed: a
# re-weighting would still trade, and the trade is what is wrong.
#
# THE REACH IS DERIVED, NEVER TUNED.  From each pinned foot the ramp runs
# back along the EAT loop's OWN centreline — the routed wrap the rect was
# recognised on, read through ``taxi_trend.taxi_chains`` so the withdrawal
# and the row it withdraws share one station frame — until the loop's
# DEM-fitted profile is reached at no more than the taxi longitudinal cap:
#
#     reach = |value − the loop's profile at the foot| / cap
#
# (KCLT: ~9 m / 0.015 ~ 600 m per side, which the end-around loop
# affords).  Over that reach the loop's vertices — the chain's own and
# every vertex of the faces that chain speaks for, so THE LOOP'S
# TRANSVERSE ROWS CARRY ITS SHOULDERS WITH IT — carry no trend target at
# all.  Where the loop is too short to ramp lawfully the crossing KEEPS
# the regulation value (a ``Pin`` is not negotiable) and the overrun is
# NAMED in the report under the taxi family, never left as a silent
# 3.9 %.
#
# THE APRON TREND YIELDS ON THE SAME TERMS.  ``apron_trend`` claims a
# vertex the taxi trend does not hold (``apron_trend.taxi_held``); a
# withdrawal that dropped only the taxi channel would hand the same DEM
# pull back at ``[design] apron_trend``.  One withdrawal, both channels —
# which is also why it runs AFTER both are published (``pipeline/build``),
# so neither claim is re-opened by the other's absence.

#: The reach withdrawal's own record, published as ``report.load.eat_reach``.
REACH: dict[str, _t.Any] = {}


def _chain_frames(pm: PlanarMap, chains) -> list[dict[str, _t.Any]]:
    """Per chain, the segment arrays a point is projected onto: the
    segment starts, the segment vectors, their squared lengths and the
    stations of both endpoints (the frame ``taxi_trend._face_extension``
    projects the face's vertices in)."""
    out = []
    for c in chains:
        xy = [pm.vertices[v].xy for v in c.vertices]
        A = [(float(p[0]), float(p[1])) for p in xy[:-1]]
        D = [(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))
             for a, b in zip(xy[:-1], xy[1:])]
        LL = [(dx * dx + dy * dy) or 1.0 for dx, dy in D]
        out.append({"A": A, "D": D, "LL": LL,
                    "S0": list(c.stations[:-1]), "S1": list(c.stations[1:]),
                    "s_lo": c.stations[0], "s_hi": c.stations[-1]})
    return out


def _project_chain(frame: dict, xy: tuple[float, float]) -> tuple[float, float]:
    """``(station, distance)`` of ``xy`` on one chain frame."""
    best_d2 = float("inf")
    best_s = 0.0
    px, py = float(xy[0]), float(xy[1])
    for (ax, ay), (dx, dy), ll, s0, s1 in zip(
            frame["A"], frame["D"], frame["LL"], frame["S0"], frame["S1"]):
        t = ((px - ax) * dx + (py - ay) * dy) / ll
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        rx, ry = px - (ax + t * dx), py - (ay + t * dy)
        d2 = rx * rx + ry * ry
        if d2 < best_d2:
            best_d2, best_s = d2, s0 + t * (s1 - s0)
    return best_s, math.sqrt(best_d2)


def eat_reach_plan(pm: PlanarMap, law: Law, airport: Airport
                   ) -> dict[str, _t.Any]:
    """THE RAMP REACH, PER PINNED FOOT (§36 (5), module block above).

    Returns ``{"withdraw": set[int], "feet": [...], "short": [...],
    "chains": n}``: the vertices whose trend target the EAT withdraws, one
    record per pinned foot (its loop, its drop, its cap, its reach and the
    loop length it actually has either side), and the feet whose loop is
    TOO SHORT with the grade the ramp is forced to instead — the report
    the law owes rather than a silent grade break.

    Derived from the pins the generator would mint on this very map, so
    the withdrawal and the pin cannot disagree.  A pin later withdrawn
    against a senior authority (:func:`withdraw_against_senior`) leaves
    its reach withdrawn: those vertices are then FREE rather than trend-
    pulled, which is the conservative direction (nothing is pulled to a
    ground the senior authority has already overruled).  KCLT withdraws 0
    such pins."""
    plan: dict[str, _t.Any] = {"withdraw": set(), "feet": [], "short": [],
                               "chains": 0, "pins": 0}
    if not (pm.taxi_trend_z or pm.apron_trend_z):
        return plan
    rows = eat_pins(pm, law, airport)
    if not rows:
        return plan
    from .taxi_trend import chain_of_face, taxi_chains
    chains = taxi_chains(pm, law)
    if not chains:
        return plan
    owner = chain_of_face(pm, law, chains)
    frames = _chain_frames(pm, chains)
    plan["chains"] = len(chains)
    plan["pins"] = len(rows)
    reach_m = float(law.tables.emit.design.taxi_trend_face_reach_m)
    vw = view(pm, law)
    # the vertices each chain speaks for: its own, and every vertex of the
    # faces it owns (the shoulders the transverse rows carry)
    members: dict[int, list[int]] = {}
    for fid, i in owner.items():
        f = pm.faces[fid]
        vs = members.setdefault(i, [])
        for ring in (f.ring, *f.holes):
            vs.extend(pm.ring_vertices(ring))
    for i, c in enumerate(chains):
        members.setdefault(i, []).extend(c.vertices)
    held = set(pm.taxi_trend_z) | set(pm.apron_trend_z)
    withdraw: set[int] = plan["withdraw"]
    for r in rows:
        v = r.v
        # THE LOOP: the chain that speaks for the foot's own faces; where
        # the foot sits on no owned face (a junction fillet), the nearest
        # chain within the trend's own face reach
        votes: dict[int, int] = {}
        for fid in pm.vertices[v].incident_faces:
            i = owner.get(fid)
            if i is not None:
                votes[i] = votes.get(i, 0) + 1
        if votes:
            ci = max(sorted(votes), key=lambda k: votes[k])
            s0, dist = _project_chain(frames[ci], pm.vertices[v].xy)
        else:
            ci, s0, dist = -1, 0.0, float("inf")
            for i, fr in enumerate(frames):
                s, d = _project_chain(fr, pm.vertices[v].xy)
                if d < dist:
                    ci, s0, dist = i, s, d
            if ci < 0 or dist > reach_m:
                plan["short"].append({
                    "vertex": v, "ll": list(pm.vertices[v].key),
                    "reason": ("no taxi centreline within "
                               f"{reach_m:.0f} m of the pinned foot "
                               f"(nearest {dist:.0f} m)")})
                continue
        # THE DROP is against the loop's OWN DEM-fitted profile — the very
        # target being withdrawn — and the DEM only where there is none
        ref = pm.taxi_trend_z.get(v)
        if ref is None:
            ref = pm.apron_trend_z.get(v)
        if ref is None:
            ref = pm.vertices[v].dem_z
        if ref is None:
            continue
        cap = vw.vertex_cap.get(v)
        if not cap or cap <= 0.0:
            continue
        drop = abs(float(ref) - float(r.z))
        reach = drop / float(cap)
        fr = frames[ci]
        back, fwd = s0 - fr["s_lo"], fr["s_hi"] - s0
        rec = {"vertex": v, "ll": list(pm.vertices[v].key), "chain": chains[ci].bl,
               "station_m": round(s0, 1), "foot_m": round(dist, 1),
               "drop_m": round(drop, 2), "cap": cap,
               "reach_m": round(reach, 1),
               "loop_back_m": round(back, 1), "loop_fwd_m": round(fwd, 1)}
        plan["feet"].append(rec)
        if back < reach or fwd < reach:
            have = max(min(back, reach), min(fwd, reach))
            short = {**rec, "forced_grade": round(drop / have, 4) if have > 0
                     else None,
                     "family": "taxi"}
            plan["short"].append(short)
        for u in members.get(ci, ()):
            if u not in held or u in withdraw:
                continue
            s, d = _project_chain(fr, pm.vertices[u].xy)
            if d <= reach_m and abs(s - s0) <= reach:
                withdraw.add(u)
    plan["withdrawn"] = len(withdraw)
    return plan


def withdraw_trend_over_reach(pm: PlanarMap, law: Law, airport: Airport,
                              report: dict | None = None) -> PlanarMap:
    """``pm`` with the ground-trend targets WITHDRAWN over every EAT ramp's
    derived reach (§36 (5); :func:`eat_reach_plan`).

    Called by ``pipeline/build`` after BOTH trend channels are published
    (and by ``pipeline/why`` and ``tools/v2_solve_replay`` in the same
    position, which is how every arm solves the pipeline's own LP).  An
    airport with no EAT — five of the six frames — is returned
    unchanged."""
    import dataclasses as _dc

    plan = eat_reach_plan(pm, law, airport)
    if report is not None:
        report.update({k: v for k, v in plan.items() if k != "withdraw"})
        report["withdrawn"] = len(plan["withdraw"])
    drop = plan["withdraw"]
    if not drop:
        return pm
    if report is not None:
        report["withdrawn_taxi"] = len(drop & set(pm.taxi_trend_z))
        report["withdrawn_apron"] = len(drop & set(pm.apron_trend_z))
    return _dc.replace(
        pm,
        taxi_trend_z={v: z for v, z in pm.taxi_trend_z.items() if v not in drop},
        apron_trend_z={v: z for v, z in pm.apron_trend_z.items()
                       if v not in drop})
