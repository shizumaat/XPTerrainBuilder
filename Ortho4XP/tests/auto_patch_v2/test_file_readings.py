"""#2176 census recommendations 1 and 2 (lane ``lfilecache``) — THE PER-FILE
READINGS KEPT ACROSS BUILDS (``airport/file_readings``) and the parts'
outlines read once per file in its own frame (``airport/part_outline``).

* the KEY is honest: every module a reader RUNS is in its kind's code key
  (``file_readings_code.READER_MODULES``, traced under a profiler) and
  every law value it READS is under its kind's law paths
  (``file_readings.KINDS``, recorded by ``law.witness.LawRecorder``);
* the STORE keeps a reading per file content, misses on a new law value,
  new code or new bytes, writes atomically and only when allowed, and a
  pickled store is off;
* a WARM store is the cold reading: the partition read through a store a
  previous build filled equals the one read without it, and sends no
  resource to the work pool;
* a part's own-frame outline PLACED is the rigid image of its vertices.
"""
from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("osgeo")

from auto_patch_v2.airport import contact as C  # noqa: E402
from auto_patch_v2.airport import deck_signature as D  # noqa: E402
from auto_patch_v2.airport import file_readings as FR  # noqa: E402
from auto_patch_v2.airport import file_readings_code as FRC  # noqa: E402
from auto_patch_v2.airport import obj8 as O  # noqa: E402
from auto_patch_v2.airport import pack_partition as PP  # noqa: E402
from auto_patch_v2.airport import pack_work as W  # noqa: E402
from auto_patch_v2.airport import part_readings as PR  # noqa: E402
from auto_patch_v2.airport import skirt as S  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.law.witness import LawRecorder  # noqa: E402

from test_parpack import _digest, world  # noqa: E402,F401  (the synthetic pack)
from test_terrain_model import _hill, _write as _write_hill  # noqa: E402

LAW = Law.for_airport("")
THICK = LAW.tables.structures.basin.min_solid_thickness_m
SRC = str(Path(__file__).resolve().parents[2] / "src") + os.sep


def _readers(path: str, law) -> dict:
    """Each kind's reader on ``path``, each on a fresh cache."""
    def cache():
        return O.ResourceCache(THICK)
    return {
        "skirt": lambda: S.below_zero_reading(cache(), path, law, settle_early=False),
        "base": lambda: cache().base_profile(path, law),
        "deck": lambda: D.elevated_deck(cache(), path, law),
        "terrain_shape": lambda: TM._shape(path),
        "part": lambda: C.member_attrs((_placed(path), cache().geometry(path),
                                        list(enumerate(cache().components(path)))),
                                       False, False, 1.0, 4, 5.0, 12),
    }


def _placed(path: str):
    return O.PlacedObject(id="dsf:0", path="x.obj", resolved=path, xy=(12.5, -7.25),
                          heading_deg=33.0, agl_m=0.0, kind="OBJECT", anchor_z=100.0,
                          below_grade=None, plan_bbox=None, solid_min_z=None,
                          solid_min_depth_m=None, hard_deck=None, deck_top_z=None)


def _ran(fn) -> set[str]:
    """The ``auto_patch_v2`` modules whose functions ``fn`` runs."""
    seen: set[str] = set()

    def prof(frame, event, _arg):
        if event == "call":
            f = frame.f_code.co_filename
            if f.startswith(SRC) and f.endswith(".py"):
                seen.add(f[len(SRC):-3].replace(os.sep, ".").replace(".__init__", ""))
    sys.setprofile(prof)
    try:
        fn()
    finally:
        sys.setprofile(None)
    # the law's own code reads law values, which the law key names
    return {m for m in seen if m.startswith("auto_patch_v2.")
            and not m.startswith(("auto_patch_v2.law", "auto_patch_v2.model"))}


@pytest.fixture(scope="module")
def files(world, tmp_path_factory):                       # noqa: F811
    hill = _write_hill(tmp_path_factory.mktemp("hill"), "hill.obj", _hill)
    return [o.resolved for o in world.objs if O.ResourceCache(THICK).geometry(o.resolved)
            is not None] + [hill]


def test_every_module_a_reader_runs_is_in_its_code_key(files):
    for path in files:
        for kind, fn in _readers(path, LAW).items():
            fn()                                      # imports settle first
            missing = _ran(fn) - set(FRC.READER_MODULES[kind])
            assert not missing, (f"{kind} ran {sorted(missing)} on {Path(path).name}: "
                                 "add them to file_readings_code.READER_MODULES")


def test_every_law_value_a_reader_reads_is_in_its_law_key(files):
    for path in files:
        for kind in FR.KINDS:
            rec = LawRecorder(LAW)
            _readers(path, rec.law())[kind]()
            keyed = FR.KINDS[kind]
            loose = [p for p in rec.record()
                     if not any(p == k or p.startswith(k + ".") for k in keyed)]
            assert not loose, f"{kind} read {loose}: add them to file_readings.KINDS"


def test_the_reader_lists_name_real_modules_and_digest():
    got = FRC.freeze_digests(str(Path(SRC)))
    assert set(got) == set(FR.KINDS) and all(got.values())
    assert FRC.runtime_digests() == got


# ── the store ────────────────────────────────────────────────────────────

def _reading(path):
    return S.reading(O.ResourceCache(THICK), path, LAW)


def test_a_kept_reading_is_served_to_the_next_build(world, tmp_path):   # noqa: F811
    path = world.objs[0].resolved
    a = FR.FileReadings(str(tmp_path), LAW)
    assert a.get("skirt", path) is FR.MISSING
    a.put("skirt", path, _reading(path))
    assert a.flush() == 1 and (tmp_path / "o4_v2_file_skirt.cache").is_file()
    b = FR.FileReadings(str(tmp_path), LAW)
    assert b.get("skirt", path) == _reading(path) and b.hits == {"skirt": 1}
    assert b.has("skirt", path) and not b.has("base", path)
    assert not list(tmp_path.glob("*.tmp*"))


def test_a_new_law_value_new_code_or_new_bytes_misses(world, tmp_path):  # noqa: F811
    import dataclasses as dc
    path = world.objs[1].resolved
    a = FR.FileReadings(str(tmp_path), LAW)
    a.put("skirt", path, _reading(path))
    a.flush()
    st = LAW.tables.structures
    law2 = dc.replace(LAW, tables=dc.replace(LAW.tables, structures=dc.replace(
        st, skirt=dc.replace(st.skirt, min_depth_m=st.skirt.min_depth_m + 0.5))))
    assert FR.FileReadings(str(tmp_path), law2).get("skirt", path) is FR.MISSING
    # a law value the kind does not read keeps the hit
    law3 = dc.replace(LAW, tables=dc.replace(LAW.tables, structures=dc.replace(
        st, bridge=dc.replace(st.bridge, deck_min_area_m2=st.bridge.deck_min_area_m2 + 1))))
    assert FR.FileReadings(str(tmp_path), law3).get("skirt", path) is not FR.MISSING
    code = {**FRC.runtime_digests(), "skirt": "0" * 64}
    assert FR.FileReadings(str(tmp_path), LAW, code=code).get("skirt", path) is FR.MISSING
    body = Path(path).read_bytes()
    try:
        Path(path).write_bytes(body + b"\n# edited\n")
        assert FR.FileReadings(str(tmp_path), LAW).get("skirt", path) is FR.MISSING
    finally:
        Path(path).write_bytes(body)


def test_a_store_may_be_forbidden_to_write_and_is_off_once_pickled(world, tmp_path):  # noqa: F811
    path = world.objs[0].resolved
    a = FR.FileReadings(str(tmp_path), LAW, write=False)
    a.put("skirt", path, _reading(path))
    assert a.flush() == 0 and not list(tmp_path.iterdir())
    b = pickle.loads(pickle.dumps(FR.FileReadings(str(tmp_path), LAW)))
    assert b.folder is None and b.get("skirt", path) is FR.MISSING and b.flush() == 0
    off = FR.FileReadings(None, LAW)
    off.put("skirt", path, _reading(path))
    assert off.get("skirt", path) is FR.MISSING and "OFF" in off.line()


def test_a_corrupt_file_is_a_miss_and_old_keys_are_bounded(world, tmp_path):   # noqa: F811
    path = world.objs[0].resolved
    (tmp_path / "o4_v2_file_skirt.cache").write_bytes(b"not a pickle")
    assert FR.FileReadings(str(tmp_path), LAW).get("skirt", path) is FR.MISSING
    for k in range(FR.SLOTS_MAX + 2):
        code = {**FRC.runtime_digests(), "skirt": f"{k:064x}"}
        s = FR.FileReadings(str(tmp_path), LAW, code=code)
        s.put("skirt", path, _reading(path))
        assert s.flush() == 1
    assert len(s._read_file("skirt")) == FR.SLOTS_MAX
    assert FR.FileReadings(str(tmp_path), LAW, code=code).get("skirt", path) \
        is not FR.MISSING                               # the newest key stands


# ── the partition, cold and warm ──────────────────────────────────────────

def _partition(world, folder, workers):                      # noqa: F811
    cache = O.ResourceCache(THICK)
    cache.files = FR.FileReadings(folder, LAW)
    asked: list[str] = []
    with W.open_pool(LAW, cache, workers=workers, out=lambda s: None) as pool:
        mapped = pool.try_map

        def try_map(fn, items, **kw):
            asked.append(kw.get("what", ""))
            return mapped(fn, items, **kw)
        pool.try_map = try_map
        part = PP.partition_pack(world.air, world.objs, cache, LAW, pool=pool)
    cache.files.flush()
    return part, cache, asked


@pytest.mark.parametrize("workers", [1, 2])
def test_a_warm_store_reads_the_cold_partition(world, tmp_path, workers):  # noqa: F811
    plain = O.ResourceCache(THICK)
    want = _digest(PP.partition_pack(world.air, world.objs, plain, LAW), plain)
    folder = str(tmp_path / f"w{workers}")
    part, cache, _done = _partition(world, folder, workers)
    assert _digest(part, cache) == want
    assert {p.name for p in Path(folder).iterdir()} >= {
        "o4_v2_file_base.cache", "o4_v2_file_deck.cache", "o4_v2_file_skirt.cache",
        "o4_v2_file_part.cache"}
    part, cache, done = _partition(world, folder, workers)
    assert _digest(part, cache) == want
    # no resource reading and no part reading is left for a worker (the
    # narrow pass still pools)
    assert not [w for w in done if "resource readings" in w or "outlines" in w]
    assert cache.files.hits.get("base") and cache.files.hits.get("part")
    assert not cache.files.misses.get("part")


# ── the part readings, by placement ───────────────────────────────────────

def test_a_kept_part_reading_is_the_placing_bit_for_bit(world):           # noqa: F811
    """Served from the book, the parts are the parts the placing derives —
    and a placement that moved (another heading) is not served."""
    import dataclasses as dc
    cache = O.ResourceCache(THICK)
    members = [(o, cache.geometry(o.resolved), list(enumerate(cache.components(o.resolved))))
               for o in world.objs[:6]]
    lines, scat, params = {3}, {2}, (1.0, 4, 5.0, 12)
    want = C.placed_parts(members, *params[:2], lines, *params[2:], scat)
    book = PR.PartBook()
    held = book.held(members, lines, scat, params)
    assert held == [None] * len(members)
    assert book.take(members, lines, scat, params, want, held) == len(members)
    held = book.held(members, lines, scat, params)
    assert all(h is not None for h in held)
    got = C.placed_parts(members, *params[:2], lines, *params[2:], scat, attrs=held)
    for a, b in zip(got, want):
        assert a.feet.tobytes() == b.feet.tobytes() and a.solid_h == b.solid_h
        assert len(a.rings) == len(b.rings) and all(
            np.asarray(x).tobytes() == np.asarray(y).tobytes()
            for x, y in zip(a.rings, b.rings))
    moved = [(dc.replace(o, heading_deg=o.heading_deg + 1.0), g, c) for o, g, c in members]
    assert book.held(moved, lines, scat, params) == [None] * len(members)
    assert book.held(members, lines, scat, (1.0, 5, 5.0, 12)) == [None] * len(members)


def test_the_freeze_writes_the_table_a_frozen_engine_reads(tmp_path):
    import O4_Code_Closure as CC
    path = FRC.write_freeze_digest(str(Path(SRC)), str(tmp_path))
    assert CC.read_digest_table(str(tmp_path), FRC.DIGEST_FILENAME) == \
        FRC.freeze_digests(str(Path(SRC)))
    assert os.path.basename(path) == FRC.DIGEST_FILENAME
    for spec in ("Ortho4XP.spec", "Ortho4XP_Qt.spec"):
        text = (Path(SRC).parent / spec).read_text(encoding="utf-8")
        assert '"file_readings_code.py")\n)["write_freeze_digest"]' in text, spec
