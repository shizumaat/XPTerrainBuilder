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

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (os.path.join(_ROOT, "src"), os.path.join(_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from harness.law_support import (           # noqa: E402
    contiguity, corridor, grade_graph, grade_law, roles, strip_seam, transect)

#: harness module -> the v1 modules its definitions were copied from.
SOURCES = {
    roles: ("auto_patch.layout", "auto_patch.pavement.strips"),
    strip_seam: ("auto_patch.strip_seam_law",),
    grade_law: ("auto_patch.grade_law",),
    grade_graph: ("auto_patch.grade_graph",),
    contiguity: ("auto_patch.lateral_contiguity", "auto_patch.lateral_spine_nodes",
                 "auto_patch.enclaves", "auto_patch.gap_fill",
                 "auto_patch.adjacent_ground"),
    corridor: ("auto_patch.elevation_per_surface.route_profile.apron_terrace",),
    transect: ("auto_patch.transect_walk",),
}

#: The four collapsed flag reads (package docstring, "THE ONE DELIBERATE
#: CHANGE").  A source pair differing ONLY by one of these lines is a match.
_FLAG_COLLAPSE = (
    'if fabric_flags.on(', 'if not fabric_flags.on(',
    'if True:', 'if False:',
)


def _v1(module_name):
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def _harness_defs(mod):
    """Top-level names the harness module DEFINES (not the ones it imports)."""
    tree = ast.parse(inspect.getsource(mod))
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append(n.name)
        elif isinstance(n, ast.Assign):
            out.extend(t.id for t in n.targets if isinstance(t, ast.Name))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.append(n.target.id)
    return out


#: The import spellings the copy rewrote: the harness form on the left, the v1
#: form on the right.  A rewritten import is not drift — a rewritten BODY is.
_IMPORT_FORMS = (
    ("from .roles import", "from .layout import"),
    ("from .strip_seam import", "from .strip_seam_law import"),
    ("from .contiguity import", "from .lateral_contiguity import"),
    ("from .contiguity import", "from .lateral_spine_nodes import"),
    ("from .contiguity import", "from .enclaves import"),
    ("from .contiguity import", "from .gap_fill import"),
    ("from .contiguity import", "from .adjacent_ground import"),
    ("from .transect import", "from .transect_walk import"),
    ("from .corridor import",
     "from .elevation_per_surface.route_profile.apron_terrace import"),
    ("from auto_patch.config import", "from .config import"),
    ("from auto_patch import config as", "from . import config as"),
)


def _normalise(text):
    """Source with the collapsed flag lines dropped and the rewritten import
    spellings canonicalised, so only a BODY change reads as drift."""
    keep = []
    for line in text.splitlines():
        if any(m in line for m in _FLAG_COLLAPSE):
            continue
        st = line.strip()
        if st.startswith("from ") or st.startswith("import "):
            for ours, theirs in _IMPORT_FORMS:
                if st.startswith(ours):
                    line = line.replace(ours, "IMPORT", 1)
                elif st.startswith(theirs):
                    line = line.replace(theirs, "IMPORT", 1)
        keep.append(line.rstrip())
    return "\n".join(keep)


@pytest.mark.parametrize("harness_module", list(SOURCES))
def test_every_copied_definition_is_the_v1_definition(harness_module):
    """Round-1 lockstep: the copy has not drifted from what it copied."""
    originals = [m for m in (_v1(n) for n in SOURCES[harness_module]) if m]
    if not originals:
        pytest.skip("the v1 modules are deleted (round 2) — nothing to compare")
    checked = compared = 0
    for name in _harness_defs(harness_module):
        if name.startswith("__"):
            continue
        ours = getattr(harness_module, name, None)
        theirs = None
        for src in originals:
            if hasattr(src, name):
                theirs = getattr(src, name)
                break
        if theirs is None:
            continue
        checked += 1
        if inspect.isfunction(ours) or inspect.isclass(ours):
            try:
                a, b = inspect.getsource(ours), inspect.getsource(theirs)
            except OSError:                       # pragma: no cover
                continue
            assert _normalise(a) == _normalise(b), (
                f"{harness_module.__name__}.{name} has DRIFTED from "
                f"{theirs.__module__}.{name}")
            compared += 1
        else:
            assert ours == theirs, (
                f"{harness_module.__name__}.{name} = {ours!r} but "
                f"the v1 value is {theirs!r}")
            compared += 1
    assert checked and compared, (
        f"{harness_module.__name__}: nothing was compared — the twin is vacuous")


def test_the_flag_collapse_is_exactly_four_lines_and_all_default_on():
    """The one deliberate change, pinned: four reads, every flag DEFAULT-ON."""
    v1_law = _v1("auto_patch.grade_law")
    if v1_law is None:
        pytest.skip("v1 deleted (round 2)")
    flags = _v1("auto_patch.fabric_flags")
    ours = inspect.getsource(grade_law)
    theirs = inspect.getsource(v1_law)
    names = [n for n in ("O4_FABRIC_W2_RETIRE_APRON_SURROUND",
                         "O4_FABRIC_W2_RETIRE_SERVICE_SHADOW",
                         "O4_FABRIC_W2_ICAO_STRIP_AUTHORITY",
                         "O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY")
             if f'fabric_flags.on("{n}")' in theirs]
    assert len(names) == 4, names
    assert "fabric_flags" not in ours.replace("# ", "").replace(
        "fabric_flags registry", "")
    for n in names:
        assert flags.on(n), f"{n} is NOT default-on — the collapse changes law"


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
        tree = ast.parse(path.read_text())
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
