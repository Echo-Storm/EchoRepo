#!/usr/bin/env python3
"""
resources/lib/pluto.py — Pluto TV channel resolver.

Pluto's stitcher URLs (the ones embedded in WOD's live.xml or in user-curated
channel lists) carry session tokens that age out and may be region-pinned to
wherever they were originally minted.  When those tokens go stale, Pluto's
stitcher returns a "service no longer available" video instead of the channel.

This module fixes that by minting our own session at play time using Pluto's
public boot endpoint — the same one pluto.tv's web player uses.

ARCHITECTURE NOTE (v3.1.1 rewrite):
  Earlier versions of this module did one boot call without channelSlug,
  hoping to receive the full channel catalog and look up channel IDs in it.
  That approach failed in practice — boot without channelSlug returns a
  default/limited response that doesn't include the user's regional channels.

  The web player works differently: it fetches the channel grid from a
  separate API, and only hits boot.pluto.tv (with channelSlug=<id>) at
  channel-switch time to mint a session for that specific channel.  This
  module now follows the same pattern — one boot call per channel.

  The 30-minute cache is now per-channel, keyed by channel ID, so we don't
  re-boot on rapid channel switches but do refresh before tokens age out.

PARAMS MATCH BROWSER EXACTLY (Edge 147 on Windows):
  Pluto's boot endpoint is sensitive to the exact param set / UA combination.
  Mismatched params return a degraded response with no playable channel.
  All values below were captured from a real browser request and verified
  to produce a working response.

Pure data layer.  No Kodi UI calls — importable and testable in isolation.
The Kodi side lives in default.py (play_pluto view, _is_pluto_url helper,
and the set_logger() call that wires our diagnostic logging into xbmc.log).
"""

import json
import re
import time
import uuid
from urllib.parse import urlencode
from urllib.request import urlopen, Request


# ---------------------------------------------------------------------------
# Constants — match Edge 147 on Windows 10, captured from real browser request
# ---------------------------------------------------------------------------

BOOT_URL = 'https://boot.pluto.tv/v4/start'

# User-Agent matching the captured browser request exactly.  default.py
# imports this constant for inputstream.adaptive's manifest_headers /
# stream_headers so the playback session uses the same UA as the boot
# session.
BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0'
)

# Other browser-shape headers.  Pluto's CDN/origin filtering may key off
# any subset of these — we send all of them to look like a real Edge tab.
_BROWSER_HEADERS = {
    'User-Agent':         BROWSER_UA,
    'Accept':             '*/*',
    'Accept-Language':    'en-US,en;q=0.9',
    'Origin':             'https://pluto.tv',
    'Referer':            'https://pluto.tv/',
    'DNT':                '1',
    'sec-ch-ua':          '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    'sec-ch-ua-mobile':   '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest':     'empty',
    'sec-fetch-mode':     'cors',
    'sec-fetch-site':     'same-site',
}

# How long to reuse a cached fresh URL.  Pluto sessions nominally last ~1
# hour; 30 minutes is comfortable headroom and matches what we want for
# rapid channel-switch scenarios (don't re-boot if you Hopstar between two
# channels in the same minute).
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

# Per-channel cache.  Each entry is {'url': str, 'fetched': float}.
_url_cache = {}

# Persistent UUID for this Kodi run.  Reused across boot calls so Pluto sees
# a stable client.  None until first use; reset by clear_session_cache().
_device_id = None

# Diagnostic logger callback.  default.py wires xbmc.log in via set_logger().
# Stays None for unit tests; callers in tests can register a list-appending
# stub to capture diagnostic output.
_logger = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_logger(fn):
    """Register a logger callback.  Signature: fn(message: str, level: str).
    Levels: 'INFO', 'WARN', 'ERROR'.  Pass None to disable logging.

    default.py is expected to call this once at import time to bridge our
    diagnostic output into xbmc.log.  pluto.py works without a logger —
    silent failures just mean less debug info in the Kodi log.
    """
    global _logger
    _logger = fn


def extract_channel_id(url):
    """Pull a 24-char Pluto channel ID out of a URL.

    Recognises the stitcher-path form (.../channel/<id>/master.m3u8) and
    the web URL form (pluto.tv/<region>/live-tv/<id>).  Returns the
    lowercase 24-char hex ID, or None if no match.
    """
    if not isinstance(url, str):
        return None
    m = _CHANNEL_ID_RE.search(url) or _WEB_CHANNEL_ID_RE.search(url)
    return m.group(1).lower() if m else None


def get_fresh_url(channel_id, timeout=15):
    """Resolve a Pluto channel ID to a current playable HLS manifest URL.

    Fetches a session from boot.pluto.tv with channelSlug=<channel_id>,
    extracts the channel's HLS URL from the response, and caches it for
    30 minutes.  Returns the URL string on success, None on any failure.

    Callers should treat None as "fall back to whatever the original URL
    was" — that way a Pluto outage doesn't make us worse than v3.0.2.

    On failure, diagnostic info is logged via the registered logger callback
    (if any): top-level keys of the response, length of the channels array,
    and a short snippet of the response body.  This lets us debug shape
    changes from the Kodi log without modifying the addon.

    The returned URL is what ISA will fetch.  It still needs the Pluto
    User-Agent + Referer headers (set in default.py via _apply_isa_properties)
    to clear Pluto's edge-server filtering on the actual stream segments.
    """
    if not channel_id:
        return None

    cached = _url_cache.get(channel_id)
    if cached and (time.time() - cached['fetched']) < _URL_TTL_SECS:
        return cached['url']

    try:
        boot = _fetch_boot(channel_id, timeout=timeout)
    except Exception as e:
        _log('pluto: boot fetch failed for {}: {}'.format(channel_id, e), 'WARN')
        return None

    url = _extract_url_from_boot(boot, channel_id)
    if url is None:
        _log_diagnostic_failure(boot, channel_id)
        return None

    _url_cache[channel_id] = {'url': url, 'fetched': time.time()}
    _log('pluto: resolved {} -> {}'.format(channel_id, url[:80]), 'INFO')
    return url


def clear_session_cache():
    """Wipe the per-channel URL cache and reset the device ID.  Next
    get_fresh_url() call will fetch a brand new boot for whatever channel
    is requested, with a brand new client UUID."""
    global _url_cache, _device_id
    _url_cache = {}
    _device_id = None


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _generate_device_id():
    """One UUID4 per Kodi run.  Re-used across boot calls so Pluto sees a
    stable client rather than a different one every play."""
    global _device_id
    if _device_id is None:
        _device_id = str(uuid.uuid4())
    return _device_id


def _log(msg, level='INFO'):
    """Internal logging — no-op when no logger registered."""
    if _logger is not None:
        try:
            _logger(msg, level)
        except Exception:
            # Never let a logger failure break resolution.
            pass


def _iso_now():
    """ISO-8601 UTC timestamp with millisecond precision and Z suffix —
    matches the format Pluto's boot endpoint expects for clientTime."""
    now = time.time()
    secs = int(now)
    ms = int((now - secs) * 1000)
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(secs)) + '.{:03d}Z'.format(ms)


def _fetch_boot(channel_id, timeout=15):
    """Hit boot.pluto.tv/v4/start with channelSlug set to one channel ID.

    Param set captured from a real Edge 147 browser request to pluto.tv.
    Mismatching the param set (e.g. wrong appVersion, missing channelSlug)
    causes Pluto to return a degraded/region-default response that doesn't
    include the channel we want.

    Returns the parsed JSON dict on success, raises on any HTTP/decode error.
    """
    params = {
        'appName':             'web',
        'appVersion':          '9.21.0-bf9f5b4369933742859f3b2581c935110922f642',
        'deviceVersion':       '147.0.0',
        'deviceModel':         'web',
        'deviceMake':          'edge-chromium',
        'deviceType':          'web',
        'clientID':            _generate_device_id(),
        'clientModelNumber':   '1.0.0',
        'channelSlug':         channel_id,   # critical — gets us THIS channel's session
        'serverSideAds':       'false',
        'drmCapabilities':     'widevine:L3',
        'blockingMode':        '',
        'notificationVersion': '1',
        'appLaunchCount':      '1',
        'lastAppLaunchDate':   _iso_now(),
        'clientTime':          _iso_now(),
    }
    url = '{}?{}'.format(BOOT_URL, urlencode(params))
    req = Request(url, headers=_BROWSER_HEADERS)
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    return json.loads(body.decode('utf-8'))


def _extract_url_from_boot(boot, channel_id):
    """Find the playable HLS URL for `channel_id` inside the boot response.

    Pluto's response shape varies by endpoint variant and over time.  We
    check several known shapes in order of likelihood — the first one that
    yields a URL wins:

      Shape A: {"channels": [{"_id": "...", "stitched": {"urls": [...]}}, ...]}
      Shape B: {"EPG":      [{"_id": "...", "stitched": {"urls": [...]}}, ...]}
               (some boot variants put the channel inside an EPG array)
      Shape C: {"channel":  {"_id": "...", "stitched": {"urls": [...]}}}
               (singular form for per-channel boot — possible since we now
               pass channelSlug)

    All three look for the same underlying structure: a `stitched.urls` list
    with at least one HLS entry.  If the response doesn't fit any shape,
    diagnostic logging fires upstream so we can see the actual shape.
    """
    if not isinstance(boot, dict):
        return None

    cid = channel_id.lower()

    # Shapes A and B both involve walking a list and finding the matching ID.
    for list_key in ('channels', 'EPG'):
        items = boot.get(list_key)
        if not isinstance(items, list):
            continue
        for ch in items:
            if not isinstance(ch, dict):
                continue
            if (ch.get('_id') or '').lower() != cid:
                continue
            url = _pick_hls_url(ch.get('stitched'))
            if url:
                return url

    # Shape C: single channel object at the top level.
    ch = boot.get('channel')
    if isinstance(ch, dict) and (ch.get('_id') or '').lower() == cid:
        url = _pick_hls_url(ch.get('stitched'))
        if url:
            return url

    return None


def _pick_hls_url(stitched):
    """Extract the first HLS URL from a stitched dict.

    Pluto's stitched URL list looks like:
      {"urls": [{"type": "hls", "url": "https://..."}, ...]}

    Some channels have multiple types listed (DASH, HLS).  We always pick
    HLS — that's what we tell Kodi we're handing it via inputstream.adaptive,
    and DASH would need different ISA properties.

    If `type` is missing, we accept the URL — Pluto's stitcher serves HLS
    by default and the type field is sometimes absent on per-channel boots.
    """
    if not isinstance(stitched, dict):
        return None
    urls = stitched.get('urls')
    if not isinstance(urls, list):
        return None
    for entry in urls:
        if not isinstance(entry, dict):
            continue
        if entry.get('type', 'hls').lower() != 'hls':
            continue
        url = entry.get('url')
        if isinstance(url, str) and url:
            return url
    return None


def _log_diagnostic_failure(boot, channel_id):
    """Called when channel lookup failed.  Dumps enough info to the logger
    that we can debug response-shape changes from the Kodi log without
    needing to reproduce or modify the addon code.

    Anything weird about the response — wrong shape, empty list, None,
    non-dict — gets logged here.  Keep messages compact; Kodi logs are
    line-oriented and we don't want to flood them.
    """
    if not isinstance(boot, dict):
        _log('pluto: boot response was not a dict (type={}); cannot extract URL'
             .format(type(boot).__name__), 'WARN')
        return

    keys = sorted(boot.keys())
    n_channels = len(boot.get('channels', [])) if isinstance(boot.get('channels'), list) else None
    n_epg      = len(boot.get('EPG', []))      if isinstance(boot.get('EPG'),      list) else None
    has_chan   = isinstance(boot.get('channel'), dict)

    _log('pluto: no URL extracted for channel {}; top-level keys={}, '
         'channels[]={}, EPG[]={}, channel(singular)={}'
         .format(channel_id, keys, n_channels, n_epg, has_chan), 'WARN')

    # Body snippet for shape inspection.  Keep short — 400 chars max.
    try:
        snippet = json.dumps(boot)[:400]
    except Exception:
        snippet = repr(boot)[:400]
    _log('pluto: response snippet: {}'.format(snippet), 'WARN')

    # If channels[] exists but is non-empty, log the first entry's _id and
    # keys so we can see if our match logic is just looking in the wrong
    # field.  Helpful when shape is right but field names changed.
    if isinstance(boot.get('channels'), list) and boot['channels']:
        first = boot['channels'][0]
        if isinstance(first, dict):
            _log('pluto: channels[0] _id={!r}, keys={}'
                 .format(first.get('_id'), sorted(first.keys())), 'WARN')
