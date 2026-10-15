"""``pack_outlines`` (protocol 1.12, patch-editor spec §2 as amended before
L4): a synthetic X-Plane folder and pack apt.dat in ``tmp_path`` — a
pavement with a bezier exterior and a hole, and a boundary — never the
shared data repo, never an install.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from o4_engine import pack_objects as PO  # noqa: E402
from o4_engine import pack_outlines as POL  # noqa: E402

TILE = "+45-123"

APT = """I
1100 Version

1 200 0 0 ZZZZ Synthetic
110 1 0.25 0.00 Apron with a hole
112 45.2000 -122.9500 45.1990 -122.9480
111 45.2000 -122.9400
111 45.2100 -122.9400
113 45.2100 -122.9500
111 45.2040 -122.9460
111 45.2040 -122.9440
111 45.2060 -122.9440
113 45.2060 -122.9460
130 Airport boundary
111 45.1990 -122.9510
111 45.1990 -122.9390
111 45.2110 -122.9390
113 45.2110 -122.9510
1 300 0 0 YYYY Other
99
"""


@pytest.fixture
def xp(tmp_path, monkeypatch):
    xp = tmp_path / "X-Plane"
    ned = xp / "Custom Scenery" / "ZZ Pack" / "Earth nav data"
    ned.mkdir(parents=True)
    (ned / "apt.dat").write_text(APT, encoding="utf-8", newline="\n")
    monkeypatch.setattr(PO, "xplane_root_for", lambda lat, lon: str(xp))
    return xp


def test_pavement_bezier_flattened_hole_kept_and_boundary(xp):
    r = POL.pack_outlines(TILE, "zzzz")
    assert r["missing"] == []
    assert [p["kind"] for p in r["pavement"]] == ["pavement", "boundary"]
    pave = r["pavement"][0]["rings"]
    assert len(pave) == 2                                 # exterior + one hole
    exterior, hole = pave
    assert len(exterior) > 4                              # the bezier edge was flattened
    assert len(hole) == 4
    assert [45.204, -122.946] in hole                     # [lat, lon], hole intact
    # the flattened edge bulges south of the straight chord at lat 45.2
    assert min(p[0] for p in exterior) < 45.2
    assert all(45.19 < p[0] < 45.22 and -122.96 < p[1] < -122.93 for p in exterior)
    assert len(r["pavement"][1]["rings"]) == 1
    json.dumps(r)                                         # wire-serialisable


def test_missing_sentences(xp, monkeypatch):
    r = POL.pack_outlines(TILE, "YYYY")                   # an airport with no row 110
    assert r["pavement"] == [] and "no pavement" in r["missing"][0]
    r = POL.pack_outlines(TILE, "QQQQ")
    assert r["pavement"] == [] and r["missing"][0].startswith("No scenery pack serves QQQQ")
    monkeypatch.setattr(PO, "xplane_root_for", lambda lat, lon: None)
    assert "No X-Plane folder" in POL.pack_outlines(TILE, "ZZZZ")["missing"][0]


def test_bad_tile_is_an_error(xp):
    with pytest.raises(ValueError, match="tile key"):
        POL.pack_outlines("north", "ZZZZ")


def test_registered_in_the_jsonl_table():
    from o4_engine import jsonl
    handlers = jsonl._build_handlers(object.__new__(jsonl.EngineSession))
    assert handlers["pack_outlines"] is POL.pack_outlines
