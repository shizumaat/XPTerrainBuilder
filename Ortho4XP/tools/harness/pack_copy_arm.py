"""``build_airport.py --pack-copy DIR`` and the #1906 pack_rebake refusal.

Owner 2026-11-06T00:09Z ("Why are we unable to run tests during
development?"): a lane's object stage writes into an APFS clone of the
airport pack under ``DIR`` (``O4_PACK_WRITES=copy:DIR``, read by
``src/auto_patch/pack_copy.py``), never the owner's install, so the drawn
check (``tools/drawn_check.py --tag``) reads the lane's OWN written pack.

``--refresh-data pack_rebake`` writes the owner's real packs (#1906): it is
refused whenever a pack this build would write lies under the owner's
X-Plane install.  The owner's install is read from the OWNER'S app config
(:func:`owner_install_roots`), never the lane cfg: on 2026-11-05 a lane cfg
redirected ``custom_scenery_dir`` to a scratch tree, the harness then
overwrote that redirect with the owner's path, and the guard defended the
scratch tree while the object stage rewrote three real packs.  A lane
cfg's explicit redirect now wins (:func:`effective_install_paths`).
"""
from __future__ import annotations

import glob
import json
import os

__all__ = ["arm_pack_copy", "effective_install_paths", "install_root",
           "owner_install_roots", "pack_rebake_refusal", "plan_pack_roots",
           "require_pack_copy_dir"]


def _under(path, root) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def install_root(custom_scenery_dir) -> str:
    """The X-Plane install a ``custom_scenery_dir`` value lives in."""
    custom = (custom_scenery_dir or "").rstrip("/\\")
    return os.path.dirname(custom) if custom else ""


def owner_install_roots(owner_cfg_values) -> tuple:
    """The OWNER'S install(s): the owner app config's ``custom_scenery_dir``
    and the default ``~/X-Plane 12``.  A root that does not exist refuses
    nothing, so the default is harmless off the owner's machine."""
    roots = {install_root(owner_cfg_values.get("custom_scenery_dir", "")),
             os.path.expanduser("~/X-Plane 12")}
    return tuple(sorted(r for r in roots if r))


def effective_install_paths(owner_values, lane_values, keys):
    """``(applied, redirects)`` for the X-Plane path ``keys``: the owner's
    value, except where the lane cfg names a DIFFERENT non-empty one — a
    lane's redirect, which wins and is reported in ``redirects``."""
    applied, redirects = {}, {}
    for key in keys:
        owner, lane = owner_values.get(key, ""), lane_values.get(key, "")
        if lane and lane != owner:
            applied[key] = redirects[key] = lane
        elif owner:
            applied[key] = owner
    return applied, redirects


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
