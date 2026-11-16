"""A texture landed while X-Plane runs shows at the next scenery reload
(#2106).

X-Plane 12.4 keeps every texture it holds across Developer > "Reload
scenery": the reload re-reads the DSF and ``.ter`` files but does not
reset its texture paging (its log shows "Pre-warming paging cache" and
"Target scale moved to 1" at a FLIGHT load, never at a scenery reload),
so a texture it already holds at the finest level it wants -- a
placeholder under the aircraft -- is not opened again and the sharp
file landed under the same name stays unseen (owner 2026-11-16T14:07Z,
#2106: sharp 4096 px files landed 13:57-13:58Z, two reloads at
~14:00Z and ~14:06Z, still low-res under the aircraft).  A NEW path is
one X-Plane does not hold.

So after a landing, :func:`renew` gives the texture a fresh name for
X-Plane: a symlink ``<textures>/.xp_reload/<stem>~<token>.dds`` pointing
at ``../<name>``, and every ``.ter`` of the tile that names the texture
rewritten (whole file, partial name, ``os.replace``) to name the symlink.
The texture's own file stays the one truth: every writer (the lander,
the cache, the downgrade, the converter) keeps writing ``<name>``, and
every symlink resolves to it, so the path X-Plane holds since its last
scenery load -- the own name or an older symlink -- still opens the
newest file at its next step-up (in flight nothing changes).  The newest
:data:`KEEP` symlinks of a texture are kept (a pass lands at most three
tiers between two loads); older ones go.

Every reader of a ``.ter``'s texture reads it back through
:func:`canonical` (the on-demand index, Convert, bundles): a symlink is
never a texture of its own.  Where no symlink can be made (Windows
without the privilege) nothing changes: the ``.ter`` keeps the own name.
"""
from __future__ import annotations

import contextlib
import os
import time

__all__ = ["ALIAS_DIR", "KEEP", "SEP", "canonical", "renew"]

#: The folder of the symlinks, beside the textures (hidden: no texture
#: listing sees it).
ALIAS_DIR = ".xp_reload"
#: Between a texture's stem and a symlink's token.
SEP = "~"
#: Symlinks kept per texture, the newest.
KEEP = 4
_TEX_WORDS = ("BASE_TEX_NOWRAP", "BASE_TEX")


def canonical(name: str) -> str:
    """The texture a ``.ter`` reference names: its base name, a symlink's
    (``<stem>~<token>.dds``) read back to ``<stem>.dds``."""
    base = os.path.basename(str(name).replace("\\", "/"))
    stem, dot, ext = base.rpartition(".")
    if dot and SEP in stem:
        return stem.split(SEP, 1)[0] + "." + ext
    return base


def _texture_ref(line: str) -> "tuple[str, str] | None":
    words = line.split()
    if len(words) == 2 and words[0] in _TEX_WORDS:
        return words[0], words[1]
    return None


def naming_ters(terrain_dir: str, name: str) -> "list[str]":
    """The ``.ter`` files of ``terrain_dir`` whose base texture is
    ``name`` (Ortho4XP names them ``<stem>.ter``, ``<stem>_water.ter``,
    ``<stem>_sea_overlay.ter`` ...); none for a missing folder."""
    stem = name[:-4] if name.endswith(".dds") else name
    out = []
    try:
        entries = sorted(os.listdir(terrain_dir))
    except OSError:
        return out
    for entry in entries:
        if not (entry.startswith(stem) and entry.endswith(".ter")):
            continue
        path = os.path.join(terrain_dir, entry)
        with contextlib.suppress(OSError):
            with open(path, encoding="utf-8", errors="replace") as handle:
                if any((ref := _texture_ref(line)) and canonical(ref[1]) == name
                       for line in handle):
                    out.append(path)
    return out


def _rewrite(ter: str, name: str, alias_rel: str) -> bool:
    """``ter`` with its base texture pointing at ``alias_rel`` (the folder
    part of the old reference kept), written whole by rename."""
    try:
        with open(ter, encoding="utf-8", errors="replace", newline="") as h:
            lines = h.read().splitlines(keepends=True)
    except OSError:
        return False
    changed = False
    for i, line in enumerate(lines):
        ref = _texture_ref(line)
        if not ref or canonical(ref[1]) != name:
            continue
        folder = ref[1].replace("\\", "/").rsplit("/", 1)
        prefix = folder[0] + "/" if len(folder) == 2 else ""
        if prefix.endswith(ALIAS_DIR + "/"):
            prefix = prefix[:-len(ALIAS_DIR) - 1]
        end = line[len(line.rstrip("\r\n")):]
        lines[i] = f"{ref[0]} {prefix}{alias_rel}{end}"
        changed = True
    if not changed:
        return False
    partial = f"{ter}.{os.getpid()}.part"
    try:
        with open(partial, "w", encoding="utf-8", newline="") as handle:
            handle.writelines(lines)
        os.replace(partial, ter)
    except OSError:
        with contextlib.suppress(OSError):
            os.remove(partial)
        return False
    return True


def _token(alias_dir: str, stem: str, now: float) -> str:
    """A token no symlink of ``stem`` has had (base 36 of the time in
    tenths of a second, bumped past any taken)."""
    n = int(now * 10)
    while True:
        token = _base36(n)
        if not os.path.lexists(os.path.join(alias_dir,
                                            f"{stem}{SEP}{token}.dds")):
            return token
        n += 1


def _base36(n: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = digits[r] + out
        if not n:
            return out


def _age(token: str) -> int:
    """A token's time (its order); an unreadable one is the oldest."""
    try:
        return int(token, 36)
    except ValueError:
        return -1


def _prune(alias_dir: str, stem: str, keep: int) -> None:
    """All but the newest ``keep`` symlinks of ``stem`` removed."""
    prefix = stem + SEP
    try:
        mine = [e for e in os.scandir(alias_dir)
                if e.name.startswith(prefix) and e.is_symlink()]
    except OSError:
        return
    mine.sort(key=lambda e: _age(e.name[len(prefix):-4]), reverse=True)
    for entry in mine[keep:]:
        with contextlib.suppress(OSError):
            os.remove(entry.path)


def renew(texture: "str | None", terrain_dir: "str | None",
          now: "float | None" = None) -> "str | None":
    """Give ``texture`` (a landed file's path) a path X-Plane does not
    hold: a fresh symlink, and the tile's ``.ter`` files that name the
    texture rewritten to it.  Returns the symlink's path, ``None`` when
    nothing changed (no ``.ter`` names it, no symlink can be made).
    Never raises."""
    try:
        if not texture or not terrain_dir or not os.path.isfile(texture):
            return None
        name = os.path.basename(texture)
        ters = naming_ters(terrain_dir, name)
        if not ters:
            return None
        stem = name[:-4]
        alias_dir = os.path.join(os.path.dirname(texture), ALIAS_DIR)
        os.makedirs(alias_dir, exist_ok=True)
        token = _token(alias_dir, stem, time.time() if now is None else now)
        alias_name = f"{stem}{SEP}{token}.dds"
        alias = os.path.join(alias_dir, alias_name)
        os.symlink(os.path.join(os.pardir, name), alias)
        rel = f"{ALIAS_DIR}/{alias_name}"
        if not any([_rewrite(ter, name, rel) for ter in ters]):
            os.remove(alias)
            return None
        _prune(alias_dir, stem, KEEP)
        return alias
    except (OSError, NotImplementedError, ValueError):
        return None
