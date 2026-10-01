"""``tools/elevation_gap_census.py --providers`` / ``--override`` (spec
us-holder-providers §5/§6.1, issue #154): the would-deliver rung per HOLDER
row read from the ENGINE's ladder (never a second registry), judged from
recorded discovery only (``--offline``: no GET at all), and the override
CSV reclassifying a false holder.  No network."""

import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _census():
    spec = importlib.util.spec_from_file_location(
        "gap_census_twin", ROOT / "tools" / "elevation_gap_census.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gap_census_twin"] = mod
    spec.loader.exec_module(mod)
    return mod


FIELDS = ["icao", "name", "state", "longest_rwy_m", "lat", "lon",
          "tnm_1m_pct", "ned19_3m_pct", "verdict"]


def _gaps(tmp_path):
    rows = [
        # NC: no 1 m, 1/9" whole -> the 3 m rung.
        ["KRDU", "Raleigh", "North Carolina", 3051, 35.87804, -78.7868,
         0.0, 100.0, "HOLDER"],
        # Aspen: no USGS 1 m, no 1/9" -> PITKIN1M (boxed to the county).
        ["KASE", "Aspen", "Colorado", 2448, 39.22, -106.86636, 0.0, 0.0,
         "HOLDER"],
        # Sells: a false USIEI holder; the override makes it NOBODY.
        ["E78", "Sells", "", 1779, 31.93065, -111.89722, 0.0, 0.0,
         "HOLDER"],
        ["KXXX", "Not a holder", "", 2000, 40.0, -100.0, 90.0, 100.0,
         "USGS-LPC/OPR"],
    ]
    path = tmp_path / "gaps.csv"
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        w.writerows(rows)
    override = tmp_path / "override.csv"
    override.write_text("icao,verdict,reason\nE78,NOBODY,pima hole\n")
    return path, override


def test_providers_mode_reads_the_engine_ladder_offline(tmp_path, monkeypatch,
                                                       capsys):
    mod = _census()
    gaps, override = _gaps(tmp_path)
    out = tmp_path / "providers.csv"
    monkeypatch.setattr(sys, "argv", [
        "elevation_gap_census.py", "--providers", "--offline",
        "--gaps", str(gaps), "--override", str(override),
        "--tnm-cache", str(tmp_path / "cache"),
        "--providers-out", str(out)])
    mod.main()
    printed = capsys.readouterr().out
    assert "E78: HOLDER -> NOBODY (pima hole)" in printed
    assert "HOLDER rows 2" in printed
    with open(out, newline="") as fh:
        rows = {r["icao"]: r for r in csv.DictReader(fh)}
    assert set(rows) == {"KRDU", "KASE"}
    assert rows["KRDU"]["would_deliver"] == "1/9 arc-second"
    assert rows["KRDU"]["would_deliver_provider"] == "USGS3DEP"
    assert rows["KASE"]["would_deliver_provider"] == "PITKIN1M"
    # Coverage-boxed: PITKIN is no rung at KRDU at all.
    assert "PITKIN1M" not in rows["KRDU"]["rungs"]
    # The unrecorded 1/3" listing was never fetched offline.
    assert "1/3 arc-second [USGS3DEP] unrecorded" in rows["KRDU"]["rungs"]
    assert not (tmp_path / "cache").exists()


def test_override_rejects_an_unknown_verdict(tmp_path):
    mod = _census()
    bad = tmp_path / "o.csv"
    bad.write_text("icao,verdict,reason\nE78,MAYBE,x\n")
    try:
        mod.read_overrides(str(bad))
    except SystemExit as exit_:
        assert "MAYBE" in str(exit_)
    else:
        raise AssertionError("an unknown verdict was accepted")


def test_tnm_dataset_key_recognises_the_opr_and_lpc_rungs():
    """#153: OPR (tnm_cog) and LPC (las_tile_index, index_format=tnm) are
    TNM listings and are judged from them, never as an authoritative
    coverage box (which would 'deliver' every US airport)."""
    mod = _census()
    opr = {"access_strategy": "tnm_cog",
           "discovery_url_template": "https://x/products?datasets=Original Product"
                                     " Resolution (OPR) Digital Elevation Model (DEM)&bbox={west}"}
    lpc = {"access_strategy": "las_tile_index", "index_format": "tnm",
           "index_url_template": "https://x/products?datasets=Lidar Point Cloud (LPC)&bbox={west}"}
    boxed = {"access_strategy": "las_tile_index", "index_format": "gpkg",
             "index_url_template": "https://x/index.gpkg"}
    assert mod._tnm_dataset_key(opr) == "opr"
    assert mod._tnm_dataset_key(lpc) == "lpc"
    assert mod._tnm_dataset_key(boxed) is None
