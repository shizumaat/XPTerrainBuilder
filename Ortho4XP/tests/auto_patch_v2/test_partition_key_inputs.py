"""issue #382 — THE PARTITION CACHE KEY COVERS WHAT THE READING READS.

The cached pack reading holds ground the DEM gave it (``anchor_z`` on every
placed object and everything built on it), content of resources resolved
outside the pack, and bridge ways from OSM; the key named none of them.

D — THE GROUND.  D1 same pack, the DEM moves -> MISS, and the re-read
overwrites; the same DEM -> HIT.  D2 a DEM that moved somewhere the reading
never asked still HITS (the samples, not the tile).  D3 the witness answers
as the DEM does and records the scalar and the batched question alike; a
NaN (outside the raster) must be a NaN again.  D4 a HIT whose clusters are
re-derived re-writes the SAME ground record.  D5 the companions follow: the
extension cache MISSES on a reading re-taken on new ground and the content
digest the object-plan sidecar is held to moves.  D6 the cached reading
asks the DEM through ``.z`` and nothing else, and ``pack_stage`` hands it
the witness.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import ast
import dataclasses as dc
import importlib
import inspect

import numpy as np
import pytest

from auto_patch_v2.airport import dem_witness as DW
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import partition_code as PCODE
from auto_patch_v2.airport import partition_cache as PC
from auto_patch_v2.law import Law

LAW = Law.for_airport("")


class _Flat:
    """A DEM that answers ``level`` everywhere."""

    def __init__(self, level: float) -> None:
        self.level = level

    def z(self, x: float, y: float) -> float:
        return self.level


def _world(tmp: Path):
    root = tmp / "c_Pack"
    (root / "Earth nav data").mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text("I\n1100\n", encoding="utf-8", newline="")
    (root / "Objects").mkdir()
    (root / "Objects" / "Terminal.obj").write_text("A\n800\nOBJ\n", encoding="utf-8", newline="")
    dump = tmp / "+18-064.dsf.84ffe846.text"
    dump.write_text("OBJECT_DEF Objects/Terminal.obj\n", encoding="utf-8", newline="")
    return root, str(dump), str(tmp / "mod")


def _airport(root: Path, dem, objects=(), ways=()):
    pk = NS(name=root.name, apt_dat_path=str(root / "Earth nav data" / "apt.dat"),
            borrowed_apt_dat_path="", borrowed_block_sha256="")
    return NS(pack=pk, frame=NS(crs="EPSG:32620", lat0=18.04, lon0=-63.1),
              icao="TNCM", dem=dem, dsf_objects=tuple(objects), osm_ways=tuple(ways))


def _read(dem_z):
    """The pack reading's own placement record for one anchor (an
    unresolved placement still takes its ``anchor_z`` from the DEM)."""
    bl = LAW.tables.structures.basin
    objs, _rep = obj8.read_placed_objects(
        [("o1", "Objects/Absent.obj", (10.0, 20.0), 0.0, None, "OBJECT")], None, None,
        dem_z, bl.admission_depth_m, bl.min_solid_thickness_m, bl.contact_band_m,
        floor_plate_normal_y_min=bl.floor_plate_normal_y_min)
    return objs


def _stage(root, dump, mod, dem):
    """What ``pack_stage`` does with the cache: key, read, and on a MISS
    read the pack through the witness and write.  ``(state, objects)``."""
    a = _airport(root, dem)
    fp = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    path = PC.cache_path(a, mod, dump)
    hit = PC.read(path, fp)
    if hit is not None:
        return "HIT", hit
    objs = _read(PC.ground_witness(fp, a.dem).z)
    assert PC.write(path, fp, objs)
    return "MISS", objs


def test_d1_a_changed_dem_misses_and_the_same_dem_hits(tmp_path):
    """THE INTERVENTION of the attribution (it was a HIT carrying
    ``anchor_z`` 100 on a DEM reading 107)."""
    root, dump, mod = _world(tmp_path)
    assert _stage(root, dump, mod, _Flat(100.0))[0] == "MISS"
    state, objs = _stage(root, dump, mod, _Flat(100.0))
    assert state == "HIT" and objs[0].anchor_z == 100.0
    state, objs = _stage(root, dump, mod, _Flat(107.0))
    assert state == "MISS" and objs[0].anchor_z == 107.0
    state, objs = _stage(root, dump, mod, _Flat(107.0))      # the re-read was kept
    assert state == "HIT" and objs[0].anchor_z == 107.0
    assert _stage(root, dump, mod, _Flat(100.0))[0] == "MISS"


class _Step(_Flat):
    """``level`` west of ``x = edge``, ``level + step`` east of it."""

    def __init__(self, level, edge, step):
        super().__init__(level)
        self.edge, self.step = edge, step

    def z(self, x, y):
        return self.level + (self.step if x > self.edge else 0.0)


def test_d2_a_dem_that_moved_where_nothing_was_asked_still_hits(tmp_path):
    root, dump, mod = _world(tmp_path)
    assert _stage(root, dump, mod, _Flat(100.0))[0] == "MISS"
    # the anchor stands at x = 10: an inset arriving east of x = 500 is not its ground
    assert _stage(root, dump, mod, _Step(100.0, 500.0, 9.0))[0] == "HIT"
    assert _stage(root, dump, mod, _Step(100.0, 5.0, 9.0))[0] == "MISS"


class _Raster:
    """A DEM with both question forms and a hole (NaN) west of x = 0."""

    def __init__(self, tilt: float) -> None:
        self.tilt = tilt
        self.extra = "the DEM's own attribute"

    def z_many(self, xs, ys):
        xs = np.asarray(xs, dtype=float)
        return np.where(xs < 0.0, np.nan, 50.0 + self.tilt * xs + 0.25 * np.asarray(ys))

    def z(self, x, y):
        return float(self.z_many(np.array([x]), np.array([y]))[0])


def test_d3_the_witness_answers_as_the_dem_and_records_every_question():
    dem = _Raster(0.1)
    w = DW.DemWitness(dem)
    assert w.z(3.0, 4.0) == dem.z(3.0, 4.0) and np.isnan(w.z(-1.0, 0.0))
    assert np.array_equal(w.z_many([1.0, 2.0], [0.0, 8.0]), dem.z_many([1.0, 2.0], [0.0, 8.0]))
    assert w.extra == dem.extra
    rec = w.record()
    assert rec["xy"].tolist() == [[3.0, 4.0], [-1.0, 0.0], [1.0, 0.0], [2.0, 8.0]]
    assert rec["z"].shape == (4,) and np.isnan(rec["z"][1])
    assert DW.holds(dem, rec) and DW.holds(_Raster(0.1), rec)
    assert not DW.holds(_Raster(0.1000001), rec)             # one bit of ground
    assert not DW.holds(None, rec) and not DW.holds(dem, {"xy": rec["xy"]})
    filled = _Raster(0.1)
    filled.z_many = lambda xs, ys: 50.0 + 0.1 * np.asarray(xs) + 0.25 * np.asarray(ys)
    assert not DW.holds(filled, rec)                         # the hole was filled
    # a reading that asked nothing, or recorded none, holds on any ground
    assert DW.holds(None, None) and DW.holds(None, DW.DemWitness(dem).record())
    # a DEM with the scalar form only is asked the way the reading asked
    assert DW.holds(_Step(51.0, 1e9, 0.0), {"xy": np.array([[1.0, 2.0]]), "z": np.array([51.0])})


def test_d4_a_rewrite_on_a_hit_keeps_the_ground_record(tmp_path):
    """``pack_stage`` writes again on a HIT whose clusters it re-derived;
    that write takes no new reading and must not drop the ground."""
    root, dump, mod = _world(tmp_path)
    assert _stage(root, dump, mod, _Flat(100.0))[0] == "MISS"
    a = _airport(root, _Flat(100.0))
    fp = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    path = PC.cache_path(a, mod, dump)
    hit = PC.read(path, fp)
    assert hit is not None and PC.write(path, fp, hit)
    assert _stage(root, dump, mod, _Flat(100.0))[0] == "HIT"
    assert _stage(root, dump, mod, _Flat(107.0))[0] == "MISS"


def test_d5_the_extension_and_the_sidecar_digest_follow_the_ground(tmp_path, monkeypatch):
    from test_v2partextend import _ext_world, _file_partition
    from auto_patch_v2.airport import extension_cache as EC
    w = _ext_world(tmp_path, monkeypatch)
    _file_partition(w)
    w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"}, keep=True)
    w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"}, keep=True)
    assert len(w.calls) == 1                                 # HIT on the same reading
    # the SAME pack re-read on ground 7 m higher: one base placement's anchor_z
    r0 = w.part.geom.members.recipes[0]
    lifted = type(r0.obj)(**{**vars(r0.obj), "anchor_z": r0.obj.anchor_z + 7.0})
    reread = dc.replace(w.part, geom=dc.replace(
        w.part.geom, members=w.PP.MemberGeometries([dc.replace(r0, obj=lifted)])))
    assert EC.base_digest(reread) != EC.base_digest(w.part)  # rebake_screen's partition_digest
    w.PP.extend_partition(reread, w.air, None, w.law, {"plate.obj"}, keep=True)
    assert len(w.calls) == 2                                 # the old extension is not joined


def test_d6_the_reading_asks_the_dem_through_z_alone_and_pack_stage_hands_the_witness():
    """The witness records ``z`` / ``z_many``; a module of the cached
    reading that asked the DEM anything else would read ground the cache
    file cannot vouch for."""
    asked: dict[str, set[str]] = {}
    for mod in PCODE.CODE_MODULES:
        path = importlib.import_module(mod).__file__
        for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "dem"):
                asked.setdefault(node.attr, set()).add(mod)
    assert set(asked) <= {"z", "z_many"}, asked
    PB = importlib.import_module("auto_patch_v2.pipeline.build")
    src = inspect.getsource(PB.pack_stage)
    assert "_read_objects(\n" in src and "ground_witness(_fp, airport.dem)" in src
