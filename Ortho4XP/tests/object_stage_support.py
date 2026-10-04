"""Shared builders for the reader / object-stage suites re-founded after
the v1 cut (RULINGS 2026-10-04j "coverage owed").

ONE module, imported by every file that needs these inputs — a builder
copied per test file is the duplicate the ratchet refuses.  Everything
here builds the inputs the KEPT code receives today (an ``OSM_layer``'s
four dicts, a tile's ``lat``/``lon``, an X-Plane install laid out under
``tmp_path``); nothing resurrects a v1 record class.
"""
from __future__ import annotations

import os
from types import SimpleNamespace


def tile(lat: int, lon: int, **extra) -> SimpleNamespace:
    """The slice of ``O4_Config_Utils.Tile`` the readers consult."""
    return SimpleNamespace(lat=lat, lon=lon, **extra)


class OsmLayer:
    """An ``O4_OSM_Utils.OSM_layer`` reduced to the four dicts its
    consumers read: nodes ``dicosmn`` (id -> (lon, lat)), ways ``dicosmw``
    (id -> node ids), relations ``dicosmr`` (id -> {"outer": [ring]}) and
    tags ``dicosmtags`` ({"w": {id: tags}, "r": {id: tags}})."""

    def __init__(self):
        self.dicosmn: dict = {}
        self.dicosmw: dict = {}
        self.dicosmr: dict = {}
        self.dicosmtags: dict = {"w": {}, "r": {}}
        self._next_id = 0

    def _nodes(self, coords) -> list:
        ids = []
        for lon, lat in coords:
            self._next_id += 1
            self.dicosmn[self._next_id] = (lon, lat)
            ids.append(self._next_id)
        return ids

    def way(self, coords, tags=None, *, closed: bool = False) -> int:
        """Add a way through ``coords`` ((lon, lat) pairs); ``closed``
        repeats the FIRST NODE ID at the end, as OSM closes a ring."""
        ids = self._nodes(coords)
        if closed:
            ids.append(ids[0])
        self._next_id += 1
        self.dicosmw[self._next_id] = ids
        if tags is not None:
            self.dicosmtags["w"][self._next_id] = dict(tags)
        return self._next_id

    def relation(self, outer_rings, tags) -> int:
        """Add a multipolygon relation with the given OUTER rings."""
        rings = []
        for coords in outer_rings:
            ids = self._nodes(coords)
            rings.append(ids + [ids[0]])
        self._next_id += 1
        self.dicosmr[self._next_id] = {"outer": rings}
        self.dicosmtags["r"][self._next_id] = dict(tags)
        return self._next_id


def square(lon: float, lat: float, half_deg: float) -> list:
    """Four corners of an axis-aligned square, (lon, lat), open ring."""
    return [(lon - half_deg, lat - half_deg), (lon + half_deg, lat - half_deg),
            (lon + half_deg, lat + half_deg), (lon - half_deg, lat + half_deg)]


def write_text(path, text: str) -> str:
    """Write ``text`` with the encoding and newline NAMED (the console /
    Windows text-I/O twins), creating parents; returns the path as str."""
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return str(path)


def custom_scenery(xplane_root, packs, ini_rows=None) -> str:
    """Lay out ``<xplane_root>/Custom Scenery/<pack>/`` for each name in
    ``packs`` and, when ``ini_rows`` is given, a ``scenery_packs.ini``
    holding exactly those rows (``("SCENERY_PACK", name)`` or
    ``("SCENERY_PACK_DISABLED", name)``), first row = highest priority.
    Returns the Custom Scenery directory."""
    custom = os.path.join(str(xplane_root), "Custom Scenery")
    for name in packs:
        os.makedirs(os.path.join(custom, name), exist_ok=True)
    if ini_rows is not None:
        body = "I\n1000 Version\nSCENERY\n\n" + "".join(
            f"{token} Custom Scenery/{name}/\n" for token, name in ini_rows)
        write_text(os.path.join(custom, "scenery_packs.ini"), body)
    return custom
