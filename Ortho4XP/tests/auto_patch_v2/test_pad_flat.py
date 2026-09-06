"""The ``pad_flat`` verify check (lane v2padflat, 2026-09-05; RULINGS
2026-09-03h a pad is a rigid flat group, 04t(1) the one lawful plane):

* the M5 hard fixture's emitted product reads ZERO ``pad_flat`` rows and
  the key is always present (never silently absent);
* an emitted pad tilted by 0.5 m — with no relaxation naming it — is ONE
  row, a DEFECT the pipeline reports apart (``DEFECT_KEYS``);
* the pinned-runway fixture relaxes under 04t(1) and — the measured
  meaning since the pad frontage hops (RULINGS 2026-09-05w) — names
  apron / no-step rows, never a pad plane: its pads stay flat;
* a pad the PUBLICATION names as relaxed is one PLANE: flat or gently
  tilted (within ``[relaxation] pad_slope_max``) it is no row; bend that
  plane and it is a row read as ``plane_residual``; lay it steeper than
  the table and it is ``plane_slope`` (05f).
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


def _published_relaxed_pad(surf, pad) -> dict:
    """A relaxed-pad row as the sidecar publishes it (``relaxed_publication``:
    kind, family, ruling, face, slack, the ring's lat/lon identities,
    slope, extent) — the census reads THIS, whichever rows the solver chose."""
    ids = set(pad.ring)
    return {"kind": "pad", "family": "pads", "ruling": "04t(1)", "face": pad.id,
            "slack_m": 0.0, "ll": [list(v.ll) for v in surf.vertices if v.id in ids],
            "slope": 0.0, "extent_m": 0.0}


def test_the_pinned_fixture_relaxes_rows_and_its_pads_stay_flat(law):
    """THE MEASURED MEANING (RULINGS 2026-09-05w, pad frontage hops): the
    pinned-runway fixture relaxes under 04t(1), and the least-total-
    variance answer names apron / no-step rows — never a pad plane: with
    the frontage hops the pads need not tilt.  Every pad is one flat value
    on the emitted product and the pad census is empty."""
    airport, pm, surf, pub, rep = _product(law, (730.0, 736.0))
    if rep.mode != "relaxed":
        pytest.skip(f"the fixture did not relax on this tree (mode {rep.mode})")
    rows = pub["relaxed_rows"]
    assert rows and not any(r["kind"] == "pad" for r in rows)
    assert {r["family"] for r in rows} <= {"no_step", "apron", "apron_edge_portion", "zones"}
    for f in surf.faces:
        if f.role == "building":
            zs = [v.z for v in surf.vertices if v.id in set(f.ring)]
            assert max(zs) - min(zs) <= law.tables.emit.materiality.elevation_m
    assert census(surf, law, pub, road_law_caps(pm, law, airport))[FAMILY_PAD_FLAT] == []


def test_a_relaxed_pad_is_one_plane_never_a_row_until_it_bends(law):
    """A pad the publication names as relaxed is read as ONE PLANE: flat it
    is no row; bent (one vertex lifted) it is one ``plane_residual`` row
    tagged relaxed.  The relaxed row is published here (the solver no
    longer picks the pad plane on this fixture, 05w)."""
    airport, pm, surf, pub, _rep = _product(law, (730.0, 736.0))
    pad = next(f for f in surf.faces if f.role == "building")
    pub2 = dict(pub, relaxed_rows=[*pub.get("relaxed_rows", []), _published_relaxed_pad(surf, pad)])
    caps = road_law_caps(pm, law, airport)
    assert census(surf, law, pub2, caps)[FAMILY_PAD_FLAT] == []
    # every OTHER pad is still read as one flat value
    for f in surf.faces:
        if f.role == "building" and f.id != pad.id:
            z2 = [v.z for v in surf.vertices if v.id in set(f.ring)]
            assert max(z2) - min(z2) <= law.tables.emit.materiality.elevation_m
    bent = _tilt(surf, list(pad.ring), 0.5)
    rows = census(bent, law, pub2, caps)[FAMILY_PAD_FLAT]
    assert len(rows) == 1 and rows[0]["reading"] == "plane_residual"
    assert rows[0]["relaxed"] is True and rows[0]["face"] == pad.id
    assert rows[0]["magnitude_m"] > law.tables.emit.relaxation.materiality_m
    # the same bend on an UNPUBLISHED pad is the plain spread row
    rows = census(bent, law, pub, caps)[FAMILY_PAD_FLAT]
    assert len(rows) == 1 and rows[0]["reading"] == "spread" and rows[0]["relaxed"] is False


def _tilt_plane(surf, pm, pad_ring_ids, slope: float):
    """The pad's ring laid on a plane of gradient ``slope`` along x."""
    ids = set(pad_ring_ids)
    x0 = min(pm.vertices[i].xy[0] for i in ids)
    verts = tuple(dataclasses.replace(v, z=v.z + slope * (pm.vertices[v.id].xy[0] - x0))
                  if v.id in ids else v for v in surf.vertices)
    return dataclasses.replace(surf, vertices=verts)


def test_a_relaxed_pad_steeper_than_the_table_is_one_row(law):
    """RULINGS 2026-09-05f: a relaxed pad is one plane AND no steeper than
    ``[relaxation] pad_slope_max``; over it by more than the grade
    materiality the census reads ``plane_slope``; within it, one plane is
    no row."""
    airport, pm, surf, pub, _rep = _product(law, (730.0, 736.0))
    pad = next(f for f in surf.faces if f.role == "building")
    pub2 = dict(pub, relaxed_rows=[*pub.get("relaxed_rows", []), _published_relaxed_pad(surf, pad)])
    caps = road_law_caps(pm, law, airport)
    rl = law.tables.emit.relaxation
    gentle = _tilt_plane(surf, pm, list(pad.ring), 0.5 * rl.pad_slope_max)
    assert census(gentle, law, pub2, caps)[FAMILY_PAD_FLAT] == []
    # re-laid as a plane 3x the cap: still one plane, but a defect by slope
    steep = _tilt_plane(surf, pm, list(pad.ring), 3.0 * rl.pad_slope_max)
    rows = census(steep, law, pub2, caps)[FAMILY_PAD_FLAT]
    assert len(rows) == 1 and rows[0]["reading"] == "plane_slope", rows
    assert rows[0]["relaxed"] is True and rows[0]["face"] == pad.id
    assert rows[0]["slope"] > rl.pad_slope_max and rows[0]["slope_max"] == rl.pad_slope_max
