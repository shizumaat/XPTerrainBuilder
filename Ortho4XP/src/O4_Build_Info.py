"""The build triple every bug report quotes: app version, engine version, commit.

A tester's "it broke in 1.0.347" does not identify a build — the app version,
the engine version and the commit are three independent numbers, and a beta
carries all three (docs/BETA-PLAN-20260916.md §1 B3).  Every release artifact
root carries ``VERSION.txt`` written by ``scripts/write_version_txt.sh``::

    app=1.0.347
    engine=1.50.1793
    sha=5883949f…

This module is the single reader of that file, and the fallback for a
development tree that has no artifact root: it never guesses a commit, it
says ``dev``.

The engine version is the one exception — ``src/O4_Version.py`` is imported
directly when it is importable, so a dev tree still reports a real engine
version rather than ``dev``.
"""

from __future__ import annotations

import os
import sys
from typing import NamedTuple

DEV = "dev"


class BuildInfo(NamedTuple):
    """app/engine/sha, each a version string or ``"dev"``."""

    app: str
    engine: str
    sha: str

    def as_lines(self) -> str:
        """The three lines an About dialog shows and a bug report pastes."""
        return (
            "App version:    %s\n"
            "Engine version: %s\n"
            "Commit:         %s" % (self.app, self.engine, self.sha)
        )


def _artifact_roots() -> list[str]:
    """Directories that may hold the artifact's VERSION.txt, best first.

    Frozen (PyInstaller onedir): the executable sits AT the artifact root,
    beside VERSION.txt.  Source tree: the repo root two levels above this
    file, where a local ``scripts/write_version_txt.sh`` run would put one.
    """
    roots: list[str] = []
    if getattr(sys, "frozen", False):
        roots.append(os.path.dirname(os.path.realpath(sys.executable)))
    here = os.path.dirname(os.path.abspath(__file__))          # …/Ortho4XP/src
    engine_dir = os.path.dirname(here)                          # …/Ortho4XP
    roots.append(engine_dir)
    roots.append(os.path.dirname(engine_dir))                   # repo root
    return roots


def _read_version_txt() -> dict[str, str]:
    for root in _artifact_roots():
        path = os.path.join(root, "VERSION.txt")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        fields: dict[str, str] = {}
        for line in text.splitlines():
            key, sep, value = line.partition("=")
            if sep and value.strip():
                fields[key.strip().lower()] = value.strip()
        # A pre-B3 artifact carried the bare engine version on one line.
        # Honour it rather than reporting "dev" for a build that has one.
        if not fields:
            bare = text.strip()
            if bare:
                fields["engine"] = bare.splitlines()[0].strip()
        if fields:
            return fields
    return {}


def _engine_version() -> str:
    try:
        import O4_Version  # noqa: PLC0415 — optional in a frozen artifact
    except Exception:
        return ""
    return str(getattr(O4_Version, "version", "") or "")


def build_info() -> BuildInfo:
    """Read the triple. Never raises; unknown components read ``"dev"``."""
    fields = _read_version_txt()
    engine = fields.get("engine") or _engine_version() or DEV
    return BuildInfo(
        app=fields.get("app") or DEV,
        engine=engine,
        sha=fields.get("sha") or DEV,
    )
