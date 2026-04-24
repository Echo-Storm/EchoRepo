"""
resources/lib/wrestling.py
Wrestling Rewind data layer for Echo OnDemand  v2.1.0

Responsibilities (data only — no Kodi UI, no xbmcplugin, no xbmcgui):
  - Fetch MicroJen XML/JSON feeds over HTTP
  - Parse them into normalised item dicts
  - Cache raw feed text to the addon profile directory
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

MicroJen XML format reference:
  <xml>
    <dir>
      <title>...</title>
      <link>https://...</link>
      <thumbnail>...</thumbnail>
      <fanart>...</fanart>
    </dir>
    <item>
      <title>...</title>
      <link>https://...</link>       <!-- single, or omitted when sublinks present -->
      <sublink>url1(Label)</sublink> <!-- zero or more; presence overrides <link> -->
      <sublink>url2(Label)</sublink>
      <thumbnail>...</thumbnail>
      <fanart>...</fanart>
      <summary>...</summary>
    </item>
  </xml>

MicroJen JSON format reference:
  {"items": [
    {"type": "dir",  "title": "...", "link": "...", "thumbnail": "...", "fanart": "..."},
    {"type": "item", "title": "...", "link": "..." | [...], "thumbnail": "...", "summary": "..."}
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
             'debrid resolution unavailable. Install resolveurl and configure '
             'your debrid account.', xbmc.LOGERROR)

_LOG_TAG = '[EchoOD/Wrestling]'
_FETCH_TIMEOUT = 15  # seconds — generous for slower mirrors


def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log('{} {}'.format(_LOG_TAG, msg), level)


# ---------------------------------------------------------------------------
# Cache — raw feed text, keyed by URL
# ---------------------------------------------------------------------------
# Stores the raw response text (not parsed items) so that a future parse-logic
# fix benefits from already-cached data without re-fetching.
# Uses the same profile-directory pattern as the rest of echoondemand.
# Cache files are named  wr_<url-hash>.json  to avoid filesystem issues with
# long or special-character URLs.

def _cache_filename(url):
    """Derive a safe, stable filename from a URL. Max 120 chars of sanitised URL."""
    safe = re.sub(r'[^a-zA-Z0-9]', '_', url)[:120]
    return 'wr_{}.json'.format(safe)


def cache_load(profile_dir, url, ttl_secs):
    """
    Return cached feed text for url, or None if absent/expired.
    ttl_secs is the maximum acceptable age in seconds.
    """
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
        log('Cache expired: {} (age {:.0f}s, ttl {}s)'.format(url[:60], age, ttl_secs))
    except Exception as e:
        log('Cache read error for {}: {}'.format(url[:60], e), xbmc.LOGWARNING)
    return None


def cache_save(profile_dir, url, text):
    """Persist raw feed text to the cache file for url."""
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
    Raises ValueError if response cannot be decoded.
    Caller is responsible for catching and handling these.
    """
    log('Fetching: {}'.format(url))
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Kodi/EchoOnDemand'}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
        raw = resp.read()
    # Detect encoding from HTTP Content-Type if available, else fall back to UTF-8.
    try:
        return raw.decode('utf-8', errors='ignore')
    except Exception:
        return raw.decode('latin-1', errors='ignore')


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

# Matches a bare & that is NOT the start of an XML character or named entity
# reference.  Examples:
#   &amp;   -> no match (already escaped)
#   &#160;  -> no match (numeric entity)
#   &#xA0;  -> no match (hex entity)
#   &foo;   -> no match (named entity)
#   &       -> match  (bare ampersand in URL, text, etc.)
_BARE_AMP_RE = re.compile(r'&(?!(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]\w*);)')


def _escape_bare_amps(text):
    """
    Escape only bare & characters in XML text — those not already part of a
    valid entity reference.  This is the correct fix for the problem that
    WR's own xml_parser.py works around by blindly replacing ALL & (which
    double-escapes things like &amp; → &amp;amp;).
    """
    return _BARE_AMP_RE.sub('&amp;', text)


def _strip_preamble(text):
    """
    Remove content that appears before the actual <xml> element in WR feeds.

    WR XML files begin with one or more of:
      <?xml version="1.0"?>                     <- processing instruction
      <layouttype>Go Away Nosey</layoutype>      <- deliberate obfuscation (note typo)
      <!-- comments -->                          <- XML comments

    All of these must be stripped before ET.fromstring() will accept the input.
    The layouttype close tag has a documented typo ('layoutype' vs 'layouttype')
    so both spellings are handled.
    """
    # Processing instructions: <?...?>
    text = re.sub(r'<\?[^?]*\?>', '', text, flags=re.IGNORECASE)
    # layouttype block (with close-tag typo tolerance)
    text = re.sub(r'<layouttype[^>]*>.*?</layouty?pe>', '', text,
                  flags=re.DOTALL | re.IGNORECASE)
    # XML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    return text.strip()


def _parse_element(element):
    """
    Convert one <dir> or <item> ET.Element into a normalised item dict.

    Sublinks become result['link'] as a list, overriding any plain <link> text.
    Tags are lowercased for consistency.

    IMPORTANT: In WR feeds, <sublink> elements are often NESTED INSIDE <link>
    rather than being direct children of <item>.  The structure looks like:

        <item>
          <title>...</title>
          <link>
            <sublink>https://host1.com/file.mkv(Label)</sublink>
            <sublink>https://host2.com/file.mkv(Label)</sublink>
          </link>
          <thumbnail>...</thumbnail>
        </item>

    A flat `for child in element` loop would find <link> as a direct child
    but its text content is None/empty (because it has child elements).
    The <sublink> grandchildren would never be reached.

    Solution: after the flat pass (which handles <sublink> as direct children
    and captures the plain-text <link> value as a fallback), do a recursive
    subtree search — element.findall('.//sublink') — identical to the approach
    in WR's own xml_parser.py (_handle_item method).
    """
    result = {'type': element.tag.lower()}
    sublinks = []

    # Flat pass: direct children only.
    # Captures plain-text <link>, <title>, <thumbnail>, <fanart>, <summary>.
    # Also catches <sublink> elements that ARE direct children (some feeds).
    for child in element:
        tag  = child.tag.lower()
        text = (child.text or '').strip()
        if tag == 'sublink':
            if text:
                sublinks.append(text)
        else:
            result[tag] = text

    # Recursive pass: find <sublink> anywhere in the subtree.
    # This catches the common WR pattern where <sublink> is nested inside <link>.
    # Uses the same findall('.//sublink') approach as WR's own parser.
    if not sublinks:
        for sub in element.findall('.//sublink'):
            text = (sub.text or '').strip()
            if text:
                sublinks.append(text)

    # Sublinks (from either pass) override the plain-text <link> value.
    if sublinks:
        result['link'] = sublinks

    # Ensure expected keys are always present (even if empty).
    for key in ('title', 'link', 'thumbnail', 'fanart', 'summary'):
        result.setdefault(key, '')

    return result


def parse_xml(text):
    """
    Parse a MicroJen XML feed.  Returns a list of item dicts (may be empty).
    Never raises — logs warnings on failure and returns [].

    Three-pass progressive recovery:
      Pass 1: strip preamble, try as-is.
      Pass 2: strip preamble + escape bare ampersands.
      Pass 3: as pass 2, but wrap content in a synthetic <root> element in case
              the feed has multiple top-level elements (technically invalid XML).
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
            log('XML parse pass {} failed: {}'.format(attempt, e), xbmc.LOGWARNING)
            continue

        # Collect <dir>/<item> elements.  The feed root may be <xml>, <root>, or
        # something else — iterate one level down regardless of the wrapper tag.
        items = []
        search_in = [root]
        # If root itself is <root> or <xml>, its children are what we want.
        # But if root is directly <dir>/<item> (degenerate feed), catch that too.
        if root.tag.lower() not in ('dir', 'item'):
            # Look one level deeper when children may be <xml><dir>... or just <dir>...
            for child in root:
                if child.tag.lower() in ('dir', 'item'):
                    items.append(_parse_element(child))
                elif child.tag.lower() == 'xml':
                    # Nested <xml> wrapper (pass 3 adds <root> around an existing <xml>)
                    for grandchild in child:
                        if grandchild.tag.lower() in ('dir', 'item'):
                            items.append(_parse_element(grandchild))
        else:
            items.append(_parse_element(root))

        if items:
            log('XML parsed OK on pass {} — {} items'.format(attempt, len(items)))
            return items

    log('All XML parse passes failed — returning empty list', xbmc.LOGWARNING)
    return []


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def parse_json(text):
    """
    Parse a MicroJen JSON feed ({"items": [...]}).
    Returns a list of item dicts (may be empty).  Never raises.

    Each item dict is normalised to match the schema parse_xml() produces:
    missing keys are filled with empty strings.
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
            'type':      raw.get('type', 'item').lower(),
            'title':     (raw.get('title') or '').strip(),
            'link':      raw.get('link', ''),
            'thumbnail': (raw.get('thumbnail') or '').strip(),
            'fanart':    (raw.get('fanart') or '').strip(),
            'summary':   (raw.get('summary') or '').strip(),
        }
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Feed dispatcher
# ---------------------------------------------------------------------------

def parse_feed(url, text):
    """
    Dispatch to parse_xml() or parse_json() based on URL extension and content.

    Detection order:
      1. URL ends with .json  → JSON
      2. Text starts with {   → JSON (content sniff, covers inline JSON)
      3. Otherwise            → XML
    """
    stripped = text.lstrip()
    if url.lower().endswith('.json') or stripped.startswith('{'):
        return parse_json(text)
    return parse_xml(text)


# ---------------------------------------------------------------------------
# Link utilities
# ---------------------------------------------------------------------------

def _strip_label_suffix(link):
    """
    Strip optional trailing (Label) from a WR link string.

    WR encodes human-readable labels as a suffix on the URL itself:
      'http://example.com/file.mkv(720p via DebridHost)'
    becomes:
      'http://example.com/file.mkv'

    Only strips if the result still looks like a URL.  A link that
    starts with 'http' after stripping is considered valid.
    """
    link = link.strip()
    if link.endswith(')') and '(' in link:
        candidate = link.rsplit('(', 1)[0].strip()
        if candidate.startswith('http'):
            return candidate
    return link


def normalise_links(raw_link):
    """
    Normalise the link field from a parsed item dict into a flat list of
    clean URLs with label suffixes stripped.

    raw_link may be:
      ''            -> []
      'http://...'  -> ['http://...']
      ['http://...', 'http://...']  -> both, cleaned

    Only HTTP(S) URLs are included — file://, plugin://, search, etc. are
    dropped since they require infrastructure we don't have in this context.
    """
    if not raw_link:
        return []
    candidates = [raw_link] if isinstance(raw_link, str) else list(raw_link)
    result = []
    for c in candidates:
        if not c or not c.strip():
            continue
        clean = _strip_label_suffix(c)
        if clean.startswith('http'):
            result.append(clean)
    return result


# ---------------------------------------------------------------------------
# Debrid resolution — the core of the integration
# ---------------------------------------------------------------------------
# Strategy:
#   Pass 1 — try resolveurl on every candidate URL.
#             resolveurl.HostedMediaFile(url).valid_url() returns True if the
#             URL is from a host that resolveurl (and thus the configured debrid
#             account) can resolve.  .resolve() returns the direct stream URL.
#             First successful resolution wins immediately.
#   Pass 2 — none of the links were resolvable via debrid.
#             Return the first URL that has a recognisable video extension as a
#             direct-play fallback.
#   Pass 3 — nothing matched either pass.  Return the first HTTP URL and let
#             Kodi try it; worst case Kodi shows an error, which is the correct
#             behaviour when there's genuinely no playable link.
#
# Returning (url, via_debrid) lets the caller log/debug without cluttering this
# function with UI concerns.

_DIRECT_VIDEO_EXTS = (
    '.mp4', '.mkv', '.avi', '.ts', '.m3u8', '.mpd', '.mov', '.wmv', '.flv', '.webm'
)


def resolve_best_link(links):
    """
    Find the best playable URL from a list of candidate links.

    Returns:
      (url: str, via_debrid: bool)  — url is None if nothing usable was found.

    Debrid is always attempted first.  Direct play is a silent fallback.
    """
    if not links:
        return None, False

    # Pass 1: debrid
    if _RESOLVEURL_OK:
        for link in links:
            try:
                hmf = resolveurl.HostedMediaFile(link)
                if not hmf.valid_url():
                    continue
                resolved = hmf.resolve()
                if resolved:
                    log('Debrid resolved: {} -> {}'.format(link[:50], resolved[:50]))
                    return resolved, True
            except Exception as e:
                log('resolveurl error on {}: {}'.format(link[:50], e), xbmc.LOGWARNING)
    else:
        log('resolveurl unavailable — skipping debrid pass', xbmc.LOGWARNING)

    # Pass 2: direct video URL (recognisable extension)
    for link in links:
        url_path = link.split('?')[0].lower()
        if any(url_path.endswith(ext) for ext in _DIRECT_VIDEO_EXTS):
            log('Direct video link: {}'.format(link[:60]))
            return link, False

    # Pass 3: first HTTP URL, whatever it is
    for link in links:
        if link.startswith('http'):
            log('Fallback to first HTTP link: {}'.format(link[:60]))
            return link, False

    log('No usable link found in: {}'.format(links), xbmc.LOGWARNING)
    return None, False
