"""
resources/lib/wrestling.py
Wrestling Rewind data layer for Echo OnDemand  v2.2.0

Responsibilities (data only — no Kodi UI, no xbmcplugin, no xbmcgui):
  - Fetch MicroJen XML/JSON feeds over HTTP with cache
  - Parse them into normalised item dicts
  - Resolve candidate links to a playable URL via resolveurl (debrid-first)

Parsed item dict schema:
  {
    'type':      'dir' | 'item'
    'title':     str
    'link':      str | list[str]   -- list when sublinks are present
    'thumbnail': str               -- may be empty
    'fanart':    str               -- may be empty
    'summary':   str               -- may be empty
  }

MicroJen XML — two valid sublink placements:

  (a) Sublinks as direct children of <item>:
        <item>
          <title>...</title>
          <sublink>https://host1.com/file.mkv(Label)</sublink>
          <sublink>https://host2.com/file.mkv(Label)</sublink>
        </item>

  (b) Sublinks nested inside <link> (more common in live WR feeds):
        <item>
          <title>...</title>
          <link>
            <sublink>https://host1.com/file.mkv(Label)</sublink>
            <sublink>https://host2.com/file.mkv(Label)</sublink>
          </link>
        </item>

  Both are handled via a recursive subtree search (.//sublink) after the
  flat direct-child pass — same approach as WR's own xml_parser._handle_item().

MicroJen JSON:
  {"items": [
    {"type": "dir",  "title": "...", "link": "...", "thumbnail": "...", "fanart": "..."},
    {"type": "item", "title": "...", "link": "..." | [...], "summary": "..."}
  ]}

Assumptions:
  - script.module.resolveurl is installed and configured with a debrid account.
  - Feed URLs are publicly accessible (no auth required for the feed itself).
  - Kodi Omega (v21) / Python 3.
"""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request

import xbmc

try:
    import resolveurl
    _RESOLVEURL_OK = True
except ImportError:
    _RESOLVEURL_OK = False
    xbmc.log('[EchoOD/Wrestling] CRITICAL: script.module.resolveurl not found — '
             'debrid resolution unavailable.', xbmc.LOGERROR)

_LOG_TAG = '[EchoOD/Wrestling]'
_FETCH_TIMEOUT = 15


def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log('{} {}'.format(_LOG_TAG, msg), level)


# ---------------------------------------------------------------------------
# Cache — raw feed text, keyed by URL
# ---------------------------------------------------------------------------
# We cache the raw text (not parsed items) so that a parse-logic fix
# takes effect on the next call without requiring a re-fetch.

def _cache_filename(url):
    """Derive a safe, stable filename from a URL (max 120 sanitised chars)."""
    safe = re.sub(r'[^a-zA-Z0-9]', '_', url)[:120]
    return 'wr_{}.json'.format(safe)


def cache_load(profile_dir, url, ttl_secs):
    """Return cached feed text for url, or None if absent/expired."""
    path = os.path.join(profile_dir, _cache_filename(url))
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        age = time.time() - data.get('ts', 0)
        if age < ttl_secs:
            log('Cache hit: {} (age {:.0f}s)'.format(url[:60], age))
            return data['payload']
        log('Cache expired: {} (age {:.0f}s)'.format(url[:60], age))
    except Exception as e:
        log('Cache read error for {}: {}'.format(url[:60], e), xbmc.LOGWARNING)
    return None


def cache_save(profile_dir, url, text):
    """Persist raw feed text to the cache."""
    path = os.path.join(profile_dir, _cache_filename(url))
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'ts': time.time(), 'payload': text}, f)
        log('Cache saved: {}'.format(url[:60]))
    except Exception as e:
        log('Cache write error for {}: {}'.format(url[:60], e), xbmc.LOGWARNING)


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def fetch_feed(url):
    """
    Fetch url and return response text.
    Raises urllib.error.URLError on network failure.
    Caller must catch and handle.
    """
    log('Fetching: {}'.format(url), xbmc.LOGINFO)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Kodi/EchoOnDemand'}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
        raw = resp.read()
    try:
        return raw.decode('utf-8', errors='ignore')
    except Exception:
        return raw.decode('latin-1', errors='ignore')


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

# Matches a bare & that is NOT the start of a valid XML entity reference.
# Examples:
#   &amp;   → no match (already escaped named entity)
#   &#160;  → no match (numeric entity)
#   &#xA0;  → no match (hex entity)
#   &       → match (bare ampersand — common in URLs inside XML feeds)
_BARE_AMP_RE = re.compile(r'&(?!(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]\w*);)')


def _escape_bare_amps(text):
    """
    Escape bare & characters that are not already part of an entity reference.

    This is the correct fix for the problem that WR's own xml_parser.py
    works around by replacing ALL & blindly (causing double-escaping of
    things like &amp; → &amp;amp;).
    """
    return _BARE_AMP_RE.sub('&amp;', text)


def _strip_preamble(text):
    """
    Remove WR-specific non-content nodes that appear before the actual data:
      <?xml ...?>                    — XML processing instructions
      <layouttype>...</layoutype>    — original obfuscation (open has double-t,
                                       close has single-t — intentional typo)
      <layoutype>...</layoutype>     — PPV feed variant (both tags use single-t)
      <!-- ... -->                   — XML comments

    Regex breakdown for the layouttype/layoutype block:
      Open tag:  <layoutt?ype...>   matches 'layouttype' (t?) and 'layoutype' (no t)
      Close tag: </layoutt?ype>     same logic for close tag
    The `t?` (optional t) handles both the double-t original and single-t variant.
    """
    text = re.sub(r'<\?[^?]*\?>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<layoutt?ype[^>]*>.*?</layoutt?ype>', '', text,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    return text.strip()


def _parse_element(element):
    """
    Convert one <dir> or <item> ET.Element into a normalised item dict.

    Two-pass sublink extraction:

    Pass 1 (flat direct-child scan):
      Iterates element's direct children.  Captures plain-text <link> and
      any <sublink> elements that ARE direct children (some feeds do this).

    Pass 2 (recursive subtree search):
      Uses element.findall('.//sublink') — identical to WR's own _handle_item()
      — which catches the common WR pattern where <sublink> elements are
      nested inside a <link> parent:
        <link>
          <sublink>https://host.com/file.mkv(Label)</sublink>
        </link>
      A flat loop finds <link> but reads its .text as None/empty (it has child
      elements, not text).  The recursive search finds the sublinks directly.

    Sublinks from either pass override the plain-text <link> value.
    """
    result = {'type': element.tag.lower()}
    sublinks = []

    # Pass 1: flat direct children
    for child in element:
        tag  = child.tag.lower()
        text = (child.text or '').strip()
        if tag == 'sublink':
            if text:
                sublinks.append(text)
        else:
            result[tag] = text

    # Pass 2: recursive subtree scan (handles sublinks-inside-link structure)
    if not sublinks:
        for sub in element.findall('.//sublink'):
            text = (sub.text or '').strip()
            if text:
                sublinks.append(text)

    if sublinks:
        result['link'] = sublinks

    for key in ('title', 'link', 'thumbnail', 'fanart', 'summary'):
        result.setdefault(key, '')

    return result


def _collect_items(root):
    """
    Find all <dir> and <item> elements in a parsed XML tree.

    Handles two nesting depths:

    Depth 1 — <dir>/<item> as direct children of root:
      Covers feeds where root itself is the <xml> wrapper and contains
      items directly.

    Depth 2 — <dir>/<item> as children of ANY intermediate wrapper:
      BUG FIX: Previous code only recognised <xml> as an intermediate
      wrapper, silently skipping items in feeds that use any other wrapper
      element name (<items>, <content>, <category>, or anything custom).
      The fix: treat ANY non-item/dir child of root as a potential wrapper
      and scan its children.  This is what caused "NO ITEMS FOUND" for the
      PPV feed — it uses a different wrapper element name than <xml>.

    Returns a flat list of parsed item dicts.
    """
    items = []

    # Depth 1: direct children of root
    for child in root:
        if child.tag.lower() in ('dir', 'item'):
            items.append(_parse_element(child))

    # Depth 2: children of any intermediate wrapper
    # Only runs when depth 1 found nothing to avoid double-counting.
    if not items:
        for child in root:
            if child.tag.lower() not in ('dir', 'item'):
                for grandchild in child:
                    if grandchild.tag.lower() in ('dir', 'item'):
                        items.append(_parse_element(grandchild))

    return items


# Regex that extracts individual <item> and <dir> blocks from raw feed text.
# Used by pass 4 (lenient extraction) when full-document XML parse fails.
# Non-greedy inner match (.+?) stops at the first matching </tag> — safe for
# MicroJen format where items never nest other items or dirs.
_ITEM_BLOCK_RE = re.compile(
    r'<(item|dir)\b[^>]*>(.+?)</\1\s*>',
    re.DOTALL | re.IGNORECASE
)


def _parse_xml_items_lenient(text):
    """
    Extract <item> and <dir> blocks individually via regex and parse each
    with ET.fromstring().  One malformed item is skipped (logged at WARNING)
    rather than aborting the entire feed.

    This handles the case where the overall document structure is broken
    (mismatched tags, unescaped < or > in magnet link dn parameters, etc.)
    but most individual items are valid XML.
    """
    items = []
    for m in _ITEM_BLOCK_RE.finditer(text):
        tag   = m.group(1).lower()
        inner = m.group(2)
        xml   = '<{0}>{1}</{0}>'.format(tag, inner)
        try:
            elem = ET.fromstring(xml)
            items.append(_parse_element(elem))
        except ET.ParseError as e:
            log('XML pass 4: skipping malformed {}: {}'.format(tag, e),
                xbmc.LOGWARNING)
    return items


def parse_xml(text):
    """
    Parse a MicroJen XML feed.  Returns a list of item dicts (may be empty).
    Never raises — logs on failure and returns [].

    Three-pass progressive recovery:
      Pass 1: preamble stripped, parse as-is.
      Pass 2: preamble stripped + bare & escaped.
      Pass 3: pass-2 text wrapped in synthetic <root> element.
              Handles the common WR pattern of multiple top-level <xml> blocks
              (each episode in its own <xml> — technically invalid XML).
      Pass 4: per-item regex extraction (lenient fallback).
              For feeds where the overall document structure is genuinely
              broken — mismatched tags, unescaped < or > in a magnet dn
              parameter, etc. — but individual <item>/<dir> blocks are
              parseable.  Extracts each block with a regex and parses it
              independently with ET.fromstring().  One broken item is
              skipped rather than aborting the whole feed.
    """
    cleaned = _strip_preamble(text)
    candidates = [
        cleaned,
        _escape_bare_amps(cleaned),
        '<root>{}</root>'.format(_escape_bare_amps(cleaned)),
    ]

    for attempt, xml_text in enumerate(candidates, start=1):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            log('XML pass {} failed: {}'.format(attempt, e), xbmc.LOGWARNING)
            continue

        if root.tag.lower() in ('dir', 'item'):
            items = [_parse_element(root)]
        else:
            items = _collect_items(root)

        if items:
            log('XML pass {} OK — {} items, root=<{}>'.format(
                attempt, len(items), root.tag), xbmc.LOGINFO)
            return items

    # Pass 4: per-item lenient extraction.
    # Regex finds every <item>...</item> and <dir>...</dir> block individually.
    # Each is parsed on its own so a single malformed item doesn't kill the feed.
    # Uses the amp-escaped text from pass 2 (bare & already handled).
    items = _parse_xml_items_lenient(_escape_bare_amps(cleaned))
    if items:
        log('XML pass 4 (lenient) OK — {} items'.format(len(items)), xbmc.LOGINFO)
        return items

    log('XML: all passes exhausted — 0 items found', xbmc.LOGWARNING)
    return []


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def parse_json(text):
    """
    Parse a MicroJen JSON feed ({"items": [...]}).
    Returns a list of normalised item dicts.  Never raises.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        log('JSON parse error: {}'.format(e), xbmc.LOGWARNING)
        return []

    raw_items = data.get('items', [])
    if not isinstance(raw_items, list):
        log('JSON "items" field is not a list', xbmc.LOGWARNING)
        return []

    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item = {
            'type':      (raw.get('type') or 'item').lower(),
            'title':     (raw.get('title') or '').strip(),
            'link':      raw.get('link', ''),
            'thumbnail': (raw.get('thumbnail') or '').strip(),
            'fanart':    (raw.get('fanart') or '').strip(),
            'summary':   (raw.get('summary') or '').strip(),
        }
        items.append(item)

    log('JSON parsed — {} items'.format(len(items)), xbmc.LOGINFO)
    return items


# ---------------------------------------------------------------------------
# Feed dispatcher
# ---------------------------------------------------------------------------

def parse_feed(url, text):
    """
    Dispatch to the appropriate parser, with mutual fallback.

    Detection order:
      1. URL ends with .json OR content starts with { or [  → JSON first
      2. Otherwise                                          → XML first
      3. If primary parser returns [] and content looks like the other
         format → try the other parser
      4. If both return [] → emit a LOGINFO diagnostic with the feed
         sample so the failure is visible WITHOUT debug mode enabled.

    The mutual fallback (step 3) handles feeds where the URL extension does
    not match the actual content type — a real occurrence in the WR feed
    ecosystem where .xml URLs sometimes serve JSON content.
    """
    stripped = text.lstrip()
    is_json_url    = url.lower().endswith('.json')
    looks_like_json = stripped.startswith('{') or stripped.startswith('[')
    looks_like_xml  = stripped.startswith('<')

    if is_json_url or looks_like_json:
        result = parse_json(text)
        if result:
            return result
        # JSON returned nothing — try XML in case the content is XML after all
        if looks_like_xml:
            result = parse_xml(text)
            if result:
                return result
    else:
        result = parse_xml(text)
        if result:
            return result
        # XML returned nothing — try JSON fallback
        if looks_like_json:
            log('XML returned empty — trying JSON fallback for {}'.format(url[:60]),
                xbmc.LOGINFO)
            result = parse_json(text)
            if result:
                return result

    # Both parsers returned nothing.  Emit a diagnostic at LOGINFO so this is
    # always visible in the Kodi log without needing debug mode.
    log('PARSE FAILED for {}  content[0:300]={!r}'.format(url[:80], text[:300]),
        xbmc.LOGINFO)
    return []


# ---------------------------------------------------------------------------
# Link utilities
# ---------------------------------------------------------------------------

# Matches the scheme prefix of any URI (http://, https://, magnet:, ftp://, etc.)
# Used to validate stripped link candidates and to decide what to include in
# normalise_links() output.
_URI_SCHEME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+\-.]*:')

def _strip_label_suffix(link):
    """
    Strip optional trailing (Label) from a WR link string.

    WR encodes human-readable labels as a suffix on the URL:
      'http://host.com/file.mkv(720p RD)'         → 'http://host.com/file.mkv'
      'magnet:?xt=...&dn=WWE...[TJET](Debrid)'    → 'magnet:?xt=...&dn=WWE...[TJET]'

    BUG FIX: The previous check `candidate.startswith('http')` caused magnet:
    URIs to NOT have their label stripped.  resolveurl then received the label
    text still attached (e.g. 'magnet:?xt=...&dn=...(Debrid)') and may have
    rejected it as an invalid URI.

    Fix: accept any valid URI scheme using a regex instead of a prefix check.
    """
    link = link.strip()
    if link.endswith(')') and '(' in link:
        candidate = link.rsplit('(', 1)[0].strip()
        if _URI_SCHEME_RE.match(candidate):
            return candidate
    return link


def normalise_links(raw_link):
    """
    Normalise the link field from a parsed item dict into a flat list of
    clean, label-stripped URIs ready for resolve_best_link().

    raw_link may be: '' | 'http://...' | 'magnet:...' | ['http://...', ...]

    Included schemes:
      http/https  — direct video hosts and debrid-resolvable hosters
      magnet:     — BitTorrent magnets; Real-Debrid can resolve cached torrents
                    to HTTP streams via resolveurl.  Previously these were
                    silently dropped, meaning Real-Debrid magnet resolution
                    was never attempted.

    Non-URI values (empty strings, 'search', 'file://', 'plugin://') are dropped
    since they require infrastructure not available in this integration.
    """
    if not raw_link:
        return []
    candidates = [raw_link] if isinstance(raw_link, str) else list(raw_link)
    result = []
    for c in candidates:
        if not c or not c.strip():
            continue
        clean = _strip_label_suffix(c)
        # Keep any valid URI — http, https, magnet, etc.
        # Specifically exclude file:// and plugin:// (require WR infrastructure)
        if _URI_SCHEME_RE.match(clean) and not clean.startswith(('file://', 'plugin://')):
            result.append(clean)
    return result


# ---------------------------------------------------------------------------
# Debrid resolution
# ---------------------------------------------------------------------------
# Strategy:
#   Pass 1 — resolveurl on each candidate.
#             valid_url() is True only for supported hosters.
#             resolve() returns a string URL or ResolvedURL object — both handled.
#             First successful resolution wins immediately.
#   Pass 2 — direct video URL (recognisable extension, no debrid needed).
#   Pass 3 — first HTTP URL regardless of extension (let Kodi try it).
#
# All outcomes logged at LOGINFO — visible without debug mode.
# This is the primary way to confirm debrid is actually firing vs. falling back.

_DIRECT_VIDEO_EXTS = (
    '.mp4', '.mkv', '.avi', '.ts', '.m3u8', '.mpd', '.mov', '.wmv', '.flv', '.webm'
)


def _url_from_resolved(resolved):
    """
    Extract a plain URL string from a resolveurl result.

    resolveurl.resolve() may return:
      - A plain string URL (all versions, most common)
      - A ResolvedURL object with a .uri attribute (newer builds)
      - None / False / empty string (resolution failed)

    If ResolvedURL carries headers, they are embedded using Kodi's native
    pipe format: 'http://stream-url|User-Agent=...&Referer=...'
    Kodi's internal HTTP handler parses this automatically.

    Returns '' on failure.
    """
    if not resolved:
        return ''
    if isinstance(resolved, str):
        return resolved

    # ResolvedURL object (newer resolveurl)
    if hasattr(resolved, 'uri'):
        uri = resolved.uri or ''
        if not uri:
            return ''
        headers = getattr(resolved, 'headers', None)
        if headers and isinstance(headers, dict):
            header_str = '&'.join('{}={}'.format(k, v) for k, v in headers.items())
            return '{}|{}'.format(uri, header_str)
        return uri

    # Last resort — stringify (should not normally be reached)
    s = str(resolved).strip()
    return s if s not in ('', 'None', 'False') else ''


def resolve_best_link(links):
    """
    Find the best playable URL from a list of candidate links.

    Returns (url: str, via_debrid: bool).
    url is None if nothing usable was found.

    All three passes and their outcomes are logged at LOGINFO so the
    debrid chain is always visible in the Kodi log without debug mode.
    """
    if not links:
        log('resolve_best_link: empty link list', xbmc.LOGWARNING)
        return None, False

    log('resolve_best_link: {} candidate(s)'.format(len(links)), xbmc.LOGINFO)
    for i, l in enumerate(links):
        log('  [{}] {}'.format(i, l[:80]), xbmc.LOGINFO)

    # Pass 1: debrid via resolveurl
    if _RESOLVEURL_OK:
        for link in links:
            try:
                hmf = resolveurl.HostedMediaFile(link)
                if not hmf.valid_url():
                    log('  resolveurl: not a supported host — {}'.format(link[:60]),
                        xbmc.LOGINFO)
                    continue
                resolved = hmf.resolve()
                stream_url = _url_from_resolved(resolved)
                if stream_url:
                    log('  resolveurl: DEBRID OK — {} -> {}...'.format(
                        link[:40], stream_url[:40]), xbmc.LOGINFO)
                    return stream_url, True
                log('  resolveurl: resolve() returned empty for {}'.format(link[:60]),
                    xbmc.LOGWARNING)
            except Exception as e:
                log('  resolveurl: exception on {}: {}'.format(link[:50], e),
                    xbmc.LOGWARNING)
    else:
        log('resolve_best_link: resolveurl not available — debrid skipped',
            xbmc.LOGWARNING)

    # Pass 2: direct video URL
    for link in links:
        url_path = link.split('?')[0].lower()
        if any(url_path.endswith(ext) for ext in _DIRECT_VIDEO_EXTS):
            log('  DIRECT video link (pass 2): {}'.format(link[:60]), xbmc.LOGINFO)
            return link, False

    # Pass 3: first HTTP URL
    for link in links:
        if link.startswith('http'):
            log('  FALLBACK HTTP link (pass 3): {}'.format(link[:60]), xbmc.LOGINFO)
            return link, False

    log('resolve_best_link: no usable URL in candidate list', xbmc.LOGWARNING)
    return None, False
