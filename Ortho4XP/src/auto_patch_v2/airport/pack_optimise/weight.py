"""THE WEIGHT OF A PACK'S OBJECTS (issue #1707): what "Optimise pack" is
offered on.

The triangles a tile DSF draws through the pack's OWN objects — each
placed ``.obj`` file's triangles (its ``POINT_COUNTS`` header: indices
/ 3) times its placements — and the same count without the placements
the recipe drops.  Library objects are X-Plane's and are not counted.

Measured 2026-10-30 (frame-rate finding): reference airport packs draw
6.4 M and 11.0 M; the pack that fell to ~10 fps drew 275.5 M.  The offer
threshold :data:`OFFER_TRIANGLES` sits well clear of the references.
"""
from __future__ import annotations

import os
import typing as _t

from ..dsf_write import placement_rows
from ..pack_art import declared_definitions

__all__ = ["OFFER_TRIANGLES", "estimate"]

#: a pack drawing more than this through its own objects is offered
#: "Optimise pack"
OFFER_TRIANGLES = 50_000_000
#: header lines read before giving up on a ``POINT_COUNTS`` row
_HEADER_LINES = 400


def _obj_triangles(path: str) -> int:
    """Triangles an OBJ8 file draws, from its ``POINT_COUNTS`` header
    (``vt lines lights indices``); ``0`` when it cannot be read."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for n, raw in enumerate(fh):
                toks = raw.split()
                if toks and toks[0] == "POINT_COUNTS":
                    return int(toks[4]) // 3 if len(toks) > 4 else 0
                if n > _HEADER_LINES or (toks and toks[0] == "VT"):
                    return 0
    except (OSError, ValueError):
        pass
    return 0


def estimate(pack_root: str, lines: _t.Sequence[str],
             drop: _t.AbstractSet[int], top: int = 0,
             swaps: _t.Mapping[str, _t.Mapping[str, _t.Any]] | None = None
             ) -> dict[str, _t.Any]:
    """``{"tris_before", "tris_after", "placements", "swapped"}`` of the
    pack's own objects in the dump ``lines``, ``drop`` being the ordinals
    the recipe deletes and ``swaps`` its library swaps (a swapped row
    counts the library object's triangles after).  ``top`` adds
    ``"top"``: the heaviest definitions, ``(tris x placements, tris,
    placements, path)`` (``tools/pack_weight.py``)."""
    defs = declared_definitions(lines)["object"]
    tris: dict[int, int] = {}
    uses: dict[int, int] = {}
    swaps = swaps or {}
    before = after = placements = swapped = 0
    for o, _i, toks in placement_rows(lines):
        d = int(toks[1])
        if d not in tris:
            path = os.path.join(pack_root, *defs[d].replace("\\", "/").split("/"))
            tris[d] = (_obj_triangles(path) if path.lower().endswith(".obj")
                       and os.path.isfile(path) else 0)
        if not tris[d]:
            continue
        placements += 1
        uses[d] = uses.get(d, 0) + 1
        before += tris[d]
        if o in drop:
            continue
        sw = swaps.get(defs[d])
        if sw:
            swapped += 1
            after += int((sw.get("tris") or (0, 0))[1])
        else:
            after += tris[d]
    out: dict[str, _t.Any] = {"tris_before": before, "tris_after": after,
                              "placements": placements, "swapped": swapped}
    if top:
        out["top"] = sorted(((tris[d] * n, tris[d], n, defs[d])
                             for d, n in uses.items()), reverse=True)[:top]
    return out
