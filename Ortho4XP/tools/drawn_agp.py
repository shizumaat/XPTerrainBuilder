"""LIBRARY of ``tools/harness/drawn_gate.py``: DO THE FLOORS OF JOINED
``.agp`` GROUPS MEET AS X-PLANE DRAWS THEM (#2090).

An ``.agp`` is drawn rigid on the drawn ground under its ``GROUND_PT``
(``auto_patch_v2.airport.agp_pieces``).  Two on-ground ``.agp`` rows whose
connector floors meet (``auto_patch_v2.airport.agp_ground.joins``: KDEN's
Concourse A sky bridge running into the Jeppesen terminal's bridge ramps)
are judged here on the WRITTEN pack: each row's drawn datum is the drawn
mesh at its ground point, and the JOIN's misfit is

    (datum_b - datum_a) - step

where ``step`` is the datum difference the floors of the written files
ask for (a lifted copy's ``OBJ_DELTA`` heights included).  ``|misfit|``
over :data:`JOIN_BAR_M` (the seam bar) is a FAIL: a floor that steps up or
down where the author drew one floor.  Read-only; it derives no law.
"""
from __future__ import annotations

import glob
import math
import os
import tempfile

#: a floor joint the sim shows as a step over this fails (the seam bar)
JOIN_BAR_M = 0.3


def lifted_or_near(sites):
    """``keep`` for :func:`join_rows`: a member written as a lifted copy
    (``<stem>__g_<hash>.agp``) or whose row stands within 600 m of a site
    ``(name, lat, lon, r)``."""
    def keep(m):
        if "__g_" in m.resource:
            return True
        kx = 111_320.0 * math.cos(math.radians(m.lat))
        return any(math.hypot((m.lon - lon) * kx, (m.lat - lat) * 111_320.0) <= 600.0 + r
                   for _n, lat, lon, r in sites)
    return keep


def written_rows(pack_root: str, tile: str, tool: str):
    """The written DSF dump of ``tile`` in ``pack_root`` (``None`` when
    the pack writes no DSF there)."""
    from auto_patch_v2.airport.dsf import read_dump
    from auto_patch_v2.airport.dsf_write import dump
    dsfs = sorted(glob.glob(os.path.join(pack_root, "Earth nav data", "*", f"{tile}.dsf")))
    if not dsfs:
        return None
    with tempfile.TemporaryDirectory(prefix="drawn_agp_") as work:
        text = os.path.join(work, "w.txt")
        dump(dsfs[0], text, tool)
        return read_dump(text, accept_polygon=lambda _p: False)


def join_rows(dump, pack_root: str, z, keep=None) -> list[dict]:
    """One record per join of the written rows: the two rows, their
    files, drawn datums, the step the floors ask for, the misfit and the
    verdict.  ``z(lon, lat)`` is the drawn mesh (NaN off it).  ``keep(m)``
    (default: every member) names the members whose joins are read -- a
    pair is read when either member is kept (reading every pair of a
    jetway-heavy pack costs minutes: KEWR 292 s)."""
    from auto_patch_v2.airport import agp_ground as _ag
    from auto_patch_v2.airport import agp_pieces as _ap
    members = _ag.candidates(dump, pack_root)
    kept = [True] * len(members) if keep is None else [bool(keep(m)) for m in members]
    out = []
    steps = _ag.joins(members, lambda i, j: kept[i] or kept[j])
    for (i, j), jn in sorted(steps.items()):
        a, b = members[i], members[j]
        za = z(*_ap.ground_point(a.agp, a.lon, a.lat, a.heading_deg))
        zb = z(*_ap.ground_point(b.agp, b.lon, b.lat, b.heading_deg))
        misfit = (zb - za) - jn.step
        ok = not (math.isnan(za) or math.isnan(zb))
        out.append({"site": f"join obj{a.index}+obj{b.index}", "lat": round(jn.lat, 7),
                    "lon": round(jn.lon, 7), "rows": [a.index, b.index],
                    "files": [a.resource, b.resource],
                    "datums": [round(za, 2), round(zb, 2)], "step": round(jn.step, 2),
                    "delta": round(misfit, 2) if ok else None,
                    "verdict": ("NOT MEASURED" if not ok else
                                "FAIL" if abs(misfit) > JOIN_BAR_M else "PASS"),
                    "fails": ([f"joined floors {misfit:+.2f} m apart (datums "
                               f"{za:.2f} / {zb:.2f}, step {jn.step:+.2f})"]
                              if ok and abs(misfit) > JOIN_BAR_M else [])})
    return out
