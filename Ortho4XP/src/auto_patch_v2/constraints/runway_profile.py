"""RUNWAY generator — the profile is the datum (H7 / RULINGS :511-516):
CIFP thresholds are absolute pins, the profile flexes between them within
the runway's longitudinal law only, the slab crowns off the profile.

Rows (all from ``rulesets.<authority>.runway`` and
``common.runway_crown_transverse``):

* ``Pin`` at the profile station nearest each threshold with a CIFP
  elevation (``RunwayEnd.threshold_elev_m``; an end without one has one
  pin fewer, never an invented one — plan §2);
* ``Diff`` along every ``runway_profile`` breakline chord at
  ``runway.longitudinal`` by code number; inside each END ZONE
  (``runway_end_zone_length_m``) at ``runway.end_zone`` where the
  authority states one (code 3 only when precision — recorded, no CIFP
  category is loaded, so code 3 keeps the body cap);
* CROWN (RULINGS 2026-08-05, family ``runway_crown``, solver mode
  ``offset``): every runway-family ring vertex off the ridge sits AT
  LEAST ``crown × lateral offset`` below the ridge's interpolation at its
  foot — a ``Linear`` floor over the two ridge stations bracketing the
  foot.  The sidecar declares the BUILT drop (:func:`crown_drops` with
  the solved ``z``), so the census re-centres every ring pair on the
  surface as built and its crown reader finds the declared fall.
* WITHIN-SHAPE lateral pairs on ``runway`` rings are IMPLIED: with the
  built drop declared, a pair's re-centred difference is the ridge
  profile's own difference between the two feet, bounded by the profile
  caps over an along-axis run no longer than the pair's distance — no
  row is minted (user 2026-07-08 station scoping is the census's own
  narrowing of the same domain; ``o4_single_poly`` is still tagged).
  ``runway_crossing`` rings sit on TWO ridges, so their pairs are stated
  explicitly in foot space (``Linear`` over the feet's interpolations).
* consecutive ridge chains of one runway (split at a crossing) are
  bridged by a ``Diff`` at the body cap so the profile stays one law
  across the crossing.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import role_cap, runway_end_zone_length_m
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Pin, Row, Source
from ..model.planar import PlanarMap
from .geometry import project_to_chain
from .precedence import View, view

__all__ = ["runway_profile", "runway_crown", "runway_within_shape",
           "crown_drops", "ridge_chains"]

GEN = "runway_profile"
RUNWAY_FAMILY = ("runway", "runway_crossing")


def ridge_chains(vw: View) -> dict[str, list[list[int]]]:
    """Runway id -> its ``runway_profile`` breakline chains (a chain may
    be split where the noding broke it)."""
    out: dict[str, list[list[int]]] = {}
    for bid, b in vw.pm.breaklines.items():
        if b.kind == "runway_profile":
            out.setdefault(b.ref, []).append(vw.chains[bid])
    return out


def _runway_code(airport: Airport, ref: str) -> tuple[int | None, str | None]:
    for rw in airport.runways:
        if rw.id == ref:
            return rw.code_number, rw.code_letter
    return None, None


def runway_profile(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Threshold pins + longitudinal caps along each profile chain."""
    vw = view(planar, law)
    rows: list[Row] = []
    chains = ridge_chains(vw)
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        cap = role_cap(law, "runway", rw.code_number, rw.code_letter)
        if cap is None:
            continue
        rs = law.ruleset.runway
        end_cap = rs.end_zone.value(rw.code_number, rw.code_letter)
        if rw.code_number in rs.end_zone_precision_only_codes:
            end_cap = None            # no CIFP category loaded: body cap
        end_len = runway_end_zone_length_m(law, rw.length_m)
        a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
        L = rw.length_m
        ux = (b_xy[0] - a_xy[0]) / L if L > 0 else 0.0
        uy = (b_xy[1] - a_xy[1]) / L if L > 0 else 0.0

        def along(v: int) -> float:
            x, y = vw.xy[v]
            return (x - a_xy[0]) * ux + (y - a_xy[1]) * uy

        src = Source(GEN, "rulesets.runway.longitudinal", (f"rwy:{rw.id}",))
        src_end = Source(GEN, "rulesets.runway.end_zone", (f"rwy:{rw.id}",))
        chs = sorted(chs, key=lambda c: min(along(c[0]), along(c[-1])))
        chs = [c if along(c[0]) <= along(c[-1]) else list(reversed(c)) for c in chs]
        for prev, nxt in zip(chs, chs[1:]):
            a, b = prev[-1], nxt[0]
            if a != b:
                d = vw.dist(a, b)
                if d > 0.0:
                    s_mid = 0.5 * (along(a) + along(b))
                    in_end = s_mid < end_len or s_mid > L - end_len
                    rows.append(Diff(a, b, end_cap if (in_end and end_cap is not None)
                                     else cap.longitudinal, d,
                                     src_end if (in_end and end_cap is not None) else src))
        for ch in chs:
            for a, b in zip(ch, ch[1:]):
                d = vw.dist(a, b)
                if d <= 0.0:
                    continue
                s_mid = 0.5 * (along(a) + along(b))
                in_end = s_mid < end_len or s_mid > L - end_len
                if in_end and end_cap is not None:
                    rows.append(Diff(a, b, end_cap, d, src_end))
                else:
                    rows.append(Diff(a, b, cap.longitudinal, d, src))
        # pins: the station nearest each threshold with a CIFP elevation
        all_ids = [v for ch in chs for v in ch]
        for end in rw.ends:
            if end.threshold_elev_m is None:
                continue
            sign = 1.0 if end is rw.ends[0] else -1.0
            tx = end.xy[0] + sign * ux * end.displaced_m
            ty = end.xy[1] + sign * uy * end.displaced_m
            best = min(all_ids, key=lambda v: (vw.xy[v][0] - tx) ** 2
                       + (vw.xy[v][1] - ty) ** 2)
            rows.append(Pin(best, float(end.threshold_elev_m),
                            Source(GEN, "RULINGS :511-516 CIFP threshold",
                                   (f"rwy:{rw.id}", f"end:{end.name}",
                                    end.cifp_source))))
    return rows


def _foot(vw: View, v: int, chains: list[list[int]]
          ) -> tuple[float, int, int, float] | None:
    """``(lateral distance, ridge a, ridge b, t)`` of the nearest ridge
    point to vertex ``v`` over the runway's chains."""
    best: tuple[float, int, int, float] | None = None
    p = vw.xy[v]
    for ch in chains:
        if len(ch) < 2:
            continue
        d, k, t, _s = project_to_chain(p, [vw.xy[c] for c in ch])
        if best is None or d < best[0]:
            best = (d, ch[k], ch[k + 1], t)
    return best


def crown_drops(planar: PlanarMap, law: Law, airport: Airport,
                z: _t.Sequence[float] | None = None) -> dict[int, float]:
    """Vertex -> crown drop (m) for every runway-family ring vertex (0.0
    on the ridge): the DESIGNED drop ``crown × d`` without ``z``, the
    BUILT drop ``z_foot − z_v`` with it — the sidecar ``crown_drops``
    field declares the built one."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    crown = law.tables.common.runway_crown_transverse
    every = [c for chs in chains.values() for c in chs]
    out: dict[int, float] = {}
    for f in vw.faces_of_role(RUNWAY_FAMILY):
        ref_ids = [f.ref] if f.role == "runway" else f.ref.split("+")
        own = [c for r in ref_ids for c in chains.get(r, [])]
        if not own:
            continue
        on_ridge = {v for c in every for v in c}
        for v in vw.rings[f.id]:
            if v in out:
                continue
            if v in on_ridge:
                out[v] = 0.0
                continue
            # the census reads the NEAREST crown spine of ANY runway
            ft = _foot(vw, v, every if z is not None else own)
            if ft is None:
                continue
            if z is None:
                out[v] = round(crown * ft[0], 6)
            else:
                d, a, b, t = ft
                out[v] = round((1.0 - t) * z[a] + t * z[b] - z[v], 6)
    return out


def runway_crown(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every off-ridge runway-family vertex sits at least ``crown × d``
    below the ridge at its foot (family ``runway_crown``, 2026-08-05;
    solver mode ``offset``)."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    crown = law.tables.common.runway_crown_transverse
    rows: list[Row] = []
    done: set[int] = set()
    for f in vw.faces_of_role(RUNWAY_FAMILY):
        ref_ids = [f.ref] if f.role == "runway" else f.ref.split("+")
        chs = [c for r in ref_ids for c in chains.get(r, [])]
        if not chs:
            continue
        own_ridge = {v for c in chs for v in c}
        src = Source(GEN, "common.runway_crown_transverse", (f"face:{f.id}", f.ref))
        for v in vw.rings[f.id]:
            if v in done or v in own_ridge:
                continue
            ft = _foot(vw, v, chs)
            if ft is None or ft[0] <= 0.0:
                continue
            done.add(v)
            d, a, b, t = ft
            drop = crown * d
            terms = ((v, 1.0), (a, -(1.0 - t)), (b, -t))
            if t <= 0.0:
                terms = ((v, 1.0), (a, -1.0))
            elif t >= 1.0:
                terms = ((v, 1.0), (b, -1.0))
            rows.append(Linear(terms, None, -drop, src))
    return rows


def runway_within_shape(planar: PlanarMap, law: Law, airport: Airport
                        ) -> list[Row]:
    """``runway_crossing`` ring pairs in FOOT space: with the built drop
    declared, the census prices ``|z_foot(a) − z_foot(b)|`` against the
    cap over the pair's distance — stated here over the feet's ridge
    interpolations (``runway`` rings are implied by the profile caps)."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    for f in vw.faces_of_role(("runway_crossing",)):
        cap = role_cap(law, f.role, f.code_number, f.code_letter)
        if cap is None:
            continue
        chs = [c for r in f.ref.split("+") for c in chains.get(r, [])]
        if not chs:
            continue
        ring = vw.rings[f.id]
        own_ridge = {v for c in chs for v in c}
        foot: dict[int, tuple[tuple[int, float], ...]] = {}
        for v in ring:
            if v in own_ridge:
                foot[v] = ((v, 1.0),)
                continue
            ft = _foot(vw, v, chs)
            if ft is None:
                foot[v] = ((v, 1.0),)
            else:
                _d, a, b, t = ft
                foot[v] = ((a, 1.0 - t), (b, t)) if 0.0 < t < 1.0 else \
                    ((a, 1.0),) if t <= 0.0 else ((b, 1.0),)
        src = Source(GEN, "rulesets.runway.longitudinal within_shape (crossing)",
                     (f"face:{f.id}", f.ref))
        n = len(ring)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = ring[i], ring[j]
                d = vw.dist(a, b)
                if d < min_d:
                    continue
                terms: dict[int, float] = {}
                for v, c in foot[a]:
                    terms[v] = terms.get(v, 0.0) + c
                for v, c in foot[b]:
                    terms[v] = terms.get(v, 0.0) - c
                terms = {v: c for v, c in terms.items() if abs(c) > 1e-12}
                if not terms:
                    continue
                bound = cap.longitudinal * d
                rows.append(Linear(tuple(terms.items()), -bound, bound, src))
    return rows
