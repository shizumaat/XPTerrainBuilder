"""Issue #2051 (KHOU, +29-096): a landing collar's difference aborted every
tile build with ``TopologyException: Ring edge missing``.  The collar is a
mitre ``buffer`` of a valid landing (``building16/landing8``) that GEOS
handed back as an outer shell with a 41.7 m2 copy NESTED inside it; the
held set crossing that copy made ``C.difference(held_c)`` refuse.  The
fixture is the real collar and the held face cut to a 30 m window around
the nested shell (``planar/landing.landing_regions``)."""
import pytest
import shapely
from shapely import wkt

from auto_patch_v2.geom.valid_area import _covered_area, minus

_COLLAR = wkt.loads(
    "MULTIPOLYGON (((-73.44313462140389 1171.1295989605344, -77.83002343565441 1198.9132281174545, 33.08899727077754 1165.5469631380822, 33.08899727077758 1165.5469631380822, 41.378444671964026 1163.0533610781379, 43.5 1162.4151623562884, 77.37742721196459 1152.224275293144, 84.76757013476949 1148.770059046237, 104.8429265759697 1136.5627230653743, 164.4298034763434 1100.3293924889695, 164.14694374520278 1071.7823180846226, 152.03349757829005 1052.662475469526, 117.1955475596014 1065.9924450941153, 113.04009797966125 1045.2151971944145, 99.69443493049988 1070, 93.53835390393407 1070, 95.49028203430852 1077.8077125214982, 92.15606005034627 1083.9998390631424, 82.8853103389307 1079.1204971097657, -70.35847968703234 1137.7558377399455, -69.85140885947017 1140.5, -60.78103423996706 1140.5, -61.27056859036164 1140.9691602082, -64.997251983633 1145.7224941238196, -68.94846817260637 1152.0665915641337, -77.21336475889677 1169.5137860444659, -73.44313462140389 1171.1295989605344)), ((117.43222678792922 1110.44715458415, 115 1115, 119.5 1121, 121.91287308170395 1119.190345188722, 122.57086014531156 1118.927150363279, 119.78543007265577 1111.9635751816395, 117.43222678792922 1110.44715458415)))")
_HELD = wkt.loads(
    "POLYGON ((110 1116, 109.5 1127.5, 108.59748660642842 1130.7818668857149, 115.78466280081618 1130.7818668857149, 116.5 1128, 117.5 1116, 117.5 1111.5, 133.7765140578469 1101.5814992459996, 133.7765140578469 1100.7818668857149, 103.77651405784688 1100.7818668857149, 103.77651405784688 1119.734091565292, 110 1116))")


def test_the_khou_collar_difference_is_refused_by_geos():
    assert shapely.is_valid_reason(_COLLAR).startswith("Nested shells")
    with pytest.raises(shapely.errors.GEOSException):
        _COLLAR.difference(_HELD)


def test_minus_reads_the_covered_area_where_geos_refuses():
    got = minus(_COLLAR, _HELD)
    assert got.is_valid and not got.is_empty
    outer = shapely.get_parts(_COLLAR)[0]
    # the nested copy is covered, never a hole: the outer shell's area
    assert _covered_area(_COLLAR).area == pytest.approx(outer.area)
    assert got.area == pytest.approx(outer.difference(_HELD).area)
    assert got.intersection(_HELD).area < 1e-6


def test_minus_is_the_exact_overlay_where_geos_answers():
    a = shapely.box(0, 0, 10, 10)
    b = shapely.box(5, 5, 20, 20)
    assert minus(a, b).equals_exact(a.difference(b), 0.0)
    assert _covered_area(a) is a
