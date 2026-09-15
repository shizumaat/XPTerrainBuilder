"""THE OBJECT READERS ARE INPUT-ORDER-FREE (lane ``v2othhdet``).

The OTHH "7/42 vs 9/44" finding of RULINGS 2026-09-15ar was ATTRIBUTED to
a shared-corpus change between the two runs (the orchestrator's
``OTHH --refresh-data osm_layers`` rewrote ``+25+051_big_roads.osm.bz2``
under the ``ROAD_CACHE_TAG_SCHEMA`` bump of main ``f6bd825d`` while the
lane's first arm was in flight), not to the reader.  But the hunt found a
REAL order dependence beside it, and these are its twins:

* ``<resource>@k`` used to take ``k`` from the placement's position in the
  INPUT list, so a re-ordered read (a pack rebake, a re-dump, 14av's split
  renaming) silently re-bound an id to a DIFFERENT placement while the
  corridor SET stayed identical — an id that is not a function of the
  geometry cannot join two arms.  Measured before the fix: six of eight
  shuffles moved the binding.
* ``read_shells``'s cover search takes the largest flush plate with a
  strict ``>``; its TIE-break was input order.
* the refusal LIST's order was the read order, so two arms' reports could
  not be diffed line by line.

One derivation site: ``airport/object_cut.placement_key`` /
``placement_order``, taken by ``tunnel_objects.read_corridors``,
``object_cut.read_shells`` and ``wall_corridors.read_wall_corridors``.
"""
from __future__ import annotations

import dataclasses as dc
import random

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import object_cut as _oc
from auto_patch_v2.airport.tunnel_objects import read_corridors
from auto_patch_v2.airport.wall_corridors import read_wall_corridors
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import read_objects

from tests.auto_patch_v2.test_tunnel_objects import (  # noqa: F401
    objs, law, _airport)

_SHUFFLES = 8


def _bore_at(x: float, wid: int):
    t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    r = {"highway": "secondary", "lanes": "2"}
    return (OsmWay(wid, "big_roads", ((x, -70.0), (x, -400.0)), False, t),
            OsmWay(wid - 1, "big_roads", ((x, -400.0), (x, -1300.0)), False, r),
            OsmWay(wid - 2, "big_roads", ((x, 80.0), (x, 380.0)), False, r))


@pytest.fixture(scope="module")
def scene(objs, law):
    """THREE placements of ONE resource (so ``@k`` has something to
    permute) each over its own mapped bore, plus four resources the
    pre-screen refuses for four different reasons."""
    xs = (0.0, 700.0, 1400.0)
    ways = tuple(w for i, x in enumerate(xs) for w in _bore_at(x, -1000 - 10 * i))
    placements = [("wall_long", (x, 0.0), 180.0, -3.0, "OBJECT_AGL") for x in xs]
    placements += [("kerb", (-400.0, 400.0), 0.0, None, "OBJECT"),
                   ("stub", (-600.0, 400.0), 0.0, None, "OBJECT"),
                   ("shallow", (-800.0, 400.0), 0.0, None, "OBJECT"),
                   ("wall_open", (-1000.0, 400.0), 0.0, None, "OBJECT")]
    airport = _airport(objs, law, placements, ways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    return airport, objects, cache


def _shuffles(objects):
    rng = random.Random(20260915)
    for _ in range(_SHUFFLES):
        sh = list(objects)
        rng.shuffle(sh)
        yield sh


def _corridor_fp(cs, st):
    """The WHOLE reading: every corridor field (so the id -> placement
    binding is in it), the refusal list IN ORDER, and the counters."""
    return ([repr(dc.astuple(c)) for c in cs], list(st.refused), st.corridors,
            st.signatures, st.resources, st.not_screened, st.placements)


def test_read_corridors_is_input_order_free(scene, law):
    airport, objects, cache = scene
    base = _corridor_fp(*read_corridors(airport, objects, cache, law))
    assert base[2] == 3, base[1]          # the fixture really admits three
    assert len(base[1]) >= 4              # and really refuses four resources
    # the three ids name three DIFFERENT placements
    assert len({c.split("', ")[2] for c in base[0]}) == 3
    for sh in _shuffles(objects):
        assert _corridor_fp(*read_corridors(airport, sh, cache, law)) == base


def test_read_shells_is_input_order_free(scene, law):
    airport, objects, cache = scene
    base = _oc.read_shells(airport, objects, cache, law)
    fp = ([repr(dc.astuple(c)) for c in base[0]], list(base[1].refused),
          base[1].screened, base[1].shells, base[1].claimed)
    for sh in _shuffles(objects):
        got = _oc.read_shells(airport, sh, cache, law)
        assert ([repr(dc.astuple(c)) for c in got[0]], list(got[1].refused),
                got[1].screened, got[1].shells, got[1].claimed) == fp


def test_read_wall_corridors_is_input_order_free(scene, law):
    airport, objects, cache = scene
    rs, st = read_wall_corridors(airport, objects, cache, law)
    fp = ([repr(dc.astuple(r)) for r in rs], list(st.refused), list(st.admission),
          st.corridors, st.bands, st.pairs, st.placements)
    for sh in _shuffles(objects):
        rs2, st2 = read_wall_corridors(airport, sh, cache, law)
        assert ([repr(dc.astuple(r)) for r in rs2], list(st2.refused),
                list(st2.admission), st2.corridors, st2.bands, st2.pairs,
                st2.placements) == fp


def test_placement_key_is_intrinsic_and_total(scene):
    """The key reads the placement's OWN resource / plan / heading / id —
    never its position, never ``id()``."""
    _airport_, objects, _cache = scene
    keys = [_oc.placement_key(o) for o in objects]
    assert len(set(keys)) == len(keys)                 # total
    assert _oc.placement_order(objects) == sorted(objects, key=_oc.placement_key)
    for o, k in zip(objects, keys):
        assert k[0] == o.path and k[4] == o.id
        assert k[1] == pytest.approx(o.xy[0], abs=5e-4)
        assert k[2] == pytest.approx(o.xy[1], abs=5e-4)
