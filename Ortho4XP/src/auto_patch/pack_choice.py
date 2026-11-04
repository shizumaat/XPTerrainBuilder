"""THE USER'S ANSWER FOR AN AIRPORT PACK, remembered per pack: the
X-Plane 12 3D trees (#1360, ``forest_stage``) and "Optimise pack" (#1707,
``optimise_stage``) share this store.  One JSON file per choice
(:func:`store_path`) in the engine's own preferences folder, never in the
pack.  Light on purpose: ``object_rebake``'s Revert to default forgets an
answer through it without importing the object stage.  The rewrite and
the Undo the two choices share are ``pack_rewrite``.
"""
from __future__ import annotations

import json
import os
import typing as _t

__all__ = ["OPTIMISE_CHOICES", "OPTIMISE_STEPS", "Store", "store_path", "read",
           "write", "relative", "step_list"]

#: the "Optimise pack" answers file (#1707; ``optimise_stage``)
OPTIMISE_CHOICES = "pack_optimise_choices.json"
#: the steps the user last chose for a pack's "Optimise pack" (#1707)
OPTIMISE_STEPS = "pack_optimise_steps.json"

#: the answers a store remembers ("" forgets)
REMEMBERED = ("update", "never")


def store_path(name: str) -> str:
    """The answers file ``name``, beside the remembered data-root choice."""
    import O4_File_Names as FNAMES
    return os.path.join(os.path.dirname(FNAMES.data_root_pointer_file), name)


def _pack_key(pack_root: str) -> str:
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


def _read_all(path: str, allowed: _t.Callable[[object], bool] = _remembered
              ) -> dict[str, str]:
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in doc.items()
            if allowed(v)} if isinstance(doc, dict) else {}


def read(path: str, pack_root: str,
         allowed: _t.Callable[[object], bool] = _remembered) -> str:
    """``"update"`` | ``"never"`` | ``""`` (ask) for a pack (or what
    ``allowed`` admits)."""
    return _read_all(path, allowed).get(_pack_key(pack_root), "")


def write(path: str, pack_root: str, choice: str,
          allowed: _t.Callable[[object], bool] = _remembered) -> None:
    """Remember (or, with ``""``, forget) the user's answer for a pack."""
    doc = _read_all(path, allowed)
    key = _pack_key(pack_root)
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
                 allowed: _t.Callable[[object], bool] = _remembered) -> None:
        self.name = name
        self.allowed = allowed

    def choice(self, pack_root: str) -> str:
        """``"update"`` | ``"never"`` | ``""`` (ask)."""
        return read(store_path(self.name), pack_root, self.allowed)

    def remember(self, pack_root: str, choice: str) -> None:
        """Remember (or, with ``""``, forget) the answer for a pack."""
        write(store_path(self.name), pack_root, choice, self.allowed)


def relative(pack_root: str, path: str) -> str:
    """``path`` relative to the pack, ``/``-separated."""
    try:
        return os.path.relpath(path, pack_root).replace(os.sep, "/")
    except ValueError:      # Windows: a path on another drive has no relpath
        return path.replace(os.sep, "/")
