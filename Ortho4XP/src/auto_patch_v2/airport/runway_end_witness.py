"""WHERE IS THE LANDING THRESHOLD — the Q1 vote and its one consequence
(#1359; owner RULINGS 2026-10-26q, 2026-10-26v; spec
``docs/specs/multi-source-terrain-spec.md`` §3 Q1, §5).

Per runway end, the threshold's station along the axis (metres in from the
apt.dat end) as each source states it:

* **layout** — apt.dat's displaced length (σ ``sigma.aptdat_xy``);
* **CIFP** — the end's own ``RWY`` record projected on the axis, UNCLAMPED
  (a record beyond the end reads negative; the join may have refused it);
* **imagery** — the build's own texture along the axis
  (``image_provider``, the law's method): the first threshold-marking row
  less ``q1.marking_inset_m`` (the markings begin 6 m inside the
  threshold); with no marking seen it abstains (a visual runway's
  designation numbers or a dirt strip do not place a threshold — a
  pavement-start reading was tried and refuted on the 81 shifted runways:
  dry grass reads as old asphalt);
* **DEM** — abstains: a graded runway and its graded safety area are one
  smooth profile, so the DEM cannot say where the runway ends.

THE RULE (26v): when the layout and the imagery agree and the CIFP record
disagrees with both (``witness_vote.decide``: it YIELDS), and it lies more
than ``q1.min_disagree_m`` from the layout's threshold (inside that the
join already accepts it as this end's, RULINGS 2026-10-22a), the record is
DROPPED for that end — position and height.  The end is then an apt.dat
end like any runway without CIFP: ``end_pins.verify`` has nothing to judge
there and ``constraints/runway_profile.end_pin_cases`` values it — on
credible lidar it FOLLOWS THE LIDAR (26v's words), with no noise floor: the
datum line it would otherwise keep is the apt.dat header, no survey.  One
loud line per drop, one record per end.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..law import Law
from ..model.airport import PIN_OUTVOTED, Airport, Runway
from . import image_edges_classic  # noqa: F401  (registers the classic method)
from .cifp import CifpRunway, match_designator
from .image_provider import Probes, provider
from .witness_vote import Abstain, Vote, decide

__all__ = ["end_station", "threshold_votes", "witness_runway_ends", "SENIORITY"]

#: Q1 seniority (spec §4.1): the pavement the sim draws, the photo the
#: pilot sees, the DEM, then CIFP — a tie-break only
SENIORITY = ("layout", "imagery", "dem", "cifp")
#: ``RunwayEnd.pin_flags`` of an end whose CIFP record was outvoted
OUTVOTED = PIN_OUTVOTED


def end_station(end_xy, other_xy, p) -> float:
    """Metres along the axis from ``end_xy`` toward ``other_xy`` of point
    ``p``'s projection, NOT clamped (negative = beyond the end)."""
    L = math.hypot(other_xy[0] - end_xy[0], other_xy[1] - end_xy[1])
    if L <= 0.0:
        return 0.0
    return ((p[0] - end_xy[0]) * (other_xy[0] - end_xy[0])
            + (p[1] - end_xy[1]) * (other_xy[1] - end_xy[1])) / L


def _image_vote(rw: Runway, k: int, textures, crs: str, law: Law) -> Vote | Abstain:
    """The imagery's threshold station at end ``k`` (module docstring)."""
    t = law.tables.terrain_witness
    q = t.q1
    if textures is None or not len(textures):
        return Abstain("imagery", "no texture of this build covers the airport")
    a = np.asarray(rw.ends[k].xy, dtype=float)
    b = np.asarray(rw.ends[1 - k].xy, dtype=float)
    L = rw.length_m
    if L <= 0.0:
        return Abstain("imagery", "zero-length runway")
    u = (b - a) / L
    after = min(q.search_after_frac * L,
                max(q.search_after_max_m, float(rw.ends[k].displaced_m or 0.0)
                    + q.search_past_threshold_m))
    offs = np.arange(-q.search_before_m, after, q.m_per_px)
    hw = q.strip_half_frac * float(rw.width_m)
    p0, p1 = a + u * offs[0], a + u * offs[-1]
    lo = np.minimum(p0, p1) - hw - 2.0
    hi = np.maximum(p0, p1) + hw + 2.0
    patch = textures.patch(crs, lo[0], lo[1], hi[0], hi[1], q.m_per_px,
                           corridor=(tuple(p0), tuple(p1), hw + 2.0))
    if patch is None or float(patch.valid.mean()) <= 0.0:
        return Abstain("imagery", "no texture under the runway end")
    prov = provider(t.image.provider)
    probes = Probes(a[None, :], u[None, :], offs, hw)
    sig = math.hypot(t.sigma.image_registration_m, t.sigma.image_px * q.m_per_px)
    mark = prov.edges(patch, probes, "threshold_marking")[0]
    if mark.offset_m is not None:
        return Vote("imagery", mark.offset_m - q.marking_inset_m,
                    math.hypot(sig, q.marking_sigma_m),
                    note=f"threshold marking at {mark.offset_m:.1f} m ({patch.source})")
    return Abstain("imagery", f"no threshold marking read ({patch.source})")


def threshold_votes(rw: Runway, k: int, rec: CifpRunway | None, to_xy, textures,
                    crs: str, law: Law) -> list[Vote | Abstain]:
    """Every source's threshold station at end ``k`` of ``rw``."""
    s = law.tables.terrain_witness.sigma
    end = rw.ends[k]
    votes: list[Vote | Abstain] = [Vote("layout", float(end.displaced_m or 0.0), s.aptdat_xy)]
    if rec is None:
        votes.append(Abstain("cifp", "no RWY record for this end"))
    else:
        st = end_station(end.xy, rw.ends[1 - k].xy, to_xy(rec.lon, rec.lat))
        votes.append(Vote("cifp", st, s.cifp_xy, note=rec.designator))
    votes.append(Abstain("dem", "a graded runway and its graded safety area are one profile"))
    votes.append(_image_vote(rw, k, textures, crs, law))
    return votes


def witness_runway_ends(airport: Airport, cifp: _t.Mapping[str, CifpRunway], to_xy,
                        textures, law: Law) -> tuple[Airport, list[dict], list[str]]:
    """THE RULE (module docstring) on ``airport``'s runways: the airport
    with every outvoted CIFP end dropped, one record per end with a CIFP
    record, and the loud lines."""
    t = law.tables.terrain_witness
    runways, records, lines = [], [], []
    for rw in airport.runways:
        ends = list(rw.ends)
        for k, end in enumerate(rw.ends):
            rec = match_designator(end.name, cifp) if cifp else None
            if rec is None:
                continue
            votes = threshold_votes(rw, k, rec, to_xy, textures, airport.frame.crs, law)
            dec = decide(votes, SENIORITY, t.vote.k)
            layout = float(end.displaced_m or 0.0)
            cif = next(v.value for v in votes if isinstance(v, Vote) and v.source == "cifp")
            drop = ("cifp" in dec.yielders and {"layout", "imagery"} <= set(dec.winners)
                    and abs(cif - layout) > t.q1.min_disagree_m)
            had = end.threshold_elev_m is not None
            if drop and had:
                ends[k] = _dc.replace(end, threshold_elev_m=None, cifp_source="",
                                      pin_along_m=None, pin_source="", cifp_elev_m=None,
                                      pin_flags=OUTVOTED)
                img = next(v for v in votes if v.source == "imagery")
                lines.append(
                    f"[witness] {airport.icao} RWY {end.name} Q1 (#1359, RULINGS 2026-10-26v): "
                    f"CIFP {rec.designator} threshold {cif:.1f} m yields to the layout "
                    f"{layout:.1f} m and the imagery "
                    f"{img.value:.1f} m{' (bound)' if img.bound else ''} — the CIFP record "
                    f"(position and height {rec.elevation_m:.2f} m) is dropped for this end")
            rec_out = dec.record(votes)
            rec_out.update({"question": "q1", "runway": rw.id, "end": end.name,
                            "dropped": bool(drop), "was_pinned": had,
                            "cifp_m": round(rec.elevation_m, 3)})
            records.append(rec_out)
        runways.append(_dc.replace(rw, ends=(ends[0], ends[1])))
    return _dc.replace(airport, runways=tuple(runways)), records, lines
