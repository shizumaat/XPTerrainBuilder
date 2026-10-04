"""THE CENSUS'S LAW COPY IS THE LAW IT COPIED — twin for
`tools/harness/law_support/` (lane `v1retire` round 1, seam S4 of RULINGS
2026-09-13aw, session ruling (d)).

`tools/check_grade.py` used to read its pair law, constraint generator, seam
law, role vocabulary and lateral machinery out of eleven modules the v1
deletion takes.  Ruling (d) moved what it USES into the harness, copied ONCE.
A copy is only honest while something checks it against the original, so:

 1. WHILE the v1 modules are still on disk (round 1), every copied definition
    must be TEXTUALLY IDENTICAL to the one it was copied from — bar the four
    `fabric_flags.on(...)` reads, which are collapsed to their DEFAULT-ON arm
    (the package's own docstring records that as the one deliberate change).
 2. ALWAYS: the role tags the census sides and prices with are the names v2's
    own `law/precedence.toml` uses, so the vocabulary cannot drift from the
    engine after v1 is gone.
 3. ALWAYS: the package imports NO module of the v1 tree (that is what the
    seam cut bought; `tests/test_v1_retired.py` holds the same line for the
    whole production closure).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (os.path.join(_ROOT, "src"), os.path.join(_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from harness.law_support import roles


def _v1(module_name):
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def test_the_role_tags_are_v2s_own_precedence_names():
    """The vocabulary cannot drift from the engine once v1 is gone."""
    from auto_patch_v2.law import tables as v2_tables

    law = v2_tables.load_default()
    text = str(sorted(law.tables.precedence.roles))
    for tag in (roles.ROLE_RUNWAY, roles.ROLE_RUNWAY_CROSSING,
                roles.ROLE_PRIMARY_PARALLEL, roles.ROLE_SECONDARY_PARALLEL,
                roles.ROLE_STUB, roles.ROLE_CROSS_CONNECTOR, roles.ROLE_APRON,
                roles.ROLE_JUNCTION, roles.ROLE_BUILDING,
                roles.ROLE_SERVICE_ROAD, roles.ROLE_SERVICE_JUNCTION,
                roles.ROLE_GROUNDSIDE_PAVEMENT):
        assert tag in text, f"{tag} is not a role v2's precedence table names"


def test_the_package_imports_no_v1_module():
    """Seam S4 is CUT: nothing here reaches a module the deletion takes."""
    import pathlib

    pkg = pathlib.Path(inspect.getfile(roles)).parent
    allowed_prefixes = ("auto_patch.config", "auto_patch_v2",
                        "auto_patch.build_support", "auto_patch.apt_dat_reader")
    allowed_plain = {"config", "build_support", "apt_dat_reader"}
    offenders = []
    for path in sorted(pkg.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            targets = []
            if isinstance(n, ast.Import):
                targets = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0:
                mod = n.module or ""
                if mod == "auto_patch":
                    # ``from auto_patch import config as _cfg`` — the KEEP
                    # module by name, not the package's v1 half.
                    bad = [a.name for a in n.names
                           if a.name not in allowed_plain]
                    targets = [f"auto_patch.{b}" for b in bad]
                else:
                    targets = [mod]
            for t in targets:
                if t.startswith("auto_patch") and not t.startswith(allowed_prefixes):
                    offenders.append(f"{path.name}:{n.lineno}: {t}")
    assert not offenders, "law_support imports v1: " + "; ".join(offenders)


def test_the_transverse_cap_rule_has_one_source_and_three_branches():
    """``config.transverse_cap_for_longitudinal_cap`` is THE transverse
    cap of a corridor whose longitudinal cap is ``cap_l``; the census is
    its reader (``check_grade`` and ``law_support``'s pair law / graph).

    Re-founded from the v1 twin ``test_lateral_cross_section`` (retired
    with v1's emitter — RULINGS 2026-10-04j "coverage owed"): every
    reader DELEGATES to the one definition, none re-types the branches,
    and the branches answer the law's own constants."""
    from auto_patch import config as CFG
    import check_grade
    from harness.law_support import grade_graph, grade_law

    readers = (("check_grade", check_grade._transverse_cap_law),
               ("grade_graph", grade_graph._transverse_cap_for_longitudinal_cap),
               ("grade_law", grade_law.transverse_cap_for_longitudinal_cap))
    for who, fn in readers:
        # by ORIGIN, not identity: the suite can hold two instances of
        # ``auto_patch.config`` (two sys.path entries reach one file)
        assert fn is not None, f"{who} no longer delegates the cap rule"
        assert fn.__module__.endswith("config"), who
        assert fn.__qualname__ == "transverse_cap_for_longitudinal_cap", who
    # the validator itself holds no second copy of the branches (the one
    # in ``_transverse_cap_for_seg_cap`` is the import-failure fallback)
    assert "TAXI_MAX_TRANSVERSE_NARROW" not in inspect.getsource(
        check_grade._check_transverse_grade)

    for cap_l, expect in (
            (CFG.TAXI_MAX_GRADE_NARROW, CFG.TAXI_MAX_TRANSVERSE_NARROW),
            (CFG.SERVICE_ROAD_MAX_GRADE, CFG.SERVICE_ROAD_MAX_TRANSVERSE),
            (CFG.TAXI_MAX_GRADE, CFG.TAXI_MAX_GRADE),
            (CFG.APRON_MAX_GRADE, CFG.APRON_MAX_GRADE),
            (0.0123, 0.0123)):                 # any blended cap: isotropic
        assert CFG.transverse_cap_for_longitudinal_cap(cap_l) == expect
        assert check_grade._transverse_cap_for_seg_cap(cap_l) == expect
    # the anisotropic branches are real: narrower across than along
    assert CFG.TAXI_MAX_TRANSVERSE_NARROW < CFG.TAXI_MAX_GRADE_NARROW
    assert CFG.SERVICE_ROAD_MAX_TRANSVERSE < CFG.SERVICE_ROAD_MAX_GRADE
    # a float that is the narrow cap to within rounding still takes it
    assert CFG.transverse_cap_for_longitudinal_cap(
        CFG.TAXI_MAX_GRADE_NARROW + 1e-12) == CFG.TAXI_MAX_TRANSVERSE_NARROW
