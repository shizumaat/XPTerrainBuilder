"""Telling failures apart: transient, mis-configured, over the cap, signed out.

A strategy must never turn "the network hiccupped" into a durable
"this provider has no data here".  These helpers classify an error
message and build the refusals every strategy words the same way.
"""

import os

import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable

__all__ = [
    "_warn_sign_in_needed_once",
    "cap_exceeded_unavailable",
    "error_message_indicates_grid_configuration_failure",
    "error_message_indicates_transient_network_failure",
]


def cap_exceeded_unavailable(definition, needs_text, cap_text, cap_key,
                             destination_path=None):
    """THE CAP CLASS (spec us-holder-providers §1/§3, RULINGS 2026-09-30bm):
    a per-airport cap exceeded is ``unavailable`` -- the engine declined
    to ask -- never a durable no-coverage (``None``) and never a silent
    truncation of the listing.  One wording for every strategy, the LAS
    strategy's (``max_tiles_per_airport`` / ``max_bytes_per_airport``)."""
    code = definition.get("code") or "elevation provider"
    airport = (" " + os.path.basename(str(destination_path)).split("_", 1)[0]
               if destination_path else "")
    return ProviderUnavailable(
        "%s:%s needs %s, cap %s (%s in %s.elv) — SKIPPED, recorded "
        "unavailable, not no-coverage"
        % (code, airport, needs_text, cap_text, cap_key, code))


# Substrings (lower-cased) of libcurl / GDAL HTTP error messages that mean
# "the network or the server had a bad moment", not "there is no data
# here".  Matched against the stringified GDAL exception; anything else is
# treated as a durable answer as before.
_TRANSIENT_NETWORK_ERROR_FRAGMENTS = (
    # libcurl CURLE_OPERATION_TIMEDOUT ("Operation timed out after 30000
    # milliseconds with 20607784 bytes received") and connect timeouts.
    "timed out",
    "timeout was reached",
    # Connection-level failures.
    "connection reset",
    "connection was reset",
    "failed to connect",
    "could not resolve host",
    "recv failure",
    "transfer closed",
    "empty reply from server",
    # Server-side conditions worth retrying; GDAL formats these as
    # "HTTP error code : 503".
    "http error code : 5",
    "http error code: 5",
    "service unavailable",
    # Rate limiting says "come back later", never "no data here"; the
    # same swisstopo throttling that poisoned the search path surfaces
    # from the warp path as a 429.
    "http error code : 429",
    "http error code: 429",
    "too many requests",
    # TRANSPORT SECURITY (issue #121, lane win121).  A TLS handshake or a
    # certificate verification that fails says the CLIENT could not talk
    # to the server -- a TLS-intercepting antivirus or proxy, a damaged or
    # stale root store, a clock off by a year -- and NOTHING about
    # coverage.  Measured on the shipped beta.1 exe on windows-latest
    # with an unrelated CA bundle (run 36661272964): GDAL's libcurl
    # (Schannel) said "schannel: the certificate or certificate chain is
    # based on an untrusted root", ``requests`` said "SSLError(...
    # CERTIFICATE_VERIFY_FAILED ...)", and BOTH became a DURABLE
    # SPAIN5M / COPERNICUSGLO30 "no-coverage" that no later run re-asked.
    "schannel",
    "ssl",
    "certificate",
    "sec_e_",
    "crypt_e_",
    # ``requests``/urllib3 connection-establishment failures (DNS, refused,
    # proxy): no HTTP answer was ever received.
    "max retries exceeded",
    "failed to establish a new connection",
    "name or service not known",
    "getaddrinfo failed",
    "nameresolutionerror",
    "proxyerror",
    "unable to connect to proxy",
)


def error_message_indicates_transient_network_failure(message):
    """Does an error message describe a retryable network/server failure?"""
    lowered = str(message).lower()
    return any(
        fragment in lowered
        for fragment in _TRANSIENT_NETWORK_ERROR_FRAGMENTS
    )


# GDAL failures that describe the RETURNED GRID rather than the data.  The
# WCS driver derives the cell count it expects from DescribeCoverage and
# fails the whole read when the server's GetCoverage answer disagrees by
# even one row or column.  Measured live 2026-08-24 against
# servicios.idee.es (SPAIN5M): DescribeCoverage advertises a 0.000045 deg
# posting while GetCoverage answers on a ~0.00004505 deg grid, so every
# window wider than about 400 cells came back exactly one row and one
# column short ("Got 1111x823 instead of 1112x824") -- and all thirteen
# airports of tile +40-004, Madrid Barajas included, recorded a DURABLE
# "SPAIN5M has no coverage here" negative for a protocol disagreement that
# says NOTHING about coverage.  Same law as the discovery classifier
# below: this is a "come back later", never a "no data here".
_GRID_CONFIGURATION_ERROR_FRAGMENTS = (
    "does not match expected configuration",
    "does not match expected band count",
    "does not match expected band configuration",
)


def error_message_indicates_grid_configuration_failure(message):
    """Does an error message describe a returned-grid disagreement?

    True for the WCS driver's tile-shape refusals, which are about the
    server's grid arithmetic and never about coverage, so callers must
    treat them as retryable instead of writing a durable no-coverage
    negative.
    """
    lowered = str(message).lower()
    return any(
        fragment in lowered
        for fragment in _GRID_CONFIGURATION_ERROR_FRAGMENTS
    )


# Providers whose ensure-session failed already this run: warn ONCE per
# provider, not once per airport.
_SIGN_IN_WARNED_PROVIDERS = set()


def _warn_sign_in_needed_once(definition, error):
    """Surface a LoginError loudly, once per provider per run."""
    provider_code = definition.get("code")
    if provider_code not in _SIGN_IN_WARNED_PROVIDERS:
        _SIGN_IN_WARNED_PROVIDERS.add(provider_code)
        UI.vprint(0, "   WARNING:", str(error))
