"""``dsf_heights.cover_row_elevations`` covers the HIGHEST elevated row
too, and ``refused_rows`` names what ``--text2dsf`` would refuse.

1.0.564 (2026-11-19): a pack DSF with no elevated row pins ``HEIGHTS
0.03125 0.0`` (top 2,047.97 m); the plan seated four object-floor bodies
``OBJECT_MSL`` at 2,348.638 m, above the top, and DSFTool failed the whole
file -- ``ERROR: could not place object`` -- so the airport kept its old
(floating) placement."""
from __future__ import annotations

import os
import subprocess

import pytest

from auto_patch.dsf_reader import _dsftool_path
from auto_patch_v2.airport import dsf_heights as DH

_ROW = "OBJECT_MSL 0 -106.867900263 39.225488766 2348.638 249.426413\n"
_EMPTY = "HEIGHTS 0.03125 0.0  # max encodeable 2047.96875\n"


def _heights(text: str) -> tuple[float, float]:
    toks = next(l for l in text.splitlines() if l.startswith("HEIGHTS ")).split()
    return float(toks[1]), float(toks[2])


def test_a_row_over_the_pinned_top_was_refused_before_the_cover():
    assert DH.refused_rows(_EMPTY + _ROW) == [f"line 2: {_ROW.strip()}"]


def test_the_base_moves_up_under_a_row_over_the_top_and_the_quantum_is_kept():
    text = DH.cover_row_elevations(_EMPTY + "OBJECT 1 -106.8 39.2 12.0\n" + _ROW)
    assert _heights(text) == (0.03125, 2348.0)
    assert DH.refused_rows(text) == []


def test_rows_spanning_more_than_the_quantum_reaches_coarsen_it_and_fit():
    low = "OBJECT_MSL 0 -106.8 39.2 10.0 0\n"
    text = DH.cover_row_elevations(_EMPTY + low + _ROW)
    quantum, base = _heights(text)
    assert base <= 10.0 and base + quantum * 65535.0 >= 2348.638
    assert quantum <= 0.0625
    assert DH.refused_rows(text) == []


def test_rows_inside_the_range_are_untouched_byte_for_byte():
    text = _EMPTY + "OBJECT_MSL 0 -106.8 39.2 1500.25 10\n"
    assert DH.cover_row_elevations(text) == text


def test_a_heading_off_the_pool_plane_is_refused_before_the_encoder():
    text = _EMPTY + "OBJECT 0 -106.8 39.2 -3.5\nOBJECT 0 -106.8 39.2 360.0\n"
    assert DH.refused_rows(text) == ["line 2: OBJECT 0 -106.8 39.2 -3.5"]


@pytest.mark.skipif(not os.path.isfile(_dsftool_path() or ""), reason="no DSFTool")
def test_dsftool_encodes_the_covered_text(tmp_path):
    head = ("A\n800\nDSF2TEXT\n\nDIVISIONS 32\n" + _EMPTY +
            "PROPERTY sim/west -107\nPROPERTY sim/east -106\n"
            "PROPERTY sim/north 40\nPROPERTY sim/south 39\n"
            "PROPERTY sim/planet earth\nPROPERTY sim/overlay 1\n"
            "OBJECT_DEF objects/x.obj\n")
    for name, text in (("raw", head + _ROW),
                       ("covered", DH.cover_row_elevations(head + _ROW))):
        src = tmp_path / f"{name}.txt"
        src.write_text(text)
        run = subprocess.run([_dsftool_path(), "--text2dsf", str(src),
                              str(tmp_path / f"{name}.dsf")],
                             capture_output=True, text=True)
        refused = "could not place object" in (run.stdout + run.stderr)
        assert refused == (name == "raw"), (name, run.stdout, run.stderr)
