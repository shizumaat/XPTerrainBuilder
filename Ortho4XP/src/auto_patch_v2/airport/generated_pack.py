"""THE GENERATED STRUCTURES, WRITTEN INTO THE AIRPORT'S PACK (spec
``docs/specs/2123.md`` A2-A3 / B2-B3; owner RULINGS 2026-11-16y; issues
#2123, #2124).

The patch build publishes each generated taxiway deck and road bridge on
the graded surface's provenance (``pipeline/generated_publication``); the
object stage turns them into a RECIPE (:func:`recipe`) and the pack write
applies it in the same write as every other placement edit
(``dsf_write.write_pack(generated=...)``):

* each DECK becomes an OBJ8 (``deck_obj8``: an ``ATTR_hard_deck`` top,
  ``thickness_m`` slab, the dropped apt.dat paint redrawn as X-Plane's own
  stripes, ``deck_paint``; the green centreline lights kept as
  ``taxi_g`` / ``taxi_g_rev``) under ``objects/o4_generated/`` with its
  texture (``deck_texture``), placed by one ``OBJECT_MSL`` row at the
  deck's solved zero; where the user's X-Plane install resolves them
  (#2132, ``deck_skin``) the slab is drawn in X-Plane's own concrete
  page and the paint + lights and the tire marks (the runway rubber page)
  are overlay objects at the same anchor, the art LINKED into the folder;
* every pack ``.pol`` / ``.lin`` page is clipped by the deck's ring and by
  each bridge's span corridor (``dsf_poly_clip``; a UV-mapped page under
  one refuses that structure by name);
* each ROAD BRIDGE becomes a road chain, junction levels 0-1-1-0
  (``dsf_additions``) in the network the pack DSF already declares, else
  the tile's road pack's (``road_net_of``), else ``[road_gen] net_def``;
* the apt.dat loses the same regions (``apt_flatten.write_regions``: a
  hole in every ``110``, the ``120`` lines split, recorded).

THE RECORD: the recipe rides the DSF's provenance entry under
:data:`RECORD_KEY`, keyed on the backup's hash, so a later write of the
same pristine DSF re-applies it and Restore originals removes the files
(:func:`remove`).  Nothing here names an airport.

Build-time impact: the object stage only -- shapely on a handful of
rings, one OBJ8 of a few thousand vertices per deck.
"""
from __future__ import annotations

import hashlib
import os
import typing as _t

from shapely import wkt as _wkt
from shapely.geometry import Polygon

from . import deck_objects as _objs
from . import deck_pavement as _pav
from . import deck_texture as _tex
from .deck_obj8 import DECK_MARK
from .deck_objects import GENERATED_DIR, TEXTURE

__all__ = ["RECORD_KEY", "GENERATED_DIR", "TEXTURE", "recipe", "apply_text",
           "write_files", "remove", "files_of", "recorded", "record",
           "regions_of"]

RECORD_KEY = "o4_generated"


def _is_generated_file(path: str) -> bool:
    """A file this module writes (the generated-objects folder)."""
    return GENERATED_DIR in path.replace("\\", "/")


def _poly(ring) -> Polygon:
    p = Polygon([tuple(q) for q in ring])
    return p if p.is_valid else p.buffer(0.0)


def recipe(generated: _t.Mapping, apt_path: str, icao: str, law,
           xplane_root: "str | None" = None, resolve_library=None) -> dict:
    """The write recipe of an airport's generated structures (module doc):
    ``xplane_root`` the install whose art draws the decks (#2132), ``None``
    to find it (``deck_skin.install_root``), ``""`` for none (the atlas);
    ``resolve_library`` the install's library lookup
    (``deck_skin.Resolver``; the object stage hands in X-Plane's merged
    index), ``None`` for none (the atlas).
    ``{"decks": [placement rows], "regions": [WKT], "chains": [...],
    "files": {pack-relative path: bytes}, "notes": [...]}``; empty lists
    where nothing was generated."""
    from . import apt_flatten as _af
    decks = list((generated or {}).get("decks") or ())
    bridges = list((generated or {}).get("road_bridges") or ())
    out: dict = {"decks": [], "regions": [], "chains": [], "files": {}, "notes": []}
    if not decks and not bridges:
        return out
    # #2131: a deck's open approaches leave the pack's pages with its ring
    regions = [_poly(d["ring"]) for d in decks] + \
        [_poly(q) for d in decks for q in d.get("approach") or () if len(q) >= 3] + \
        [_wkt.loads(b["span_wkt"]) for b in bridges if b.get("span_wkt")]
    dropped_by_deck: dict[int, list] = {}
    if apt_path:
        shipped = _af.read_path(apt_path)
        try:
            with open(shipped, "rb") as fh:
                data = _af.stripped(fh.read())
            for k, d in enumerate(decks):
                _data, _rec, dropped = _af._cut(data, icao, [_poly(d["ring"])])
                dropped_by_deck[k] = dropped
        except OSError as exc:
            out["notes"].append(f"apt.dat unreadable ({exc}): no paint redrawn")
    g = law.tables.structures.deck_gen
    art = _install(apt_path, g, xplane_root, resolve_library) if decks else None
    apt = _apt_block(apt_path, icao) if decks else None
    for k, d in enumerate(decks):
        code = _pav.carried_surface(apt, _poly(d["ring"]), str(d.get("family") or "")) \
            if apt is not None else None
        objs, st = _objs.deck_objects(d, dropped_by_deck.get(k, ()), art, g, surface_code=code)
        rel = str(d["resource"])
        frame = st["frame"]
        for orel, text in objs:
            out["files"][orel] = text.encode("ascii")
            out["decks"].append({"object_id": d["object_id"] + orel[len(rel) - 4:-4],
                                 "resource": orel, "lon": frame.lon, "lat": frame.lat,
                                 "msl": round(float(d["zero_m"]), 4),
                                 "hdg": round(frame.heading_deg, 6)})
        R = _poly(d["ring"])
        out["notes"].append(f"deck {d['object_id']}: {len(R.exterior.coords) - 1}-point ring, "
                            f"zero {float(d['zero_m']):.2f} m, heading {frame.heading_deg:.1f}, "
                            f"surface {code if code is not None else 'unknown'} "
                            f"({st.get('slab') or 'generated atlas'}), {st['parts']} part(s) "
                            f"({st.get('piers', 0)} column(s)), "
                            f"{st['lines']} line run(s) of {len(dropped_by_deck.get(k, ()))} "
                            f"dropped line piece(s), {st['lights']} light(s), "
                            f"{len(objs)} object(s)"
                            + (f", {st['unpainted']} line(s) of a type not painted"
                               if st["unpainted"] else ""))
    if art is not None:
        out["links"] = dict(art.links)
    if decks:
        out["files"][f"{GENERATED_DIR}/{TEXTURE}"] = _tex.deck_texture_png()
    for b in bridges:
        out["chains"].append({"subtype": int(b["subtype"]),
                              "junctions": [list(j) for j in b["junctions"]],
                              "net": str(b.get("net") or "")})
        out["notes"].append(f"road bridge {b.get('id')}: {len(b['junctions'])} junction(s), "
                            f"subtype {b['subtype']}")
    out["regions"] = [r.wkt for r in regions]
    return out


def _install(apt_path: str, g, root: "str | None", resolve):
    """#2132: X-Plane's own art for the decks (``deck_objects.install_art``)
    from the install the pack stands in, else the app's (``deck_skin``)."""
    from . import deck_skin as _skin
    root = _skin.install_root(apt_path) if root is None else root
    return _objs.install_art(g, root, resolve)


def _apt_block(apt_path: str, icao: str):
    """The airport's apt.dat block as shipped (``apt_dat.AptAirport``), or
    ``None`` (the decks then keep ``[deck_gen] concrete_pol``)."""
    from . import apt_dat as _apt
    from . import apt_flatten as _af
    try:
        block = _apt.read_airport_block(_af.read_path(apt_path), icao) if apt_path else None
        return _apt.parse_airport_block(block) if block else None
    except (OSError, ValueError):
        return None


def regions_of(rec: _t.Mapping) -> list[Polygon]:
    """The recipe's regions (lon/lat polygons)."""
    return [_wkt.loads(w) for w in (rec or {}).get("regions") or ()]


def apply_text(text: str, rec: _t.Mapping, net_default: str = "") -> tuple[str, dict]:
    """The DSF dump ``text`` with the recipe applied (module doc): pages
    clipped by every region, every deck placed, every chain added.
    Returns ``(text, counts)``."""
    from . import dsf_additions as _add
    from . import dsf_poly_clip as _clip
    counts = {"pages_cut": 0, "lines_cut": 0, "area_removed_m2": 0.0, "decks": 0,
              "chains": 0}
    if not rec:
        return text, counts
    for r in regions_of(rec):
        try:
            text, rep = _clip.clip_text(text, r)
        except _clip.UvMappedPage:
            # a UV-mapped page under the structure is never cut (A3)
            counts["regions_refused"] = counts.get("regions_refused", 0) + 1
            continue
        counts["pages_cut"] += rep.pages_cut
        counts["lines_cut"] += rep.lines_cut
        counts["area_removed_m2"] += rep.area_removed_m2
    for d in rec.get("decks") or ():
        text, _idx = _add.add_object(text, d["resource"], float(d["lon"]), float(d["lat"]),
                                     float(d["msl"]), float(d["hdg"]))
        counts["decks"] += 1
    chains = rec.get("chains") or ()
    if chains:
        nets = [ln.split(None, 1)[1].strip() for ln in text.split("\n")
                if ln.startswith("NETWORK_DEF ")]
        net = nets[0] if nets else (chains[0].get("net") or net_default)
        text = _add.add_network(text, net, [
            _add.Chain(int(c["subtype"]), tuple((float(a), float(b), int(lv))
                                                for a, b, lv in c["junctions"]))
            for c in chains])
        counts["chains"] = len(chains)
    return text, counts


def write_files(pack_root: str, rec: _t.Mapping) -> list[str]:
    """Write the recipe's files into the pack, and place its LINKS to the
    user's X-Plane art (#2132, ``O4_World_Pack.share_file``: a symbolic
    link, else a hard link, else one copy); the paths written."""
    import O4_World_Pack as _wp
    out = []
    for rel, src in sorted(((rec or {}).get("links") or {}).items()):
        path = os.path.join(pack_root, *rel.split("/"))
        if os.path.isfile(src):
            _wp.share_file(src, path, symlink=True)
            out.append(path)
    for rel, data in sorted(((rec or {}).get("files") or {}).items()):
        path = os.path.join(pack_root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".o4tmp", "wb") as fh:
            fh.write(data)
        os.replace(path + ".o4tmp", path)
        out.append(path)
    return out


def files_of(entry: _t.Mapping) -> list[str]:
    """The pack-relative files a DSF record's recipe wrote."""
    r = (entry or {}).get(RECORD_KEY) or {}
    return [f for f in r.get("files") or () if isinstance(f, str)]


def remove(pack_root: str, rels: _t.Iterable[str]) -> list[str]:
    """Remove the generated files ``rels`` (only under the generated
    folder, only an OBJ that carries the generated mark); the paths gone."""
    gone = []
    for rel in rels:
        if not _is_generated_file(rel):
            continue
        path = os.path.join(pack_root, *rel.split("/"))
        if not (os.path.isfile(path) or os.path.islink(path)):   # a link to X-Plane's art
            continue
        if path.endswith(".obj"):
            try:
                with open(path, encoding="ascii", errors="replace") as fh:
                    if DECK_MARK not in fh.read(256):
                        continue
            except OSError:
                continue
        os.remove(path)
        gone.append(path)
    d = os.path.join(pack_root, *GENERATED_DIR.split("/"))
    if os.path.isdir(d) and not os.listdir(d):
        os.rmdir(d)
    return gone


def record(backup_sha: str, rec: _t.Mapping, counts: _t.Mapping, stamp: str) -> dict:
    """The record row: the recipe without the file bytes, keyed on the
    backup it applies to."""
    return {"backup_sha256": backup_sha, "time": stamp,
            "decks": list(rec.get("decks") or ()), "regions": list(rec.get("regions") or ()),
            "chains": list(rec.get("chains") or ()),
            "files": sorted(set((rec.get("files") or {}).keys())
                            | set((rec.get("links") or {}).keys())
                            | set(rec.get("kept_files") or ())),
            "sha256": {k: hashlib.sha256(v).hexdigest()
                       for k, v in sorted((rec.get("files") or {}).items())},
            "counts": dict(counts)}


def recorded(entry: _t.Mapping, backup_sha: str) -> dict:
    """The recipe a DSF record holds for ``backup_sha`` (files already on
    disk: no bytes), ``{}`` when none."""
    r = (entry or {}).get(RECORD_KEY) or {}
    if not r or r.get("backup_sha256") != backup_sha:
        return {}
    return {"decks": r.get("decks") or [], "regions": r.get("regions") or [],
            "chains": r.get("chains") or [], "files": {}, "kept_files": r.get("files") or []}
