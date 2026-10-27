"""DEM PREP READS THE PACK'S DRAPED PAVEMENT THE BUILD READS (#1208, owner
RULINGS 2026-10-27d: inside the boundary only runways and pavement stay
flat).  ``airport/pack_pavement.pavement_pages`` must admit every
``dsf:pol`` page ``load.load_with_report`` turns into pavement — measured
at VHHH, 55 % of the aprons on the hill east of the terminals are such
pages — and the flat-site decision must hold them at Z0 with apt.dat's.

Synthetic only: the checked-in CYXY fixture (read-only), no network.
"""
from __future__ import annotations

import math
from pathlib import Path

from auto_patch_v2.airport import flat_site_prep as PREP
from auto_patch_v2.airport import pack_pavement as PP
from auto_patch_v2.airport.load import _own_extent, load_with_report
from auto_patch_v2.law import Law
from shapely.geometry import Polygon
from shapely.ops import unary_union
from tests.auto_patch_v2.test_airport_load import FIX, fixture_inputs


def _pages(site):
    law = Law.for_airport("CYXY")
    lat0, lon0 = site.frame.origin
    to_xy = site.frame.transformers()[0]
    return PP.pavement_pages(
        site.pack_root, site.pack_name, math.floor(lat0), math.floor(lon0),
        to_xy, _own_extent(site.runways, site.pavements, site.boundaries,
                           law.tables.emit.identity.dsf_pavement_admission_m),
        str(FIX / "Airport_mod_cache"), str(FIX))


def test_dem_prep_reads_every_draped_page_the_build_reads():
    law = Law.for_airport("CYXY")
    airport, _rep = load_with_report("CYXY", fixture_inputs(), law)
    built = [Polygon(p.outer, list(p.holes)).buffer(0)
             for p in airport.pavements if p.id.startswith("dsf:pol")]
    assert built, "the fixture carries draped pavement pages"
    site = PREP.site_inputs("CYXY", str(FIX), str(FIX / "CIFP" / "CYXY.dat"), law)
    assert site.pack_name == "CYXY Fixture"
    pages = _pages(site)
    assert len(pages) >= len(built)
    missed = unary_union(built).difference(unary_union(pages).buffer(0.01))
    assert missed.area < 1e-6 * unary_union(built).area


def test_no_mod_cache_reads_no_pages():
    law = Law.for_airport("CYXY")
    site = PREP.site_inputs("CYXY", str(FIX), str(FIX / "CIFP" / "CYXY.dat"), law)
    lat0, lon0 = site.frame.origin
    assert PP.pavement_pages(site.pack_root, site.pack_name, math.floor(lat0),
                             math.floor(lon0), site.frame.transformers()[0],
                             None, None, str(FIX)) == []
    assert PP.pavement_pages("", "", 60, -136, site.frame.transformers()[0],
                             None, str(Path(FIX) / "Airport_mod_cache"),
                             str(FIX)) == []
