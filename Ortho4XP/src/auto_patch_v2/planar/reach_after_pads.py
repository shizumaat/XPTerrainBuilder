"""AIRCRAFT REACHABILITY, READ AGAIN ONCE THE BUILDINGS STAND (#1302; owner
RULINGS 2026-10-19ag, 2026-10-27h).

19ag: "pavement aircraft can reach only through a passage too narrow to
manoeuvre is groundside", and a building divides when aircraft cannot get
around it.  ``classify/reachability`` reads it on the pavement pages, BEFORE
the building pads are cut out of them -- a page drawn under a terminal is
room there.  MEASURED LFPG T2: ``dsf:pol459`` (507,378 m2) runs from the
stands under the halls into the 43,482 m2 central corridor between 2E and
2F; read whole it is reachable, so the corridor stayed apron, solved at
103.2-104.1 m between lower levels held at 97.8 m.

HERE, after ``pad_cut.apron_cut_to_pads`` (the apron cut back to every pad
it carries), the same read (``reachability.unreachable_aprons``, the one
derivation) runs on each connected piece of every apron region the pads
cut apart: a piece whose room is all beyond, a lot by that read's own
test, with no startup on it, while another piece of the same page stays
reachable, is GROUNDSIDE -- ``<ref>#beyond<k>`` with the role
``open_default.unclassified_groundside_role`` names.  A page wholly beyond
is classify's to judge, as it judged it.  The pads join the
pavement for the "joined to the taxi network" read only (``bridge``): a
piece the pads enclose is pavement among buildings, never a detached
island.  The pieces aircraft reach keep the region whole.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..law.tables import role_side

__all__ = ["BEYOND", "unreachable_after_pads"]

#: the ref spelling of an apron piece made groundside here
BEYOND = "#beyond"


def unreachable_after_pads(base_regions: list, pad_regions: _t.Sequence, law, airport
                           ) -> "tuple[list, dict]":
    """``(base_regions, counts)``: the regions with every apron piece aircraft
    cannot reach once the pads stand made groundside (module docstring)."""
    from ..classify.reachability import unreachable_aprons
    from ..classify.rules import load_rules
    cells = [(i, r) for i, r in enumerate(base_regions)
             if r.source == "cell" and r.polygon is not None and not r.polygon.is_empty]
    if not any(r.role == "apron" for _i, r in cells):
        return base_regions, {}
    entries: list[list] = []
    owner: list[int] = []
    for i, r in cells:
        if r.role == "apron":
            for q in nonempty_polygon_parts(r.polygon):
                entries.append([r.role, r.ref, q, r.code_letter, {}, r.role])
                owner.append(i)
        elif role_side(law, r.role) == "airside":
            entries.append([r.role, r.ref, r.polygon, r.code_letter, {}, r.role])
            owner.append(i)
    runways = [r.polygon for _i, r in cells if r.role in ("runway", "runway_crossing")]
    pads = unary_union([r.polygon for r in pad_regions
                        if r.polygon is not None and not r.polygon.is_empty])
    starts = [s.xy for s in getattr(airport, "startups", ()) or ()]
    rep = unreachable_aprons(entries, runways, law, load_rules(), starts, bridge=pads)
    if not rep.get("reach_demoted"):
        return base_regions, {"reach_after_pads": 0}
    kept: dict[int, list] = {}
    lost: dict[int, list] = {}
    for (role, _ref, q, _l, _e, _k), i in zip(entries, owner, strict=True):
        if base_regions[i].role != "apron":
            continue
        (kept if role == "apron" else lost).setdefault(i, []).append((role, q))
    # a page wholly beyond is classify's verdict to give
    # (``classify/reachability``), never this split's: only a page the pads
    # cut into pieces aircraft reach and pieces they do not is split
    reached = {str(base_regions[i].ref) for i in kept}
    out: list = []
    n, m2 = 0, 0.0
    for i, r in enumerate(base_regions):
        if i not in lost or str(r.ref) not in reached:
            out.append(r)
            continue
        if kept.get(i):
            out.append(_dc.replace(r, polygon=unary_union([q for _r, q in kept[i]])))
        for k, (role, q) in enumerate(lost[i], 1):
            out.append(_dc.replace(r, role=role, ref=f"{r.ref}{BEYOND}{k}", polygon=q,
                                   side=role_side(law, role)))
            n += 1
            m2 += float(q.area)
    return out, {"reach_after_pads": n, "reach_after_pads_m2": round(m2, 1)}
