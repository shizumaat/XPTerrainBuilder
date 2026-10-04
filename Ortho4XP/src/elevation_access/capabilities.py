"""What THIS run can decode: LERC, LAS and LAZ.

A provider skipped because the engine lacks a decoder is recorded as
``unavailable:`` and re-probed by an engine that has it -- never as a
durable no-coverage.  These are the capability names and their probes.
"""

import os

__all__ = [
    "CAPABILITY_LAS",
    "CAPABILITY_LAZ",
    "CAPABILITY_LERC",
    "_definition_needs_laz",
    "las_reader_available",
    "laz_reader_available",
    "lerc_decode_available",
    "lerc_selftest_argv",
    "lerc_worker_argv",
]


#: THE LERC DECODE WORKER (owner RULINGS 2026-09-12as (3)).  The decode
#: is a SUBPROCESS because imagecodecs' LERC decoder and the osgeo
#: shared libraries abort a process that loads both; the code it runs is
#: ``src/O4_LERC_Decode.py``, which imports no GDAL and which the frozen
#: bundle carries (Ortho4XP.spec pins tifffile / imagecodecs).
_LERC_DECODE_MODULE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "O4_LERC_Decode.py")                 # src/, one level above this package


def lerc_worker_argv(source, destination):
    """The argv that decodes ``source`` (a LERC GeoTIFF, or a directory
    of ``.lerc`` blobs) into ``destination``.

    From source that is ``python src/O4_LERC_Decode.py IN OUT``; frozen
    it is the engine's own binary with the internal ``--lerc-decode``
    argv, dispatched in ``Ortho4XP.py`` ahead of the heavy imports.
    Before this the packaged engine had no decoder at all and NEW
    ZEALAND's 1 m lidar silently degraded to the base tier.
    """
    import sys

    if getattr(sys, "frozen", False):
        return [sys.executable, "--lerc-decode", source, destination]
    return [sys.executable, _LERC_DECODE_MODULE, source, destination]


def lerc_selftest_argv():
    """The same worker argv, asking only "can you decode LERC at all?".

    The worker imports ``tifffile`` and ``imagecodecs`` at module level,
    so a clean exit IS the capability answer -- no fixture, no file, no
    network.
    """
    argv = lerc_worker_argv("IN", "OUT")
    return argv[:-2] + ["--selftest"]


# =====================================================================
# WHAT THIS RUN IS CAPABLE OF (owner RULINGS 2026-09-13b (2))
# =====================================================================
# The index used to record WHAT a provider answered and never WHAT THE
# RUN COULD ASK.  Those are different facts, and conflating them is how
# a 1.0.324 engine with no LERC decoder wrote a permanent "New Zealand
# has no 1 m lidar at NZQN".  From now on every durable status written
# for a CAPABILITY-GATED provider carries the engine version and the
# capability set of the run that wrote it, and a pre-existing negative
# with no such record is UNVERIFIED -- re-probed exactly once.
CAPABILITY_LERC = "lerc"


#: Reading LAS point-cloud tiles (``laspy``) -- the ``las_tile_index``
#: strategy (#130, spec ``las-tile-lidar-provider-spec.md`` §1).  An engine
#: without it records ``unavailable:`` and re-probes once it has it (the
#: 13b door), never a durable no-coverage.
CAPABILITY_LAS = "las"


#: Decompressing LAZ point clouds (``lazrs``, laspy's Rust backend) -- a
#: ``las_tile_index`` provider declaring ``point_compression=laz`` (the
#: USGS Lidar Point Cloud rung, #153).  Missing -> ``unavailable:`` and
#: the ladder climbs on; re-probed once the engine has it (13b).
CAPABILITY_LAZ = "laz"


#: Memo for the LERC capability probe: ``[None]`` until probed.
_LERC_CAPABILITY = [None]


def las_reader_available():
    """Can THIS process read LAS tiles?  True when ``laspy`` imports.

    In-process (unlike LERC, no library conflict): the import IS the
    capability answer, for the frozen engine too.
    """
    try:
        import laspy  # noqa: F401
    except Exception:
        return False
    return True


def laz_reader_available():
    """Can THIS process DECOMPRESS LAZ tiles?  True when laspy finds a
    LAZ backend (``lazrs``) -- in-process, so the import is the answer
    for the frozen engine too."""
    try:
        import laspy

        return any(backend.is_available() for backend in laspy.LazBackend)
    except Exception:
        return False


def _definition_needs_laz(definition):
    """``point_compression=laz``: the provider's tiles are LAZ."""
    return str((definition or {}).get("point_compression", "")).strip() \
        .lower() == "laz"


def lerc_decode_available():
    """Can THIS process decode LERC?  Probed once, memoised.

    Runs the production worker argv with ``--selftest``, so the answer is
    about the exact interpreter/binary a real decode would spawn -- the
    frozen engine included.  A child that cannot import the codecs exits
    non-zero and the answer is False.
    """
    if _LERC_CAPABILITY[0] is None:
        import subprocess

        try:
            completed = subprocess.run(
                lerc_selftest_argv(),
                capture_output=True,
                text=True,
                timeout=120,
            )
            _LERC_CAPABILITY[0] = completed.returncode == 0
        except Exception:
            _LERC_CAPABILITY[0] = False
    return _LERC_CAPABILITY[0]
