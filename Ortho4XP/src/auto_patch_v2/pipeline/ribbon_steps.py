"""THE RIBBON'S CONTACT STEP, DECLARED (owner RULINGS 2026-09-30aa rule 7,
issue #100 round 8).

A mapped-road ribbon is welded to the airside at both kerbs where it runs
in the gap between two airside bodies; under §20b (option (c), stage 1 on
the ribbon-free map) both kerbs carry stage 1's constants, and where those
stand further apart than the road's transverse cap can span the ribbon
cannot grade between them.  Rule 7: the road never moves the airside — it
arrives below the HIGHER contact and the difference is a reported
``road_contact_step``.  The step is DECLARED there, through the existing
declared-step register (sidecar ``terrace_joints``, the record shape of
``publication.pad_terrace_joints``), so both instruments forgive exactly
the declared height across that line and price any excess.

MEASURED (HECA replay, ribbon ``small_roads:-18656``): the corridor
98.5-99.1 m and the apron 3 m lower at 30.1217131, 31.4204600 — 15
CRITICAL motion cliffs (``within_shape`` / ``road_cross_section``
``[apron|apron]``, 3.22 m over 8.5 m) that the ribbon-free map does not
have.

The line stands at :data:`AT` of the way from the higher kerb vertex to
its lower partner — at the higher contact, inside the ribbon, so every
kerb-to-kerb chord crosses it once.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import Point, Polygon

from ..law import Law
from ..model.planar import PlanarMap, is_osm_ribbon_ref
from ..model.frame import rotated_rectangle

__all__ = ["ribbon_contact_steps", "AT"]

#: where the declared line stands along each chord, from the higher kerb
AT = 0.25
#: the patch writes elevations to the centimetre (``publication``'s own)
_EMIT_Z_ROUND_M = 0.01


def ribbon_contact_steps(planar: PlanarMap, law: Law,
                         z: _t.Sequence[float] | None = None) -> list[dict[str, _t.Any]]:
    """One ``terrace_joints`` record (``kind`` ``road_contact_step``) per
    ribbon face whose kerb-to-kerb chords between two AIRSIDE stage
    vertices exceed the ribbon's transverse cap — the 30aa rule 7 step,
    declared at the higher contact.  Empty before a solve."""
    if z is None:
        return []
    from ..law.tables import role_cap
    from ..solve.design_roles import airside_stage_vertices
    air = set(airside_stage_vertices(planar, law))
    floor = float(law.tables.emit.materiality.elevation_m)
    # a CLIFF only (§31 (7): steeper than the design surface's own 1:3
    # bank): a steep-but-rollable chord is a slope the census prices by
    # its cap, and a declared line inside a runway strip is itself a
    # defect (``terrace_joint_strip``) — measured: -18556 at 30.0966385,
    # 31.4178300 read 2.69 m there when every over-cap chord was declared
    bank = float(law.tables.emit.design.bank_slope)
    out: list[dict[str, _t.Any]] = []
    for f in planar.faces.values():
        if f.role != "service_road" or not is_osm_ribbon_ref(f.ref):
            continue
        cap = role_cap(law, f.role)
        if cap is None:
            continue
        cap_t = min(float(cap.transverse), float(cap.longitudinal))
        ring = planar.ring_vertices(f.ring)
        kerb = [v for v in dict.fromkeys(ring) if v in air]
        if len(kerb) < 2:
            continue
        poly = Polygon([planar.vertices[v].xy for v in ring])
        if not poly.is_valid:
            poly = poly.buffer(0.0)
        chords: list[tuple[int, int, float]] = []
        for i, a in enumerate(kerb):
            ax, ay = planar.vertices[a].xy
            for b in kerb[i + 1:]:
                bx, by = planar.vertices[b].xy
                d = math.hypot(ax - bx, ay - by)
                if d <= 0.0:
                    continue
                dz = abs(float(z[a]) - float(z[b]))
                if dz <= floor or dz <= max(cap_t, bank) * d:
                    continue
                # a CHORD ACROSS the ribbon (its midpoint strictly inside),
                # never a pair along one kerb
                if not poly.contains(Point((ax + bx) / 2.0, (ay + by) / 2.0)):
                    continue
                hi, lo = (a, b) if float(z[a]) >= float(z[b]) else (b, a)
                chords.append((hi, lo, dz))
        if not chords:
            continue
        # the line: AT of the way along EVERY declared chord from its higher
        # kerb vertex, ordered along the ribbon's long axis; a chord the line
        # does not cross properly gets a short line of its own across it
        from shapely.geometry import LineString
        rect = rotated_rectangle(poly)
        cs = list(rect.exterior.coords)
        e0 = (cs[1][0] - cs[0][0], cs[1][1] - cs[0][1])
        e1 = (cs[2][0] - cs[1][0], cs[2][1] - cs[1][1])
        ax_ = e0 if math.hypot(*e0) >= math.hypot(*e1) else e1

        def at(hi: int, lo: int) -> tuple[float, float]:
            hx, hy = planar.vertices[hi].xy
            lx, ly = planar.vertices[lo].xy
            return (hx + AT * (lx - hx), hy + AT * (ly - hy))
        pts = sorted(dict.fromkeys(at(h, l) for h, l, _dz in chords),
                     key=lambda p: p[0] * ax_[0] + p[1] * ax_[1])
        lines = [pts] if len(pts) >= 2 else []
        line = LineString(pts) if len(pts) >= 2 else None
        for hi, lo, _dz in chords:
            seg = LineString([planar.vertices[hi].xy, planar.vertices[lo].xy])
            if line is not None and seg.crosses(line):
                continue
            (px, py) = at(hi, lo)
            hx, hy = planar.vertices[hi].xy
            lx, ly = planar.vertices[lo].xy
            n = math.hypot(lx - hx, ly - hy) or 1.0
            nx, ny = -(ly - hy) / n * 0.25, (lx - hx) / n * 0.25
            lines.append([(px - nx, py - ny), (px + nx, py + ny)])
        to_ll = _to_ll(planar)
        step = max(dz for _h, _l, dz in chords) + _EMIT_Z_ROUND_M
        for ln in lines:
            out.append({"points": [list(to_ll(x, y)) for x, y in ln],
                        "step_m": round(step, 4), "declared_step_m": round(step, 4),
                        "faced": False, "kind": "road_contact_step", "faces": [],
                        "shapes": [str(f.ref)], "gap": True, "roles": [f.role],
                        "pairs": len(chords), "length_m": 0.0})
    return out


def _to_ll(planar: PlanarMap) -> _t.Callable[[float, float], tuple[float, float]]:
    """Plan metres -> (lat, lon), an affine least-squares fit over the map's
    own vertex keys (no frame here: at a patch's scale the frame's local
    tangent plane is affine to well under a centimetre)."""
    import numpy as np
    vs = list(planar.vertices.values())
    vs = vs[:: max(1, len(vs) // 400)]
    M = np.array([[v.xy[0], v.xy[1], 1.0] for v in vs])
    lat = np.linalg.lstsq(M, np.array([v.key[0] for v in vs]), rcond=None)[0]
    lon = np.linalg.lstsq(M, np.array([v.key[1] for v in vs]), rcond=None)[0]

    def f(x: float, y: float) -> tuple[float, float]:
        return (float(lat[0] * x + lat[1] * y + lat[2]),
                float(lon[0] * x + lon[1] * y + lon[2]))
    return f
