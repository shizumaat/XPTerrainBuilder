"""issue #843 step 4 (B3-11; spec ``v2-stage-cache-spec.md`` §8 T4/T5) — THE
FRONT-HALF STAGE CACHE: a record is served only for its key and its
witnesses, and is refused (never repaired) otherwise.

Synthetic throughout (no corpus): a toy airport, a toy DEM, the shipped law
tables, and a stage function that reads the law, the DEM and a file.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import pickle
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest
from auto_patch_v2.airport import dem_record as DR
from auto_patch_v2.airport import file_witness as FW
from auto_patch_v2.airport import stage_cache as SC
from auto_patch_v2.law import Law
from auto_patch_v2.law import witness as LW
from auto_patch_v2.pipeline import front_cache as FC

ROOT = Path(__file__).resolve().parents[2]


class ToyDem:
    """A DEM: a plane, plus the non-sample questions the front half asks."""

    def __init__(self, tilt: float = 0.01, posting: float = 30.0) -> None:
        self.tilt, self.posting = tilt, posting
        self.provenance = {"frame": "toy"}

    def z(self, x: float, y: float) -> float:
        return 100.0 + self.tilt * x

    def z_many(self, xs, ys):
        return 100.0 + self.tilt * np.asarray(xs, dtype=np.float64)

    def posting_m(self) -> float:
        return self.posting


@_dc.dataclass(frozen=True)
class ToyAirport:
    icao: str
    dem: object
    pack: object = None
    dsf_objects: tuple = ()
    partition: object = None
    runways: tuple = (("09", 1.0),)


def _law() -> Law:
    return Law.load()


def _edit(law: Law, section: str, field: str, value) -> Law:
    """``law`` with ``tables.<section>.<field>`` replaced."""
    sec = getattr(law.tables, section)
    return _dc.replace(law, tables=_dc.replace(law.tables, **{
        section: _dc.replace(sec, **{field: value})}))


def _cache(tmp_path, airport, law, enabled=True) -> FC.FrontCache:
    fc = FC.FrontCache("TOYS", airport, law, enabled=enabled,
                       mod_cache_root=str(tmp_path / "mod"), pack=())
    return fc


def _stage(read_file: Path | None = None, calls: list | None = None):
    """A stage reading one law value (``tables.common.pavement_max_grade``),
    the DEM at two points and its posting, and optionally a file."""
    def fn(law, airport):
        if calls is not None:
            calls.append(1)
        v = law.tables.common.pavement_max_grade
        z = airport.dem.z_many(np.array([0.0, 50.0]), np.array([0.0, 0.0]))
        text = read_file.read_text(encoding="utf-8") if read_file is not None else ""
        return {"law": v, "z": z.tolist(), "post": airport.dem.posting_m(), "text": text}
    return fn


def _run(tmp_path, law, dem, *, inputs=None, calls=None, read_file=None, enabled=True):
    ap = ToyAirport("TOYS", dem)
    fc = _cache(tmp_path, ap, law, enabled=enabled)
    ap = fc.airport(ap)
    fc.window(True)
    fn = _stage(read_file, calls)
    out = fc.run("classify", dict(inputs or {"airport": fc.airport_digest(ap)}),
                 lambda lw: fn(lw, ap))
    rep = fc.finish()
    return out, rep["stages"].get("classify", {}), fc


# ── T4: miss → write → hit ──────────────────────────────────────────────
def test_t4_a_miss_writes_and_the_next_build_is_served_the_same_record(tmp_path):
    law, calls = _law(), []
    a, ra, fa = _run(tmp_path, law, ToyDem(), calls=calls)
    b, rb, fb = _run(tmp_path, law, ToyDem(), calls=calls)
    assert ra["state"] == "miss" and ra["written_bytes"] > 0
    assert rb["state"] == "hit", rb
    assert calls == [1], "a hit does not run the stage"
    assert a == b
    assert fa.output_digest("classify") == fb.output_digest("classify")
    assert SC.digest_of(a) == fa.output_digest("classify")


def test_t4_a_changed_code_digest_misses(tmp_path, monkeypatch):
    law = _law()
    _run(tmp_path, law, ToyDem())
    real = FC._code.runtime_digests()
    monkeypatch.setattr(FC._code, "runtime_digests",
                        lambda: {**real, "classify": "0" * 64})
    _o, r, _f = _run(tmp_path, law, ToyDem())
    assert r["state"] == "miss"


def test_t4_a_changed_input_digest_misses(tmp_path):
    law = _law()
    _run(tmp_path, law, ToyDem(), inputs={"airport": "a"})
    _o, r, _f = _run(tmp_path, law, ToyDem(), inputs={"airport": "b"})
    assert r["state"] == "miss"


def test_t4_a_moved_dem_sample_refuses_by_witness(tmp_path):
    law = _law()
    _run(tmp_path, law, ToyDem(tilt=0.01), inputs={"airport": "a"})
    out, r, _f = _run(tmp_path, law, ToyDem(tilt=0.02), inputs={"airport": "a"})
    assert r["state"] == "refused: dem:samples"
    assert out["z"][1] == pytest.approx(101.0), "the stage ran on today's DEM"


def test_t4_a_changed_dem_answer_to_a_method_refuses(tmp_path):
    law = _law()
    _run(tmp_path, law, ToyDem(posting=30.0), inputs={"airport": "a"})
    _o, r, _f = _run(tmp_path, law, ToyDem(posting=10.0), inputs={"airport": "a"})
    assert r["state"] == "refused: dem:posting_m"


def test_t4_a_law_row_read_misses_and_a_row_not_read_hits(tmp_path):
    law = _law()
    _run(tmp_path, law, ToyDem(), inputs={"airport": "a"})
    c = law.tables.common
    # its sibling row, which the stage never read
    unread = _edit(law, "common", "road_max_grade", c.road_max_grade + 0.01)
    _o, r, _f = _run(tmp_path, unread, ToyDem(), inputs={"airport": "a"})
    assert r["state"] == "hit", r
    read = _edit(law, "common", "pavement_max_grade", c.pavement_max_grade + 0.01)
    out, r, _f = _run(tmp_path, read, ToyDem(), inputs={"airport": "a"})
    assert r["state"] == "refused: law:tables.common.pavement_max_grade", r
    assert out["law"] == read.tables.common.pavement_max_grade


def test_t4_a_touched_file_the_stage_opened_refuses(tmp_path):
    law, f = _law(), tmp_path / "side.txt"
    f.write_text("one", encoding="utf-8", newline="\n")
    _run(tmp_path, law, ToyDem(), inputs={"airport": "a"}, read_file=f)
    _o, r, _f = _run(tmp_path, law, ToyDem(), inputs={"airport": "a"}, read_file=f)
    assert r["state"] == "hit"
    f.write_text("two!", encoding="utf-8", newline="\n")
    out, r, _f = _run(tmp_path, law, ToyDem(), inputs={"airport": "a"}, read_file=f)
    assert r["state"] == f"refused: file:{f}"
    assert out["text"] == "two!"


def test_t4_the_off_switch_runs_every_stage_and_writes_nothing(tmp_path):
    law, calls = _law(), []
    for _ in range(2):
        _o, r, fc = _run(tmp_path, law, ToyDem(), calls=calls, inputs={"airport": "a"},
                         enabled=False)
        assert r == {} and fc.report["state"] == "bypass: off"
    assert calls == [1, 1]
    assert not (tmp_path / "mod").exists() or not list((tmp_path / "mod").iterdir())


def test_t4_the_off_switch_is_read_in_the_wrapper_and_classified():
    wrapper = (ROOT / "src" / "auto_patch" / "engine_v2.py").read_text(encoding="utf-8")
    assert '"O4_V2_STAGE_CACHE", "1"' in wrapper
    assert "stage_cache=stage_cache_enabled()" in wrapper
    from auto_patch.engine_v2 import stage_cache_enabled
    assert stage_cache_enabled({}) is True
    assert stage_cache_enabled({"O4_V2_STAGE_CACHE": "0"}) is False
    harness = (ROOT / "tools" / "harness" / "build_airport.py").read_text(encoding="utf-8")
    assert "Config(stage_cache=stage_cache_enabled())" in harness
    from auto_patch import provenance_env
    assert "O4_V2_STAGE_CACHE" in provenance_env.RUN_ENVIRONMENT
    from auto_patch_v2.pipeline.build import Config
    assert Config().stage_cache is False, "a direct caller writes no record"


def test_t4_a_newer_cache_version_refuses(tmp_path, monkeypatch):
    law = _law()
    _run(tmp_path, law, ToyDem(), inputs={"airport": "a"})
    monkeypatch.setattr(SC, "CACHE_VERSION", SC.CACHE_VERSION + 1)
    _o, r, _f = _run(tmp_path, law, ToyDem(), inputs={"airport": "a"})
    # the key carries the version, so a newer engine asks another file
    assert r["state"] == "miss"
    old = [p for p in (tmp_path / "mod").glob("o4_stage_TOYS_classify_*.cache")
           if SC.read_header(str(p))["version"] != SC.CACHE_VERSION]
    assert len(old) == 1
    path = old[0]
    head = SC.read_header(str(path))
    with pytest.raises(SC.Refused, match="version"):
        SC.read(str(path), head["key"])


def test_t4_an_altered_payload_is_refused(tmp_path):
    law = _law()
    _run(tmp_path, law, ToyDem(), inputs={"airport": "a"})
    path = next((tmp_path / "mod").glob("o4_stage_TOYS_classify_*.cache"))
    head = SC.read_header(str(path))
    raw = path.read_bytes()
    import struct
    import zlib
    at = len(SC.MAGIC)
    (n,) = struct.unpack("<Q", raw[at:at + 8])
    at += 8 + n
    (m,) = struct.unpack("<Q", raw[at:at + 8])
    at += 8 + m
    path.write_bytes(raw[:at] + zlib.compress(pickle.dumps({"law": 0}), 1))
    _h, _w, load = SC.read(str(path), head["key"])
    with pytest.raises(SC.Refused, match="payload_sha256"):
        load()
    _o, r, _f = _run(tmp_path, law, ToyDem(), inputs={"airport": "a"})
    assert r["state"] == "refused: payload_sha256"


def test_t4_the_sweep_evicts_the_oldest_used_first(tmp_path):
    folder = tmp_path / "root" / "pack"
    paths = []
    for k in range(3):
        p = SC.entry_path(str(folder), "TOYS", "classify", str(k) * 64)
        assert SC.write(p, {"key": k}, {}, b"x" * 1000) > 0
        SC.touch(p, when=100.0 + k)
        paths.append(p)
    SC.touch(paths[0], when=500.0)                 # the first is used last
    size = os.path.getsize(paths[0])
    gone = SC.sweep(str(tmp_path / "root"), cap=2 * size)
    assert gone == [paths[1]]
    assert os.path.isfile(paths[0]) and os.path.isfile(paths[2])


# ── the witnesses themselves ────────────────────────────────────────────
def test_the_law_proxy_reads_as_the_law_and_records_paths():
    law = _law()
    rec = LW.LawRecorder(law)
    lw = rec.law()
    assert isinstance(lw, Law) and _dc.is_dataclass(lw)
    rs = lw.ruleset
    assert isinstance(rs, type(law.ruleset)) and rs == law.ruleset
    assert lw.tables.common.road_max_grade == law.tables.common.road_max_grade
    replaced = _dc.replace(lw.tables.emit, chords=law.tables.emit.chords)
    assert type(replaced) is type(law.tables.emit)
    got = rec.record()
    assert "ruleset_key" in got
    assert f"tables.rulesets.{law.ruleset_key}" in got, "the whole ruleset was compared"
    assert "tables.common.road_max_grade" in got
    assert "tables.common" not in got, "a leaf read is not the whole section"
    assert not any(k.startswith("tables.emit") for k in got), (
        "replace copied the sections' proxies; nothing in them was read yet")
    assert replaced.identity == law.tables.emit.identity
    assert "tables.emit.identity" in rec.record(), "the copy still records"
    assert LW.holds(law, got) is None
    assert LW.holds(_edit(law, "common", "road_max_grade", 1.0), got) == \
        "law:tables.common.road_max_grade"
    assert pickle.loads(pickle.dumps(lw)) == law, "pickles as the real law"
    assert type(pickle.loads(pickle.dumps(lw.tables.emit))) is type(law.tables.emit)
    assert set(rec.record()) == {""}, "pickling the root read the whole law"


def test_the_dem_recorder_answers_as_the_dem_and_records_every_question():
    dem = ToyDem()
    rec = DR.DemRecorder(dem)
    assert isinstance(rec, ToyDem)
    rec.recording(True)
    rec.z(1.0, 2.0)
    rec.z_many(np.array([3.0]), np.array([4.0]))
    assert rec.posting_m() == 30.0
    _ = rec.provenance
    rec.recording(False)
    rec.z(9.0, 9.0)                                    # outside the window
    got = rec.record()
    assert got["samples"]["xy"].tolist() == [[1.0, 2.0], [3.0, 4.0]]
    assert [c[0] for c in got["calls"]] == ["posting_m"]
    assert set(got["attrs"]) == {"provenance"}
    assert DR.holds(ToyDem(), got) is None
    assert DR.holds(ToyDem(tilt=0.5), got) == "dem:samples"
    assert DR.holds(ToyDem(posting=1.0), got) == "dem:posting_m"
    assert pickle.loads(pickle.dumps(rec)).__class__ is ToyDem


def test_the_file_recorder_sees_reads_not_writes_nor_code(tmp_path):
    rec = FW.FileRecorder()
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("a", encoding="utf-8", newline="\n")
    rec.recording(True)
    a.read_text(encoding="utf-8")
    b.write_text("b", encoding="utf-8", newline="\n")
    (tmp_path / "o4_stage_X.cache").write_bytes(b"")
    (tmp_path / "o4_stage_X.cache").read_bytes()
    rec.recording(False)
    a.read_text(encoding="utf-8")
    got = rec.record()
    assert list(got) == [str(a)]
    assert FW.holds(got) is None
    os.utime(a, ns=(1, 1))
    assert FW.holds(got) == f"file:{a}"


# ── T5: digest stability across processes ───────────────────────────────
_T5 = textwrap.dedent("""
    import dataclasses as dc, sys
    sys.path.insert(0, sys.argv[1])
    from auto_patch_v2.airport import stage_cache as SC
    @dc.dataclass(frozen=True)
    class P:
        a: tuple
        b: dict
        c: frozenset
    built = {}
    for k in sys.argv[2].split(","):
        built[k] = len(k)
    p = P(a=(1.5, "x"), b=built, c=frozenset({(1, 2), (3, 4), (10, 7)}))
    q = P(a=(), b={}, c=frozenset({"apron", "runway", "taxiway", "stand"}))
    print(SC.digest_of(p), SC.canonical_digest(q))
""")


def test_t5_digest_of_is_stable_across_processes():
    def run(order: str, seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        return subprocess.run([sys.executable, "-c", _T5, str(ROOT / "src"), order],
                              capture_output=True, text=True, check=True,
                              env=env).stdout.strip()
    one, two = run("k1,k2,k3", "1").split(), run("k1,k2,k3", "2").split()
    assert one[0] == two[0], "the same product digests the same in two processes"
    assert one[1] == two[1], "a set of strings, sorted, under two hash seeds"
    assert run("k3,k2,k1", "1").split()[0] != one[0], "dict order is part of the product"


# ── T5b: THE AIRPORT INPUT digests the same in every process (issue #844) ──
#: A partition with no reading digest (every ``--capture``, a pack with no
#: fingerprint) is pickled whole, and its ``frozenset[str]`` fields came
#: out in the process's hash-seed order: three HECA captures of one tree
#: each named a new airport and missed every front-half stage.
_T5B = textwrap.dedent("""
    import dataclasses as dc, sys, tempfile
    sys.path.insert(0, sys.argv[1])
    from auto_patch_v2.airport.pack_partition import PackPartition
    from auto_patch_v2.law import Law
    from auto_patch_v2.pipeline import front_cache as FC
    class Dem:
        provenance = {"frame": "toy"}
        def z(self, x, y): return 100.0
        def posting_m(self): return 30.0
    @dc.dataclass(frozen=True)
    class Ap:
        icao: str
        dem: object
        pack: object = None
        dsf_objects: tuple = ()
        partition: object = None
    names = frozenset(f"objects/{sys.argv[2]}{i}.obj" for i in range(40))
    part = PackPartition(icao="TOYS", pack_name="p", pack_root="/r", units=(),
                         skipped=(), counts={}, multi_anchor=names)
    ap = Ap("TOYS", Dem(), partition=part)
    fc = FC.FrontCache("TOYS", ap, Law.for_airport("TOYS"), enabled=True,
                       mod_cache_root=tempfile.mkdtemp())
    assert fc.partition is None          # no fingerprint: the field is pickled
    print(fc.airport_digest(fc.airport(ap)))
""")


def test_t5b_the_airport_digest_is_the_same_in_two_processes(tmp_path):
    def run(stem: str, seed: str, where: Path) -> str:
        where.mkdir(exist_ok=True)
        env = {**os.environ, "PYTHONHASHSEED": seed, "TMPDIR": str(where)}
        return subprocess.run([sys.executable, "-c", _T5B, str(ROOT / "src"), stem],
                              capture_output=True, text=True, check=True, env=env,
                              cwd=str(where)).stdout.strip()
    one = run("o", "1", tmp_path / "a")
    assert one and one == run("o", "2", tmp_path / "b"), \
        "one airport, two hash seeds, two temp dirs: one digest"
    assert run("q", "1", tmp_path / "a") != one, "a changed placement name moves it"
