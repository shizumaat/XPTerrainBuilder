"""Issue #362 twins: the four CLASSIFICATION-FREE pack reads of the planar
build (tunnel corridors, thin plates, door wells, sunken roads) run ONCE
per build — the ribbon-free second pass (#100 (c)) is handed the first
pass's reading (``planar/pack_reads``), and its planar map is the one a
fresh read builds.  Synthetic, offline."""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.airport import frame_entry as _fe
from auto_patch_v2.airport.obj8 import ResourceCache
from auto_patch_v2.classify import classify
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.stage_one_map import ribbon_free
from auto_patch_v2.planar import pack_reads as _pr
from auto_patch_v2.planar.build import build as planar_build

from test_roadmint100 import SOUTH, _SlopeDem, _way, _with

READERS = ("read_corridors", "read_plates", "read_door_wells", "read_sunken_roads")


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _cache(law):
    return ResourceCache(law.tables.structures.basin.min_solid_thickness_m,
                         _fe.quantum(law))


def _counted(monkeypatch):
    calls = {n: 0 for n in READERS}
    for n in READERS:
        real = getattr(_pr, n)

        def spy(*a, _n=n, _real=real, **k):
            calls[_n] += 1
            return _real(*a, **k)
        monkeypatch.setattr(_pr, n, spy)
    return calls


def _untimed(stats):
    """A stats record without its wall clocks (``*_s``)."""
    return {k: v for k, v in _dc.asdict(stats).items() if not k.endswith("_s")}


def _same_map(a, b):
    assert a.faces == b.faces
    assert a.edges == b.edges
    assert a.vertices == b.vertices
    assert a.breaklines == b.breaklines


def test_the_four_reads_run_once_across_both_planar_passes(law, monkeypatch):
    """A late (ribbon) cell makes the build run the planar prefix twice.
    The second pass — on the ribbon-free classification, with the airport
    RE-BOUND as the build re-binds it (the flat-site verdict) — calls no
    reader, and its map equals the one a fresh read (main's second pass)
    builds."""
    airport = _dc.replace(_with(_way(-3, SOUTH, highway="tertiary")), dem=_SlopeDem())
    cl = classify(airport, law)
    cl0 = ribbon_free(cl)
    assert cl0 is not None, "the fixture must carry a ribbon"
    calls = _counted(monkeypatch)
    cache, oo = _cache(law), []
    pm1, st1 = planar_build(airport, cl, law, objects_out=oo, cache=cache)
    assert calls == {n: 1 for n in READERS}
    rebound = _dc.replace(airport, flat_site=airport.flat_site)
    assert rebound is not airport
    pm0, _st0 = planar_build(rebound, cl0, law, cache=cache, objects=oo[0],
                             object_report=st1.basins.objects)
    assert calls == {n: 1 for n in READERS}
    # main's second pass: every read made afresh
    fresh, _f = planar_build(rebound, cl0, law, cache=_cache(law), objects=oo[0],
                             object_report=st1.basins.objects)
    assert calls == {n: 2 for n in READERS}
    _same_map(pm0, fresh)
    # and the first pass is untouched by the second
    again, st_again = planar_build(airport, cl, law, cache=_cache(law))
    _same_map(pm1, again)
    for name in ("tunnel_objects", "door_wells", "sunken_roads"):
        assert _untimed(getattr(st1, name)) == _untimed(getattr(st_again, name))


def test_a_reused_reading_equals_a_fresh_one_and_no_caller_can_write_it(law):
    """Deep equality of the handed-out reading with a fresh call, and the
    stats are each caller's OWN copy: the planar build appends to them
    (``sunken_groups`` -> ``refused``), which must not reach the next pass."""
    airport = _dc.replace(_with(), dem=_SlopeDem())
    cache, objects = _cache(law), []
    first = _pr.pack_reads(airport, objects, cache, law)
    first.road_stats.refused.append("written by the first pass")
    first.tunnel_stats.refused.append("written by the first pass")
    first.corridors.append("not a corridor")
    second = _pr.pack_reads(airport, objects, cache, law)
    fresh = _pr._read(airport, objects, _cache(law), law)
    for name in ("corridors", "plates", "wells", "roads"):
        assert getattr(second, name) == getattr(fresh, name)
    for name in ("tunnel_stats", "plate_stats", "door_stats", "road_stats"):
        assert _untimed(getattr(second, name)) == _untimed(getattr(fresh, name))
    assert second.road_stats.refused == []


def test_a_different_input_is_read_afresh(law, monkeypatch):
    """The reading is reused only while EVERY input is the same object —
    another object list, law or DEM is another reading."""
    airport = _dc.replace(_with(), dem=_SlopeDem())
    calls = _counted(monkeypatch)
    cache, objects = _cache(law), []
    _pr.pack_reads(airport, objects, cache, law)
    _pr.pack_reads(_dc.replace(airport), objects, cache, law)
    assert calls["read_door_wells"] == 1
    _pr.pack_reads(airport, [], cache, law)
    assert calls["read_door_wells"] == 2
    _pr.pack_reads(_dc.replace(airport, dem=_SlopeDem()), objects, cache, law)
    assert calls["read_door_wells"] == 3
    _pr.pack_reads(airport, objects, cache, Law.for_airport("SYNT"))
    assert calls["read_door_wells"] == 4


def test_the_second_pass_prints_no_reader_progress(law):
    """The heartbeat stays truthful: a reused reading ticks no reader's
    label (``model/pulse``)."""
    from auto_patch_v2.model import pulse
    airport = _dc.replace(_with(), dem=_SlopeDem())
    cache, objects = _cache(law), []
    _pr.pack_reads(airport, objects, cache, law)
    pulse.tick("the caller's own step")
    _pr.pack_reads(airport, objects, cache, law)
    assert pulse.describe() == "the caller's own step"
    pulse.clear()
