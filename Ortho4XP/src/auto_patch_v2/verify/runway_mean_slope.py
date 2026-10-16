"""``runway_mean_slope`` over the emitted crown spine (ICAO Annex 14
§3.1.13; audit §4 M1, owner RULINGS 2026-10-15l (1)): a runway's highest
minus its lowest ridge elevation between its two ends, over its length,
against the EFFECTIVE cap the build priced (sidecar ``runway_axes`` slot
19, ``constraints.runway_mean_slope.mean_slope_caps``) — the table's
(``tables.runway_mean_slope_max``) for a row that does not carry it.  One
row per runway over the cap by more than the reader's coarse quantum."""
from __future__ import annotations

import math

from ..law.tables import runway_mean_slope_max
from .frame import Patch, Row, row
from .runway_witness import published_row

__all__ = ["FAMILY_MEAN_SLOPE", "runway_mean_slope"]

FAMILY_MEAN_SLOPE = "runway_mean_slope"
_CAP_SLOT = 19


def runway_mean_slope(p: Patch) -> list[Row]:
    law = p.law
    q = law.tables.emit.instrument.coarse_noise_m
    rows_ax = p.publication.get("runway_axes") or ()
    code: dict[str, tuple[int | None, str | None]] = {}
    for sh in p.shapes:
        if sh.role == "runway" and sh.ref not in code:
            code[sh.ref] = (sh.code_number, sh.code_letter)
    pts: dict[str, list[tuple[float, float, float]]] = {}
    for sh in p.features:
        if sh.feature == "crown_spine":
            pts.setdefault(sh.ref, []).extend(
                (x, y, z) for (x, y), z in zip(sh.xy, sh.z))
    out: list[Row] = []
    for ref, xyz in pts.items():
        r = published_row(rows_ax, ref)
        if r is None:
            continue
        a, b = p.to_m(float(r[1]), float(r[2])), p.to_m(float(r[3]), float(r[4]))
        L = math.dist(a, b)
        if L <= 0.0:
            continue
        cap = r[_CAP_SLOT] if len(r) > _CAP_SLOT else \
            runway_mean_slope_max(law, *code.get(ref, (None, None)))
        if cap is None:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        on = [(x, y, z) for x, y, z in xyz
              if -q <= (x - a[0]) * ux + (y - a[1]) * uy <= L + q]
        if len(on) < 2:
            continue
        hi, lo = max(on, key=lambda t: t[2]), min(on, key=lambda t: t[2])
        spread = hi[2] - lo[2]
        over = spread - float(cap) * L
        if over <= q:
            continue
        rr = row(FAMILY_MEAN_SLOPE, ("runway", "runway"), p.side("runway"),
                 over, 100 * spread / L, 100 * float(cap), L,
                 (hi[0], hi[1]), (lo[0], lo[1]), ref, ref)
        rr.update({"reading": "mean_slope", "face": ref})
        out.append(rr)
    return out
