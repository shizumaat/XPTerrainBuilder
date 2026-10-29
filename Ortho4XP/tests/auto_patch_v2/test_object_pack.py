"""#1630: an airport whose block only Global Airports defines takes as its
OBJECT PACK the Custom Scenery pack drawn above Global Airports that places
its own objects inside the airport's boundary, even when that pack's
apt.dat defines another airport only (``airport/object_pack``).  The
selection's folder and name are that pack's; its apt.dat stays Global's.
"""
from __future__ import annotations

import os

import pytest
from auto_patch_v2.airport import apt_dat as A
from auto_patch_v2.airport import dsf as D
from auto_patch_v2.airport import object_pack as OP
from auto_patch_v2.airport import pack as P

TILE = (47, -123)
BLOCK = os.path.join("+40-130", "+47-123.dsf")
#: a synthetic airport: one boundary ring around (47.90, -122.28)
GLOBAL_APT = """I
1200 synthetic
1 184 0 0 ZQQA Test Field
100 45.00 1 0 0.25 1 2 0 16R 47.9200 -122.2800 0 0 3 0 0 0 34L 47.8900 -122.2800 0 0 3 0 0 0
130 boundary
111 47.880 -122.300
111 47.880 -122.260
111 47.930 -122.260
113 47.930 -122.300
99
"""
OTHER_APT = """I
1200 synthetic
1 100 0 0 ZQQB Elsewhere
100 45.00 1 0 0.25 1 2 0 16R 47.4600 -122.3000 0 0 3 0 0 0 34L 47.4400 -122.3000 0 0 3 0 0 0
99
"""


def _write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _dump_text(rows):
    defs = sorted({d for d, _lo, _la in rows})
    lines = ["I", "800", "DSF2TEXT", "", "PROPERTY sim/west -123",
             "PROPERTY sim/east -122", "PROPERTY sim/north 48", "PROPERTY sim/south 47"]
    lines += [f"OBJECT_DEF {d}" for d in defs]
    lines += [f"OBJECT {defs.index(d)} {lo:.9f} {la:.9f} 0.000000" for d, lo, la in rows]
    return "\n".join(lines) + "\n"


def _pack(xp, mods, name, rows, *, apt="", objs=("objects/tower.obj",), dumped=True):
    root = os.path.join(xp, "Custom Scenery", name)
    dsf = os.path.join(root, "Earth nav data", BLOCK)
    _write(dsf, "synthetic dsf " + name)
    if apt:
        _write(os.path.join(root, "Earth nav data", "apt.dat"), apt)
    for rel in objs:
        _write(os.path.join(root, rel))
    if dumped:
        cache = D.mod_cache_dir(mods, name)
        _write(os.path.join(cache, f"+47-123.dsf.{D.text_dump_tag(dsf)}.text"),
               _dump_text(rows))
    return root


def _install(tmp_path, ini_rows):
    xp, mods = str(tmp_path / "X-Plane"), str(tmp_path / "mods")
    _write(os.path.join(xp, "Global Scenery", "Global Airports", "Earth nav data",
                        "apt.dat"), GLOBAL_APT)
    os.makedirs(os.path.join(xp, "Custom Scenery"), exist_ok=True)
    _write(os.path.join(xp, "Custom Scenery", "scenery_packs.ini"),
           "I\n1000 Version\nSCENERY\n\n" + "".join(r + "\n" for r in ini_rows))
    return xp, mods


@pytest.fixture(autouse=True)
def _fresh_selection_maps():
    A._SELECTION.clear()
    OP._first_placing.cache_clear()
    yield


def _select(xp, mods, monkeypatch, icao="ZQQA"):
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "airport_mod_cache_root", lambda: mods)
    return P.select_pack(xp, icao)


ABOVE = ["SCENERY_PACK Custom Scenery/region pack/", "SCENERY_PACK *GLOBAL_AIRPORTS*"]
TOWER = [("objects/tower.obj", -122.279, 47.909)]


def test_a_pack_placing_its_own_objects_inside_the_airport_is_its_object_pack(
        tmp_path, monkeypatch):
    xp, mods = _install(tmp_path, ABOVE)
    root = _pack(xp, mods, "region pack", TOWER, apt=OTHER_APT)
    sel = _select(xp, mods, monkeypatch)
    assert (sel.name, sel.root) == ("region pack", root)
    # the block is still Global Airports' — nothing else defines the airport
    assert sel.apt_dat_path.endswith(os.path.join("Global Airports", "Earth nav data",
                                                  "apt.dat"))
    assert not sel.borrow.apt_dat_path
    # the signature names the pack's folder, so the plan and the DSF write land there
    block = A.read_airport_block(sel.apt_dat_path, "ZQQA")
    pack = P.signature(sel, block, *TILE)
    assert pack.pack_root == root and pack.name == "region pack"
    assert pack.dsf_paths == (os.path.join(root, "Earth nav data", BLOCK),)


def test_the_pack_serving_its_own_airport_is_unchanged(tmp_path, monkeypatch):
    xp, mods = _install(tmp_path, ABOVE)
    root = _pack(xp, mods, "region pack", TOWER, apt=OTHER_APT)
    sel = _select(xp, mods, monkeypatch, icao="ZQQB")
    assert sel.root == root and sel.apt_dat_path.startswith(root)
    block = A.read_airport_block(sel.apt_dat_path, "ZQQB")
    assert P.signature(sel, block, *TILE).root == ""      # derived from the apt.dat


@pytest.mark.parametrize("why, ini, rows, objs", [
    ("objects outside the boundary", ABOVE,
     [("objects/tower.obj", -122.30, 47.45)], ("objects/tower.obj",)),
    ("library objects only (an overlay)", ABOVE,
     [("lib/airport/tower.obj", -122.279, 47.909)], ("objects/other.obj",)),
    ("drawn below Global Airports", list(reversed(ABOVE)), TOWER, ("objects/tower.obj",)),
    ("disabled", ["SCENERY_PACK_DISABLED Custom Scenery/region pack/",
                  "SCENERY_PACK *GLOBAL_AIRPORTS*"], TOWER, ("objects/tower.obj",)),
])
def test_global_airports_stays_the_pack(tmp_path, monkeypatch, why, ini, rows, objs):
    xp, mods = _install(tmp_path, ini)
    _pack(xp, mods, "region pack", rows, apt=OTHER_APT, objs=objs)
    assert _select(xp, mods, monkeypatch).name == "Global Airports", why


def test_an_undumped_candidate_is_not_chosen_but_is_named_for_the_refresh(
        tmp_path, monkeypatch):
    xp, mods = _install(tmp_path, ABOVE)
    root = _pack(xp, mods, "region pack", TOWER, dumped=False)
    assert _select(xp, mods, monkeypatch).name == "Global Airports"
    # the pre-build refresh dumps exactly the candidates (engine_v2.fresh_pack_dump)
    assert OP.candidates(xp, *TILE) == [root]


def test_the_first_pack_in_priority_wins(tmp_path, monkeypatch):
    xp, mods = _install(tmp_path, ["SCENERY_PACK Custom Scenery/b higher/",
                                   "SCENERY_PACK Custom Scenery/a lower/",
                                   "SCENERY_PACK *GLOBAL_AIRPORTS*"])
    _pack(xp, mods, "a lower", TOWER)
    high = _pack(xp, mods, "b higher", TOWER)
    assert _select(xp, mods, monkeypatch).root == high


def test_names_above_global_airports_follows_the_ini(tmp_path):
    import O4_Scenery_Packs as SP
    scenery = tmp_path / "Custom Scenery"
    for n in ("new", "above", "below", "off"):
        (scenery / n).mkdir(parents=True)
    (scenery / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\nSCENERY_PACK Custom Scenery/above/\n"
        "SCENERY_PACK_DISABLED Custom Scenery/off/\nSCENERY_PACK *GLOBAL_AIRPORTS*\n"
        "SCENERY_PACK Custom Scenery/below/\n", encoding="utf-8", newline="\n")
    assert SP.names_above_global_airports(str(scenery)) == ["new", "above"]
    # parse_ini is unchanged by the Global row
    assert SP.parse_ini(str(scenery / "scenery_packs.ini")) == (["above", "below"], {"off"})


# ── owner Q284 (a): the object pack replaces Global Airports' OBJECTS only ──
PAGE = "lib/airport/pavement/asphalt_1L.pol"
TERMINAL = "lib/airport/Modern_Airports/Terminal_kit/term_building_1.fac"


def _polygon_dump(polys):
    """A DSF text dump of draped polygons ``(def, [(lon, lat), ...])``."""
    defs = sorted({d for d, _r in polys})
    lines = ["I", "800", "DSF2TEXT", ""] + [f"POLYGON_DEF {d}" for d in defs]
    for d, ring in polys:
        lines += [f"BEGIN_POLYGON {defs.index(d)} 0 2", "BEGIN_WINDING"]
        lines += [f"POLYGON_POINT {lo:.9f} {la:.9f}" for lo, la in ring]
        lines += ["END_WINDING", "END_POLYGON"]
    return "\n".join(lines) + "\n"


def _square(lon, lat, d=0.001):
    return [(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d)]


def test_the_pavement_pages_stay_global_airports(tmp_path, monkeypatch):
    xp, mods = _install(tmp_path, ABOVE)
    root = _pack(xp, mods, "region pack", TOWER, apt=OTHER_APT)
    glob = os.path.join(xp, "Global Scenery", "Global Airports")
    _write(os.path.join(glob, "Earth nav data", BLOCK), "synthetic global dsf")
    sel = _select(xp, mods, monkeypatch)
    assert sel.root == root
    # the pages are read from the pack that serves them, and the signature
    # names that DSF too, so a Global Airports update invalidates the plan
    assert (sel.pages_root, sel.pages_name) == (glob, "Global Airports")
    block = A.read_airport_block(sel.apt_dat_path, "ZQQA")
    assert P.signature(sel, block, *TILE).dsf_paths == (
        os.path.join(root, "Earth nav data", BLOCK),
        os.path.join(glob, "Earth nav data", BLOCK))
    # a pack serving its own airport reads its own pages, as before
    own = _select(xp, mods, monkeypatch, icao="ZQQB")
    assert (own.pages_root, own.pages_name, own.pages_from) == (root, "region pack", "")


def test_the_load_reads_pages_from_one_dump_and_the_rest_from_the_other(tmp_path):
    from auto_patch_v2.airport.load import _DsfPolygons
    pages = tmp_path / "global.text"
    _write(str(pages), _polygon_dump([(TERMINAL, _square(-122.28, 47.90)),
                                      (PAGE, _square(-122.27, 47.91))]))
    objects = tmp_path / "pack.text"
    _write(str(objects), _polygon_dump([(PAGE, _square(-122.29, 47.90)),
                                        (TERMINAL, _square(-122.28, 47.92))]))
    polys = _DsfPolygons(lambda lo, la: (lo * 1e5, la * 1e5), None)
    polys.read(str(pages), str(tmp_path), None, pages=True, rest=False)
    polys.read(str(objects), str(tmp_path), None, pages=False, rest=True)
    # Global's page keeps the id it had when Global served the whole read
    assert [p.id for p in polys.pavements] == ["dsf:pol1"]
    assert polys.pavements[0].outer[0] == (-122.27 * 1e5, 47.91 * 1e5)
    # the facades are the object pack's alone
    assert [(b.id, b.outer[0]) for b in polys.buildings] == [
        ("dsf:fac1", (-122.28 * 1e5, 47.92 * 1e5))]
