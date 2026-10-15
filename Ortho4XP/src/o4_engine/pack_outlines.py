"""``pack_outlines`` — the airport pack's own pavement and boundary, as
dashed reference outlines under the patch editor's layer (protocol 1.12,
``docs/specs/patch-editor-20261015.md`` §2 as amended before L4).

The pack is found exactly as ``pack_objects`` finds it
(``pack_objects.xplane_root_for`` + ``airport/pack.select_pack``), and its
apt.dat block is read and flattened by ``auto_patch_v2/airport/apt_dat.py``
— the one apt.dat reader, its bezier flattening included.  Rows 110
(pavement) and 130 (boundary) become ``{kind, rings}``: the first ring is
the exterior, later rings are the holes.  Building footprints are NOT
here: the map draws them from the ``pack_objects`` result.

Synchronous and read-only: nothing is downloaded or regenerated; a
problem is a sentence in ``missing``.
"""
from __future__ import annotations

import typing as _t

__all__ = ["pack_outlines"]


def _rings(rings: _t.Iterable[_t.Iterable[tuple[float, float]]]) -> list[list[list[float]]]:
    """apt_dat's ``(lon, lat)`` rings as the wire's ``[[lat, lon], ...]``."""
    return [[[lat, lon] for lon, lat in ring] for ring in rings]


def pack_outlines(tile: str, icao: str) -> dict:
    """``{pavement: [{kind, rings}], missing: [reason]}`` for ``icao``'s
    pack, ``tile`` naming the build whose X-Plane folder is read."""
    from auto_patch_v2.airport import apt_dat as _apt
    from auto_patch_v2.airport import pack as _pack

    from .pack_objects import _tile, xplane_root_for

    lat, lon = _tile(tile)
    out: dict = {"pavement": [], "missing": []}
    missing: list[str] = out["missing"]
    xroot = xplane_root_for(lat, lon)
    if not xroot:
        missing.append("No X-Plane folder is set for this tile, so its airport pack "
                       "cannot be found.")
        return out
    sel = _pack.select_pack(xroot, str(icao))
    if sel is None:
        missing.append(f"No scenery pack serves {icao} under {xroot}.")
        return out
    block = _apt.read_airport_block(sel.apt_dat_path, str(icao))
    if not block:
        missing.append(f"The apt.dat of {sel.name} could not be read for {icao}.")
        return out
    try:
        airport = _apt.parse_airport_block(block)
    except ValueError as error:
        missing.append(f"The apt.dat of {sel.name} has an unreadable {icao} entry ({error}).")
        return out
    for pv in airport.pavements:
        out["pavement"].append({"kind": "pavement", "rings": _rings(pv.rings)})
    for bd in airport.boundaries:
        out["pavement"].append({"kind": "boundary", "rings": _rings(bd.rings)})
    if not airport.pavements:
        missing.append(f"The pack {sel.name} draws no pavement of its own for {icao}.")
    return out
