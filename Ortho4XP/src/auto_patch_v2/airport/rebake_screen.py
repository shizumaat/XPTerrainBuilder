"""THE SCREEN SIDECAR — what the patch build hands the object step so the
REBAKE PLAN can be built there (owner RULINGS 2026-10-04x (1), issue #362).

The plan (``rebake_plan.plan`` -> ``o4_v2_rebake_<ICAO>.json``) is read by
the post-mesh object stage and by nothing in the patch: it ran AFTER
``write_patch`` and cost OTHH ~195 s of every cold patch build.  It is a
pure function of

* the PACK PARTITION — which the patch build already keeps, in the
  partition cache (``partition_cache``), with the placed objects it was
  read from; and
* a handful of PLANAR and SOLVED facts that are gone once the build
  returns: the placements the terrain adapted to, the plate seats, the
  below-grade regions and their owners, the solved surface's value at
  every deck ring, the connector verdict, the flat-site datum, the frame.

Those facts are this record (:class:`RebakeScreen`, :func:`take`), written
beside the patch as ``o4_v2_rebake_<ICAO>.screen.json``.  The object step
calls :func:`build_plan`: the partition is REVIVED under the exact
fingerprint the patch build recorded and handed to the same
``rebake_plan.plan``, so the plan's bytes are the ones the patch build
used to write.

NEVER SERVED STALE.  The record is KEYED to the build that wrote it — the
patch body's sha256 (every piece it emitted), the partition cache's
fingerprint and the partition's own content digest, the law tables, the
partition code digest and the plan version — and :func:`build_plan`
REFUSES (:class:`StaleScreen`) on any mismatch.  A partition that is no
longer cached is :class:`ColdPartition`: the object step never
re-partitions (that is the patch build's work, with the patch build's
DEM); the tile driver's freshness gate sends such an airport back through
its patch build (:func:`unservable`).

A patch build that kept NO partition cache (no pack dump, no mod-cache
root, a refused write) writes no sidecar and plans inline, as before.

No environment is read here.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import json
import os
import typing as _t

from ..law import Law
from ..model.airport import FlatVerdict, SceneryPack
from ..model.frame import Frame, XY
from ..model.rebake import PLAN_VERSION, RebakePlan
from . import extension_cache as _extcache
from . import partition_cache as _pcache
from . import rebake_plan as _rplan

__all__ = ["SCREEN_VERSION", "SCREEN_FILENAME", "RebakeScreen", "StaleScreen",
           "ColdPartition", "patch_body_sha256", "take", "read", "revived",
           "stale_reason", "unservable", "build_plan", "plan_line"]

#: Bump when the SHAPE of the record changes; another version is refused.
SCREEN_VERSION = 2

#: ``<patch dir>/o4_v2_rebake_<ICAO>.screen.json`` — beside the patch and
#: beside the plan it becomes (``model.rebake.PLAN_FILENAME``).  The object
#: stage's plan glob does not match it (``engine_v2._PLAN_NAME_RE``).
SCREEN_FILENAME = "o4_v2_rebake_{icao}.screen.json"


class StaleScreen(RuntimeError):
    """The sidecar is not the record of the patch / partition / law / code
    in hand: no plan is built from it."""


class ColdPartition(StaleScreen):
    """The partition the sidecar names is no longer cached under its
    fingerprint: the plan cannot be built without re-partitioning, which
    is the PATCH build's work."""


def patch_body_sha256(path: str | os.PathLike) -> str:
    """sha256 of a patch's BODY — every line after the XML declaration and
    the ``<osm …>`` root tag that carries the build's provenance stamps
    (the harness's ``build_airport.body_sha256``; a twin holds the two
    equal)."""
    with open(path, "rb") as fh:
        lines = fh.read().split(b"\n")
    return hashlib.sha256(b"\n".join(lines[2:])).hexdigest()


def _law_key(law: Law) -> tuple[str | None, str]:
    from ..law.tables import law_tables_digest
    return law_tables_digest().get("sha256"), str(law.ruleset_key)


@_dc.dataclass(frozen=True)
class RebakeScreen:
    """Everything ``rebake_plan.plan`` reads beyond the cached partition;
    JSON round-trips exactly (floats by ``repr``, polygons as WKB hex).

    ``plates`` placement id -> ``(plate y, stations in frame xy[,
    clearance])`` exactly as ``pipeline.build._plate_seats`` minted them;
    ``below_grade`` ``(region WKB hex | None, owner ids)`` per basin;
    ``deck_datum`` ``(ring in frame xy, solved z | None)`` for every ring
    the plan can ask about (``rebake_plan.datum_rings``); ``connectors``
    the stamped verdicts in their plan form; ``flat`` the flat-site
    verdict's ``(verdict, auto verdict, z0, source, region)`` or ``None``.
    The KEY: ``patch_bodies`` (the body sha256 of the whole patch and of
    every tile piece), ``partition_path`` / ``partition_fp`` /
    ``partition_digest``, ``law_sha256`` / ``ruleset``, ``code_digest``
    and ``plan_version``."""

    icao: str
    pack_name: str
    pack_root: str
    frame: Frame
    excluded: tuple[str, ...]
    plates: _t.Mapping[str, tuple]
    below_grade: tuple[tuple[str | None, tuple[str, ...]], ...]
    deck_datum: tuple[tuple[tuple[XY, ...], float | None], ...]
    connectors: "tuple[_t.Mapping[str, _t.Any], ...] | None"
    flat: "tuple | None"
    patch_bodies: tuple[str, ...]
    partition_path: str
    partition_fp: str
    partition_digest: str | None
    law_sha256: str | None
    ruleset: str
    code_digest: str
    plan_version: int = PLAN_VERSION
    #: object-placement spec §18: the seat records the plan publishes
    authored_seats: tuple[_t.Mapping[str, _t.Any], ...] = ()

    def to_json(self) -> str:
        fr = self.frame
        d = {
            "version": SCREEN_VERSION, "icao": self.icao,
            "pack_name": self.pack_name, "pack_root": self.pack_root,
            "frame": {"icao": fr.icao, "origin": list(fr.origin),
                      "identity_dp": fr.identity_dp, "crs": fr.crs,
                      "input_quantum_m": fr.input_quantum_m},
            "excluded": list(self.excluded),
            "plates": {k: [v[0], [list(p) for p in v[1]], *v[2:]]
                       for k, v in self.plates.items()},
            "authored_seats": [dict(r) for r in self.authored_seats],
            "below_grade": [[w, list(ids)] for w, ids in self.below_grade],
            "deck_datum": [[[list(p) for p in ring], z]
                           for ring, z in self.deck_datum],
            "connectors": (None if self.connectors is None
                           else [dict(c) for c in self.connectors]),
            "flat": None if self.flat is None else {
                "verdict": self.flat[0], "auto_verdict": self.flat[1],
                "z0_m": self.flat[2], "source": self.flat[3],
                "region": [[[list(p) for p in outer],
                            [[list(p) for p in h] for h in holes]]
                           for outer, holes in self.flat[4]]},
            "key": {"patch_bodies": list(self.patch_bodies),
                    "partition_path": self.partition_path,
                    "partition_fp": self.partition_fp,
                    "partition_digest": self.partition_digest,
                    "law_sha256": self.law_sha256, "ruleset": self.ruleset,
                    "code_digest": self.code_digest,
                    "plan_version": self.plan_version},
        }
        return json.dumps(d, sort_keys=True, separators=(",", ":"),
                          default=_plain)

    @classmethod
    def from_json(cls, text: str) -> "RebakeScreen":
        d = json.loads(text)
        if d.get("version") != SCREEN_VERSION:
            raise StaleScreen(f"screen sidecar version {d.get('version')!r}, "
                              f"this engine reads {SCREEN_VERSION}")
        ring = lambda r: tuple((float(a), float(b)) for a, b in r)      # noqa: E731
        fr, k, fl = d["frame"], d["key"], d.get("flat")
        return cls(
            str(d["icao"]), str(d["pack_name"]), str(d["pack_root"]),
            Frame(str(fr["icao"]), (float(fr["origin"][0]), float(fr["origin"][1])),
                  int(fr["identity_dp"]), str(fr["crs"]),
                  float(fr["input_quantum_m"])),
            tuple(str(x) for x in d["excluded"]),
            {str(i): (v[0], [tuple(p) for p in v[1]], *v[2:])
             for i, v in d["plates"].items()},
            tuple((w, tuple(str(x) for x in ids)) for w, ids in d["below_grade"]),
            tuple((ring(r), z) for r, z in d["deck_datum"]),
            None if d.get("connectors") is None else tuple(d["connectors"]),
            None if fl is None else (
                str(fl["verdict"]), str(fl["auto_verdict"]), fl["z0_m"],
                str(fl["source"]),
                tuple((ring(outer), tuple(ring(h) for h in holes))
                      for outer, holes in fl["region"])),
            tuple(str(x) for x in k["patch_bodies"]),
            str(k["partition_path"]), str(k["partition_fp"]),
            k.get("partition_digest"), k.get("law_sha256"), str(k["ruleset"]),
            str(k["code_digest"]), int(k["plan_version"]),
            tuple(dict(r) for r in d.get("authored_seats", ())))


def _plain(v: _t.Any) -> _t.Any:
    """``json`` default: a numpy scalar as the Python value it prints as."""
    item = getattr(v, "item", None)
    if callable(item):
        return item()
    raise TypeError(f"not JSON-serialisable in a screen sidecar: {type(v).__name__}")


def _wkb(geom: _t.Any) -> str | None:
    if geom is None:
        return None
    import shapely
    return shapely.to_wkb(geom, hex=True)


def _from_wkb(text: str | None) -> _t.Any:
    if text is None:
        return None
    import shapely
    return shapely.from_wkb(text)


def take(airport: _t.Any, objects: _t.Sequence, law: Law, *,
         deck_datum: _rplan.DeckDatum | None,
         exclude: _t.Collection[str],
         tunnel_objects: _t.Mapping[str, tuple],
         below_grade: _t.Sequence[tuple[object, _t.Collection[str]]],
         patches: _t.Iterable[str | os.PathLike],
         authored_seats: _t.Sequence[_t.Mapping[str, _t.Any]] = ()) -> RebakeScreen | None:
    """The record of THIS patch build — its keywords are ``rebake_plan.
    plan``'s own (``pipeline.build._rebake_inputs`` assembles them) — or ``None`` when the run
    kept no partition cache (the caller then plans inline).  ``patches``
    are the patch files the build emitted (the whole patch and every tile
    piece); the solved surface is read HERE, at every deck ring, because
    it is gone by the object step."""
    part = airport.partition
    kept = None if part is None else _pcache.filed(part.pack_root, airport.icao)
    if kept is None:
        return None
    fv = airport.flat_site
    law_sha, ruleset = _law_key(law)
    return RebakeScreen(
        airport.icao, airport.pack.name, part.pack_root, airport.frame,
        tuple(sorted(exclude)), dict(tunnel_objects),
        tuple((_wkb(r), tuple(ids)) for r, ids in below_grade),
        tuple((tuple(ring), None if deck_datum is None else deck_datum(ring))
              for ring in _rplan.datum_rings(objects, below_grade)),
        (None if getattr(part, "connectors", None) is None
         else tuple(v.to_dict() for v in part.connectors)),
        None if fv is None else (fv.verdict, fv.auto_verdict, fv.z0_m,
                                 fv.source, fv.region),
        tuple(sorted({patch_body_sha256(p) for p in patches})),
        kept[0], kept[1], _extcache.base_digest(part), law_sha, ruleset,
        _pcache.code_digest(), authored_seats=tuple(dict(r) for r in authored_seats))


def read(path: str | os.PathLike) -> RebakeScreen:
    """The sidecar at ``path``; :class:`StaleScreen` when it is not one
    this engine reads."""
    try:
        with open(path, encoding="utf-8") as fh:
            return RebakeScreen.from_json(fh.read())
    except StaleScreen:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise StaleScreen(f"unreadable screen sidecar {path}: {exc}") from exc


def stale_reason(screen: RebakeScreen, law: Law,
                 patch: str | os.PathLike | None = None) -> str | None:
    """Why ``screen`` is NOT the record of the build in hand, or ``None``.
    ``patch`` is the patch file the mesh was built from; its body must be
    one this record's build emitted."""
    law_sha, ruleset = _law_key(law)
    if (screen.law_sha256, screen.ruleset) != (law_sha, ruleset):
        return "the law tables moved since the patch was built"
    if screen.code_digest != _pcache.code_digest():
        return "the engine's pack-reading code moved since the patch was built"
    if screen.plan_version != PLAN_VERSION:
        return (f"plan version {screen.plan_version} was recorded, this "
                f"engine writes {PLAN_VERSION}")
    if patch is not None:
        try:
            body = patch_body_sha256(patch)
        except OSError as exc:
            return f"the patch cannot be read ({exc})"
        if body not in screen.patch_bodies:
            return (f"the patch body {body[:12]} is not the one this record "
                    f"was written for ({', '.join(b[:12] for b in screen.patch_bodies)})")
    return None


def unservable(path: str | os.PathLike) -> str | None:
    """STAT-CHEAP: why the sidecar at ``path`` can never become a plan —
    it cannot be read, or the partition cache file it names is gone — or
    ``None``.  The tile driver's freshness gate asks this for a patch
    whose plan is not built yet, so a cold partition is re-read by the
    PATCH build and never by the object step."""
    try:
        screen = read(path)
    except StaleScreen as exc:
        return str(exc)
    if not os.path.isfile(screen.partition_path):
        return f"partition cache {screen.partition_path} is gone"
    return None


def revived(payload: _t.Any, law: Law) -> "tuple[_t.Any, list, _t.Any] | None":
    """``(ResourceCache, placed objects, partition)`` of a partition-cache
    payload, put back as ``pipeline.build.pack_stage`` puts a HIT back: the
    placements and the small per-resource readings restored, the
    partition's member recipes bound to this run's cache.  ``None`` for a
    payload of another shape."""
    if not isinstance(payload, tuple) or len(payload) != 5:
        return None
    from . import frame_entry as _fe
    from . import partition_cache as _pcache
    from .obj8 import ResourceCache
    objects, _report, part, _clusters, _derived = payload
    cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m,
                          _fe.quantum(law))
    _pcache.put_back(cache, payload)
    return cache, objects, part


@_dc.dataclass(frozen=True)
class _Site:
    """What ``rebake_plan.plan`` reads off an ``Airport`` when it is given
    the partition (its doc): the object step has no loaded airport."""

    icao: str
    frame: Frame
    pack: SceneryPack
    flat_site: FlatVerdict | None


def build_plan(screen: RebakeScreen, law: Law, *,
               patch: str | os.PathLike | None = None,
               keep_extension: bool = False) -> RebakePlan:
    """THE PLAN, from the cached partition and ``screen`` — the same
    ``rebake_plan.plan`` call the patch build used to make, so
    ``to_json()`` is byte-identical for identical inputs.

    Raises :class:`StaleScreen` when the record is not this build's
    (:func:`stale_reason`; ``patch`` names the patch to hold it against),
    :class:`ColdPartition` when the partition is not cached under the
    recorded fingerprint or is not the reading the record digested.
    ``keep_extension``: may the extension be WRITTEN beside the partition
    cache — the object step and the harness's plan step pass ``True``."""
    why = stale_reason(screen, law, patch)
    if why:
        raise StaleScreen(why)
    got = revived(_pcache.revive(screen.partition_path, screen.partition_fp,
                                 screen.pack_root, screen.icao), law)
    if got is None:
        raise ColdPartition(
            f"partition cache {screen.partition_path} holds no reading under "
            f"the fingerprint the patch build recorded ({screen.partition_fp[:12]})")
    cache, objects, part = got
    if _extcache.base_digest(part) != screen.partition_digest:
        raise ColdPartition(
            f"partition cache {screen.partition_path} is not the reading the "
            "patch was built from (content digest differs)")
    datum = {ring: z for ring, z in screen.deck_datum}

    def _datum(ring_xy: _t.Sequence[XY]) -> float | None:
        try:
            return datum[tuple(ring_xy)]
        except KeyError:
            raise StaleScreen("a deck ring the patch build never read: the "
                              "pack's decks moved since the patch was built"
                              ) from None

    fl = screen.flat
    site = _Site(screen.icao, screen.frame,
                 SceneryPack(screen.pack_name, "", "", (), ()),
                 None if fl is None else FlatVerdict(fl[0], fl[1], fl[2], fl[3],
                                                     fl[4], {}))
    rplan = _rplan.plan(
        site, objects, cache, law, _datum, exclude=screen.excluded,
        tunnel_objects=screen.plates,
        below_grade=[(_from_wkb(w), ids) for w, ids in screen.below_grade],
        partition=part, keep_extension=keep_extension,
        authored_seats=screen.authored_seats)
    return _dc.replace(rplan, connectors=screen.connectors)


def plan_line(icao: str, rplan: RebakePlan, seconds: float) -> str:
    """The ``[ICAO] rebake plan …`` line — ONE spelling for whoever built
    the plan (the object step, the harness's plan step, an inline build)."""
    rc = rplan.counts
    return (f"[{icao}] rebake plan {seconds:.2f} s  units {rc['units']}  "
            f"members {rc['members']}  deck members {rc['deck_members']} "
            f"(signature {rc.get('signature_decks', 0)} in {rc.get('deck_families', 0)} "
            f"deck families)  "
            f"parts {rc['parts']}  contacts {rc['contacts']}  pools {rc['pools']}  "
            f"structures {rc['structures']}  skipped {len(rplan.skipped)} "
            f"(stock {rc['stock']}, multi-anchor {rc['multi_anchor']}, "
            f"outside pack {rc['outside_pack']}, msl {rc['msl']}, "
            f"terrain-adapted {rc['terrain_adapted']}, below grade {rc['below_grade']})")
