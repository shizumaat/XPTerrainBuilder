"""``build_airport.py --pack-copy DIR`` and the #1906 pack_rebake refusal.

Owner 2026-11-06T00:09Z ("Why are we unable to run tests during
development?"): a lane's object stage writes into an APFS clone of the
airport pack under ``DIR`` (``O4_PACK_WRITES=copy:DIR``, read by
``src/auto_patch/pack_copy.py``), never the owner's install, so the drawn
check (``tools/drawn_check.py --tag``) reads the lane's OWN written pack.

``--refresh-data pack_rebake`` writes the owner's real packs (#1906): it is
refused whenever a pack this build would write lies under the owner's
X-Plane install.
"""
from __future__ import annotations

import glob
import json
import os

__all__ = ["arm_pack_copy", "pack_rebake_refusal", "plan_pack_roots",
           "require_pack_copy_dir"]


def _under(path, root) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def require_pack_copy_dir(pack_copy, install_roots) -> str:
    """The absolute pack-copy dir; ``SystemExit`` when it lies inside the
    owner's X-Plane install (a clone there IS a write to the install)."""
    target = os.path.abspath(pack_copy)
    for root in install_roots:
        if root and _under(target, root):
            raise SystemExit(
                f"REFUSING --pack-copy {target}: it lies inside the X-Plane "
                f"install {root}.  The copy must live in lane space "
                f"(a scratchpad or the --out dir).")
    return target


def plan_pack_roots(patch_dir) -> list:
    """The ``pack_root`` of every rebake plan beside the tile's patches."""
    roots = []
    for path in sorted(glob.glob(os.path.join(str(patch_dir),
                                              "o4_v2_rebake_*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                root = json.load(fh).get("pack_root")
        except (OSError, ValueError, AttributeError):
            continue
        if root:
            roots.append(root)
    return roots


def pack_rebake_refusal(requested, pack_roots, install_roots) -> str | None:
    """The #1906 refusal text when ``pack_rebake`` is requested and any of
    ``pack_roots`` lies under an install root, else ``None``."""
    if "pack_rebake" not in set(requested or ()):
        return None
    live = sorted({p for p in pack_roots for r in install_roots
                   if r and _under(p, r)})
    if not live:
        return None
    return ("REFUSING --refresh-data pack_rebake (#1906): it writes the "
            "owner's REAL packs, and this build's plan(s) name "
            f"{len(live)} under the X-Plane install: "
            + "; ".join(live[:4]) + (" ..." if len(live) > 4 else "")
            + ".  A lane writes a COPY: --pack-copy DIR.")


def arm_pack_copy(target, env_name, prog=None) -> dict:
    """Point the engine's placement write at ``target`` (made here)."""
    os.makedirs(target, exist_ok=True)
    os.environ[env_name] = "copy:" + target
    if prog is not None:
        prog.note(f"pack writes go to a COPY: {env_name}=copy:{target} — the "
                  f"object stage clones each pack it writes into this dir "
                  f"(APFS clonefile) and never writes the installed pack")
    return {"dir": target, "env": f"{env_name}=copy:{target}"}
