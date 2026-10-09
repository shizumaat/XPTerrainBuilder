"""THE ZONE-PART WIDTH FLOOR (spec §59 (4) row 10's GENERAL CURE; review
``gapreview`` D5; §39 (2)): a zone part that holds no disc of diameter
``emit.identity.min_distinct_spacing_m`` is dropped at the part floor's
line in ``planar/zones.zone_regions`` — and what the floor does NOT reach
(lane ``zonefloor``): a slit grown as a LIMB of a real part."""
from __future__ import annotations

import pathlib

import pytest
from shapely.geometry import box

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_side
from auto_patch_v2.planar import zones as Z

LAW = Law.for_airport("HECA")
SPACING = float(LAW.tables.emit.identity.min_distinct_spacing_m)


def _cell(i, role, ref, b, code_number=None, code_letter=None):
    return Cell(i, role, ref, tuple(b.exterior.coords)[:-1], (), code_number,
                code_letter, role_side(LAW, role), role, {})


def _field(gap_m):
    """A runway with three aprons along one edge: the outer two flush, the
    middle one ``gap_m`` off the edge over 1,100 m — the lip left there is
    a part of its own."""
    return (_cell(0, "runway", "05/23", box(0, 0, 3000, 60), code_number=4),
            _cell(1, "apron", "pav1", box(-200, 60, 1000, 300)),
            _cell(2, "apron", "pav2", box(1000, 60 + gap_m, 2100, 300)),
            _cell(3, "apron", "pav3", box(2100, 60, 3200, 300)))


def _parts(cells):
    return sorted(z.polygon.normalize().wkb_hex for z in Z.zone_regions(cells, LAW))


def test_a_hairline_lip_is_no_zone_part(monkeypatch):
    """1,100 m x 1 mm = 1.1 m2 passes the 1 m2 area floor; it cannot hold two
    distinct vertices across it.  With the floor the bands are the bands of
    the same field with the apron flush: no ring runs down the runway edge."""
    lip = box(1000.5, 60.0002, 2099.5, 60.0008)
    got = Z.zone_regions(_field(0.001), LAW)
    assert got and not any(z.polygon.intersects(lip) for z in got)
    assert _parts(_field(0.001)) == _parts(_field(0.0))
    # the twin tests the WIDTH floor: the area floor alone keeps the lip
    monkeypatch.setattr(Z, "_unmeshable", lambda g, s: False)
    kept = [z for z in Z.zone_regions(_field(0.001), LAW) if z.polygon.intersects(lip)]
    assert len(kept) == 1 and 1.0 < kept[0].polygon.area < 1.2 and kept[0].zone == 1


def test_a_real_strip_is_kept():
    """2 m of lip between the runway and an apron is ground a band grades."""
    assert float(LAW.tables.zones.adjacent_ground.lip_width_m) >= 2.0
    strip = box(1000.5, 60.5, 2099.5, 61.5)
    got = [z for z in Z.zone_regions(_field(2.0), LAW) if z.polygon.intersects(strip)]
    assert len(got) == 1 and got[0].zone == 1
    assert got[0].polygon.area == pytest.approx(1100 * 2.0, rel=1e-6)


def test_the_floor_reads_the_law_and_the_widest_place():
    assert Z._unmeshable(box(0, 0, 1000, 0.8 * SPACING), SPACING)
    assert not Z._unmeshable(box(0, 0, 1000, 1.2 * SPACING), SPACING)
    # a fat body with a tail is not thin (the inscribed disc, never 2A/P)
    tailed = box(0, 0, 2, 2).union(box(2, 0, 1000, 0.001))
    assert not Z._unmeshable(tailed, SPACING)
    assert not Z._unmeshable(box(0, 0, 1000, 0.001), 0.0)      # no spacing: no floor


# ── the HECA frame twin (review ``gapreview`` D5) ────────────────────────

#: ``planar/overlay``'s own arguments to ``zone_regions`` on the capture
#: ``frames/gapapron3/HECA.pkl`` (``docs/briefs/zonefloor/zone_args.py``: the
#: replay's prelude).  The claim's union is input-chaotic — a re-derivation of
#: the cells here (classify without the capture state) pops no hairline at all.
FRAME = pathlib.Path("/Users/noah/XPTerrainBuilderData/.harness/frames/zonefloor/HECA_zone_args.pkl")


def _frame_zone_args():
    import pickle
    with open(FRAME, "rb") as fh:
        a = pickle.load(fh)
    return (a["cells"], LAW, a["keepouts"], a["dem"], a["roads"], None, a["declared"],
            a["shore_wedge_m"], a["pack_walls"])


@pytest.mark.skipif(not FRAME.exists(), reason="frames zonefloor (the zone arguments) not mounted")
def test_the_floor_on_a_real_map_and_why_the_claim_trim_stays(monkeypatch):
    """MEASURED (lane ``zonefloor``, planar replays of this capture, runway-ring
    vertices against the tree's 2,610): the 11 gap-apron cells put back INTO
    the claim give +143 / -3 without the floor, **+77 / -3 with it** — the
    1,689 m hairline PART is gone, but the same re-noding grows slits as
    LIMBS of real zone-1 parts (405.72 m2 with 1,399 m of slit 0.01 mm wide),
    which no part floor reads.  So the floor does NOT make §59's claim trim
    redundant, and the trim stays."""
    args = _frame_zone_args()
    floor = Z._unmeshable
    spacing = float(args[1].tables.emit.identity.min_distinct_spacing_m)

    def run(with_floor, trimmed):
        with monkeypatch.context() as m:
            if not with_floor:
                m.setattr(Z, "_unmeshable", lambda g, s: False)
            if not trimmed:
                m.setattr(Z, "is_gap_apron_ref", lambda ref: False)
            return Z.zone_regions(*args)

    def key(zs):
        return sorted(z.polygon.normalize().wkb for z in zs)

    def runway(zs):
        return [z for z in zs if z.family == "runway"]

    # THE TREE: the floor drops four taxi-band hairlines and no runway part
    tree, bare = run(True, True), run(False, True)
    gone = [z for z in bare if floor(z.polygon, spacing)]
    assert sorted(round(z.polygon.area, 2) for z in gone) == [1.62, 1.88, 2.74, 3.24]
    assert all(z.family == "taxi" for z in gone)
    assert key(tree) == key([z for z in bare if not floor(z.polygon, spacing)])
    assert key(runway(tree)) == key(runway(bare))
    assert not any(floor(z.polygon, spacing) for z in tree)
    # THE 11 CELLS IN THE CLAIM: the hairline part pops, and the floor drops it
    claim_bare, claim = run(False, False), run(True, False)
    hair = [z for z in runway(claim_bare) if floor(z.polygon, spacing)]
    assert len(hair) == 1 and hair[0].zone == 1 and hair[0].polygon.length > 3000.0
    assert not any(floor(z.polygon, spacing) for z in claim)
    # the hairline is NOT under the entry lattice (1 mm x sqrt 2): its widest place is
    # 4.1 mm, the thinnest part the tree carries 22 mm — no law number lies between
    lattice = float(args[1].tables.emit.identity.input_quantum_m) * 2 ** 0.5
    assert not floor(hair[0].polygon, lattice) and floor(hair[0].polygon, 0.01)
    assert not any(floor(z.polygon, 0.01) for z in bare)
    # …and what the floor cannot reach: the slits that are limbs of real parts.
    # (If this stops holding, the trim may have become redundant: re-measure the
    # runway ring with docs/briefs/zonefloor/zone_probe.py before removing it.)
    def lip_rim(zs):
        return sum(z.polygon.length for z in runway(zs) if z.zone == 1)
    assert lip_rim(claim) - lip_rim(tree) > 1000.0          # measured: +4,578 m of ring
    assert sum(z.polygon.area for z in runway(claim)) == pytest.approx(
        sum(z.polygon.area for z in runway(tree)), abs=1.0)  # …around no ground at all
