"""ONE IDENTITY between a DSF definition and a plan's resource
(``obj8.same_resource``).

A pack may place its own objects through VIRTUAL paths its
``library.txt`` exports; the plan records the resolved pack-relative
file.  Found at KDEN 2026-11-12 (``dump resource 'XCD_…/Jetways/…obj',
plan says 'Objects/Jetways/…obj'``: no placement written); the rule is
general.  Headless, synthetic pack in ``tmp_path``.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport.placement_record import Split as RecordSplit
from auto_patch_v2.model.placement import (
    Anchor,
    Body,
    PlacementPlan,
    PlacementRef,
    Provenance,
    Split,
)

VIRT = "VENDOR_PACK/Gates/bridge.obj"
FILE = "Objects/Gates/bridge.obj"

DUMP = f"""A
800 written by DSFTool 2.4.0-b1
DSF2TEXT

PROPERTY sim/west -95
OBJECT_DEF {VIRT}
OBJECT_MSL 0 -94.719717041 39.294637407 303.799313344 352.787366
"""


def _pack(tmp_path, library_name="Library.txt"):
    (tmp_path / "Objects" / "Gates").mkdir(parents=True)
    (tmp_path / FILE).write_text("A\n800\nOBJ\n", encoding="utf-8", newline="")
    (tmp_path / library_name).write_text(
        "A\n800\nLIBRARY\n\nREGION_DEFINE Old\nREGION Old\n"
        f"EXPORT_EXCLUDE {VIRT}\tObjects/Gates/Old/bridge.obj\n"
        "REGION_DEFINE Default\nREGION_ALL\nREGION Default\n"
        f"EXPORT {VIRT}\t\t{FILE}\n", encoding="utf-8", newline="\n")
    return str(tmp_path)


def _plan(root, resource=FILE):
    body = Body("b0", "building", (0,), Anchor(-94.7197, 39.2946, 352.787366),
                "pad point", "Objects/Gates/bridge__b0.obj", (0.0, 0.0, 0.0))
    return PlacementPlan(
        icao="TEST", pack_name="pack", pack_root=root,
        dsf_path=root + "/t.dsf", dsf_backup_path=root + "/t.dsf.anchor_bak",
        provenance=Provenance("sha", "1.0", "digest"),
        splits=(Split(PlacementRef(0, resource, -94.719717041, 39.294637407,
                                   352.787366), (body,)),))


@pytest.mark.parametrize("library_name", ["library.txt", "Library.txt"])
def test_a_virtual_definition_is_the_file_its_pack_exports(
        tmp_path, library_name):
    root = _pack(tmp_path, library_name)
    assert obj8.same_resource(VIRT, FILE, root)
    assert obj8.same_resource(FILE, FILE, None)
    assert not obj8.same_resource(VIRT, "Objects/Gates/other.obj", root)
    assert not obj8.same_resource(VIRT, FILE, None)   # no pack: no alias


def test_the_dump_edit_matches_a_virtual_row_to_the_plan(tmp_path):
    root = _pack(tmp_path)
    out = W.edit_dump(DUMP, _plan(root), pack_root=root).splitlines()
    assert not any(ln.startswith("OBJECT_MSL 0 ") for ln in out)
    assert "OBJECT_DEF Objects/Gates/bridge__b0.obj" in out
    with pytest.raises(ValueError, match="dump resource"):
        W.edit_dump(DUMP, _plan(root, "Objects/Gates/other.obj"),
                    pack_root=root)


def test_the_plan_reads_the_virtual_row_as_its_witness(tmp_path):
    import types
    root = _pack(tmp_path)
    record = RecordSplit(0, "dsf:obj0", FILE, f"{root}/{FILE}", 0.0, 0.0,
                         0.0, ())
    row = types.SimpleNamespace(def_path=VIRT)
    assert PP._row_of(record, [row]) is row
    other = types.SimpleNamespace(def_path="VENDOR_PACK/Gates/other.obj")
    assert PP._row_of(record, [other]) is None
