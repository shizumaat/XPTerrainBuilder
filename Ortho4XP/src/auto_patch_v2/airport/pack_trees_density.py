"""THE PLANT COUNT of a pack's own low vegetation upgraded to X-Plane 12
ground cover (issue #1920 follow-up).

A forest polygon's parameter (0-255, area mode) is the density as a share
of the ``SPACING`` its ``.for`` declares.  The X-Plane 12 planters
(:data:`.pack_trees_map.PLANTERS`) are spaced at half a metre; a pack's own
grass, reeds and shrubs at one to seven metres.  Renamed as they stand,
the LGAV pack's 430 ha of grass and reeds would draw 14 million plants
where its author drew 0.3 million.  So each polygon of a renamed
planter keeps the pack's plant count: its parameter is scaled by
``planter cell / pack cell`` (never above what it was, never below 1).
Line and point forests (parameter 256 and up) are untouched: their plants
are their edges' and vertices'.  Any pack, any tile.
"""
from __future__ import annotations

import typing as _t

from .obj8 import resolve_resource
from .pack_art import declared_definitions
from .pack_trees_map import PLANTERS

__all__ = ["keep_plant_count"]

#: a forest polygon parameter at or above this draws along edges / at vertices
LINE_FOREST = 256


def for_spacing(path: str) -> tuple[float, float] | None:
    """The ``SPACING`` (x, z) metres of a ``.for`` file; ``None`` without."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                tok = raw.split()
                if tok[:1] == ["SPACING"] and len(tok) >= 3:
                    x, z = float(tok[1]), float(tok[2])
                    return (x, z) if x > 0 and z > 0 else None
    except (OSError, ValueError):
        pass
    return None


def _factors(text: str, renames: _t.Mapping[str, str], pack_root: str
             ) -> dict[int, float]:
    """``POLYGON_DEF`` index -> density factor of each pack file
    ``renames`` sends to a planter (read BEFORE the rename: the index is
    the pack file's)."""
    out: dict[int, float] = {}
    for i, path in enumerate(declared_definitions(text.splitlines())["polygon"]):
        tgt = renames.get(path)
        if tgt not in PLANTERS:
            continue
        phys = resolve_resource(path.replace("\\", "/").replace(":", "/"),
                                pack_root, None)
        sp = for_spacing(phys) if phys else None
        if sp is not None:
            px, pz = PLANTERS[tgt][1]
            out[i] = (px * pz) / (sp[0] * sp[1])
    return out


def keep_plant_count(text: str, renames: _t.Mapping[str, str],
                     pack_root: str) -> tuple[str, int]:
    """``text`` (BEFORE the rename) with each area polygon of a pack file
    ``renames`` sends to a planter at the pack's plant count (module doc).  Returns the text and
    the polygons changed."""
    factors = _factors(text, renames, pack_root)
    if not factors:
        return text, 0
    out: list[str] = []
    n = 0
    for raw in text.splitlines(keepends=True):
        tok = raw.split()
        if tok[:1] == ["BEGIN_POLYGON"] and len(tok) >= 3:
            try:
                idx, param = int(tok[1]), int(tok[2])
            except ValueError:
                idx, param = -1, LINE_FOREST
            if idx in factors and param < LINE_FOREST:
                new = max(1, min(param, round(param * factors[idx])))
                if new != param:
                    end = raw[len(raw.rstrip("\r\n")):]
                    raw = " ".join(["BEGIN_POLYGON", tok[1], str(new),
                                    *tok[3:]]) + end
                    n += 1
        out.append(raw)
    return "".join(out), n
