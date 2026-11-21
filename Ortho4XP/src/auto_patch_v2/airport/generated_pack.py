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
  ``taxi_g`` / ``taxi_g_rev``; the pack author's pages and lines on and
  around it, ``deck_author_art``, #2183) under ``objects/o4_generated/`` with its
  texture (``deck_texture``), placed by one ``OBJECT_MSL`` row at the
  deck's solved zero; where the user's X-Plane install resolves them
  (#2132, ``deck_skin``) the slab is drawn in X-Plane's own concrete
  page and the paint + lights and the author's films are overlay objects
  at the same anchor, the art LINKED into the folder;
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
from . import deck_ride as _ride
from . import deck_texture as _tex
from . import dsf_row_hide as _hide
from .deck_obj8 import DECK_MARK
from .deck_objects import GENERATED_DIR, TEXTURE, ring_polygon

__all__ = ["RECORD_KEY", "GENERATED_DIR", "TEXTURE", "recipe", "apply_text",
           "write_files", "remove", "files_of", "recorded", "record",
           "regions_of"]

RECORD_KEY = "o4_generated"


def _is_generated_file(path: str) -> bool:
    """A file this module writes (the generated-objects folder)."""
    return GENERATED_DIR in path.replace("\\", "/")


def recipe(generated: _t.Mapping, apt_path: str, icao: str, law,
           xplane_root: "str | None" = None, resolve_library=None,
           read_dump: "_t.Callable[[str], str | None] | None" = None) -> dict:
    """The write recipe of an airport's generated structures (module doc):
    ``xplane_root`` the install whose art draws the decks (#2132), ``None``
    to find it (``deck_skin.install_root``), ``""`` for none (the atlas);
    ``resolve_library`` the install's library lookup
    (``deck_skin.Resolver``; the object stage hands in X-Plane's merged
    index), ``None`` for none (the atlas); ``read_dump(dsf path)`` the
    path of a DSF's text dump (the caller's cache), ``None`` for none (the
    decks then carry none of the pack author's art, #2183).
    ``{"decks": [placement rows], "regions": [WKT], "chains": [...],
    "files": {pack-relative path: bytes}, "notes": [...]}``; empty lists
    where nothing was generated."""
    from . import apt_flatten as _af
    decks = list((generated or {}).get("decks") or ())
    bridges = list((generated or {}).get("road_bridges") or ())
    out: dict = {"decks": [], "regions": [], "chains": [], "files": {}, "notes": [],
                 "hides": [], "deck_tops": []}
    if not decks and not bridges:
        return out
    # owner 2026-11-17 (KPHX): a pack placement that only fakes the cut
    # under a deck is hidden -- the real cut and the deck replace it
    out["hides"] = [dict(h) for d in decks for h in d.get("hides") or ()]
    # #2131: a deck's open approaches leave the pack's pages with its ring
    regions = [ring_polygon(d["ring"]) for d in decks] + \
        [ring_polygon(q) for d in decks for q in d.get("approach") or () if len(q) >= 3] + \
        [_wkt.loads(b["span_wkt"]) for b in bridges if b.get("span_wkt")]
    dropped_by_deck: dict[int, list] = {}
    if apt_path:
        shipped = _af.read_path(apt_path)
        try:
            with open(shipped, "rb") as fh:
                data = _af.stripped(fh.read())
            for k, d in enumerate(decks):
                _data, _rec, dropped = _af._cut(data, icao, [ring_polygon(d["ring"])])
                dropped_by_deck[k] = dropped
        except OSError as exc:
            out["notes"].append(f"apt.dat unreadable ({exc}): no paint redrawn")
    g = law.tables.structures.deck_gen
    root = _install_root(apt_path, xplane_root) if decks else None
    art = _objs.install_art(g, root, resolve_library) if decks else None
    apt = _apt_block(apt_path, icao) if decks else None
    author = _Author(apt_path, root, resolve_library, read_dump)
    # owner 2026-11-21T06:47Z (KMCO): a hidden bridge takes its own drapes
    out["hides"] += author.companions(decks, out["hides"], g.hide_inside_share)
    for k, d in enumerate(decks):
        code = _pav.carried_surface(apt, ring_polygon(d["ring"]), str(d.get("family") or ""),
                                    d.get("route")) if apt is not None else None
        runway = _pav.carried_runway(apt, ring_polygon(d["ring"])) if apt is not None else None
        objs, st = _objs.deck_objects(d, dropped_by_deck.get(k, ()), art, g, surface_code=code,
                                      runway=runway, authored=author.of(d))
        rel = str(d["resource"])
        frame = st["frame"]
        # RULINGS 2026-11-19c: the pack's placements on the deck ride its top
        out["deck_tops"].append(_ride.deck_top(d, frame, st["top_y"]))
        for orel, text in objs:
            out["files"][orel] = text.encode("ascii")
            out["decks"].append({"object_id": d["object_id"] + orel[len(rel) - 4:-4],
                                 "resource": orel, "lon": frame.lon, "lat": frame.lat,
                                 "msl": round(float(d["zero_m"]), 4),
                                 "hdg": round(frame.heading_deg, 6)})
        R = ring_polygon(d["ring"])
        out["notes"].append(f"deck {d['object_id']}: {len(R.exterior.coords) - 1}-point ring, "
                            f"zero {float(d['zero_m']):.2f} m, heading {frame.heading_deg:.1f}, "
                            f"surface {code if code is not None else 'unknown'} "
                            f"({st.get('slab') or 'generated atlas'}), {st['parts']} part(s) "
                            f"({st.get('piers', 0)} column(s)), "
                            f"{st['lines']} line run(s) of {len(dropped_by_deck.get(k, ()))} "
                            f"dropped line piece(s), {st['lights']} light(s), "
                            f"{len(objs)} object(s)"
                            + (f", {st['runway_marks']} runway mark(s)"
                               if st.get("runway_marks") else "")
                            + f", author film(s) {st.get('films') or 'none'}"
                            + (f", {st['author_lines']} author line run(s)"
                               if st.get("author_lines") else "")
                            + (f", {st['unpainted']} line(s) of a type not painted"
                               if st["unpainted"] else ""))
    if art is not None:
        out["links"] = dict(art.links)
        out["files"].update(art.files)
    if decks:
        out["files"][f"{GENERATED_DIR}/{TEXTURE}"] = _tex.deck_texture_png()
    for b in bridges:
        if not b.get("junctions"):
            continue        # #2183 item 5: a road bridge is a deck (pipeline/road_deck)
        out["chains"].append({"subtype": int(b["subtype"]),
                              "junctions": [list(j) for j in b["junctions"]],
                              "net": str(b.get("net") or "")})
        out["notes"].append(f"road bridge {b.get('id')}: {len(b['junctions'])} junction(s), "
                            f"subtype {b['subtype']}")
    out["regions"] = [r.wkt for r in regions]
    return out


def _install_root(apt_path: str, root: "str | None") -> "str | None":
    """#2132: the install whose art draws the decks: ``root`` as given,
    else the one the pack stands in, else the app's (``deck_skin``)."""
    from . import deck_skin as _skin
    return _skin.install_root(apt_path) if root is None else root


class _Author:
    """The pack author's art per deck (``deck_author_art``, #2183): the
    pack DSF's pages read once per tile from its PRISTINE dump."""

    def __init__(self, apt_path: str, root, resolve, read_dump) -> None:
        from . import deck_author_art as _aa
        from . import deck_skin as _skin
        self.pack = os.path.dirname(os.path.dirname(apt_path)) if apt_path else ""
        self.root, self.read_dump = root, read_dump
        self.look = _aa.pack_first(self.pack, _skin.laminar_first(resolve) if root else resolve)
        self.pages: dict = {}
        self.rows: dict = {}
        #: per tile, the page indices never carried (``deck_companions``)
        self.skip: dict = {}

    def _pages(self, lon: float, lat: float) -> list:
        import math

        from . import deck_author_art as _aa
        from . import deck_companions as _dc
        from .backup_state import pristine_dsf_path
        from .dsf import dsf_path_in_pack
        key = (math.floor(lat), math.floor(lon))
        if key not in self.pages:
            self.pages[key], self.rows[key] = [], {}
            dsf = pristine_dsf_path(dsf_path_in_pack(self.pack, *key))
            dump = self.read_dump(dsf) if os.path.isfile(dsf) else None
            if dump:
                with open(dump, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
                self.pages[key], self.rows[key] = _aa.pack_pages(text), _dc.placements(text)
        return self.pages[key]

    def companions(self, decks: _t.Sequence[_t.Mapping], hides: _t.Sequence[_t.Mapping],
                   share: float) -> list[dict]:
        """The ``hides`` rows of the hidden bridges' own drapes
        (``deck_companions``), remembered so no deck carries them."""
        import math

        from . import deck_companions as _dc
        from .obj8 import resolve_resource
        if not (self.pack and self.read_dump and decks):
            return []
        spans = [(ring_polygon(d["ring"]), d.get("route")) for d in decks]
        by_tile: dict = {}
        for h in hides:
            lon, lat = float(h["lon"]), float(h["lat"])
            self._pages(lon, lat)
            key = (math.floor(lat), math.floor(lon))
            hdg = next((r[2] for r in self.rows[key].get(str(h["resource"]), ())
                        if abs(r[0] - lon) <= _hide.TOL_DEG and abs(r[1] - lat) <= _hide.TOL_DEG),
                       None)
            phys = resolve_resource(str(h["resource"]), self.pack, None) or (
                self.look(str(h["resource"]), self.root) if self.root else None)
            plan = _dc.plan_box(phys, lon, lat, hdg) if hdg is not None and phys else None
            if plan is not None:
                by_tile.setdefault(key, []).append((plan, str(h["object_id"])))
        out: list[dict] = []
        for key, plans in by_tile.items():
            found = _dc.companions(self.pages[key], [p for p, _o in plans], spans, share)
            self.skip[key] = {k for k, _i in found}
            out += _dc.rows(self.pages[key], found, [o for _p, o in plans])
        return out

    def of(self, d: _t.Mapping) -> "_objs.Authored | None":
        """The :class:`deck_objects.Authored` of deck record ``d``."""
        from . import deck_author_art as _aa
        from . import deck_line_art as _la
        from . import deck_skin as _skin
        if not (self.pack and self.root and self.read_dump):
            return None
        import math
        R = ring_polygon(d["ring"])
        pages = self._pages(R.centroid.x, R.centroid.y)
        skip = self.skip.get((math.floor(R.centroid.y), math.floor(R.centroid.x)), set())
        arts = []
        for p in _aa.end_pages(pages, R, d.get("route")):
            art = _skin.page_art(p, self.root, self.look)
            if art is not None:
                arts.append((_aa.draw_order(self.look(p, self.root) or ""), art))
        # X-Plane's draw order: layer group, then the DSF's own order
        films = tuple(a for _o, a in sorted(arts, key=lambda t: t[0]))
        lines = []
        for path, pts in _aa.deck_lines(pages, R, d.get("route"), skip):
            try:
                phys = self.look(path, self.root)
            except (OSError, ValueError):
                phys = None
            page = _la.read_page(phys) if phys else None
            if page is not None:
                lines.append((page, pts))
        return _objs.Authored(films, tuple(lines))


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


def apply_text(text: str, rec: _t.Mapping, net_default: str = "",
               splits: _t.Sequence = (), pack_root: str = "") -> tuple[str, dict]:
    """The DSF dump ``text`` with the recipe applied (module doc): pages
    clipped by every region, every deck placed, every chain added, every
    hidden placement dropped -- as its bodies where ``splits`` (the plan's
    ``Split`` rows) wrote it split (#2167) -- and every pack placement left
    standing on a deck seated on its top (``deck_ride``, RULINGS
    2026-11-19c; ``pack_root`` reads the models and object strings).
    #2178: only the decks anchored on the dump's tile, and the chains
    clipped to it (``generated_tile.for_tile``).  Returns ``(text, counts)``."""
    from . import dsf_additions as _add
    from . import dsf_poly_clip as _clip
    from . import generated_tile as _gt
    from .split_guard import tile_box
    counts = {"pages_cut": 0, "lines_cut": 0, "area_removed_m2": 0.0, "decks": 0,
              "chains": 0}
    if not rec:
        return text, counts
    rec, tile_counts = _gt.for_tile(rec, tile_box(text))
    counts.update(tile_counts)
    # a hidden bridge's own drapes leave first: the clip moves the first
    # point that names them (``deck_companions``)
    drapes = [(h["resource"], h["lon"], h["lat"]) for h in rec.get("hides") or ()
              if h.get("companion")]
    if drapes:
        text, counts["drapes_hidden"] = _hide.hide_rows(text, drapes)
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
    hides = [(h["resource"], h["lon"], h["lat"]) for h in rec.get("hides") or ()
             if not h.get("within") and not h.get("companion")]
    # a piece-wise hide: only the bodies of its split standing within
    pieces = [(h["resource"], h["lon"], h["lat"], h["within"])
              for h in rec.get("hides") or () if h.get("within") and not h.get("companion")]
    rows = _hide.through_splits(hides, splits, pack_root=pack_root) if hides else []
    if pieces:
        rows += _hide.pieces_within(pieces, splits, pack_root=pack_root)
    if hides or pieces:
        text, counts["hidden"] = _hide.hide_rows(text, rows)
    if hides or pieces:
        # the written text read back: no hidden placement, nor any body of
        # its split (within a piece-wise hide's plan), may still be drawn
        # (census ``pack_bridge_under_deck``)
        counts["hides_drawn"] = [list(r) for r in _hide.drawn_rows(text, hides, splits)
                                 + _hide.drawn_pieces(text, pieces, splits)]
    if rec.get("overlap_hides"):
        # #2145: the structures another pack also draws, the user's answer
        # (``pack_overlap_choice.overlap_hides``)
        text, counts["overlap_hidden"] = _hide.hide_rows(
            text, _hide.through_splits(rec["overlap_hides"], splits, pack_root=pack_root))
    text, ride, _rides = _ride.ride_text(text, rec.get("deck_tops") or (), pack_root)
    counts.update(ride)
    if rec.get("drop_network"):
        # RULINGS 2026-11-19i: our overlay's roads where another pack
        # replaces the default road network over the tile
        text, counts["segments_dropped"] = _hide.drop_segments(text)
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
            # #2140: the faked-cut placements hidden ride the record too,
            # so a write that keeps it (``recorded``) still hides them
            "hides": list(rec.get("hides") or ()),
            "deck_tops": list(rec.get("deck_tops") or ()),
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
            "chains": r.get("chains") or [], "hides": r.get("hides") or [],
            "deck_tops": r.get("deck_tops") or [], "files": {}, "kept_files": r.get("files") or []}
