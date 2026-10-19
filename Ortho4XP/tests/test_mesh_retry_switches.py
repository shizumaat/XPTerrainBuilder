"""#874: Triangle4XP's lower-angle retry runs with the first run's switches.

``build_mesh`` retries Triangle4XP with a lower ``q`` angle when the first
run fails.  The retry used to rebuild its switch string by hand and dropped
``a`` (REGIONAL area constraints), so a retried tile meshed the bank
annulus (RULINGS 2026-09-09x) as if it had no area limit.

The twin drives ``build_mesh`` itself with every collaborator stubbed: the
"Triangle4XP" run records its switches and fails once; the retry records
its own and raises the Stop flag so the step ends there.  Headless — no
DEM, no Triangle4XP binary, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import O4_File_Names as FNAMES  # noqa: E402
import O4_Mesh_Utils as MESH  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

NX = NY = 3


class _FakeDem:
    def __init__(self, *args, **kwargs):
        self.nxdem, self.nydem = NX, NY
        self.x0, self.y0, self.x1, self.y1 = -4, 40, -3, 41
        self.nodata = -32768


class _FakeRun:
    def __init__(self, returncode):
        self.returncode = returncode

    def poll(self):
        return self.returncode


def _switches_of_a_retried_run(tmp_path, monkeypatch, *, iterate, binary):
    """The switch strings of the first run and the first retry."""
    tile = SimpleNamespace(
        lat=40, lon=-4, iterate=iterate, build_dir=str(tmp_path),
        min_angle=10, limit_tris=0, custom_dem="", fill_nodata=None,
        curvature_tol=2, elevation_level="auto", dem=None)
    Path(FNAMES.input_node_file(tile)).write_text(
        "100 2 1 0\n", encoding="utf-8", newline="\n")
    Path(FNAMES.input_poly_file(tile)).write_text(
        "0 2 1 0\n", encoding="utf-8", newline="\n")
    Path(FNAMES.alt_file(tile)).write_bytes(b"\0" * (4 * NX * NY))

    monkeypatch.setattr(MESH, "_refuse_on_broken_proj", lambda: False)
    monkeypatch.setattr(UI, "logprint", lambda *a, **k: None)
    monkeypatch.setattr(UI, "progress_bar", lambda *a, **k: None)
    monkeypatch.setattr(UI, "exit_message_and_bottom_line",
                        lambda *a, **k: None)
    monkeypatch.setattr(UI, "is_working", 0)
    monkeypatch.setattr(MESH.DEM, "DEM", _FakeDem)
    monkeypatch.setattr(MESH.DEM, "drop_missing_pinned_files", lambda s: s)
    monkeypatch.setattr(MESH.INSETS, "assemble_inset_composite_source",
                        lambda tile, source: source)
    monkeypatch.setattr(MESH.INSETS, "densify_tile_dem_for_insets",
                        lambda tile: None)
    monkeypatch.setattr(MESH.TRI_BIN, "refine_inputs_as_text",
                        lambda *a: None)
    monkeypatch.setattr(MESH.TRI_BIN, "use_binary_io",
                        lambda cmd, refine: binary and not refine)
    monkeypatch.setattr(MESH.TRI_BIN, "binary_inputs",
                        lambda node, poly: poly + ".bin")
    monkeypatch.setattr(MESH, "build_curv_tol_weight_map",
                        lambda tile, weights: None)
    monkeypatch.setattr(MESH, "hairline_preflight", lambda poly, tile: True)
    monkeypatch.setattr(MESH.time, "sleep", lambda s: None)

    switches = []

    def run(mesh_cmd):
        switches.append(mesh_cmd[1])
        if len(switches) == 1:
            return _FakeRun(1)          # the first run fails: retry
        UI.red_flag = True              # end the step after one retry
        return _FakeRun(0)

    monkeypatch.setattr(MESH, "_run_triangulation_process", run)
    try:
        assert MESH.build_mesh(tile) == 0
    finally:
        UI.red_flag = False
    assert len(switches) == 2, switches
    return switches


@pytest.mark.parametrize("binary", [False, True])
def test_the_retry_keeps_every_first_run_switch_but_the_angle(
        tmp_path, monkeypatch, binary):
    first, retry = _switches_of_a_retried_run(
        tmp_path, monkeypatch, iterate=0, binary=binary)
    assert first.startswith("-pq10Aa"), first
    assert retry == first.replace("-pq10", "-pq8", 1)
    assert ("b" in retry.split("S")[0]) is binary


def test_the_iterate_retry_refines_without_regional_areas(
        tmp_path, monkeypatch):
    first, retry = _switches_of_a_retried_run(
        tmp_path, monkeypatch, iterate=1, binary=True)
    assert first.startswith("-pq10ruYB"), first
    assert "a" not in first and "b" not in first.split("S")[0]
    assert retry == first.replace("-pq10", "-pq8", 1)
