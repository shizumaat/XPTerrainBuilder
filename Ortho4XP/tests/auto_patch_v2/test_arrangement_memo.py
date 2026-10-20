"""The arrangement's FRONT is read once per build (late-stage prefix reuse
spec §5 phase 2, issue #803): inside ``arrangement_memo.scoped`` a second
``build_arrangement`` over the same non-late cells is served the front, and
its arrangement is the one a fresh build gives; outside a build nothing is
held."""
from __future__ import annotations

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import GAP_PREFIX
from auto_patch_v2.planar import arrangement_memo, overlay


class _Flat:
    provenance = {"synthetic": "flat"}

    def z(self, x, y):
        return 700.0

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _airport(law):
    from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
    from auto_patch_v2.model.frame import Frame
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0,
                   (Runway("09/27", 45.0, 1, ends, 3, "D"),), (), (), {},
                   (), (), (), (), (), (), (), pack, _Flat(), law.ruleset_key)


_BASE = (
    Cell(0, "runway", "09/27", ((-600, -22.5), (600, -22.5), (600, 22.5), (-600, 22.5)),
         (), 3, "D", "airside", "runway", {}),
    Cell(1, "apron", "apron1", ((-200, 100), (200, 100), (200, 300), (-200, 300)),
         (), None, "D", "airside", "apron", {}),
    Cell(2, "building", "pad1", ((-50, 300), (50, 300), (50, 360), (-50, 360)),
         (), None, None, "airside", "pad", {}),
)
_GAP = Cell(3, "groundside_pavement", f"{GAP_PREFIX}:0",
            ((300, 100), (360, 100), (360, 160), (300, 160)), (), None, None,
            "groundside", "gap", {})


def _faces(arr):
    return sorted((r.role, r.ref, p.wkb_hex) for p, r in arr.faces)


def test_a_build_serves_the_front_once_and_the_answer_is_a_fresh_builds(monkeypatch):
    law = Law.for_airport("ZZZZ")
    airport = _airport(law)
    calls = []
    real = overlay.weld_cells
    monkeypatch.setattr(overlay, "weld_cells",
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    base = Classification(_BASE, (), {}, ())
    cut = Classification(_BASE + (_GAP,), (), {}, ())
    fresh = _faces(overlay.build_arrangement(airport, cut, law))
    assert len(calls) == 1

    @arrangement_memo.scoped
    def one_build():
        overlay.build_arrangement(airport, base, law)
        return overlay.build_arrangement(airport, cut, law)
    served = _faces(one_build())
    assert len(calls) == 2                    # the cut map was served the front
    assert served == fresh
    overlay.build_arrangement(airport, cut, law)
    assert len(calls) == 3                    # nothing outlived the build
