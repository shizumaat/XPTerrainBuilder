"""CODE IDENTITY BY IMPORT CLOSURE — the ONE implementation (issue #842).

A content-keyed cache is a function of its inputs AND of the code that
produced it.  The code half is: the static import closure of the entry
modules where the cached work is entered, and one sha256 of those
modules' source bytes.  A frozen engine has no sources, so the FREEZE
takes the digest from the files PyInstaller is about to compile and
writes it to a file the frozen engine reads back.

Callers (each declares its own entry modules and its own module list,
held against :func:`closure` by a twin):

- ``auto_patch_v2/airport/partition_code.py`` (the pack partition, #362),
- ``auto_patch_v2/pipeline/stage_code.py`` (the v2 stages, #842),
- ``auto_patch/provenance_code.py`` (the patch freshness gate: the
  patch build's closure, #880, and the #346 whole-tree digest behind
  ``O4_PATCH_FRESHNESS_WHOLE_TREE=1``),
- the tile pipeline's per-step closure (``O4_Step_Code.py``, #836).

STDLIB ONLY, NO RELATIVE IMPORT, NO ENGINE IMPORT: the ``.spec`` files
execute the callers by path with ``runpy`` (they never import engine
packages), and a caller run that way loads this file by path too.
"""
from __future__ import annotations

import ast
import hashlib
import os
import typing as _t

__all__ = ["source_path", "imports_of", "closure", "digest_of",
           "modules_digest", "write_digest_file", "read_digest",
           "read_digest_table"]

_HEX = frozenset("0123456789abcdef")


def source_path(src_root: str, name: str) -> str:
    """``name``'s source under ``src_root``: ``<name>.py``, or the
    package's ``__init__.py``."""
    base = os.path.join(src_root, *name.split("."))
    return os.path.join(base, "__init__.py") if os.path.isdir(base) else base + ".py"


def _existing(src_root: str, name: str) -> "str | None":
    path = source_path(src_root, name)
    return path if os.path.isfile(path) else None


def _wanted(name: str, prefixes: "_t.Collection[str] | None") -> bool:
    return prefixes is None or name.split(".")[0] in prefixes


def _from_base(node: ast.ImportFrom, pkg: str) -> str:
    """The absolute module a ``from … import`` names (relative resolved
    against ``pkg``, the importing module's package)."""
    base = node.module or ""
    if node.level:
        up = pkg.split(".") if pkg else []
        up = up[:len(up) - (node.level - 1)]
        base = ".".join(up + ([node.module] if node.module else []))
    return base


def imports_of(src_root: str, name: str,
               prefixes: "_t.Collection[str] | None" = None) -> set[str]:
    """Every module with a source under ``src_root`` that ``name`` imports,
    ANYWHERE in its source (function-level imports included), limited to
    top-level packages in ``prefixes`` when given.  ``from <package>
    import x`` is the submodule ``x`` where there is one, else the package
    itself (a name its ``__init__`` defines or re-exports — whose own
    imports are then followed)."""
    path = source_path(src_root, name)
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    if path.endswith("__init__.py"):
        pkg = name
    else:
        pkg = name.rsplit(".", 1)[0] if "." in name else ""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names if _wanted(a.name, prefixes)
                    and (prefixes is not None or _existing(src_root, a.name))}
        elif isinstance(node, ast.ImportFrom):
            base = _from_base(node, pkg)
            found = _existing(src_root, base) if base else None
            if not _wanted(base, prefixes) or found is None:
                continue
            if found.endswith("__init__.py"):
                out |= {f"{base}.{a.name}" if _existing(src_root, f"{base}.{a.name}")
                        else base for a in node.names}
            else:
                out.add(base)
    return out


def _parent_packages(src_root: str, name: str) -> list[str]:
    """Every package above ``name`` that has an ``__init__.py`` under
    ``src_root`` (``a.b.c`` -> ``a``, ``a.b``)."""
    parts = name.split(".")
    found = []
    for i in range(1, len(parts)):
        pkg = ".".join(parts[:i])
        if os.path.isfile(os.path.join(src_root, *parts[:i], "__init__.py")):
            found.append(pkg)
    return found


def closure(src_root: str, entry_modules: _t.Iterable[str],
            prefixes: "_t.Collection[str] | None" = None, *,
            packages: bool = False) -> tuple[str, ...]:
    """The static import closure of ``entry_modules`` under ``src_root``
    (:func:`imports_of`, followed to a fixed point), entries included,
    sorted.  A package appears as its own name (its ``__init__``).

    ``packages``: also every package ABOVE a module in the closure — its
    ``__init__`` runs when the module is imported (issue #880) — and what
    that ``__init__`` imports, as Python loads it (``o4_engine``'s imports
    the app session).  Off by default: the stage, step and partition
    closures were declared without them."""
    seen: set[str] = set()
    stack = list(entry_modules)
    while stack:
        name = stack.pop()
        if name not in seen:
            seen.add(name)
            stack.extend(imports_of(src_root, name, prefixes))
            if packages:
                stack.extend(p for p in _parent_packages(src_root, name)
                             if _wanted(p, prefixes))
    return tuple(sorted(seen))


def digest_of(sources: _t.Iterable[tuple[str, "str | None"]]) -> str | None:
    """sha256 over ``name \\0 source bytes \\0`` of every ``(module name,
    source path)`` in order, or ``None`` when ANY source is missing or
    unreadable — a digest of some of the code is not a digest of the code."""
    h = hashlib.sha256()
    for name, src in sources:
        try:
            if not src or not os.path.isfile(src):
                return None
            with open(src, "rb") as fh:
                h.update(name.encode()); h.update(b"\0")
                h.update(fh.read()); h.update(b"\0")
        except OSError:
            return None
    return h.hexdigest()


def modules_digest(src_root: str, modules: _t.Iterable[str]) -> str | None:
    """:func:`digest_of` over ``modules`` read under ``src_root``, in the
    order given."""
    return digest_of((name, source_path(src_root, name)) for name in modules)


def write_digest_file(out_dir: str, filename: str,
                      digest: "str | _t.Mapping[str, str | None] | None",
                      refusal: str) -> str:
    """THE FREEZE'S ACT: write ``digest`` to ``out_dir/filename`` and
    return that path.  One digest is one line; a mapping is one ``name
    digest`` line per entry, sorted (:func:`read_digest_table`).  RAISES
    ``SystemExit(refusal)`` when there is no digest, or any entry has none
    — an engine frozen without its file would key on its version again,
    silently."""
    if isinstance(digest, _t.Mapping):
        if not digest or not all(digest.values()):
            raise SystemExit(refusal)
        text = "".join(f"{k} {digest[k]}\n" for k in sorted(digest))
    elif digest:
        text = digest + "\n"
    else:
        raise SystemExit(refusal)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    return path


def _sha(text: str) -> str | None:
    got = text.strip().lower()
    return got if len(got) == 64 and set(got) <= _HEX else None


def read_digest(directory: str, filename: str) -> str | None:
    """The one digest in ``directory/filename``, or ``None`` when the file
    is absent or is not one sha256 (a checkout; an engine frozen by a spec
    that predates it) — the caller then falls back."""
    try:
        with open(os.path.join(directory, filename), "r", encoding="ascii") as fh:
            return _sha(fh.read(256))
    except (OSError, ValueError):
        return None


def read_digest_table(directory: str, filename: str) -> dict[str, str] | None:
    """The ``{name: digest}`` table :func:`write_digest_file` wrote, or
    ``None`` when the file is absent or any line is not ``name sha256``."""
    try:
        with open(os.path.join(directory, filename), "r", encoding="ascii") as fh:
            lines = fh.read(1 << 16).splitlines()
    except (OSError, ValueError):
        return None
    table: dict[str, str] = {}
    for line in lines:
        parts = line.split()
        sha = _sha(parts[1]) if len(parts) == 2 else None
        if sha is None:
            return None
        table[parts[0]] = sha
    return table or None
