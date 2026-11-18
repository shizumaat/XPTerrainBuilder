"""#2145: large structures two packs both draw — the detector
(``pack_overlap``), the row hide (``dsf_row_hide``), the answers store
(``pack_overlap_choice``), the pack write's reading of it
(``dsf_write._with_overlap_hides``) and the command's rewrite set
(``overlap_stage._answer``).  Synthetic packs, no X-Plane, no DSFTool."""
from __future__ import annotations

import os

import pytest
from auto_patch_v2.airport import dsf_row_hide as H
from auto_patch_v2.airport import obj8 as _obj8
from auto_patch_v2.airport import pack_choice as PC
from auto_patch_v2.airport import pack_overlap as PO
from auto_patch_v2.airport import pack_overlap_choice as OVC
from shapely.geometry import Polygon

LON0, LAT0 = 55.36, 25.25
BUILDING_FAC = "I\n800\nFACADE\nRING 1\nDOUBLED 0\nROOF_SCALE 0 1 0 1 1 1 1 1\n"
FENCE_FAC = "I\n800\nFACADE\nRING 0\nDOUBLED 1\n"
#: a 40 x 40 m box, 10 m tall: floor, roof and four walls
_VT = [(-20, 0, -20), (20, 0, -20), (20, 0, 20), (-20, 0, 20),
       (-20, 10, -20), (20, 10, -20), (20, 10, 20), (-20, 10, 20)]
_IDX = [0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1,
        1, 5, 6, 1, 6, 2, 2, 6, 7, 2, 7, 3, 3, 7, 4, 3, 4, 0]
OBJ = ("I\n800\nOBJ\n\nPOINT_COUNTS 8 0 0 36\n"
       + "".join(f"VT {x} {y} {z} 0 1 0 0 0\n" for x, y, z in _VT)
       + "".join(f"IDX {i}\n" for i in _IDX)
       + "TRIS 0 36\n")


def _deg(dx: float, dy: float) -> tuple[float, float]:
    fr = PO.Frame(LON0, LAT0)
    ux = fr.xy(LON0 + 1e-3, LAT0)[0] / 1e-3
    uy = fr.xy(LON0, LAT0 + 1e-3)[1] / 1e-3
    return LON0 + dx / ux, LAT0 + dy / uy


def _square(cx, cy, half):
    return [_deg(cx + sx * half, cy + sy * half)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _dump(objects=(), facades=()) -> list[str]:
    """A DSF dump: ``objects`` ``(resource, lon, lat)``, ``facades``
    ``(resource, ring)``."""
    odefs = sorted({o[0] for o in objects})
    pdefs = sorted({f[0] for f in facades})
    out = [f"OBJECT_DEF {d}" for d in odefs] + [f"POLYGON_DEF {d}" for d in pdefs]
    out += [f"OBJECT {odefs.index(r)} {lo:.9f} {la:.9f} 0.000000" for r, lo, la in objects]
    for r, ring in facades:
        out += [f"BEGIN_POLYGON {pdefs.index(r)} 10 2", "BEGIN_WINDING"]
        out += [f"POLYGON_POINT {lo:.9f} {la:.9f}" for lo, la in ring]
        out += ["END_WINDING", "END_POLYGON"]
    return out


@pytest.fixture
def pack(tmp_path):
    root = tmp_path / "pack"
    (root / "facades").mkdir(parents=True)
    (root / "objects").mkdir()
    (root / "facades" / "block.fac").write_text(BUILDING_FAC, encoding="utf-8", newline="")
    (root / "facades" / "fence.fac").write_text(FENCE_FAC, encoding="utf-8", newline="")
    (root / "objects" / "box.obj").write_text(OBJ, encoding="utf-8", newline="")
    return str(root)


def _structures(pack_root, name, lines, region_half=600.0):
    fr = PO.Frame(LON0, LAT0)
    region = Polygon([(-region_half, -region_half), (region_half, -region_half),
                      (region_half, region_half), (-region_half, region_half)])
    cache = _obj8.ResourceCache(0.05)

    def resolve(r):
        p = os.path.join(pack_root, r)
        return p if os.path.isfile(p) else None
    return PO.structures(name, lines, fr, region, 250.0, resolve, cache)


def test_the_same_building_in_two_packs_is_one_pair_and_fences_are_not(pack):
    a = _dump(objects=[("objects/box.obj", *_deg(0, 0))],
              facades=[("facades/fence.fac", _square(300, 0, 50))])
    b = _dump(facades=[("facades/block.fac", _square(5, 0, 20)),   # on the box
                       ("facades/block.fac", _square(-300, 0, 20)),  # alone
                       ("facades/fence.fac", _square(300, 0, 50))])  # a fence
    sa = _structures(pack, "Airport", a)
    sb = _structures(pack, "Autogen", b)
    assert [s.kind for s in sa] == ["object"]
    assert sa[0].area_m2 == pytest.approx(1600.0, rel=1e-3)
    assert [s.kind for s in sb] == ["facade", "facade"]
    [pair] = PO.overlaps({"Airport": sa, "Autogen": sb})
    assert pair.packs == ("Airport", "Autogen") and pair.count == 1
    assert pair.rows[0] == (sa[0].row,)
    assert pair.rows[1] == (sb[0].row,)
    assert "both draw 1 large structure" in pair.summary()


def test_a_small_or_distant_structure_is_not_read(pack):
    lines = _dump(facades=[("facades/block.fac", _square(0, 0, 5)),      # 100 m2
                           ("facades/block.fac", _square(2000, 0, 20))])  # outside
    assert _structures(pack, "P", lines) == []


def test_half_of_the_smaller_is_the_bar(pack):
    big = _structures(pack, "Big", _dump(facades=[("facades/block.fac", _square(0, 0, 40))]))
    half = _dump(facades=[("facades/block.fac", _square(39, 0, 20))])    # ~0.52 inside
    far = _dump(facades=[("facades/block.fac", _square(55, 0, 20))])     # 0.125 inside
    assert PO.overlaps({"Big": big, "Half": _structures(pack, "Half", half)})
    assert not PO.overlaps({"Big": big, "Far": _structures(pack, "Far", far)})


def test_hide_rows_drops_objects_and_facades_by_anchor():
    ring = _square(0, 0, 20)
    other = _square(100, 0, 20)
    text = "\n".join(_dump(objects=[("o.obj", 55.1, 25.1), ("o.obj", 55.2, 25.2)],
                           facades=[("f.fac", ring), ("f.fac", other)]))
    out, n = H.hide_rows(text, [("o.obj", 55.1, 25.1), ("f.fac", *ring[0])])
    assert n == 2
    assert "55.100000000 25.100000000" not in out and "55.200000000" in out
    assert out.count("BEGIN_POLYGON") == 1 and f"{other[0][0]:.9f}" in out
    assert "OBJECT_DEF o.obj" in out and "POLYGON_DEF f.fac" in out
    assert H.hide_rows(text, []) == (text, 0)


@pytest.fixture
def stores(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / "prefs" / name))
    scenery = tmp_path / "Custom Scenery"
    for n in ("Airport", "Autogen"):
        (scenery / n / "Earth nav data" / "+20+050").mkdir(parents=True)
    key = OVC.pair_key(str(scenery), "Autogen", "Airport")
    OVC.remember_found(key, 25, 55, "Airport", ("Airport", "Autogen"),
                       ((PO.HideRow("a.obj", 55.1, 25.1),),
                        (PO.HideRow("b.fac", 55.2, 25.2),)))
    return str(scenery), key


def _dsf(scenery, name):
    return os.path.join(scenery, name, "Earth nav data", "+20+050", "+25+055.dsf")


def test_no_answer_hides_nothing_and_the_answer_hides_the_loser(stores):
    scenery, key = stores
    air, auto = (os.path.join(scenery, n) for n in ("Airport", "Autogen"))
    assert OVC.pair_key(scenery, "Airport", "Autogen") == key
    assert OVC.overlap_hides(air, _dsf(scenery, "Airport")) == []
    assert OVC.overlap_hides(auto, _dsf(scenery, "Autogen")) == []
    OVC.STORE.remember(key, "Airport")
    assert OVC.overlap_hides(auto, _dsf(scenery, "Autogen")) == [
        PO.HideRow("b.fac", 55.2, 25.2)]
    assert OVC.overlap_hides(air, _dsf(scenery, "Airport")) == []
    assert OVC.kept_rows(air, 25, 55) == [PO.HideRow("a.obj", 55.1, 25.1)]
    assert OVC.overlap_hides(auto, _dsf(scenery, "Autogen").replace(
        "+25+055", "+25+054")) == []                       # another tile
    OVC.STORE.remember(key, OVC.BOTH)
    assert OVC.overlap_hides(auto, _dsf(scenery, "Autogen")) == []


def test_the_pack_write_reads_the_answer(stores):
    from auto_patch_v2.airport import dsf_write as DW
    scenery, key = stores
    auto = os.path.join(scenery, "Autogen")
    rec = {"decks": [1]}
    assert DW._with_overlap_hides(auto, _dsf(scenery, "Autogen"), rec) is rec
    OVC.STORE.remember(key, "Airport")
    got = DW._with_overlap_hides(auto, _dsf(scenery, "Autogen"), rec)
    assert got == {"decks": [1], "overlap_hides": [("b.fac", 55.2, 25.2)]}


def test_the_answer_rewrites_only_the_packs_whose_hiding_changed(stores, monkeypatch):
    from auto_patch import overlap_stage as OV
    scenery, key = stores
    written = []
    monkeypatch.setattr(OV, "_rewrite", lambda s, n, la, lo: written.append(n) or n)
    monkeypatch.setattr(OV.UI, "vprint", lambda *a, **k: None)
    out = OV._answer(scenery, "choose", [{"key": key, "winner": "Airport"}])
    assert out["state"] == "chosen" and written == ["Autogen"]
    written.clear()
    OV._answer(scenery, "choose", [{"key": key, "winner": "Autogen"}])
    assert sorted(written) == ["Airport", "Autogen"]      # one hides, one shows
    written.clear()
    OV._answer(scenery, "undo", [{"key": key}])
    assert written == ["Airport"] and OVC.winner(key) == ""
    with pytest.raises(ValueError):
        OV._answer(scenery, "choose", [{"key": key, "winner": "Elsewhere"}])


def test_default_follows_the_ini_order_then_the_airport_pack(tmp_path):
    """RULINGS 17o/17s: the pair's one airport pack wins; two airport packs
    go by scenery_packs.ini, though alphabetical order says the other;
    packs the ini does not list rank after, alphabetically."""
    from auto_patch import overlap_stage as OS
    (tmp_path / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n"
        "SCENERY_PACK Custom Scenery/Zeta City/\n"
        "SCENERY_PACK Custom Scenery/Alpha City/\n", encoding="utf-8", newline="")
    d = str(tmp_path)
    both = {"Alpha City", "Zeta City"}
    assert OS.default_pack(d, both, ["Alpha City", "Zeta City"]) == "Zeta City"
    assert OS.default_pack(d, {"Alpha City"}, ["Alpha City", "Zeta City"]) == "Alpha City"
    assert OS.default_pack(d, {"Beta", "Alpha City"}, ["Beta", "Alpha City"]) == "Alpha City"
    assert OS.default_pack(d, {"Delta", "Beta"}, ["Delta", "Beta"]) == "Beta"


# --- RULINGS 17s: who is asked about (the twins) ---------------------------

def _scenery(tmp_path, airports, others):
    scenery = tmp_path / "Custom Scenery"
    for n in airports:
        (scenery / n / "Earth nav data").mkdir(parents=True)
        (scenery / n / "Earth nav data" / "apt.dat").write_text(
            "I\n1100 Version\n\n1 10 0 0 XXXX Field\n100 45 1 0 0.25 0 2 1 "
            "09 25.25 55.36 0 0 2 0 0 0 27 25.25 55.37 0 0 2 0 0 0\n99\n",
            encoding="utf-8", newline="")
    for n in others:
        (scenery / n / "Earth nav data").mkdir(parents=True)
    return scenery


@pytest.fixture
def detect(tmp_path, monkeypatch):
    """``_detect`` on a synthetic scenery folder: every pair of the tile's
    packs is found overlapping; returns the rows."""
    from auto_patch import overlap_stage as OS
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / "prefs" / name))
    monkeypatch.setattr(OS, "_context", lambda root: {})
    monkeypatch.setattr(OS, "_structures", lambda *a: [])
    monkeypatch.setattr(PO, "airport_regions", lambda apt: [(None, None)])

    def run(airports, others, folder_extra=()):
        scenery = _scenery(tmp_path, [*airports, *folder_extra], others)
        on_tile = [*airports, *others]
        monkeypatch.setattr(OS, "_candidates", lambda d, la, lo: (
            [str(scenery / a) for a in airports], [str(scenery / n) for n in on_tile]))
        names = sorted(on_tile)
        monkeypatch.setattr(PO, "overlaps", lambda by_pack: [
            PO.OverlapPair((a, b), ((), ()), 1, 1.0)
            for i, a in enumerate(names) for b in names[i + 1:]])
        return OS._detect(str(scenery), 25, 55, str(tmp_path))
    return run


def test_non_airport_against_airport_is_a_row_with_the_airport_default(detect):
    rows = detect(["c_X - 100_airport - ABCD_Field_Vendor1"], ["Vendor2_City_Autogen"])
    assert [(sorted(r["packs"]), r["default"]) for r in rows] == [(
        ["Vendor2_City_Autogen", "c_X - 100_airport - ABCD_Field_Vendor1"],
        "c_X - 100_airport - ABCD_Field_Vendor1")]


def test_two_non_airport_packs_are_not_a_row(detect):
    rows = detect(["Field_Airport"], ["Region-05-details", "Other_City_Autogen"])
    assert all("Field_Airport" in r["packs"] for r in rows) and len(rows) == 2


def test_one_family_is_not_a_row(detect):
    """A vendor's airport and its overlays, one region set of a larger
    package: kept both, unasked."""
    assert detect(["Vendor_Town_0_airport"], ["Vendor_Town_1_overlays"],
                  folder_extra=["Vendor_Elsewhere_0_airport"]) == []


def test_a_prefix_two_airports_carry_is_no_family(detect):
    """A shared sorting prefix several airports carry (a user's own
    ``<country> - 100_airport -`` scheme) names no product: still asked."""
    rows = detect(["c_X - 100_airport - ABCD_Field"], ["c_X - 200_landmark - Town"],
                  folder_extra=["c_X - 100_airport - EFGH_Other"])
    assert len(rows) == 1


def test_family_witness_reads_words_not_ordering_marks():
    from auto_patch_v2.airport import pack_family as PF
    assert PF.words("1-Vendor - Town Airport") == ("vendor", "town", "airport")
    assert PF.shared_lead("Pub_A_KXYZ_Field", "Pub_B_KXYZ_Overlays") == ("pub", "kxyz")
    names = ["Pub_A_KXYZ_Field", "Pub_B_KXYZ_Overlays", "Pub_A_KQRS_Field"]
    airport = {"Pub_A_KXYZ_Field", "Pub_A_KQRS_Field"}.__contains__
    assert PF.same_family("Pub_A_KXYZ_Field", "Pub_B_KXYZ_Overlays", names, airport)
    assert not PF.same_family("Pub_A_KQRS_Field", "Pub_B_KXYZ_Overlays", names, airport)
    assert not PF.same_family("Vendor2_Town_Autogen", "c_XY - 100_airport - ABCD_Town_Vendor1",
                              names, airport)


# --- RULINGS 17s (23:37Z): two packs defining one airport (the twins) ------

_INI = ("I\n1000 Version\nSCENERY\n\n"
        "SCENERY_PACK Custom Scenery/Zeta_ABCD_Field/\n"
        "SCENERY_PACK Custom Scenery/Other_City/\n"
        "SCENERY_PACK Custom Scenery/Alpha_ABCD_Airport/\n"
        "SCENERY_PACK *GLOBAL_AIRPORTS*\n")


@pytest.fixture
def same_airport(tmp_path, monkeypatch):
    """A scenery folder whose two airport packs (by different vendors)
    both define ``XXXX``; Zeta's row is higher in the ini."""
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / "prefs" / name))
    scenery = _scenery(tmp_path, ["Zeta_ABCD_Field", "Alpha_ABCD_Airport"],
                       ["Other_City"])
    (scenery / "scenery_packs.ini").write_text(_INI, encoding="utf-8", newline="")
    return scenery


def _dup_rows(scenery, on_tile=("Alpha_ABCD_Airport",)):
    from auto_patch import duplicate_stage as DS
    return DS.rows(str(scenery), on_tile)


def test_the_lower_of_two_packs_defining_one_airport_is_offered(same_airport):
    from auto_patch_v2.airport import pack_duplicate as PD
    (row,) = _dup_rows(same_airport)
    assert row["kind"] == "duplicate" and row["airport"] == "XXXX"
    assert row["packs"] == ["Zeta_ABCD_Field", "Alpha_ABCD_Airport"]
    assert row["lower"] == "Alpha_ABCD_Airport" and row["default"] == PD.DISABLE
    assert row["winner"] == ""
    assert _dup_rows(same_airport, on_tile=("Other_City",)) == []   # not this tile


def test_one_family_defining_one_airport_is_not_offered(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / "prefs" / name))
    scenery = _scenery(tmp_path, ["Vendor_Town_airport_v1", "Vendor_Town_airport_v2"], [])
    (scenery / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n"
        "SCENERY_PACK Custom Scenery/Vendor_Town_airport_v2/\n"
        "SCENERY_PACK Custom Scenery/Vendor_Town_airport_v1/\n", encoding="utf-8", newline="")
    assert _dup_rows(scenery, on_tile=("Vendor_Town_airport_v1",)) == []


def test_a_pack_the_ini_does_not_list_is_reported_not_offered(same_airport):
    (same_airport / "scenery_packs.ini").write_text(
        _INI.replace("SCENERY_PACK Custom Scenery/Alpha_ABCD_Airport/\n", ""),
        encoding="utf-8", newline="")
    (row,) = _dup_rows(same_airport)
    assert row["lower"] == "" and row["default"] == ""
    assert "Alpha_ABCD_Airport is not listed" in row["summary"]


def test_yes_disables_only_the_lower_row_keeps_a_backup_and_is_idempotent(
        same_airport, monkeypatch):
    from auto_patch import overlap_stage as OS
    from auto_patch_v2.airport import pack_duplicate as PD
    monkeypatch.setattr(OS.UI, "vprint", lambda *a, **k: None)
    ini = same_airport / "scenery_packs.ini"
    (row,) = _dup_rows(same_airport)
    before = sorted(p.name for p in (same_airport / "Alpha_ABCD_Airport").rglob("*"))
    out = OS._answer(str(same_airport), "choose", [{"key": row["key"], "winner": "disable"}])
    assert out["state"] == "chosen" and out["files"] == [str(ini)]
    assert out["items"][0]["lower"] == "Alpha_ABCD_Airport"
    want = _INI.replace("SCENERY_PACK Custom Scenery/Alpha_ABCD_Airport/",
                        "SCENERY_PACK_DISABLED Custom Scenery/Alpha_ABCD_Airport/")
    assert ini.read_text(encoding="utf-8") == want
    assert (same_airport / "scenery_packs.ini.o4bak").read_text(encoding="utf-8") == _INI
    assert sorted(p.name for p in (same_airport / "Alpha_ABCD_Airport").rglob("*")) == before
    assert PD.STORE.choice(row["key"]) == PD.DISABLE
    again = OS._answer(str(same_airport), "choose", [{"key": row["key"], "winner": "disable"}])
    assert again["files"] == [] and ini.read_text(encoding="utf-8") == want
    assert (same_airport / "scenery_packs.ini.o4bak").read_text(encoding="utf-8") == _INI


def test_no_is_remembered_and_not_now_asks_again(same_airport, monkeypatch):
    from auto_patch import overlap_stage as OS
    from auto_patch_v2.airport import pack_duplicate as PD
    (row,) = _dup_rows(same_airport)
    OS._answer(str(same_airport), "choose", [{"key": row["key"], "winner": ""}])
    assert PD.STORE.choice(row["key"]) == ""                  # Not now: asked again
    OS._answer(str(same_airport), "choose", [{"key": row["key"], "winner": "keep"}])
    assert _dup_rows(same_airport)[0]["winner"] == PD.KEEP    # No: never asked again
    assert (same_airport / "scenery_packs.ini").read_text(encoding="utf-8") == _INI
    with pytest.raises(ValueError):
        OS._answer(str(same_airport), "choose", [{"key": row["key"], "winner": "Other"}])


def test_a_same_airport_pair_is_not_also_a_structure_pair(detect, tmp_path, monkeypatch):
    import auto_patch.drape_stage as DSTG
    (tmp_path / "Custom Scenery").mkdir()
    (tmp_path / "Custom Scenery" / "scenery_packs.ini").write_text(
        _INI, encoding="utf-8", newline="")
    monkeypatch.setattr(DSTG, "_folder_packs", lambda d, la, lo: [
        os.path.join(d, "Alpha_ABCD_Airport")])
    rows = detect(["Zeta_ABCD_Field", "Alpha_ABCD_Airport"], ["Other_City"])
    kinds = sorted((r.get("kind", "overlap"), tuple(sorted(r["packs"]))) for r in rows)
    assert ("duplicate", ("Alpha_ABCD_Airport", "Zeta_ABCD_Field")) in kinds
    assert ("overlap", ("Alpha_ABCD_Airport", "Zeta_ABCD_Field")) not in kinds
    assert len([k for k in kinds if k[0] == "overlap"]) == 2
