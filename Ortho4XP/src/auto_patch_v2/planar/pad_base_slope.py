"""THE PAD UNDER A SLOPED BASE TAKES THE OBJECT'S AUTHORED PLANE (owner
RULINGS 2026-11-19o (1), amending 2026-09-09c's flat target; #2184) — the
ONE derivation of which pad is sloped and by how much.

Owner 2026-11-19T15:06Z: "taking into account the shape of the bottom of
objects that were designed to fit on a hill".  RULED (19o): a planar
sloped base gets a pad ON THAT PLANE — the 09c 1 % allowance measured from
it, the plane capped at the pavement law (``[common] pavement_max_grade``,
5 %); a flat base keeps the flat target.

THE READ IS THE PACK'S OWN.  ``airport/obj8_grade.base_profile`` already
classifies every member's authored bottom (FLAT / STEPPED / SLOPED / FEET,
base-profile spec §1 (2)) and publishes a SLOPED member's contact-plane
gradient in its AUTHORED frame.  This module only:

* admits a SLOPED member as a PLANE where its fit is within
  ``[base_profile] sloped_pad_rms_m`` (the 12y pavement visibility bar) —
  MEASURED KASE: ``Objects/test.obj`` (the covered aircraft parking, 116
  column feet) fits 1.90 % at rms 0.001 m, the pack's eleven other SLOPED
  members 0.10-0.28 m (uneven contact geometry, not an authored plane);
* rotates the gradient into the airport frame by the placement heading
  (``obj8_grade._place_matrix``, the matrix every base polygon is placed
  with) and caps its magnitude at the pavement law, keeping its direction;
* hands it to the pad the member's §16g cluster IS (the cluster whose
  outline covers the most of the pad, as ``pad_blocks.unit_base`` reads a
  pad's unit) when every placement of the cluster's resources agrees.

READERS (the consumer census, RULINGS 2026-08-30l, in
``tests/auto_patch_v2/test_pad_base_slope.py``): ``planar/platform`` (a
sloped pad is not HELD flat at a datum), ``constraints/pad_relief`` (the
offsets: the plate's target AND its 1 % ceiling, the sidecar the verify
and the census read).  No mesh, no DEM: the pack, the frame and the law.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

__all__ = ["SlopeField", "sloped_pads"]


@_dc.dataclass(frozen=True)
class SlopeField:
    """One sloped pad's authored plane in the airport frame: the terrain
    target at ``(x, y)`` is the pad's level plus :meth:`offset`."""

    gx: float
    gy: float
    #: the plane's reference point: the member's placement origin
    x0: float
    y0: float
    #: the gradient as authored, and the magnitude the pad carries (the
    #: same where the authored grade is within the pavement law)
    authored: float
    grade: float
    member: str

    def offset(self, x: float, y: float) -> float:
        """Metres the authored base stands above its value at the origin."""
        return self.gx * (x - self.x0) + self.gy * (y - self.y0)


def _qualifies(member: _t.Any, rms_max: float) -> bool:
    bp = getattr(member, "base_profile", None) or {}
    return (rms_max > 0.0 and bp.get("verdict") == "sloped"
            and float(bp.get("residual_rms_m", math.inf)) <= rms_max
            and getattr(member, "origin", None) is not None)


def _member_field(member: _t.Any, to_xy: _t.Callable, cap: float) -> SlopeField | None:
    """The member's authored base plane in the frame ``to_xy(lon, lat)``,
    its magnitude capped at ``cap`` (direction kept); ``None`` for a
    member whose profile carries no gradient."""
    from ..airport.obj8_grade import _place_matrix
    from ..model.frame import m_per_deg_exact
    bp = getattr(member, "base_profile", None) or {}
    sl = bp.get("slope") or (0.0, 0.0)
    a, b, d, e, _xo, _yo = _place_matrix(0.0, 0.0, float(member.heading_deg))
    # authored (x, z) -> metres east / north: a gradient is a covector, and
    # the placement is a rotation, so it maps as the vector does
    gE = a * float(sl[0]) + b * float(sl[1])
    gN = d * float(sl[0]) + e * float(sl[1])
    lat, lon = float(member.origin[0]), float(member.origin[1])
    ml, mo = m_per_deg_exact(lat)
    x0, y0 = to_xy(lon, lat)
    xe, ye = to_xy(lon + 100.0 / mo, lat)
    xn, yn = to_xy(lon, lat + 100.0 / ml)
    # J: metres east / north -> frame metres; the frame gradient is J^-T g
    j11, j21 = (xe - x0) / 100.0, (ye - y0) / 100.0
    j12, j22 = (xn - x0) / 100.0, (yn - y0) / 100.0
    det = j11 * j22 - j12 * j21
    if det == 0.0:
        return None
    gx = (j22 * gE - j21 * gN) / det
    gy = (-j12 * gE + j11 * gN) / det
    g = math.hypot(gx, gy)
    if g <= 0.0:
        return None
    k = min(1.0, cap / g) if cap > 0.0 else 1.0
    return SlopeField(gx * k, gy * k, float(x0), float(y0), g, g * k,
                      str(getattr(member, "resource", "")))


_INDEX: dict[int, tuple] = {}


def _cluster_index(airport: _t.Any, law: _t.Any) -> tuple[list, _t.Any]:
    """``([(outline, field or None)], STRtree)`` over the airport's §16g
    clusters, once per airport: each cluster's outline and the plane its
    members agree on."""
    hit = _INDEX.get(id(airport))
    if hit is not None and hit[0] is airport and hit[1] is law:
        return hit[2], hit[3]
    part = getattr(airport, "partition", None)
    units = {str(getattr(u, "id", "")): u for u in (getattr(part, "units", ()) or ())}
    to_xy = airport.frame.entry()
    rms_max = float(law.tables.structures.base_profile.sloped_pad_rms_m)
    cap = float(law.tables.common.pavement_max_grade)
    agree = float(law.tables.emit.materiality.grade)
    rows: list = []
    for c in getattr(airport, "clusters", ()) or ():
        polys = []
        for r in getattr(c, "rings", ()) or ():
            if len(r) >= 3:
                q = Polygon([to_xy(float(lo), float(la)) for la, lo in r])
                q = q if q.is_valid else q.buffer(0.0)
                if not q.is_empty and q.area > 0.0:
                    polys.append(q)
        if not polys:
            continue
        u = units.get(str(getattr(c, "unit", "")))
        want = set(getattr(c, "members", ()) or ())
        mems = [m for m in (getattr(u, "members", ()) or ()) if str(m.resource) in want]
        field = None
        if mems and all(_qualifies(m, rms_max) for m in mems):
            fs = [_member_field(m, to_xy, cap) for m in mems]
            if all(f is not None for f in fs) and all(
                    math.hypot(f.gx - fs[0].gx, f.gy - fs[0].gy) <= agree for f in fs):
                field = fs[0]
        rows.append((unary_union(polys), field))
    tree = STRtree([g for g, _f in rows]) if rows else None
    _INDEX.clear()
    _INDEX[id(airport)] = (airport, law, rows, tree)
    return rows, tree


def sloped_pads(pads: _t.Iterable[tuple[str, Polygon]], airport: _t.Any, law: _t.Any
                ) -> dict[str, SlopeField]:
    """``{pad ref: its authored plane}`` for every pad ``(ref, plan
    polygon)`` whose cluster — the one covering most of it, and at least
    half of it — stands on a sloped base plane (module doc).  Empty where
    the airport carries no clusters or the law is disarmed."""
    if airport is None or not getattr(airport, "clusters", None):
        return {}
    if float(law.tables.structures.base_profile.sloped_pad_rms_m) <= 0.0:
        return {}
    rows, tree = _cluster_index(airport, law)
    if tree is None:
        return {}
    out: dict[str, SlopeField] = {}
    for ref, P in pads:
        if P is None or P.is_empty or P.area <= 0.0:
            continue
        best, field = 0.0, None
        for j in tree.query(P, predicate="intersects"):
            g, f = rows[int(j)]
            try:
                a = g.intersection(P).area
            except Exception:  # noqa: BLE001 — a degenerate outline
                continue
            if a > best:
                best, field = a, f
        if field is not None and best >= 0.5 * P.area:
            prev = out.get(str(ref))
            out[str(ref)] = field if prev is None else prev
    return out
