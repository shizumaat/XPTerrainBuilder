"""``transverse`` over the emitted rings: the transect walk
(``constraints.geometry.walk_transects`` — the census's own station set,
owner 2026-08-21) driven by the PUBLISHED axes, budget ``cT × width``
plus the crossed role's instrument envelope."""
from __future__ import annotations

from ..constraints.geometry import TransectAxis, TransectShape, walk_transects
from ..constraints.transverse import priced_roles
from .frame import Patch, Row, noise_m, row

__all__ = ["transverse"]


def transverse(p: Patch) -> list[Row]:
    law = p.law
    tw = law.tables.emit.transect
    axes: list[TransectAxis] = []
    for k, entry in enumerate(p.publication.get("axes") or []):
        pts = [p.to_m(float(la), float(lo)) for la, lo in entry[0]]
        if len(pts) < 2:
            continue
        svc = bool(entry[4]) if len(entry) > 4 else False
        axes.append(TransectAxis(pts, float(entry[1]), svc, key=(k, float(entry[2]))))
    roles = priced_roles(law, False) | priced_roles(law, True)
    shapes = [TransectShape(sh.role, sh.closed_ring, sh.key)
              for sh in p.shapes if sh.role in roles and len(sh.ids) >= 3]
    by_key = {sh.key: sh for sh in p.shapes}
    out: list[Row] = []
    for st in walk_transects(shapes, axes, lambda ax: priced_roles(law, ax.is_service),
                             step_m=tw.step_m, half_m=tw.half_width_m,
                             min_width_m=tw.min_width_m, max_gap_m=tw.max_gap_m):
        cap_t = st.axis_key[1] if isinstance(st.axis_key, tuple) else st.cap_l
        sh = by_key[st.shape_key]
        allow = cap_t * st.width_m + noise_m(law, sh.role)
        dz = abs(st.z_hi - st.z_lo)
        if dz <= allow:
            continue
        out.append(row("transverse", (sh.role, sh.role), p.side(sh.role), dz,
                       100 * dz / st.width_m, 100 * cap_t, st.width_m,
                       st.point_lo(), st.point_hi(), sh.key, sh.key))
    out.sort(key=lambda r: -r["grade_pct"])
    return out
