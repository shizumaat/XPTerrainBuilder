"""THE PATCH LIBRARY (#1699 phase 2, "Airport entries"): solved airport
patches shared through ONE public GitHub repository.

An AIRPORT ENTRY is one airport's solved patch family (the patch, its
sidecar, the graded surface, the object plans) plus the user's edits,
stamped with the pack signature and the auto-patch law that solved it.
A user whose installed pack and engine match an entry downloads it and
the tile's build skips that airport's solve; any mismatch falls back to
today's local solve.  Spec: ``docs/specs/patch-library-phase2-20261102.md``.

* :mod:`.config` — where the library is (configuration, never a literal
  in a caller);
* :mod:`.layout` — the repository's layout (stdlib only);
* :mod:`.terms` — each source's terms and the entry's licence (stdlib
  only);
* :mod:`.checks` / :mod:`.index` — what the library's GitHub Actions run:
  the entry checks and the regional index rebuild (stdlib only, entries
  read as DATA, never executed; the app's pre-publish check is the same
  code);
* :mod:`.key` — an entry's match key on this machine;
* :mod:`.entry` — an entry packaged from a built tile;
* :mod:`.client` — reading the library (no account, ever);
* :mod:`.scan` — the check when the app opens, and the build box's
  match list;
* :mod:`.adoption` / :mod:`.apply` — an entry laid down, and the record
  the build's reuse gate reads;
* :mod:`.github` / :mod:`.publish` — "Publish patch": GitHub device
  sign-in, fork, branch and pull request, from the app.

This package's ``__init__``, :mod:`.layout`, :mod:`.terms`, :mod:`.checks`
and :mod:`.index` import nothing of the engine: the library's workflow runs
them from a sparse checkout of this repository.
"""
from __future__ import annotations

__all__ = ["FORMAT", "INDEX_FORMAT", "LICENCE", "LICENCE_NC", "LibraryRefused"]

#: The airport-entry format this engine writes and reads.
FORMAT = "xptl-airport-1"

#: The regional index format.
INDEX_FORMAT = "xptl-index-1"

#: The library's licence, and an entry's whose sources are all open
#: (owner Q304, 2026-11-02).
LICENCE = "ODbL-1.0"

#: An entry with a non-commercial source: offered for non-commercial use
#: under each source's terms (owner Q319, 2026-11-03; :mod:`.terms`).
LICENCE_NC = "per-source-noncommercial"


class LibraryRefused(ValueError):
    """A library action that cannot be done, with the reason in the
    user's words."""
