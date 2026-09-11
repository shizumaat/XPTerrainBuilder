"""THE DSF WRITE HALF — dump → edit → encode → verify → write (spec
``docs/specs/auto-patch-v2/object-placement-spec.md`` §3, §5; owner
RULINGS 2026-09-11b).

``airport/dsf.py`` READS the DSFTool text dump; this module EDITS it and
puts the re-encoded DSF back into the pack.  The edit is a find-and-
replace, exactly as the ruling says:

* an ``OBJECT_MSL idx lon lat z hdg`` / ``OBJECT_AGL idx lon lat z hdg``
  row of a PACK resource becomes ``OBJECT idx lon lat hdg`` — X-Plane's
  "on ground": the object's origin sits on the terrain under its anchor,
  so no seat computes anything (§5).  Stock/library resources are never
  touched (09z (2)).
* a split placement becomes N ``OBJECT`` rows, one per body, with
  ``OBJECT_DEF`` lines APPENDED for the new resources — never a
  renumbering of the existing defs, which every existing row indexes.
* every other line is byte-identical, tokens and all: the coordinates
  are copied as TEXT (a KMCI dump spells them to 9 decimals, not the 7 a
  reformat would produce).

THE ROUND TRIP IS LOSSY, AND THIS IS THE MEASUREMENT THAT PINS IT
(KMCI ``+39-095.dsf``, 8,860 + 716 MSL + 1,016 AGL placements, 345
polygons, DSFTool 2.4.0-b1, 2026-09-11): dump → ``--text2dsf`` → dump
with NO EDIT AT ALL already differs in 25,656 body lines.  A DSF stores
coordinates in 16-bit pools, so re-encoding REQUANTISES every number and
REPOOLS the file:

===========================  ==================  =====================
quantity                     measured max drift  pinned tolerance
===========================  ==================  =====================
lon / lat                    4.77e-07 deg        ``TOL_DEG`` 2e-06
  (= 0.03125 deg pool span / 65535, ~0.04 m)
heading                      0.005493 deg        ``TOL_HEADING_DEG`` 0.011
  (= 360 / 65535)
elevation (MSL / AGL)        0.031067 m          ``TOL_ELEV_M`` 0.0625
  (= 2047.96875 / 65535)
row ORDER                    ``OBJECT`` rows and whole polygons are
                             REORDERED by the encoder; the per-keyword
                             counts and the def lists are not.
FILTER                       a filter command is STATE: ``-1`` is the
                             default, the encoder emits the default rows
                             ahead of any ``FILTER`` line and drops one
                             that became redundant.  Compared as the
                             filter IN FORCE per placement / polygon,
                             never as a row sequence (OTHH, 11e).
comments                     ``# file:`` names the encoded path and the
                             ``# pool`` block is regenerated wholesale.
===========================  ==================  =====================

So "identical" CANNOT mean byte-identical text, and a byte diff is not a
verification — it is noise 25,656 lines deep.  :func:`verify_roundtrip`
is what identical means here:

1. every non-comment line that is not a placement or a polygon row —
   the header, ``PROPERTY``, ``FILTER``, ``OBJECT_DEF``, ``POLYGON_DEF``
   — equal IN ORDER, token for token (the def lists are the indices
   every row depends on);
2. the placements equal as a MULTISET per ``(keyword, def index)``,
   matched nearest-first, every matched pair inside the tolerances
   above, none unmatched;
3. the polygons equal as a multiset of ``(def index, param, coords per
   point, per-winding point counts)``, and the ROAD NETWORK as a
   multiset of ``(net def, subtype, shape-point count)`` segments
   matched on both endpoints inside ``TOL_DEG`` — the encoder reorders
   segments, RENUMBERS their node ids (LEMD: node 249 -> 243 on an
   untouched round trip) and may emit one end-first.

The write itself follows the OBJ discipline of v1's ``object_rebake``: the pristine DSF is kept once as
``<name>.dsf.anchor_bak`` and is the SOURCE of every later edit, so a
rerun is idempotent and cannot stack; a provenance record
``o4_placement_provenance.json`` lands beside it.

LANE SAFETY (§3.5): :func:`write_pack` REFUSES a pack under a live
X-Plane installation unless the caller passes ``allow_live_install``.
The app's driver passes it; a lane copies the pack to its scratch.

THE CONSUMERS (spec §3.6, the RULE column this module owns):

===============================  ======================================
consumer                         rule
===============================  ======================================
the dump cache (mtime-keyed,     the write CHANGES the DSF's mtime, so
``find_text_dump`` refuses a     the old dump is refused by the 09ac
stale dump — 09ac)               freshness rule on its own.  The fresh
                                 text is returned as
                                 ``WriteResult.dump_text_path``; the
                                 CALLER installs it, because the mod
                                 cache is the shared data repo and a
                                 write there is a ``--refresh-data``
                                 act, never a build side effect.
``airport/dsf.read_dump``        reads the written DSF unchanged: the
                                 new ``OBJECT_DEF``s are appended, so
                                 every existing index still resolves,
                                 and each converted row now parses as
                                 ``kind="OBJECT"``, ``elevation=None``.
``o4_object_anchor_worklist``    v1's seat worklist: the converted
                                 placements no longer carry an
                                 elevation to correct — retired with
                                 the seat (spec §8), not fed.
``seat_feet_census``             §7's ``--placement-plan`` reads the
                                 plan, not this module.
``tools/reanchor_dsf_objects``   writes ``.obj`` files ONLY, never a
                                 DSF: no second writer exists, and this
                                 module stays the only one.
the Swift app's console lines    the counts of ``WriteResult.counts``.
===============================  ======================================
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import typing as _t
from bisect import bisect_left

from ..model.placement import (BACKUP_SUFFIX, CONVERTIBLE_KINDS, KIND_AGL,
                               KIND_MSL, KIND_ON_GROUND, PROVENANCE_FILENAME,
                               PlacementPlan)

__all__ = ["conversions_for_dump", "TOL_DEG", "TOL_HEADING_DEG", "TOL_ELEV_M",
           "PLACEMENT_KINDS", "RoundTripReport", "WriteResult", "placement_rows",
           "edit_dump", "dump", "encode", "verify_roundtrip", "write_pack",
           "live_install_roots", "pristine_dsf_path", "written_body_files"]


def pristine_dsf_path(dsf_path: str) -> str:
    """THE ONE READ FRAME of the object stage (RULINGS 2026-09-11m).

    ``<dsf>.anchor_bak`` when one is there, else the live file.  Once
    :func:`write_pack` has run, the live DSF carries the bodies this
    stage minted and the backup beside it is the pack as installed; a
    plan derived from the LIVE file names placements (``dsf:obj3021`` …)
    that the write half — which dumps the backup — cannot find, and
    ``edit_dump`` refuses.  EVERY object-stage read resolves through
    here, so a second build over a written pack plans exactly what the
    first one planned.

    A path that already IS a backup is returned unchanged (never
    ``.anchor_bak.anchor_bak``)."""
    if not dsf_path or dsf_path.endswith(BACKUP_SUFFIX):
        return dsf_path
    bak = dsf_path + BACKUP_SUFFIX
    return bak if os.path.isfile(bak) else dsf_path

#: The three placement rows (``airport/dsf.read_dump``'s grammar).
PLACEMENT_KINDS = (KIND_ON_GROUND, KIND_MSL, KIND_AGL)

#: The pinned round-trip tolerances (the table above: ~4x the measured
#: drift, which is one 16-bit quantum of the widest pool seen).
TOL_DEG = 2.0e-6
TOL_HEADING_DEG = 0.011
TOL_ELEV_M = 0.0625

#: A DSF under one of these is the user's LIVE scenery: never a lane's.
_LIVE_HINTS = ("/X-Plane 12/", "/X-Plane 11/", "/X-Plane 12 Demo/")


def live_install_roots(path: str) -> bool:
    """Whether ``path`` lies inside a live X-Plane installation."""
    p = os.path.abspath(path).replace(os.sep, "/") + "/"
    return any(h in p for h in _LIVE_HINTS)


#: WHERE DSFTool COMES FROM: the CALLER passes it.  ``auto_patch_v2``
#: imports no v1 module and reads no environment variable (the package
#: hygiene twin ``test_model.test_no_v1_import_no_env_gate_no_geometry_in_model``
#: enforces both), so the binary is resolved by whoever owns the install
#: — v1's v1's ``dsf_reader`` resolver in the engine, the
#: same call in ``tools/dsf_placement_diff.py`` and in the twins.  One
#: resolver, passed down, never a second one here.


# ── §5: which placements convert ────────────────────────────────────────

def conversions_for_dump(dump_obj: _t.Any, pack_root: str | None = None,
                         library_index: _t.Mapping[str, str] | None = None
                         ) -> tuple[list, list]:
    """``(conversions, kept)`` for a ``airport/dsf.DsfDump`` (§5).

    EVERY ``OBJECT_MSL`` / ``OBJECT_AGL`` placement converts to on-ground
    — pack-authored AND stock library resources alike (owner RULINGS
    2026-09-11d: "it's only changing the placement, not modifying the
    object, and this will then allow them to sit on the new terrain
    better"; 09z (2) forbids REWRITING a library object, never placing
    it).  Nothing is kept here: the ``Kept`` reasons belong to the SPLIT
    (§4 — a stock object is never split or re-anchored).  A placement
    that is already ``OBJECT`` is not listed at all — there is nothing to
    do.

    An ``OBJECT_MSL`` that is a genuine flying object is not
    distinguishable from the DSF; the law is on-ground for everything
    placed, and the owner's sim read is the acceptance."""
    from ..model.placement import Conversion
    conversions: list = []
    kept: list = []
    for i, p in enumerate(dump_obj.placements):
        if p.kind not in CONVERTIBLE_KINDS:
            continue
        conversions.append(Conversion(i, p.def_path, p.lon, p.lat,
                                      p.heading_deg, p.kind,
                                      0.0 if p.elevation is None else p.elevation))
    return conversions, kept


# ── the text edit (pure) ────────────────────────────────────────────────

def placement_rows(lines: _t.Sequence[str]) -> list[tuple[int, int, list[str]]]:
    """``(ordinal, line index, tokens)`` for every row
    ``airport/dsf.read_dump`` counts as a placement, in dump order.

    The ordinal is the plan's ``index``, so the acceptance rule here is
    read_dump's EXACTLY — a row whose def index is out of range, or
    whose numbers do not parse, is a placement to neither (twin-asserted
    in ``tests/auto_patch_v2/test_v2dsfagl.py``)."""
    out: list[tuple[int, int, list[str]]] = []
    n_defs = 0
    ordinal = 0
    for i, raw in enumerate(lines):
        if not raw or raw[0] in "#\n":
            continue
        toks = raw.split()
        kw = toks[0]
        if kw == "OBJECT_DEF":
            n_defs += 1
            continue
        if kw == KIND_ON_GROUND and len(toks) >= 4:
            hi, elev_i = 4, None
        elif kw in CONVERTIBLE_KINDS and len(toks) >= 5:
            hi, elev_i = 5, 4
        else:
            continue
        try:
            oi = int(toks[1])
            float(toks[2]); float(toks[3])
            if len(toks) > hi:
                float(toks[hi])
            if elev_i is not None:
                float(toks[elev_i])
        except (ValueError, IndexError):
            continue
        if not (0 <= oi < n_defs):
            continue
        out.append((ordinal, i, toks))
        ordinal += 1
    return out


def _object_defs(lines: _t.Sequence[str]) -> tuple[list[str], int]:
    """The ``OBJECT_DEF`` paths in order and the line index AFTER the
    last one (where new defs are appended)."""
    defs: list[str] = []
    last = -1
    for i, raw in enumerate(lines):
        if raw.startswith("OBJECT_DEF"):
            defs.append(raw[len("OBJECT_DEF"):].strip())
            last = i
    return defs, last + 1


def duplicate_rows(lines: _t.Sequence[str],
                   of: _t.AbstractSet[int] | None = None
                   ) -> dict[int, list[int]]:
    """§15 (4): the DUPLICATE placement rows, ``{first ordinal: [the
    others]}``.

    Rows of one resource identical in DEF, longitude, latitude and
    HEADING are ONE placement: the pack drew the same object twice on
    the same spot, and the re-seat plan reads it once.  Splitting then
    replaced ONE of them and left the other drawing the WHOLE un-split
    object at the datum — measured on LEMD's pristine DSF, 19 of the
    ``Airport_Cargo`` resources carry two identical rows on the shared
    datum ``-3.564788 40.492764``, so 19 whole objects survived every
    split the plan made.

    ``of`` restricts the answer to groups whose FIRST row is one of
    those ordinals — the plan's SPLIT indices, an EMPTY set meaning no
    split and so no group: a pack that authors the same info sign twice
    on purpose is the pack's business, and nothing here touches a row no
    split replaces.  ``None`` is every group (what the twin reads)."""
    seen: dict[tuple, list[int]] = {}
    for o, _i, toks in placement_rows(lines):
        hdg = toks[4] if toks[0] == KIND_ON_GROUND else (
            toks[5] if len(toks) > 5 else "")
        seen.setdefault((toks[0], toks[1], toks[2], toks[3], hdg), []).append(o)
    return {v[0]: v[1:] for v in seen.values()
            if len(v) > 1 and (of is None or v[0] in of)}


def _eol(lines: _t.Sequence[str]) -> str:
    for raw in lines:
        if raw.endswith("\r\n"):
            return "\r\n"
        if raw.endswith("\n"):
            return "\n"
    return "\n"


def _num(x: float, places: int) -> str:
    return f"{x:.{places}f}"


def edit_dump(text: str, plan: PlacementPlan) -> str:
    """The edited dump text (§3.2).  Pure: no I/O, no DSFTool.

    Raises ``ValueError`` when the plan does not describe THIS dump — a
    placement index past the end, a ``kind_before`` or ``resource`` that
    is not what the row says, an index both converted and split.  A
    stale plan silently editing the wrong rows is the failure this
    refuses."""
    lines = text.splitlines(keepends=True)
    rows = placement_rows(lines)
    by_ordinal = {o: (i, toks) for o, i, toks in rows}
    defs, append_at = _object_defs(lines)

    conv = {c.index: c for c in plan.conversions}
    spl = {s.placement.index: s for s in plan.splits}
    both = sorted(set(conv) & set(spl))
    if both:
        raise ValueError(f"placements both converted and split: {both}")
    missing = sorted((set(conv) | set(spl)) - set(by_ordinal))
    if missing:
        raise ValueError(f"plan names placements this dump does not have: "
                         f"{missing[:8]} (dump has {len(rows)})")

    for idx, c in conv.items():
        _i, toks = by_ordinal[idx]
        if toks[0] != c.kind_before:
            raise ValueError(f"placement {idx}: dump row is {toks[0]}, plan says "
                             f"{c.kind_before}")
        res = defs[int(toks[1])]
        if c.resource and res != c.resource:
            raise ValueError(f"placement {idx}: dump resource {res!r}, plan says "
                             f"{c.resource!r}")
    for idx, s in spl.items():
        _i, toks = by_ordinal[idx]
        res = defs[int(toks[1])]
        if s.placement.resource and res != s.placement.resource:
            raise ValueError(f"placement {idx}: dump resource {res!r}, plan says "
                             f"{s.placement.resource!r}")
        if not s.bodies:
            raise ValueError(f"placement {idx}: split with no body")

    # §15 (4): a split replaces EVERY row of its placement, not one of
    # them.  The first row of a duplicate group takes the body rows (the
    # object is drawn once); the rest are DELETED, so none survives to
    # draw the un-split object at the datum.
    dups = duplicate_rows(lines, set(spl))
    drop = {o for others in dups.values() for o in others}
    if drop & set(conv):
        raise ValueError(f"placements both split-duplicate and converted: "
                         f"{sorted(drop & set(conv))[:8]}")

    eol = _eol(lines)
    new_res = plan.new_resources()
    new_index = {r: len(defs) + k for k, r in enumerate(new_res)}

    edits: dict[int, list[str]] = {}
    for o, i, toks in rows:
        if o in drop:
            edits[i] = []                       # §15 (4): one placement
        elif o in conv:
            # OBJECT_MSL/AGL idx lon lat z hdg -> OBJECT idx lon lat hdg
            # (tokens copied verbatim: no coordinate is re-formatted)
            hdg = toks[5] if len(toks) > 5 else "0.000000"
            edits[i] = [" ".join((KIND_ON_GROUND, toks[1], toks[2], toks[3], hdg)) + eol]
        elif o in spl:
            s = spl[o]
            edits[i] = [" ".join((KIND_ON_GROUND, str(new_index[b.new_resource]),
                                  _num(b.anchor.lon, 9), _num(b.anchor.lat, 9),
                                  _num(b.anchor.heading_deg, 6))) + eol
                        for b in s.bodies]

    out: list[str] = []
    for i, raw in enumerate(lines):
        if i == append_at and new_res:
            out.extend(f"OBJECT_DEF {r}{eol}" for r in new_res)
        out.extend(edits.get(i, (raw,)))
    if new_res and append_at >= len(lines):
        out.extend(f"OBJECT_DEF {r}{eol}" for r in new_res)
    return "".join(out)


# ── DSFTool ─────────────────────────────────────────────────────────────

def _run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:2])} failed (rc {proc.returncode}): "
                           f"{(proc.stderr or proc.stdout).strip()[:400]}")


def dump(dsf_path: str, text_out: str, tool: str) -> str:
    """``DSFTool --dsf2text`` into ``text_out``; returns it."""
    if not tool or not os.path.isfile(tool):
        raise RuntimeError(f"DSFTool binary required, got {tool!r}")
    _run([tool, "--dsf2text", dsf_path, text_out])
    return text_out


def encode(text_path: str, dsf_out: str, tool: str) -> str:
    """``DSFTool --text2dsf`` into ``dsf_out``; returns it."""
    if not tool or not os.path.isfile(tool):
        raise RuntimeError(f"DSFTool binary required, got {tool!r}")
    os.makedirs(os.path.dirname(os.path.abspath(dsf_out)) or ".", exist_ok=True)
    _run([tool, "--text2dsf", text_path, dsf_out])
    if not os.path.isfile(dsf_out):
        raise RuntimeError(f"DSFTool wrote no DSF at {dsf_out}")
    return dsf_out


# ── the verification ────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class RoundTripReport:
    """What the re-dump of the encoded DSF says about the edited text."""

    ok: bool
    placements: int
    unmatched: int
    max_deg: float
    max_heading_deg: float
    max_elev_m: float
    findings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, _t.Any]:
        return _dc.asdict(self)


def _split_rows(text: str) -> tuple[list[list[str]], dict, list[tuple], dict]:
    """``(structural rows, placements, polygon shapes, road segments)``.

    The encoder REORDERS placements, whole polygons and whole road
    segments, and RENUMBERS the network's node ids, so those three never
    compare in order or by id — only as multisets (measured: LEMD's
    ``+40-004.dsf``, 7,218 segments, node 249 -> 243 on an untouched
    round trip)."""
    struct: list[list[str]] = []
    places: dict[tuple[str, int, str], list[tuple[float, ...]]] = {}
    polys: list[tuple] = []
    segs: dict[tuple, list[tuple[float, ...]]] = {}
    cur: list | None = None
    seg: list | None = None
    #: THE FILTER IS STATE, NOT A ROW (measured at OTHH 2026-09-11e): a
    #: ``FILTER`` command sets the filter in force for the rows that
    #: follow, and ``-1`` IS the default (no filter) — so the encoder
    #: emits the default rows first, ahead of any ``FILTER`` line, and
    #: drops a ``FILTER -1`` that has become redundant.  Converting every
    #: elevated row to on-ground does exactly that: OTHH's 36 rows under
    #: an explicit ``FILTER -1`` came back in the default region and the
    #: dump lost two structural rows (2642 -> 2640) with every row's
    #: filter intact.  Comparing the FILTER ROWS in order therefore reads
    #: a canonicalisation as a loss; what must be preserved — and what is
    #: compared here — is the filter IN FORCE at each placement and each
    #: polygon.
    filt = "-1"
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s[0] == "#":
            continue
        toks = s.split()
        kw = toks[0]
        if kw == "HEIGHTS":
            # the encoder's DERIVED height pool (quantum, base, comment):
            # its base follows the elevations that remain, so converting
            # every MSL row moves it (measured: "-9.0" -> "0.0" on KMCI
            # under RULINGS 2026-09-11d).  The quantum is the invariant.
            struct.append(toks[:2])
            continue
        if kw == "FILTER" and len(toks) >= 2:
            filt = "-1" if toks[1] == "-1" else toks[1]
            continue
        if kw in PLACEMENT_KINDS:
            try:
                key = (kw, int(toks[1]), filt)
                places.setdefault(key, []).append(tuple(float(x) for x in toks[2:]))
            except ValueError:
                struct.append(toks)
            continue
        if kw == "BEGIN_SEGMENT" and len(toks) >= 6:
            # BEGIN_SEGMENT def subtype node lon lat elev — the node id is
            # the encoder's, never ours
            seg = [(toks[1], toks[2]), [float(toks[4]), float(toks[5])], 0,
                   [0.0, 0.0]]
            continue
        if kw == "SHAPE_POINT" and seg is not None:
            seg[2] += 1
            continue
        if kw == "END_SEGMENT" and seg is not None and len(toks) >= 5:
            seg[3] = [float(toks[2]), float(toks[3])]
            # CANONICAL ORIENTATION: the encoder may emit a segment
            # end-first, and both ends of a junction share a coordinate —
            # so a segment is matched on BOTH endpoints, ordered.
            p0 = (seg[1][0], seg[1][1])
            p1 = (seg[3][0], seg[3][1])
            if p1 < p0:
                p0, p1 = p1, p0
            segs.setdefault((seg[0][0], seg[0][1], seg[2]), []).append(
                (p0[0], p0[1], p1[0], p1[1]))
            seg = None
            continue
        if kw == "BEGIN_POLYGON":
            cur = [tuple(toks[1:]) + (filt,), []]
            continue
        if kw == "BEGIN_WINDING" and cur is not None:
            cur[1].append(0)
            continue
        if kw == "POLYGON_POINT" and cur is not None and cur[1]:
            cur[1][-1] += 1
            continue
        if kw == "END_WINDING" and cur is not None:
            continue
        if kw == "END_POLYGON" and cur is not None:
            polys.append((cur[0], tuple(cur[1])))
            cur = None
            continue
        struct.append(toks)
    return struct, places, polys, segs


def _match(a: list, b: list, tol: float, tiebreak: bool,
           dims: int = 2) -> tuple[int, list]:
    """Greedy nearest-first match of two coordinate-row lists over their
    first ``dims`` columns (indexed on column 0); returns
    ``(unmatched, pairs)``.  ``tiebreak`` separates coincident rows by
    their last column (a heading: two objects may stand on the same
    metre and differ only there); ``dims=4`` matches a road segment on
    BOTH its endpoints, since every junction shares one of them."""
    order = sorted(range(len(b)), key=lambda j: b[j][0])
    lons = [b[j][0] for j in order]
    used = [False] * len(b)
    pairs: list = []
    unmatched = 0
    for row in a:
        j = bisect_left(lons, row[0] - tol)
        best, bd = None, 1e18
        while j < len(order) and lons[j] <= row[0] + tol:
            cand = order[j]
            if not used[cand]:
                o = b[cand]
                d = sum(abs(o[i] - row[i]) for i in range(dims))
                if tiebreak:
                    d += 1e-9 * _ang(o[-1], row[-1])
                if d < bd:
                    bd, best = d, cand
            j += 1
        if best is None:
            unmatched += 1
            continue
        used[best] = True
        pairs.append((row, b[best]))
    return unmatched, pairs


def _ang(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def compare_dumps(expected: str, actual: str) -> RoundTripReport:
    """The pinned comparison of two dump texts (the module docstring's
    rules).  Order-insensitive wherever the encoder reorders."""
    findings: list[str] = []
    sa, pa, ga, na = _split_rows(expected)
    sb, pb, gb, nb = _split_rows(actual)

    if len(sa) != len(sb):
        findings.append(f"structural rows {len(sa)} -> {len(sb)}")
    for k, (x, y) in enumerate(zip(sa, sb)):
        if x != y:
            findings.append(f"structural row {k}: {' '.join(x)!r} -> {' '.join(y)!r}")
            break

    if sorted(ga) != sorted(gb):
        findings.append(f"polygon shapes differ ({len(ga)} -> {len(gb)})")

    total = unmatched = 0
    md = mh = mz = 0.0
    for key in sorted(set(pa) | set(pb)):
        a = pa.get(key, [])
        b = list(pb.get(key, []))
        total += len(a)
        if len(a) != len(b):
            findings.append(f"{key[0]} def {key[1]} (filter {key[2]}): "
                            f"{len(a)} -> {len(b)} placements")
        u, pairs = _match(a, b, TOL_DEG, True)
        unmatched += u
        has_z = key[0] in CONVERTIBLE_KINDS
        for row, o in pairs:
            md = max(md, abs(o[0] - row[0]), abs(o[1] - row[1]))
            mh = max(mh, _ang(o[-1], row[-1]))
            if has_z and len(o) > 2 and len(row) > 2:
                mz = max(mz, abs(o[2] - row[2]))
    if unmatched:
        findings.append(f"{unmatched} placement(s) with no counterpart within "
                        f"{TOL_DEG} deg")

    seg_unmatched = 0
    for key in sorted(set(na) | set(nb)):
        a = na.get(key, [])
        b = list(nb.get(key, []))
        if len(a) != len(b):
            findings.append(f"network {key}: {len(a)} -> {len(b)} segments")
        u, pairs = _match(a, b, TOL_DEG, False, dims=4)
        seg_unmatched += u
        for row, o in pairs:
            md = max(md, max(abs(o[i] - row[i]) for i in range(4)))
    if seg_unmatched:
        findings.append(f"{seg_unmatched} road segment(s) with no counterpart "
                        f"within {TOL_DEG} deg")

    if md > TOL_DEG:
        findings.append(f"position drift {md:.3g} deg > {TOL_DEG}")
    if mh > TOL_HEADING_DEG:
        findings.append(f"heading drift {mh:.4g} deg > {TOL_HEADING_DEG}")
    if mz > TOL_ELEV_M:
        findings.append(f"elevation drift {mz:.4g} m > {TOL_ELEV_M}")
    return RoundTripReport(not findings, total, unmatched + seg_unmatched, md, mh, mz,
                           tuple(findings))


def verify_roundtrip(dsf_path: str, expected_text: str, tool: str,
                     text_out: str | None = None) -> RoundTripReport:
    """Dump ``dsf_path`` again and compare it with the edited text."""
    tmp = text_out
    if tmp is None:
        fd, tmp = tempfile.mkstemp(suffix=".verify.text")
        os.close(fd)
    dump(dsf_path, tmp, tool)
    with open(tmp, "r", errors="replace") as fh:
        actual = fh.read()
    if text_out is None:
        os.unlink(tmp)
    return compare_dumps(expected_text, actual)


# ── the write ───────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class WriteResult:
    dsf_path: str
    backup_path: str
    backup_created: bool
    dump_text_path: str
    provenance_path: str
    report: RoundTripReport
    counts: _t.Mapping[str, int]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def written_body_files(pack_root: str, dsf_path: str) -> tuple[str, ...]:
    """The body files the PREVIOUS write of this DSF made, as absolute
    paths, from ``o4_placement_provenance.json`` beside it (11m).

    The restore step removes exactly these before writing again — a plan
    that cuts fewer bodies than the last one would otherwise leave the
    surplus ``__b<k>.obj`` in the pack forever.  A pack with no
    provenance, or provenance from before this key existed, names
    nothing and NOTHING is removed."""
    prov = os.path.join(os.path.dirname(dsf_path), PROVENANCE_FILENAME)
    try:
        with open(prov) as fh:
            rows = json.load(fh).get("body_files") or []
    except (OSError, ValueError, AttributeError):
        return ()
    out: list[str] = []
    root = os.path.abspath(pack_root)
    for rel in rows:
        if not isinstance(rel, str) or not rel:
            continue
        p = os.path.abspath(os.path.join(root, *rel.replace("\\", "/").split("/")))
        if p.startswith(root + os.sep):
            out.append(p)
    return tuple(out)


def write_pack(pack_root: str, plan: PlacementPlan, tool: str, *,
               allow_live_install: bool = False,
               work_dir: str | None = None,
               engine_version: str = "",
               law_digest: str = "",
               body_files: _t.Sequence[str] = ()) -> WriteResult:
    """Apply ``plan`` to the pack's DSF (§3.3-§3.5).

    The pristine DSF is kept ONCE as ``<name>.dsf.anchor_bak`` and is
    the source of the dump every time, so a rerun of the same plan
    produces the same bytes and two different plans never stack.  The
    edited text is encoded to a temp DSF, VERIFIED, and only then moved
    into place; ``o4_placement_provenance.json`` lands beside it.

    ``allow_live_install`` is the lane-safety switch of §3.5: without it
    a pack under a live X-Plane install is REFUSED."""
    dsf_path = plan.dsf_path or ""
    if not os.path.isfile(dsf_path):
        raise FileNotFoundError(f"DSF not found: {dsf_path!r}")
    if not os.path.abspath(dsf_path).startswith(os.path.abspath(pack_root) + os.sep):
        raise ValueError(f"DSF {dsf_path!r} is not inside pack root {pack_root!r}")
    if live_install_roots(dsf_path) and not allow_live_install:
        raise PermissionError(
            f"REFUSING to write a live X-Plane installation: {dsf_path!r} "
            f"(spec §3.5 — a lane writes a COPY of the pack; the app's driver "
            f"passes allow_live_install=True)")

    backup = plan.dsf_backup_path or (dsf_path + BACKUP_SUFFIX)
    created = False
    if not os.path.isfile(backup):
        shutil.copy2(dsf_path, backup)
        created = True

    work = work_dir or tempfile.mkdtemp(prefix="o4_dsf_write_")
    os.makedirs(work, exist_ok=True)
    base = os.path.basename(dsf_path)
    pristine_text = os.path.join(work, base + ".pristine.text")
    edited_text = os.path.join(work, base + ".edited.text")
    out_dsf = os.path.join(work, base + ".new")

    dump(backup, pristine_text, tool)
    with open(pristine_text, "r", errors="replace") as fh:
        text = fh.read()
    edited = edit_dump(text, plan)
    with open(edited_text, "w") as fh:
        fh.write(edited)

    encode(edited_text, out_dsf, tool)
    report = verify_roundtrip(out_dsf, edited, tool)
    if not report.ok:
        raise RuntimeError("DSF round-trip verification failed: "
                           + "; ".join(report.findings[:4]))

    shutil.move(out_dsf, dsf_path)

    counts = dict(plan.counts())
    prov = {
        "version": 1,
        "icao": plan.icao,
        "pack_name": plan.pack_name,
        "dsf": base,
        "backup": os.path.basename(backup),
        "dump_sha256": hashlib.sha256(text.encode("utf-8", "replace")).hexdigest(),
        "backup_sha256": _sha256(backup),
        "written_sha256": _sha256(dsf_path),
        "engine_version": engine_version or plan.provenance.engine_version,
        "law_digest": law_digest or plan.provenance.law_digest,
        "counts": counts,
        "roundtrip": report.to_dict(),
        # 11m: what the NEXT restore removes — pack-relative, sorted, and
        # ONLY the files this writer made.
        "body_files": sorted(
            os.path.relpath(os.path.abspath(f), os.path.abspath(pack_root)
                            ).replace(os.sep, "/")
            for f in body_files),
    }
    prov_path = os.path.join(os.path.dirname(dsf_path), PROVENANCE_FILENAME)
    with open(prov_path, "w") as fh:
        json.dump(prov, fh, indent=1, sort_keys=True)

    return WriteResult(dsf_path, backup, created, edited_text, prov_path,
                       report, counts)
