"""OSM extracts — the three per-tile feeds Ortho4XP already keeps
(``<osm_root>/+60-140/+60-136/+60-136_<feed>.osm.bz2``: ``airports``,
``airport_small_roads``, ``big_roads``; v1 ``osm_load`` is the reference
for the tile layout and the 0.05° selection box).

The reader keeps the TAGS OF INTEREST only (``model.airport.OsmWay``):
``highway``, ``railway``, ``bridge``, ``tunnel``, ``layer``, ``aeroway``,
``building``, ``building:part``, ``service``, ``access``, ``name``,
``surface``, ``width``, ``lanes``, ``oneway``, ``height``,
``building:levels``.  Ways are selected when any vertex lies inside the
box around the airport; the 3x3 tile neighbourhood is merged with
per-tile id namespacing (Overpass exports reuse negative ids across
tiles — user 2026-04-29).  Read-only.
"""
from __future__ import annotations

import bz2
import dataclasses as _dc
import math
import os
import typing as _t
import xml.etree.ElementTree as ET

__all__ = ["OsmDoc", "RawWay", "read_osm_file", "feed_path", "load_feed",
           "TAGS_OF_INTEREST", "FEEDS"]

TAGS_OF_INTEREST = frozenset((
    "highway", "railway", "bridge", "tunnel", "layer", "aeroway",
    "building", "building:part", "service", "access", "name", "surface",
    "width", "lanes", "oneway", "height", "building:levels", "area",
))
FEEDS = ("airports", "airport_small_roads", "big_roads")


@_dc.dataclass(frozen=True)
class RawWay:
    """One way: ``points`` are ``(lat, lon)`` in node order."""

    id: str
    points: tuple[tuple[float, float], ...]
    tags: _t.Mapping[str, str]

    @property
    def closed(self) -> bool:
        return len(self.points) >= 4 and self.points[0] == self.points[-1]


@_dc.dataclass(frozen=True)
class OsmDoc:
    """The ways of one feed inside the selection box."""

    feed: str
    ways: tuple[RawWay, ...]
    sources: tuple[str, ...]


def tile_dir(osm_root: str, lat: int, lon: int) -> str:
    """``<root>/+60-140/+60-136`` for tile (60, -136)."""
    blat, blon = (lat // 10) * 10, (lon // 10) * 10
    return os.path.join(osm_root, f"{blat:+03d}{blon:+04d}",
                        f"{lat:+03d}{lon:+04d}")


def feed_path(osm_root: str, lat: int, lon: int, feed: str) -> str:
    """The extract path (``.osm.bz2``, else ``.osm``) for one feed."""
    base = os.path.join(tile_dir(osm_root, lat, lon),
                        f"{lat:+03d}{lon:+04d}_{feed}.osm")
    return base + ".bz2" if os.path.isfile(base + ".bz2") else base


def read_osm_file(path: str, namespace: str = "") -> tuple[
        dict[str, tuple[float, float]], list[tuple[str, list[str],
                                                    dict[str, str]]]]:
    """``(nodes, ways)`` of one OSM XML file (plain or bz2); node and way
    ids are prefixed with ``namespace``."""
    opener = bz2.open if path.endswith(".bz2") else open
    with opener(path, "rb") as fh:
        root = ET.fromstring(fh.read())
    nodes: dict[str, tuple[float, float]] = {}
    ways: list[tuple[str, list[str], dict[str, str]]] = []
    for el in root:
        if el.tag == "node":
            nodes[namespace + el.get("id", "")] = (float(el.get("lat")),
                                                   float(el.get("lon")))
        elif el.tag == "way":
            nds = [namespace + nd.get("ref", "") for nd in el.findall("nd")]
            tags = {t.get("k", ""): t.get("v", "") for t in el.findall("tag")
                    if t.get("k") in TAGS_OF_INTEREST}
            ways.append((namespace + el.get("id", ""), nds, tags))
    return nodes, ways


def load_feed(osm_root: str, feed: str, lat: float, lon: float,
              radius_deg: float = 0.05) -> OsmDoc:
    """Ways of ``feed`` with a vertex inside the ``radius_deg`` box around
    ``(lat, lon)``, merged over the 3x3 tile neighbourhood (a missing
    tile contributes nothing; a missing natural tile is an empty feed —
    never a download)."""
    blat, blon = int(math.floor(lat)), int(math.floor(lon))
    out: list[RawWay] = []
    sources: list[str] = []
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            tlat, tlon = blat + dlat, blon + dlon
            path = feed_path(osm_root, tlat, tlon, feed)
            if not os.path.isfile(path):
                continue
            sources.append(path)
            ns = f"{tlat:+03d}{tlon:+04d}:"
            nodes, ways = read_osm_file(path, ns)
            for wid, nds, tags in ways:
                pts = tuple(nodes[n] for n in nds if n in nodes)
                if len(pts) < 2:
                    continue
                if not any(abs(p[0] - lat) <= radius_deg
                           and abs(p[1] - lon) <= radius_deg for p in pts):
                    continue
                out.append(RawWay(wid, pts, tags))
    return OsmDoc(feed, tuple(out), tuple(sources))
