"""#843 step 9b — the solve's record and the last stage's records
(``pipeline/solve_record``, ``pipeline/late_records``; spec
``v2-stage-cache-spec.md`` §4b.4, §4b.5, §8 T7/T8/T9 (c)/T10/T12/T13).

Synthetic, no corpus.  THE SOLVE: ``test_backhalf_records``' airport through
the prefix (``prefix.run_prefix``, through the records) and the base solve
three ways — COLD (no cache), the MISS arm, the HIT arm — compared on ``z``
(bits), the report and the map's registries.  THE LAST STAGE:
``test_roads609``'s pad road (the base without it, then the road against
its levels) through ``run_late_stage(records=...)``, the derive a
``Deriver`` on the build's cache.  The closing HECA / CYXY byte identity
is the master's."""
from __future__ import annotations

import array
import dataclasses as dc
import pickle
import subprocess
import sys
import types
import typing as _t
from pathlib import Path

import pytest
from auto_patch_v2.pipeline import capture_state as CS
from auto_patch_v2.pipeline import front_cache as FC
from auto_patch_v2.pipeline import solve_record as SR
from auto_patch_v2.pipeline.late_records import LateRecords, prefix_identity
from auto_patch_v2.pipeline.prefix import Deriver, PackRead
from auto_patch_v2.solve import Options, solve_design
from tests.auto_patch_v2.test_backhalf_records import (
    ICAO,
    _copy,
    _record,
    _rewrite,
    _states,
    _with_code,
    synthetic,
)

ROOT = Path(__file__).resolve().parents[2]
INPUTS = types.SimpleNamespace(road_grade_limit=0.08, lane_width_m=3.5)
PACK = PackRead(None, None, None)
PREFIX = {"planar", "flat_site", "road_profile", "shapes", "constraints.assembly",
          "jetway_strip"}


def _cache(root: Path | None, airport, law, **kw):
    if root is None:
        return None, airport
    fc = FC.FrontCache(ICAO, airport, law, enabled=True, mod_cache_root=str(root), **kw)
    return fc, fc.airport(airport)


def _solve_arm(root: Path | None, *, options: Options | None = None, solve: bool = True,
               **kw) -> dict:
    """The prefix and the base solve as the build runs them; ``solve``
    False stops after the prefix (a build stopped after the assembly)."""
    law, airport, cl = synthetic()
    fc, airport = _cache(root, airport, law, **kw)
    derive = Deriver(airport, law, INPUTS, PACK, cache=fc,
                     common=fc.common_inputs(None, None) if fc else None)
    derive(cl)
    pre = derive.last
    out: dict = {"pre": pre}
    if solve:
        opts = options or Options()

        def run():
            size: dict = {}
            sol, rep = solve_design(pre.pm, pre.cs, law, opts, size_out=size,
                                    strips=pre.strips, hold=pre.hold)
            return sol, rep, size, {}, None
        got = SR.solve_stage(fc, {**pre.keys, "stage_one": "none",
                                  "options": fc.digest(opts) if fc else None},
                             run, cs=pre.cs, n=len(pre.pm.vertices), law=law, options=opts,
                             held=pre.pm.registries.held)
        out.update(got=got, registries=_registries(pre.pm))
    out["rep"] = fc.finish() if fc is not None else {}
    return out


def _registries(pm) -> dict:
    """The map's registries' record (``capture_state.collect``)."""
    return CS.collect(pm.registries)


def _equal(x, y) -> bool:
    """Equal by value (numpy arrays by their elements)."""
    import numpy as np
    if isinstance(x, np.ndarray) or isinstance(y, np.ndarray):
        return bool(np.array_equal(x, y))
    if isinstance(x, dict) and isinstance(y, dict):
        return set(x) == set(y) and all(_equal(x[k], y[k]) for k in x)
    if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
        return len(x) == len(y) and all(_equal(u, v) for u, v in zip(x, y, strict=True))
    return bool(x == y)


def _states_of(arm: dict) -> dict[str, str]:
    return {k.split("@")[0]: v for k, v in _states(arm["rep"]).items()
            if not k.startswith("constraints.gen.")}


def _unclocked(d):
    """``d`` without its clocks (every ``*_s`` key and the ``qp_solves``
    log, whose rows carry seconds, at any depth)."""
    if isinstance(d, dict):
        return {k: _unclocked(v) for k, v in d.items()
                if not str(k).endswith("_s") and k != "qp_solves"}
    if isinstance(d, (list, tuple)):
        return type(d)(_unclocked(v) for v in d)
    if isinstance(d, str):                      # a line that names its seconds
        import re
        return re.sub(r"\d+\.\d+ s\b", "<s>", d)
    return d


def _first_difference(x, y, path: str = "") -> str | None:
    """Where two report trees first differ (``None``: nowhere)."""
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y), key=str):
            d = _first_difference(x.get(k), y.get(k), f"{path}/{k}")
            if d:
                return d
        return None
    if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)) and len(x) == len(y):
        for i, (u, v) in enumerate(zip(x, y, strict=True)):
            d = _first_difference(u, v, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if x == y else f"{path}: {x!r} != {y!r}"


def _same_solve(a: dict, b: dict) -> None:
    sa, sb = a["got"].value, b["got"].value
    assert array.array("d", sa.sol.z).tobytes() == array.array("d", sb.sol.z).tobytes()
    assert sa.sol.status == sb.sol.status and sa.sol.residual == sb.sol.residual
    assert not _first_difference(_unclocked(sa.design.as_dict()), _unclocked(sb.design.as_dict()))
    assert sa.size == sb.size and sa.certificate == sb.certificate
    assert _equal(a["registries"], b["registries"])


@pytest.fixture(scope="module")
def cold():
    return _solve_arm(None)


@pytest.fixture(scope="module")
def warm(tmp_path_factory):
    root = tmp_path_factory.mktemp("warm")
    return root, _solve_arm(root)


# ── T8 / T13: hit == cold; resume after the assembly ────────────────────

def test_t8_the_solve_hit_equals_cold(cold, warm, tmp_path):
    root, miss = warm
    assert _states_of(miss)["solve"] == "miss"
    _same_solve(cold, miss)
    hit = _solve_arm(_copy(root, tmp_path / "c"))
    assert set(_states_of(hit).values()) == {"hit"}
    assert "check_s" in hit["rep"]["stages"]["solve"]
    _same_solve(cold, hit)


def test_t8_solve_only_miss_equals_cold(cold, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")
    _record(root, "solve").unlink()
    got = _solve_arm(root)
    st = _states_of(got)
    assert st.pop("solve") == "miss" and set(st.values()) == {"hit"}
    _same_solve(cold, got)


def test_t13_a_build_stopped_after_the_assembly_resumes_with_the_solve(cold, tmp_path):
    _solve_arm(tmp_path, solve=False)
    got = _solve_arm(tmp_path)
    st = _states_of(got)
    assert st.pop("solve") == "miss"
    assert PREFIX <= set(st) and set(st.values()) == {"hit"}
    _same_solve(cold, got)


# ── T9 (c): the certificate ─────────────────────────────────────────────

def _plant(path: Path, move: _t.Callable[[bytes], bytes]) -> None:
    """Rewrite the record's payload by ``move`` and its header's
    ``payload_sha256`` / ``output_digest`` to match — a planted record
    whose header and payload agree."""
    import hashlib
    new: dict = {}

    def payload(b: bytes) -> bytes:
        new["b"] = move(b)
        return new["b"]
    _rewrite(path, payload=payload)

    def header(h: dict) -> dict:
        h["payload_sha256"] = h["output_digest"] = hashlib.sha256(new["b"]).hexdigest()
        return h
    _rewrite(path, header=header)


def test_t9c_a_moved_z_with_its_hashes_rewritten_is_refused_by_the_certificate(
        cold, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")
    v = min(p.v for p in cold["pre"].cs.pins)            # a vertex a row reads

    def moved(blob: bytes) -> bytes:
        z, s = pickle.loads(blob)
        z[v] += 0.01
        return pickle.dumps((z, s), protocol=5)
    _plant(_record(root, "solve"), moved)
    got = _solve_arm(root)
    assert _states_of(got)["solve"] == "refused: certificate: residual"
    _same_solve(cold, got)


# ── T10 / T12 ────────────────────────────────────────────────────────────

def test_t10_a_solve_code_change_reruns_the_solve_and_nothing_before(cold, warm, tmp_path,
                                                                     monkeypatch):
    root = _copy(warm[0], tmp_path / "c")
    _with_code(monkeypatch, "solve")
    got = _solve_arm(root)
    st = _states_of(got)
    assert st.pop("solve") == "miss" and set(st.values()) == {"hit"}
    _same_solve(cold, got)


def test_t10_an_assembly_code_change_reruns_the_solve(warm, tmp_path, monkeypatch):
    """The solve names the assembly by its KEY (RULINGS 2026-10-18e)."""
    root = _copy(warm[0], tmp_path / "c")
    _with_code(monkeypatch, "constraints.assembly")
    st = _states_of(_solve_arm(root))
    assert st["constraints.assembly"] == "miss" and st["solve"] == "miss"
    assert st["shapes"] == "hit"


def test_t12_a_time_limit_bypasses_the_solve(warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")
    got = _solve_arm(root, options=Options(time_limit_s=600.0))
    st = _states_of(got)
    assert st.pop("solve") == "bypass: time_limit" and set(st.values()) == {"hit"}


def test_t12_the_xplat_dump_bypasses_the_solve(tmp_path):
    st = _states_of(_solve_arm(tmp_path, bypass="xplat"))
    assert st["solve"] == "bypass: xplat" and set(st.values()) == {"bypass: xplat"}


# ── T7: cold == cold, two processes ─────────────────────────────────────

_T7 = """
import array, hashlib, sys
sys.path[:0] = [{src!r}, {root!r}]
from tests.auto_patch_v2.test_solve_late_records import _solve_arm
s = _solve_arm(None)["got"].value
print(hashlib.sha256(array.array("d", s.sol.z).tobytes()).hexdigest())
"""


def test_t7_two_cold_solves_in_two_processes_are_byte_identical():
    code = _T7.format(src=str(ROOT / "src"), root=str(ROOT))
    outs = [subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           cwd=str(ROOT), timeout=600) for _ in range(2)]
    shas = [o.stdout.strip().splitlines()[-1] for o in outs]
    assert all(o.returncode == 0 for o in outs), [o.stderr[-2000:] for o in outs]
    assert shas[0] == shas[1]


# ── the last stage (§4b.5) ───────────────────────────────────────────────

def _late_world():
    from auto_patch_v2.classify import load_rules
    from auto_patch_v2.classify.roles import Classification, _cut_back_groundside
    from auto_patch_v2.law import Law
    from tests.auto_patch_v2.test_pad_touch import _airport
    from tests.auto_patch_v2.test_roads609 import _FallingDem, _ribbon_cells
    class Dem(_FallingDem):                     # the DEM recorder asks in bulk
        def z_many(self, xs, ys):
            import numpy as np
            return np.array([self.z(float(x), float(y)) for x, y in zip(xs, ys)])
    law = Law.for_airport("ZZZZ")
    airport = _airport(law, Dem())
    cells, _n = _cut_back_groundside(_ribbon_cells(), law, load_rules(), airport,
                                     only=[2], hold=False)
    return law, airport, Classification(tuple(cells), (), {}, ())


def _late_arm(root: Path | None, **kw) -> dict:
    """The base (the classification without its pad road) and the last
    stage, as the build runs them."""
    from auto_patch_v2.pipeline.late_stage import run_last_stages
    from auto_patch_v2.pipeline.stage_one_map import gap_free
    law, airport, cl = _late_world()
    fc, airport = _cache(root, airport, law, **kw)
    common = fc.common_inputs(None, None) if fc else None
    derive = Deriver(airport, law, INPUTS, PACK, cache=fc, common=common)
    base = gap_free(cl)
    pm0, cs0, strips0, hold0 = derive(base)
    keys0 = dict(derive.last.keys)

    def run():
        sol, rep = solve_design(pm0, cs0, law, Options(), strips=strips0, hold=hold0)
        return sol, rep, {}, {}, None
    got = SR.solve_stage(fc, {**keys0, "stage_one": "none",
                              "options": fc.digest(Options()) if fc else None},
                         run, cs=cs0, n=len(pm0.vertices), law=law, options=Options(),
                         held=pm0.registries.held)
    sol0 = got.value.sol
    records = None if fc is None else LateRecords(
        fc, {"airport": keys0.get("airport"), "options": fc.digest(Options())},
        SR.identity(keys0.get("pm"), got.digest), law, Options())
    lines: list[str] = []
    pm1, sol1, rep = run_last_stages(
        cl, airport, law, derive,
        {"pm": pm0, "z": sol0.z, "pin_yield": list(got.value.design.pin_yield or ()),
         "hard_conflict": list(got.value.design.hard_conflict)},
        options=Options(), out=lines.append, records=records)
    return {"pm": pm1, "sol": sol1, "rep": rep, "lines": lines,
            "registries": _registries(pm1),
            "cache": fc.finish() if fc is not None else {}}


def _late_states(arm: dict) -> dict[str, str]:
    return {k: v["state"] for k, v in arm["cache"].get("stages", {}).items()
            if k.startswith(("late.", "solve"))}


_CLOCKS = ("wall_s",)


def _same_late(a: dict, b: dict) -> None:
    assert array.array("d", a["sol"].z).tobytes() == array.array("d", b["sol"].z).tobytes()
    assert a["pm"].vertices == b["pm"].vertices and a["pm"].faces == b["pm"].faces
    assert {f.name: getattr(a["pm"], f.name) for f in dc.fields(a["pm"])
            if f.name not in ("registries",)} == \
        {f.name: getattr(b["pm"], f.name) for f in dc.fields(b["pm"])
         if f.name not in ("registries",)}
    ra, rb = a["rep"], b["rep"]
    assert set(ra) == set(rb)
    for k in ra:
        if k in _CLOCKS:
            continue
        if k == "design":
            assert _unclocked(ra[k].as_dict()) == _unclocked(rb[k].as_dict())
        elif k in ("cs", "cs_full"):
            assert ra[k].rows() == rb[k].rows()
        else:
            assert _unclocked(ra[k]) == _unclocked(rb[k]), k
    assert _equal(a["registries"], b["registries"])
    assert _unclocked(a["lines"]) == _unclocked(b["lines"])


@pytest.fixture(scope="module")
def late_cold():
    return _late_arm(None)


@pytest.fixture(scope="module")
def late_warm(tmp_path_factory):
    root = tmp_path_factory.mktemp("late")
    return root, _late_arm(root)


def test_t8_the_late_stage_hit_equals_cold(late_cold, late_warm, tmp_path):
    root, miss = late_warm
    assert _late_states(miss) == {"solve": "miss", "late.cut.1": "miss",
                                  "late.solve.1": "miss"}
    _same_late(late_cold, miss)
    hit = _late_arm(_copy(root, tmp_path / "c"))
    assert set(hit["cache"]["stages"][k]["state"] for k in hit["cache"]["stages"]) == {"hit"}
    _same_late(late_cold, hit)


def test_t8_late_only_miss_equals_cold(late_cold, late_warm, tmp_path):
    root = _copy(late_warm[0], tmp_path / "c")
    _record(root, "late.solve.1").unlink()
    got = _late_arm(root)
    assert _late_states(got) == {"solve": "hit", "late.cut.1": "hit", "late.solve.1": "miss"}
    _same_late(late_cold, got)


def test_t10_a_late_solve_code_change_reruns_the_late_solve_only(late_cold, late_warm,
                                                                 tmp_path, monkeypatch):
    root = _copy(late_warm[0], tmp_path / "c")
    _with_code(monkeypatch, "late_solve")
    got = _late_arm(root)
    st = {k: v["state"] for k, v in got["cache"]["stages"].items()}
    assert st.pop("late.solve.1") == "miss" and set(st.values()) == {"hit"}
    _same_late(late_cold, got)


def test_t9c_a_late_record_with_a_moved_z_is_refused_by_the_certificate(
        late_cold, late_warm, tmp_path):
    root = _copy(late_warm[0], tmp_path / "c")
    path = _record(root, "late.solve.1")
    cs_full = late_cold["rep"]["cs_full"]
    v = min(cs_full.vertices())

    def moved(blob: bytes) -> bytes:
        rec = pickle.loads(blob)
        rec["z"][v] += 10.0
        return pickle.dumps(rec, protocol=5)
    _plant(path, moved)
    got = _late_arm(root)
    assert _late_states(got)["late.solve.1"].startswith("refused: certificate")
    _same_late(late_cold, got)


def test_the_late_records_key_on_the_derive_and_the_cut(late_warm):
    rep = late_warm[1]["cache"]["stages"]
    assert {"late.cut.1", "late.solve.1"} <= set(rep)
    assert prefix_identity({}) is None
    assert SR.identity("a", None) is None and SR.identity("a", "b") != SR.identity("b", "a")
