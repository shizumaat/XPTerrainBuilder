"""Asking a server what it has: JSON listings and HTTP answer classes.

The shared discovery calls: fetch a JSON listing, page through it, and
sort an HTTP status into ok / absent / unavailable / transient so that
only a real "nothing here" is recorded as no-coverage.
"""

import O4_UI_Utils as UI

from elevation_access.base import TransientFetchError

__all__ = [
    "HTTP_ABSENT_STATUSES",
    "HTTP_OUTCOME_ABSENT",
    "HTTP_OUTCOME_OK",
    "HTTP_OUTCOME_TRANSIENT",
    "HTTP_OUTCOME_UNAVAILABLE",
    "HTTP_UNAVAILABLE_STATUSES",
    "TNM_LISTING_MAX_PAGES",
    "_DISCOVERY_ERROR_KEYS",
    "discovery_json_payload",
    "discovery_listing_items",
    "discovery_status_is_transient",
    "http_answer_outcome",
    "raise_transient_discovery_failure",
    "tnm_listing_items",
]


# =====================================================================
# HTTP DISCOVERY CLASSIFIER — the ONE place a discovery response becomes
# "no coverage" or "come back later"
# =====================================================================
#
# THE LAW (small-queue spec 2026-08-11 SQ3): a discovery failure that says
# NOTHING about coverage raises :class:`TransientFetchError`; only a
# genuine no-data answer -- a successful response carrying no usable items
# -- returns ``None``.  The module-wide convention every ``fetch_inset`` /
# ``discover_inset`` caller already honours does the rest: a RAISED
# failure is never recorded as a durable no-coverage negative, a returned
# ``None`` is.
#
# The defect this closes: every HTTP ``discover()`` used to answer ``None``
# for a timeout, a 503, a 504 or an error page, so one outage wrote
# "this provider has no data at this airport" into the coverage index and
# no later run ever asked again.
#
# Exactly ONE convention lives here -- a second classifier at a call site
# is the defect, not a refinement.
def discovery_status_is_transient(status_code):
    """Does an HTTP status say nothing about coverage?

    ``5xx`` (the server broke: 500, 502, 503, 504) and ``429`` (rate
    limiting says "come back later", never "no data here").  Every other
    non-2xx status -- 400, 401, 403, 404 -- is the server ANSWERING about
    this request, so it stays a durable answer.
    """
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return False
    return code == 429 or 500 <= code <= 599


def raise_transient_discovery_failure(description, reason):
    """WARN in the module idiom and raise :class:`TransientFetchError`.

    Never returns.  ``description`` names the request ("TNM discovery
    request"), ``reason`` what went wrong (an exception, a status).
    """
    UI.vprint(
        1,
        "   WARNING: " + str(description) + " failed:",
        str(reason),
        "- transient, NOT recorded as no-coverage.",
    )
    raise TransientFetchError("%s failed: %s" % (description, reason))


# =====================================================================
# THE ANSWER-OUTCOME LAW — what ONE HTTP answer about ONE OBJECT means
# =====================================================================
#
# ``discovery_status_is_transient`` above classifies a LISTING response
# (does this catalog show coverage, or should we come back later?) and
# is deliberately two-way: a listing is either an answer about coverage
# or it is not.
#
# An answer about ONE NAMED OBJECT -- "is this COG in the bucket?", "did
# this archive download?" -- is a different question with a THIRD
# outcome that the two-way classifier structurally cannot express, and
# RULINGS 2026-09-13b requires it: a provider the engine could not ASK
# records ``unavailable:<reason>``, never ``no-coverage``.  So exactly
# ONE classifier lives here for that question, and its transient half
# DELEGATES to ``discovery_status_is_transient`` -- there is no second
# transient convention in this module.
#
# The defect this closes (issue #124): ``DegreeNamedCogStrategy.
# _url_exists`` printed "existence probe for ... returned status N" and
# returned ``False`` for EVERY answer that was not 200 or 404.  A CDN
# 403, a proxy 407, a 429 or a 503 therefore meant "this cell does not
# exist", and COPERNICUSGLO30 could be written into the coverage index
# as a durable ``no-coverage`` for the airport -- the #121 class again
# (a failed transport becoming a permanent negative).
HTTP_OUTCOME_OK = "ok"


HTTP_OUTCOME_ABSENT = "absent"


HTTP_OUTCOME_UNAVAILABLE = "unavailable"


HTTP_OUTCOME_TRANSIENT = "transient"


#: The ONLY statuses that are a well-formed answer ABOUT THE OBJECT: the
#: server looked, and it is not there (404) or no longer there (410).
#: These alone may become a durable negative.
HTTP_ABSENT_STATUSES = (404, 410)


#: Statuses where the server refused to serve THIS CLIENT rather than
#: answering about the object: authentication and proxy refusals (401,
#: 403, 407), a legal block (451), and a host that rejects the method
#: the probe used (405 Method Not Allowed -- Saxony's tile host answers
#: 401 to HEAD, hence the ``probe_mode`` knob elsewhere in this file).
#: None of them says whether the object exists, so they are
#: ``unavailable:<reason>``, never no-coverage.
#:
#: 501 Not Implemented is deliberately NOT here although it is the same
#: "this host will not answer that question" shape: it is a 5xx, which
#: ``discovery_status_is_transient`` already owns, and a SECOND opinion
#: about one status is the drift SQ3 forbids.  Transient is the safe
#: side of that disagreement -- nothing is recorded either way.
HTTP_UNAVAILABLE_STATUSES = (401, 403, 405, 407, 451)


def http_answer_outcome(status_code):
    """Which outcome class one HTTP answer about one object belongs to.

    * ``2xx``                    -> :data:`HTTP_OUTCOME_OK`.
    * ``404`` / ``410``          -> :data:`HTTP_OUTCOME_ABSENT` (durable).
    * ``401 403 405 407 451 501``-> :data:`HTTP_OUTCOME_UNAVAILABLE`.
    * everything else            -> :data:`HTTP_OUTCOME_TRANSIENT`.

    That last line is the point of the law, and it SUBSUMES the ``429`` /
    ``5xx`` of ``discovery_status_is_transient`` (a twin pins that every
    status that classifier calls transient lands here as transient too,
    so the two never drift apart).  An answer this classifier does not
    recognise -- a surfacing 3xx (a redirect loop or a 304), a 400, a 418
    from a bot wall -- says NOTHING about whether the object is there,
    and minting a durable negative from an answer nobody understood is
    exactly how one outage became permanent.  Only the two statuses that
    MEAN "not there" are allowed to.
    """
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return HTTP_OUTCOME_TRANSIENT
    if 200 <= code < 300:
        return HTTP_OUTCOME_OK
    if code in HTTP_ABSENT_STATUSES:
        return HTTP_OUTCOME_ABSENT
    if code in HTTP_UNAVAILABLE_STATUSES:
        return HTTP_OUTCOME_UNAVAILABLE
    return HTTP_OUTCOME_TRANSIENT


def discovery_json_payload(response, description):
    """The parsed JSON body of one discovery response, or ``None``.

    * 2xx + JSON body      -> the payload (the caller decides whether the
      items in it amount to coverage; an EMPTY catalog is a durable
      answer).
    * 5xx / 429            -> :class:`TransientFetchError`.
    * any other non-2xx    -> ``None`` with a WARN (durable: the server
      answered about this request).
    * 2xx + non-JSON body  -> :class:`TransientFetchError`.  An error page
      served with a 200 is an outage artefact (proxies, captive portals,
      maintenance pages), never a catalog answer -- and treating it as
      "no data" is exactly how an outage became permanent.
    """
    status = getattr(response, "status_code", 200)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 200
    if not 200 <= status < 300:
        if discovery_status_is_transient(status):
            raise_transient_discovery_failure(
                description, "status %d" % status
            )
        UI.vprint(
            1,
            "   WARNING: " + str(description) + " returned status",
            status,
            "- durable, recorded as no-coverage.",
        )
        return None
    try:
        return response.json()
    except Exception:
        raise_transient_discovery_failure(
            description, "a non-JSON body on a %d response" % status
        )


#: Keys a discovery body uses to report its own failure.  A listing that
#: carries one is degraded, whatever its HTTP status said.
_DISCOVERY_ERROR_KEYS = ("error", "errors", "fault", "exception")


def discovery_listing_items(payload, description, items_key="items",
                            total_key="total"):
    """The items of a COMPLETE product listing, or a transient raise.

    The second half of the SQ3 law, and the defect KPHX measured on
    2026-09-15: a degraded service does not only answer 5xx.  While TNM
    was 504-ing it also answered **HTTP 200 with a body that is JSON but
    is not a catalog** -- a gateway error envelope, or a listing that
    lost its items array -- and ``payload.get("items") or []`` read every
    one of those as "this provider has no data here".  Twenty airports
    across ``+33-113`` / ``+33-112`` took a durable ``no-coverage`` for
    USGS3DEP that way, KPHX among them, while TNM in fact publishes four
    1 m products over it.

    Only a WELL-FORMED, COMPLETE zero-products answer is no-coverage:

    * not a mapping, or no ``items_key`` LIST   -> transient (an error
      envelope such as ``{"message": "Internal Server Error"}`` is not a
      catalog at all);
    * a truthy error key                        -> transient (the service
      said it failed inside a 200);
    * ``total`` > 0 with an EMPTY item list     -> transient (the answer
      contradicts itself: a truncated listing, never "nothing here");
    * anything else                             -> the list, empty or not.
      An empty list from an otherwise intact envelope is the ONE durable
      negative.
    """
    if not isinstance(payload, dict):
        raise_transient_discovery_failure(
            description, "a 200 body that is not a product listing"
        )
    items = payload.get(items_key)
    if not isinstance(items, list):
        raise_transient_discovery_failure(
            description,
            "a 200 body carrying no '%s' listing" % items_key,
        )
    for key in _DISCOVERY_ERROR_KEYS:
        if payload.get(key):
            raise_transient_discovery_failure(
                description,
                "a 200 body reporting '%s': %s" % (key, payload[key]),
            )
    if not items and total_key is not None:
        try:
            total = int(payload.get(total_key, 0))
        except (TypeError, ValueError):
            total = 0
        if total > 0:
            raise_transient_discovery_failure(
                description,
                "a 200 body claiming %d product(s) and listing none"
                % total,
            )
    return items


#: At most this many TNM listing pages per discovery (50 items each by
#: default): an OPR listing over an inset box reads ~100 tiles (KGEG 97,
#: measured 2026-10-01); a listing past the cap is refused as transient
#: rather than silently truncated.
TNM_LISTING_MAX_PAGES = 40


def tnm_listing_items(url, description, timeout=30):
    """Every item of a TNM Access API product listing, PAGED (#153).

    The API answers ``max`` items per page (50 by default) beside the
    listing's ``total``.  A 1 m listing over an airport box is a handful
    of 10 km tiles and always fits one page -- that request is exactly
    the one discovery always made -- but an Original Product Resolution
    listing is per ~1 km tile (KGEG: 97), and reading only the first page
    would cut half the airport out of the mosaic with no word said.
    Further pages are asked with ``offset=`` only while ``total`` says
    more exist; a page that adds nothing while more are claimed, or a
    listing beyond :data:`TNM_LISTING_MAX_PAGES`, is TRANSIENT (a
    truncated listing is never a coverage answer -- the SQ3 law).
    Returns ``None`` for a durable 4xx answer (``discovery_json_payload``).
    """
    import requests

    items = []
    offset = 0
    for page in range(TNM_LISTING_MAX_PAGES):
        page_url = url if page == 0 else "%s&offset=%d" % (url, offset)
        try:
            response = requests.get(page_url, timeout=timeout)
        except Exception as error:
            raise_transient_discovery_failure(description + " request",
                                              error)
        payload = discovery_json_payload(response, description)
        if payload is None:
            if page == 0:
                return None
            raise_transient_discovery_failure(
                description, "page %d of a listing answered no catalog"
                % (page + 1))
        # A 200 is not by itself an answer about coverage: only a
        # COMPLETE listing is (2026-09-15, KPHX).
        page_items = discovery_listing_items(payload, description)
        items.extend(page_items)
        offset += len(page_items)
        try:
            total = int(payload.get("total", 0) or 0)
        except (TypeError, ValueError):
            total = 0
        if total <= len(items):
            return items
        if not page_items:
            raise_transient_discovery_failure(
                description,
                "a listing claiming %d product(s) stopped at %d"
                % (total, len(items)))
    raise_transient_discovery_failure(
        description,
        "a listing of more than %d pages (%d of %d items read)"
        % (TNM_LISTING_MAX_PAGES, len(items), total))
