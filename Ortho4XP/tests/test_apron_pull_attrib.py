"""Twin for ``tools/apron_pull_attrib.py`` — the binding-constraint reader.

Known-answer on hand-built arms: the tool derives no law and must classify
each node by the same precedence its docstring states.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import apron_pull_attrib as APA                                # noqa: E402


def _arm(**kw):
    base = dict(z={}, role={}, dem={}, adj={}, clamped=set(), transect={})
    base.update(kw)
    return base


def test_a_band_clamped_node_is_attributed_to_the_band_first():
    """Precedence matters: a clamped node may ALSO have tight edges, and
    the clamp is the thing that actually set its value."""
    arm = _arm(z={"a": 10.0, "b": 12.0}, role={"a": "apron", "b": "apron"},
               dem={"a": 10.0, "b": 12.0}, adj={"a": [("b", 0.1)]},
               clamped={"a"})
    assert APA.classify(arm, "a")[0] == "band"


def test_a_bound_transect_to_a_dem_far_side_is_named():
    arm = _arm(z={"a": 10.0, "b": 5.0}, role={"a": "apron", "b": "apron"},
               dem={"a": 10.0, "b": 5.0}, transect={"a": {"b"}})
    assert APA.classify(arm, "a")[0] == "transect"


def test_a_tight_edge_to_dem_following_ground_is_a_weld():
    """The membrane hung from a DEM edge — a NON-apron neighbour on the
    terrain, reached by an edge carrying its whole budget."""
    arm = _arm(z={"a": 10.0, "b": 9.0},
               role={"a": "apron", "b": "graded_strip"},
               dem={"a": 12.0, "b": 9.0}, adj={"a": [("b", 1.0)]})
    cls, why = APA.classify(arm, "a")
    assert cls == "weld_ground" and "graded_strip" in why


def test_the_pull_propagating_inside_the_apron_is_its_own_class():
    arm = _arm(z={"a": 10.0, "b": 9.0}, role={"a": "apron", "b": "apron"},
               dem={"a": 12.0, "b": 9.0}, adj={"a": [("b", 1.0)]})
    assert APA.classify(arm, "a")[0] == "weld_apron"


def test_no_tight_edge_is_the_convergence_class():
    """Nothing held this node at the DEM — the value simply returned
    there.  A slack edge must never be read as a constraint."""
    arm = _arm(z={"a": 10.0, "b": 10.2}, role={"a": "apron", "b": "apron"},
               dem={"a": 10.0, "b": 10.2}, adj={"a": [("b", 5.0)]})
    cls, why = APA.classify(arm, "a")
    assert cls == "unbound" and "tight" in why


def test_every_class_is_declared():
    assert set(APA.CLASSES) == {"band", "transect", "weld_ground",
                                "weld_apron", "unbound"}


def test_the_tool_is_in_the_index():
    idx = (_ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "Ortho4XP/tools/apron_pull_attrib.py" in idx


# ══════════════════════════════════════════════════════════════════════
# THE --way / --site SCOPE (promoted 2026-08-28 from the hecar2 lane's
# ``tmp/way_authority_read.py`` on its SECOND use, RULINGS 7e90032)
# ══════════════════════════════════════════════════════════════════════

def test_the_way_scope_names_the_tight_edges_and_prices_no_law():
    """It answers "who authors the values on this way" — per node the
    emitted value, the DEM under it, and every enforced edge with its
    budget and whether it is TIGHT.  It derives no law: the budgets come
    verbatim from the sidecar's ``pair_caps`` through ``load_arm``."""
    import inspect
    src = inspect.getsource(APA.way_authority)
    assert 'arm["adj"]' in src, "budgets must come from the sidecar graph"
    assert "WAY_TIGHT_TOL_M" in src
    doc = inspect.getdoc(APA.way_authority)
    assert "counts no defects" in doc
    assert "census.py" in doc


def test_the_way_scope_is_a_parameter_on_the_near_fit_not_a_fork():
    """RULINGS 7e90032: extend a near-fit (a parameter, a subcommand);
    never fork it.  The scope lives in ``apron_pull_attrib`` and shares
    its ``load_arm`` — there is no second loader."""
    import inspect
    src = inspect.getsource(APA)
    assert src.count("def load_arm") == 1
    main_src = inspect.getsource(APA.main)
    assert '"--way"' in main_src and '"--site"' in main_src
    assert "load_arm(a.patch" in main_src
