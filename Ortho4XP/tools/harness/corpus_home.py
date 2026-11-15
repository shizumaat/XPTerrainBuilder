"""THE HARNESS CORPUS LOCATION — one setting, and the app's root it must
never be (owner 2026-11-15T02:42Z, #2093).

    "I would say the app shouldn't know anything about tests or
    development, so it can't know to skip cache clearing. We should keep a
    separate copy in the development folder for test use."

Until #2093 the harness corpus WAS the app's data root
(``~/XPTerrainBuilderData``), and the app's automatic storage cleanup
deleted 14,183 Elevation_data files from it on 2026-11-14 — an unledgered
corpus change no lane was told about.  The app knows nothing of the
harness and never will, so the harness keeps its OWN copy, outside every
app data root, and refuses to run on an app root.

ONE SETTING: ``O4_DATA_REPO`` when set, else :data:`DEV_CORPUS_DEFAULT`.
Every reader resolves it through :func:`data_repo` — the write guard
(``shared_repo_guard.DATA_REPO``), the cloud-snapshot leak watch
(``corpus_snapshot.SHARED_DATA_REPO_DEFAULT``), the lane ritual
(``lane_worktree.sh`` ``DATA_REPO``, twin-pinned equal), the frames
registry's durable root and the tests (``tests/conftest.py``
``DATA_REPO``).  This module imports nothing else of the harness, so it
can be read before the guard (which freezes the env at import).
"""
from __future__ import annotations

import os
from pathlib import Path

#: The environment override (also the cloud-snapshot arm's lever).
ENV = "O4_DATA_REPO"

#: THE development corpus: a sibling of the repo checkout on the same APFS
#: volume (so it was seeded as a clone and every lane's symlink mount
#: works unchanged), outside git (no ``git clean -x`` or tree walk reaches
#: it) and outside every app data root (no app cleanup reaches it).
DEV_CORPUS_DEFAULT = Path("/Users/noah/XPTerrainBuilderDevData")

#: The corpus this setting replaced (the app's default data root).  Read
#: only to re-home registry rows (``frames.py rehome``) and as a leak root.
LEGACY_CORPUS = Path("/Users/noah/XPTerrainBuilderData")


def data_repo(environ=None) -> Path:
    """The harness corpus: ``O4_DATA_REPO``, else the development default."""
    environ = os.environ if environ is None else environ
    return Path(environ.get(ENV) or DEV_CORPUS_DEFAULT)


def app_data_roots() -> list:
    """Every folder the app may be using as its data root: its default
    (``O4_File_Names.default_data_root``, twin-pinned) and the remembered
    first-launch choice (``~/.ortho4xp/data_root.txt``).  Read-only; the
    harness knows about the app, never the other way round."""
    home = Path(os.path.expanduser("~"))
    roots = [home / "XPTerrainBuilderData"]
    try:
        pointed = (home / ".ortho4xp" / "data_root.txt").read_text(
            encoding="utf-8").strip()
    except OSError:
        pointed = ""
    if pointed:
        roots.append(Path(pointed))
    return roots


def app_root_overlap(path) -> "Path | None":
    """The app data root ``path`` is, lies inside or contains — the app's
    storage cleanup would reach the corpus there — or ``None``."""
    real = Path(os.path.realpath(path))
    for root in app_data_roots():
        r = Path(os.path.realpath(root))
        if real == r or r in real.parents or real in r.parents:
            return r
    return None


def require_not_app_root(path) -> None:
    """Refuse a harness corpus the app's cleanup can delete (#2093)."""
    hit = app_root_overlap(path)
    if hit is not None:
        raise SystemExit(
            f"REFUSING: the harness corpus {path} overlaps the app's data "
            f"root {hit}.  The app's automatic storage cleanup deletes "
            f"caches there and knows nothing of the harness (owner "
            f"2026-11-15T02:42Z, #2093).  Use the development corpus "
            f"{DEV_CORPUS_DEFAULT} (unset {ENV}) or another folder outside "
            f"every app data root.")


if __name__ == "__main__":
    # `corpus_home.py` prints the corpus; `--check PATH` refuses an app root
    # (exit 2, the lane ritual's refusal code).
    import sys
    if sys.argv[1:2] == ["--check"] and len(sys.argv) == 3:
        try:
            require_not_app_root(sys.argv[2])
        except SystemExit as exc:
            print(exc, file=sys.stderr)
            sys.exit(2)
    else:
        print(data_repo())
