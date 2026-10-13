"""Twin of ``tools/bore_table.py`` — the wrapper changes no verdict and logs
the readings; the diff names an unexpected verdict change."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import bore_table  # noqa: E402


def _row(ids, built, passage=None):
    return {"ids": ids, "built": built, "why": "w", "len_m": 10.0, "cover_m": 0.0,
            "layer": None, "rise_m": 0.0, "passage": passage}


def test_the_wrapper_logs_each_bore_and_returns_the_engines_verdict():
    from auto_patch_v2.law import Law
    law = Law.for_airport("ZZZZ")
    pack = types.SimpleNamespace(passage=lambda ln, w, c: ("Terminals/link.obj", "unit:1", 3.4),
                                 at=lambda xy: None)
    service = types.SimpleNamespace(
        terrain_tunnel_witness=lambda ap, lw, of, ways: (lambda bore: (True, "under cover")),
        _PackBuildings=lambda *a: pack, _fence_of=lambda ap: None,
        _rise_m=lambda ap, ln: 0.123, _layer_of_bore=lambda b: -1,
        _osm_tunnel=lambda b, adm: True)
    airport = types.SimpleNamespace(frame=types.SimpleNamespace(
        transformers=lambda: (None, lambda x, y: (y / 1e5, x / 1e5))))
    field = types.SimpleNamespace(cover_run_m=lambda ln: 7.0)
    way = types.SimpleNamespace(id=-7, tags={"highway": "service", "tunnel": "yes"})
    bore = types.SimpleNamespace(line=LineString([(0, 0), (30, 0)]), ways=[way],
                                 points=[(0.0, 0.0), (30.0, 0.0)])
    rows: list = []
    witness = bore_table.logged(service, rows)(airport, law, field, ())
    assert witness(bore) == (True, "under cover")
    assert len(rows) == 1 and rows[0]["ids"] == "-7" and rows[0]["built"] is True
    assert rows[0]["layer"] == -1 and rows[0]["cover_m"] == 7.0 and rows[0]["rise_m"] == 0.12
    assert rows[0]["passage"] == ["Terminals/link.obj", "unit:1", 3.4]


def test_the_diff_names_an_unexpected_verdict_change(tmp_path):
    base, branch = tmp_path / "a", tmp_path / "b"
    for d, second in ((base, True), (branch, False)):
        d.mkdir()
        (d / "ZZZZ.bores.json").write_text(json.dumps(
            [_row("-1", True), _row("-2+-3", second, ["x/deck.obj", "unit:2", 3.0])]),
            encoding="utf-8", newline="\n")
    lines, unexpected = bore_table.diff(base, branch, ["ZZZZ"])
    assert unexpected == ["ZZZZ -2+-3"] and "*** CHANGED" in lines[2] and "CHANGED" not in lines[1]
    assert "deck.obj @ 3.0 m" in lines[2]
    assert bore_table.diff(base, branch, ["ZZZZ"], {"-2+-3"})[1] == []
    assert bore_table.main(["diff", str(base), str(branch), "ZZZZ"]) == 1
    assert bore_table.main(["diff", str(base), str(branch), "ZZZZ", "--expect=-2+-3"]) == 0
