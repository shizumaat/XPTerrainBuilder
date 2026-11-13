"""A flight's departure or destination on an adopted tile, or another
tool's (#2025, owner 2026-11-12T19:42Z):

    "If I plan a flight departing or arriving at these types of tiles I
    want the app to ask the user if they want to use the old mesh or
    upgrade the tile before flying it."

* :func:`endpoint_reader` -- ``info(tile)`` for an endpoint whose World
  pack tile is a mesh (``world_state.FULL`` or ``MESH_LOWRES``) that this app did not build (origin
  ``O4_Tile_Info.ORIGIN_ADOPTED`` or ``ORIGIN_OTHER``): ``{"origin",
  "built_by", "patched"}``; None for any other tile.
* :func:`airport_patched_reader` -- was the tile, or
  the endpoint's airport, patched in the tool that built it: ``yes`` /
  ``no`` / ``unknown`` (``ortho4xp_patched``: the source's Ortho4XP
  install, a cfg / log naming a patch, or the build's own airport and
  runway data in the tile's folder).
* :class:`ChoiceBook` -- the pilot's answer per tile (``keep``: fly the
  existing mesh; ``upgrade``: a ``full`` build of ours replaces it in the
  pack, the adopted package kept for Undo by the Convert journal),
  remembered in the data folder (:data:`CHOICES_FILE`) and applied to
  later flights without asking; with it, each endpoint airport's
  ``patched`` once read ``yes`` / ``no`` (the source's drive need not
  stay mounted).
* :class:`Endpoints` -- one flight's view of them: each tile read once,
  its answer (``ask`` while none), the pilot's answer checked and
  remembered, and the ``FlightStatus.choices`` rows (:func:`choice_row`).

No tile, airport or install is named here.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Dict, Optional, Tuple

import O4_DSF_Header as DSFH
import O4_File_Names as FNAMES
import O4_Tile_Info as TINFO
import O4_World_Pack as WP

from . import ortho4xp_patched as PATCHED
from .ortho4xp_patched import PATCHED_NO, PATCHED_UNKNOWN, PATCHED_YES
from .world_state import FULL, MESH_LOWRES, journal_record, read_tile

__all__ = ["KEEP", "UPGRADE", "CHOICES", "ASK", "PATCHED_YES",
           "PATCHED_NO", "PATCHED_UNKNOWN", "CHOICES_FILE", "endpoint_reader",
           "airport_patched_reader",
           "ChoiceBook", "choices_path", "parse_tile", "Endpoints"]

Tile = Tuple[int, int]

KEEP = "keep"
UPGRADE = "upgrade"
CHOICES = (KEEP, UPGRADE)
#: An adopted endpoint with no answer yet: the flight asks.
ASK = "ask"
#: The remembered answers, in the data folder.
CHOICES_FILE = "adopted_tile_choices.json"
_MESH_STATES = (FULL, MESH_LOWRES)
_NOT_OURS = (TINFO.ORIGIN_ADOPTED, TINFO.ORIGIN_OTHER)


def _source_dirs(record: Optional[dict]) -> list:
    """The tile's own folders a journal record names (where it came from
    first, then where its files are now)."""
    record = record or {}
    return [p for p in (record.get("source"), record.get("link_target"),
                        record.get("original"), record.get("config_dir"))
            if isinstance(p, str) and p]


def _patched(record: Optional[dict], lat: int, lon: int, icao: str = "") -> str:
    """Was the tile (its airport ``icao``, when given) patched in the tool
    that built it: ``yes`` / ``no`` / ``unknown``, read from the folders
    its journal ``record`` names (``ortho4xp_patched.patched``)."""
    return PATCHED.patched(_source_dirs(record), lat, lon, icao)


def airport_patched_reader(scenery_dir: str) -> Callable[[Tile, str], str]:
    """``patched_of(tile, icao)``: :func:`patched` for an endpoint's
    airport, from the tile's Convert journal record; never raises."""
    def patched_of(tile, icao: str) -> str:
        try:
            tile = (int(tile[0]), int(tile[1]))
            return _patched(journal_record(scenery_dir, tile), *tile, icao)
        except Exception:                   # unread: the words say unknown
            return PATCHED_UNKNOWN
    return patched_of


def _built_by(scenery_dir: str, tile: Tile) -> str:
    """The tool the DSF names (its ``sim/creation_agent``'s first word),
    or ``""``."""
    from . import world_commands as WORLD
    path = os.path.join(WORLD.pack_dir(scenery_dir), WP.dsf_relpath(*tile))
    agent = (DSFH.dsf_properties(path) or {}).get("sim/creation_agent", "")
    words = agent.split()
    return words[0] if words and not words[0].startswith("[") else ""


def endpoint_reader(scenery_dir: str,
                    build_dir_of: Optional[Callable[[int, int], str]] = None
                    ) -> Callable[[Tile], Optional[dict]]:
    """``info(tile)`` (see the module), with ``upgrade_ok`` False when
    our build folder for the tile (``build_dir_of``) is the adopted
    package's own (:func:`upgrade_overwrites`); never raises."""
    def info(tile) -> Optional[dict]:
        tile = (int(tile[0]), int(tile[1]))
        try:
            state = read_tile(scenery_dir, tile)
            if (state is None or state.state not in _MESH_STATES
                    or state.origin not in _NOT_OURS):
                return None
            record = journal_record(scenery_dir, tile)
            build_dir = build_dir_of(*tile) if build_dir_of else ""
            return {"origin": state.origin,
                    "built_by": _built_by(scenery_dir, tile),
                    "patched": _patched(record, *tile),
                    "upgrade_ok": not upgrade_overwrites(build_dir, record)}
        except Exception:                   # unread: the flight does not ask
            return None
    return info


def upgrade_overwrites(build_dir: str, record: Optional[dict]) -> bool:
    """Would a build of ours in ``build_dir`` write over the adopted
    package (the folder carries the adopted stamp, or is one the journal
    names as the tile's own)?  Then the upgrade is refused: Undo needs it."""
    if not build_dir:
        return False
    if TINFO.adopted_record(build_dir):
        return True
    here = os.path.normcase(os.path.realpath(build_dir))
    return any(os.path.normcase(os.path.realpath(p)) == here
               for p in _source_dirs(record))


def choices_path(data_root: Optional[str] = None) -> str:
    """``<data folder>/adopted_tile_choices.json``."""
    return os.path.join(data_root or FNAMES.current_data_root(), CHOICES_FILE)


class ChoiceBook:
    """The remembered answers ``{tile name: {"choice", "at"}}``; ``path``
    None keeps them in memory only."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._rows: Dict[str, dict] = {}
        if path:
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self._rows = data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                self._rows = {}

    def _row(self, tile) -> dict:
        row = self._rows.get(WP.tile_name(int(tile[0]), int(tile[1])))
        return row if isinstance(row, dict) else {}

    def get(self, tile) -> Optional[str]:
        choice = self._row(tile).get("choice")
        return choice if choice in CHOICES else None

    def set(self, tile, choice: str) -> None:
        if choice not in CHOICES:
            raise ValueError("Choose %s or %s." % CHOICES)
        self._update(tile, {"choice": choice, "at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

    def patched(self, tile, icao: str) -> Optional[str]:
        """The airport's remembered ``patched`` (``yes`` / ``no``), or None."""
        seen = self._row(tile).get("patched")
        value = seen.get(icao.upper()) if isinstance(seen, dict) else None
        return value if value in (PATCHED_YES, PATCHED_NO) else None

    def set_patched(self, tile, icao: str, value: str) -> None:
        """Remember a ``yes`` / ``no`` read; ``unknown`` is read again."""
        if value not in (PATCHED_YES, PATCHED_NO) or not icao:
            return
        seen = dict(self._row(tile).get("patched") or {})
        seen[icao.upper()] = value
        self._update(tile, {"patched": seen})

    def _update(self, tile, fields: dict) -> None:
        name = WP.tile_name(int(tile[0]), int(tile[1]))
        with self._lock:
            row = dict(self._rows.get(name) or {})
            row.update(fields)
            self._rows[name] = row
            if self.path:
                os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                partial = self.path + ".partial"
                with open(partial, "w", encoding="utf-8", newline="\n") as fh:
                    json.dump(self._rows, fh, indent=1, sort_keys=True)
                os.replace(partial, self.path)


def parse_tile(tile) -> Tile:
    """``[lat, lon]`` or a tile name (``+53-061``) as ``(lat, lon)``."""
    if isinstance(tile, str):
        return WP.parse_tile(tile)
    try:
        return int(tile[0]), int(tile[1])
    except (TypeError, ValueError, IndexError) as error:
        raise ValueError("Name the tile: [lat, lon] or +53-061.") from error


def choice_row(tile: Tile, role: str, icao: str, info: dict,
               choice: Optional[str], estimate_s: Optional[float]) -> dict:
    """One ``FlightStatus.choices`` row: ``tile`` ``[lat, lon]``, ``role``,
    ``icao``, ``origin``, ``built_by``, ``patched``, ``upgrade_estimate_s``
    (the upgrade's high estimate; None unknown) and ``choice`` (``""``
    while unanswered)."""
    return {"tile": [int(tile[0]), int(tile[1])], "role": role,
            "icao": icao or "", "origin": info.get("origin", ""),
            "built_by": info.get("built_by", ""),
            "patched": info.get("patched", PATCHED_UNKNOWN),
            "upgrade_estimate_s": (None if estimate_s is None
                                   else round(float(estimate_s), 1)),
            "choice": choice or ""}


class Endpoints:
    """One flight's adopted endpoints (the module docstring): ``info``
    (:func:`endpoint_reader`'s callable) read once per tile, answers in
    ``book`` (a :class:`ChoiceBook`; in memory when None); ``patched_of``
    (:func:`airport_patched_reader`) reads an endpoint airport's
    ``patched`` once, over the tile's own in ``info``."""

    def __init__(self, info: Callable[[Tile], Optional[dict]],
                 book: Optional[ChoiceBook] = None,
                 patched_of: Optional[Callable[[Tile, str], str]] = None
                 ) -> None:
        self._read = info
        self.book = book if book is not None else ChoiceBook()
        self._patched_of = patched_of
        self._info: Dict[Tile, Optional[dict]] = {}
        self._upgrade_s: Dict[Tile, Optional[float]] = {}
        self._patched: Dict[Tuple[Tile, str], str] = {}

    def info(self, tile) -> Optional[dict]:
        tile = (int(tile[0]), int(tile[1]))
        if tile not in self._info:
            self._info[tile] = self._read(tile)
        return self._info[tile]

    def choice_of(self, tile) -> Optional[str]:
        """:data:`ASK`, :data:`KEEP` or :data:`UPGRADE` for an adopted
        mesh, None for any other tile; a remembered upgrade that would
        write over the adopted package is asked again."""
        info = self.info(tile)
        if info is None:
            return None
        choice = self.book.get(tile)
        if choice == UPGRADE and info.get("upgrade_ok") is False:
            return ASK
        return choice or ASK

    def remember(self, tile, role: str, choice: str) -> None:
        """The pilot's answer for an endpoint (``role``) of the flight;
        raises ValueError with the sentence to show when it cannot be."""
        if role not in ("departure", "destination") or self.info(tile) is None:
            raise ValueError("That tile is not an adopted departure or "
                             "destination of this flight.")
        if choice not in CHOICES:
            raise ValueError("Choose keep or upgrade.")
        if choice == UPGRADE and self.info(tile).get("upgrade_ok") is False:
            raise ValueError("This tile's own folder is where XPTerrainBuilder "
                             "would build it: an upgrade would write over it. "
                             "Fly the existing mesh, or Convert it first.")
        self.book.set(tile, choice)

    def _estimate(self, tile, role: str, estimate) -> Optional[float]:
        if tile not in self._upgrade_s:
            try:
                self._upgrade_s[tile] = float(estimate(tile, "full", role)[1])
            except Exception:               # no figure: the words say so
                self._upgrade_s[tile] = None
        return self._upgrade_s[tile]

    def patched(self, tile, icao: str, info: dict) -> str:
        """The endpoint airport's ``patched``: remembered, else read once
        (``patched_of``) and remembered when ``yes`` / ``no``, else the
        tile's own (``info``)."""
        tile = (int(tile[0]), int(tile[1]))
        key = (tile, (icao or "").upper())
        if key not in self._patched:
            value = self.book.patched(tile, key[1]) if key[1] else None
            if value is None and key[1] and self._patched_of is not None:
                value = self._patched_of(tile, key[1])
                try:
                    self.book.set_patched(tile, key[1], value)
                except OSError:             # read again next flight
                    pass
            if value not in (PATCHED_YES, PATCHED_NO):
                value = info.get("patched", PATCHED_UNKNOWN)
            self._patched[key] = value
        return self._patched[key]

    def rows(self, jobs, plan, estimate) -> Tuple[dict, ...]:
        """``FlightStatus.choices``: one row per adopted endpoint among
        ``jobs`` (``O4_Flight_Schedule.Job``); ``estimate(tile, kind,
        role)`` gives the upgrade's seconds (its high end)."""
        rows = []
        for job in jobs:
            if job.role not in ("departure", "destination"):
                continue
            info = self.info(job.tile)
            if info is None:
                continue
            point = (plan.waypoints[0] if job.role == "departure"
                     else plan.waypoints[-1])
            choice = self.choice_of(job.tile)
            info = dict(info, patched=self.patched(job.tile, point.ident,
                                                   info))
            rows.append(choice_row(
                job.tile, job.role, point.ident, info,
                "" if choice == ASK else choice,
                self._estimate(job.tile, job.role, estimate)))
        return tuple(rows)
