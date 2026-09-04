"""THE SEAT (RULINGS 2026-09-04i 04f-1): after the tile mesh is built,
every placed object of an airport v2 patched is re-seated against the
NEW terrain — "otherwise the objects would not comply with the terrain
the patch produced".  Law: ``structures.toml [rebake]``.

:func:`seat` runs AFTER the mesh, over the tile build's plan
(``model/rebake.py``, built by ``airport/rebake_plan.py``) and a sampler
of the built mesh (``sampler(lat, lon) -> (z, is_water) | None``): per
member the seat that lands its witnesses on the terrain, per unit ONE
delta.  A rigid unit stands on the members whose feet reach ITS lowest
band (a railing's feet are on the deck, a canopy's in the air — they
inherit, v1 invariant I-8) AND carry enough land witnesses — the
FOUNDING WITNESS FLOOR (04k: ``founding_min_witnesses`` /
``founding_min_share``; TerminalRoads_03_004's 4 witnesses lifted 400
objects 6.3 m); a deck member founds the family (memory
``othh-bridge-deck-datum-r12``: the datum is the deck TOP, never the
authored y = 0 plane) — a SIGNATURE deck (``airport/deck_signature.py``)
at its ABUTMENTS: the ground is sampled along each deck-end line, a
sample on water is discarded and the line WALKS LANDWARD along the axis
until ``abutment_min_land_samples`` stand on land (R12 amendment 1, the
mesh's own water bits the authority — amendment 2), the member delta is
``grade − (base + deck top)``, and the family takes the agreeing
coalition of member deltas (amendments 3/4); a flagged deck at the
solved surface / its ring.  After the seat the mesh under a deck's
CREST must lie ``deck_min_clearance_under_m`` under the seated crest or
be water — a bridge stands over something lower than itself; a plate
seated onto the ground it covers (a canopy, an elevated kerb road on
columns) spans nothing, the deck seat is refused with a finding and the
feet law governs.  Otherwise the agreeing coalition of founding feet seats
(R12 amendments 3/4), else the median with a finding.  A foot on a
water triangle never founds a seat (OTHH's canal is not a datum); a
unit with no founding witness on land is HELD — the pack's current
bytes are kept and a finding is raised; a unit that moves under
``min_delta_m`` stays and the terrain adapts.

Nothing here writes: the delta per unit is handed to the v1 driver hook
(``engine_v2.rebake_after_mesh``), which rewrites the pack's OBJ8 vertex
``y`` tokens through v1's ``object_rebake.apply`` — the ONE writer both
engines share, with its ``.anchor_bak`` backup discipline, provenance
sidecar and reversion pass.  No environment is read here.
"""
from __future__ import annotations

import math
import statistics
import typing as _t

import numpy as np

from ..law import Law
from ..model.frame import LL, XY
from ..model.rebake import (DATUM_DECK_TOP, DATUM_FEET, PLAN_FILENAME, PLAN_VERSION,
                            Foot, Member, MemberSeat, RebakePlan, SeatResult, Unit,
                            UnitSeat)

__all__ = ["seat", "deck_datum_from_surface", "Sampler", "Foot", "Member", "Unit",
           "RebakePlan", "MemberSeat", "UnitSeat", "SeatResult", "PLAN_VERSION",
           "PLAN_FILENAME", "DATUM_FEET", "DATUM_DECK_TOP"]

#: ``sampler(lat, lon) -> (z, is_water)`` or ``None`` off the mesh.
Sampler = _t.Callable[[float, float], "tuple[float, bool] | None"]


def deck_datum_from_surface(surface, ring_xy: _t.Sequence[XY], to_xy,
                            buffer_m: float = 0.5) -> float | None:
    """The SOLVED surface's value at a deck: the median ``z`` of the
    graded surface's vertices inside the deck ring (buffered by
    ``buffer_m`` so the ring's own vertices count).  ``None`` when the
    surface has no vertex there (the deck founds no solved value)."""
    from shapely import contains_xy
    from shapely.geometry import Polygon
    if surface is None or len(ring_xy) < 3 or not surface.vertices:
        return None
    try:
        poly = Polygon(ring_xy).buffer(buffer_m)
    except Exception:
        return None
    xs = []; ys = []; zs = []
    for sv in surface.vertices:
        x, y = to_xy(sv.ll[1], sv.ll[0])
        xs.append(x); ys.append(y); zs.append(sv.z)
    mask = contains_xy(poly, np.asarray(xs), np.asarray(ys))
    inside = [z for z, m in zip(zs, mask) if m]
    return float(statistics.median(inside)) if inside else None


def _coalition(values: _t.Sequence[float], window: float
               ) -> tuple[list[float] | None, str]:
    """The largest ≥2-member subset within ``window`` that strictly
    out-numbers every rival subset; ``(None, why)`` on a tie or none."""
    if len(values) < 2:
        return None, "single member"
    order = sorted(range(len(values)), key=lambda i: values[i])
    vs = [values[i] for i in order]
    best: list[frozenset[int]] = []
    best_n = 1
    for i in range(len(vs)):
        j = i
        while j + 1 < len(vs) and vs[j + 1] - vs[i] <= window:
            j += 1
        n = j - i + 1
        if n > best_n:
            best_n, best = n, [frozenset(order[i:j + 1])]
        elif n == best_n and n >= 2:
            s = frozenset(order[i:j + 1])
            if s not in best:
                best.append(s)
    if best_n < 2:
        return None, "no two members agree within the window"
    if len(best) > 1:
        return None, f"tie: {len(best)} rival coalitions of {best_n}"
    return [values[i] for i in sorted(best[0])], ""


def _metres_per_degree(lat: float) -> tuple[float, float]:
    """``(m per degree of latitude, m per degree of longitude)`` — the
    local scale the abutment walk steps by (a 5 m step at OTHH's 25°N is
    4.5e-5° of latitude; the equirectangular error is < 0.1 %)."""
    m_lat = 111_132.954 - 559.822 * math.cos(2 * math.radians(lat)) \
        + 1.175 * math.cos(4 * math.radians(lat))
    m_lon = 111_412.84 * math.cos(math.radians(lat)) - 93.5 * math.cos(3 * math.radians(lat))
    return m_lat, m_lon


def _abutment_grade(ends: tuple[tuple[LL, LL], tuple[LL, LL]], sampler: Sampler, br,
                    water_founds: bool) -> tuple[float | None, list[str], int, int, int]:
    """THE ABUTMENT GRADE of a signature deck (R12 amendments 1–2): per
    deck-end line, samples ``abutment_sample_step_m`` apart; a sample on
    a water triangle is discarded; with fewer than
    ``abutment_min_land_samples`` on land the line moves LANDWARD (away
    from the other end) one step at a time up to ``abutment_walk_max_m``.
    Returns ``(median grade over the ends that found land, records,
    land samples, water samples, off-mesh samples)``."""
    mids = [((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in ends]
    m_lat, m_lon = _metres_per_degree(mids[0][0])
    pooled: list[float] = []
    records: list[str] = []
    n_land = n_water = n_off = 0
    for i, (a, b) in enumerate(ends):
        other = mids[1 - i]
        dx = (mids[i][1] - other[1]) * m_lon
        dy = (mids[i][0] - other[0]) * m_lat
        norm = math.hypot(dx, dy)
        landward = (dx / norm, dy / norm) if norm > 1e-6 else None
        length = math.hypot((b[1] - a[1]) * m_lon, (b[0] - a[0]) * m_lat)
        steps = max(2, int(math.ceil(length / br.abutment_sample_step_m)))
        walked = 0.0
        kept: list[float] = []
        lost = off = 0
        while True:
            off_lat = (landward[1] * walked / m_lat) if landward else 0.0
            off_lon = (landward[0] * walked / m_lon) if landward else 0.0
            kept, lost, off = [], 0, 0
            for k in range(steps + 1):
                f = k / steps
                la = a[0] + (b[0] - a[0]) * f + off_lat
                lo = a[1] + (b[1] - a[1]) * f + off_lon
                smp = sampler(la, lo)
                if smp is None:
                    off += 1
                elif smp[1] and not water_founds:
                    lost += 1
                else:
                    kept.append(float(smp[0]))
            if len(kept) >= br.abutment_min_land_samples:
                break
            if landward is None or walked + br.abutment_sample_step_m > br.abutment_walk_max_m:
                break
            walked += br.abutment_sample_step_m
        found = len(kept) >= br.abutment_min_land_samples
        records.append(f"{'start' if i == 0 else 'far'} end: walked {walked:.0f} m, "
                       f"{len(kept)} land / {lost} water / {off} off-mesh samples"
                       + (f", grade {statistics.median(kept):.3f}" if found else ", no land found"))
        n_land += len(kept); n_water += lost; n_off += off
        if found:
            pooled.extend(kept)
    grade = float(statistics.median(pooled)) if pooled else None
    return grade, records, n_land, n_water, n_off


def _mid_span(m: Member, base: float, delta: float, sampler: Sampler, br
              ) -> tuple[bool, str]:
    """AFTER the seat: the mesh under SOME station of the deck (near-
    horizontal faces of the plate's own components, spread along the
    axis) must lie ``deck_min_clearance_under_m`` under the seated face
    there, or be water — a bridge stands over something lower than
    itself; a kerb road or a canopy over the ground it is built on does
    not.  ``(ok, record)``."""
    if not m.deck_stations:
        return True, "stations: none recorded"
    best = -math.inf
    water = off = 0
    for la, lo, y in m.deck_stations:
        smp = sampler(la, lo)
        if smp is None:
            off += 1
            continue
        if smp[1]:
            water += 1
            continue
        best = max(best, base + delta + y - float(smp[0]))
    n = len(m.deck_stations)
    if water:
        return True, f"{water}/{n} stations over water" \
            + (f", best land clearance {best:.2f} m" if best > -math.inf else "")
    if best == -math.inf:
        return True, f"stations: all {n} off the mesh"
    ok = best >= br.deck_min_clearance_under_m
    return ok, (f"best clearance under the seated deck {best:.2f} m over {n} stations "
                + ("" if ok else f"< {br.deck_min_clearance_under_m}: the deck stands on the "
                   "ground it covers, deck seat refused"))


def _founders(u: Unit, seats: list[MemberSeat], rb) -> list[bool]:
    """Which foot members may found the unit: those over the WITNESS
    FLOOR (land witnesses ≥ ``founding_min_witnesses`` and ≥
    ``founding_min_share`` of the unit's largest member's) whose feet
    reach the unit's lowest band over the eligible members (v1 I-8 — a
    railing's feet are on the deck, it inherits)."""
    n = [s.witnesses if s.datum == DATUM_FEET else 0 for s in seats]
    largest = max(n, default=0)
    # the floor is RELATIVE: it demotes a small piece beside a larger
    # member; a unit whose every member is small (a sign on four feet)
    # still seats on what it has
    floor = min(rb.founding_min_witnesses, largest) if largest > 0 else 0
    eligible = [k >= floor and k >= rb.founding_min_share * largest and k > 0 for k in n]
    min_y = [min((f.y for f in m.feet), default=math.inf) for m in u.members]
    band_min = min((my for my, e in zip(min_y, eligible) if e), default=math.inf)
    return [e and my <= band_min + rb.foot_band_m for my, e in zip(min_y, eligible)]


def _feet_reading(m: Member, base: float, sampler: Sampler, rb) -> MemberSeat:
    rs: list[float] = []
    water = off = 0
    for f in m.feet:
        s = sampler(f.lat, f.lon)
        if s is None:
            off += 1
        elif s[1] and not rb.water_founds_seat:
            water += 1
        else:
            rs.append(float(s[0]) - base - f.y)
    delta = float(statistics.median(rs)) if rs else None
    outliers = sum(1 for r in rs if abs(r - delta) > rb.residual_report_m) \
        if delta is not None else 0
    return MemberSeat(m.resource, DATUM_FEET, delta, len(rs), water, off, outliers,
                      "" if rs else "no foot on land within the mesh")


def _deck_reading(m: Member, base: float, sampler: Sampler, rb, br) -> MemberSeat | None:
    """The deck-top reading of a deck member, ``None`` for a foot member."""
    if m.deck_ring is None or rb.deck_datum != DATUM_DECK_TOP or m.deck_top_y is None:
        return None
    if m.deck_kind == "signature":
        if m.deck_ends is None:
            return MemberSeat(m.resource, DATUM_DECK_TOP, None, 0, 0, 0, 0,
                              "signature deck without end lines (plate under "
                              f"{br.deck_min_span_m} m): seats with its family",
                              tuple(m.deck_evidence))
        grade, recs, nl, nw, noff = _abutment_grade(m.deck_ends, sampler, br,
                                                    rb.water_founds_seat)
        delta = None if grade is None else grade - (base + m.deck_top_y)
        return MemberSeat(m.resource, DATUM_DECK_TOP, delta, nl, nw, noff, 0,
                          "abutment grade at the deck-end lines (R12)" if grade is not None
                          else "no abutment on land within the walk",
                          tuple(recs) + tuple(m.deck_evidence))
    datum_z = m.deck_datum_z
    water = off = 0
    n = 1 if datum_z is not None else 0
    note = "solved surface at the deck" if datum_z is not None else ""
    if datum_z is None:
        zs = []
        for la, lo in m.deck_ring:
            s = sampler(la, lo)
            if s is None:
                off += 1
            elif s[1] and not rb.water_founds_seat:
                water += 1
            else:
                zs.append(float(s[0]))
        n = len(zs)
        datum_z = float(statistics.median(zs)) if zs else None
        note = "mesh at the deck ring (no solved value there)"
    delta = None if datum_z is None else datum_z - (base + m.deck_top_y)
    return MemberSeat(m.resource, DATUM_DECK_TOP, delta, n, water, off, 0, note,
                      tuple(m.deck_evidence))


def seat(plan_: RebakePlan, sampler: Sampler, law: Law) -> SeatResult:
    """ONE delta per unit against the built mesh (see module doc)."""
    rb = law.tables.structures.rebake
    br = law.tables.structures.bridge
    out: list[UnitSeat] = []
    for u in plan_.units:
        resources = tuple(m.resource for m in u.members)
        a = sampler(u.anchor[0], u.anchor[1])
        if a is None:
            out.append(UnitSeat(u.id, resources, None, DATUM_FEET, None, None, (),
                                "anchor off the mesh"))
            continue
        anchor_ground = float(a[0])
        base = anchor_ground + u.agl_m          # the rendered y = 0 plane
        feet = [_feet_reading(m, base, sampler, rb) for m in u.members]
        decks = [_deck_reading(m, base, sampler, rb, br) for m in u.members]
        findings: list[str] = []
        # ── the deck datum: a deck member founds the family ─────────────
        measurable_decks = [(k, d) for k, d in enumerate(decks)
                            if d is not None and d.delta_m is not None]
        datum = DATUM_FEET
        delta: float | None = None
        founding = [False] * len(u.members)
        seats: list[MemberSeat] = [d if d is not None else f for d, f in zip(decks, feet)]
        if measurable_decks:
            vals = [d.delta_m for _k, d in measurable_decks]
            coal_idx: list[int]
            if len(vals) == 1:
                delta, coal_idx = vals[0], [0]
            else:
                coal, why = _coalition(vals, rb.agreement_window_m)
                if coal is not None:
                    delta = float(statistics.median(coal))
                    coal_idx = [i for i, v in enumerate(vals) if v in coal]
                    if len(coal) < len(vals):
                        findings.append(f"deck coalition {len(coal)}/{len(vals)} members within "
                                        f"{rb.agreement_window_m} m; {len(vals) - len(coal)} "
                                        "outlier member(s)")
                else:
                    # R12 amendment 4: a tie is genuine ambiguity, no
                    # coalition is no measurement — the deck seat stands
                    # down and the residual goes to the owner
                    delta, coal_idx = None, []
                    findings.append(f"deck seat refused: deck members disagree ({why}), "
                                    f"spread {max(vals) - min(vals):.3f} m over {len(vals)} — "
                                    "the feet law governs (R12 amendment 4)")
            # THE CLEARANCE CONFIRMATION: a deck stands over something lower
            spans = []
            for j in coal_idx:
                k, d = measurable_decks[j]
                ok, rec = _mid_span(u.members[k], base, delta, sampler, br)
                seats[k] = _dc_replace(d, records=d.records + (rec,))
                spans.append(ok)
            if any(spans):
                datum = DATUM_DECK_TOP
                for j, ok in zip(coal_idx, spans):
                    founding[measurable_decks[j][0]] = bool(ok)
                n_feet = sum(1 for d in decks if d is None)
                if n_feet:
                    findings.append(f"deck founds the family: {n_feet} foot member(s) follow "
                                    "rigidly")
            elif coal_idx:
                findings.append("deck seat refused: no founding deck member stands over "
                                f"anything lower than itself (clearance < "
                                f"{br.deck_min_clearance_under_m} m over land) — the feet law "
                                "governs")
                delta = None
        if datum == DATUM_FEET:
            # every member by its FEET (a refused deck member's too), the
            # deck readings kept in the records
            seats = [f if d is None else _dc_replace(f, records=d.records + (f"deck reading: "
                     f"{d.note}" + (f" delta {d.delta_m:.3f}" if d.delta_m is not None else ""),))
                     for d, f in zip(decks, feet)]
            founding = _founders(u, seats, rb)
            measurable = [s for s, f in zip(seats, founding) if s.delta_m is not None and f]
            n_w = sum(s.water for s in seats)
            if not measurable:
                out.append(UnitSeat(u.id, resources, anchor_ground, DATUM_FEET, None, None,
                                    tuple(seats),
                                    f"held: no founding witness on land ({n_w} on water, "
                                    f"{sum(founding)} founding member(s) over the witness "
                                    "floor) — the pack's current state is kept",
                                    tuple(findings), True))
                continue
            below_floor = [s.resource for s, f in zip(seats, founding)
                           if not f and s.delta_m is not None
                           and s.witnesses < max(min(rb.founding_min_witnesses,
                                                     max(x.witnesses for x in seats)),
                                                 rb.founding_min_share
                                                 * max(x.witnesses for x in seats))]
            if below_floor:
                findings.append(f"{len(below_floor)} member(s) under the founding witness floor "
                                f"({rb.founding_min_witnesses} land witnesses / "
                                f"{rb.founding_min_share:.0%} of the largest member's): "
                                + ", ".join(r.rsplit('/', 1)[-1] for r in below_floor[:3]))
            vals = [s.delta_m for s in measurable]
            if len(vals) == 1:
                delta = vals[0]
            else:
                coal, why = _coalition(vals, rb.agreement_window_m)
                if coal is not None:
                    delta = float(statistics.median(coal))
                    if len(coal) < len(vals):
                        findings.append(f"coalition {len(coal)}/{len(vals)} members within "
                                        f"{rb.agreement_window_m} m; "
                                        f"{len(vals) - len(coal)} outlier member(s)")
                else:
                    delta = float(statistics.median(vals))
                    findings.append(f"no agreeing coalition ({why}): median of "
                                    f"{len(vals)} members, spread "
                                    f"{max(vals) - min(vals):.3f} m")
        seats = [_dc_replace(s, founding=f) for s, f in zip(seats, founding)]
        n_out = sum(s.outliers for s in seats)
        if n_out:
            findings.append(f"{n_out} foot witness(es) further than "
                            f"{rb.residual_report_m} m off the mesh under the rigid seat")
        if delta is None or not math.isfinite(delta):
            out.append(UnitSeat(u.id, resources, anchor_ground, datum, None, None,
                                tuple(seats), "non-finite seat", tuple(findings)))
            continue
        reason = None
        if abs(delta) < rb.min_delta_m and not (datum == DATUM_DECK_TOP
                                                and rb.deck_seat_threshold_exempt):
            reason = (f"below_threshold: |{delta:.3f}| m < {rb.min_delta_m} m — the unit "
                      "stays at its authored y and the terrain adapts")
        out.append(UnitSeat(u.id, resources, anchor_ground, datum, delta, base + delta,
                            tuple(seats), reason, tuple(findings)))
    return SeatResult(plan_.icao, tuple(out))


def _dc_replace(s: MemberSeat, **kw) -> MemberSeat:
    import dataclasses as _dc
    return _dc.replace(s, **kw)
