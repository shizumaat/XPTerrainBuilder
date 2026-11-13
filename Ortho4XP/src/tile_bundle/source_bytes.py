"""WHAT A RECIPIENT DOWNLOADS (#2014 follow-up; owner 2026-11-11T16:45Z:
"If the user has to download a whole elevation area and create insets
plus all the OSM that will take much longer and require much more
download size right?").

A package that leaves a data file out does not leave the recipient that
file to download: it leaves the SOURCE the file was made from.  This
module prices each left-out data member (``inputs.files`` names) at the
bytes its source costs to fetch, by class:

* an OpenStreetMap layer (``…/OSM_data/…/<tile>/*.osm.bz2``): the
  Overpass answer, the same XML gzip-encoded on the wire —
  :data:`OSM_WIRE_RATIO` times the cached bz2 (measured on tile +33-119,
  2026-11-11: 3.37 MB of bz2 is 4.30 MB of gzip, 1.28) — and one
  Overpass query per layer (:data:`OVERPASS_SECONDS_PER_LAYER`);
* an elevation raster (base cell, airport inset, approach-ring cell,
  band cell): what its sidecar recorded fetching when it did
  (``bytes_fetched``; ``prefetched_whole_bytes`` for a stripped product
  fetched whole), else the gridded raster's own bytes for each source it
  was read from — a windowed read fetches every overlapping source's
  share of the window, so ``sources_used`` sources cost
  ``1 + OVERLAP_PER_SOURCE * (n - 1)`` windows (:data:`OVERLAP_PER_SOURCE`,
  a planning figure: KLAX's 1 m inset mosaics four sources, two projects
  over two tiles);
* a sidecar or index (``.json``): its own bytes.

:func:`left_out` sums them per class; every figure is an ESTIMATE and
both apps say so.  No tile, airport or provider is named here.
"""
from __future__ import annotations

import json
import os

__all__ = ["OSM_WIRE_RATIO", "OVERPASS_SECONDS_PER_LAYER", "OVERLAP_PER_SOURCE",
           "CLASSES", "left_out"]

#: gzip-encoded Overpass XML over the cached bz2 (module doc: measured).
OSM_WIRE_RATIO = 1.28
#: One Overpass query's wait, per layer: a planning figure (the server's
#: queue and query time, not the bytes; the cold build of +33-119 on
#: 2026-10-17 fetched its seven layers, eight insets and its approach
#: rings in 668 s together).
OVERPASS_SECONDS_PER_LAYER = 30.0
#: A windowed read's extra share per overlapping source (module doc).
OVERLAP_PER_SOURCE = 0.5

#: The classes, in the order the estimate lists them.
CLASSES = ("osm", "base", "inset", "ring", "band", "sidecar")

_RECORDED = ("bytes_fetched", "prefetched_whole_bytes")


def _member_class(name: str) -> str:
    """The class (:data:`CLASSES`) of a ``data/…`` member name, or ``""``
    for a member that is not downloaded data (a patch)."""
    parts = name.split("/")
    if len(parts) < 4 or parts[0] != "data":
        return ""
    if name.endswith(".json"):
        return "sidecar"
    if parts[1] == "OSM_data":
        return "osm"
    if len(parts) == 4:
        return "base"
    folder = parts[-2]
    if folder.endswith("_airport_insets"):
        return "inset"
    if folder.endswith("_approach_rings"):
        return "ring"
    return "band"


def _sidecar(path: str) -> dict:
    stem = path[: -len(".tiff")] if path.lower().endswith(".tiff") else path[:-4]
    try:
        with open(stem + ".json", encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _source_bytes(name: str, path: str) -> int:
    """What fetching the source of member ``name`` (at ``path``) costs
    (module doc)."""
    size = os.path.getsize(path)
    kind = _member_class(name)
    if kind == "osm":
        return int(size * OSM_WIRE_RATIO)
    if kind in ("inset", "ring", "band"):
        doc = _sidecar(path)
        recorded = sum(int(doc.get(k) or 0) for k in _RECORDED)
        if recorded > 0:
            return recorded
        try:
            sources = max(1, int(doc.get("sources_used") or 1))
        except (TypeError, ValueError):
            sources = 1
        return int(size * (1.0 + OVERLAP_PER_SOURCE * (sources - 1)))
    return size


def left_out(members) -> dict:
    """``{class: {"files", "bytes", "source_bytes"}}`` of ``[(name,
    path)]`` (data members only; a class with none is absent)."""
    out: dict = {}
    for name, path in members:
        kind = _member_class(name)
        if not kind:
            continue
        row = out.setdefault(kind, {"files": 0, "bytes": 0, "source_bytes": 0})
        row["files"] += 1
        row["bytes"] += os.path.getsize(path)
        row["source_bytes"] += _source_bytes(name, path)
    return out
