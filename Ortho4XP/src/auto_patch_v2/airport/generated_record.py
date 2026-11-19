"""THE GENERATED STRUCTURES AS A PORTABLE RECORD (#2140; owner
2026-11-17T16:08Z: "make sure that our new bridge generator records the
necessary details when a tile is packaged into an xptb file so they can be
quickly reconstructed, perhaps the objects get added to the package?").

A generated deck or road bridge is written into the airport's pack from a
RECIPE (``generated_pack.recipe``): the deck OBJ8 files and their texture,
one placement row per object, the road chains, the regions cut out of the
pack's pages and the apt.dat, the faked-cut placements hidden, and LINKS
from the generated folder to X-Plane's own art (#2132, ``deck_skin``).
:func:`to_record` turns that recipe into a record a package can carry
(``tile_bundle.generated``); :func:`_from_record` turns it back into the
same recipe on another machine, with no planar map, no solve and no deck
generator:

* the generated files ride WHOLE (the OBJ8 text, the atlas PNG as base64);
* each link rides as a REFERENCE -- its file's path relative to the X-Plane
  install it was read from (``Resources/default scenery/...``) -- never the
  art itself (Laminar's files are never copied into a package); the
  receiving machine resolves each against ITS install, and a reference it
  does not have makes the record unusable there (the generator then runs
  as on any build);
* the record is keyed on the PUBLICATION it was made from
  (:func:`_publication_sha`: the graded surface's ``provenance.generated``),
  so a receiving build uses it only where its own solve published the same
  structures (:func:`installed_recipe`) -- a deck is never placed on a
  surface it was not solved for.

Nothing here names an airport.  Build-time impact: one JSON read per
airport with a generated structure; the generator is skipped when it
matches.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import typing as _t

__all__ = ["SCHEMA", "to_record", "installed_path", "installed_recipe"]

#: The record's schema (a package's compatibility key carries it).
SCHEMA = "o4-generated-1"

#: Where an installed package's record lands in the tile's patch folder.
_FILENAME = "o4_generated_{icao}.json"

_ROWS = ("decks", "regions", "chains", "hides", "notes", "deck_tops")


def _publication_sha(pub: _t.Mapping) -> str:
    """The sha256 of a graded surface's ``generated`` publication, in a
    canonical JSON spelling."""
    text = json.dumps(pub or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reference(path: str, root: str) -> "str | None":
    """``path`` relative to the install ``root``, ``/``-separated; ``None``
    when it lies outside it."""
    if not root or not path:
        return None
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    if rel == os.curdir or rel.startswith(os.pardir) or os.path.isabs(rel):
        return None
    return rel.replace(os.sep, "/")


def _file_body(rel: str, data: bytes) -> dict:
    """An OBJ8 as its text, any other file as base64."""
    if rel.endswith(".obj"):
        try:
            return {"text": data.decode("ascii")}
        except UnicodeDecodeError:
            pass
    return {"base64": base64.b64encode(data).decode("ascii")}


def to_record(rec: _t.Mapping, pub: _t.Mapping, icao: str,
              xplane_root: "str | None") -> "dict | None":
    """The portable record of the recipe ``rec`` made from ``pub`` (module
    doc), or ``None`` when a link names a file outside ``xplane_root``
    (no other machine could resolve it) or nothing was made."""
    if not rec or not (rec.get("decks") or rec.get("chains")):
        return None
    refs = {}
    for rel, src in sorted((rec.get("links") or {}).items()):
        ref = _reference(src, xplane_root or "")
        if ref is None:
            return None
        refs[rel] = ref
    doc = {"schema": SCHEMA, "icao": str(icao).upper(),
           "publication_sha256": _publication_sha(pub),
           "files": {rel: _file_body(rel, data)
                     for rel, data in sorted((rec.get("files") or {}).items())},
           "references": refs}
    doc.update({k: list(rec.get(k) or ()) for k in _ROWS})
    return doc


def _resolve(refs: _t.Mapping, xplane_root: "str | None") -> "dict | None":
    """``{pack name: file in xplane_root}`` of every reference, ``None``
    when one is missing there or malformed."""
    links = {}
    for rel, ref in sorted(refs.items()):
        parts = str(ref).split("/")
        if not xplane_root or any(p in ("", ".", "..") for p in parts):
            return None
        path = os.path.join(xplane_root, *parts)
        if not os.path.isfile(path):
            return None
        links[rel] = path
    return links


def _from_record(doc: _t.Mapping, xplane_root: "str | None") -> "dict | None":
    """The recipe a record holds, its references resolved in
    ``xplane_root``; ``None`` for another schema or a reference this
    install does not have."""
    if not doc or doc.get("schema") != SCHEMA:
        return None
    links = _resolve(doc.get("references") or {}, xplane_root)
    if links is None:
        return None
    rec: dict = {k: list(doc.get(k) or ()) for k in _ROWS}
    rec["files"] = {rel: (body["text"].encode("ascii") if "text" in body
                          else base64.b64decode(body.get("base64") or ""))
                    for rel, body in (doc.get("files") or {}).items()}
    if links:
        rec["links"] = links
    return rec


def installed_path(patch_dir: str, icao: str) -> str:
    """The installed record of ``icao`` in the tile's patch folder."""
    return os.path.join(patch_dir, _FILENAME.format(icao=str(icao).upper()))


def installed_recipe(patch_dir: str, icao: str, pub: _t.Mapping,
                     apt_path: str) -> "dict | None":
    """The recipe an installed package recorded for ``icao`` when it was
    made from this very publication ``pub``, resolved in the install the
    pack stands in (``deck_skin.install_root``); ``None`` otherwise (the
    generator runs)."""
    if not patch_dir or not pub:
        return None
    try:
        with open(installed_path(patch_dir, icao), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    if doc.get("publication_sha256") != _publication_sha(pub):
        return None
    from .deck_skin import install_root
    return _from_record(doc, install_root(apt_path))
