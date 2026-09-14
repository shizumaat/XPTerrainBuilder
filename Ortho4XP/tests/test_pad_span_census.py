"""Twin for ``tools/pad_span_census.py`` (§16g (1)/(7); owner RULINGS
2026-09-14c item 1, attributed 14g; promoted on its second use)."""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pad_span_census as PSC  # noqa: E402


def _graded(pads):
    """``pads`` = [(lat0, lon0, lat1, lon1, z, ref)] as building faces."""
    verts, faces = [], []
    for k, (a0, o0, a1, o1, z, ref) in enumerate(pads):
        base = len(verts)
        for a, o in ((a0, o0), (a1, o0), (a1, o1), (a0, o1)):
            verts.append([len(verts), a, o, z])
        faces.append({"id": 100 + k, "ref": ref, "role": "building",
                      "ring": [base, base + 1, base + 2, base + 3]})
    # one NON-building face, which the census must ignore
    base = len(verts)
    for a, o in ((40.10, -3.0), (40.11, -3.0), (40.11, -2.99), (40.10, -2.99)):
        verts.append([len(verts), a, o, 999.0])
    faces.append({"id": 900, "ref": "apron9", "role": "apron",
                  "ring": [base, base + 1, base + 2, base + 3]})
    return {"vertices": verts, "faces": faces}


def _plan(bodies):
    """``bodies`` = [(index, comp, foot lat, foot lon, unit_of)]."""
    rb = {"units": [{"id": "unit:0", "anchor": [40.0, -3.0], "agl_m": 0.0,
                     "members": []}]}
    splits = []
    for i, (idx, comp, fa, fo, uid) in enumerate(bodies):
        rb["units"][0]["members"].append({
            "id": f"dsf:obj{idx}", "resource": f"o/{idx}.obj",
            "authored_path": "", "live_path": "", "heading_deg": 0.0,
            "parts": [[i, comp, fa, fo, 0.0, 1.0, fa, fo, fa, fo,
                       [[fa, fo, 0.0]], False]]})
        splits.append({"placement": {"index": idx, "resource": f"o/{idx}.obj"},
                       "bodies": [{"body_id": "b0", "components": [comp],
                                   "unit_of": uid}]})
    return {"splits": splits}, rb


def test_the_pad_span_is_the_units_own_pads_and_nothing_else():
    """The row is a UNIT's pads: a unit standing on two pads 5 m apart is
    listed at 5 m, a unit on one pad is not a row at all, and the apron
    face is not a pad.  This is the reading 14g stated its bar in —
    HECA's `fu:38:20`, 136 pads spanning 34.8 m."""
    graded = _graded([(40.000, -3.000, 40.001, -2.999, 100.0, "b1"),
                      (40.002, -3.000, 40.003, -2.999, 105.0, "b2"),
                      (40.004, -3.000, 40.005, -2.999, 100.2, "b3")])
    pl, rb = _plan([(1, 0, 40.0005, -2.9995, "fu:0:0"),     # pad b1
                    (2, 0, 40.0025, -2.9995, "fu:0:0"),     # pad b2  -> 5 m
                    (3, 0, 40.0045, -2.9995, "fu:0:9"),     # pad b3
                    (4, 0, 40.1050, -2.9950, "fu:0:9")])    # the APRON
    res = PSC.census(pl, graded, rb, over_m=1.0)
    assert res["units_with_a_unit_of"] == 2
    # `fu:0:9` stands on ONE pad (the apron face is not one) -> not a row
    assert res["units_on_two_or_more_pads"] == 1
    assert res["units_over"] == 1 and res["bodies_in_units_over"] == 2
    row = res["rows"][0]
    assert row["unit"] == "fu:0:0" and row["pads"] == 2
    assert abs(row["span_m"] - 5.0) < 1e-6
    # the FLOOR is a listing floor, not a threshold with any standing
    assert PSC.census(pl, graded, rb, over_m=10.0)["units_over"] == 0
    # a body with no unit_of is not counted at all
    pl["splits"][0]["bodies"][0]["unit_of"] = ""
    assert PSC.census(pl, graded, rb, 1.0)["units_on_two_or_more_pads"] == 0


def test_the_cli_json_is_the_library_result_and_the_index_names_it():
    import io
    import contextlib
    import tempfile
    graded = _graded([(40.000, -3.000, 40.001, -2.999, 100.0, "b1"),
                      (40.002, -3.000, 40.003, -2.999, 105.0, "b2")])
    pl, rb = _plan([(1, 0, 40.0005, -2.9995, "fu:0:0"),
                    (2, 0, 40.0025, -2.9995, "fu:0:0")])
    with tempfile.TemporaryDirectory() as d:
        pp, gp, rp, op = (f"{d}/p.json", f"{d}/g.json", f"{d}/r.json",
                          f"{d}/o.json")
        json.dump(pl, open(pp, "w"))
        json.dump(graded, open(gp, "w"))
        json.dump(rb, open(rp, "w"))
        with contextlib.redirect_stdout(io.StringIO()):
            assert PSC.main([pp, gp, rp, "--json", op]) == 0
        assert json.load(open(op)) == PSC.census(pl, graded, rb, 1.0)
    idx = (ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "pad_span_census.py" in idx
