"""THE FROZEN BUNDLE'S IMPORT SMOKE TEST — ``<engine> --import-selfcheck
MODULE[,MODULE...]`` (#130, #510, #539): every named module imports in THIS
interpreter, and the registries the engine reads lazily by key (elevation
access strategies, provider files, imagery definitions) are whole.

Moved out of ``O4_Proj_Runtime`` (#836): that module is imported by every
tile step, and this check's imports (the elevation registry, the insets,
the imagery self-check) put them in every step's code key.  The entry
files (``Ortho4XP.py``, ``Ortho4XP_Qt.py``) are its only callers.
"""
from __future__ import annotations

__all__ = ["import_selfcheck_main"]


def import_selfcheck_main(argv: list[str]) -> int:
    """``--import-selfcheck MODULE[,MODULE...]``: exit 0 when every named
    module imports in THIS interpreter -- the frozen bundle's smoke test
    for packages the engine imports LAZILY (laspy, #130: the static scan
    never sees a function-level import, the highspy precedent of
    2026-09-10).  One line per module on stdout, then one line for the
    elevation access registry (:func:`elevation_access.registry.
    registry_selfcheck`): the number of registered strategy keys, and a
    failure naming the missing and the unexpected ones; then one line for
    the bundled provider files (:func:`O4_Airport_Elevation_Insets.
    provider_registry_selfcheck`) and one for the bundled imagery
    definitions (:func:`O4_Imagery_Selfcheck.imagery_registry_selfcheck`)."""
    import importlib

    names = [name.strip() for name in
             argv[argv.index("--import-selfcheck") + 1].split(",")
             if name.strip()]
    failed = 0
    for name in names:
        try:
            module = importlib.import_module(name)
            line = "%s: ok %s" % (name, getattr(module, "__version__", ""))
        except Exception as error:
            failed += 1
            line = "%s: %s: %s" % (name, type(error).__name__, error)
        try:
            print(line.rstrip())
        except Exception:
            pass
    # The elevation access strategies are looked up BY KEY, so a strategy
    # module missing from the bundle is no ImportError anywhere -- the
    # binary counts its own registry against the pinned set.
    try:
        from elevation_access.registry import registry_selfcheck

        (registry_ok, line) = registry_selfcheck()
    except Exception as error:
        (registry_ok, line) = (False, "elevation_access registry: %s: %s"
                               % (type(error).__name__, error))
    if not registry_ok:
        failed += 1
    try:
        print(line.rstrip())
    except Exception:
        pass
    # The provider FILES are data beside the binary, read lazily on first
    # use: a file the bundle lacks or cannot decode is no error anywhere,
    # only a provider gone from the ladder (#510).
    try:
        from O4_Airport_Elevation_Insets import provider_registry_selfcheck

        (providers_ok, line) = provider_registry_selfcheck()
    except Exception as error:
        (providers_ok, line) = (False, "elevation provider registry: %s: %s"
                                % (type(error).__name__, error))
    if not providers_ok:
        failed += 1
    try:
        print(line.rstrip())
    except Exception:
        pass
    # The imagery definitions (.lay / .comb / extents / filters) are the
    # same kind of data, parsed at start-up (#539).
    try:
        from O4_Imagery_Selfcheck import imagery_registry_selfcheck

        (imagery_ok, line) = imagery_registry_selfcheck()
    except Exception as error:
        (imagery_ok, line) = (False, "imagery provider registry: %s: %s"
                              % (type(error).__name__, error))
    if not imagery_ok:
        failed += 1
    try:
        print(line.rstrip())
    except Exception:
        pass
    return 0 if names and not failed else 1
