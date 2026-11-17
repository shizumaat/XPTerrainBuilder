"""THE OFFER TO HIDE LARGE STRUCTURES TWO PACKS BOTH DRAW (issue #2145).

Owner (2026-11-17T19:15Z): both Chudoba Dubai and OMDB TaiModels "model
the train and it's stations.  We want the user to be able to pick which
one to keep, then adjust that one to fit the terrain.  Default would be
to prefer the airport pack, but let the user choose which pack they want
to take priority."

* :func:`_detect` — THE TILE'S READING: for each airport pack on the tile
  (a runway of its own, ``drape_stage``'s scan), every other enabled
  pack with an overlay DSF on the tile is read for the large structures
  both draw within 1 km of the airport (``auto_patch_v2.airport.
  pack_overlap``).  A pair is asked about only when an airport pack is
  one of the two and the two are not parts of one larger package (owner
  2026-11-17T23:21Z, RULINGS 17s: two non-airport packs, or one family —
  ``pack_family.same_family`` — are kept both, unasked).  Each pair
  asked about is remembered (``pack_overlap_choice.remember_found``) and
  becomes one row.
* :func:`overlap_stage` — the build's call once a tile is built
  (``o4_engine.session``, on a thread of its own): the rows the user has
  not answered announced as ``PackOverlaps(state="found")`` (the report,
  ``"ask"``, lists every row).  Never raises.
* :func:`overlap_choice` — the ``pack_overlaps`` command: ``"ask"`` (the
  report), ``"choose"`` (``items``: ``{"key", "winner"}`` per pair, the
  winner a pack name or ``"both"``), ``"undo"`` (forget the answers of
  ``items``' keys).  Each pack whose hiding changed is rewritten at once
  (``pack_rewrite.rewrite_dsf``: the write reads the answers,
  ``dsf_write._with_overlap_hides``; its original stays the backup and
  Restore originals puts it back).

A row: ``{"key", "packs": [a, b], "airport", "default", "winner",
"count", "rows": [n_a, n_b], "summary"}`` — ``default`` is the airport
pack; when both are airport packs (the one case 17s leaves to the ini),
the pack higher in the user's ``scenery_packs.ini`` (owner
2026-11-17T20:24Z, RULINGS 17o; alphabetical only among packs the ini
does not list) — the picker's pre-selection; ``winner`` the stored answer ("" when
unanswered).  Nothing here names an airport or a pack.
"""
from __future__ import annotations

import os
import traceback
import typing as _t

import O4_UI_Utils as UI
from auto_patch_v2.airport import pack_overlap as _po
from auto_patch_v2.airport import pack_overlap_choice as _ovc

__all__ = ["ACTIONS", "overlap_stage", "overlap_choice"]

#: the actions of the ``pack_overlaps`` command
ACTIONS = ("ask", "choose", "undo")


def _announce(lat: int, lon: int, state: str, items: list, files=(),
              error: str = "") -> None:
    UI.pack_overlaps(lat=int(lat), lon=int(lon), state=state, items=items,
                     files=list(files), error=error)


def _candidates(scenery_dir: str, lat: int, lon: int) -> tuple[list[str], list[str]]:
    """``(airport packs, every pack read)`` of the tile: enabled, outside
    the simulator's folders, not the app's own overlay pack, with an
    overlay DSF on the tile (an airport pack always)."""
    import O4_DSF_Header as _H
    import O4_Overlay_Pack as _OP
    from auto_patch_v2.airport import dsf as _dsf2

    from .drape_stage import _folder_packs, _runway_apt
    from .post_mesh import _is_protected_scenery_root
    airports, packs = [], []
    for p in _folder_packs(scenery_dir, lat, lon):
        if _is_protected_scenery_root(p) or os.path.isfile(os.path.join(p, _OP.MARKER)):
            continue
        if _runway_apt(p):
            airports.append(p)
            packs.append(p)
        elif _H.dsf_is_overlay(_dsf2.dsf_path_in_pack(p, lat, lon)):
            packs.append(p)
    return airports, packs


def _structures(pack_root: str, lat: int, lon: int, frame, region, ctx
                ) -> list[_po.Structure]:
    from . import obj8_reader as _or
    from .object_stage import pack_dump
    pd = pack_dump(pack_root, lat, lon, read_only=False)
    if pd is None:
        return []
    name = os.path.basename(os.path.normpath(pack_root))
    with open(pd.dump_path, encoding="utf-8", errors="replace") as fh:
        return _po.structures(
            name, fh, frame, region, ctx["min_area_m2"],
            lambda r: _or.resolve_object_resource(r, pack_root, ctx["xplane_root"]),
            ctx["cache"])


def _context(xplane_root: str) -> dict:
    from auto_patch_v2.airport import frame_entry as _fe
    from auto_patch_v2.airport import obj8 as _obj8
    from auto_patch_v2.law.model import Law
    law = Law.load()
    return {"xplane_root": xplane_root,
            "min_area_m2": float(law.tables.structures.building_pad.min_area_m2),
            "cache": _obj8.ResourceCache(
                law.tables.structures.basin.min_solid_thickness_m, _fe.quantum(law))}


def default_pack(scenery_dir: str, airports: _t.Collection[str],
                 packs: _t.Sequence[str]) -> str:
    """The pre-selected winner of a pair: its one airport pack; when both
    (or neither) are airport packs, the pack X-Plane loads first (higher in
    ``scenery_packs.ini``); packs the ini does not list rank after the
    listed ones, alphabetically (RULINGS 17o, 17s)."""
    own = [p for p in packs if p in airports]
    if len(own) == 1:
        return own[0]
    import O4_Scenery_Packs as _SP
    ordered, _disabled = _SP.parse_ini(
        os.path.join(scenery_dir or "", _SP.INI_FILENAME))
    rank = {name: i for i, name in enumerate(ordered)}
    return min(packs, key=lambda p: (rank.get(p, len(rank)), p))


def _row(key: str, airport: str, pair: _po.OverlapPair,
         scenery_dir: str = "", airports: _t.Collection[str] = ()) -> dict:
    return {"key": key, "packs": list(pair.packs), "airport": airport,
            "default": default_pack(scenery_dir, {airport, *airports},
                                    pair.packs),
            "winner": _ovc.winner(key), "count": pair.count,
            "rows": [len(r) for r in pair.rows], "summary": pair.summary()}


def _asked(scenery_dir: str, airports: _t.Collection[str]):
    """The test a found pair passes to become a row (RULINGS 17s): an
    airport pack is one of the two, and they are not one family."""
    from auto_patch_v2.airport import pack_family as _pf

    from .drape_stage import _runway_apt
    try:
        names = sorted(n for n in os.listdir(scenery_dir)
                       if os.path.isdir(os.path.join(scenery_dir, n)))
    except OSError:
        names = []
    seen: dict[str, bool] = dict.fromkeys(airports, True)

    def is_airport(name: str) -> bool:
        if name not in seen:
            seen[name] = bool(_runway_apt(os.path.join(scenery_dir, name)))
        return seen[name]

    def asked(a: str, b: str) -> bool:
        return ((is_airport(a) or is_airport(b))
                and not _pf.same_family(a, b, names, is_airport))
    return asked


def _detect(scenery_dir: str, lat: int, lon: int, xplane_root: str) -> list[dict]:
    """THE TILE'S READING (module doc): one row per pack pair."""
    from auto_patch_v2.airport import apt_flatten as _af
    airports, packs = _candidates(scenery_dir, lat, lon)
    if not airports or len(packs) < 2:
        return []
    ctx = _context(xplane_root)
    anames = [os.path.basename(os.path.normpath(a)) for a in airports]
    asked = _asked(scenery_dir, anames)
    rows: dict[str, dict] = {}
    for ap in airports:
        aname = os.path.basename(os.path.normpath(ap))
        for frame, region in _po.airport_regions(_af.apt_dat_of(ap)):
            by_pack = {os.path.basename(os.path.normpath(p)):
                       _structures(p, lat, lon, frame, region, ctx) for p in packs}
            for pair in _po.overlaps(by_pack):
                key = _ovc.pair_key(scenery_dir, *pair.packs)
                if key in rows or not asked(*pair.packs):
                    continue
                _ovc.remember_found(key, lat, lon, aname, pair.packs, pair.rows)
                rows[key] = _row(key, aname, pair, scenery_dir, anames)
    return list(rows.values())


def overlap_stage(lat: int, lon: int, xplane_root: str | None) -> list[dict]:
    """The build's offer for a built tile (module doc).  Never raises."""
    try:
        if not xplane_root:
            return []
        rows = _detect(os.path.join(xplane_root, "Custom Scenery"), lat, lon,
                      xplane_root)
        rows = [r for r in rows if not r["winner"]]      # answered: not asked again
        for r in rows:
            UI.vprint(0, f"  [overlap] {r['summary']}")
        if rows:
            _announce(lat, lon, "found", rows)
        return rows
    except Exception as exc:
        UI.vprint(1, f"  [overlap] the overlapping-structure check failed ({exc})")
        UI.vprint(2, traceback.format_exc())
        return []


def _rewrite(scenery_dir: str, name: str, lat: int, lon: int) -> str:
    """Write one pack's tile DSF with the answers as they now stand;
    returns its pack-relative DSF path, ``""`` when it has none."""
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport.pack_choice import relative

    from . import pack_rewrite as _PR
    root = os.path.join(scenery_dir, name)
    dsf = _dsf2.dsf_path_in_pack(root, lat, lon)
    if not os.path.isfile(dsf):
        return ""
    _PR.rewrite_dsf(root, name, dsf)
    return relative(root, dsf)


def overlap_choice(xplane_root: str | None, action: str,
                   items: _t.Sequence[_t.Mapping] = (),
                   lat: int | None = None, lon: int | None = None) -> dict:
    """THE USER'S ANSWER (module doc); announces the outcome and returns
    its fields.  Never raises: a failure is ``state="failed"``."""
    la, lo = int(lat or 0), int(lon or 0)
    try:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        if not xplane_root:
            raise ValueError("no X-Plane install for this tile")
        scenery = os.path.join(xplane_root, "Custom Scenery")
        if action == "ask":
            rows = _detect(scenery, la, lo, xplane_root)
            out = {"state": "ask", "items": rows, "files": []}
        else:
            out = _answer(scenery, action, items)
    except Exception as exc:
        UI.vprint(0, f"  [overlap] the answer could not be applied ({exc})")
        UI.vprint(2, traceback.format_exc())
        out = {"state": "failed", "items": [], "files": [], "error": str(exc)}
    _announce(la, lo, out["state"], out["items"], out["files"], out.get("error", ""))
    return out


def _hidden(scenery: str, name: str, lat: int, lon: int) -> list:
    from auto_patch_v2.airport import dsf as _dsf2
    root = os.path.join(scenery, name)
    return _ovc.overlap_hides(root, _dsf2.dsf_path_in_pack(root, lat, lon))


def _answer(scenery: str, action: str, items: _t.Sequence[_t.Mapping]) -> dict:
    """Store the answers of ``items`` and rewrite every pack whose hiding
    changed (a pack whose rows stay is never written)."""
    found = [(str(it.get("key") or ""), it) for it in items]
    found = [(k, it, _ovc.found(k)) for k, it in found]
    found = [(k, it, d) for k, it, d in found if d.get("packs")]
    packs = {(p, int(d["lat"]), int(d["lon"])) for _k, _it, d in found
             for p in d["packs"]}
    before = {t: _hidden(scenery, *t) for t in packs}
    rows = []
    for key, it, doc in found:
        after = "" if action == "undo" else str(it.get("winner") or "")
        if after and after != _ovc.BOTH and after not in doc["packs"]:
            raise ValueError(f"{after!r} is not one of {doc['packs']}")
        _ovc.STORE.remember(key, after)
        rows.append({"key": key, "packs": list(doc["packs"]), "winner": after})
    files = [f for t in sorted(packs) if _hidden(scenery, *t) != before[t]
             for f in [_rewrite(scenery, *t)] if f]
    for r in rows:
        UI.vprint(0, f"  [overlap] {' and '.join(r['packs'])}: "
                + (f"keeping {r['winner']}'s structures, hiding the other's"
                   if r["winner"] not in ("", _ovc.BOTH) else "both packs drawn"))
    return {"state": "undone" if action == "undo" else "chosen",
            "items": rows, "files": files}
