"""INSIDE THE FENCE THE TAG IS NOT ITS OWN WITNESS (owner RULINGS
2026-10-28p (4), Q243 "a", #1338): pavement painted over a tagged tunnel
is not by itself a witness that the tunnel exists; it needs one of RULINGS
2026-10-27z's witnesses.  NZWN's multi-storey car park maps its ground
level as ``layer=-1 tunnel=yes`` service ways under its own pavement, and
the classified cover and that layer cut them to -3.1 m.  SPJC -5724's
fixture (``test_tunnelwitness2._spjc``), with the car park's cover and
layer laid on it."""
from __future__ import annotations

import pytest
import test_tunnelwitness2 as TW  # noqa: E402
from auto_patch_v2.law import Law

CAR_PARK = {"highway": "service", "lanes": "1", "tunnel": "yes", "layer": "-1"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_cover_and_layer_alone_inside_the_fence_are_REFUSED_by_name(law):
    for tags, kw in ((TW.SPJC_TAGS, {"extra_cells": (TW.APRON,)}),
                     (CAR_PARK, {}), (CAR_PARK, {"extra_cells": (TW.APRON,)})):
        _cl, tunnels, st = TW._spjc(law, tags=tags, **kw)
        assert st.tunnels == 0 and not tunnels, (tags, st.mouths_off_field_nearest)
        named = TW._refusals(st)
        assert len(named) == 1 and "WITH NO WITNESS" in named[0], named
        assert "28p (4)" in named[0]


def test_the_same_bore_OUTSIDE_the_fence_is_built_by_cover_or_layer(law):
    for tags, kw in ((TW.SPJC_TAGS, {"extra_cells": (TW.APRON,)}), (CAR_PARK, {})):
        _cl, _t, st = TW._spjc(law, tags=tags, fence=None, **kw)
        assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest


def test_a_27z_witness_still_builds_it_inside_the_fence(law):
    # a rise of the ground over the bore (witness 1)
    _cl, _t, st = TW._spjc(law, tags=CAR_PARK, extra_cells=(TW.APRON,), dem=TW._hill(2.0))
    assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest
    # a pack part at grade over its line (witness 4)
    over = TW._part(0.0, 6.0, TW._ll_ring(310, -110, 325, -90))
    _cl, _t, st = TW._spjc(law, tags=CAR_PARK, partition=TW._link(over))
    assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest
