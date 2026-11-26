"""THE USER'S ANSWER FOR AN AIRPORT PACK, remembered per pack: the
X-Plane 12 3D trees (#1360, ``forest_stage``), "Optimise pack" (#1707,
``optimise_stage``) and the hidden draped photos (#1916, ``drape_stage``)
share this store.  One JSON file per choice
(:func:`store_path`) in the engine's own preferences folder, never in the
pack.  Light on purpose: ``object_rebake``'s Revert to default forgets an
answer through it without importing the object stage.  The rewrite and
the Undo the two choices share are ``pack_rewrite``.
"""
from __future__ import annotations

import json
import os
import typing as _t

__all__ = ["OPTIMISE_CHOICES", "OPTIMISE_STEPS", "DRAPE_CHOICES",
           "GATEWAY_CHOICES", "GROUND_CHOICES", "GENERIC_CHOICES", "TERRAIN_CHOICES",
           "TERRAIN_FOUND", "TERRAIN_MODELS", "TERRAIN_OBJECTS", "PRIORITY_CHOICES",
           "terrain_answers", "OVERLAP_FOUND", "hidden_terrain",
           "TERRAIN_DEFAULT", "TERRAIN_STORE", "terrain_hiding", "hides",
           "TERRAIN_ALL_CHOICES", "TERRAIN_ALL_STORE", "hides_all",
           "Store", "store_path", "read", "read_all",
           "write", "relative", "step_list"]

#: the "Optimise pack" answers file (#1707; ``optimise_stage``)
OPTIMISE_CHOICES = "pack_optimise_choices.json"
#: the steps the user last chose for a pack's "Optimise pack" (#1707)
OPTIMISE_STEPS = "pack_optimise_steps.json"
#: the "Hide draped photos" answers file (#1916; ``drape_stage``)
DRAPE_CHOICES = "pack_drape_choices.json"
#: the Gateway airport answers file (#1989; ``gateway_stage``): keyed by
#: ``gateway_stage.choice_key(ICAO)``, not by a pack
GATEWAY_CHOICES = "gateway_airport_choices.json"
#: the "Hide large ground textures" answers file (#1962; ``drape_stage``)
GROUND_CHOICES = "pack_ground_choices.json"
#: the "Hide generic X-Plane ground" answers file (#2085; ``drape_stage``)
GENERIC_CHOICES = "pack_generic_choices.json"
#: the "Hide terrain objects" answers file (RULINGS 2026-11-13i; ``drape_stage``)
TERRAIN_CHOICES = "pack_terrain_choices.json"
#: the terrain objects a build offered for hiding, per pack
#: (``auto_patch_v2.airport.pack_terrain``): the answer works outside a build
TERRAIN_FOUND = "pack_terrain_found.json"
#: every terrain object a build recognised, per pack (#2272: the Adjust…
#: row lists them, offered or not)
TERRAIN_MODELS = "pack_terrain_models.json"
#: the per-object answers of the terrain row, per pack (#2272,
#: ``pack_terrain.encode_answers``)
TERRAIN_OBJECTS = "pack_terrain_objects.json"
#: the terrain row's "hide them all" answers (RULINGS 2026-11-25l,
#: :func:`hides_all`): "update" hides every terrain object a build
#: recognises, matched by our elevation or not
TERRAIN_ALL_CHOICES = "pack_terrain_all_choices.json"
#: which pack keeps a structure two packs both draw, per pack pair (#2145;
#: ``pack_overlap_choice``): keyed by ``pack_overlap_choice.pair_key``
PRIORITY_CHOICES = "pack_priority_choices.json"
#: the overlapping structures a build found, per pack pair (#2145)
OVERLAP_FOUND = "pack_overlap_found.json"
#: whether to disable the lower of two packs defining one airport, per
#: pair (#2145, RULINGS 17s; ``pack_duplicate``): "disable" / "keep"
DUPLICATE_AIRPORT_CHOICES = "pack_duplicate_airport_choices.json"

#: the answers a store remembers ("" forgets)
REMEMBERED = ("update", "never")


def store_path(name: str) -> str:
    """The answers file ``name``, beside the remembered data-root choice."""
    import O4_File_Names as FNAMES
    return os.path.join(os.path.dirname(FNAMES.data_root_pointer_file), name)


def pack_key(pack_root: str) -> str:
    return os.path.normcase(os.path.abspath(pack_root or ""))


def _remembered(value: object) -> bool:
    return value in REMEMBERED


def step_list(value: object) -> bool:
    """A remembered list of steps — the :data:`OPTIMISE_STEPS` store's:
    ``"dedupe,swap"`` (lower-case names, comma-separated, none empty), or
    the steps chosen and the steps the question showed,
    ``"dedupe,swap|dedupe,swap,objects"``."""
    return (isinstance(value, str) and bool(value) and value.count("|") <= 1
            and all(w.isalpha() and w.islower()
                    for part in value.split("|") for w in part.split(",")))


def read_all(path: str, allowed: _t.Callable[[object], bool] = _remembered
             ) -> dict[str, str]:
    """Every remembered answer of the file ``path``, by key."""
    import O4_File_Names as FNAMES
    return {str(k): str(v) for k, v in FNAMES.read_json_dict(path).items()
            if allowed(v)}


def read(path: str, pack_root: str,
         allowed: _t.Callable[[object], bool] = _remembered) -> str:
    """``"update"`` | ``"never"`` | ``""`` (ask) for a pack (or what
    ``allowed`` admits)."""
    return read_all(path, allowed).get(pack_key(pack_root), "")


def write(path: str, pack_root: str, choice: str,
          allowed: _t.Callable[[object], bool] = _remembered) -> None:
    """Remember (or, with ``""``, forget) the user's answer for a pack."""
    doc = read_all(path, allowed)
    key = pack_key(pack_root)
    if doc.get(key, "") == (choice if allowed(choice) else ""):
        return                          # nothing to change: no write
    if allowed(choice):
        doc[key] = choice
    else:
        doc.pop(key, None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


class Store:
    """One choice's answers file, by name (:func:`store_path` is read at
    every call, so a test may redirect it); ``allowed`` says which values
    it remembers (default ``"update"`` / ``"never"``)."""

    def __init__(self, name: str,
                 allowed: _t.Callable[[object], bool] = _remembered,
                 default: str = "") -> None:
        self.name = name
        self.allowed = allowed
        #: the answer of a pack with none remembered (``""``: ask)
        self.default = default

    def choice(self, pack_root: str) -> str:
        """``"update"`` | ``"never"`` | ``""`` (ask); :attr:`default` when
        the pack has no answer."""
        return read(store_path(self.name), pack_root, self.allowed) or self.default

    def remember(self, pack_root: str, choice: str) -> None:
        """Remember (or, with ``""``, forget) the answer for a pack."""
        write(store_path(self.name), pack_root, choice, self.allowed)


def relative(pack_root: str, path: str) -> str:
    """``path`` relative to the pack, ``/``-separated."""
    try:
        return os.path.relpath(path, pack_root).replace(os.sep, "/")
    except ValueError:      # Windows: a path on another drive has no relpath
        return path.replace(os.sep, "/")


#: THE TERRAIN ROW'S DEFAULT (owner 2026-11-25, #2285, on RULINGS
#: 2026-11-24k (1)): a pack with no answer HIDES every terrain object the
#: build offers -- our ground under it is quality elevation (10 m or finer
#: over 90 % of its plan) that models it (``terrain_model.quality``).  The
#: user's "never" and per-object Keep answers still keep one.
TERRAIN_DEFAULT = "update"
#: the "Hide terrain objects" answers, :data:`TERRAIN_DEFAULT` for none
TERRAIN_STORE = Store(TERRAIN_CHOICES, default=TERRAIN_DEFAULT)


#: the "hide them all" answers (no answer: the terrain row's own offer)
TERRAIN_ALL_STORE = Store(TERRAIN_ALL_CHOICES)


def hides_all(pack_root: str) -> bool:
    """THE USER PREFERS OUR ELEVATION (owner RULINGS 2026-11-25l): the
    pack hides EVERY terrain object a build recognises -- shells, rocks,
    relief skins -- whatever ``terrain_model.quality`` says and whatever
    the per-object answers are.  A refinement of the terrain row: only
    while that row's answer is "update" (its Undo / "never" keeps all)."""
    return (bool(pack_root) and TERRAIN_STORE.choice(pack_root) == "update"
            and TERRAIN_ALL_STORE.choice(pack_root) == "update")


class _TerrainHiding(frozenset):
    """The terrain objects a build hides (:func:`terrain_hiding`): the set
    is the paths hidden by name (:func:`hidden_terrain`); :attr:`kept` is
    ``None`` when the pack does not hide its offer, else the paths the
    user keeps -- every other object this build finds hideable is hidden
    too (:func:`hides`), so a pack's first build hides what it offers;
    :attr:`every` hides every object recognised (:func:`hides_all`)."""

    kept: "frozenset[str] | None" = None
    every: bool = False

    def __new__(cls, paths: _t.Iterable[str] = (),
                kept: "_t.Iterable[str] | None" = None,
                every: bool = False) -> "_TerrainHiding":
        self = super().__new__(cls, paths)
        self.kept = None if kept is None else frozenset(kept)
        self.every = bool(every)
        return self


def hides(hidden: _t.AbstractSet[str], path: str, hideable: bool) -> bool:
    """Is the terrain object ``path`` hidden: named in ``hidden``, or
    offered (``hideable``) where ``hidden`` is a :class:`_TerrainHiding`
    that hides its offer and the user does not keep it -- or any
    recognised object where it hides them all (:func:`hides_all`)."""
    if path in hidden or getattr(hidden, "every", False):
        return True
    kept = getattr(hidden, "kept", None)
    return bool(hideable) and kept is not None and path not in kept


def terrain_hiding(pack_root: str) -> _TerrainHiding:
    """THE BUILD'S HIDING for a pack (#2285): :func:`hidden_terrain`, and
    when the pack's answer is ``update`` (:data:`TERRAIN_DEFAULT` with
    none) the objects the user keeps (``pack_terrain.KEEP``); every
    recognised object where the pack hides them all (:func:`hides_all`)."""
    if hides_all(pack_root):
        return _TerrainHiding(hidden_terrain(pack_root), (), every=True)
    if not pack_root or TERRAIN_STORE.choice(pack_root) != "update":
        return _TerrainHiding(hidden_terrain(pack_root))
    from .pack_terrain import KEEP
    return _TerrainHiding(hidden_terrain(pack_root),
                         (p for p, a in terrain_answers(pack_root).items() if a == KEEP))


def hidden_terrain(pack_root: str) -> frozenset[str]:
    """The terrain objects the user HID (#2077 4.2): the pack's
    :data:`TERRAIN_CHOICES` answer ``update`` (:data:`TERRAIN_DEFAULT`
    with none, #2285) over the offer the last build
    remembered (:data:`TERRAIN_FOUND`, ``drape_stage.terrain_paths``) as the
    per-object answers move it (:data:`TERRAIN_OBJECTS`, #2272); empty
    otherwise.  The build reads it (their frames dissolve,
    ``auto_patch_v2.airport.terrain_model``) and the patch stamps it
    (``provenance.terrain_hidden_identity``).  Where the pack hides them
    all (:func:`hides_all`): the offer and every object the last build
    recognised (:data:`TERRAIN_MODELS`), whatever the per-object answers."""
    if not pack_root:
        return frozenset()
    if TERRAIN_STORE.choice(pack_root) != "update":
        return frozenset()
    from .pack_terrain import decode, offered
    found = Store(TERRAIN_FOUND, lambda v: isinstance(v, str) and bool(v)).choice(pack_root)
    if hides_all(pack_root):
        models = Store(TERRAIN_MODELS, lambda v: isinstance(v, str) and bool(v))
        return frozenset(decode(found)) | frozenset(decode(models.choice(pack_root)))
    # #2272: the user's per-object answers move objects in and out
    return frozenset(offered(decode(found), terrain_answers(pack_root)))


def terrain_answers(pack_root: str) -> dict[str, str]:
    """The terrain row's per-object answers for a pack (#2272, path ->
    ``pack_terrain.HIDE`` | ``KEEP``; written by
    ``drape_stage.terrain_answers``)."""
    from .pack_terrain import decode_answers
    if not pack_root:
        return {}
    return decode_answers(Store(TERRAIN_OBJECTS, lambda v: isinstance(v, str) and bool(v))
                          .choice(pack_root))
