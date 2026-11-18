"""THE HAND-ROLE REPLAY ARM of ``tools/v2_solve_replay.py`` (lane lkbna15,
#2112 / #2134): re-role named pavement SOURCES in a replay's classification
before the planar map is built, to price what a corrected classification
would do downstream — without a classifier change.

``--hand-role dsf:pol267=primary_parallel`` gives every cell of source
``dsf:pol267`` whose role is NOT already taxi family or a non-pavement role
(runway, shoulder, building, strip) the named role.  It reads the shipped
#1697 hand-set-role table (``airport.user_roles.CHOOSABLE``) for the roles
a user may set, and differs from ``user_roles.apply`` in two arm-only ways,
both printed:

* a cell already in the TAXI FAMILY keeps its role (the source's own
  ``secondary_parallel`` corridor stays one), so the arm moves only the
  cells the classifier put outside the family;
* a re-roled taxi-family cell takes the CODE LETTER / NUMBER of the
  largest taxi-family cell of the same source, else of the nearest
  taxi-family cell anywhere (the taxi law is lettered; the #1697 path
  leaves ``None``).

An EXTRACT-ONLY measurement switch: nothing in ``src/`` reads it.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["force_roles"]


def _poly(c):
    from shapely.geometry import Polygon
    p = Polygon(c.ring, c.holes)
    return p if p.is_valid else p.buffer(0.0)


def force_roles(cl, pairs: _t.Mapping[str, str], side_of: _t.Callable[[str], str]
                ) -> tuple[object, list[str]]:
    """``(classification, report lines)`` with ``pairs`` (source -> role)
    applied as the module doc says."""
    from auto_patch_v2.airport.user_roles import CHOOSABLE, source_of
    from auto_patch_v2.classify.roles import TAXI_FAMILY
    roles = {r for r, _ in CHOOSABLE}
    bad = [f"{s}={r}" for s, r in pairs.items() if r not in roles]
    if bad:
        raise SystemExit(f"--hand-role: not a choosable role: {', '.join(bad)} "
                         f"(choosable: {', '.join(sorted(roles))})")
    taxi = [c for c in cl.cells if c.role in TAXI_FAMILY and c.code_letter]
    out, lines = [], []
    for c in cl.cells:
        src = source_of(c.ref) or c.ref
        role = pairs.get(src)
        if role is None or c.role not in roles or c.role in TAXI_FAMILY:
            out.append(c)
            continue
        num, let = c.code_number, c.code_letter
        if role in TAXI_FAMILY:
            same = [t for t in taxi if (source_of(t.ref) or t.ref) == src]
            if same:
                donor = max(same, key=lambda t: _poly(t).area)
            else:
                p = _poly(c)
                donor = min(taxi, key=lambda t: _poly(t).distance(p)) if taxi else None
            if donor is not None:
                num, let = donor.code_number, donor.code_letter
        out.append(_dc.replace(c, role=role, side=side_of(role), code_number=num,
                               code_letter=let,
                               evidence={**c.evidence, "user_role": role,
                                         "classified_as": c.role}))
        lines.append(f"hand-role arm: cell {c.id} {c.ref} {c.role} -> {role} "
                     f"(letter {let}, {_poly(c).area:,.0f} m2)")
    missing = sorted(set(pairs) - {source_of(c.ref) or c.ref for c in cl.cells})
    lines += [f"hand-role arm: source {s} names no cell" for s in missing]
    return _dc.replace(cl, cells=tuple(out)), lines
