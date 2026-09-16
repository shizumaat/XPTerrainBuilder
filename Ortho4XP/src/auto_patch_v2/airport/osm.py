"""OSM extracts — the three per-tile feeds Ortho4XP already keeps
(``<osm_root>/+60-140/+60-136/+60-136_<feed>.osm.bz2``: ``airports``,
``airport_small_roads``, ``big_roads``; v1 ``osm_load`` is the reference
for the tile layout and the 0.05° selection box).

The reader keeps the TAGS OF INTEREST only (``model.airport.OsmWay``):
``highway``, ``railway``, ``bridge``, ``tunnel``, ``layer``, ``aeroway``,
``building``, ``building:part``, ``service``, ``access``, ``name``,
``surface``, ``width``, ``lanes``, ``oneway``, ``height``,
``building:levels``, ``amenity``, ``parking``.  Ways are selected when any vertex lies inside the
box around the airport; the 3x3 tile neighbourhood is merged with
per-tile id namespacing (Overpass exports reuse negative ids across
tiles — user 2026-04-29).  Read-only.

RELATIONS ARE EVIDENCE (spec §25, RULINGS 2026-09-11aq item B).  Until
2026-09-11 the reader saw ``<node>`` and ``<way>`` only, so a
multipolygon's outer ways arrived TAGLESS: LEMD's Terminal 2 (relation
−1, outer way −48, 31,956 m²) and six ``aeroway=apron`` relations were
invisible to every consumer, and ``pav146`` read as a car park on 5 %
apron cover.  ``read_osm_file`` now hands every ``type=multipolygon`` /
``type=building`` relation's TAGS OF INTEREST to its ``outer`` member
ways (a way's OWN tag wins), stitches an outer ring chained from several
open ways into one closed way, and DROPS inner rings this round (§25 (2):
a courtyard in a pad is covered by the pad; holes are owed).  This is the
ONE derivation site — every consumer of ``OsmDoc.ways`` (``classify/
evidence.py``, ``classify/sources.py``, ``planar/structures.py``,
``airport/deck_signature.py``, ``airport/tunnel_objects.py``) sees the
same ``RawWay`` shape it always did.
"""
from __future__ import annotations

import bz2
import dataclasses as _dc
import math
import os
import typing as _t
import xml.etree.ElementTree as ET

__all__ = ["OsmDoc", "RawWay", "RelationReport", "read_osm_file", "feed_path",
           "load_feed", "TAGS_OF_INTEREST", "FEEDS", "RELATION_TYPES",
           "ROAD_FEEDS", "ROAD_CACHE_TAG_SCHEMA", "feed_tag_schema"]

TAGS_OF_INTEREST = frozenset((
    "highway", "railway", "bridge", "tunnel", "layer", "aeroway",
    "building", "building:part", "service", "access", "name", "surface",
    "width", "lanes", "oneway", "height", "building:levels", "area",
    "amenity", "parking",   # amenity=parking lots (owner 2026-09-04j evidence)
    # §34 (12) (5) (a) (owner RULINGS 2026-09-16d, lane `v2vmmcbore`): a
    # `covered=yes` structure is an ENCLOSURE a bore may END in, and this
    # whitelist dropped the tag, so the witness could not be read at all.
    # `O4_Vector_Map.ROADS_TAGS_OF_INTEREST` has kept it since the
    # 2026-09-15 schema (§45 (9)); every consumer reads tags BY KEY, so
    # one more key changes no existing reading.
    "covered",
))
FEEDS = ("airports", "airport_small_roads", "big_roads")

#: The feeds written under a TAG WHITELIST — ``O4_Vector_Map``'s
#: ``ROADS_TAGS_OF_INTEREST``.  The airports feed keeps ``["all"]`` and
#: carries no schema.
ROAD_FEEDS = ("airport_small_roads", "big_roads")

#: THE WHITELIST'S VERSION, mirrored from ``O4_Vector_Map.
#: ROAD_CACHE_TAG_SCHEMA`` (which this package must not import: it pulls
#: the whole v1 tile pipeline).  ``tests/auto_patch_v2/test_v2othhdet.py``
#: twin-asserts the two are equal, the same drift guard the JSONL wire
#: names use — a bump on one side and not the other is silent otherwise.
ROAD_CACHE_TAG_SCHEMA = "2026-09-15"

#: The root attribute an Ortho4XP-written road cache carries.
_SCHEMA_ATTR = "o4_tag_schema"


def feed_tag_schema(path: str) -> str | None:
    """The ``o4_tag_schema`` of a cached feed, or ``None`` when the file
    carries none (every cache written before the attribute existed, and
    ``airport_small_roads`` at every tile today — its writer,
    ``O4_Vector_Map._airport_auto_roads_layer``, passes no
    ``cache_schema`` and recycles the file unconditionally).

    Read from the ROOT TAG ALONE — the first two lines of the XML — so
    checking a 3 MB bz2 costs a single small decompression block, not a
    parse."""
    opener = bz2.open if path.endswith(".bz2") else open
    try:
        with opener(path, "rb") as fh:
            head = fh.read(4096).decode("utf-8", "replace")
    except OSError:
        return None
    i = head.find("<osm")
    if i < 0:
        return None
    j = head.find(">", i)
    root = head[i:j if j > 0 else len(head)]
    k = root.find(_SCHEMA_ATTR + '="')
    if k < 0:
        return None
    k += len(_SCHEMA_ATTR) + 2
    e = root.find('"', k)
    return root[k:e] if e > 0 else None

#: The relation types whose outer ways carry the relation's tags (§25 (1)).
#: ``type=route`` / ``type=boundary`` and the rest are NOT areas and never
#: hand tags down.
RELATION_TYPES = frozenset(("multipolygon", "building"))


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
class RelationReport:
    """What §25 did to one feed (or file): relations read, outer member
    ways given the relation's tags, outer rings STITCHED from open ways,
    outers that could not be closed (named), inner rings dropped."""

    relations: int = 0
    tagged_ways: int = 0
    stitched: int = 0
    unclosable: tuple[str, ...] = ()
    inners_dropped: int = 0
    inner_area_m2: float = 0.0

    def merge(self, other: "RelationReport") -> "RelationReport":
        return RelationReport(
            self.relations + other.relations,
            self.tagged_ways + other.tagged_ways,
            self.stitched + other.stitched,
            self.unclosable + other.unclosable,
            self.inners_dropped + other.inners_dropped,
            self.inner_area_m2 + other.inner_area_m2)

    def line(self) -> str:
        s = (f"relations {self.relations}, outer ways tagged {self.tagged_ways}, "
             f"stitched {self.stitched}, inners dropped {self.inners_dropped} "
             f"({self.inner_area_m2:,.0f} m2)")
        if self.unclosable:
            s += f", unclosable outers {list(self.unclosable)}"
        return s


@_dc.dataclass(frozen=True)
class OsmDoc:
    """The ways of one feed inside the selection box."""

    feed: str
    ways: tuple[RawWay, ...]
    sources: tuple[str, ...]
    relations: RelationReport = _dc.field(default_factory=RelationReport)
    #: ``(source path, o4_tag_schema or None)`` per file actually read
    tag_schemas: tuple[tuple[str, str | None], ...] = ()


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


def _ring_area_m2(nds: _t.Sequence[str],
                  nodes: _t.Mapping[str, tuple[float, float]]) -> float:
    """Shoelace area of a closed node ring, metres² (local equirectangular
    scaling around the ring's mean latitude — a REPORTING figure)."""
    pts = [nodes[n] for n in nds if n in nodes]
    if len(pts) < 4:
        return 0.0
    lat0 = sum(p[0] for p in pts) / len(pts)
    k = math.cos(math.radians(lat0))
    a = 0.0
    for (la1, lo1), (la2, lo2) in zip(pts, pts[1:]):
        a += (lo1 * k) * la2 - (lo2 * k) * la1
    return abs(a) * 0.5 * (111_320.0 ** 2)


def _stitch(chains: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    """Join open node chains end-to-end into closed rings.  Returns
    ``(closed, leftover)`` — a ring is closed when its first node id
    equals its last."""
    pool = [list(c) for c in chains if len(c) >= 2]
    closed: list[list[str]] = []
    left: list[list[str]] = []
    while pool:
        cur = pool.pop(0)
        joined = True
        while joined and cur[0] != cur[-1]:
            joined = False
            for i, other in enumerate(pool):
                if other[0] == cur[-1]:
                    cur = cur + other[1:]
                elif other[-1] == cur[-1]:
                    cur = cur + other[-2::-1]
                elif other[-1] == cur[0]:
                    cur = other[:-1] + cur
                elif other[0] == cur[0]:
                    cur = other[::-1][:-1] + cur
                else:
                    continue
                pool.pop(i)
                joined = True
                break
        if cur[0] == cur[-1] and len(cur) >= 4:
            closed.append(cur)
        else:
            # an unclosable remnant: reported, never a half-ring feature.
            # The pool keeps going — one broken ring must not lose the
            # relation's OTHER, closable rings.
            left.append(cur)
    return closed, left


def read_osm_file(path: str, namespace: str = "") -> tuple[
        dict[str, tuple[float, float]], list[tuple[str, list[str],
                                                    dict[str, str]]],
        RelationReport]:
    """``(nodes, ways, relation_report)`` of one OSM XML file (plain or
    bz2); node and way ids are prefixed with ``namespace``.

    §25: every ``type=multipolygon`` / ``type=building`` relation hands
    its TAGS OF INTEREST to its ``outer`` member ways (the way's own tag
    wins); an outer ring chained from several open member ways is ALSO
    emitted as one stitched closed way (id ``<ns><relid>#<k>``); inner
    rings are dropped this round (counted, with their area)."""
    opener = bz2.open if path.endswith(".bz2") else open
    with opener(path, "rb") as fh:
        root = ET.fromstring(fh.read())
    nodes: dict[str, tuple[float, float]] = {}
    ways: list[tuple[str, list[str], dict[str, str]]] = []
    rels: list[tuple[str, dict[str, str], list[str], list[str]]] = []
    for el in root:
        if el.tag == "node":
            nodes[namespace + el.get("id", "")] = (float(el.get("lat")),
                                                   float(el.get("lon")))
        elif el.tag == "way":
            nds = [namespace + nd.get("ref", "") for nd in el.findall("nd")]
            tags = {t.get("k", ""): t.get("v", "") for t in el.findall("tag")
                    if t.get("k") in TAGS_OF_INTEREST}
            ways.append((namespace + el.get("id", ""), nds, tags))
        elif el.tag == "relation":
            all_tags = {t.get("k", ""): t.get("v", "") for t in el.findall("tag")}
            if all_tags.get("type") not in RELATION_TYPES:
                continue
            rtags = {k: v for k, v in all_tags.items() if k in TAGS_OF_INTEREST}
            outer = [namespace + m.get("ref", "") for m in el.findall("member")
                     if m.get("type") == "way" and m.get("role", "outer") in ("outer", "")]
            inner = [namespace + m.get("ref", "") for m in el.findall("member")
                     if m.get("type") == "way" and m.get("role") == "inner"]
            rels.append((namespace + el.get("id", ""), rtags, outer, inner))
    if not rels:
        return nodes, ways, RelationReport()

    by_id = {w[0]: i for i, w in enumerate(ways)}
    tagged = stitched = inners = 0
    unclosable: list[str] = []
    inner_area = 0.0
    extra: list[tuple[str, list[str], dict[str, str]]] = []
    for rid, rtags, outer, inner in rels:
        for wid in inner:
            i = by_id.get(wid)
            if i is not None:
                inners += 1
                inner_area += _ring_area_m2(ways[i][1], nodes)
        if not rtags:
            continue
        open_chains: list[list[str]] = []
        for wid in outer:
            i = by_id.get(wid)
            if i is None:
                continue
            oid, nds, own = ways[i]
            merged = dict(rtags)
            merged.update(own)          # the way's OWN tag wins (§25 (1))
            if merged != own:
                ways[i] = (oid, nds, merged)
                tagged += 1
            if len(nds) < 4 or nds[0] != nds[-1]:
                open_chains.append(nds)
        if open_chains:
            rings, left = _stitch(open_chains)
            for k, ring in enumerate(rings):
                extra.append((f"{rid}#{k}", ring, dict(rtags)))
                stitched += 1
            if left:
                unclosable.append(rid)
    ways.extend(extra)
    return nodes, ways, RelationReport(len(rels), tagged, stitched,
                                       tuple(unclosable), inners, inner_area)


def load_feed(osm_root: str, feed: str, lat: float, lon: float,
              radius_deg: float = 0.05) -> OsmDoc:
    """Ways of ``feed`` with a vertex inside the ``radius_deg`` box around
    ``(lat, lon)``, merged over the 3x3 tile neighbourhood (a missing
    tile contributes nothing; a missing natural tile is an empty feed —
    never a download)."""
    blat, blon = int(math.floor(lat)), int(math.floor(lon))
    out: list[RawWay] = []
    sources: list[str] = []
    schemas: list[tuple[str, str | None]] = []
    rep = RelationReport()
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            tlat, tlon = blat + dlat, blon + dlon
            path = feed_path(osm_root, tlat, tlon, feed)
            if not os.path.isfile(path):
                continue
            sources.append(path)
            schemas.append((path, feed_tag_schema(path)))
            ns = f"{tlat:+03d}{tlon:+04d}:"
            nodes, ways, frep = read_osm_file(path, ns)
            rep = rep.merge(frep)
            for wid, nds, tags in ways:
                pts = tuple(nodes[n] for n in nds if n in nodes)
                if len(pts) < 2:
                    continue
                if not any(abs(p[0] - lat) <= radius_deg
                           and abs(p[1] - lon) <= radius_deg for p in pts):
                    continue
                out.append(RawWay(wid, pts, tags))
    return OsmDoc(feed, tuple(out), tuple(sources), rep, tuple(schemas))
