"""RULINGS 2026-11-19h: a lower pack's draped polygons inside a custom
airport — the reading (``pack_overlap_drapes``), the offer's rows
(``drape_overlap_stage``), the answer's hiding (``pack_overlap_choice``
drape keys, read by every pack write) and the row hide touching nothing
outside the boundary.  Synthetic packs, no X-Plane, no DSFTool."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from auto_patch_v2.airport import dsf_row_hide as H
from auto_patch_v2.airport import pack_choice as PC
from auto_patch_v2.airport import pack_overlap as PO
from auto_patch_v2.airport import pack_overlap_choice as OVC
from auto_patch_v2.airport import pack_overlap_drapes as POD
from shapely.geometry import box

#: the airport's boundary (row 130): 55.30..55.40 E, 25.20..25.30 N
_APT = ("I\n1100 Version\n\n1 10 0 0 XXXX Field\n"
        "100 45 1 0 0.25 0 2 1 09 25.25 55.32 0 0 2 0 0 0 27 25.25 55.38 0 0 2 0 0 0\n"
        "130 Airport Boundary\n111 25.20 55.30\n111 25.20 55.40\n"
        "111 25.30 55.40\n113 25.30 55.30\n99\n")


def _sq(lon, lat, h=0.002):
    return [(round(lon + dx, 6), round(lat + dy, 6))
            for dx, dy in ((-h, -h), (h, -h), (h, h), (-h, h))]


def _dump(polys) -> str:
    """A DSF dump of ``polys`` ``(definition, ring)``."""
    defs = sorted({d for d, _r in polys})
    out = [f"POLYGON_DEF {d}" for d in defs]
    for d, ring in polys:
        out += [f"BEGIN_POLYGON {defs.index(d)} 0 2", "BEGIN_WINDING"]
        out += [f"POLYGON_POINT {lo:.9f} {la:.9f}" for lo, la in ring]
        out += ["END_WINDING", "END_POLYGON"]
    return "\n".join(out) + "\n"


INSIDE = [("lib/Asphalt.pol", _sq(55.35, 25.25)), ("lib/Concrete.pol", _sq(55.33, 25.22))]
OUTSIDE = [("lib/Asphalt.pol", _sq(55.45, 25.25)), ("lib/Concrete.pol", _sq(55.35, 25.35))]
#: most of it inside: counts; most of it outside: never named
CROSSING_IN = ("lib/Asphalt.pol", [(55.38, 25.24), (55.401, 25.24), (55.401, 25.26),
                                   (55.38, 25.26)])
CROSSING_OUT = ("lib/Asphalt.pol", [(55.399, 25.24), (55.42, 25.24), (55.42, 25.26),
                                    (55.399, 25.26)])
NOT_DRAPED = [("lib/Hangar.fac", _sq(55.36, 25.26)), ("lib/Edge.lin", _sq(55.34, 25.24))]
REGION = box(55.30, 25.20, 55.40, 25.30)


def test_the_reading_names_the_draped_polygons_inside_and_only_those():
    text = _dump(INSIDE + OUTSIDE + [CROSSING_IN, CROSSING_OUT] + NOT_DRAPED)
    rows = POD.draped_rows(text.split("\n"), REGION)
    assert sorted(r.resource for r in rows) == ["lib/Asphalt.pol", "lib/Asphalt.pol",
                                                "lib/Concrete.pol"]
    assert PO.HideRow("lib/Asphalt.pol", *INSIDE[0][1][0]) in rows
    assert PO.HideRow("lib/Asphalt.pol", *CROSSING_OUT[1][0]) not in rows
    assert POD.draped_rows(text.split("\n"), None) == []
    assert "3 ground polygons inside XXXX's boundary" in POD.summary("Low", "Air", "XXXX", rows)


def test_hiding_the_rows_leaves_every_polygon_outside_the_boundary():
    keep = OUTSIDE + [CROSSING_OUT] + NOT_DRAPED
    text = _dump(INSIDE + [CROSSING_IN] + keep)
    rows = POD.draped_rows(text.split("\n"), REGION)
    out, n = H.hide_rows(text, rows)
    assert n == 3
    left = POD.draped_rows(out.split("\n"), box(50, 20, 60, 30))
    assert sorted(left) == sorted(PO.HideRow(d, *r[0]) for d, r in keep if d.endswith(".pol"))
    assert out.count("BEGIN_POLYGON") == len(keep)


# --- the offer's rows ------------------------------------------------------

def _ini(order):
    return ("I\n1000 Version\nSCENERY\n\n"
            + "".join(f"SCENERY_PACK Custom Scenery/{n}/\n" for n in order)
            + "SCENERY_PACK *GLOBAL_AIRPORTS*\n")


NAMES = ["Above Overlays", "Vendor1 XXXX Field", "Vendor1 Library", "World Overlays",
         "c_Other XXXX Gateway"]


@pytest.fixture
def scenery(tmp_path, monkeypatch):
    """A custom airport (NAMES[1]) with a pack above it, a pack of its own
    family and a worldwide overlay below it, and a second airport pack
    defining the same airport; every pack's dump the same polygons."""
    from auto_patch import object_stage as OST
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / "prefs" / name))
    root = tmp_path / "Custom Scenery"
    for n in NAMES:
        (root / n / "Earth nav data").mkdir(parents=True)
    for n in (NAMES[1], NAMES[4]):
        (root / n / "Earth nav data" / "apt.dat").write_text(_APT, encoding="utf-8", newline="")
    (root / "scenery_packs.ini").write_text(_ini(NAMES), encoding="utf-8", newline="")
    dump = tmp_path / "dump.txt"
    dump.write_text(_dump(INSIDE + OUTSIDE + NOT_DRAPED), encoding="utf-8", newline="")
    monkeypatch.setattr(OST, "pack_dump", lambda r, la, lo, read_only=False:
                        SimpleNamespace(dump_path=str(dump)))
    return root


def _rows(root, remembered):
    from auto_patch import drape_overlap_stage as DOS
    from auto_patch import duplicate_stage as DS
    packs = [str(root / n) for n in NAMES]
    same = DS.family(str(root), [NAMES[1], NAMES[4]])[0]
    return DOS.rows(str(root), 25, 55, [packs[1]], packs, same,
                    lambda *a: remembered.append(a))


def test_only_a_lower_pack_of_another_vendor_not_defining_the_airport_is_offered(scenery):
    seen = []
    (row,) = _rows(scenery, seen)
    assert row["kind"] == "drapes" and row["lower"] == "World Overlays"
    assert row["default"] == row["airport"] == NAMES[1]      # the airport pack wins
    assert row["packs"] == [NAMES[1], "World Overlays"]
    assert row["count"] == 2 and row["rows"] == [0, 2] and row["winner"] == ""
    assert row["key"] == OVC.drape_key(str(scenery), 25, 55, "World Overlays", NAMES[1])
    ((key, la, lo, air, pair),) = seen
    assert (key, la, lo, air) == (row["key"], 25, 55, NAMES[1])
    assert sorted(pair.rows[1]) == sorted(PO.HideRow(d, *r[0]) for d, r in INSIDE)
    assert pair.rows[0] == ()


def test_a_pack_the_ini_does_not_list_is_never_offered(scenery):
    (scenery / "scenery_packs.ini").write_text(_ini(NAMES[:3]), encoding="utf-8", newline="")
    assert _rows(scenery, []) == []


def test_the_answer_hides_the_lower_packs_rows_on_that_tile_only(scenery):
    from auto_patch_v2.airport import dsf_write as DW
    seen = []
    _rows(scenery, seen)
    key, la, lo, air, pair = seen[0]
    OVC.remember_found(key, la, lo, air, pair.packs, pair.rows)
    low = str(scenery / "World Overlays")
    dsf = os.path.join(low, "Earth nav data", "+20+050", "+25+055.dsf")
    assert OVC.overlap_hides(low, dsf) == []                 # no answer: nothing
    OVC.STORE.remember(key, NAMES[1])                        # "Hide …"
    assert OVC.overlap_hides(low, dsf) == sorted(pair.rows[1])
    assert OVC.overlap_hides(low, dsf.replace("+25+055", "+25+054")) == []
    assert OVC.overlap_hides(str(scenery / NAMES[1]),
                             dsf.replace("World Overlays", NAMES[1])) == []
    assert len(DW._with_overlap_hides(low, dsf, {})["overlap_hides"]) == 2
    OVC.STORE.remember(key, OVC.BOTH)                        # "Keep both"
    assert OVC.overlap_hides(low, dsf) == []


def test_a_drape_pair_and_a_structure_pair_of_two_packs_are_two_keys(scenery):
    a = OVC.pair_key(str(scenery), NAMES[1], "World Overlays")
    b = OVC.drape_key(str(scenery), 25, 55, NAMES[1], "World Overlays")
    assert a != b
    assert OVC._scenery_of(a) == OVC._scenery_of(b) == os.path.abspath(scenery)
