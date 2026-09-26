"""THE WRITE HALF, JOINED (owner RULINGS 2026-09-11e (3); spec
``object-placement-spec.md`` §9).

Round one produced the two halves and no join: ``placement_plan`` decides
the bodies, their anchors and the cut files; ``dsf_write`` edits, encodes
and verifies the pack's DSF.  THIS module is the single order in which a
pack is changed, so that the engine's write half and every tool run the
same sequence and nobody grows a second one:

0. the RESTORE (owner RULINGS 2026-09-11f (1); spec §8's one-shot
   restore, run on every ``agl`` write): every ``<obj>.anchor_bak`` in
   the pack is copied back over its object BEFORE any file is written.
   The v1 seat baked its deltas into the pack's own ``.obj`` files and
   kept the originals beside them; under the placement law those deltas
   are wrong twice over — a body's vertices are re-anchored by the CUT,
   and a placement the plan keeps WHOLE is never rewritten at all, so it
   would otherwise render on the old seat's vertex offsets forever.  The
   pass is idempotent (a pack with no backup restores nothing, a pack
   already restored copies nothing) and the backups are KEPT: they are
   what ``placement_plan.pristine_path`` reads, and §8 deletes them with
   the seat, not before.  The PREVIOUS write's OWN body files go in the
   same step (11m) — the ones ``o4_placement_provenance.json`` names,
   and only those, each confirmed to carry this writer's ``CUT_MARK``;
1. the PLAN — ``conversions`` for every MSL / AGL row of the dump (11d:
   stock placements convert too), ``splits`` for the placements whose
   bodies were coarsened into more than one file, ``kept`` for the rest;
2. the CUT FILES into the pack's ``objects/`` under NEW names
   (``<stem>__b<k>.obj``): an authored file is never opened for writing,
   so no ``.anchor_bak`` is needed for them and a rerun overwrites only
   what this writer itself made;
3. the DSF — ``dsf_write.write_pack``: the pristine DSF is kept once as
   ``<name>.dsf.anchor_bak`` and is the source of every dump, the edited
   text is encoded, VERIFIED against the re-dump, and only then moved
   into place beside ``o4_placement_provenance.json``;
4. the DUMP CACHE — the read path (v1's DSF reader and its mtime-keyed
   ``<dsf>.<tag>.text``) is keyed on the DSF's mtime, which
   step 3 just changed; the caller passes its own
   ``refresh_dump(dsf_path)`` (v2 imports no v1 module) and it is called
   AFTER the move, so the next build reads the pack it wrote and not the
   07-30 dump (the OTHH precedent);
5. the PLAN JSON beside the patch — ``o4_v2_placement_<ICAO>.json``,
   which ``tools/seat_feet_census.py --placement-plan`` censuses.

NOTHING HERE DECIDES ANYTHING.  The bodies are ``placement_plan``'s, the
anchors ``anchor_rule``'s, the edit ``dsf_write``'s; what this adds is the
ORDER and the refusals — a split index that is also a conversion, a cut
file that would land on an authored name, a pack under a live X-Plane
install without the app's explicit ``allow_live_install``.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import typing as _t

from ..model.placement import (CUT_MARK, PLAN_FILENAME, PlacementPlan,
                               Provenance)
from . import backup_state as _bs
from . import dsf_write as _dw
from . import footprint_unit as _fu
from . import placement_plan as _pp

__all__ = ["PlacementWriteResult", "RestoreResult", "build_plan", "write_files",
           "restore_pack_objects", "apply_plan"]

#: v1's seat kept the authored bytes beside the file it baked.
ANCHOR_BAK = ".anchor_bak"


@_dc.dataclass(frozen=True)
class RestoreResult:
    """Step 0 (11f (1)): the backups found and the objects put back."""

    backups: tuple[str, ...] = ()
    restored: tuple[str, ...] = ()
    #: the PREVIOUS write's body files, removed before this one (11m)
    bodies_removed: tuple[str, ...] = ()
    #: §12a rows O6 / O7 and D7: the stale backup was RETIRED under a
    #: ``.superseded-<UTC>`` name and the user's file was left alone
    adopted: tuple[str, ...] = ()
    #: §12a row O5: ours by WITNESS only — the live bytes were kept as
    #: ``<obj>.unrecognised-<UTC>`` before the backup went back over them
    unproven: tuple[str, ...] = ()

    @property
    def counts(self) -> dict[str, int]:
        return {"restore_backups": len(self.backups),
                "restore_restored": len(self.restored),
                "restore_bodies_removed": len(self.bodies_removed),
                "restore_adopted": len(self.adopted),
                "restore_unproven": len(self.unproven)}


@_dc.dataclass(frozen=True)
class PlacementWriteResult:
    """What the write did, in the shape the engine's summary prints."""

    plan: PlacementPlan
    plan_path: str
    files_written: tuple[str, ...]
    dsf: _dw.WriteResult | None
    dump_refreshed: str | None
    counts: _t.Mapping[str, int]
    restore: RestoreResult = RestoreResult()


# ── step 1: the plan ────────────────────────────────────────────────────

def build_plan(rebake_plan: _t.Any, dump: _t.Any, surface: _t.Callable,
               *, icao: str, pack_name: str, pack_root: str, dsf_path: str,
               split_tol_m: float, elevated_base_m: float = 0.0,
               line_segment_m: float = 0.0, line_stations_max: int = 0,
               line_ratio: float = 0.0, line_max_h: float = 0.0,
               foot_band_m: float = 0.0,
               coarsen_reach_m: float = 0.0, contact_eps_m: float = 0.0,
               rigid_reach_m: float = 0.0,
               bind_ground_m: float = 0.0,
               cluster_min_m2: float = 0.0,
               touch_m: float = 0.0, connector_span_m: float = 0.0,
               chain_min_height_m: float = 0.0,
               airside_floor: bool = False,
               # RETIRED (owner RULINGS 2026-09-17t): the low-side pad
               # datum is gone; kept as an accepted no-op keyword because
               # ``src/auto_patch/engine_v2.py`` still passes it.
               low_side: bool = False,
               hard_tol_m: float = 0.02,
               abutment_step_m: float = 0.0,
               abutment_walk_max_m: float = 0.0,
               pads: _t.Sequence = (), rims: _t.Sequence = (),
               engine_version: str = "", law_digest: str = "",
               write_cuts: bool = True,
               decks: _t.Sequence = (),                                 # §49
               deck_on_fraction: float = 0.5,
               deck_edge_m: float = 0.0,
               deck_under_m: float = 0.0,
               jetway_strips: _t.Sequence = ()) -> tuple[PlacementPlan, tuple, _pp.SplitSet]:
    """``(plan, cut files, the SplitSet behind it)``.

    ``rebake_plan`` is the build's own ``<ICAO>.rebake.json`` model (the
    pack read once, its parts and the ε-contact graph — the bodies ARE
    its); ``dump`` a ``airport/dsf.DsfDump`` of the pack's DSF;
    ``surface`` the design surface X-Plane will drape on
    (``surface(lat, lon) -> z | None``).

    A placement that is SPLIT is never also converted: its rows are
    replaced outright (``dsf_write.edit_dump`` refuses the overlap), so
    the conversions are filtered by the split indices here, where the two
    lists are first seen together."""
    ss = _pp.build_splits(rebake_plan, surface, pads, rims, write=write_cuts,
                          split_tol_m=split_tol_m, elevated_base_m=elevated_base_m,
                          line_segment_m=line_segment_m,
                          line_stations_max=line_stations_max,
                          line_ratio=line_ratio, line_max_h=line_max_h,
                          foot_band_m=foot_band_m,
                          coarsen_reach_m=coarsen_reach_m,
                          contact_eps_m=contact_eps_m,
                          rigid_reach_m=rigid_reach_m,
                          bind_ground_m=bind_ground_m,
                          cluster_min_m2=cluster_min_m2,
                          touch_m=touch_m,
                          connector_span_m=connector_span_m,
                          chain_min_height_m=chain_min_height_m,
                          airside_floor=airside_floor,
                          abutment_step_m=abutment_step_m,
                          abutment_walk_max_m=abutment_walk_max_m,
                          decks=decks, deck_on_fraction=deck_on_fraction,
                          deck_edge_m=deck_edge_m, deck_under_m=deck_under_m)
    splits, kept = _pp.to_placement_records(ss)
    conversions, _kept_conv = _dw.conversions_for_dump(dump, pack_root)
    split_idx = frozenset(s.placement.index for s in splits)
    conversions = tuple(c for c in conversions if c.index not in split_idx)
    # §16g (5) PER-PLACEMENT ELEVATION (owner RULINGS 2026-09-13bw; the
    # owner's own 2026-09-11a/b words).  A MULTI-ANCHOR resource — one
    # file at N anchors needing N seats — is dropped from the plan, keeps
    # its authored row and renders wherever the terrain went; KCLT's
    # passengers and seats are 205 of them.  It is seated HERE, on the
    # row, because this is the one place the DUMP and the plan are seen
    # together.
    _flat = getattr(rebake_plan, "flat", None)
    _msl_counts: dict[str, int] = {}
    msl = _fu.msl_seats_for_dump(dump, rebake_plan, ss.unit_seats, surface,
                                 pack_root, split_idx,
                                 tol_m=hard_tol_m,
                                 authored_ground=(None if _flat is None
                                                  else _flat.z0_m),
                                 counts=_msl_counts)
    # a row seated by §16g (5) is NOT also converted to on-ground: the
    # whole point is that it keeps an elevation column
    _conv0 = conversions
    _mi = frozenset(m.index for m in msl)
    conversions = tuple(c for c in conversions if c.index not in _mi)
    # jetway-strip spec §4 / C17 (issue #31): THE RIDERS — a placement the
    # plan holds no geometry for, riding the unit whose outline it stands
    # at.  The population is the DESIGN side's (the graded surface's
    # ``jetway_strips``), never a second host search.  A rider row is
    # left ON GROUND where the terrain at its anchor already equals its
    # unit's datum (after the strip law, the normal case); it carries
    # ``OBJECT_MSL`` = datum + authored offset only on a CLAMPED gate, and
    # never for an ``.agp`` (§4 (3), Q6 default).  Where §16g (5) had
    # already written a row for a rider on ground it is withdrawn: the
    # strip IS its seat.
    from . import riders as _riders
    riders = _riders.riders_for_dump(
        dump, jetway_strips, pads, surface, split_idx, tol_m=hard_tol_m,
        authored_ground=(None if _flat is None else _flat.z0_m))
    if riders:
        _ground = {r.index for r in riders if r.seat_why == "on_ground"}
        _have = {m.index for m in msl}
        from ..model.placement import MslSeat as _MslSeat
        msl = tuple(m for m in msl if m.index not in _ground) + tuple(
            _MslSeat(r.index, r.resource, r.lon, r.lat, r.heading_deg,
                     float(r.seat_z), "rider")
            for r in riders if r.seat_why == "msl_written"
            and r.index not in _have and r.seat_z is not None)
        _mi = frozenset(m.index for m in msl)
        conversions = tuple(c for c in _conv0 if c.index not in _mi)
    counts_extra = {"msl_seats": len(msl)}
    counts_extra.update(_msl_counts)
    counts_extra.update(_riders.rider_census(riders))
    counts_extra.update(_fu.multi_anchor_census(dump, rebake_plan, msl,
                                                split_idx, ss.unit_seats))
    files = tuple(f for s in ss.splits for f in s.files)
    counts = dict(ss.counts)
    counts["conversions"] = len(conversions)
    counts.update(counts_extra)
    plan = PlacementPlan(
        icao=icao, pack_name=pack_name, pack_root=pack_root, dsf_path=dsf_path,
        dsf_backup_path=dsf_path + ".anchor_bak",
        provenance=Provenance("", engine_version, law_digest, counts),
        conversions=conversions, splits=splits, kept=kept, msl_seats=msl,
        riders=tuple(riders),
        jetway_strips=tuple(dict(j) for j in (jetway_strips or ())))
    return plan, files, ss


# ── step 2: the cut files ───────────────────────────────────────────────

#: ``CUT_MARK`` (every file this writer makes carries it — ``obj8_split``'s
#: provenance line; it is what says a file on a split's name is OURS to
#: replace) is the model's, re-exported here: ``dsf_write`` reads the same
#: definition and cannot import this module.


def write_files(pack_root: str, files: _t.Sequence, *,
                allow_live_install: bool = False) -> tuple[str, ...]:
    """Write the cut OBJ8s into the pack under their new names.

    REFUSES to overwrite anything that is not itself a cut file of this
    writer (an authored object must never be replaced by a body of
    itself), and refuses a live X-Plane install without the app's own
    ``allow_live_install`` (§3.5: a lane writes a COPY)."""
    if not files:
        return ()
    if _dw.live_install_roots(pack_root) and not allow_live_install:
        raise PermissionError(
            f"REFUSING to write a live X-Plane installation: {pack_root!r} "
            f"(spec §3.5 — a lane writes a COPY of the pack)")
    out: list[str] = []
    for f in files:
        rel = f.resource.replace("\\", "/")
        path = os.path.join(pack_root, *rel.split("/"))
        if os.path.isfile(path):
            with open(path, "r", errors="replace") as fh:
                head = fh.read(4096)
            if CUT_MARK not in head:
                raise ValueError(
                    f"REFUSING to overwrite an authored object with a cut body: "
                    f"{rel!r} (the split names are new names only, §4.5)")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # latin-1 is deliberate (X-Plane reads OBJ8 text as 8-bit); the
        # newline is pinned so Windows does not rewrite the same object
        # with CRLF (lane xplatcrlf, 2026-09-17).
        with open(path, "w", encoding="latin-1", errors="replace",
                  newline="\n") as fh:
            fh.write(f.text)
        out.append(path)
    return tuple(out)


# ── step 0: the restore ─────────────────────────────────────────────────

def restore_pack_objects(pack_root: str, *, allow_live_install: bool = False,
                         dsf_path: str = "", icao: str = "") -> RestoreResult:
    """Put every ``<obj>.anchor_bak`` back over its object (11f (1)).

    ``icao`` (#25): the airport about to be written.  The previous
    write's bodies removed in this step are THAT airport's only — a
    sibling airport served by the same DSF keeps its bodies, which the
    DSF the caller is about to compose still references.  Without it,
    every airport's bodies (the whole-pack restore).

    A BYTE copy of the pristine file, only where the live file differs
    from it (so a second run writes nothing and no mtime moves), and only
    for ``.obj`` — the DSF's own ``<name>.dsf.anchor_bak`` is §3's
    backup, whose discipline ``dsf_write`` owns and which is the SOURCE
    of the dump, never a thing to copy back under it.  The backups
    themselves are kept.

    §12a — THE OBJECT TABLE (rows O1-O7), through
    ``backup_state.classify_object``.  Before it, EVERY backup whose live
    file differed was copied back: a ``.obj`` the user's NEW version of
    the pack had changed was reverted, and one the new version had
    DROPPED was RESURRECTED (``have = b""``).  Now:

    * O2 / O3 — the same bytes: nothing, or one ``utime`` so the next
      build is two stats and reads no file at all;
    * O4 / O5 — ours: the backup goes back, and under the WITNESS-only
      row O5 the live bytes are kept as ``<obj>.unrecognised-<UTC>``
      FIRST, because a witness is not a proof;
    * O6 / O7 — the USER'S file, or a file the new version dropped: the
      stale backup is RETIRED to ``.superseded-<UTC>`` and nothing is
      written over the pack.  The DSF's own ``.dsf.anchor_bak`` is
      retired here too when its live DSF is gone (row D7).

    Refuses a live X-Plane install without the app's explicit
    ``allow_live_install``, exactly as :func:`write_files` does: this
    writes pack files."""
    if _dw.live_install_roots(pack_root) and not allow_live_install:
        raise PermissionError(
            f"REFUSING to restore inside a live X-Plane installation: "
            f"{pack_root!r} (spec §3.5 — a lane writes a COPY of the pack)")
    backups: list[str] = []
    restored: list[str] = []
    adopted: list[str] = []
    unproven: list[str] = []
    for root, _dirs, names in os.walk(pack_root):
        for n in names:
            if not n.endswith(ANCHOR_BAK):
                continue
            live = os.path.join(root, n[: -len(ANCHOR_BAK)])
            bak = os.path.join(root, n)
            if live.lower().endswith(".dsf"):
                # row D7: the new version dropped this tile — retire the
                # backup so no later build dumps it; the DSF's own
                # discipline is ``dsf_write``'s in every other row.
                v = _bs.classify_dsf(live)
                if v.state is _bs.State.LIVE_MISSING:
                    try:
                        adopted.append(_bs.adopt(v))
                    except OSError:
                        pass
                continue
            if not live.lower().endswith(".obj"):
                continue
            backups.append(bak)
            v = _bs.classify_object(live, pack_root)
            if v.state in (_bs.State.REPLACED, _bs.State.LIVE_MISSING):
                # O6 / O7: the pack's own file, or one the new version
                # dropped.  NEVER overwrite, NEVER resurrect.
                try:
                    adopted.append(_bs.adopt(v))
                except OSError:
                    pass
                continue
            if not v.may_write:
                continue                       # O1 / O2: nothing to do
            try:
                if v.witness == "sha256" and v.state is _bs.State.PRISTINE:
                    # O3: the same bytes under a moved mtime — sync it and
                    # the pair is row O2 (two stats, no read) for ever
                    st = os.stat(bak)
                    os.utime(live, ns=(st.st_atime_ns, st.st_mtime_ns))
                    _bs.invalidate_memo()
                    continue
                if v.witness == "y-only":
                    # O5: a witness is not a proof — the bytes survive
                    unproven.append(_bs.preserve_live_copy(v))
                with open(bak, "rb") as fh:
                    want = fh.read()
                with open(live + ".tmp", "wb") as fh:
                    fh.write(want)
                os.replace(live + ".tmp", live)
                st = os.stat(bak)
                os.utime(live, ns=(st.st_atime_ns, st.st_mtime_ns))
                _bs.invalidate_memo()
            except OSError:
                continue
            restored.append(live)
    # 11m: the PREVIOUS write's own body files go too — and ONLY those.
    # ``o4_placement_provenance.json`` beside the DSF names them; a
    # pack with no provenance removes nothing.  Each is confirmed to
    # carry this writer's CUT_MARK before it is unlinked, so a corrupt
    # or hand-edited provenance can never delete an authored object.
    removed: tuple[str, ...] = ()
    if dsf_path:
        removed = _dw.remove_cut_files(
            _dw.written_body_files(pack_root, dsf_path, icao))
    return RestoreResult(tuple(sorted(backups)), tuple(sorted(restored)),
                         removed,
                         tuple(sorted(p for p in adopted if p)),
                         tuple(sorted(p for p in unproven if p)))


# ── steps 0-5: the whole write ──────────────────────────────────────────

def apply_plan(plan: PlacementPlan, files: _t.Sequence, tool: str, *,
               patch_dir: str = "", allow_live_install: bool = False,
               work_dir: str | None = None,
               refresh_dump: _t.Callable[[str], str | None] | None = None,
               engine_version: str = "", law_digest: str = ""
               ) -> PlacementWriteResult:
    """The writes in the one lawful order (module doc, steps 0-5).

    §12a (3) row 5: THE DSF IS CLASSIFIED FIRST.  When its write half
    stands down (rows D2 / D8) nothing at all happens — no restore, no
    cut file, no record — and ``BackupUnproven`` reaches the caller: a
    pack half-written against a DSF we may not touch is torn geometry."""
    v = _bs.classify_dsf(plan.dsf_path)
    if not v.may_write:
        raise _dw.BackupUnproven(_dw._stand_down_line(v))
    restore = restore_pack_objects(plan.pack_root,
                                   allow_live_install=allow_live_install,
                                   dsf_path=plan.dsf_path, icao=plan.icao)
    written = write_files(plan.pack_root, files,
                          allow_live_install=allow_live_install)
    dsf = _dw.write_pack(plan.pack_root, plan, tool,
                         allow_live_install=allow_live_install,
                         work_dir=work_dir, engine_version=engine_version,
                         law_digest=law_digest, body_files=written)
    refreshed = None
    if refresh_dump is not None:
        # §3.6: the READ path keys its text dump on the DSF's mtime, which
        # the move above just changed — refresh it HERE, where the write
        # is known to have happened, never as a read-time side effect
        refreshed = refresh_dump(plan.dsf_path)
    # the restore is PROVENANCE (11f (1)): the plan beside the patch says
    # how many of the pack's objects were put back before it was written
    plan = _dc.replace(plan, provenance=_dc.replace(
        plan.provenance, counts={**dict(plan.provenance.counts), **restore.counts}))
    plan_path = ""
    if patch_dir:
        os.makedirs(patch_dir, exist_ok=True)
        plan_path = os.path.join(patch_dir, PLAN_FILENAME.format(icao=plan.icao))
        with open(plan_path + ".tmp", "w", encoding="utf-8",
                  newline="\n") as fh:
            json.dump(plan.to_dict(), fh, indent=1)
        os.replace(plan_path + ".tmp", plan_path)
    counts = dict(plan.counts())
    counts["files_written"] = len(written)
    counts.update(restore.counts)
    return PlacementWriteResult(plan, plan_path, written, dsf, refreshed, counts,
                                restore)
