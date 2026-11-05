"""A PACK WRITE IS ALL OR NOTHING, AND A TORN PACK MENDS ITSELF.

Owner 2026-11-04 (app 1.0.465): "PAKT built and the terrain looks right
but I don't see any objects".  The pack's DSF named 156 split bodies the
pack no longer held — a write had removed the previous bodies, written
new ones and then failed to encode, so X-Plane loaded none of its
objects; the build "continued".  Pinned here:

* the encode refusal itself: an ``OBJECT_MSL`` seat below the dump's
  ``HEIGHTS`` base (a ferry ramp at -0.08 m) — the base is lowered to
  cover it (``dsf_heights.cover_row_elevations``);
* ``placement_write.apply_plan`` failing after its restore and body
  writes leaves the pack byte-identical (``pack_journal.transaction``);
* a pack whose live DSF names missing bodies is put back on its
  ``.anchor_bak`` original and the stale record row dropped
  (``torn_pack.repair``) — also when the DSF already IS the original
  beside a stale record;
* the round-trip verifier pairs a dense cluster of one object by a
  maximum matching (KLGB: 9,012 grass rows failed an untouched round
  trip, "heading drift 106.6 deg").
"""
from __future__ import annotations

import os

import pytest

from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_heights as DH
from auto_patch_v2.airport import dsf_write as DW
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport import torn_pack as TP

from auto_patch_v2.model import placement as PM
from test_backup_state import DUMP4, _Cut, _plan, _split, _tncm  # noqa: E402
from test_pack_journal import _bytes  # noqa: E402
from test_unpatched_pack import _clean_memo, seated  # noqa: E402,F401


# ── the encode refusal ──────────────────────────────────────────────────

_TEXT = ("HEIGHTS 0.03125 0.0  # max encodeable 2047.96875\n"
         "PROPERTY sim/overlay 1\n"
         "OBJECT_MSL 0 -131.71 55.35 {z} 0.000000\n"
         "OBJECT 1 -131.70 55.36 10.0\n")


def test_a_seat_under_the_heights_base_lowers_the_base():
    out = DH.cover_row_elevations(_TEXT.format(z="-0.0790"))
    assert out.splitlines()[0] == ("HEIGHTS 0.03125 -1.0  # max encodeable "
                                   "2046.96875")
    assert out.splitlines()[1:] == _TEXT.format(z="-0.0790").splitlines()[1:]


def test_seats_at_or_over_the_base_leave_the_text_byte_identical():
    for z in ("0.0000", "12.5000"):
        text = _TEXT.format(z=z)
        assert DH.cover_row_elevations(text) is text


# ── the round-trip matcher ──────────────────────────────────────────────

def test_a_cluster_greedy_nearest_first_could_not_pair_is_paired():
    # a1 is nearest to b1, the ONLY counterpart a2 has inside tolerance:
    # nearest-first gave b1 to a1 and left a2 with nothing
    a = [(0.5, 0.0, 10.0), (0.0, 0.0, 10.0)]
    b = [(0.6, 0.0, 10.0), (1.4, 0.0, 10.0)]
    unmatched, pairs = DW._match(a, b, 1.0, True, tol_heading=1.0)
    assert unmatched == 0
    assert sorted(pairs) == [((0.0, 0.0, 10.0), (0.6, 0.0, 10.0)),
                             ((0.5, 0.0, 10.0), (1.4, 0.0, 10.0))]


def test_a_row_with_no_counterpart_is_still_unmatched():
    a = [(0.0, 0.0, 10.0), (5.0, 0.0, 10.0)]
    b = [(0.1, 0.0, 10.0), (9.0, 0.0, 10.0)]
    unmatched, pairs = DW._match(a, b, 1.0, True, tol_heading=1.0)
    assert unmatched == 1 and pairs == [((0.0, 0.0, 10.0), (0.1, 0.0, 10.0))]


# ── all or nothing ──────────────────────────────────────────────────────

def test_a_failed_encode_leaves_the_seated_pack_byte_identical(
        seated, monkeypatch):
    seated.write(_tncm, "w1")
    before = _bytes(seated.pack)

    def refused(*_a, **_k):
        raise DW.DsfToolError("ERROR: could not place object 1, 2, 0.0")

    monkeypatch.setattr(DW, "encode", refused)
    # a new cut: the restore removes b__b0/b__b1, the write mints b__c0
    plan = _plan(seated.pack, seated.dsf, icao="TNCM",
                 conversions=(PM.Conversion(0, "objects/a.obj", -63.1, 18.04,
                                            10.0, "OBJECT_MSL", 5.0),),
                 splits=(_split(1, "objects/b.obj", -63.11, 18.041, 20.0,
                                ["objects/b__c0.obj"]),))
    files = [_Cut("objects/b__c0.obj")]
    with pytest.raises(DW.DsfToolError):
        PW.apply_plan(plan, files, seated.tool, patch_dir=seated.patch,
                      work_dir=str(seated.tmp / "w2"))
    assert _bytes(seated.pack) == before


# ── the torn pack ───────────────────────────────────────────────────────

def _tear(world) -> str:
    """Remove one body the live DSF names — the PAKT state."""
    gone = world.pack / "objects" / "b__b0.obj"
    gone.unlink()
    return "objects/b__b0.obj"


def test_a_torn_pack_is_put_back_on_its_original(seated):
    seated.write(_tncm, "w1")
    missing = _tear(seated)
    assert B.classify_dsf(str(seated.dsf)).state is B.State.OURS

    got = TP.repair(str(seated.pack), str(seated.dsf))

    assert got is not None and got.restored_original
    assert got.missing == (missing,) and got.airports == ("TNCM",)
    assert seated.dsf.read_text(encoding="utf-8") == DUMP4
    assert not (seated.pack / "objects" / "b__b1.obj").exists()
    assert TP.missing_bodies(str(seated.pack), str(seated.dsf)) == {}
    assert TP.repair(str(seated.pack), str(seated.dsf)) is None


def test_the_next_write_of_a_torn_pack_seats_it_again(seated):
    seated.write(_tncm, "w1")
    seated_once = _bytes(seated.pack)
    _tear(seated)

    seated.write(_tncm, "w2")

    after = _bytes(seated.pack)
    assert sorted(n for n in after if "__b" in n) == [
        "objects/b__b0.obj", "objects/b__b1.obj"]
    assert after[os.path.relpath(str(seated.dsf), str(seated.pack)).replace(
        os.sep, "/")] == seated_once[os.path.relpath(
            str(seated.dsf), str(seated.pack)).replace(os.sep, "/")]


def test_an_original_dsf_beside_a_stale_record_only_loses_the_row(seated):
    seated.write(_tncm, "w1")
    _tear(seated)
    backup = str(seated.dsf) + B.BACKUP_SUFFIX
    with open(backup, "rb") as fh:
        seated.dsf.write_bytes(fh.read())        # restored by hand
    B.invalidate_memo()

    got = TP.repair(str(seated.pack), str(seated.dsf))

    assert got is not None and not got.restored_original
    assert seated.dsf.read_text(encoding="utf-8") == DUMP4
    assert TP.missing_bodies(str(seated.pack), str(seated.dsf)) == {}


def test_a_whole_pack_is_left_alone(seated):
    seated.write(_tncm, "w1")
    before = _bytes(seated.pack)
    assert TP.repair(str(seated.pack), str(seated.dsf)) is None
    assert _bytes(seated.pack) == before
