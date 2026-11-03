"""§46 (7) twin (#1670, #1673): the constraint stage spells every length
in IEEE-exact operations, so its rows are the same doubles on macOS,
Linux and Windows.

``math.hypot``, ``math.dist``, ``np.hypot`` and a float ``**`` round
differently per platform in the last bit (``geom/exact.py`` says why);
on the beta 6 release dry run (41179511687) that bit reached 1,900 of
CYXY's 68,000 constraint rows.  The constraint package and the road
ramp's target producers (``PlanarMap.road_ramp_z`` /
``road_route_frame``, read straight into rows) use ``geom.exact``.
"""
from __future__ import annotations

import ast
import math
import pathlib
import random

import numpy as np

from auto_patch_v2.geom import exact

_V2 = pathlib.Path(exact.__file__).resolve().parents[1]

#: The road ramp's target channel producers (``airport/road_ramp.py``
#: publishes what ``constraints/road_ramp.py`` reads as row values).
_ROAD_TARGETS = ("road_ramp.py", "road_profile.py", "road_joint.py",
                 "public_road.py", "road_stations.py")

#: RECORDED: files another lane owns (the bridge/deck redesign) whose
#: sites stay until that lane lands.  May only fall.
RECORDED = {"constraints/edge_deck.py": 3, "constraints/structures.py": 5}

_LIBM = {("math", "hypot"), ("math", "dist"), ("_math", "hypot"),
         ("_math", "dist"), ("np", "hypot"), ("_np", "hypot"),
         ("numpy", "hypot"), ("math", "pow"), ("np", "power")}


def _sites(path: pathlib.Path) -> list[str]:
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            out.append("%d: **" % node.lineno)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and isinstance(node.func.value, ast.Name)
              and (node.func.value.id, node.func.attr) in _LIBM):
            out.append("%d: %s.%s" % (node.lineno, node.func.value.id, node.func.attr))
    return out


def _files() -> list[pathlib.Path]:
    return (sorted((_V2 / "constraints").glob("*.py"))
            + [_V2 / "airport" / n for n in _ROAD_TARGETS])


def test_constraint_lengths_are_platform_exact():
    found = {}
    for p in _files():
        rel = p.relative_to(_V2).as_posix()
        s = _sites(p)
        if s and len(s) > RECORDED.get(rel, 0):
            found[rel] = s
    assert not found, ("libm length / float pow differs per platform "
                       "(§46 (7)); use geom.exact: %s" % found)


def test_recorded_only_falls():
    for rel, n in RECORDED.items():
        assert len(_sites(_V2 / rel)) <= n, rel


def test_exact_is_the_ieee_spelling():
    rng = random.Random(1670)
    for _ in range(5000):
        dx, dy = rng.uniform(-3e3, 3e3), rng.uniform(-3e3, 3e3)
        want = math.sqrt(dx * dx + dy * dy)
        assert exact.hypot(dx, dy) == want
        assert exact.dist((dx, dy), (0.0, 0.0)) == want
        assert exact.sq(dx) == dx * dx
        # within an ulp of libm's hypot: the same length, spelt exactly
        assert abs(want - math.hypot(dx, dy)) <= 2.0 * math.ulp(want)
    a = np.array([rng.uniform(-1e3, 1e3) for _ in range(500)])
    b = np.array([rng.uniform(-1e3, 1e3) for _ in range(500)])
    got = exact.hypot_array(a, b)
    assert [float(g) for g in got] == [exact.hypot(float(x), float(y))
                                       for x, y in zip(a, b)]


def test_the_road_ramp_targets_publish_on_the_read_grid():
    """CYXY's beta 6/7 dry runs: 15-21 road ramp targets (~725 m DEM
    levels) differed by 8e-13 m across the runners — PROJ's inverse in
    the DEM read.  The targets are published on ``exact.READ_DP``."""
    z = 725.0 + 0.123456789
    assert exact.on_read_grid(z) == exact.on_read_grid(z + 8e-13) == round(z, 6)
    src = (_V2 / "airport" / "road_ramp.py").read_text(encoding="utf-8")
    assert "exact.on_read_grid(z) for v, z in targets.items()" in src
