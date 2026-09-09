"""Twin for ``tools/patch_seed_seal.py`` (RULINGS `7e90032`: a promoted
lane script lands with its index entry and its twin).

Headless and synthetic: a patch directory written into ``tmp_path`` with
two closed ways nanometres apart — the HECA class the tool was written for
— plus a control directory with one honest ring.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "tools")):
    if path not in sys.path:
        sys.path.insert(0, path)

import patch_seed_seal as PSS  # noqa: E402

#: The two nodes HECA's coincident bank level rings share, tile-relative.
A = (0.41367461122, 0.12822382732)
D = (0.41366859242, 0.12822486347)
FAR = [(0.4130, 0.1290), (0.4140, 0.1290)]


def _extra_node():
    ux, uy = D[0] - A[0], D[1] - A[1]
    length = math.hypot(ux, uy)
    return (A[0] + 0.5 * ux - 3.0e-14 * uy / length,
            A[1] + 0.5 * uy + 3.0e-14 * ux / length)


def _write_patch(directory: Path, rings, lat=30, lon=31):
    """A minimal auto-patch OSM: absolute lat/lon, one closed way each."""
    lines = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<osm version='0.6' generator='test'>"]
    node_id, way_nodes = -1, []
    for ring in rings:
        ids = []
        for (x, y) in ring[:-1]:
            lines.append(f"  <node id='{node_id}' action='modify' "
                         f"visible='true' lat='{y + lat:.11f}' "
                         f"lon='{x + lon:.11f}'>")
            lines.append("    <tag k='alt_abs' v='100.0' />")
            lines.append("  </node>")
            ids.append(node_id)
            node_id -= 1
        way_nodes.append(ids)
    way_id = -1000
    for ids in way_nodes:
        lines.append(f"  <way id='{way_id}' action='modify' visible='true'>")
        for nid in ids + [ids[0]]:
            lines.append(f"    <nd ref='{nid}' />")
        lines.append("    <tag k='o4_feature' v='bank_foot' />")
        lines.append("  </way>")
        way_id -= 1
    lines.append("</osm>")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ZZZZ_auto.patch.osm").write_text("\n".join(lines))
    return directory


def test_tile_origin_parses_the_patch_directory_name():
    assert PSS.tile_origin("Patches/+30+030/+30+031") == (30, 31)
    assert PSS.tile_origin("/a/b/-13-078") == (-13, -78)


def test_an_honest_ring_seals(tmp_path, monkeypatch):
    directory = _write_patch(tmp_path / "+30+031",
                             [[(0.10, 0.10), (0.11, 0.10),
                               (0.11, 0.11), (0.10, 0.11), (0.10, 0.10)]])
    monkeypatch.chdir(ROOT)
    assert PSS.main([str(directory)]) == 0


def test_the_nanometre_pair_is_refused_a_seed_and_still_seals(
        tmp_path, monkeypatch, capsys):
    """The HECA class: the sliver between two ways 2.7 nanometres apart is
    refused a seed (so the audit passes), and ``--faces`` names it."""
    rings = [[A, D] + FAR + [A], [A, _extra_node(), D] + FAR + [A]]
    directory = _write_patch(tmp_path / "+30+031", rings)
    monkeypatch.chdir(ROOT)

    assert PSS.main([str(directory), "--faces"]) == 0

    out = capsys.readouterr().out
    assert "1 face(s) refused a seed" in out
    assert "refused  area" in out


def test_the_cli_reports_no_closed_ways(tmp_path, monkeypatch, capsys):
    empty = tmp_path / "+30+031"
    empty.mkdir(parents=True)
    monkeypatch.chdir(ROOT)
    assert PSS.main([str(empty)]) == 0
    assert "no closed patch ways" in capsys.readouterr().out
