"""THE REBAKE PLAN LEAVES THE PATCH BUILD (owner RULINGS 2026-10-04x (1),
issue #362; ``airport/rebake_screen.py``).

The patch build writes the SCREEN SIDECAR; the object step builds the plan
from it and the cached partition.  These twins hold:

* the plan built from a sidecar that went through JSON is BYTE-IDENTICAL
  to the plan the patch build used to write inline;
* a sidecar is never served stale — another patch body, moved law or
  code, another plan version, a partition that is gone or is not the one
  the record digested, each refuse BY NAME;
* a build that kept no partition cache writes no sidecar (it plans
  inline), and a default ``plan()`` never writes the extension cache;
* the object stage (``airport/object_plan.py``) builds the plan beside the patch, reads
  it back on the next run, and the freshness gate sends a cold partition
  back through the patch build.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import importlib.util
import inspect
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_tunnel_objects import corridor_map, law, objs  # noqa: E402,F401

from auto_patch_v2.airport import obj8  # noqa: E402
from auto_patch_v2.airport import partition_cache as PC  # noqa: E402
from auto_patch_v2.airport import rebake_screen as RS  # noqa: E402
from auto_patch_v2.airport.pack_partition import partition_pack  # noqa: E402
from auto_patch_v2.airport.rebake_plan import plan as rebake_plan  # noqa: E402
from auto_patch_v2.model.rebake import PLAN_FILENAME, RebakePlan  # noqa: E402
from auto_patch_v2.planar.basins import read_objects  # noqa: E402

PATCH = ("<?xml version='1.0' encoding='UTF-8'?>\n"
         "<osm version='0.6' o4_stamp='{stamp}'>\n"
         "  <node id='-1' lat='1.0' lon='2.0'/>\n</osm>\n")


def _datum(ring):
    """A stand-in solved surface: a value that depends on the ring."""
    return round(100.0 + len(ring) + ring[0][0] * 1e-3, 6)


@pytest.fixture()
def world(corridor_map, law, tmp_path, monkeypatch):  # noqa: F811
    """The patch build's state at its rebake section: the loaded airport
    with its partition, the partition FILED in a cache, the plate seats,
    and the patch it emitted."""
    from auto_patch_v2.pipeline.build import _plate_seats
    monkeypatch.setattr(PC, "_TAKEN", {})
    monkeypatch.setattr(PC, "_FILED", {})
    airport, pm, _stats = corridor_map
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, rep = read_objects(airport, law, cache)
    part = partition_pack(airport, objects, cache, law)
    airport = _dc.replace(airport, partition=part)
    cpath, fp = str(tmp_path / "mod" / "o4_v2_partition_ZZZZ.cache"), "f" * 64
    assert PC.write(cpath, fp, (objects, rep, part, (), cache.derived_state()))
    PC._TAKEN[(os.path.abspath(part.pack_root), airport.icao)] = fp
    patch = tmp_path / "ZZZZ_auto.patch.osm"
    patch.write_text(PATCH.format(stamp="a"), encoding="utf-8", newline="\n")
    args = dict(deck_datum=_datum, exclude=set(), below_grade=[])
    return _dc.make_dataclass("W", ["airport", "objects", "cache", "part", "seats",
                                    "patch", "args", "cpath", "fp"])(
        airport, objects, cache, part, _plate_seats(pm, law), patch, args, cpath, fp)


def _take(w, law):  # noqa: F811
    return RS.take(w.airport, w.objects, law, tunnel_objects=w.seats,
                   patches=[w.patch], **w.args)


def _inline(w, law):  # noqa: F811
    return rebake_plan(w.airport, w.objects, w.cache, law, tunnel_objects=w.seats,
                       partition=w.part, **w.args)


def test_the_plan_from_the_sidecar_is_the_inline_plan_byte_for_byte(world, law):  # noqa: F811
    inline = _inline(world, law)
    assert inline.counts["plate_members"] == 1          # the screen is not empty
    screen = _take(world, law)
    text = screen.to_json()
    back = RS.RebakeScreen.from_json(text)
    assert back.to_json() == text                        # the record round-trips
    assert (back.partition_path, back.partition_fp) == (world.cpath, world.fp)
    # a FRESH process: nothing fingerprinted, nothing filed
    PC._TAKEN.clear(); PC._FILED.clear()
    built = RS.build_plan(back, law, patch=world.patch)
    assert built.to_json() == inline.to_json()
    assert hashlib.sha256(built.to_json().encode()).hexdigest() == \
        hashlib.sha256(inline.to_json().encode()).hexdigest()
    # ...and the reading is this process's from then on (the companions resolve)
    assert PC.filed(world.part.pack_root, "ZZZZ") == (world.cpath, world.fp)


def test_the_connectors_and_the_flat_datum_travel_in_the_record(world, law):  # noqa: F811
    """The stamped connector verdict reads the DEM and the flat-site
    verdict the pipeline — neither is in the partition cache."""
    from auto_patch_v2.model.airport import FlatVerdict

    class _V:
        def to_dict(self):
            return {"pids": [3, 1], "resource": "r.obj", "span_m": 212.5,
                    "solid": True, "own_a": [[0.5, 1]]}

    ring = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))
    air = _dc.replace(world.airport,
                      partition=_dc.replace(world.part, connectors=(_V(),)),
                      flat_site=FlatVerdict("flat_candidate", "flat_candidate",
                                            12.25, "cifp", ((ring, ()),), {"s1": 1}))
    w = _dc.replace(world, airport=air, part=air.partition)
    inline = _inline(w, law)
    assert inline.flat is not None and inline.counts["flat_site"] == 1
    assert inline.connectors == ({"pids": [3, 1], "resource": "r.obj", "span_m": 212.5,
                                  "solid": True, "own_a": [[0.5, 1]]},)
    built = RS.build_plan(RS.RebakeScreen.from_json(_take(w, law).to_json()), law)
    assert built.to_json() == inline.to_json()


def test_a_sidecar_is_never_served_stale(world, law, monkeypatch):  # noqa: F811
    screen = _take(world, law)
    assert RS.stale_reason(screen, law, world.patch) is None
    # the provenance stamp may move; the BODY may not
    world.patch.write_text(PATCH.format(stamp="b"), encoding="utf-8", newline="\n")
    assert RS.stale_reason(screen, law, world.patch) is None
    other = world.patch.with_name("other.osm")
    other.write_text(PATCH.format(stamp="a").replace("lat='1.0'", "lat='1.5'"),
                     encoding="utf-8", newline="\n")
    assert "patch body" in RS.stale_reason(screen, law, other)
    with pytest.raises(RS.StaleScreen, match="patch body"):
        RS.build_plan(screen, law, patch=other)
    assert "cannot be read" in RS.stale_reason(screen, law, other.with_name("gone.osm"))
    for field, value, said in (("law_sha256", "0" * 64, "law tables"),
                               ("ruleset", "nope", "law tables"),
                               ("code_digest", "0" * 64, "code"),
                               ("plan_version", -1, "plan version")):
        with pytest.raises(RS.StaleScreen, match=said):
            RS.build_plan(_dc.replace(screen, **{field: value}), law)
    with pytest.raises(RS.StaleScreen, match="version"):
        RS.RebakeScreen.from_json(screen.to_json().replace('"version":1', '"version":0'))


def test_a_partition_that_is_not_the_recorded_one_is_cold(world, law):  # noqa: F811
    screen = _take(world, law)
    # another fingerprint in the same file: a MISS, never served
    with pytest.raises(RS.ColdPartition, match="fingerprint"):
        RS.build_plan(_dc.replace(screen, partition_fp="e" * 64), law)
    # the same key over ANOTHER reading: the content digest refuses it
    with pytest.raises(RS.ColdPartition, match="content digest"):
        RS.build_plan(_dc.replace(screen, partition_digest="0" * 64), law)
    assert RS.unservable(world.patch) is not None          # not a sidecar at all
    side = world.patch.with_name("s.screen.json")
    side.write_text(screen.to_json(), encoding="utf-8", newline="\n")
    assert RS.unservable(side) is None
    os.remove(world.cpath)
    assert "is gone" in RS.unservable(side)
    PC._FILED.clear()
    with pytest.raises(RS.ColdPartition):
        RS.build_plan(screen, law)


def test_a_deck_ring_the_patch_build_never_read_refuses(world, law, monkeypatch):  # noqa: F811
    screen = _dc.replace(_take(world, law), deck_datum=())
    from auto_patch_v2.airport import rebake_plan as RP

    def _asks(site, objects, cache, law_, deck_datum, **kw):
        return deck_datum([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])

    monkeypatch.setattr(RP, "plan", _asks)
    with pytest.raises(RS.StaleScreen, match="deck ring"):
        RS.build_plan(screen, law)


def test_no_partition_cache_no_sidecar_and_a_default_plan_keeps_nothing(world, law):  # noqa: F811
    PC._TAKEN.clear()
    assert _take(world, law) is None                       # the build plans inline
    from auto_patch_v2.airport import rebake_plan as RP
    assert inspect.signature(RP.plan).parameters["keep_extension"].default is False
    src = inspect.getsource(sys.modules["auto_patch_v2.pipeline.build"].build)
    assert "keep_extension=False" in src and "_rscreen.take(" in src


def test_the_body_hash_is_the_harness_body_hash(world):
    spec = importlib.util.spec_from_file_location(
        "build_airport_for_body_sha",
        Path(__file__).resolve().parents[2] / "tools" / "harness" / "build_airport.py")
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    assert RS.patch_body_sha256(world.patch) == harness.body_sha256(world.patch)


# ── the object stage ─────────────────────────────────────────────────────

#: this run's own mod-cache root in the object-stage twins: NOT where the
#: world's partition cache stands (a carried-over patch dir)
ROOT = "/nowhere/mod-cache"


class _UI:
    def __init__(self):
        self.lines: list[str] = []

    def vprint(self, _level, *parts):
        self.lines.append(" ".join(str(p) for p in parts))


def test_the_object_stage_builds_the_plan_beside_the_patch(world, law, tmp_path, monkeypatch):  # noqa: F811
    from auto_patch import engine_v2 as E
    from auto_patch_v2.airport import object_plan as OP
    inline = _inline(world, law).to_json()
    scratch = tmp_path / "scratch"; scratch.mkdir()
    src_screen = scratch / "ZZZZ.rebake.screen.json"
    src_screen.write_text(_take(world, law).to_json(), encoding="utf-8", newline="\n")
    patch_dir = world.patch.parent
    plan_path = patch_dir / PLAN_FILENAME.format(icao="ZZZZ")
    plan_path.write_text("an EARLIER build's plan", encoding="utf-8", newline="\n")
    placed = OP.place(str(patch_dir), None, "ZZZZ", src_screen)
    # the sidecar is placed and the earlier build's plan is GONE
    assert Path(placed).name == RS.SCREEN_FILENAME.format(icao="ZZZZ")
    assert OP.SCREEN_NAME_RE.match(Path(placed).name)
    assert not E._PLAN_NAME_RE.match(Path(placed).name) and not plan_path.exists()
    assert OP.unservable(str(patch_dir), "ZZZZ") is None

    ui = _UI()
    screen = RS.read(placed)
    got = OP.from_screen(screen, str(plan_path), str(patch_dir), law,
                          say=ui.vprint, mod_cache_root=ROOT)
    assert plan_path.read_bytes() == inline.encode("utf-8")
    assert got == RebakePlan.from_json(inline)
    assert any("building the object plan" in ln for ln in ui.lines)
    assert any("rebake plan" in ln and "units" in ln for ln in ui.lines)
    # a carried-over patch dir names ANOTHER tree's cache: nothing is kept there
    assert sorted(p.name for p in Path(world.cpath).parent.iterdir()) == \
        [Path(world.cpath).name]
    # the next object step READS the plan it built
    ui2 = _UI()
    monkeypatch.setattr(RS, "build_plan", lambda *a, **k: pytest.fail("rebuilt"))
    assert OP.from_screen(screen, str(plan_path), str(patch_dir), law,
                          say=ui2.vprint, mod_cache_root=ROOT) == got
    assert not ui2.lines
    # ...but never against another patch
    world.patch.write_text(PATCH.format(stamp="a").replace("lat='1.0'", "lat='9.0'"),
                           encoding="utf-8", newline="\n")
    assert OP.from_screen(screen, str(plan_path), str(patch_dir), law,
                          say=ui2.vprint, mod_cache_root=ROOT) is None
    assert "STALE" in ui2.lines[-1] and "rebuild the airport's patch" in ui2.lines[-1]

    # an INLINE plan (a build that kept no partition cache) replaces the sidecar
    src_plan = scratch / "ZZZZ.rebake.json"
    src_plan.write_text(inline, encoding="utf-8", newline="\n")
    assert OP.place(str(patch_dir), src_plan, "ZZZZ", None) == str(plan_path)
    assert not Path(placed).exists() and plan_path.read_text(encoding="utf-8") == inline
    assert OP.place(str(patch_dir), None, "ZZZZ", None) is None


def test_a_cold_partition_sends_the_patch_back_through_its_build(world, law, tmp_path):  # noqa: F811
    from auto_patch import engine_v2 as E
    from auto_patch_v2.airport import object_plan as OP
    patch_dir = world.patch.parent
    side = patch_dir / RS.SCREEN_FILENAME.format(icao="ZZZZ")
    side.write_text(_take(world, law).to_json(), encoding="utf-8", newline="\n")
    assert OP.unservable(str(patch_dir), "ZZZZ") is None
    os.remove(world.cpath)
    assert "is gone" in OP.unservable(str(patch_dir), "ZZZZ")
    # the object step itself never re-partitions: it skips, by name
    PC._FILED.clear()
    ui = _UI()
    plan_path = patch_dir / PLAN_FILENAME.format(icao="ZZZZ")
    assert OP.from_screen(RS.read(side), str(plan_path), str(patch_dir), law,
                          say=ui.vprint, mod_cache_root=ROOT) is None
    assert "cannot be built" in ui.lines[-1] and not plan_path.exists()
    # a plan ALREADY built needs no partition
    plan_path.write_text("{}", encoding="utf-8", newline="\n")
    assert OP.unservable(str(patch_dir), "ZZZZ") is None
    # and the driver's gate asks
    from auto_patch import driver
    assert "_oplan.unservable(" in inspect.getsource(driver._auto_patch_is_current)


def test_rebake_after_mesh_places_from_a_sidecar_and_skips_a_stale_one(
        world, law, tmp_path, monkeypatch):  # noqa: F811
    """The stage's own loop: a sidecar in the patch dir is a plan not yet
    built — built once, handed to the placement path as the plan read back
    from its JSON, and never built against another patch."""
    import O4_File_Names as FNAMES
    import O4_Scenery_Packs as SP
    import O4_Vector_Map as VMAP
    from auto_patch import engine_v2 as E, mesh_sampler, post_mesh
    patch_dir = world.patch.parent
    side = patch_dir / RS.SCREEN_FILENAME.format(icao="ZZZZ")
    side.write_text(_take(world, law).to_json(), encoding="utf-8", newline="\n")
    mesh = tmp_path / "mesh.mes"; mesh.write_text("", encoding="utf-8", newline="\n")
    tile = _dc.make_dataclass("T", ["build_dir", "lat", "lon", "modify_custom_airports"])(
        str(tmp_path), 0, 0, True)
    monkeypatch.setattr(post_mesh, "object_anchor_worklist_path",
                        lambda _t: str(patch_dir / "worklist.json"))
    monkeypatch.setattr(post_mesh, "_mesh_is_newer_than_alt", lambda _t, _m: True)
    monkeypatch.setattr(post_mesh, "_is_protected_scenery_root", lambda _p: False)
    monkeypatch.setattr(FNAMES, "mesh_file", lambda _b, _la, _lo: str(mesh))
    monkeypatch.setattr(FNAMES, "airport_mod_cache_root", lambda: str(tmp_path / "elsewhere"))
    monkeypatch.setattr(VMAP, "auto_patch_not_applied", lambda *a, **k: None)
    monkeypatch.setattr(SP, "pack_enabled", lambda _p: True)
    monkeypatch.setattr(mesh_sampler, "MeshElevationSampler", lambda *a, **k: object())
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    placed: list = []
    monkeypatch.setattr(E, "_place_objects",
                        lambda plan_, *a, **k: placed.append(plan_) or {"packs_written": 0})
    inline = _inline(world, law).to_json()

    counts = E.rebake_after_mesh(tile)
    plan_path = patch_dir / PLAN_FILENAME.format(icao="ZZZZ")
    assert counts["airports"] == 1 and counts["airports_failed"] == 0
    assert placed == [RebakePlan.from_json(inline)]
    assert plan_path.read_bytes() == inline.encode("utf-8")
    # the second run reads the plan; ONE airport, not two (plan + sidecar)
    monkeypatch.setattr(RS, "build_plan", lambda *a, **k: pytest.fail("rebuilt"))
    counts = E.rebake_after_mesh(tile)
    assert counts["airports"] == 1 and len(placed) == 2 and placed[1] == placed[0]
    # another patch under the same sidecar: SKIPPED, nothing placed
    world.patch.write_text(PATCH.format(stamp="a").replace("lat='1.0'", "lat='7.0'"),
                           encoding="utf-8", newline="\n")
    counts = E.rebake_after_mesh(tile)
    assert counts["airports"] == 0 and counts["airports_skipped_stale_plan"] == 1
    assert len(placed) == 2
