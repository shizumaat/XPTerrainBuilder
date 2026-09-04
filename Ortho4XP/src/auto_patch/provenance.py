"""Patch provenance — the single source of truth for "how was this patch built".

After a bake nobody should have to run forensics to learn whether a patch was
produced by the current code, with which gate configuration, and on which
elevation surface.  This module assembles that provenance and renders it three
ways from ONE computed record:

1.  As tags on the ``<osm>`` root element that ``PavementLayout.to_osm`` writes
    (``provenance_tags``).  They ride on the root exactly like the existing
    ``o4_apt_dat`` / ``o4_apt_dat_mtime`` stamp, so they perturb no geometry:
    the mesher's patch reader (``O4_Vector_Map.include_patches`` via
    ``O4_OSM_Utils.OSM_layer``) and the chain-divergence audit both parse only
    ``<node>`` / ``<way>`` elements and never look at root attributes.

2.  As a one-line human summary logged at default verbosity, one per airport,
    at patch completion (``format_log_line``).  The no-inset case reads as a
    warning — that is the silent-raw-DEM incident this feature exists to catch.

3.  Read back and printed by ``tools/patch_provenance.py`` (via the ``parse_*``
    helpers), which is a seconds-fast, no-build reader for humans and CI.

Three provenance facets are captured:

* **Source tree** — the git commit sha of the tree at build time and a
  dirty-tree flag (``git_provenance``).  Gracefully absent outside a checkout;
  provenance never crashes a build.
* **Gate configuration** — every ``O4_`` gate defined in :mod:`auto_patch.config`
  is enumerated by introspecting that module's source (``gate_provenance``), so
  the list cannot rot as gates are added or removed.  The record names which
  boolean gates are ON and, separately, every gate whose live value differs
  from its in-source default (the actionable "someone flipped a gate" signal).
* **Elevation provenance** — which airport-elevation insets actually baked into
  the DEM this patch was graded on, read from the inset provenance sidecars the
  ``O4_Airport_Elevation_Insets`` cache writes (provider, source_ids,
  fetch_date).  When no inset baked, the record says so LOUDLY.

The elevation facet is honest about the standalone-vs-production split: the
inset list is stamped onto the DEM object by ``bake_airport_insets_into_alt_dem``
at the moment it bakes, and read back here from that same object — so a
standalone build (which loads the raw base tile and never bakes) correctly
reports RAW even when an inset is sitting in the cache.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import re
import subprocess
import urllib.parse


# Master gate for the whole feature.  ON by default (provenance should be on
# for every production build); set ``O4_PATCH_PROVENANCE=0`` to suppress the
# stamp + log line (used for the byte/audit A/B comparison).
def provenance_enabled() -> bool:
    """True when patch provenance stamping + logging is active (default ON)."""
    return os.environ.get("O4_PATCH_PROVENANCE", "1") == "1"


# ──────────────────────────────────────────────────────────────────────────────
# Facet 1 — source tree (git)
# ──────────────────────────────────────────────────────────────────────────────
def git_provenance(cwd: str | None = None) -> dict:
    """Return ``{"sha": str | None, "dirty": bool | None}`` for the source tree.

    ``sha`` is the short commit hash of ``HEAD``; ``dirty`` is True when the
    working tree has uncommitted changes (tracked or untracked).  Both are
    ``None`` outside a git checkout or when git is unavailable — provenance must
    never crash a build, so every failure mode is swallowed to a graceful
    absent value.
    """
    if cwd is None:
        # The auto_patch package lives inside the source checkout; resolve git
        # relative to it, not the process cwd (a build may run from anywhere).
        cwd = os.path.dirname(os.path.abspath(__file__))
    sha: str | None = None
    dirty: bool | None = None
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip() or None
    except Exception:
        return {"sha": None, "dirty": None}
    if sha is None:
        # Not a checkout (or detached with no commit): report absent, and do
        # not claim a dirty state we cannot determine.
        return {"sha": None, "dirty": None}
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        dirty = bool(status.stdout.strip())
    except Exception:
        dirty = None
    return {"sha": sha, "dirty": dirty}


# ──────────────────────────────────────────────────────────────────────────────
# Facet 2 — gate configuration (config.py introspection)
# ──────────────────────────────────────────────────────────────────────────────
# Matches ``environ.get("O4_NAME", "default")`` regardless of the os alias
# (``_os`` / ``_os_early``) or an enclosing ``int(...)`` / ``float(...)`` cast.
# Only two-argument calls with a STRING default are captured; a bare
# ``environ.get("O4_X")`` (default None) is intentionally skipped.
_ENV_GATE_RE = re.compile(
    r"""environ\.get\(\s*["'](O4_[A-Za-z0-9_]+)["']\s*,\s*["']([^"']*)["']"""
)


def _config_source_path() -> str | None:
    """Absolute path to the ``auto_patch.config`` source file, or None."""
    try:
        from . import config as _config

        return os.path.abspath(_config.__file__)
    except Exception:
        return None


# Parsed ``{gate_name: default}`` per config source, memoised on the source
# file's (mtime, size).  Only the SOURCE parse is cached — the live env value
# is re-read on every call, so a gate flipped mid-process is still seen.  The
# freshness gate calls this once per airport per tile build; without the memo
# that is one full re-read + regex sweep of config.py (~130 KB) per airport.
_GATE_DEFAULTS_CACHE: dict = {}


def _gate_defaults(source_path: str) -> dict:
    """``{gate_name: in-source default}`` for a config source, memoised."""
    try:
        stat = os.stat(source_path)
        key = (source_path, stat.st_mtime, stat.st_size)
    except OSError:
        return {}
    cached = _GATE_DEFAULTS_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        with open(source_path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return {}
    defaults: dict = {}
    for match in _ENV_GATE_RE.finditer(text):
        # A gate can be referenced more than once; keep the first default seen
        # (they agree in practice) but never overwrite with a later duplicate.
        defaults.setdefault(match.group(1), match.group(2))
    _GATE_DEFAULTS_CACHE.clear()          # one source per process in practice
    _GATE_DEFAULTS_CACHE[key] = defaults
    return defaults


def introspect_config_gates(source_path: str | None = None) -> dict:
    """Enumerate every ``O4_`` env gate declared in ``config.py``.

    Reads the config module's SOURCE (not a hand-maintained list) so the gate
    inventory tracks the code automatically.  Returns
    ``{name: {"default": str, "value": str, "is_boolean": bool}}`` where
    ``value`` is the live ``os.environ`` value falling back to the in-source
    default, and ``is_boolean`` marks gates whose default is ``"0"`` / ``"1"``.
    Returns an empty dict when the source cannot be read.
    """
    if source_path is None:
        source_path = _config_source_path()
    if not source_path or not os.path.isfile(source_path):
        return {}
    gates: dict = {}
    for name, default in _gate_defaults(source_path).items():
        gates[name] = {
            "default": default,
            "value": os.environ.get(name, default),
            "is_boolean": default in ("0", "1"),
        }
    return gates


def gate_provenance(source_path: str | None = None) -> dict:
    """Compute the active gate configuration from config introspection.

    Returns ``{"on": [names], "nondefault": [(name, value)], "total": int}``:

    * ``on`` — boolean gates whose live value is ``"1"`` (the active feature
      set), sorted.
    * ``nondefault`` — every gate (boolean or not) whose live value differs
      from its in-source default, as ``(name, value)`` pairs, sorted.  This is
      the actionable drift signal: a build that silently ran with a gate
      flipped shows here.
    * ``total`` — how many gates were enumerated (0 signals introspection
      failed, so a reader can distinguish "no gates on" from "could not read").
    """
    gates = introspect_config_gates(source_path)
    on = sorted(
        name
        for name, info in gates.items()
        if info["is_boolean"] and info["value"] == "1"
    )
    nondefault = sorted(
        (name, info["value"])
        for name, info in gates.items()
        if info["value"] != info["default"]
    )
    return {"on": on, "nondefault": nondefault, "total": len(gates)}


# ──────────────────────────────────────────────────────────────────────────────
# Facet 3 — elevation / inset provenance
# ──────────────────────────────────────────────────────────────────────────────
# Attribute name under which ``bake_airport_insets_into_alt_dem`` records the
# insets it baked onto the DEM object.  A list of per-inset dicts (possibly
# empty); ABSENT entirely when no bake step ran on this DEM (the standalone
# raw-load path), which reads as RAW.
DEM_INSET_PROVENANCE_ATTR = "airport_inset_provenance"

# Attribute name under which ``O4_Airport_Elevation_Insets._overlay_flat_site_
# insets`` records the SYNTHETIC CONSTANT INSETS it blended in (FLAT-SITE mode,
# docs/specs/flat-site-mode-spec.md section 2.3).  A list of per-airport dicts;
# ABSENT when the mode never fired.  A flat-mode patch and a real-DEM patch are
# DIFFERENT FRAMES, so this travels with the inset record and never inside it.
DEM_SYNTHETIC_FLAT_SITE_ATTR = "synthetic_flat_site_provenance"

# Attribute name under which the same bake records the insets it REFUSED for
# holding (almost) no valid pixels — R11-3, docs/specs/round11-kmci-flat-claim-
# spec.md.  These never touched the raster, so they stay OUT of the inset list
# and out of ``raw``: the patch WAS graded on the base DEM and must say so.
DEM_INSET_NODATA_REFUSAL_ATTR = "airport_inset_nodata_refusals"


def dem_provenance_from_dem(dem_obj, icao: str | None = None) -> dict:
    """Read elevation provenance off the DEM object the solve graded against.

    Returns ``{"insets": [ {provider, source_ids, fetch_date, ...}, ... ],
    "raw": bool, "synthetic_flat_site": entry | None}``, plus
    ``"nodata_refused": [ {..., nodata_fraction, fallback}, ... ]`` when — and
    only when — an inset was refused for holding no data (R11-3).  The key is
    absent otherwise, so a record with nothing to report is the record every
    existing reader already knows.  ``raw`` is True when no inset baked into
    this DEM — either the bake step never ran (standalone raw-load path: the
    attribute is absent) or it ran and baked nothing (empty list).  Either way
    the patch was graded on the base DEM, which the log/stamp must announce
    loudly.

    ``raw`` keeps its meaning — it is about FETCHED insets.  A synthetic
    flat-site surface is not an inset of anything and is reported on its own
    key: Z0, the detector's evidence record and the extent it covers.  So is a
    raster that was FETCHED and held no data: it is not an inset either, it is
    the reason the base DEM is what graded this airport, and ``raw`` stays
    True beside it.

    A production ``tile.dem`` is shared by every airport on the tile and carries
    all their baked insets; ``icao`` filters the record to the insets fetched
    for THIS airport (matched on the ICAO the bake parsed from the cache file
    name).  Entries with no ICAO field, or when ``icao`` is None, are kept.
    """
    synthetic = _synthetic_flat_site_from_dem(dem_obj, icao=icao)
    refused = _entries_for_icao(
        getattr(dem_obj, DEM_INSET_NODATA_REFUSAL_ATTR, None), icao)
    insets = getattr(dem_obj, DEM_INSET_PROVENANCE_ATTR, None)
    normalised = _entries_for_icao(insets, icao) if insets else []
    out = {"insets": normalised, "raw": len(normalised) == 0,
           "synthetic_flat_site": synthetic}
    if refused:
        out["nodata_refused"] = refused
    return out


def _entries_for_icao(entries, icao: str | None) -> list:
    """The dict entries of a per-DEM record belonging to ``icao`` (all of
    them when ``icao`` is None or an entry carries no ICAO)."""
    out = []
    for entry in entries or ():
        if not isinstance(entry, dict):
            continue
        if icao is not None and entry.get("icao"):
            if str(entry["icao"]).upper() != str(icao).upper():
                continue
        out.append(entry)
    return out


def _synthetic_flat_site_from_dem(dem_obj, icao: str | None = None):
    """This airport's ``synthetic_flat_site`` entry on the DEM, or None.

    A multi-airport tile can carry several; ``icao`` selects the one whose
    surface this patch was graded on.  With no ``icao`` the FIRST entry is
    returned, which is the whole record on a single-airport DEM.
    """
    entries = getattr(dem_obj, DEM_SYNTHETIC_FLAT_SITE_ATTR, None)
    if not entries:
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if icao is not None and entry.get("icao"):
            if str(entry["icao"]).upper() != str(icao).upper():
                continue
        return entry
    return None


def _inset_label(entry: dict) -> str:
    """Render one baked inset as ``PROVIDER(source_id[,source_id])``."""
    provider = entry.get("provider") or "?"
    source_ids = entry.get("source_ids") or []
    if source_ids:
        return f"{provider}({','.join(str(s) for s in source_ids)})"
    return str(provider)


def dem_label(dem_meta: dict) -> str:
    """Human ``dem=`` value: ``base+PROVIDER(source)`` or the loud RAW form.

    A FLAT-SITE substitution is appended as its own clause: the patch was
    not graded on the raster the inset clause names, and a reader comparing
    two patches must see that before it compares any number.
    """
    if not dem_meta:
        return "base RAW (no inset baked)"
    if dem_meta.get("raw", True):
        label = "base RAW (no inset baked)"
    else:
        label = "base+" + "+".join(
            _inset_label(e) for e in dem_meta.get("insets", []))
    synthetic = dem_meta.get("synthetic_flat_site")
    if synthetic:
        label += " +FLAT_SITE(Z0=%s m)" % synthetic.get("z0_m")
    return label


# ──────────────────────────────────────────────────────────────────────────────
# Assembly + tag rendering
# ──────────────────────────────────────────────────────────────────────────────
def assemble_provenance(icao: str, dem_meta: dict | None) -> dict:
    """Build the full provenance record for one airport patch.

    ``dem_meta`` is the ``dem_provenance_from_dem`` result (or None → RAW).
    """
    if dem_meta is None:
        dem_meta = {"insets": [], "raw": True}
    return {
        "icao": icao,
        "git": git_provenance(),
        "gates": gate_provenance(),
        "dem": dem_meta,
        "built": datetime.datetime.now().replace(microsecond=0).isoformat(),
    }


def _quote(value: str) -> str:
    """Percent-encode a tag value so it never contains a quote/space/newline."""
    return urllib.parse.quote(str(value), safe="")


def provenance_tags(prov: dict) -> dict:
    """Render the provenance record as ``o4_provenance_*`` root-attribute tags.

    Values are percent-encoded so the attribute string is always quote-safe,
    mirroring the ``o4_apt_dat`` convention.  Keys are stable so the reader can
    parse them back.  Absent facets are stamped explicitly (e.g. ``sha=absent``)
    so the reader can tell "no git" from "old unstamped patch".
    """
    git = prov.get("git") or {}
    gates = prov.get("gates") or {}
    dem = prov.get("dem") or {}
    tags: dict = {}
    tags["o4_provenance_sha"] = _quote(git.get("sha") or "absent")
    dirty = git.get("dirty")
    tags["o4_provenance_dirty"] = (
        "unknown" if dirty is None else ("true" if dirty else "false")
    )
    tags["o4_provenance_gates_on"] = _quote(",".join(gates.get("on", [])))
    tags["o4_provenance_gates_nondefault"] = _quote(
        ",".join(f"{n}={v}" for n, v in gates.get("nondefault", []))
    )
    tags["o4_provenance_gates_total"] = str(gates.get("total", 0))
    tags["o4_provenance_dem_raw"] = "true" if dem.get("raw", True) else "false"
    tags["o4_provenance_dem"] = _quote(dem_label(dem))
    tags["o4_provenance_built"] = _quote(prov.get("built") or "")
    tags["o4_provenance_icao"] = _quote(prov.get("icao") or "")
    return tags


def format_log_line(prov: dict) -> str:
    """One-line human summary logged per airport at patch completion.

    Compact by design: the full gate lists live in the tags/reader.  The line
    shows the sha (with a ``*`` dirty marker), the count of ON gates plus any
    non-default deviations (the actionable drift), and the DEM label.  The
    no-inset case is rendered as a WARNING so it stands out in the build log.
    """
    icao = prov.get("icao") or "????"
    git = prov.get("git") or {}
    gates = prov.get("gates") or {}
    dem = prov.get("dem") or {}
    sha = git.get("sha") or "absent"
    if git.get("dirty"):
        sha += "*"  # dirty-tree marker
    on_count = len(gates.get("on", []))
    nondefault = gates.get("nondefault", [])
    if nondefault:
        drift = ",".join(f"{n}={v}" for n, v in nondefault)
        gate_str = f"{on_count}on nondefault=[{drift}]"
    else:
        gate_str = f"{on_count}on"
    dem_str = dem_label(dem)
    line = f"  [provenance] {icao} patch: sha={sha} gates={gate_str} dem={dem_str}"
    if dem.get("raw", True):
        line += "  ← WARNING: graded on base DEM, no airport-elevation inset"
    return line


# ──────────────────────────────────────────────────────────────────────────────
# Reader side — parse the stamp back out of a written patch
# ──────────────────────────────────────────────────────────────────────────────
_ROOT_ATTR_RE = re.compile(r"o4_provenance_([a-z_]+)='([^']*)'")


def parse_patch_provenance(path: str) -> dict | None:
    """Read the provenance stamp back from a ``.patch.osm`` file's root.

    Returns a dict of the decoded facets, or ``None`` when the file is missing,
    unreadable, or carries no provenance stamp (an old/unstamped patch).  Only
    the first line or two are read — the ``<osm>`` root — so this is fast on any
    patch size.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            line = handle.readline()
            if "<osm " not in line:
                line = handle.readline()
    except OSError:
        return None
    if "<osm " not in line:
        return None
    raw: dict = {}
    for match in _ROOT_ATTR_RE.finditer(line):
        raw[match.group(1)] = match.group(2)
    if not raw:
        return None
    decoded: dict = {}
    decoded["sha"] = urllib.parse.unquote(raw.get("sha", ""))
    decoded["dirty"] = raw.get("dirty", "unknown")
    decoded["gates_on"] = [
        g
        for g in urllib.parse.unquote(raw.get("gates_on", "")).split(",")
        if g
    ]
    decoded["gates_nondefault"] = [
        g
        for g in urllib.parse.unquote(raw.get("gates_nondefault", "")).split(",")
        if g
    ]
    decoded["gates_total"] = raw.get("gates_total", "0")
    decoded["dem_raw"] = raw.get("dem_raw", "true") == "true"
    decoded["dem"] = urllib.parse.unquote(raw.get("dem", ""))
    decoded["built"] = urllib.parse.unquote(raw.get("built", ""))
    decoded["icao"] = urllib.parse.unquote(raw.get("icao", ""))
    return decoded


# ──────────────────────────────────────────────────────────────────────────────
# Freshness fingerprints — the inputs the rebuild-skip gate compares
# ──────────────────────────────────────────────────────────────────────────────
# ``driver._auto_patch_is_current`` reuses an existing ``*_auto.patch.osm``
# only when EVERY input that can change the emitted patch is unchanged.  The
# fingerprints below are what "unchanged" is measured against; they are stamped
# on the ``<osm>`` root by ``PavementLayout.to_osm`` alongside the two legacy
# ``o4_apt_dat*`` stamps, and recomputed by the gate for comparison.
#
# Three hard rules:
#
# 1. FAIL-SAFE.  A missing, unparseable or unrecognised stamp means REBUILD.
#    Every value therefore has an explicit "could not determine" spelling
#    (``absent`` / ``unknown`` / ``?``) rather than an empty string that could
#    collide with a legitimately empty result.
# 2. CHEAP.  The gate runs per airport per tile build, so this is stat()-level
#    work and in-memory hashing only — never a DSF content read, a DEM raster
#    read, or an apt.dat re-parse.
# 3. INPUTS, NOT DERIVED ARTIFACTS.  Nothing here may key on a file the tile
#    build itself rewrites (``Data<tile>.alt`` above all): that would
#    self-invalidate every patch on every tile build and destroy caching.
#
# Bump when the stamp SET or any value's meaning changes: a patch whose
# ``o4_fresh_v`` differs from this is treated as unrecognised and rebuilds once.
# "2" (2026-09-04): ``o4_ap_engine`` joined the compared keys — a patch one
# auto-patch engine wrote is never current for the other (RULINGS
# 2026-09-03d, v2 beside v1).  Every "1" patch rebuilds exactly once.
FRESHNESS_SCHEMA_VERSION = "2"

# Stamp keys the gate compares one-for-one.  ``o4_dsf_tiles`` is deliberately
# NOT here: it is an INPUT to the recomputation of ``o4_dsf`` (which 1°×1°
# tiles' DSFs the build consulted), not a value with a "today" counterpart —
# the tile set today is only knowable by re-parsing apt.dat and re-reading the
# DSF pavement (it follows the airport's pavement bbox), which rule 2 forbids.
# It needs no direct check: the tile set can only move if the apt.dat or a pack
# DSF moved, and both of those ARE compared.
FRESHNESS_COMPARED_KEYS = (
    "o4_fresh_v",
    "o4_cfg",
    "o4_dem",
    "o4_cifp",
    "o4_pack",
    "o4_engine",
    "o4_ap_engine",
    "o4_dsf",
)

# Every stamp key written, in the order they appear on the root element.
FRESHNESS_KEYS = FRESHNESS_COMPARED_KEYS + ("o4_dsf_tiles",)


def _identity(path: str | None) -> str:
    """``<quoted path>|<size>|<mtime>`` for one input file.

    The path is percent-encoded so the value carries no quote or space and can
    ride in a single-quoted XML attribute; ``|`` and ``;`` are left literal as
    field / list separators.  A path that cannot be stat'ed is rendered
    ``<quoted path>|missing`` — a distinct value, so a file that disappears
    (or reappears) flips the fingerprint instead of silently comparing equal.
    """
    if not path:
        return "none"
    try:
        stat = os.stat(path)
    except OSError:
        return _quote(path) + "|missing"
    return f"{_quote(path)}|{stat.st_size}|{stat.st_mtime:.6f}"


def identity_list(paths) -> str:
    """``;``-joined :func:`_identity` for a set of input files.

    SORTED, so a reader-order difference between the emit side and the gate
    side can never read as a changed input.  ``""`` means "read nothing" — a
    real, comparable answer, distinct from the ``"?"`` the callers use for
    "never recorded".
    """
    return ";".join(sorted(_identity(p) for p in (paths or ())))


def _stable_repr(value) -> str:
    """Order-independent, float-exact repr for a config constant."""
    if isinstance(value, (set, frozenset)):
        return "{" + ",".join(sorted(_stable_repr(v) for v in value)) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{_stable_repr(k)}:{_stable_repr(v)}"
            for k, v in sorted(value.items(), key=lambda kv: repr(kv[0]))
        ) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_stable_repr(v) for v in value) + "]"
    return repr(value)


# What the config digest deliberately LEAVES OUT.
#
# The digest must invalidate a patch when a setting that can change the emitted
# geometry or elevations changes — and must NOT invalidate it otherwise, or a
# user turning up log verbosity would rebuild every airport in the world.  The
# four excluded constants are the ones whose own source comments declare them
# output-only, and each is excluded for a reason that is verifiable at its
# definition site in config.py:
#
#   LOG_VERBOSITY      — chatter volume only.  (It used to also gate the
#                        ``.axes.json`` sidecar; since 2026-08-05 that is
#                        written unconditionally, so this constant now
#                        touches nothing but print volume.)
#   BUILD_PROGRESS     — progress banners; "the emitted patch is byte-identical
#                        regardless".
#   REPORT_GRADE_AUDIT — a build-time WARN audit that nothing acts on;
#                        "output-only — the emitted patch is identical".
#   PARALLEL_AIRPORTS  — scheduling only; the parallel path is validated
#                        BYTE-IDENTICAL to serial.
#
# Everything else in config.py is IN, including every numeric standards /
# tuning constant and every ``O4_`` env gate — the whole point of the digest is
# that it cannot rot as constants are added.  The env gate whose default
# produced each excluded constant is excluded alongside it, otherwise the gate
# value would re-introduce exactly what the constant exclusion removed.
CONFIG_DIGEST_EXCLUDED_CONSTANTS = frozenset({
    "LOG_VERBOSITY",
    "BUILD_PROGRESS",
    "REPORT_GRADE_AUDIT",
    "PARALLEL_AIRPORTS",
})
CONFIG_DIGEST_EXCLUDED_GATES = frozenset({
    "O4_LOG_VERBOSITY",
    "O4_BUILD_PROGRESS",
    "O4_REPORT_GRADE_AUDIT",
    "O4_PARALLEL_AIRPORTS",
    # Not settings at all: the freshness gate's own force-rebuild flag (which
    # the gate consults directly and which must not itself be an input), and
    # the provenance stamp's master switch (it governs the header block, not
    # any emitted geometry).
    "O4_AUTO_PATCH_REBUILD",
    "O4_PATCH_PROVENANCE",
})


def config_digest() -> str:
    """One 16-hex digest over every config value that can change a patch.

    Three contributions:

    * every ``O4_`` env gate :mod:`auto_patch.config` DECLARES, at its live
      value — enumerated by :func:`introspect_config_gates`, the same
      introspection the provenance stamp uses, so the inventory tracks the
      source automatically and cannot rot as gates come and go;
    * every ``O4_`` variable actually SET in the environment.  Two reasons:
      gates read at a call site outside config.py (``O4_FORCE_APT_DAT``, the
      pavement-model toggles in ``driver``) are covered, and — the important
      one — a FROZEN engine ships no ``.py`` for the introspection to read, so
      without this a gate flip would be invisible in the packaged app; and
    * every module-level constant config.py defines (standards numbers, role
      tables, tuning knobs) — the source-edit half, which no env gate covers,
      and which reads correctly from the compiled module when frozen.

    See ``CONFIG_DIGEST_EXCLUDED_*`` for what is left out and why.  Returns
    ``"unknown"`` only when the config module itself cannot be imported.
    """
    try:
        from . import config as _config
    except Exception:
        return "unknown"
    parts: list[str] = []
    gates = introspect_config_gates()
    # Recorded so a build whose config SOURCE was readable never silently
    # compares equal to one where it was not: the two enumerate different
    # gate sets, and a patch must not cross that boundary unrebuilt.
    parts.append("introspect:" + ("ok" if gates else "unavailable"))
    for name in sorted(gates):
        if name in CONFIG_DIGEST_EXCLUDED_GATES:
            continue
        parts.append(f"gate:{name}={gates[name]['value']}")
    for name in sorted(os.environ):
        if not name.startswith("O4_") or name in CONFIG_DIGEST_EXCLUDED_GATES:
            continue
        if name in gates:
            continue                     # already digested at its live value
        parts.append(f"env:{name}={os.environ[name]}")
    for name in sorted(dir(_config)):
        if name.startswith("_") or name in CONFIG_DIGEST_EXCLUDED_CONSTANTS:
            continue
        try:
            value = getattr(_config, name)
        except Exception:
            continue
        if not isinstance(value, (bool, int, float, str, bytes,
                                  tuple, list, set, frozenset, dict,
                                  type(None))):
            continue                     # functions, modules, classes
        parts.append(f"const:{name}={_stable_repr(value)}")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


# Sentinel telling "the attribute was never set" from "it was set to empty".
_UNSET = object()


def dem_fingerprint(tile, icao: str | None = None) -> str:
    """Fingerprint of the DEM INPUTS this airport's elevations were solved on.

    Deliberately NOT a fingerprint of the DEM the solve saw: that surface is a
    derived artifact (``Data<tile>.alt`` is rewritten by the vector/mesh steps
    of the very build that would consume this patch), so keying on it would
    self-invalidate every patch on every tile build.  Two input facets instead:

    * ``spec`` — a digest over the DEM SOURCE SPECIFICATION for this tile: the
      composite source string the tile DEM was constructed from
      (``base;inset;inset``, which already names a ``custom_dem`` and every
      cached inset), the identity of each source token that is a file on disk,
      the generic per-tile ``.tif`` when the base token is empty
      (``DEM.load_data`` prefers it over the configured provider, so its
      arrival changes the DEM),
      and the tile's elevation settings — level, smoothing, inset and grid
      knobs — plus the app-level base elevation source.  This facet is
      TILE-WIDE on purpose even though the patch is one airport's: the inset
      set drives ``densify_tile_dem_for_insets``, which resets the working
      grid posting for the whole tile, so an inset arriving anywhere on it
      really can move this airport's sampled elevations.
    * ``insets`` — the identities (path+size+mtime) of the airport-elevation
      inset rasters that ACTUALLY baked into this tile's DEM, from the
      provenance ``bake_airport_insets_into_alt_dem`` stamps on the DEM object,
      filtered to this airport.  ``unbaked`` (the bake step never ran — the
      standalone raw-load path) is a DIFFERENT value from ``none`` (it ran and
      baked nothing for this airport), so the silent-raw-DEM case cannot be
      confused with a never-baked one.

    Returns ``"absent"`` with no tile — a value no live tile produces, so a
    patch stamped from a real build never compares equal to a gate that has
    lost its tile.
    """
    if tile is None:
        return "absent"
    dem = getattr(tile, "dem", None)
    spec_parts: list[str] = []
    source_spec = getattr(dem, "source_path", None) if dem is not None else None
    if dem is None:
        spec_parts.append("dem:nodem")
    else:
        spec_parts.append(f"dem:{source_spec!r}")
        tokens = str(source_spec or "").split(";")
        for token in tokens:
            if token and os.path.exists(token):
                spec_parts.append("src:" + _identity(token))
        if not tokens or not tokens[0]:
            # Empty base token: DEM.load_data falls back to the generic
            # per-tile .tif when one exists, before consulting the provider
            # registry.  Stat it so dropping one in is seen as a DEM change.
            try:
                import O4_File_Names as _FNAMES

                generic = _FNAMES.generic_tif(tile.lat, tile.lon)
                if os.path.exists(generic):
                    spec_parts.append("generic:" + _identity(generic))
            except Exception:
                pass
    for name in ("custom_dem", "fill_nodata", "elevation_level",
                 "elevation_coastline_band_km", "apt_smoothing_pix",
                 "apt_smoothing_auto", "airport_elevation_insets",
                 "airport_elevation_providers", "airport_elevation_level",
                 "airport_elevation_inset_margin_m",
                 "airport_elevation_inset_feather_m", "airport_inset_water",
                 "working_grid_arc_seconds"):
        spec_parts.append(f"cfg:{name}={getattr(tile, name, _UNSET)!r}")
    try:
        # The app-level base source is a per-tile setting only in effect when
        # ``custom_dem`` is empty; the config registry assigns it onto
        # O4_DEM_Utils (``"module": "DEM"``), which any real tile build has
        # already imported to construct ``tile.dem``.
        import O4_DEM_Utils as _DEM

        spec_parts.append(
            f"app:base_elevation_source="
            f"{getattr(_DEM, 'base_elevation_source', _UNSET)!r}")
    except Exception:
        spec_parts.append("app:base_elevation_source=unknown")
    spec = hashlib.sha256("\n".join(spec_parts).encode("utf-8")).hexdigest()

    if dem is None:
        insets = "nodem"
    else:
        recorded = getattr(dem, DEM_INSET_PROVENANCE_ATTR, _UNSET)
        if recorded is _UNSET:
            insets = "unbaked"
        else:
            paths = []
            for entry in (recorded or ()):
                if not isinstance(entry, dict):
                    continue
                if icao is not None and entry.get("icao"):
                    if str(entry["icao"]).upper() != str(icao).upper():
                        continue
                if entry.get("path"):
                    paths.append(entry["path"])
            insets = identity_list(paths) if paths else "none"
    return f"spec:{spec[:16]};insets:{insets}"


def engine_version() -> str:
    """The running engine's version string, or ``absent``.

    Imported the way the rest of the engine does it (``import O4_Version``).
    The version carries a build number that increments on every engine build,
    so this stamp invalidates every patch whenever a new engine is built —
    intended (owner 2026-07-24): a rebuilt engine may emit different geometry.
    """
    try:
        import O4_Version

        return str(getattr(O4_Version, "version", "") or "") or "absent"
    except Exception:
        return "absent"


def freshness_mismatch(stamped: dict, live: dict) -> str | None:
    """First stamp key whose stamped value is missing or differs, else None.

    Fail-safe by construction: a key missing from EITHER side reports as a
    mismatch, so an old-format patch, a patch written by a standalone tool, and
    a gate that could not compute a live value all rebuild rather than being
    compared as "both absent, therefore equal".
    """
    for key in FRESHNESS_COMPARED_KEYS:
        if key not in stamped or key not in live:
            return key
        if stamped[key] != live[key]:
            return key
    return None
