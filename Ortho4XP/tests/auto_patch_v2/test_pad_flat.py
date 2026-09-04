"""The ``pad_flat`` verify check (lane v2padflat, 2026-09-05; RULINGS
2026-09-03h a pad is a rigid flat group, 04t(1) the one lawful plane):

* the M5 hard fixture's emitted product reads ZERO ``pad_flat`` rows and
  the key is always present (never silently absent);
* an emitted pad tilted by 0.5 m — with no relaxation naming it — is ONE
  row, a DEFECT the pipeline reports apart (``DEFECT_KEYS``);
* a pad the 04t(1) relaxation named is one PLANE: its spread is well above
  the flat tolerance yet it is no row; bend that plane and it is a row
  read as ``plane_residual``.
"""
from __future__ import annotations

import dataclasses

import pytest

from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.roads import road_law_caps
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, relaxed_publication
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.tiers import solve_law_ordered
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import DEFECT_KEYS, FAMILY_PAD_FLAT
from tests.auto_patch_v2.test_m5 import _airport


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _product(law, second_runway_z):
    airport, pm = _airport(law, second_runway_z)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.OPTIMAL
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol.z)
    rr = relaxed_publication(rep)
    if rr:
        pub["relaxed_rows"] = rr
    return airport, pm, surf, pub, rep


def _tilt(surf, pad_ring_ids, dz: float):
    """The pad's first ring vertex lifted by ``dz`` (a bent pad)."""
    v0 = pad_ring_ids[0]
    verts = tuple(dataclasses.replace(v, z=v.z + dz) if v.id == v0 else v
                  for v in surf.vertices)
    return dataclasses.replace(surf, vertices=verts)


def test_the_hard_fixtures_pads_read_flat_and_the_key_is_present(law):
    airport, pm, surf, pub, rep = _product(law, None)
    assert rep.mode == "hard"
    rows = census(surf, law, pub, road_law_caps(pm, law, airport))
    assert FAMILY_PAD_FLAT in rows and rows[FAMILY_PAD_FLAT] == []
    assert FAMILY_PAD_FLAT in DEFECT_KEYS


def test_a_tilted_unrelaxed_pad_is_one_defect_row(law):
    airport, pm, surf, pub, _rep = _product(law, None)
    pad = next(f for f in surf.faces if f.role == "building")
    bent = _tilt(surf, list(pad.ring), 0.5)
    rows = census(bent, law, pub, road_law_caps(pm, law, airport))[FAMILY_PAD_FLAT]
    assert len(rows) == 1
    r = rows[0]
    assert r["roles"] == "building" and r["reading"] == "spread"
    assert abs(r["magnitude_m"] - 0.5) < 1e-6 and r["face"] == pad.id
    assert r["relaxed"] is False and r["site_m"] and r["lat"] is not None


def test_a_relaxed_pad_is_one_plane_never_a_row_until_it_bends(law):
    airport, pm, surf, pub, rep = _product(law, (730.0, 736.0))
    if rep.mode != "relaxed":
        pytest.skip(f"the fixture did not relax on this tree (mode {rep.mode})")
    relaxed = [r for r in pub["relaxed_rows"] if r["kind"] == "pad"]
    assert relaxed, "the pinned-runway fixture relaxes the apron pad"
    fid = relaxed[0]["face"]
    pad = next(f for f in surf.faces if f.id == fid)
    zs = [v.z for v in surf.vertices if v.id in set(pad.ring)]
    assert max(zs) - min(zs) > 10 * law.tables.emit.materiality.elevation_m
    rows = census(surf, law, pub, road_law_caps(pm, law, airport))
    assert rows[FAMILY_PAD_FLAT] == [], rows[FAMILY_PAD_FLAT]
    # every OTHER pad is still one flat value on the emitted product
    for f in surf.faces:
        if f.role == "building" and f.id != fid:
            z2 = [v.z for v in surf.vertices if v.id in set(f.ring)]
            assert max(z2) - min(z2) <= law.tables.emit.materiality.elevation_m
    bent = _tilt(surf, list(pad.ring), 0.5)
    rows = census(bent, law, pub, road_law_caps(pm, law, airport))[FAMILY_PAD_FLAT]
    assert len(rows) == 1 and rows[0]["reading"] == "plane_residual"
    assert rows[0]["relaxed"] is True and rows[0]["face"] == fid
    assert rows[0]["magnitude_m"] > law.tables.emit.relaxation.materiality_m
