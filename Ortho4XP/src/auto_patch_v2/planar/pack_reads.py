"""The CLASSIFICATION-FREE pack reads of the planar build, made ONCE per
build (issue #362; the single-pass principle).

``planar/build.build`` runs TWICE in a build that mints a ribbon: once on
the classification and once on the ribbon-free one (#100 option (c),
``pipeline/stage_one_map``).  Five of its structure reads take NO
classification — the tunnel corridors, the thin plates, the door wells and
the sunken roads (:func:`pack_reads`) and the wall corridors
(:func:`wall_corridor_reads`) read the airport's DEM, frame, mapped
ways and DSF objects, the pack's placed objects, the parsed geometry and
the law — so the second pass's reading IS the first's by construction.  At
OTHH the door wells alone were 628 s and the wall corridors 120 s, paid
twice.  (The wall-corridor reader takes a classification ONLY for the
``--stage structures`` replay's ``measure`` probe; a build never passes
one, so none is an input here.)

:func:`pack_reads` is the one site: the reading is kept on the build's own
``ResourceCache`` (``placed``, beside the pack's object read, which is
never pickled) and reused while EVERY input is the same object.  A
different airport field, object list or law is a different reading and is
read afresh — never a stale answer.

:func:`ring_reads` is the SAME store's second kind of entry: the basin
pass's per-ring pack readings (the rim diagnostic, the cover fractions, the
ramp decks), which read a ring of the pack's own floor witnesses, the
members' parsed geometry and the DEM — never a cell.  The basin pass keys
each on the ring and its members, so a ring the second pass derives
differently (another claimed set) is read afresh.  At OTHH they were the
basin pass's ~150 s, paid twice.

The records are frozen; the STATS are not, and the planar build writes
them (``tstats.plates`` / ``tstats.refused``; ``sunken_groups`` appends to
the road stats' ``refused``).  Every call therefore hands out its OWN deep
copy of the stats and a fresh list of the records, so no pass can write
another pass's reading.

Twin: ``tests/auto_patch_v2/test_once362.py``.
"""
from __future__ import annotations

import copy
import dataclasses as _dc
import typing as _t

from ..airport import reader_work as _rw
from ..airport.door_wells import DoorStats, read_door_wells
from ..airport.sunken_roads import SunkenRoadStats, read_sunken_roads
from ..airport.thin_plates import PlateStats, read_plates
from ..airport.tunnel_objects import TunnelObjectStats, read_corridors
from ..airport.wall_corridors import WallCorridorStats
from ..airport.wall_family import read_wall_corridors
from ..model import pulse as _pulse

__all__ = ["PackReads", "pack_reads", "pool_report", "ring_reads",
           "wall_corridor_reads"]

#: the key on ``ResourceCache.placed``
_KEY = "planar_pack_reads"
#: the store's entries
_READS, _WALLS, _RINGS, _POOL = "reads", "walls", "rings", "pool"


@_dc.dataclass
class PackReads:
    """The four readings, each with its own stats."""

    corridors: list
    tunnel_stats: TunnelObjectStats
    plates: list
    plate_stats: PlateStats
    wells: list
    door_stats: DoorStats
    roads: list
    road_stats: SunkenRoadStats

    def handout(self) -> "PackReads":
        """A caller's own copy: fresh lists over the same frozen records,
        deep-copied stats."""
        return PackReads(
            list(self.corridors), copy.deepcopy(self.tunnel_stats),
            list(self.plates), copy.deepcopy(self.plate_stats),
            list(self.wells), copy.deepcopy(self.door_stats),
            list(self.roads), copy.deepcopy(self.road_stats))


def _inputs(airport, objects, law) -> tuple:
    """Everything the readers read besides the cache itself: the
    airport fields they open (not the airport — the build re-binds it with
    the flat-site verdict between the two passes), the objects, the law."""
    return (airport.dem, airport.frame, airport.osm_ways, airport.dsf_objects,
            objects, law)


def _read(airport, objects, cache, law, store: dict | None = None,
          walls: bool = False) -> PackReads:
    """The four readings.  With a work pool every reader is read by its
    workers (and, with ``walls``, the wall corridors — kept on ``store``
    for :func:`wall_corridor_reads`); what a pool does not answer is read
    here, the same computation.  The door wells and the sunken roads leave
    their at-grade read on ``cache`` (``airport/reader_work``): they are
    settled — or read — in the order one core reads them."""
    kinds = tuple(k for k in _rw.READERS if k != _rw.WALLS or (walls and store is not None))
    ahead = _rw.begin(airport, objects, cache, law, kinds)
    if ahead is None:
        _pulse.tick("tunnel and plate objects")
        tunnels = _tunnels(airport, objects, cache, law)
        wells, dstats = read_door_wells(airport, objects, cache, law)
        roads, rstats = read_sunken_roads(airport, objects, cache, law)
        return PackReads(*tunnels, wells, dstats, roads, rstats)
    try:
        got = ahead.collect()
    finally:
        ahead.close()
    if store is not None:
        store[_POOL] = ahead.report
        if _rw.WALLS in got:
            store[_WALLS] = got[_rw.WALLS]
    tunnels = got.get(_rw.TUNNELS) or _tunnels(airport, objects, cache, law)
    wells, dstats = ahead.settle(_rw.DOORS) or read_door_wells(airport, objects, cache, law)
    roads, rstats = ahead.settle(_rw.ROADS) or read_sunken_roads(airport, objects, cache, law)
    return PackReads(*tunnels, wells, dstats, roads, rstats)


def _tunnels(airport, objects, cache, law) -> tuple:
    corridors, tstats = read_corridors(airport, objects, cache, law)
    # an object is read ONCE, by the senior reader: the plates skip the
    # resources the corridors already admitted
    return (corridors, tstats,
            *read_plates(airport, objects, cache, law, {c.resource for c in corridors}))


def _store(airport, objects: _t.Sequence, cache, law) -> dict:
    """THE ONE MEMO: this build's readings, kept while every input is the
    SAME object and dropped whole when one is not."""
    inputs = _inputs(airport, objects, law)
    held = cache.placed.get(_KEY)
    if held is None or len(held[0]) != len(inputs) \
            or any(a is not b for a, b in zip(held[0], inputs)):
        # the inputs are held WITH the readings, so their identities cannot
        # be recycled while they stand
        held = (inputs, {})
        cache.placed[_KEY] = held
    return held[1]


def pack_reads(airport, objects: _t.Sequence, cache, law, *,
               walls: bool = False) -> PackReads:
    """The four classification-free readings for this build: read on the
    first call, reused while every input is the SAME object.  ``walls``
    says the caller asks :func:`wall_corridor_reads` next, so a work pool
    reads the wall corridors beside these (``_read``)."""
    store = _store(airport, objects, cache, law)
    if _READS not in store:
        store[_READS] = _read(airport, objects, cache, law, store,
                              walls and _WALLS not in store)
    return store[_READS].handout()


def pool_report(cache) -> dict | None:
    """The work pool's own account of this build's readings (``WorkPool.
    report`` + the ``readers`` it answered), or ``None`` when they were
    read on one core.  A clock and a head count — never part of a digest."""
    held = cache.placed.get(_KEY)
    return held[1].get(_POOL) if held else None


def wall_corridor_reads(airport, objects: _t.Sequence, cache, law
                        ) -> tuple[list, WallCorridorStats]:
    """The wall corridors for this build (``airport/wall_corridors``), read
    on the first call and reused like :func:`pack_reads`: the caller's own
    list of the frozen records and its own copy of the stats.  A reading of
    its own rather than a fifth field of :class:`PackReads`, because the
    ``--stage structures`` replay takes the four and reads the corridors
    itself, with its ``measure`` probe."""
    store = _store(airport, objects, cache, law)
    if _WALLS not in store:
        _pulse.tick("wall corridors")
        store[_WALLS] = read_wall_corridors(airport, objects, cache, law)
    walls, stats = store[_WALLS]
    return list(walls), copy.deepcopy(stats)


def ring_reads(airport, objects: _t.Sequence, cache, law) -> dict:
    """The basin pass's per-ring pack readings for this build
    (``planar/basins.build_basins(reads=...)``, which owns the keys): the
    same store, so the same inputs scope them."""
    return _store(airport, objects, cache, law).setdefault(_RINGS, {})
