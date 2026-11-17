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
  deck's solved zero;
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
import math
import os
import typing as _t

from shapely import wkt as _wkt
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.ops import transform

from . import deck_paint as _paint
from . import deck_texture as _tex
from .deck_obj8 import DECK_MARK, DeckFrame, DeckLight, DeckLine, deck_obj8_text

__all__ = ["RECORD_KEY", "GENERATED_DIR", "TEXTURE", "recipe", "apply_text",
           "write_files", "remove", "files_of", "recorded", "record",
           "regions_of"]

RECORD_KEY = "o4_generated"
GENERATED_DIR = "objects/o4_generated"
TEXTURE = "o4_deck_concrete.png"


def _is_generated_file(path: str) -> bool:
    """A file this module writes (the generated-objects folder)."""
    return GENERATED_DIR in path.replace("\\", "/")


def _poly(ring) -> Polygon:
    p = Polygon([tuple(q) for q in ring])
    return p if p.is_valid else p.buffer(0.0)


def _mean(pts) -> tuple[float, float]:
    """The centroid of the points ``pts`` (an end line's stations)."""
    c = MultiPoint([tuple(p) for p in pts]).centroid
    return (c.x, c.y)


def _deck_frame(rec: _t.Mapping) -> DeckFrame:
    """The placement frame: anchored at the ring's centroid, heading along
    the carried route (end A to end B), so the route runs along ``-z``."""
    c = _poly(rec["ring"]).centroid
    f0 = DeckFrame(c.x, c.y, 0.0)
    (ax, az), (bx, bz) = (f0.to_local(*_mean(rec["seats_a"])),
                          f0.to_local(*_mean(rec["seats_b"])))
    hdg = math.degrees(math.atan2(bx - ax, -(bz - az))) % 360.0
    return DeckFrame(c.x, c.y, hdg)


def _top_fn(rec: _t.Mapping, frame: DeckFrame):
    """``top_y(x, z)``: the deck's one plane in the object frame -- level
    across the route, ``top_a`` at end A rising to ``top_b`` at end B,
    plus ``top_lift_m`` (the object's zero is the deck's zero)."""
    a = frame.to_local(*_mean(rec["seats_a"]))
    b = frame.to_local(*_mean(rec["seats_b"]))
    dx, dz = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dz * dz or 1.0
    ta, tb, lift = float(rec["top_a"]), float(rec["top_b"]), float(rec.get("top_lift_m", 0.02))

    def top_y(x: float, z: float) -> float:
        t = ((x - a[0]) * dx + (z - a[1]) * dz) / n2
        return ta + t * (tb - ta) + lift
    return top_y


def _paint_of(dropped, R_local: Polygon, frame: DeckFrame, light_step: float
              ) -> tuple[list[DeckLine], list[DeckLight], dict]:
    """The dropped apt.dat ``120`` pieces inside the deck, as X-Plane's
    own stripes (``deck_paint``) and named lights."""
    lines: list[DeckLine] = []
    lights: list[DeckLight] = []
    stats = {"lines": 0, "unpainted": 0, "lights": 0}
    inner = R_local.buffer(-0.05)
    for d in dropped:
        g = LineString([frame.to_local(lo, la) for lo, la in d.points])
        g = g.intersection(inner)
        for piece in getattr(g, "geoms", [g]):
            if piece.is_empty or piece.geom_type != "LineString" or piece.length < 0.2:
                continue
            stripes = _paint.stripes_of(int(d.line)) if d.line else ()
            if d.line and not stripes:
                stats["unpainted"] += 1
            for k, (off, w, colour, dash) in enumerate(stripes):
                ln = piece.parallel_offset(off, "left") if abs(off) > 1e-6 else piece
                for gg in getattr(ln, "geoms", [ln]):
                    if gg.is_empty or gg.length < 0.05:
                        continue
                    for seg in _paint.dashed_pieces(gg, dash):
                        lines.append(DeckLine(tuple(seg.coords), w, colour,
                                              0.0 if colour == "black" else 0.004 * (k + 1)))
                stats["lines"] += 1
            names = _paint.light_names(int(d.light)) if d.light else ()
            if names:
                s = light_step / 2.0
                while s < piece.length:
                    p = piece.interpolate(s)
                    lights += [DeckLight(n, p.x, p.y) for n in names]
                    stats["lights"] += 1
                    s += light_step
    return lines, lights, stats


def recipe(generated: _t.Mapping, apt_path: str, icao: str, law) -> dict:
    """The write recipe of an airport's generated structures (module doc):
    ``{"decks": [placement rows], "regions": [WKT], "chains": [...],
    "files": {pack-relative path: bytes}, "notes": [...]}``; empty lists
    where nothing was generated."""
    from . import apt_flatten as _af
    decks = list((generated or {}).get("decks") or ())
    bridges = list((generated or {}).get("road_bridges") or ())
    out: dict = {"decks": [], "regions": [], "chains": [], "files": {}, "notes": []}
    if not decks and not bridges:
        return out
    regions = [_poly(d["ring"]) for d in decks] + \
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
    for k, d in enumerate(decks):
        frame = _deck_frame(d)
        R = transform(lambda x, y, _z=None, _f=frame: _f.to_local(x, y), _poly(d["ring"]))
        top_y = _top_fn(d, frame)
        lines, lights, st = _paint_of(dropped_by_deck.get(k, ()), R, frame,
                                      float(g.light_spacing_m))
        rel = str(d["resource"])
        text = deck_obj8_text(R, top_y, thickness_m=float(d.get("thickness_m", 1.0)),
                              texture=TEXTURE, lines=lines, lights=lights,
                              lod_m=(0.0, float(g.lod_m)),
                              comments=[f"{d['object_id']} spec 2123 A2: zero "
                                        f"{float(d['zero_m']):.3f} m heading "
                                        f"{frame.heading_deg:.3f}"])
        out["files"][rel] = text.encode("ascii")
        out["decks"].append({"object_id": d["object_id"], "resource": rel,
                             "lon": frame.lon, "lat": frame.lat,
                             "msl": round(float(d["zero_m"]), 4),
                             "hdg": round(frame.heading_deg, 6)})
        out["notes"].append(f"deck {d['object_id']}: {len(R.exterior.coords) - 1}-point ring "
                            f"{R.area:,.0f} m2, zero {float(d['zero_m']):.2f} m, "
                            f"{st['lines']} stripe run(s) of {len(dropped_by_deck.get(k, ()))} "
                            f"dropped line piece(s), {st['lights']} light(s)"
                            + (f", {st['unpainted']} line(s) of a type not painted"
                               if st["unpainted"] else ""))
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
    """Write the recipe's files into the pack; the paths written."""
    out = []
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
        if not os.path.isfile(path):
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
