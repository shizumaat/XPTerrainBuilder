"""THE ONE SITE where the engine asks whether a CHILD PROCESS may write.

Issue #159, RULINGS 2026-09-30bs (the osmium clip) and 2026-09-30bw (the
GDAL rasters).  ``tools/harness/shared_repo_guard.SharedRepoWriteGuard``
patches ``builtins.open`` and the ``os`` write family, so it refuses every
PYTHON write into the shared data repo at the call.  A write a child
process makes passes none of those: lane tx154's clip cutter spawned
``osmium extract --output <corpus>/....tmp-52850-....osm.pbf`` with the
guard armed and osmium wrote 10.5 MB into the shared
``OSM_data/_regional_extracts/clips/`` through the mounted symlink.  Eight
older strays show the hole predates that lane.

A SPAWN IS A WRITE DECLARATION.  The launcher knows the output path before
the child exists, so it declares it HERE and the child is never started
when an armed guard refuses that path.  That is the whole mechanism: no
sandbox, no filesystem permissions, one question asked one place.

WHY THE LOOKUP.  The engine must not import the harness (the harness is a
measurement tool that imports the engine, and ``src/`` is also shipped
inside the app bundle without ``tools/``).  So this module finds whichever
loaded module exposes the harness's own ``refuse_external_write`` /
``external_write_refusal`` and asks it; with no guard armed — every
production run, and every run of the Qt app — nothing is loaded, every
function here is a no-op, and the spawn proceeds exactly as before.

The guard RECORDS what it refuses here, so a caller that swallows the
refusal and falls back is caught by the harness's swallowed-refusal
detector (``require_no_swallowed_write_block``) exactly as a swallowed
Python-level refusal is.  That is deliberate: a spawn is not a
best-effort write — the build wants that output — which is why this module
is separate from the best-effort question
``elevation_access.downloads._write_refused_by_armed_guard`` asks.
"""
from __future__ import annotations

import sys
import types
from typing import Iterable, Optional

#: The harness attributes this module looks for.  BOTH must be present on
#: the same module object: ``_ACTIVE_GUARDS`` is the guard registry, and
#: finding a bare function of the right name on some unrelated module (or a
#: mock parked in ``sys.modules``) must never be mistaken for the harness.
_GUARD_REGISTRY_ATTR = "_ACTIVE_GUARDS"
_ASK_ATTR = "external_write_refusal"
_REFUSE_ATTR = "refuse_external_write"


class ExternalWriteRefused(RuntimeError):
    """A child process was about to write a path an armed shared-repo write
    guard refuses, and was not started.

    Raised INSTEAD of the harness's own ``SharedRepoWriteBlocked`` only
    when the harness is not importable from here, which it never is: the
    normal path re-raises the harness's exception unchanged, so a lane sees
    one exception type for a refused write whatever made it.
    """


def _harness_namespaces() -> Iterable[dict]:
    """Every loaded module that looks like the harness's write guard."""
    for module in list(sys.modules.values()):
        if not isinstance(module, types.ModuleType):
            continue                     # a mock parked in sys.modules
        namespace = getattr(module, "__dict__", {})
        if not isinstance(namespace.get(_GUARD_REGISTRY_ATTR), list):
            continue
        if callable(namespace.get(_ASK_ATTR)):
            yield namespace


def refusal_for(path) -> Optional[tuple]:
    """``(relpath, scope)`` when an armed guard would refuse ``path``.

    ``None`` when none would, and ``None`` when no guard is loaded at all.
    Asks only; records nothing.  Use it to CHOOSE a lawful path; use
    :func:`declare_external_write` when the spawn is going ahead.
    """
    for namespace in _harness_namespaces():
        try:
            hit = namespace[_ASK_ATTR](path)
        except Exception:
            continue
        if hit:
            return (hit[0], hit[1])
    return None


def declare_external_write(path, *, writer: str) -> None:
    """DECLARE that a child process is about to write ``path``.

    Raises when an armed shared-repo write guard refuses it (the harness's
    own ``SharedRepoWriteBlocked``, recorded in ``guard.blocked`` with
    ``via='spawn <writer> writing'``), so the caller never spawns the
    child.  Returns ``None`` — and costs one ``sys.modules`` walk — when no
    guard is armed, which is every production run.

    ``writer`` is the child's name as a human would say it (``osmium``,
    ``DSFTool``, ``lerc-worker``): it is what the refusal and the
    swallowed-refusal report name, and "a subprocess" is not an answer a
    lane can act on.
    """
    if path is None:
        return
    asked = False
    for namespace in _harness_namespaces():
        refuse = namespace.get(_REFUSE_ATTR)
        if not callable(refuse):
            continue
        asked = True
        refuse(path, writer=writer)      # raises when it refuses
    if asked:
        return
    # A guard registry with no ``refuse_external_write``: an older harness.
    # Fall back to the ASK half so the write is still refused, just without
    # the record only the harness can make.
    hit = refusal_for(path)
    if hit is not None:
        rel, scope = hit
        raise ExternalWriteRefused(
            f"REFUSING to spawn {writer}: it would write '{rel}' in the "
            f"SHARED data repo, which no --refresh-data scope authorises "
            f"(scope {scope or '<outside every named scope>'}).  Owner "
            f"ruling e9daef5: a cache regeneration is an EXPLICIT, locked, "
            f"hash-stamped event — never a build side effect.")


def declare_external_writes(paths, *, writer: str) -> None:
    """:func:`declare_external_write` for every path a child will write.

    The FIRST refusal raises, which is the whole contract: the child is not
    started, so no later path matters.
    """
    for path in paths or ():
        declare_external_write(path, writer=writer)
