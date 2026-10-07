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
from ..law.tables import zone2_half_width_m
from ..model.frame import rotated_rectangle

__all__ = ["strip_keepout"]


def strip_keepout(classification: Classification, law: Law):
    """The RUNWAY STRIP keep-out: every runway-family cell's long axis,
    extended by the end-skirt corridor at both ends, buffered to the
    zone-2 (strip) half width — a joint touching it is never declared."""
    polys = []
    rw_roles = set(law.tables.precedence.runway_family.members)
    cl = law.ruleset.end_skirt.corridor_length_m
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
        end = (cl.value(c.code_number, c.code_letter) if cl is not None else 0.0) or 0.0
        rect = rotated_rectangle(poly)
        pts = list(rect.exterior.coords)[:4]
        if len(pts) < 4:
            polys.append(poly.buffer(half))
            continue
        sides = [(math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]), k)
                 for k in range(3)] + [(math.hypot(pts[0][0] - pts[3][0], pts[0][1] - pts[3][1]), 3)]
        _l, k = max(sides)
        p, q = pts[k], pts[(k + 1) % 4]
        r, s = pts[(k + 3) % 4], pts[(k + 2) % 4]
        a = ((p[0] + r[0]) / 2.0, (p[1] + r[1]) / 2.0)
        b = ((q[0] + s[0]) / 2.0, (q[1] + s[1]) / 2.0)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0.0:
            polys.append(poly.buffer(half))
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        axis = LineString([(a[0] - ux * end, a[1] - uy * end), (b[0] + ux * end, b[1] + uy * end)])
        width = max(half, poly.area / max(L, 1.0) / 2.0)
        polys.append(axis.buffer(width, cap_style="flat").union(poly.buffer(half)))
    return unary_union(polys) if polys else None
