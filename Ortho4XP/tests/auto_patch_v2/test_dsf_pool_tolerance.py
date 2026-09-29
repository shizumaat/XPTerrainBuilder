"""#60 twins: the no-op round-trip verifier's tolerance follows the DSF's
OWN pool resolution, and a 0-byte cached dump is a refused cache entry.

The #23 class sweep left 4 of 442 dumps failing: three were tolerances
pinned for a 0.03125 deg pool read against coarser pools (0.125 / 0.25
deg, and a 3-quantum heading pairing), one a 0-byte dump DSFTool had
died writing.  These pin the rule both ways — a coarse pool's drift
passes, the SAME drift on a fine pool still fails — and the 0-byte
handling at every reader.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

from auto_patch_v2.airport import dsf as D
from auto_patch_v2.airport import dsf_write as W

ROOT = Path(__file__).resolve().parents[2]


def _dump(span: float, rows: list[tuple[float, float, float]],
          pool_offsets=(7.0, 46.0)) -> str:
    lines = ["A", "800", "DSF2TEXT", "",
             "# file: /fixture/+46+007.dsf", "",
             f"# pool  0: p=3 s=  {len(rows)}  {span:.5f} {pool_offsets[0]:.5f}  "
             f"{span:.5f} {pool_offsets[1]:.5f}  360.00000 0.00000",
             "",
             "PROPERTY sim/west 7", "PROPERTY sim/east 8",
             "PROPERTY sim/south 46", "PROPERTY sim/north 47",
             "OBJECT_DEF lib/a.obj"]
    lines += [f"OBJECT 0 {lon:.9f} {lat:.9f} {hdg:.6f}" for lon, lat, hdg in rows]
    return "\n".join(lines) + "\n"


def test_pool_tolerances_read_the_widest_plane_and_keep_the_floors():
    fine = _dump(0.03125, [(7.01, 46.01, 10.0)])
    coarse = _dump(0.125, [(7.01, 46.01, 10.0)])
    t_deg, t_hdg = W.pool_tolerances(fine)
    assert t_deg == W.TOL_DEG                    # 4 * 0.03125/65535 < 2e-6
    assert abs(t_hdg - 4 * 360.0 / 65535) < 1e-12
    t_deg, _ = W.pool_tolerances(fine, coarse)   # either text's pools count
    assert abs(t_deg - 4 * 0.125 / 65535) < 1e-15
    assert W.pool_tolerances("A\n800\nOBJECT 0 1 2 3\n") == (
        W.TOL_DEG, W.TOL_HEADING_DEG)            # no pools: the pinned floors


def test_a_coarse_pool_drift_passes_and_the_same_drift_on_a_fine_pool_fails():
    q = 0.125 / 65535
    base = [(7.01, 46.01, 10.0), (7.02, 46.02, 200.0)]
    moved = [(lon + 2 * q, lat - 2 * q, h) for lon, lat, h in base]
    # simHeaven +46+007 class: 2 quanta of a 0.125 deg pool (3.81e-06 deg)
    rep = W.compare_dumps(_dump(0.125, base), _dump(0.125, moved))
    assert rep.ok, rep.findings
    # the SAME 3.8e-06 deg on the 0.03125 deg pool the floor was pinned for
    rep = W.compare_dumps(_dump(0.03125, base), _dump(0.03125, moved))
    assert not rep.ok
    assert any("drift" in f or "counterpart" in f for f in rep.findings)


def test_two_near_coincident_objects_pair_inside_the_pool_heading_tolerance():
    """Global Airports ``+39-095``: two objects 4.8e-07 deg apart whose
    headings differ by 2 quanta; the greedy pairing read 3 quanta
    (0.01648 deg) against the pinned 2-quanta 0.011."""
    hq = 360.0 / 65535
    exp = [(-94.782238975, 39.486218242, 359.368276),
           (-94.782238975, 39.486218719, 359.379263)]
    act = [(-94.782238975, 39.486218242, 359.368276 + hq),
           (-94.782238975, 39.486217765, 359.379263 - 3 * hq)]
    rep = W.compare_dumps(_dump(0.0625, exp, (-94.8125, 39.4375)),
                          _dump(0.0625, act, (-94.8125, 39.4375)))
    assert rep.ok, rep.findings
    assert rep.max_heading_deg <= 4 * hq + 1e-9


def test_a_zero_byte_dump_is_never_served(tmp_path):
    pack = tmp_path / "xp" / "Custom Scenery" / "P"
    dsf = pack / "Earth nav data" / "+40+000" / "+47+007.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"XPLNEDSF")
    root = tmp_path / "mod_cache"
    (root / "P").mkdir(parents=True)
    keyed = root / "P" / f"+47+007.dsf.{D.text_dump_tag(str(dsf))}.text"
    keyed.write_bytes(b"")
    st = os.stat(dsf)
    os.utime(keyed, (st.st_atime + 60, st.st_mtime + 60))
    assert D.find_text_dump(str(root), "P", 47, 7, dsf_path=str(dsf)) is None
    assert D.find_text_dump(str(root), "P", 47, 7) is None
    keyed.write_text("A\n800\nDSF2TEXT\n", encoding="utf-8", newline="")
    os.utime(keyed, (st.st_atime + 60, st.st_mtime + 60))
    assert D.find_text_dump(str(root), "P", 47, 7, dsf_path=str(dsf)) == str(keyed)


def test_the_v1_reader_regenerates_a_zero_byte_cached_dump(tmp_path, monkeypatch):
    import auto_patch.dsf_reader as R
    dsf = tmp_path / "bare" / "+47+007.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"XPLNEDSF")
    cache = tmp_path / "cache"
    cache.mkdir()
    ran = []

    def _fake_run(cmd, **kw):
        ran.append(cmd)
        Path(cmd[-1]).write_text("A\n800\nDSF2TEXT\n", encoding="utf-8", newline="")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(R, "_dsftool_path", lambda: "/fixture/DSFTool")
    monkeypatch.setattr(R.subprocess, "run", _fake_run)
    first = R.ensure_dsf_text_path(str(dsf), str(cache))
    assert first and os.path.getsize(first) > 0 and len(ran) == 1
    assert R.ensure_dsf_text_path(str(dsf), str(cache)) == first
    assert len(ran) == 1                                  # warm: no re-dump
    Path(first).write_bytes(b"")                          # a DSFTool that died
    assert R.ensure_dsf_text_path(str(dsf), str(cache)) == first
    assert len(ran) == 2 and os.path.getsize(first) > 0   # regenerated


def test_the_sweep_lists_a_zero_byte_dump_as_refused_not_failed(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "_dsf_placement_diff", ROOT / "tools" / "dsf_placement_diff.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    d = tmp_path / "Global Airports"
    d.mkdir()
    empty = d / "+47+007.dsf.fa60276f.text"
    empty.write_bytes(b"")
    rep = tool.sweep_noop(str(tmp_path), "/fixture/DSFTool", jobs=1)
    assert rep["failed"] == 0 and rep["dumps"] == 0
    assert rep["empty_dumps_refused"] == [str(empty)]
