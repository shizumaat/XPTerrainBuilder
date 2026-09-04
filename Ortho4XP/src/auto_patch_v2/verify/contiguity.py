"""``lateral_contiguity`` over the emitted rings (v1
``check_grade._check_lateral_contiguity``, the fourth reader): every
road-family ring is re-walked with the SAME station walk the generator
used (``constraints.contiguity._cross_section`` over the emitted
polygons), and a station is a row when the cap the ring was BUILT to —
the role cap, the way-level ``o4_grade_law_cap``, and the PUBLISHED
``station_caps`` value at that station, whichever is strictest — is
looser than the re-walked law cap.  Unlike the oracle (which trusts a
published cap as the law there), this reader prices the publication
against its own walk, so an emitter that published a looser cap than
the cross-section carries is caught, never blessed."""
from __future__ import annotations

from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

from ..constraints.contiguity import _cross_section
from ..constraints.geometry import long_axis
from ..constraints.roads import road_family_roles
from .frame import Patch, Row, row

__all__ = ["lateral_contiguity"]


def lateral_contiguity(p: Patch) -> list[Row]:
    law = p.law
    lc = law.tables.emit.lateral_contiguity
    roads = road_family_roles(law)
    polys: list[Polygon] = []
    caps: list[float] = []
    roles: list[str] = []
    shapes = []
    for sh in p.shapes:
        cap = p.cap(sh)
        if cap is None or len(sh.xy) < 3:
            continue
        poly = Polygon(sh.xy)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        polys.append(poly)
        # the LAW cap of a class is its role cap (never the way tag)
        from ..law.tables import role_cap
        rc = role_cap(law, sh.role, sh.code_number, sh.code_letter)
        caps.append(rc.longitudinal if rc is not None else cap)
        roles.append(sh.role)
        shapes.append(sh)
    if not polys:
        return []
    tree = STRtree(polys)
    published = [(p.to_m(float(e[0]), float(e[1])), float(e[2]))
                 for e in (p.publication.get("station_caps") or [])]
    out: list[Row] = []
    for k, sh in enumerate(shapes):
        if sh.role not in roads:
            continue
        built = p.cap(sh)
        if built is None:
            continue
        axis = long_axis(list(sh.xy))
        if axis is None:
            continue
        (ux, uy), length, mid = axis
        nx, ny = -uy, ux
        n_st = max(1, int(length / lc.station_step_m))
        for i in range(n_st):
            t = -0.5 * length + length * (i + 0.5) / n_st
            px, py = mid[0] + ux * t, mid[1] + uy * t
            if not polys[k].contains(Point(px, py)):
                continue
            present = _cross_section(px, py, nx, ny, lc.probe_m, lc.gap_tol_m,
                                     lc.min_member_m, tree, polys, roles, k)
            if not present:
                continue
            law_cap = min(caps[j] for j in present)
            b = built
            if published:
                pc = min(published, key=lambda e: (e[0][0] - px) ** 2 + (e[0][1] - py) ** 2)[1]
                b = min(b, pc)
            if b <= law_cap + 1e-12:
                continue
            out.append(row("lateral_contiguity", (sh.role, sh.role), p.side(sh.role),
                           b - law_cap, 100.0 * b, 100.0 * law_cap, 0.0,
                           (px, py), (px, py), sh.key, sh.key))
    out.sort(key=lambda r: -r["magnitude_m"])
    return out
