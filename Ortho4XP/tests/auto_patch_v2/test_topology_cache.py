"""issue #362 (lane perfC362) — THE CONNECTOR TOPOLOGY, CACHED beside the
partition (``airport/topology_cache``).

``solid_connectors`` runs on every build because its verdict reads the DEM;
its cost is the DEM-free topology before it.  T1 the kept topology gives
the SAME verdicts as the computed one, on the ground of the day.  T2 it is
written ONLY when the partition cache is — a stage that never writes the
partition (a HIT, ``write_cache=False``) writes nothing.  T3 every changed
input MISSES: a part, a contact, a law number, the partition fingerprint
(pack content, partition code).
"""
from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from auto_patch_v2.airport import footprint_connector as FC
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import partition_cache as PC
from auto_patch_v2.airport import topology_cache as TC
from auto_patch_v2.law import Law

LAW = Law.for_airport("")


def _lat(m: float) -> float:
    return 41.0 + m / 111_132.0


def _part(pid, la0, la1, height, lo0=-3.0, lo1=-2.9990):
    box = (_lat(la0), lo0, _lat(la1), lo1)
    lat, lon = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
    return NS(pid=pid, box=box, line=False, scatter=False, lat=lat, lon=lon,
              base_y=0.0, feet=((lat, lon, 0.0),), comp=0, area_m2=1.0,
              height_m=float(height), rings=())


def _member(resource, parts):
    return NS(id=resource, resource=resource, parts=tuple(parts), deck_datum_z=None,
              deck_ring=None, deck_shade_ring=None, deck_kind="", elevated_deck=False,
              heading_deg=0.0)


def _plan(root: str):
    """Two walled buildings joined by a 300 m walled strip (the unit-platform
    twin's ``strip``), as VALUES: a ``SimpleNamespace`` reprs by content."""
    a = _member("objects/a.obj", [_part(1, 0, 100, 12.0)])
    b = _member("objects/b.obj", [_part(2, 400, 500, 12.0)])
    c = _member("objects/link.obj", [_part(10, 100, 400, 4.0, -2.99960, -2.99940)])
    return NS(units=(NS(id="unit:0", anchor=(41.0, -3.0), members=(a, b, c)),),
              contacts=(), abutments=(), connectors=None, pack_root=root, icao="ZZZZ")


def _ground(step: float):
    return lambda la, lo: 100.0 + (step if la > _lat(250) else 0.0)


@pytest.fixture()
def world(tmp_path, monkeypatch):
    root = tmp_path / "pack"
    (root / "Earth nav data").mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text("I\n", encoding="utf-8", newline="")
    (root / "a.obj").write_text("A\n800\nOBJ\n", encoding="utf-8", newline="")
    dump = tmp_path / "+41-003.dsf.0b0b0b0b.text"
    dump.write_text("OBJECT_DEF a.obj\n", encoding="utf-8", newline="")
    air = NS(icao="ZZZZ", dsf_objects=(), frame=NS(crs="EPSG:32630", lat0=41.0, lon0=-3.0),
             pack=NS(name="pack", apt_dat_path=str(root / "Earth nav data" / "apt.dat"),
                     borrowed_apt_dat_path="", borrowed_block_sha256=""))
    calls = []
    real = FU.plan_units_and_connectors
    monkeypatch.setattr(FU, "plan_units_and_connectors",
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    for name in ("_TAKEN", "_FILED", "_HELD"):
        monkeypatch.setattr(PC, name, {})
    w = NS(root=root, dump=str(dump), air=air, calls=calls, mp=monkeypatch,
           path=str(tmp_path / "mod" / "pack" / "o4_v2_partition_+41-003_ZZZZ.cache"))
    w.fp = lambda: PC.fingerprint(air, LAW, dump_path=w.dump, radius_deg=0.05)
    return w


def _solve(plan, step=2.5, span_m=200.0):
    FC._VERDICT_MEMO.clear()                 # the in-process identity memo
    return FC.solid_connectors(plan, _ground(step), touch_m=0.5, span_m=span_m,
                               visual_m=0.5, chain_min_height_m=2.5,
                               gap_max_m=20.0, step_max_m=15.0 * 0.33)


def _files(w):
    d = Path(w.path).parent
    return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


def test_t1_t2_kept_with_the_partition_and_the_same_verdicts(world):
    w = world
    plan = _plan(str(w.root))
    fp = w.fp()
    want = _solve(plan)
    assert [v.solid for v in want] == [True] and len(w.calls) == 1
    # nothing is written until the PARTITION is: computed again, held again
    assert _solve(plan) == want and len(w.calls) == 2 and _files(w) == []
    assert PC.write(w.path, fp, "the load reading")
    assert _files(w) == ["o4_v2_partition_+41-003_ZZZZ.cache",
                         "o4_v2_partition_+41-003_ZZZZ.cache" + TC.SUFFIX]
    # the same process, and a fresh one that HITS the partition, revive it
    assert _solve(plan) == want and len(w.calls) == 2
    for name in ("_TAKEN", "_FILED", "_HELD"):
        w.mp.setattr(PC, name, {})
    assert PC.read(w.path, w.fp()) == "the load reading"
    assert _solve(_plan(str(w.root))) == want and len(w.calls) == 2
    # THE VERDICT IS STILL THE GROUND'S: another DEM, the kept topology
    cut = _solve(plan, step=29.0)
    assert [v.solid for v in cut] == [False] and len(w.calls) == 2
    w.mp.setattr(TC, "load", lambda plan, key: None)
    assert _solve(plan, step=29.0) == cut and len(w.calls) == 3


def test_t2_a_stage_that_never_writes_the_partition_writes_no_topology(world):
    w = world
    assert PC.write(w.path, w.fp(), "the load reading")        # an earlier build
    assert _files(w) == ["o4_v2_partition_+41-003_ZZZZ.cache"]   # nothing was held
    for name in ("_TAKEN", "_FILED", "_HELD"):
        w.mp.setattr(PC, name, {})
    # the dry stage (write_cache=False): fingerprint, HIT, connectors
    assert PC.read(w.path, w.fp()) == "the load reading"
    before = _files(w)
    _solve(_plan(str(w.root)))
    _solve(_plan(str(w.root)))
    assert len(w.calls) == 2 and _files(w) == before
    # and a plan of no fingerprinted pack holds nothing at all
    assert TC.load(_plan("/nowhere"), "k") is None
    assert PC.hold_companion("/nowhere", "ZZZZ", TC.SUFFIX, "k", ()) is False


def test_t3_every_changed_input_misses(world):
    w = world
    plan = _plan(str(w.root))
    fp = w.fp()
    want = _solve(plan)
    assert PC.write(w.path, fp, "the load reading")
    assert _solve(plan) == want and len(w.calls) == 1            # HIT
    # (1) one part's box
    moved = copy.deepcopy(plan)
    b = moved.units[0].members[2].parts[0]
    b.box = (b.box[0], b.box[1], b.box[2] + 1e-7, b.box[3])
    _solve(moved)
    assert len(w.calls) == 2
    # (2) a contact edge, an abutment
    for field in ("contacts", "abutments"):
        other = copy.deepcopy(plan)
        setattr(other, field, ((1, 10),))
        _solve(other)
    assert len(w.calls) == 4
    # (3) a law number
    _solve(plan, span_m=199.0)
    assert len(w.calls) == 5
    assert _solve(plan) == want and len(w.calls) == 5            # still a HIT
    # (4) PACK CONTENT: the fingerprint moves; the old file is not this key's
    (w.root / "a.obj").write_text("A\n800\nOBJ\n# v2\n", encoding="utf-8", newline="")
    fp2 = w.fp()
    assert fp2 != fp
    _solve(plan)
    assert len(w.calls) == 6
    assert PC.write(w.path, fp2, "the load reading, re-read")    # writes the held one
    assert _solve(plan) == want and len(w.calls) == 6
    # (5) PARTITION CODE: the same, through the code digest
    w.mp.setattr(PC, "_CODE_DIGEST", "d" * 64)
    fp3 = w.fp()
    assert fp3 not in (fp, fp2)
    assert PC.write(w.path, fp3, "the load reading, new code")   # nothing held for fp3
    _solve(plan)
    assert len(w.calls) == 7                                     # fp2's file refused
    w.mp.setattr(PC, "_CODE_DIGEST", None)
