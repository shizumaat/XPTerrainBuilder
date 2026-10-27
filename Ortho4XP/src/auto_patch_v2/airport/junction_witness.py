"""WHERE PAVEMENT REALLY JOINS A RUNWAY — the imagery witness of a junction
flat (owner RULINGS 2026-10-27n, Q205: "a runway flattens only where the
photo shows real pavement joining it"; under 2026-10-26q; spec
``docs/findings/vnlk-junctions-lvnlk.md`` §10).

A steep runway's junction flat (2026-10-26n / 27b, ``constraints/
runway_junctions``) is minted where a pavement joins the runway.  The
installed layout can draw a pavement that is not there: at VNLK the pack's
``Helo Apron`` is a bare dirt plot behind a grass verge, and flattening the
runway for it bent the whole profile off the owner's video.  This reads,
for every pavement polygon touching a runway's edge, the build's own
imagery ACROSS that edge along the contact: at each 1 m station where the
ground 1.5 m beyond the edge lies inside the pavement, a probe from the
runway body out past the edge (``image_provider`` ``edges(...,
"paved_contact")``, the classic method's saturation test).  The pavement
JOINS PAVED when at least half its stations read as pavement.

The product is ``Airport.paved_joins``: pavement id -> ``True`` (paved) /
``False`` (the imagery refutes it), ``None`` when the build has no imagery
— every pavement then keeps its junction (the vote ABSTAINS, today's law).
A pavement the witness found no contact for is absent from the map and
keeps its junction too.  One loud line per refuted pavement.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np

from ..law import Law
from ..model.airport import Airport
from . import image_edges_classic  # noqa: F401  (registers the classic method)
from .image_provider import Probes, provider

__all__ = ["witness_paved_joins", "PAVED_SHARE"]

#: a pavement joins paved when at least this share of its contact stations
#: read as pavement
PAVED_SHARE = 0.5
#: probe geometry, metres: stations along the edge, how far beyond the edge
#: a station must lie inside the pavement, the body samples (inside the
#: runway, clear of its edge paint) and the ground samples beyond the edge
_STEP_M = 1.0
_INSIDE_M = 1.5
_BODY_M = (2.0, 2.0)          # from 2 m inside the edge to 2 m short of the centreline
_BEYOND_M = (1.0, 6.0)
_SAMPLE_M = 0.5
_ALONG_M = 1.0
_PX_M = 0.5


def _runway_probes(rw, poly, side: float):
    """``(stations xy, normal)`` of the contact of ``poly`` along one edge."""
    from shapely import contains_xy
    a, b = np.asarray(rw.ends[0].xy, float), np.asarray(rw.ends[1].xy, float)
    L = float(rw.length_m)
    if L <= 0.0:
        return None
    u = (b - a) / L
    n = np.array([-u[1], u[0]]) * side
    half = float(rw.width_m) / 2.0
    s = np.arange(0.0, L, _STEP_M)
    edge = a + np.outer(s, u) + n * half
    probe = edge + n * _INSIDE_M
    keep = contains_xy(poly, probe[:, 0], probe[:, 1])
    if not keep.any():
        return None
    return edge[keep], np.tile(n, (int(keep.sum()), 1))


def witness_paved_joins(airport: Airport, textures, law: Law
                        ) -> tuple[Airport, list[dict], list[str]]:
    """``(airport with paved_joins, one record per joining pavement, the
    loud lines)`` (module docstring)."""
    if textures is None or not len(textures):
        return (_dc.replace(airport, paved_joins=None), [],
                [f"[{airport.icao}] JUNCTION WITNESS: no airport imagery — every "
                 f"pavement joining a runway keeps its junction (RULINGS 2026-10-27n "
                 f"abstains)"])
    from shapely.geometry import Polygon
    method = provider(law.tables.terrain_witness.image.provider)
    paved: dict[str, bool] = {}
    recs: list[dict] = []
    lines: list[str] = []
    for rw in airport.runways:
        half = float(rw.width_m) / 2.0
        xs = [e.xy[0] for e in rw.ends]
        ys = [e.xy[1] for e in rw.ends]
        pad = half + _BEYOND_M[1] + 5.0
        patch = textures.patch(airport.frame.crs, min(xs) - pad, min(ys) - pad,
                               max(xs) + pad, max(ys) + pad, _PX_M)
        if patch is None:
            continue
        body = np.arange(-(half - _BODY_M[1]), -_BODY_M[0] + 1e-9, _SAMPLE_M)
        beyond = np.arange(_BEYOND_M[0], _BEYOND_M[1] + 1e-9, _SAMPLE_M)
        offs = np.concatenate([body, beyond])
        for pv in airport.pavements:
            try:
                poly = Polygon(pv.outer, [h for h in pv.holes if len(h) >= 3])
            except (ValueError, TypeError):
                continue
            if not poly.is_valid:
                poly = poly.buffer(0.0)
            got = [g for side in (1.0, -1.0) if (g := _runway_probes(rw, poly, side))]
            if not got:
                continue
            xy = np.vstack([g[0] for g in got])
            nrm = np.vstack([g[1] for g in got])
            ev = method.edges(patch, Probes(xy, nrm, offs, _ALONG_M), "paved_contact")
            read = [e for e in ev if e.strength > 0.0 or e.label != "none"]
            if not read:
                continue
            share = sum(e.label == "paved_contact" for e in read) / len(read)
            ok = share >= PAVED_SHARE
            paved[pv.id] = paved.get(pv.id, False) or ok
            recs.append({"runway": rw.id, "pavement": pv.id, "description": pv.description,
                         "stations": len(read), "paved_share": round(share, 3),
                         "paved": ok, "source": patch.source})
            if not ok:
                lines.append(f"[{airport.icao}] JUNCTION WITNESS {rw.id}: pavement {pv.id} "
                             f"({pv.description or 'unnamed'}) is not paved where it meets "
                             f"the runway in the imagery ({100 * share:.0f} % of "
                             f"{len(read)} stations read as pavement) — no junction flat "
                             f"(RULINGS 2026-10-27n)")
    return _dc.replace(airport, paved_joins=paved), recs, lines
