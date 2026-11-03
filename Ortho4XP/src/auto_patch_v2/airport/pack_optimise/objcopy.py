"""O1 + O2 — A PACK OBJECT'S LIGHTER COPY (issue #1707, "Optimise pack").

Measured on one heavy airport pack (the frame-rate finding of
2026-10-30): about 98 % of its triangles were on objects under 12 m,
none of which had a draw distance, and an ``ATTR_shiny_rat`` midway
through its cars (7,184 placements) keeps X-Plane from instancing them.
The owner's sim reads (2026-10-30/31): a draw distance of 1000 x size
clamped to 400-1,500 m, with the library swap, took the pack from 15 to
26-30 fps.

THE COPY (never the vendor file): ``<stem>.o4opt.obj`` beside the
vendor's, so its texture paths still resolve, which the optimised DSF
names instead (D3, :func:`rename_rows`):

* O1 — every ``ATTR_shiny_rat`` goes and the file's specular becomes
  one ``GLOBAL_specular`` (the largest it used), so the object can be
  instanced;
* O4 — its texture rows name the lighter textures (``textures``);
* O2 — an object under :data:`SMALL_M` with no draw distance of its own
  gets ``ATTR_LOD 0 D``, ``D`` = :data:`LOD_PER_M` x its size clamped to
  :data:`LOD_MIN_M`-:data:`LOD_MAX_M`, and its lights outside any
  animation are drawn again in a tail block ``ATTR_LOD D 20000`` so they
  stay visible past it; an object with a light inside an animation keeps
  no draw distance.

What a copy gets is decided once, when the user accepts
(:func:`plan_objects`), and recorded in the recipe; the copy is written
from the vendor file on every write that needs it (``write_generated``).
"""
from __future__ import annotations

import hashlib
import json
import os
import typing as _t

from . import shape as _sh

__all__ = ["COPY_SUFFIX", "SMALL_M", "LOD_PER_M", "LOD_MIN_M", "LOD_MAX_M",
           "MIN_WEIGHT", "placed_objects", "plan_objects", "copy_path",
           "copy_text", "rename_rows"]

#: the copy of ``<stem>.obj``
COPY_SUFFIX = ".o4opt.obj"
#: an object whose largest dimension is under this gets a draw distance
SMALL_M = 12.0
#: owner 2026-10-31: 1000 x size, clamped to 400-1,500 m
LOD_PER_M, LOD_MIN_M, LOD_MAX_M = 1000.0, 400.0, 1500.0
#: the far end of the lights' tail block (X-Plane's own distance)
LIGHTS_FAR_M = 20000
#: an object drawing fewer triangles than this across the tile is not
#: worth a copy for its draw distance
MIN_WEIGHT = 100_000
_HEADER = frozenset({"I", "A", "800", "OBJ", "POINT_COUNTS", "VT", "VLINE",
                     "VLIGHT", "IDX", "IDX10"})
#: attributes X-Plane reads before the first LOD
_BEFORE_LOD = frozenset({"ATTR_layer_group", "ATTR_layer_group_draped",
                         "ATTR_LOD_draped"})


def copy_path(path: str) -> str:
    """The copy of the declared ``path``."""
    stem, _ext = os.path.splitext(path)
    return stem + COPY_SUFFIX


def _lod_distance(size_m: float) -> int:
    return int(round(min(LOD_MAX_M, max(LOD_MIN_M, LOD_PER_M * size_m))))


def _scan(phys: str) -> tuple[list[float], list[float], bool, bool]:
    """``(ATTR_shiny_rat values, GLOBAL_specular values, has an ATTR_LOD,
    has a light inside an ANIM)``."""
    shiny: list[float] = []
    glob: list[float] = []
    lod = anim_light = False
    depth = 0
    with open(phys, encoding="latin-1") as fh:
        for raw in fh:
            toks = raw.split()
            if not toks:
                continue
            kw = toks[0]
            if kw in ("ATTR_shiny_rat", "GLOBAL_specular") and len(toks) > 1:
                try:
                    (shiny if kw == "ATTR_shiny_rat" else glob).append(float(toks[1]))
                except ValueError:
                    pass
            elif kw == "ATTR_LOD":
                lod = True
            elif kw == "ANIM_begin":
                depth += 1
            elif kw == "ANIM_end":
                depth = max(0, depth - 1)
            elif kw.startswith("LIGHT") and depth:
                anim_light = True
    return shiny, glob, lod, anim_light


def placed_objects(pack_root: str, defs: _t.Sequence[str],
                   uses: _t.Mapping[int, int], skip: _t.AbstractSet[str]
                   ) -> dict[str, tuple[_sh.Shape, int]]:
    """``{declared path: (shape, placements)}`` of the placed pack objects
    a copy may be made of: the pack's own ``.obj`` files, not in ``skip``,
    not one of our body files or copies."""
    out: dict[str, tuple[_sh.Shape, int]] = {}
    for d, n in sorted(uses.items()):
        path = defs[d]
        if (path in skip or not path.lower().endswith(".obj")
                or "__b" in os.path.basename(path) or ".o4opt" in path):
            continue
        phys = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
        s = _sh.read_shape(phys) if os.path.isfile(phys) else None
        if s is not None:
            prev = out.get(path)
            out[path] = (s, n + (prev[1] if prev else 0))
    return out


def plan_objects(pack_root: str, placed: _t.Mapping[str, tuple[_sh.Shape, int]]
                 ) -> dict[str, dict[str, _t.Any]]:
    """``{declared path: {"specular": value | None, "lod": D | None}}``
    for every placed object (:func:`placed_objects`) the copy changes: O1
    for an object placed more than once, O2 for one drawing at least
    :data:`MIN_WEIGHT` triangles on the tile."""
    out: dict[str, dict[str, _t.Any]] = {}
    for path, (s, n) in sorted(placed.items()):
        phys = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
        shiny, glob, has_lod, anim_light = _scan(phys)
        spec = round(max(shiny + glob), 4) if shiny and n >= 2 else None
        size = max(s.size)
        lod = (_lod_distance(size) if size < SMALL_M and not has_lod
               and not anim_light and s.tris * n >= MIN_WEIGHT else None)
        if spec is not None or lod:
            out[path] = {"specular": spec, "lod": lod}
    return out


def stamp(phys: str, params: _t.Mapping[str, _t.Any]) -> str:
    """What a copy is written from: the vendor file's size and time and
    the params (a copy carrying it is current)."""
    st = os.stat(phys)
    h = hashlib.sha256(f"{st.st_size}:{st.st_mtime_ns}:".encode())
    h.update(json.dumps(dict(params), sort_keys=True).encode())
    return h.hexdigest()[:20]


def copy_text(phys: str, params: _t.Mapping[str, _t.Any]) -> str:
    """The copy of the vendor file ``phys`` (read and written as latin-1,
    so every byte is the vendor's but the rows the copy changes)."""
    with open(phys, encoding="latin-1", newline="") as fh:
        raw = fh.read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)
    spec = params.get("specular")
    if spec is not None:
        lines = [ln for ln in lines if ln.split()[:1] != ["ATTR_shiny_rat"]
                 and ln.split()[:1] != ["GLOBAL_specular"]]
        pc = next(i for i, ln in enumerate(lines)
                  if ln.split()[:1] == ["POINT_COUNTS"])
        lines.insert(pc, f"GLOBAL_specular {spec:g}")
    tex = params.get("tex") or {}
    if tex:
        lines = [_retextured(ln, tex) for ln in lines]
    lod = params.get("lod")
    if lod:
        lines = _with_lod(lines, int(lod))
    head = lines[:3] + [f"# o4opt {stamp(phys, params)}"] + lines[3:]
    return eol.join(head)


def _retextured(line: str, tex: _t.Mapping[str, str]) -> str:
    """A ``TEXTURE`` / ``TEXTURE_LIT`` row naming the O4 texture (O4,
    ``textures``) instead of the vendor's; any other row as it is."""
    toks = line.split(None, 1)
    if len(toks) == 2 and toks[0] in ("TEXTURE", "TEXTURE_LIT"):
        ref = toks[1].strip()
        if ref in tex:
            return f"{toks[0]}\t{tex[ref]}"
    return line


def _with_lod(lines: list[str], lod: int) -> list[str]:
    """The commands inside ``ATTR_LOD 0 lod``, and the lights outside
    any animation again in ``ATTR_LOD lod 20000``."""
    pc = next(i for i, ln in enumerate(lines) if ln.split()[:1] == ["POINT_COUNTS"])
    i = pc + 1
    while i < len(lines) and _header(lines[i]):
        i += 1
    while i < len(lines) and (not lines[i].split()
                              or lines[i].split()[0] in _BEFORE_LOD):
        i += 1
    cmds = lines[i:]
    tail: list[str] = []
    while cmds and not cmds[-1].strip():
        tail.append(cmds.pop())
    depth = 0
    lights: list[str] = []
    for ln in cmds:
        toks = ln.split()
        if not toks:
            continue
        if toks[0] == "ANIM_begin":
            depth += 1
        elif toks[0] == "ANIM_end":
            depth = max(0, depth - 1)
        elif not depth and (toks[0] in _sh.LIGHT_ROWS or toks[0] == "LIGHTS"):
            lights.append(ln.strip())
    out = lines[:i] + [f"ATTR_LOD 0 {lod}"] + cmds
    if lights:
        out += [f"ATTR_LOD {lod} {LIGHTS_FAR_M}"] + lights
    return out + tail[::-1]


def _header(line: str) -> bool:
    toks = line.split()
    return (not toks or toks[0] in _HEADER or toks[0].startswith("GLOBAL_")
            or toks[0].startswith("TEXTURE") or toks[0].startswith("#")
            or toks[0] in ("NORMAL_METALNESS", "BLEND_GLASS", "TILTED",
                           "REQUIRE_WET", "REQUIRE_DRY", "PARTICLE_SYSTEM",
                           "SLUNG_LOAD_WEIGHT", "SPECULAR", "BUMP_LEVEL",
                           "NO_BLEND", "ONE_SIDED", "NO_SHADOW", "COCKPIT_REGION"))


def rename_rows(text: str, copies: _t.Mapping[str, _t.Any]) -> tuple[str, int]:
    """D3 (pure): ``text`` with each ``OBJECT_DEF`` that has a copy naming
    it instead; every row keeps its index.  Returns the text and the
    definitions renamed."""
    if not copies:
        return text, 0
    out: list[str] = []
    n = 0
    for raw in text.splitlines(keepends=True):
        if raw.startswith("OBJECT_DEF "):
            path = raw[len("OBJECT_DEF "):].strip()
            if path in copies:
                end = raw[len(raw.rstrip("\r\n")):]
                out.append(f"OBJECT_DEF {copy_path(path)}{end}")
                n += 1
                continue
        out.append(raw)
    return "".join(out), n
