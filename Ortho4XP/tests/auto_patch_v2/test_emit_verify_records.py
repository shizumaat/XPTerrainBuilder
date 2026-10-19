"""#843 step 9c — the emit and verify records (``pipeline/emit_records``,
``pipeline/emit_stage.render`` / ``install``, ``pipeline/verify_stage``;
spec ``v2-stage-cache-spec.md`` §4b.6, §4b.7, §7, §8 T8/T9 (d) (e)/T10).

Synthetic, no corpus: ``test_backhalf_records``'s airport, solved once,
then emitted and verified COLD (no cache), through a MISS (every record
written) and through HITs — the files on disk, the report and the rows
compared byte for byte.  The closing HECA / CYXY identity is the master's."""
from __future__ import annotations

import dataclasses as dc
import hashlib
import pickle
import re
import shutil
import types
from pathlib import Path

import pytest
from test_backhalf_records import ICAO, _copy, _record, _rewrite, _states, synthetic

from auto_patch_v2.airport.rebake_screen import patch_body_sha256
from auto_patch_v2.emit.osm_adapter import render_patch
from auto_patch_v2.pipeline import emit_records as ER
from auto_patch_v2.pipeline import front_cache as FC
from auto_patch_v2.pipeline.constraint_records import strips_stage
from auto_patch_v2.pipeline.shapes import joint_steps, shape_constraints, shape_stage
from auto_patch_v2.planar.build import build as build_planar
from auto_patch_v2.solve import solve_design


@pytest.fixture(scope="module")
def solved():
    law, airport, cl = synthetic()
    pm, _stats = build_planar(airport, cl, law)
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, _counts, _walls = shape_constraints(stage.pm, law, airport, stage, yielded_out=[])
    con = types.SimpleNamespace(cs=cs, key=None, chain="")
    strips = strips_stage(None, stage.pm, law, airport, con, {})
    sol, design = solve_design(stage.pm, cs, law, strips=strips)
    assert sol.status.value in ("optimal", "feasible"), sol.message
    return dict(law=law, airport=airport, cl=cl, pm=stage.pm, stage=stage, cs=cs,
                strips=strips, sol=sol, design=design)


def _arm(w, out_dir: Path, root: Path | None, *, header=None, between=None, **fc_kw):
    """Emit + verify once into a fresh ``out_dir``: ``(files, report, lines,
    rows, cache states, Emit, cache report)``; ``root`` None is COLD."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    law, pm, sol = w["law"], w["pm"], w["sol"]
    fc = FC.FrontCache(ICAO, w["airport"], law, enabled=root is not None,
                       mod_cache_root=None if root is None else str(root), **fc_kw)
    airport = fc.airport(w["airport"])
    report: dict = {"joint_steps": joint_steps(pm, law, w["stage"], sol.z)}
    wall: dict = {}
    lines: list[str] = []
    lrep = types.SimpleNamespace(dsf_dump_path=None)
    kw = dict(pm=pm, sol=sol, cs=w["cs"], cl=w["cl"], strips=w["strips"],
              design_rep=w["design"], hard_conflict=w["design"].hard_conflict,
              yield_records=[], late_report=None, lrep=lrep, airport=airport,
              objects_out=[])
    em_in = ER.emit_inputs(fc, cs_key="synthetic-assembly-key",
                           common=fc.common_inputs(None, None), feather_m=60.0, **kw)
    em = ER.emit(fc, em_in, icao=ICAO, law=law, header_extra=header, out_dir=out_dir,
                 report=report, wall=wall, out=lines.append, **kw)
    if between is not None:
        between(em)
    rows = ER.verify(fc, em, pm_digest=em_in.get("pm"), airport_digest=em_in.get("airport"),
                     icao=ICAO, pm=pm, law=law, airport=airport, report=report, wall=wall,
                     pool_out=[], out=lines.append)
    rep = fc.finish()
    files = {str(p.relative_to(out_dir)): p.read_bytes()
             for p in sorted(out_dir.rglob("*")) if p.is_file()}
    return files, report, lines, rows, _states(rep), em, rep


def _clockless(lines):
    return [re.sub(r"\d+\.\d\d s|served", "T", ln) for ln in lines]


def _same(a, b) -> None:
    assert a[0] == b[0]                                    # every file, byte for byte
    ra, rb = dict(a[1]), dict(b[1])
    va, vb = ra.pop("verify"), rb.pop("verify")
    assert ra == rb
    assert {k: v for k, v in va.items() if k != "wall_s"} == \
        {k: v for k, v in vb.items() if k != "wall_s"}
    assert _clockless(a[2]) == _clockless(b[2])            # the lines, re-printed
    assert a[3] == b[3]                                    # the rows by family


@pytest.fixture(scope="module")
def warm(solved, tmp_path_factory):
    root = tmp_path_factory.mktemp("warm")
    return root, _arm(solved, tmp_path_factory.mktemp("o") / "out", root)


# ── T8: hit == cold, and each single-record miss ────────────────────────

def test_t8_cold_miss_and_hit_are_byte_identical(solved, warm, tmp_path):
    cold = _arm(solved, tmp_path / "out", None)
    assert cold[4] == {}
    root, miss = warm
    assert miss[4] == {"emit": "miss", "verify": "miss"}
    _same(cold, _arm(solved, tmp_path / "out", None))       # T7 on the fixture
    hit = _arm(solved, tmp_path / "out", _copy(root, tmp_path / "c"))
    assert hit[4] == {"emit": "hit", "verify": "hit"}
    _same(cold, hit)
    assert any("verify served" in ln for ln in hit[2])
    _same(cold, _arm(solved, tmp_path / "out", None))
    assert miss[0] == hit[0] and _clockless(miss[2]) == _clockless(hit[2])


def test_t8_emit_only_miss(solved, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")
    _record(root, "emit").unlink()
    got = _arm(solved, tmp_path / "out", root)
    assert got[4] == {"emit": "miss", "verify": "hit"}      # the same output digest
    _same(_arm(solved, tmp_path / "out", None), got)


def test_t8_verify_only_miss_decodes_the_served_surface(solved, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")
    _record(root, "verify").unlink()
    got = _arm(solved, tmp_path / "out", root)
    assert got[4] == {"emit": "hit", "verify": "miss"}
    _same(_arm(solved, tmp_path / "out", None), got)


def test_the_miss_arm_reports_its_cost(warm):
    for name in ("emit", "verify"):
        r = warm[1][6]["stages"][name]
        assert {"key", "encode_s", "digest_s", "write_s", "written_bytes"} <= set(r), name
        assert r["written_bytes"] > 0


# ── the header split (§4b.6) ────────────────────────────────────────────

def test_the_header_is_applied_on_every_write_and_is_not_keyed(solved, warm, tmp_path):
    """A host's freshness stamps change: emit and verify still HIT, the
    patch on disk carries the new header and equals a cold build's."""
    stamp = {"o4_code": "a-new-commit", "o4_apt_dat": "percent%20encoded"}
    root = _copy(warm[0], tmp_path / "c")
    got = _arm(solved, tmp_path / "out", root, header=stamp)
    assert got[4] == {"emit": "hit", "verify": "hit"}
    cold = _arm(solved, tmp_path / "out", None, header=stamp)
    _same(cold, got)
    patch = f"{ICAO}_auto.patch.osm"
    assert b"o4_code='a-new-commit'" in got[0][patch]
    assert got[0][patch] != warm[1][0][patch]
    body = lambda b: b.split(b"\n")[2:]                       # noqa: E731
    assert body(got[0][patch]) == body(warm[1][0][patch])


def test_the_split_renders_render_patch_exactly(solved, warm):
    em = warm[1][5]
    surf, _pub = em.surf_pub()
    assert hashlib.sha256(em.emitted.patch.body.encode()).hexdigest() == \
        patch_body_sha256(em.paths.patch)
    text = em.paths.patch.read_text(encoding="utf-8")
    assert text.split("\n", 2)[2] == em.emitted.patch.body
    # the welded surface is what was written; the root line is render_patch's
    assert text.split("\n")[:2] == render_patch(surf, solved["law"], {
        "o4_apt_dat": "apt.dat", "o4_pack": "fixture", "o4_apt_dat_borrowed": ""})[0] \
        .split("\n")[:2]


# ── T9: planted stale entries ───────────────────────────────────────────

def test_t9d_an_emit_body_that_no_longer_hashes_is_refused(solved, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")
    path = _record(root, "emit")
    new: dict = {}

    def payload(b: bytes) -> bytes:
        rec = pickle.loads(b)
        rec = rec._replace(patch=dc.replace(rec.patch, body=rec.patch.body + "<!-- x -->\n"))
        new["blob"] = pickle.dumps(rec, protocol=5)
        return new["blob"]

    _rewrite(path, payload=payload)
    _rewrite(path, header=lambda h: {**h, "payload_sha256":
                                     hashlib.sha256(new["blob"]).hexdigest()})
    got = _arm(solved, tmp_path / "out", root)
    assert got[4]["emit"] == f"refused: body:{ICAO}_auto.patch.osm"
    _same(_arm(solved, tmp_path / "out", None), got)


def test_t9e_a_verdict_over_a_patch_edited_since_is_refused(solved, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")

    def edit(em):
        with open(em.paths.patch, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("<!-- edited after emit -->\n")
    got = _arm(solved, tmp_path / "out", root, between=edit)
    assert got[4] == {"emit": "hit", "verify": "refused: body:disk"}


# ── T10 / T11 / T12 ─────────────────────────────────────────────────────

def _with_code(monkeypatch, entry: str) -> None:
    real = FC._code.runtime_digests

    def patched():
        d = real()
        d[entry] = "f" * 64
        return d
    monkeypatch.setattr(FC._code, "runtime_digests", patched)


def test_t10_a_verify_code_change_reruns_verify_alone(solved, warm, tmp_path, monkeypatch):
    _with_code(monkeypatch, "verify")
    got = _arm(solved, tmp_path / "out", _copy(warm[0], tmp_path / "c"))
    assert got[4] == {"emit": "hit", "verify": "miss"}


def test_t10_an_emit_code_change_reruns_emit(solved, warm, tmp_path, monkeypatch):
    _with_code(monkeypatch, "emit")
    got = _arm(solved, tmp_path / "out", _copy(warm[0], tmp_path / "c"))
    assert got[4]["emit"] == "miss"
    # verify names emit by its OUTPUT digest: the same record is a hit
    # (early cutoff, spec §4c)
    assert got[4]["verify"] == "hit"
    _same(_arm(solved, tmp_path / "out", None), got)


def test_t11_a_changed_environment_misses_both(solved, warm, tmp_path, monkeypatch):
    real = FC._xplat.environment
    monkeypatch.setattr(FC._xplat, "environment", lambda: {**real(), "numpy": "0.0.0"})
    got = _arm(solved, tmp_path / "out", _copy(warm[0], tmp_path / "c"))
    assert got[4] == {"emit": "miss", "verify": "miss"}


def test_t12_the_xplat_dump_bypasses_both(solved, tmp_path):
    got = _arm(solved, tmp_path / "out", tmp_path / "c", bypass="xplat")
    assert got[4] == {"emit": "bypass: xplat", "verify": "bypass: xplat"}
    _same(_arm(solved, tmp_path / "out", None), got)
