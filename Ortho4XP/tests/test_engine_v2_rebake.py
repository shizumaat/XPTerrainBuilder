"""The v2 re-bake driver hook (``auto_patch.engine_v2.rebake_after_mesh``,
RULINGS 2026-09-04i 04f-1) end to end over a synthetic pack, plan and
mesh: writes only with ``modify_custom_airports`` on, through v1's
``.anchor_bak`` discipline; byte-idempotent on a second run; the restore
round-trip returns the authored bytes; a shared-anchor family takes ONE
delta; the mesh-end hook dispatches by engine.  Hermetic under
``tmp_path`` (the synthetic mesh of ``tests/test_post_mesh.py``)."""
from __future__ import annotations

import hashlib
import json
import os
import types

import pytest

import O4_File_Names as FNAMES
import O4_Mesh_Utils
from auto_patch import engine_v2, object_rebake, post_mesh
from auto_patch_v2.emit import rebake as R

TILE_LAT, TILE_LON, TILE = 35, -81, "+35-081"
ANCHOR = (35.21, -80.93)
BASE = 100.0
SLOPE = 10000.0              # m per degree of longitude
WEST = ANCHOR[1] - 0.002


def _z(lon: float) -> float:
    return BASE + (lon - WEST) * SLOPE


def _write_mesh(path: str) -> None:
    corners = [(WEST, ANCHOR[0] - 0.002), (ANCHOR[1] + 0.002, ANCHOR[0] - 0.002),
               (ANCHOR[1] + 0.002, ANCHOR[0] + 0.002), (WEST, ANCHOR[0] + 0.002)]
    lines = ["MeshVersionFormatted 2", "Dimension 3", "", "Vertices", "4"]
    for lon, lat in corners:
        lines.append(f"{lon:.15f} {lat:.15f} {_z(lon) / 100000.0:.15f} 0")
    lines += ["", "Normals", "0", "", "Triangles", "2", "1 2 3 0", "1 3 4 0"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _slab(y: float) -> str:
    """A 10 m slab at authored ``y`` (feet = the slab itself)."""
    vt = [(-5, y, -5), (5, y, -5), (5, y, 5), (-5, y, 5)]
    return "\n".join(["A", "800", "OBJ", "", "POINT_COUNTS 4 0 0 6"] +
                     [f"VT {x:.6f} {yy:.6f} {z:.6f} 0.0 1.0 0.0 0.0 0.0" for x, yy, z in vt] +
                     ["IDX10 0 1 2 0 2 3", "TRIS 0 6"]) + "\n"


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@pytest.fixture()
def world(tmp_path, monkeypatch):
    patches = tmp_path / "Patches" / TILE
    patches.mkdir(parents=True)
    monkeypatch.setattr(FNAMES, "patch_dir", lambda la, lo: str(patches))
    build_dir = tmp_path / "Tiles" / f"zOrtho4XP_{TILE}"
    build_dir.mkdir(parents=True)
    tile = types.SimpleNamespace(lat=TILE_LAT, lon=TILE_LON, build_dir=str(build_dir),
                                 modify_custom_airports=True, auto_patch_engine="v2")
    _write_mesh(FNAMES.mesh_file(tile.build_dir, TILE_LAT, TILE_LON))
    pack = tmp_path / "Custom Scenery" / "ZZZZ Pack"
    (pack / "objects").mkdir(parents=True)
    authored = {"objects/a.obj": _slab(-5.0), "objects/b.obj": _slab(-5.0),
                "objects/flat.obj": _slab(0.0)}
    for rel, text in authored.items():
        (pack / rel).write_text(text)
    feet = tuple(R.Foot(ANCHOR[0], ANCHOR[1], -5.0) for _ in range(4))
    members = tuple(R.Member(f"dsf:{n}", f"objects/{n}.obj", str(pack / f"objects/{n}.obj"),
                             str(pack / f"objects/{n}.obj"), 0.0, feet) for n in ("a", "b"))
    flat = R.Member("dsf:flat", "objects/flat.obj", str(pack / "objects/flat.obj"),
                    str(pack / "objects/flat.obj"), 0.0,
                    tuple(R.Foot(ANCHOR[0], ANCHOR[1], 0.0) for _ in range(4)))
    plan = R.RebakePlan("ZZZZ", "ZZZZ Pack", str(pack), (
        R.Unit("unit:0", ANCHOR, 0.0, members),
        R.Unit("unit:1", (ANCHOR[0] + 0.0005, ANCHOR[1]), 0.0, (flat,))), (), {"units": 2})
    (patches / R.PLAN_FILENAME.format(icao="ZZZZ")).write_text(plan.to_json())
    return types.SimpleNamespace(tile=tile, pack=pack, patches=patches, authored=authored)


def _live(w, n):
    return str(w.pack / f"objects/{n}.obj")


def _baks(w):
    return sorted(p for p in (w.pack / "objects").iterdir() if p.name.endswith(".anchor_bak"))


def test_bakes_through_v1_writer_with_backup_and_one_family_delta(world):
    w = world
    counts = engine_v2.rebake_after_mesh(w.tile)
    assert counts["airports"] == 1 and counts["units"] == 2
    assert counts["units_baked"] == 1 and counts["units_below_threshold"] == 1
    assert counts["objects_written"] == 2 and counts["packs_written"] == 1
    # the family: a and b, one delta (+5: feet at −5 onto the ground)
    for n in ("a", "b"):
        bak = _live(w, n) + ".anchor_bak"
        assert os.path.isfile(bak) and open(bak).read() == w.authored[f"objects/{n}.obj"]
        ys = [float(l.split()[2]) for l in open(_live(w, n)) if l.startswith("VT")]
        assert ys == pytest.approx([0.0] * 4, abs=1e-6)
    # below threshold: untouched, no backup
    assert open(_live(w, "flat")).read() == w.authored["objects/flat.obj"]
    assert not os.path.exists(_live(w, "flat") + ".anchor_bak")
    prov = json.load(open(w.pack / object_rebake.PROVENANCE_FILENAME))
    assert prov["objects"]["objects/a.obj"]["delta_m"] == pytest.approx(5.0)
    assert prov["objects"]["objects/b.obj"]["delta_m"] == pytest.approx(5.0)
    assert prov["objects"]["objects/a.obj"]["decision_kind"] == "v2_feet"
    res = json.load(open(w.patches / engine_v2.REBAKE_RESULT_FILENAME.format(icao="ZZZZ")))
    assert res["seat"]["counts"]["baked"] == 1 and not res["measure_only"]


def test_second_run_is_byte_idempotent(world):
    w = world
    engine_v2.rebake_after_mesh(w.tile)
    before = {n: _sha(_live(w, n)) for n in ("a", "b", "flat")}
    baks = _baks(w)
    engine_v2.rebake_after_mesh(w.tile)
    assert {n: _sha(_live(w, n)) for n in ("a", "b", "flat")} == before
    assert _baks(w) == baks and len(baks) == 2
    for p in baks:                       # never overwritten with a bake
        assert p.read_text() == w.authored["objects/" + p.name[:-len(".anchor_bak")]]


def test_restore_round_trip_returns_the_authored_bytes(world):
    w = world
    engine_v2.rebake_after_mesh(w.tile)
    assert _sha(_live(w, "a")) != hashlib.sha256(w.authored["objects/a.obj"].encode()).hexdigest()
    assert object_rebake.restore(str(w.pack)) == 2
    for rel, text in w.authored.items():
        assert open(w.pack / rel).read() == text
    assert not os.path.exists(w.pack / object_rebake.PROVENANCE_FILENAME)


def test_modify_custom_airports_off_writes_nothing(world):
    w = world
    w.tile.modify_custom_airports = False
    before = {rel: _sha(str(w.pack / rel)) for rel in w.authored}
    counts = engine_v2.rebake_after_mesh(w.tile)
    assert counts["objects_written"] == 0 and counts["packs_written"] == 0
    assert {rel: _sha(str(w.pack / rel)) for rel in w.authored} == before
    assert _baks(w) == []
    assert not os.path.exists(w.pack / object_rebake.PROVENANCE_FILENAME)


def test_modify_custom_airports_off_puts_an_earlier_bake_back(world):
    """v1 semantics: OFF is measure-only, and a pack an earlier build
    baked converges back to its authored bytes."""
    w = world
    engine_v2.rebake_after_mesh(w.tile)
    w.tile.modify_custom_airports = False
    counts = engine_v2.rebake_after_mesh(w.tile)
    assert counts["objects_reverted"] == 2
    for rel, text in w.authored.items():
        assert open(w.pack / rel).read() == text


def test_mesh_end_hook_dispatches_by_engine(world, monkeypatch):
    calls = []
    monkeypatch.setattr(engine_v2, "rebake_after_mesh", lambda t: calls.append("v2") or {})
    monkeypatch.setattr(post_mesh, "rebake_dsf_objects", lambda t: calls.append("v1") or {})
    O4_Mesh_Utils._auto_patch_post_mesh_rebake(world.tile)
    world.tile.auto_patch_engine = "v1"
    O4_Mesh_Utils._auto_patch_post_mesh_rebake(world.tile)
    assert calls == ["v2", "v1"]


def test_kill_switch_measures_and_writes_nothing(world, monkeypatch):
    """v1's ``DSF_OBJECT_REANCHOR`` off: the seat is measured and recorded
    (the result sidecar), no pack file is written or reverted."""
    from auto_patch import config
    w = world
    monkeypatch.setattr(config, "DSF_OBJECT_REANCHOR", False)
    before = {rel: _sha(str(w.pack / rel)) for rel in w.authored}
    counts = engine_v2.rebake_after_mesh(w.tile)
    assert counts["units"] == 2 and counts["units_baked"] == 1
    assert counts["objects_written"] == 0 and _baks(w) == []
    assert {rel: _sha(str(w.pack / rel)) for rel in w.authored} == before
    res = json.load(open(w.patches / engine_v2.REBAKE_RESULT_FILENAME.format(icao="ZZZZ")))
    assert res["write_enabled"] is False and res["seat"]["counts"]["baked"] == 1
    assert res["seat"]["units"][0]["delta_m"] == pytest.approx(5.0)


def test_held_unit_keeps_the_current_bytes(world):
    """A unit v2 cannot judge (every founding foot on water) is HELD:
    an earlier bake on disk is neither re-seated nor reverted."""
    w = world
    engine_v2.rebake_after_mesh(w.tile)                 # bake a and b (+5)
    baked = {n: _sha(_live(w, n)) for n in ("a", "b")}
    plan = R.RebakePlan.from_json(
        (w.patches / R.PLAN_FILENAME.format(icao="ZZZZ")).read_text())
    # every witness of unit:0 moves to water: the synthetic mesh has no
    # water triangle, so mark the mesh's triangle attribute as water
    mesh = FNAMES.mesh_file(w.tile.build_dir, TILE_LAT, TILE_LON)
    from auto_patch import mesh_sampler
    text = open(mesh).read().replace("1 2 3 0", f"1 2 3 {mesh_sampler.WATER_BIT_MASK}") \
        .replace("1 3 4 0", f"1 3 4 {mesh_sampler.WATER_BIT_MASK}")
    open(mesh, "w").write(text)
    mesh_sampler._read_mesh_cached.cache_clear() if hasattr(
        mesh_sampler._read_mesh_cached, "cache_clear") else None
    counts = engine_v2.rebake_after_mesh(w.tile)
    assert counts["units_held"] == 2 and counts["objects_written"] == 0
    assert counts["objects_reverted"] == 0
    assert {n: _sha(_live(w, n)) for n in ("a", "b")} == baked
