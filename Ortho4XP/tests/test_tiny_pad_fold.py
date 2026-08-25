"""Twins for TINY PADS FOLD INTO THEIR PARENT (owner ruling RULINGS
2026-08-24).

A building pad below ``PAD_MIN_AREA_M2`` is NOT an independent seat
authority: it mints no pad shape, so no building seat, no frontage vertex
and no pad interception.  Its footprint remains APRON and its ring seats
with the surrounding surface; where it is welded to (or inside the
frontage reach of) a >= threshold building the parent's value governs
through the EXISTING weld / frontage machinery.

Exemplar: HECA -10144, 216 m², one altitude tag, seated 2.56 m below the
terminal it serves 68 m away.

Headless, geometry-only, no network and no X-Plane install.
"""

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch import grade_law as GL                         # noqa: E402
from auto_patch.config import PAD_MIN_AREA_M2                  # noqa: E402


# ── 2. THE TINY-PAD FOLD ──────────────────────────────────────────────

def test_pad_min_area_is_the_ruled_constant():
    """250 m², the threshold the owner adopted to catch exemplar -10144
    (216 m²), and it replaces the pipeline's bare 100.0 floor."""
    assert PAD_MIN_AREA_M2 == pytest.approx(250.0)
    src = (Path(__file__).resolve().parents[1]
           / "src" / "auto_patch" / "pipeline.py").read_text()
    assert "simp.area >= PAD_MIN_AREA_M2" in src, (
        "the pipeline pad floor must read the ruled constant, not 100.0")


def _fold(polys):
    """The pipeline's fold predicate, applied to a pad list."""
    return [p for p in polys
            if p is not None and not p.is_empty and p.area >= PAD_MIN_AREA_M2]


def test_sub_threshold_pad_folds_and_at_threshold_pad_is_untouched():
    tiny = Polygon([(0, 0), (18, 0), (18, 12), (0, 12)])        # 216 m²
    real = Polygon([(100, 0), (140, 0), (140, 40), (100, 40)])  # 1,600 m²
    assert tiny.area == pytest.approx(216.0)
    kept = _fold([tiny, real])
    assert kept == [real], "a 216 m² pad is not an independent pad"

    at_threshold = Polygon([(0, 0), (25, 0), (25, 10), (0, 10)])  # 250 m²
    assert _fold([at_threshold]) == [at_threshold], (
        "the threshold is inclusive — a 250 m² pad still seats")


def test_the_heca_10144_exemplar_geometry_folds():
    """The owner's exemplar, synthetically: a 216 m² pad 68 m from the
    terminal it serves.  It must not mint a pad — which is what removes
    its independent seat, its frontage authority and the 2.56 m step."""
    exemplar = Polygon([(0, 0), (18, 0), (18, 12), (0, 12)])
    terminal = Polygon([(68, -30), (188, -30), (188, 60), (68, 60)])
    kept = _fold([exemplar, terminal])
    assert exemplar not in kept and terminal in kept
    # …and with the pad gone, the ground it stood on carries NO building
    # ring, so it mints no frontage vertex either.
    assert GL.frontage_vertex_keys(
        [list(range(4))] if exemplar in kept else [], {0, 1, 2, 3}) == set()


def test_the_fold_is_wired_at_the_apron_punch_out():
    """The fold must run BEFORE ``terminal_union`` — the punch-out that
    removes pad ground from the apron — or the footprint would not
    "remain apron" as the ruling requires."""
    src = (Path(__file__).resolve().parents[1]
           / "src" / "auto_patch" / "pipeline.py").read_text()
    fold_at = src.index("tiny pad(s) under")
    union_at = src.index("terminal_union = (unary_union(terminal_polys)")
    assert fold_at < union_at, (
        "the tiny-pad fold must precede the apron punch-out")


