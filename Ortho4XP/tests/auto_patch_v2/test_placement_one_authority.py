"""A PLACEMENT TAKES EXACTLY ONE AUTHORITY, decided at ONE site
(``terrain_shaped.row_seats``).  KLAX 1.0.472, placement 7230
(``Misc/Underpass_1.obj``), and EGKK, placement 1508: the split stage cut
the row into a basin-rim body AND the roofed-portal record seated the same
row whole at its pinned mouth floor; the writer refused the whole pack
("placements both row-seated and converted/split") and no seat of the
airport was written.  A split row is seated by its bodies; every
whole-row record (portal floor, terrain fit, object floor, entrance face)
seats only a row the plan does not split."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport.terrain_shaped import (
    ENTRANCE_SEAT,
    OBJECT_FLOOR_SEAT,
    PORTAL_SEAT,
    SEAT,
    row_seats,
)
from auto_patch_v2.model.placement import (
    Anchor,
    Body,
    MslSeat,
    PlacementPlan,
    PlacementRef,
    Provenance,
    Split,
)


def _row(path):
    return types.SimpleNamespace(def_path=path, lon=-118.39, lat=33.94, heading_deg=352.9)


DUMP = types.SimpleNamespace(placements=[_row("a.obj"), _row("Misc/Underpass_1.obj")])


def _rec(seat):
    return {"id": "dsf:obj1", "resource": "Misc/Underpass_1.obj", "datum": "portal",
            "seat": seat, "elevation": 25.543, "end": [33.94, -118.39]}


@pytest.mark.parametrize("seat", [PORTAL_SEAT, SEAT, OBJECT_FLOOR_SEAT, ENTRANCE_SEAT])
def test_a_split_row_takes_no_whole_row_seat(seat):
    assert row_seats(DUMP, [_rec(seat)], frozenset({1})) == ()


@pytest.mark.parametrize("seat", [PORTAL_SEAT, SEAT, OBJECT_FLOOR_SEAT, ENTRANCE_SEAT])
def test_an_unsplit_row_takes_its_whole_row_seat(seat):
    got = row_seats(DUMP, [_rec(seat)], frozenset({0}))
    assert [(m.index, m.elevation) for m in got] == [(1, 25.543)]


def test_the_writer_refuses_two_authorities():
    """The refusal the seat site keeps from firing (``edit_dump``)."""
    text = ("A\n800 written by DSFTool 2.4.0-b1\nDSF2TEXT\n\nPROPERTY sim/west -119\n"
            "OBJECT_DEF Misc/Underpass_1.obj\n"
            "OBJECT 0 -118.396187629 33.940259022 352.946670\n")
    body = Body(body_id="b0", body_class="basin", components=(0,),
                anchor=Anchor(-118.3961, 33.9402, 352.9), anchor_reason="rim",
                new_resource="Misc/Underpass_1__b0.obj")
    plan = PlacementPlan(
        icao="T", pack_name="p", pack_root="/r", dsf_path="/r/x.dsf",
        dsf_backup_path="/r/x.dsf.anchor_bak", provenance=Provenance("", "", "", {}),
        conversions=(), kept=(),
        splits=(Split(PlacementRef(0, "Misc/Underpass_1.obj", -118.3961, 33.9402, 352.9),
                      (body,)),),
        msl_seats=(MslSeat(0, "Misc/Underpass_1.obj", -118.3961, 33.9402, 352.9, 25.5,
                           "portal_floor"),))
    with pytest.raises(ValueError, match="both row-seated and converted/split"):
        W.edit_dump(text, plan)
