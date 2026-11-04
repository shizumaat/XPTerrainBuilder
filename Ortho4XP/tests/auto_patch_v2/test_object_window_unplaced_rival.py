"""A pack apt.dat block the reader cannot place (a seaplane base whose only
rows are water runways and an empty datum) is no rival -- it used to raise
out of ``rivals`` and fail the whole load (PAKT's pack, 2026-11-04)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import object_window as OW
from shapely.geometry import box


def test_an_unplaceable_block_is_skipped(monkeypatch, tmp_path):
    p = tmp_path / "apt.dat"
    p.write_text("I\n", encoding="utf-8", newline="\n")

    def _boom():
        raise ValueError("no reference point derivable")

    seaplane = types.SimpleNamespace(reference_point=_boom)
    monkeypatch.setattr(OW, "_parsed", lambda *a: (("SEA1", seaplane),))
    assert OW.rivals(str(p), "LAND", (55.0, -131.0), lambda lo, la: (lo, la),
                     box(0, 0, 1, 1)) == ()
