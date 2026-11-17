"""Twin of ``tools/apron_census.py`` (lane lkbna15, #2112/#2134)."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import apron_census as AC  # noqa: E402
from auto_patch_v2.classify import load_rules  # noqa: E402


def test_pack_page_path_names_its_taxiway():
    r = load_rules()
    assert AC.pack_name_taxi("Pavement/Taxiways/Concrete/KBNA_Taxiway-H.pol", r) == "taxiway H"
    assert AC.pack_name_taxi("Pavement/Patio/Concrete_apron.pol", r) == ""


def test_reasons_follow_the_evidence():
    assert AC.apron_reason({"apron_cover_refused_corridor": 1.0}, "pav1").startswith("§40(2)")
    assert AC.apron_reason({"airside_edge_flip": 1.0, "airside_edge_was": "parking_lot"},
                           "dsf:pol1") == "§27 airside-edge flip (was parking_lot)"
    assert AC.apron_reason({}, "gapapron:3") == "gap_apron(§59)"


class _Frame:
    def transformers(self):
        return (lambda lon, lat: (lon, lat)), (lambda x, y: (y * 1e-5, x * 1e-5))


def _cell(i, x0, ev):
    ring = ((x0, 0), (x0 + 10, 0), (x0 + 10, 100), (x0, 100))
    return NS(id=i, role="apron", ref="pav1", ring=ring, holes=(), evidence=ev)


def test_lists_route_cells_without_stands_only():
    cl = NS(cells=(_cell(1, 0, {"apron_cover_refused_corridor": 1.0, "cell_apron_cover": 0.2}),
                   _cell(2, 20, {}),                     # a route, but a stand on it
                   _cell(3, 40, {})),                    # no route, no taxiway name
            cut_lines=(NS(kind="taxi_centerline", points=((5, 0), (5, 100))),
                       NS(kind="taxi_centerline", points=((25, 0), (25, 100)))),
            sources=())
    ap = NS(frame=_Frame(), startups=(NS(xy=(25, 50)),), osm_ways=())
    rec = AC.census("TEST", ap, cl)
    assert rec["n_apron"] == 3
    assert [r["id"] for r in rec["rows"]] == [1]
    assert rec["rows"][0]["cover"] == 0.2 and rec["rows"][0]["taxi_m"] >= 100
