"""The resolution tiers of one orthophoto texture, and a tier cut from a
full DDS without a re-encode (#1992, local-imagery-cache spec §4.3, §4.6).

A texture built at zoom ``zl`` is 4096 px wide.  On demand it can stand on
disk at a lower TIER instead: the same square fetched ``drop`` zoom levels
coarser, ``4096 >> drop`` px wide, a whole DDS with its own full mip chain.
X-Plane reads the header of the file it opens, so a smaller file under the
full texture's name loads (spec §2.3).

* :data:`TIER_DROPS` are the tiers by drop: 3 (512 px, the placeholder),
  2 (1024), 1 (2048) and 0 (4096, full).
* :func:`tier_width` maps a drop to the file's width (the zoom its
  imagery comes from is ``O4_Imagery_Placeholder.fetch_zoom``: the drop,
  raised to the provider's ``min_source_zl``).
* :func:`tier_from_dds` is a lower tier of a full (or any larger) DDS:
  the same block data minus its top levels, re-headed
  (``O4_DDS_File.split_levels`` -> ``build_header`` -> ``assemble``).  A
  tier of a full texture is therefore byte for byte the full's own levels
  (the later on-demand phases land tiers through it, spec §14).
* :func:`tier_from_file` is the same cut read from a texture ON DISK,
  reading only the header and the levels it keeps (a 512 px tier of a
  4096 px BC1 file reads ~175 KB of its 11 MB): the converter of built
  tiles (``O4_Imagery_OnDemand_Convert``) and the lander's mounted-source
  path use it; :func:`tier_span` is where those levels lie (and so the
  tier's size) from the header alone.
* :func:`texture_header` reads the width and block format of a texture
  on disk from its header alone; :func:`is_dxt5` whether it carries alpha.

Standard library only.
"""
from __future__ import annotations

import os
import struct

import O4_DDS_File as DDS

__all__ = ["FULL_WIDTH", "TIER_DROPS", "is_dxt5", "texture_header",
           "tier_from_dds", "tier_from_file", "tier_span", "tier_width"]

#: Width of a texture built at its own zoom (16 x 16 map tiles of 256 px).
FULL_WIDTH = 4096
#: The tiers, coarsest first, by zoom levels below the build's.
TIER_DROPS = (3, 2, 1, 0)
#: ``DDSD_MIPMAPCOUNT``: the header's mip count is valid.
_MIPMAPCOUNT = 0x20000


def tier_width(drop: int) -> int:
    """Width in px of the tier ``drop`` zoom levels below the build's."""
    if drop not in TIER_DROPS:
        raise ValueError(f"no tier {drop} zoom levels below the build's")
    return FULL_WIDTH >> drop


def texture_header(path: str) -> "tuple[int, str | None] | None":
    """``(width, "bc1" | "bc3" | None)`` of the DDS at ``path`` from its
    header, or ``None`` when it cannot be read as a DDS."""
    try:
        with open(path, "rb") as handle:
            header = handle.read(DDS.HEADER_BYTES)
    except OSError:
        return None
    if len(header) < DDS.HEADER_BYTES or header[:4] != b"DDS ":
        return None
    (width,) = struct.unpack_from("<I", header, 16)
    fourcc = header[84:88]
    fmt = next((name for name, (cc, _) in DDS.BLOCK_FORMATS.items()
                if cc == fourcc), None)
    return width, fmt


def tier_from_dds(data, width: int) -> bytes:
    """The file image of the ``width`` px tier of the DDS image ``data``:
    its levels from ``width`` down, under a new header.  ``ValueError``
    when ``data`` is not square or ``width`` is not one of its levels."""
    (full_w, full_h, fmt), levels = DDS.split_levels(data)
    if full_w != full_h:
        raise ValueError("a tier is cut from a square texture")
    skip = 0
    while (full_w >> skip) > width:
        skip += 1
    if (full_w >> skip) != width or skip >= len(levels):
        raise ValueError(f"{width} px is not a level of a {full_w} px texture")
    return DDS.assemble(width, width, fmt, levels[skip:])


def tier_span(path: str, width: int) -> "tuple[str, int, list[int]] | None":
    """``(fmt, offset, [bytes per level])`` of the ``width`` px tier inside
    the DDS at ``path``: where its levels start and how long each is, read
    from the header alone; ``None`` when the file is not a square
    DXT1/DXT5 DDS whose mip chain holds a ``width`` px level (a file with
    no mips, or narrower than ``width``).  The tier's file is
    ``HEADER_BYTES + sum(sizes)`` long."""
    try:
        with open(path, "rb") as handle:
            header = handle.read(DDS.HEADER_BYTES)
    except OSError:
        return None
    if len(header) < DDS.HEADER_BYTES or header[:4] != b"DDS ":
        return None
    (flags, height, full_w) = struct.unpack_from("<III", header, 8)
    (mip_count,) = struct.unpack_from("<I", header, 28)
    fmt = next((name for name, (cc, _) in DDS.BLOCK_FORMATS.items()
                if cc == header[84:88]), None)
    count = max(mip_count, 1) if flags & _MIPMAPCOUNT else 1
    if fmt is None or full_w != height:
        return None
    dims = DDS.mip_dims(full_w, height, count)
    skip = next((k for k, (w, _h) in enumerate(dims) if w == width), None)
    if skip is None:
        return None
    offset = DDS.HEADER_BYTES + sum(DDS.level_size(w, h, fmt)
                                    for (w, h) in dims[:skip])
    return fmt, offset, [DDS.level_size(w, h, fmt) for (w, h) in dims[skip:]]


def tier_from_file(path: str, width: int) -> "bytes | None":
    """The file image of the ``width`` px tier of the DDS at ``path``, read
    from its header and its levels from ``width`` down only (a 512 px tier
    of a 4096 px BC1 file reads ~175 KB of its 11 MB); ``None`` as
    :func:`tier_span`, or when the file is shorter than its header says."""
    span = tier_span(path, width)
    if span is None:
        return None
    fmt, offset, sizes = span
    try:
        with open(path, "rb") as handle:
            handle.seek(offset)
            blob = handle.read(sum(sizes))
    except OSError:
        return None
    if len(blob) < sum(sizes):
        return None
    levels, start = [], 0
    for size in sizes:
        levels.append(blob[start:start + size])
        start += size
    return DDS.assemble(width, width, fmt, levels)


#: The size rule the scenery-file step judged a texture's format by before
#: it read headers: a 4096 px DXT5 is ~22 MB, a DXT1 ~11 MB.
_LEGACY_DXT5_BYTES = 20000000


def is_dxt5(path: str) -> bool:
    """Does the texture at ``path`` carry alpha (DXT5)?  Read from its
    header; a header this module cannot name falls back to the old size
    rule (a 4096 px DXT5 is over 20 MB)."""
    header = texture_header(path)
    if header is not None and header[1] is not None:
        return header[1] == "bc3"
    return os.path.getsize(path) >= _LEGACY_DXT5_BYTES
