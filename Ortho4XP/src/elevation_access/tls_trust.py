"""Per-provider extra certificate authorities for ``requests`` (issue #1923).

Some hosts send only their leaf certificate and leave the intermediate
out.  A browser fetches the missing intermediate through the leaf's AIA
"CA Issuers" URL; Python's ``ssl`` (and ``truststore`` on macOS) does
not, so every request fails verification -- the Schleswig-Holstein
``geodaten`` host since its 2026-09 certificate.  Verification is NEVER
disabled: the definition names the missing intermediate, shipped under
``Providers/Elevation/ca/`` and pinned by the SHA-256 of its DER bytes::

    tls_extra_ca=D-TRUST_BR_CA_1-20-1_2020.pem
    tls_extra_ca_sha256=199ab2aa...

and :func:`requests_verify` hands ``requests`` a bundle of certifi's
roots plus that intermediate, for that provider's requests only.  The
same bundle serves both HTTPS stacks Python may run on: plain OpenSSL
(the venv; it needs certifi's root to close the chain) and ``truststore``
(the frozen engine, which loads the bundle as extra anchors on macOS and
Windows).  A missing file or a pin mismatch refuses the provider rather
than falling back to an unverified or unextended request.
"""

import base64
import functools
import hashlib
import os
import ssl
import tempfile

import O4_File_Names as FNAMES

from elevation_access.base import ProviderUnavailable

__all__ = ["requests_verify"]


def extra_ca_path(file_name):
    """The shipped PEM ``file_name`` under ``Providers/Elevation/ca``."""
    return os.path.join(FNAMES.Provider_dir, "Elevation", "ca", file_name)


def requests_verify(definition):
    """``verify=`` for this provider's ``requests`` calls.

    ``True`` (requests' default) when the definition names no extra CA;
    otherwise the path of the certifi + pinned-intermediate bundle.
    Raises :class:`ProviderUnavailable` when the shipped PEM is missing,
    unreadable or does not match its pin.
    """
    file_name = str(definition.get("tls_extra_ca", "")).strip()
    if not file_name:
        return True
    pin = str(definition.get("tls_extra_ca_sha256", "")).strip().lower()
    return _bundle_path(extra_ca_path(file_name), pin.replace(":", ""))


@functools.cache
def _bundle_path(pem_path, pin):
    """Write (once) and return certifi's roots + the pinned PEM."""
    try:
        with open(pem_path, "r", encoding="ascii") as handle:
            der = ssl.PEM_cert_to_DER_cert(handle.read())
    except (OSError, ValueError, UnicodeDecodeError) as error:
        raise ProviderUnavailable(
            "extra certificate authority %s could not be read: %s"
            % (pem_path, error)) from error
    digest = hashlib.sha256(der).hexdigest()
    if not pin or digest != pin:
        raise ProviderUnavailable(
            "extra certificate authority %s has SHA-256 %s, not its pin %s"
            " - refused, verification is never weakened"
            % (pem_path, digest, pin or "(none)"))
    import certifi

    with open(certifi.where(), "r", encoding="utf-8") as handle:
        roots = handle.read()
    body = roots.rstrip("\n") + "\n" + _canonical_pem(der)
    directory = os.path.join(tempfile.gettempdir(), "xptb_extra_ca")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(
        directory,
        hashlib.sha256(body.encode("utf-8")).hexdigest()[:16] + ".pem")
    if not os.path.exists(path):
        scratch = "%s.%d.tmp" % (path, os.getpid())
        with open(scratch, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        os.replace(scratch, path)
    return path


def _canonical_pem(der):
    """DER bytes as one PEM block (64-column base64)."""
    text = base64.b64encode(der).decode("ascii")
    lines = [text[i:i + 64] for i in range(0, len(text), 64)]
    return ("-----BEGIN CERTIFICATE-----\n" + "\n".join(lines)
            + "\n-----END CERTIFICATE-----\n")
