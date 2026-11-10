"""THE "HIDE DRAPED POLYGONS" ADJUSTMENTS in the object stage: the pack's
draped photos (issue #1916) and its large draped ground textures (#1962).

Owner (2026-11-06): "when a package includes draped ortho images in the
airport that would obscure our imagery … let the user choose to hide
draped orthos."  (2026-11-08, RULINGS 2026-11-09a (3)) the ground
textures that "primarily cover non-pavement areas" are "an option the
user can choose to hide or not".  Two kinds (:class:`_Kind`), one each:

* :data:`PHOTOS` (row ``drapes``) — the machine-named photo grids
  (``auto_patch_v2.airport.pack_drapes``); checked when asked;
* :data:`GROUND` (row ``ground``) — the ground sheets
  (``auto_patch_v2.airport.pack_ground_sheets``); UNCHECKED when asked,
  never hidden without the user's tick (#1946).

Both are one omission: ``dsf_write.write_pack(drapes=)`` leaves the
definitions and their polygons out of the rewritten DSF, keeps the
pristine DSF as its ``.anchor_bak`` and re-applies the recorded set on
every later write.  The record holds the UNION of what the user chose to
hide; a kind's write or undo changes only its own part (what the other
kind detects stays).  The question is a row of the pack's adjustments
(``adjust_stage``), never a box of its own.

THE TILE'S SCAN (owner RULINGS 2026-11-09a (9), #1960: "we definitely
need to scan every airport pack in every tile"): :func:`scanned` names
every pack on the tile the build asks about, built or not — each airport
pack (a runway of its own) and each companion overlay that lays an
airport's photo grid (#1968: no runway, its apt.dat may hold a heliport).
A companion is judged against its own airports and those of the packs
with a runway it shares the tile with (:func:`_airports`).

The answer is the user's, per pack and kind (``pack_choice``):
"update" (hide them) and "never" are remembered outside the pack.  Undo
(:func:`drape_choice` ``"undo"``) and the pack's Restore originals put
them back.  Nothing here raises into the build.
"""
from __future__ import annotations

import os
import re
import traceback
import typing as _t

from . import pack_choice as _PC
from . import pack_rewrite as _PR
from .pack_choice import relative as _relative

__all__ = ["ACTIONS", "STORE", "PHOTOS", "GROUND", "KINDS", "check_all",
           "scanned", "drape_stage", "drape_choice"]

#: the actions of a drape row of the ``pack_adjust`` command
ACTIONS = ("update", "never", "undo")


class _Kind(_t.NamedTuple):
    """One kind of hideable draped polygon."""

    key: str              # its adjustment row (``pack_adjust`` item)
    store: _PC.Store      # the user's answer per pack
    noun: str             # the log's words


PHOTOS = _Kind("drapes", _PC.Store(_PC.DRAPE_CHOICES), "draped photo")
GROUND = _Kind("ground", _PC.Store(_PC.GROUND_CHOICES), "draped ground texture")
KINDS = (PHOTOS, GROUND)
#: the photos' answers (the name ``adjust_stage`` and older callers read)
STORE = PHOTOS.store


class PackDrapes(_t.NamedTuple):
    """One pack tile DSF's draped polygons of one kind over its airports,
    and the hiding the live file already carries."""

    pack_name: str
    dsf_path: str
    drapes: tuple              # this kind's ``MissingDef`` rows
    hidden: tuple              # the recorded hiding (every kind), () = none
    others: tuple = ()         # the other kinds' rows

    @property
    def keep(self) -> tuple:
        """The recorded hiding that belongs to the other kinds."""
        return tuple(m for m in self.hidden if m in set(self.others))

    @property
    def current(self) -> bool:
        """The live DSF already hides these, and nothing stale."""
        return (bool(self.drapes) and set(self.drapes) <= set(self.hidden)
                and set(self.hidden) <= set(self.drapes) | set(self.others))


def _runway_apt(pack_root: str) -> str:
    """The pack's apt.dat when it declares a land runway (row 100), else
    ``""``."""
    from auto_patch_v2.airport import apt_flatten as _af
    apt = _af.apt_dat_of(pack_root)
    try:
        with open(apt, "rb") as fh:
            if any(line.startswith(b"100 ") for line in fh):
                return apt
    except OSError:
        pass
    return ""


def _apt_dats(pack_root: str, lat: int, lon: int) -> list[str]:
    """The apt.dat the pack's draped polygons are judged against: its own
    when it has a runway, else its own (if any) and every enabled pack's
    with a runway and a DSF on the same tile."""
    from auto_patch_v2.airport import apt_flatten as _af
    if _runway_apt(pack_root):
        return [_af.apt_dat_of(pack_root)]
    own = [_af.apt_dat_of(pack_root)] if _af.apt_dat_of(pack_root) else []
    return own + [a for a in (_runway_apt(p) for p in _tile_packs(pack_root, lat, lon))
                  if a]


def _airports(pack_root: str, lat: int, lon: int
             ) -> tuple[list, list[bool], list[str]]:
    """``(boxes, bounded, apt_paths)``: the airports a pack's draped
    polygons are judged against (``pack_drapes.airport_boxes`` of
    :func:`_apt_dats`), and whether each box is an authored boundary."""
    from auto_patch_v2.airport import pack_drapes as _pd
    apts = _apt_dats(pack_root, lat, lon)
    rows = [r for apt in apts for r in _pd.airport_boxes(apt)]
    return [b for b, _ok in rows], [ok for _b, ok in rows], apts


def _folder_packs(scenery_dir: str, lat: int, lon: int) -> list[str]:
    """The enabled packs of a Custom Scenery folder with a DSF on the
    tile."""
    import O4_Scenery_Packs as _SP
    from auto_patch_v2.airport import dsf as _dsf2
    try:
        names = sorted(_SP.enabled_pack_names(scenery_dir))
    except OSError:
        return []
    return [os.path.join(scenery_dir, n) for n in names
            if os.path.isfile(_dsf2.dsf_path_in_pack(
                os.path.join(scenery_dir, n), lat, lon))]


def _tile_packs(pack_root: str, lat: int, lon: int) -> list[str]:
    """The other enabled packs of the pack's Custom Scenery folder with a
    DSF on the tile."""
    me = os.path.normpath(pack_root)
    return [p for p in _folder_packs(os.path.dirname(me), lat, lon)
            if os.path.normpath(p) != me]


#: the most directory entries :func:`_ships_photo_grid` reads in one pack
_SCAN_ENTRIES = 50_000


def _ships_photo_grid(pack_root: str) -> bool:
    """A cheap look before a DSF dump: the pack ships at least
    ``pack_drape_grid.MIN_TILES`` of its own draped non-wrapping image
    ``.pol`` files (witness (1)-(3))."""
    from auto_patch_v2.airport import pack_drape_grid as _pg
    from auto_patch_v2.airport import pack_drapes as _pd
    found = seen = 0
    for top, dirs, files in os.walk(pack_root):
        dirs[:] = [d for d in dirs if d.lower() != "earth nav data"]
        seen += len(files) + len(dirs)
        for f in files:
            if f.lower().endswith(".pol") and _pd.is_ortho_header(
                    _pd.pol_header(os.path.join(top, f))):
                found += 1
                if found >= _pg.MIN_TILES:
                    return True
        if seen > _SCAN_ENTRIES:
            return False
    return False


def scanned(scenery_dir: str, lat: int, lon: int) -> list[str]:
    """THE TILE'S SCAN (RULINGS 2026-11-09a (9)): the enabled packs of
    ``scenery_dir`` with a DSF on the tile, outside the simulator's
    folders, that are an airport pack (a runway of their own) or a
    companion that may lay an airport's photos (#1968: no runway, ships a
    photo grid's files)."""
    from .post_mesh import _is_protected_scenery_root
    return [p for p in _folder_packs(scenery_dir, lat, lon)
            if not _is_protected_scenery_root(p)
            and (_runway_apt(p) or _ships_photo_grid(p))]


def check_all(pack_root: str, lat: int, lon: int, *,
              read_only: bool) -> dict[str, PackDrapes]:
    """THE CHECK for one pack's tile DSF, one :class:`PackDrapes` per kind
    (``{}`` when there is nothing to judge: ``object_stage.pack_dump``)."""
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import pack_drapes as _pd
    from auto_patch_v2.airport import pack_ground_sheets as _pg
    from auto_patch_v2.airport.file_hash import sha256_file

    from .object_stage import pack_dump

    pd = pack_dump(pack_root, lat, lon, read_only=read_only)
    if pd is None:
        return {}
    areas, bounded, apts = _airports(pack_root, lat, lon)
    found = {PHOTOS.key: _pd.draped_orthos(pack_root, pd.dump_path, areas,
                                           bounded=bounded),
             GROUND.key: _pg.ground_sheets(pack_root, pd.dump_path, apts,
                                           areas)}
    hidden: tuple = ()
    if os.path.isfile(pd.pristine) and pd.pristine != pd.dsf_path:
        entry = _bs.dsf_entry(_bs.read_record(pd.dsf_path),
                              os.path.basename(pd.dsf_path))
        hidden = _pd.recorded(entry, sha256_file(pd.pristine))
    return {k.key: PackDrapes(pd.pack_name, pd.dsf_path, found[k.key], hidden,
                              tuple(m for o, v in found.items() if o != k.key
                                    for m in v))
            for k in KINDS}


def _check(pack_root: str, lat: int, lon: int, *, read_only: bool,
          kind: _Kind = PHOTOS) -> PackDrapes | None:
    """THE CHECK of one kind, or ``None`` when there is nothing to judge."""
    return check_all(pack_root, lat, lon, read_only=read_only).get(kind.key)


def _write(pd: PackDrapes, pack_root: str, drapes: tuple, kind: _Kind) -> None:
    import O4_UI_Utils as UI
    backup = _PR.rewrite_dsf(pack_root, pd.pack_name, pd.dsf_path,
                             drapes=drapes)
    mine = [m for m in drapes if m not in set(pd.others)]
    UI.vprint(0, f"  [pack] {pd.pack_name}: "
                 + (f"{sum(m.uses for m in mine)} {kind.noun} polygon(s) "
                    f"hidden" if mine else f"the {kind.noun}s are back")
                 + f" — rewrote {_relative(pack_root, pd.dsf_path)} (the "
                   f"original is kept as {os.path.basename(backup)})")


def _hide(pd: PackDrapes, pack_root: str, kind: _Kind) -> str:
    """Write the hiding and say so; returns ``"hidden"`` or ``"failed"``."""
    try:
        _write(pd, pack_root, pd.keep + tuple(pd.drapes), kind)
    except Exception as exc:
        import O4_UI_Utils as UI
        UI.vprint(0, f"  [pack] {pd.pack_name}: the {kind.noun}s could not "
                     f"be hidden ({exc}); the pack is as it was")
        UI.vprint(2, traceback.format_exc())
        return "failed"
    return "hidden"


def drape_stage(plan_, tile, *, writes: bool, kind: _Kind = PHOTOS,
                found: dict[str, PackDrapes] | None = None,
                ) -> tuple[str, PackDrapes | None]:
    """The step of ONE kind for ONE pack, ahead of its placement write
    (``found``: :func:`check_all`'s answer, read once for every kind).
    Returns ``(state, check)``: ``""`` (nothing to say), ``"found"`` (the
    adjustments question names it), ``"hidden"``, ``"failed"``,
    ``"never"``, ``"current"``.  Never raises."""
    import O4_UI_Utils as UI
    pack_root = getattr(plan_, "pack_root", "") or ""
    try:
        if found is None:
            found = check_all(pack_root, tile.lat, tile.lon,
                              read_only=not writes)
    except Exception as exc:
        UI.vprint(1, f"  [pack] {kind.noun} check skipped ({exc})")
        UI.vprint(2, traceback.format_exc())
        return "", None
    pd = found.get(kind.key)
    if pd is None or not pd.drapes:
        return "", pd
    UI.vprint(1, f"  [pack] {pd.pack_name}: {len(pd.drapes)} {kind.noun} "
                 f"definition(s) over its airport cover the tile's imagery")
    if pd.current:
        return "current", pd
    choice = kind.store.choice(pack_root)
    if choice == "never":
        return "never", pd
    if writes and choice == "update":
        return _hide(pd, pack_root, kind), pd
    return "found", pd


def drape_choice(pack_root: str, action: str, lat: int | None = None,
                 lon: int | None = None, kind: _Kind = PHOTOS
                 ) -> tuple[str, list[str]]:
    """THE USER'S ANSWER for one kind of the pack's draped polygons (its
    row of ``pack_adjust``): ``"update"`` remembers it and hides them in
    the tile's DSF now, ``"never"`` remembers it, ``"undo"`` forgets the
    answer and puts them back in every DSF of the pack (only the tile's
    with ``lat``/``lon``).  Returns ``(state, files)``; raises on a bad
    action (the caller reports it)."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    if action == "never":
        kind.store.remember(pack_root, "never")
        return "never", []
    if action == "undo":
        kind.store.remember(pack_root, "")
        files = undo(pack_root, lat, lon, kind)
        return ("undone" if files else "none"), files
    kind.store.remember(pack_root, "update")
    pd = _check(pack_root, int(lat or 0), int(lon or 0), read_only=False,
               kind=kind)
    if pd is None or not pd.drapes:
        return "none", []
    if pd.current:
        return "hidden", []
    state = _hide(pd, pack_root, kind)
    return state, ([_relative(pack_root, pd.dsf_path)]
                   if state == "hidden" else [])


_TILE = re.compile(r"^([+-]\d{2})([+-]\d{3})\.dsf$", re.IGNORECASE)


def _kept(pack_root: str, dsf: str, kind: _Kind) -> tuple:
    """The recorded hiding of ``dsf`` that belongs to the other kinds."""
    m = _TILE.match(os.path.basename(dsf))
    if not m:
        return ()
    pd = _check(pack_root, int(m.group(1)), int(m.group(2)), read_only=False,
               kind=kind)
    return pd.keep if pd is not None else ()


def undo(pack_root: str, lat: int | None = None, lon: int | None = None,
         kind: _Kind = PHOTOS) -> list[str]:
    """Put one kind's draped polygons back in the pack's DSFs that hide
    them (what the other kinds hide stays); returns the files rewritten
    (``pack_rewrite.undo_recorded``)."""
    from auto_patch_v2.airport import pack_drapes as _pd
    name = os.path.basename(os.path.normpath(pack_root))
    kept: dict[str, tuple] = {}

    def keep(dsf: str) -> tuple:
        if dsf not in kept:
            kept[dsf] = _kept(pack_root, dsf, kind)
        return kept[dsf]

    return _PR.undo_recorded(
        pack_root, lat, lon, _pd.RECORD_KEY,
        lambda dsf: _write(PackDrapes(name, dsf, (), (), keep(dsf)), pack_root,
                           keep(dsf), kind),
        keeps=lambda dsf: bool(keep(dsf)))
