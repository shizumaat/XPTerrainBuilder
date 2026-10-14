"""Twin for ``tools/tunnel_mouth_depths.py`` (lane ``mouth75``, owner
RULINGS 2026-10-14f): on a two-way synthetic patch — one ``tunnel_ramp``
ring falling 7.5 m to its mouth, one ``structure_rim`` at the ground over
it — the table reads the depth rim − floor, the floor's place, and pairs
it with a 5.1 m reference mouth by the nearest floor."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tunnel_mouth_depths as T  # noqa: E402


def _patch(path: Path, depth: float) -> Path:
    # a 100 m ramp along +lon at lat 0, mouth (floor) at lon 0, rim at the mouth
    dlon = 100.0 / 111320.0
    nodes = [(-1, 0.0, 0.0, 10.0 - depth), (-2, 0.0, dlon, 10.0), (-3, 1e-4, dlon, 10.0),
             (-4, 1e-4, 0.0, 10.0 - depth), (-5, -2e-5, -2e-5, 10.0), (-6, 1.2e-4, -2e-5, 10.0)]
    txt = ["<osm>"]
    for nid, la, lo, z in nodes:
        txt.append(f"  <node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'>\n"
                   f"    <tag k='alt_abs' v='{z:.3f}' />\n  </node>")
    txt.append("  <way id='-10'>" + "".join(f"<nd ref='{n}' />" for n in (-1, -2, -3, -4, -1))
               + "<tag k='role' v='tunnel_ramp' /><tag k='ref' v='tunnel_ramp' /></way>")
    txt.append("  <way id='-11'>" + "".join(f"<nd ref='{n}' />" for n in (-5, -6))
               + "<tag k='o4_feature' v='structure_rim' /></way>")
    txt.append("</osm>")
    path.write_text("\n".join(txt))
    return path


def test_the_table_reads_rim_minus_floor_and_pairs_the_reference(tmp_path):
    new = T.mouth_rows(_patch(tmp_path / "new.osm", 7.5))
    ref = T.mouth_rows(_patch(tmp_path / "ref.osm", 5.1))
    assert len(new) == 1 and new[0]["depth_m"] == pytest.approx(7.5)
    assert ref[0]["depth_m"] == pytest.approx(5.1)
    assert new[0]["extent_m"] == pytest.approx(100.0, abs=1.5)
    assert new[0]["grade"] == pytest.approx(0.075, abs=0.002)
    rows = T.pair_rows(new, ref, 30.0)
    assert len(rows) == 1 and rows[0]["ref"]["depth_m"] == pytest.approx(5.1)
    assert T.main([str(tmp_path / "new.osm"), "--ref", str(tmp_path / "ref.osm")]) == 0
