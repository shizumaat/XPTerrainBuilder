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
* ``weight`` — the triangles the pack's own objects draw, before and
  after: what the offer is made on.

Phase 1 ships D1; library swaps, LODs and textures (D2-O5) follow and
add their fields to the same record row.
"""
from __future__ import annotations

import hashlib
import json
import typing as _t

from . import dedupe as _dd

__all__ = ["RECORD_KEY", "RECIPE_VERSION", "default_recipe",
           "record", "recorded", "drop_ordinals"]

#: the key of the record row (``o4_placement_provenance.json``)
RECORD_KEY = "pack_optimise"
#: the recipe's shape; recorded with it so a later phase can read an
#: older row
RECIPE_VERSION = 1


def default_recipe() -> dict[str, _t.Any]:
    """What "Optimise" means today."""
    return {"version": RECIPE_VERSION, "dedupe": dict(_dd.DEFAULTS)}


def _decision_key(pristine_sha256: str, recipe: _t.Mapping[str, _t.Any]) -> str:
    """What an accepted recipe is keyed to: the PRISTINE DSF content and
    the recipe.  A pack update is a different key."""
    h = hashlib.sha256(pristine_sha256.encode("ascii", "replace"))
    h.update(b"\n" + json.dumps(dict(recipe), sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def record(pristine_sha256: str, recipe: _t.Mapping[str, _t.Any],
           counts: _t.Mapping[str, int], time: str) -> dict[str, _t.Any]:
    """The :data:`RECORD_KEY` entry of ``o4_placement_provenance.json``:
    the recipe and what it did to this write."""
    return {"accepted": True, "time": time,
            "key": _decision_key(pristine_sha256, recipe),
            "pristine_sha256": pristine_sha256,
            "recipe_version": int(recipe.get("version", RECIPE_VERSION)),
            "params": dict(recipe),
            "dedupe": {k: int(v) for k, v in counts.items()},
            # later phases (#1707 D2-O4): library swaps, re-pointed
            # definitions, generated files
            "swaps": [], "renames": [], "generated": []}


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
