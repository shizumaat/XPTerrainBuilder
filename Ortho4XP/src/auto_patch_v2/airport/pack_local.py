"""THE PACK-LOCAL OBJECT WITNESS: which placements of a pack's DSF are the
pack's OWN objects inside an airport — a ``.obj`` file the pack itself
ships, resolved inside its own folder.  An overlay that places only library
objects (``lib/...`` and other virtual paths another pack exports) owns
none.  Read by ``airport/companion`` (owner RULINGS 2026-10-28p (5)) and
``airport/object_pack`` (#1630): one witness, two rules.
"""
from __future__ import annotations

import os
import typing as _t

__all__ = ["ships_objects", "admitted"]


def _inside(path: str, root: str) -> bool:
    real = os.path.realpath(root)
    try:
        return os.path.commonpath([os.path.realpath(path), real]) == real
    except ValueError:
        return False


def ships_objects(root: str) -> bool:
    """Does the pack ship any ``.obj`` of its own (outside its DSFs)?  The
    cheap gate before a DSF is dumped: an overlay that places only
    library objects ships none and is never dumped."""
    for here, dirs, files in os.walk(root):
        if os.path.basename(here) == "Earth nav data":
            dirs[:] = []
            continue
        if any(f.lower().endswith(".obj") for f in files):
            return True
    return False


def admitted(dump, root: str, inside: _t.Callable[[float, float], bool]
             ) -> list[tuple[int, _t.Any]]:
    """The rows of ``dump`` a pack owns at an airport: ``.obj`` placements whose
    resource is a file ``root`` ships and whose anchor ``(lon, lat)`` is
    ``inside`` the airport."""
    rows = []
    for i, pl in enumerate(dump.placements):
        if not pl.def_path.lower().endswith(".obj"):
            continue
        path = os.path.join(root, pl.def_path)
        if not (os.path.isfile(path) and _inside(path, root)):
            continue
        if inside(pl.lon, pl.lat):
            rows.append((i, pl))
    return rows
