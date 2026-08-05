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

THIRD-COPY ABSORPTION (spec seam-continuity-v3 §1) extends the same three
properties to the EMITTER half of the law,
``adjacent_ground.blend_cross_strip_seam_steps``, which carried a third
equal-valued copy of the radius and step floor under bare-"seam" names:

* the healer's thresholds ARE the law module's objects (identity);
* ``adjacent_ground`` declares no strip-seam constant of its own (AST);
* the retired bare spellings survive nowhere (regex, both sites).
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
from auto_patch import adjacent_ground  # noqa: E402

# The thresholds the EMITTER shares with the census: the radius and step
# floor (v3 §1, third copy) and — since spec seam-continuity-v4 §1 ruled
# the coupling v3 flagged and deferred — the cliff-GRADE floor (fourth
# copy).  The healer's pairing test and its non-worsening guard now both
# quote the census predicate itself.
HEALER_ABSORBED_CONSTANTS = (
    "STRIP_SEAM_TEAR_RADIUS_M",
    "STRIP_SEAM_TEAR_MIN_STEP_M",
    "STRIP_SEAM_TEAR_MIN_GRADE",
)
# The bare-"seam" names the healer used to declare locally.
RETIRED_HEALER_SPELLINGS = (
    r"(?<![A-Z_])SEAM_STEP_RADIUS_M\b",
    r"(?<![A-Z_])SEAM_STEP_MIN_DELTA_M\b",
    r"(?<![A-Z_])SEAM_STEP_MIN_GRADE\b",
)

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


def test_the_healer_reads_every_absorbed_constant_from_the_law_module():
    """v3 §1 THIRD-COPY ABSORPTION, identity not equality.

    ``blend_cross_strip_seam_steps`` is the EMITTER half of the strip-seam
    law; the census (``check_grade._check_strip_seam_tears``) is the
    validator half.  Their radius and step floor being the SAME OBJECT is
    what makes "the healer sees exactly the pair population the census
    reports" a structural fact rather than a coincidence — and therefore
    what makes every surviving census row provably a decline."""
    for name in HEALER_ABSORBED_CONSTANTS:
        assert (getattr(adjacent_ground, name)
                is getattr(strip_seam_law, name)), (
            f"adjacent_ground.{name} is not the law module's object: the "
            f"third copy of a rule value has been re-introduced")
        assert (getattr(check_grade, name)
                is getattr(adjacent_ground, name)), (
            f"emitter and validator disagree on the object behind {name}")


def test_the_census_predicate_is_one_function_for_both_halves():
    """v4 §1: the guard allowance and ``_check_strip_seam_tears`` are
    computed from ONE function.

    IDENTITY half — the validator's verdict call IS the law module's
    ``seam_pair_is_tear``, and the emitter imports the same object."""
    assert check_grade._seam_pair_is_tear is strip_seam_law.seam_pair_is_tear
    assert (adjacent_ground.seam_pair_is_tear
            is strip_seam_law.seam_pair_is_tear)
    assert (adjacent_ground.seam_guard_allowance_m
            is strip_seam_law.seam_guard_allowance_m)


def test_the_guard_allowance_never_permits_a_census_tear():
    """ARITHMETIC half of the same twin, swept over the pair space: any
    |Δalt| the guard allows at a distance must be a Δ the census does NOT
    call a tear.  A drift in either function breaks this immediately."""
    for step in range(0, 121):
        planar = step * 0.05                    # 0 .. 6 m, the tear radius
        allowance = strip_seam_law.seam_guard_allowance_m(planar)
        for frac in (0.0, 0.25, 0.5, 0.75, 0.999, 1.0):
            de = allowance * frac
            assert not strip_seam_law.seam_pair_is_tear(de, planar), (
                f"the guard allows Δ={de:.4f} m at {planar:.2f} m, which "
                f"the census reports as a tear")
        # And the allowance is TIGHT: a Δ one margin above it is a tear
        # (otherwise the guard is silently over-strict again — the exact
        # defect the bounds-attribution verdict attributed).
        over = allowance + 2 * strip_seam_law.STRIP_SEAM_GUARD_MARGIN_M
        assert strip_seam_law.seam_pair_is_tear(over, planar), (
            f"Δ={over:.4f} m at {planar:.2f} m is not a tear — the "
            f"allowance is looser than the census predicate")


def test_the_guard_allowance_is_grade_aware_past_the_step_floor():
    """The bounds-attribution verdict's mechanism 1, as a number: at the
    MEASURED site distances (2.2-6.0 m) the census-identical allowance is
    strictly larger than the retired bare step-floor allowance, and by up
    to 3x at the radius."""
    flat = (strip_seam_law.STRIP_SEAM_TEAR_MIN_STEP_M
            - strip_seam_law.STRIP_SEAM_GUARD_MARGIN_M)
    for planar in (2.2, 2.84, 3.41, 5.98, 6.0):
        assert strip_seam_law.seam_guard_allowance_m(planar) > flat
    assert (strip_seam_law.seam_guard_allowance_m(6.0) / flat) > 2.9


def test_adjacent_ground_defines_no_strip_seam_constant_of_its_own():
    src = Path(inspect.getsourcefile(adjacent_ground)).read_text()
    tree = ast.parse(src)
    assigned = {
        t.id
        for node in tree.body if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name)
    }
    strayed = sorted(n for n in assigned if n.startswith("STRIP_SEAM"))
    assert not strayed, (
        f"adjacent_ground re-declares strip-seam constant(s) {strayed} — "
        f"they belong to auto_patch.strip_seam_law and must only be "
        f"imported")


def test_no_bare_seam_step_spelling_survives_in_the_emitter():
    """The retired bare-"seam" names must not come back — including inside
    a comment or docstring, which is how a "temporary" second copy is
    normally reintroduced."""
    for mod in (adjacent_ground, strip_seam_law):
        src = Path(inspect.getsourcefile(mod)).read_text()
        for banned in RETIRED_HEALER_SPELLINGS:
            assert not re.search(banned, src), (
                f"{mod.__name__} still spells a strip-seam threshold with "
                f"a retired bare-'seam' name ({banned}) — use "
                f"STRIP_SEAM_TEAR_*")


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
