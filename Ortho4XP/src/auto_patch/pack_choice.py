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

__all__ = ["OPTIMISE_CHOICES", "Store", "store_path", "read", "write",
           "relative"]

#: the "Optimise pack" answers file (#1707; ``optimise_stage``)
OPTIMISE_CHOICES = "pack_optimise_choices.json"

#: the answers a store remembers ("" forgets)
REMEMBERED = ("update", "never")


def store_path(name: str) -> str:
    """The answers file ``name``, beside the remembered data-root choice."""
    import O4_File_Names as FNAMES
    return os.path.join(os.path.dirname(FNAMES.data_root_pointer_file), name)


def _pack_key(pack_root: str) -> str:
    return os.path.normcase(os.path.abspath(pack_root or ""))


def _read_all(path: str) -> dict[str, str]:
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in doc.items()
            if v in REMEMBERED} if isinstance(doc, dict) else {}


def read(path: str, pack_root: str) -> str:
    """``"update"`` | ``"never"`` | ``""`` (ask) for a pack."""
    return _read_all(path).get(_pack_key(pack_root), "")


def write(path: str, pack_root: str, choice: str) -> None:
    """Remember (or, with ``""``, forget) the user's answer for a pack."""
    doc = _read_all(path)
    key = _pack_key(pack_root)
    if doc.get(key, "") == (choice if choice in REMEMBERED else ""):
        return                          # nothing to change: no write
    if choice in REMEMBERED:
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
    every call, so a test may redirect it)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def choice(self, pack_root: str) -> str:
        """``"update"`` | ``"never"`` | ``""`` (ask)."""
        return read(store_path(self.name), pack_root)

    def remember(self, pack_root: str, choice: str) -> None:
        """Remember (or, with ``""``, forget) the answer for a pack."""
        write(store_path(self.name), pack_root, choice)


def relative(pack_root: str, path: str) -> str:
    """``path`` relative to the pack, ``/``-separated."""
    try:
        return os.path.relpath(path, pack_root).replace(os.sep, "/")
    except ValueError:      # Windows: a path on another drive has no relpath
        return path.replace(os.sep, "/")
