#!/usr/bin/env python3
"""
resources/lib/pluto_catalog.py — Pluto TV channel catalog fetcher.

Pulls the gzipped JSON catalog maintained by Matt Huisman (mjh.nz) at
https://i.mjh.nz/PlutoTV/.channels.json.gz and exposes it to default.py
for rendering the dynamic Live → <category> → <channel> tree.

The catalog is the same data feed that slyguy.pluto.tv.provider uses, so
its shape and freshness are well-known: organized by region (us, uk, mx,
etc.), with each region containing channels keyed by their 24-char Pluto
channel ID.  Each channel has a `name`, `group` (category like "Sports"),
`logo`, `art`, optional `description`, and a `programs` list with
upcoming-EPG entries as [iso_timestamp, title] pairs.

This module only handles fetching, caching, and lookup.  Rendering Kodi
list items lives in default.py.

DEPENDENCIES:
- i.mjh.nz — Matt Huisman's catalog hosting.  Stable; updates as Pluto
  adds/removes channels.  6-hour cache TTL since channel turnover is slow.
  If the host goes down, the resolver still works for any channels we
  have cached, and a refresh will fail with a logged warning rather
  than crash.
"""

import gzip
import json
import time
from urllib.request import urlopen, Request


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATALOG_URL = 'https://i.mjh.nz/PlutoTV/.channels.json.gz'

# USA region key.  Pluto's biggest market and what we render.  If this key
# isn't in the catalog (Pluto pulls out of the US, mjh changes the schema,
# etc.), usa_groups() and channels_in_group() return empty rather than
# raising; default.py shows an empty Live menu and logs a warning.
USA_REGION_KEY = 'us'

# Refresh cadence.  Pluto's channel lineup turns over slowly — a 6-hour
# cache is plenty fresh and avoids hammering mjh's server on every Live
# click.  Forced refresh available via the addon's "Refresh / Clear Cache"
# menu entry, which calls clear_cache() through the wiring in default.py.
TTL_SECS = 6 * 3600

# Browser-shaped UA for the catalog fetch.  mjh's host doesn't enforce a
# specific UA, but generic Mozilla/5.0 is a polite default.
_UA = 'Mozilla/5.0 (compatible; EchoOnDemand/3.3; +Kodi)'


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

# In-memory cache.  {data: dict|None, fetched: float}.  Lives for the
# lifetime of one Kodi addon process.  Re-import gives a fresh empty cache,
# which is fine — first Live click after Kodi restart pays one fetch.
_cache = {'data': None, 'fetched': 0.0}

# Diagnostic logger callback (set by default.py at module load time to
# bridge into xbmc.log).  None disables logging.
_logger = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_logger(fn):
    """Register a logger callback.  Signature: fn(message: str, level: str).
    Levels: 'INFO', 'WARN', 'ERROR'.  None disables logging."""
    global _logger
    _logger = fn


def get_catalog(timeout=15, force=False):
    """Fetch and parse mjh's PlutoTV catalog.

    Returns the parsed dict on success, None on any failure (network error,
    decompression error, JSON error).  Caches the parsed dict for TTL_SECS.
    Pass force=True to bypass the cache and fetch fresh.

    Failure mode is intentional: callers receive None and must handle the
    "no catalog" case (typically by showing an empty list with a friendly
    notification).  Failures don't poison the cache — next call retries.
    """
    now = time.time()
    if not force and _cache['data'] is not None:
        age = now - _cache['fetched']
        if age < TTL_SECS:
            return _cache['data']

    try:
        req = Request(CATALOG_URL, headers={'User-Agent': _UA})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        body = gzip.decompress(raw)
        data = json.loads(body.decode('utf-8'))
    except Exception as e:
        _log('catalog: fetch failed: {}'.format(e), 'WARN')
        return None

    _cache['data']    = data
    _cache['fetched'] = now
    n_regions = len(data.get('regions', {}) or {})
    _log('catalog: fetched ({} regions, {} bytes compressed)'
         .format(n_regions, len(raw)), 'INFO')
    return data


def clear_cache():
    """Wipe the in-memory catalog cache.  Wired into the addon's
    Refresh / Clear Cache menu entry."""
    global _cache
    _cache = {'data': None, 'fetched': 0.0}


def usa_groups(catalog):
    """Return {group_name: count} for the USA region.

    Each USA channel has a `group` field (Pluto's category — "Sports",
    "News", "Entertainment", etc.).  This walks the channel dict and
    aggregates counts.  Channels without a group are bucketed under "Other".

    Returns an empty dict if the catalog is missing the USA region or
    has no channels.  default.py shows an empty Live menu in that case.
    """
    region = _get_usa_region(catalog)
    if region is None:
        return {}
    groups = {}
    for chan in (region.get('channels') or {}).values():
        if not isinstance(chan, dict):
            continue
        g = chan.get('group') or 'Other'
        groups[g] = groups.get(g, 0) + 1
    return groups


def channels_in_group(catalog, group_name):
    """Return a list of channel dicts in the given USA group.

    Each returned dict has the channel's data PLUS an 'id' field with the
    24-char Pluto channel ID (which the catalog stores as the dict key,
    not as a field inside the channel data).  default.py needs the id to
    construct play URLs.

    Returns [] if the catalog is missing or the group has no channels.
    Channel ordering is unspecified — caller (default.py) sorts.
    """
    region = _get_usa_region(catalog)
    if region is None:
        return []
    out = []
    for chan_id, chan in (region.get('channels') or {}).items():
        if not isinstance(chan, dict):
            continue
        if (chan.get('group') or 'Other') != group_name:
            continue
        entry = dict(chan)
        entry['id'] = chan_id
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _get_usa_region(catalog):
    """Return the USA region dict from the catalog, or None if absent."""
    if not isinstance(catalog, dict):
        return None
    regions = catalog.get('regions')
    if not isinstance(regions, dict):
        return None
    region = regions.get(USA_REGION_KEY)
    if not isinstance(region, dict):
        return None
    return region


def _log(msg, level='INFO'):
    """Internal logging — no-op when no logger registered."""
    if _logger is not None:
        try:
            _logger(msg, level)
        except Exception:
            pass
