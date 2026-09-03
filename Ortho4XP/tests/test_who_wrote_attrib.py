"""Twins for ``tools/harness/who_wrote.py``'s R1.1 attribution half:
the vertex-history probe (``--vertex-dump``) and the NO-BUILD
``--cert-attrib`` reader.  Headless, synthetic, no build."""
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "harness"))

import who_wrote as WW  # noqa: E402


@dataclass
class _Shape:
    role: str = "apron"
    ref: str = ""
    polygon: object = None
    node_altitudes: list = field(default=None)


class _Poly:
    geom_type = "Polygon"
    is_empty = False

    def __init__(self, coords):
        self.exterior = type("E", (), {"coords": coords})()


def test_vertex_history_records_changes_and_skips_replace_carries():
    probe = WW.AuthorshipProbe(_Shape, track_vertices=True,
                               author_tol=0.01)
    coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 0.0)]
    s = _Shape(role="apron", ref="A", polygon=_Poly(coords))
    probe._record(s, [1.0, 2.0, 3.0, 1.0])            # origin
    probe._record(s, [1.0, 2.5, 3.0, 1.0])            # one change
    s2 = _Shape(role="apron", ref="A", polygon=_Poly(coords))
    probe._record(s2, [1.0, 2.5, 3.0, 1.0])           # replace: carry
    probe._record(s2, [1.0, 2.5, 9.0, 1.0])           # change at k=2
    k1 = ("apron", "A", 10.0, 0.0)
    k2 = ("apron", "A", 10.0, 10.0)
    assert [v for _, v in probe.vhist[k1]] == [2.0, 2.5]
    assert [v for _, v in probe.vhist[k2]] == [3.0, 9.0]
    assert len(probe.site_list) >= 1


def test_vertex_dump_roundtrip(tmp_path):
    probe = WW.AuthorshipProbe(_Shape, track_vertices=True)
    s = _Shape(polygon=_Poly([(0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]))
    probe._record(s, [5.0, 6.0, 5.0])
    out = probe.write_vertex_dump(tmp_path / "v.jsonl")
    assert out["vertices"] == 2
    sites, index = WW.load_vertex_dump(tmp_path / "v.jsonl")
    assert len(sites) == out["sites"]
    assert index[(1.0, 0.0)][0]["final"] == 6.0


def _sites():
    return [
        "solve.py:6246:solve_route_profile <- solver.py:29:solve <- "
        "pipeline.py:6652:solve_and_finalize",
        "pipeline.py:7127:solve_and_finalize <- pipeline.py:4351:<lambda>",
        "solve.py:10859:final_grade_projection <- "
        "pipeline.py:7285:solve_and_finalize",
        "conformance.py:1824:planarize_airside <- "
        "pipeline.py:7363:_post_projection_conformance_passes",
    ]


def _vertex(role, x, y, hist, ref=""):
    return {"kind": "vertex", "role": role, "ref": ref, "x": x, "y": y,
            "hist": hist, "final": hist[-1][1],
            "solved": next((v for si, v in reversed(hist) if si == 0),
                           None), "last_site": hist[-1][0]}


def test_stage_and_endpoint_state():
    sites = _sites()
    assert WW.stage_of_site(sites[0]) == "solve@6246"
    assert WW.stage_of_site(sites[1]) == "pipeline@7127"
    assert WW.stage_of_site(sites[2]) == "fgp"
    assert WW.stage_of_site(sites[3]) == "planarize_airside"
    recs = [_vertex("apron", 1.0, 1.0,
                    [[0, 10.0], [1, 10.2], [2, 11.0], [3, 11.0]])]
    st = WW.endpoint_state(recs, sites, fgp_line=7285)
    assert st["last_stage"] == "pipeline@7127"
    assert st["fgp_moved"] and abs(st["fgp_dm"] - 0.8) < 1e-9
    assert st["solved"] == 10.0
    # no FGP entry: the pipeline line orders pre/post
    st2 = WW.endpoint_state(
        [_vertex("apron", 1.0, 1.0, [[0, 10.0], [3, 12.0]])],
        sites, fgp_line=7285)
    assert st2["last_stage"] == "solve@6246" and not st2["fgp_moved"]


def test_cert_attrib_groups_and_dispositions(tmp_path):
    sites = _sites()
    vd = tmp_path / "v.jsonl"
    with vd.open("w") as fh:
        fh.write(json.dumps({"kind": "meta", "sites": sites,
                             "tol_m": 0.01,
                             "solve_site": "solve_route_profile"}) + "\n")
        for r in (
            _vertex("apron", 0.0, 0.0, [[0, 10.0], [2, 11.0]]),
            _vertex("apron", 5.0, 0.0, [[0, 10.0]]),
            _vertex("service_junction", 20.0, 0.0, [[0, 3.0], [1, 3.5]]),
            _vertex("apron", 25.0, 0.0, [[0, 3.0]]),
            _vertex("junction", 40.0, 0.0, [[0, 7.0]]),
            _vertex("runway", 45.0, 0.0, [[0, 7.0]]),
        ):
            fh.write(json.dumps(r) + "\n")
    rows = [
        {"family": "unified:apron", "idx": [0, 1], "excess_m": 0.5,
         "both_hard": False, "mixed": False, "hard": [False, False],
         "xy": [[0.0, 0.0], [5.0, 0.0]], "ll": [[1, 1], [1, 2]],
         "pins": [None, None]},
        {"family": "service_junction:-", "idx": [2, 3], "excess_m": 0.9,
         "both_hard": False, "mixed": True, "hard": [True, False],
         "xy": [[20.0, 0.0], [25.0, 0.0]], "pins": ["svc_free_end", None]},
        {"family": "unified:junction", "idx": [4, 5], "excess_m": 0.2,
         "both_hard": False, "mixed": False, "hard": [False, True],
         "xy": [[40.0, 0.0], [45.0, 0.0]], "pins": [None, "runway_node"]},
        {"family": "transverse", "idx": [0, 1, 4, 5], "excess_m": 0.1,
         "both_hard": False, "mixed": False, "hard": [False] * 4,
         "xy": [[0.0, 0.0], [5.0, 0.0], [40.0, 0.0], [45.0, 0.0]],
         "pins": [None] * 4},
    ]
    cert = tmp_path / "c.json"
    cert.write_text(json.dumps({"tag": "final1_exit", "n_over": 4,
                                "rows": rows}))
    base = tmp_path / "b.json"
    base.write_text(json.dumps({"tag": "solve_exit", "n_over": 1,
                                "rows": [rows[1]]}))
    out = WW.attribute_certificate(cert, vd, base_paths=[f"solve={base}"])
    s = out["summary"]
    assert s["n_rows"] == 4 and s["endpoints_unjoined"] == 0
    assert s["fgp_pipeline_line"] == 7285
    assert s["rows_with_fgp_moved_endpoint"] == 2   # apron row + transect
    assert s["by_membership"] == {"solve": 1}
    disp = {r["family"]: r["disposition"] for r in out["rows"]}
    assert disp["unified:apron"].startswith("closes:S2")
    assert disp["service_junction:-"] == \
        "closes:S1-hold-release (svc_free_end)"
    assert disp["unified:junction"] == "senior-protected (runway_node)"
    assert disp["transverse"].startswith("closes:S1")
    g = {(x["family"], x["pair"]): x for x in out["groups"]}
    assert g[("apron", "apron|apron")]["last_stage"] == "solve@6246"
    assert g[("apron", "apron|apron")]["fgp_moved"] is True
    assert g[("service_junction", "apron|service_junction")]["member"] \
        == {"solve": 1}
    md = WW.render_attribution_md(out)
    assert "| apron | apron|apron |" in md


def test_cert_attrib_cli_is_no_build(tmp_path, capsys):
    vd = tmp_path / "v.jsonl"
    vd.write_text(json.dumps({"kind": "meta", "sites": _sites(),
                              "tol_m": 0.01,
                              "solve_site": "solve_route_profile"}) + "\n")
    cert = tmp_path / "c.json"
    cert.write_text(json.dumps({"tag": "final1_exit", "n_over": 0,
                                "rows": []}))
    rc = WW.main(["--cert-attrib", str(cert), "--vertex-json", str(vd),
                  "--attrib-md", str(tmp_path / "t.md")])
    assert rc == 0
    assert (tmp_path / "t.md").exists()
    with pytest.raises(SystemExit):
        WW.main(["--cert-attrib", str(cert)])
