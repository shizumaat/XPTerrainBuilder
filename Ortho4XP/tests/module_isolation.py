"""Stand-in engine modules that leave ``sys.modules`` as they found it (#639).

A twin that puts a stand-in for a first-party module into ``sys.modules``
changes what EVERY import on its xdist worker resolves to while it is there,
and two things outlive a per-name restore:

  * a real module first imported UNDER the stand-in stays cached, bound to
    the stand-in's names (``from .load import Inputs`` kept the stub class);
  * a path-less stand-in for a PACKAGE answers ``from pkg import sub`` only
    when an earlier test already cached the real ``pkg.sub`` — the import
    statement falls back to ``sys.modules["pkg.sub"]`` — so the twin is
    green or red by test order (``cannot import name 'object_plan' from
    'auto_patch_v2.airport' (unknown location)``).

``install`` answers both: a stand-in for a package carries the real
package's ``__path__`` (its unstubbed submodules resolve in any order), and
every ``sys.modules`` entry under the top-level names it touches is
snapshotted and put back EXACTLY by ``restore_all``, which ``conftest`` runs
after each test.  ``left_behind`` is the guard: what a test left that is not
the engine's own module.
"""

import importlib.util
import os
import sys
import types

__all__ = ["SRC", "first_party", "install", "restore_all", "left_behind",
           "evict"]

#: The engine's source root; a first-party module is one that lives here.
SRC = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    os.pardir, "src"))


def _top_level_names():
    """Every importable top-level name under ``src`` (``auto_patch``,
    ``auto_patch_v2``, ``o4_engine``, ``elevation_access``, ``O4_*``)."""
    names = set()
    for entry in os.listdir(SRC):
        path = os.path.join(SRC, entry)
        if entry.endswith(".py"):
            names.add(entry[:-3])
        elif os.path.isfile(os.path.join(path, "__init__.py")):
            names.add(entry)
    return frozenset(names)


_FIRST_PARTY = _top_level_names()

#: Open snapshots, ``{top-level name: {module name: module}}``; a name is
#: snapshotted once per test, before the first stand-in under it goes in.
_open = {}

#: ``{module name: module}`` already seen to be the engine's own, so the
#: per-test guard re-reads only what changed.
_known_real = {}


def first_party(name):
    """True when ``name`` is an engine module or lives in an engine package."""
    return name.partition(".")[0] in _FIRST_PARTY


def _under(roots):
    return {name: module for name, module in list(sys.modules.items())
            if name.partition(".")[0] in roots}


def _package_path(name):
    """The real package's search path for ``name``, or None for a plain
    module or a name the engine does not have.  Asked of whatever holds
    the name now first: a second ``install`` in one test finds the first
    one's stand-in there, which has no spec to ask."""
    held = getattr(sys.modules.get(name), "__path__", None)
    if held:
        return list(held)
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None
    locations = getattr(spec, "submodule_search_locations", None)
    return list(locations) if locations else None


def install(stand_ins, *, also=()):
    """Put ``stand_ins`` (``{module name: module}``) into ``sys.modules``
    until the end of the running test.

    ``also`` names further top-level modules to put back afterwards — the
    one a twin pops so that it re-imports against the stand-ins.
    """
    roots = {name.partition(".")[0] for name in stand_ins} | set(also)
    paths = {name: _package_path(name) for name in stand_ins
             if not hasattr(stand_ins[name], "__path__")}
    for root in roots - set(_open):
        _open[root] = _under({root})
    for name, module in stand_ins.items():
        if paths.get(name):
            module.__path__ = paths[name]
        sys.modules[name] = module


def _forget(name, module):
    """Drop ``name`` from ``sys.modules`` and from its parent's namespace."""
    sys.modules.pop(name, None)
    parent, _, leaf = name.rpartition(".")
    owner = sys.modules.get(parent) if parent else None
    if owner is not None and getattr(owner, leaf, None) is module:
        delattr(owner, leaf)


def restore_all():
    """Put every snapshotted name back: what was there returns, and what was
    imported while a stand-in was in place is forgotten (deepest first, so a
    parent is still there to forget its child)."""
    saved = {}
    for snapshot in _open.values():
        saved.update(snapshot)
    roots = set(_open)
    _open.clear()
    if not roots:
        return
    sys.modules.update(saved)
    for name, module in sorted(_under(roots).items(), reverse=True):
        if name not in saved:
            _forget(name, module)


def _is_real(module):
    """The engine's own module: a module object whose file (or, for a
    namespace package, search path) is under ``src``."""
    if not isinstance(module, types.ModuleType):
        return False
    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None) or getattr(module, "__file__", None)
    if origin and origin not in ("namespace", "built-in", "frozen"):
        return os.path.realpath(origin).startswith(SRC + os.sep)
    return any(os.path.realpath(p).startswith(SRC + os.sep)
               for p in getattr(module, "__path__", ()))


def left_behind():
    """The first-party names in ``sys.modules`` that are NOT the engine's own
    module — a stand-in a test put there and did not take out.  A name that
    is simply absent (an optional module never imported) is not listed."""
    leaked = []
    for name, module in list(sys.modules.items()):
        if _known_real.get(name) is module or not first_party(name):
            continue
        if _is_real(module):
            _known_real[name] = module
        else:
            leaked.append(name)
    return sorted(leaked)


def evict(names):
    """Take the named stand-ins out, so one leak fails one test and not
    every later test on the worker."""
    for name in names:
        _forget(name, sys.modules.get(name))
