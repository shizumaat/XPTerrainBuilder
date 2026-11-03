"""THE USER'S "OPTIMISE PACK" (issue #1707): a heavy airport pack's DSF
written lighter, as a RECORDED DECISION re-applied on every write.

Owner (2026-10-30, chose option b): an opt-in "optimise pack" option,
applied only to the rebaked copy of the pack, per pack, reversible from
the pristine backup; every rule general (size-, duplicate- and texture-
derived), none naming an airport.  And (2026-10-31, after 1.0.454 lost a
hand optimisation on rebuild): "the optimisations must be applied inside
``write_pack``, re-applied on every write from the pristine file, the
same way an accepted #1360 forest upgrade is."

So the optimisation is a RECIPE, not an edit: ``dsf_write.write_pack
(optimise=)`` applies it to the dump of the PRISTINE DSF on every write,
the record beside the DSF holds it (:func:`record`), and every later
write re-applies it while the pristine file is the one it was accepted
for (:func:`recorded`).  Vendor files are never written.

The operations, one module each (spec
``docs/specs/pack-optimise-1707-20261103.md``):

* D1 ``dedupe`` — duplicate placements dropped (same definition and row
  kind, within 0.2 m, heading within 1°, same height).
* D2 ``swap`` — heavy vehicles and ground equipment re-pointed at
  X-Plane's library equivalents (name and footprint witnessed, lights
  kept in a lights-only copy); the match is made once, when the user
  accepts (:func:`build_recipe`), and recorded in the recipe.
* O1 + O2 ``objcopy`` — a lighter copy of a pack object: its specular
  made global so it instances, a size-derived draw distance with its
  lights kept beyond it; the DSF names the copy (D3).
* ``weight`` — the triangles the pack's own objects draw, before and
  after: what the offer is made on.

Every file the recipe needs beside the vendor's (a lights-only copy, an
object copy) is NEW, named ``<stem>.o4opt…``, written on every write
from the vendor file (:func:`write_generated`) and listed in the
record's ``generated``; Undo removes it.
"""
from __future__ import annotations

import hashlib
import json
import os
import typing as _t

from . import dedupe as _dd
from . import objcopy as _oc
from . import swap as _sw

__all__ = ["RECORD_KEY", "RECIPE_VERSION", "default_recipe", "build_recipe",
           "record", "recorded", "drop_ordinals", "apply_rows",
           "write_generated", "generated_of", "remove_generated",
           "GENERATED_MARK"]

#: the key of the record row (``o4_placement_provenance.json``)
RECORD_KEY = "pack_optimise"
#: the recipe's shape; recorded with it so a later phase can read an
#: older row (1: dedupe only; 2: + library swaps; 3: + object copies)
RECIPE_VERSION = 3
#: every file the recipe writes beside the vendor's carries this in its name
GENERATED_MARK = ".o4opt"


def default_recipe() -> dict[str, _t.Any]:
    """What "Optimise" means today without the pack's files: the rules
    that need no match (:func:`build_recipe` adds the matches)."""
    return {"version": RECIPE_VERSION, "dedupe": dict(_dd.DEFAULTS)}


def build_recipe(pack_root: str, lines: _t.Sequence[str],
                 exports_of: _t.Callable[[str], _t.Sequence[str]] | None
                 ) -> dict[str, _t.Any]:
    """The recipe for one pristine dump ``lines``: :func:`default_recipe`,
    with the install's library (``exports_of``) the library swaps of its
    objects (``swap.plan_swaps``), and the lighter copies of the rest
    (``objcopy.plan_objects``).  Deterministic for one pack and one
    install."""
    from ..dsf_write import placement_rows
    from ..pack_art import declared_definitions
    recipe = default_recipe()
    defs = declared_definitions(lines)["object"]
    uses: dict[int, int] = {}
    for _o, _i, toks in placement_rows(lines):
        uses[int(toks[1])] = uses.get(int(toks[1]), 0) + 1
    swaps = (_sw.plan_swaps(pack_root, defs, uses, exports_of)
             if exports_of is not None else {})
    if swaps:
        recipe["swap"] = swaps
    copies = _oc.plan_objects(pack_root, defs, uses, set(swaps))
    if copies:
        recipe["objects"] = copies
    return recipe


def _decision_key(pristine_sha256: str, recipe: _t.Mapping[str, _t.Any]) -> str:
    """What an accepted recipe is keyed to: the PRISTINE DSF content and
    the recipe.  A pack update is a different key."""
    h = hashlib.sha256(pristine_sha256.encode("ascii", "replace"))
    h.update(b"\n" + json.dumps(dict(recipe), sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def record(pristine_sha256: str, recipe: _t.Mapping[str, _t.Any],
           counts: _t.Mapping[str, int], time: str,
           applied: _t.Mapping[str, _t.Any] | None = None) -> dict[str, _t.Any]:
    """The :data:`RECORD_KEY` entry of ``o4_placement_provenance.json``:
    the recipe and what it did to this write (``applied``: the rows each
    swap moved, ``{"swaps": {path: rows}, "generated": [files]}``)."""
    applied = applied or {}
    swaps = applied.get("swaps") or {}
    to = (recipe.get("swap") or {})
    return {"accepted": True, "time": time,
            "key": _decision_key(pristine_sha256, recipe),
            "pristine_sha256": pristine_sha256,
            "recipe_version": int(recipe.get("version", RECIPE_VERSION)),
            "params": dict(recipe),
            "dedupe": {k: int(v) for k, v in counts.items()},
            "swaps": [{"path": p, "to": (to.get(p) or {}).get("to", ""),
                       "rows": int(n)} for p, n in sorted(swaps.items())],
            # later phases (#1707 D3-O4): re-pointed definitions
            "renames": [],
            "generated": sorted(applied.get("generated") or ())}


def recorded(entry: _t.Mapping[str, _t.Any] | None,
             pristine_sha256: str) -> dict[str, _t.Any]:
    """The recipe the user accepted for THIS pristine DSF, read back from
    :func:`record`'s row; ``{}`` when none is recorded, when it belongs to
    another pristine file, or when the row no longer reads as written."""
    row = (entry or {}).get(RECORD_KEY)
    if not (isinstance(row, dict) and row.get("accepted") is True
            and row.get("pristine_sha256") == pristine_sha256):
        return {}
    recipe = row.get("params")
    if not isinstance(recipe, dict) or not recipe:
        return {}
    return dict(recipe) if row.get("key") == _decision_key(
        pristine_sha256, recipe) else {}


def drop_ordinals(lines: _t.Sequence[str], recipe: _t.Mapping[str, _t.Any],
                  edited: _t.AbstractSet[int]) -> tuple[set[int], dict[str, int]]:
    """The placement ordinals ``recipe`` deletes from the pristine dump
    ``lines`` and its counts; nothing without a recipe.  ``edited`` are
    the rows the placement plan edits, which are never dropped."""
    params = (recipe or {}).get("dedupe")
    if not isinstance(params, _t.Mapping):
        return set(), {}
    return _dd.drop_set(lines, params, edited)


def apply_rows(text: str, recipe: _t.Mapping[str, _t.Any]
               ) -> tuple[str, dict[str, int]]:
    """The recipe's row rewrites on an edited dump — D2 ``swap.apply``,
    then D3 ``objcopy.rename_rows`` — the text and ``{declared path:
    rows swapped}``."""
    swaps = (recipe or {}).get("swap")
    counts: dict[str, int] = {}
    if isinstance(swaps, _t.Mapping) and swaps:
        text, counts = _sw.apply(text, swaps)
    copies = (recipe or {}).get("objects")
    if isinstance(copies, _t.Mapping) and copies:
        text, _n = _oc.rename_rows(text, copies)
    return text, counts


def write_generated(pack_root: str, recipe: _t.Mapping[str, _t.Any]
                    ) -> list[str]:
    """Write every file the recipe's edited DSF names beside the vendor's
    (the lights-only copies, ``swap.lights_text``; the object copies,
    ``objcopy.copy_text``) from the vendor file, when it is absent or
    differs; returns them pack-relative.  A vendor
    file that no longer reads raises: the DSF must never name a missing
    file."""
    out: list[str] = []
    for path, sw in sorted(((recipe or {}).get("swap") or {}).items()):
        rel = (sw or {}).get("lights") or ""
        if not rel:
            continue
        src = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
        text = _sw.lights_text(src)
        if text is None:
            raise ValueError(f"{path}: its lights can no longer be read")
        _write_if_changed(os.path.join(pack_root, *rel.replace("\\", "/").split("/")),
                          text)
        out.append(rel.replace("\\", "/"))
    for path, params in sorted(((recipe or {}).get("objects") or {}).items()):
        src = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
        rel = _oc.copy_path(path).replace("\\", "/")
        dst = os.path.join(pack_root, *rel.split("/"))
        if not _current_copy(dst, _oc.stamp(src, params)):
            _write_if_changed(dst, _oc.copy_text(src, params), "latin-1")
        out.append(rel)
    return out


def _current_copy(path: str, stamp: str) -> bool:
    """Whether the copy at ``path`` was written from today's vendor file
    and params (its fourth line carries the stamp)."""
    try:
        with open(path, encoding="latin-1") as fh:
            head = [fh.readline() for _ in range(4)]
    except OSError:
        return False
    return head[3].strip() == f"# o4opt {stamp}"


def _write_if_changed(path: str, text: str, encoding: str = "utf-8") -> None:
    data = text.encode(encoding)
    try:
        with open(path, "rb") as fh:
            if fh.read() == data:
                return
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def generated_of(entry: _t.Mapping[str, _t.Any] | None) -> list[str]:
    """The pack-relative files a DSF's record says the recipe wrote."""
    row = (entry or {}).get(RECORD_KEY)
    files = row.get("generated") if isinstance(row, dict) else None
    return [f for f in (files or ()) if isinstance(f, str)]


def remove_generated(pack_root: str, rels: _t.Iterable[str]) -> list[str]:
    """Remove the recipe's files ``rels`` (pack-relative); only a name
    carrying :data:`GENERATED_MARK` inside the pack is ever touched, so a
    vendor file never is.  Returns those removed."""
    root = os.path.abspath(pack_root) + os.sep
    gone: list[str] = []
    for rel in sorted(set(rels)):
        path = os.path.abspath(os.path.join(pack_root, *rel.split("/")))
        if (GENERATED_MARK in os.path.basename(path) and path.startswith(root)
                and os.path.isfile(path)):
            os.remove(path)
            gone.append(rel)
    return gone
