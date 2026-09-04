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
inherit, v1 invariant I-8); a deck member founds the family (memory
``othh-bridge-deck-datum-r12``: the datum is the deck TOP, never the
authored y = 0 plane); otherwise the agreeing coalition of founding
member seats (R12 amendments 3/4), else the median with a finding.  A
foot on a water triangle never founds a seat (OTHH's canal is not a
datum); a unit with no founding witness on land is HELD — the pack's
current bytes are kept and a finding is raised; a unit that moves under
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
from ..model.frame import XY
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


def seat(plan_: RebakePlan, sampler: Sampler, law: Law) -> SeatResult:
    """ONE delta per unit against the built mesh (see module doc)."""
    rb = law.tables.structures.rebake
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
        # THE UNIT'S CONTACT BAND: a rigid unit stands on the members whose
        # feet reach its own lowest band (a railing's feet are ON the deck,
        # a canopy's are in the air — they inherit, v1 invariant I-8); a
        # deck member always founds.
        min_y = [min((f.y for f in m.feet), default=math.inf) for m in u.members]
        unit_min = min(min_y) if min_y else math.inf
        founding = [my <= unit_min + rb.foot_band_m or (m.deck_ring is not None)
                    for my, m in zip(min_y, u.members)]
        seats: list[MemberSeat] = []
        for m, founds in zip(u.members, founding):
            if m.deck_ring is not None and rb.deck_datum == DATUM_DECK_TOP \
                    and m.deck_top_y is not None:
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
                seats.append(MemberSeat(m.resource, DATUM_DECK_TOP, delta, n, water, off,
                                        0, note))
                continue
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
            seats.append(MemberSeat(m.resource, DATUM_FEET, delta, len(rs), water, off,
                                    outliers,
                                    ("" if founds else "inherits (feet above the unit's "
                                     "contact band)") if rs
                                    else "no foot on land within the mesh"))
        measurable = [s for s, founds in zip(seats, founding)
                      if s.delta_m is not None and founds]
        findings: list[str] = []
        if not measurable:
            n_w = sum(s.water for s, f in zip(seats, founding) if f)
            out.append(UnitSeat(u.id, resources, anchor_ground, DATUM_FEET, None, None,
                                tuple(seats),
                                f"held: no founding witness on land ({n_w} on water, "
                                f"{sum(f for f in founding)} founding member(s)) — the "
                                "pack's current state is kept", (), True))
            continue
        if len(measurable) < sum(founding):
            findings.append(f"{sum(founding) - len(measurable)} founding member(s) "
                            "unmeasurable (water / off the mesh)")
        decks = [s.delta_m for s in measurable if s.datum == DATUM_DECK_TOP]
        if decks:
            datum = DATUM_DECK_TOP
            delta = float(statistics.median(decks))
            if len(decks) < len(measurable):
                findings.append(f"deck founds the family: {len(measurable) - len(decks)} "
                                "foot member(s) follow rigidly")
        else:
            datum = DATUM_FEET
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
        n_out = sum(s.outliers for s in seats)
        if n_out:
            findings.append(f"{n_out} foot witness(es) further than "
                            f"{rb.residual_report_m} m off the mesh under the rigid seat")
        if not math.isfinite(delta):
            out.append(UnitSeat(u.id, resources, anchor_ground, datum, None, None,
                                tuple(seats), "non-finite seat", tuple(findings)))
            continue
        reason = None
        if abs(delta) < rb.min_delta_m:
            reason = (f"below_threshold: |{delta:.3f}| m < {rb.min_delta_m} m — the unit "
                      "stays at its authored y and the terrain adapts")
        out.append(UnitSeat(u.id, resources, anchor_ground, datum, delta, base + delta,
                            tuple(seats), reason, tuple(findings)))
    return SeatResult(plan_.icao, tuple(out))
