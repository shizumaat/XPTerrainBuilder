"""DSF point-pool quantization must survive deep quadtree pools (#18).

``build_dsf`` stores each vertex as the 16 bits that follow its pool's
L-bit quadtree key.  The address used to carry 24 bits, so a pool deeper
than level 8 read fewer than 16 bits and wrote them as the low bits of a
16-bit fraction: NLWF's 1.47 M-triangle island mesh (532 k nodes in
level-14 pools) came out of the encoder with its vertices a median 5.9 m
(max 148.7 m) off the mesh — the ridge across the runway and the terraced
threshold bars of the owner's sim read.  Headless, no tile build.
"""
import random

import O4_DSF_Utils as DSF


def _encode_decode(points, bucket_size):
    """Pool the points exactly as ``build_dsf`` does, then decode them the
    way X-Plane does (origin + icoord / 65535 * 2**-L)."""
    q = DSF.QuadTree(DSF.quad_init_level, bucket_size)
    for x, y in points:
        q.insert(DSF.float2qquad(x), DSF.float2qquad(y), DSF.quad_init_level)
    q.clean()
    out = {}
    for key in q:
        level = len(key[0])
        scale = 2.0 ** -level
        ox, oy = int(key[0], 2) * scale, int(key[1], 2) * scale
        for idx in q[key]["idx_nodes"]:
            bx, by = q.nodes[idx]
            out[idx] = (
                level,
                ox + DSF.pool_icoord(bx, level) / 65535 * scale,
                oy + DSF.pool_icoord(by, level) / 65535 * scale,
            )
    return out


def test_deep_pools_decode_onto_their_vertices():
    rng = random.Random(18)
    # A 2 m cluster (the NLWF class): a tiny bucket forces the cap level.
    base_x, base_y = 0.9285, 0.6883
    pts = [(base_x + rng.random() * 2e-5, base_y + rng.random() * 2e-5)
           for _ in range(400)]
    dec = _encode_decode(pts, bucket_size=4)
    deepest = max(level for level, _, _ in dec.values())
    assert deepest == DSF.QUAD_MAX_LEVEL
    for idx, (x, y) in enumerate(pts):
        level, dx, dy = dec[idx]
        tol = 2.0 ** -level / 65535 * 2          # two quantization steps
        assert abs(dx - x) <= tol and abs(dy - y) <= tol, (idx, level)


def test_every_level_reads_sixteen_bits():
    for level in range(DSF.QUAD_MAX_LEVEL + 1):
        assert len(DSF.float2qquad(0.123456789)[level:level + 16]) == 16
    assert DSF.float2qquad(1.0) == "1" * DSF.QQUAD_BITS


def test_shallow_addresses_are_the_old_prefix():
    """Levels <= 8 read bits 0..23, identical to the 24-bit address, so
    every tile that never pooled deeper than 8 encodes byte-identically."""
    rng = random.Random(7)
    for _ in range(2000):
        x = rng.random()
        old = format(int(16777216 * x), "024b")
        assert DSF.float2qquad(x)[:24] == old
