"""Test-raster helper: give a synthetic inset a few centimetres of relief.

A raster whose valid pixels carry no relief is a provider FILL, not
elevation data (#1171, ``elevation_access.warp.inset_carries_no_relief``),
and the engine declines it.  Fixtures that stand for a REAL inset pass
their array through :func:`with_relief` so they stay elevation data; the
added ramp (0 to ``metres`` west to east) is far below every tolerance
the tests assert.
"""

import numpy


def with_relief(values, nodata, metres=0.02):
    """``values`` with a west-to-east ramp of ``metres`` on valid pixels."""
    values = numpy.array(values, dtype=numpy.float64)
    if values.ndim != 2 or values.shape[1] < 2:
        return values
    ramp = numpy.linspace(0.0, metres, values.shape[1])[None, :]
    valid = numpy.isfinite(values)
    if nodata is not None:
        valid &= values != nodata
    return numpy.where(valid, values + ramp, values)
