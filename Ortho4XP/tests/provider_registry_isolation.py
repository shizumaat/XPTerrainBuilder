"""Per-test isolation of the elevation provider registry (issue #510).

``O4_Airport_Elevation_Insets.elevation_providers_dict`` is a MODULE GLOBAL
that ``initialize_elevation_providers_dict(directory)`` REBINDS, and every
reader fills it lazily with ``if not elevation_providers_dict: initialize()``.
A twin that parses a scratch directory of ``.elv`` files therefore leaves a
non-empty registry holding only its own fakes, and the next lazy reader on
the same xdist worker trusts it.  ``snapshot`` / ``restore`` put the registry
back to what the test found; ``conftest`` wraps every test in the pair.
"""

import sys

__all__ = ["REGISTRY_MODULE", "snapshot", "restore"]

REGISTRY_MODULE = "O4_Airport_Elevation_Insets"
_ATTRIBUTE = "elevation_providers_dict"


def _one_level(registry):
    """The registry's entries, each definition copied one level deep."""
    return {code: dict(definition) if isinstance(definition, dict)
            else definition for code, definition in registry.items()}


def snapshot():
    """What ``restore`` needs: the module, its registry object, its entries,
    and a one-level copy of each definition.  ``None`` while the engine
    module is not imported (it is never imported from here: that would pull
    the engine into every test)."""
    module = sys.modules.get(REGISTRY_MODULE)
    registry = getattr(module, _ATTRIBUTE, None)
    if not isinstance(registry, dict):
        return None
    return module, registry, dict(registry), _one_level(registry)


def restore(saved):
    """Rebind the registry ``snapshot`` saw and put its entries back.

    With no snapshot (the test itself imported the engine module) the
    registry returns to its import state, empty, so the next reader parses
    the shipped directory.  Returns True when the test had left the registry
    different from how it found it."""
    if saved is None:
        module = sys.modules.get(REGISTRY_MODULE)
        if not getattr(module, "__file__", None):
            return False   # absent, or a stand-in module a test installed
        left = bool(getattr(module, _ATTRIBUTE, None))
        setattr(module, _ATTRIBUTE, {})
        return left
    module, registry, entries, definitions = saved
    changed = (getattr(module, _ATTRIBUTE, None) is not registry
               or _one_level(registry) != definitions
               or any(registry[code] is not entries[code] for code in entries))
    if changed:
        for code, definition in entries.items():
            if isinstance(definition, dict):
                definition.clear()
                definition.update(definitions[code])
        registry.clear()
        registry.update(entries)
        setattr(module, _ATTRIBUTE, registry)
    return changed
