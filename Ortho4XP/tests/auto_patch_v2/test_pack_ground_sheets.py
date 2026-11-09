"""LARGE DRAPED GROUND TEXTURES A PACK LAYS OVER ITS AIRPORT (#1962,
RULINGS 2026-11-09a (3)): the coverage witness, the shared omission with
the photos, and the companion pack that lays an airport's photo grid
(#1968).

A ground sheet is the pack's own draped polygon, with no SURFACE, over the
airport, at least ten hectares, MOSTLY OFF PAVEMENT (the apt.dat's paved
runways and pavement, the pack's paved draped polygons).  A painted apron,
a sheet with a surface, a small patch, a sheet off the airport and a
photo-grid tile are never one.  Synthetic packs; no network, no corpus.
"""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import pack_art as PA
from auto_patch_v2.airport import pack_drapes as PD
from auto_patch_v2.airport import pack_ground_sheets as GS

# a 2.2 km runway, 45 m wide, east-west along lat 25.000, lon 51.000-51.022,
# and a 300 m x 200 m paved apron north of it
APT = ("I\n1100 test\n\n1      12 0 0 OTST Test Field\n"
       "100 45.00 1 0 0.25 0 2 0 09 25.00000 51.00000 0 0 1 0 0 0 "
       "27 25.00000 51.02200 0 0 1 0 0 0\n"
       "110 1 0.25 0 apron\n111 25.0010 51.0080\n111 25.0010 51.0110\n"
       "111 25.0028 51.0110\n113 25.0028 51.0080\n99\n")
POLS = {
    "ground/grass.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE grass.png\n"
                        "SCALE 100 100\nLAYER_GROUP runways -3\n",
    "ground/painted.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP painted.png\n"
                          "DECAL_LIB lib/g10/decals/grass.dcl\nSCALE 1 1\n"
                          "LAYER_GROUP markings -30\n",
    "ground/apron.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP apron.png\n"
                        "SCALE 1 1\nLAYER_GROUP markings -2\n",
    "ground/turf.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE turf.dds\n"
                       "SURFACE grass\nSCALE 5 5\n",
    "ground/grime.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP grime.png\n"
                        "WEATHER_TRANSPARENT\nSCALE 25 25\n",
    "ground/concrete.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE concrete.png\n"
                           "SURFACE concrete\nSCALE 25 25\n",
    **{f"grid/Tile{n}.pol": f"A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP Tile{n}.dds\n"
                            "SCALE 25 25\nLOAD_CENTER 25.0 51.0 300 2048\n"
                            "LAYER_GROUP terrain 1\n" for n in range(1, 5)},
}


def _box(lon0, lat0, lon1, lat1, hole=None):
    return (lon0, lat0, lon1, lat1, hole)


#: def index -> (path, the polygons (lon0, lat0, lon1, lat1[, hole]))
SHEET = _box(50.995, 24.990, 51.027, 25.010)                  # ~720 ha
PAD = (51.002, 25.003, 51.012, 25.0066)        # the pack's 40 ha of concrete
AROUND = (51.000, 25.0025, 51.014, 25.0071)    # 72 ha around it
DEFS = [
    ("ground/grass.pol", [SHEET]),                            # 0 a sheet
    ("ground/painted.pol", [_box(50.996, 24.995, 51.026, 25.006,
                                 (51.0, 24.999, 51.02, 25.001))]),  # 1 holed
    ("ground/apron.pol", [_box(51.0080, 25.0010, 51.0110, 25.0028)]),  # 2 apron
    ("ground/turf.pol", [SHEET]),                             # 3 has a SURFACE
    ("ground/grime.pol", [SHEET]),                            # 4 see-through
    ("ground/grass.pol", []),                                 # 5 (unused)
    ("ground/painted.pol", [_box(51.500, 25.500, 51.530, 25.520)]),  # 6 off
    ("ground/grass.pol", [_box(51.001, 25.002, 51.003, 25.004)]),    # 7 small
    ("lib/g10/terrain/grass.pol", [SHEET]),                   # 8 library
    ("ground/concrete.pol", [_box(*PAD)]),                    # 9 paved
    ("ground/apron.pol", [_box(*PAD)]),                       # 10 on it
] + [(f"grid/Tile{n + 1}.pol",                                # 11-14 a grid
      [_box(51.0 + 0.01 * (n % 2), 24.99 + 0.01 * (n // 2),
            51.01 + 0.01 * (n % 2), 25.0 + 0.01 * (n // 2))]) for n in range(4)]


def _ring(lon0, lat0, lon1, lat1):
    return "BEGIN_WINDING\n" + "".join(
        f"POLYGON_POINT {x:.6f} {y:.6f} {u} {v}\n" for x, y, u, v in (
            (lon0, lat0, 0, 0), (lon1, lat0, 1, 0), (lon1, lat1, 1, 1),
            (lon0, lat1, 0, 1))) + "END_WINDING\n"


def _dump(defs=DEFS) -> list[str]:
    text = "".join(f"POLYGON_DEF {p}\n" for p, _b in defs)
    for i, (_p, boxes) in enumerate(defs):
        for lon0, lat0, lon1, lat1, hole in boxes:
            text += (f"BEGIN_POLYGON {i} 65535 4\n" + _ring(lon0, lat0, lon1, lat1)
                     + (_ring(*hole) if hole else "") + "END_POLYGON\n")
    return text.splitlines(True)


@pytest.fixture
def pack(tmp_path):
    root = tmp_path / "Custom Scenery" / "Ground Pack"
    for rel, text in POLS.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8", newline="")
    nav = root / "Earth nav data"
    nav.mkdir()
    (nav / "apt.dat").write_text(APT, encoding="utf-8", newline="")
    return root


def _sheets(pack, defs=DEFS):
    apt = str(pack / "Earth nav data" / "apt.dat")
    return GS.ground_sheets(str(pack), _dump(defs), [apt],
                            [b for b, _ok in PD.airport_boxes(apt)])


def test_the_sheets_mostly_off_pavement_are_found(pack):
    found = _sheets(pack)
    assert [(m.index, m.path, m.uses) for m in found] == [
        (0, "ground/grass.pol", 1), (1, "ground/painted.pol", 1)]
    assert all(m.kind == "polygon" for m in found)


def test_what_is_never_a_sheet(pack):
    found = {m.index for m in _sheets(pack)}
    assert not found & {2, 10}, "a painted apron lies on pavement"
    assert 3 not in found, "a SURFACE is the author's ground"
    assert 4 not in found, "a weather-transparent overlay"
    assert 6 not in found, "off the airport"
    assert 7 not in found, "under ten hectares"
    assert 8 not in found, "a library polygon"
    assert 9 not in found, "pavement itself"
    assert not found & {11, 12, 13, 14}, "photo-grid tiles are the photo rule's"


def test_the_coverage_is_the_witness_not_the_size(pack):
    """The same 72 ha painted sheet is a ground sheet alone, and none once
    the pack's own concrete lies under most of it."""
    sheet = ("ground/painted.pol", [_box(*AROUND)])
    assert [m.index for m in _sheets(pack, [sheet])] == [0]
    assert _sheets(pack, [sheet, DEFS[9]]) == (), "56 % of it on concrete"


def test_holes_are_taken_out(pack):
    """The sheet with the concrete cut out of it lies all off pavement."""
    ring = ("ground/painted.pol", [_box(*AROUND, PAD)])
    assert [m.index for m in _sheets(pack, [ring, DEFS[9]])] == [0]


def test_without_an_airport_nothing_is_found(pack):
    assert GS.ground_sheets(str(pack), _dump(), [], []) == ()


# ── the stage: one record, two kinds ────────────────────────────────────

PHOTO = PA.MissingDef("polygon", 11, "grid/Tile1.pol", 1)
GRASS = PA.MissingDef("polygon", 0, "ground/grass.pol", 1)


@pytest.fixture
def stage(monkeypatch):
    import O4_UI_Utils as UI
    from auto_patch import drape_stage as DS
    from auto_patch import pack_rewrite as PR
    writes: list = []
    monkeypatch.setattr(PR, "rewrite_dsf", lambda root, name, dsf, drapes:
                        writes.append(tuple(drapes)) or dsf + ".anchor_bak")
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    return types.SimpleNamespace(DS=DS, writes=writes)


def test_hiding_one_kind_keeps_the_other(stage):
    DS = stage.DS
    pd = DS.PackDrapes("P", "/p/+25+051.dsf", (GRASS,), (PHOTO,), (PHOTO,))
    assert not pd.current and pd.keep == (PHOTO,)
    assert DS._hide(pd, "/p", DS.GROUND) == "hidden"
    assert stage.writes == [(PHOTO, GRASS)], "the photos stay hidden"
    done = DS.PackDrapes("P", "/p/+25+051.dsf", (GRASS,), (PHOTO, GRASS), (PHOTO,))
    assert done.current


def test_a_stale_hiding_is_not_current(stage):
    DS = stage.DS
    old = PA.MissingDef("polygon", 9, "gone.pol", 1)
    pd = DS.PackDrapes("P", "/p/+25+051.dsf", (GRASS,), (GRASS, old), (PHOTO,))
    assert not pd.current and pd.keep == ()
    DS._hide(pd, "/p", DS.GROUND)
    assert stage.writes == [(GRASS,)], "what no kind claims any more goes"


def test_undo_of_one_kind_rewrites_with_the_other(stage, monkeypatch):
    DS = stage.DS
    from auto_patch import pack_rewrite as PR
    calls = {}

    def undo_recorded(root, lat, lon, key, rewrite, keeps=None):
        if calls.get("ask", True):        # nothing else of ours: it asks
            calls["keeps"] = keeps("/p/Earth nav data/+20+050/+25+051.dsf")
        rewrite("/p/Earth nav data/+20+050/+25+051.dsf")
        return ["Earth nav data/+20+050/+25+051.dsf"]

    monkeypatch.setattr(PR, "undo_recorded", undo_recorded)
    monkeypatch.setattr(DS, "_check", lambda root, lat, lon, *, read_only, kind:
                        DS.PackDrapes("P", "/p/x.dsf", (GRASS,), (PHOTO, GRASS),
                                      (PHOTO,)) if (lat, lon) == (25, 51) else None)
    assert DS.undo("/p", kind=DS.GROUND) == ["Earth nav data/+20+050/+25+051.dsf"]
    assert calls["keeps"] is True
    assert stage.writes == [(PHOTO,)], "the photos stay hidden, the grass is back"
    calls["ask"] = False                  # placements of ours: no question
    DS.undo("/p", kind=DS.GROUND)
    assert stage.writes[-1] == (PHOTO,), "the rewrite reads the kept part itself"


# ── the tile's scan (#1968, RULINGS 2026-11-09a (9)) ────────────────────

def test_the_scan_is_every_airport_pack_and_companion(pack, tmp_path):
    from auto_patch import drape_stage as DS
    scenery = pack.parent
    for name, apt, pols in (("Overlay", "", 4), ("Hospital", "17 0 0 0 H1 Pad\n", 4),
                            ("Other Airport", APT, 4), ("Bare", "", 1)):
        root = scenery / name
        (root / "Earth nav data" / "+20+050").mkdir(parents=True)
        (root / "Earth nav data" / "+20+050" / "+25+051.dsf").write_bytes(b"")
        if apt:
            (root / "Earth nav data" / "apt.dat").write_text(apt, encoding="utf-8", newline="")
        for n in range(pols):
            (root / f"o{n}.pol").write_text(POLS["grid/Tile1.pol"], encoding="utf-8", newline="")
    (pack / "Earth nav data" / "+20+050").mkdir()
    (pack / "Earth nav data" / "+20+050" / "+25+051.dsf").write_bytes(b"")
    got = sorted(p.rsplit("/", 1)[-1] for p in DS.scanned(str(scenery), 25, 51))
    assert got == sorted(["Hospital", "Other Airport", "Overlay", pack.name]), \
        "every airport pack, built or not; a runway-less pack with one .pol is no grid"
    boxes, bounded, apts = DS._airports(str(scenery / "Overlay"), 25, 51)
    assert len(apts) == 2 and len(boxes) == 2 and bounded == [False, False], \
        "judged against the tile's airport packs"
