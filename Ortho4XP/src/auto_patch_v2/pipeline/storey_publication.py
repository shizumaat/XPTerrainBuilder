"""THE ``storey_shells`` SIDECAR KEY (#2062, RULINGS 2026-11-13w; spec
``2062-storey-shell-spec`` §3 R1 step 5): one record per storey shell the
map carries (``model.storey_shell``), in lat/lon, with the SOLVED zero.

A REPORT key the drawn check reads (``tools/drawn_check.check_storey``: at
every run the drawn ground stands at ``zero + foot``); no census family
prices it.  ``block_z`` is the solved height of the block (its pad's face,
the median of its vertices), ``zero`` = ``block_z - levels[block]``."""
from __future__ import annotations

import statistics as _st
import typing as _t

from ..geom.parts import nonempty_polygon_parts as _parts

__all__ = ["storey_shell_records"]


def storey_shell_records(planar, airport, z: "_t.Sequence[float] | None") -> list[dict]:
    """The ``storey_shells`` records (module docstring)."""
    shells = tuple(getattr(planar, "storey_shells", ()) or ())
    if not shells:
        return []
    to_ll = airport.frame.transformers()[1]

    def ll(pts) -> list:
        return [[round(float(a), 8), round(float(b), 8)]
                for a, b in (to_ll(x, y) for x, y in pts)]
    out = []
    for sh in shells:
        vs = sorted({v for f in planar.faces.values() if f.ref == sh.pad_ref
                     for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)})
        block_z = (round(float(_st.median(float(z[v]) for v in vs)), 3)
                   if z is not None and vs else None)
        lat, lon = to_ll(*sh.anchor_xy)
        out.append({
            "id": sh.id, "pad_ref": sh.pad_ref, "member_ids": list(sh.member_ids),
            "resources": list(sh.paths), "levels": [round(float(y), 3) for y in sh.levels],
            "block": sh.block, "level_refs": list(sh.level_refs), "block_z": block_z,
            "zero": None if block_z is None else round(block_z - float(sh.levels[sh.block]), 3),
            "anchor_longitude_latitude": [round(float(lon), 8), round(float(lat), 8)],
            "plan_ll": ll(sh.plan), "pad_ll": ll(sh.pad),
            "scope": sh.scope, "kerbs": len(sh.kerbs),
            # the cut's FLOOR: the back cut less its kerb (the riser up to the lot)
            "back_cut_ll": [ll(q.exterior.coords) for q in _parts(
                sh.back_cut if sh.kerb is None or sh.back_cut is None
                else sh.back_cut.difference(sh.kerb))],
            "runs": [{"ll": ll(r.xy), "foot": r.foot, "level": r.level, "minor": r.minor,
                      "airside": r.airside, "back_cut_m": r.back_cut_m,
                      "clipped_by": list(r.clipped_by)} for r in sh.runs]})
    return out
