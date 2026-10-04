"""The CLASSIFICATION-FREE pack reads of the planar build, made ONCE per
build (issue #362; the single-pass principle).

``planar/build.build`` runs TWICE in a build that mints a ribbon: once on
the classification and once on the ribbon-free one (#100 option (c),
``pipeline/stage_one_map``).  Four of its structure reads take NO
classification — the tunnel corridors, the thin plates, the door wells and
the sunken roads read the airport's DEM, frame, mapped ways and DSF
objects, the pack's placed objects, the parsed geometry and the law — so
the second pass's reading IS the first's by construction.  At OTHH the
door wells alone were 628 s, paid twice.

:func:`pack_reads` is the one site: the reading is kept on the build's own
``ResourceCache`` (``placed``, beside the pack's object read, which is
never pickled) and reused while EVERY input is the same object.  A
different airport field, object list or law is a different reading and is
read afresh — never a stale answer.

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

from ..airport.door_wells import DoorStats, read_door_wells
from ..airport.sunken_roads import SunkenRoadStats, read_sunken_roads
from ..airport.thin_plates import PlateStats, read_plates
from ..airport.tunnel_objects import TunnelObjectStats, read_corridors
from ..model import pulse as _pulse

__all__ = ["PackReads", "pack_reads"]

#: the key on ``ResourceCache.placed``
_KEY = "planar_pack_reads"


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
    """Everything the four readers read besides the cache itself: the
    airport fields they open (not the airport — the build re-binds it with
    the flat-site verdict between the two passes), the objects, the law."""
    return (airport.dem, airport.frame, airport.osm_ways, airport.dsf_objects,
            objects, law)


def _read(airport, objects, cache, law) -> PackReads:
    _pulse.tick("tunnel and plate objects")
    corridors, tstats = read_corridors(airport, objects, cache, law)
    # an object is read ONCE, by the senior reader: the plates skip the
    # resources the corridors already admitted
    plates, pstats = read_plates(airport, objects, cache, law,
                                 {c.resource for c in corridors})
    wells, dstats = read_door_wells(airport, objects, cache, law)
    roads, rstats = read_sunken_roads(airport, objects, cache, law)
    return PackReads(corridors, tstats, plates, pstats, wells, dstats, roads, rstats)


def pack_reads(airport, objects: _t.Sequence, cache, law) -> PackReads:
    """The four classification-free readings for this build: read on the
    first call, reused while every input is the SAME object."""
    inputs = _inputs(airport, objects, law)
    held = cache.placed.get(_KEY)
    if held is None or len(held[0]) != len(inputs) \
            or any(a is not b for a, b in zip(held[0], inputs)):
        # the inputs are held WITH the reading, so their identities cannot
        # be recycled while it stands
        held = (inputs, _read(airport, objects, cache, law))
        cache.placed[_KEY] = held
    return held[1].handout()
