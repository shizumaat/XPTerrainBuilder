"""A PLACEMENT TAKES EXACTLY ONE AUTHORITY, decided at ONE site
(``placement_write.placement_records``).  KLAX 1.0.472, placement 7230
(``Misc/Underpass_1.obj``), and EGKK, placement 1508: the split stage cut
the row into a basin-rim body AND the roofed-portal record seated the same
row whole at its pinned mouth floor (``terrain_shaped.row_seats``); the
writer refused the whole pack ("placements both row-seated and
converted/split") and no seat of the airport was written.  A whole-row
seat now withdraws the split; an ENTRANCE face is a body's seat and still
defers to the split."""
from __future__ import annotations

import types

from auto_patch_v2.airport import placement_plan as _pp
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport.terrain_shaped import ENTRANCE_SEAT, PORTAL_SEAT


def _row(path):
    return types.SimpleNamespace(def_path=path, lon=-118.39, lat=33.94, heading_deg=352.9)


def _split(i, path):
    return types.SimpleNamespace(placement=types.SimpleNamespace(index=i, resource=path))


def _records(monkeypatch, seat):
    dump = types.SimpleNamespace(placements=[_row("a.obj"), _row("Misc/Underpass_1.obj")])
    splits = (_split(0, "a.obj"), _split(1, "Misc/Underpass_1.obj"))
    monkeypatch.setattr(_pp, "to_placement_records", lambda _ss: (splits, ()))
    rec = {"id": "dsf:obj1", "resource": "Misc/Underpass_1.obj", "datum": "portal",
           "seat": seat, "elevation": 25.543, "end": [33.94, -118.39]}
    return PW.placement_records(None, dump, types.SimpleNamespace(authored_seats=[rec]))


def test_a_portal_floor_seat_withdraws_the_split(monkeypatch):
    splits, kept = _records(monkeypatch, PORTAL_SEAT)
    assert [s.placement.index for s in splits] == [0]
    assert [(k.index, k.reason) for k in kept] == [
        (1, "seated whole on its row (portal_floor)")]


def test_an_entrance_face_defers_to_the_split(monkeypatch):
    splits, kept = _records(monkeypatch, ENTRANCE_SEAT)
    assert [s.placement.index for s in splits] == [0, 1] and kept == ()
