"""Unit twins for the ONE strip-seam law home (spec seam-continuity-v2 §1).

The v1 seam-continuity round died because two unrelated notions of "seam"
lived under one word: the STRIP seam (tears between two ``graded_strip``
shapes) and the TILE seam (the graticule tile-cut corridor).  §1 gives the
strip seam a single home in ``src`` so a generation-binding law and the
census validator read ONE definition (docs/RULINGS.md, grade-law
completeness standard: emitter and validator lockstep, never two copies).

These are SOURCE-INSPECTION twins in the ``test_reference_honesty`` idiom:
the properties they defend are structural (who owns a constant, how many
copies of a name exist), so inspecting the source is the direct test — a
behavioural test would pass just as well with a silently re-introduced
second copy.

Properties, one test each:

* every strip-seam constant ``check_grade`` exposes IS the law module's
  object (identity, not equality — an equal-but-separate copy fails);
* ``check_grade`` defines NO strip-seam constant of its own (the move is
  a move, not a fork);
* the strip-seam predicates ``check_grade`` uses come from the law module;
* the law module is import-light (stdlib only) — a law that can fail to
  import is not a law, and the standalone validator must keep running;
* the TILE-seam constants are named ``TILE_SEAM_*`` at BOTH sites and
  agree in value (the two-site-agreement idiom);
* a bare ``_SEAM_LL_TOL_DEG`` / ``_SEAM_ZONE_M`` survives nowhere (the
  banned bare-"seam" spelling for the tile corridor).
"""
from __future__ import annotations

import ast
import inspect
import os
import re
import sys
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "tools"), os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade  # noqa: E402
from auto_patch import strip_seam_law  # noqa: E402
from auto_patch import grade_graph_validate  # noqa: E402

STRIP_CONSTANTS = (
    "STRIP_SEAM_TEAR_RADIUS_M",
    "STRIP_SEAM_TEAR_MIN_STEP_M",
    "STRIP_SEAM_TEAR_MIN_GRADE",
    "STRIP_SEAM_TEAR_MIN_DISTANCE_M",
    "STRIP_SEAM_WALL_STRADDLE_TOL_M",
    "STRIP_SEAM_ROLE",
    "STRIP_SEAM_OPEN_GROUND_MIN_M",
    "STRIP_SEAM_OPEN_GROUND_SAMPLES",
    "STRIP_SEAM_GRADED_ROLES",
    "STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M",
)


def test_check_grade_reads_every_strip_constant_from_the_law_module():
    """IDENTITY, not equality: an equal-but-separate copy is exactly the
    drift this move exists to make impossible."""
    for name in STRIP_CONSTANTS:
        assert hasattr(strip_seam_law, name), (
            f"{name} is missing from the law module — the census still "
            f"needs it")
        assert getattr(check_grade, name) is getattr(strip_seam_law, name), (
            f"check_grade.{name} is not the law module's object: a second "
            f"copy of a rule value has been re-introduced")


def test_check_grade_defines_no_strip_seam_constant_of_its_own():
    src = Path(inspect.getsourcefile(check_grade)).read_text()
    tree = ast.parse(src)
    assigned = {
        t.id
        for node in tree.body if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name)
    }
    strayed = sorted(n for n in assigned if n.startswith("STRIP_SEAM"))
    assert not strayed, (
        f"check_grade re-declares strip-seam constant(s) {strayed} — they "
        f"belong to auto_patch.strip_seam_law and must only be imported")


def test_the_strip_seam_predicates_come_from_the_law_module():
    assert check_grade._GradedDomain is strip_seam_law.GradedDomain
    assert check_grade._WallFaces is strip_seam_law.WallFaces
    assert (check_grade._open_ground_between_law
            is strip_seam_law.open_ground_between)
    assert check_grade._point_in_ring is strip_seam_law.point_in_ring


def test_the_law_module_is_import_light():
    """``tools/check_grade.py`` runs standalone and the solve imports this
    module on a hot path: it must pull nothing but the stdlib (no shapely,
    no numpy, no auto_patch.config)."""
    src = Path(inspect.getsourcefile(strip_seam_law)).read_text()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed = {"math", "collections", "typing", "__future__"}
    assert imported <= allowed, (
        f"strip_seam_law grew a heavy dependency: {sorted(imported - allowed)}")


def test_the_tile_seam_constants_agree_at_both_sites():
    """Two-site agreement (the ``test_reference_honesty`` idiom): the tile
    corridor is deliberately duplicated (``src`` must not import ``tools``),
    so the twin is the only thing keeping the copies honest."""
    assert (check_grade.TILE_SEAM_LL_TOL_DEG
            == grade_graph_validate.TILE_SEAM_LL_TOL_DEG)
    assert (check_grade.TILE_SEAM_ZONE_M
            == grade_graph_validate.TILE_SEAM_ZONE_M)


def test_no_bare_seam_spelling_survives_for_the_tile_corridor():
    """The v1 conflation was a NAMING failure.  A bare ``_SEAM_*`` for the
    tile corridor is banned at both sites."""
    for mod in (check_grade, grade_graph_validate):
        src = Path(inspect.getsourcefile(mod)).read_text()
        for banned in (r"(?<![A-Z_])_SEAM_LL_TOL_DEG\b",
                       r"(?<![A-Z_])_SEAM_ZONE_M\b"):
            assert not re.search(banned, src), (
                f"{mod.__name__} still spells the TILE-seam corridor with a "
                f"bare 'seam' name ({banned}) — use TILE_SEAM_*")
