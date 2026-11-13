"""The provider blend of one World drape, from the World pack and the
photo source (#2018, spec ``docs/specs/auto-imagery-provider-spec-20261113.md``
§3): what ``O4_Imagery_Provider_Blend.plan`` needs to know about the
neighbours, and the casts it blends with.

* :func:`facts_reader` -- ``facts(lat, lon)`` of a neighbour: the World
  pack's record when the pack holds a real tile there (``built``), else
  the provider the job would draw it with (``world_job_run.photo_source``).
* :func:`blend_for` -- the tile's ``Blend``: casts from the data folder's
  book (``O4_Imagery_Provider_Cast.book``), each square fetched into the
  imagery cache of the tile on that provider's side of the edge (the
  drape of that tile finds it there).  Any failure is logged and the
  drape goes without a blend.

No tile or airport is named here.
"""
from __future__ import annotations

from typing import Callable, Optional

import O4_Imagery_Provider_Blend as BLEND
import O4_World_Imagery_Record as IREC
import O4_World_Pack as WP

__all__ = ["blend_for"]


def facts_reader(scenery_dir: str, source: Callable) -> Callable:
    """``facts(lat, lon)`` (``BLEND.TileFacts``) of the World pack in
    ``scenery_dir``; ``source((lat, lon))`` is the job's photo source."""
    from . import world_commands as WORLD
    pack = WORLD.pack_dir(scenery_dir) if scenery_dir else ""

    def facts(lat: int, lon: int) -> BLEND.TileFacts:
        if pack and WP.holds_tile(scenery_dir, lat, lon):
            record = IREC.read(pack, lat, lon)
            return BLEND.TileFacts(str(record.get("provider") or ""), True,
                                   dict(record.get("blend") or {}))
        return BLEND.TileFacts(source((lat, lon))[0])
    return facts


def _caster():
    import O4_Imagery_Provider_Cast as CAST
    casts = CAST.book()

    def cast(edge, a: str, b: str):
        kind, lat, lon = edge
        # the square's folder: the tile on that provider's side of the edge
        # (the edge is named from the tile north or east of it)
        north_east = (lat, lon)
        south_west = (lat - 1, lon) if kind == "H" else (lat, lon - 1)

        def image_of(provider, til_x, til_y):
            folder = south_west if provider == a else north_east
            return CAST.fetch_square(provider, til_x, til_y, folder)
        return casts.cast(edge, a, b, image_of)
    return cast


def blend_for(tile, provider: str, scenery_dir: str, source: Callable,
              log: Optional[Callable] = None) -> Optional[BLEND.Blend]:
    """Drape tile ``(lat, lon)``'s blend (module docstring); None when it
    has no provider edge or the blend could not be made."""
    lat, lon = (int(v) for v in tile)
    try:
        blend = BLEND.plan(lat, lon, provider, facts_reader(scenery_dir, source),
                           _caster())
    except Exception as error:              # never fail a drape for a blend
        if log is not None:
            log({"blend_error": repr(error)[:300], "tile": WP.tile_name(lat, lon)})
        return None
    return blend if blend.terms else None
