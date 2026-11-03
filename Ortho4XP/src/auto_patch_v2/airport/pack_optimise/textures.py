"""O4 — A PACK OBJECT'S TEXTURES, LIGHTER (issue #1707, "Optimise pack").

Measured on one heavy airport pack (the frame-rate finding of
2026-10-30): its object textures were an estimated 4.5-5.2 GB of video
memory — 17 uncompressed 4K DDS files about 967 MB, 91 textures of 2K
and more serving only props under 12 m 1,135 MB, 68 byte-identical
copies 468 MB.  The owner's hand pass took the estimate from 4,517 MB to
3,027 MB.

THE RULES, per texture a placed pack object (that is not swapped) names
in its ``TEXTURE`` / ``TEXTURE_LIT`` row (X-Plane draws ``<stem>.dds``
when it sits beside a named ``.png``; a normal map is left alone):

* an UNCOMPRESSED DDS is encoded to BC1 (BC3 when its alpha is used)
  with its mips — no visible change;
* a PNG of 4096 px or more becomes such a DDS;
* a texture of 2048 px or more that ONLY objects under ``SMALL_M`` use is
  halved (a DDS with mips drops its first level; anything else is
  re-encoded at half size);
* byte-identical copies are read as ONE file: every object copy names
  the first (in path order).

The result is a NEW file beside the vendor's, ``<stem>.o4opt.dds`` (or
``<stem>.o4opt-half.dds``), written on every write that needs it and
current while its time is the vendor file's; the object copies
(``objcopy``) name it.  The plan is made once, when the user accepts
(:func:`plan_textures`), and recorded in the recipe.
"""
from __future__ import annotations

import hashlib
import os
import struct
import typing as _t

import numpy as np
import O4_DDS_Encode as _enc
import O4_DDS_File as _ddsf
from O4_DDS_Decode import decode_dds
from O4_DDS_Mips import mip_chain

from . import objcopy as _oc

__all__ = ["BIG_PX", "HUGE_PX", "plan_textures", "texture_refs", "write_texture",
           "vram_bytes", "out_path", "estimate_vram"]

#: a texture this wide or more, serving only small props, is halved
BIG_PX = 2048
#: a PNG this wide or more becomes a DDS
HUGE_PX = 4096
_REF_ROWS = ("TEXTURE", "TEXTURE_LIT")


class TexInfo(_t.NamedTuple):
    """One texture file: ``kind`` ``"dds"`` | ``"png"``, its size, its
    format (``"DXT1"``, ``"DXT5"``, ``"RGB"``, ``"RGBA"``, a PNG's mode)
    and its mip levels."""

    kind: str
    width: int
    height: int
    fmt: str
    mips: int


def texture_refs(phys: str) -> list[tuple[str, str]]:
    """``[(row keyword, path as written)]`` of an OBJ8's texture rows."""
    out = []
    with open(phys, encoding="latin-1") as fh:
        for raw in fh:
            toks = raw.split(None, 1)
            if not toks:
                continue
            if toks[0] == "POINT_COUNTS":
                break
            if toks[0] in _REF_ROWS and len(toks) > 1:
                out.append((toks[0], toks[1].strip()))
    return out


def effective(obj_phys: str, ref: str) -> str | None:
    """The file X-Plane loads for ``ref`` in ``obj_phys``: the ``.dds``
    beside a named ``.png`` first."""
    p = os.path.normpath(os.path.join(os.path.dirname(obj_phys),
                                      ref.replace("\\", "/")))
    stem, ext = os.path.splitext(p)
    if ext.lower() == ".png" and os.path.isfile(stem + ".dds"):
        return stem + ".dds"
    return p if os.path.isfile(p) else None


def info(path: str) -> TexInfo | None:
    """What :class:`TexInfo` the header says; ``None`` when unreadable."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(128)
    except OSError:
        return None
    if head[:4] == b"DDS " and len(head) >= 128:
        h, w = struct.unpack_from("<II", head, 12)
        mips = max(1, struct.unpack_from("<I", head, 28)[0])
        pf_flags = struct.unpack_from("<I", head, 80)[0]
        fourcc = head[84:88]
        if pf_flags & 0x4:
            fmt = fourcc.decode("latin-1")
        else:
            fmt = "RGBA" if pf_flags & 0x1 else "RGB"
        return TexInfo("dds", w, h, fmt, mips)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack_from(">II", head, 16)
        return TexInfo("png", w, h, {0: "L", 2: "RGB", 3: "P", 4: "LA", 6: "RGBA"}.get(
            head[25], "?"), 1)
    return None


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def out_path(path: str, halve: bool) -> str:
    stem, _ext = os.path.splitext(path)
    return stem + (".o4opt-half.dds" if halve else ".o4opt.dds")


def _pow2(n: int) -> bool:
    return n > 0 and not n & (n - 1)


def _action(t: TexInfo, small_only: bool) -> tuple[str, bool] | None:
    big = max(t.width, t.height) >= BIG_PX and small_only
    if not (_pow2(t.width) and _pow2(t.height)):
        return None
    if t.kind == "dds" and t.fmt in ("RGB", "RGBA"):
        return "encode", big
    if t.kind == "png" and (max(t.width, t.height) >= HUGE_PX or big):
        return "encode", big
    if t.kind == "dds" and big and t.fmt in ("DXT1", "DXT5"):
        return "halve", True
    return None


def plan_textures(pack_root: str, objects: _t.Iterable[tuple[str, float]]
                  ) -> tuple[dict[str, dict[str, _t.Any]], dict[str, dict[str, str]]]:
    """THE PLAN for the placed pack objects ``objects`` (``(declared
    path, size m)``): ``({texture: {"act", "halve", "to"}}, {object:
    {path as written: new path as written}})`` — every path
    pack-relative but the rows' own, which are relative to their object."""
    root = os.path.abspath(pack_root)
    users: dict[str, list[tuple[str, str, str, float]]] = {}
    for path, size in objects:
        phys = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
        for kw, ref in texture_refs(phys):
            eff = effective(phys, ref)
            if eff is None or not os.path.abspath(eff).startswith(root + os.sep):
                continue
            users.setdefault(eff, []).append((path, kw, ref, size))
    infos = {e: info(e) for e in users}
    groups: dict[str, list[str]] = {}
    for e in sorted(users):
        if infos[e] is not None:
            groups.setdefault(_sha(e), []).append(e)
    textures: dict[str, dict[str, _t.Any]] = {}
    final: dict[str, str] = {}
    for members in groups.values():
        canon = members[0]
        small = all(u[3] < _oc.SMALL_M for m in members for u in users[m])
        act = _action(infos[canon], small)
        target = canon
        if act is not None:
            target = out_path(canon, act[1])
            textures[_rel(root, canon)] = {"act": act[0], "halve": act[1],
                                          "to": _rel(root, target)}
        for m in members:
            final[m] = target
    rewrites: dict[str, dict[str, str]] = {}
    for eff, rows in users.items():
        target = final.get(eff, eff)
        if target == eff:
            continue
        for path, _kw, ref, _size in rows:
            phys = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
            new = os.path.relpath(target, os.path.dirname(phys)).replace(os.sep, "/")
            rewrites.setdefault(path, {})[ref] = new
    return textures, rewrites


def _rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def _rgba(src: str, t: TexInfo) -> np.ndarray:
    """The top level of a texture as ``(h, w, 4)`` uint8."""
    if t.kind == "png":
        from PIL import Image
        with Image.open(src) as im:
            return np.asarray(im.convert("RGBA"))
    data = open(src, "rb").read()
    if t.fmt in ("DXT1", "DXT5"):
        return decode_dds(data)[0]
    pitch_bits = struct.unpack_from("<I", data, 88)[0]
    masks = struct.unpack_from("<4I", data, 92)
    bpp = pitch_bits // 8
    a = np.frombuffer(data, np.uint8, t.width * t.height * bpp, 128).reshape(
        t.height, t.width, bpp)
    out = np.full((t.height, t.width, 4), 255, np.uint8)
    for ch, mask in enumerate(masks):
        if mask:
            out[..., ch] = a[..., (mask.bit_length() - 1) // 8]
    if t.fmt == "RGB":
        out[..., 3] = 255
    return out


def write_texture(pack_root: str, rel: str, plan: _t.Mapping[str, _t.Any]) -> None:
    """Write one planned texture beside the vendor's, unless the one there
    is current (its time is the vendor file's)."""
    src = os.path.join(pack_root, *rel.split("/"))
    dst = os.path.join(pack_root, *str(plan["to"]).split("/"))
    st = os.stat(src)
    try:
        if os.stat(dst).st_mtime_ns == st.st_mtime_ns:
            return
    except OSError:
        pass
    t = info(src)
    if t is None:
        raise ValueError(f"{rel}: the texture can no longer be read")
    if plan["act"] == "halve" and t.mips > 1:
        (w, h, fmt), levels = _ddsf.split_levels(open(src, "rb").read())
        data = _ddsf.assemble(w // 2, h // 2, fmt, [bytes(x) for x in levels[1:]])
    else:
        rgba = _rgba(src, t)
        fmt = "bc3" if int(rgba[..., 3].min()) < 255 else "bc1"
        if plan["act"] == "halve":
            fmt = "bc1" if t.fmt == "DXT1" else "bc3"
        levels = mip_chain(rgba, mode=_enc.DEFAULT_MIP_MODE)
        if plan.get("halve"):
            levels = levels[1:]
        data = _ddsf.assemble(levels[0].shape[1], levels[0].shape[0], fmt,
                              [_enc.encode_level(lv, fmt) for lv in levels])
    tmp = dst + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, dst)
    os.utime(dst, ns=(st.st_atime_ns, st.st_mtime_ns))


def vram_bytes(path: str) -> int:
    """The video memory a texture takes, estimated from its header (with
    mips; a PNG is read as BC3)."""
    t = info(path)
    if t is None:
        return 0
    per_px = {"DXT1": 0.5, "DXT3": 1.0, "DXT5": 1.0}.get(t.fmt, 4.0) \
        if t.kind == "dds" else 1.0
    return int(t.width * t.height * per_px * 4 / 3)



def estimate_vram(pack_root: str, before: _t.Iterable[str], after: _t.Iterable[str],
                  plan: _t.Mapping[str, _t.Mapping[str, _t.Any]]) -> tuple[int, int]:
    """The video memory (bytes, :func:`vram_bytes`) of the textures the
    placed pack objects ``before`` name, and of those ``after`` name once
    ``plan`` is written (a planned texture as its BC1/BC3 result, halved
    where planned; a byte-identical copy counted once)."""
    root = os.path.abspath(pack_root)

    def files(objects):
        out = set()
        for path in objects:
            phys = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
            for _kw, ref in texture_refs(phys):
                eff = effective(phys, ref)
                if eff is not None:
                    out.add(eff)
        return out

    first = sum(vram_bytes(f) for f in files(before))
    seen: set[str] = set()
    second = 0
    for f in sorted(files(after)):     # the first of identical copies is planned
        sha = _sha(f)
        if sha in seen:
            continue
        seen.add(sha)
        row = plan.get(_rel(root, f))
        t = info(f)
        if row is None or t is None:
            second += vram_bytes(f)
            continue
        k = 2 if row.get("halve") else 1
        alpha = t.fmt in ("RGBA", "DXT5", "LA") or (t.kind == "png" and t.fmt == "RGBA")
        second += int((t.width // k) * (t.height // k) * (1.0 if alpha else 0.5) * 4 / 3)
    return first, second
