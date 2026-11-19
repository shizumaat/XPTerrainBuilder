"""THE OFFER TO HIDE A LOWER PACK'S DRAPED POLYGONS INSIDE A CUSTOM
AIRPORT (RULINGS 2026-11-19h; the reading is ``auto_patch_v2.airport.
pack_overlap_drapes``).

Owner (2026-11-19T01:35Z): "Offer to hide overlapping pack polygons,
yes".  :func:`rows` is the tile's reading for ``overlap_stage``: for each
airport pack on the tile (a runway of its own) and each other pack with
an overlay DSF there that X-Plane loads AFTER it (lower in
``scenery_packs.ini``), defines none of its airports (two packs of one
airport are ``duplicate_stage``'s question) and is not of its larger
package (RULINGS 17s), the lower pack's draped ``.pol`` polygons inside
the airport's boundary make one row of the ``PackOverlaps`` event,
``"kind": "drapes"`` -- a pack the ini does not list is never offered.

The row is a #2145 pair (``pack_overlap_choice``, key
``drape_key``: one per tile): ``default`` the airport pack (owner
2026-11-17T19:15Z, the airport pack wins), ``lower`` the pack whose
polygons hide; its picker offers "Hide <lower>'s polygons" (winner = the
airport pack) or "Keep both".  The answer is remembered; the write is the
pair's (every write of the lower pack's tile DSF drops the rows,
``dsf_write._with_overlap_hides`` -> ``dsf_row_hide``), never a file
deleted; Restore originals on the pack (Modified airports) puts it back.

Nothing here names an airport or a pack.
"""
from __future__ import annotations

import os
import typing as _t

from auto_patch_v2.airport import pack_overlap_choice as _ovc
from auto_patch_v2.airport import pack_overlap_drapes as _pod

__all__ = ["KIND", "rows"]

#: the ``kind`` of a drape row
KIND = "drapes"


def _name(root: str) -> str:
    return os.path.basename(os.path.normpath(root))


def _idents(root: str) -> tuple[str, ...]:
    from auto_patch_v2.airport import apt_dat as _ad
    from auto_patch_v2.airport import apt_flatten as _af
    apt = _af.apt_dat_of(root)
    return _ad.airports_in(apt) if apt else ()


def _lower_packs(scenery_dir: str, airport: str, packs: _t.Sequence[str],
                 same: _t.Callable[[str, str], bool]) -> list[str]:
    """The packs of ``packs`` (roots) X-Plane loads after ``airport``
    (a root) that define none of its airports and are not of its family."""
    import O4_Scenery_Packs as _SP
    order, _off = _SP.parse_ini(os.path.join(scenery_dir, _SP.INI_FILENAME))
    rank = {n: i for i, n in enumerate(order)}
    aname = _name(airport)
    if aname not in rank:
        return []
    mine = set(_idents(airport))
    return [p for p in packs if _name(p) != aname and _name(p) in rank
            and rank[_name(p)] > rank[aname] and not same(aname, _name(p))
            and not mine & set(_idents(p))]


def _dump_rows(root: str, lat: int, lon: int, region: _t.Any) -> list:
    """The pack's draped polygons inside ``region``, one row per polygon
    (two polygons sharing a first point are two rows of one key)."""
    from .object_stage import pack_dump
    pd = pack_dump(root, lat, lon, read_only=False)
    if pd is None:
        return []
    with open(pd.dump_path, encoding="utf-8", errors="replace") as fh:
        return _pod.draped_rows(fh, region)


def rows(scenery_dir: str, lat: int, lon: int, airports: _t.Sequence[str],
         packs: _t.Sequence[str], same: _t.Callable[[str, str], bool],
         remember: _t.Callable[..., None]) -> list[dict]:
    """THE READING (module doc): one row per (airport pack, lower pack)
    with draped polygons inside the airport; each found pair is handed to
    ``remember(key, lat, lon, airport, pair)`` (``overlap_stage._remember``:
    an answered pair whose rows change is rewritten at once)."""
    from auto_patch_v2.airport import pack_overlap as _po
    from auto_patch_v2.airport import sibling_riders as _sr
    from shapely.ops import unary_union
    out = []
    for ap in airports:
        idents = _idents(ap)
        regions = [g for g in (_sr.airport_region(ap, i) for i in idents) if g is not None]
        if not regions:
            continue
        region = unary_union(regions)
        aname = _name(ap)
        for low in _lower_packs(scenery_dir, ap, packs, same):
            found = _dump_rows(low, lat, lon, region)
            if not found:
                continue
            lname = _name(low)
            key = _ovc.drape_key(scenery_dir, lat, lon, aname, lname)
            pair = _po.OverlapPair((aname, lname), ((), tuple(found)), len(found), 0.0)
            remember(key, lat, lon, aname, pair)
            out.append({"key": key, "kind": KIND, "packs": list(pair.packs),
                        "airport": aname, "default": aname,
                        "winner": _ovc.winner(key), "lower": lname,
                        "count": len(found), "rows": [0, len(found)],
                        "summary": _pod.summary(lname, aname, ", ".join(idents), found)})
    return out
