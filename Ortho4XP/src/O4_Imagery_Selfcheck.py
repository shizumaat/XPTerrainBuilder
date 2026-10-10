"""Does every bundled imagery definition file become a registry entry?

The imagery twin of ``O4_Airport_Elevation_Insets.provider_registry_
selfcheck`` (issues #539, #510), run by ``--import-selfcheck`` in the
frozen binary: the provider ``.lay`` / ``.comb`` files, the extents and
the colour filters are data beside the executable, and one that is missing
from the bundle or read in the wrong encoding is no error anywhere -- only
a provider gone from the menu.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import O4_File_Names as FNAMES
import O4_Text_Files as TEXT

__all__ = ["imagery_registry_selfcheck"]

_NAME = "imagery provider registry"


def _definition_files(directory: str, extension: str, nested: bool,
                      accepts) -> Dict[str, str]:
    """``{code: path}`` of the definition files the registry walk reads:
    one level of sub-directories when ``nested``, the directory itself
    otherwise."""
    folders = [directory]
    if nested:
        folders = [os.path.join(directory, name)
                   for name in sorted(os.listdir(directory))
                   if os.path.isdir(os.path.join(directory, name))]
    return {name.split(".")[0]: os.path.join(folder, name)
            for folder in folders for name in sorted(os.listdir(folder))
            if accepts(name, extension)}


def _not_utf8(path: str, values) -> bool:
    """Is the file not UTF-8, or a parsed non-ASCII value not its text?"""
    try:
        with open(path, "rb") as handle:
            text = handle.read().decode(TEXT.SHIPPED_ENCODING)
    except (OSError, UnicodeDecodeError):
        return True
    return any(isinstance(value, str) and not value.isascii()
               and value not in text for value in values)


def imagery_registry_selfcheck(
        provider_dir: Optional[str] = None, extent_dir: Optional[str] = None,
        filter_dir: Optional[str] = None) -> Tuple[bool, str]:
    """``(ok, line)`` for ``--import-selfcheck``.

    The binary parses its OWN bundled ``Providers`` / ``Extents`` /
    ``Filters`` and fails when a ``.lay``, ``.comb``, ``.ext`` or ``.flt``
    file is missing from its registry, when a file is not UTF-8, or when
    a parsed non-ASCII value is not the file's UTF-8 text.  The registries
    in force are left as they were found.
    """
    import O4_Imagery_Utils as IMG

    directories = {"Provider_dir": provider_dir or FNAMES.Provider_dir,
                   "Extent_dir": extent_dir or FNAMES.Extent_dir,
                   "Filter_dir": filter_dir or FNAMES.Filter_dir}
    for directory in directories.values():
        if not os.path.isdir(directory):
            return (False, "%s: FAIL no directory %s" % (_NAME, directory))
    accepts = IMG._is_registry_file
    files = {
        "lay": _definition_files(directories["Provider_dir"], "lay", True,
                                 accepts),
        "comb": _definition_files(directories["Provider_dir"], "comb", False,
                                  accepts),
        "ext": _definition_files(directories["Extent_dir"], "ext", True,
                                 accepts),
        "flt": _definition_files(directories["Filter_dir"], "flt", False,
                                 accepts)}
    registries = {"lay": IMG.providers_dict,
                  "comb": IMG.combined_providers_dict,
                  "ext": IMG.extents_dict, "flt": IMG.color_filters_dict}
    in_force = {kind: dict(registry) for (kind, registry)
                in registries.items()}
    paths_in_force = {name: getattr(FNAMES, name) for name in directories}
    try:
        for (name, directory) in directories.items():
            setattr(FNAMES, name, directory)
        for (kind, registry) in registries.items():
            # Only what THIS parse reads may answer for a file; the
            # built-in entries no file defines ("global", "none") stay.
            for code in files[kind]:
                registry.pop(code, None)
        IMG.initialize_extents_dict()
        IMG.initialize_color_filters_dict()
        IMG.initialize_providers_dict()
        IMG.initialize_combined_providers_dict()
        parsed = {kind: dict(registry) for (kind, registry)
                  in registries.items()}
    finally:
        for (name, directory) in paths_in_force.items():
            setattr(FNAMES, name, directory)
        for (kind, registry) in registries.items():
            registry.clear()
            registry.update(in_force[kind])
    absent: List[str] = []
    garbled: List[str] = []
    for (kind, by_code) in files.items():
        for (code, path) in sorted(by_code.items()):
            entry = parsed[kind].get(code)
            if entry is None:
                absent.append("%s.%s" % (code, kind))
            values = entry.values() if isinstance(entry, dict) else ()
            if _not_utf8(path, values):
                garbled.append("%s.%s" % (code, kind))
    total = sum(len(by_code) for by_code in files.values())
    if files["lay"] and not (absent or garbled):
        return (True, "%s: ok %d providers, %d combined, %d extents, "
                "%d filters" % ((_NAME,) + tuple(
                    len(files[kind]) for kind in ("lay", "comb", "ext",
                                                  "flt"))))
    parts = ["%d of %d files" % (total - len(absent), total)]
    if absent:
        parts.append("not parsed " + ",".join(absent))
    if garbled:
        parts.append("not read as UTF-8 " + ",".join(garbled))
    return (False, "%s: FAIL %s" % (_NAME, "; ".join(parts)))
