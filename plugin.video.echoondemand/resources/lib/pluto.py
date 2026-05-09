#!/usr/bin/env python3
"""
resources/lib/pluto.py — Pluto TV channel resolver (v3.2.0 — slyguy approach).

REWRITE NOTE (v3.2.0):
The earlier v3.1.x approach hit Pluto's boot endpoint directly with browser-
shaped params, then either extracted or constructed a `/v2/stitch/embed/hls/`
URL.  In production, Pluto's web stitcher CDN returned HTTP 403 on every
manifest fetch despite a valid session being minted — almost certainly
CORS-style origin filtering on that specific endpoint.

This rewrite adopts the strategy used by the slyguy.pluto.tv.provider Kodi
addon, which is well-maintained and known-working in production:

  1. HEAD https://jmp2.uk/plu-<channel_id>.m3u8
  2. The 302 response's Location header points at a current Pluto stitcher
     URL with session params baked in — but containing one or more {PSID}
     placeholders for the device ID.
  3. Substitute {PSID} (and its URL-encoded form %7BPSID%7D) with a
     deterministic UUID3 of the machine's MAC address — same machine
     always presents the same identity to Pluto.
  4. The resulting URL targets Pluto's AppleTV-app stitcher endpoint, NOT
     the web one.  AppleTV apps don't operate in a browser context, so
     this endpoint doesn't enforce CORS / Origin checks.  Identifying
     ourselves as the AppleTV app via User-Agent (see BROWSER_UA below)
     is what makes our requests pass through.

DEPENDENCIES:
- jmp2.uk — Matt Huisman's (mjh.nz) redirect service.  Maps Pluto channel
  IDs to current stitcher URLs.  Stable and widely used by Kodi addons.
  If it goes down, the kill-switch setting in default.py disables the
  resolver gracefully.

Module is pure data-layer.  No Kodi UI calls — importable and testable in
isolation.  Public API matches the v3.1.x version (extract_channel_id,
get_fresh_url, clear_session_cache, set_logger, BROWSER_UA) so the rest
of the addon needs zero changes.
"""

import http.client
import re
import time
import uuid
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# AppleTV native Pluto app User-Agent.  This is what makes the difference —
# the AppleTV stitcher endpoint doesn't enforce CORS, so requests with this
# UA aren't subjected to the Origin/Referer checks that block our web-UA
# requests.  Constant exposed publicly; default.py imports it for ISA's
# inputstream.adaptive stream/manifest header properties.
BROWSER_UA = (
    'otg/1.5.1 (AppleTv Apple TV 4; tvOS16.0; appletv.client) '
    'libcurl/7.58.0 OpenSSL/1.0.2o zlib/1.2.11 clib/1.8.56'
)

# Redirect service.  HEAD on this URL with channel ID substituted returns a
# 302 with a Location header pointing at the actual playable URL (with
# {PSID} placeholders that we then substitute).
_JMP2_URL = 'https://jmp2.uk/plu-{}.m3u8'

# Fixed UUID3 namespace for device-ID generation.  Same value used by
# slyguy.pluto.tv.provider — using their namespace means our addon presents
# the same client identity to Pluto as slyguy would, which keeps things
# consistent if a user has both addons installed.
_UUID_NAMESPACE = uuid.UUID('122e1611-0232-4336-bf43-e054c8ecd0d5')

# How long to reuse a cached resolved URL.  Pluto's session tokens (baked
# into the URL by the stitcher) typically last around an hour; 30 minutes
# is comfortable headroom.
_URL_TTL_SECS = 1800

# 24-char lowercase-hex (BSON ObjectId-shape) channel ID inside a stitcher URL.
_CHANNEL_ID_RE = re.compile(r'/channel/([0-9a-f]{24})', re.IGNORECASE)
# Same ID inside the public web URL form (pluto.tv/<region>/live-tv/<id>).
_WEB_CHANNEL_ID_RE = re.compile(
    r'pluto\.tv/[a-z]{2}/live-tv/([0-9a-f]{24})', re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

# Per-channel resolved-URL cache.  Each entry: {'url': str, 'fetched': float}.
_url_cache = {}

# Diagnostic logger callback.  default.py wires xbmc.log in via set_logger().
_logger = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_logger(fn):
    """Register a logger callback.  Signature: fn(message: str, level: str).
    Levels: 'INFO', 'WARN', 'ERROR'.  Pass None to disable.
    Called once at addon import time by default.py to bridge into xbmc.log.
    """
    global _logger
    _logger = fn


def extract_channel_id(url):
    """Pull a 24-char Pluto channel ID out of a URL.

    Recognises the stitcher-path form (.../channel/<id>/master.m3u8) and the
    web URL form (pluto.tv/<region>/live-tv/<id>).  Returns the lowercase
    24-char hex ID, or None if no match.
    """
    if not isinstance(url, str):
        return None
    m = _CHANNEL_ID_RE.search(url) or _WEB_CHANNEL_ID_RE.search(url)
    return m.group(1).lower() if m else None


def get_fresh_url(channel_id, timeout=15):
    """Resolve a Pluto channel ID to a current playable HLS manifest URL.

    Uses the jmp2.uk redirect service to obtain a current stitcher URL,
    then substitutes the {PSID} device-ID placeholders.  Caches the result
    for 30 minutes per channel.

    Returns the URL on success, None on failure (network error, no
    redirect, etc.).  Callers should treat None as "fall back" — for
    play_wr that means the original (potentially stale) URL; for
    play_pluto there's no fallback, so a failure shows the user a
    notification.
    """
    if not channel_id:
        return None

    cached = _url_cache.get(channel_id)
    if cached and (time.time() - cached['fetched']) < _URL_TTL_SECS:
        return cached['url']

    try:
        location = _resolve_via_jmp2(channel_id, timeout=timeout)
    except Exception as e:
        _log('pluto: jmp2 resolve failed for {}: {}'.format(channel_id, e), 'WARN')
        return None

    if not location:
        _log('pluto: jmp2 returned no Location for channel {}'.format(channel_id), 'WARN')
        return None

    psid = _get_psid()
    url = location.replace('%7BPSID%7D', psid).replace('{PSID}', psid)

    _url_cache[channel_id] = {'url': url, 'fetched': time.time()}
    _log('pluto: resolved {} -> {}'.format(channel_id, url[:80]), 'INFO')
    return url


def clear_session_cache():
    """Wipe the per-channel URL cache.  Next get_fresh_url() call will hit
    jmp2.uk fresh for whatever channel is requested."""
    global _url_cache
    _url_cache = {}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _get_psid():
    """Generate a deterministic per-machine device ID for Pluto's PSID slot.

    Uses UUID3 (MD5-based namespaced UUID) of the machine's MAC address in a
    fixed namespace.  Same machine = same UUID across restarts.  This lets
    Pluto track us as a stable device rather than a different one per play.

    `uuid.getnode()` returns the MAC as a 48-bit int.  In containers or
    unusual environments where a real MAC isn't available, getnode() falls
    back to a random 48-bit value cached for the process lifetime — still
    stable within that process.
    """
    return str(uuid.uuid3(_UUID_NAMESPACE, str(uuid.getnode())))


def _resolve_via_jmp2(channel_id, timeout=10):
    """HEAD request to jmp2.uk/plu-<id>.m3u8.  Returns Location header
    string from the 302 redirect, or None if not redirected.

    We use http.client directly rather than urllib.request because urllib
    auto-follows redirects by default — but we *want* the Location header
    raw, with its {PSID} placeholders intact.  Following the redirect would
    make Pluto try to interpret the literal string '{PSID}' as a real
    device ID, which fails.

    Raises on unrecoverable network errors (DNS, TLS, connection refused).
    Caller catches those and treats them as resolve failures.
    """
    url = _JMP2_URL.format(channel_id)
    parsed = urlparse(url)

    if parsed.scheme == 'https':
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=timeout)
    else:
        conn = http.client.HTTPConnection(parsed.netloc, timeout=timeout)

    try:
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        conn.request('HEAD', path, headers={'User-Agent': BROWSER_UA})
        resp = conn.getresponse()
        if resp.status in (301, 302, 303, 307, 308):
            location = resp.getheader('Location')
            if location:
                return location
            _log('pluto: jmp2 returned {} but no Location header'.format(resp.status), 'WARN')
            return None
        # Unexpected status — log and signal failure.  jmp2 should always
        # 302 for valid channel IDs.  A 404 means mjh's catalog doesn't
        # know about this channel; a 5xx means the service is having
        # problems.
        _log('pluto: jmp2 returned status {} for {} (expected redirect)'
             .format(resp.status, channel_id), 'WARN')
        return None
    finally:
        conn.close()


def _log(msg, level='INFO'):
    """Internal logging — no-op when no logger registered."""
    if _logger is not None:
        try:
            _logger(msg, level)
        except Exception:
            # Never let a logger failure break resolution.
            pass
