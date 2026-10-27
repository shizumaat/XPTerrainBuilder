"""``dsf_heights.pin_heights``: the ``HEIGHTS`` row an edit is encoded
from is the FILE's (its ``# pool`` header), never the row DSFTool printed
from memory it over-read (batch AK CI, Windows, 2026-10-27: two writes of
one plan, elevation planes based at -1 and at 0)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from auto_patch.dsf_reader import _dsftool_path
from auto_patch_v2.airport import dsf as D
from auto_patch_v2.airport import dsf_heights as H
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.model.placement import PlacementPlan, Provenance

_HEAD = ("A\n800 written by DSFTool 2.4.0-b1\nDSF2TEXT\n\n# file: x.dsf\n\n"
         "# pool  0: p=3 s=    1  0.12500 -94.75000  0.12500 39.25000  360.00000 0.00000\n"
         "{p4}"
         "# pool  2: p=4 s=    3  0.25000 -94.75000  0.25000 39.12500  1.00000 0.00000  1.00000 0.00000\n"
         "# pool  3: # obj_pools found: 2\n\n"
         "DIVISIONS 8\nHEIGHTS {row}  # max encodeable 1.0\n"
         "PROPERTY sim/west -95\nPROPERTY sim/overlay 1\nOBJECT_DEF a.obj\n")
_P4 = ("# pool  1: p=4 s=    3  0.12500 -94.75000  0.12500 39.25000  "
       "360.00000 0.00000  {span} {off}\n")


def _text(row: str, span: str | None = "65535.00000", off: str = "0.00000") -> str:
    p4 = _P4.format(span=span, off=off) if span else ""
    return _HEAD.format(p4=p4, row=row)


def _row(text: str) -> str:
    return next(l for l in text.splitlines() if l.startswith("HEIGHTS "))


def test_a_printed_row_from_overread_memory_is_replaced_by_the_files():
    assert _row(H.pin_heights(_text("1.00000 -1.0"))) == \
        "HEIGHTS 1.00000 0.0  # max encodeable 65535.00000"


def test_a_pack_quantum_is_read_from_the_elevation_plane():
    # KASE (#131): WED wrote 0.06250 for rows up to 2444 m
    assert _row(H.pin_heights(_text("1.00000 0.0", "4095.93750"))) == \
        "HEIGHTS 0.06250 0.0  # max encodeable 4095.93750"
    # a pool based below sea level keeps its floor
    assert _row(H.pin_heights(_text("1.00000 0.0", "4095.93750", "-430.00000"))) \
        .startswith("HEIGHTS 0.06250 -430.0")


def test_no_elevated_pool_is_dsflibs_own_empty_answer():
    # #131: a polygon/road-only DSF re-dumps 0.50000
    assert _row(H.pin_heights(_text("0.12500 0.0", None))).startswith(
        "HEIGHTS 0.50000 0.0")


def test_a_base_mesh_or_a_text_without_the_row_is_untouched():
    mesh = _text("1.00000 -1.0").replace("PROPERTY sim/overlay 1\n", "")
    assert H.pin_heights(mesh) == mesh
    bare = "\n".join(l for l in _text("1.0 0.0").splitlines()
                     if not l.startswith("HEIGHTS"))
    assert H.pin_heights(bare) == bare


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_two_writes_of_one_plan_agree_whatever_heights_row_the_dump_printed(
        tmp_path, monkeypatch):
    """The CI failure, made deterministic: the pristine dump of each write
    prints a different ``HEIGHTS`` base (as DSFTool's over-read does at
    random); the written DSF is the same bytes."""
    from test_v2dsfagl import _synthetic_pack
    tool = _dsftool_path()
    pack = tmp_path / "pack"
    dsf = Path(_synthetic_pack(pack, tool))
    dump = D.read_dump(W.dump(str(dsf), str(tmp_path / "p.text"), tool))
    conv, kept = W.conversions_for_dump(dump, str(pack))
    plan = PlacementPlan(icao="TEST", pack_name="pack", pack_root=str(pack),
                         dsf_path=str(dsf), dsf_backup_path=str(dsf) + ".anchor_bak",
                         provenance=Provenance("", "test", ""),
                         conversions=tuple(conv), kept=tuple(kept))
    real_dump = W.dump
    printed = iter(["1.00000 -1.0", "1.00000 0.0"])

    def lying_dump(dsf_path, text_out, tool_, **kw):
        out = real_dump(dsf_path, text_out, tool_, **kw)
        if dsf_path.endswith(".anchor_bak") and text_out.endswith(".pristine.text"):
            body = Path(out).read_text(encoding="utf-8")
            lines = [("HEIGHTS " + next(printed)) if l.startswith("HEIGHTS ") else l
                     for l in body.split("\n")]
            Path(out).write_text("\n".join(lines), encoding="utf-8", newline="")
        return out

    monkeypatch.setattr(W, "dump", lying_dump)
    W.write_pack(str(pack), plan, tool, work_dir=str(tmp_path / "w"))
    first = dsf.read_bytes()
    W.write_pack(str(pack), plan, tool, work_dir=str(tmp_path / "w2"))
    assert dsf.read_bytes() == first
    assert os.path.isfile(str(dsf) + ".anchor_bak")
