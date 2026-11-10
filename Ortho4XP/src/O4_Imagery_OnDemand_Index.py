"""The on-demand imagery index: one row per (tile, texture name), what
tier is on disk and when the aircraft was last near it (#1992,
local-imagery-cache spec §5, phase P2).

SQLite (standard library ``sqlite3``, WAL) at
``<data>/Imagery_on_demand/index.sqlite``.  The index is a CACHE of facts
on disk: :func:`rebuild` restores every column from the tiles' textures,
``.ter`` files and imagery manifests, except ``last_near_at`` (set to the
rebuild time, so a lost index downgrades nothing).

COLUMNS (:data:`COLUMNS`, spec §5.1):

* ``tile`` (``+60-136``), ``name`` (the texture's file name), ``zl``,
  ``provider`` -- identity;
* ``centre_lat``, ``centre_lon``, ``load_size_m`` -- the ``.ter``
  ``LOAD_CENTER`` (S, spec §4.3);
* ``state`` -- one of :data:`STATES`: ``low`` (the placeholder),
  ``upgrading`` (a fetch in flight), ``upgraded`` (a finer tier landed),
  ``failed`` (three failed fetches; retried next session);
* ``tier_px`` -- width of the file on disk (512, 1024, 2048, 4096);
* ``core`` -- in an airport core (spec §6.1); ``pinned`` -- in a pinned
  tile (never downgraded, outside the cap);
* ``placeholder_path`` -- the kept placeholder DDS (the store of
  ``O4_Imagery_Placeholder``);
* ``full_bytes`` -- freeable bytes of the upgraded file
  (``O4_Disk_Usage.freeable_bytes``; 0 while ``low``);
* ``dds_cache_key``, ``jpeg_path`` -- what a downgrade frees;
* ``fetched_at``, ``last_near_at``, ``near_count``, ``late_count`` -- the
  LRU and spec §11 U5 (epoch seconds).

API (stable: the follow job, P3b, reads and writes through it):

* :func:`index_path` -- where the index lives under a data root.
* :func:`open_index` -- open (create, migrate) the index; a WAL
  connection with ``sqlite3.Row`` rows.
* :func:`upsert` -- insert or replace one row's columns (a dict).
* :func:`get` / :func:`rows` -- read one row / the rows matching
  ``tile``, ``state``, ``pinned``, ``core``.
* :func:`set_state` -- a state change with the columns it carries
  (``upgrading`` -> ``upgraded`` with ``tier_px``, ``full_bytes``, ...).
* :func:`mark_near` -- ``last_near_at = now`` for names the camera came
  within their tier distance of (at most once a minute per row), and
  ``near_count += 1`` for those that start a new approach.
* :func:`mark_late` -- ``late_count += 1`` (a tier landed after its
  crossing, spec §4.7 R5).
* :func:`set_pinned` / :func:`set_core` -- the per-tile pin, the airport
  core flags.
* :func:`reset_upgrading` -- every ``upgrading`` row back to ``low`` (the
  start of a session, spec §8).
* :func:`capped_bytes` / :func:`pinned_bytes` -- what counts against the
  cap (upgraded, unpinned) and the pins line.
* :func:`lru_order` -- the downgrade order of spec §6.2 (cores last, then
  oldest ``last_near_at``).
* :func:`protected_cache_keys` / :func:`protected_jpegs` -- what the
  ``imagery`` / ``dds`` cache caps must skip (upgraded or pinned rows).
* :func:`scan_tile` -- the rows one tile's build dir implies (headers,
  ``.ter`` S, manifest pin); pure reading, no index.
* :func:`rebuild` -- replace a tile's rows (or every tile's) from
  :func:`scan_tile`, keeping nothing but the rows' facts on disk.

Standard library only (plus the engine's own header readers).
"""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import time

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_Disk_Usage as DISK
import O4_File_Names as FNAMES
import O4_Imagery_Placeholder as PLACEHOLDER

__all__ = [
    "COLUMNS", "INDEX_FILE", "NEAR_WRITE_EVERY_S", "SCHEMA_VERSION",
    "STATES", "capped_bytes", "get", "index_path", "lru_order",
    "mark_late", "mark_near", "open_index", "pinned_bytes",
    "protected_cache_keys", "protected_jpegs", "rebuild",
    "reset_upgrading", "rows", "scan_tile", "set_core", "set_pinned",
    "set_state", "upsert",
]

SCHEMA_VERSION = 1
#: Under ``<data>/Imagery_on_demand/`` (``O4_Imagery_Placeholder.STORE_DIR``).
INDEX_FILE = "index.sqlite"
STATES = ("low", "upgrading", "upgraded", "failed")
#: ``mark_near`` writes a row's ``last_near_at`` at most this often (§5.3).
NEAR_WRITE_EVERY_S = 60.0

#: (column, SQL type, default) in table order.
_SCHEMA = (
    ("tile", "TEXT NOT NULL", None),
    ("name", "TEXT NOT NULL", None),
    ("zl", "INTEGER", 0),
    ("provider", "TEXT", ""),
    ("centre_lat", "REAL", None),
    ("centre_lon", "REAL", None),
    ("load_size_m", "REAL", None),
    ("state", "TEXT NOT NULL", "low"),
    ("tier_px", "INTEGER", 512),
    ("core", "INTEGER", 0),
    ("pinned", "INTEGER", 0),
    ("placeholder_path", "TEXT", None),
    ("full_bytes", "INTEGER", 0),
    ("dds_cache_key", "TEXT", None),
    ("jpeg_path", "TEXT", None),
    ("fetched_at", "REAL", None),
    ("last_near_at", "REAL", None),
    ("near_count", "INTEGER", 0),
    ("late_count", "INTEGER", 0),
)
COLUMNS = tuple(column for (column, _type, _default) in _SCHEMA)
_DEFAULTS = {column: default for (column, _type, default) in _SCHEMA}
_TEXTURES = "textures"
_TERRAIN = "terrain"


def index_path(data_root: "str | None" = None) -> str:
    """The index file under ``data_root`` (default: the engine's data
    root)."""
    folder = (os.path.join(data_root, PLACEHOLDER.STORE_DIR) if data_root
              else FNAMES.data_path(PLACEHOLDER.STORE_DIR))
    return os.path.join(folder, INDEX_FILE)


def open_index(path: "str | None" = None) -> sqlite3.Connection:
    """Open the index at ``path`` (default :func:`index_path`), creating
    its folder and table.  A file of an older schema is dropped and
    recreated: the index is a cache, :func:`rebuild` restores it."""
    path = path or index_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    with contextlib.suppress(sqlite3.DatabaseError):
        conn.execute("PRAGMA journal_mode=WAL")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        conn.execute("DROP TABLE IF EXISTS textures")
    columns = ", ".join(f"{column} {kind}" for (column, kind, _d) in _SCHEMA)
    conn.execute(f"CREATE TABLE IF NOT EXISTS textures ({columns}, "
                 "PRIMARY KEY (tile, name))")
    conn.execute("CREATE INDEX IF NOT EXISTS textures_lru "
                 "ON textures (state, pinned, core, last_near_at)")
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    return conn


def _check(values: dict) -> None:
    unknown = set(values) - set(COLUMNS)
    if unknown:
        raise KeyError(f"not an index column: {sorted(unknown)}")
    if "state" in values and values["state"] not in STATES:
        raise ValueError(f"not an index state: {values['state']!r}")


def upsert(conn: sqlite3.Connection, row: dict) -> None:
    """Insert ``row`` (``tile`` and ``name`` required), or replace the
    columns it names on the existing row; other columns keep their value
    (or take their default on a new row)."""
    _check(row)
    if not row.get("tile") or not row.get("name"):
        raise ValueError("a row needs its tile and name")
    full = {**_DEFAULTS, **row}
    names = ", ".join(COLUMNS)
    marks = ", ".join("?" for _ in COLUMNS)
    updates = ", ".join(f"{c} = excluded.{c}" for c in row
                        if c not in ("tile", "name")) or "tile = tile"
    conn.execute(f"INSERT INTO textures ({names}) VALUES ({marks}) "
                 f"ON CONFLICT (tile, name) DO UPDATE SET {updates}",
                 [full[c] for c in COLUMNS])


def get(conn: sqlite3.Connection, tile: str, name: str) -> "dict | None":
    """The row of ``(tile, name)`` as a dict, or ``None``."""
    found = conn.execute("SELECT * FROM textures WHERE tile = ? AND name = ?",
                         (tile, name)).fetchone()
    return dict(found) if found is not None else None


def rows(conn: sqlite3.Connection, *, tile: "str | None" = None,
         state: "str | None" = None, pinned: "bool | None" = None,
         core: "bool | None" = None) -> "list[dict]":
    """The rows matching every filter given, ordered by tile and name."""
    where, args = [], []
    for column, value in (("tile", tile), ("state", state),
                          ("pinned", pinned), ("core", core)):
        if value is not None:
            where.append(f"{column} = ?")
            args.append(int(value) if isinstance(value, bool) else value)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return [dict(r) for r in conn.execute(
        f"SELECT * FROM textures{clause} ORDER BY tile, name", args)]


def set_state(conn: sqlite3.Connection, tile: str, name: str, state: str,
              **columns) -> bool:
    """Set ``(tile, name)``'s state and the ``columns`` that go with it;
    ``True`` when the row exists."""
    values = {"state": state, **columns}
    _check(values)
    sets = ", ".join(f"{c} = ?" for c in values)
    cursor = conn.execute(
        f"UPDATE textures SET {sets} WHERE tile = ? AND name = ?",
        [*values.values(), tile, name])
    return cursor.rowcount > 0


def mark_near(conn: sqlite3.Connection, tile: str, names, now: float, *,
              approaching=()) -> int:
    """The camera is within tier distance of ``names`` of ``tile``:
    ``last_near_at = now`` where it is older than
    :data:`NEAR_WRITE_EVERY_S`; ``near_count += 1`` for the names in
    ``approaching`` (the first sample of an approach).  Returns the rows
    written."""
    written = 0
    with conn:
        for name in names:
            cursor = conn.execute(
                "UPDATE textures SET last_near_at = ? WHERE tile = ? AND "
                "name = ? AND (last_near_at IS NULL OR last_near_at <= ?)",
                (now, tile, name, now - NEAR_WRITE_EVERY_S))
            written += cursor.rowcount
        for name in approaching:
            conn.execute("UPDATE textures SET near_count = near_count + 1 "
                         "WHERE tile = ? AND name = ?", (tile, name))
    return written


def mark_late(conn: sqlite3.Connection, tile: str, name: str) -> None:
    """One tier of ``(tile, name)`` landed after its crossing."""
    conn.execute("UPDATE textures SET late_count = late_count + 1 "
                 "WHERE tile = ? AND name = ?", (tile, name))


def set_pinned(conn: sqlite3.Connection, tile: str, pinned: bool) -> int:
    """Pin (or unpin) every row of ``tile``; returns the rows changed."""
    return conn.execute("UPDATE textures SET pinned = ? WHERE tile = ?",
                        (int(bool(pinned)), tile)).rowcount


def set_core(conn: sqlite3.Connection, tile: str, names) -> int:
    """``tile``'s airport core is exactly ``names``: those rows get
    ``core = 1``, the tile's others ``core = 0``.  Returns the core rows."""
    wanted = set(names)
    count = 0
    with conn:
        for row in conn.execute("SELECT name, core FROM textures "
                                "WHERE tile = ?", (tile,)).fetchall():
            flag = int(row["name"] in wanted)
            count += flag
            if flag != row["core"]:
                conn.execute("UPDATE textures SET core = ? WHERE tile = ? "
                             "AND name = ?", (flag, tile, row["name"]))
    return count


def reset_upgrading(conn: sqlite3.Connection) -> int:
    """Every ``upgrading`` row back to ``low`` (an interrupted fetch never
    landed: its partial is swept, the old file still stands)."""
    return conn.execute("UPDATE textures SET state = 'low' "
                        "WHERE state = 'upgrading'").rowcount


def capped_bytes(conn: sqlite3.Connection) -> int:
    """Freeable bytes counted against the cap: upgraded, unpinned rows."""
    return int(conn.execute(
        "SELECT COALESCE(SUM(full_bytes), 0) FROM textures "
        "WHERE state = 'upgraded' AND pinned = 0").fetchone()[0])


def pinned_bytes(conn: sqlite3.Connection) -> int:
    """Bytes of the pinned tiles' upgraded textures (outside the cap)."""
    return int(conn.execute(
        "SELECT COALESCE(SUM(full_bytes), 0) FROM textures "
        "WHERE state = 'upgraded' AND pinned = 1").fetchone()[0])


def lru_order(conn: sqlite3.Connection) -> "list[dict]":
    """Upgraded, unpinned rows in downgrade order: non-core first, then
    oldest ``last_near_at`` (never-near first)."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM textures WHERE state = 'upgraded' AND pinned = 0 "
        "ORDER BY core, COALESCE(last_near_at, 0), tile, name")]


def protected_cache_keys(conn: sqlite3.Connection) -> "set[str]":
    """``DDS_cache`` keys of upgraded or pinned rows: the ``dds`` cap's
    LRU must keep them (spec §6.3)."""
    return {r[0] for r in conn.execute(
        "SELECT dds_cache_key FROM textures WHERE dds_cache_key IS NOT NULL "
        "AND (state = 'upgraded' OR pinned = 1)")}


def protected_jpegs(conn: sqlite3.Connection) -> "set[str]":
    """Tier JPEG paths of upgraded or pinned rows: the ``imagery`` cap's
    LRU must keep them (spec §6.3)."""
    return {os.path.normcase(os.path.abspath(r[0])) for r in conn.execute(
        "SELECT jpeg_path FROM textures WHERE jpeg_path IS NOT NULL "
        "AND (state = 'upgraded' OR pinned = 1)")}


# ---------------------------------------------------------------- rebuild


def _read_ter(path: str) -> "tuple[str, float, float, float] | None":
    """``(texture name, centre lat, centre lon, S)`` of one ``.ter``."""
    centre, texture = None, None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                words = line.split()
                if len(words) >= 4 and words[0] == "LOAD_CENTER":
                    centre = (float(words[1]), float(words[2]),
                              float(words[3]))
                elif len(words) >= 2 and words[0] in ("BASE_TEX_NOWRAP",
                                                      "BASE_TEX"):
                    texture = os.path.basename(words[1].replace("\\", "/"))
    except (OSError, ValueError):
        return None
    if centre is None or not texture or not texture.endswith(".dds"):
        return None
    return (texture, *centre)


def _identity(name: str) -> "tuple[int, str]":
    """``(zl, provider)`` from ``<til_y>_<til_x>_<provider><zl>.dds``: the
    zoom is the trailing two digits when they read as a zoom (11-20),
    else one."""
    stem = name[:-4].split("_", 2)[-1]
    for digits in (2, 1):
        text, provider = stem[-digits:], stem[:-digits]
        if provider and text.isdigit() and (digits == 1 or
                                            10 <= int(text) <= 20):
            return int(text), provider
    return 0, stem


def _manifest(build_dir: str, tile: str) -> dict:
    """The tile's imagery manifest (``O4_Tile_Utils.imagery_manifest_path``
    names it from a tile object; the index has only the folder)."""
    path = os.path.join(build_dir, f"Ortho4XP_{tile}_imagery.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def scan_tile(build_dir: str, lat: int, lon: int, *,
              placeholder_dir: "str | None" = None,
              cache_keys: "dict | None" = None, now: "float | None" = None
              ) -> "list[dict]":
    """The rows tile ``(lat, lon)``'s build dir implies: one per texture a
    ``.ter`` names and ``textures/`` holds whole; ``tier_px`` from its
    header, ``low`` when that equals the placeholder width, else
    ``upgraded`` with its freeable bytes; ``pinned`` from the imagery
    manifest; ``placeholder_path`` when ``placeholder_dir`` holds it;
    ``dds_cache_key`` from ``cache_keys`` (name -> key); ``last_near_at``
    and ``fetched_at`` = ``now``.  Never raises on a missing folder."""
    tile = FNAMES.short_latlon(lat, lon)
    now = time.time() if now is None else now
    manifest = _manifest(build_dir, tile)
    pinned = int(bool(manifest.get("pinned")))
    low_zl = manifest.get("placeholder_zl")
    found = {}
    with contextlib.suppress(OSError):
        for item in os.scandir(os.path.join(build_dir, _TERRAIN)):
            if item.name.endswith(".ter"):
                facts = _read_ter(item.path)
                if facts is not None:
                    found.setdefault(facts[0], facts[1:])
    result = []
    for name, (centre_lat, centre_lon, size) in sorted(found.items()):
        path = os.path.join(build_dir, _TEXTURES, name)
        header = TIERS.texture_header(path)
        if header is None or not DDS.is_whole(path):
            continue
        zl, provider = _identity(name)
        drop = (zl - int(low_zl)) if low_zl else 3
        low_px = TIERS.tier_width(drop) if drop in TIERS.TIER_DROPS else 512
        kept = (os.path.join(placeholder_dir, name) if placeholder_dir
                else None)
        upgraded = header[0] > low_px
        result.append({
            "tile": tile, "name": name, "zl": zl, "provider": provider,
            "centre_lat": centre_lat, "centre_lon": centre_lon,
            "load_size_m": size,
            "state": "upgraded" if upgraded else "low",
            "tier_px": header[0], "core": 0, "pinned": pinned,
            "placeholder_path": kept if kept and os.path.isfile(kept)
            else None,
            "full_bytes": DISK.freeable_bytes(path) if upgraded else 0,
            "dds_cache_key": (cache_keys or {}).get(name),
            "jpeg_path": None, "fetched_at": now, "last_near_at": now,
            "near_count": 0, "late_count": 0,
        })
    return result


def rebuild(conn: sqlite3.Connection, tiles, *, now: "float | None" = None,
            placeholder_root: "str | None" = None, cache_keys=None) -> int:
    """Replace the rows of each ``(build_dir, lat, lon)`` in ``tiles`` by
    :func:`scan_tile`'s; a tile's ``core`` flags survive (they come from
    its airports, not its files: :func:`set_core`).  ``placeholder_root``
    is the store's ``placeholders`` folder; ``cache_keys`` a callable
    ``build_dir -> {name: key}``.  Returns the rows written."""
    now = time.time() if now is None else now
    written = 0
    for build_dir, lat, lon in tiles:
        tile = FNAMES.short_latlon(lat, lon)
        cores = {r["name"] for r in rows(conn, tile=tile, core=True)}
        keep_dir = (os.path.join(placeholder_root, tile)
                    if placeholder_root else None)
        keys = cache_keys(build_dir) if cache_keys else None
        found = scan_tile(build_dir, lat, lon, placeholder_dir=keep_dir,
                          cache_keys=keys, now=now)
        with conn:
            conn.execute("DELETE FROM textures WHERE tile = ?", (tile,))
            for row in found:
                row["core"] = int(row["name"] in cores)
                upsert(conn, row)
        written += len(found)
    return written
