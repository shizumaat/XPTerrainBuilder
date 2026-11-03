"""WHERE THE LIBRARY IS (#1699 phase 2) — configuration, read at call time.

The library is one public GitHub repository; nothing of ours is hosted
(owner, 2026-11-02).  Reading it needs no account: the index and the
entries are plain files under :func:`settings`'s ``raw_base``.  Publishing
uses the publisher's own GitHub account through GitHub's device sign-in,
which needs only the OAuth app's public ``client_id`` — no secret.

GOING LIVE is setting :data:`REPO` and :data:`CLIENT_ID` below (the owner
creates the repository from ``library_template/`` and registers the OAuth
app).  Until then :func:`configured` is false and every library command
says so.  The ``XPTB_LIBRARY_*`` environment variables override each
value (the tests' and the gate's fake library); they are NOT ``O4_``
variables, which the auto-patch configuration digest reads.
"""
from __future__ import annotations

import os

__all__ = ["REPO", "CLIENT_ID", "BRANCH", "settings", "configured"]

#: ``owner/name`` of the library repository ("" until it exists).
REPO = "shizumaat/xptb-patch-library"

#: The public client id of the library's GitHub OAuth app (device flow).
CLIENT_ID = "Ov23liYUGBNlCuCnNKvu"

#: The library's default branch.
BRANCH = "main"

_ENV = {"repo": "XPTB_LIBRARY_REPO", "raw_base": "XPTB_LIBRARY_RAW",
        "api_base": "XPTB_LIBRARY_API", "oauth_base": "XPTB_LIBRARY_OAUTH",
        "client_id": "XPTB_LIBRARY_CLIENT_ID", "branch": "XPTB_LIBRARY_BRANCH"}


def settings() -> dict:
    """``{"repo", "branch", "raw_base", "api_base", "oauth_base",
    "client_id"}`` — :data:`REPO` etc. with the environment over them."""
    repo = os.environ.get(_ENV["repo"], REPO)
    branch = os.environ.get(_ENV["branch"], BRANCH)
    raw = os.environ.get(_ENV["raw_base"]) or (
        "https://raw.githubusercontent.com/%s/%s" % (repo, branch) if repo else "")
    return {"repo": repo, "branch": branch, "raw_base": raw.rstrip("/"),
            "api_base": os.environ.get(_ENV["api_base"],
                                       "https://api.github.com").rstrip("/"),
            "oauth_base": os.environ.get(_ENV["oauth_base"],
                                         "https://github.com").rstrip("/"),
            "client_id": os.environ.get(_ENV["client_id"], CLIENT_ID)}


def configured(publishing: bool = False) -> bool:
    """Whether the library can be read (and, ``publishing``, published to)."""
    s = settings()
    return bool(s["raw_base"]) and (not publishing
                                    or bool(s["repo"] and s["client_id"]))
