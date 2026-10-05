"""THE CONNECTOR TOPOLOGY, CACHED beside the partition (issue #362).

``footprint_connector.solid_connectors`` runs on EVERY build, cached
partition or not, because its verdict reads the DEM.  But all of its cost
is the step before the DEM is asked anything — ``footprint_unit.
plan_units_and_connectors``, the §16g (6) articulation reading (OTHH:
~45 s of ring-to-ring tests, for a pack that turns out to have no
connector at all) — and that step is a pure function of the plan's units
and contacts and four law numbers.  The candidates it returns are kept
here; the verdict is still taken fresh on the ground of the day.

KEY: the partition's own fingerprint (pack content, dump, law, frame,
code — ``partition_cache``), a digest of the plan in hand (:func:`digest`:
its units with every part, its contacts and abutments, and the law
numbers), through ``partition_cache.companion``.

WRITTEN ONLY WITH THE PARTITION.  The record is HELD
(``partition_cache.hold_companion``) and reaches the disk only when the
partition cache itself is written — so a stage that may not write the
partition cache (``write_cache=False``), a replay or a tool writes no
topology either, and a build that HIT the partition only ever reads.
"""
from __future__ import annotations

import hashlib
import typing as _t

from . import partition_cache as _pcache

__all__ = ["SUFFIX", "digest", "load", "hold"]

#: Appended to the partition cache's own file name.  Bump the trailing
#: number when the SHAPE of the record changes.
SUFFIX = ".topo1"


def digest(plan: _t.Any, params: tuple) -> str:
    """sha256 of what the topology reads: every unit, member and part of
    ``plan`` by VALUE (their ``repr`` — floats round-trip exactly), its
    contacts and abutments, and ``params`` (the law numbers)."""
    h = hashlib.sha256()
    for piece in (getattr(plan, "units", ()), getattr(plan, "contacts", ()),
                  getattr(plan, "abutments", ()), tuple(params)):
        h.update(repr(piece).encode()); h.update(b"\0")
    return h.hexdigest()


def load(plan: _t.Any, key: str) -> "tuple | None":
    """The connector candidates kept for ``plan`` under ``key``
    (:func:`digest`), or ``None``."""
    slot = _pcache.companion(getattr(plan, "pack_root", ""),
                             getattr(plan, "icao", ""), SUFFIX, key)
    got = None if slot is None else _pcache.read(*slot)
    return got if isinstance(got, tuple) else None


def hold(plan: _t.Any, key: str, conns: tuple) -> None:
    """Hand ``conns`` to the partition cache, to be written IF AND WHEN
    it writes this airport's partition (module doc)."""
    _pcache.hold_companion(getattr(plan, "pack_root", ""),
                           getattr(plan, "icao", ""), SUFFIX, key, conns)
