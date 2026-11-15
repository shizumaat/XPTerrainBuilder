"""GENERIC X-PLANE GROUND ANOTHER PACK DRAPES OVER A BUILT TILE (#2085).

Owner (2026-11-14T15:20Z): "Yes, add a prompt to hide generic ground
textures from all packs covering the tile."  A landmark or city pack may
drape X-Plane's own land-class polygons — grass, sand, scrub — over
thousands of hectares; X-Plane draws them over the tile's orthophotos as
it draws them over its own mesh, so the imagery is gone where they lie.
This module is their WITNESS; the hiding is the same omission as the
pack's draped photos and ground sheets (``dsf_write.write_pack(drapes=)``,
the drape stage's ``GENERIC``), asked in the pack's adjustments.

THE WITNESS — a ``POLYGON_DEF`` of the pack's tile DSF is generic ground
when, read from the paths and files, never from a pack's name:

1. it is a ``.pol`` under X-Plane's stock land-class library
   (:data:`STOCK_PREFIXES`: ``lib/g10/terrain10/``, ``lib/g8/pol/``) —
   the library's airport surfaces, pavement, markings, decals and urban
   kits (``lib/airport/…``, ``lib/terrain/…``) are never one; or
2. it is the PACK'S OWN draped ``.pol`` whose ``TEXTURE`` lies in the
   simulator's stock land-class textures (:data:`STOCK_TEXTURE_DIR`) and
   which draws no pavement (``pack_drapes.paved_header``).

A pack-authored image, a third-party library's polygon, water and every
``.lin``/``.fac``/``.for`` stay.  :func:`generic_ground` reports each
definition with its polygon count and the hectares they cover (holes
taken out, one definition's polygons unioned).
"""
from __future__ import annotations

import os
import typing as _t

from .pack_art import MissingDef, _lines

__all__ = ["STOCK_PREFIXES", "STOCK_TEXTURE_DIR", "GenericGround",
           "is_stock_land_class", "generic_indices", "generic_ground"]

#: X-Plane's stock land-class polygon libraries (lower case)
STOCK_PREFIXES = ("lib/g10/terrain10/", "lib/g8/pol/")
#: the simulator's stock land-class folder a pack ``.pol`` may borrow
#: its texture from (path components, lower case)
STOCK_TEXTURE_DIR = ("resources", "default scenery", "1000 world terrain")


class GenericGround(_t.NamedTuple):
    """One pack tile DSF's generic ground: the definitions the omission
    takes (``uses``: their polygons) and the hectares each covers."""

    defs: tuple
    areas: tuple

    def hectares(self, defs: _t.Iterable[MissingDef] | None = None) -> float:
        """The hectares ``defs`` (default: all) cover."""
        keep = set(self.defs if defs is None else defs)
        return sum(a for m, a in zip(self.defs, self.areas, strict=True) if m in keep)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("/").lower()


def is_stock_land_class(def_path: str) -> bool:
    """Witness (1): a ``.pol`` of X-Plane's stock land-class library."""
    p = _norm(def_path)
    return p.endswith(".pol") and p.startswith(STOCK_PREFIXES)


def _stock_texture(pol_path: str, header: _t.Mapping[str, str]) -> bool:
    """Witness (2): the pack ``.pol`` drapes a stock land-class texture."""
    from .pack_drapes import paved_header
    tex = header.get("TEXTURE") or header.get("TEXTURE_NOWRAP") or ""
    if "DRAPED_POLYGON" not in header or not tex or paved_header(header):
        return False
    full = os.path.normpath(os.path.join(os.path.dirname(pol_path),
                                         tex.replace("\\", "/")))
    parts = [c.lower() for c in full.replace("\\", "/").split("/")]
    n = len(STOCK_TEXTURE_DIR)
    return any(tuple(parts[i:i + n]) == STOCK_TEXTURE_DIR
               for i in range(len(parts) - n + 1))


def generic_indices(pack_root: str, defs: _t.Sequence[str]) -> list[int]:
    """The indices of ``defs`` (a DSF's ``POLYGON_DEF`` paths) that are
    generic ground (witness (1) or (2))."""
    from .pack_drapes import pol_header
    out = []
    for i, path in enumerate(defs):
        if is_stock_land_class(path):
            out.append(i)
            continue
        rel = path.replace("\\", "/").lstrip("/")
        local = os.path.join(pack_root, rel) if rel.lower().endswith(".pol") else ""
        if local and os.path.isfile(local) and _stock_texture(
                local, pol_header(local)):
            out.append(i)
    return out


def generic_ground(pack_root: str, source: str | _t.Sequence[str]
                   ) -> GenericGround:
    """THE WITNESS over one pristine DSF dump (a path or its rows)."""
    from shapely.ops import unary_union

    from .pack_ground_sheets import _shape
    from .pack_trees_clear import _frame, _polygon_blocks
    lines = list(_lines(source))
    defs = [ln.split(None, 1)[1].strip() for ln in lines
            if ln.startswith("POLYGON_DEF") and len(ln.split(None, 1)) > 1]
    wanted = set(generic_indices(pack_root, defs))
    if not wanted:
        return GenericGround((), ())
    to_m = None
    shapes: dict[int, list] = {}
    for _s, _e, idx, _p, _tail, windings in _polygon_blocks(lines):
        if idx not in wanted or not windings or not windings[0]:
            continue
        if to_m is None:
            to_m = _frame(windings[0][0][1])[0]
        shapes.setdefault(idx, []).append(_shape(windings, to_m))
    out, areas = [], []
    for i in sorted(shapes):
        found = [g for g in shapes[i] if g is not None]
        out.append(MissingDef("polygon", i, defs[i], len(shapes[i])))
        areas.append(unary_union(found).area / 10_000.0 if found else 0.0)
    return GenericGround(tuple(out), tuple(areas))
