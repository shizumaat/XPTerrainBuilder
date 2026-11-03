"""A HUNG ROW RIDES THE UNIT IT STANDS IN (issue #1726; owner RULINGS
2026-10-22o "connected objects stay as one group", 2026-11-02 / 22o / 23e:
object groups under a metre apart seat together).

A multi-anchor row the plan dropped (one file, N rows: KBWI's 48
``GateDoor`` rows, the ``Style3`` jetway heads and extensions) is seated
on its row (``footprint_unit.msl_seats_for_dump``).  Standing on the
unit's pad it takes the unit's zero; anywhere else it took the design
surface at its own anchor — right for a vehicle or a light mast, whose
geometry stands on its origin, and wrong for a door or a jetway head,
whose geometry HANGS metres above its origin on the building's wall: the
drape put KBWI's doors on whatever face lay under the anchor, 0.2-0.9 m
off the terminal they hang on.

The witness is the geometry, never a name: a resource EVERY vertex of
which (animated and draped ones too: a walking figure's legs, a jetway's
telescoping strut reach the ground) stands more than ``[rebake]
elevated_base_m`` above its origin has no ground of its own (the reading
that makes a plan part ELEVATED, v1 I-8), so a row of it inside a unit's
box rides that unit's zero.  ROWS SHARING ONE ORIGIN ARE ONE RIGID SET
(``msl_feet``'s rule): a sign panel placed at its post's origin hangs on
the POST, so a row hangs only where every row at its origin point does (KIAH's
6.4 m road-sign panels at their posts' origins stay with the posts)."""
from __future__ import annotations

import os
import typing as _t

__all__ = ["hung_resources", "hung_rows"]


def hung_resources(pack_root: str, elevated_m: float
                   ) -> "_t.Callable[[str], bool] | None":
    """``def_path -> bool``: does the pack resource's static geometry stand
    wholly above its origin (every vertex) by more than ``elevated_m``?  ``None`` (the
    rule disarmed) where ``elevated_m`` is 0 or no pack is known; a file
    that does not resolve or has no static solid never hangs."""
    if elevated_m <= 0.0 or not pack_root:
        return None
    from . import obj8 as _obj8
    memo: dict[str, bool] = {}

    def hung(def_path: str) -> bool:
        if def_path not in memo:
            phys = os.path.join(pack_root, def_path)
            memo[def_path] = False
            if os.path.isfile(phys):
                try:
                    v = _obj8.parse_obj8(phys).vertices
                except (OSError, ValueError):
                    v = None
                memo[def_path] = (v is not None and v.shape[0] > 0
                                  and float(v[:, 1].min()) > elevated_m)
        return memo[def_path]
    return hung


def hung_rows(rows: _t.Sequence[_t.Any], pack_root: str,
              elevated_m: float) -> "_t.Callable[[int], bool] | None":
    """``row index -> bool``: does DSF row ``rows[i]`` hang
    (:func:`hung_resources`) with every row standing at its origin point
    (any heading: a panel turned on its post is still on it)?  Lazy — a
    resource is read only when a row asks; ``None`` with the rule
    disarmed."""
    hung = hung_resources(pack_root, elevated_m)
    if hung is None:
        return None
    sets: dict[tuple, list[int]] = {}
    for i, p in enumerate(rows):
        sets.setdefault(_point(p), []).append(i)

    def ask(i: int) -> bool:
        return all(hung(rows[j].def_path) for j in sets.get(_point(rows[i]), (i,)))
    return ask


def _point(p: _t.Any) -> tuple:
    """A row's origin point to the DSF's own precision (1e-8 deg)."""
    return (round(float(p.lat), 8), round(float(p.lon), 8))
