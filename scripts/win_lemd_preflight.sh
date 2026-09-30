#!/usr/bin/env bash
# Pre-flight probes for .github/workflows/win-lemd-elevation.yml (issue #121).
# Never fails the job: every probe is RECORDED (to the log and to
# <logs>/preflight.txt) so a red LEMD pass can be read against it.
#
# Usage: scripts/win_lemd_preflight.sh <bundle-dir> <logs-dir>
set -uo pipefail
BUNDLE="${1:?bundle dir}"
LOGS="${2:?logs dir}"
mkdir -p "$LOGS"
OUT="$LOGS/preflight.txt"
{
  echo "== bundle: $BUNDLE"
  for rel in _internal/certifi/cacert.pem _internal/osgeo/data/proj/proj.db; do
    if [[ -f "$BUNDLE/$rel" ]]; then
      echo "PRESENT  $rel ($(wc -c < "$BUNDLE/$rel") bytes)"
    else
      echo "MISSING  $rel"
    fi
  done
  echo "== every *.pem / *.crt / curl-ca-bundle in the bundle:"
  find "$BUNDLE" -iname '*.pem' -o -iname '*.crt' -o -iname 'curl-ca-bundle*' | head -20
  echo "== GDAL / curl DLLs:"
  find "$BUNDLE" -iname '*gdal*.dll' -o -iname '*curl*.dll' -o -iname 'libssl*.dll' -o -iname 'libcrypto*.dll' | head -20
  echo "== env CA hints: CURL_CA_BUNDLE=${CURL_CA_BUNDLE:-} SSL_CERT_FILE=${SSL_CERT_FILE:-} GDAL_HTTP_USE_CAPI_STORE=${GDAL_HTTP_USE_CAPI_STORE:-}"
  echo "== runner reachability (curl.exe, Schannel):"
  for url in \
    "https://servicios.idee.es/wcs-inspire/mdt?SERVICE=WCS&REQUEST=GetCapabilities" \
    "https://copernicus-dem-30m.s3.amazonaws.com/" \
    "http://viewfinderpanoramas.org/dem3/K30.zip"; do
    code=$(curl.exe -s -o NUL -w '%{http_code} %{ssl_verify_result} %{time_total}s' -I --max-time 60 "$url" 2>&1)
    echo "PROBE  $url -> $code"
  done
  echo "== verbose idee.es handshake:"
  curl.exe -sv --max-time 60 "https://servicios.idee.es/wcs-inspire/mdt?SERVICE=WCS&REQUEST=GetCapabilities" -o NUL 2>&1 | grep -E '^\*|^< HTTP' | head -40
} 2>&1 | tee "$OUT"
if grep -q 'idee.es.*-> 000' "$OUT"; then
  echo "::warning::RUNNER CANNOT REACH servicios.idee.es — the LEMD result below is NOT evidence about the bundle"
fi
exit 0
