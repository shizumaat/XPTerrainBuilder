"""THE RUNWAY STRIP KEEP-OUT (06n; owner 2026-08-01: walls at runway edges
are never lawful) — the region inside which a boundary edge WELDS its two
bodies and no joint is declared (``planar/shapes._weld_strip``).  Split out
of ``shapes.py`` by the planar layer's 1,000-line budget, as the apron law
(``shape_airside``), the mouth weld (``shape_mouths``) and the gap parts
(``shape_parts``) were: the keep-out is a region derived from the
classification alone, never from the map."""
from __future__ import annotations

import math

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..classify.roles import Classification, is_runway_shoulder
from ..law import Law
from ..law.tables import runway_safety_area_length_m, zone2_half_width_m
from ..geom.rotated_rect import long_axis, rotated_rectangle

__all__ = ["strip_keepout"]


def strip_keepout(classification: Classification, law: Law):
    """The RUNWAY STRIP keep-out: every runway-family cell's long axis,
    extended by the end-skirt corridor at both ends, buffered to the
    zone-2 (strip) half width — a joint touching it is never declared."""
    polys = []
    rw_roles = set(law.tables.precedence.runway_family.members)
    for c in classification.cells:
        # §40 (4): a SHOULDER manufactures no region (the same rule the
        # strip keep-out in ``planar/structures`` and the zone bands
        # follow) — its host runway's keep-out already covers it
        if c.role not in rw_roles or len(c.ring) < 3 or is_runway_shoulder(c):
            continue
        poly = Polygon(c.ring)
        if poly.is_empty or poly.area <= 0.0:
            continue
        half = zone2_half_width_m(law, "runway", c.code_number, c.code_letter) or 0.0
        # the RSA length (owner RULINGS 2026-10-15c (2)), from the slab end:
        # a keep-out may overshoot the band by the overrun, never fall short
        # a cell carries no instrument status (RULINGS 2026-10-15k): the
        # longer of the two, so the keep-out never falls short of the band
        end = max(runway_safety_area_length_m(law, c.code_number, c.code_letter, ins)
                  for ins in (False, True))
        ab = long_axis(rotated_rectangle(poly))
        if ab is None:
            polys.append(poly.buffer(half))
            continue
        a, b = ab
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        axis = LineString([(a[0] - ux * end, a[1] - uy * end), (b[0] + ux * end, b[1] + uy * end)])
        width = max(half, poly.area / max(L, 1.0) / 2.0)
        polys.append(axis.buffer(width, cap_style="flat").union(poly.buffer(half)))
    return unary_union(polys) if polys else None
