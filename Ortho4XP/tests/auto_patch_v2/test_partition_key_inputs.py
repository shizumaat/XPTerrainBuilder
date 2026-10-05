"""issue #382 — THE PARTITION CACHE KEY COVERS WHAT THE READING READS.

The cached pack reading holds ground the DEM gave it (``anchor_z`` on every
placed object and everything built on it), content of resources resolved
outside the pack, and bridge ways from OSM; the key named none of them.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from auto_patch_v2.airport import obj8
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


@pytest.mark.xfail(strict=True, reason="#382: the key names no DEM — attribution twin")
def test_d0_a_changed_dem_is_served_the_old_ground(tmp_path):
    """THE INTERVENTION.  Same pack, same dump; the DEM moves 7 m."""
    root, dump, mod = _world(tmp_path)
    a = _airport(root, _Flat(100.0))
    fp_a = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    path = PC.cache_path(a, mod, dump)
    assert PC.write(path, fp_a, _read(a.dem.z))
    b = _airport(root, _Flat(107.0))
    fp_b = PC.fingerprint(b, LAW, dump_path=dump, radius_deg=0.05)
    served = PC.read(path, fp_b)
    fresh = _read(b.dem.z)
    assert fresh[0].anchor_z == 107.0
    assert served is None or served[0].anchor_z == fresh[0].anchor_z, \
        f"HIT carrying anchor_z {served[0].anchor_z} on a DEM that reads {fresh[0].anchor_z}"
